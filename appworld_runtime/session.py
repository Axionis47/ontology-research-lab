"""Own one fresh native world and its official MCP connection per episode."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from appworld_runtime.rpc import request
from react_runtime.loop import Tool

ROOT = Path(__file__).resolve().parents[1]


class AppWorldSession:
    def __init__(self, *, root: Path, task_id: str, application: str, experiment: str,
                 log_directory: Path, timeout: float = 90, max_api_calls: int = 512):
        self.root, self.task_id, self.application = root.resolve(), task_id, application
        self.experiment, self.logs, self.timeout = experiment, log_directory, timeout
        self.directory = None
        if type(max_api_calls) is not int or max_api_calls < 1: raise ValueError("Invalid native API budget")
        self.max_api_calls = max_api_calls
        self.process = None

    def __enter__(self):
        self.logs.mkdir(parents=True, exist_ok=False)
        self.directory = tempfile.TemporaryDirectory(prefix="aw-", dir="/tmp")
        self.address = str(Path(self.directory.name) / "session.sock")
        self.output = (self.logs / "session.log").open("wb")
        env = {**os.environ, "APPWORLD_ROOT": str(self.root),
               "APPWORLD_CACHE": str(self.root / ".cache"),
               "IPYTHONDIR": str(self.root / ".ipython"),
               "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")}
        command = [sys.executable, "-m", "appworld_runtime.worker", "--socket", self.address,
                   "--task-id", self.task_id, "--application", self.application,
                   "--experiment", self.experiment, "--logs", str(self.logs.resolve()), "--max-api-calls", str(self.max_api_calls)]
        try:
            self.process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=self.output,
                                            stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + self.timeout
            while not Path(self.address).exists():
                if self.process.poll() is not None:
                    raise RuntimeError(f"AppWorld session failed; see {self.logs / 'session.log'}")
                if time.monotonic() >= deadline:
                    raise TimeoutError("AppWorld session initialization timed out")
                time.sleep(0.05)
            self.info = request(self.address, "info", timeout=self.timeout)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def tools(self) -> list[Tool]:
        client = str(ROOT / "appworld_runtime/tool_client.py")
        object_output = {"type": "object"}
        def tool(name, description, method, properties, required=(), effect="READ"):
            return Tool(name, description,
                        {"type": "object", "properties": properties, "required": list(required),
                         "additionalProperties": False},
                        [sys.executable, client, self.address, method], object_output,
                        timeout_seconds=90, effect=effect)
        return [
            tool("discover_tools", "Search the MCP tool catalog by words, or page through it. Returns names and descriptions. Inspect a tool before calling it.",
                 "discover", {"query": {"type": "string", "maxLength": 200},
                              "offset": {"type": "integer", "minimum": 0},
                              "strategy": {"oneOf": [{"enum": ["legacy", "exact", "weighted"]},
                                  {"type": "object", "properties": {"name_weight": {"type": "integer", "minimum": 1, "maximum": 8},
                                   "description_weight": {"type": "integer", "minimum": 0, "maximum": 4}},
                                   "required": ["name_weight", "description_weight"], "additionalProperties": False}]},
                              "limit": {"type": "integer", "minimum": 1, "maximum": 10}}),
            tool("inspect_tool", "Get one discovered MCP tool's input/output schemas and description.",
                 "describe", {"name": {"type": "string", "maxLength": 200}}, ("name",)),
            tool("call_tool", "Call a discovered MCP tool with arguments matching its inspected schema. This can change the simulated world. A completion marker is not an evaluation score.",
                 "call", {"name": {"type": "string", "maxLength": 200},
                          "arguments": {"type": "object"}}, ("name", "arguments"), "WRITE"),
        ]

    def evaluate(self) -> dict:
        return request(self.address, "evaluate", timeout=120)

    def __exit__(self, *_):
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    request(self.address, "close", timeout=5)
                    self.process.wait(timeout=5)
                except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
                    pass
            # A worker interrupted during a call may leave an API/MCP child.
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=3)
        if hasattr(self, "output"):
            self.output.close()
        if self.directory is not None:
            self.directory.cleanup()

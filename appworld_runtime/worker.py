"""Isolated native environment owner; all actor API execution goes through MCP."""

from __future__ import annotations

import argparse
import contextlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback

from jsonschema import ValidationError

from appworld_runtime.catalog import Catalog
from appworld_runtime.credentials import SessionCredentials
from appworld_runtime.rpc import receive


def launch_api_server(logs: Path):
    import requests
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    output = (logs / "api-server.log").open("wb")
    # Array arguments preserve workspace paths containing spaces. Bind only localhost.
    command = [sys.executable, "-m", "uvicorn", "appworld.serve._apis:app",
               "--host", "127.0.0.1", "--port", str(port), "--workers", "1"]
    process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 60
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Native API server failed; inspect api-server.log")
            try:
                if requests.get(url, timeout=0.5).status_code < 500:
                    return process, output, url
            except requests.RequestException:
                pass
            time.sleep(0.1)
        raise TimeoutError("Native API server did not start")
    except BaseException:
        process.terminate()
        process.wait(timeout=5)
        output.close()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--application", required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--logs", type=Path, required=True)
    parser.add_argument("--max-api-calls", type=int, default=512)
    args = parser.parse_args()
    from appworld import AppWorld
    from appworld.serve._mcp import MCPClient

    process, log, url = launch_api_server(args.logs)
    try:
        with contextlib.ExitStack() as stack:
            # Retain native defaults, evaluation and task state. The actor is a
            # text-only CLI and has no interface to this lifecycle controller.
            world = stack.enter_context(AppWorld(task_id=args.task_id,
                experiment_name=args.experiment, remote_apis_url=url))
            mcp = MCPClient.from_dict({"type": "stdio",
                "app_names": [args.application, "supervisor"], "remote_apis_url": url})
            mcp.params.env = {**(mcp.params.env or {}),
                             **{k: os.environ[k] for k in ("APPWORLD_ROOT", "APPWORLD_CACHE", "IPYTHONDIR")}}
            mcp = stack.enter_context(mcp)
            catalog = Catalog(mcp.list_tools(), args.application)
            credentials = SessionCredentials(args.application, catalog)
            (args.logs / "mcp-catalog.json").write_text(json.dumps(catalog.tools, indent=2))
            public = {"instruction": world.task.instruction,
                      "supervisor": dict(world.task.supervisor),
                      "task_datetime": world.task.datetime.isoformat(),
                      "application": args.application, "appworld_version": version("appworld"),
                      "mcp_version": version("mcp"), "catalog_revision": catalog.revision,
                      "catalog_size": len(catalog.tools), "db_version": world.task.db_version,
                      "native_output_directory": str(Path(world.output_directory).resolve())}
            evaluated = False
            api_calls = 0
            inspected = set()
            def record(event: dict) -> None:
                with (args.logs / "mcp-transcript.jsonl").open("a") as stream:
                    stream.write(json.dumps(event, allow_nan=False) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(args.socket)
                os.chmod(args.socket, 0o600)
                server.listen(1)
                while True:
                    connection, _ = server.accept()
                    with connection:
                        connection.settimeout(150)
                        close = False
                        call_dispatched = False
                        try:
                            message = receive(connection)
                            method, params = message["method"], message.get("arguments", {})
                            if method == "info":
                                result = {**public, "api_calls": api_calls, "max_api_calls": args.max_api_calls}
                            elif method == "close":
                                close, result = True, {"closed": True}
                            elif method == "evaluate":
                                evaluated = True
                                # MCP calls change server memory; save is mandatory
                                # before the native database-state evaluator runs.
                                world.save()
                                tracker = world.evaluate()
                                result = {"status": "EVALUATED", "task_completed": world.task_completed(),
                                          "native_result": tracker.to_dict(stats_only=False),
                                          "native_output_directory": public["native_output_directory"]}
                            elif evaluated:
                                raise ValueError("Episode is closed for actor operations after evaluation")
                            elif method == "bind_credentials":
                                result = credentials.bind(**params)
                                (args.logs / "credential-binding.json").write_text(json.dumps(result))
                            elif method == "discover":
                                result = catalog.discover(**params)
                            elif method == "describe":
                                result = credentials.describe(**params)
                                inspected.add(params["name"])
                            elif method == "call":
                                name, arguments = params["name"], params["arguments"]
                                if name not in inspected:
                                    raise ValueError("Inspect the tool schema before calling it")
                                arguments, managed_fields = credentials.prepare(name, arguments)
                                catalog.validate_call(name, arguments)
                                if api_calls >= args.max_api_calls:
                                    raise ValueError("Native API call budget exhausted")
                                api_calls += 1
                                record({"event": "call_started", "call_id": api_calls, "name": name, "arguments": arguments,
                                        "catalog_revision": catalog.revision, "managed_session_fields": managed_fields})
                                async def invoke():
                                    response = await mcp.session.call_tool(name, arguments=arguments)
                                    return response.model_dump(mode="json", by_alias=True)
                                call_dispatched = True
                                response = mcp._submit_coroutine(invoke())
                                record({"event": "call_result", "call_id": api_calls, "name": name, "result": response})
                                world.save()
                                result = {"tool": name, "catalog_revision": catalog.revision,
                                          "mcp_result": response, "task_completed": world.task_completed()}
                            else:
                                raise ValueError("Unknown session operation")
                        except (KeyError, ValueError, TypeError, ValidationError) as error:
                            if call_dispatched:
                                # The API may already have changed state. A decode,
                                # receipt or save failure cannot invite a retry.
                                traceback.print_exc()
                                result = {"session_error": f"{type(error).__name__}: {error}"}
                            else:
                                result = {"rejected": True, "error": type(error).__name__, "message": str(error)[:1500]}
                        except Exception as error:
                            traceback.print_exc()
                            result = {"session_error": f"{type(error).__name__}: {error}"}
                        try:
                            connection.sendall((json.dumps(result, allow_nan=False) + "\n").encode())
                        except (BrokenPipeError, ConnectionResetError):
                            # The caller may have exhausted its deadline after an
                            # effect. Stop this owner rather than accept more calls.
                            return
                        if close:
                            return
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run the first ReAct component against local read-only fixtures, without a benchmark adapter."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from react_runtime.loop import Config, ReactLoop, Tool
from react_runtime.store import RunStore


def fixture_tool(padding: int = 0) -> Tool:
    return Tool("get_record", "Read a local synthetic record by ID. Returns status, proof, and padding.",
                {"type": "object", "properties": {"record_id": {"type": "string", "minLength": 1, "maxLength": 20}},
                 "required": ["record_id"], "additionalProperties": False},
                [sys.executable, str(ROOT / "react_runtime/fixtures.py"), "record", "--padding", str(padding)],
                {"type": "object", "properties": {key: {"type": "string"} for key in ("record_id", "status", "proof", "padding")},
                 "required": ["record_id", "status", "proof", "padding"], "additionalProperties": False})


def verify_short(proposal: dict, results: list[dict]) -> tuple[bool, str]:
    observed = any(r["action"] == "get_record" and r["arguments"] == {"record_id": "123"}
                   and r["result"]["status"] == "delivered" for r in results)
    passed = observed and proposal["answer"].strip() == "delivered"
    return passed, "Verified recorded status." if passed else "Read record 123 and return exactly its observed status."


def verify_long(proposal: dict, results: list[dict]) -> tuple[bool, str]:
    records = {}
    for result in results:
        if result["action"] == "get_record":
            records.setdefault(result["arguments"]["record_id"], result)
    needed = {f"r{i}" for i in range(1, 6)}
    if not needed.issubset(records):
        return False, f"Still need records: {sorted(needed - records.keys())}"
    first = records["r1"]
    reread = any(r["action"] == "read_output" and r["arguments"].get("output_id") == first["output_id"]
                 and r["arguments"].get("json_pointer") == "/proof"
                 and r["step"] > max(records[key]["step"] for key in needed)
                 and r["result"].get("start") == 0 and r["result"].get("next_start") is None
                 and r["result"].get("content") == json.dumps(first["result"]["proof"], ensure_ascii=False)
                 for r in results)
    passed = reread and proposal["answer"].strip() == first["result"]["proof"]
    return passed, "Verified original r1 output after later reads." if passed else "After all five records, use read_output on the ORIGINAL r1 result at /proof, start 0; read the whole value and return exactly it."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["ollama", "gemini", "scripted"], default="ollama")
    parser.add_argument("--fixture", choices=["short", "compaction"], default="short")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--max-steps", type=int, help="Override the recorded step budget for a bounded smoke run")
    args = parser.parse_args()
    models = tomllib.loads((ROOT / "config/models.toml").read_text())
    settings = tomllib.loads((ROOT / "config/react_loop.toml").read_text())
    if args.max_steps is not None:
        settings["max_steps"] = args.max_steps
    long = args.fixture == "compaction"
    if long:
        settings["max_context_chars"] = 11000
    info = {"provider": args.provider, "resolved_model": None, "benchmark": False}
    if args.provider == "ollama":
        executable = shutil.which("ollama")
        if not executable:
            raise SystemExit("Configured Ollama CLI is not installed")
        selected = models["ollama"]
        command = [sys.executable, str(ROOT / "react_runtime/ollama.py")]
        info.update({"requested_model": selected["model"], "transport": "ollama-http/1",
                     "applied_options": {k: selected[k] for k in ("num_ctx", "num_predict", "temperature", "think")}})
    elif args.provider == "gemini":
        selected = models["gemini"]
        executable = shutil.which(selected["executable"])
        if not executable:
            raise SystemExit("Configured Gemini CLI is not installed")
        command = [executable, "--extensions", "none", "--allowed-mcp-server-names", "model-check-no-servers",
                   "--policy", str(ROOT / selected["policy"]), "--skip-trust", "--output-format", "json", "--prompt", "{prompt}"]
        info["model_selection"] = "Inherited from configured CLI; no model override"
    else:
        executable = sys.executable
        command = [executable, str(ROOT / "react_runtime/fixtures.py"), "scripted"] + (["--long"] if long else [])
        info["note"] = "Deterministic scripted fixture, not a model or benchmark result"
    if args.provider != "scripted":
        version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=15)
        info["cli_version"] = version.stdout.strip() or "unavailable"
    info["command_template"] = command
    directory = args.output_dir or ROOT / "runs/react" / str(uuid.uuid4())
    store = RunStore(directory)
    try:
        task = ("Read records r1, r2, r3, r4, r5 with get_record. Then use read_output on the original r1 output, "
                "JSON pointer /proof. Finish with exactly that proof value.") if long else (
                "Use get_record to inspect record 123. Finish with exactly its observed status.")
        loop = ReactLoop(store=store, task=task, constraints=["Do not modify any record."],
                         model_command=command, tools=[fixture_tool(6000 if long else 0)],
                         verifier=verify_long if long else verify_short, config=Config(**settings),
                         provider=args.provider, model_info=info)
        result = loop.run()
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "VERIFIED_SUCCESS" and result["judge_packet"]["complete"] else 1
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())

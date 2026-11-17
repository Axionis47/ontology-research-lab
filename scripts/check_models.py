#!/usr/bin/env python3
"""Small live model checks, independent of the planned agent implementation."""

import argparse
import ast
import json
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_object(text):
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = "\n".join(text.splitlines()[1:-1])
    value = json.loads(text)
    require(isinstance(value, dict), "Expected a JSON object")
    return value


def ollama_request(config, messages, **extra):
    payload = {
        "model": config["model"],
        "messages": messages,
        "stream": False,
        "think": config["think"],
        "options": {key: config[key] for key in ("num_ctx", "num_predict", "temperature")},
        **extra,
    }
    request = urllib.request.Request(
        config["base_url"].rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=config["timeout_seconds"]) as response:
        result = json.load(response)
    require(result.get("done") is True, "Ollama did not finish the response")
    require(result.get("done_reason") != "length", "Ollama output was truncated")
    require(result.get("model") == config["model"], "Unexpected Ollama model")
    return result


def usage(result):
    return {key: result.get(key) for key in (
        "model", "prompt_eval_count", "eval_count", "total_duration", "load_duration"
    )}


def check_ollama(config):
    greeting = ollama_request(config, [{"role": "user", "content": "Reply with exactly MODEL_OK."}])
    require(greeting["message"]["content"].strip() == "MODEL_OK", "Text response mismatch")
    yield "text", {"response": greeting["message"]["content"], "usage": usage(greeting)}

    schema = {
        "type": "object",
        "properties": {"order_id": {"type": "integer"}, "status": {"type": "string"}},
        "required": ["order_id", "status"],
        "additionalProperties": False,
    }
    result = ollama_request(config, [{"role": "user", "content":
        'Return JSON for order 123, whose status is delivered. Use order_id and status.'
    }], format=schema)
    data = parse_object(result["message"]["content"])
    require(data == {"order_id": 123, "status": "delivered"}, "Structured response mismatch")
    yield "structured_json", {"response": data, "usage": usage(result)}

    tool = {"type": "function", "function": {
        "name": "inspect_order",
        "description": "Look up an order's current status. Use this instead of guessing.",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "integer"}},
                       "required": ["order_id"], "additionalProperties": False},
    }}
    messages = [{"role": "user", "content":
        "Use inspect_order to check order 123. After the tool responds, reply with only its status."
    }]
    first = ollama_request(config, messages, tools=[tool])
    calls = first["message"].get("tool_calls", [])
    require(len(calls) == 1, "Expected exactly one native tool call")
    call = calls[0]["function"]
    require(call["name"] == "inspect_order" and call["arguments"] == {"order_id": 123},
            "Incorrect tool name or arguments")
    messages.extend([first["message"], {
        "role": "tool", "tool_name": "inspect_order",
        "content": json.dumps({"order_id": 123, "status": "delivered"}),
    }])
    second = ollama_request(config, messages, tools=[tool])
    require(not second["message"].get("tool_calls"), "Model repeated the tool call")
    require(second["message"]["content"].strip().lower() == "delivered", "Tool result was not used")
    yield "native_tool_round_trip", {
        "call": call, "response": second["message"]["content"],
        "usage": [usage(first), usage(second)], "environment": "synthetic read-only fixture",
    }


def gemini_request(config, prompt):
    executable = shutil.which(str(Path(config["executable"]).expanduser()))
    require(executable is not None, "Gemini CLI is not on PATH")
    command = [
        executable, "--extensions", "none",
        "--allowed-mcp-server-names", "model-check-no-servers",
        "--policy", str(ROOT / config["policy"]), "--output-format", "json",
        "--skip-trust", "--prompt", prompt,
    ]
    completed = subprocess.run(command, cwd=ROOT, input="", capture_output=True,
                               text=True, timeout=config["timeout_seconds"])
    if completed.returncode:
        # Do not persist arbitrary CLI stderr, which might contain authentication details.
        if "UNSUPPORTED_CLIENT" in completed.stderr:
            raise RuntimeError("Gemini CLI default call was rejected by Google: UNSUPPORTED_CLIENT for the existing saved login")
        raise RuntimeError(f"Gemini CLI exited {completed.returncode}; inspect authentication/model availability")
    result = parse_object(completed.stdout)
    require(not result.get("error"), "Gemini CLI returned an error")
    stats = result.get("stats", {})
    require(stats.get("tools", {}).get("totalCalls", 0) == 0, "Model probe unexpectedly used a tool")
    models = stats.get("models", {})
    require(bool(models), "CLI did not report which models were used")
    return result


def check_gemini(config):
    executable = str(Path(config["executable"]).expanduser())
    version = subprocess.run([executable, "--version"], capture_output=True,
                             text=True, timeout=30, check=True).stdout.strip()
    yield "cli_version", {"version": version, "executable": shutil.which(executable),
                          "model_selection": "inherited from CLI; no model override"}
    result = gemini_request(config, "Do not use tools. Reply with exactly MODEL_OK and nothing else.")
    require(result.get("response", "").strip() == "MODEL_OK", "Gemini text response mismatch")
    yield "authenticated_inference", {"response": result["response"], "stats": result.get("stats")}

    prompt = (
        "Do not use tools or modify files. Return only a JSON object with one key, code. "
        "Repair this Python function: def within_limit(amount, limit): return amount < limit. "
        "The rule is inclusive: an amount equal to the limit is allowed. "
        "Return only the corrected function in code, with the same name and arguments, "
        "a single return statement, no annotations, no docstring, and no extra statements."
    )
    result = gemini_request(config, prompt)
    code = parse_object(result["response"])["code"]
    expected = ast.parse("def within_limit(amount, limit):\n    return amount <= limit\n")
    require(ast.dump(ast.parse(code)) == ast.dump(expected), "Repair did not produce the required inclusive comparison")
    # Check the exact expected AST; do not execute model-generated code during setup.
    yield "structured_code_repair", {
        "code": code, "validation": "Exact expected Python AST; generated code not executed",
        "stats": result.get("stats"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["ollama", "gemini", "all"], default="all")
    args = parser.parse_args()
    config = tomllib.loads((ROOT / "config/models.toml").read_text())
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "checks": [], "passed": True}
    providers = ["ollama", "gemini"] if args.provider == "all" else [args.provider]
    for provider in providers:
        started = time.monotonic()
        try:
            checks = check_ollama(config[provider]) if provider == "ollama" else check_gemini(config[provider])
            for name, detail in checks:
                report["checks"].append({"provider": provider, "check": name, "passed": True, **detail})
                print(f"PASS {provider}: {name}", flush=True)
        except Exception as error:
            report["passed"] = False
            report["checks"].append({"provider": provider, "passed": False, "error": f"{type(error).__name__}: {error}"})
            print(f"FAIL {provider}: {error}", flush=True)
        report.setdefault("elapsed_seconds", {})[provider] = round(time.monotonic() - started, 2)
    directory = ROOT / "runs/model-checks"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"{stamp}-{args.provider}.json"
    text = json.dumps(report, indent=2) + "\n"
    path.write_text(text)
    (directory / f"latest-{args.provider}.json").write_text(text)
    print(f"Report: {path}", flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

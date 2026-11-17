#!/usr/bin/env python3
"""Ten bounded, inspectable Gemini CLI lessons. Never executes model-written code."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value, key=None):
    """Compare JSON types exactly; answer sets unordered, triple positions ordered."""
    if isinstance(value, dict):
        return {k: canonical(v, k) for k, v in sorted(value.items())}
    if isinstance(value, list):
        items = value if key in {"positive_triples", "negative_sentence_positive_triples"} else [canonical(v) for v in value]
        return sorted(items, key=lambda v: json.dumps(v, sort_keys=True))
    return value


def equal(actual, expected):
    return json.dumps(canonical(actual), sort_keys=True) == json.dumps(canonical(expected), sort_keys=True)


def check_answer(actual, expected, number, data):
    fields = {key: key in actual and equal(actual[key], value) if key not in {"positive_triples", "negative_sentence_positive_triples"}
              else key in actual and equal({key: actual[key]}, {key: value})
              for key, value in expected.items()}
    checks = {"exact_keys": set(actual) == set(expected), "fields": fields}
    # This is a trusted miniature executor. Gemini cannot set its allow flag.
    if number == "07":
        effects = {}
        for case in ("A", "B"):
            proposal = actual.get(case)
            valid = equal(proposal, expected[case])
            approval = data["input"]["cases"][case]["approval"]
            allowed = (valid and approval is not None and approval.get("current") is True
                       and bool(approval.get("source"))
                       and approval.get("service") == "LoginService"
                       and approval.get("environment") == "Production")
            effects[case] = {"before": {"deployed": False}, "admitted": allowed,
                             "after": {"deployed": allowed}, "kind": "local_boolean_fixture"}
        checks["runtime_effects"] = effects
        checks["gate_correct"] = not effects["A"]["admitted"] and effects["B"]["admitted"]
    checks["passed"] = checks["exact_keys"] and all(fields.values()) and checks.get("gate_correct", True)
    return checks


def invoke(command, cwd, timeout):
    process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate("", timeout=timeout)
        return process.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        return 124, "", "TIMEOUT"


def failure_category(code, stderr):
    # Preserve a category/hash, not arbitrary authentication diagnostics.
    for marker in ("UNSUPPORTED_CLIENT", "MODEL_NOT_FOUND", "RESOURCE_EXHAUSTED"):
        if marker in stderr:
            return marker
    if code == 124:
        return "TIMEOUT"
    if any(s in stderr for s in ("EPERM", "Operation not permitted", "EACCES")):
        return "ENVIRONMENT_PERMISSION_ERROR"
    return "CLI_ERROR"


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", default="all", choices=["all"] + [f"{i:02}" for i in range(1, 11)])
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    folders = sorted(p for p in HERE.glob("[0-9][0-9]-*") if p.is_dir()
                     and (args.experiment == "all" or p.name.startswith(args.experiment + "-")))
    config_path = ROOT / "config/models.toml"
    config = tomllib.loads(config_path.read_text())["gemini"]
    policy = ROOT / config["policy"]
    executable = shutil.which(config["executable"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = HERE / "gemini-results" / stamp
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / "empty-workspace"
    workspace.mkdir()
    version = None
    if args.live and executable:
        try:
            version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
        except subprocess.TimeoutExpired:
            version = "VERSION_CHECK_TIMEOUT"
    manifest = {"kind": "synthetic_gemini_teaching_experiments", "created_utc": stamp,
                "live_requested": args.live, "provider": "installed Gemini CLI",
                "role": "teaching_experiment_participant_user_selected",
                "model_selection": "CLI configured default; no override or substitute",
                "cli_version": version, "executable": executable,
                "config_sha256": digest(config_path), "policy_sha256": digest(policy),
                "runner_sha256": digest(Path(__file__)), "timeout_per_call_seconds": config["timeout_seconds"],
                "maximum_cli_invocations": len(folders),
                "context_boundary": "empty working directory, inherited CLI/global configuration, no resumed session",
                "appworld_runs": 0, "native_improvement": False,
                "experiments": []}
    for folder in folders:
        manifest["experiments"].append({"id": folder.name, "source_sha256": {
            name: digest(folder / name) for name in ("gemini-input.json", "gemini-expected.json", "gemini-prompt.txt")}})
    save(output / "manifest.json", manifest)
    halted = None
    rows = []
    for folder in folders:
        number = folder.name[:2]
        prompt = (folder / "gemini-prompt.txt").read_text()
        expected = json.loads((folder / "gemini-expected.json").read_text())
        data = json.loads((folder / "gemini-input.json").read_text())
        receipt = {"experiment": folder.name, "status": "PREPARED_NOT_RUN", "prompt": prompt,
                   "expected_held_out_of_prompt": expected, "reported_models": [], "passed": None}
        save(output / (number + "-receipt.json"), receipt)
        if args.live and halted:
            receipt.update(status="NOT_RUN", reason=halted)
        elif args.live and not executable:
            halted = "GEMINI_CLI_NOT_FOUND"
            receipt.update(status="CLI_UNAVAILABLE", reason=halted)
        elif args.live:
            command = [executable, "--extensions", "none", "--allowed-mcp-server-names", "model-check-no-servers",
                       "--policy", str(policy), "--output-format", "json", "--skip-trust", "--prompt", prompt]
            receipt["status"] = "IN_FLIGHT"
            save(output / (number + "-receipt.json"), receipt)
            code, stdout, stderr = invoke(command, workspace, config["timeout_seconds"])
            receipt.update(exit_code=code, stderr_sha256=hashlib.sha256(stderr.encode()).hexdigest())
            if code:
                halted = failure_category(code, stderr)
                receipt.update(status="CLI_UNAVAILABLE", reason=halted)
            else:
                try:
                    envelope = json.loads(stdout)
                    receipt["cli_response"] = envelope
                    if envelope.get("error"):
                        halted = "CLI_RESPONSE_ERROR"
                        receipt.update(status="CLI_UNAVAILABLE", reason=halted)
                    else:
                        stats = envelope.get("stats", {})
                        receipt["reported_models"] = list(stats.get("models", {}))
                        if not receipt["reported_models"]:
                            raise ValueError("CLI did not report model identity")
                        if stats.get("tools", {}).get("totalCalls", 0) != 0:
                            raise ValueError("Unexpected tool call in no-tools experiment")
                        response = envelope.get("response", "")
                        actual = json.loads(response)
                        if not isinstance(actual, dict):
                            raise ValueError("Expected a JSON object")
                        receipt["checks"] = check_answer(actual, expected, number, data)
                        receipt.update(status="MEASURED", answer=actual, passed=receipt["checks"]["passed"])
                except (ValueError, TypeError, KeyError) as error:
                    receipt.update(status="RESPONSE_INVALID", reason=str(error), passed=False)
                    # Capture successful CLI stdout for inspection even when JSON parsing fails.
                    receipt["raw_stdout"] = stdout
        save(output / (number + "-receipt.json"), receipt)
        rows.append({key: receipt.get(key) for key in ("experiment", "status", "passed", "reason", "reported_models")})
        print(f"{number}: {receipt['status']}" + (f" passed={receipt['passed']}" if receipt['passed'] is not None else ""), flush=True)
        save(output / "summary.json", {"experiments": rows, "complete": False})
    summary = {"kind": manifest["kind"], "live_requested": args.live, "complete": True,
               "all_measured_and_passed": bool(rows) and all(r["status"] == "MEASURED" and r["passed"] is True for r in rows),
               "experiments": rows, "appworld_runs": 0}
    save(output / "summary.json", summary)
    print(f"Receipts: {output}")
    return 0 if not args.live or summary["all_measured_and_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Frozen complex-ontology pilot: six strategies, no automatic run retries."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import shutil
import subprocess
import tomllib
from engine import (RULE_IDS, closure, execute, gate, interfaces, payload, revoked, score, score_details, sha)
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("helpers", HERE.parent / "gemini_experiments.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--experiment", default="all", choices=["all"] + [f"{i:02}" for i in range(1, 7)])
    args = parser.parse_args()
    world = json.loads((HERE / "facts.json").read_text())
    ontology = json.loads((HERE / "ontology.json").read_text())
    folders = sorted(p for p in HERE.glob("[0-9][0-9]-*") if p.is_dir() and (args.experiment == "all" or p.name.startswith(args.experiment + "-")))
    random.Random(20261116).shuffle(folders)
    cfg_path = ROOT / "config/models.toml"
    cfg = tomllib.loads(cfg_path.read_text())["gemini"]
    executable = shutil.which(cfg["executable"])
    policy = ROOT / cfg["policy"]
    out = HERE / "results" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out.mkdir(parents=True)
    workspace = out / "empty-workspace"
    workspace.mkdir()
    version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=30).stdout.strip() if args.live and executable else None
    records = []
    for folder in folders:
        protocol = json.loads((folder / "protocol.json").read_text())
        base = payload(protocol["mode"], world, ontology)
        records.append((folder, protocol, base))
    h.save(out / "manifest.json", {"kind": "same_task_ontology_consumption", "cli_version": version, "live": args.live,
        "facts_sha256": h.digest(HERE / "facts.json"), "ontology_sha256": h.digest(HERE / "ontology.json"),
        "runner_sha256": h.digest(Path(__file__)), "helper_sha256": h.digest(HERE.parent / "gemini_experiments.py"),
        "config_sha256": h.digest(cfg_path), "policy_sha256": h.digest(policy), "max_calls_each": 8, "max_total_cli_calls": 8 * len(records),
        "order_seed": 20261116, "execution_order": [f.name for f, p, b in records],
        "engine_sha256": h.digest(HERE / "engine.py"), "oracle_sha256": h.digest(HERE / "oracle.json"), "retry_policy": "No automatic retries; attempt every method independently once",
        "task_hashes": {f.name: sha(b["task"]) for f, p, b in records}, "initial_fact_hashes": {f.name: sha(b["facts"]) for f, p, b in records},
        "protocol_hashes": {f.name: h.digest(f / "protocol.json") for f, p, b in records}, "appworld_runs": 0,
        "rules": RULE_IDS, "model_selection": "configured CLI routing; no override"})
    stopped = None
    summaries = []
    for folder, protocol, base in records:
        mode = protocol["mode"]
        rec = {"experiment": folder.name, "mode": mode, "status": "PREPARED_NOT_RUN", "initial_payload": base,
               "calls": [], "history": [], "passed": None, "successful_interface_calls": 0,
               "definition_names_exposed": sorted(base.get("definitions", {}))}
        if args.live:
            rec["status"] = "CALL_LIMIT"
            for step in range(8):
                prompt = "Solve the same fixed task using only the supplied facts, ontology and interfaces. Return one JSON object, no Markdown. Do not use CLI tools, read files, or change any external state.\n" + json.dumps({"context": base, "history": rec["history"]}, separators=(",", ":"))
                event = {"step": step, "submitted_prompt": prompt, "user_chars": len(prompt), "status": "IN_FLIGHT"}
                rec["calls"].append(event)
                h.save(out / (folder.name + ".json"), rec)
                if not executable:
                    stopped = "CLI_NOT_FOUND"
                    rec.update(status="CLI_UNAVAILABLE", reason=stopped)
                    break
                command = [executable, "--extensions", "none", "--allowed-mcp-server-names", "model-check-no-servers", "--policy", str(policy), "--output-format", "json", "--skip-trust", "--prompt", prompt]
                code, stdout, stderr = h.invoke(command, workspace, cfg["timeout_seconds"])
                event["exit_code"] = code
                event["stderr_sha256"] = hashlib.sha256(stderr.encode()).hexdigest()
                if code:
                    stopped = h.failure_category(code, stderr)
                    event.update(status="CLI_UNAVAILABLE", reason=stopped)
                    rec.update(status="CLI_UNAVAILABLE", reason=stopped)
                    break
                try:
                    env = json.loads(stdout)
                    event["cli_response"] = env
                    stats = env.get("stats", {})
                    if env.get("error") or not stats.get("models") or stats.get("tools", {}).get("totalCalls", 0):
                        raise ValueError("CLI error, missing identity, or unexpected CLI tool use")
                    msg = json.loads(env["response"])
                    if not isinstance(msg, dict):
                        raise ValueError("Response must be an object")
                    event.update(status="RECEIVED", parsed=msg)
                    if msg.get("type") == "finish":
                        rec["answer"] = msg
                        rec["score_details"] = score_details(msg, world, ontology)
                        rec["answer_correct"] = rec["score_details"]["passed"]
                        rec["protocol_followed"] = (not interfaces(mode) or rec["successful_interface_calls"] > 0) and (mode != "inspect" or "eligibility" in rec["definition_names_exposed"])
                        rec["passed"] = rec["answer_correct"] and rec["protocol_followed"]
                        rec["gate_before_change"] = gate(msg, world, ontology)
                        changed = revoked(world)
                        rec["gate_after_revocation"] = gate(msg, changed, ontology)
                        rec["gate_with_forged_current_revision"] = gate({**msg, "graph_revision": changed["revision"]}, changed, ontology)
                        rec["status"] = "MEASURED"
                        break
                    try:
                        observation = execute(msg, mode, world, ontology)
                        rec["successful_interface_calls"] += 1
                        rec["definition_names_exposed"] = sorted(set(rec["definition_names_exposed"]) | set(observation.get("definitions", {})))
                    except ValueError as error:
                        observation = {"error": str(error)}
                    rec["history"].append({"model_request": msg, "runtime_result": observation})
                except (ValueError, KeyError, TypeError) as error:
                    event.update(status="RESPONSE_INVALID", reason=str(error), raw_stdout=stdout)
                    rec.update(status="RESPONSE_INVALID", reason=str(error))
                    break
                h.save(out / (folder.name + ".json"), rec)
        h.save(out / (folder.name + ".json"), rec)
        summaries.append({"experiment": folder.name, "status": rec["status"], "passed": rec["passed"], "calls": len(rec["calls"]), "interface_calls": rec["successful_interface_calls"]})
        h.save(out / "summary.json", {"complete": False, "experiments": summaries})
        print(folder.name, rec["status"], rec["passed"], flush=True)
    h.save(out / "summary.json", {"complete": True, "experiments": summaries, "appworld_runs": 0})
    print("Evidence:", out)
    return 0 if not args.live or all(r["passed"] is True for r in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())

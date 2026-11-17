#!/usr/bin/env python3
"""Preregister, execute and audit the live-model inference/repair acceptance run.

No scripted actor is available. Failed and interrupted runs stay in the archive.
This is a finite engineering acceptance test, not a claim about arbitrary tasks.
"""

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import secrets
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from appworld_runtime.batch import configured_model, validate_selection
from react_runtime.completion import fingerprint
from react_runtime.store import RunStore
from repair_runtime.evaluation import challenges, trial
from repair_runtime.inference import run_request, continue_learning, execution_gate
from repair_runtime.store import Archive, runtime_sources


def preregister(archive, data_root, repeats):
    selection = json.loads((ROOT / "runs/appworld/baseline-v1/selection.json").read_text())
    validate_selection(data_root, selection)
    command, model = configured_model()
    tasks = [t["task_id"] for t in selection["tasks"]]
    phases = []
    for phase, raw in (("raw", True), ("recovery", False)):
        for task in tasks:
            phases.append({"phase": phase, "request": {"request_id": phase + ":" + task,
                "adapter": "appworld", "actor": "ollama", "root": str(data_root), "task_id": task,
                "raw": raw, "learn": False}})
    for repeat in range(repeats):
        for task in tasks:
            phases.append({"phase": "after", "request": {"request_id": f"after:{repeat}:{task}",
                "adapter": "appworld", "actor": "ollama", "root": str(data_root), "task_id": task, "learn": False}})
    from scripts.demo_repair_scoring import cases
    for index, phase in ((0, "relationship_recovery"), (1, "relationship_transfer")):
        phases.append({"phase": phase, "request": {"request_id": phase, "adapter": "local", "actor": "ollama",
            "data": cases()[index][2], "loop_config": {"max_steps": 12, "deadline_seconds": 240,
                "model_timeout_seconds": 90, "inline_output_chars": 6000, "max_stagnant_steps": 3}}})
    phases.append({"phase": "old_native_after_second_repair", "request": {"request_id": "old-native-final",
        "adapter": "appworld", "actor": "ollama", "root": str(data_root), "task_id": tasks[0], "learn": False}})
    # These inputs are never exposed to the proposer. Freeze them before any
    # live model run, then test only the final accepted package.
    fresh = challenges(secrets.randbits(48), 50, function="direct", numeric=True)
    fresh += challenges(secrets.randbits(48), 50, function="related")
    manifest = {"version": 1, "model": model, "model_command": command, "selection": selection,
                "repeats": repeats, "phases": phases, "sources": runtime_sources(), "stress_cases": archive.put(fresh),
                "requirements": ["Every scheduled task passes", "Live model is used for every raw/recovery episode",
                    "Recovery preserves world and original goal", "Every retained case passes without fallback before promotion",
                    "Two automatic repairs preserve old cases", "All 100 frozen generated cases pass"],
                "negative_control": "Bypass the learned direct numeric filter and require fresh execution gates to reject the regression without changing active state",
                "limitations": ["The three native tasks are previously exposed training variants, not sealed held-out tasks.",
                                "Generated structural cases are not additional native benchmark tasks."]}
    reference = archive.put(manifest)
    with archive.db: archive.event("LIVE_PROOF_PREREGISTERED", {"manifest": reference})
    (archive.root / "proof-manifest.json").write_text(json.dumps({"reference": reference, **manifest}, indent=2))
    return manifest


def audit_episode(archive, result):
    episode = result.get("episode")
    if episode is None: return {"passed": False, "error": result.get("error", result.get("status"))}
    store = RunStore.open_existing(Path(episode["run_directory"]))
    try:
        audit = store.audit()
        events = audit["events"]
        start = next(e for e in events if e["type"] == "episode_started")
        manifest = json.loads(store.get(start["payload"]["manifest_ref"]["id"]))
        counts = Counter(e["type"] for e in events)
        model_calls = [e for e in events if e["type"] == "model_started"]
        model_results = [e for e in events if e["type"] == "model_result"]
        configuration = tomllib.loads((ROOT / "config/models.toml").read_text())["ollama"]
        wire_receipts, wire_valid = [], True
        for event in model_results:
            try:
                wire = json.loads(store.get(event["payload"]["stderr_ref"]["id"]))
                options = wire["request"]["options"]
                actual_context = wire["runtime"][0]["context_length"]
                user_context = json.loads(wire["request"]["messages"][1]["content"])
                valid = (wire["transport"] == "ollama-http/1" and not wire.get("error")
                         and wire["response"]["model"] == configuration["model"]
                         and options == {k: configuration[k] for k in ("num_ctx", "num_predict", "temperature")}
                         and actual_context >= configuration["num_ctx"]
                         and user_context["task"]["objective"] == manifest["task"])
                wire_valid &= valid
                wire_receipts.append({"event": event["seq"], "valid": valid, "context_length": actual_context,
                    "prompt_tokens": wire["response"].get("prompt_eval_count"), "output_tokens": wire["response"].get("eval_count"),
                    "duration_ms": event["payload"]["execution"]["duration_ms"]})
            except (ValueError, KeyError, IndexError, TypeError): wire_valid = False
        goals_pinned = all(json.loads(store.get(e["payload"]["input_ref"]["id"]))["task"]["objective"] == manifest["task"] for e in model_calls)
        scripted = manifest["model"].get("actor") in {"reference", "scripted"} or any(
            part in {"observe-reference", "fixture-actor", "reference"} for tool in manifest["tool_implementations"] for part in tool["command"])
        native = result.get("native")
        official = archive.get(native["evaluation"]) if native else None
        judged = archive.get(result["judge"])
        passed = (result.get("task_state") == "TRUE" and episode["status"] == "VERIFIED_SUCCESS"
                  and audit["complete"] and goals_pinned and not scripted and wire_valid
                  and judged["coverage"]["integrity_complete"]
                  and (official is None or official["native_result"]["success"] is True))
        return {"passed": passed, "native_success": None if official is None else official["native_result"]["success"],
                "native_checks": None if official is None else official["native_result"]["num_tests"],
                "model_calls": len(model_calls), "kernel_calls": counts["kernel_started"],
                "handoffs": counts["kernel_handoff"], "goals_pinned": goals_pinned, "scripted_actor": scripted,
                "trace_complete": audit["complete"], "event_head": audit["last_event_sha256"],
                "task_state": result.get("task_state"), "execution_stop": episode["status"],
                "steps": episode["steps"], "tool_attempts": episode["tool_attempts"],
                "compactions": episode["compactions"], "judge": result["judge"], "run": episode["run_directory"],
                "wire_receipts_valid": wire_valid, "wire_receipts": wire_receipts}
    finally: store.close()


def build_report(archive, manifest, rows):
    decisions = [archive.get(d["receipt"]) for d in archive.status()["decisions"]]
    package = archive.get(archive.meta("active"))
    stress = [trial(package, data) for data in archive.get(manifest["stress_cases"])]
    stress_receipt = archive.put({"results": [{"case": r["case"], "state": r["state"], "evidence": archive.put(r)} for r in stress]})
    active = archive.meta("active")
    negative = deepcopy(package)
    direct = negative["functions"]["direct"]
    returned = direct["nodes"][direct["return"]]
    negative_gate = {"state": "UNKNOWN", "reason": "No learned numeric return to bypass"}
    if returned["op"] == "filter_numeric":
        direct["return"] = returned["input"]
        suite, _ = archive.snapshot()
        negative_gate = execution_gate(archive)(active, archive.put(negative), suite)
    negative_receipt = archive.put(negative_gate)
    conditions = {"all_scheduled_finished": len(rows) == len(manifest["phases"]),
        "all_tasks_passed": bool(rows) and all(r["audit"]["passed"] for r in rows),
        "live_model_used": all(r["audit"].get("model_calls", 0) > 0 for r in rows if r["phase"] in {"raw", "recovery", "relationship_recovery"}),
        "kernel_gaps_recovered": all(r["audit"].get("handoffs", 0) == 1 and r["audit"]["passed"] for r in rows if r["phase"] in {"recovery", "relationship_recovery"}),
        "learned_inference_needs_no_fallback": all(r["audit"].get("model_calls", 0) == 0 and r["audit"].get("handoffs", 0) == 0 for r in rows if r["phase"] in {"after", "relationship_transfer", "old_native_after_second_repair"}),
        "two_automatic_repairs": len(decisions) == 2,
        "every_regression_gate_passed": bool(decisions) and all(d["execution_gate"]["state"] == "TRUE" and not d["regressed"] and not d["requirements_lost"] for d in decisions),
        "all_frozen_stress_cases_passed": all(r["state"] == "TRUE" for r in stress),
        "regression_negative_control_rejected": negative_gate["state"] == "FALSE" and archive.meta("active") == active,
        "protected_sources_unchanged": runtime_sources() == manifest["sources"], "archive_integrity": archive.audit()["complete"]}
    return {"passed": all(conditions.values()), "conditions": conditions, "model": manifest["model"],
            "episodes": rows, "phase_counts": dict(Counter(r["phase"] for r in rows)),
            "promotions": archive.status()["decisions"], "regression_suite_sizes": [d["scheduled"] for d in decisions],
            "stress": {"scheduled": len(stress), "passed": sum(r["state"] == "TRUE" for r in stress), "receipt": stress_receipt},
            "negative_control": {"state": negative_gate["state"], "receipt": negative_receipt,
                                 "active_unchanged": archive.meta("active") == active},
            "limitations": manifest["limitations"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=ROOT / ".appworld")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1: parser.error("At least one post-repair repeat is required")
    archive = Archive(args.archive, create=not (args.archive / "archive.sqlite").exists())
    try:
        manifest_path = archive.root / "proof-manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else preregister(archive, args.data_root.resolve(), args.repeats)
        rows = []
        learned_native = False
        for entry in manifest["phases"]:
            if entry["phase"] == "after" and not learned_native:
                continue_learning(archive)
                learned_native = True
            result = run_request(archive, entry["request"], learn=entry["phase"] == "relationship_recovery")
            row = {"phase": entry["phase"], "request_id": entry["request"]["request_id"], "audit": audit_episode(archive, result)}
            rows.append(row)
            (archive.root / "proof-progress.json").write_text(json.dumps(rows, indent=2))
            print(json.dumps(row), flush=True)
        report = build_report(archive, manifest, rows)
        (archive.root / "proof-report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({"passed": report["passed"], "conditions": report["conditions"], "report": str(archive.root / "proof-report.json")}))
        return 0 if report["passed"] else 1
    finally: archive.close()


if __name__ == "__main__": raise SystemExit(main())

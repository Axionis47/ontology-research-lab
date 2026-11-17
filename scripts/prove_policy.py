#!/usr/bin/env python3
"""Frozen policy experiment with real-model acceptance before final activation."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from react_runtime.policy import legacy_policy
from repair_runtime.store import Archive, runtime_sources
from repair_runtime.policy_repair import import_previous, freeze, register_failure, register_episode, binding_counterexample, work, promote
from repair_runtime.policy_evaluation import score, probe
from repair_runtime.inference import execute_request
from repair_runtime.judge import judge_episode
from repair_runtime.program import seed_package
from scripts.prove_inference import audit_episode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--previous", type=Path, default=ROOT / "runs/learning/live-acceptance-v2")
    parser.add_argument("--policy-failure", type=Path, help="Completed policy proof whose local failure requires declared state bootstrap")
    parser.add_argument("--binding-failure-run", type=Path, help="Original local run exposing a bound mutation argument failure")
    parser.add_argument("--proposer", choices=["gemini"], default="gemini", help="Gemini improvement proposer; this component test does not replace the separate judge stage")
    args = parser.parse_args()
    archive = Archive(args.archive, create=True)
    try:
        imported = import_previous(archive, args.previous)
        with archive.db: archive.set("frozen_kernel", True)
        manifest = freeze(archive, imported["stress"])
        phases = [p for p in imported["manifest"]["phases"] if p["phase"] in {"raw", "recovery", "relationship_recovery"}]
        old_rows = json.loads((args.previous / "proof-report.json").read_text())["episodes"]
        targets, evidence = {}, {}
        bootstrap_evidence = None
        if args.policy_failure:
            failure_report = json.loads((args.policy_failure / "proof-report.json").read_text())
            failed = [r for r in failure_report["live"] if r["phase"] == "relationship_recovery" and not r["audit"]["passed"]]
            if len(failed) != 3: raise ValueError("Expected three recorded local fallback failures")
            from react_runtime.store import RunStore
            for row in failed:
                original = RunStore.open_existing(Path(row["audit"]["run"]))
                try:
                    if not original.audit()["complete"]: raise ValueError("Incomplete original failure evidence")
                finally: original.close()
            bootstrap_evidence = archive.put({"kind": "missing_declared_state_observation", "archive": str(args.policy_failure.resolve()), "rows": failed})
        # Reproduce the three observed component defects using original evidence.
        for row in old_rows:
            if row["phase"] not in {"raw", "recovery", "relationship_recovery"}: continue
            audit = row["audit"]
            run = Path(audit["run"])
            from react_runtime.store import RunStore
            old = RunStore.open_existing(run)
            try:
                checked = old.audit()
                evidence[row["request_id"]] = archive.put({"source_archive": str(args.previous.resolve()), "audit": audit,
                                                         "event_head": checked["last_event_sha256"], "trace_complete": checked["complete"]})
            finally: old.close()
            if "discovery" not in targets and (run.parent / "session/mcp-catalog.json").exists():
                catalogue = json.loads((run.parent / "session/mcp-catalog.json").read_text())
                req = next(p["request"] for p in phases if p["request"]["request_id"] == row["request_id"])
                # Expected API comes from the fixed declared adapter, not search.
                target = {"component": "discovery", "goal": "Follow all the classical artists on Spotify that have at least 22 followers.",
                          "tools": [{"name": t["name"], "description": t.get("description", "")} for t in catalogue.values()], "expected": "spotify__follow_artist"}
                if bootstrap_evidence: target["require_state_bootstrap"] = True
                targets["discovery"] = register_failure(archive, "discovery", target, [evidence[row["request_id"]]] + ([bootstrap_evidence] if bootstrap_evidence else []))
            # Fresh judge scans the old immutable trace. It does not execute or modify it.
            judged = judge_episode(archive, run)
            if judged["repair_route"] in {"POLICY_BINDING", "POLICY_CONTEXT"}:
                key = register_episode(archive, {"judge": judged["receipt"], "episode": {"run_directory": str(run)}})
                if key:
                    component = archive.meta("policy_groups")[key]["component"]
                    targets.setdefault(component, key)
        if args.binding_failure_run:
            from react_runtime.store import RunStore
            original = RunStore.open_existing(args.binding_failure_run)
            try:
                audited = original.audit()
                if not audited["complete"]: raise ValueError("Incomplete binding failure trace")
                start = next(e for e in audited["events"] if e["type"] == "episode_started")
                original_manifest = json.loads(original.get(start["payload"]["manifest_ref"]["id"]))
                target = binding_counterexample(original, original_manifest, audited["events"])
                if target is None: raise ValueError("No reproduced bound mutation failure")
                provenance = archive.put({"run": str(original.root), "event_head": audited["last_event_sha256"], "manifest": original_manifest, "target": target})
                targets["binding"] = register_failure(archive, "binding", target, [provenance])
            finally: original.close()
        if set(targets) != {"discovery", "binding", "context"}:
            raise ValueError("Unable to reproduce all three original component failures: " + str(targets))
        proof_manifest = {"sources": runtime_sources(), "suite": archive.meta("policy_manifest"), "targets": targets,
                          "phases": phases, "repeats_per_failed_case": 3, "retained_count": archive.db.execute("SELECT count(*) FROM cases").fetchone()[0],
                          "model": imported["manifest"]["model"], "previous": str(args.previous.resolve())}
        (archive.root / "proof-manifest.json").write_text(json.dumps(proof_manifest, indent=2))
        print(json.dumps({"event": "frozen", "retained": proof_manifest["retained_count"], "sealed": 12, "live_scheduled": len(phases) * 3}), flush=True)
        # Search one group at a time, so the ordering and edit boundary are explicit.
        all_groups = archive.meta("policy_groups")
        keep = {targets[c]: all_groups[targets[c]] for c in ("discovery", "binding", "context")}
        with archive.db: archive.set("policy_groups", keep)
        live_rows = []
        seed = archive.put(seed_package())
        def live_gate(policy_ref):
            attempt_rows = []
            for phase in phases:
                for repeat in range(3):
                    request = deepcopy(phase["request"])
                    request["request_id"] += ":policy:" + str(repeat)
                    directory = archive.root / "live" / policy_ref[:16] / (phase["phase"] + "-" + str(phases.index(phase)) + "-" + str(repeat))
                    try:
                        outcome = execute_request(archive, request, directory, package_ref=seed, policy_ref=policy_ref)
                        judged = judge_episode(archive, outcome["episode"]["run_directory"], native=outcome["native"])
                        result = {"episode": outcome["episode"], "native": outcome["native"], "judge": judged["receipt"], "task_state": judged["task_state"]}
                        audit = audit_episode(archive, result)
                        audit["passed"] &= audit["model_calls"] > 0
                        if phase["phase"] != "raw": audit["passed"] &= audit["handoffs"] == 1
                    except Exception as error: audit = {"passed": False, "error": str(error)}
                    row = {"case": phase["request"]["request_id"], "repeat": repeat, "phase": phase["phase"], "audit": audit}
                    live_rows.append(row)
                    attempt_rows.append(row)
                    (archive.root / "proof-progress.json").write_text(json.dumps(live_rows, indent=2))
                    print(json.dumps({"event": "live_finished", "case": row["case"], "repeat": repeat,
                                      "passed": audit["passed"], "stop": audit.get("execution_stop"), "model_calls": audit.get("model_calls")}), flush=True)
            return {"passed": len(attempt_rows) == len(phases) * 3 and all(r["audit"]["passed"] for r in attempt_rows), "rows": attempt_rows}
        from repair_runtime.policy_proposer import PolicyModelProposer
        proposer = PolicyModelProposer(args.proposer, timeout=180)
        decisions = []
        def decided(result):
            print(json.dumps({"event": "candidate_decided", "component": result["component"], "accepted": result["accepted"],
                              "conditions": result.get("conditions"), "status": result.get("status"), "reason": result.get("reason"),
                              "proposal": result.get("proposal")}), flush=True)
        for component in ("discovery", "binding", "context"):
            key = targets[component]
            decisions.extend(work(archive, proposer=proposer, group_keys=[key],
                                  live_gate=live_gate if component == "context" else None, on_decision=decided))
        versions = archive.meta("active"), archive.meta("active_policy")
        current = archive.get(versions[1])
        negative = {**current, "version": 2, "discovery": "legacy" if current["discovery"] != "legacy" else [{"op": "observe_declared_state"}]}
        target = deepcopy(archive.get(keep[targets["discovery"]]["target"]))
        target["goal"] += " "
        group = register_failure(archive, "discovery", target)
        rejected = promote(archive, negative, group)
        sealed = score(archive.get(archive.meta("active_policy")), archive.get(manifest["sealed"]))
        accepted_live = next((d["live_gate"]["rows"] for d in decisions if d["accepted"] and d.get("live_gate")), [])
        report = {"passed": {d["component"] for d in decisions if d["accepted"]} == {"discovery", "binding", "context"} and len(accepted_live) == 21 and all(r["audit"]["passed"] for r in accepted_live)
                             and not rejected["accepted"] and versions == (archive.meta("active"), archive.meta("active_policy")) and all(r["passed"] for r in sealed),
                  "decisions": [{k: d[k] for k in ("receipt", "component", "accepted", "conditions", "proposal", "status", "reason") if k in d} for d in decisions],
                  "live": live_rows, "sealed": sealed, "negative_control": {"receipt": rejected["receipt"], "accepted": rejected["accepted"], "versions_unchanged": versions == (archive.meta("active"), archive.meta("active_policy"))},
                  "active_kernel": archive.meta("active"), "active_policy": archive.meta("active_policy"), "sources_unchanged": runtime_sources() == proof_manifest["sources"],
                  "manual_changes": ["Bounded typed policy instruction interpreter and proposer transport", "Session errors stop uncertain effects", "Immutable import, frozen evaluator, promotion protocol"],
                  "learned_changes": [{"component": d["component"], "bundle": d["candidate"], "proposal": d["proposal"]} for d in decisions if d["accepted"]],
                  "limitations": ["Finite engineering acceptance, not general API semantics learning", "Native cases are exposed training variants", "Model composes registered mechanism primitives, no model weight training"]}
        report["passed"] &= report["sources_unchanged"] and archive.audit()["complete"]
        with archive.db:
            archive.set("deployment_ready", report["passed"])
            archive.event("POLICY_EXPERIMENT_FINISHED", {"passed": report["passed"], "model_proposer": args.proposer})
        (archive.root / "proof-report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({"event": "proof_finished", "passed": report["passed"], "report": str(archive.root / "proof-report.json")}), flush=True)
        return 0 if report["passed"] else 1
    finally: archive.close()


if __name__ == "__main__": raise SystemExit(main())

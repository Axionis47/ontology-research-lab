"""Durable repair scheduler. A verified counterexample is sufficient to start."""

from copy import deepcopy
import json
import secrets
import time
import uuid

from react_runtime.completion import evaluate, fingerprint
from react_runtime.store import RunStore
from .evaluation import trial, compare, challenges, save_trial
from .program import validate_package, function_name
from .proposer import SearchProposer, make_packet
from .store import runtime_sources


def import_run(archive, directory):
    """Import trusted completion evidence from a finished real ReAct episode."""
    from pathlib import Path
    store = RunStore.open_existing(Path(directory))
    try:
        audit = store.audit()
        if not audit["complete"]: raise ValueError("Incomplete or invalid episode evidence")
        events = audit["events"]
        checks = [e for e in events if e["type"] == "completion_checked"]
        if not checks: raise ValueError("No bound completion contract; native scores alone cannot define a repair")
        event = checks[-1]
        if any(e["type"] == "dispatch_started" and e["seq"] > event["seq"] for e in events):
            raise ValueError("Completion observation is stale")
        binding = json.loads(store.get(event["payload"]["binding_ref"]["id"]))
        report = json.loads(store.get(event["payload"]["report_ref"]["id"]))
        contract = json.loads(store.get(binding["contract_ref"]["id"]))
        before = json.loads(store.get(binding["before_ref"]["id"]))
        refs = report["evidence_refs"]
        if refs[:2] != [binding["contract_ref"], binding["before_ref"]] or len(refs) != 3:
            raise ValueError("Completion evidence binding differs")
        after = json.loads(store.get(refs[2]["id"]))
        recomputed = evaluate(contract, before, after)
        if {k: v for k, v in report.items() if k != "evidence_refs"} != recomputed:
            raise ValueError("Completion report contradicts original observations")
        start = next(e for e in events if e["type"] == "episode_started")
        manifest = json.loads(store.get(start["payload"]["manifest_ref"]["id"]))
        if manifest["task"] != contract["goal"] or manifest["verifier_binding_ref"] != event["payload"]["binding_ref"]:
            raise ValueError("Episode goal or verifier binding changed")
        origin = {"kind": "react_episode", "directory": str(store.root), "event_head": audit["last_event_sha256"],
                  "report": archive.put(report), "after": archive.put(after),
                  "handoffs": [e for e in events if e["type"] == "kernel_handoff"]}
        return archive.add_case({"contract": contract, "before": before}, origin)
    finally:
        store.close()


def validate_delta(parent, candidate, name):
    validate_package(candidate)
    for other in parent["functions"]:
        if other != name and candidate["functions"][other] != parent["functions"][other]:
            raise ValueError("Candidate changed an undeclared function")
    if candidate == parent: raise ValueError("Candidate made no change")


def repair_case(archive, row, proposer, *, max_attempts=96, validation_gate=None):
    case_id = row["id"]
    parent_ref = archive.meta("active")
    parent, data = archive.get(parent_ref), archive.get(row["input_ref"])
    baseline = trial(parent, data)
    baseline_ref = archive.put(baseline)
    if baseline["state"] == "TRUE":
        archive.finish_case(case_id, "RESOLVED", parent_ref, baseline_ref)
        return "RESOLVED"
    if baseline["state"] == "UNKNOWN":
        archive.finish_case(case_id, "NEEDS_EVIDENCE", parent_ref, baseline_ref)
        return "NEEDS_EVIDENCE"
    packet = make_packet(archive, case_id, data, parent_ref, baseline)
    suite, suite_ref = archive.snapshot()
    # Challenges are frozen before proposing, and never sent to the proposer.
    seed = secrets.randbits(48)
    fresh = challenges(seed, function=packet["function"], numeric=bool(data["contract"]["selector"].get("numeric")))
    challenge_ref = archive.put({"generator": "selective-update-structural/1", "seed": seed, "cases": fresh})
    packet_ref = archive.put(packet)
    with archive.db:
        archive.event("REPAIR_OPENED", {"case": case_id, "parent": parent_ref, "suite": suite_ref,
                                       "packet": packet_ref, "challenges": challenge_ref, "proposer": proposer.name})
    proposals = iter(proposer.propose(archive, packet, parent))
    terminal = "SEARCH_EXHAUSTED"
    last_receipt = baseline_ref
    for _ in range(max_attempts):
        attempt = archive.reserve_attempt(case_id, parent_ref, suite_ref, "pending:" + str(uuid.uuid4()))
        if attempt is None:
            terminal = "BUDGET_EXHAUSTED"
            break
        try:
            proposal = next(proposals)
        except StopIteration:
            archive.finish_attempt(attempt, "NO_MORE_PROPOSALS", archive.put({"reason": "Proposer exhausted"}))
            break
        proposal_ref = archive.put(proposal)
        kind = proposal.get("kind")
        if kind != "candidate":
            terminal = {"needs_evidence": "NEEDS_EVIDENCE", "needs_capability": "NEEDS_CAPABILITY",
                        "needs_configuration": "NEEDS_CONFIGURATION", "unavailable": "RETRY_WAIT"}.get(kind, "INVALID_PROPOSAL")
            last_receipt = archive.put({"proposal": proposal_ref, "status": terminal,
                                       "retry_after": time.time() + 60 if terminal == "RETRY_WAIT" else None})
            archive.finish_attempt(attempt, terminal, last_receipt)
            break
        try:
            candidate = proposal["candidate"]
            validate_delta(parent, candidate, packet["function"])
            candidate_ref = archive.put(candidate)
        except (ValueError, TypeError, KeyError) as error:
            last_receipt = archive.put({"decision": "INVALID", "reason": str(error), "proposal": proposal_ref})
            archive.finish_attempt(attempt, "INVALID", last_receipt)
            continue
        duplicate = archive.db.execute("SELECT 1 FROM attempts WHERE parent=? AND suite=? AND candidate=? AND id<>? AND status NOT IN ('INTERRUPTED','ACCEPT_FOR_DEVELOPMENT')",
                                       (parent_ref, suite_ref, candidate_ref, attempt)).fetchone()
        with archive.db:
            archive.db.execute("UPDATE attempts SET candidate=? WHERE id=?", (candidate_ref, attempt))
        if duplicate:
            archive.finish_attempt(attempt, "DUPLICATE", proposal_ref)
            continue
        target = trial(candidate, data)
        if target["state"] != "TRUE":
            last_receipt = archive.put({"decision": "REJECT", "reason": "TARGET_NOT_FIXED", "target": target, "proposal": proposal_ref})
            archive.finish_attempt(attempt, "REJECT", last_receipt)
            continue
        visible = (archive.get(r["input_ref"]) for r in suite["cases"])
        comparison = compare(parent, candidate, visible, case_id, write=archive.put)
        comparison.update(parent_ref=parent_ref, candidate_ref=candidate_ref, suite_ref=suite_ref,
                          proposal_ref=proposal_ref, challenge_ref=challenge_ref, native_performance_claimed=False)
        if comparison["decision"] == "ACCEPT_FOR_DEVELOPMENT":
            challenge_results = [save_trial(trial(candidate, case), archive.put) for case in fresh]
            comparison["challenge_results"] = challenge_results
            if any(r["state"] != "TRUE" for r in challenge_results):
                comparison.update(decision="REJECT", reasons=["FRESH_CHALLENGE_FAILED"])
        if comparison["decision"] == "ACCEPT_FOR_DEVELOPMENT" and archive.meta("execution_gate_required"):
            if validation_gate is None:
                comparison.update(decision="INCONCLUSIVE", reasons=["EXECUTION_GATE_UNAVAILABLE"])
            else:
                gate = validation_gate(parent_ref, candidate_ref, suite)
                comparison["execution_gate"] = gate
                if gate.get("state") != "TRUE":
                    comparison.update(decision="REJECT" if gate.get("state") == "FALSE" else "INCONCLUSIVE",
                                      reasons=["EXECUTION_REGRESSION_GATE_FAILED"])
        last_receipt = archive.put(comparison)
        archive.finish_attempt(attempt, comparison["decision"], last_receipt)
        if comparison["decision"] == "ACCEPT_FOR_DEVELOPMENT":
            if runtime_sources() != archive.meta("sources"): raise ValueError("Protected source changed during comparison")
            if archive.activate(parent_ref, candidate_ref, suite, last_receipt):
                archive.finish_case(case_id, "RESOLVED", candidate_ref, last_receipt)
                return "ACCEPTED"
            terminal = "READY"  # Suite or active version changed; never commit stale evidence.
            break
        if comparison["decision"] == "INCONCLUSIVE":
            terminal = "NEEDS_EVIDENCE"
            break
        if comparison["reasons"] == ["FRESH_CHALLENGE_FAILED"]:
            # Retire this fresh check. Further search gets a new cycle and seed.
            terminal = "CHALLENGE_REJECTED"
            break
    archive.finish_case(case_id, terminal, parent_ref, last_receipt)
    return terminal


def work(archive, proposer=None, *, max_jobs=20, max_attempts=96, validation_gate=None, case_id=None):
    if max_jobs < 1 or max_attempts < 1: raise ValueError("Work budgets must be positive")
    proposer = proposer or SearchProposer()
    completed = []
    with archive.worker():
        for _ in range(max_jobs):
            if runtime_sources() != archive.meta("sources"): raise ValueError("Protected source revision changed")
            with archive.db:
                for row in archive.db.execute("SELECT id,last_report FROM cases WHERE status='RETRY_WAIT'").fetchall():
                    if archive.get(row["last_report"])["retry_after"] <= time.time():
                        archive.db.execute("UPDATE cases SET status='READY' WHERE id=?", (row["id"],))
                row = archive.db.execute("SELECT * FROM cases WHERE status='READY' AND (? IS NULL OR id=?) ORDER BY created,id LIMIT 1",
                                         (case_id, case_id)).fetchone()
                if row is None or archive.meta("cycles_spent") >= archive.meta("max_cycles"): break
                archive.set("cycles_spent", archive.meta("cycles_spent") + 1)
                archive.db.execute("UPDATE cases SET status='RUNNING' WHERE id=?", (row["id"],))
                archive.event("CASE_CLAIMED", {"case": row["id"], "proposer": proposer.name})
            try:
                outcome = repair_case(archive, row, proposer, max_attempts=max_attempts, validation_gate=validation_gate)
            except Exception as error:
                receipt = archive.put({"error_type": type(error).__name__, "reason": str(error)[:1000]})
                archive.finish_case(row["id"], "ERROR", archive.meta("active"), receipt)
                # Integrity/runtime faults are not candidate-edit opportunities.
                raise
            completed.append({"case": row["id"], "outcome": outcome})
    return {"completed": completed, **archive.status()}

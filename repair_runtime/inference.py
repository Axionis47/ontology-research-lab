"""One-request inference, whole-episode judgement, gated repair, next inference."""

from contextlib import contextmanager
import fcntl
from pathlib import Path
import sys
import uuid

from react_runtime.completion import fingerprint
from react_runtime.loop import Config
from .engine import import_run, work
from .episode import run_episode
from .judge import judge_episode


@contextmanager
def inference_owner(archive):
    with (archive.root / "inference.lock").open("a") as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError("Another inference controller owns this archive") from None
        try: yield
        finally: fcntl.flock(lock, fcntl.LOCK_UN)


def execute_request(archive, request, directory, *, package_ref=None, regression=False, policy_ref=None):
    kind = request["adapter"]
    actor = request.get("actor", "ollama")
    disabled = [sys.executable, "-c", "raise SystemExit('Fallback is disabled in kernel regression replay')"]
    if kind == "local":
        episode = run_episode(archive, request["data"], directory, actor=actor,
                              raw=request.get("raw", False) and not regression,
                              package_ref=package_ref, policy_ref=policy_ref, ingest=False,
                              config=Config(**request["loop_config"]) if "loop_config" in request else None,
                              actor_command=disabled if regression else None)
        return {"episode": episode, "data": request["data"], "native": None}
    if kind == "appworld":
        from appworld_runtime.inference import run_native_episode
        return run_native_episode(archive, request, directory, package_ref=package_ref, policy_ref=policy_ref,
                                  actor_command=disabled if regression else None, regression=regression)
    raise ValueError("Unknown inference adapter")


def execution_gate(archive, policy_ref=None):
    policy_ref = policy_ref or archive.meta("active_policy")
    def gate(parent, candidate, suite):
        rows = []
        adapters = archive.meta("case_adapters")
        root = archive.root / "regressions" / str(uuid.uuid4())
        for row in suite["cases"]:
            data = archive.get(row["input_ref"])
            request = archive.get(adapters[row["id"]]) if row["id"] in adapters else {"adapter": "local", "data": data}
            try:
                outcome = execute_request(archive, request, root / row["id"][:16], package_ref=candidate, policy_ref=policy_ref, regression=True)
                if fingerprint(outcome["data"]) != row["id"]:
                    raise ValueError("Fresh replay did not reproduce the registered initial contract and state")
                judged = judge_episode(archive, outcome["episode"]["run_directory"], native=outcome["native"])
                # A fallback would mask a defective kernel. All old cases must
                # succeed using the candidate itself in a fresh environment.
                passed = (judged["task_state"] == "TRUE" and not judged["kernel_gap"]
                          and outcome["episode"]["status"] == "VERIFIED_SUCCESS")
                rows.append({"case": row["id"], "state": "TRUE" if passed else "FALSE", "judge": judged["receipt"]})
            except Exception as error:
                rows.append({"case": row["id"], "state": "UNKNOWN", "error": str(error)[:1000]})
        state = "UNKNOWN" if any(r["state"] == "UNKNOWN" for r in rows) else "FALSE" if any(r["state"] != "TRUE" for r in rows) else "TRUE"
        return {"state": state, "parent": parent, "candidate": candidate, "suite": suite, "rows": rows,
                "fallback_enabled": False, "fresh_worlds": True, "policy_version": policy_ref}
    return gate


def continue_learning(archive, proposer=None):
    # Explicit injection remains available for isolated legacy component tests.
    if proposer is None:
        return gemini_learning(archive)
    frozen = archive.db.execute("SELECT value FROM meta WHERE key='frozen_kernel'").fetchone()
    result = {"active": archive.meta("active"), "decisions": [], "kernel_frozen": True} if frozen and archive.meta("frozen_kernel") else work(archive, proposer, validation_gate=execution_gate(archive))
    from .policy_repair import work as policy_work
    result["policy_decisions"] = policy_work(archive)
    return result


def gemini_learning(archive):
    """Connect the agreed model roles to the existing bounded program-repair gate."""
    from .evaluation import trial
    from .gemini_judge import diagnose
    from .proposer import ModelProposer

    def stopped(reason, **extra):
        return {"active": archive.meta("active"), "decisions": [], "policy_decisions": [],
                "kernel_frozen": True, "status": "BLOCKED", "reason": reason, **extra}

    with inference_owner(archive):
        episodes = [archive.get(ref) for ref in archive.meta("inference_completed").values()]
        episodes = [r for r in episodes if r.get("episode") and r.get("judge")]
        if not episodes: return stopped("GEMINI_DIAGNOSIS_REQUIRED", detail="No recorded episode to diagnose; no proposer invoked.")
        frozen = archive.db.execute("SELECT value FROM meta WHERE key='frozen_kernel'").fetchone()
        if frozen and archive.meta("frozen_kernel"):
            return stopped("KERNEL_FROZEN", detail="This connected slice repairs one program function. Enable --allow-kernel-repair explicitly.")
        # All observed cases remain in the regression suite. Only the diagnosed
        # case can be selected for proposal, even when other cases are READY.
        targets = []
        adapters = archive.meta("case_adapters")
        parent = archive.meta("active")
        for result in episodes:
            case = import_run(archive, result["episode"]["run_directory"])
            adapters[case] = archive.meta("inference_requests")[result["request_id"]]["request"]
            row = archive.db.execute("SELECT * FROM cases WHERE id=?", (case,)).fetchone()
            if row["status"] == "READY" and trial(archive.get(parent), archive.get(row["input_ref"]))["state"] == "FALSE":
                targets.append((case, result))
        with archive.db: archive.set("case_adapters", adapters)
        if not targets:
            return {"status": "IDLE", "active": parent, "decisions": [], "policy_decisions": [],
                    "detail": "No reproduced program failure requires a new proposal."}
        case, result = targets[0]
        diagnosis = diagnose(archive, result)
        if diagnosis["status"] != "VALIDATED": return stopped(diagnosis["status"], diagnosis=diagnosis["receipt"])
        assessment = diagnosis["assessment"]
        packet = archive.get(diagnosis["input"])
        program_evidence = {e["evidence_id"] for e in packet["evidence"] if e["kind"] in {"parent_program", "program_preflight"}}
        findings = [f for f in assessment["findings"] if f["status"] == "SUPPORTED"
                    and f["component"] in {"FUNCTION", "KERNEL"} and f["repair_class"] == "DOMAIN_PACKAGE"
                    and any(c["relationship"] == "SUPPORTS" and c["evidence_id"] in program_evidence for c in f["citations"])]
        if assessment["needs_more_evidence"] or not findings:
            return stopped("NO_SUPPORTED_PROGRAM_TARGET", diagnosis=diagnosis["receipt"])
        if archive.meta("active") != diagnosis["parent"]: return stopped("STALE_DIAGNOSIS")
        proposer = ModelProposer("gemini", timeout=180, diagnosis={"receipt": diagnosis["receipt"], "parent": parent,
            "findings": findings})
        learned = work(archive, proposer, max_jobs=1, max_attempts=3, case_id=case, validation_gate=execution_gate(archive))
        return {**learned, "status": "IMPROVED" if archive.meta("active") != parent else "NO_IMPROVEMENT",
                "diagnosis": diagnosis["receipt"], "diagnosed_case": case, "policy_decisions": [],
                "unaddressed_findings": [f for f in assessment["findings"] if f not in findings]}


def run_request(archive, request, *, learn=True, proposer=None):
    """A stable request_id is an idempotency key, not a conversation turn.

    A crashed execution is retained as interrupted, never silently replayed.
    Completed execution can resume its learning phase without repeating writes.
    """
    if not isinstance(request.get("request_id"), str) or not request["request_id"]:
        raise ValueError("Each single-request episode needs a stable request_id")
    with inference_owner(archive):
        key, digest = request["request_id"], fingerprint(request)
        started, completed = archive.meta("inference_requests"), archive.meta("inference_completed")
        if key in started and started[key]["request"] != digest:
            raise ValueError("Request ID was reused with different input")
        if key in completed:
            result = archive.get(completed[key])
        else:
            if key in started:
                return {"request_id": key, "status": "INTERRUPTED_REQUIRES_RECONCILIATION", "execution": started[key],
                        "reason": "Execution started but no final receipt exists; no automatic write replay was attempted."}
            archive.put(request)
            directory = archive.root / "inference" / digest[:20]
            with archive.db:
                archive.set("execution_gate_required", True)
                started[key] = {"request": digest, "package": archive.meta("active"), "policy": archive.meta("active_policy"), "directory": str(directory)}
                archive.set("inference_requests", started)
                archive.event("INFERENCE_STARTED", {"request_id": key, **started[key]})
            try:
                outcome = execute_request(archive, request, directory, package_ref=started[key]["package"], policy_ref=started[key]["policy"])
                episode, native = outcome["episode"], outcome["native"]
                judged = judge_episode(archive, episode["run_directory"], native=native)
                case = None
                if judged["repair_route"] == "PROGRAM_COMPARISON":
                    case = import_run(archive, episode["run_directory"])
                    adapters = archive.meta("case_adapters")
                    adapters[case] = digest
                    with archive.db: archive.set("case_adapters", adapters)
                result = {"request_id": key, "episode": episode, "judge": judged["receipt"],
                          "task_state": judged["task_state"], "recovered": judged["recovered"],
                          "repair_route": judged["repair_route"], "repair_case": case,
                          "native": native, "package_used": started[key]["package"], "policy_used": started[key]["policy"]}
            except Exception as error:
                result = {"request_id": key, "status": "EXECUTION_ERROR", "error": str(error)[:1500],
                          "directory": str(directory), "repair_route": "RUNTIME_OR_EVIDENCE"}
            with archive.db:
                completed[key] = archive.put(result)
                archive.set("inference_completed", completed)
                archive.event("INFERENCE_FINISHED", {"request_id": key, "receipt": completed[key]})
            if result.get("repair_route", "").startswith("POLICY_"):
                from .policy_repair import register_episode
                register_episode(archive, result)
    if learn:
        result = {**result, "learning": continue_learning(archive, proposer), "next_package": archive.meta("active"), "next_policy": archive.meta("active_policy")}
    return result

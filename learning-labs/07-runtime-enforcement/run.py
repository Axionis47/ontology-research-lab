"""Deterministic fixture: proposed calls are supplied, no model is simulated."""
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def gate(request, approval):
    # Handwritten validator for this exact contract, not general JSON Schema.
    if not isinstance(request, dict) or set(request) != {"service", "environment", "evidence_id"} or not all(type(v) is str for v in request.values()):
        return "INVALID_ARGUMENTS"
    if not approval or approval["id"] != request["evidence_id"] or not approval.get("source_receipt"):
        return "MISSING_EVIDENCE"
    if not approval["current"]:
        return "STALE_APPROVAL"
    if any(approval[key] != request[key] for key in ("service", "environment")):
        return "SCOPE_MISMATCH"
    return "ALLOW"


def run():
    data = json.loads((HERE / "inputs.json").read_text())
    rows = []
    checks = {}
    for name, change, expected in [
        ("missing", None, "MISSING_EVIDENCE"),
        ("wrong-environment", {"environment": "Staging"}, "SCOPE_MISMATCH"),
        ("stale", {"current": False}, "STALE_APPROVAL"),
        ("unattributed", {"source_receipt": None}, "MISSING_EVIDENCE"),
        ("valid", {}, "ALLOW"),
    ]:
        approval = None if change is None else {**data["approval"], **change}
        state = {"deployed": False}
        before = copy.deepcopy(state)
        decision = gate(data["request"], approval)
        dispatched = decision == "ALLOW"
        if dispatched:
            state["deployed"] = True
        checks[name] = decision == expected and (state["deployed"] if dispatched else state == before)
        rows.append({"case": name, "request": data["request"], "approval": approval, "decision": decision, "dispatched": dispatched, "before": before, "after": state, "passed": checks[name]})
    bad = {**data["request"], "bypass": True}
    checks["extra_argument_rejected"] = gate(bad, data["approval"]) == "INVALID_ARGUMENTS"
    # A deliberate negative control illustrates missing enforcement. No LLM generated it.
    unguarded = {"deployed": False}
    unguarded["deployed"] = True
    report = {"experiment": "07-runtime-enforcement", "kind": "deterministic synthetic component checks", "model_calls": 0, "checks": checks, "cases": rows, "negative_control": {"approval": None, "gate_installed": False, "state_after_deliberate_dispatch": unguarded, "interpretation": "An unguarded dispatcher accepts the supplied bad proposal. This does not measure how often an LLM makes it."}}
    print(json.dumps(report, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(run())

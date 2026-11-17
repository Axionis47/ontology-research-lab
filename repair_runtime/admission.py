"""Reuse the fixed kernel preflight for a declared local mutation binding.

This rejects a proposal. It never supplies replacement target IDs, changes
arguments, changes a verifier, or infers semantics for arbitrary APIs.
"""
import json
from react_runtime.completion import evaluate
from .evaluation import apply_update


def check_update(data, current, name, arguments):
    if name != "apply_update": return None
    if arguments["revision"] != current["revision"]:
        return "revision does not match the current observed state revision " + repr(current["revision"]) + "; refresh state and correct the argument"
    projected = apply_update(data["contract"], current, arguments["entity_ids"])
    checked = evaluate(data["contract"], data["before"], projected)
    protected = next(c for c in checked["checks"] if c["requirement_id"] == "unrelated_state_preserved")
    if protected["value"] == "TRUE": return None
    return ("No update dispatched. These proposed entity_ids violate the original selection constraints: "
            + json.dumps(protected["entity_ids"]) + ". Required selector: "
            + json.dumps(data["contract"]["selector"]) + ". Correct the proposed arguments using observed records.")[:1200]

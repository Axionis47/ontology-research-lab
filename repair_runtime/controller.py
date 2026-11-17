"""Forced, finite execution of a pinned program, with evidence-based handoff."""

from copy import deepcopy

from react_runtime.completion import evaluate, fingerprint, index_snapshot
from react_runtime.loop import KernelHandoff
from .evaluation import apply_update
from .program import select, Unsupported


def finish(request_id):
    return {"kind": "finish", "request_id": request_id, "answer": "Requested update applied",
            "artifact_refs": [], "claimed_requirement_ids": ["task"]}


def state_key(snapshot):
    entities, edges = index_snapshot(snapshot)
    return fingerprint({"scope": snapshot["scope"], "complete": snapshot["complete"],
                        "entities": entities, "relations": sorted(edges)})


class ControlledPolicy:
    """Adapters supply observation and action bindings, never the selected IDs.

    All actual effects go through ReactLoop.act. The preflight checker can refuse
    an unsafe selection but cannot repair the candidate or substitute target IDs.
    A handoff keeps the same world, original contract, goal, ledger and budgets.
    """
    def __init__(self, package, data, store, observe, actions):
        self.package, self.data = deepcopy(package), deepcopy(data)
        self.store, self.observe, self.actions = store, observe, actions
        self.pending = None
        self.previous = None

    def __call__(self, context):
        step, request = context["turn"]["step"], context["turn"]["request_id"]
        current = self.observe()
        report = evaluate(self.data["contract"], self.data["before"], current)
        ref = self.store.write("observations", {"snapshot": current, "report": report}, step, visible=True)
        self.store.event("kernel_checkpoint", step, evidence_ref=ref, state=report["state"])

        def handoff(reason, message):
            return KernelHandoff(reason, message, (ref["id"],))

        if report["state"] == "TRUE": return finish(request)
        if report["state"] == "UNKNOWN":
            return handoff("EVIDENCE_GAP", "Required scope, properties or relationships are unresolved. Inspect current evidence before acting.")
        protected = next(c for c in report["checks"] if c["requirement_id"] == "unrelated_state_preserved")
        if protected["value"] != "TRUE":
            return handoff("CAPABILITY_GAP", "Readback found changes outside the requested update. Reconcile against the recorded original state.")
        if self.previous is not None and state_key(current) == self.previous:
            return handoff("NO_PROGRESS", "The last admitted kernel action produced no observed state change. Resolve the failed postcondition from this state.")
        if self.pending is None:
            try:
                selected = select(self.package, self.data["contract"], self.data["before"])
                projected = apply_update(self.data["contract"], current, selected["entity_ids"])
                preflight = evaluate(self.data["contract"], self.data["before"], projected)
                plan_ref = self.store.write("observations", {"selection": selected, "preflight": preflight}, step, visible=True)
                self.store.event("kernel_plan_checked", step, plan_ref=plan_ref, state=preflight["state"])
                protection = next(c for c in preflight["checks"] if c["requirement_id"] == "unrelated_state_preserved")
                if protection["value"] != "TRUE":
                    return handoff("CAPABILITY_GAP", "The learned selection would change protected records. Its plan was refused before dispatch; use the original conditions and current evidence.")
                self.pending = list(self.actions(selected["entity_ids"], current))
            except Unsupported as error:
                return handoff("EVIDENCE_GAP", str(error)[:900])
        if not self.pending:
            return handoff("NO_PROGRESS", "The learned program has no remaining actions, but mandatory completion checks still fail. Continue from the current state.")
        action, arguments = self.pending.pop(0)
        self.previous = state_key(current)
        return {"kind": "act", "request_id": request, "action_id": action, "arguments": arguments,
                "evidence_ids": [ref["id"]], "reason": "Execute the next action of the pinned, preflight-checked program"}

"""Model-authored policy programs with bounded original-evidence retrieval."""
import json
import os
import uuid
from itertools import combinations
from jsonschema import Draft202012Validator, ValidationError

from react_runtime.loop import parse_json
from react_runtime.policy import GRAMMAR, changed_component, validate_policy
from react_runtime.process import execute
from react_runtime.store import json_bytes
from .proposer import ModelProposer


def response_schema(component, allowed):
    def obj(properties):
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    steps = []
    for op, parameters in GRAMMAR[component].items():
        properties = {}
        for name, bounds in parameters.items():
            properties[name] = ({"type": "array", "items": {"enum": bounds}, "minItems": 1, "maxItems": len(bounds), "uniqueItems": True}
                                if name == "fields" else {"type": "integer", "minimum": bounds[0], "maximum": bounds[1]})
        steps.append(obj(properties))
    # Encode the same structural rules enforced by the interpreter. This
    # constrains legal program shapes, not parameter values or candidate choice.
    shapes = []
    names = list(GRAMMAR[component])
    for count in range(1, len(steps) + 1):
        for indices in combinations(range(len(steps)), count):
            ops = {names[i] for i in indices}
            if "inspect_shortlist" in ops and "rank_catalogue" not in ops: continue
            if "check_bound_update" in ops and "require_observed_ids" not in ops: continue
            if component == "context" and "bound_history" not in ops: continue
            shapes.append(obj({names[i]: steps[i] for i in indices}))
    reason = {"type": "string", "maxLength": 300}
    return {"oneOf": [obj({"kind": {"const": "candidate"}, "steps": {"oneOf": shapes}, "reason": reason}),
                       obj({"kind": {"const": "read"}, "artifact": {"enum": sorted(allowed)},
                            "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 3000}}),
                       obj({"kind": {"enum": ["needs_evidence", "needs_capability"]}, "reason": reason})]}


class PolicyModelProposer(ModelProposer):
    def __init__(self, provider="gemini", **kwargs):
        super().__init__(provider, **kwargs)

    def one(self, archive, key, parent, attempt):
        from .policy_repair import evidence_view
        group = archive.meta("policy_groups")[key]
        target = archive.get(group["target"])
        allowed = set(group["evidence"]) | {group["target"]}
        goal = group.get("goal", target.get("goal"))
        if not goal and "preflight_data" in target: goal = target["preflight_data"]["contract"]["goal"]
        if not goal: raise ValueError("Repair requires the original goal")
        # The target is visible training evidence. Sealed cases and raw gate
        # receipts are deliberately absent, including from allowed read IDs.
        system = {
            "protocol": "execution-policy-proposal/2", "component": group["component"],
            "instructions": "Diagnose the mechanism from original evidence and rejection feedback. Return JSON only. Author steps for only the named component as an object mapping chosen operation names to their parameter objects. Operations without parameters map to {}. The runtime compiles the operations in dependency order and applies them to the unchanged parent as a version 2 bundle. Do not emit a legacy strategy label as the repair. No task IDs, API names, data constants, prompt text, Python, new operators, budget changes or verifier edits in steps. Rejected candidates never become the parent. You may request bounded pages of allowed original evidence. If the instruction set cannot express the repair, return needs_capability. Do not invent a successful outcome.",
            "grammar": {group["component"]: GRAMMAR[group["component"]]},
            "instruction_order": list(GRAMMAR[group["component"]]),
            "semantics": {
                "rank_catalogue": "Exact word tokens. Score name overlap times name_weight plus description overlap times description_weight. No substring matches.",
                "inspect_shortlist": "Automatically inspect the first limit ranked APIs before model dispatch. Requires rank_catalogue.",
                "observe_declared_state": "When no catalogue broker exists, call a trusted declared zero-argument read-only state reader once.",
                "require_observed_ids": "Reject mutation IDs absent from actual observed entity bindings; schema validation is always mandatory.",
                "check_bound_update": "If the adapter has a fixed bound mutation guard, reject stale revisions and updates violating its preservation constraint before dispatch. Never substitute arguments. Requires require_observed_ids.",
                "bound_history": "Keep at most recent full observations and index compact references in context; cap the actual provider request. Full originals stay retrievable.",
                "carry_state": "Retain chosen bounded working-state fields in each call: revision, pending correction messages, effects, bindings. Requires bound_history.",
                "detect_stagnation": "Detect repeated semantic evidence, including alternating calls and exhausted pages, using the fixed threshold. New evidence counts as progress.",
            },
            "constraints": "The compiler follows instruction_order. Integer pairs are inclusive bounds; fields is a unique subset of the listed names. Original goal, permissions, retry cap (two repairs), verifier, hard budgets and kernel are locked.",
            "responses": [{"kind": "read", "artifact": "allowed SHA256", "offset": 0, "limit": 3000},
                          {"kind": "candidate", "steps": "object mapping operation names to parameter objects", "reason": "causal hypothesis"},
                          {"kind": "needs_evidence", "reason": "missing observation"},
                          {"kind": "needs_capability", "reason": "unsupported mechanism"}],
        }
        reads, receipts = [], []
        for call in range(self.max_calls):
            context = {"system_instructions": "You are the repair proposer. " + system["instructions"],
                       "_response_schema": response_schema(group["component"], allowed),
                       "original_goal": goal, "system": system, "parent": parent, "attempt": attempt,
                       "target_ref": group["target"], "allowed_evidence": sorted(allowed),
                       "evidence_and_rejections": evidence_view(archive, group), "recent_reads": reads[-2:]}
            encoded = json_bytes(context)
            if len(encoded) > 24000:
                return {"kind": "needs_evidence", "reason": "Proposer pinned context exceeds 24000 bytes", "evidence": receipts}
            directory = archive.root / "policy-proposer" / uuid.uuid4().hex
            directory.mkdir(parents=True)
            input_ref = archive.put(context)
            with archive.db:
                archive.event("POLICY_MODEL_CALL_STARTED", {"input": input_ref, "provider": self.name,
                              "directory": str(directory.relative_to(archive.root)), "group": key})
            command = [part.replace("{prompt}", encoded.decode()) for part in self.command]
            status = execute(command, b"" if any("{prompt}" in p for p in self.command) else encoded,
                             directory / "stdout.txt", timeout=self.timeout, max_output_bytes=65536,
                             cwd=directory, stderr_path=directory / "stderr.txt", env={**os.environ, "OLLAMA_NOHISTORY": "1"})
            raw = (directory / "stdout.txt").read_text(errors="replace") if (directory / "stdout.txt").exists() else ""
            receipt = archive.put({"input": input_ref, "execution": status, "output": raw, "provider": self.name,
                                   "directory": str(directory.relative_to(archive.root)), "group": key, "call": call})
            receipts.append(receipt)
            with archive.db: archive.event("POLICY_MODEL_CALL_FINISHED", {"receipt": receipt})
            if status["status"] != "COMPLETE":
                return {"kind": "unavailable", "reason": status["status"], "evidence": receipts}
            try:
                if self.name == "gemini":
                    envelope = parse_json(raw)
                    if envelope.get("error") or envelope.get("stats", {}).get("tools", {}).get("totalCalls", 0):
                        return {"kind": "unavailable", "reason": "CLI error or unexpected tool execution", "evidence": receipts}
                    raw = envelope["response"]
                response = parse_json(raw)
                Draft202012Validator(context["_response_schema"]).validate(response)
                kind = response.get("kind")
                if kind == "read" and set(response) == {"kind", "artifact", "offset", "limit"}:
                    ref, offset, limit = response["artifact"], response["offset"], response["limit"]
                    if ref not in allowed or type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 3000:
                        raise ValueError("Read outside allowed original evidence or bounds")
                    raw_evidence = json.dumps(archive.get(ref), ensure_ascii=False, sort_keys=True)
                    page = {"artifact": ref, "offset": offset, "content": raw_evidence[offset:offset + limit],
                            "next_offset": offset + limit if offset + limit < len(raw_evidence) else None}
                    reads.append(page)
                    with archive.db: archive.event("POLICY_EVIDENCE_READ", {"receipt": archive.put(page), "group": key})
                    continue
                if kind == "candidate" and set(response) == {"kind", "steps", "reason"}:
                    steps = response["steps"]
                    if not isinstance(steps, dict) or not steps or set(steps) - set(GRAMMAR[group["component"]]):
                        raise ValueError("steps must map registered operation names to parameter objects")
                    if any(not isinstance(v, dict) for v in steps.values()): raise ValueError("Operation parameters must be objects")
                    compiled = [{"op": op, **steps[op]} for op in GRAMMAR[group["component"]] if op in steps]
                    candidate = validate_policy({**parent, "version": 2, group["component"]: compiled})
                    if candidate["version"] != 2 or not isinstance(candidate[group["component"]], list):
                        raise ValueError("Repair must be an instruction composition, not a registered strategy label")
                    if changed_component(parent, candidate) != group["component"]: raise ValueError("Changed wrong component")
                    if any(candidate[c] != parent[c] for c in GRAMMAR if c != group["component"]): raise ValueError("Other components must be copied exactly")
                    return {"kind": kind, "candidate": candidate, "reason": response["reason"], "evidence": receipts}
                if kind in {"needs_evidence", "needs_capability"} and set(response) == {"kind", "reason"}:
                    return {**response, "evidence": receipts}
                raise ValueError("Invalid policy response")
            except (ValueError, TypeError, KeyError, AttributeError, ValidationError) as error:
                reads.append({"protocol_error": str(error)[:500]})
        return {"kind": "needs_evidence", "reason": "Bounded proposer call budget exhausted", "evidence": receipts}

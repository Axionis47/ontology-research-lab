"""Deterministic completion checks over trusted, scoped before/after observations.

This small component does not translate language, infer schemas, or certify a
source's coverage. The adapter supplies those bindings before acting begins.
"""

from copy import deepcopy
import hashlib
import json

from jsonschema import Draft202012Validator

from .store import json_bytes


CHECKER_VERSION = "selective-update-completion/2"
CHECK_IDS = ("scope_complete", "target_set_known", "targets_updated", "unrelated_state_preserved")
NAME = {"type": "string", "minLength": 1, "maxLength": 200}
WHERE = {"type": "object", "maxProperties": 20}
NUMERIC = {"type": "array", "maxItems": 20, "items": {
    "type": "object", "additionalProperties": False, "required": ["property", "op", "value"],
    "properties": {"property": NAME, "op": {"enum": ["gte", "gt", "lte", "lt", "eq"]},
                   "value": {"type": "number"}}}}
CONTRACT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["version", "goal", "scope", "selector", "update"],
    "properties": {
        "version": {"const": 1}, "goal": {"type": "string", "minLength": 1}, "scope": NAME,
        "selector": {"type": "object", "additionalProperties": False,
            "required": ["entity_type", "where"], "properties": {
                "entity_type": NAME, "where": WHERE, "numeric": NUMERIC,
                "related": {"type": "object", "additionalProperties": False,
                    "required": ["relation_type", "direction", "entity_type", "where"],
                    "properties": {"relation_type": NAME, "direction": {"enum": ["out", "in"]},
                                   "entity_type": NAME, "where": WHERE, "numeric": NUMERIC}}}},
        "update": {"oneOf": [
            {"type": "object", "additionalProperties": False,
             "required": ["kind", "property", "value"], "properties": {
                 "kind": {"const": "set_property"}, "property": NAME, "value": {}}},
            {"type": "object", "additionalProperties": False,
             "required": ["kind", "relation_type", "anchor_id", "direction"], "properties": {
                 "kind": {"const": "ensure_relation"}, "relation_type": NAME,
                 "anchor_id": NAME, "direction": {"enum": ["out", "in"]}}}]},
    },
}


def fingerprint(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def equal(left, right):
    """JSON equality that does not confuse a boolean with a numeric value."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(equal(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right))
    return left == right


def validate_contract(contract):
    Draft202012Validator(CONTRACT_SCHEMA).validate(contract)
    json_bytes(contract)  # Reject NaN/infinity and non-JSON bindings.


def index_snapshot(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != {"scope", "revision", "complete", "entities", "relations"}:
        raise ValueError("Snapshot requires scope, revision, complete, entities and relations")
    if not isinstance(snapshot["scope"], str) or not isinstance(snapshot["revision"], str) or not snapshot["revision"]:
        raise ValueError("Snapshot scope and revision must be source-bound strings")
    if type(snapshot["complete"]) is not bool or not isinstance(snapshot["entities"], list) or not isinstance(snapshot["relations"], list):
        raise ValueError("Invalid snapshot collections or coverage marker")
    json_bytes(snapshot)
    entities = {}
    for entity in snapshot["entities"]:
        if not isinstance(entity, dict) or set(entity) != {"id", "type", "properties"}:
            raise ValueError("Entity requires id, type and properties")
        if not all(isinstance(entity[k], str) and entity[k] for k in ("id", "type")) or not isinstance(entity["properties"], dict):
            raise ValueError("Invalid entity identity or properties")
        if entity["id"] in entities:
            raise ValueError("Duplicate entity identity")
        entities[entity["id"]] = entity
    relations = set()
    for relation in snapshot["relations"]:
        if not isinstance(relation, dict) or set(relation) != {"source", "type", "target"}:
            raise ValueError("Relation requires source, type and target")
        if not all(isinstance(relation[k], str) and relation[k] for k in relation):
            raise ValueError("Invalid relation identity")
        edge = (relation["source"], relation["type"], relation["target"])
        if edge in relations:
            raise ValueError("Duplicate relation")
        if edge[0] not in entities or edge[2] not in entities:
            raise ValueError("Relation endpoint is unobserved")
        relations.add(edge)
    return entities, relations


def matches(entity, entity_type, predicates, numeric=()):
    if entity["type"] != entity_type:
        return "FALSE"
    unknown = False
    for key, wanted in predicates.items():
        if key not in entity["properties"]:
            unknown = True
        elif not equal(entity["properties"][key], wanted):
            return "FALSE"
    for predicate in numeric:
        value = entity["properties"].get(predicate["property"])
        if type(value) not in (int, float):
            unknown = True
            continue
        wanted, op = predicate["value"], predicate["op"]
        passed = {"gte": value >= wanted, "gt": value > wanted, "lte": value <= wanted,
                  "lt": value < wanted, "eq": value == wanted}[op]
        if not passed: return "FALSE"
    return "UNKNOWN" if unknown else "TRUE"


def target_set(contract, entities, relations):
    selector = contract["selector"]
    targets, unresolved = [], []
    for identity, entity in sorted(entities.items()):
        state = matches(entity, selector["entity_type"], selector["where"], selector.get("numeric", ()))
        if state != "FALSE" and "related" in selector:
            spec = selector["related"]
            related = [target if spec["direction"] == "out" else source
                       for source, kind, target in relations if kind == spec["relation_type"]
                       and (source if spec["direction"] == "out" else target) == identity]
            values = [matches(entities[k], spec["entity_type"], spec["where"], spec.get("numeric", ())) for k in related]
            relation_state = "TRUE" if "TRUE" in values else "UNKNOWN" if "UNKNOWN" in values else "FALSE"
            state = "FALSE" if relation_state == "FALSE" else "UNKNOWN" if "UNKNOWN" in (state, relation_state) else "TRUE"
        if state == "TRUE":
            targets.append(identity)
        elif state == "UNKNOWN":
            unresolved.append(identity)
    return targets, unresolved


def desired_edge(update, identity):
    anchor = update["anchor_id"]
    return (anchor, update["relation_type"], identity) if update["direction"] == "out" else (identity, update["relation_type"], anchor)


def evaluate(contract, before, after):
    """Evaluate final state, never the actor's claim or preferred action path.

    Coverage is a trusted adapter assertion over the contract's complete scope,
    including protected fields/relations. Partial snapshots cannot prove success.
    """
    validate_contract(contract)
    report = {"checker_version": CHECKER_VERSION, "contract_sha256": fingerprint(contract),
              "before_sha256": fingerprint(before), "after_sha256": fingerprint(after),
              "scope": contract["scope"], "target_ids": [], "checks": []}

    def check(name, value, reason, entities=()):
        report["checks"].append({"requirement_id": name, "value": value,
                                 "reason": reason, "entity_ids": sorted(entities)})

    def finish():
        values = [c["value"] for c in report["checks"]]
        report["state"] = "FALSE" if "FALSE" in values else "UNKNOWN" if "UNKNOWN" in values else "TRUE"
        report["reward"] = {"TRUE": 1, "FALSE": 0, "UNKNOWN": None}[report["state"]]
        return report

    try:
        old, old_edges = index_snapshot(before)
        new, new_edges = index_snapshot(after)
        if before["scope"] != contract["scope"] or after["scope"] != contract["scope"]:
            raise ValueError("Evidence belongs to a different task scope")
        if not before["complete"] or not after["complete"]:
            raise ValueError("Source coverage is incomplete")
    except (ValueError, TypeError) as error:
        for name in CHECK_IDS:
            check(name, "UNKNOWN", str(error))
        return finish()
    check("scope_complete", "TRUE", "Both observations cover the declared scope")
    targets, unresolved = target_set(contract, old, old_edges)
    report["target_ids"] = targets
    update = contract["update"]
    if update["kind"] == "ensure_relation" and update["anchor_id"] not in old:
        unresolved.append(update["anchor_id"])
    if unresolved:
        check("target_set_known", "UNKNOWN", "Selection fields or relation anchor are unobserved", unresolved)
        for name in CHECK_IDS[2:]:
            check(name, "UNKNOWN", "The complete target set is unresolved")
        return finish()
    check("target_set_known", "TRUE", "Targets derived from pre-action properties and relationships", targets)
    old_protected, new_protected = deepcopy(old), deepcopy(new)
    if update["kind"] == "set_property":
        missed = [k for k in targets if k not in new or update["property"] not in new[k]["properties"]
                  or not equal(new[k]["properties"][update["property"]], update["value"])]
        for k in targets:
            old_protected[k]["properties"].pop(update["property"], None)
            if k in new_protected:
                new_protected[k]["properties"].pop(update["property"], None)
        old_protected_edges, new_protected_edges = old_edges, new_edges
    else:
        allowed = {desired_edge(update, k) for k in targets}
        missed = [k for k in targets if desired_edge(update, k) not in new_edges]
        old_protected_edges, new_protected_edges = old_edges - allowed, new_edges - allowed
    check("targets_updated", "FALSE" if missed else "TRUE",
          "Required target updates are missing" if missed else "Every target has the requested resulting state", missed)
    changed = [k for k in old_protected.keys() | new_protected.keys()
               if not equal(old_protected.get(k), new_protected.get(k))]
    changed_edges = old_protected_edges ^ new_protected_edges
    affected = set(changed) | {k for source, _, target in changed_edges for k in (source, target)}
    check("unrelated_state_preserved", "FALSE" if affected else "TRUE",
          "Changes outside the permitted update were observed" if affected else "All protected state is unchanged", affected)
    return finish()


def bind_verifier(store, contract, before, observe):
    """Pin a trusted binding and record each independent readback/check in C0.

    `observe` belongs to the trusted adapter, not to the actor. It must return
    current state in the bound scope. This component cannot prove its honesty.
    """
    validate_contract(contract)
    frozen_contract, frozen_before = deepcopy(contract), deepcopy(before)
    contract_ref = store.write("metadata", frozen_contract)
    before_ref = store.write("metadata", frozen_before)
    binding_ref = store.write("metadata", {"checker_version": CHECKER_VERSION,
        "contract_ref": contract_ref, "before_ref": before_ref,
        "authority": "trusted_adapter_binding", "natural_language_grounding_verified_by_component": False})

    def verify(_proposal, _results):
        # The loop commits this start before calling the independent verifier.
        row = store.db.execute("SELECT step FROM events WHERE type='verification_started' ORDER BY seq DESC LIMIT 1").fetchone()
        step = row[0] if row else 0
        after = observe()
        after_ref = store.write("observations", after, step)
        report = evaluate(frozen_contract, frozen_before, after)
        report["evidence_refs"] = [contract_ref, before_ref, after_ref]
        report_ref = store.write("observations", report, step, visible=True)
        store.event("completion_checked", step, binding_ref=binding_ref, report_ref=report_ref, state=report["state"])
        failed = [c for c in report["checks"] if c["value"] != "TRUE"]
        explanation = "; ".join(c["requirement_id"] + ": " + c["reason"] for c in failed) or "All mandatory completion checks passed"
        # UNKNOWN prevents verified completion and lets the actor gather evidence.
        return report["state"] == "TRUE", explanation + f". Evidence report: {report_ref['id']}"

    verify.binding_ref = binding_ref
    verify.bound_goal = frozen_contract["goal"]
    return verify

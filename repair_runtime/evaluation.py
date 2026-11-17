"""Paired, independent final-state checks and fresh structural challenges."""

from copy import deepcopy
import random

from react_runtime.completion import CHECK_IDS, evaluate, fingerprint, validate_contract, index_snapshot
from .program import select, Unsupported


def apply_update(contract, before, ids):
    """Trusted adapter semantics. Candidate programs only return entity IDs."""
    after = deepcopy(before)
    if len(ids) != len(set(ids)) or not set(ids) <= {e["id"] for e in before["entities"]}:
        raise ValueError("Candidate returned invalid entity identities")
    update = contract["update"]
    for entity in after["entities"]:
        if entity["id"] not in ids: continue
        if update["kind"] == "set_property":
            entity["properties"][update["property"]] = deepcopy(update["value"])
        else:
            source, target = (update["anchor_id"], entity["id"]) if update["direction"] == "out" else (entity["id"], update["anchor_id"])
            edge = {"source": source, "type": update["relation_type"], "target": target}
            if edge not in after["relations"]: after["relations"].append(edge)
    after["revision"] = before["revision"] + ":updated"
    return after


def trial(package, data):
    validate_contract(data["contract"])
    index_snapshot(data["before"])
    before, contract = data["before"], data["contract"]
    after, selection, error = deepcopy(before), None, None
    try:
        selection = select(package, contract, before)
        after = apply_update(contract, before, selection["entity_ids"])
    except Unsupported as exc:
        error = str(exc)
    report = evaluate(contract, before, after)
    return {"package": fingerprint(package), "case": fingerprint(data), "after": after,
            "selection": selection, "error": error, "report": report,
            "state": "UNKNOWN" if error else report["state"]}


def save_trial(value, write):
    return {"state": value["state"], "case": value["case"], "package": value["package"], "evidence_ref": write(value)}


def compare(parent, candidate, cases, target_id, *, write=None):
    rows, fixed, regressed, lost, unknown = [], [], [], [], []
    for data in cases:
        key = fingerprint(data)
        old, new = trial(parent, data), trial(candidate, data)
        rows.append({"case": key, "parent": save_trial(old, write) if write else old,
                     "candidate": save_trial(new, write) if write else new})
        if "UNKNOWN" in (old["state"], new["state"]): unknown.append(key)
        if old["state"] == "FALSE" and new["state"] == "TRUE": fixed.append(key)
        if old["state"] == "TRUE" and new["state"] != "TRUE": regressed.append(key)
        old_checks = {c["requirement_id"]: c["value"] for c in old["report"]["checks"]}
        new_checks = {c["requirement_id"]: c["value"] for c in new["report"]["checks"]}
        lost += [{"case": key, "requirement": k} for k in CHECK_IDS if old_checks[k] == "TRUE" and new_checks[k] != "TRUE"]
    target = next((r for r in rows if r["case"] == target_id), None)
    reasons = []
    if target is None: reasons.append("TARGET_MISSING")
    elif target["parent"]["state"] != "FALSE": reasons.append("FAILURE_NOT_REPRODUCED")
    elif target["candidate"]["state"] != "TRUE": reasons.append("TARGET_NOT_FIXED")
    if regressed or lost: reasons.append("REGRESSION")
    if any(r["candidate"]["state"] != "TRUE" for r in rows): reasons.append("CANDIDATE_NOT_ALL_PASSING")
    if fingerprint(parent) == fingerprint(candidate): reasons.append("NO_CHANGE")
    return {"decision": "INCONCLUSIVE" if unknown else "REJECT" if reasons else "ACCEPT_FOR_DEVELOPMENT",
            "reasons": reasons + (["UNKNOWN_EVIDENCE"] if unknown else []), "scheduled": len(rows),
            "fixed": fixed, "regressed": regressed, "requirements_lost": lost, "unknown": unknown, "rows": rows}


def challenges(seed, count=16, *, function=None, numeric=False):
    """Fresh generated inputs, independent of candidate code and expected answers.

    Vary the task's schema names, predicate values, direction, edge topology and
    cardinality. The unchanged completion checker derives every expected result.
    These are generated conformance cases, never native benchmark instances.
    """
    rng = random.Random(seed)
    result = []
    for number in range(count):
        prefix = f"g{seed:x}-{number}"
        kind, owner_kind = prefix + "Record", prefix + "Group"
        prop, region, relation = prefix + "state", prefix + "region", prefix + "belongs"
        wanted = rng.choice([True, 1, "open"])
        other = False if wanted is True else 2 if wanted == 1 else "closed"
        direction = "in" if number % 2 else "out"
        related = number % 4 != 0 if function is None else function == "related"
        selector = {"entity_type": kind, "where": {prop: wanted}}
        if related:
            selector["related"] = {"entity_type": owner_kind, "where": {region: "wanted"},
                                   "relation_type": relation, "direction": direction}
        if numeric:
            selector["numeric"] = [{"property": prefix + "quantity", "op": ("gte", "gt", "lte", "lt", "eq")[number % 5], "value": 3}]
        entities = [{"id": prefix + ":a", "type": owner_kind, "properties": {region: "wanted"}},
                    {"id": prefix + ":b", "type": owner_kind, "properties": {region: "other"}}]
        edges = []
        for i in range(number % 7):
            entity_id = prefix + ":r" + str(i)
            entities.append({"id": entity_id, "type": kind, "properties": {prop: rng.choice([wanted, other]), "done": False}})
            if numeric: entities[-1]["properties"][prefix + "quantity"] = rng.choice([1, 3, 5])
            for anchor in rng.sample(entities[:2], rng.randrange(3)):
                source, target = (entity_id, anchor["id"]) if direction == "out" else (anchor["id"], entity_id)
                edges.append({"source": source, "type": relation, "target": target})
        rng.shuffle(entities); rng.shuffle(edges)
        update = {"kind": "set_property", "property": "done", "value": True}
        if number % 5 == 0:
            update = {"kind": "ensure_relation", "relation_type": prefix + "selected", "anchor_id": prefix + ":a", "direction": direction}
        scope = "generated:" + prefix
        contract = {"version": 1, "goal": "Apply the declared update to every record satisfying the declared predicates and relationship; preserve all other state.",
                    "scope": scope, "selector": selector, "update": update}
        result.append({"contract": contract, "before": {"scope": scope, "revision": "0", "complete": True,
                       "entities": entities, "relations": edges}})
    return result

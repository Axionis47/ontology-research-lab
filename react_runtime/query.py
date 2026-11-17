"""Bounded read-only predicates over observed entities, using locked operators.

The caller supplies types and conditions. No target set is inferred from a task.
"""

from jsonschema import Draft202012Validator
from copy import deepcopy
from .completion import NUMERIC

QUERY_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "entity_type": {"type": "string"}, "where": {"type": "object", "maxProperties": 20}, "numeric": NUMERIC,
    "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}}


def query_schema(snapshot):
    observed = {}
    names = {str: "string", bool: "boolean", int: "number", float: "number", list: "array", dict: "object", type(None): "null"}
    for entity in snapshot["entities"]:
        fields = observed.setdefault(entity["type"], {})
        for name, value in entity["properties"].items(): fields.setdefault(name, set()).add(names[type(value)])
    branches = [{"type": "object", "properties": {}, "additionalProperties": False}]
    for kind, fields in sorted(observed.items()):
        schema = deepcopy(QUERY_SCHEMA)
        properties = schema["properties"]
        properties["entity_type"] = {"const": kind}
        properties["where"] = {"type": "object", "additionalProperties": False,
                               "properties": {name: {"type": sorted(types)} for name, types in fields.items()}}
        numeric_names = sorted(name for name, types in fields.items() if "number" in types)
        if numeric_names: properties["numeric"]["items"]["properties"]["property"] = {"enum": numeric_names}
        else: properties["numeric"]["maxItems"] = 0
        schema["required"] = ["entity_type"]
        branches.append(schema)
    # Native tool templates read root properties. Keep the per-type branches
    # for independent validation, and expose the shared argument vocabulary.
    properties = deepcopy(QUERY_SCHEMA["properties"])
    properties["entity_type"] = {"enum": sorted(observed)}
    merged = {}
    for fields in observed.values():
        for name, types in fields.items(): merged.setdefault(name, set()).update(types)
    properties["where"] = {"type": "object", "additionalProperties": False,
                           "properties": {name: {"type": sorted(types)} for name, types in merged.items()}}
    numeric_names = sorted(name for name, types in merged.items() if "number" in types)
    if numeric_names: properties["numeric"]["items"]["properties"]["property"] = {"enum": numeric_names}
    else: properties["numeric"]["maxItems"] = 0
    return {"type": "object", "properties": properties, "additionalProperties": False, "oneOf": branches}


def query_snapshot(snapshot, arguments):
    from repair_runtime.program import seed_package, select
    Draft202012Validator(query_schema(snapshot)).validate(arguments)
    if "entity_type" not in arguments:
        types = {}
        for entity in snapshot["entities"]:
            row = types.setdefault(entity["type"], {"count": 0, "properties": {}})
            row["count"] += 1
            for name, value in entity["properties"].items():
                row["properties"].setdefault(name, set()).add(type(value).__name__)
        return {"scope": snapshot["scope"], "revision": snapshot["revision"], "complete": snapshot["complete"],
            "types": {name: {"count": row["count"], "properties": {k: sorted(v) for k, v in row["properties"].items()}} for name, row in types.items()},
            "next_action": "Query with entity_type and caller-chosen where/numeric predicates. Empty predicates return all records of that type."}
    package = seed_package()
    package["functions"]["direct"]["nodes"].append({"op": "filter_numeric", "input": 1, "predicates": "selector.numeric"})
    package["functions"]["direct"]["return"] = 2
    selector = {k: arguments.get(k, default) for k, default in (("entity_type", ""), ("where", {}), ("numeric", []))}
    ids = select(package, {"selector": selector, "scope": snapshot["scope"]}, snapshot)["entity_ids"]
    offset, limit = arguments.get("offset", 0), arguments.get("limit", 10)
    page = set(ids[offset:offset + limit])
    return {"scope": snapshot["scope"], "revision": snapshot["revision"], "complete_scope": snapshot["complete"],
            "query": selector, "total_matches": len(ids), "next_offset": offset + limit if offset + limit < len(ids) else None,
            "entities": [e for e in snapshot["entities"] if e["id"] in page],
            "relations": [r for r in snapshot["relations"] if r["source"] in page or r["target"] in page]}

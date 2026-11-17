"""A deliberately finite program language over four existing OaK operators.

Programs contain slot paths and set references, never task values or Python.
The checker is independently implemented in react_runtime.completion.
"""

from copy import deepcopy
from itertools import product
import json


VERSION = 1
MAX_NODES = 8
MAX_ENTITIES = 2000
MAX_EDGES = 8000
MAX_WORK = 100000
TYPE_SLOTS = ("selector.entity_type", "selector.related.entity_type")
WHERE_SLOTS = ("selector.where", "selector.related.where")
NUMERIC_SLOTS = ("selector.numeric", "selector.related.numeric")
FUNCTIONS = ("direct", "related")


class Unsupported(ValueError):
    """The program cannot establish an answer within its contract/budget."""


def identity(value):
    # Keep bool distinct from integer while preserving JSON numeric equality.
    if isinstance(value, bool): return ("bool", value)
    if isinstance(value, (int, float)): return ("number", value)
    if isinstance(value, list): return ("list", tuple(identity(v) for v in value))
    if isinstance(value, dict): return ("object", tuple(sorted((k, identity(v)) for k, v in value.items())))
    return (type(value).__name__, value)


def slot(contract, path):
    value = contract
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            raise Unsupported("Unbound slot: " + path)
        value = value[key]
    return value


def function_name(contract):
    return "related" if "related" in contract["selector"] else "direct"


def validate_program(program, name):
    if not isinstance(program, dict) or set(program) != {"nodes", "return"}:
        raise ValueError("Program requires nodes and return")
    nodes = program["nodes"]
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= MAX_NODES:
        raise ValueError("Program node budget exceeded")
    for i, node in enumerate(nodes):
        if not isinstance(node, dict): raise ValueError("Invalid node")
        op = node.get("op")
        if op == "lookup_entities":
            if set(node) != {"op", "type"} or node["type"] not in TYPE_SLOTS:
                raise ValueError("Lookup type must be a declared input slot")
        elif op == "filter_property_categorical":
            if set(node) != {"op", "input", "where"} or node["where"] not in WHERE_SLOTS:
                raise ValueError("Filter predicates must be a declared input slot")
        elif op == "filter_numeric":
            if set(node) != {"op", "input", "predicates"} or node["predicates"] not in NUMERIC_SLOTS:
                raise ValueError("Numeric predicates must be a declared input slot")
        elif op == "filter_relation_connected":
            if (set(node) != {"op", "input", "anchors", "relation", "direction"}
                    or node["relation"] != "selector.related.relation_type"
                    or node["direction"] not in {"selector.related.direction", "in", "out"}):
                raise ValueError("Invalid relationship binding")
        else:
            raise ValueError("Unsupported operator: " + str(op))
        for key in ("input", "anchors"):
            if key in node and (type(node[key]) is not int or not 0 <= node[key] < i):
                raise ValueError("Set reference must point to an earlier node")
        if name == "direct" and any(isinstance(v, str) and "related" in v for v in node.values()):
            raise ValueError("Direct function cannot require a relationship slot")
    if type(program["return"]) is not int or not 0 <= program["return"] < len(nodes):
        raise ValueError("Invalid return reference")


def validate_package(package):
    if (not isinstance(package, dict) or set(package) != {"version", "functions"}
            or type(package["version"]) is not int or package["version"] != VERSION
            or not isinstance(package["functions"], dict) or set(package["functions"]) != set(FUNCTIONS)):
        raise ValueError("Invalid package")
    for name, program in package["functions"].items(): validate_program(program, name)


def seed_package():
    direct = {"nodes": [{"op": "lookup_entities", "type": TYPE_SLOTS[0]},
                        {"op": "filter_property_categorical", "input": 0, "where": WHERE_SLOTS[0]}], "return": 1}
    related = deepcopy(direct)
    # Initial coverage gap: related entities are discoverable, but not joined.
    related["nodes"] += [{"op": "lookup_entities", "type": TYPE_SLOTS[1]},
                         {"op": "filter_property_categorical", "input": 2, "where": WHERE_SLOTS[1]}]
    return {"version": VERSION, "functions": {"direct": direct, "related": related}}


def select(package, contract, snapshot, *, max_work=MAX_WORK):
    validate_package(package)
    if not snapshot.get("complete") or snapshot.get("scope") != contract.get("scope"):
        raise Unsupported("Complete evidence in the bound scope is required")
    raw, edges = snapshot["entities"], snapshot["relations"]
    if len(raw) > MAX_ENTITIES or len(edges) > MAX_EDGES:
        raise Unsupported("Observation exceeds supported scope size")
    entities = {e["id"]: e for e in raw}
    if len(entities) != len(raw) or any(e[k] not in entities for e in edges for k in ("source", "target")):
        raise Unsupported("Conflicting identities or unresolved relationship endpoint")
    work = 0

    def spend(amount):
        nonlocal work
        work += amount
        if work > max_work: raise Unsupported("Computation budget exhausted")

    program = package["functions"][function_name(contract)]
    values, trace = [], []
    for node in program["nodes"]:
        op = node["op"]
        if op == "lookup_entities":
            kind = slot(contract, node["type"])
            spend(len(entities))
            found = {k for k, e in entities.items() if e["type"] == kind}
        elif op == "filter_property_categorical":
            predicates = slot(contract, node["where"])
            found = set()
            for k in values[node["input"]]:
                props = entities[k]["properties"]
                spend(max(1, len(predicates)))
                # False evidence can resolve a conjunction despite another missing field.
                if any(p in props and identity(props[p]) != identity(v) for p, v in predicates.items()):
                    continue
                if any(p not in props for p in predicates):
                    raise Unsupported("Missing property needed by " + node["where"])
                found.add(k)
        elif op == "filter_numeric":
            # An absent optional numeric clause is the identity filter.
            path, key = node["predicates"].rsplit(".", 1)
            predicates = slot(contract, path).get(key, [])
            found = set()
            for k in values[node["input"]]:
                spend(max(1, len(predicates)))
                unresolved, rejected = False, False
                for predicate in predicates:
                    value = entities[k]["properties"].get(predicate["property"])
                    if type(value) not in (int, float):
                        unresolved = True
                        continue
                    bound, op = predicate["value"], predicate["op"]
                    rejected |= ((op == "gte" and value < bound) or (op == "gt" and value <= bound)
                                 or (op == "lte" and value > bound) or (op == "lt" and value >= bound)
                                 or (op == "eq" and value != bound))
                if rejected: continue
                if unresolved: raise Unsupported("Missing numeric evidence needed by " + node["predicates"])
                found.add(k)
        else:
            relation = slot(contract, node["relation"])
            direction = node["direction"]
            if direction.startswith("selector."): direction = slot(contract, direction)
            anchors = values[node["anchors"]]
            connected = set()
            spend(len(edges))
            for edge in edges:
                start, end = (edge["source"], edge["target"]) if direction == "out" else (edge["target"], edge["source"])
                if edge["type"] == relation and end in anchors: connected.add(start)
            found = values[node["input"]] & connected
        values.append(found)
        trace.append({"node": len(values) - 1, "op": op, "count": len(found)})
    return {"entity_ids": sorted(values[program["return"]]), "work": work, "trace": trace}


def mutations(package, name):
    """Enumerate one-node edits without looking at data, IDs or expected answers.

    The worker chooses among these by execution. New operators are not invented.
    Output rewiring, replacement and insertion cover existing composition gaps.
    """
    program = package["functions"][name]
    types = TYPE_SLOTS if name == "related" else TYPE_SLOTS[:1]
    predicates = WHERE_SLOTS if name == "related" else WHERE_SLOTS[:1]
    seen = set()

    def emit(nodes, output):
        proposed = {"nodes": nodes, "return": output}
        signature = json.dumps(proposed, sort_keys=True)
        if signature in seen or proposed == program: return None
        seen.add(signature)
        candidate = deepcopy(package)
        candidate["functions"][name] = proposed
        validate_package(candidate)
        return candidate

    for output in range(len(program["nodes"])):
        candidate = emit(program["nodes"], output)
        if candidate: yield candidate
    for position in [len(program["nodes"])] + list(range(len(program["nodes"]))):
        if position >= MAX_NODES: continue
        nodes = [{"op": "lookup_entities", "type": s} for s in types]
        nodes += [{"op": "filter_property_categorical", "input": i, "where": s}
                  for i, s in product(range(position), predicates)]
        nodes += [{"op": "filter_numeric", "input": i, "predicates": s}
                  for i, s in product(range(position), NUMERIC_SLOTS if name == "related" else NUMERIC_SLOTS[:1])]
        if name == "related":
            nodes += [{"op": "filter_relation_connected", "input": i, "anchors": j,
                       "relation": "selector.related.relation_type", "direction": d}
                      for i, j, d in product(range(position), range(position), ("selector.related.direction", "in", "out"))]
        for node in nodes:
            changed = deepcopy(program["nodes"])
            if position == len(changed): changed.append(node)
            else: changed[position] = node
            candidate = emit(changed, position if position == len(program["nodes"]) else program["return"])
            if candidate: yield candidate

"""Closed execution-policy vocabulary. Policies are data, never Python or prompts."""

from copy import deepcopy
import re

COMPONENTS = ("discovery", "binding", "context")
CHOICES = {
    "discovery": ("legacy", "exact", "weighted"),
    "binding": ("legacy", "observed", "constrained"),
    "context": ("legacy", "working"),
}

# A small interpreted instruction set. Limits constrain the editable mechanism,
# never the verifier, permissions, original schema, or episode budgets.
GRAMMAR = {
    "discovery": {
        "rank_catalogue": {"name_weight": [1, 8], "description_weight": [0, 4]},
        "inspect_shortlist": {"limit": [1, 5]},
        "observe_declared_state": {},
    },
    "binding": {"require_observed_ids": {}, "check_bound_update": {}},
    "context": {
        "bound_history": {"recent": [0, 3], "index": [0, 4]},
        "carry_state": {"fields": ["revision", "pending", "effects", "bindings"]},
        "detect_stagnation": {},
    },
}


def operations(policy, component):
    value = policy[component]
    if isinstance(value, list): return value
    if value == "legacy": return []
    if component == "discovery":
        return [{"op": "rank_catalogue", "name_weight": 1 if value == "exact" else 4, "description_weight": 1},
                {"op": "inspect_shortlist", "limit": 3}] + ([{"op": "observe_declared_state"}] if value == "weighted" else [])
    if component == "binding":
        return [{"op": "require_observed_ids"}] + ([{"op": "check_bound_update"}] if value == "constrained" else [])
    return [{"op": "bound_history", "recent": 2, "index": 4},
            {"op": "carry_state", "fields": ["revision", "pending", "effects", "bindings"]},
            {"op": "detect_stagnation"}]


def instruction(policy, component, op):
    return next((s for s in operations(policy, component) if s["op"] == op), None)


def ranking(policy):
    value = policy["discovery"]
    if isinstance(value, str): return value
    step = instruction(policy, "discovery", "rank_catalogue")
    return {k: step[k] for k in ("name_weight", "description_weight")} if step else "legacy"


def legacy_policy():
    return {"version": 1, **{key: "legacy" for key in COMPONENTS}}


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) != {"version", *COMPONENTS} or type(policy["version"]) is not int or policy["version"] not in {1, 2}:
        raise ValueError("Invalid execution-policy bundle")
    for component in COMPONENTS:
        value = policy[component]
        if isinstance(value, str):
            if value not in CHOICES[component]: raise ValueError("Unregistered policy strategy")
            continue
        if policy["version"] != 2 or not isinstance(value, list) or not 1 <= len(value) <= len(GRAMMAR[component]):
            raise ValueError("Expected a bounded instruction list")
        seen, last = set(), -1
        for step in value:
            if not isinstance(step, dict) or step.get("op") not in GRAMMAR[component]: raise ValueError("Unknown policy instruction")
            op = step["op"]
            spec = GRAMMAR[component][op]
            order = list(GRAMMAR[component]).index(op)
            if op in seen or order <= last or set(step) != {"op", *spec}: raise ValueError("Invalid policy instruction order or fields")
            seen.add(op); last = order
            for key, bounds in spec.items():
                if key == "fields":
                    if not isinstance(step[key], list) or not step[key] or any(v not in bounds for v in step[key]) or len(set(step[key])) != len(step[key]):
                        raise ValueError("Invalid carried state fields")
                elif type(step[key]) is not int or not bounds[0] <= step[key] <= bounds[1]: raise ValueError("Policy parameter outside bounds")
        if "inspect_shortlist" in seen and "rank_catalogue" not in seen: raise ValueError("Inspect requires ranking")
        if "check_bound_update" in seen and "require_observed_ids" not in seen: raise ValueError("Bound check requires observed bindings")
        if component == "context" and "bound_history" not in seen: raise ValueError("Context plan requires bounded history")
    return deepcopy(policy)


def changed_component(parent, candidate):
    validate_policy(parent); validate_policy(candidate)
    changed = [key for key in COMPONENTS if operations(parent, key) != operations(candidate, key)]
    if len(changed) != 1: raise ValueError("A policy candidate must change exactly one component")
    return changed[0]


def candidates(parent, component):
    if component not in COMPONENTS: raise ValueError("Unknown repair component")
    for strategy in CHOICES[component]:
        if strategy != parent[component]:
            yield {**parent, component: strategy}


def tokens(text):
    # Word boundaries prevent follow from matching unfollow. Conservative noun
    # plural normalization makes an artist schema discoverable for artists.
    words = re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)
    stop = {"a", "an", "the", "all", "on", "in", "of", "to", "and", "or", "that", "have", "has", "with", "at", "least", "please"}
    return {w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words if w not in stop}


def rank_tools(tools, query, strategy):
    if isinstance(strategy, dict):
        validate_policy({**legacy_policy(), "version": 2, "discovery": [{"op": "rank_catalogue", **strategy}]})
    elif strategy not in {"exact", "weighted"}: raise ValueError("Unknown catalogue ranking strategy")
    wanted = tokens(query)
    ranked = []
    for tool in tools:
        name = tokens(tool["name"])
        description = tokens(tool.get("description", ""))
        overlap = wanted & (name | description)
        if wanted and not overlap: continue
        if isinstance(strategy, dict): score = strategy["name_weight"] * len(wanted & name) + strategy["description_weight"] * len(wanted & description)
        else: score = len(overlap) if strategy == "exact" else 4 * len(wanted & name) + len(wanted & description)
        ranked.append((-score, tool["name"], tool))
    return [t for _, _, t in sorted(ranked)]


def input_schema(schema):
    """Provider projection; admission always uses the complete original schema."""
    schema = deepcopy(schema)
    if schema.get("type") == "object":
        schema.setdefault("properties", {})
        schema.setdefault("required", [])
        # query_schema has a shared root vocabulary and duplicate per-type
        # branches. Keep the full branches at admission, not in every token view.
        if schema["properties"]: schema.pop("oneOf", None)
    return schema

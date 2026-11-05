"""Lossless prompt projection of repeated construction semantics and feedback.

Artifacts remain authoritative and unchanged. Interning is restricted to
declared semantic containers, feedback and parent functions. Source documents,
schemas and tool contracts remain untouched. No semantic rewrite occurs.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from copy import deepcopy

from oak.store import canonical

_FORMAT = "oak.construction-context"
_VERSION = 2
_PREFIXES = {"program": "p", "field": "f", "operation": "o", "input_domain": "d", "shared": "s"}
_SHARED_SLOTS = (
    "validation_feedback",
    "execution_feedback",
    "parent_functions",
    "requirements",
    "task_ir",
    "behavior_bank",
    "obligations",
)
_SHARED_PROGRAMS = "definitions.programs"
_PROGRAM_CONTAINERS = (
    ("requirements", "interpretations"),
    ("task_ir", "obligations"),
    ("behavior_bank", "behaviors"),
)
_INSTRUCTIONS = (
    "Lossless inputs encoding; all definitions are included. First, in shared_slots "
    "(inputs members or definitions.programs), replace {$shared:ID} with literal "
    "definitions.shared[ID], without recursively interpreting its contents. Then "
    "{$program:ID}, {$field:ID}, {$operation:ID}, {$input_domain:ID} refer respectively "
    "to definitions.programs, fields, operations, input_domains. Substitute values "
    "exactly, preserving order, metadata, IDs and denominators. References do not "
    "change the requested output contract."
)


def _program_slots(inputs):
    """Visit only the explicit semantic containers of a construction request."""
    containers = [inputs.get("obligations", [])]
    for name, collection in _PROGRAM_CONTAINERS:
        container = inputs.get(name)
        if isinstance(container, dict):
            containers.append(container.get(collection, []))
    for collection in containers:
        if isinstance(collection, list):
            for item in collection:
                if isinstance(item, dict) and "program" in item:
                    yield item


def _is_program(value):
    """Recognize serialized programs without validating or normalizing them."""
    return (
        isinstance(value, dict)
        and isinstance(value.get("fields"), list)
        and all(isinstance(item, dict) for item in value["fields"])
        and isinstance(value.get("operations"), list)
        and bool(value["operations"])
        and all(isinstance(item, dict) for item in value["operations"])
        and isinstance(value.get("input_domain"), dict)
        and isinstance(value.get("result"), str)
        and isinstance(value.get("observation_contract"), str)
    )


def _shared_projection(inputs, intern):
    """Count repeated values, then encode only repeated values that save bytes.

    A selected parent remains a complete literal definition. Its children are
    never encoded inside that definition, which prevents recursive references.
    The second pass discounts occurrences hidden by selected parents.
    """
    counts = Counter()
    eligible_slots = []

    def visit(value, counts):
        if isinstance(value, (dict, list, str)):
            encoded = canonical(value)
            if len(encoded) > 32:
                counts[encoded] += 1
        if isinstance(value, dict):
            if set(value) == {"$shared"}:
                return False
            return all(visit(item, counts) for item in value.values())
        if isinstance(value, list):
            return all(visit(item, counts) for item in value)
        return True

    for slot in (*_SHARED_SLOTS, _SHARED_PROGRAMS):
        if slot in inputs:
            local = Counter()
            # A literal source value using our reference syntax keeps its
            # entire slot untouched, so it can never be decoded accidentally.
            if visit(inputs[slot], local):
                eligible_slots.append(slot)
                counts.update(local)

    def worthwhile(encoded, count):
        reference_bytes = 32  # {"$shared":"s_" + sixteen hex digits}
        definition_key_bytes = 22
        return (count - 1) * len(encoded) > count * reference_bytes + definition_key_bytes

    selected = {encoded for encoded, count in counts.items() if worthwhile(encoded, count)}
    visible = Counter()

    def walk(value, emit):
        encoded = canonical(value) if isinstance(value, (dict, list, str)) else None
        if encoded in selected:
            visible[encoded] += 1
            return intern("shared", "shared", value) if emit else value
        if isinstance(value, dict):
            return {key: walk(item, emit) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item, emit) for item in value]
        return value

    for slot in eligible_slots:
        walk(inputs[slot], False)
    selected = {encoded for encoded in selected if worthwhile(encoded, visible[encoded])}
    for slot in eligible_slots:
        inputs[slot] = walk(inputs[slot], True)
    return eligible_slots


def compact_construction_context(inputs: dict) -> dict:
    """Intern exact repeated programs, fields, operations and input domains.

    Content-derived IDs are deterministic and independent of traversal order.
    Short hash collisions fail explicitly rather than overwrite a definition.
    Other data, including missing or null programs, remains unchanged. The
    returned JSON object is detached from the caller and expands exactly.
    """
    if not isinstance(inputs, dict):
        raise TypeError("Construction context must be an object")
    canonical(inputs)  # Reject non-JSON values or cycles before traversing.
    projected = deepcopy(inputs)
    definitions = {name: {} for name in ("programs", "fields", "operations", "input_domains")}

    def intern(collection, kind, value):
        encoded = canonical(value)
        identity = _PREFIXES[kind] + "_" + hashlib.sha256(encoded).hexdigest()[:16]
        definitions.setdefault(collection, {})
        if (
            identity in definitions[collection]
            and canonical(definitions[collection][identity]) != encoded
        ):
            raise ValueError(f"Construction context definition ID collision: {identity}")
        definitions.setdefault(collection, {})[identity] = deepcopy(value)
        return {"$" + kind: identity}

    for slot in _program_slots(projected):
        if not _is_program(slot["program"]):
            continue
        # deepcopy(inputs) intentionally preserves aliases. Detach this value
        # again so another slot sharing the original program stays unencoded.
        program = deepcopy(slot["program"])
        program["fields"] = [intern("fields", "field", item) for item in program["fields"]]
        program["operations"] = [
            intern("operations", "operation", item) for item in program["operations"]
        ]
        program["input_domain"] = intern("input_domains", "input_domain", program["input_domain"])
        slot["program"] = intern("programs", "program", program)
    shared_targets = {name: projected[name] for name in _SHARED_SLOTS if name in projected}
    shared_targets[_SHARED_PROGRAMS] = definitions["programs"]
    shared_slots = _shared_projection(shared_targets, intern)
    for name, value in shared_targets.items():
        if name == _SHARED_PROGRAMS:
            definitions["programs"] = value
        else:
            projected[name] = value
    return {
        "format": _FORMAT,
        "version": _VERSION,
        "reference_instructions": _INSTRUCTIONS,
        "definitions": definitions,
        "shared_slots": shared_slots,
        "inputs": projected,
    }


def expand_construction_context(context: dict) -> dict:
    """Reconstruct an encoded request exactly, rejecting missing definitions.

    Expansion is local inspection and testing only. It does not read files,
    fetch references, evaluate task programs, or modify the supplied context.
    """
    if context.get("format") != _FORMAT or context.get("version") not in {1, _VERSION}:
        raise ValueError("Unsupported construction context encoding")
    result = deepcopy(context["inputs"])
    definitions = deepcopy(context["definitions"])

    def resolve(collection, kind, reference):
        if not isinstance(reference, dict) or set(reference) != {"$" + kind}:
            raise ValueError(f"Invalid {kind} reference")
        identity = reference["$" + kind]
        try:
            value = definitions[collection][identity]
        except (KeyError, TypeError) as error:
            raise ValueError(f"Missing {kind} definition: {identity}") from error
        expected = _PREFIXES[kind] + "_" + hashlib.sha256(canonical(value)).hexdigest()[:16]
        if identity != expected:
            raise ValueError(f"Changed {kind} definition: {identity}")
        return deepcopy(value)

    def expand_shared(value):
        if isinstance(value, dict):
            if set(value) == {"$shared"}:
                return resolve("shared", "shared", value)
            return {key: expand_shared(item) for key, item in value.items()}
        if isinstance(value, list):
            return [expand_shared(item) for item in value]
        return value

    if context["version"] == _VERSION:
        for name in context.get("shared_slots", []):
            if name == _SHARED_PROGRAMS:
                definitions["programs"] = expand_shared(definitions["programs"])
                continue
            if name not in _SHARED_SLOTS or name not in result:
                raise ValueError("Invalid shared construction context slot")
            result[name] = expand_shared(result[name])

    for slot in _program_slots(result):
        if not isinstance(slot["program"], dict) or set(slot["program"]) != {"$program"}:
            continue
        program = resolve("programs", "program", slot["program"])
        program["fields"] = [resolve("fields", "field", item) for item in program["fields"]]
        program["operations"] = [
            resolve("operations", "operation", item) for item in program["operations"]
        ]
        program["input_domain"] = resolve("input_domains", "input_domain", program["input_domain"])
        slot["program"] = program
    return result

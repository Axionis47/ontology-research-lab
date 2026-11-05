"""Lossless prompt projection of repeated construction task programs.

Artifacts remain authoritative and unchanged. Only declared semantic program
slots are interned, so source documents and tool contracts cannot accidentally
be interpreted as task programs. No model call or semantic rewrite occurs.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy

from oak.store import canonical

_FORMAT = "oak.construction-context"
_VERSION = 1
_PREFIXES = {"program": "p", "field": "f", "operation": "o", "input_domain": "d"}
_PROGRAM_CONTAINERS = (
    ("requirements", "interpretations"),
    ("task_ir", "obligations"),
    ("behavior_bank", "behaviors"),
)
_INSTRUCTIONS = (
    "Lossless reference encoding. The inputs member is the original request. "
    "At semantic program slots, {$program: ID} means definitions.programs[ID]. "
    "Within a program definition, fields contain {$field: ID} references to "
    "definitions.fields, operations contain {$operation: ID} references to "
    "definitions.operations, and input_domain contains {$input_domain: ID} "
    "referencing definitions.input_domains. Substitute the referenced values "
    "without changing list order, metadata, IDs, defaults, or denominators. "
    "Every definition is included here; no external lookup is needed. "
    "References are encoding only and do not change the requested output contract."
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


def compact_construction_context(inputs: dict) -> dict:
    """Intern exact repeated programs, fields, operations and input domains.

    Content-derived IDs are deterministic and independent of traversal order.
    Short hash collisions fail explicitly rather than overwrite a definition.
    Other data, including missing or null programs, remains unchanged. The
    returned JSON object is detached from the caller and expands exactly.
    """
    if not isinstance(inputs, dict):
        raise TypeError("Construction context must be an object")
    projected = deepcopy(inputs)
    definitions = {name: {} for name in ("programs", "fields", "operations", "input_domains")}

    def intern(collection, kind, value):
        encoded = canonical(value)
        identity = _PREFIXES[kind] + "_" + hashlib.sha256(encoded).hexdigest()[:16]
        if (
            identity in definitions[collection]
            and canonical(definitions[collection][identity]) != encoded
        ):
            raise ValueError(f"Construction context definition ID collision: {identity}")
        definitions[collection][identity] = deepcopy(value)
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
    return {
        "format": _FORMAT,
        "version": _VERSION,
        "reference_instructions": _INSTRUCTIONS,
        "definitions": definitions,
        "inputs": projected,
    }


def expand_construction_context(context: dict) -> dict:
    """Reconstruct an encoded request exactly, rejecting missing definitions.

    Expansion is local inspection and testing only. It does not read files,
    fetch references, evaluate task programs, or modify the supplied context.
    """
    if context.get("format") != _FORMAT or context.get("version") != _VERSION:
        raise ValueError("Unsupported construction context encoding")
    result = deepcopy(context["inputs"])
    definitions = context["definitions"]

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

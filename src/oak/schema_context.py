"""Exact, version-bound ontology declarations for inference context discovery.

These views are presentations of the full frozen schema, never replacement
ontologies. The executor, graph validator, HermiT, and historical replay retain
the authoritative complete schema. Dependencies are resolved from the supported
ontology grammar, without model inference, external lookup, or guessed links.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy

from oak.materialization import EvidenceDemand
from oak.ontology import SchemaSpec, parse_schema
from oak.store import canonical


class SchemaContextError(ValueError):
    """A requested schema context cannot be presented faithfully within bounds."""


def _pointer(*parts: str | int) -> str:
    return "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def _document(schema: dict | SchemaSpec) -> dict:
    return schema.model_dump(mode="json") if isinstance(schema, SchemaSpec) else deepcopy(schema)


def schema_entries(schema: dict | SchemaSpec) -> dict[str, dict]:
    """Index exact declarations and their semantic dependencies by JSON Pointer.

    A type entry retains its exact original definition, including optional
    properties. Optional members also have individual entries so callers can
    inspect them without loading the whole type. Dependency lists identify
    validation requirements, rather than declaring every optional member needed.
    Consumers must page oversized definitions instead of truncating them.
    """
    source = _document(schema)
    spec = parse_schema(source)
    entries = {}
    reverse_disjoints = {name: [] for name in spec.entity_types}
    inverse_relations = {name: [] for name in spec.relations}
    for name, entity in spec.entity_types.items():
        for other in entity.disjoint_with:
            reverse_disjoints[other].append(name)
    for name, relation in spec.relations.items():
        if relation.inverse_of:
            inverse_relations[relation.inverse_of].append(name)

    def add(identity, kind, name, definition, dependencies, description=None):
        entries[identity] = {
            "kind": kind,
            "name": name,
            "description": description or "",
            "definition": deepcopy(definition),
            "dependencies": sorted(set(dependencies)),
        }

    for name, entity in spec.entity_types.items():
        type_id = _pointer("entity_types", name)
        dependencies = [
            _pointer("entity_types", name, "properties", prop)
            for prop, declaration in entity.properties.items()
            if prop == entity.primary_key or declaration.required
        ]
        dependencies.extend(_pointer("entity_types", other) for other in entity.parents)
        dependencies.extend(_pointer("entity_types", other) for other in entity.disjoint_with)
        dependencies.extend(_pointer("entity_types", other) for other in reverse_disjoints[name])
        dependencies.extend(
            _pointer("entity_types", name, "restrictions", index)
            for index in range(len(entity.restrictions))
        )
        add(
            type_id,
            "entity_type",
            name,
            source["entity_types"][name],
            dependencies,
            entity.description,
        )
        for prop, declaration in entity.properties.items():
            add(
                _pointer("entity_types", name, "properties", prop),
                "property",
                f"{name}.{prop}",
                source["entity_types"][name]["properties"][prop],
                [type_id],
                declaration.description,
            )
        for index, restriction in enumerate(entity.restrictions):
            if restriction.property in spec.relations:
                dependencies = [
                    type_id,
                    _pointer("relations", restriction.property),
                    _pointer("entity_types", restriction.filler),
                ]
            else:
                owner, prop = restriction.property.split(".")
                dependencies = [type_id, _pointer("entity_types", owner, "properties", prop)]
            add(
                _pointer("entity_types", name, "restrictions", index),
                "restriction",
                f"{name}: {restriction.property} {restriction.kind}",
                source["entity_types"][name]["restrictions"][index],
                dependencies,
            )
    for name, relation in spec.relations.items():
        dependencies = [
            _pointer("entity_types", relation.source),
            _pointer("entity_types", relation.target),
        ]
        if relation.inverse_of:
            dependencies.append(_pointer("relations", relation.inverse_of))
        dependencies.extend(_pointer("relations", other) for other in inverse_relations[name])
        add(
            _pointer("relations", name),
            "relation",
            name,
            source.get("relations", {})[name],
            dependencies,
            relation.description,
        )
    return entries


def extraction_schema_context(
    schema: dict | SchemaSpec, demand: EvidenceDemand | dict, *, max_bytes: int = 40_000
) -> dict:
    """Present the exact demanded declarations and their constraint closure.

    Selected properties keep their original declarations. Keys, required fields,
    inherited constraints, restriction targets, disjoint types, relation endpoints,
    and inverse relations are included even when not explicitly requested. The
    view is not asserted to preserve all OWL consequences of the original schema;
    full-schema validation remains mandatory outside the model context.

    An oversized closure is an explicit recoverable context error. Callers can
    narrow the executable demand or inspect further declarations through catalog
    expansion. They must not silently discard dependencies or send an unbounded
    full schema as a fallback.
    """
    if type(max_bytes) is not int or max_bytes < 256:
        raise ValueError("Schema context max_bytes must be an integer of at least 256")
    source = _document(schema)
    spec = parse_schema(source)
    demand = EvidenceDemand.model_validate(demand) if isinstance(demand, dict) else demand
    schema_sha256 = hashlib.sha256(canonical(source)).hexdigest()
    if schema_sha256 != demand.schema_sha256:
        raise SchemaContextError("Evidence demand belongs to another frozen schema revision")
    entries = schema_entries(source)
    selected_types = set(demand.entity_types) | set(demand.required_fields)
    selected_relations = set(demand.relation_types)
    for selector in demand.selectors:
        selected_types.update(selector.entity_types)
    for traversal in demand.traversals:
        selected_relations.update(traversal.relation_types)
    absent_types = selected_types - spec.entity_types.keys()
    absent_relations = selected_relations - spec.relations.keys()
    if absent_types or absent_relations:
        raise SchemaContextError(
            f"Demand references undeclared types or relations: {sorted(absent_types | absent_relations)}"
        )
    pending = [_pointer("entity_types", name) for name in sorted(selected_types)]
    pending.extend(_pointer("relations", name) for name in sorted(selected_relations))
    requested_fields = {name: set(fields) for name, fields in demand.required_fields.items()}
    for selector in demand.selectors:
        for name in selector.entity_types or sorted(selected_types):
            requested_fields.setdefault(name, set()).update(selector.primary_key)
            requested_fields[name].update(selector.property_filters)
    for name, fields in requested_fields.items():
        for field in fields:
            owners = [
                owner
                for owner in sorted({name} | spec.ancestors(name))
                if field in spec.entity_types[owner].properties
            ]
            if not owners:
                raise SchemaContextError(f"Demand references undeclared property {name}.{field}")
            pending.extend(_pointer("entity_types", owner, "properties", field) for owner in owners)
    included = set()
    while pending:
        identity = pending.pop()
        if identity in included:
            continue
        if identity not in entries:
            raise SchemaContextError(f"Schema dependency has no exact declaration: {identity}")
        included.add(identity)
        pending.extend(entries[identity]["dependencies"])
    types, relations = {}, {}
    for name, definition in source["entity_types"].items():
        if _pointer("entity_types", name) not in included:
            continue
        types[name] = {
            **deepcopy(definition),
            "properties": {
                field: deepcopy(declaration)
                for field, declaration in definition["properties"].items()
                if _pointer("entity_types", name, "properties", field) in included
            },
        }
    for name, definition in source.get("relations", {}).items():
        if _pointer("relations", name) in included:
            relations[name] = deepcopy(definition)
    # The partial presentation intentionally omits non-declaration top-level
    # prose. A large global description must not be repeated for every query.
    presentation = {
        "schema_version": source.get("schema_version", 1),
        "name": source["name"],
        "entity_types": types,
        "relations": relations,
    }
    result = {
        "format_version": 1,
        "kind": "inference_schema_context",
        "schema_sha256": schema_sha256,
        "demand_id": demand.demand_id,
        "complete_schema": False,
        "schema": presentation,
        "declaration_refs": sorted(included),
        "requested_entity_types": sorted(selected_types),
        "requested_relation_types": sorted(selected_relations),
        "dependency_entity_types": sorted(set(types) - selected_types),
        "omitted": {
            "entity_types": len(spec.entity_types) - len(types),
            "relations": len(spec.relations) - len(relations),
            "properties": sum(len(entity.properties) for entity in spec.entity_types.values())
            - sum(len(entity["properties"]) for entity in types.values()),
        },
        "validation": "The executor validates all extracted records against the full frozen schema.",
    }
    measured = len(canonical(result))
    if measured > max_bytes:
        raise SchemaContextError(
            f"Dependency-closed schema module is {measured} bytes, above the {max_bytes} byte bound; "
            "select a narrower valid callable/demand or inspect definitions through catalog expansion. "
            "No declarations were silently dropped."
        )
    return result

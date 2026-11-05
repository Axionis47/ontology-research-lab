"""Deterministic graph translation for shared historical replay adapter edges.

The DSL copies existing typed facts. Record projections express property
relocation and splits; complete one-to-one keyed joins express recombination.
It cannot supply values, branch on cases, evaluate code, or acquire evidence.
This module checks graph integrity. OWL/HermiT validation remains a separate
required piece of candidate evidence, not a claim made by this interpreter.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from oak.ontology import SchemaSpec, parse_schema, validate_graph_records
from oak.store import canonical

MAX_MIGRATED_NODES = 100_000
MAX_MIGRATED_EDGES = 200_000


class MigrationContract(BaseModel):
    """Reject unknown fields and coercion in a finite transformation program."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class PropertySource(MigrationContract):
    """Copy a property from one declared source alias, retaining missingness."""

    source: str = Field(min_length=1)
    property: str = Field(min_length=1)


class RecordIdentity(MigrationContract):
    """Preserve one source ID or derive an ID from named target key properties."""

    source: str | None = None
    keys: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def exclusive_strategy(self) -> RecordIdentity:
        if bool(self.source) == bool(self.keys):
            raise ValueError("Record identity requires exactly one of source or keys")
        if len(self.keys) != len(set(self.keys)) or any(not key for key in self.keys):
            raise ValueError("Identity keys must be distinct nonempty property names")
        return self


class RecordProjection(MigrationContract):
    """Replace source records with copied fields under one target type.

    A single source requires no join. Multiple source types require one-to-one
    joins over equal nonempty key lists and an explicit ordering anchor. Every
    source row must match exactly once. Multiple projections of one source type
    form a split. All facts of replaced source records must remain represented
    across those projections; deliberate information deletion is unsupported.
    """

    sources: dict[str, str] = Field(min_length=1, max_length=8)
    join_keys: dict[str, list[str]] = Field(default_factory=dict)
    anchor: str | None = None
    target_type: str = Field(min_length=1)
    properties: dict[str, PropertySource] = Field(min_length=1, max_length=256)
    identity: RecordIdentity

    @model_validator(mode="after")
    def references_and_keys(self) -> RecordProjection:
        if any(not alias or not kind for alias, kind in self.sources.items()):
            raise ValueError("Sources require nonempty aliases and entity types")
        if len(set(self.sources.values())) != len(self.sources):
            raise ValueError("Self joins are unsupported; source entity types must be distinct")
        if self.anchor is not None and self.anchor not in self.sources:
            raise ValueError("Ordering anchor must name a source alias")
        if len(self.sources) > 1:
            if self.anchor is None or set(self.join_keys) != set(self.sources):
                raise ValueError("Joins require an explicit anchor and keys for every source")
            widths = {len(keys) for keys in self.join_keys.values()}
            if len(widths) != 1 or 0 in widths:
                raise ValueError("Join keys must have the same nonzero arity")
            if any(len(keys) != len(set(keys)) for keys in self.join_keys.values()):
                raise ValueError("Join keys must be distinct property names")
        elif self.join_keys:
            raise ValueError("A single source projection does not accept join keys")
        if any(ref.source not in self.sources for ref in self.properties.values()):
            raise ValueError("Property mappings must refer to declared source aliases")
        if self.identity.source is not None and self.identity.source not in self.sources:
            raise ValueError("Preserved identity must refer to a declared source alias")
        if not set(self.identity.keys).issubset(self.properties):
            raise ValueError("Derived identity keys must name copied target properties")
        return self


class EndpointTypes(MigrationContract):
    """Select one mapped type per endpoint when a split creates alternatives."""

    source: str | None = None
    target: str | None = None


class DerivedRelation(MigrationContract):
    """Connect two outputs derived from the same actual source record."""

    source_type: str = Field(min_length=1)
    source_target_type: str = Field(min_length=1)
    target_target_type: str = Field(min_length=1)
    relation: str = Field(min_length=1)


class MigrationSpec(MigrationContract):
    """One shared graph transformation, independent of tasks and expected answers.

    Renames and identity remaps address original types and original properties.
    Explicit record projections replace all records of their source types and
    cannot overlap rename/remap rules for those types. Relations retain their
    order, multiplicity, and provenance. An explicitly contracted relation may
    disappear only when a keyed join maps both endpoints to the same record.
    """

    version: Literal[1] = 1
    type_renames: dict[str, str] = Field(default_factory=dict, max_length=256)
    property_renames: dict[str, dict[str, str]] = Field(default_factory=dict, max_length=256)
    relation_renames: dict[str, str] = Field(default_factory=dict, max_length=256)
    identity_remaps: dict[str, list[str]] = Field(default_factory=dict, max_length=256)
    records: list[RecordProjection] = Field(default_factory=list, max_length=64)
    endpoint_types: dict[str, EndpointTypes] = Field(default_factory=dict, max_length=256)
    derived_relations: list[DerivedRelation] = Field(default_factory=list, max_length=128)
    contracted_relations: list[str] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def disjoint_operations(self) -> MigrationSpec:
        replaced = {kind for rule in self.records for kind in rule.sources.values()}
        renamed = set(self.type_renames) | set(self.property_renames) | set(self.identity_remaps)
        if replaced & renamed:
            raise ValueError("Record projections cannot overlap rename or identity-remap rules")
        if len(self.contracted_relations) != len(set(self.contracted_relations)):
            raise ValueError("Contracted relations must be distinct")
        if set(self.contracted_relations) & (set(self.relation_renames) | set(self.endpoint_types)):
            raise ValueError("Contracted relations cannot also be renamed or remapped")
        for keys in self.identity_remaps.values():
            if not keys or len(keys) > 16 or len(keys) != len(set(keys)):
                raise ValueError("Identity remaps require one to sixteen distinct key properties")
        return self


class MigrationError(ValueError):
    """An attributable unsupported or invalid transformation, never a partial success."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.details = details


def _properties(schema: SchemaSpec, kind: str) -> dict:
    if kind not in schema.entity_types:
        raise MigrationError("unknown_type", f"Undeclared entity type {kind!r}")
    return {
        name: prop
        for scope in [*sorted(schema.ancestors(kind)), kind]
        for name, prop in schema.entity_types[scope].properties.items()
    }


def _validate_program(spec: MigrationSpec, old: SchemaSpec, new: SchemaSpec) -> None:
    """Validate declared references even when the retained graph has no rows."""
    for kind in set(spec.type_renames) | set(spec.property_renames) | set(spec.identity_remaps):
        properties = _properties(old, kind)
        target = spec.type_renames.get(kind, kind)
        target_properties = _properties(new, target)
        renames = spec.property_renames.get(kind, {})
        if not set(renames).issubset(properties):
            raise MigrationError("unknown_property", f"Property rename is undeclared on {kind}")
        names = [renames.get(name, name) for name in properties]
        if len(names) != len(set(names)):
            raise MigrationError("property_collision", f"Property renames collide on {kind}")
        if not set(names).issubset(target_properties):
            raise MigrationError("unknown_property", f"Renamed fields are undeclared on {target}")
        for key in spec.identity_remaps.get(kind, []):
            if key not in properties or not properties[key].functional:
                raise MigrationError("invalid_key", f"Identity key {kind}.{key} must be scalar")
    old_relations = set(spec.relation_renames) | set(spec.endpoint_types)
    old_relations |= set(spec.contracted_relations)
    if not old_relations.issubset(old.relations):
        raise MigrationError(
            "unknown_relation", "A relation mapping is undeclared in the old schema"
        )
    if not set(spec.relation_renames.values()).issubset(new.relations):
        raise MigrationError(
            "unknown_relation", "A renamed relation is undeclared in the new schema"
        )
    for endpoints in spec.endpoint_types.values():
        for kind in (endpoints.source, endpoints.target):
            if kind is not None:
                _properties(new, kind)
    represented: dict[str, set[str]] = {}
    for rule in spec.records:
        target_properties = _properties(new, rule.target_type)
        for alias, kind in rule.sources.items():
            properties = _properties(old, kind)
            represented.setdefault(kind, set())
            for key in rule.join_keys.get(alias, []):
                if key not in properties or not properties[key].functional:
                    raise MigrationError("invalid_key", f"Join key {kind}.{key} must be scalar")
        for name, ref in rule.properties.items():
            kind = rule.sources[ref.source]
            source_properties = _properties(old, kind)
            if ref.property not in source_properties or name not in target_properties:
                raise MigrationError(
                    "unknown_property",
                    f"Undeclared copied property {kind}.{ref.property} -> {rule.target_type}.{name}",
                )
            source_property, target_property = (
                source_properties[ref.property],
                target_properties[name],
            )
            if (source_property.type, source_property.functional) != (
                target_property.type,
                target_property.functional,
            ):
                raise MigrationError(
                    "property_contract",
                    f"Copy changes datatype or multiplicity at {rule.target_type}.{name}",
                )
            represented[kind].add(ref.property)
        for key in rule.identity.keys:
            if not target_properties[key].functional:
                raise MigrationError(
                    "invalid_key", f"Identity key {rule.target_type}.{key} must be scalar"
                )
        # An equal join key copied from one side also represents that same
        # typed fact on the other sides. Runtime joins check exact key equality.
        if rule.join_keys:
            copied = {(ref.source, ref.property) for ref in rule.properties.values()}
            for position in range(len(next(iter(rule.join_keys.values())))):
                if any((alias, keys[position]) in copied for alias, keys in rule.join_keys.items()):
                    for alias, keys in rule.join_keys.items():
                        represented[rule.sources[alias]].add(keys[position])
    for kind, fields in represented.items():
        missing = set(_properties(old, kind)) - fields
        if missing:
            raise MigrationError(
                "lost_properties", f"Replacement of {kind} omits properties {sorted(missing)}"
            )
    for rule in spec.derived_relations:
        _properties(old, rule.source_type)
        _properties(new, rule.source_target_type)
        _properties(new, rule.target_target_type)
        if rule.relation not in new.relations:
            raise MigrationError(
                "unknown_relation", f"Derived relation {rule.relation} is undeclared"
            )


def _key(properties: dict, keys: list[str], context: str) -> bytes:
    for key in keys:
        if key not in properties or properties[key] is None:
            raise MigrationError("missing_key", f"Missing key {key!r} in {context}")
        if not isinstance(properties[key], (str, int, float, bool)):
            raise MigrationError("invalid_key", f"Key {key!r} in {context} is not scalar")
    return canonical([properties[key] for key in keys])


def _identity(kind: str, properties: dict, keys: list[str]) -> str:
    values = _key(properties, keys, kind)
    return "migrated:" + hashlib.sha256(canonical([kind, keys]) + b":" + values).hexdigest()


def _joined_rows(rule: RecordProjection, by_type: dict[str, list[dict]]) -> list[dict]:
    aliases = sorted(rule.sources)
    if len(aliases) == 1:
        alias = aliases[0]
        return [{alias: node} for node in by_type.get(rule.sources[alias], [])]
    indexes: dict[str, dict[bytes, dict]] = {}
    for alias, kind in sorted(rule.sources.items()):
        index: dict[bytes, dict] = {}
        for node in by_type.get(kind, []):
            key = _key(node["properties"], rule.join_keys[alias], node["id"])
            if key in index:
                raise MigrationError(
                    "ambiguous_join",
                    f"Join key is not unique for {kind}",
                    node_ids=[index[key]["id"], node["id"]],
                )
            index[key] = node
        indexes[alias] = index
    anchor = rule.anchor
    keys = set(indexes[anchor])
    if any(set(index) != keys for index in indexes.values()):
        raise MigrationError(
            "unmatched_join", "Every source row must have exactly one matching keyed row"
        )
    return [{alias: indexes[alias][key] for alias in aliases} for key in indexes[anchor]]


def _provenance(nodes: list[dict]) -> list[dict]:
    """Use multiset union so split/join does not erase or amplify attribution."""
    sources, maximum_counts = [], {}
    for node in nodes:
        local_counts: dict[bytes, int] = {}
        for source in node["sources"]:
            key = canonical(source)
            local_counts[key] = local_counts.get(key, 0) + 1
            if local_counts[key] > maximum_counts.get(key, 0):
                sources.append(deepcopy(source))
                maximum_counts[key] = local_counts[key]
    return sources


def migrate_graph(
    graph: dict,
    spec: MigrationSpec | dict,
    old_schema: dict | SchemaSpec,
    new_schema: dict | SchemaSpec,
) -> dict:
    """Translate a retained graph without modifying inputs or acquiring evidence.

    Returns ``graph``, ``identity_mapping`` (old IDs to ordered target-ID lists),
    and ``derivations`` for actual copied nodes and rewritten/derived relations.
    Graph metadata is retained, with existing node/edge counts updated. Invalid
    graphs, fact loss, ambiguous joins, collisions, and unresolved endpoints
    raise ``MigrationError``. No partially translated graph is returned.

    Programs operate only on declared types and properties. Schema semantics
    are not inferred from names. Candidate replay establishes observational
    preservation separately by executing current-kernel functions.
    """
    program = MigrationSpec.model_validate(
        spec.model_dump(mode="json") if isinstance(spec, MigrationSpec) else deepcopy(spec)
    )
    old, new = parse_schema(old_schema), parse_schema(new_schema)
    if (
        not isinstance(graph, dict)
        or not isinstance(graph.get("nodes"), list)
        or not isinstance(graph.get("edges", []), list)
    ):
        raise MigrationError("invalid_graph", "Graph requires nodes and optional edges lists")
    if len(graph["nodes"]) > MAX_MIGRATED_NODES or len(graph.get("edges", [])) > MAX_MIGRATED_EDGES:
        raise MigrationError("resource_limit", "Input graph exceeds the migration record limit")
    validation = validate_graph_records(old, graph["nodes"], graph.get("edges", []))
    if not validation["valid"]:
        raise MigrationError(
            "invalid_old_graph", "Original graph failed integrity validation", validation=validation
        )
    _validate_program(program, old, new)
    original = deepcopy(graph)
    by_type: dict[str, list[dict]] = {}
    for node in original["nodes"]:
        by_type.setdefault(node["type"], []).append(node)
    replaced = {kind for rule in program.records for kind in rule.sources.values()}
    replacements: dict[str, list[tuple[dict, dict]]] = {}
    identity_mapping: dict[str, list[str]] = {node["id"]: [] for node in original["nodes"]}
    projected_count = 0
    for index, rule in enumerate(program.records):
        anchor = rule.anchor or next(iter(rule.sources))
        for row in _joined_rows(rule, by_type):
            if projected_count >= MAX_MIGRATED_NODES:
                raise MigrationError("resource_limit", "Record projection exceeds the node limit")
            projected_count += 1
            properties = {
                name: deepcopy(row[ref.source]["properties"][ref.property])
                for name, ref in rule.properties.items()
                if ref.property in row[ref.source]["properties"]
            }
            identity = (
                row[rule.identity.source]["id"]
                if rule.identity.source
                else _identity(rule.target_type, properties, rule.identity.keys)
            )
            node = {
                "id": identity,
                "type": rule.target_type,
                "properties": properties,
                "sources": _provenance(list(row.values())),
            }
            inputs = [row[alias]["id"] for alias in sorted(rule.sources)]
            derivation = {
                "operation": "record_projection",
                "rule": index,
                "input_ids": inputs,
                "output_id": identity,
            }
            replacements.setdefault(row[anchor]["id"], []).append((node, derivation))
            for input_id in inputs:
                identity_mapping[input_id].append(identity)
    nodes, derivations = [], []
    for old_node in original["nodes"]:
        if old_node["type"] in replaced:
            for node, derivation in replacements.get(old_node["id"], []):
                nodes.append(node)
                derivations.append(derivation)
            continue
        node = deepcopy(old_node)
        old_type = old_node["type"]
        node["type"] = program.type_renames.get(old_type, old_type)
        renames = program.property_renames.get(old_type, {})
        node["properties"] = {
            renames.get(key, key): value for key, value in node["properties"].items()
        }
        if old_type in program.identity_remaps:
            keys = [renames.get(key, key) for key in program.identity_remaps[old_type]]
            node["id"] = _identity(node["type"], node["properties"], keys)
        nodes.append(node)
        identity_mapping[old_node["id"]] = [node["id"]]
        derivations.append(
            {
                "operation": "identity" if node == old_node else "rename",
                "input_ids": [old_node["id"]],
                "output_id": node["id"],
            }
        )
    by_id = {node["id"]: node for node in nodes}
    if len(by_id) != len(nodes):
        raise MigrationError("identity_collision", "Different translated records have the same ID")
    if len(nodes) > MAX_MIGRATED_NODES:
        raise MigrationError("resource_limit", "Translated graph exceeds the node limit")
    if any(not ids for ids in identity_mapping.values()):
        raise MigrationError("lost_record", "A source record has no translated representation")

    def endpoint(identity: str, kind: str | None = None) -> str:
        candidates = identity_mapping[identity]
        if kind is not None:
            candidates = [item for item in candidates if by_id[item]["type"] == kind]
        if len(candidates) != 1:
            raise MigrationError(
                "ambiguous_endpoint",
                f"Source {identity} requires exactly one target endpoint of type {kind!r}",
                candidates=candidates,
            )
        return candidates[0]

    edges = []
    for index, old_edge in enumerate(original.get("edges", [])):
        relation = old_edge["relation"]
        if relation in program.contracted_relations:
            source, target = endpoint(old_edge["source"]), endpoint(old_edge["target"])
            if source != target or old_edge["source"] == old_edge["target"]:
                raise MigrationError(
                    "invalid_contraction",
                    "Contracted relation endpoints must be distinct inputs joined into one target",
                )
            derivations.append(
                {
                    "operation": "contract_relation",
                    "input_edge": index,
                    "output_id": source,
                    "sources": deepcopy(old_edge["sources"]),
                }
            )
            continue
        selection = program.endpoint_types.get(relation, EndpointTypes())
        edge = deepcopy(old_edge)
        edge.update(
            source=endpoint(old_edge["source"], selection.source),
            target=endpoint(old_edge["target"], selection.target),
            relation=program.relation_renames.get(relation, relation),
        )
        edges.append(edge)
        derivations.append(
            {"operation": "relation", "input_edge": index, "output_edge": len(edges) - 1}
        )
    pairs = {(edge["relation"], edge["source"], edge["target"]) for edge in edges}
    for index, rule in enumerate(program.derived_relations):
        for node in by_type.get(rule.source_type, []):
            if len(edges) >= MAX_MIGRATED_EDGES:
                raise MigrationError("resource_limit", "Derived relations exceed the edge limit")
            edge = {
                "source": endpoint(node["id"], rule.source_target_type),
                "target": endpoint(node["id"], rule.target_target_type),
                "relation": rule.relation,
                "sources": deepcopy(node["sources"]),
            }
            pair = (edge["relation"], edge["source"], edge["target"])
            if pair in pairs:
                raise MigrationError(
                    "duplicate_derivation",
                    "A derived relation would duplicate an existing translated relation",
                )
            pairs.add(pair)
            edges.append(edge)
            derivations.append(
                {
                    "operation": "derive_relation",
                    "rule": index,
                    "input_ids": [node["id"]],
                    "output_edge": len(edges) - 1,
                }
            )
    result = {**original, "nodes": nodes, "edges": edges}
    for name, values in (("node_count", nodes), ("edge_count", edges)):
        if name in result:
            result[name] = len(values)
    validation = validate_graph_records(new, nodes, edges)
    if not validation["valid"]:
        raise MigrationError(
            "invalid_new_graph",
            "Translated graph failed integrity validation",
            validation=validation,
        )
    return {"graph": result, "identity_mapping": identity_mapping, "derivations": derivations}

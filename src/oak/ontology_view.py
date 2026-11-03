"""Readable, provenance-preserving projections of saved ontology artifacts.

These helpers do not reason, validate, mutate a revision, or invent graph edges.
Human labels are presentation only; every node and declaration retains its exact
identifier. A bounded graph view explicitly reports what it leaves out.
"""

from __future__ import annotations

import copy
import json
import re
from collections import Counter, defaultdict
from typing import Any

from oak.ontology import RestrictionSpec, SchemaSpec, parse_schema

_HASH = re.compile(r"(?i)(?<![a-z0-9])[a-f0-9]{32,}(?![a-z0-9])")
_DATATYPES = {
    "string": "Text",
    "integer": "Whole number",
    "number": "Number",
    "boolean": "True or false",
    "date_time": "Date and time",
}
_SEMANTICS = [
    "This view shows saved declarations and explicit records, not inferred relationships.",
    "Required fields are checked in explicit records and translated to OWL minimum cardinality 1. "
    "OWL uses an open world: a missing explicit value can be unknown, rather than inconsistent.",
    "Functional means at most one value. It does not require that a value exists.",
    "Primary keys identify explicit records within their concrete type. They are not owl:hasKey axioms.",
    "Descriptions are schema annotations, not additional executable constraints or verified source facts.",
]


def humanize(identifier: str) -> str:
    """Separate identifier words without changing the identifier used by the engine."""
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", str(identifier))
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"[_\s]+", " ", text).strip()
    return text[:1].upper() + text[1:]


def property_rows(schema: dict[str, Any] | SchemaSpec, type_name: str) -> list[dict[str, Any]]:
    """Describe every applicable declaration, retaining distinct inherited scopes.

    A child and parent can both declare a field named ``Date``. They are distinct
    OWL properties and both record checks apply, so this projection never merges
    those rows into an apparent override.
    """
    spec = parse_schema(schema)
    rows = []
    for owner in [type_name, *sorted(spec.ancestors(type_name))]:
        entity = spec.entity_types[owner]
        for name, prop in entity.properties.items():
            key = name == entity.primary_key
            required = prop.required or key
            record_rule = "Required" if required else "Optional"
            record_rule += "; one scalar value" if prop.functional else "; list of values"
            if key and owner == type_name:
                record_rule += "; unique primary key within this concrete type"
            ontology = (
                ["At most one value (functional)"]
                if prop.functional
                else ["No functional limit in this declaration"]
            )
            if required:
                ontology.append("at least one value of the declared datatype (minimum 1)")
            else:
                ontology.append("no existence requirement from this declaration")
            rows.append(
                {
                    "name": name,
                    "label": humanize(name),
                    "qualified_name": f"{owner}.{name}",
                    "type": prop.type,
                    "datatype_label": _DATATYPES[prop.type],
                    "declared_by": owner,
                    "declared_by_label": humanize(owner),
                    "inherited": owner != type_name,
                    "required": required,
                    "functional": prop.functional,
                    "primary_key": key,
                    "record_rule": record_rule,
                    "ontology_rule": "; ".join(ontology) + ".",
                    "description": prop.description or "",
                }
            )
    return rows


def _restriction_text(spec: SchemaSpec, owner: str, rule: RestrictionSpec) -> str:
    prop = (
        humanize(rule.property)
        if rule.property in spec.relations
        else ".".join(humanize(part) for part in rule.property.split("."))
    )
    filler = (
        humanize(rule.filler)
        if rule.property in spec.relations
        else _DATATYPES[rule.filler].lower()
    )
    subject = humanize(owner)
    if rule.kind == "only":
        return f"{subject}: every {prop} value must be {filler}; this alone does not require any value."
    if rule.kind == "some":
        return f"{subject}: at least one {prop} value must be {filler}."
    quantity = {"min": "at least", "max": "at most", "exact": "exactly"}[rule.kind]
    return f"{subject}: {quantity} {rule.cardinality} {prop} value(s) of type {filler}."


def _relation_details(name: str, relation: Any) -> list[str]:
    source, target, label = map(humanize, (relation.source, relation.target, name))
    details = [
        f"{source} → {label} → {target}.",
        "Domain and range classify relation endpoints; they do not require a relationship to exist.",
    ]
    wording = {
        "functional": "At most one distinct target for each source (functional).",
        "inverse_functional": "At most one distinct source for each target (inverse functional).",
        "transitive": "If A relates to B and B relates to C, A relates to C (transitive).",
        "symmetric": "If A relates to B, B relates to A (symmetric).",
        "asymmetric": "If A relates to B, B cannot relate to A (asymmetric).",
        "reflexive": "Every individual relates to itself (reflexive).",
        "irreflexive": "No individual can relate to itself (irreflexive).",
    }
    details.extend(wording[flag] for flag in relation.characteristics)
    if relation.inverse_of:
        details.append(f"Inverse of {humanize(relation.inverse_of)}: its direction is reversed.")
    if relation.description:
        details.append(relation.description)
    return details


def schema_view(
    schema: dict[str, Any] | SchemaSpec, graph: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return class nodes, distinct edge kinds, and full readable declarations.

    ``direct_count`` counts saved explicit types. ``compatible_count`` also counts
    records explicitly typed as descendants, without materializing extra nodes.
    """
    spec = parse_schema(schema)
    counts = Counter(node["type"] for node in (graph or {}).get("nodes", []))
    nodes, edges, relations = [], [], []
    disjoint_pairs = set()
    disjoint_by_type: dict[str, set[str]] = defaultdict(set)
    for name, entity in spec.entity_types.items():
        for other in entity.disjoint_with:
            disjoint_by_type[name].add(other)
            disjoint_by_type[other].add(name)
    for name, entity in spec.entity_types.items():
        constraints = []
        for owner in [name, *sorted(spec.ancestors(name))]:
            constraints.extend(
                {
                    "declared_by": owner,
                    "inherited": owner != name,
                    "text": _restriction_text(spec, owner, restriction),
                    **restriction.model_dump(),
                }
                for restriction in spec.entity_types[owner].restrictions
            )
        compatible_count = sum(
            count
            for child, count in counts.items()
            if child in spec.entity_types and name in {child, *spec.ancestors(child)}
        )
        details = [entity.description] if entity.description else []
        details.extend(f"Is a {humanize(parent)}." for parent in entity.parents)
        for owner in [name, *sorted(spec.ancestors(name))]:
            details.extend(
                f"No individual can belong to both {humanize(owner)} and {humanize(other)} "
                f"(disjoint classes{', inherited' if owner != name else ''})."
                for other in sorted(disjoint_by_type[owner])
            )
        details.extend(row["text"] for row in constraints)
        node = {
            "id": name,
            "label": humanize(name),
            "kind": "class",
            "subtitle": f"{counts[name]:,} explicit records",
            "description": entity.description or "",
            "properties": property_rows(spec, name),
            "restrictions": constraints,
            "parents": list(entity.parents),
            "ancestors": sorted(spec.ancestors(name)),
            "disjoint_with": list(entity.disjoint_with),
            "primary_key": entity.primary_key,
            "direct_count": counts[name],
            "compatible_count": compatible_count,
            "details": details,
        }
        nodes.append(node)
        for parent in entity.parents:
            edges.append(
                {
                    "id": f"parent:{name}:{parent}",
                    "source": name,
                    "target": parent,
                    "label": "is a",
                    "kind": "inheritance",
                    "details": [f"Every {humanize(name)} is also a {humanize(parent)}."],
                }
            )
        for other in entity.disjoint_with:
            pair = tuple(sorted((name, other)))
            if pair not in disjoint_pairs:
                disjoint_pairs.add(pair)
                edges.append(
                    {
                        "id": f"disjoint:{pair[0]}:{pair[1]}",
                        "source": pair[0],
                        "target": pair[1],
                        "label": "disjoint with",
                        "kind": "disjoint",
                        "details": [
                            f"No individual can belong to both {humanize(pair[0])} and {humanize(pair[1])}."
                        ],
                    }
                )
    for name, relation in spec.relations.items():
        relation_details = _relation_details(name, relation)
        relation_details.extend(
            f"Inverse of {humanize(other)}: its direction is reversed."
            for other, declaration in spec.relations.items()
            if declaration.inverse_of == name and relation.inverse_of != other
        )
        item = {
            "id": name,
            "label": humanize(name),
            "kind": "relation",
            "source": relation.source,
            "target": relation.target,
            "source_label": humanize(relation.source),
            "target_label": humanize(relation.target),
            "description": relation.description or "",
            "characteristics": list(relation.characteristics),
            "inverse_of": relation.inverse_of,
            "details": relation_details,
        }
        relations.append(item)
        edges.append({**copy.deepcopy(item), "id": f"relation:{name}"})
    return {
        "name": humanize(spec.name),
        "description": spec.description or "",
        "nodes": nodes,
        "edges": edges,
        "types": {node["id"]: node for node in nodes},
        "relations": relations,
        "semantics": list(_SEMANTICS),
    }


def _display_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def _readable_value(value: Any) -> bool:
    return value is not None and str(value).strip() != "" and not _HASH.search(str(value))


def _entity_label(node: dict[str, Any], spec: SchemaSpec) -> tuple[str, list[str]]:
    """Prefer semantic names, dates, and measures to opaque record identities."""
    values = node.get("properties", {})
    type_name = node["type"]
    entity = spec.entity_types.get(type_name)
    primary_key = entity.primary_key if entity else None
    candidates = [(name, value) for name, value in values.items() if _readable_value(value)]
    for preferred in ("name", "title", "label", "place"):
        for name, value in candidates:
            words = humanize(name).lower().split()
            if preferred in words and isinstance(value, str):
                return value, [name]
    for name, value in candidates:
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T.*)?", value):
            return value, [name]
    measures = [
        (name, value)
        for name, value in candidates
        if name != primary_key
        and not set(humanize(name).lower().split()) & {"id", "identifier", "key"}
    ]
    if measures:
        chosen = measures[:2]
        return " · ".join(f"{humanize(name)}: {_display_value(value)}" for name, value in chosen), [
            name for name, _ in chosen
        ]
    if primary_key in values and _readable_value(values[primary_key]):
        value = str(values[primary_key])
        if "://" in value or value.startswith("urn:"):
            value = re.split(r"[/#:]", value.rstrip("/#"))[-1]
        if value and not _HASH.search(value):
            return humanize(value), [primary_key]
    return humanize(type_name), []


def entity_catalog(
    schema: dict[str, Any] | SchemaSpec, graph: dict[str, Any]
) -> list[dict[str, Any]]:
    """Label real records and preserve exact fields, source references, and IDs.

    Duplicate labels receive stable ordinals sorted by real source references
    and identifiers. Units are never guessed from a domain: field names and
    saved descriptions remain visible with each value.
    """
    spec = parse_schema(schema)
    declarations = {name: property_rows(spec, name) for name in spec.entity_types}
    nodes, groups = [], defaultdict(list)
    for raw in graph.get("nodes", []):
        base_label, label_properties = _entity_label(raw, spec)
        properties = []
        for row in declarations.get(raw["type"], []):
            properties.append(
                {
                    **row,
                    "value": copy.deepcopy(raw.get("properties", {}).get(row["name"])),
                    "present": row["name"] in raw.get("properties", {}),
                }
            )
        declared_names = {row["name"] for row in properties}
        for name, value in raw.get("properties", {}).items():
            if name not in declared_names:
                properties.append(
                    {
                        "name": name,
                        "label": humanize(name),
                        "value": copy.deepcopy(value),
                        "present": True,
                        "description": "Undeclared field in this saved graph.",
                    }
                )
        node = {
            "id": raw["id"],
            "label": base_label,
            "base_label": base_label,
            "label_properties": label_properties,
            "kind": "entity",
            "type": raw["type"],
            "type_label": humanize(raw["type"]),
            "subtitle": humanize(raw["type"]),
            "properties": properties,
            "values": copy.deepcopy(raw.get("properties", {})),
            "sources": copy.deepcopy(raw.get("sources", [])),
            "details": [spec.entity_types[raw["type"]].description or ""]
            if raw["type"] in spec.entity_types
            else ["Type is not declared in this schema."],
        }
        nodes.append(node)
        groups[base_label].append(node)
    for same_label in groups.values():
        if len(same_label) > 1:
            ordered = sorted(
                same_label,
                key=lambda item: (json.dumps(item["sources"], sort_keys=True), item["id"]),
            )
            for index, item in enumerate(ordered, 1):
                item["label"] += f" ({index})"
                item["label_ordinal"] = index
    return sorted(nodes, key=lambda item: (item["type_label"], item["label"], item["id"]))


def instance_view(
    schema: dict[str, Any] | SchemaSpec,
    graph: dict[str, Any],
    *,
    focus_id: str | None = None,
    type_name: str | None = None,
    search: str = "",
    max_nodes: int = 80,
    hops: int = 1,
    max_edges: int = 240,
) -> dict[str, Any]:
    """Return a bounded explicit graph, or a focus node's undirected neighborhood.

    Browse mode applies search and type filters, including named descendants.
    Focus mode follows actual edges in either direction regardless of filters,
    then preserves their original direction. Bounds and omissions are reported.
    """
    if not 1 <= max_nodes <= 300 or not 0 <= hops <= 3 or not 1 <= max_edges <= 2000:
        raise ValueError("View bounds require 1..300 nodes, 0..3 hops, and 1..2000 edges")
    spec = parse_schema(schema)
    if type_name is not None and type_name not in spec.entity_types:
        raise ValueError(f"Unknown entity type: {type_name}")
    catalog = entity_catalog(spec, graph)
    by_id = {node["id"]: node for node in catalog}
    needle = search.strip().casefold()
    matching = [
        node
        for node in catalog
        if (
            type_name is None
            or (
                node["type"] in spec.entity_types
                and type_name in {node["type"], *spec.ancestors(node["type"])}
            )
        )
        and (
            not needle
            or needle
            in json.dumps(
                [node["label"], node["type_label"], node["values"]], ensure_ascii=False
            ).casefold()
        )
    ]
    if focus_id is not None:
        if focus_id not in by_id:
            raise ValueError("Focus entity is not present in this saved graph")
        adjacency = defaultdict(set)
        for edge in graph.get("edges", []):
            if edge["source"] in by_id and edge["target"] in by_id:
                adjacency[edge["source"]].add(edge["target"])
                adjacency[edge["target"]].add(edge["source"])
        reached, frontier = {focus_id}, {focus_id}
        for _ in range(hops):
            frontier = {other for node in frontier for other in adjacency[node]} - reached
            reached.update(frontier)
        eligible = [
            by_id[focus_id],
            *(node for node in catalog if node["id"] in reached and node["id"] != focus_id),
        ]
        scope = f"Explicit neighborhood within {hops} hop(s) of {by_id[focus_id]['label']}; neighbors may have other types."
    else:
        eligible = matching
        scope = "Matching saved entities; edges are shown only when both endpoints are displayed."
    shown = eligible[:max_nodes]
    selected = {node["id"] for node in shown}
    edges = [
        {
            "id": f"edge:{index}",
            "source": edge["source"],
            "target": edge["target"],
            "label": humanize(edge["relation"]),
            "relation": edge["relation"],
            "kind": "relation",
            "sources": copy.deepcopy(edge.get("sources", [])),
            "details": [
                f"{by_id[edge['source']]['label']} → {humanize(edge['relation'])} → {by_id[edge['target']]['label']}.",
                "Explicit saved relationship; not an inferred edge.",
            ],
        }
        for index, edge in enumerate(graph.get("edges", []))
        if edge["source"] in selected and edge["target"] in selected
    ]
    visible_edges = edges[:max_edges]
    return {
        "nodes": shown,
        "edges": visible_edges,
        "total_nodes": len(catalog),
        "matching_nodes": len(matching),
        "eligible_nodes": len(eligible),
        "shown_nodes": len(shown),
        "omitted_nodes": len(catalog) - len(shown),
        "truncated_nodes": len(eligible) - len(shown),
        "total_edges": len(graph.get("edges", [])),
        "shown_edges": len(visible_edges),
        "omitted_edges": len(graph.get("edges", [])) - len(visible_edges),
        "truncated_edges": len(edges) - len(visible_edges),
        "focus_id": focus_id,
        "scope": scope,
        "max_nodes": max_nodes,
        "hops": hops,
    }

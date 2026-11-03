"""Bounded implementations of OaK's generic graph and data operators.

Condition/result shapes are explicit engineering choices for paper Appendix B.
These operators execute on real supplied graph values. They do not call providers,
invent missing data, or read files. Runtime-slot extraction requires a real caller-
supplied model callback.
"""

from __future__ import annotations

import inspect
import math
from collections.abc import Callable, Iterable
from copy import deepcopy
from decimal import Decimal
from typing import Any, Literal, get_args

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class OperatorError(ValueError):
    """An unsupported operation, invalid contract, or invalid source value."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CategoricalCondition(StrictModel):
    property: str
    operator: Literal["in", "not_in"] = "in"
    values: list[JsonValue]


class NumericCondition(StrictModel):
    property: str
    operator: Literal["==", "!=", "<", "<=", ">", ">=", "between"]
    value: int | float | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None

    @model_validator(mode="after")
    def check_operands(self) -> NumericCondition:
        if self.operator == "between":
            if self.minimum is None or self.maximum is None or self.value is not None:
                raise ValueError("between requires minimum and maximum, without value")
            if number(self.minimum) > number(self.maximum):
                raise ValueError("minimum must not exceed maximum")
        elif self.value is None or self.minimum is not None or self.maximum is not None:
            raise ValueError("Numeric comparison requires value only")
        if self.value is not None:
            number(self.value)
        return self


class RelationCondition(StrictModel):
    relation: str
    anchor_ids: list[str] = Field(min_length=1)
    direction: Literal["outgoing", "incoming", "both"] = "outgoing"
    mode: Literal["any", "all"] = "any"


class SetCondition(StrictModel):
    property: str
    values: list[str | int | float | bool | None]
    mode: Literal["any", "all", "minimum"] = "any"
    minimum_overlap: int = Field(default=1, ge=0)


class AggregateRequest(StrictModel):
    operation: Literal["count", "sum", "min", "max", "mean", "average"]
    field: str | None = None
    group_by: str | None = None
    nulls: Literal["error", "skip"] = "error"

    @model_validator(mode="after")
    def check_field(self) -> AggregateRequest:
        if self.operation != "count" and self.field is None:
            raise ValueError("Numeric aggregation requires a field")
        if self.operation == "count" and self.field is not None:
            raise ValueError("count counts items; omit field")
        return self


def number(value: Any) -> Decimal:
    """Read a finite numeric value without accepting booleans or numeric strings."""
    if isinstance(value, bool) or not isinstance(value, int | float | Decimal):
        raise OperatorError(f"Expected a finite number, received {type(value).__name__}")
    result = Decimal(str(value))
    if not result.is_finite():
        raise OperatorError("Non-finite values are not supported")
    return result


def _json_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    result = float(value)
    if not math.isfinite(result):
        raise OperatorError("Numeric result exceeds finite JSON number range")
    return result


def entity_list(value: Any) -> list[dict[str, Any]]:
    """Accept an entity list or an explicit traversal/lookup result."""
    values = value.get("entities") if isinstance(value, dict) else value
    if not isinstance(values, list):
        raise OperatorError("Expected an entity list or result containing entities")
    if any(
        not isinstance(item, dict) or not {"id", "type", "properties"} <= item.keys()
        for item in values
    ):
        raise OperatorError("Each entity requires id, type, and properties")
    return values


def network(graph: dict[str, Any]) -> nx.MultiDiGraph:
    """Build the NetworkX graph while rejecting missing endpoints or duplicate IDs."""
    result = nx.MultiDiGraph()
    for entity in entity_list(graph.get("nodes")):
        if not isinstance(entity["id"], str) or entity["id"] in result:
            raise OperatorError("Graph entity IDs must be unique strings")
        result.add_node(entity["id"], entity=deepcopy(entity))
    for index, relation in enumerate(graph.get("edges", [])):
        if relation["source"] not in result or relation["target"] not in result:
            raise OperatorError("Graph relation references an unknown endpoint")
        result.add_edge(
            relation["source"], relation["target"], key=index, relation=deepcopy(relation)
        )
    return result


def lookup_entities(
    graph: dict[str, Any],
    *,
    entity_types: list[str] | None = None,
    entity_ids: list[str] | None = None,
    primary_key: dict[str, Any] | None = None,
    property_filters: dict[str, Any] | None = None,
    name_query: str | None = None,
    text_query: str | None = None,
    fuzzy: bool = True,
    top_k: int | None = None,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Look up entities by exact types, IDs, keys, and properties in stable ID order.

    Text/fuzzy ranking is explicitly unsupported in this first implementation.
    The paper does not define its ranking semantics; use structured filters.
    """
    if name_query is not None or text_query is not None or min_score != 0:
        raise OperatorError("Text/name ranking is unsupported; use exact property_filters")
    if top_k is not None and (isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1):
        raise OperatorError("top_k must be a positive integer")
    filters = dict(primary_key or {})
    for key, value in (property_filters or {}).items():
        if key in filters and filters[key] != value:
            raise OperatorError(f"Conflicting exact filters for {key}")
        filters[key] = value
    net = network(graph)
    matches = []
    for identifier in sorted(net.nodes):
        entity = net.nodes[identifier]["entity"]
        if entity_types is not None and entity["type"] not in entity_types:
            continue
        if entity_ids is not None and identifier not in entity_ids:
            continue
        if all(
            key in entity["properties"] and entity["properties"][key] == value
            for key, value in filters.items()
        ):
            matches.append(entity)
    return matches if top_k is None else matches[:top_k]


def traverse_relations(
    graph: dict[str, Any],
    *,
    start_entity_ids: list[str],
    relation_types: list[str] | None = None,
    direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    max_hops: int = 1,
    include_starting_entities: bool = True,
) -> dict[str, Any]:
    """Traverse matching actual relations with deterministic ordering and at most 8 hops."""
    if direction not in {"outgoing", "incoming", "both"}:
        raise OperatorError("direction must be outgoing, incoming, or both")
    if isinstance(max_hops, bool) or not isinstance(max_hops, int) or not 0 <= max_hops <= 8:
        raise OperatorError("max_hops must be an integer between 0 and 8")
    net = network(graph)
    if any(identifier not in net for identifier in start_entity_ids):
        raise OperatorError("Traversal seed does not exist in the graph")
    visited = set(start_entity_ids)
    frontier = set(start_entity_ids)
    selected_edges: dict[int, dict[str, Any]] = {}
    for _ in range(max_hops):
        next_frontier = set()
        for identifier in sorted(frontier):
            candidates = []
            if direction in {"outgoing", "both"}:
                candidates.extend(net.out_edges(identifier, keys=True, data=True))
            if direction in {"incoming", "both"}:
                candidates.extend(net.in_edges(identifier, keys=True, data=True))
            for source, target, key, data in candidates:
                relation = data["relation"]
                if relation_types is not None and relation["relation"] not in relation_types:
                    continue
                selected_edges[key] = relation
                neighbor = target if source == identifier else source
                if neighbor not in visited:
                    next_frontier.add(neighbor)
        visited.update(next_frontier)
        frontier = next_frontier
    included = visited if include_starting_entities else visited - set(start_entity_ids)
    return {
        "entities": [deepcopy(net.nodes[identifier]["entity"]) for identifier in sorted(included)],
        "relations": [selected_edges[key] for key in sorted(selected_edges)],
    }


def project_properties(
    entities: Any,
    *,
    property_names: list[str],
    missing_value: Any = None,
) -> list[dict[str, Any]]:
    """Project properties while retaining entity IDs, types, and available primary keys."""
    selected = entity_list(entities)
    reserved = {"__entity_id", "__entity_type", "__primary_key", "__sources"}
    if reserved.intersection(property_names):
        raise OperatorError("Projection property collides with reserved provenance metadata")
    return [
        {
            "__entity_id": entity["id"],
            "__entity_type": entity["type"],
            "__sources": deepcopy(entity.get("sources", [])),
            **(
                {"__primary_key": deepcopy(entity["primary_key"])}
                if "primary_key" in entity
                else {}
            ),
            **{
                name: deepcopy(entity["properties"].get(name, missing_value))
                for name in property_names
            },
        }
        for entity in selected
    ]


def filter_property_categorical(
    entities: Any,
    *,
    conditions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """AND exact inclusion/exclusion conditions; missing or null values do not match."""
    checks = [CategoricalCondition.model_validate(condition) for condition in conditions]

    def matches(entity: dict[str, Any]) -> bool:
        for check in checks:
            if check.property not in entity["properties"]:
                return False
            value = entity["properties"][check.property]
            if value is None:
                return False
            contained = value in check.values
            if contained != (check.operator == "in"):
                return False
        return True

    return [deepcopy(entity) for entity in entity_list(entities) if matches(entity)]


filter_categorical = filter_property_categorical


def filter_numeric(entities: Any, *, conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """AND numeric comparisons; between is inclusive, and missing/null never matches."""
    checks = [NumericCondition.model_validate(condition) for condition in conditions]

    def matches(entity: dict[str, Any]) -> bool:
        for check in checks:
            raw = entity["properties"].get(check.property)
            if raw is None:
                return False
            actual = number(raw)
            if check.operator == "between":
                accepted = number(check.minimum) <= actual <= number(check.maximum)
            else:
                expected = number(check.value)
                accepted = {
                    "==": actual == expected,
                    "!=": actual != expected,
                    "<": actual < expected,
                    "<=": actual <= expected,
                    ">": actual > expected,
                    ">=": actual >= expected,
                }[check.operator]
            if not accepted:
                return False
        return True

    return [deepcopy(entity) for entity in entity_list(entities) if matches(entity)]


def filter_set_overlap(entities: Any, *, conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter actual multivalued properties by any/all/minimum unique overlap."""
    checks = [SetCondition.model_validate(condition) for condition in conditions]

    def matches(entity: dict[str, Any]) -> bool:
        for check in checks:
            value = entity["properties"].get(check.property)
            if value is None:
                return False
            if not isinstance(value, list):
                raise OperatorError(
                    f"{check.property} must contain a list for set-overlap filtering"
                )
            try:
                overlap = set(value).intersection(check.values)
            except TypeError as error:
                raise OperatorError("Set-overlap values must be scalar") from error
            required = (
                len(set(check.values))
                if check.mode == "all"
                else (check.minimum_overlap if check.mode == "minimum" else 1)
            )
            if len(overlap) < required:
                return False
        return True

    return [deepcopy(entity) for entity in entity_list(entities) if matches(entity)]


def filter_relation_connected(
    graph: dict[str, Any],
    entities: Any,
    *,
    conditions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep entities with direct matching connections to actual anchor IDs."""
    checks = [RelationCondition.model_validate(condition) for condition in conditions]
    net = network(graph)
    for check in checks:
        if any(identifier not in net for identifier in check.anchor_ids):
            raise OperatorError("Relation anchor does not exist in the graph")
    selected = []
    for entity in entity_list(entities):
        accepted = True
        for check in checks:
            candidates = []
            if check.direction in {"outgoing", "both"}:
                candidates.extend(net.out_edges(entity["id"], data=True))
            if check.direction in {"incoming", "both"}:
                candidates.extend(net.in_edges(entity["id"], data=True))
            neighbors = set()
            for _, _, data in candidates:
                relation = data["relation"]
                if relation["relation"] != check.relation:
                    continue
                neighbors.add(
                    relation["target"] if relation["source"] == entity["id"] else relation["source"]
                )
            matches = [identifier in neighbors for identifier in check.anchor_ids]
            if not (all(matches) if check.mode == "all" else any(matches)):
                accepted = False
                break
        if accepted:
            selected.append(deepcopy(entity))
    return selected


def aggregate_values(items: Iterable[dict[str, Any]], *, request: dict[str, Any]) -> Any:
    """Aggregate rows/entities, optionally grouped; count/sum empty is 0, other empty is null."""
    spec = AggregateRequest.model_validate(request)
    rows = list(items)

    def get(row: dict[str, Any], field: str) -> Any:
        data = row["properties"] if "properties" in row else row
        if field not in data:
            raise OperatorError(f"Aggregate field {field} is absent")
        return data[field]

    def compute(group: list[dict[str, Any]]) -> Any:
        if spec.operation == "count":
            return len(group)
        values = [get(row, spec.field) for row in group]
        if spec.nulls == "skip":
            values = [value for value in values if value is not None]
        elif any(value is None for value in values):
            raise OperatorError(
                "Null aggregate value; explicitly select nulls='skip' if appropriate"
            )
        numeric = [number(value) for value in values]
        if spec.operation == "sum":
            return _json_number(sum(numeric, Decimal(0)))
        if not numeric:
            return None
        result = (
            min(numeric)
            if spec.operation == "min"
            else (max(numeric) if spec.operation == "max" else sum(numeric) / len(numeric))
        )
        return _json_number(result)

    if spec.group_by is None:
        return compute(rows)
    groups: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        value = get(row, spec.group_by)
        if not isinstance(value, str | int | float | bool | type(None)):
            raise OperatorError("group_by requires scalar values")
        groups.setdefault(value, []).append(row)
    return [{"group": key, "value": compute(group)} for key, group in groups.items()]


def arithmetic(
    *, operation: Literal["add", "subtract", "multiply", "divide"], left: Any, right: Any
) -> Any:
    """Run bounded scalar pre/post-processing, an explicit extension to the nine operators."""
    a, b = number(left), number(right)
    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            raise OperatorError("Division by zero")
        result = a / b
    else:
        raise OperatorError("Arithmetic operation must be add, subtract, multiply, or divide")
    return _json_number(result)


def extract_runtime_slots(
    *,
    query: str,
    slot_specs: list[dict[str, Any]],
    task_context: str = "",
    max_attempts: int = 3,
    max_tokens: int = 2000,
    slot_extractor: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Delegate slot extraction to a real configured model callback."""
    if slot_extractor is None:
        raise OperatorError("extract_runtime_slots requires a configured real model callback")
    if not 1 <= max_attempts <= 3 or not 1 <= max_tokens <= 2000:
        raise OperatorError("Slot extraction allows at most 3 attempts and 2000 output tokens")
    return slot_extractor(
        query=query,
        slot_specs=slot_specs,
        task_context=task_context,
        max_attempts=max_attempts,
        max_tokens=max_tokens,
    )


def invoke_capability(
    *,
    capability: str,
    arguments: dict[str, Any],
    capability_invoker: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Acquire real evidence through an executor-owned, version-checked MCP binding.

    The callback records the real call and extracts observations under the frozen
    schema. Returned entities belong to the current episode graph. This operator
    cannot invent an endpoint or execute without an explicitly supplied binding.
    """
    if capability_invoker is None:
        raise OperatorError("invoke_capability requires an explicit live capability binding")
    return capability_invoker(capability=capability, arguments=arguments)


OperatorName = Literal[
    "lookup_entities",
    "traverse_relations",
    "project_properties",
    "filter_property_categorical",
    "filter_categorical",
    "filter_relation_connected",
    "filter_numeric",
    "filter_set_overlap",
    "aggregate_values",
    "extract_runtime_slots",
    "arithmetic",
    "invoke_capability",
]
OPERATORS: dict[str, Callable[..., Any]] = {
    name: globals()[name] for name in get_args(OperatorName)
}
GRAPH_OPERATORS = {"lookup_entities", "traverse_relations", "filter_relation_connected"}


def operator_contracts() -> dict[str, Any]:
    """Generate model-facing operator descriptions and condition schemas from actual code."""
    return {
        "operators": {
            name: {
                "signature": str(inspect.signature(function)),
                "description": inspect.getdoc(function),
            }
            for name, function in OPERATORS.items()
        },
        "conditions": {
            "filter_property_categorical": CategoricalCondition.model_json_schema(),
            "filter_relation_connected": RelationCondition.model_json_schema(),
            "filter_numeric": NumericCondition.model_json_schema(),
            "filter_set_overlap": SetCondition.model_json_schema(),
            "aggregate_values_request": AggregateRequest.model_json_schema(),
        },
    }

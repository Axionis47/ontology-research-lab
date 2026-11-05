"""Materialization checks execute on checksum-verified retained weather evidence.

Function derivatives below are mechanical operator probes over genuine records,
not fabricated model responses or a claimed new agent run. Destructive input
variants test error boundaries and never overwrite retained artifacts.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from oak.bootstrap import empty_graph, merge_observations
from oak.functions import execute_function
from oak.materialization import (
    CoverageReceipt,
    assess_sufficiency,
    derive_demand,
    extraction_schema,
    materialization_cache_key,
    slice_graph,
)
from oak.ontology import validate_graph_records
from oak.store import canonical
from oak.tasks.weather import parse_daily_forecast

FIXTURES = Path(__file__).parent / "fixtures/observer/weather/artifacts"
KERNEL = "2c112be392425277cf1d469ab6c7fd4a98546c3e520452a40802d6ac43c6eaad"
GRAPH = "3d22ea885e705dc8d46186e4f3f795653a9182ab7c8142876facb99633e658da"
RECEIPT = "ae2346d6f91a7a973a986a2304a717bf6640897a675aec3a655233e25bf43cd6"


def artifact(identity: str) -> dict:
    raw = (FIXTURES / f"{identity}.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == identity
    return json.loads(raw)["data"]


def graph_hash(graph: dict) -> str:
    return hashlib.sha256(canonical(graph)).hexdigest()


def point_function(schema: dict, graph: dict, field: str = "high_temperature") -> dict:
    """Bind a generic lookup/projection probe to an actual saved entity."""
    node = next(node for node in graph["nodes"] if node["type"] == "DailyForecast")
    key = schema["entity_types"][node["type"]]["primary_key"]
    return {
        "name": "retained_point_projection",
        "description": "Project one property from an actual retained entity",
        "inputs": {
            "type": "object",
            "properties": {"identity": {"type": "string"}},
            "required": ["identity"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "array"},
        "steps": [
            {
                "id": "lookup",
                "operator": "lookup_entities",
                "args": {
                    "entity_types": [node["type"]],
                    "primary_key": {key: {"$arg": "identity"}},
                },
            },
            {
                "id": "project",
                "operator": "project_properties",
                "args": {
                    "entities": {"$step": "lookup"},
                    "property_names": [field],
                },
            },
        ],
        "result": {"$step": "project"},
    }


def actual_point_args(schema: dict, graph: dict) -> dict:
    node = next(node for node in graph["nodes"] if node["type"] == "DailyForecast")
    return {"identity": node["properties"][schema["entity_types"][node["type"]]["primary_key"]]}


def test_point_projection_materializes_one_record_and_matches_real_full_execution() -> None:
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    schema = kernel["schema"]
    function = point_function(schema, graph)
    args = actual_point_args(schema, graph)
    demand = derive_demand(schema, function, args)
    assert demand.coverage_mode == "witness"
    assert "low_temperature" in demand.required_fields["DailyForecast"]
    assert "sunset" not in demand.required_fields["DailyForecast"]
    materialized = slice_graph(schema, graph, demand)
    assert len(materialized["nodes"]) == 1 < len(graph["nodes"])
    assert materialized["edges"] == []
    assert validate_graph_records(schema, materialized["nodes"], materialized["edges"])["valid"]
    full = execute_function(graph, [function], function["name"], args, schema=schema)
    small = execute_function(materialized, [function], function["name"], args, schema=schema)
    assert full["value"] == small["value"]
    assert assess_sufficiency(schema, materialized, demand).status == "satisfied"
    assert graph == artifact(GRAPH)
    assert extraction_schema(schema, demand) == schema


def test_aggregate_demand_retains_all_required_values_without_unrelated_facts() -> None:
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    function = kernel["functions"][0]
    demand = derive_demand(
        kernel["schema"], function, {"native_arguments": artifact(RECEIPT)["args"]}
    )
    assert demand.coverage_mode == "complete_scope"
    materialized = slice_graph(kernel["schema"], graph, demand)
    assert len(materialized["nodes"]) == 3 and materialized["edges"] == []
    assert all(node["type"] == "DailyForecast" for node in materialized["nodes"])
    assert assess_sufficiency(kernel["schema"], materialized, demand).status == "unknown"


def test_model_and_snapshot_completeness_cannot_authorize_exact_aggregation() -> None:
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    demand = derive_demand(
        kernel["schema"], kernel["functions"][0], {"native_arguments": artifact(RECEIPT)["args"]}
    )
    graph = slice_graph(kernel["schema"], graph, demand)
    receipt = CoverageReceipt(
        demand_id=demand.demand_id,
        schema_sha256=demand.schema_sha256,
        graph_sha256=graph_hash(graph),
        basis="model_claim",
        scope="source_population",
        population_complete=True,
        fields_checked=demand.required_fields,
        source_receipt_ids=[RECEIPT],
    )
    assert assess_sufficiency(kernel["schema"], graph, demand, [receipt]).status == "unknown"
    receipt = receipt.model_copy(
        update={"basis": "observed_only", "scope": "materialized_snapshot"}
    )
    assert assess_sufficiency(kernel["schema"], graph, demand, [receipt]).status == "unknown"
    partial = deepcopy(graph)
    partial["nodes"] = partial["nodes"][:1]
    assert assess_sufficiency(kernel["schema"], partial, demand, [receipt]).status == "unknown"


def test_independent_source_checks_are_bound_to_the_exact_materialization() -> None:
    """Actual parser plus source-value comparisons establishes this fixture's scope."""
    kernel, graph, source = artifact(KERNEL), artifact(GRAPH), artifact(RECEIPT)
    demand = derive_demand(
        kernel["schema"], kernel["functions"][0], {"native_arguments": source["args"]}
    )
    graph = slice_graph(kernel["schema"], graph, demand)
    parsed = parse_daily_forecast(source)
    by_date = {node["properties"]["date"]: node["properties"] for node in graph["nodes"]}
    assert set(by_date) == {row["date"] for row in parsed["days"]}
    native_text = source["output"]["content"][0]["text"]
    lows = [
        int(value)
        for value in re.findall(r"\*\*Temperature:\*\* High -?\d+°C / Low (-?\d+)°C", native_text)
    ]
    assert len(lows) == len(parsed["days"])
    for row, low in zip(parsed["days"], lows, strict=True):
        actual = by_date[row["date"]]
        assert actual["high_temperature"] == row["high"]
        assert actual["low_temperature"] == low
        assert actual["temperature_unit"] == row["unit"]
        assert actual["source"] == source["args"]["source"]
        assert actual["forecast_id"] == (
            f"forecast_openmeteo_{parsed['latitude']}_{parsed['longitude']}_{row['date']}"
        )
    receipt = CoverageReceipt(
        demand_id=demand.demand_id,
        schema_sha256=demand.schema_sha256,
        graph_sha256=graph_hash(graph),
        basis="adapter_verified",
        scope="source_population",
        population_complete=True,
        fields_checked=demand.required_fields,
        source_receipt_ids=[RECEIPT],
        evidence_refs=[RECEIPT, GRAPH],
        checker_id="weather-retained-value-check",
        checker_version="1",
    )
    assert assess_sufficiency(kernel["schema"], graph, demand, [receipt]).status == "satisfied"
    partial = deepcopy(graph)
    partial["nodes"].pop()
    assert assess_sufficiency(kernel["schema"], partial, demand, [receipt]).status == "unknown"


def test_missingness_does_not_fabricate_nulls_or_absence() -> None:
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    schema = kernel["schema"]
    function = point_function(schema, graph, "daylight_duration")
    demand = derive_demand(schema, function, actual_point_args(schema, graph))
    materialized = slice_graph(schema, graph, demand)
    result = assess_sufficiency(schema, materialized, demand)
    assert result.status == "needs_evidence"
    assert result.missing[0].state == "explicit_null"
    materialized["nodes"][0]["properties"].pop("daylight_duration")
    result = assess_sufficiency(schema, materialized, demand)
    assert result.missing[0].state == "unmaterialized"
    materialized["nodes"] = []
    result = assess_sufficiency(schema, materialized, demand)
    assert result.status == "needs_evidence"


def test_traversal_keeps_required_endpoints_and_requires_adjacency_evidence() -> None:
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    start = next(node for node in graph["nodes"] if node["type"] == "DailyForecast")
    function = {
        "name": "retained_traversal",
        "description": "Traverse a genuine retained relationship",
        "inputs": {"type": "object", "properties": {}, "additionalProperties": False},
        "output_schema": {"type": "object"},
        "steps": [
            {
                "id": "walk",
                "operator": "traverse_relations",
                "args": {
                    "start_entity_ids": [start["id"]],
                    "relation_types": [graph["edges"][0]["relation"]],
                    "max_hops": 1,
                },
            }
        ],
        "result": {"$step": "walk"},
    }
    demand = derive_demand(kernel["schema"], function, {})
    materialized = slice_graph(kernel["schema"], graph, demand)
    assert len(materialized["nodes"]) == 2 and len(materialized["edges"]) == 1
    assert validate_graph_records(kernel["schema"], materialized["nodes"], materialized["edges"])[
        "valid"
    ]
    assert demand.coverage_mode == "complete_adjacency"
    assert assess_sufficiency(kernel["schema"], materialized, demand).status != "satisfied"


def test_cache_and_schema_binding_include_all_versions_and_bound_inputs() -> None:
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    function = point_function(kernel["schema"], graph)
    demand = derive_demand(kernel["schema"], function, actual_point_args(kernel["schema"], graph))
    first = materialization_cache_key(RECEIPT, KERNEL, "extractor-v1", demand)
    assert first == materialization_cache_key(RECEIPT, KERNEL, "extractor-v1", demand)
    assert first != materialization_cache_key(RECEIPT, KERNEL, "extractor-v2", demand)
    assert first != materialization_cache_key(GRAPH, KERNEL, "extractor-v1", demand)
    changed = deepcopy(kernel["schema"])
    changed["description"] += " revised"
    with pytest.raises(ValueError, match="another schema"):
        slice_graph(changed, graph, demand)
    assert assess_sufficiency(changed, graph, demand).status == "incompatible"


def test_mixed_resolved_and_runtime_traversals_keep_the_later_frontier() -> None:
    """A real forecast-to-location path can expand back to other forecast days."""
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    start = next(node for node in graph["nodes"] if node["type"] == "DailyForecast")
    location = next(node for node in graph["nodes"] if node["type"] == "Location")
    location_position = sorted([start["id"], location["id"]]).index(location["id"])
    relation = graph["edges"][0]["relation"]
    function = {
        "name": "retained_two_stage_traversal",
        "description": "Traverse a retained location then its actual forecast records",
        "inputs": {"type": "object", "properties": {}, "additionalProperties": False},
        "output_schema": {"type": "object"},
        "steps": [
            {
                "id": "locate",
                "operator": "traverse_relations",
                "args": {
                    "start_entity_ids": [start["id"]],
                    "relation_types": [relation],
                    "max_hops": 1,
                },
            },
            {
                "id": "expand",
                "operator": "traverse_relations",
                "args": {
                    "start_entity_ids": [
                        {"$path": ["locate", "entities", location_position, "id"]}
                    ],
                    "relation_types": [relation],
                    "direction": "incoming",
                    "max_hops": 1,
                },
            },
        ],
        "result": {"$step": "expand"},
    }
    demand = derive_demand(kernel["schema"], function, {})
    assert demand.unknowns and demand.traversals == []
    materialized = slice_graph(kernel["schema"], graph, demand)
    assert len(materialized["edges"]) == len(graph["edges"]) == 3
    full = execute_function(graph, [function], function["name"], {}, schema=kernel["schema"])
    scoped = execute_function(
        materialized, [function], function["name"], {}, schema=kernel["schema"]
    )
    assert scoped["value"] == full["value"]


def test_reusing_recorded_documents_does_not_inflate_graph_source_counts() -> None:
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    # Annotate an in-memory derivative with IDs actually present in this retained
    # artifact. The original has one source document and remains untouched.
    source_ids = sorted(
        {source["document_id"] for node in graph["nodes"] for source in node["sources"]}
    )
    assert len(source_ids) == graph["source_document_count"] == 1
    graph["source_document_ids"] = source_ids
    graph["source_document_count_basis"] = "unique_recorded_ids"
    first = merge_observations(kernel["schema"], empty_graph(), graph)
    second = merge_observations(kernel["schema"], first, graph)
    assert second["source_document_count"] == 1
    assert second["source_document_ids"] == source_ids
    assert second["nodes"] == first["nodes"]
    assert second["edges"] == first["edges"]
    assert "source_document_ids" not in artifact(GRAPH)
    legacy = merge_observations(kernel["schema"], artifact(GRAPH), artifact(GRAPH))
    assert legacy["source_document_count"] == 2
    assert legacy["source_document_count_basis"] == "legacy_additive_overlap_unknown"
    assert "source_document_ids" not in legacy


def test_direct_result_property_path_retains_actual_optional_value() -> None:
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    schema = kernel["schema"]
    function = point_function(schema, graph)
    function["steps"] = function["steps"][:1]
    function["result"] = {"$path": ["lookup", 0, "properties", "conditions"]}
    function["output_schema"] = {"type": "string"}
    args = actual_point_args(schema, graph)
    assert schema["entity_types"]["DailyForecast"]["properties"]["conditions"]["required"] is False
    demand = derive_demand(schema, function, args)
    assert "conditions" in demand.required_fields["DailyForecast"]
    materialized = slice_graph(schema, graph, demand)
    full = execute_function(graph, [function], function["name"], args, schema=schema)
    scoped = execute_function(materialized, [function], function["name"], args, schema=schema)
    assert scoped["value"] == full["value"] == graph["nodes"][0]["properties"]["conditions"]


def test_arithmetic_property_paths_retain_actual_optional_values() -> None:
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    schema = kernel["schema"]
    function = point_function(schema, graph)
    function["steps"] = function["steps"][:1] + [
        {
            "id": "difference",
            "operator": "arithmetic",
            "args": {
                "operation": "subtract",
                "left": {"$path": ["lookup", 0, "properties", "feels_like_high"]},
                "right": {"$path": ["lookup", 0, "properties", "feels_like_low"]},
            },
        }
    ]
    function["result"] = {"$step": "difference"}
    function["output_schema"] = {"type": "number"}
    args = actual_point_args(schema, graph)
    demand = derive_demand(schema, function, args)
    assert {"feels_like_high", "feels_like_low"} <= set(demand.required_fields["DailyForecast"])
    materialized = slice_graph(schema, graph, demand)
    full = execute_function(graph, [function], function["name"], args, schema=schema)
    scoped = execute_function(materialized, [function], function["name"], args, schema=schema)
    assert scoped["value"] == full["value"]


def test_direct_acquisition_entity_result_path_keeps_actual_returned_fields() -> None:
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    function = deepcopy(kernel["functions"][0])
    function["steps"] = function["steps"][:1]
    function["result"] = {"$path": ["fetch_forecast", "entities_by_type", "DailyForecast"]}
    function["output_schema"] = {"type": "array"}
    demand = derive_demand(
        kernel["schema"], function, {"native_arguments": artifact(RECEIPT)["args"]}
    )
    assert demand.entity_types == ["DailyForecast"]
    assert "conditions" in demand.required_fields["DailyForecast"]
    materialized = slice_graph(kernel["schema"], graph, demand)
    # No effectful invocation is simulated. Compare only this real graph slice.
    assert materialized["nodes"] == [
        node for node in graph["nodes"] if node["type"] == "DailyForecast"
    ]

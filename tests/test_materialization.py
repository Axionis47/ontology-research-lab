"""Materialization checks execute on checksum-verified retained weather evidence.

Function derivatives below are mechanical operator probes over genuine records,
not fabricated model responses or a claimed new agent run. Destructive input
variants test error boundaries and never overwrite retained artifacts.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from urllib.parse import urljoin

import pytest
from jsonschema import ValidationError

from oak.bootstrap import empty_graph, merge_observations, result_acquisition_evidence
from oak.functions import execute_function
from oak.materialization import (
    CoverageReceipt,
    assess_sufficiency,
    derive_demand,
    derive_step_demand,
    extraction_schema,
    freeze_acquisition_binding,
    materialization_cache_key,
    prepare_bound_materialization,
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


def bound_point() -> tuple[dict, dict, dict, dict]:
    """A source-bound pure probe using the retained discovery and native request."""
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    function = point_function(kernel["schema"], graph)
    function["inputs"]["properties"]["source_request"] = {"type": "object"}
    function["inputs"]["required"].append("source_request")
    args = {
        **actual_point_args(kernel["schema"], graph),
        "source_request": artifact(RECEIPT)["args"],
    }
    return kernel, graph, function, args


def test_bound_pure_point_prepares_real_native_contract_and_executes_from_empty_graph() -> None:
    kernel, retained, function, args = bound_point()
    tools = kernel["catalog"]["tools"]
    binding = freeze_acquisition_binding(
        kernel["schema"], function, tools[0]["id"], {"$arg": "source_request"}, tools
    )
    prepared = prepare_bound_materialization(
        kernel["schema"], function, args, [binding, binding], tools
    )
    assert len(prepared.acquisitions) == 1
    request = prepared.acquisitions[0]
    assert request.arguments == artifact(RECEIPT)["args"]
    assert "identity" not in request.arguments
    assert request.contract_id == tools[0]["contract_id"]
    assert request.binding_id == binding.binding_id
    assert prepared.demand.selectors[0].primary_key

    # This is retained-evidence execution, not a claimed fresh MCP dispatch.
    graph = empty_graph()
    graph = merge_observations(
        kernel["schema"], graph, slice_graph(kernel["schema"], retained, prepared.demand)
    )
    assert len(graph["nodes"]) == 1
    assert (
        execute_function(graph, [function], function["name"], args, schema=kernel["schema"])[
            "value"
        ]
        == execute_function(retained, [function], function["name"], args, schema=kernel["schema"])[
            "value"
        ]
    )


def test_later_field_demand_reuses_same_source_request_and_retained_receipt() -> None:
    kernel, retained, first, args = bound_point()
    second = deepcopy(first)
    second["name"] = "retained_sunrise_projection"
    second["steps"][1]["args"]["property_names"] = ["sunrise"]
    tools = kernel["catalog"]["tools"]
    bindings = [
        freeze_acquisition_binding(
            kernel["schema"], function, tools[0]["id"], {"$arg": "source_request"}, tools
        )
        for function in (first, second)
    ]
    preparations = [
        prepare_bound_materialization(kernel["schema"], function, args, bindings, tools)
        for function in (first, second)
    ]
    requests = [item.acquisitions[0] for item in preparations]
    assert requests[0].capability == requests[1].capability
    assert requests[0].arguments == requests[1].arguments == artifact(RECEIPT)["args"]
    assert preparations[0].demand.demand_id != preparations[1].demand.demand_id
    graph = slice_graph(kernel["schema"], retained, preparations[0].demand)
    assert "sunrise" not in graph["nodes"][0]["properties"]
    graph = merge_observations(
        kernel["schema"],
        graph,
        slice_graph(kernel["schema"], retained, preparations[1].demand),
    )
    assert len(graph["nodes"]) == 1
    assert graph["nodes"][0]["properties"]["sunrise"] is not None
    for function in (first, second):
        assert (
            execute_function(graph, [function], function["name"], args, schema=kernel["schema"])[
                "value"
            ]
            == execute_function(
                retained, [function], function["name"], args, schema=kernel["schema"]
            )["value"]
        )


@pytest.mark.parametrize("operation", ["list", "count"])
def test_empty_bound_result_keeps_actual_receipt_attribution_without_claiming_absence(
    operation,
) -> None:
    """A negative lookup over genuine evidence is not a fabricated empty source."""
    kernel, retained, function, args = bound_point()
    # Deliberately request an identity outside this saved receipt's records.
    # The receipt and graph facts are unchanged; this is a negative input probe.
    args["identity"] += "/outside-retained-scope"
    function["steps"] = function["steps"][:1]
    function["result"] = {"$step": "lookup"}
    if operation == "count":
        function["steps"].append(
            {
                "id": "count",
                "operator": "aggregate_values",
                "args": {"items": {"$step": "lookup"}, "request": {"operation": "count"}},
            }
        )
        function["result"] = {"$step": "count"}
        function["output_schema"] = {"type": "integer"}
    tools = kernel["catalog"]["tools"]
    binding = freeze_acquisition_binding(
        kernel["schema"], function, tools[0]["id"], {"$arg": "source_request"}, tools
    )
    prepared = prepare_bound_materialization(kernel["schema"], function, args, [binding], tools)
    assert prepared.acquisitions[0].arguments == artifact(RECEIPT)["args"]
    graph = slice_graph(kernel["schema"], retained, prepared.demand)
    assert graph["nodes"] == [] and graph["edges"] == []
    execution = execute_function(graph, [function], function["name"], args, schema=kernel["schema"])
    assert execution["value"] == (0 if operation == "count" else [])
    receipts = [{**artifact(RECEIPT), "evidence_id": RECEIPT, "reused": True}]
    assert result_acquisition_evidence(function, execution, graph, receipts) == []
    assert result_acquisition_evidence(
        function, execution, graph, receipts, materialization_receipt_ids=[RECEIPT, GRAPH]
    ) == [RECEIPT]
    assert (
        result_acquisition_evidence(
            function, execution, graph, [], materialization_receipt_ids=[RECEIPT]
        )
        == []
    )
    assert assess_sufficiency(kernel["schema"], graph, prepared.demand).status in {
        "needs_evidence",
        "unknown",
    }


def test_source_binding_nested_input_paths_and_frozen_contract_validation() -> None:
    kernel, _, function, args = bound_point()
    tools = kernel["catalog"]["tools"]
    template = {key: {"$arg_path": ["source_request", key]} for key in artifact(RECEIPT)["args"]}
    binding = freeze_acquisition_binding(
        kernel["schema"], function, tools[0]["id"], template, tools
    )
    prepared = prepare_bound_materialization(kernel["schema"], function, args, [binding], tools)
    assert prepared.acquisitions[0].arguments == artifact(RECEIPT)["args"]
    with pytest.raises(ValueError, match="authorized capability"):
        prepare_bound_materialization(kernel["schema"], function, args, [binding], [])
    changed_tools = deepcopy(tools)
    changed_tools[0]["contract_id"] = "changed"
    with pytest.raises(ValueError, match="contract changed"):
        prepare_bound_materialization(kernel["schema"], function, args, [binding], changed_tools)
    changed_function = deepcopy(function)
    changed_function["description"] += " changed"
    with pytest.raises(ValueError, match="frozen schema/function"):
        prepare_bound_materialization(kernel["schema"], changed_function, args, [binding], tools)
    invalid_args = deepcopy(args)
    invalid_args["source_request"]["days"] = 100
    with pytest.raises(ValidationError, match="maximum"):
        prepare_bound_materialization(kernel["schema"], function, invalid_args, [binding], tools)


@pytest.mark.parametrize(
    "template",
    [
        {"$step": "acquire"},
        {"$arg": "undeclared"},
        {"$arg_path": ["source_request", -1]},
        {"$arg_path": ["source_request", True]},
        {"$arg": "source_request", "days": 1},
    ],
)
def test_source_bindings_cannot_escape_declared_argument_templates(template: dict) -> None:
    kernel, _, function, _ = bound_point()
    tools = kernel["catalog"]["tools"]
    with pytest.raises(ValueError):
        freeze_acquisition_binding(kernel["schema"], function, tools[0]["id"], template, tools)


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


def test_actual_step_outputs_refine_frontier_before_real_graph_operator() -> None:
    kernel, retained = artifact(KERNEL), artifact(GRAPH)
    schema = kernel["schema"]
    function = point_function(schema, retained)
    function["steps"] = [
        function["steps"][0],
        {
            "id": "walk",
            "operator": "traverse_relations",
            "args": {
                "start_entity_ids": [{"$path": ["lookup", 0, "id"]}],
                "relation_types": [retained["edges"][0]["relation"]],
                "max_hops": 1,
            },
        },
    ]
    function["result"] = {"$step": "walk"}
    function["output_schema"] = {"type": "object"}
    args = actual_point_args(schema, retained)
    unresolved = derive_demand(schema, function, args)
    assert unresolved.traversals == [] and unresolved.unknowns
    graph = empty_graph()
    counts = []
    refined_demands = []

    def materialize(*, step_id: str, operator: str, arguments: dict, step_outputs: dict) -> None:
        assert operator == function["steps"][len(counts)]["operator"]
        demand = derive_step_demand(
            schema,
            function,
            args,
            step_id,
            step_outputs=step_outputs,
        )
        assert demand.function_sha256 == unresolved.function_sha256
        if step_id == "walk":
            assert demand.traversals[0].start_entity_ids == arguments["start_entity_ids"]
            assert not demand.unknowns
            refined_demands.append(demand)
        incoming = slice_graph(schema, retained, demand)
        graph.update(merge_observations(schema, graph, incoming))
        counts.append((len(graph["nodes"]), len(graph["edges"])))
        arguments.clear()
        step_outputs.clear()

    result = execute_function(
        graph, [function], function["name"], args, schema=schema, before_step=materialize
    )
    full = execute_function(retained, [function], function["name"], args, schema=schema)
    assert result["value"] == full["value"]
    assert counts == [(1, 0), (2, 1)]
    assert result["dependencies"]["source_ids"]
    assert result["dependencies"]["graph_sha256"] != result["dependencies"]["graph_after_sha256"]
    assert all(trace["graph_materialized_sha256"] for trace in result["steps"])
    assert assess_sufficiency(schema, graph, refined_demands[0]).status != "satisfied"


def test_resolved_demand_paths_never_guess_missing_step_output_fields() -> None:
    kernel, retained = artifact(KERNEL), artifact(GRAPH)
    function = point_function(kernel["schema"], retained)
    function["steps"][0]["args"]["entity_ids"] = {"$path": ["prior", "missing"]}
    with pytest.raises(ValueError, match="actual step output"):
        derive_demand(kernel["schema"], function, {}, step_outputs={"prior": {}})


def test_deferred_target_property_keeps_initial_graph_narrow_and_executes_exactly() -> None:
    kernel, retained = artifact(KERNEL), artifact(GRAPH)
    schema = kernel["schema"]
    function = point_function(schema, retained)
    function["steps"] = [
        function["steps"][0],
        {
            "id": "location",
            "operator": "traverse_relations",
            "args": {
                "start_entity_ids": [{"$path": ["lookup", 0, "id"]}],
                "relation_types": [retained["edges"][0]["relation"]],
                "include_starting_entities": False,
            },
        },
        {
            "id": "latitude",
            "operator": "project_properties",
            "args": {
                "entities": {"$path": ["location", "entities"]},
                "property_names": ["latitude"],
            },
        },
    ]
    function["result"] = {"$step": "latitude"}
    args = actual_point_args(schema, retained)
    graph, sizes = empty_graph(), []

    def materialize(*, step_id, operator, arguments, step_outputs):
        if operator not in {"lookup_entities", "traverse_relations"}:
            return
        demand = derive_step_demand(schema, function, args, step_id, step_outputs=step_outputs)
        if step_id == "lookup":
            assert demand.entity_types == ["DailyForecast"]
            assert "Location" not in demand.required_fields
            assert "latitude" not in demand.required_fields["DailyForecast"]
        incoming = slice_graph(schema, retained, demand)
        graph.update(merge_observations(schema, graph, incoming))
        sizes.append((len(graph["nodes"]), len(graph["edges"])))

    partial = execute_function(
        graph, [function], function["name"], args, schema=schema, before_step=materialize
    )
    complete = execute_function(retained, [function], function["name"], args, schema=schema)
    assert partial["value"] == complete["value"]
    assert partial["value"][0]["latitude"] is not None
    assert sizes == [(1, 0), (2, 1)]
    invalid = deepcopy(function)
    invalid["steps"][-1]["args"]["property_names"] = ["undeclared_target_property"]
    with pytest.raises(ValueError, match="undeclared properties"):
        derive_step_demand(schema, invalid, args, "lookup")


def test_frontier_does_not_materialize_unrelated_endpoint_entities_from_real_rdf() -> None:
    """Project actual W3C Wine/Winery assertions, without inventing relationships."""
    directory = Path(__file__).parent / "fixtures/ontology"
    raw = (directory / "wine.rdf").read_bytes()
    manifest = json.loads((directory / "manifest.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == manifest["files"]["wine"]["sha256"]
    root = ET.fromstring(raw)
    base = root.attrib["{http://www.w3.org/XML/1998/namespace}base"]
    rdf = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
    source = [{"document_id": "w3c:wine.rdf", "source_ref": manifest["files"]["wine"]["url"]}]
    nodes, edges = {}, []
    for element in root:
        identity = element.attrib.get(rdf + "ID")
        if identity is None:
            continue
        for predicate in element:
            target = predicate.attrib.get(rdf + "resource")
            if predicate.tag.split("}")[-1] != "hasMaker" or target is None:
                continue
            wine, maker = urljoin(base, "#" + identity), urljoin(base, target)
            for entity_id, entity_type in ((wine, "Wine"), (maker, "Winery")):
                nodes[entity_id] = {
                    "id": entity_id,
                    "type": entity_type,
                    "properties": {"iri": entity_id},
                    "sources": deepcopy(source),
                }
            edges.append(
                {
                    "source": wine,
                    "target": maker,
                    "relation": "hasMaker",
                    "sources": deepcopy(source),
                }
            )
    graph = {"nodes": list(nodes.values()), "edges": edges}
    schema = {
        "name": "W3CNamedMakerProjection",
        "entity_types": {
            name: {
                "primary_key": "iri",
                "properties": {"iri": {"type": "string", "required": True}},
            }
            for name in ("Wine", "Winery")
        },
        "relations": {"hasMaker": {"source": "Wine", "target": "Winery"}},
    }
    assert len({edge["target"] for edge in edges}) > 1
    function = {
        "name": "maker_for_wine",
        "description": "Return the recorded maker for one RDF wine",
        "inputs": {
            "type": "object",
            "properties": {"iri": {"type": "string"}},
            "required": ["iri"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "object"},
        "steps": [
            {
                "id": "wine",
                "operator": "lookup_entities",
                "args": {"entity_types": ["Wine"], "primary_key": {"iri": {"$arg": "iri"}}},
            },
            {
                "id": "maker",
                "operator": "traverse_relations",
                "args": {
                    "start_entity_ids": [{"$path": ["wine", 0, "id"]}],
                    "relation_types": ["hasMaker"],
                },
            },
        ],
        "result": {"$step": "maker"},
    }
    args = {"iri": edges[0]["source"]}
    output = execute_function(graph, [function], function["name"], args, schema=schema)
    demand = derive_step_demand(
        schema, function, args, "maker", step_outputs={"wine": output["steps"][0]["output"]}
    )
    materialized = slice_graph(schema, graph, demand)
    assert len(materialized["nodes"]) == 2
    assert len(materialized["edges"]) == 1
    assert (
        execute_function(materialized, [function], function["name"], args, schema=schema)["value"]
        == output["value"]
    )


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

"""Scoped context checks over retained weather and genuine W3C declarations.

These are deterministic context and executor checks, not claimed model runs.
The W3C projection deliberately covers only supported declarations; engineering
IRI keys identify the real ontology terms without claiming a full OWL import.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from copy import deepcopy

import pytest
from test_materialization import GRAPH, KERNEL, RECEIPT, actual_point_args, artifact, point_function
from test_ontology import FIXTURES, OWL, RDF, RDFS
from test_ontology import wine_schema as wine_schema

from oak.functions import execute_function
from oak.materialization import derive_demand, prepare_bound_materialization, slice_graph
from oak.ontology import parse_schema, validate_graph_records, validate_ontology
from oak.schema_context import SchemaContextError, extraction_schema_context, schema_entries
from oak.store import canonical


def _lookup(schema: dict, name: str) -> tuple[dict, object]:
    function = {
        "name": "inspect_retained_type",
        "description": "Read declared identities from the retained ontology projection",
        "inputs": {"type": "object", "properties": {}, "additionalProperties": False},
        "output_schema": {"type": "array"},
        "steps": [{"id": "read", "operator": "lookup_entities", "args": {"entity_types": [name]}}],
        "result": {"$step": "read"},
    }
    return function, derive_demand(schema, function, {})


@pytest.fixture
def constrained_wine(wine_schema):
    """Add only constraints whose source declarations are verified below."""
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    raw = (FIXTURES / "wine.rdf").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["files"]["wine"]["sha256"]
    root = ET.fromstring(raw)
    classes = {item.get(RDF + "ID"): item for item in root.findall(OWL + "Class")}
    properties = {item.get(RDF + "ID"): item for item in root.findall(OWL + "ObjectProperty")}
    schema = deepcopy(wine_schema)
    for name in ("LateHarvest", "EarlyHarvest"):
        assert classes[name].find(RDFS + "subClassOf").get(RDF + "resource") == "#Wine"
        schema["entity_types"][name] = {
            "primary_key": "iri",
            "properties": {"iri": {"type": "string"}},
            "parents": ["Wine"],
        }
    assert (
        classes["LateHarvest"].find(OWL + "disjointWith").get(RDF + "resource") == "#EarlyHarvest"
    )
    schema["entity_types"]["LateHarvest"]["disjoint_with"] = ["EarlyHarvest"]
    assert properties["producesWine"].find(OWL + "inverseOf").get(RDF + "resource") == "#hasMaker"
    schema["relations"]["producesWine"] = {
        "source": "Winery",
        "target": "Wine",
        "inverse_of": "hasMaker",
    }
    restrictions = classes["Wine"].findall(".//" + OWL + "Restriction")
    assert any(
        restriction.find(OWL + "onProperty").get(RDF + "resource") == "#hasMaker"
        and restriction.find(OWL + "allValuesFrom") is not None
        and restriction.find(OWL + "allValuesFrom").get(RDF + "resource") == "#Winery"
        for restriction in restrictions
    )
    schema["entity_types"]["Wine"]["restrictions"] = [
        {"property": "hasMaker", "kind": "only", "filler": "Winery"}
    ]
    return schema


def test_weather_view_omits_optional_fields_but_keeps_required_and_disjoint_constraints():
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    schema = kernel["schema"]
    before = canonical(schema)
    function = point_function(schema, graph)
    args = actual_point_args(schema, graph)
    demand = derive_demand(schema, function, args)
    view = extraction_schema_context(schema, demand)
    shown = view["schema"]["entity_types"]["DailyForecast"]
    assert "high_temperature" in shown["properties"]
    assert "conditions" not in shown["properties"]
    for name, declaration in schema["entity_types"]["DailyForecast"]["properties"].items():
        if declaration["required"]:
            assert shown["properties"][name] == declaration
    assert shown["disjoint_with"] == ["Location"]
    assert "Location" in view["schema"]["entity_types"]
    assert view["schema"]["relations"] == {}
    assert view["complete_schema"] is False
    assert view["schema_sha256"] == hashlib.sha256(before).hexdigest()
    assert view["demand_id"] == demand.demand_id
    assert view["omitted"]["properties"] > 0
    assert canonical(schema) == before

    # Presentation never replaces the complete schema in real execution.
    selected = slice_graph(schema, graph, demand)
    assert validate_graph_records(schema, selected["nodes"], selected["edges"])["valid"]
    assert (
        execute_function(selected, [function], function["name"], args, schema=schema)["value"]
        == (execute_function(graph, [function], function["name"], args, schema=schema)["value"])
    )


def test_entry_definitions_are_exact_retained_fragments_and_dependencies_resolve():
    schema = artifact(KERNEL)["schema"]
    entries = schema_entries(schema)
    for pointer, entry in entries.items():
        fragment = schema
        for component in pointer[1:].split("/"):
            name = component.replace("~1", "/").replace("~0", "~")
            fragment = fragment[int(name)] if isinstance(fragment, list) else fragment[name]
        assert entry["definition"] == fragment
        assert all(dependency in entries for dependency in entry["dependencies"])


def test_parent_restriction_inverse_and_reverse_disjoint_closure(constrained_wine, tmp_path):
    schema = constrained_wine
    _, demand = _lookup(schema, "EarlyHarvest")
    view = extraction_schema_context(schema, demand)
    entries = schema_entries(schema)
    assert "/entity_types/LateHarvest" in entries["/entity_types/EarlyHarvest"]["dependencies"]
    assert "/relations/producesWine" in entries["/relations/hasMaker"]["dependencies"]
    assert set(view["schema"]["entity_types"]) == {"EarlyHarvest", "LateHarvest", "Wine", "Winery"}
    assert (
        view["schema"]["entity_types"]["Wine"]["restrictions"]
        == schema["entity_types"]["Wine"]["restrictions"]
    )
    assert set(view["schema"]["relations"]) == {"hasMaker", "producesWine"}
    assert view["schema"]["entity_types"]["EarlyHarvest"]["parents"] == ["Wine"]
    assert parse_schema(view["schema"])
    # Only the original projection receives actual ontology validation.
    assert validate_ontology(schema, tmp_path / "full-schema")["valid"]


def test_selected_relation_keeps_both_endpoints_and_their_required_fields():
    schema = artifact(KERNEL)["schema"]
    _, demand = _lookup(schema, "DailyForecast")
    demand = demand.model_copy(
        update={
            "entity_types": [],
            "required_fields": {},
            "relation_types": ["forecast_for_location"],
        }
    )
    view = extraction_schema_context(schema, demand)
    assert set(view["schema"]["entity_types"]) == {"DailyForecast", "Location"}
    assert view["schema"]["relations"] == schema["relations"]
    for name, entity in view["schema"]["entity_types"].items():
        assert entity["primary_key"] in entity["properties"]
        for field, declaration in schema["entity_types"][name]["properties"].items():
            if declaration["required"]:
                assert field in entity["properties"]


def test_selector_fields_cannot_be_dropped_when_required_field_list_is_empty():
    schema, graph = artifact(KERNEL)["schema"], artifact(GRAPH)
    function = point_function(schema, graph, "conditions")
    demand = derive_demand(schema, function, actual_point_args(schema, graph))
    # A narrower mechanical selector checks closure independently of the demand
    # derivation implementation, using a genuine retained optional property.
    condition = next(
        node["properties"]["conditions"]
        for node in graph["nodes"]
        if node["type"] == "DailyForecast"
    )
    selector = demand.selectors[0].model_copy(
        update={"property_filters": {"conditions": condition}}
    )
    demand = demand.model_copy(update={"required_fields": {}, "selectors": [selector]})
    view = extraction_schema_context(schema, demand)
    assert "conditions" in view["schema"]["entity_types"]["DailyForecast"]["properties"]


def test_context_failure_is_explicit_for_wrong_revision_missing_field_and_size():
    schema, graph = artifact(KERNEL)["schema"], artifact(GRAPH)
    function = point_function(schema, graph)
    demand = derive_demand(schema, function, actual_point_args(schema, graph))
    with pytest.raises(SchemaContextError, match="another frozen schema"):
        extraction_schema_context(schema, demand.model_copy(update={"schema_sha256": "0" * 64}))
    with pytest.raises(SchemaContextError, match="undeclared property"):
        extraction_schema_context(
            schema, demand.model_copy(update={"required_fields": {"DailyForecast": ["absent"]}})
        )
    with pytest.raises(SchemaContextError, match="Dependency-closed schema module.*narrower valid"):
        extraction_schema_context(schema, demand, max_bytes=256)


def test_explicit_datatype_restriction_keeps_its_otherwise_optional_property():
    schema, graph = artifact(KERNEL)["schema"], artifact(GRAPH)
    function = point_function(schema, graph)
    args = actual_point_args(schema, graph)
    initial = extraction_schema_context(schema, derive_demand(schema, function, args))
    assert "wind_speed" not in initial["schema"]["entity_types"]["DailyForecast"]["properties"]
    # Controlled schema mutation tests a supported constraint over a genuine
    # retained optional field. It introduces no invented entity or observation.
    schema["entity_types"]["DailyForecast"]["restrictions"] = [
        {"property": "DailyForecast.wind_speed", "kind": "only", "filler": "number"}
    ]
    view = extraction_schema_context(schema, derive_demand(schema, function, args))
    declaration = view["schema"]["entity_types"]["DailyForecast"]
    assert (
        declaration["properties"]["wind_speed"]
        == schema["entity_types"]["DailyForecast"]["properties"]["wind_speed"]
    )
    assert declaration["restrictions"] == schema["entity_types"]["DailyForecast"]["restrictions"]
    assert parse_schema(view["schema"])


@pytest.mark.parametrize("function_index", [0, 1])
def test_legacy_weather_functions_derive_bounded_context_without_a_profile_flag(function_index):
    kernel, graph = artifact(KERNEL), artifact(GRAPH)
    assert kernel.get("construction_profile") is None
    function = kernel["functions"][function_index]
    arguments = {"native_arguments": artifact(RECEIPT)["args"]}
    if "min_high_temperature" in function["inputs"]["properties"]:
        arguments["min_high_temperature"] = min(
            node["properties"]["high_temperature"]
            for node in graph["nodes"]
            if node["type"] == "DailyForecast"
        )
    prepared = prepare_bound_materialization(
        kernel["schema"],
        function,
        arguments,
        kernel.get("acquisition_bindings", []),
        kernel["catalog"]["tools"],
    )
    assert prepared.acquisitions == []  # Original F acquires directly through invoke_capability.
    assert prepared.demand.acquisitions == [
        {"capability": "weather/get_forecast", "arguments": artifact(RECEIPT)["args"]}
    ]
    assert prepared.demand.entity_types == ["DailyForecast"]
    assert prepared.demand.unknowns == []
    context = extraction_schema_context(kernel["schema"], prepared.demand)
    assert len(canonical(context)) < 40_000
    properties = context["schema"]["entity_types"]["DailyForecast"]["properties"]
    assert "high_temperature" in properties and "wind_speed" not in properties
    assert context["complete_schema"] is False

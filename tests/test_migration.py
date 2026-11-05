"""Shared graph migrations execute over real Coffee and retained weather facts.

Transformation contracts are explicitly authored component inputs. Faulty
variants remove, repeat, or mis-map real records to check rejection behavior;
they are never labeled benchmark data or model-generated migrations.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from oak.functions import execute_function
from oak.migration import MigrationError, MigrationSpec, migrate_graph
from oak.ontology import validate_ontology
from oak.store import canonical
from oak.tasks.coffee import DEFAULT_CACHE, load_coffee


@pytest.fixture(scope="module")
def coffee() -> tuple[dict, dict]:
    if not (DEFAULT_CACHE / "coffee_price.csv").is_file():
        pytest.fail("Install the checksum-pinned genuine Coffee data before migration checks")
    documents = load_coffee()["corpus"]["documents"][:32]
    schema = {
        "name": "AuthoredCoffeeMigrationContract",
        "entity_types": {
            "Quote": {
                "primary_key": "Date",
                "properties": {
                    "Date": {"type": "string", "required": True},
                    "High": {"type": "number", "required": True},
                    "Low": {"type": "number", "required": True},
                },
            }
        },
        "relations": {},
    }
    graph = {
        "nodes": [
            {
                "id": document["id"],
                "type": "Quote",
                "properties": {
                    "Date": json.loads(document["content"])["Date"],
                    "High": float(json.loads(document["content"])["High"]),
                    "Low": float(json.loads(document["content"])["Low"]),
                },
                "sources": [{"document_id": document["id"], "source_ref": document["source_ref"]}],
            }
            for document in documents
        ],
        "edges": [],
        "source_document_count": len(documents),
        "ignored_documents": [],
    }
    return schema, graph


@pytest.fixture(scope="module")
def weather() -> tuple[dict, dict]:
    directory = Path(__file__).parent / "fixtures/observer/weather/artifacts"

    def artifact(identity: str) -> dict:
        raw = (directory / f"{identity}.json").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == identity
        return json.loads(raw)["data"]

    kernel = artifact("2c112be392425277cf1d469ab6c7fd4a98546c3e520452a40802d6ac43c6eaad")
    graph = artifact("3d22ea885e705dc8d46186e4f3f795653a9182ab7c8142876facb99633e658da")
    return kernel["schema"], graph


def split_contract(schema: dict) -> tuple[dict, dict]:
    props = schema["entity_types"]["Quote"]["properties"]
    target = {
        "name": "AuthoredSplitCoffeeContract",
        "entity_types": {
            "QuoteDay": {"primary_key": "Date", "properties": {"Date": props["Date"]}},
            "QuoteValues": {"primary_key": "Date", "properties": deepcopy(props)},
        },
        "relations": {
            "has_values": {
                "source": "QuoteDay",
                "target": "QuoteValues",
                "characteristics": ["functional"],
            }
        },
    }
    spec = {
        "records": [
            {
                "sources": {"quote": "Quote"},
                "target_type": kind,
                "properties": {name: {"source": "quote", "property": name} for name in names},
                "identity": identity,
            }
            for kind, names, identity in (
                ("QuoteDay", ["Date"], {"source": "quote"}),
                ("QuoteValues", list(props), {"keys": ["Date"]}),
            )
        ],
        "derived_relations": [
            {
                "source_type": "Quote",
                "source_target_type": "QuoteDay",
                "target_target_type": "QuoteValues",
                "relation": "has_values",
            }
        ],
    }
    return target, spec


def join_contract() -> dict:
    return {
        "records": [
            {
                "sources": {"day": "QuoteDay", "values": "QuoteValues"},
                "join_keys": {"day": ["Date"], "values": ["Date"]},
                "anchor": "day",
                "target_type": "Quote",
                "properties": {
                    name: {"source": "day" if name == "Date" else "values", "property": name}
                    for name in ("Date", "High", "Low")
                },
                "identity": {"source": "day"},
            }
        ],
        "contracted_relations": ["has_values"],
    }


@pytest.mark.parametrize("surface", ["coffee", "weather"])
def test_identity_preserves_actual_facts_order_and_provenance(surface, request) -> None:
    schema, graph = request.getfixturevalue(surface)
    original = canonical(graph)
    result = migrate_graph(graph, MigrationSpec(), schema, schema)
    assert canonical(result["graph"]) == original
    assert canonical(graph) == original
    assert result["graph"] is not graph
    assert result["identity_mapping"] == {node["id"]: [node["id"]] for node in graph["nodes"]}


def test_weather_rename_and_identity_remap_updates_actual_relationships(weather) -> None:
    schema, graph = weather
    target = deepcopy(schema)
    forecast = target["entity_types"]["DailyForecast"]
    forecast["properties"]["maximum"] = forecast["properties"].pop("high_temperature")
    target["relations"]["at_location"] = target["relations"].pop("forecast_for_location")
    spec = {
        "property_renames": {"DailyForecast": {"high_temperature": "maximum"}},
        "relation_renames": {"forecast_for_location": "at_location"},
        "identity_remaps": {"DailyForecast": ["forecast_id"]},
    }
    result = migrate_graph(graph, spec, schema, target)
    repeated = migrate_graph(graph, spec, schema, target)
    assert result == repeated
    mapped = {node["id"]: node for node in result["graph"]["nodes"]}
    for old in graph["nodes"]:
        new = mapped[result["identity_mapping"][old["id"]][0]]
        assert new["sources"] == old["sources"]
        if old["type"] == "DailyForecast":
            assert new["properties"]["maximum"] == old["properties"]["high_temperature"]
            assert new["id"] != old["id"]
    for old, new in zip(graph["edges"], result["graph"]["edges"], strict=True):
        assert new["source"] == result["identity_mapping"][old["source"]][0]
        assert new["target"] == old["target"]
        assert new["relation"] == "at_location"
        assert new["sources"] == old["sources"]


def test_real_coffee_split_join_restores_original_records_and_runs_functions(
    coffee, tmp_path
) -> None:
    schema, graph = coffee
    target, split = split_contract(schema)
    report = validate_ontology(target, tmp_path / "split-ontology")
    assert report["valid"], report
    intermediate = migrate_graph(graph, split, schema, target)
    assert len(intermediate["graph"]["nodes"]) == 2 * len(graph["nodes"])
    assert len(intermediate["graph"]["edges"]) == len(graph["nodes"])
    assert all(len(ids) == 2 for ids in intermediate["identity_mapping"].values())
    restored = migrate_graph(intermediate["graph"], join_contract(), target, schema)
    assert canonical(restored["graph"]) == canonical(graph)
    function = {
        "name": "maximum_quote",
        "description": "Authored real-data maximum probe",
        "inputs": {"type": "object", "properties": {}, "additionalProperties": False},
        "output_schema": {"type": "number"},
        "steps": [
            {"id": "rows", "operator": "lookup_entities", "args": {"entity_types": ["Quote"]}},
            {
                "id": "highest",
                "operator": "aggregate_values",
                "args": {
                    "items": {"$step": "rows"},
                    "request": {"field": "High", "operation": "max"},
                },
            },
        ],
        "result": {"$step": "highest"},
    }
    assert (
        execute_function(restored["graph"], [function], function["name"], {}, schema=schema)[
            "value"
        ]
        == execute_function(graph, [function], function["name"], {}, schema=schema)["value"]
    )


def test_type_rename_is_scoped_and_does_not_change_values(coffee) -> None:
    schema, graph = coffee
    target = deepcopy(schema)
    target["entity_types"]["MarketQuote"] = target["entity_types"].pop("Quote")
    result = migrate_graph(graph, {"type_renames": {"Quote": "MarketQuote"}}, schema, target)
    assert all(node["type"] == "MarketQuote" for node in result["graph"]["nodes"])
    assert [node["properties"] for node in result["graph"]["nodes"]] == [
        node["properties"] for node in graph["nodes"]
    ]


def test_property_collision_cannot_silently_overwrite_a_real_fact(coffee) -> None:
    schema, graph = coffee
    with pytest.raises(MigrationError, match="property_collision"):
        migrate_graph(graph, {"property_renames": {"Quote": {"High": "Low"}}}, schema, schema)


def test_record_replacement_cannot_drop_source_properties(coffee) -> None:
    schema, graph = coffee
    target, spec = split_contract(schema)
    del spec["records"][1]["properties"]["Low"]
    with pytest.raises(MigrationError, match="lost_properties"):
        migrate_graph(graph, spec, schema, target)


def test_split_rejects_identity_collision(coffee) -> None:
    schema, graph = coffee
    target, spec = split_contract(schema)
    spec["records"][1]["identity"] = {"source": "quote"}
    with pytest.raises(MigrationError, match="identity_collision"):
        migrate_graph(graph, spec, schema, target)


def test_keyed_join_rejects_unmatched_actual_rows(coffee) -> None:
    schema, graph = coffee
    target, spec = split_contract(schema)
    intermediate = migrate_graph(graph, spec, schema, target)["graph"]
    omitted = next(node["id"] for node in intermediate["nodes"] if node["type"] == "QuoteValues")
    incomplete = deepcopy(intermediate)
    incomplete["nodes"] = [node for node in incomplete["nodes"] if node["id"] != omitted]
    incomplete["edges"] = [edge for edge in incomplete["edges"] if edge["target"] != omitted]
    with pytest.raises(MigrationError, match="unmatched_join"):
        migrate_graph(incomplete, join_contract(), target, schema)


def test_keyed_join_rejects_nonunique_keys_on_genuine_rows(coffee) -> None:
    schema, graph = coffee
    target, spec = split_contract(schema)
    intermediate = migrate_graph(graph, spec, schema, target)["graph"]
    join = join_contract()
    # Using an actual repeated numeric value as a join key cannot silently
    # create a cartesian product. Date identities and all source values remain.
    joined_schema = deepcopy(schema)
    joined_schema["entity_types"]["Quote"]["properties"]["OtherDate"] = {
        "type": "string",
        "required": True,
    }
    join["records"][0]["properties"]["OtherDate"] = {"source": "values", "property": "Date"}
    join["records"][0]["join_keys"]["values"] = ["High"]
    with pytest.raises(MigrationError, match="ambiguous_join"):
        migrate_graph(intermediate, join, target, joined_schema)


def test_optional_absence_and_null_remain_distinct(weather) -> None:
    schema, graph = weather
    variant = deepcopy(graph)
    forecast = next(node for node in variant["nodes"] if node["type"] == "DailyForecast")
    assert forecast["properties"]["daylight_duration"] is None
    del forecast["properties"]["sunrise"]
    result = migrate_graph(variant, {}, schema, schema)["graph"]
    translated = next(node for node in result["nodes"] if node["id"] == forecast["id"])
    assert "sunrise" not in translated["properties"]
    assert translated["properties"]["daylight_duration"] is None


def test_missing_identity_key_fails_instead_of_inventing_a_value(weather) -> None:
    schema, graph = weather
    with pytest.raises(MigrationError, match="missing_key"):
        migrate_graph(
            graph, {"identity_remaps": {"DailyForecast": ["daylight_duration"]}}, schema, schema
        )


def test_relationship_multiplicity_is_preserved(weather) -> None:
    schema, graph = weather
    repeated = deepcopy(graph)
    repeated["edges"].append(deepcopy(repeated["edges"][0]))
    result = migrate_graph(repeated, {}, schema, schema)["graph"]
    assert result["edges"] == repeated["edges"]


def test_split_relationship_endpoint_needs_explicit_target_type(weather) -> None:
    schema, graph = weather
    target = deepcopy(schema)
    properties = target["entity_types"]["DailyForecast"]["properties"]
    target["entity_types"]["ForecastCopy"] = {
        "primary_key": "forecast_id",
        "properties": deepcopy(properties),
    }
    spec = {
        "records": [
            {
                "sources": {"forecast": "DailyForecast"},
                "target_type": kind,
                "properties": {
                    name: {"source": "forecast", "property": name} for name in properties
                },
                "identity": identity,
            }
            for kind, identity in (
                ("DailyForecast", {"source": "forecast"}),
                ("ForecastCopy", {"keys": ["forecast_id"]}),
            )
        ]
    }
    with pytest.raises(MigrationError, match="ambiguous_endpoint"):
        migrate_graph(graph, spec, schema, target)
    spec["endpoint_types"] = {"forecast_for_location": {"source": "DailyForecast"}}
    result = migrate_graph(graph, spec, schema, target)
    assert result["graph"]["edges"] == graph["edges"]


def test_empty_population_remains_empty_but_invalid_program_still_fails(coffee) -> None:
    schema, _ = coffee
    empty = {"nodes": [], "edges": []}
    target, spec = split_contract(schema)
    result = migrate_graph(empty, spec, schema, target)
    assert result["graph"] == empty
    invalid = deepcopy(spec)
    invalid["records"][0]["properties"]["Date"]["property"] = "unavailable"
    with pytest.raises(MigrationError, match="unknown_property"):
        migrate_graph(empty, invalid, schema, target)


@pytest.mark.parametrize("field", ["task_id", "expected_answer", "python", "model", "defaults"])
def test_program_rejects_unbounded_or_answer_conditioned_fields(field) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MigrationSpec.model_validate({field: "forbidden"})


def test_original_graph_endpoints_are_checked_before_translation(weather) -> None:
    schema, graph = weather
    broken = deepcopy(graph)
    broken["nodes"] = broken["nodes"][:-1]
    with pytest.raises(MigrationError, match="invalid_old_graph"):
        migrate_graph(broken, {}, schema, schema)


def test_join_is_stable_when_artifact_serialization_sorts_aliases(coffee) -> None:
    schema, graph = coffee
    target, split = split_contract(schema)
    intermediate = migrate_graph(graph, split, schema, target)["graph"]
    join = join_contract()
    join["records"][0]["sources"] = {"values": "QuoteValues", "day": "QuoteDay"}
    encoded = json.loads(canonical(join))
    assert migrate_graph(intermediate, join, target, schema) == migrate_graph(
        intermediate, encoded, target, schema
    )


def test_split_join_preserves_repeated_source_attribution(coffee) -> None:
    schema, graph = coffee
    repeated = deepcopy(graph)
    repeated["nodes"][0]["sources"].append(deepcopy(repeated["nodes"][0]["sources"][0]))
    target, split = split_contract(schema)
    intermediate = migrate_graph(repeated, split, schema, target)
    restored = migrate_graph(intermediate["graph"], join_contract(), target, schema)
    assert canonical(restored["graph"]) == canonical(repeated)


def test_new_required_information_cannot_be_fabricated(coffee) -> None:
    schema, graph = coffee
    target = deepcopy(schema)
    target["entity_types"]["Quote"]["properties"]["unavailable"] = {
        "type": "string",
        "required": True,
    }
    with pytest.raises(MigrationError, match="invalid_new_graph"):
        migrate_graph(graph, {}, schema, target)


def test_relation_contraction_cannot_delete_an_unjoined_relationship(weather) -> None:
    schema, graph = weather
    with pytest.raises(MigrationError, match="invalid_contraction"):
        migrate_graph(graph, {"contracted_relations": ["forecast_for_location"]}, schema, schema)


def test_derived_relation_cannot_duplicate_an_existing_edge(coffee) -> None:
    schema, graph = coffee
    target, spec = split_contract(schema)
    spec["derived_relations"].append(deepcopy(spec["derived_relations"][0]))
    with pytest.raises(MigrationError, match="duplicate_derivation"):
        migrate_graph(graph, spec, schema, target)

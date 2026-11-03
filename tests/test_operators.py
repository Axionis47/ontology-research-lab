"""Real-data checks for generic operators and the bounded function interpreter.

The table/RDF mappings and DSL catalogs here are explicit integration-test
contracts, not model-generated artifacts or agent benchmark results.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin

import pytest

from oak import operators as op
from oak.functions import FunctionExecutionError, execute_function, validate_functions
from oak.tasks.coffee import DEFAULT_CACHE, load_coffee

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def coffee_graph() -> tuple[dict, dict, list[dict]]:
    if not (DEFAULT_CACHE / "coffee_price.csv").is_file():
        pytest.fail("Run ensure_coffee_data() before real-data operator checks")
    coffee = load_coffee()
    # A bounded genuine table slice is enough to test execution semantics.
    documents = coffee["corpus"]["documents"][:20]
    rows = [json.loads(document["content"]) for document in documents]
    properties = {
        name: {"type": "string" if name in {"Date", "Currency"} else "number", "required": True}
        for name in coffee["corpus"]["columns"]
    }
    schema = {
        "name": "OfficialCoffeeTableOperatorTest",
        "entity_types": {"CoffeeRow": {"primary_key": "Date", "properties": properties}},
        "relations": {},
    }
    graph = {
        "nodes": [
            {
                "id": document["id"],
                "type": "CoffeeRow",
                "sources": [{"document_id": document["id"], "source_ref": document["source_ref"]}],
                "properties": {
                    key: value if key in {"Date", "Currency"} else float(value)
                    for key, value in row.items()
                },
            }
            for document, row in zip(documents, rows, strict=True)
        ],
        "edges": [],
    }
    return graph, schema, rows


def test_exact_lookup_numeric_filter_and_projection_on_real_table(coffee_graph: tuple) -> None:
    graph, _, rows = coffee_graph
    matches = op.lookup_entities(
        graph, entity_types=["CoffeeRow"], property_filters={"Date": rows[0]["Date"]}
    )
    assert len(matches) == 1
    projected = op.project_properties(matches, property_names=["Open", "Close"])
    assert projected[0]["Open"] == float(rows[0]["Open"])
    assert projected[0]["__entity_id"] == matches[0]["id"]
    assert projected[0]["__sources"] == matches[0]["sources"]
    filtered = op.filter_numeric(
        graph["nodes"], conditions=[{"property": "Volume", "operator": ">", "value": 6000}]
    )
    assert {node["properties"]["Date"] for node in filtered} == {
        row["Date"] for row in rows if float(row["Volume"]) > 6000
    }
    categorized = op.filter_categorical(
        graph["nodes"], conditions=[{"property": "Currency", "values": [rows[0]["Currency"]]}]
    )
    assert len(categorized) == len(rows)


def test_aggregates_and_decimal_postprocessing_on_real_values(coffee_graph: tuple) -> None:
    graph, _, rows = coffee_graph
    result = op.aggregate_values(graph["nodes"], request={"operation": "sum", "field": "Volume"})
    assert result == sum(int(row["Volume"]) for row in rows)
    grouped = op.aggregate_values(
        graph["nodes"], request={"operation": "count", "group_by": "Currency"}
    )
    assert grouped == [{"group": "USD", "value": len(rows)}]
    actual = op.arithmetic(
        operation="subtract", left=float(rows[0]["High"]), right=float(rows[0]["Low"])
    )
    assert actual == float(Decimal(rows[0]["High"]) - Decimal(rows[0]["Low"]))
    no_matches = op.lookup_entities(graph, entity_ids=[])
    assert op.aggregate_values(no_matches, request={"operation": "count"}) == 0
    assert op.aggregate_values(no_matches, request={"operation": "min", "field": "Open"}) is None


@pytest.fixture(scope="module")
def wine_graph() -> dict:
    """Read explicit resource relations directly from the authentic W3C Wine RDF."""
    source = ROOT / "tests/fixtures/ontology/wine.rdf"
    root = ET.parse(source).getroot()
    rdf = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
    base = root.attrib["{http://www.w3.org/XML/1998/namespace}base"]
    nodes, edges = {}, []
    for element in root:
        identifier = element.attrib.get(rdf + "ID")
        about = element.attrib.get(rdf + "about")
        if identifier is None and about is None:
            continue
        source_id = urljoin(base, "#" + identifier if identifier is not None else about)
        nodes.setdefault(
            source_id,
            {
                "id": source_id,
                "type": "Resource",
                "properties": {"iri": source_id},
                "sources": ["w3c:wine.rdf"],
            },
        )
        for predicate in element:
            reference = predicate.attrib.get(rdf + "resource")
            if reference is None:
                continue
            target_id = urljoin(base, reference)
            relation = predicate.tag.split("}")[-1]
            nodes.setdefault(
                target_id,
                {
                    "id": target_id,
                    "type": "Resource",
                    "properties": {"iri": target_id},
                    "sources": ["w3c:wine.rdf"],
                },
            )
            nodes[source_id]["properties"].setdefault(relation, []).append(target_id)
            edges.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "relation": relation,
                    "sources": ["w3c:wine.rdf"],
                }
            )
    assert edges
    return {"nodes": list(nodes.values()), "edges": edges}


def test_traversal_connectivity_and_set_overlap_use_real_rdf_relations(wine_graph: dict) -> None:
    edge = next(edge for edge in wine_graph["edges"] if edge["relation"] == "madeFromGrape")
    traversed = op.traverse_relations(
        wine_graph,
        start_entity_ids=[edge["source"]],
        relation_types=[edge["relation"]],
        include_starting_entities=False,
    )
    assert edge["target"] in {entity["id"] for entity in traversed["entities"]}
    connected = op.filter_relation_connected(
        wine_graph,
        wine_graph["nodes"],
        conditions=[{"relation": edge["relation"], "anchor_ids": [edge["target"]]}],
    )
    assert edge["source"] in {entity["id"] for entity in connected}
    overlap = op.filter_set_overlap(
        wine_graph["nodes"],
        conditions=[{"property": edge["relation"], "values": [edge["target"]], "mode": "all"}],
    )
    assert {entity["id"] for entity in overlap} == {entity["id"] for entity in connected}


def _range_catalog() -> list[dict]:
    return [
        {
            "name": "daily_range",
            "description": "Return the actual high minus low for a supplied date.",
            "inputs": {
                "type": "object",
                "properties": {"date": {"type": "string"}},
                "required": ["date"],
                "additionalProperties": False,
            },
            "output_schema": {"type": "number"},
            "steps": [
                {
                    "id": "row",
                    "operator": "lookup_entities",
                    "args": {
                        "entity_types": ["CoffeeRow"],
                        "property_filters": {"Date": {"$arg": "date"}},
                    },
                },
                {
                    "id": "high",
                    "operator": "aggregate_values",
                    "args": {
                        "items": {"$step": "row"},
                        "request": {"operation": "max", "field": "High"},
                    },
                },
                {
                    "id": "low",
                    "operator": "aggregate_values",
                    "args": {
                        "items": {"$step": "row"},
                        "request": {"operation": "min", "field": "Low"},
                    },
                },
                {
                    "id": "range",
                    "operator": "arithmetic",
                    "args": {
                        "operation": "subtract",
                        "left": {"$step": "high"},
                        "right": {"$step": "low"},
                    },
                },
            ],
            "result": {"$step": "range"},
        }
    ]


def test_typed_function_executes_real_steps_and_records_source_dependencies(
    coffee_graph: tuple,
) -> None:
    graph, schema, rows = coffee_graph
    catalog = _range_catalog()
    result = execute_function(
        graph, catalog, "daily_range", {"date": rows[0]["Date"]}, schema=schema
    )
    assert result["value"] == float(Decimal(rows[0]["High"]) - Decimal(rows[0]["Low"]))
    assert len(result["steps"]) == 4
    assert all(step["status"] == "completed" for step in result["steps"])
    assert result["steps"][0]["inputs"]["property_filters"] == {"Date": rows[0]["Date"]}
    assert result["dependencies"]["coverage"] == "entire_graph_conservative"
    assert graph["nodes"][0]["sources"][0]["document_id"] in result["dependencies"]["source_ids"]
    assert graph["nodes"][0]["properties"]["High"] == float(rows[0]["High"])


def test_function_rejects_forward_references_undeclared_fields_and_canned_results(
    coffee_graph: tuple,
) -> None:
    _, schema, _ = coffee_graph
    catalog = _range_catalog()
    bad = deepcopy(catalog)
    bad[0]["steps"][0]["args"]["property_filters"] = {"Date": {"$step": "high"}}
    with pytest.raises(ValueError, match="forward"):
        validate_functions(bad, schema)
    bad = deepcopy(catalog)
    bad[0]["steps"][1]["args"]["request"]["field"] = "undeclared"
    with pytest.raises(ValueError, match="Undeclared"):
        validate_functions(bad, schema)
    bad = deepcopy(catalog)
    bad[0]["result"] = 42
    with pytest.raises(ValueError, match="canned"):
        validate_functions(bad, schema)


def test_dynamic_property_references_are_checked_at_execution(coffee_graph: tuple) -> None:
    graph, schema, _ = coffee_graph
    catalog = _range_catalog()
    catalog[0]["inputs"]["properties"]["field"] = {"type": "string"}
    catalog[0]["inputs"]["required"].append("field")
    catalog[0]["steps"][1]["args"]["request"]["field"] = {"$arg": "field"}
    with pytest.raises(FunctionExecutionError, match="Undeclared") as caught:
        execute_function(
            graph,
            catalog,
            "daily_range",
            {"date": graph["nodes"][0]["properties"]["Date"], "field": "undeclared"},
            schema=schema,
        )
    assert caught.value.steps[-1]["status"] == "failed"
    assert caught.value.steps[0]["status"] == "completed"


def test_slot_operator_never_substitutes_a_fake_model() -> None:
    with pytest.raises(op.OperatorError, match="real model callback"):
        op.extract_runtime_slots(query="What is the corpus scope?", slot_specs=[])


def test_projection_keeps_schema_primary_key_and_supports_typed_paths(coffee_graph: tuple) -> None:
    graph, schema, rows = coffee_graph
    catalog = _range_catalog()
    catalog[0]["steps"] = catalog[0]["steps"][:1] + [
        {
            "id": "projection",
            "operator": "project_properties",
            "args": {"entities": {"$step": "row"}, "property_names": ["Open"]},
        }
    ]
    catalog[0]["output_schema"] = {"type": "string"}
    catalog[0]["result"] = {"$path": ["projection", 0, "__primary_key", "Date"]}
    result = execute_function(
        graph, catalog, "daily_range", {"date": rows[0]["Date"]}, schema=schema
    )
    assert result["value"] == rows[0]["Date"]
    assert result["steps"][1]["output"][0]["Open"] == float(rows[0]["Open"])


def test_modified_actual_entity_cannot_be_supplied_as_graph_evidence(coffee_graph: tuple) -> None:
    graph, schema, _ = coffee_graph
    modified = deepcopy(graph["nodes"][:1])
    modified[0]["properties"]["Volume"] += 1
    catalog = [
        {
            "name": "provided_rows",
            "description": "Attempt aggregation over caller supplied rows.",
            "inputs": {
                "type": "object",
                "properties": {"rows": {"type": "array"}},
                "required": ["rows"],
                "additionalProperties": False,
            },
            "output_schema": {"type": "number"},
            "steps": [
                {
                    "id": "total",
                    "operator": "aggregate_values",
                    "args": {
                        "items": {"$arg": "rows"},
                        "request": {"operation": "sum", "field": "Volume"},
                    },
                }
            ],
            "result": {"$step": "total"},
        }
    ]
    with pytest.raises(FunctionExecutionError, match="actual graph snapshot"):
        execute_function(graph, catalog, "provided_rows", {"rows": modified}, schema=schema)


def test_unsupported_fuzzy_mode_fails_explicitly(coffee_graph: tuple) -> None:
    graph, _, _ = coffee_graph
    with pytest.raises(op.OperatorError, match="unsupported"):
        op.lookup_entities(graph, name_query="coffee")

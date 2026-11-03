"""Presentation checks against saved real tasks and the unchanged W3C ontology.

Local task tests skip when their genuine content-addressed artifacts are absent.
The Wine projection retains a documented subset of real declarations, with an
engineering identity field for the source IRI, as in test_ontology.py.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from oak.ontology_view import (
    entity_catalog,
    humanize,
    instance_view,
    property_rows,
    schema_view,
)

ROOT = Path(__file__).resolve().parents[1]
RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
RDFS = "{http://www.w3.org/2000/01/rdf-schema#}"
OWL = "{http://www.w3.org/2002/07/owl#}"
USGS = "0249900d19c5f1c7e6b5cc824f7cda50ae1e9c411c3b554648240b90a8e017d3"
COFFEE = "0c7e58d98071595d62bb8f8276de18b96fbb6c76e520c3344e305ef46d95a431"


def _saved_revision(identity: str) -> dict:
    path = ROOT / ".local" / "artifacts" / f"{identity}.json"
    if not path.exists():
        pytest.skip("Genuine local task artifact is not installed")
    payload = path.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == identity
    return json.loads(payload)["data"]


@pytest.fixture
def wine_projection() -> tuple[dict, dict]:
    """Project actual classes, hierarchy, disjointness, and maker declarations.

    Wine's cardinality-one maker plus all-values Winery restriction is encoded
    as qualified exactly-one Winery plus the all-values restriction. Other OWL
    constructs outside this test's subset are omitted, not claimed preserved.
    Winery instances and their IRI values are taken directly from the RDF file.
    """
    path = ROOT / "tests" / "fixtures" / "ontology" / "wine.rdf"
    root = ET.fromstring(path.read_bytes())
    declarations = {item.get(RDF + "ID"): item for item in root.findall(OWL + "Class")}
    selected = ("Wine", "Winery", "LateHarvest", "EarlyHarvest", "WineGrape", "Region")
    types = {}
    for name in selected:
        declaration = declarations[name]
        parents = [
            item.get(RDF + "resource", "").removeprefix("#")
            for item in declaration.findall(RDFS + "subClassOf")
        ]
        disjoint = [
            item.get(RDF + "resource", "").removeprefix("#")
            for item in declaration.findall(OWL + "disjointWith")
        ]
        types[name] = {
            "primary_key": "iri",
            "properties": {"iri": {"type": "string"}},
            "parents": [name for name in parents if name in selected],
            "disjoint_with": [name for name in disjoint if name in selected],
        }
    wine_restrictions = declarations["Wine"].findall(".//" + OWL + "Restriction")
    maker_restrictions = [
        item
        for item in wine_restrictions
        if item.find(OWL + "onProperty").get(RDF + "resource") == "#hasMaker"
    ]
    assert any(
        item.find(OWL + "cardinality") is not None and item.find(OWL + "cardinality").text == "1"
        for item in maker_restrictions
    )
    assert any(
        item.find(OWL + "allValuesFrom") is not None
        and item.find(OWL + "allValuesFrom").get(RDF + "resource") == "#Winery"
        for item in maker_restrictions
    )
    types["Wine"]["restrictions"] = [
        {"property": "hasMaker", "kind": "only", "filler": "Winery"},
        {"property": "hasMaker", "kind": "exact", "filler": "Winery", "cardinality": 1},
    ]
    props = {item.get(RDF + "ID"): item for item in root.findall(OWL + "ObjectProperty")}
    assert (
        props["hasMaker"].find(RDF + "type").get(RDF + "resource").endswith("#FunctionalProperty")
    )
    assert props["producesWine"].find(OWL + "inverseOf").get(RDF + "resource") == "#hasMaker"
    assert (
        props["adjacentRegion"]
        .find(RDF + "type")
        .get(RDF + "resource")
        .endswith("#SymmetricProperty")
    )
    schema = {
        "name": "W3C Wine supported declaration projection",
        "entity_types": types,
        "relations": {
            "hasMaker": {"source": "Wine", "target": "Winery", "characteristics": ["functional"]},
            "producesWine": {"source": "Winery", "target": "Wine", "inverse_of": "hasMaker"},
            "adjacentRegion": {
                "source": "Region",
                "target": "Region",
                "characteristics": ["symmetric"],
            },
        },
    }
    winery_elements = [item for item in root if item.tag.endswith("}Winery")]
    base = "http://www.w3.org/TR/2003/PR-owl-guide-20031209/wine#"
    graph = {
        "nodes": [
            {
                "id": base + item.get(RDF + "ID"),
                "type": "Winery",
                "properties": {"iri": base + item.get(RDF + "ID")},
                "sources": [
                    {
                        "document_id": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "source_ref": "#" + item.get(RDF + "ID"),
                    }
                ],
            }
            for item in winery_elements
            if item.get(RDF + "ID")
        ],
        "edges": [],
    }
    assert graph["nodes"]
    return schema, graph


def test_wine_constraints_remain_distinct_from_identity_and_record_rules(wine_projection) -> None:
    schema, graph = wine_projection
    before = json.dumps((schema, graph), sort_keys=True)
    view = schema_view(schema, graph)
    late = view["types"]["LateHarvest"]
    assert late["parents"] == ["Wine"]
    assert late["disjoint_with"] == ["EarlyHarvest"]
    assert "Late Harvest" in " ".join(view["types"]["EarlyHarvest"]["details"])
    assert all(rule["inherited"] and rule["declared_by"] == "Wine" for rule in late["restrictions"])
    assert {edge["kind"] for edge in view["edges"]} == {"inheritance", "disjoint", "relation"}
    wine = view["types"]["Wine"]
    sentences = " ".join(row["text"] for row in wine["restrictions"])
    assert "exactly 1" in sentences and "does not require any value" in sentences
    key = wine["properties"][0]
    assert key["required"] and "minimum 1" in key["ontology_rule"]
    assert "unique primary key" in key["record_rule"]
    assert "not owl:hasKey" in " ".join(view["semantics"])
    relations = {item["id"]: item for item in view["relations"]}
    assert "At most one" in " ".join(relations["hasMaker"]["details"])
    assert "Inverse of Produces Wine" in " ".join(relations["hasMaker"]["details"])
    assert "Inverse of Has Maker" in " ".join(relations["producesWine"]["details"])
    assert "symmetric" in " ".join(relations["adjacentRegion"]["details"])
    catalog = entity_catalog(schema, graph)
    assert any(node["label"] == "Beringer" for node in catalog)
    assert all(node["sources"] for node in catalog)
    assert json.dumps((schema, graph), sort_keys=True) == before


def test_real_usgs_labels_neighborhood_and_exact_edges() -> None:
    revision = _saved_revision(USGS)
    schema, graph = revision["schema"], revision["graph"]
    view = schema_view(schema, graph)
    assert {node["direct_count"] for node in view["nodes"]} == {15}
    assert len(view["edges"]) == 3
    catalog = entity_catalog(schema, graph)
    assert len(catalog) == 60
    assert len({node["label"] for node in catalog}) == 60
    assert all(not re.search(r"[a-f0-9]{32,}", node["label"]) for node in catalog)
    event = next(node for node in catalog if node["type"] == "EarthquakeEvent")
    assert event["base_label"] == event["values"]["place"]
    depth = next(node for node in catalog if node["type"] == "Depth")
    assert "Depth km:" in depth["label"]
    assert any("kilometres" in prop["description"] for prop in depth["properties"])
    neighborhood = instance_view(schema, graph, focus_id=event["id"])
    assert neighborhood["shown_nodes"] == 4 and neighborhood["shown_edges"] == 3
    assert neighborhood["omitted_nodes"] == 56
    real_edges = {(edge["source"], edge["target"], edge["relation"]) for edge in graph["edges"]}
    assert all(
        (edge["source"], edge["target"], edge["relation"]) in real_edges
        for edge in neighborhood["edges"]
    )
    bounded = instance_view(schema, graph, focus_id=event["id"], max_nodes=2)
    assert bounded["truncated_nodes"] == 2 and bounded["omitted_nodes"] == 58
    assert "Explicit neighborhood" in bounded["scope"]


def test_real_coffee_scoped_inheritance_and_disconnected_records() -> None:
    revision = _saved_revision(COFFEE)
    schema, graph = revision["schema"], revision["graph"]
    rows = property_rows(schema, "CoffeeMarketDay")
    assert len(rows) == 14
    dates = [row for row in rows if row["name"] == "Date"]
    assert {row["qualified_name"] for row in dates} == {
        "CoffeeMarketDay.Date",
        "CommodityPriceRecord.Date",
    }
    assert sum(row["inherited"] for row in dates) == 1
    view = schema_view(schema, graph)
    assert view["types"]["CommodityPriceRecord"]["direct_count"] == 0
    assert view["types"]["CommodityPriceRecord"]["compatible_count"] == 5746
    assert view["types"]["CoffeeMarketDay"]["direct_count"] == 5746
    browse = instance_view(schema, graph, type_name="CommodityPriceRecord", max_nodes=12)
    assert browse["matching_nodes"] == 5746 and browse["truncated_nodes"] == 5734
    assert browse["shown_nodes"] == 12 and browse["shown_edges"] == 0
    assert all(node["label"] == node["values"]["Date"] for node in browse["nodes"])
    filtered = instance_view(schema, graph, search="2015-07-06", max_nodes=12)
    assert filtered["matching_nodes"] == 1
    assert filtered["nodes"][0]["values"]["Date"] == "2015-07-06"
    focus = instance_view(schema, graph, focus_id=filtered["nodes"][0]["id"])
    assert focus["shown_nodes"] == 1 and focus["shown_edges"] == 0
    assert focus["omitted_nodes"] == 5745


def test_view_bounds_and_unknown_focus_fail_explicitly(wine_projection) -> None:
    schema, graph = wine_projection
    with pytest.raises(ValueError, match="View bounds"):
        instance_view(schema, graph, max_nodes=0)
    with pytest.raises(ValueError, match="Focus entity"):
        instance_view(schema, graph, focus_id="not-present")
    with pytest.raises(ValueError, match="Unknown entity type"):
        instance_view(schema, graph, type_name="not-declared")
    empty = instance_view(schema, graph, search="no matching winery here")
    assert empty["matching_nodes"] == 0 and empty["shown_nodes"] == 0
    assert empty["omitted_nodes"] == len(graph["nodes"])


def test_identifier_words_use_actual_schema_identifiers(wine_projection) -> None:
    schema, _ = wine_projection
    assert humanize("hasMaker") == "Has Maker"
    assert humanize("LateHarvest") == "Late Harvest"
    assert humanize("schema_version") == "Schema version"
    assert all(humanize(name) for name in schema["entity_types"])

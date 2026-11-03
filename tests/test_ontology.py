"""Real W3C ontology fixtures and explicit, recorded negative mutations.

No mocked reasoner or fabricated benchmark records. The lightweight schema is
an explicitly documented projection of real W3C declarations, not a claim to
roundtrip all constructs in the full wine ontology.
"""

from __future__ import annotations

import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import owlready2 as owl
import pytest
from pydantic import ValidationError

from oak.ontology import (
    parse_schema,
    schema_json_schema,
    schema_to_owl,
    validate_graph_records,
    validate_ontology,
    validate_owl_file,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ontology"
BASE = "http://www.w3.org/TR/2003/PR-owl-guide-20031209/"
RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
RDFS = "{http://www.w3.org/2000/01/rdf-schema#}"
OWL = "{http://www.w3.org/2002/07/owl#}"


def _bundle(destination: Path, mutation: str | None = None) -> Path:
    """Preserve source bytes; remap only import locations in execution copies."""
    destination.mkdir(parents=True)
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    for name in ("wine", "food"):
        source = FIXTURES / f"{name}.rdf"
        assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest["files"][name]["sha256"]
        text = source.read_text()
        other = "food" if name == "wine" else "wine"
        text = text.replace(
            f'<owl:imports rdf:resource="{BASE}{other}"/>',
            f'<owl:imports rdf:resource="{(destination / (other + ".rdf")).as_uri()}"/>'
            if name == "wine"
            else "",
        )
        if name == "wine" and mutation == "unsatisfiable":
            # Add one named negative-control class to the genuine source, with
            # incompatible superclasses. No instance is asserted for that class.
            control = f'''<owl:Class rdf:about="urn:oak:test:ContradictoryWine">
              <rdfs:subClassOf rdf:resource="{BASE}wine#Wine"/>
              <rdfs:subClassOf><owl:Class><owl:complementOf
                rdf:resource="{BASE}wine#Wine"/></owl:Class></rdfs:subClassOf>
            </owl:Class>'''
            text = text.replace("</rdf:RDF>", control + "</rdf:RDF>")
        if name == "wine" and mutation == "inconsistent":
            # Wine has actual named individuals in this upstream artifact.
            control = f'''<owl:Class rdf:about="{BASE}wine#Wine">
              <rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Nothing"/>
            </owl:Class>'''
            text = text.replace("</rdf:RDF>", control + "</rdf:RDF>")
        (destination / f"{name}.rdf").write_text(text)
    (destination / "derivation.json").write_text(
        json.dumps(
            {
                "source_manifest": manifest,
                "transformations": [
                    "Wine import mapped to local food; redundant food-to-root import removed; "
                    "all axioms/IRIs retained"
                ],
                "controlled_mutation": mutation,
            },
            indent=2,
        )
    )
    return destination / "wine.rdf"


@pytest.fixture
def wine_schema() -> dict:
    """Project actual Wine/Winery/maker declarations into the supported grammar.

    `iri` is an engineering identity field storing the upstream RDF identifier.
    The source has madeFromGrape and many other axioms omitted by this small
    projection; full-original reasoning is tested independently below.
    """
    root = ET.fromstring((FIXTURES / "wine.rdf").read_bytes())
    declarations = {item.get(RDF + "ID"): item for item in root.findall(OWL + "Class")}
    assert "Wine" in declarations and "Winery" in declarations
    props = {item.get(RDF + "ID"): item for item in root.findall(OWL + "ObjectProperty")}
    has_maker = props["hasMaker"]
    restrictions = declarations["Wine"].findall(".//" + OWL + "Restriction")
    assert any(
        item.find(OWL + "onProperty").get(RDF + "resource") == "#hasMaker"
        and item.find(OWL + "allValuesFrom") is not None
        and item.find(OWL + "allValuesFrom").get(RDF + "resource") == "#Winery"
        for item in restrictions
    )
    assert has_maker.find(RDF + "type").get(RDF + "resource") == OWL[1:-1] + "FunctionalProperty"
    return {
        "schema_version": 1,
        "name": "W3C wine declaration projection",
        "description": "Real Wine/Winery/hasMaker declarations; technical RDF IRI identity added",
        "entity_types": {
            name: {"primary_key": "iri", "properties": {"iri": {"type": "string"}}}
            for name in ("Wine", "Winery")
        },
        "relations": {
            "hasMaker": {
                "source": "Wine",
                "target": "Winery",
                "characteristics": ["functional"],
            }
        },
    }


def test_full_w3c_bundle_and_real_negative_controls(tmp_path: Path) -> None:
    """Distinguish satisfiable input, unsatisfiable class, and inconsistent world."""
    for mutation, expected in (
        (None, "consistent"),
        ("unsatisfiable", "unsatisfiable_classes"),
        ("inconsistent", "inconsistent"),
    ):
        name = mutation or "original"
        path = _bundle(tmp_path / name / "input", mutation)
        report = validate_owl_file(path, tmp_path / name / "reasoner")
        assert report["status"] == expected, Path(report["stderr"]["path"]).read_text()[:1500]
        assert report["command"] and report["java"]["version_output"]
        assert report["input"]["sha256"]
        assert Path(report["stdout"]["path"]).exists()
        if mutation == "unsatisfiable":
            assert "urn:oak:test:ContradictoryWine" in report["unsatisfiable_classes"]
            assert report["consistent"] is True and report["valid"] is False
        elif mutation == "inconsistent":
            assert report["consistent"] is False
        else:
            assert report["valid"] is True


def test_schema_to_real_owl_reasoning_and_restriction_contradiction(
    wine_schema: dict,
    tmp_path: Path,
) -> None:
    original = validate_ontology(wine_schema, tmp_path / "original")
    assert original["status"] == "consistent", original
    changed = copy.deepcopy(wine_schema)
    changed["entity_types"]["Wine"]["restrictions"] = [
        {"property": "hasMaker", "kind": "min", "filler": "Winery", "cardinality": 2},
    ]
    # A functional hasMaker cannot give a Wine two distinct Winery fillers.
    negative = validate_ontology(changed, tmp_path / "cardinality-conflict")
    assert negative["status"] == "unsatisfiable_classes", negative
    assert any(iri.endswith("type__Wine") for iri in negative["unsatisfiable_classes"])
    # No global-world contamination from a rejected candidate.
    repeat = validate_ontology(wine_schema, tmp_path / "repeat")
    assert repeat["valid"] is True
    assert repeat["schema"]["sha256"] == original["schema"]["sha256"]
    with pytest.raises(FileExistsError):
        validate_ontology(wine_schema, tmp_path / "original")


def test_mapping_exact_universal_existential_and_inverse(wine_schema: dict, tmp_path: Path) -> None:
    candidate = copy.deepcopy(wine_schema)
    candidate["relations"]["madeByInverse"] = {
        "source": "Winery",
        "target": "Wine",
        "inverse_of": "hasMaker",
    }
    candidate["entity_types"]["Wine"]["restrictions"] = [
        {"property": "hasMaker", "kind": "exact", "filler": "Winery", "cardinality": 1},
        {"property": "hasMaker", "kind": "only", "filler": "Winery"},
        {"property": "hasMaker", "kind": "some", "filler": "Winery"},
    ]
    translation = schema_to_owl(candidate, tmp_path / "schema.owl")
    world = owl.World()
    try:
        world.get_ontology((tmp_path / "schema.owl").as_uri()).load()
        wine = world[translation["classes"]["Wine"]]
        maker = world[translation["properties"]["hasMaker"]]
        inverse = world[translation["properties"]["madeByInverse"]]
        assert maker.inverse_property == inverse
        restrictions = [x for x in wine.is_a if isinstance(x, owl.Restriction)]
        assert {owl.EXACTLY, owl.ONLY, owl.SOME}.issubset({x.type for x in restrictions})
    finally:
        world.close()
    assert validate_ontology(candidate, tmp_path / "reasoner")["valid"]


def test_unknown_fields_bad_references_and_empty_schema_are_rejected(
    wine_schema: dict,
    tmp_path: Path,
) -> None:
    variants = []
    for mutation in ("root", "entity", "property", "relation", "empty", "date", "reference"):
        candidate = copy.deepcopy(wine_schema)
        if mutation == "root":
            candidate["invented"] = True
        elif mutation == "entity":
            candidate["entity_types"]["Wine"]["invented"] = True
        elif mutation == "property":
            candidate["entity_types"]["Wine"]["properties"]["iri"]["invented"] = True
        elif mutation == "relation":
            candidate["relations"]["hasMaker"]["invented"] = True
        elif mutation == "empty":
            candidate["entity_types"] = {}
        elif mutation == "date":
            candidate["entity_types"]["Wine"]["properties"]["iri"]["type"] = "date"
        else:
            candidate["relations"]["hasMaker"]["target"] = "Undeclared"
        variants.append((mutation, candidate))
    for mutation, candidate in variants:
        with pytest.raises(ValidationError):
            parse_schema(candidate)
        report = validate_ontology(candidate, tmp_path / mutation)
        assert report["status"] == "invalid_schema"
        assert report["consistent"] is None
    assert schema_json_schema()["additionalProperties"] is False


def test_real_wine_records_data_integrity_separate_from_owl(wine_schema: dict) -> None:
    root = ET.fromstring((FIXTURES / "wine.rdf").read_bytes())
    actual_wineries = [
        x for x in root.iter() if x.tag == "{" + BASE + "wine#}Winery" and x.get(RDF + "ID")
    ]
    assert len(actual_wineries) > 1
    source = {"url": "https://www.w3.org/TR/2004/REC-owl-guide-20040210/wine.rdf"}
    nodes = [
        {
            "id": item.get(RDF + "ID"),
            "type": "Winery",
            "properties": {
                "iri": BASE + "wine#" + item.get(RDF + "ID"),
            },
            "sources": [source],
        }
        for item in actual_wineries[:2]
    ]
    assert validate_graph_records(wine_schema, nodes, [])["valid"]
    duplicate = copy.deepcopy(nodes[0])
    duplicate["id"] += "_duplicate_negative_control"
    invalid = validate_graph_records(wine_schema, nodes + [duplicate], [])
    assert not invalid["valid"] and any("duplicate primary key" in x for x in invalid["errors"])
    missing = copy.deepcopy(nodes)
    missing[0]["properties"].pop("iri")
    assert not validate_graph_records(wine_schema, missing, [])["valid"]


def test_disjointness_and_property_flags_are_reasoned(wine_schema: dict, tmp_path: Path) -> None:
    """Controlled changes to real vocabulary exercise two other Appendix A categories."""
    disjoint = copy.deepcopy(wine_schema)
    disjoint["entity_types"]["Wine"]["parents"] = ["Winery"]
    disjoint["entity_types"]["Wine"]["disjoint_with"] = ["Winery"]
    result = validate_ontology(disjoint, tmp_path / "disjoint")
    assert result["status"] == "unsatisfiable_classes", result
    contradictory_property = copy.deepcopy(wine_schema)
    contradictory_property["relations"]["hasMaker"]["characteristics"] = [
        "reflexive",
        "irreflexive",
    ]
    result = validate_ontology(contradictory_property, tmp_path / "property")
    assert result["status"] == "inconsistent", result

"""Replay the deterministic assembler on a genuine retained extraction failure."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from oak.materialization import derive_demand
from oak.ontology import validate_graph_records
from oak.pipeline import assemble_extracted_relations
from oak.store import canonical

ARTIFACTS = Path(__file__).parents[1] / ".local/artifacts"


def actual(identity):
    path = ARTIFACTS / f"{identity}.json"
    if not path.exists():
        pytest.skip("Retained real demand-extraction failure is unavailable")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == identity
    return json.loads(raw)["data"]


def test_unsolicited_relations_are_excluded_but_demanded_endpoints_still_validate():
    kernel = actual("ccacfea059f9fccbe0ff8509d2f313f47ca23c2200fb73b250683977ef2e99c7")
    saved = actual("6a013b5687d8c60530d094e9abf96c0a4392568efbc3701e5ec43184fcc87619")
    receipt = actual("46c028968f6b999b5c5924100b07d3f83aa60e359b3bc7ebacca4063b73d53f4")
    function = next(
        item for item in kernel["functions"] if item["name"] == "fetch_max_forecast_high"
    )
    demand = derive_demand(kernel["schema"], function, {"native_arguments": receipt["args"]})
    assert demand.relation_types == []
    sources = {
        identity: {"document_id": identity, "source_ref": identity}
        for identity in saved["citation_aliases"].values()
    }
    nodes = []
    for table in saved["extraction"]["entity_tables"]:
        for row in table["rows"]:
            properties = dict(zip(table["columns"], row["values"], strict=True))
            key = properties[kernel["schema"]["entity_types"][table["type"]]["primary_key"]]
            nodes.append(
                {
                    "id": hashlib.sha256(canonical([table["type"], key])).hexdigest(),
                    "type": table["type"],
                    "properties": properties,
                    "sources": [
                        sources[saved["citation_aliases"].get(x, x)] for x in row["source_ids"]
                    ],
                }
            )
    relations = deepcopy(saved["extraction"]["relations"])
    edges, excluded = assemble_extracted_relations(kernel["schema"], relations, sources, demand)
    assert edges == [] and len(excluded) == 2
    assert validate_graph_records(kernel["schema"], nodes, edges)["valid"]
    full_edges, excluded = assemble_extracted_relations(kernel["schema"], relations, sources)
    assert len(full_edges) == 2 and excluded == []
    assert not validate_graph_records(kernel["schema"], nodes, full_edges)["valid"]
    assert relations == saved["extraction"]["relations"]

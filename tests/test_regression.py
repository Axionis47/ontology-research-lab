"""Compatibility checks over actual Coffee executions, without simulated agents.

The catalogs/adapters are explicit test contracts. Function calls execute for real.
No test labels a handcrafted response as an LLM answer or supplies a fake proposer.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from oak.functions import execute_function
from oak.regression import (
    AdapterSpec,
    adapter_proposal_payload,
    replay_function_call,
    replay_recorded_calls,
    validate_adapter,
)
from oak.store import canonical
from oak.tasks.coffee import DEFAULT_CACHE, load_coffee


@pytest.fixture(scope="module")
def versions() -> tuple[dict, dict, dict, dict]:
    if not (DEFAULT_CACHE / "coffee_price.csv").is_file():
        pytest.fail("Install the genuine Coffee data before regression integration checks")
    data = load_coffee()
    documents = data["corpus"]["documents"][:2]
    schema = {
        "name": "GenuineCoffeeInterfaceTest",
        "entity_types": {
            "Quote": {
                "primary_key": "Date",
                "properties": {
                    "Date": {"type": "string", "required": True},
                    "High": {"type": "number", "required": True},
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
                },
                "sources": [{"document_id": document["id"], "source_ref": document["source_ref"]}],
            }
            for document in documents
        ],
        "edges": [],
    }
    function = {
        "name": "read_high",
        "description": "Read the high from the actual supplied quote.",
        "inputs": {
            "type": "object",
            "properties": {"date": {"type": "string"}},
            "required": ["date"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {"high": {"type": "number"}},
            "required": ["high"],
            "additionalProperties": False,
        },
        "steps": [
            {
                "id": "lookup",
                "operator": "lookup_entities",
                "args": {
                    "entity_types": ["Quote"],
                    "property_filters": {"Date": {"$arg": "date"}},
                },
            }
        ],
        "result": {"high": {"$path": ["lookup", 0, "properties", "High"]}},
    }
    old = {
        "schema": schema,
        "graph": graph,
        "functions": [function],
        "corpus_id": data["corpus"]["id"],
        "assessment": {"construction_results": []},
    }
    old["id"] = hashlib.sha256(canonical(old)).hexdigest()
    new = deepcopy(old)
    new["parent"] = old["id"]
    new["schema"]["entity_types"]["Quote"]["properties"]["Peak"] = new["schema"]["entity_types"][
        "Quote"
    ]["properties"].pop("High")
    for entity in new["graph"]["nodes"]:
        entity["properties"]["Peak"] = entity["properties"].pop("High")
    fn = new["functions"][0]
    fn["name"] = "read_peak"
    fn["inputs"]["properties"] = {"day": {"type": "string"}}
    fn["inputs"]["required"] = ["day"]
    fn["output_schema"]["properties"] = {"peak": {"type": "number"}}
    fn["output_schema"]["required"] = ["peak"]
    fn["steps"][0]["args"]["property_filters"] = {"Date": {"$arg": "day"}}
    fn["result"] = {"peak": {"$path": ["lookup", 0, "properties", "Peak"]}}
    new["id"] = hashlib.sha256(canonical(new)).hexdigest()
    spec = {
        "old_revision": old["id"],
        "new_revision": new["id"],
        "mappings": [
            {
                "old_function": "read_high",
                "new_function": "read_peak",
                "arguments": {"date": "day"},
                "output_fields": {"peak": "high"},
            }
        ],
    }
    args = {"date": graph["nodes"][0]["properties"]["Date"]}
    executed = execute_function(graph, [function], "read_high", args, schema=schema)
    receipt = {"function": "read_high", "args": args, "status": "completed", **executed}
    return old, new, spec, receipt


def test_actual_call_replays_through_bijective_renames(versions: tuple) -> None:
    old, new, adapter, receipt = versions
    validated = validate_adapter(adapter, old, new)
    result = replay_function_call(old, new, receipt, adapter=validated)
    assert result["status"] == "passed"
    assert result["new_args"] == {"day": receipt["args"]["date"]}
    assert result["new_value"] == {"peak": receipt["value"]["high"]}
    assert result["adapted_value"] == receipt["value"]
    assert result["steps"][0]["status"] == "completed"
    assert result["fresh_agent_success"] == "unverified"


def test_adapter_is_bound_to_exact_saved_revisions(versions: tuple) -> None:
    old, new, adapter, _ = versions
    incorrect = deepcopy(adapter)
    incorrect["old_revision"] = new["id"]
    with pytest.raises(ValueError, match="revision IDs"):
        validate_adapter(incorrect, old, new)


def test_type_conversion_and_constant_overrides_are_rejected(versions: tuple) -> None:
    old, new, adapter, _ = versions
    changed = deepcopy(new)
    changed["functions"][0]["inputs"]["properties"]["day"] = {"type": "integer"}
    with pytest.raises(ValueError, match="input contract"):
        validate_adapter(adapter, old, changed)
    forbidden = deepcopy(adapter)
    forbidden["mappings"][0]["defaults"] = {"day": old["graph"]["nodes"][0]["properties"]["Date"]}
    with pytest.raises(ValueError, match="Extra inputs"):
        validate_adapter(forbidden, old, new)


def test_actual_different_corpus_values_fail_output_comparison(versions: tuple) -> None:
    old, new, adapter, receipt = versions
    # Replay a genuine call from the second source row against a candidate that
    # contains only the first row. The absent evidence must not return an old answer.
    args = {"date": old["graph"]["nodes"][1]["properties"]["Date"]}
    execution = execute_function(
        old["graph"], old["functions"], "read_high", args, schema=old["schema"]
    )
    other_receipt = {"function": "read_high", "args": args, "status": "completed", **execution}
    narrowed = deepcopy(new)
    narrowed["graph"]["nodes"] = narrowed["graph"]["nodes"][:1]
    result = replay_function_call(old, narrowed, other_receipt, adapter=adapter)
    assert result["status"] == "failed"
    assert "reason" in result
    assert result["steps"][0]["output"] == []
    assert "adapted_value" not in result
    assert receipt["value"] != other_receipt["value"]


def test_proposal_context_excludes_graphs_trajectories_and_expected_outputs(
    versions: tuple,
) -> None:
    old, new, _, receipt = versions
    with_receipt = deepcopy(old)
    with_receipt["assessment"]["construction_results"] = [{"result": receipt}]
    payload = adapter_proposal_payload(with_receipt, new)
    assert set(payload["old"]) == {"id", "schema", "functions"}
    assert set(payload["new"]) == {"id", "schema", "functions"}
    assert "graph" not in payload["old"] and "assessment" not in payload["old"]
    assert payload["adapter_schema"] == AdapterSpec.model_json_schema()


def test_empty_and_non_agent_receipts_never_claim_answer_preservation(versions: tuple) -> None:
    old, new, adapter, receipt = versions
    empty = replay_recorded_calls(old, new, adapter=adapter)
    assert empty["status"] == "unverified" and not empty["checks"]
    # This is explicitly a deterministic component receipt, not an LLM answer.
    component = {
        "status": "component_execution",
        "kernel_revision": old["id"],
        "trajectory": [receipt],
    }
    result = replay_recorded_calls(old, new, [component], adapter=adapter)
    assert result["status"] == "unverified"
    assert result["checks"][0]["executed_calls"] == 0
    assert result["fresh_agent_success"] == "unverified"


def test_actual_saved_construction_trajectories_are_included_without_ask_receipts() -> None:
    """Replay actual Gemini construction traces through an explicit identity test contract."""
    pilot_path = Path(".local/pilots/usgs.json")
    if not pilot_path.is_file():
        pytest.skip("The genuine local USGS construction pilot has not run")
    pilot = json.loads(pilot_path.read_text())
    identity = pilot.get("inference_check", {}).get("result", {}).get("kernel_revision")
    if not identity:
        pytest.skip("The genuine local USGS pilot has not saved an initial revision")
    raw = (Path(".local/artifacts") / f"{identity}.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == identity
    old = {**json.loads(raw)["data"], "id": identity}
    assert old["assessment"]["construction_results"]
    assert all(
        item["result"]["kernel_revision"] is None
        and item["result"]["status"] == "answered"
        and item["score"] is True
        for item in old["assessment"]["construction_results"]
    )
    # This candidate is a declared identity integration contract, not a claimed
    # model-generated revision. Both source artifacts and old trajectories are real.
    candidate = {**deepcopy(old), "parent": identity}
    candidate["id"] = hashlib.sha256(canonical(candidate)).hexdigest()
    replay = replay_recorded_calls(old, candidate)
    assert replay["status"] == "passed"
    assert len(replay["checks"]) == len(old["assessment"]["construction_results"])
    assert all(check["executed_calls"] > 0 for check in replay["checks"])
    assert all(check["origin"] == "parent_construction" for check in replay["checks"])
    assert replay["fresh_agent_success"] == "unverified"

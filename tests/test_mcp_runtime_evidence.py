"""Check MCP admission boundaries against genuine retained pilot artifacts.

Counterfactual catalog edits below are explicitly unexecuted negative inputs.
No model output, MCP response, or successful task execution is simulated.
"""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from oak.bootstrap import acquisition_result, function_dataflow, sampled_episode_summary
from oak.construction_contracts import requirement_inputs, validate_function_coverage
from oak.service import Service
from oak.store import Store
from oak.task_context import TaskSurface

PROJECT = Path(__file__).resolve().parents[1]


def test_unused_acquisition_cannot_turn_real_graph_function_into_acquisition_witness():
    manifest_path = PROJECT / ".local/pilots/usgs.json"
    if not manifest_path.exists():
        pytest.skip("Run the genuine USGS pilot before checking retained functions")
    manifest = json.loads(manifest_path.read_text())
    service = Service(PROJECT / ".local")
    revision = service.revision(manifest["task_id"], manifest["candidate_revision"])
    function = deepcopy(revision["functions"][0])
    assert not function_dataflow(function)["result_acquisition_steps"]
    # Deliberately add an unused call after a real, generated graph computation.
    # This catalog is never executed or represented as a successful model output.
    function["steps"].append(
        {
            "id": "unused_negative_control",
            "operator": "invoke_capability",
            "args": {"capability": "unexecuted/negative-control", "arguments": {}},
        }
    )
    assert not function_dataflow(function)["acquisition_computation_steps"]
    assert "unused_negative_control" not in function_dataflow(function)["result_steps"]


def test_actual_starter_summary_preserves_behavior_without_answer_values():
    manifest_path = PROJECT / ".local/verification/weather/starter.json"
    if not manifest_path.exists():
        pytest.skip("Run the genuine MCP starter episode before retained-evidence checks")
    manifest = json.loads(manifest_path.read_text())
    store = Store(PROJECT / ".local")
    episode = store.get(manifest["episode_id"])
    summary = sampled_episode_summary(manifest["episode_id"], episode)
    assert "answer" not in summary
    assert summary["terminal_status"] == episode["status"]
    assert summary["assessment"]["status"] == "unmeasured"
    assert summary["observations"]
    assert all("output" not in observation for observation in summary["observations"])
    assert [item["receipt_ids"] for item in summary["observations"]] == [
        item["receipt_ids"] for item in episode["observations"]
    ]


def test_acquisition_view_excludes_other_real_response_records():
    manifest_path = PROJECT / ".local/verification/weather/construction.json"
    if not manifest_path.exists():
        pytest.skip("Run real MCP construction before checking acquired graph scope")
    manifest = json.loads(manifest_path.read_text())
    store = Store(PROJECT / ".local")
    kernel = store.get(manifest["kernel_id"])
    graph = store.get(kernel["evidence"]["graph_id"])
    document = graph["nodes"][0]["sources"][0]["document_id"]
    observed = [
        node
        for node in graph["nodes"]
        if any(source["document_id"] == document for source in node["sources"])
    ]
    assert 0 < len(observed) < len(graph["nodes"])
    # This is a view over genuine recorded nodes, not generated observation data.
    result = acquisition_result(kernel["schema"], graph, {"nodes": observed}, document)
    assert {node["id"] for node in result["entities"]} == {node["id"] for node in observed}
    for kind, nodes in result["entities_by_type"].items():
        assert all(node["type"] == kind and node in observed for node in nodes)


def test_real_focused_construction_retains_prompt_and_requirement_evidence():
    """Inspect the genuine two-case verification without replaying model outputs."""
    receipt_path = PROJECT / ".local/verification/focused-construction/receipt.json"
    if not receipt_path.exists():
        pytest.skip("Run genuine focused-stage construction before inspecting its evidence")
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] == "completed"
    store = Store(PROJECT / ".local")
    kernel = store.get(receipt["construction"]["kernel_id"])
    evidence = kernel["evidence"]
    manifest = store.get(evidence["prompt_manifest_id"])
    for source in manifest["sources"]:
        assert hashlib.sha256(source["content"].encode()).hexdigest() == source["sha256"]
    for stage in manifest["stages"].values():
        assert hashlib.sha256(stage["instruction"].encode()).hexdigest() == stage["sha256"]

    source = store.get(receipt["task"]["artifact_id"])
    surface = TaskSurface.model_validate(source["configuration"])
    obligations = requirement_inputs(surface.queries)
    coverage = store.get(evidence["coverage_id"])
    checked = validate_function_coverage(coverage["mappings"], obligations, kernel["functions"])
    assert checked.structurally_complete and checked.counts.obligations == 4
    assert coverage["outcome_status"] == "not_checked"
    assert kernel["assessment"]["fresh_task_success"] == "unmeasured"
    assert kernel["validation"]["valid"] is True
    probes = store.get(evidence["probes_id"])
    assert {item["probe"]["function"] for item in probes} == {
        f["name"] for f in kernel["functions"]
    }
    assert all(item["status"] == "passed" for item in probes)

    receipts = store.rows(
        "SELECT evidence_id FROM model_calls WHERE run_id=? AND evidence_id IS NOT NULL",
        (receipt["construction"]["run_id"],),
    )
    recorded = {}
    for row in receipts:
        call = store.get(row["evidence_id"])
        request = json.loads(call["request"]["prompt"])
        prefix = request["stage"].split(".")[0]
        stage = {
            "requirements": "requirements",
            "schema": "schema",
            "compose": "functions",
            "construction_extract": "extraction",
            "probe_extract": "extraction",
        }.get(prefix)
        if stage:
            assert request["instruction"] == manifest["stages"][stage]["instruction"]
            recorded[stage] = request
    assert set(recorded) == {"requirements", "schema", "functions", "extraction"}
    assert "schema" not in recorded["requirements"]["inputs"]
    assert "requirements" in recorded["schema"]["inputs"]
    assert "requirements" in recorded["functions"]["inputs"]
    assert "requirements" not in recorded["extraction"]["inputs"]


def test_real_fresh_details_question_uses_frozen_projection_without_pool_changes():
    """Inspect fresh live inference, with execution distinct from task assessment."""
    directory = PROJECT / ".local/verification/focused-construction"
    if not (directory / "inference-v2.json").exists():
        pytest.skip("Run the genuine fresh details question before inspecting its trajectory")
    construction = json.loads((directory / "receipt.json").read_text())
    inference = json.loads((directory / "inference-v2.json").read_text())
    assert inference["status"] == "completed"
    episode = inference["result"]["episode"]
    assert episode["status"] == "complete"
    assert episode["kernel_revision"] == construction["construction"]["kernel_id"]
    assert episode["split"] == "inference"
    assert episode["assessment"]["status"] == "unmeasured"
    store = Store(PROJECT / ".local")
    kernel = store.get(episode["kernel_revision"])
    function = next(
        f for f in kernel["functions"] if f["name"] == episode["trajectory"][0]["function"]
    )
    assert "project_properties" in {step["operator"] for step in function["steps"]}
    assert episode["observations"][0]["status"] == "completed"
    assert episode["observations"][0]["acquisition_evidence_ids"]
    configured = store.rows(
        "SELECT artifact_id FROM mcp_surfaces WHERE id=?", (episode["surface_id"],)
    )
    source = store.get(configured[0]["artifact_id"])
    assert {query["id"] for query in source["configuration"]["queries"]} == {
        "forecast-details",
        "forecast-maximum",
    }
    assert inference["after"]["reserved_usd"] == construction["before"]["reserved_usd"]

"""Check MCP admission boundaries against genuine retained pilot artifacts.

Counterfactual catalog edits below are explicitly unexecuted negative inputs.
No model output, MCP response, or successful task execution is simulated.
"""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from oak.bootstrap import acquisition_result, function_dataflow, sampled_episode_summary
from oak.service import Service
from oak.store import Store

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

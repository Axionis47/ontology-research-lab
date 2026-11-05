"""Read-only presentation of genuine computations and mandatory replay admission."""

import hashlib
import shutil

from fastapi.testclient import TestClient
from test_historical_replay import replay_chain as replay_chain
from test_selective_evaluation import retained as weather_retained

from oak.api import create_app
from oak.historical_replay import check_candidate_replay
from oak.observer import Observer
from oak.store import Store


def _workspace_fingerprint(store):
    """Detect storage changes while reading, including newly created replay tables."""
    return {
        "tables": store.rows("SELECT name,sql FROM sqlite_master ORDER BY name"),
        "events": store.rows("SELECT * FROM events ORDER BY id"),
        "calls": store.rows("SELECT * FROM model_calls ORDER BY id"),
        "artifacts": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (store.root / "artifacts").glob("*.json")
        },
    }


def test_new_policy_kernel_without_a_bank_is_not_offered_for_inference(tmp_path):
    """A genuine retained kernel cannot bypass the new gate by omitting its bank."""
    store, _, _, original, _ = weather_retained.__wrapped__(tmp_path)
    candidate_id = store.put("mcp_kernel", {**original, "historical_replay_policy": "inherited_v1"})
    before = _workspace_fingerprint(store)
    observer = Observer(store.root)
    kernel = observer.kernel(candidate_id)
    assert kernel["eligible_for_inference"] is False
    assert kernel["validation"]["historical_replay"]["allowed"] is False
    assert "protected historical bank" in kernel["validation"]["historical_replay"]["reason"]
    assert kernel["limitations"]
    assert _workspace_fingerprint(store) == before


def test_authoritative_replay_contracts_are_exposed_without_initializing_storage(tmp_path):
    root = tmp_path / "unopened"
    app = create_app(root)
    schemas = app.openapi()["components"]["schemas"]
    assert {
        "ReplayCase",
        "ReplayBank",
        "ReplayReport",
        "ReplayBankReport",
        "ComparisonContract",
        "AdapterEdge",
        "HistoricalReplayView",
    } <= schemas.keys()
    assert "historical_replay" in schemas["FlowEvidence"]["properties"]
    assert not root.exists()


def test_real_two_edge_replay_and_regression_are_inspectable_without_execution(replay_chain):
    """Use actual Coffee/HermiT replay reports, including the older-case regression."""
    store = replay_chain["store"]
    _, _, candidate_id = replay_chain["kernels"]
    with TestClient(create_app(store.root), base_url="http://127.0.0.1:8501") as client:
        before = _workspace_fingerprint(store)
        response = client.get(f"/api/v1/runs/{replay_chain['run_id']}/events?limit=500")
        assert response.status_code == 200, response.text
        events = [
            event for event in response.json()["items"] if event["stage"] == "historical_replay"
        ]
        assert all(event["type"] == "validation.recorded" for event in events)
        views = {
            event["flow_evidence"]["historical_replay"]["candidate_kernel_id"]: event[
                "flow_evidence"
            ]["historical_replay"]
            for event in events
        }
        preserved = views[candidate_id]
        assert preserved["status"] == "preserved"
        assert preserved["allowed"] is True
        assert preserved["case_count"] == len(replay_chain["case_ids"])
        assert preserved["model_calls"] == preserved["live_mcp_calls"] == 0
        cases = {case["original_case_id"]: case for case in preserved["cases"]}
        earliest = cases[replay_chain["case_ids"][0]]
        assert earliest["adapter_path"] == replay_chain["edges"]
        assert earliest["scope"] == "component"
        assert earliest["assessment_category"] == "execution_succeeded"
        assert cases[replay_chain["case_ids"][1]]["scope"] == "trajectory"
        assert earliest["original_graph_ids"] and earliest["migrated_graph_ids"]

        references = [
            preserved["report_id"],
            preserved["bank_id"],
            earliest["original_case_id"],
            earliest["baseline_execution_id"],
            earliest["candidate_execution_id"],
            *earliest["adapter_path"],
            *earliest["original_graph_ids"],
            *earliest["migrated_graph_ids"],
        ]
        for identity in references:
            artifact = client.get(f"/api/v1/artifacts/{identity}")
            assert artifact.status_code == 200, artifact.text
            actual = artifact.json()
            assert actual["source_sha256"] == identity
            if actual["kind"] in {
                "replay_bank_report",
                "replay_bank",
                "replay_case",
                "adapter_edge",
            }:
                assert actual["typed_data"] is not None

        rejected = views[replay_chain["bad_kernel_id"]]
        assert rejected["status"] == "regressed"
        assert rejected["allowed"] is False
        failure = next(case for case in rejected["cases"] if case["status"] == "regressed")
        assert failure["first_difference"]["repair_target"] == "function"
        assert failure["first_difference"]["expected"] != failure["first_difference"]["actual"]
        assert rejected["feedback"]
        kernel = client.get(f"/api/v1/kernels/{replay_chain['bad_kernel_id']}")
        assert kernel.status_code == 200, kernel.text
        assert kernel.json()["validation"]["historical_replay"]["allowed"] is False
        assert _workspace_fingerprint(store) == before


def test_missing_case_remains_visible_with_unknown_scope_and_origin(replay_chain, tmp_path):
    """Corrupt retained evidence is an explicit visible gap, not an omitted case."""
    root = tmp_path / "missing-case"
    shutil.copytree(replay_chain["store"].root, root)
    store = Store(root)
    case_id = replay_chain["case_ids"][0]
    (root / "artifacts" / f"{case_id}.json").unlink()
    run_id = store.create_run(
        replay_chain["task_id"], "regress", {"purpose": "Actual missing-case replay failure"}
    )
    result = check_candidate_replay(store, replay_chain["kernels"][2], run_id=run_id)
    assert result["allowed"] is False
    assert result["status"] == "unable_to_check"
    before = _workspace_fingerprint(store)
    events = Observer(root).events(run_id, limit=500)["items"]
    event = next(event for event in events if event["stage"] == "historical_replay")
    view = event["flow_evidence"]["historical_replay"]
    case = next(case for case in view["cases"] if case["original_case_id"] == case_id)
    assert case["scope"] == "unknown"
    assert case["origin_kernel_id"] is None
    assert case["status"] == "unable_to_check"
    assert case["first_difference"]["repair_target"] == "verification_gap"
    assert view["omitted_cases"] == 0
    assert _workspace_fingerprint(store) == before

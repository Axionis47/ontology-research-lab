"""Observe actual catalog interactions over the genuine portable weather kernel."""

import hashlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oak.api import create_app
from oak.inference_catalog import EXPAND, INSPECT, SEARCH, InferenceCatalog
from oak.observer import Observer
from oak.store import Store, canonical

FIXTURE = Path(__file__).parent / "fixtures/observer/weather"
EPISODE = "697f6356e475e850faee6abc4ca3b70e520f36df9c2fe1d5f235c0dd2a0b51ea"


def fingerprint(store):
    return {
        "tables": store.rows("SELECT name,sql FROM sqlite_master ORDER BY name"),
        "events": store.rows("SELECT * FROM events ORDER BY id"),
        "calls": store.rows("SELECT * FROM model_calls ORDER BY id"),
        "artifacts": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (store.root / "artifacts").glob("*.json")
        },
    }


@pytest.fixture
def navigation(tmp_path):
    """Persist real component lookups, without presenting them as agent inference."""
    shutil.copytree(FIXTURE, tmp_path / "weather")
    store = Store(tmp_path / "weather")
    episode = store.get(EPISODE)
    kernel_id = episode["kernel_revision"]
    catalog = InferenceCatalog(store.get(kernel_id), kernel_id=kernel_id, page_size=1)
    catalog_ref = store.put("inference_catalog", catalog.manifest())
    run_id = store.create_run(
        episode["surface_id"],
        "mcp_episode",
        {"purpose": "Actual deterministic catalog observation check", "kernel_id": kernel_id},
    )
    state = catalog.initial_state()
    calls = []

    def lookup(tool, args):
        nonlocal state
        state, result = catalog.dispatch(tool, args, state)
        result_ref = store.put("inference_discovery_result", result)
        state_ref = store.put("inference_discovery_state", state)
        event_ref = store.event(
            run_id,
            "inference_discovery",
            result["status"],
            "Actual catalog component lookup",
            {
                "catalog_id": catalog.catalog_id,
                "kernel_id": kernel_id,
                "catalog_ref": catalog_ref,
                "step": len(calls),
                "tool": tool,
                "args": args,
                "result": result,
                "state_ref": state_ref,
                "result_ref": result_ref,
            },
        )
        calls.append(
            {
                "result": result,
                "event_ref": event_ref,
                "state_ref": state_ref,
                "result_ref": result_ref,
            }
        )
        return result

    first = lookup(SEARCH, {"kind": "function"})
    definition_id = first["items"][0]["id"]
    lookup(INSPECT, {"id": definition_id})
    lookup(EXPAND, {"id": definition_id})
    lookup(SEARCH, {"kind": "function", "cursor": "invalid-cursor"})
    view = catalog.prompt(state)
    view_ref = store.put("inference_prompt_view", view)
    context = catalog.context_summary(state, view=view).model_dump(mode="json")
    store.event(
        run_id,
        "inference_context",
        "ok",
        "Actual bounded prompt view",
        {
            **context,
            "catalog_ref": catalog_ref,
            "step": len(calls),
            "view_ref": view_ref,
        },
    )
    with pytest.raises(ValueError) as unavailable:
        catalog.resolve_call("unloaded_tool", state)
    store.event(
        run_id,
        "inference_tool_error",
        "error",
        "Actual unloaded callable rejection",
        {
            "catalog_id": catalog.catalog_id,
            "kernel_id": kernel_id,
            "catalog_ref": catalog_ref,
            "step": len(calls),
            "requested_tool": "unloaded_tool",
            "error": str(unavailable.value),
        },
    )
    return store, run_id, catalog, catalog_ref, calls, view, view_ref, context


def test_catalog_contracts_are_public_without_creating_workspace(tmp_path):
    root = tmp_path / "unopened"
    schemas = create_app(root).openapi()["components"]["schemas"]
    assert {
        "DiscoveryResult",
        "DiscoveryState",
        "DiscoveryContextSummary",
        "InferenceDiscoveryView",
        "InferenceContextView",
    } <= schemas.keys()
    assert not root.exists()


def test_navigation_receipts_are_bounded_and_separate_from_domain_observations(navigation):
    store, run_id, catalog, catalog_ref, calls, view, view_ref, context = navigation
    before = fingerprint(store)
    with TestClient(create_app(store.root), base_url="http://127.0.0.1:8501") as client:
        response = client.get(f"/api/v1/runs/{run_id}/events?limit=500")
        assert response.status_code == 200, response.text
        events = response.json()["items"]
        navigation_events = [event for event in events if event["stage"].startswith("inference_")]
        assert len(navigation_events) == len(calls) + 2
        for event in navigation_events:
            assert event["type"] == "evidence.recorded"
            assert event["flow"] is None
            assert event["flow_evidence"] is None
            assert event["payload"]["context_only"] is True
            assert "result" not in event["payload"]
            refs = {item["id"] for item in event["artifact_refs"]}
            assert catalog_ref in refs
            assert catalog.catalog_id not in refs

        receipts = [
            event["inference_discovery"]
            for event in navigation_events
            if event["inference_discovery"]
        ]
        assert receipts[0]["result_count"] == 1
        assert receipts[0]["total_count"] == 2
        assert receipts[0]["has_more"] is True
        assert receipts[0]["next_cursor"] == calls[0]["result"]["next_cursor"]
        assert receipts[1]["loaded_tool_name"] == calls[1]["result"]["loaded_tool_name"]
        assert receipts[1]["definition_id"] == calls[1]["result"]["definition_id"]
        assert "definition" not in receipts[1]
        assert calls[1]["result"]["definition"] is not None
        assert receipts[2]["result_ids"] == [item["id"] for item in calls[2]["result"]["items"]]
        assert receipts[3]["status"] == "error"
        assert receipts[3]["kind"] == "function"
        assert receipts[3]["error"]

        snapshot_event = next(event for event in events if event["inference_context"])
        snapshot = snapshot_event["inference_context"]
        assert snapshot["view_ref"] == view_ref
        assert snapshot["context"] == context
        assert snapshot["context"]["context_bytes"] == len(canonical(view))
        assert snapshot["context"]["context_bytes"] <= snapshot["context"]["max_context_bytes"]
        assert view_ref in {item["id"] for item in snapshot_event["artifact_refs"]}
        artifact = client.get(f"/api/v1/artifacts/{view_ref}").json()
        assert artifact["source_sha256"] == view_ref
        assert artifact["data"] == view

        for call in calls:
            for ref in (call["event_ref"], call["result_ref"], call["state_ref"]):
                artifact = client.get(f"/api/v1/artifacts/{ref}").json()
                assert artifact["source_sha256"] == ref
                assert artifact["typed_data"] is not None
    assert fingerprint(store) == before


def test_viewer_event_watermark_does_not_discover_or_rebuild_context(navigation):
    store, run_id, _, _, calls, _, _, _ = navigation
    observer = Observer(store.root)
    before = fingerprint(store)
    events = observer.events(run_id, limit=500)["items"]
    inspected = next(
        event
        for event in events
        if event["inference_discovery"] and event["inference_discovery"]["tool"] == INSPECT
    )
    playback = observer.events(run_id, through=inspected["cursor"], limit=500)["items"]
    assert not any(event["inference_context"] for event in playback)
    assert playback[-1]["inference_discovery"]["state_ref"] == calls[1]["state_ref"]
    assert fingerprint(store) == before

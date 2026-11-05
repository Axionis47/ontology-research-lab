"""Observer checks against genuine saved artifacts and actual SQLite reads.

The portable campaign exercises genuine recorded evidence on every checkout.
Additional local saved-run checks skip when the private pilot index is absent.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from oak.observer import Observer, sanitize_public
from oak.store import canonical

ROOT = Path(__file__).resolve().parents[1]
WEATHER_TASK = "mcp:064d950af7a04b3e823a103a6ce8c6b2"
HELSINKI_RUN = "998d8311b79a414993d0337a3908bbff"
WEATHER_CHILD = "f9d723509bcd5f6e64c0f76a8adf809950d702e7eaaf221e5539716e91339c90"
WEATHER_PARENT = "eb54778d20ecbb4041d0d7c7e4d753a24b315cbc35526f29505be8cc4ab1c227"


@pytest.fixture
def observer(tmp_path: Path) -> Observer:
    """Clone genuine index state while retaining immutable artifact sources."""
    database = ROOT / ".local/catalog.sqlite"
    if not database.is_file():
        pytest.skip("Run the genuine pilots before saved observer integration checks")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as original:
        with sqlite3.connect(tmp_path / "catalog.sqlite") as target:
            original.backup(target)
    (tmp_path / "artifacts").symlink_to(ROOT / ".local/artifacts", target_is_directory=True)
    checkpoint = ROOT / ".local/mcp-checkpoints.sqlite"
    if checkpoint.exists():
        with sqlite3.connect(checkpoint.as_uri() + "?mode=ro", uri=True) as original:
            with sqlite3.connect(tmp_path / "mcp-checkpoints.sqlite") as target:
                original.backup(target)
    return Observer(tmp_path)


def test_observer_empty_workspace_does_not_create_files(tmp_path: Path) -> None:
    root = tmp_path / "not-created"
    observer = Observer(root)
    assert observer.tasks()["items"] == []
    assert observer.workspace()["run_count"] == 0
    assert not root.exists()


def test_genuine_generated_flows_remain_separate_and_inspectable(observer: Observer) -> None:
    """Read the actual two-flow campaign without dispatching or assessing a task."""
    task_id = "mcp:a3a582974dc04fae9708af91e612c396"
    inference_id = "8b2d74aac05b4018b6366266d492ac71"
    try:
        run = observer.run(inference_id)
        history = observer.history(task_id)
    except LookupError:
        pytest.skip("The genuine two-flow verification campaign is unavailable")
    before = observer.workspace()
    assert run["outcome"] == "complete"
    assert run["assessment"]["status"] == "not_checked"
    assert observer.graph(run["graph_id"])["total_nodes"] == 2
    assert len(history["attempts"]) == 1  # The campaign wrapper is not another attempt.
    events = observer.events(inference_id, limit=200)["items"]
    for stage in ("evidence_demand", "materialization_plan", "evidence_scope"):
        event = next(item for item in events if item["stage"] == stage)
        assert event["flow"] == "instantiation"
        evidence = observer.artifact(event["artifact_refs"][0]["id"])
        assert evidence["typed_data"] is not None
        assert evidence["data"]["flow"] == "instantiation"
    scope = next(item for item in events if item["stage"] == "evidence_scope")
    assert scope["payload"]["nonblocking"] is True
    assert observer.workspace() == before


def test_real_portable_artifact_hash_is_preserved_and_tampering_fails(tmp_path: Path) -> None:
    fixture = ROOT / "tests/fixtures/weather/mcp-preflight.json"
    source = json.loads(fixture.read_text())
    payload = canonical({"format_version": 1, "kind": "recorded_weather_preflight", "data": source})
    identity = hashlib.sha256(payload).hexdigest()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    path = artifacts / f"{identity}.json"
    path.write_bytes(payload)
    observer = Observer(tmp_path)
    before = path.read_bytes()
    view = observer.artifact(identity)
    assert view["source_sha256"] == identity
    assert view["projection_sha256"] == hashlib.sha256(canonical(view["data"])).hexdigest()
    assert view["data"]["calls"] == source["calls"]
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="identifier"):
        observer.artifact("../catalog.sqlite")
    path.write_bytes(payload + b" ")
    with pytest.raises(ValueError, match="integrity"):
        observer.artifact(identity)


def test_public_projection_redacts_diagnostics_and_credentials_without_erasing_counts() -> None:
    # Deliberate secret-shaped negative inputs test confidentiality, not agent output.
    value = {
        "stderr": "unpublished diagnostic",
        "env_refs": {"CLIENT_SECRET": "PRIVATE_ENV_NAME"},
        "nested": {"access_token": "test-secret", "input_tokens": 42},
        "message": "authorization: Bearer secret-value at /Users/example/private/file.json",
        "provider": {
            "call_id": "redaction-check",
            "model_request_attempted": False,
            "request": {"project": "private-provider-project", "prompt": "private-model-prompt"},
        },
    }
    public, removed = sanitize_public(value)
    rendered = json.dumps(public)
    assert "test-secret" not in rendered and "secret-value" not in rendered
    assert "/Users/example" not in rendered and "unpublished diagnostic" not in rendered
    assert "PRIVATE_ENV_NAME" not in rendered
    assert "private-provider-project" not in rendered and "private-model-prompt" not in rendered
    assert "$.provider.request" in removed
    assert public["nested"]["input_tokens"] == 42
    assert {"$.stderr", "$.env_refs", "$.nested.access_token", "$.message"} <= set(removed)
    assert value["nested"]["access_token"] == "test-secret"


def test_portable_weather_campaign_preserves_provenance_and_actual_replay() -> None:
    """The packaged subset is a documented derivative, never a simulated run."""
    fixture = ROOT / "tests/fixtures/observer/weather"
    manifest = json.loads((fixture / "manifest.json").read_text())
    before = {
        name: hashlib.sha256((fixture / name).read_bytes()).hexdigest()
        for name in manifest["files"]
    }
    assert before == manifest["files"]
    exported = {}
    for source_id, entry in manifest["source_artifacts"].items():
        exported_id = entry["exported_artifact_id"]
        raw = (fixture / "artifacts" / f"{exported_id}.json").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == exported_id
        exported[source_id] = exported_id
        if entry.get("unchanged"):
            assert entry["source_sha256"] == exported_id
        elif "source_artifact_id" in entry:
            assert (
                entry["redacted_fields"]
                or entry["reference_rewrites"]
                or entry.get("portable_schema_artifact_id")
            )
        source_path = ROOT / ".local/artifacts" / f"{source_id}.json"
        if source_path.is_file():
            assert hashlib.sha256(source_path.read_bytes()).hexdigest() == entry["source_sha256"]

    observer = Observer(fixture)
    derived = observer.artifact(exported[WEATHER_CHILD])
    provenance = derived["provenance"]
    assert derived["source_sha256"] == exported[WEATHER_CHILD]
    assert provenance["stored_artifact_id"] == exported[WEATHER_CHILD]
    assert provenance["stored_sha256"] == exported[WEATHER_CHILD]
    origin = next(
        item for item in provenance["origins"] if item["source_artifact_id"] == WEATHER_CHILD
    )
    assert origin["source_sha256"] == WEATHER_CHILD
    assert origin["relationship"] == "sanitized_derivative"
    assert origin["source_bytes_verified"] is False
    assert len(observer.tasks()["items"]) == 1
    run = observer.run(HELSINKI_RUN)
    assert (run["status"], run["outcome"], run["assessment"]["status"]) == (
        "completed",
        "complete",
        "passed",
    )
    assert observer.graph(run["initial_graph_id"])["total_nodes"] == 0
    graph = observer.graph(run["graph_id"])
    assert (graph["total_nodes"], graph["total_edges"]) == (4, 3)
    history = observer.history(WEATHER_TASK)
    rounds = {attempt["round_index"]: attempt for attempt in history["attempts"]}
    assert rounds[0]["status"] == "failed" and rounds[0]["kernel_id"] is None
    assert len(rounds[0]["schema_view"]["nodes"]) == 3
    assert rounds[2]["parent_kernel_id"] == exported[WEATHER_PARENT]
    assert rounds[2]["kernel_id"] == exported[WEATHER_CHILD]
    assert all(case.get("episode_run_id") for case in rounds[2]["case_links"])
    diff = observer.kernel_diff(exported[WEATHER_CHILD], exported[WEATHER_PARENT])
    assert diff["is_parent"] and diff["schema_changed"]
    events = observer.events(HELSINKI_RUN, limit=100)["items"]
    assert len(events) == run["event_count"]
    assert any(item["type"] == "graph.snapshot" for item in events)
    assert before == {
        name: hashlib.sha256((fixture / name).read_bytes()).hexdigest() for name in before
    }


def test_genuine_weather_replay_keeps_outcome_score_graph_and_ledger_distinct(
    observer: Observer,
) -> None:
    try:
        run = observer.run(HELSINKI_RUN)
    except LookupError:
        pytest.skip("The genuine Helsinki episode is unavailable")
    before = observer.workspace()
    assert run["status"] == "completed"
    assert run["outcome"] == "complete"
    assert run["assessment"]["status"] == "passed"
    assert run["assessment"]["evaluator_version"] == "weather-displayed-daily-v1"
    assert run["assessment"]["evidence_refs"]
    assert observer.graph(run["graph_id"])["total_nodes"] == 4
    assert observer.graph(run["graph_id"])["total_edges"] == 3
    if run["initial_graph_id"]:
        assert observer.graph(run["initial_graph_id"])["total_nodes"] == 0

    page = observer.events(HELSINKI_RUN, limit=4)
    watermark = page["through"]
    events = list(page["items"])
    while page["has_more"]:
        page = observer.events(HELSINKI_RUN, after=page["next_cursor"], through=watermark, limit=4)
        events.extend(page["items"])
    assert len(events) == run["event_count"]
    assert len({event["cursor"] for event in events}) == len(events)
    assert [int(event["cursor"]) for event in events] == sorted(
        int(event["cursor"]) for event in events
    )
    assert all("occurred_at" in event and "run_id" in event for event in events)
    snapshot = next(event for event in events if event["stage"] == "graph_snapshot")
    assert snapshot["payload"]["node_count"] == 4
    assert "nodes" not in snapshot["payload"] and "edges" not in snapshot["payload"]
    observation = next(event for event in events if event["stage"] == "observation")
    assert len(observation["payload"]["highlight_node_ids"]) == 2
    assert len(observation["payload"]["steps"]) == 3
    assert (
        observer.events(HELSINKI_RUN, after="0", through=watermark, limit=4)["items"] == events[:4]
    )
    assert observer.workspace() == before


def test_weather_history_retains_failed_attempt_and_real_parent_diff(observer: Observer) -> None:
    try:
        history = observer.history(WEATHER_TASK)
    except LookupError:
        pytest.skip("The genuine weather construction campaign is unavailable")
    rounds = {attempt["round_index"]: attempt for attempt in history["attempts"]}
    assert rounds[0]["status"] == "failed"
    assert rounds[0]["kernel_id"] is None
    assert {case["id"] for case in rounds[0]["case_links"]} == {
        "construction-07",
        "construction-09",
    }
    assert rounds[2]["kernel_id"] == WEATHER_CHILD
    diff = observer.kernel_diff(WEATHER_CHILD, WEATHER_PARENT)
    assert diff["is_parent"] and diff["schema_changed"] and diff["functions_changed"]
    city = next(
        item
        for item in diff["changes"]
        if item["path"] == "/schema/entity_types/Location/properties/city_name/required"
    )
    assert city["before"] is True and city["after"] is False
    child = observer.kernel(WEATHER_CHILD)
    assert child["eligible_for_inference"]
    assert child["assessment"]["status"] == "not_checked"


def test_legacy_coffee_graph_is_available_from_start_without_invented_edges(
    observer: Observer,
) -> None:
    identity = "0c7e58d98071595d62bb8f8276de18b96fbb6c76e520c3344e305ef46d95a431"
    try:
        kernel = observer.kernel(identity)
    except LookupError:
        pytest.skip("The genuine Coffee kernel is unavailable")
    graph = observer.graph(identity, limit=3)
    assert graph["total_nodes"] == 5746 and graph["total_edges"] == 0
    assert graph["shown_nodes"] == 3 and graph["omitted_nodes"] == 5743
    assert graph["edges"] == []
    assert kernel["eligible_for_inference"] is False
    assert kernel["task_id"].startswith("corpus:")
    history = observer.history(kernel["task_id"])
    assert history["attempts"]
    before = observer.run("4406240ec1f14f8aa83578fee983696c")
    assert before["initial_graph_id"] == identity
    construction = observer.run("3e01ffff6cec418cb0548a68bdabab11")
    assert construction["initial_graph_id"] is None
    with pytest.raises(ValueError, match="Graph limit"):
        observer.graph(identity, limit=0)

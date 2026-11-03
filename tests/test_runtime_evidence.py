"""Exercise real saved USGS revisions, source receipts, and promotion gates.

The local acceptance pilot must run first. Every model response and status in
these tests comes from that pilot. Database copies isolate deliberate history
changes. No model callback, network response, or successful agent answer is faked.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from oak.regression import replay_recorded_calls
from oak.service import Service, corpus_documents

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def recorded_workspace(tmp_path_factory):
    manifest_path = ROOT / ".local/pilots/usgs.json"
    if not manifest_path.exists():
        pytest.skip("Run the genuine USGS acceptance pilot before saved-runtime checks")
    manifest = json.loads(manifest_path.read_text())
    if not manifest.get("candidate_revision"):
        pytest.skip("The genuine USGS pilot has not saved its scope-expansion revision")
    target = tmp_path_factory.mktemp("actual-usgs-evidence")
    with sqlite3.connect(f"file:{ROOT / '.local/catalog.sqlite'}?mode=ro", uri=True) as source:
        with sqlite3.connect(target / "catalog.sqlite") as destination:
            source.backup(destination)
    # Content-addressed artifacts are immutable and published before their index
    # entries, so a database snapshot plus these saved files is a coherent view.
    shutil.copytree(ROOT / ".local/artifacts", target / "artifacts")
    return target, manifest


@pytest.fixture
def evidence(recorded_workspace, tmp_path):
    saved, manifest = recorded_workspace
    shutil.copy2(saved / "catalog.sqlite", tmp_path / "catalog.sqlite")
    shutil.copytree(saved / "artifacts", tmp_path / "artifacts")
    service = Service(tmp_path)
    candidate = service.revision(manifest["task_id"], manifest["candidate_revision"])
    parent = service.revision(manifest["task_id"], candidate["parent"])
    return service, manifest, parent, candidate


def test_saved_graphs_retain_every_actual_source_record(evidence) -> None:
    service, _, parent, candidate = evidence
    assert parent["corpus_id"] == candidate["corpus_id"]
    documents = corpus_documents(service.artifact(parent["corpus_id"]))
    by_document = {document["document_id"]: document for document in documents}
    assert len(documents) > 1
    for revision in (parent, candidate):
        graph = revision["graph"]
        assert graph["source_document_count"] == len(documents)
        assert graph["ignored_documents"] == []
        actual_sources = {
            source["document_id"]
            for record in graph["nodes"] + graph["edges"]
            for source in record["sources"]
        }
        assert actual_sources == set(by_document)
        for node in graph["nodes"]:
            source = by_document[node["sources"][0]["document_id"]]["record"]
            if node["type"] == "EarthquakeEvent":
                primary_key = revision["schema"]["entity_types"][node["type"]]["primary_key"]
                assert node["properties"][primary_key] == source["id"]
                magnitude_key = "mag" if "mag" in node["properties"] else "magnitude"
                assert node["properties"][magnitude_key] == source["properties"]["mag"]
            if "place" in node["properties"]:
                assert node["properties"]["place"] == source["properties"]["place"]
            if "depth_km" in node["properties"]:
                assert node["properties"]["depth_km"] == source["geometry"]["coordinates"][2]
    assert all("depth_km" in node["properties"] for node in candidate["graph"]["nodes"])


def test_service_replays_original_construction_calls_without_model_use(evidence) -> None:
    service, manifest, parent, candidate = evidence
    # Establish the actual compatibility path before calling a service that can
    # propose an adapter for other candidates. This pair requires no model work.
    assert parent["corpus_id"] == candidate["corpus_id"]
    assert replay_recorded_calls(parent, candidate)["status"] == "passed"
    model_calls_before = service.store.rows("SELECT id FROM model_calls ORDER BY id")
    report = service.regression(manifest["task_id"], candidate)
    assert service.store.rows("SELECT id FROM model_calls ORDER BY id") == model_calls_before
    assert report["status"] == "passed"
    assert report["adapter"] is None
    assert report["fresh_agent_success"] == "unverified"
    checks = [check for group in report["reports"] for check in group["checks"]]
    construction = [check for check in checks if check["origin"] == "parent_construction"]
    assert len(construction) == len(parent["assessment"]["construction_results"])
    assert construction and all(check["executed_calls"] > 0 for check in construction)
    for check in construction:
        for call in check["calls"]:
            assert (
                call["new_dependencies"]["graph_sha256"]
                == hashlib.sha256(
                    json.dumps(candidate["graph"], sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
            )
            assert call["adapted_value"] == call["old_value"]


def test_actual_promoted_revision_cannot_be_promoted_again(evidence) -> None:
    service, manifest, _, candidate = evidence
    assert service.task(manifest["task_id"])["active_revision"] == candidate["id"]
    check = service.promotion_check(manifest["task_id"], candidate["id"])
    assert check["allowed"] is False
    assert "already active" in check["reason"]
    with pytest.raises(ValueError, match="already active"):
        service.promote(manifest["task_id"], candidate["id"])


def test_actual_saved_evidence_allows_promotion_and_retains_parent(evidence) -> None:
    service, manifest, parent, candidate = evidence
    task_id = manifest["task_id"]
    parent_bytes = (service.root / "artifacts" / f"{parent['id']}.json").read_bytes()
    # Restore only the active pointer in an isolated copy to exercise the genuine
    # pre-promotion gate. No revision, answer, run status, or validation is invented.
    with service.store.connect() as connection:
        connection.execute("UPDATE tasks SET active_revision=? WHERE id=?", (parent["id"], task_id))
    check = service.promotion_check(task_id, candidate["id"])
    assert check["allowed"] is True
    service.promote(task_id, candidate["id"])
    assert service.task(task_id)["active_revision"] == candidate["id"]
    assert (service.root / "artifacts" / f"{parent['id']}.json").read_bytes() == parent_bytes
    assert service.revision(task_id, parent["id"])["id"] == parent["id"]


def test_missing_replay_evidence_blocks_even_an_actually_validated_candidate(evidence) -> None:
    service, manifest, parent, candidate = evidence
    with service.store.connect() as connection:
        connection.execute(
            "UPDATE tasks SET active_revision=? WHERE id=?", (parent["id"], manifest["task_id"])
        )
        connection.execute("DELETE FROM events WHERE stage='regression'")
    check = service.promotion_check(manifest["task_id"], candidate["id"])
    assert check["allowed"] is False
    assert "needs recorded-call regression" in check["reason"]


def test_actual_incomplete_capture_cannot_create_task(tmp_path) -> None:
    snapshots = [
        json.loads(path.read_text())
        for path in sorted((ROOT / ".local/verification/corpus").glob("*.json"))
    ]
    incomplete = next((item for item in snapshots if item.get("status") == "incomplete"), None)
    if incomplete is None:
        pytest.skip("Run the genuine USGS truncation acquisition check first")
    service = Service(tmp_path)
    with pytest.raises(ValueError, match="complete request coverage"):
        service.create_task(
            "Truncated real capture",
            "Count the earthquakes in the specified source interval.",
            incomplete,
            ["How many earthquakes are in the source interval?"],
        )
    assert service.tasks() == []
    assert service.store.rows("SELECT id FROM model_calls") == []


def test_reference_labels_stay_bound_to_their_actual_corpus(evidence) -> None:
    service, manifest, _, candidate = evidence
    task = service.task(manifest["task_id"])
    for run in service.runs(manifest["task_id"]):
        inputs = service.artifact(run["input_id"])
        if inputs.get("references"):
            assert inputs["corpus_id"] == task["reference_corpus_id"]
    assert candidate["assessment"]["heldout_accuracy"] == "unmeasured"
    # The genuine depth check is a fresh answer receipt. It is not relabelled as
    # construction accuracy and does not enter the parent revision's replay set.
    old_receipts = service._regression_receipts(manifest["task_id"], candidate["parent"])
    assert all(item["result"]["kernel_revision"] == candidate["parent"] for item in old_receipts)
    assert all(item["result"]["status"] == "answered" for item in old_receipts)

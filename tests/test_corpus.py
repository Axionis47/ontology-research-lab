"""Exercise corpus parsing and actual public API acquisition, without HTTP mocks."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
from pathlib import Path

import pytest

from oak.corpus import fetch_usgs, load_local_corpus, normalize_snapshot

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "tests/fixtures/ontology/manifest.json"


def test_supplied_json_preserves_genuine_source_manifest() -> None:
    snapshot = load_local_corpus(SOURCE_MANIFEST, source_id="oak:ontology-fixture-manifest")
    documents = normalize_snapshot(snapshot)
    assert snapshot["status"] == "ready"
    assert base64.b64decode(snapshot["raw_payload_base64"]) == SOURCE_MANIFEST.read_bytes()
    assert len(documents) == 1
    assert documents[0]["record"] == json.loads(SOURCE_MANIFEST.read_text())
    assert documents[0]["source_id"] == "oak:ontology-fixture-manifest"
    assert documents[0]["snapshot_id"] == snapshot["snapshot_id"]


def test_supplied_text_retains_real_project_readme() -> None:
    source = ROOT / "README.md"
    snapshot = load_local_corpus(source)
    documents = normalize_snapshot(snapshot)
    assert len(documents) == 1
    assert documents[0]["text"] == source.read_bytes().decode("utf-8")
    assert documents[0]["content_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_csv_and_jsonl_preserve_actual_source_records(tmp_path: Path) -> None:
    records = list(json.loads(SOURCE_MANIFEST.read_text())["files"].values())
    csv_path = tmp_path / "source-files.csv"
    with csv_path.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    csv_documents = normalize_snapshot(load_local_corpus(csv_path))
    assert [item["record"]["sha256"] for item in csv_documents] == [
        row["sha256"] for row in records
    ]
    assert [item["locator"] for item in csv_documents] == ["row:1", "row:2"]

    jsonl_path = tmp_path / "source-files.jsonl"
    jsonl_path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    jsonl_documents = normalize_snapshot(load_local_corpus(jsonl_path))
    assert [item["record"] for item in jsonl_documents] == records


def test_modified_actual_snapshot_is_rejected() -> None:
    snapshot = load_local_corpus(SOURCE_MANIFEST)
    snapshot["raw_payload_base64"] = base64.b64encode(SOURCE_MANIFEST.read_bytes() + b" ").decode()
    with pytest.raises(ValueError, match="digest mismatch"):
        normalize_snapshot(snapshot)


def test_invalid_interval_is_rejected_before_acquisition() -> None:
    with pytest.raises(ValueError, match="endtime"):
        fetch_usgs("2025-01-01T00:00:00.1Z", "2025-01-01T00:00:00Z")


@pytest.fixture(scope="module")
def live_snapshot() -> dict:
    if os.environ.get("OAK_LIVE_TESTS") != "1":
        pytest.skip("Set OAK_LIVE_TESTS=1 to call the actual public USGS API")
    snapshot = fetch_usgs("2025-01-01", "2025-01-02", minmagnitude=5)
    directory = ROOT / ".local/verification/corpus"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{snapshot['snapshot_id']}.json").write_text(
        json.dumps(snapshot, indent=2) + "\n"
    )
    assert snapshot["status"] == "ready", snapshot["error"]
    return snapshot


def test_live_usgs_bytes_scope_and_record_provenance(live_snapshot: dict) -> None:
    assert live_snapshot["http_status"] == 200
    payload = base64.b64decode(live_snapshot["raw_payload_base64"])
    assert hashlib.sha256(payload).hexdigest() == live_snapshot["raw_sha256"]
    raw = json.loads(payload)
    documents = normalize_snapshot(live_snapshot)
    assert 0 < len(documents) <= 100
    assert len(documents) == len(raw["features"])
    assert live_snapshot["coverage"]["complete_for_request"]
    for document, feature in zip(documents, raw["features"], strict=True):
        assert document["record"] == feature
        assert document["source_id"] == f"usgs:{feature['id']}"
        assert document["snapshot_id"] == live_snapshot["snapshot_id"]
        assert "depth kilometres" in document["text"]
        assert feature["properties"]["mag"] >= 5


def test_live_api_limit_cannot_be_mistaken_for_complete_corpus(live_snapshot: dict) -> None:
    assert live_snapshot["coverage"]["records_returned"] > 1
    limited = fetch_usgs("2025-01-01", "2025-01-02", minmagnitude=5, max_records=1)
    directory = ROOT / ".local/verification/corpus"
    (directory / f"{limited['snapshot_id']}.json").write_text(json.dumps(limited, indent=2) + "\n")
    assert limited["status"] == "incomplete", limited["error"]
    assert not limited["coverage"]["complete_for_request"]
    assert limited["coverage"]["records_returned"] == 2
    with pytest.raises(ValueError, match="complete request coverage"):
        normalize_snapshot(limited)

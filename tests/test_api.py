"""Exercise the actual HTTP application and genuine saved evidence, without mocks."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oak.api import create_app

ROOT = Path(__file__).resolve().parents[1]
HELSINKI_RUN = "998d8311b79a414993d0337a3908bbff"


def test_openapi_generation_does_not_initialize_storage(tmp_path):
    root = tmp_path / "unopened"
    schema = create_app(root).openapi()
    assert not root.exists()
    assert "/api/v1/runs/{identity}/stream" in schema["paths"]
    envelope = schema["components"]["schemas"]["EventEnvelope"]
    assert envelope["properties"]["cursor"]["type"] == "string"
    assert {"task_id", "run_id", "root_run_id", "parent_run_id", "occurred_at"} <= envelope[
        "properties"
    ].keys()
    assert "Replay" not in json.dumps(schema)
    assert {
        "TaskIR",
        "CandidateSelection",
        "EvidenceDemand",
        "MaterializationPlan",
        "CoverageReceipt",
        "SufficiencyResult",
        "VerificationReport",
        "PreservationCertificate",
    } <= schema["components"]["schemas"].keys()
    assert "flow" in envelope["properties"]


def test_empty_workspace_and_security_do_not_execute(tmp_path):
    with TestClient(
        create_app(tmp_path), base_url="http://127.0.0.1:8501", raise_server_exceptions=False
    ) as client:
        workspace = client.get("/api/v1/workspace")
        assert workspace.status_code == 200, workspace.text
        data = workspace.json()
        assert data["budget"]["calls"] == 0
        assert client.get("/api/v1/tasks").json()["items"] == []
        assert client.get("/api/v1/workspace").json()["session_token"] == data["session_token"]
        for headers in (
            {},
            {"X-Oak-Session": "wrong"},
            {"X-Oak-Session": data["session_token"], "Origin": "https://example.org"},
        ):
            denied = client.post("/api/v1/connector-discoveries", json={}, headers=headers)
            assert denied.status_code == 403
            assert set(denied.json()) >= {"code", "message", "retryable"}
        assert (
            client.get("/api/v1/workspace", headers={"Host": "attacker.example"}).status_code == 403
        )
        invalid = client.post(
            "/api/v1/tasks", json={"root": "/tmp"}, headers={"X-Oak-Session": data["session_token"]}
        )
        assert invalid.status_code == 422
        assert client.get("/api/v1/not-a-route").status_code == 404
        assert client.get("/api/v1/workspace").json()["budget"]["calls"] == 0
    with sqlite3.connect(tmp_path / "catalog.sqlite") as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0


@pytest.fixture
def saved_workspace(tmp_path):
    source_root = ROOT / ".local"
    original = source_root / "catalog.sqlite"
    available = False
    if original.is_file():
        with sqlite3.connect(original.as_uri() + "?mode=ro", uri=True) as source:
            available = bool(
                source.execute("SELECT id FROM runs WHERE id=?", (HELSINKI_RUN,)).fetchone()
            )
    if not available:
        source_root = ROOT / "tests/fixtures/observer/weather"
        original = source_root / "catalog.sqlite"
    with sqlite3.connect(f"file:{original}?mode=ro", uri=True) as source:
        assert source.execute("SELECT id FROM runs WHERE id=?", (HELSINKI_RUN,)).fetchone()
        with sqlite3.connect(tmp_path / "catalog.sqlite") as target:
            source.backup(target)
    if source_root == ROOT / ".local":
        (tmp_path / "artifacts").symlink_to(source_root / "artifacts", target_is_directory=True)
    else:
        shutil.copytree(source_root / "artifacts", tmp_path / "artifacts")
        shutil.copyfile(source_root / "manifest.json", tmp_path / "manifest.json")
    checkpoint = source_root / "mcp-checkpoints.sqlite"
    if checkpoint.is_file():
        with sqlite3.connect(checkpoint.as_uri() + "?mode=ro", uri=True) as source:
            with sqlite3.connect(tmp_path / "mcp-checkpoints.sqlite") as target:
                source.backup(target)
    return tmp_path


def test_real_history_sse_resume_and_reads_leave_execution_unchanged(saved_workspace):
    with TestClient(
        create_app(saved_workspace), base_url="http://127.0.0.1:8501", raise_server_exceptions=False
    ) as client:
        before = client.get("/api/v1/workspace").json()
        detail = client.get(f"/api/v1/runs/{HELSINKI_RUN}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["answer"] == "2"
        assert detail.json()["outcome"] == "complete"
        assert detail.json()["assessment"]["status"] == "passed"
        page = client.get(f"/api/v1/runs/{HELSINKI_RUN}/events?limit=500").json()
        assert page["items"]
        stream = client.get(f"/api/v1/runs/{HELSINKI_RUN}/stream")
        assert stream.status_code == 200, stream.text
        streamed = [
            json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith("data: ")
        ]
        assert streamed == page["items"]
        cursor = streamed[len(streamed) // 2]["cursor"]
        resumed = client.get(
            f"/api/v1/runs/{HELSINKI_RUN}/stream", headers={"Last-Event-ID": cursor}
        )
        later = [
            json.loads(line[6:]) for line in resumed.text.splitlines() if line.startswith("data: ")
        ]
        assert later == [event for event in streamed if int(event["cursor"]) > int(cursor)]
        pinned = client.get(f"/api/v1/runs/{HELSINKI_RUN}/events?through={cursor}").json()
        assert all(int(event["cursor"]) <= int(cursor) for event in pinned["items"])
        after = client.get("/api/v1/workspace").json()
        assert after["run_count"] == before["run_count"]
        assert after["budget"] == before["budget"]

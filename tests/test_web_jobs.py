"""Actual storage/process checks for the local UI boundary, without model calls.

Negative connection inputs exercise genuine OS failures. No MCP provider or
model result is replaced. Historical-kernel checks inspect real saved evidence.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from oak.mcp_bridge import ConnectionConfig, MCPBridge
from oak.service import Service
from oak.store import Store, now
from oak.task_context import InferenceQuery, TaskSurface, build_runtime_context, sample_construction
from oak.web_jobs import WebJobError, WebJobs, _process_identity

PROJECT = Path(__file__).resolve().parents[1]


def test_additive_migration_backs_up_real_legacy_index_once(tmp_path: Path) -> None:
    """An actual pre-migration SQLite index and its request remain readable."""
    original = tmp_path / "catalog.sqlite"
    source = (PROJECT / "README.md").read_text()
    with sqlite3.connect(original) as connection:
        connection.execute(
            "CREATE TABLE runs(id TEXT PRIMARY KEY, task_id TEXT, kind TEXT, status TEXT, created_at TEXT, input_id TEXT, result_id TEXT, error TEXT)"
        )
        connection.execute("CREATE TABLE retained_source(text TEXT)")
        connection.execute("INSERT INTO retained_source VALUES(?)", (source,))
        connection.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)",
            (
                "inspection-request",
                "source-audit",
                "audit",
                "queued",
                now(),
                "unexecuted-source-request",
                None,
                None,
            ),
        )
    store = Store(tmp_path)
    backups = list((tmp_path / "backups").glob("*.sqlite"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute("SELECT text FROM retained_source").fetchone()[0] == source
        assert "owner_kind" not in {row[1] for row in connection.execute("PRAGMA table_info(runs)")}
    assert store.rows("SELECT owner_kind,root_run_id FROM runs")[0] == {
        "owner_kind": None,
        "root_run_id": None,
    }
    Store(tmp_path)
    assert list((tmp_path / "backups").glob("*.sqlite")) == backups


def test_lifecycle_result_and_event_are_in_one_sqlite_snapshot(tmp_path: Path) -> None:
    store = Store(tmp_path)
    run_id = store.create_run("source-audit", "inspection", {"source": str(PROJECT / "README.md")})
    store.set_run(run_id, "running")
    result = {"source_bytes": (PROJECT / "README.md").stat().st_size}
    store.set_run(run_id, "completed", result=result)
    with store.connect() as connection:
        connection.execute("BEGIN")
        row = connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        event = connection.execute(
            "SELECT * FROM events WHERE run_id=? AND stage='lifecycle' ORDER BY id DESC", (run_id,)
        ).fetchone()
        assert row["status"] == event["status"] == "completed"
        payload = store.get(event["artifact_id"])
        assert payload["result_id"] == row["result_id"]
        assert payload["previous_status"] == "running"
        assert store.get(row["result_id"]) == result
    count = len(store.rows("SELECT id FROM events"))
    store.set_run(run_id, "completed", result=result)
    assert len(store.rows("SELECT id FROM events")) == count


def test_failed_event_insert_rolls_back_terminal_status(tmp_path: Path) -> None:
    """A real SQLite rejection cannot leave a terminal row without its event."""
    store = Store(tmp_path)
    run_id = store.create_run("source-audit", "inspection", {})
    with store.connect() as connection:
        connection.execute(
            "CREATE TRIGGER reject_lifecycle BEFORE INSERT ON events WHEN NEW.stage='lifecycle' BEGIN SELECT RAISE(ABORT,'negative transaction control'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="negative transaction control"):
        store.set_run(
            run_id, "completed", result={"source_bytes": (PROJECT / "README.md").stat().st_size}
        )
    row = store.rows("SELECT status,result_id FROM runs WHERE id=?", (run_id,))[0]
    assert row == {"status": "queued", "result_id": None}
    assert not store.rows("SELECT id FROM events WHERE stage='lifecycle'")


def test_service_reconciliation_does_not_claim_inline_mcp_children(tmp_path: Path) -> None:
    service = Service(tmp_path)
    root = service.store.create_run(
        "mcp-scope", "mcp_construct", {"purpose": "ownership validation"}, owner_kind="web"
    )
    child = service.store.create_run(
        "mcp-scope", "mcp_episode", {"purpose": "ownership validation"}, parent_run_id=root
    )
    service._reconcile_jobs("mcp-scope")
    rows = {row["id"]: row for row in service.store.rows("SELECT * FROM runs")}
    assert rows[root]["status"] == rows[child]["status"] == "queued"
    assert rows[child]["root_run_id"] == rows[child]["owner_run_id"] == root
    assert rows[child]["parent_run_id"] == root
    assert rows[child]["owner_kind"] == "child"


def _wait_terminal(jobs: WebJobs, identity: str, timeout: float = 10) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = jobs.discovery(identity)
        if state["status"] not in {"queued", "running"}:
            return state
        time.sleep(0.05)
    pytest.fail("Actual discovery worker did not finish within its bound")


def test_discovery_worker_records_real_missing_executable_and_deduplicates(tmp_path: Path) -> None:
    jobs = WebJobs(tmp_path)
    connection = {
        "name": "missing",
        "transport": "stdio",
        "command": str(tmp_path / "does-not-exist"),
        "timeout_seconds": 1.0,
    }
    first = jobs.discover(connection, "actual-missing-executable")
    repeated = jobs.discover(connection, "actual-missing-executable")
    assert repeated["run_id"] == first["run_id"] and repeated["reused"]
    finished = _wait_terminal(jobs, first["run_id"])
    assert finished["status"] == "failed"
    assert finished["connection"]["command"] == connection["command"]
    assert finished["artifact_refs"]
    events = jobs.store.rows("SELECT * FROM events WHERE run_id=?", (first["run_id"],))
    assert any(
        event["stage"] == "mcp_discovery" and event["status"] == "failed" for event in events
    )
    assert any(event["stage"] == "lifecycle" and event["status"] == "failed" for event in events)
    assert jobs.store.rows("SELECT id FROM model_calls") == []
    assert jobs.discover(connection, "actual-missing-executable")["run_id"] == first["run_id"]
    with pytest.raises(WebJobError) as mismatch:
        jobs.discover({**connection, "timeout_seconds": 2.0}, "actual-missing-executable")
    assert mismatch.value.code == "idempotency_conflict"
    with pytest.raises(ValueError, match="finish successfully"):
        jobs.save_connector(first["run_id"], ["unavailable"])


def test_discovery_only_bridge_cannot_invoke_even_with_valid_tool_shape(tmp_path: Path) -> None:
    store = Store(tmp_path)
    run_id = store.create_run("source-audit", "discovery_guard", {})
    connection = ConnectionConfig(name="not_connected", transport="stdio", command=sys.executable)
    bridge = MCPBridge([connection], store, run_id, discovery_only=True)
    result = bridge.invoke("not_connected/anything", {})
    assert result["status"] == "failed" and result["tool_call_attempted"] is False
    assert "Discovery-only" in result["error"]["message"]


def test_run_local_inference_does_not_change_curated_pool() -> None:
    surface = TaskSurface.model_validate(
        json.loads((PROJECT / "config/weather-surface.json").read_text())
    )
    original = surface.model_dump(mode="json")
    sample = sample_construction(surface, 0)
    query = InferenceQuery(
        id="run-local-inspection",
        query="Which source observations are available?",
        requirements=["Cite actual observations."],
    )
    context = build_runtime_context(surface, query, [])
    assert context["query"] == query.query and context["requirements"] == query.requirements
    assert surface.model_dump(mode="json") == original
    assert sample_construction(surface, 0) == sample
    with pytest.raises(ValidationError):
        TaskSurface.model_validate({**original, "queries": [query]})


def test_real_exited_process_marks_its_saved_children_interrupted(tmp_path: Path) -> None:
    jobs = WebJobs(tmp_path)
    root = jobs.store.create_run("ownership-audit", "mcp_construct", {}, owner_kind="web")
    child = jobs.store.create_run("ownership-audit", "mcp_episode", {}, parent_run_id=root)
    with subprocess.Popen(
        [sys.executable, "-c", "print('exited')"], stdout=subprocess.PIPE, text=True
    ) as process:
        started = _process_identity(process.pid)
        with jobs.store.connect() as connection:
            connection.execute(
                "INSERT INTO web_jobs VALUES(?,?,?,?,?,?,?)",
                (
                    root,
                    "construct",
                    "actual-exited-process",
                    "ownership-check",
                    "not-an-execution-token",
                    process.pid,
                    started,
                ),
            )
        assert process.stdout is not None and process.stdout.read().strip() == "exited"
        time.sleep(0.05)
        changed = jobs.reconcile()
    assert {row["run_id"] for row in changed} == {root, child}
    assert all(row["status"] == "interrupted" for row in jobs.store.rows("SELECT status FROM runs"))
    assert jobs.store.rows("SELECT id FROM model_calls") == []


def test_saved_real_weather_kernel_passes_existing_gates_without_model_calls() -> None:
    root = PROJECT / ".local"
    identity = "f9d723509bcd5f6e64c0f76a8adf809950d702e7eaaf221e5539716e91339c90"
    if not (root / "artifacts" / f"{identity}.json").is_file():
        pytest.skip("Actual historical weather kernel is unavailable")
    jobs = WebJobs(root)
    before = jobs.store.budget()["calls"]
    kernel = jobs.store.get(identity)
    assert jobs._kernel(identity, kernel["surface_id"])["kind"] == "mcp_kernel"
    assert jobs.store.budget()["calls"] == before


def test_inference_worker_records_missing_real_kernel_without_model_calls(tmp_path: Path) -> None:
    """An incomplete saved request fails before inference and preserves its local query.

    Copy only the genuine historical surface, deliberately leaving its real
    kernel absent. This is invalid execution input, never a replacement answer.
    """
    source = PROJECT / ".local"
    identity = "f9d723509bcd5f6e64c0f76a8adf809950d702e7eaaf221e5539716e91339c90"
    if not (source / "artifacts" / f"{identity}.json").is_file():
        pytest.skip("Actual historical weather kernel is unavailable")
    original = Store(source)
    kernel = original.get(identity)
    surface_row = original.rows("SELECT * FROM mcp_surfaces WHERE id=?", (kernel["surface_id"],))[0]
    surface = original.get(surface_row["artifact_id"])
    jobs = WebJobs(tmp_path)
    surface_id = jobs.store.put("mcp_surface", surface)
    with jobs.store.connect() as connection:
        connection.execute(
            "INSERT INTO mcp_surfaces VALUES(?,?)", (kernel["surface_id"], surface_id)
        )
    query = InferenceQuery(
        id="run-local-evidence-check",
        query="Which acquired forecast observations support this answer?",
    )
    # Public submission correctly rejects the absent evidence before dispatch.
    with pytest.raises(WebJobError) as rejected:
        jobs.submit(
            kernel["surface_id"], "infer", "reject-missing", kernel_id=identity, query=query.query
        )
    assert rejected.value.code == "artifact_missing"
    assert jobs.store.rows("SELECT id FROM runs") == []
    # The worker must also fail safely if evidence disappears after acceptance.
    accepted = jobs._enqueue(
        kernel["surface_id"],
        "infer",
        {
            "surface_id": kernel["surface_id"],
            "operation": "infer",
            "kernel_id": identity,
            "inference_query": query.model_dump(mode="json"),
        },
        "missing-after-acceptance",
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        row = jobs.store.rows("SELECT * FROM runs WHERE id=?", (accepted["run_id"],))[0]
        if row["status"] not in {"queued", "running"}:
            break
        time.sleep(0.05)
    assert row["status"] == "failed"
    events = jobs.store.rows("SELECT * FROM events WHERE run_id=? ORDER BY id", (row["id"],))
    assert events[-1]["stage"] == "lifecycle" and events[-1]["status"] == "failed"
    error = next(event for event in events if event["stage"] == "worker_error")
    assert jobs.store.get(error["artifact_id"])["code"] == "artifact_missing"
    assert jobs.store.get(row["input_id"])["inference_query"]["split"] == "inference"
    assert jobs.store.get(surface_id) == surface
    assert jobs.store.rows("SELECT id FROM model_calls") == []


def test_running_process_lease_survives_reconciliation_and_readers(tmp_path: Path) -> None:
    """An actual independent process owns the lease; readers cannot restart it."""
    jobs = WebJobs(tmp_path)
    run_id = jobs.store.create_run("lease-audit", "mcp_construct", {}, owner_kind="web")
    directory = tmp_path / "web-jobs"
    directory.mkdir()
    program = "import fcntl,sys; f=open(sys.argv[1],'a'); fcntl.flock(f,fcntl.LOCK_EX); print('owned',flush=True); sys.stdin.readline()"
    with subprocess.Popen(
        [sys.executable, "-c", program, str(directory / f"{run_id}.lock")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    ) as process:
        assert process.stdout is not None and process.stdout.readline().strip() == "owned"
        with jobs.store.connect() as connection:
            connection.execute(
                "INSERT INTO web_jobs VALUES(?,?,?,?,?,?,?)",
                (
                    run_id,
                    "construct",
                    "real-live-lease",
                    "ownership-check",
                    "not-an-execution-token",
                    process.pid,
                    _process_identity(process.pid),
                ),
            )
        jobs.store.set_run(run_id, "running")
        before = jobs.store.rows("SELECT id FROM events")
        assert jobs.reconcile() == []
        assert jobs.connectors() == []
        assert Service(tmp_path).runs("lease-audit")[0]["status"] == "running"
        assert jobs.store.rows("SELECT id FROM events") == before
        assert process.stdin is not None
        process.stdin.write("finish\n")
        process.stdin.flush()
        process.wait(timeout=5)
    assert jobs.reconcile() == [{"run_id": run_id, "status": "interrupted"}]

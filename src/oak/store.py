"""Immutable evidence objects and a small transactional index for local runs."""

from __future__ import annotations

import fcntl
import hashlib
import json
import re
import sqlite3
import subprocess
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(UTC).isoformat()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def implementation_receipt() -> dict:
    """Pin executable source and dependency locks without copying credentials or data."""
    project = Path(__file__).resolve().parents[2]
    paths = sorted((project / "src/oak").rglob("*.py"))
    paths += [project / name for name in ("uv.lock", "package-lock.json", "config/runtime.json")]
    hashes = {
        str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
        if path.is_file()
    }
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = None
    return {
        "git_commit": commit,
        "source_and_lock_sha256": hashes,
        "meaning": "Files present when the run was created; hashes identify uncommitted changes too",
    }


class Store:
    """Content-addressed JSON artifacts with durable task/run/revision indexes.

    SQLite is the local single-user index. Artifact files are immutable and
    verified on read. LangGraph checkpoints live in their own database.
    """

    def __init__(self, root: str | Path = ".local"):
        self.root = Path(root).resolve()
        (self.root / "artifacts").mkdir(parents=True, exist_ok=True)
        self._migrate()

    def _migrate(self) -> None:
        """Back up an existing index before one additive, serialized migration.

        The SQLite backup API includes committed WAL data. Immutable artifacts
        and LangGraph checkpoints are neither rewritten nor copied. Legacy run
        lineage remains unknown; it is not inferred from timestamps.
        """
        with (self.root / "schema.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.connect() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version > 1:
                    raise ValueError("Catalog was created by a newer schema version")
                if version == 1:
                    return
                existing = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
                ).fetchone()
                if existing:
                    directory = self.root / "backups"
                    directory.mkdir(exist_ok=True)
                    backup = directory / f"catalog-v0-{uuid.uuid4().hex}.sqlite"
                    with sqlite3.connect(backup) as target:
                        connection.backup(target)
                connection.executescript("""
                CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, data TEXT NOT NULL, active_revision TEXT);
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, task_id TEXT NOT NULL, kind TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, input_id TEXT NOT NULL, result_id TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    parent TEXT, created_at TEXT NOT NULL, status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT,
                    time TEXT NOT NULL, stage TEXT NOT NULL, status TEXT NOT NULL, summary TEXT NOT NULL, artifact_id TEXT);
                CREATE TABLE IF NOT EXISTS model_calls(id TEXT PRIMARY KEY, run_id TEXT, status TEXT NOT NULL,
                    reserved REAL NOT NULL, estimated REAL NOT NULL DEFAULT 0, evidence_id TEXT);
                """)
                connection.execute("BEGIN IMMEDIATE")
                columns = {row[1] for row in connection.execute("PRAGMA table_info(runs)")}
                for name in ("parent_run_id", "root_run_id", "owner_run_id", "owner_kind"):
                    if name not in columns:
                        connection.execute(f"ALTER TABLE runs ADD COLUMN {name} TEXT")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS mcp_surfaces "
                    "(id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS connectors "
                    "(id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS web_jobs ("
                    "run_id TEXT PRIMARY KEY, operation TEXT NOT NULL, "
                    "idempotency_key TEXT NOT NULL UNIQUE, request_sha256 TEXT NOT NULL, "
                    "owner_token TEXT NOT NULL, pid INTEGER, process_started_at TEXT)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS events_run_cursor ON events(run_id,id)"
                )
                connection.execute("CREATE INDEX IF NOT EXISTS runs_root ON runs(root_run_id)")
                connection.execute("PRAGMA user_version=1")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.root / "catalog.sqlite", timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def put(self, kind: str, data: Any) -> str:
        """Persist actual output and return its content identity."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            return self._put_locked(kind, data)

    def _put_locked(self, kind: str, data: Any) -> str:
        """Publish an immutable file while the caller owns the SQLite writer lock."""
        payload = canonical({"format_version": 1, "kind": kind, "data": data})
        identity = hashlib.sha256(payload).hexdigest()
        destination = self.root / "artifacts" / f"{identity}.json"
        if destination.exists():
            if destination.read_bytes() != payload:
                raise ValueError("Artifact integrity failure")
        else:
            temporary = destination.with_suffix(f".{uuid.uuid4().hex}.tmp")
            temporary.write_bytes(payload)
            temporary.replace(destination)
        return identity

    def get(self, identity: str) -> Any:
        """Read an artifact only after checking its SHA-256 identity."""
        if not re.fullmatch(r"[a-f0-9]{64}", identity):
            raise ValueError("Invalid artifact identifier")
        raw = (self.root / "artifacts" / f"{identity}.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != identity:
            raise ValueError("Artifact content has changed")
        return json.loads(raw)["data"]

    def event(
        self, run_id: str, stage: str, status: str, summary: str, data: Any = None
    ) -> str | None:
        artifact_id = self.put(stage, data) if data is not None else None
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO events(run_id,time,stage,status,summary,artifact_id) VALUES(?,?,?,?,?,?)",
                (run_id, now(), stage, status, summary, artifact_id),
            )
        return artifact_id

    def rows(self, query: str, parameters: tuple = ()) -> list[dict]:
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query, parameters)]

    def create_run(
        self,
        task_id: str,
        kind: str,
        inputs: dict,
        *,
        parent_run_id: str | None = None,
        root_run_id: str | None = None,
        owner_run_id: str | None = None,
        owner_kind: str | None = None,
    ) -> str:
        """Create an attributable run and its initial event in one transaction.

        An inline child inherits its parent's root and process owner. Existing
        corpus job kinds default to the legacy service worker for CLI callers.
        """
        identity = uuid.uuid4().hex
        inputs = {**inputs, "implementation": implementation_receipt()}
        input_id = self.put("run_input", inputs)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if parent_run_id:
                parent = connection.execute(
                    "SELECT * FROM runs WHERE id=?", (parent_run_id,)
                ).fetchone()
                if parent is None or parent["task_id"] != task_id:
                    raise ValueError("Parent run must belong to the same task")
                root_run_id = root_run_id or parent["root_run_id"] or parent_run_id
                owner_run_id = owner_run_id or parent["owner_run_id"]
                owner_kind = owner_kind or "child"
            if owner_kind is None:
                owner_kind = (
                    "service" if kind in {"construct", "ask", "revise", "regress"} else "inline"
                )
            if owner_kind in {"service", "web"}:
                owner_run_id = owner_run_id or identity
            connection.execute(
                "INSERT INTO runs(id,task_id,kind,status,created_at,input_id,"
                "parent_run_id,root_run_id,owner_run_id,owner_kind) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    identity,
                    task_id,
                    kind,
                    "queued",
                    now(),
                    input_id,
                    parent_run_id,
                    root_run_id or identity,
                    owner_run_id,
                    owner_kind,
                ),
            )
            connection.execute(
                "INSERT INTO events(run_id,time,stage,status,summary,artifact_id) VALUES(?,?,?,?,?,?)",
                (identity, now(), "request", "queued", f"{kind.capitalize()} requested", input_id),
            )
        return identity

    def set_run(
        self, run_id: str, status: str, *, result: Any = None, error: str | None = None
    ) -> None:
        """Publish a status/result and its lifecycle event atomically.

        Artifacts are durable before the transaction refers to them. Repeating
        an identical transition is a no-op. This does not retry external work.
        """
        result_id = self.put("run_result", result) if result is not None else None
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if previous is None:
                raise ValueError("Unknown run")
            if (
                previous["status"] == status
                and previous["error"] == error
                and (result_id is None or previous["result_id"] == result_id)
            ):
                return
            event_id = self._put_locked(
                "run_lifecycle",
                {
                    "previous_status": previous["status"],
                    "status": status,
                    "result_id": result_id or previous["result_id"],
                    "error": error,
                },
            )
            connection.execute(
                "UPDATE runs SET status=?,result_id=COALESCE(?,result_id),error=? WHERE id=?",
                (status, result_id, error, run_id),
            )
            connection.execute(
                "INSERT INTO events(run_id,time,stage,status,summary,artifact_id) VALUES(?,?,?,?,?,?)",
                (
                    run_id,
                    now(),
                    "lifecycle",
                    status,
                    f"Run {previous['status']} to {status}",
                    event_id,
                ),
            )

    def budget(self, limit: float = 40.0) -> dict:
        rows = self.rows("SELECT status,reserved,estimated FROM model_calls")
        estimated = sum(row["estimated"] for row in rows)
        reserved = sum(row["reserved"] for row in rows if row["status"] != "settled")
        return {
            "limit_usd": limit,
            "estimated_usd": estimated,
            "reserved_usd": reserved,
            "remaining_usd": max(0.0, limit - estimated - reserved),
            "calls": len(rows),
        }

    def reserve(self, run_id: str, amount: float, limit: float) -> str:
        """Reserve before a subprocess starts; concurrent jobs share one spending limit."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            used = connection.execute(
                "SELECT COALESCE(SUM(estimated + CASE WHEN status='settled' THEN 0 ELSE reserved END),0) FROM model_calls"
            ).fetchone()[0]
            if used + amount > limit:
                raise RuntimeError(
                    f"Budget exhausted: ${used:.3f} accounted for, ${amount:.3f} needed"
                )
            call_id = uuid.uuid4().hex
            connection.execute(
                "INSERT INTO model_calls(id,run_id,status,reserved) VALUES(?,?,?,?)",
                (call_id, run_id, "reserved", amount),
            )
        return call_id

    def settle(self, call_id: str, estimated: float | None, evidence: dict) -> None:
        """Retain the reservation when usage is missing or a request was interrupted."""
        evidence_id = self.put("model_usage", evidence)
        with self.connect() as connection:
            connection.execute(
                "UPDATE model_calls SET status=?,estimated=?,evidence_id=? WHERE id=?",
                (
                    "settled" if estimated is not None else "unknown",
                    estimated or 0.0,
                    evidence_id,
                    call_id,
                ),
            )

"""Immutable evidence objects and a small transactional index for local runs."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
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


class Store:
    """Content-addressed JSON artifacts with durable task/run/revision indexes.

    SQLite is the local single-user index. Artifact files are immutable and
    verified on read. LangGraph checkpoints live in their own database.
    """

    def __init__(self, root: str | Path = ".local"):
        self.root = Path(root).resolve()
        (self.root / "artifacts").mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
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
        payload = canonical({"format_version": 1, "kind": kind, "data": data})
        identity = hashlib.sha256(payload).hexdigest()
        destination = self.root / "artifacts" / f"{identity}.json"
        # SQLite writers serialize publication so a reader cannot see half a file.
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
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

    def create_run(self, task_id: str, kind: str, inputs: dict) -> str:
        identity = uuid.uuid4().hex
        input_id = self.put("run_input", inputs)
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO runs(id,task_id,kind,status,created_at,input_id) VALUES(?,?,?,?,?,?)",
                (identity, task_id, kind, "queued", now(), input_id),
            )
        self.event(identity, "request", "queued", f"{kind.capitalize()} requested", inputs)
        return identity

    def set_run(
        self, run_id: str, status: str, *, result: Any = None, error: str | None = None
    ) -> None:
        result_id = self.put("run_result", result) if result is not None else None
        with self.connect() as connection:
            connection.execute(
                "UPDATE runs SET status=?,result_id=COALESCE(?,result_id),error=? WHERE id=?",
                (status, result_id, error, run_id),
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

"""Single-run artifact files and a transactional index, independent of context."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n").encode()


class IntegrityError(RuntimeError):
    pass


class RunStore:
    KINDS = {"inputs", "model", "tools", "observations", "compactions", "results", "metadata", "diagnostics", "sources"}

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.db = sqlite3.connect(self.root / "ledger.sqlite")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE artifacts (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, step INTEGER NOT NULL,
                path TEXT UNIQUE NOT NULL, digest TEXT NOT NULL, size INTEGER NOT NULL,
                visible INTEGER NOT NULL, complete INTEGER NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL,
                step INTEGER NOT NULL, at TEXT NOT NULL, monotonic_ns INTEGER NOT NULL,
                payload TEXT NOT NULL, previous_sha256 TEXT NOT NULL, sha256 TEXT NOT NULL
            );
        """)
        self.db.commit()

    @classmethod
    def open_existing(cls, root: Path) -> RunStore:
        store = cls.__new__(cls)
        store.root = root.resolve(strict=True)
        store.db = sqlite3.connect((store.root / "ledger.sqlite").as_uri() + "?mode=ro", uri=True)
        return store

    def reserve(self, kind: str, step: int) -> tuple[str, Path]:
        if kind not in self.KINDS:
            raise ValueError("Unknown artifact kind")
        directory = self.root / ("outputs" if kind in {"model", "tools"} else "") / kind
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        artifact_id = str(uuid.uuid4())
        path = directory / f"step-{step:04d}-{artifact_id}.txt"
        with path.open("xb"):
            pass
        path.chmod(0o600)
        return artifact_id, path

    def publish(self, artifact_id: str, path: Path, kind: str, step: int,
                *, visible: bool = False, complete: bool = True) -> dict:
        relative = path.resolve().relative_to(self.root)
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
            data = handle.read()
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        digest = hashlib.sha256(data).hexdigest()
        with self.db:
            self.db.execute("INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (artifact_id, kind, step, str(relative), digest, len(data),
                             int(visible), int(complete), timestamp()))
        path.chmod(0o400)
        return {"id": artifact_id, "path": str(relative), "sha256": digest,
                "bytes": len(data), "complete": complete, "kind": kind, "step": step}

    def write(self, kind: str, value: object, step: int = 0, *, raw: bool = False,
              visible: bool = False, complete: bool = True) -> dict:
        artifact_id, path = self.reserve(kind, step)
        data = value if raw else json_bytes(value)
        if isinstance(data, str):
            data = data.encode()
        if not isinstance(data, bytes):
            raise TypeError("Raw artifacts must be bytes or text")
        with path.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        return self.publish(artifact_id, path, kind, step, visible=visible, complete=complete)

    def event(self, event_type: str, step: int = 0, **payload: object) -> int:
        with self.db:
            previous = self.db.execute("SELECT seq,sha256 FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            event = {"seq": previous[0] + 1 if previous else 1, "type": event_type, "step": step,
                     "at": timestamp(), "monotonic_ns": time.monotonic_ns(), "payload": payload,
                     "previous_sha256": previous[1] if previous else "0" * 64}
            digest = hashlib.sha256(json_bytes(event)).hexdigest()
            self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",
                            (event["seq"], event_type, step, event["at"], event["monotonic_ns"],
                             json_bytes(payload).decode(), event["previous_sha256"], digest))
        return event["seq"]

    def get(self, artifact_id: str, *, actor: bool = False) -> bytes:
        row = self.db.execute("SELECT path,digest,size,visible FROM artifacts WHERE id=?",
                              (artifact_id,)).fetchone()
        if row is None or (actor and not row[3]):
            raise KeyError("Output is unavailable in this run's visible scope")
        path = self.root / row[0]
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise IntegrityError("Artifact path escaped the run")
        try:
            data = path.read_bytes()
        except OSError as error:
            raise IntegrityError(f"Artifact unavailable: {artifact_id}") from error
        if len(data) != row[2] or hashlib.sha256(data).hexdigest() != row[1]:
            raise IntegrityError(f"Artifact failed integrity check: {artifact_id}")
        return data

    def visible_outputs(self) -> list[dict]:
        rows = self.db.execute("SELECT id,kind,step,size,complete FROM artifacts WHERE visible=1 ORDER BY rowid").fetchall()
        return [{"output_id": r[0], "kind": r[1], "step": r[2], "bytes": r[3],
                 "complete": bool(r[4])} for r in rows]

    def audit(self) -> dict:
        from .trace_audit import audit_store
        return audit_store(self)

    def export_judge_packet(self) -> dict:
        packet = self.audit()
        directory = self.root / "exports" / str(uuid.uuid4())
        directory.mkdir(parents=True, mode=0o700)
        with (directory / "judge_packet.json").open("xb") as handle:
            handle.write(json_bytes(packet))
            handle.flush()
            os.fsync(handle.fileno())
        with (directory / "events.jsonl").open("xb") as handle:
            for event in packet["events"]:
                handle.write(json_bytes(event))
            handle.flush()
            os.fsync(handle.fileno())
        return {"path": str(directory / "judge_packet.json"), "complete": packet["complete"], "problems": packet["problems"]}

    def close(self) -> None:
        self.db.close()

"""One SQLite writer, immutable JSON objects, and restartable repair work."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid

from react_runtime.completion import fingerprint, index_snapshot, validate_contract
from react_runtime.store import json_bytes, timestamp
from .program import seed_package, validate_package, MAX_ENTITIES, MAX_EDGES
from react_runtime.policy import legacy_policy

ROOT = Path(__file__).resolve().parents[1]
MAX_OBJECT_BYTES = 2_000_000


def runtime_sources():
    paths = list((ROOT / "repair_runtime").glob("*.py"))
    paths += list((ROOT / "react_runtime").glob("*.py"))
    paths += list((ROOT / "appworld_runtime").glob("*.py"))
    paths += [ROOT / p for p in ("scripts/repair.py", "scripts/inference.py", "scripts/prove_inference.py", "scripts/prove_policy.py", "config/models.toml", "config/gemini-no-tools.toml", "docs/system/contracts.schema.json", "oak-nine-operators.md")]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths) if p.is_file()}


class Archive:
    def __init__(self, root, *, create=False):
        self.root = Path(root).resolve()
        if create: self.root.mkdir(parents=True, exist_ok=False, mode=0o700)
        if not (self.root / "archive.sqlite").exists() and not create:
            raise ValueError("Repair archive does not exist; initialize it first")
        self.db = sqlite3.connect(self.root / "archive.sqlite", timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        if create:
            self.db.executescript("""
                CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE events(seq INTEGER PRIMARY KEY, type TEXT, at TEXT, payload TEXT,
                                    previous TEXT, sha256 TEXT);
                CREATE TABLE cases(id TEXT PRIMARY KEY, input_ref TEXT, origin_ref TEXT,
                                   status TEXT, last_parent TEXT, last_report TEXT, created TEXT);
                CREATE TABLE definitions(scope TEXT, kind TEXT, name TEXT, definition_ref TEXT,
                                         PRIMARY KEY(scope,kind,name,definition_ref));
                CREATE TABLE entities(case_id TEXT, identity TEXT, type TEXT, record_ref TEXT,
                                      PRIMARY KEY(case_id,identity));
                CREATE INDEX entities_by_type ON entities(case_id,type,identity);
                CREATE TABLE relations(case_id TEXT, source TEXT, type TEXT, target TEXT,
                                       PRIMARY KEY(case_id,source,type,target));
                CREATE INDEX relations_by_target ON relations(case_id,target,type,source);
                CREATE TABLE attempts(id INTEGER PRIMARY KEY, case_id TEXT, parent TEXT,
                                      suite TEXT, candidate TEXT, status TEXT, receipt TEXT);
                CREATE TABLE decisions(id INTEGER PRIMARY KEY, parent TEXT, candidate TEXT,
                                       receipt TEXT, accepted INTEGER, at TEXT);
            """)
            with self.db:
                for key, value in {"version": 1, "active": self.put(seed_package()), "generation": 0,
                                   "sources": runtime_sources(), "proposals_spent": 0, "cycles_spent": 0,
                                   "max_proposals": 512, "max_cycles": 20, "execution_gate_required": False,
                                   "inference_requests": {}, "inference_completed": {}, "case_adapters": {},
                                   "active_policy": self.put(legacy_policy()), "policy_groups": {}, "policy_decisions": []}.items(): self.set(key, value)
                self.set("source_snapshots", {name: self.put({"path": name, "text": (ROOT / name).read_text()})
                                              for name in self.meta("sources")})
                self.event("INITIALIZED", {"active": self.meta("active"), "sources": self.meta("sources")})
        if self.meta("version") != 1 or self.meta("sources") != runtime_sources():
            self.db.close()
            raise ValueError("Archive runtime revision differs; retain the old archive and initialize a new experiment")

    def close(self): self.db.close()

    def meta(self, key):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if row is None: raise KeyError(key)
        return json.loads(row[0])

    def set(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json_bytes(value).decode()))

    def put(self, value):
        data = json_bytes(value)
        if len(data) > MAX_OBJECT_BYTES: raise ValueError("Artifact size limit exceeded")
        key = hashlib.sha256(data).hexdigest()
        directory = self.root / "objects" / key[:2]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (key + ".json")
        temporary = directory / (".pending-" + str(uuid.uuid4()))
        try:
            with temporary.open("xb") as file:
                file.write(data); file.flush(); os.fsync(file.fileno())
            temporary.chmod(0o400)
            os.link(temporary, path)
            fd = os.open(directory, os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != data: raise ValueError("Artifact integrity violation")
        finally:
            temporary.unlink(missing_ok=True)
        return key

    def get(self, key):
        if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key):
            raise ValueError("Invalid artifact key")
        path = self.root / "objects" / key[:2] / (key + ".json")
        if path.is_symlink() or not path.resolve().is_relative_to(self.root): raise ValueError("Artifact path escaped archive")
        data = path.read_bytes()
        if len(data) > MAX_OBJECT_BYTES or hashlib.sha256(data).hexdigest() != key:
            raise ValueError("Artifact integrity violation")
        return json.loads(data)

    def event(self, kind, payload):
        last = self.db.execute("SELECT seq,sha256 FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        value = {"seq": last[0] + 1 if last else 1, "type": kind, "at": timestamp(),
                 "payload": payload, "previous": last[1] if last else "0" * 64}
        self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)", (value["seq"], kind, value["at"],
                        json_bytes(payload).decode(), value["previous"], fingerprint(value)))

    def audit(self):
        previous = "0" * 64
        for expected, row in enumerate(self.db.execute("SELECT * FROM events ORDER BY seq"), 1):
            value = {k: row[k] for k in ("seq", "type", "at", "previous")}
            value["payload"] = json.loads(row["payload"])
            if row["seq"] != expected or row["previous"] != previous or fingerprint(value) != row["sha256"]:
                raise ValueError("Repair event chain integrity violation")
            previous = row["sha256"]
        for path in (self.root / "objects").glob("*/*.json"): self.get(path.stem)
        self.get(self.meta("active"))
        for row in self.db.execute("SELECT input_ref,origin_ref,last_report FROM cases"):
            for ref in row:
                if ref is not None: self.get(ref)
        for row in self.db.execute("SELECT receipt FROM attempts WHERE receipt IS NOT NULL"): self.get(row[0])
        for row in self.db.execute("SELECT receipt FROM decisions"): self.get(row[0])
        for ref in self.meta("source_snapshots").values(): self.get(ref)
        return {"complete": True, "event_head": previous}

    @contextmanager
    def worker(self):
        with (self.root / "worker.lock").open("a") as lock:
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise RuntimeError("Another repair worker owns this archive") from None
            try:
                self.audit()
                with self.db:
                    running = [r[0] for r in self.db.execute("SELECT id FROM cases WHERE status='RUNNING'")]
                    self.db.execute("UPDATE cases SET status='READY' WHERE status='RUNNING'")
                    self.db.execute("UPDATE attempts SET status='INTERRUPTED' WHERE status='STARTED'")
                    if running: self.event("RECOVERED", {"cases": running, "spent_budget_preserved": True})
                yield
            finally: fcntl.flock(lock, fcntl.LOCK_UN)

    def add_case(self, data, origin=None):
        if not isinstance(data, dict) or set(data) != {"contract", "before"}: raise ValueError("Case requires contract and before")
        validate_contract(data["contract"])
        index_snapshot(data["before"])
        if len(data["before"]["entities"]) > MAX_ENTITIES or len(data["before"]["relations"]) > MAX_EDGES:
            raise ValueError("Case exceeds supported observation size")
        ref = self.put(data)
        origin_ref = self.put(origin or {"kind": "trusted_bound_input", "synthetic": False})
        with self.db:
            existing = self.db.execute("SELECT id FROM cases WHERE id=?", (ref,)).fetchone()
            if existing is None:
                self.db.execute("INSERT INTO cases VALUES (?,?,?,?,?,?,?)", (ref, ref, origin_ref, "READY", None, None, timestamp()))
                self.set("generation", self.meta("generation") + 1)
                self._discover(data)
            self.event("CASE_OBSERVED", {"case": ref, "origin": origin_ref, "duplicate": existing is not None})
        return ref

    def _discover(self, data):
        # Observed definitions carry scope and source identity; presence does not prove completeness.
        snapshot = data["before"]
        types = {}
        by_id = {e["id"]: e for e in snapshot["entities"]}
        case_id = fingerprint(data)
        for entity in by_id.values():
            self.db.execute("INSERT OR IGNORE INTO entities VALUES (?,?,?,?)",
                            (case_id, entity["id"], entity["type"], self.put(entity)))
            props = types.setdefault(entity["type"], {})
            for name, value in entity["properties"].items():
                props.setdefault(name, set()).add(type(value).__name__)
        records = [("entity_type", name, {"properties": {k: sorted(v) for k, v in props.items()}})
                   for name, props in types.items()]
        for edge in snapshot["relations"]:
            self.db.execute("INSERT OR IGNORE INTO relations VALUES (?,?,?,?)",
                            (case_id, edge["source"], edge["type"], edge["target"]))
            records.append(("relation_type", edge["type"], {"source_type": by_id[edge["source"]]["type"],
                            "target_type": by_id[edge["target"]]["type"]}))
        for kind, name, definition in records:
            ref = self.put({"scope": snapshot["scope"], "kind": kind, "name": name,
                            "observed_definition": definition, "source_case": fingerprint(data)})
            self.db.execute("INSERT OR IGNORE INTO definitions VALUES (?,?,?,?)", (snapshot["scope"], kind, name, ref))

    def discover(self, scope, *, offset=0, limit=20):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("Invalid discovery page")
        rows = self.db.execute("SELECT * FROM definitions WHERE scope=? ORDER BY kind,name,definition_ref LIMIT ? OFFSET ?",
                               (scope, limit + 1, offset)).fetchall()
        return {"records": [dict(r) for r in rows[:limit]], "next_offset": offset + limit if len(rows) > limit else None}

    def query_entities(self, case_id, *, entity_type=None, identity=None, offset=0, limit=20):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("Invalid entity page")
        rows = self.db.execute("SELECT * FROM entities WHERE case_id=? AND (? IS NULL OR type=?) AND (? IS NULL OR identity=?) ORDER BY identity LIMIT ? OFFSET ?",
                               (case_id, entity_type, entity_type, identity, identity, limit + 1, offset)).fetchall()
        return {"case": case_id, "records": [dict(r) for r in rows[:limit]],
                "next_offset": offset + limit if len(rows) > limit else None}

    def query_relations(self, case_id, identity, *, direction="out", offset=0, limit=20):
        if direction not in {"in", "out"} or type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("Invalid relationship page")
        column = "source" if direction == "out" else "target"
        rows = self.db.execute(f"SELECT * FROM relations WHERE case_id=? AND {column}=? ORDER BY type,source,target LIMIT ? OFFSET ?",
                               (case_id, identity, limit + 1, offset)).fetchall()
        return {"case": case_id, "records": [dict(r) for r in rows[:limit]],
                "next_offset": offset + limit if len(rows) > limit else None}

    def snapshot(self):
        with self.db:
            self.db.execute("BEGIN")
            rows = self.db.execute("SELECT id,input_ref FROM cases ORDER BY id").fetchall()
            value = {"generation": self.meta("generation"), "cases": [dict(r) for r in rows]}
        return value, self.put(value)

    def finish_case(self, case_id, state, parent, receipt):
        with self.db:
            self.db.execute("UPDATE cases SET status=?,last_parent=?,last_report=? WHERE id=?", (state, parent, receipt, case_id))
            self.event("CASE_FINISHED", {"case": case_id, "status": state, "parent": parent, "receipt": receipt})

    def reserve_attempt(self, case_id, parent, suite, candidate):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if self.meta("proposals_spent") >= self.meta("max_proposals"): return None
            if self.db.execute("SELECT 1 FROM attempts WHERE parent=? AND suite=? AND candidate=?",
                               (parent, suite, candidate)).fetchone(): return None
            self.set("proposals_spent", self.meta("proposals_spent") + 1)
            cursor = self.db.execute("INSERT INTO attempts(case_id,parent,suite,candidate,status) VALUES (?,?,?,?,'STARTED')",
                                     (case_id, parent, suite, candidate))
            self.event("ATTEMPT_RESERVED", {"id": cursor.lastrowid, "case": case_id, "parent": parent, "candidate": candidate})
            return cursor.lastrowid

    def finish_attempt(self, attempt, status, receipt):
        with self.db:
            self.db.execute("UPDATE attempts SET status=?,receipt=? WHERE id=?", (status, receipt, attempt))
            self.event("ATTEMPT_FINISHED", {"id": attempt, "status": status, "receipt": receipt})

    def activate(self, parent, candidate, suite, receipt):
        if set(self.meta("inference_requests")) - set(self.meta("inference_completed")):
            raise ValueError("Activation is only allowed between completed episodes")
        validate_package(self.get(candidate))
        scored = self.get(receipt)
        if (scored.get("decision") != "ACCEPT_FOR_DEVELOPMENT" or scored.get("parent_ref") != parent
                or scored.get("candidate_ref") != candidate or self.get(scored["suite_ref"]) != suite
                or not scored.get("challenge_results") or any(r["state"] != "TRUE" for r in scored["challenge_results"])):
            raise ValueError("Activation requires the matching complete comparison receipt")
        if self.meta("execution_gate_required"):
            gate = scored.get("execution_gate", {})
            if (gate.get("state") != "TRUE" or gate.get("parent") != parent or gate.get("candidate") != candidate
                    or gate.get("policy_version") != self.meta("active_policy")
                    or gate.get("suite") != suite
                    or sorted(r["case"] for r in gate.get("rows", [])) != sorted(r["id"] for r in suite["cases"])
                    or any(r["state"] != "TRUE" for r in gate.get("rows", []))):
                raise ValueError("Activation requires fresh execution of every retained case")
            for row in gate["rows"]:
                judged = self.get(row["judge"])
                if judged["task_state"] != "TRUE" or judged["kernel_gap"] or not judged["coverage"]["integrity_complete"]:
                    raise ValueError("Execution gate contradicts its original judge receipt")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if set(self.meta("inference_requests")) - set(self.meta("inference_completed")):
                self.event("ACTIVATION_DEFERRED", {"reason": "EPISODE_RUNNING", "candidate": candidate})
                return False
            if self.meta("active") != parent or self.meta("generation") != suite["generation"]:
                self.event("STALE_COMPARISON", {"parent": parent, "candidate": candidate, "receipt": receipt})
                return False
            self.set("active", candidate)
            self.db.execute("INSERT INTO decisions(parent,candidate,receipt,accepted,at) VALUES (?,?,?,1,?)",
                            (parent, candidate, receipt, timestamp()))
            self.db.execute("UPDATE cases SET status='READY'")
            self.event("ACTIVATED_FOR_DEVELOPMENT", {"parent": parent, "candidate": candidate, "receipt": receipt})
            return True

    def rollback(self, expected, target, reason):
        if not reason.strip(): raise ValueError("Rollback requires a reason")
        validate_package(self.get(target))
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if self.meta("active") != expected: raise ValueError("Active package changed")
            known = self.db.execute("SELECT 1 FROM decisions WHERE parent=? OR candidate=?", (target, target)).fetchone()
            if known is None: raise ValueError("Rollback target is not in the accepted lineage")
            self.set("active", target)
            self.db.execute("UPDATE cases SET status='READY'")
            self.event("ROLLED_BACK", {"from": expected, "to": target, "reason": reason})

    def status(self):
        return {"active": self.meta("active"), "generation": self.meta("generation"),
                "active_policy": self.meta("active_policy"), "policy_decisions": self.meta("policy_decisions"),
                "proposals_spent": self.meta("proposals_spent"), "cycles_spent": self.meta("cycles_spent"),
                "cases": {r[0]: r[1] for r in self.db.execute("SELECT status,count(*) FROM cases GROUP BY status")},
                "decisions": [dict(r) for r in self.db.execute("SELECT * FROM decisions ORDER BY id")],
                "native_performance_claimed": False}

"""Local application boundary for evidence, jobs, answers, and revision audits."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import traceback
import uuid
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from oak.corpus import normalize_snapshot
from oak.historical_replay import (
    accepted_replay_report,
    check_candidate_replay,
    inference_admission,
    prepare_candidate_adapter,
)
from oak.model import GeminiCLI, runtime_config
from oak.pipeline import answer, construction_graph
from oak.store import Store, canonical, now
from oak.tasks.evaluation import get_scorer


def source_parts(snapshot: dict) -> list[dict]:
    """Flatten a corpus bundle, retaining every source snapshot's acquisition receipt."""
    if snapshot.get("kind") == "corpus_bundle":
        return [part for child in snapshot["parts"] for part in source_parts(child)]
    return [snapshot]


def combine_corpus(previous: dict, incoming: dict) -> dict:
    """Replace an identical source request; append genuinely different sources."""
    parts = {
        canonical(
            [part.get("connector_id"), part.get("source_id"), part.get("request")]
        ).decode(): part
        for part in source_parts(previous)
    }
    for part in source_parts(incoming):
        key = canonical(
            [part.get("connector_id"), part.get("source_id"), part.get("request")]
        ).decode()
        parts[key] = part
    return {
        "kind": "corpus_bundle",
        "parts": list(parts.values()),
        "policy": "same_source_request_replaces_other_sources_append",
    }


def corpus_documents(snapshot: dict) -> list[dict]:
    documents = []
    for part in source_parts(snapshot):
        documents.extend(normalize_snapshot(part))
    identities = [document["document_id"] for document in documents]
    if len(identities) != len(set(identities)):
        raise ValueError(
            "Corpus sources contain duplicate document IDs; refresh or identify sources explicitly"
        )
    return documents


class Service:
    """Serve a small local UI from real saved artifacts and background processes."""

    def __init__(self, root: str | Path = ".local"):
        self.store = Store(root)
        self.root = self.store.root

    def artifact(self, identity: str):
        return self.store.get(identity)

    def budget(self) -> dict:
        return self.store.budget(runtime_config()["total_budget_usd"])

    def tasks(self) -> list[dict]:
        return [
            self.task(row["id"])
            for row in self.store.rows("SELECT id FROM tasks ORDER BY rowid DESC")
        ]

    def task(self, task_id: str) -> dict:
        rows = self.store.rows("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not rows:
            raise ValueError("Task does not exist")
        row = rows[0]
        task = {**json.loads(row["data"]), "id": task_id, "active_revision": row["active_revision"]}
        task["status"] = "ready" if row["active_revision"] else "awaiting_construction"
        if row["active_revision"]:
            revision = self.artifact(row["active_revision"])
            task.update(
                scope=revision["scope"],
                corpus_id=revision["corpus_id"],
                example_queries=revision.get("queries", task["example_queries"]),
            )
        return task

    def create_task(
        self,
        title: str,
        scope: str,
        snapshot: dict,
        queries: list[str],
        *,
        references: dict[str, str] | None = None,
        evaluator: str | None = None,
    ) -> str:
        """Create an auditable task from real supplied evidence and construction queries."""
        if (
            not title.strip()
            or not scope.strip()
            or not queries
            or any(not q.strip() for q in queries)
        ):
            raise ValueError("Title, task scope, and at least one construction query are required")
        if len(queries) > 12:
            raise ValueError("Use at most 12 construction queries for the first bounded pilot")
        corpus_documents(snapshot)  # Reject incomplete acquisitions before starting model work.
        get_scorer(evaluator)
        if references and evaluator is None:
            raise ValueError("Reference answers require a task-specific evaluator")
        identity = uuid.uuid4().hex
        data = {
            "title": title.strip(),
            "scope": scope.strip(),
            "example_queries": queries,
            "corpus_id": self.store.put("corpus_snapshot", snapshot),
            "created_at": now(),
            "references": references,
            "evaluator": evaluator,
        }
        data["reference_corpus_id"] = data["corpus_id"]
        with self.store.connect() as connection:
            connection.execute(
                "INSERT INTO tasks(id,data) VALUES(?,?)", (identity, json.dumps(data))
            )
        return identity

    def runs(self, task_id: str) -> list[dict]:
        with (self.root / "jobs.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # Job submitters may already hold this lock. Reading history must
                # neither deadlock their caller nor block the live interface.
                pass
            else:
                self._reconcile_jobs(task_id)
        return self.store.rows(
            "SELECT * FROM runs WHERE task_id=? ORDER BY created_at DESC", (task_id,)
        )

    def events(self, run_id: str) -> list[dict]:
        return self.store.rows("SELECT * FROM events WHERE run_id=? ORDER BY id", (run_id,))

    def revisions(self, task_id: str) -> list[dict]:
        return self.store.rows(
            "SELECT * FROM revisions WHERE task_id=? ORDER BY created_at DESC", (task_id,)
        )

    def revision(self, task_id: str, revision_id: str | None = None) -> dict:
        identity = revision_id or self.task(task_id)["active_revision"]
        if not identity:
            raise ValueError("Construct an ontology before asking a question")
        revision = self.artifact(identity)
        if revision.get("task_id") != task_id:
            raise ValueError("Revision belongs to another task")
        return {**revision, "id": identity}

    def start_job(
        self,
        task_id: str,
        kind: str,
        query: str | None = None,
        scope: str | None = None,
        snapshot: dict | None = None,
        queries: list[str] | None = None,
    ) -> str:
        """Explicitly enqueue one task action and launch it outside Streamlit reruns."""
        if kind not in {"construct", "ask", "revise", "regress"}:
            raise ValueError("Unsupported job kind")
        task = self.task(task_id)
        if kind != "construct" and not task["active_revision"]:
            raise ValueError("This action needs an active kernel revision")
        if kind == "ask" and not (query or "").strip():
            raise ValueError("A query is required")
        if kind == "ask":
            admission = inference_admission(self.store, task["active_revision"])
            if not admission["allowed"]:
                raise ValueError(admission["reason"])
        if kind == "construct" and task["active_revision"]:
            raise ValueError("Use Revise to change an existing ontology")
        corpus = self.artifact(task["corpus_id"])
        if snapshot is not None:
            corpus = combine_corpus(corpus, snapshot)
        corpus_documents(corpus)
        corpus_id = self.store.put("corpus_snapshot", corpus)
        all_queries = list(dict.fromkeys(task["example_queries"] + (queries or [])))
        if not all_queries or len(all_queries) > 12 or any(not q.strip() for q in all_queries):
            raise ValueError("Provide 1 to 12 nonempty validation questions")
        inputs = {
            "task_id": task_id,
            "kind": kind,
            "query": query,
            "scope": scope.strip() if scope and scope.strip() else task["scope"],
            "corpus_id": corpus_id,
            "parent": task["active_revision"],
            "queries": all_queries,
            "references": task.get("references")
            if corpus_id == task.get("reference_corpus_id")
            else None,
            "evaluator": task.get("evaluator"),
        }
        with (self.root / "jobs.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self._reconcile_jobs(task_id)
            if self.store.rows(
                "SELECT id FROM runs WHERE task_id=? AND status IN ('queued','running')", (task_id,)
            ):
                raise ValueError("A job is already active for this task")
            run_id = self.store.create_run(task_id, kind, inputs)
            try:
                self._spawn(run_id)
            except OSError as error:
                self.store.set_run(run_id, "failed", error=str(error))
                raise
        return run_id

    def _spawn(self, run_id: str) -> None:
        directory = self.root / "jobs"
        directory.mkdir(exist_ok=True)
        with (directory / f"{run_id}.log").open("a") as output:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "oak.cli",
                    "worker",
                    "--run-id",
                    run_id,
                    "--root",
                    str(self.root),
                ],
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=Path(__file__).resolve().parents[2],
            )
        (directory / f"{run_id}.pid").write_text(str(process.pid))

    def _reconcile_jobs(self, task_id: str) -> None:
        """Mark a saved job interrupted only when its recorded worker no longer exists."""
        for row in self.store.rows(
            "SELECT id FROM runs WHERE task_id=? AND status IN ('queued','running') "
            "AND (owner_kind='service' OR (owner_kind IS NULL "
            "AND kind IN ('construct','ask','revise','regress')))",
            (task_id,),
        ):
            path = self.root / "jobs" / f"{row['id']}.pid"
            if not path.exists():
                # Launch holds jobs.lock until its PID is written. Never execute a
                # model request in a worker without first publishing its identity.
                self.store.set_run(
                    row["id"],
                    "interrupted",
                    error="Launch has no saved worker identity; resume the saved request",
                )
                self.store.event(
                    row["id"], "worker", "interrupted", "Launch did not publish a worker identity"
                )
                continue
            try:
                pid = int(path.read_text())
                try:
                    exited, _ = os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    exited = 0
                if exited == pid:
                    raise ProcessLookupError("Worker exited")
                os.kill(pid, 0)
            except ProcessLookupError:
                self.store.set_run(
                    row["id"], "interrupted", error="Worker process exited before saving a result"
                )
                self.store.event(
                    row["id"], "worker", "interrupted", "Worker process no longer exists"
                )
            except PermissionError:
                pass

    def resume_job(self, run_id: str) -> None:
        with (self.root / "jobs.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            rows = self.store.rows("SELECT * FROM runs WHERE id=?", (run_id,))
            if not rows:
                raise ValueError("Run does not exist")
            if rows[0]["kind"] not in {"construct", "ask", "revise", "regress"}:
                raise ValueError("This run is not resumable by the corpus worker")
            self._reconcile_jobs(rows[0]["task_id"])
            row = self.store.rows("SELECT * FROM runs WHERE id=?", (run_id,))[0]
            if row["status"] not in {"failed", "interrupted"}:
                raise ValueError("Only a failed or interrupted run can resume")
            if self.store.rows(
                "SELECT id FROM runs WHERE task_id=? AND status IN ('queued','running')",
                (row["task_id"],),
            ):
                raise ValueError("A job is already active for this task")
            self.store.set_run(run_id, "queued")
            try:
                self._spawn(run_id)
            except OSError as error:
                self.store.set_run(run_id, "failed", error=str(error))
                raise

    def _regression_receipts(self, task_id: str, parent_id: str) -> list[dict]:
        receipts = []
        for row in self.store.rows(
            "SELECT result_id FROM runs WHERE task_id=? AND kind='ask' AND status='completed'",
            (task_id,),
        ):
            result = self.artifact(row["result_id"])
            if result.get("kernel_revision") == parent_id and result.get("status") == "answered":
                receipts.append({"receipt_id": row["result_id"], "result": result})
        return receipts

    def promotion_check(self, task_id: str, revision_id: str) -> dict:
        """Require candidate checks and the complete inherited historical bank."""
        revision = self.revision(task_id, revision_id)
        active = self.task(task_id)["active_revision"]
        if active == revision_id:
            return {"allowed": False, "reason": "This revision is already active"}
        if revision["assessment"]["status"] != "passed":
            return {"allowed": False, "reason": "Candidate construction checks failed"}
        if active != revision["parent"]:
            return {"allowed": False, "reason": "Candidate is based on a different active revision"}
        try:
            report = accepted_replay_report(self.store, revision_id, refresh_bank=False)
        except (ValueError, KeyError, OSError) as error:
            return {"allowed": False, "reason": str(error)}
        return {
            "allowed": True,
            "reason": "Every inherited protected computation passed on the candidate",
            "regression": report,
        }

    def promote(self, task_id: str, revision_id: str) -> None:
        """Serialize promotion with job creation and require a stable parent receipt set."""
        with (self.root / "jobs.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self._reconcile_jobs(task_id)
            if self.store.rows(
                "SELECT id FROM runs WHERE task_id=? AND status IN ('queued','running')", (task_id,)
            ):
                raise ValueError("Wait for the current task job before promoting a candidate")
            self._promote_checked(task_id, revision_id)

    def _promote_checked(self, task_id: str, revision_id: str) -> None:
        """Promote an explicitly selected checked candidate without rewriting history."""
        revision = self.revision(task_id, revision_id)
        check = self.promotion_check(task_id, revision_id)
        if not check["allowed"]:
            raise ValueError(check["reason"])
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT active_revision FROM tasks WHERE id=?", (task_id,)
            ).fetchone()[0]
            if current == revision_id:
                return
            if current != revision["parent"]:
                raise ValueError(
                    "Active revision changed; revalidate the candidate against its current parent"
                )
            connection.execute(
                "UPDATE tasks SET active_revision=? WHERE id=?", (revision_id, task_id)
            )
            connection.execute("UPDATE revisions SET status='promoted' WHERE id=?", (revision_id,))
        self.store.event(
            revision["run_id"],
            "promotion",
            "completed",
            "Candidate promoted; parent retained",
            {"parent": current, "revision_id": revision_id},
        )

    def regression(self, task_id: str, candidate: dict, run_id: str | None = None) -> dict:
        """Execute the complete inherited historical bank with no model or live acquisition.

        Shared adapter proposal belongs to construction. This command cannot
        extract a changed corpus or invoke a model to hide a missing mapping.
        """
        self.revision(task_id, candidate["id"])
        result = check_candidate_replay(
            self.store, candidate["id"], run_id=run_id or candidate["run_id"]
        )
        return {
            **result,
            "candidate_revision": candidate["id"],
            "parent_revision": candidate.get("parent"),
            "evidence_type": "historical_execution_replay",
            "fresh_agent_success": "unverified",
        }

    def run_worker(self, run_id: str) -> None:
        """Execute or resume a saved job, retaining actual errors and checkpoints."""
        directory = self.root / "jobs"
        directory.mkdir(exist_ok=True)
        (directory / f"{run_id}.pid").write_text(str(os.getpid()))
        row = self.store.rows("SELECT * FROM runs WHERE id=?", (run_id,))[0]
        if row["kind"] not in {"construct", "ask", "revise", "regress"}:
            raise ValueError("This run does not belong to the corpus worker")
        inputs = self.artifact(row["input_id"])
        self.store.set_run(run_id, "running")
        try:
            if row["kind"] in {"construct", "revise"}:
                documents_id = self.store.put(
                    "corpus_documents", corpus_documents(self.artifact(inputs["corpus_id"]))
                )
                initial = {
                    key: inputs[key]
                    for key in ["task_id", "scope", "queries", "corpus_id", "parent"]
                }
                initial.update(
                    run_id=run_id,
                    documents_id=documents_id,
                    round=0,
                    suggestion=inputs.get("query"),
                )
                with SqliteSaver.from_conn_string(str(self.root / "checkpoints.sqlite")) as saver:
                    graph = construction_graph(
                        self.store,
                        saver,
                        inputs.get("references"),
                        get_scorer(inputs.get("evaluator")),
                    )
                    graph_config = {"configurable": {"thread_id": run_id}, "recursion_limit": 60}
                    checkpoint = graph.get_state(graph_config)
                    self.store.event(
                        run_id,
                        "workflow",
                        "running",
                        "Construction workflow started or resumed",
                        {
                            "mermaid": graph.get_graph().draw_mermaid(),
                            "resume": bool(checkpoint.values),
                        },
                    )
                    final = graph.invoke(None if checkpoint.values else initial, graph_config)
                revision = self.revision(inputs["task_id"], final["revision_id"])
                if inputs["parent"]:
                    try:
                        proposal_model = GeminiCLI(self.store, run_id)
                        prepare_candidate_adapter(
                            self.store,
                            revision["id"],
                            run_id=run_id,
                            proposer=lambda payload: proposal_model.json(
                                "historical_adapter",
                                "Propose one shared bounded migration and interface adapter. "
                                "Use only supplied contracts and DSL. Never insert answers, "
                                "task identifiers, defaults, or external calls.",
                                payload,
                            ),
                        )
                    except (ValueError, RuntimeError) as error:
                        self.store.event(run_id, "historical_adapter", "failed", str(error))
                replay = (
                    self.regression(inputs["task_id"], revision, run_id)
                    if inputs["parent"]
                    else None
                )
                if replay:
                    self.store.event(
                        run_id,
                        "regression",
                        replay["status"],
                        "Previous real calls replayed against candidate",
                        replay,
                    )
                result = {
                    "revision_id": final["revision_id"],
                    "assessment": revision["assessment"],
                    "regression": replay,
                }
                self.store.set_run(
                    run_id,
                    "completed" if revision["assessment"]["status"] == "passed" else "failed",
                    result=result,
                )
            elif row["kind"] == "ask":
                revision = self.revision(inputs["task_id"], inputs["parent"])
                admission = inference_admission(self.store, revision["id"])
                if not admission["allowed"]:
                    raise ValueError(admission["reason"])
                demand_profile = (
                    revision.get("instantiation_profile", revision.get("construction_profile"))
                    == "demand_v1"
                )
                materialize = None
                reused = inputs["corpus_id"] == revision["corpus_id"]
                # Fresh inference evidence always waits for an executable
                # demand, including kernels frozen before profile flags existed.
                demand_driven = demand_profile or not reused
                if demand_driven:
                    from oak.corpus_materialization import CorpusMaterializer

                    materialize = CorpusMaterializer(
                        self.store,
                        GeminiCLI(self.store, run_id),
                        schema=revision["schema"],
                        kernel_id=revision["id"],
                        corpus_id=inputs["corpus_id"],
                        load_documents=lambda: corpus_documents(self.artifact(inputs["corpus_id"])),
                        retained_graph=revision["graph"] if reused else None,
                    )
                    revision["graph"] = {
                        "nodes": [],
                        "edges": [],
                        "source_document_ids": [],
                        "source_document_count": 0,
                    }
                    revision["corpus_id"] = inputs["corpus_id"]
                    self.store.event(
                        run_id,
                        "graph_snapshot",
                        "completed",
                        "Initial empty query graph",
                        revision["graph"],
                    )
                # Identical corpus/schema reuses the actual frozen graph artifact as a documented cache extension.
                if not demand_driven and revision["graph"].get("ignored_documents"):
                    raise ValueError(
                        "Inference graph excludes source documents; revise and validate corpus coverage before answering"
                    )

                def save_query_graph():
                    return self.store.event(
                        run_id,
                        "inference_graph",
                        "completed",
                        "Actual query graph saved",
                        {
                            "kernel_revision": revision["id"],
                            "corpus_id": revision["corpus_id"],
                            "graph": revision["graph"],
                            "reused_construction_graph": reused,
                            "instantiation_profile": "demand_v1" if demand_driven else "legacy",
                        },
                    )

                graph_id = save_query_graph() if not demand_driven else None
                result = answer(
                    self.store,
                    GeminiCLI(self.store, run_id),
                    revision,
                    inputs["query"],
                    materialize=materialize,
                )
                if demand_driven:
                    graph_id = save_query_graph()
                result["query"] = inputs["query"]
                result["graph_artifact_id"] = graph_id
                self.store.set_run(run_id, "completed", result=result)
            else:
                candidates = self.revisions(inputs["task_id"])
                candidate = next(
                    (item for item in candidates if item["parent"] == inputs["parent"]), None
                )
                if candidate is None:
                    raise ValueError("No candidate based on the active revision exists")
                result = self.regression(
                    inputs["task_id"], self.revision(inputs["task_id"], candidate["id"]), run_id
                )
                self.store.event(
                    run_id,
                    "regression",
                    result["status"],
                    "Recorded-call regression finished",
                    result,
                )
                self.store.set_run(run_id, "completed", result=result)
        except BaseException as error:
            self.store.event(
                run_id,
                "error",
                "failed",
                str(error),
                {
                    "type": type(error).__name__,
                    "message": str(error),
                    "traceback": traceback.format_exc(),
                },
            )
            self.store.set_run(
                run_id,
                "interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                error=str(error),
            )
            raise

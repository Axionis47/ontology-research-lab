"""Durable local submissions around the existing MCP engine.

HTTP requests persist work and start a detached worker. Readers never launch,
reconcile, or retry work. LangGraph remains the workflow engine. A dead worker
is interrupted, never resumed automatically across an uncertain external call.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oak.bootstrap import SurfaceEngine
from oak.functions import validate_functions
from oak.mcp_bridge import ConnectionConfig, MCPBridge, ServerConfig, reviewed_catalog
from oak.model import redact_diagnostic, runtime_config
from oak.store import Store, canonical, implementation_receipt, now
from oak.task_context import InferenceQuery, TaskSurface


class WebJobError(ValueError):
    """An actionable application failure, separate from malformed input."""

    def __init__(
        self,
        code: str,
        message: str,
        retryable: bool = False,
        evidence_refs: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.evidence_refs = evidence_refs or []


def _process_identity(pid: int) -> str | None:
    """Read a real process start identity so PID reuse does not imply ownership."""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        # Restricted hosts can deny process enumeration. Running workers also
        # hold an owner-specific OS lock, which is the authoritative live lease.
        return None
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


class WebJobs:
    """Persist connector selections, immutable surfaces, and bounded async jobs.

    ``discover`` and ``submit`` return run_id/status/operation/reused and an
    optional public task_id. ``save_connector`` and ``connectors`` return
    connector_id/discovery_id/configuration/catalog. ``create_task`` returns
    task_id/surface_id/kind/artifact_id. All identities refer to real stored
    records; discovery calls no model and execution calls no fake component.
    """

    def __init__(self, root: str | Path = ".local") -> None:
        self.store = Store(root)
        self.root = self.store.root

    @contextmanager
    def _lock(self):
        with (self.root / "web-jobs.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def _artifact(self, identity: str) -> Any:
        try:
            return self.store.get(identity)
        except FileNotFoundError as error:
            raise WebJobError(
                "artifact_missing", "Saved evidence is missing", evidence_refs=[identity]
            ) from error

    @staticmethod
    def _surface_id(task_id: str) -> str:
        if task_id.startswith("mcp:"):
            task_id = task_id[4:]
        if ":" in task_id or not task_id:
            raise ValueError("Web execution requires an MCP task")
        return task_id

    def _surface(self, task_id: str) -> dict:
        identity = self._surface_id(task_id)
        rows = self.store.rows("SELECT artifact_id FROM mcp_surfaces WHERE id=?", (identity,))
        if not rows:
            raise WebJobError("artifact_missing", "MCP task does not exist")
        return self._artifact(rows[0]["artifact_id"])

    def _accepted(self, run_id: str, *, reused: bool) -> dict:
        row = self.store.rows(
            "SELECT r.*,j.operation FROM runs r JOIN web_jobs j ON j.run_id=r.id WHERE r.id=?",
            (run_id,),
        )[0]
        result = {
            "run_id": run_id,
            "status": row["status"],
            "operation": row["operation"],
            "reused": reused,
        }
        if row["operation"] == "discover":
            result["discovery_id"] = run_id
        else:
            result["task_id"] = f"mcp:{row['task_id']}"
        return result

    def discover(self, connection: dict, key: str) -> dict:
        """Queue actual initialize/list-tools discovery, without granting call access."""
        checked = ConnectionConfig.model_validate(connection).model_dump(mode="json")
        return self._enqueue(None, "discover", {"connection": checked}, key)

    def discovery(self, identity: str) -> dict:
        """Read discovery status/evidence without retrying or reconciling a process."""
        rows = self.store.rows(
            "SELECT r.* FROM runs r JOIN web_jobs j ON j.run_id=r.id "
            "WHERE r.id=? AND j.operation='discover'",
            (identity,),
        )
        if not rows:
            raise WebJobError("artifact_missing", "Connector discovery does not exist")
        row = rows[0]
        inputs = self._artifact(row["input_id"])
        result = {
            "id": identity,
            "run_id": identity,
            "status": row["status"],
            "error": row["error"],
            "connection": inputs["connection"],
            "catalog": None,
            "artifact_refs": [row["input_id"]],
        }
        if row["result_id"]:
            result["catalog"] = self._artifact(row["result_id"])["catalog"]
            result["artifact_refs"].append(row["result_id"])
        for event in self.store.rows(
            "SELECT artifact_id FROM events WHERE run_id=? AND stage IN ('mcp_discovery','worker_error')",
            (identity,),
        ):
            if event["artifact_id"] and event["artifact_id"] not in result["artifact_refs"]:
                result["artifact_refs"].append(event["artifact_id"])
        return result

    def save_connector(self, discovery_id: str, allowed_tools: list[str]) -> dict:
        """Save the user's reviewed selection from a successful real discovery."""
        discovery = self.discovery(discovery_id)
        if discovery["status"] != "completed" or not discovery["catalog"]:
            raise ValueError("Connector discovery must finish successfully before selection")
        config = ServerConfig.model_validate(
            {**discovery["connection"], "allowed_tools": allowed_tools}
        )
        catalog = reviewed_catalog(discovery["catalog"], config)
        catalog["catalog_id"] = self.store.put("reviewed_mcp_catalog", catalog)
        value = {
            "format_version": 1,
            "discovery_id": discovery_id,
            "configuration": config.model_dump(mode="json"),
            "catalog": catalog,
        }
        identity = self.store.put("connector", value)
        with self.store.connect() as connection:
            connection.execute("INSERT OR IGNORE INTO connectors VALUES(?,?)", (identity, identity))
        return {"connector_id": identity, **value}

    def connectors(self) -> list[dict]:
        """List saved reviewed connections, with no network or worker side effects."""
        return [
            {"connector_id": row["id"], **self._artifact(row["artifact_id"])}
            for row in self.store.rows("SELECT * FROM connectors ORDER BY rowid")
        ]

    def create_task(self, config: dict, connector_ids: list[str]) -> dict:
        """Freeze curated inputs against selected, genuinely discovered catalogs.

        This saves setup only. It does not rediscover, invoke tools, create a
        kernel, or start construction. Invocation checks live contract identity.
        """
        if not connector_ids or len(set(connector_ids)) != len(connector_ids):
            raise ValueError("Select at least one distinct saved connector")
        if "servers" in config:
            raise ValueError("Task servers come from saved connector selections")
        selected = []
        for identity in connector_ids:
            rows = self.store.rows("SELECT artifact_id FROM connectors WHERE id=?", (identity,))
            if not rows:
                raise WebJobError(
                    "artifact_missing", "Saved connector does not exist", evidence_refs=[identity]
                )
            selected.append(self._artifact(rows[0]["artifact_id"]))
        surface = TaskSurface.model_validate(
            {**config, "servers": [item["configuration"] for item in selected]}
        )
        runtime = runtime_config()
        if surface.limits.max_steps > runtime["max_agent_steps"]:
            raise ValueError("Task step limit exceeds the supported runtime bound")
        if surface.limits.max_new_spend_usd > runtime["total_budget_usd"]:
            raise ValueError("Task spending limit exceeds the global allowance")
        if surface.limits.max_new_spend_usd < 0.01 or surface.sampling_fraction < 0.01:
            raise ValueError("Task spend and sampling settings are below the supported minimum")
        if not any(query.split == "construction" for query in surface.queries):
            raise ValueError("A task needs at least one curated construction request")
        budget = self.store.budget(runtime_config()["total_budget_usd"])
        identity = uuid.uuid4().hex
        catalog = {
            "format_version": 1,
            "status": "completed",
            "selection": "saved_reviewed_discoveries",
            "connector_ids": connector_ids,
            "servers": [server for item in selected for server in item["catalog"]["servers"]],
            "tools": [tool for item in selected for tool in item["catalog"]["tools"]],
        }
        catalog["catalog_id"] = self.store.put("mcp_catalog_selection", catalog)
        value = {
            "surface_id": identity,
            "configuration": surface.model_dump(mode="json"),
            "catalog": catalog,
            "created_at": now(),
            "connector_ids": connector_ids,
            "budget_ceiling_usd": min(
                budget["limit_usd"],
                budget["estimated_usd"] + budget["reserved_usd"] + surface.limits.max_new_spend_usd,
            ),
        }
        artifact_id = self.store.put("mcp_surface", value)
        with self.store.connect() as connection:
            connection.execute("INSERT INTO mcp_surfaces VALUES(?,?)", (identity, artifact_id))
        return {
            "task_id": f"mcp:{identity}",
            "surface_id": identity,
            "kind": "mcp",
            "artifact_id": artifact_id,
        }

    def _kernel(self, identity: str, surface_id: str) -> dict:
        kernel = self._artifact(identity)
        if kernel.get("kind") != "mcp_kernel" or kernel.get("surface_id") != surface_id:
            raise ValueError("Kernel must belong to this MCP task")
        from oak.historical_replay import inference_admission

        admission = inference_admission(self.store, identity)
        if not admission["allowed"]:
            raise ValueError(
                f"Kernel has not passed historical preservation: {admission['reason']}"
            )
        assessment = kernel.get("assessment", {})
        if (
            kernel.get("validation", {}).get("valid") is not True
            or assessment.get("logical_validity") != "passed"
            or assessment.get("function_execution") != "passed"
        ):
            raise ValueError("Kernel has not passed the existing ontology and function gates")
        functions = validate_functions(kernel["functions"], kernel["schema"])
        evidence = kernel.get("evidence", {})
        if not evidence.get("probes_id"):
            raise ValueError("Kernel is missing real function probe evidence")
        probes = self._artifact(evidence["probes_id"])
        if (
            not isinstance(probes, list)
            or not probes
            or any(p.get("status") != "passed" for p in probes)
        ):
            raise ValueError("Kernel function probes did not pass")
        covered = {probe.get("probe", {}).get("function") for probe in probes}
        if covered != {function.name for function in functions}:
            raise ValueError("Kernel probes do not cover its function catalog")
        return kernel

    def submit(
        self,
        task_id: str,
        operation: str,
        key: str,
        *,
        kernel_id: str | None = None,
        query: str | None = None,
        requirements: list[str] | None = None,
        query_id: str | None = None,
    ) -> dict:
        """Queue bounded construction or fresh frozen inference idempotently."""
        surface_id = self._surface_id(task_id)
        data = self._surface(surface_id)
        surface = TaskSurface.model_validate(data["configuration"])
        if operation not in {"construct", "infer"}:
            raise ValueError("Operation must be construct or infer")
        inputs: dict[str, Any] = {"surface_id": surface_id, "operation": operation}
        if operation == "construct":
            if any(value is not None for value in (kernel_id, query, requirements, query_id)):
                raise ValueError(
                    "Construction uses the saved curated pool without inference arguments"
                )
        else:
            if not kernel_id or ((query is None) == (query_id is None)):
                raise ValueError("Inference requires a kernel and exactly one query or query_id")
            self._kernel(kernel_id, surface_id)
            inputs["kernel_id"] = kernel_id
            if query is not None:
                if not isinstance(query, str) or not query.strip():
                    raise ValueError("Inference query must be nonempty")
                digest = hashlib.sha256(canonical([key, query, requirements or []])).hexdigest()[
                    :24
                ]
                local = InferenceQuery(
                    id=f"inference-{digest}", query=query, requirements=requirements or []
                )
                inputs["inference_query"] = local.model_dump(mode="json")
            else:
                if requirements is not None:
                    raise ValueError("Registered query requirements cannot be overwritten")
                if not any(item.id == query_id for item in surface.queries):
                    raise ValueError("Query is absent from the declared surface")
                inputs["query_id"] = query_id
        return self._enqueue(surface_id, operation, inputs, key)

    def _enqueue(self, task_id: str | None, operation: str, inputs: dict, key: str) -> dict:
        if not isinstance(key, str) or not key.strip() or len(key) > 200:
            raise ValueError("An idempotency key of 1 to 200 characters is required")
        request_hash = hashlib.sha256(
            canonical({"task_id": task_id, "operation": operation, "inputs": inputs})
        ).hexdigest()
        with self._lock():
            previous = self.store.rows("SELECT * FROM web_jobs WHERE idempotency_key=?", (key,))
            if previous:
                if previous[0]["request_sha256"] != request_hash:
                    raise WebJobError(
                        "idempotency_conflict",
                        "This idempotency key belongs to a different request",
                    )
                return self._accepted(previous[0]["run_id"], reused=True)
            if task_id:
                active = self.store.rows(
                    "SELECT id FROM runs WHERE task_id=? AND status IN ('queued','running')",
                    (task_id,),
                )
                if active:
                    raise WebJobError(
                        "active_run_conflict",
                        "This task already has active work",
                        evidence_refs=[active[0]["id"]],
                    )
                data = self._surface(task_id)
                budget = self.store.budget(runtime_config()["total_budget_usd"])
                if budget["estimated_usd"] + budget["reserved_usd"] >= min(
                    budget["limit_usd"], data["budget_ceiling_usd"]
                ):
                    raise WebJobError(
                        "budget_exhausted",
                        "The task campaign or global spending limit is exhausted",
                    )
            identity = uuid.uuid4().hex
            owner_token = uuid.uuid4().hex
            kind = {
                "discover": "mcp_discovery",
                "construct": "mcp_construct",
                "infer": "mcp_episode",
            }[operation]
            input_id = self.store.put(
                "run_input", {**inputs, "implementation": implementation_receipt()}
            )
            with self.store.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO runs(id,task_id,kind,status,created_at,input_id,root_run_id,owner_run_id,owner_kind) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        identity,
                        task_id or f"connector:{identity}",
                        kind,
                        "queued",
                        now(),
                        input_id,
                        identity,
                        identity,
                        "web",
                    ),
                )
                connection.execute(
                    "INSERT INTO web_jobs(run_id,operation,idempotency_key,request_sha256,owner_token) VALUES(?,?,?,?,?)",
                    (identity, operation, key, request_hash, owner_token),
                )
                connection.execute(
                    "INSERT INTO events(run_id,time,stage,status,summary,artifact_id) VALUES(?,?,?,?,?,?)",
                    (
                        identity,
                        now(),
                        "request",
                        "queued",
                        f"{operation.capitalize()} requested",
                        input_id,
                    ),
                )
            try:
                self._spawn(identity, owner_token)
            except (OSError, subprocess.SubprocessError) as error:
                self.store.set_run(identity, "failed", error=redact_diagnostic(str(error)))
                raise WebJobError(
                    "worker_launch_failed",
                    "Could not start the saved worker",
                    evidence_refs=[identity],
                ) from error
            return self._accepted(identity, reused=False)

    def _spawn(self, run_id: str, owner_token: str) -> None:
        directory = self.root / "web-jobs"
        directory.mkdir(exist_ok=True)
        with (directory / f"{run_id}.log").open("a") as output:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "oak.cli",
                    "web-worker",
                    "--run-id",
                    run_id,
                    "--root",
                    str(self.root),
                ],
                cwd=Path(__file__).resolve().parents[2],
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env={**os.environ, "OAK_WEB_WORKER_TOKEN": owner_token},
            )
        with self.store.connect() as connection:
            connection.execute(
                "UPDATE web_jobs SET pid=?,process_started_at=? WHERE run_id=?",
                (process.pid, _process_identity(process.pid), run_id),
            )

    def run_worker(self, run_id: str) -> dict:
        """Claim and execute a saved request once, retaining real terminal evidence."""
        if not run_id or any(character not in "0123456789abcdef" for character in run_id):
            raise ValueError("Invalid web run identity")
        directory = self.root / "web-jobs"
        directory.mkdir(exist_ok=True)
        with (directory / f"{run_id}.lock").open("a") as lease:
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError("This web request already has a live worker") from error
            return self._run_owned(run_id)

    def _run_owned(self, run_id: str) -> dict:
        """Execute while the unique per-run process lease remains held."""
        with self._lock():
            rows = self.store.rows(
                "SELECT r.*,j.operation,j.owner_token,j.pid FROM runs r "
                "JOIN web_jobs j ON j.run_id=r.id WHERE r.id=?",
                (run_id,),
            )
            if not rows:
                raise ValueError("Unknown web worker request")
            row = rows[0]
            if row["status"] != "queued":
                raise ValueError("Only a queued web request may execute")
            if (
                row["pid"] != os.getpid()
                or os.environ.get("OAK_WEB_WORKER_TOKEN") != row["owner_token"]
            ):
                raise ValueError("This process does not own the saved web request")
            self.store.set_run(run_id, "running")
        try:
            inputs = self._artifact(row["input_id"])
            if row["operation"] == "discover":
                bridge = MCPBridge([inputs["connection"]], self.store, run_id, discovery_only=True)
                catalog = bridge.discover()
                result = {
                    "discovery_id": run_id,
                    "connection": inputs["connection"],
                    "catalog": catalog,
                }
                self.store.set_run(run_id, "completed", result=result)
            else:
                engine = SurfaceEngine(self.root)
                if row["operation"] == "construct":
                    result = engine.construct(inputs["surface_id"], run_id=run_id)
                else:
                    self._kernel(inputs["kernel_id"], inputs["surface_id"])
                    result = engine.run_episode(
                        inputs["surface_id"],
                        inputs.get("query_id"),
                        kernel_id=inputs["kernel_id"],
                        inference_query=inputs.get("inference_query"),
                        run_id=run_id,
                    )
            return result
        except BaseException as error:
            message = redact_diagnostic(f"{type(error).__name__}: {error}")
            status = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
            evidence = self.store.event(
                run_id,
                "worker_error",
                "failed",
                "Worker stopped",
                {
                    "type": type(error).__name__,
                    "message": message,
                    "code": getattr(error, "code", "execution_failed"),
                    "retryable": getattr(error, "retryable", False),
                    "evidence_refs": getattr(error, "evidence_refs", []),
                },
            )
            self.store.set_run(
                run_id,
                status,
                error=message,
            )
            return {"run_id": run_id, "status": status, "error": message, "evidence_id": evidence}

    def reconcile(self) -> list[dict]:
        """Mark actually exited owned workers and their active children interrupted.

        This runs on the server's maintenance timer, never from a read method.
        A missing owner is not permission to repeat model or MCP work.
        """
        changed = []
        with self._lock():
            jobs = self.store.rows(
                "SELECT r.id,r.status,r.created_at,j.pid,j.process_started_at FROM runs r JOIN web_jobs j ON j.run_id=r.id "
                "WHERE r.status IN ('queued','running') OR EXISTS ("
                "SELECT 1 FROM runs child WHERE child.owner_run_id=r.id "
                "AND child.id<>r.id AND child.status IN ('queued','running'))"
            )
            for job in jobs:
                alive = False
                launch_expired = (
                    job["status"] == "queued"
                    and (
                        datetime.now(UTC) - datetime.fromisoformat(job["created_at"])
                    ).total_seconds()
                    > 30
                )
                if job["status"] != "queued":
                    path = self.root / "web-jobs" / f"{job['id']}.lock"
                    if path.exists():
                        with path.open("a") as lease:
                            try:
                                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            except BlockingIOError:
                                alive = True
                    if alive:
                        continue
                if job["pid"]:
                    try:
                        exited, _ = os.waitpid(job["pid"], os.WNOHANG)
                    except ChildProcessError:
                        exited = 0
                    if not exited and job["status"] == "queued" and not launch_expired:
                        identity = _process_identity(job["pid"])
                        if identity is not None:
                            alive = (
                                job["process_started_at"] is None
                                or identity == job["process_started_at"]
                            )
                        elif job["process_started_at"] is None:
                            try:
                                os.kill(job["pid"], 0)
                                alive = True
                            except ProcessLookupError:
                                pass
                            except PermissionError:
                                alive = True
                if alive:
                    continue
                rows = self.store.rows(
                    "SELECT id FROM runs WHERE (id=? OR owner_run_id=?) AND status IN ('queued','running')",
                    (job["id"], job["id"]),
                )
                for row in rows:
                    self.store.set_run(
                        row["id"],
                        "interrupted",
                        error=(
                            "Worker did not claim its request within 30 seconds; external work was not started"
                            if launch_expired
                            else "Worker exited before saving a terminal result; external work was not repeated"
                        ),
                    )
                    changed.append({"run_id": row["id"], "status": "interrupted"})
        return changed

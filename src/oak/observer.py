"""Read-only, versioned projections of genuine OaK runs and artifacts.

The observer opens SQLite in read-only mode and never starts jobs, reconciles
workers, changes a kernel, or invokes a model or MCP server. Replay uses durable
event IDs. A sanitized response has its own projection hash; the source hash
always identifies the untouched stored artifact.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from oak import api_contracts as contracts
from oak.api_contracts import (
    ArtifactResponse,
    ConstructionAttempt,
    EventEnvelope,
    EventsResponse,
    GraphResponse,
    HistoryResponse,
    KernelDiffResponse,
    KernelResponse,
    KernelSummary,
    RunResponse,
    RunSummary,
    TaskListResponse,
    TaskResponse,
    TaskSummary,
    WorkspaceResponse,
)
from oak.historical_replay import inference_admission
from oak.model import redact_diagnostic, runtime_config
from oak.ontology_view import humanize, instance_view, schema_view
from oak.store import canonical

_ARTIFACT_ID = re.compile(r"^[a-f0-9]{64}$")
_ROW_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SECRET_KEY = re.compile(
    r"^(?:_?(?:access|refresh|id)[_-]?token|token|password|passwd|secret|client[_-]?(?:secret|id)|"
    r"api[_-]?key|authorization|proxy[_-]?authorization|private[_-]?key|credentials?)$",
    re.I,
)
_OMITTED_KEYS = {
    "stdout",
    "stderr",
    "stdout_tail",
    "stderr_tail",
    "raw_stdout",
    "raw_stderr",
    "environment",
    "env",
    "env_refs",
    "command",
    "cwd",
    "work_directory",
    "runtime_directory",
    "system_prompt",
    "launch_prompt",
    "application_prompt",
    "application_payload",
    "isolation_inspection",
    "raw_payload_base64",
}
_LOCAL_PATH = re.compile(r"(?:file://)?/(?:Users|home|private|tmp|var|opt|Volumes)/[^\s\"'<>]*")
_WINDOWS_PATH = re.compile(r"[A-Za-z]:\\(?:[^\s\"'<>]+)")
_LIFECYCLE = {"queued", "running", "completed", "failed", "interrupted"}


def sanitize_public(value: Any) -> tuple[Any, list[str]]:
    """Redact credentials, local paths, and raw diagnostics in a derived view.

    Field paths describe every transformation. Strings containing serialized
    diagnostics still pass through credential redaction before publication.
    """
    removed: list[str] = []

    def visit(item: Any, path: str = "$") -> Any:
        if isinstance(item, dict):
            result = {}
            provider_request = bool(item.get("call_id")) and (
                "model_request_attempted" in item or "request_key" in item
            )
            for key, child in item.items():
                location = f"{path}.{key}"
                if (
                    key.lower() in _OMITTED_KEYS
                    or _SECRET_KEY.fullmatch(key)
                    or (provider_request and key == "request")
                ):
                    result[key] = "[redacted]"
                    removed.append(location)
                else:
                    result[key] = visit(child, location)
            return result
        if isinstance(item, list):
            return [visit(child, f"{path}[{index}]") for index, child in enumerate(item)]
        if isinstance(item, str):
            cleaned = _WINDOWS_PATH.sub(
                "[local path]", _LOCAL_PATH.sub("[local path]", redact_diagnostic(item))
            )
            if cleaned != item:
                removed.append(path)
            return cleaned
        return item

    return visit(value), sorted(set(removed))


def normalize_outcome(value: str | None) -> str | None:
    """Translate an agent termination claim without turning it into a score."""
    if value in {"answered", "complete"}:
        return "complete"
    if value in {"clarify", "needs_input"}:
        return "needs_input"
    if value in {"insufficient_evidence", "step_limit", "unresolved"}:
        return "unresolved"
    return None


def _lifecycle(value: str) -> str:
    if value in _LIFECYCLE:
        return value
    if value in {"pending", "starting", "in_progress"}:
        return "running"
    return "interrupted"


def _references(value: Any) -> list[str]:
    """Find artifact-looking references without interpreting arbitrary paths."""
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                isinstance(item, str)
                and _ARTIFACT_ID.fullmatch(item)
                and (key.endswith("_id") or key in {"parent", "kernel_revision", "artifact"})
            ):
                found.add(item)
            elif key.endswith("_ids") and isinstance(item, list):
                found.update(x for x in item if isinstance(x, str) and _ARTIFACT_ID.fullmatch(x))
            elif isinstance(item, (dict, list)):
                found.update(_references(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_references(item))
    return sorted(found)


class _ReplayReader:
    """Expose hash-checked reads to the shared admission rule without a Store writer."""

    def __init__(self, observer):
        self.observer = observer

    def get(self, identity):
        try:
            return self.observer._source(identity)["data"]
        except LookupError as error:
            raise ValueError(str(error)) from error

    def rows(self, query, parameters=()):
        return self.observer._rows(query, parameters)


class Observer:
    """Serve saved evidence without initializing or mutating the workspace."""

    def __init__(self, root: str | Path = ".local"):
        self.root = Path(root).resolve()
        self.database = self.root / "catalog.sqlite"
        self._evaluation_stamp: int | None = None
        self._evaluations: dict[str, list[str]] = {}

    def _rows(self, query: str, parameters: tuple = ()) -> list[dict[str, Any]]:
        if not self.database.exists():
            return []
        with sqlite3.connect(
            self.database.as_uri() + "?mode=ro", uri=True, timeout=10
        ) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            return [dict(row) for row in connection.execute(query, parameters)]

    def _has_table(self, name: str) -> bool:
        return bool(
            self._rows("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
        )

    def _source(self, identity: str) -> dict[str, Any]:
        if not _ARTIFACT_ID.fullmatch(identity):
            raise ValueError("Invalid artifact identifier")
        path = self.root / "artifacts" / f"{identity}.json"
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            raise LookupError("Artifact is not available") from None
        if hashlib.sha256(raw).hexdigest() != identity:
            raise ValueError("Artifact integrity check failed")
        envelope = json.loads(raw)
        if not isinstance(envelope, dict) or "data" not in envelope:
            raise ValueError("Unsupported artifact envelope")
        return envelope

    def _data(self, identity: str | None, default: Any = None) -> Any:
        if not identity:
            return default
        try:
            return self._source(identity)["data"]
        except LookupError:
            return default

    def _run_row(self, identity: str) -> dict[str, Any]:
        if not _ROW_ID.fullmatch(identity):
            raise ValueError("Invalid run identifier")
        rows = self._rows("SELECT * FROM runs WHERE id=?", (identity,))
        if not rows:
            raise LookupError("Run is not available")
        return rows[0]

    def _run_inputs(self, row: dict) -> dict:
        """Join the accepted request to its actual later worker context."""
        result = dict(self._data(row.get("input_id"), {}))
        events = self._rows(
            "SELECT artifact_id FROM events WHERE run_id=? AND stage IN ('construction_request','episode_context') ORDER BY id",
            (row["id"],),
        )
        for event in events:
            actual = self._data(event["artifact_id"], {})
            if isinstance(actual, dict):
                result.update(actual)
        return result

    def _task_key(self, raw: str) -> str:
        if self._has_table("mcp_surfaces") and self._rows(
            "SELECT id FROM mcp_surfaces WHERE id=?", (raw,)
        ):
            return f"mcp:{raw}"
        return f"corpus:{raw}"

    def _split_task_key(self, identity: str) -> tuple[str, str]:
        if ":" in identity:
            kind, raw = identity.split(":", 1)
            if kind not in {"mcp", "corpus"}:
                raise ValueError("Unknown task kind")
        else:
            kind, raw = self._task_key(identity).split(":", 1)
        if not _ROW_ID.fullmatch(raw):
            raise ValueError("Invalid task identifier")
        return kind, raw

    def workspace(self) -> dict[str, Any]:
        """Summarize actual ledger totals and catalog counts."""
        rows = (
            self._rows("SELECT status,reserved,estimated FROM model_calls")
            if self._has_table("model_calls")
            else []
        )
        config = runtime_config()
        limit = float(config["total_budget_usd"])
        estimated = sum(row["estimated"] for row in rows)
        reserved = sum(row["reserved"] for row in rows if row["status"] != "settled")
        return WorkspaceResponse(
            budget={
                "limit_usd": limit,
                "estimated_usd": estimated,
                "reserved_usd": reserved,
                "remaining_usd": max(0.0, limit - estimated - reserved),
                "calls": len(rows),
            },
            task_count=len(self.tasks()["items"]),
            run_count=self._rows("SELECT COUNT(*) AS count FROM runs")[0]["count"]
            if self._has_table("runs")
            else 0,
            model=config.get("model", ""),
        ).model_dump()

    def tasks(self) -> dict[str, Any]:
        """List MCP surfaces and legacy corpus tasks without reconciling jobs."""
        items = []
        if self._has_table("tasks"):
            items.extend(
                self._task_summary("corpus", row["id"])
                for row in self._rows("SELECT id FROM tasks")
            )
        if self._has_table("mcp_surfaces"):
            items.extend(
                self._task_summary("mcp", row["id"])
                for row in self._rows("SELECT id FROM mcp_surfaces")
            )
        items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return TaskListResponse(items=items).model_dump()

    def _task_record(self, kind: str, raw: str) -> tuple[dict, dict]:
        table = "mcp_surfaces" if kind == "mcp" else "tasks"
        rows = (
            self._rows(f"SELECT * FROM {table} WHERE id=?", (raw,))
            if self._has_table(table)
            else []
        )
        if not rows:
            raise LookupError("Task is not available")
        row = rows[0]
        data = self._data(row["artifact_id"], {}) if kind == "mcp" else json.loads(row["data"])
        return row, data

    def _kernel_ids(self, kind: str, raw: str) -> list[str]:
        if kind == "corpus":
            return [
                row["id"]
                for row in self._rows(
                    "SELECT id FROM revisions WHERE task_id=? ORDER BY created_at DESC", (raw,)
                )
            ]
        ids = []
        for row in self._rows(
            "SELECT result_id FROM runs WHERE task_id=? AND kind='mcp_construct' ORDER BY created_at DESC",
            (raw,),
        ):
            result = self._data(row["result_id"], {})
            if isinstance(result, dict) and result.get("kernel_id"):
                ids.append(result["kernel_id"])
        return list(dict.fromkeys(ids))

    def _task_summary(self, kind: str, raw: str) -> dict[str, Any]:
        row, record = self._task_record(kind, raw)
        configuration = record.get("configuration", {}) if kind == "mcp" else record
        ids = self._kernel_ids(kind, raw)
        selected_kernel_id = None
        if kind == "mcp":
            for run in self._rows(
                "SELECT result_id FROM runs WHERE task_id=? AND kind='mcp_construct' AND status='completed' ORDER BY created_at DESC",
                (raw,),
            ):
                result = self._data(run["result_id"], {})
                if result.get("selection_id"):
                    selected_kernel_id = result.get("kernel_id")
                    break
        count = self._rows("SELECT COUNT(*) AS count FROM runs WHERE task_id=?", (raw,))[0]["count"]
        data, _ = sanitize_public(
            {
                "id": f"{kind}:{raw}",
                "kind": kind,
                "name": configuration.get("name", configuration.get("title", "Untitled task")),
                "description": configuration.get("description", configuration.get("scope", "")),
                "created_at": record.get("created_at"),
                "legacy": kind == "corpus",
                "status": "history_only"
                if kind == "corpus"
                else ("candidate_available" if ids else "configured"),
                "active_kernel_id": row.get("active_revision"),
                "latest_kernel_id": ids[0] if ids else None,
                "selected_kernel_id": selected_kernel_id,
                "run_count": count,
                "query_count": len(
                    configuration.get("queries", configuration.get("example_queries", []))
                ),
            }
        )
        return TaskSummary(**data).model_dump()

    def task(self, identity: str) -> dict[str, Any]:
        """Return public task setup, never evaluator labels or secret values."""
        kind, raw = self._split_task_key(identity)
        _, record = self._task_record(kind, raw)
        config = record.get("configuration", {}) if kind == "mcp" else record
        queries = (
            config.get("queries", [])
            if kind == "mcp"
            else [
                {
                    "id": f"construction-{index + 1}",
                    "query": query,
                    "split": "construction",
                    "requirements": [],
                }
                for index, query in enumerate(config.get("example_queries", []))
            ]
        )
        connections = []
        for server in config.get("servers", []):
            connections.append(
                {
                    key: server[key]
                    for key in ("name", "transport", "url", "allowed_tools", "timeout_seconds")
                    if key in server
                }
            )
        details, _ = sanitize_public(
            {
                **self._task_summary(kind, raw),
                "base_prompt": config.get("base_prompt", ""),
                "queries": queries,
                "connections": connections,
                "limits": config.get("limits", {}),
                "capabilities": record.get("catalog", {}).get("tools", []),
                "limitations": ["Legacy corpus tasks are available for history and replay."]
                if kind == "corpus"
                else [],
            }
        )
        return TaskResponse(**details).model_dump()

    def _episode(self, result: dict) -> dict:
        if isinstance(result.get("episode"), dict):
            return result["episode"]
        return self._data(result.get("episode_id"), {}) if result.get("episode_id") else result

    def _assessment(self, result: dict, run_id: str) -> dict:
        """Use independent recorded scores when present, never agent confidence."""
        checks = self._rows(
            "SELECT artifact_id FROM events WHERE run_id=? AND (stage LIKE '%evaluation%' OR stage LIKE '%score%') ORDER BY id DESC",
            (run_id,),
        )
        candidates = [
            {**self._data(row["artifact_id"], {}), "artifact_id": row["artifact_id"]}
            for row in checks
        ]
        # Existing weather scores were stored as artifacts without event rows.
        episode_id = result.get("episode_id")
        if episode_id:
            folder = self.root / "artifacts"
            stamp = folder.stat().st_mtime_ns if folder.exists() else 0
            if stamp != self._evaluation_stamp:
                self._evaluations = {}
                for path in folder.glob("*.json"):
                    if path.stat().st_size > 200_000:
                        continue
                    try:
                        envelope = json.loads(path.read_bytes())
                    except (OSError, ValueError):
                        continue
                    if envelope.get("kind") == "weather_evaluation":
                        linked = envelope.get("data", {}).get("episode_id")
                        if linked:
                            self._evaluations.setdefault(linked, []).append(path.stem)
                self._evaluation_stamp = stamp
            for identity in self._evaluations.get(episode_id, []):
                candidates.insert(0, {**self._source(identity)["data"], "artifact_id": identity})
        for candidate in candidates:
            registered = candidate.get("assessment", {}) if isinstance(candidate, dict) else {}
            if registered.get("status") in {"not_checked", "passed", "failed", "unable_to_check"}:
                return {
                    **{
                        key: registered.get(key)
                        for key in ("status", "evaluator", "evaluator_version", "result", "scope")
                    },
                    "evidence_refs": list(
                        dict.fromkeys(
                            [
                                *registered.get("evidence_refs", []),
                                *(
                                    [candidate["artifact_id"]]
                                    if candidate.get("artifact_id")
                                    else []
                                ),
                            ]
                        )
                    ),
                    "details": {"evaluation": candidate.get("evaluation", {})},
                }
            evaluation = (
                candidate.get("evaluation", candidate) if isinstance(candidate, dict) else {}
            )
            if "success" in evaluation and evaluation.get("status") in {"scored", "unscored"}:
                return {
                    "status": "unable_to_check"
                    if evaluation["status"] == "unscored"
                    else ("passed" if evaluation["success"] else "failed"),
                    "evaluator": "weather"
                    if evaluation.get("evaluator_version", "").startswith("weather")
                    else evaluation.get("evaluator"),
                    "evaluator_version": evaluation.get("evaluator_version"),
                    "result": evaluation.get("success"),
                    "scope": evaluation.get("scope"),
                    "evidence_refs": [candidate["artifact_id"]]
                    if candidate.get("artifact_id")
                    else [],
                    "details": candidate,
                }
        saved = result.get("assessment", {})
        if isinstance(saved, dict):
            scored = [
                item.get("score")
                for item in saved.get("construction_results", [])
                if item.get("score") is not None
            ]
            if scored:
                return {
                    "status": "passed"
                    if all(score is True or score == 1 for score in scored)
                    else "failed",
                    "scope": "Recorded construction cases",
                    "result": {
                        "passed": sum(score is True or score == 1 for score in scored),
                        "total": len(scored),
                    },
                    "details": {"recorded": saved},
                }
        return {"status": "not_checked", "details": {"recorded": saved}}

    def _initial_graph(self, run_id: str) -> str | None:
        """Read the genuine primitive initial MCP checkpoint without resuming it."""
        path = self.root / "mcp-checkpoints.sqlite"
        if not path.is_file():
            return None
        import ormsgpack

        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
            rows = connection.execute(
                "SELECT type,checkpoint FROM checkpoints WHERE thread_id=? ORDER BY checkpoint_id LIMIT 2",
                (run_id,),
            ).fetchall()
        for encoding, raw in rows:
            if encoding == "msgpack":
                try:
                    checkpoint = ormsgpack.unpackb(raw)
                except ValueError:
                    continue
            elif encoding == "json":
                checkpoint = json.loads(raw)
            else:
                continue
            values = checkpoint.get("channel_values", {})
            state = values.get("__start__", values)
            if isinstance(state, dict) and state.get("graph_id"):
                identity = state["graph_id"]
                if self._data(identity) is not None:
                    return identity
        return None

    def _run_summary(self, row: dict) -> dict:
        inputs = self._run_inputs(row)
        result = self._data(row.get("result_id"), {})
        result = result if isinstance(result, dict) else {}
        episode = self._episode(result)
        query_input = inputs.get("query", inputs.get("context", {}).get("query")) or inputs.get(
            "inference_query", {}
        ).get("query")
        if isinstance(query_input, dict):
            query_input = query_input.get("query")
        kernel_id = (
            inputs.get("kernel_id")
            or episode.get("kernel_revision")
            or result.get("kernel_id")
            or result.get("revision_id")
        )
        data, _ = sanitize_public(
            {
                "id": row["id"],
                "task_id": self._task_key(row["task_id"]),
                "kind": row["kind"],
                "status": _lifecycle(row["status"]),
                "created_at": row["created_at"],
                "query": episode.get("query") or query_input,
                "query_id": episode.get("query_id")
                or inputs.get("query_id")
                or inputs.get("inference_query", {}).get("id"),
                "split": episode.get("split") or inputs.get("inference_query", {}).get("split"),
                "kernel_id": kernel_id,
                "root_run_id": row.get("root_run_id"),
                "parent_run_id": row.get("parent_run_id"),
                "answer": episode.get("answer"),
                "outcome": normalize_outcome(episode.get("status")),
                "assessment": self._assessment(result, row["id"]),
            }
        )
        return RunSummary(**data).model_dump()

    def _run_family(self, row: dict) -> list[str]:
        columns = {item["name"] for item in self._rows("PRAGMA table_info(runs)")}
        if "root_run_id" not in columns:
            return [row["id"]]
        children = self._rows(
            "SELECT id FROM runs WHERE root_run_id=? OR parent_run_id=?", (row["id"], row["id"])
        )
        return list(dict.fromkeys([row["id"], *(child["id"] for child in children)]))

    def run(self, identity: str) -> dict[str, Any]:
        """Read one run and its available replay boundary."""
        row = self._run_row(identity)
        inputs = self._run_inputs(row)
        result = self._data(row.get("result_id"), {})
        episode = self._episode(result) if isinstance(result, dict) else {}
        family = self._run_family(row)
        placeholders = ",".join("?" for _ in family)
        stats = self._rows(
            f"SELECT COUNT(*) AS count,MAX(id) AS last FROM events WHERE run_id IN ({placeholders})",
            tuple(family),
        )[0]
        graph_id = episode.get("graph_id")
        kernel_id = self._run_summary(row)["kernel_id"]
        if not graph_id and kernel_id:
            kernel = self._data(kernel_id, {})
            graph_id = (
                kernel_id if "graph" in kernel else kernel.get("evidence", {}).get("graph_id")
            )
        initial = inputs.get("graph_id")
        if not initial:
            request_events = self._rows(
                "SELECT artifact_id FROM events WHERE run_id=? AND stage='episode_start' ORDER BY id LIMIT 1",
                (identity,),
            )
            if request_events:
                initial = self._data(request_events[0]["artifact_id"], {}).get("graph_id")
        if not initial and row["kind"] == "mcp_episode":
            initial = self._initial_graph(identity)
        if (
            not initial
            and row["kind"] == "ask"
            and kernel_id
            and "graph" in self._data(kernel_id, {})
        ):
            initial = kernel_id
        limitations = []
        if row.get("root_run_id") is None:
            limitations.append("This older run has no recorded parent/root lineage.")
        if not graph_id:
            limitations.append("No completed graph snapshot is recorded for this run.")
        usage_rows = self._rows(
            "SELECT status,reserved,estimated FROM model_calls WHERE run_id=?", (identity,)
        )
        data, _ = sanitize_public(
            {
                **self._run_summary(row),
                "event_count": stats["count"],
                "last_cursor": str(stats["last"] or 0),
                "artifact_refs": [
                    value
                    for value in (
                        row.get("input_id"),
                        row.get("result_id"),
                        result.get("episode_id"),
                    )
                    if value
                ],
                "limitations": limitations,
                "graph_id": graph_id,
                "initial_graph_id": initial,
                "error": row.get("error"),
                "usage": {
                    "calls": len(usage_rows),
                    "estimated_usd": sum(item["estimated"] for item in usage_rows),
                    "reserved_usd": sum(
                        item["reserved"] for item in usage_rows if item["status"] != "settled"
                    ),
                },
            }
        )
        return RunResponse(**data).model_dump()

    def _case_links(self, kernel: dict) -> list[dict]:
        sample = kernel.get("sample", {})
        if sample:
            episodes = {}
            for episode_id in self._data(kernel.get("evidence", {}).get("episodes_id"), []):
                episode = self._data(episode_id, {})
                episodes[episode.get("query_id")] = {
                    "episode_id": episode_id,
                    "query": episode.get("query"),
                }
            rows = self._rows(
                "SELECT id,result_id FROM runs WHERE task_id=? AND kind='mcp_episode'",
                (kernel.get("surface_id"),),
            )
            run_ids = {
                result.get("episode_id"): row["id"]
                for row in rows
                if (result := self._data(row["result_id"], {})).get("episode_id")
            }
            return [
                {
                    "id": identity,
                    "split": "construction",
                    **episodes.get(identity, {}),
                    "episode_run_id": run_ids.get(episodes.get(identity, {}).get("episode_id")),
                }
                for identity in sample.get("selected_query_ids", [])
            ]
        return [
            {"id": f"construction-{index + 1}", "query": query, "split": "construction"}
            for index, query in enumerate(kernel.get("queries", []))
        ]

    def _kernel_summary(self, identity: str) -> dict:
        data = self._data(identity)
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("schema"), dict)
            or "functions" not in data
        ):
            raise LookupError("Kernel is not available")
        task = data.get("surface_id") or data.get("task_id")
        kind = "mcp" if data.get("surface_id") else "corpus"
        replay_admission = inference_admission(_ReplayReader(self), identity)
        flow_evidence = {
            flow: [
                value
                for name in names
                if isinstance(value := data.get("evidence", {}).get(name), str)
                and _ARTIFACT_ID.fullmatch(value)
            ]
            for flow, names in {
                "learning": (
                    "task_ir_id",
                    "learning_id",
                    "demands_id",
                    "behavior_bank_id",
                    "behavior_bindings_id",
                    "behavior_input_id",
                    "compilation_id",
                ),
                "verification": ("verification_id", "preservation_id"),
                "instantiation": ("materialization_id", "coverage_id", "sufficiency_id"),
            }.items()
        }
        # Post-candidate checks cannot be embedded in the candidate they hash.
        # Resolve recorded relationships without rewriting frozen artifacts.
        for row in self._rows(
            "SELECT e.stage,e.artifact_id FROM events e JOIN runs r ON r.id=e.run_id "
            "WHERE r.task_id=? AND e.stage IN ('candidate_verification','candidate_selection',"
            "'evaluation_plan','selective_evaluation','historical_replay') ORDER BY e.id",
            (task,),
        ):
            evidence = self._data(row["artifact_id"], {})
            if row["stage"] == "historical_replay" and evidence.get("kernel_id") == identity:
                for name in ("report_id", "bank_id"):
                    reference = evidence.get(name)
                    if isinstance(reference, str) and _ARTIFACT_ID.fullmatch(reference):
                        flow_evidence["verification"].append(reference)
            if row["stage"] == "candidate_verification" and evidence.get("kernel_id") == identity:
                reference = evidence.get("verification_id")
                if isinstance(reference, str) and _ARTIFACT_ID.fullmatch(reference):
                    flow_evidence["verification"].append(reference)
            if row["stage"] == "candidate_selection" and identity in evidence.get(
                "candidate_ids", []
            ):
                reference = evidence.get("selection_id")
                if isinstance(reference, str) and _ARTIFACT_ID.fullmatch(reference):
                    flow_evidence["learning"].append(reference)
            if (
                row["stage"] in {"evaluation_plan", "selective_evaluation"}
                and evidence.get("kernel_id", evidence.get("candidate_id")) == identity
            ):
                reference = evidence.get("evaluation_plan_id") or evidence.get(
                    "evaluation_receipt_id"
                )
                if isinstance(reference, str) and _ARTIFACT_ID.fullmatch(reference):
                    flow_evidence["verification"].append(reference)
        result, _ = sanitize_public(
            {
                "id": identity,
                "task_id": f"{kind}:{task}",
                "parent_id": data.get("parent"),
                "created_at": data.get("created_at"),
                "run_id": data.get("run_id"),
                "name": humanize(data["schema"].get("name", "Kernel")),
                "assessment": {
                    "status": "not_checked",
                    "details": {"recorded": data.get("assessment", {})},
                },
                "eligible_for_inference": kind == "mcp"
                and bool(data.get("validation", {}).get("valid"))
                and data.get("assessment", {}).get("function_execution") == "passed"
                and replay_admission["allowed"],
                "validation": {
                    **{
                        key: data.get("validation", {})[key]
                        for key in ("valid", "status", "coverage", "evidence_type")
                        if key in data.get("validation", {})
                    },
                    "historical_replay": replay_admission,
                },
                "case_links": self._case_links(data),
                "schema_id": data.get("evidence", {}).get("schema_id"),
                "graph_id": data.get("evidence", {}).get("graph_id")
                or (identity if "graph" in data else None),
                "construction_profile": data.get("construction_profile"),
                "flow_evidence": {
                    key: list(dict.fromkeys(refs)) for key, refs in flow_evidence.items()
                },
            }
        )
        return KernelSummary(**result).model_dump()

    def kernel(self, identity: str) -> dict[str, Any]:
        """Expose recorded S/F and readable declarations with their exact source."""
        summary = self._kernel_summary(identity)
        data = self._data(identity)
        graph = data.get("graph") or self._data(data.get("evidence", {}).get("graph_id"))
        public, _ = sanitize_public(
            {
                **summary,
                "schema": data["schema"],
                "functions": data["functions"],
                "acquisition_bindings": data.get("acquisition_bindings", []),
                "schema_view": schema_view(data["schema"], graph),
                "artifact_refs": sorted(set([identity, *_references(data.get("evidence", {}))])),
                "limitations": [
                    "Kernel assessment and independent task scores are distinct evidence."
                ]
                + (
                    [summary["validation"]["historical_replay"]["reason"]]
                    if not summary["validation"]["historical_replay"]["allowed"]
                    else []
                ),
            }
        )
        return KernelResponse(**public).model_dump()

    def _attempt(self, row: dict, kernels: list[dict]) -> dict:
        inputs = self._run_inputs(row)
        kernel = next((item for item in kernels if item["run_id"] == row["id"]), None)
        schema_id = kernel.get("schema_id") if kernel else None
        schema = self._data(schema_id) if schema_id else None
        schema_ref = schema_id
        validation = {}
        limitations = []
        events = self._rows(
            "SELECT stage,artifact_id FROM events WHERE run_id=? AND stage IN ('schema','ontology_validation') ORDER BY id DESC",
            (row["id"],),
        )
        for event in events:
            value = self._data(event["artifact_id"], {})
            if schema is None and isinstance(value, dict) and value.get("schema_artifact_id"):
                schema_id = value["schema_artifact_id"]
                schema = self._data(schema_id)
                schema_ref = event["artifact_id"]
            if event["stage"] == "ontology_validation" and not validation:
                validation = {
                    key: value[key]
                    for key in (
                        "valid",
                        "status",
                        "evidence_type",
                        "coverage",
                        "unsatisfiable_classes",
                    )
                    if key in value
                }
            if schema is None and isinstance(value, dict) and "entity_types" in value:
                schema, schema_id, schema_ref = value, event["artifact_id"], event["artifact_id"]
            if schema is None and isinstance(value, dict) and isinstance(value.get("schema"), dict):
                source = value["schema"]
                if source.get("path") and source.get("sha256"):
                    path = Path(source["path"]).resolve()
                    if path.is_relative_to(self.root / "reasoner") and path.is_file():
                        raw = path.read_bytes()
                        if hashlib.sha256(raw).hexdigest() == source["sha256"]:
                            schema = json.loads(raw)
                            schema_ref = event["artifact_id"]
        sample = inputs.get("sample", {})
        cases = (
            kernel["case_links"]
            if kernel
            else [
                {"id": identity, "split": "construction"}
                for identity in sample.get("selected_query_ids", [])
            ]
        )
        if not cases:
            cases = [
                {"id": f"construction-{index + 1}", "query": query, "split": "construction"}
                for index, query in enumerate(inputs.get("queries", []))
            ]
        if schema is None:
            limitations.append("No schema definition is available for this attempt.")
        checks = self._rows(
            "SELECT stage,status,artifact_id FROM events WHERE run_id=? AND stage IN ('ontology_validation','function_probes','composition_attempt') ORDER BY id",
            (row["id"],),
        )
        ontology_check = next(
            (item for item in reversed(checks) if item["stage"] == "ontology_validation"), None
        )
        function_check = next(
            (
                item
                for item in reversed(checks)
                if item["stage"] in {"function_probes", "composition_attempt"}
            ),
            None,
        )
        result = self._data(row.get("result_id"), {})
        regression = result.get("regression") or {}
        validation.update(
            {
                "ontology": {
                    "status": "passed"
                    if ontology_check and ontology_check["status"] == "passed"
                    else "failed"
                    if ontology_check
                    else "not_checked",
                    "evidence_refs": [ontology_check["artifact_id"]] if ontology_check else [],
                },
                "functions": {
                    "status": "passed"
                    if function_check and function_check["status"] == "passed"
                    else "failed"
                    if function_check
                    else "not_checked",
                    "evidence_refs": [function_check["artifact_id"]] if function_check else [],
                },
                "task": self._assessment(result, row["id"]),
                "regression": {
                    "status": regression.get("status", "not_checked"),
                    "details": regression,
                },
            }
        )
        public, _ = sanitize_public(
            {
                "run_id": row["id"],
                "status": _lifecycle(row["status"]),
                "created_at": row["created_at"],
                "round_index": sample.get("round_index"),
                "kernel_id": kernel["id"] if kernel else None,
                "parent_kernel_id": (kernel or {}).get("parent_id")
                or inputs.get("parent_id")
                or inputs.get("parent"),
                "case_links": cases,
                "schema_id": schema_id,
                "schema_artifact_ref": schema_ref,
                "schema_view": schema_view(schema) if schema else None,
                "validation": validation,
                "artifact_refs": [event["artifact_id"] for event in events if event["artifact_id"]],
                "limitations": limitations,
            }
        )
        return ConstructionAttempt(**public).model_dump()

    def history(self, identity: str) -> dict[str, Any]:
        """Join attempts to their genuine cases and produced kernels."""
        kind, raw = self._split_task_key(identity)
        self._task_record(kind, raw)
        rows = self._rows("SELECT * FROM runs WHERE task_id=? ORDER BY created_at DESC", (raw,))
        kernels = [self._kernel_summary(key) for key in self._kernel_ids(kind, raw)]
        return HistoryResponse(
            task_id=f"{kind}:{raw}",
            runs=[self._run_summary(row) for row in rows],
            kernels=kernels,
            attempts=[
                self._attempt(row, kernels)
                for row in rows
                if row["kind"] in {"construct", "revise", "mcp_construct"}
                and not self._data(row.get("result_id"), {}).get("selection_id")
            ],
        ).model_dump()

    @staticmethod
    def _event_type(stage: str) -> str:
        if stage in {"request", "lifecycle"}:
            return "run.lifecycle"
        if stage == "kernel_candidate":
            return "kernel.candidate"
        if stage in {"evaluation_plan", "selective_evaluation", "historical_replay"}:
            return "validation.recorded"
        if any(word in stage for word in ("verification", "preservation", "sufficiency")):
            return "validation.recorded"
        if any(word in stage for word in ("learning", "materialization", "evidence_demand")):
            return "evidence.recorded"
        if stage in {"operator", "observation"}:
            return "observation.recorded"
        if "usage" in stage:
            return "usage.recorded"
        if "decision" in stage or ".step" in stage:
            return "decision.recorded"
        if "graph" in stage and "integrity" not in stage:
            return "graph.snapshot"
        if any(word in stage for word in ("evaluation", "score", "judge")):
            return "assessment.recorded"
        if any(word in stage for word in ("validation", "integrity", "probe")):
            return "validation.recorded"
        if any(word in stage for word in ("tool", "function", "mcp_call", "execution")):
            return "observation.recorded"
        if stage in {"schema", "draft", "analyze", "extract", "compose", "freeze"}:
            return "stage.status"
        return "evidence.recorded"

    def _event_payload(self, value: Any, artifact_id: str | None) -> dict:
        if not isinstance(value, dict):
            return {"value": value} if value is not None else {}
        if "nodes" in value and "edges" in value:
            return {
                "graph_id": artifact_id,
                "node_count": len(value["nodes"]),
                "edge_count": len(value["edges"]),
            }
        selected = {
            key: child
            for key, child in value.items()
            if key
            not in {
                "schema",
                "graph",
                "catalog",
                "context",
                "documents",
                "implementation",
                "request",
                "configuration",
                "surface",
            }
        }
        if value.get("execution_id") and "steps" not in selected:
            execution = self._data(value["execution_id"], {})
            if isinstance(execution, dict) and "steps" in execution:
                selected["steps"] = execution["steps"]
        if isinstance(value.get("entity_types"), dict):
            return {
                "schema_id": artifact_id,
                "name": value.get("name"),
                "types": list(value["entity_types"]),
                "relations": list(value.get("relations", {})),
            }
        if "steps" in selected:
            steps = []
            for step in selected["steps"]:
                if not isinstance(step, dict):
                    continue
                output = step.get("output")
                output_entities = (
                    output
                    if isinstance(output, list)
                    else output.get("entities", [])
                    if isinstance(output, dict)
                    else []
                )
                steps.append(
                    {
                        key: step[key]
                        for key in ("id", "operator", "status", "duration_seconds", "error")
                        if key in step
                    }
                    | {
                        "inputs": step.get("inputs", {}),
                        "selected_entity_ids": [
                            node["id"]
                            for node in output_entities
                            if isinstance(node, dict) and "id" in node
                        ][:300],
                        "highlight_node_ids": [
                            node["id"]
                            for node in output_entities
                            if isinstance(node, dict) and "id" in node
                        ][:80],
                        "output": output
                        if not isinstance(output, (dict, list))
                        else {"kind": type(output).__name__, "count": len(output)},
                    }
                )
            selected["steps"] = steps
            selected["highlight_node_ids"] = next(
                (
                    step["highlight_node_ids"]
                    for step in reversed(steps)
                    if step["highlight_node_ids"]
                ),
                [],
            )
        if "functions" in selected and isinstance(selected["functions"], list):
            selected["functions"] = [
                {"name": item.get("name"), "description": item.get("description")}
                for item in selected["functions"]
                if isinstance(item, dict)
            ]
        public, _ = sanitize_public(selected)

        # Nested execution inputs can contain a large graph-derived entity set.
        def bound(item: Any, depth: int = 0) -> Any:
            if isinstance(item, list):
                if item and all(
                    isinstance(child, dict) and {"id", "type", "properties"} <= child.keys()
                    for child in item
                ):
                    return {
                        "entity_ids": [child["id"] for child in item[:80]],
                        "count": len(item),
                        "detail_in_artifact": True,
                    }
                if len(item) > 20:
                    return {
                        "count": len(item),
                        "preview": [bound(x, depth + 1) for x in item[:5]],
                        "truncated": True,
                    }
                return [bound(x, depth + 1) for x in item]
            if isinstance(item, dict):
                if "nodes" in item and "edges" in item:
                    return {
                        "node_count": len(item["nodes"]),
                        "edge_count": len(item["edges"]),
                        "detail_in_artifact": True,
                    }
                if depth > 5:
                    return {"fields": list(item), "detail_in_artifact": True}
                return {key: bound(child, depth + 1) for key, child in item.items()}
            if isinstance(item, str) and len(item) > 2000:
                return item[:2000] + " [truncated; see artifact]"
            return item

        return bound(public)

    def _flow_evidence(self, stage: str, value: Any, artifact_id: str | None) -> dict | None:
        """Project actual flow records before generic payload truncation loses structure."""
        if not isinstance(value, dict) or value.get("flow") not in {
            "learning",
            "verification",
            "instantiation",
        }:
            return None
        view: dict[str, Any] = {"kind": stage, "artifact_id": artifact_id}
        actions, checks, unknowns = [], [], []
        metrics = {}
        if stage == "historical_replay":
            reports = value.get("reports", [])
            if not isinstance(reports, list):
                reports = []
            cases = []
            for report in reports[:30]:
                if not isinstance(report, dict):
                    continue
                try:
                    case_view = {
                        key: report[key]
                        for key in contracts.ReplayCaseView.model_fields
                        if key in report
                    }
                    if isinstance(case_view.get("first_difference"), dict):
                        case_view["first_difference"] = self._event_payload(
                            case_view["first_difference"], None
                        )
                    cases.append(contracts.ReplayCaseView.model_validate(case_view).model_dump())
                except ValidationError:
                    unknowns.append(
                        "A historical replay case lacks valid presentation fields; inspect the original report."
                    )
            try:
                view["historical_replay"] = contracts.HistoricalReplayView.model_validate(
                    {
                        "status": value.get("status"),
                        "allowed": value.get("allowed"),
                        "candidate_kernel_id": value.get("kernel_id"),
                        "report_id": value.get("report_id"),
                        "bank_id": value.get("bank_id"),
                        "case_count": value.get("case_count", len(reports)),
                        "cases": cases,
                        "omitted_cases": max(0, len(reports) - len(cases)),
                        "model_calls": value.get("model_calls"),
                        "live_mcp_calls": value.get("live_mcp_calls"),
                        "feedback": [
                            self._event_payload(item, None)
                            for item in value.get("feedback", [])[:30]
                            if isinstance(item, dict)
                        ],
                    }
                ).model_dump()
            except ValidationError:
                unknowns.append(
                    "Historical replay status is incomplete; inspect the original report before judging preservation."
                )
        if stage == "evaluation_plan":
            for decision in value.get("decisions", []):
                case = decision.get("case", {})
                actions.append(
                    {
                        "case_id": case.get("case_id", "Unidentified recorded case"),
                        "local_action": decision.get("local_action", "unknown"),
                        "planner_action": decision.get("planner_action"),
                        "reasons": decision.get("reasons", []),
                        "planner_reason": decision.get("planner_reason"),
                        "evidence_refs": [decision["previous_receipt_ref"]]
                        if decision.get("previous_receipt_ref")
                        else [],
                    }
                )
            for key in ("estimated_fresh_cost", "max_fresh_cases", "bank_comparable"):
                if key in value:
                    metrics[key] = value[key]
        if stage == "selective_evaluation":
            for case_id, reference in value.get("case_receipt_refs", {}).items():
                receipt = self._data(reference, {})
                if not isinstance(receipt, dict) or not receipt:
                    unknowns.append(f"Missing evaluation receipt for {case_id}")
                    continue
                actions.append(
                    {
                        "case_id": case_id,
                        "local_action": receipt.get("action", "unknown"),
                        "planner_action": receipt.get("planner_exposure"),
                        "status": receipt.get("status"),
                        "reasons": [receipt["summary"]] if receipt.get("summary") else [],
                        "source_candidate_id": receipt.get("source_candidate_id"),
                        "fresh_candidate_id": receipt.get("fresh_candidate_id"),
                        "task_assessment": receipt.get("task_assessment"),
                        "evidence_refs": [reference, *receipt.get("evidence_refs", [])],
                    }
                )
            unknowns.extend(
                f"Deferred: {case_id}" for case_id in value.get("deferred_case_ids", [])
            )
            for key in ("known_regression_case_ids", "preservation_difference_case_ids"):
                if key in value:
                    metrics[key.removesuffix("_case_ids") + "_count"] = len(value[key])
        behavior = value.get("behavior_evaluation") or {}
        if not isinstance(behavior, dict):
            behavior = {}
        for check in [*behavior.get("checks", []), *value.get("checks", [])]:
            if not isinstance(check, dict):
                continue
            checks.append(
                {
                    "id": check.get("behavior_id") or check.get("obligation_id") or check.get("id"),
                    "function_name": check.get("function_name"),
                    "dimension": check.get("dimension", "generated_behavior"),
                    "status": check.get("status", "unknown"),
                    "summary": check.get("summary")
                    or check.get("reason")
                    or check.get("reference_basis")
                    or "Recorded callable check",
                    "evidence_refs": check.get("evidence_refs", []),
                }
            )
        groups = behavior.get("behavior_coverage_by_group") or value.get(
            "behavior_coverage_by_group"
        )
        if groups:
            view["group_results"] = groups
        penalties = behavior.get("penalties", value.get("penalties", []))
        view["penalties"] = [
            f"{item.get('behavior_id', 'Behavior')}: {item.get('reason', 'Recorded penalty')}"
            if isinstance(item, dict)
            else str(item)
            for item in penalties
        ][:30]
        unknowns.extend(value.get("unresolved_obligation_ids", []))
        unknowns.extend(behavior.get("unresolved_behavior_ids", []))
        unknowns.extend(behavior.get("limitations", []))
        if stage == "candidate_selection":
            for key in ("selected_kernel_id", "disposition", "stop_reason"):
                if value.get(key) is not None:
                    metrics[key] = value[key]
        if stage == "candidate_comparison" and isinstance(value.get("comparison"), dict):
            comparison = value["comparison"]
            for key in ("deferred_cases", "unexecuted_previous"):
                unknowns.extend(
                    f"Fresh execution deferred: {identity}" for identity in comparison.get(key, [])
                )
            if comparison.get("boundary_failure"):
                unknowns.append(str(comparison["boundary_failure"]))
            if isinstance(comparison.get("same_source_behavior_comparison"), bool):
                metrics["same_source_behavior_comparison"] = comparison[
                    "same_source_behavior_comparison"
                ]
        for key in ("known_regressions", "mutants_executed", "node_count", "edge_count", "reused"):
            source = behavior if key in behavior else value
            if key in source and isinstance(source[key], (int, float, str, bool)):
                metrics[key] = source[key]
        if value.get("flow") == "instantiation":
            scope = (
                value.get("sufficiency") or value
                if stage == "evidence_scope"
                else value.get("sufficiency")
            )
            if isinstance(scope, dict):
                try:
                    view["scope"] = contracts.SufficiencyResult.model_validate(
                        {
                            key: scope[key]
                            for key in contracts.SufficiencyResult.model_fields
                            if key in scope
                        }
                    ).model_dump()
                except ValidationError:
                    pass
            view["demand_id"] = value.get("demand_id")
            view["expansion_reason"] = value.get("expansion_reason")
            view["receipt_refs"] = value.get("receipt_ids", [])
            unknowns.extend(value.get("unknowns", []))
            demand = value.get("demand")
            if isinstance(demand, dict):
                unknowns.extend(demand.get("unknowns", []))
        view.update(
            actions=actions[:30],
            omitted_actions=max(0, len(actions) - 30),
            checks=checks[:30],
            omitted_checks=max(0, len(checks) - 30),
            remaining_unknowns=list(dict.fromkeys(unknowns))[:30],
            metrics=metrics,
        )
        for field, records, key in (
            ("action_counts", actions, "local_action"),
            ("planner_counts", actions, "planner_action"),
            ("check_counts", checks, "status"),
        ):
            counts: dict[str, int] = {}
            for record in records:
                if record.get(key):
                    counts[record[key]] = counts.get(record[key], 0) + 1
            view[field] = counts
        return contracts.FlowEvidence.model_validate(sanitize_public(view)[0]).model_dump()

    def events(
        self,
        run_id: str,
        after: str | int = "0",
        through: str | int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Page recorded events without inventing intermediate graph snapshots."""
        if not 1 <= limit <= 500:
            raise ValueError("Event limit must be between 1 and 500")
        try:
            cursor = int(after)
            boundary = int(through) if through is not None else None
        except (TypeError, ValueError):
            raise ValueError("Event cursors must be nonnegative integer strings") from None
        if cursor < 0 or (boundary is not None and boundary < 0):
            raise ValueError("Event cursors must be nonnegative")
        row = self._run_row(run_id)
        family = self._run_family(row)
        placeholders = ",".join("?" for _ in family)
        if boundary is None:
            boundary = (
                self._rows(
                    f"SELECT MAX(id) AS last FROM events WHERE run_id IN ({placeholders})",
                    tuple(family),
                )[0]["last"]
                or 0
            )
        rows = self._rows(
            f"SELECT * FROM events WHERE run_id IN ({placeholders}) AND id>? AND id<=? ORDER BY id LIMIT ?",
            (*family, cursor, boundary, limit + 1),
        )
        has_more = len(rows) > limit
        items = []
        for event in rows[:limit]:
            owner = self._run_row(event["run_id"])
            data = self._data(event["artifact_id"], {})
            payload = {"status": event["status"], **self._event_payload(data, event["artifact_id"])}
            refs = [
                {"id": identity, "role": "event" if identity == event["artifact_id"] else "related"}
                for identity in list(
                    dict.fromkeys(
                        [
                            *([event["artifact_id"]] if event["artifact_id"] else []),
                            *_references(data),
                        ]
                    )
                )
            ]
            summary, _ = sanitize_public(event["summary"])
            items.append(
                EventEnvelope(
                    cursor=str(event["id"]),
                    occurred_at=event["time"],
                    task_id=self._task_key(owner["task_id"]),
                    run_id=owner["id"],
                    root_run_id=owner.get("root_run_id"),
                    parent_run_id=owner.get("parent_run_id"),
                    step_id=str(data.get("id"))
                    if isinstance(data, dict) and data.get("id")
                    else None,
                    parent_step_id=None,
                    flow=data.get("flow")
                    if isinstance(data, dict)
                    and data.get("flow") in {"learning", "verification", "instantiation"}
                    else None,
                    type=self._event_type(event["stage"]),
                    stage=event["stage"],
                    summary=summary,
                    artifact_refs=refs,
                    payload=payload,
                    flow_evidence=self._flow_evidence(event["stage"], data, event["artifact_id"]),
                )
            )
        return EventsResponse(
            run_id=run_id,
            items=items,
            next_cursor=items[-1].cursor if items else str(cursor),
            through=str(boundary),
            has_more=has_more,
        ).model_dump()

    def kernel_diff(self, identity: str, against: str) -> dict[str, Any]:
        """Compare exact S/F definitions without asserting semantic equivalence."""
        current, previous = self.kernel(identity), self.kernel(against)
        changes = []

        def compare(left: Any, right: Any, path: str) -> None:
            if isinstance(left, dict) and isinstance(right, dict):
                for key in sorted(left.keys() | right.keys()):
                    child = f"{path}/{key}"
                    if key not in left:
                        changes.append(
                            {"path": child, "change": "added", "before": None, "after": right[key]}
                        )
                    elif key not in right:
                        changes.append(
                            {"path": child, "change": "removed", "before": left[key], "after": None}
                        )
                    else:
                        compare(left[key], right[key], child)
            elif left != right:
                changes.append({"path": path, "change": "changed", "before": left, "after": right})

        compare(previous["schema"], current["schema"], "/schema")
        compare(
            {item["name"]: item for item in previous["functions"]},
            {item["name"]: item for item in current["functions"]},
            "/functions",
        )
        return KernelDiffResponse(
            id=identity,
            against=against,
            changes=changes,
            schema_changed=current["schema"] != previous["schema"],
            functions_changed=current["functions"] != previous["functions"],
            same_task=current["task_id"] == previous["task_id"],
            is_parent=current["parent_id"] == against,
            limitations=[
                "Structural changes do not establish equivalent meaning or attribute a change to one individual construction case."
            ],
        ).model_dump()

    def graph(self, identity: str, focus: str | None = None, limit: int = 80) -> dict[str, Any]:
        """Return actual nodes/edges from a graph or embedded legacy kernel graph."""
        if not 1 <= limit <= 300:
            raise ValueError("Graph limit must be between 1 and 300")
        source = self._source(identity)["data"]
        if not isinstance(source, dict):
            raise ValueError("Artifact is not a graph")
        data = source.get("graph", source)
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("nodes"), list)
            or not isinstance(data.get("edges"), list)
        ):
            raise ValueError("Artifact is not a graph")
        schema = source.get("schema")
        if schema:
            view = instance_view(schema, data, focus_id=focus, max_nodes=limit)
            ids = {node["id"] for node in view["nodes"]}
            labels = {node["id"]: node["label"] for node in view["nodes"]}
        else:
            by_id = {node["id"]: node for node in data["nodes"]}
            if focus and focus not in by_id:
                raise LookupError("Entity is not present in this graph")
            adjacent = {focus} if focus else set()
            if focus:
                for edge in data["edges"]:
                    if edge["source"] == focus:
                        adjacent.add(edge["target"])
                    if edge["target"] == focus:
                        adjacent.add(edge["source"])
            eligible = (
                [
                    by_id[focus],
                    *(
                        node
                        for node in data["nodes"]
                        if node["id"] in adjacent and node["id"] != focus
                    ),
                ]
                if focus
                else data["nodes"]
            )
            ids = {node["id"] for node in eligible[:limit]}
            labels = {}
        nodes = []
        for node in data["nodes"]:
            if node["id"] not in ids:
                continue
            properties = node.get("properties", {})
            candidates = [
                properties.get(key)
                for key in ("name", "city_name", "place", "date", "Date", "location_id", "event_id")
            ]
            label = labels.get(node["id"]) or next(
                (str(value) for value in candidates if value is not None), humanize(node["type"])
            )
            nodes.append({**node, "label": label})
        edges = [
            {**edge, "id": f"edge:{index}", "label": humanize(edge["relation"])}
            for index, edge in enumerate(data["edges"])
            if edge["source"] in ids and edge["target"] in ids
        ][:240]
        public, _ = sanitize_public(
            {
                "id": identity,
                "source_artifact_id": identity,
                "nodes": nodes,
                "edges": edges,
                "total_nodes": len(data["nodes"]),
                "total_edges": len(data["edges"]),
                "shown_nodes": len(nodes),
                "shown_edges": len(edges),
                "omitted_nodes": len(data["nodes"]) - len(nodes),
                "omitted_edges": len(data["edges"]) - len(edges),
                "scope": "Recorded neighbors of the selected entity"
                if focus
                else "Bounded view of recorded graph entities",
                "limitations": [
                    "Selection highlights do not modify the saved graph. Relationships are explicit recorded edges."
                ],
            }
        )
        return GraphResponse(**public).model_dump()

    def _artifact_provenance(self, identity: str) -> dict[str, Any] | None:
        """Join a verified stored artifact to declared portable-export origins.

        The manifest is evidence about an export, not proof of unavailable
        original bytes. Only identical stored/source hashes verify those bytes.
        Database migrations do not invalidate immutable artifact provenance.
        """
        path = self.root / "manifest.json"
        try:
            if path.stat().st_size > 5_000_000:
                return None
            raw = path.read_bytes()
            manifest = json.loads(raw)
        except (OSError, ValueError):
            return None
        if not isinstance(manifest, dict) or manifest.get("format_version") != 1:
            return None
        files = manifest.get("files", {})
        sources = manifest.get("source_artifacts", {})
        if not isinstance(files, dict) or files.get(f"artifacts/{identity}.json") != identity:
            return None
        if not isinstance(sources, dict):
            return None
        origins = []
        for entry in sources.values():
            if not isinstance(entry, dict) or entry.get("exported_artifact_id") != identity:
                continue
            source_hash = entry.get("source_sha256")
            if not isinstance(source_hash, str) or not _ARTIFACT_ID.fullmatch(source_hash):
                continue
            source_id = entry.get("source_artifact_id")
            if source_id and (
                not isinstance(source_id, str) or not _ARTIFACT_ID.fullmatch(source_id)
            ):
                continue
            origins.append(
                {
                    "source_artifact_id": source_id,
                    "source_sha256": source_hash,
                    "relationship": "unchanged"
                    if source_hash == identity
                    else "sanitized_derivative"
                    if source_id
                    else "wrapped_source",
                    "source_bytes_verified": source_hash == identity,
                    "redacted_fields": entry.get("redacted_fields", []),
                    "reference_rewrites": entry.get("reference_rewrites", []),
                    "transformation": entry.get("transformation"),
                }
            )
        if not origins:
            return None
        return sanitize_public(
            {
                "kind": "portable_export",
                "stored_artifact_id": identity,
                "stored_sha256": identity,
                "manifest_sha256": hashlib.sha256(raw).hexdigest(),
                "origins": origins,
                "verification": "Stored bytes match the artifact and manifest hashes. Different origin hashes are export declarations, not independently verified source bytes.",
            }
        )[0]

    def artifact(self, identity: str) -> dict[str, Any]:
        """Inspect a sanitized data view while preserving its stored identity."""
        source = self._source(identity)
        data, redacted = sanitize_public(source["data"])
        models = {
            "task_ir": contracts.TaskIR,
            "candidate_selection": contracts.CandidateSelection,
            "evidence_demand": contracts.EvidenceDemand,
            "materialization_plan": contracts.MaterializationPlan,
            "coverage_receipt": contracts.CoverageReceipt,
            "sufficiency": contracts.SufficiencyResult,
            "evidence_scope": contracts.SufficiencyResult,
            "candidate_verification": contracts.VerificationReport,
            "preservation_certificate": contracts.PreservationCertificate,
            "evaluation_plan": contracts.EvaluationPlan,
            "evaluation_receipt": contracts.EvaluationReceipt,
            "selective_evaluation": contracts.EvaluationReceipt,
            "case_evaluation_receipt": contracts.CaseEvaluationReceipt,
            "selective_case_evaluation": contracts.CaseEvaluationReceipt,
            "behavior_bank": contracts.BehaviorBank,
            "behavior_compilation": contracts.CompilationResult,
            "replay_comparison": contracts.ComparisonContract,
            "comparison_contract": contracts.ComparisonContract,
            "replay_case": contracts.ReplayCase,
            "replay_bank": contracts.ReplayBank,
            "replay_report": contracts.ReplayReport,
            "replay_bank_report": contracts.ReplayBankReport,
            "historical_replay": contracts.ReplayBankReport,
            "adapter_edge": contracts.AdapterEdge,
        }
        typed = None
        model = models.get(source.get("kind"))
        if model is not None:
            try:
                # Events attach attribution to the authoritative artifact body.
                # Keep those bytes in data; only unwrap known event metadata for
                # the typed product projection.
                metadata = {
                    "flow",
                    "nonblocking",
                    "kernel_id",
                    "verification_id",
                    "demand_id",
                    "report_id",
                }
                typed = model.model_validate(
                    {
                        key: value
                        for key, value in data.items()
                        if key not in metadata or key in model.model_fields
                    }
                    if isinstance(data, dict)
                    else data
                )
            except ValidationError:
                # Older or redacted evidence remains inspectable as recorded.
                pass
        return ArtifactResponse(
            id=identity,
            kind=source.get("kind", "unknown"),
            source_sha256=identity,
            projection_sha256=hashlib.sha256(canonical(data)).hexdigest(),
            redacted=bool(redacted),
            redacted_fields=redacted,
            data=data,
            typed_data=typed,
            provenance=self._artifact_provenance(identity),
            limitations=[
                "The source hash identifies the unchanged stored artifact. The projection hash identifies this sanitized data view."
            ],
        ).model_dump()

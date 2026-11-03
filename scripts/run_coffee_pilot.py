"""Run explicit phases of the genuine Coffee pilot through the real OaK service.

Preparation downloads/pins data and saves the protocol without making model calls.
Construction, development, and held-out phases use the same application pipeline
and spending ledger. No ontology, function, or agent answer is supplied by this script.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from oak.corpus import load_local_corpus
from oak.service import Service
from oak.store import now
from oak.tasks.coffee import (
    SOURCE_LOCK,
    ensure_coffee_data,
    load_coffee,
    load_reference_answers,
    score_answer,
)


def write_json(path: Path, value: Any) -> None:
    """Atomically publish a protocol/report pointer after its evidence is available."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def run_record(service: Service, run_id: str) -> dict[str, Any]:
    rows = service.store.rows("SELECT * FROM runs WHERE id=?", (run_id,))
    if not rows:
        raise ValueError(f"Pilot run no longer exists: {run_id}")
    return rows[0]


def prepare(service: Service, folder: Path, pilot: str) -> dict[str, Any]:
    """Save a label-free protocol and separate evaluator references, using the entire corpus."""
    protocol_path = folder / "protocol.json"
    if protocol_path.exists():
        protocol = json.loads(protocol_path.read_text())
        service.task(protocol["task_id"])
        if protocol["source_lock_sha256"] != hashlib.sha256(SOURCE_LOCK.read_bytes()).hexdigest():
            raise ValueError("Source lock changed; preserve this pilot and create a new protocol")
        actual = load_coffee(service.root / "benchmarks/toolqa-coffee", pilot=pilot)
        labels = load_reference_answers(service.root / "benchmarks/toolqa-coffee")
        expected_roles = {
            role: actual["splits"][role] for role in ("construction", "development", "heldout")
        }
        expected_queries = {
            query["id"]: query["query"]
            for query in actual["task_inputs"]
            if any(query["id"] in ids for ids in expected_roles.values())
        }
        references = json.loads((folder / "evaluator-references.json").read_text())
        if (
            protocol["roles"] != expected_roles
            or protocol["queries"] != expected_queries
            or references["roles"]
            != {role: {qid: labels[qid] for qid in ids} for role, ids in expected_roles.items()}
        ):
            raise ValueError("Pilot questions, splits, or references differ from pinned sources")
        return protocol
    cache = service.root / "benchmarks/toolqa-coffee"
    paths = ensure_coffee_data(cache)
    task = load_coffee(cache, pilot=pilot)
    query_by_id = {query["id"]: query["query"] for query in task["task_inputs"]}
    labels = load_reference_answers(cache)
    role_ids = {role: task["splits"][role] for role in ("construction", "development", "heldout")}
    snapshot = load_local_corpus(
        paths["corpus"], source_id=f"toolqa-coffee:{task['corpus']['sha256']}"
    )
    if snapshot["coverage"].get("records_returned") != task["corpus"]["row_count"]:
        raise ValueError("Service corpus normalization did not preserve the full Coffee table")
    construction_queries = [query_by_id[qid] for qid in role_ids["construction"]]
    task_id = service.create_task(
        f"ToolQA Coffee {pilot} pilot",
        task["task_description"],
        snapshot,
        construction_queries,
        references={query_by_id[qid]: labels[qid] for qid in role_ids["construction"]},
        evaluator="toolqa_exact_match",
    )
    protocol = {
        "format_version": 1,
        "protocol": task["splits"]["protocol"],
        "pilot": pilot,
        "task_id": task_id,
        "created_at": now(),
        "source_lock_sha256": hashlib.sha256(SOURCE_LOCK.read_bytes()).hexdigest(),
        "corpus_raw_sha256": task["corpus"]["sha256"],
        "corpus_id": service.task(task_id)["corpus_id"],
        "corpus_rows": task["corpus"]["row_count"],
        "roles": role_ids,
        "queries": {qid: query_by_id[qid] for ids in role_ids.values() for qid in ids},
        "templates": task["splits"]["templates"],
        "source_provenance": task["provenance"],
        "metric": "ToolQA normalized exact match",
        "scope": "Small real pilot, not reproduction of the paper's reported aggregate scores",
    }
    references = {
        "protocol": protocol["protocol"],
        "pilot": pilot,
        "roles": {role: {qid: labels[qid] for qid in ids} for role, ids in role_ids.items()},
        "usage": "Evaluator only; development/heldout labels must not enter model context",
    }
    write_json(folder / "evaluator-references.json", references)
    write_json(protocol_path, protocol)
    service.store.put("benchmark_protocol", protocol)
    return protocol


def job_inputs(service: Service, protocol: dict, kind: str, query: str | None = None) -> dict:
    """Bind a synchronous run to the real task and corpus without evaluation-label leakage."""
    task = service.task(protocol["task_id"])
    if task["corpus_id"] != protocol["corpus_id"]:
        raise ValueError("Pilot task corpus changed from the original full benchmark snapshot")
    return {
        "task_id": task["id"],
        "kind": kind,
        "query": query,
        "scope": task["scope"],
        "corpus_id": task["corpus_id"],
        "parent": task["active_revision"],
        "queries": task["example_queries"],
        "references": task.get("references") if kind == "construct" else None,
        "evaluator": "toolqa_exact_match" if kind == "construct" else None,
    }


def execute_saved_run(service: Service, run_id: str, *, resume: bool) -> dict:
    """Execute the actual worker synchronously, or explicitly resume a failed saved attempt."""
    row = run_record(service, run_id)
    if row["status"] == "completed":
        return row
    if row["status"] == "running":
        raise ValueError("Run is marked running; inspect its worker before any restart")
    if row["status"] in {"failed", "interrupted"} and not resume:
        raise ValueError("Saved run failed or was interrupted. Inspect evidence, then use --resume")
    jobs = service.root / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    (jobs / f"{run_id}.pid").write_text(str(os.getpid()))
    print(
        json.dumps({"run_id": run_id, "status": "executing", "budget": service.budget()}),
        flush=True,
    )
    service.run_worker(run_id)
    return run_record(service, run_id)


def create_run(service: Service, task_id: str, kind: str, inputs: dict) -> str:
    """Coordinate real synchronous jobs with the application's other job submitters."""
    with (service.root / "jobs.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if any(run["status"] in {"queued", "running"} for run in service.runs(task_id)):
            raise ValueError("Another job is active for this task")
        run_id = service.store.create_run(task_id, kind, inputs)
        jobs = service.root / "jobs"
        jobs.mkdir(parents=True, exist_ok=True)
        (jobs / f"{run_id}.pid").write_text(str(os.getpid()))
    return run_id


def construct(service: Service, folder: Path, protocol: dict, *, resume: bool) -> dict:
    """Construct the real kernel against all 5746 source rows and construction queries."""
    state_path = folder / "construction.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        if service.task(protocol["task_id"])["active_revision"]:
            raise ValueError("Task already has a kernel outside this pilot construction record")
        inputs = job_inputs(service, protocol, "construct")
        run_id = create_run(service, protocol["task_id"], "construct", inputs)
        state = {"run_id": run_id, "started_at": now(), "budget_before": service.budget()}
        write_json(state_path, state)
    try:
        row = execute_saved_run(service, state["run_id"], resume=resume)
    finally:
        state.update(run=run_record(service, state["run_id"]), budget_after=service.budget())
        write_json(state_path, state)
    if row["status"] != "completed":
        raise ValueError("Construction did not complete successfully; inspect its saved assessment")
    result = service.artifact(row["result_id"])
    state["result"] = result
    state["status"] = result["assessment"]["status"]
    state["artifact_id"] = service.store.put("benchmark_construction", state)
    write_json(state_path, state)
    return state


def evaluate_phase(
    service: Service, folder: Path, protocol: dict, phase: str, *, resume: bool
) -> dict:
    """Run genuine queries sequentially, preserving first answers and scoring outside the agent."""
    revision = service.revision(protocol["task_id"])
    if revision["assessment"]["status"] != "passed":
        raise ValueError("Evaluation requires a successfully constructed frozen revision")
    reports = folder / "reports" / revision["id"]
    if phase == "heldout":
        development_path = reports / "development.json"
        if (
            not development_path.exists()
            or json.loads(development_path.read_text())["status"] != "completed"
        ):
            raise ValueError(
                "Complete development evaluation on this exact revision before heldout"
            )
    path = reports / f"{phase}.json"
    report = (
        json.loads(path.read_text())
        if path.exists()
        else {
            "protocol": protocol["protocol"],
            "pilot": protocol["pilot"],
            "phase": phase,
            "kernel_revision": revision["id"],
            "corpus_id": protocol["corpus_id"],
            "metric": protocol["metric"],
            "started_at": now(),
            "budget_before": service.budget(),
            "results": {},
            "status": "in_progress",
        }
    )
    labels = json.loads((folder / "evaluator-references.json").read_text())["roles"][phase]
    try:
        for qid in protocol["roles"][phase]:
            if service.task(protocol["task_id"])["active_revision"] != revision["id"]:
                raise ValueError("Active kernel changed during the frozen evaluation")
            item = report["results"].get(qid)
            if item is not None and item.get("score") is not None:
                continue  # An observed wrong answer is still final for this frozen evaluation.
            if item is None:
                inputs = job_inputs(service, protocol, "ask", protocol["queries"][qid])
                inputs["benchmark_role"] = phase
                run_id = create_run(service, protocol["task_id"], "ask", inputs)
                item = {"qid": qid, "query": protocol["queries"][qid], "run_id": run_id}
                report["results"][qid] = item
                write_json(path, report)
            row = execute_saved_run(service, item["run_id"], resume=resume)
            item["run_status"] = row["status"]
            if row["status"] != "completed" or not row["result_id"]:
                raise ValueError(f"Query {qid} lacks a completed real result")
            actual = service.artifact(row["result_id"])
            item.update(result_id=row["result_id"], answer_status=actual.get("status"))
            if actual.get("status") not in {"answered", "insufficient_evidence"}:
                raise ValueError(f"Query {qid} has an unsupported terminal answer status")
            if not isinstance(actual.get("answer"), str):
                raise ValueError(f"Query {qid} has no actual answer string to score")
            item.update(
                prediction=actual["answer"],
                reference=labels[qid],
                score=score_answer(actual["answer"], labels[qid]),
            )
            service.store.event(
                item["run_id"],
                "benchmark_score",
                "completed",
                f"{phase} official score recorded",
                item,
            )
            write_json(path, report)
            print(
                json.dumps({"qid": qid, "score": item["score"], "result_id": row["result_id"]}),
                flush=True,
            )
        report["status"] = "completed"
    except BaseException as error:
        report.update(status="incomplete", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        measured = [
            result["score"]
            for result in report["results"].values()
            if result.get("score") is not None
        ]
        report.update(
            total_queries=len(protocol["roles"][phase]),
            scored_queries=len(measured),
            correct=sum(measured),
            answered_queries=sum(
                result.get("answer_status") == "answered"
                for result in report["results"].values()
            ),
            insufficient_evidence_queries=sum(
                result.get("answer_status") == "insufficient_evidence"
                for result in report["results"].values()
            ),
            accuracy=sum(measured) / len(measured)
            if len(measured) == len(protocol["roles"][phase])
            else None,
            budget_after=service.budget(),
            updated_at=now(),
        )
        report["artifact_id"] = service.store.put("benchmark_report", report)
        write_json(path, report)
    return report


def main() -> None:
    """Require an explicit phase so preparation cannot silently become a paid benchmark run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", required=True, choices=["prepare", "construct", "development", "heldout"]
    )
    parser.add_argument("--root", type=Path, default=Path(".local"))
    parser.add_argument("--pilot", choices=["small", "expanded"], default="small")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume failed saved runs after inspecting their evidence",
    )
    arguments = parser.parse_args()
    service = Service(arguments.root)
    folder = service.root / "evaluation/toolqa-coffee" / arguments.pilot
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "pilot.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        protocol = prepare(service, folder, arguments.pilot)
        with (service.root / "jobs.lock").open("a") as jobs_lock:
            fcntl.flock(jobs_lock, fcntl.LOCK_EX)
            service._reconcile_jobs(protocol["task_id"])
        active_jobs = [
            row
            for row in service.runs(protocol["task_id"])
            if row["status"] in {"queued", "running"}
        ]
        if arguments.phase != "prepare" and active_jobs:
            raise ValueError("An active saved job exists; inspect it before starting another phase")
        if arguments.phase == "prepare":
            result = {
                "status": "prepared",
                "protocol_path": str(folder / "protocol.json"),
                "task_id": protocol["task_id"],
                "corpus_rows": protocol["corpus_rows"],
                "budget": service.budget(),
            }
        elif arguments.phase == "construct":
            result = construct(service, folder, protocol, resume=arguments.resume)
        else:
            result = evaluate_phase(
                service, folder, protocol, arguments.phase, resume=arguments.resume
            )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

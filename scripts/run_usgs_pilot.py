"""Bounded real USGS construction, inference, and revision acceptance checks.

This is a task-specific evaluator. Its independent numeric references never enter
schema, extraction, function-composition, or answering prompts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from oak.corpus import fetch_usgs, normalize_snapshot
from oak.service import Service, combine_corpus
from oak.tasks.evaluation import numeric_match

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / ".local/pilots/usgs.json"
COUNT = "How many earthquakes are in this supplied corpus? Return only the number."
MAXIMUM = (
    "What is the maximum earthquake magnitude in this supplied corpus? Return only the number."
)
MINIMUM = (
    "What is the minimum earthquake magnitude in this supplied corpus? Return only the number."
)
DEPTH = "What is the maximum earthquake depth in kilometres in this supplied corpus? Return only the number."
SCOPE = "Audit the supplied USGS earthquake events: count events and answer magnitude and location questions, including numeric magnitude filters. Use event IDs as source identities. Results apply only to the supplied time-bounded evidence."


def save(value):
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2) + "\n")


def execute(service, receipt, kind, *, query=None, scope=None, snapshot=None, queries=None):
    task = service.task(receipt["task_id"])
    corpus = service.artifact(task["corpus_id"])
    if snapshot is not None:
        corpus = combine_corpus(corpus, snapshot)
    corpus_id = service.store.put("corpus_snapshot", corpus)
    inputs = {
        "task_id": task["id"],
        "kind": kind,
        "query": query,
        "scope": scope or task["scope"],
        "corpus_id": corpus_id,
        "parent": task["active_revision"],
        "queries": list(dict.fromkeys(task["example_queries"] + (queries or []))),
        "references": task.get("references")
        if corpus_id == task.get("reference_corpus_id")
        else None,
        "evaluator": task.get("evaluator"),
    }
    run_id = service.store.create_run(task["id"], kind, inputs)
    receipt.setdefault("runs", []).append({"id": run_id, "kind": kind, "query": query})
    save(receipt)
    print(json.dumps({"run_id": run_id, "kind": kind}), flush=True)
    service.run_worker(run_id)
    run = service.store.rows("SELECT * FROM runs WHERE id=?", (run_id,))[0]
    result = service.artifact(run["result_id"]) if run["result_id"] else None
    print(
        json.dumps(
            {
                "status": run["status"],
                "error": run["error"],
                "result": result,
                "budget": service.budget(),
            }
        ),
        flush=True,
    )
    if run["status"] != "completed":
        raise RuntimeError(run["error"] or "Run failed its checks")
    return result


def main():
    phase = sys.argv[1]
    service = Service(ROOT / ".local")
    if phase == "prepare":
        if RECEIPT.exists():
            print(RECEIPT.read_text())
            return
        snapshot = fetch_usgs("2025-01-01T00:00:00Z", "2025-01-02T00:00:00Z", minmagnitude=5.0)
        records = [d["record"] for d in normalize_snapshot(snapshot)]
        references = {
            COUNT: str(len(records)),
            MAXIMUM: str(max(r["properties"]["mag"] for r in records)),
        }
        task_id = service.create_task(
            "USGS earthquake audit",
            SCOPE,
            snapshot,
            [COUNT, MAXIMUM],
            references=references,
            evaluator="numeric",
        )
        receipt = {
            "task_id": task_id,
            "source_snapshot_id": snapshot["snapshot_id"],
            "records": len(records),
            "heldout_references": {
                MINIMUM: str(min(r["properties"]["mag"] for r in records)),
                DEPTH: str(max(r["geometry"]["coordinates"][2] for r in records)),
            },
        }
        save(receipt)
        print(json.dumps(receipt, indent=2))
        return
    receipt = json.loads(RECEIPT.read_text())
    if phase == "construct":
        execute(service, receipt, "construct")
    elif phase == "ask":
        result = execute(service, receipt, "ask", query=MINIMUM)
        receipt["inference_check"] = {
            "result": result,
            "expected": receipt["heldout_references"][MINIMUM],
            "passed": numeric_match(result["answer"], receipt["heldout_references"][MINIMUM]),
        }
        save(receipt)
        assert receipt["inference_check"]["passed"]
    elif phase == "revise":
        result = execute(
            service,
            receipt,
            "revise",
            query="Expand the task scope to depth and minimum magnitude questions. Extract depth in kilometres from the supplied USGS coordinates. Preserve all existing magnitude/count functions and their input/output interfaces when possible.",
            scope=SCOPE
            + " Also answer depth questions in kilometres, including maximum depth and minimum magnitude.",
            queries=[DEPTH, MINIMUM],
        )
        receipt["candidate_revision"] = result["revision_id"]
        save(receipt)
        check = service.promotion_check(receipt["task_id"], result["revision_id"])
        print(json.dumps(check))
        assert check["allowed"], check["reason"]
        service.promote(receipt["task_id"], result["revision_id"])
    elif phase == "depth":
        result = execute(service, receipt, "ask", query=DEPTH)
        receipt["depth_check"] = {
            "result": result,
            "expected": receipt["heldout_references"][DEPTH],
            "passed": numeric_match(result["answer"], receipt["heldout_references"][DEPTH]),
        }
        save(receipt)
        assert receipt["depth_check"]["passed"]
    elif phase == "report":
        print(
            json.dumps(
                {
                    "receipt": receipt,
                    "budget": service.budget(),
                    "runs": service.runs(receipt["task_id"]),
                }
            )
        )
    else:
        raise ValueError("Choose prepare, construct, ask, revise, depth, or report")


if __name__ == "__main__":
    main()

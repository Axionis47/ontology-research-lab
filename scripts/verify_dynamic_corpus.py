"""Run the authorized USGS dynamic-corpus acceptance on the real shared ledger.

This task-specific evaluator keeps independently computed numeric expectations
outside model and adapter prompts. No service, model, or execution is replaced.
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path

from oak.corpus import fetch_usgs
from oak.service import Service, combine_corpus, corpus_documents, source_parts
from oak.store import Store, canonical, now
from oak.tasks.evaluation import numeric_match

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/verification/dynamic-corpus.json"
TASK = "92a95ecf291d41d9887cdaa1be74fe67"
LIMIT = 0.50
COUNT = "How many earthquakes are in this supplied corpus? Return only the number."
SUGGESTION = (
    "Expand only the evidence corpus by appending the supplied next-day USGS records. "
    "Preserve the existing schema and all existing callable function definitions and interfaces. "
    "Retain the task scope and every validation query. Existing computations already cover the "
    "expanded evidence; do not add constants, new question patterns, or new scope."
)


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def differences(old, new, path: str = "") -> list[dict]:
    """Record actual revision changes, including descriptive annotations."""
    if old == new:
        return []
    if isinstance(old, dict) and isinstance(new, dict):
        changes = []
        for key in sorted(old.keys() | new.keys()):
            location = path + "/" + str(key)
            if key not in old or key not in new:
                changes.append({"path": location, "before": old.get(key), "after": new.get(key)})
            else:
                changes.extend(differences(old[key], new[key], location))
        return changes
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        return [
            change
            for index, (left, right) in enumerate(zip(old, new, strict=True))
            for change in differences(left, right, path + "/" + str(index))
        ]
    return [{"path": path, "before": old, "after": new}]


def save(report: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report["updated_at"] = now()
    temporary = REPORT.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(REPORT)


def features(snapshot: dict) -> dict[str, dict]:
    result = {}
    for part in source_parts(snapshot):
        raw = base64.b64decode(part["raw_payload_base64"], validate=True)
        if hashlib.sha256(raw).hexdigest() != part["raw_sha256"]:
            raise ValueError("Source response digest mismatch")
        for feature in json.loads(raw)["features"]:
            previous = result.get(feature["id"])
            if previous is not None and previous != feature:
                raise ValueError("Adjacent source snapshots disagree about the same event")
            result[feature["id"]] = feature
    return result


class CampaignStore(Store):
    """Apply a campaign spend guard while retaining the real store's reservations."""

    def __init__(self, root: Path, report: dict):
        super().__init__(root)
        self.report = report

    def campaign_calls(self) -> list[dict]:
        runs = [item["run_id"] for item in self.report.get("runs", [])]
        if not runs:
            return []
        placeholders = ",".join("?" for _ in runs)
        return self.rows(f"SELECT * FROM model_calls WHERE run_id IN ({placeholders})", tuple(runs))

    def campaign_budget(self) -> dict:
        calls = self.campaign_calls()
        return {
            "limit_usd": LIMIT,
            "estimated_usd": sum(call["estimated"] for call in calls),
            "unknown_or_pending_reserved_usd": sum(
                call["reserved"] for call in calls if call["status"] != "settled"
            ),
            "model_calls": len(calls),
        }

    def reserve(self, run_id: str, amount: float, limit: float) -> str:
        if run_id not in {item["run_id"] for item in self.report.get("runs", [])}:
            raise RuntimeError("Unregistered dynamic-corpus campaign run")
        with (self.root / "dynamic-corpus-budget.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            budget = self.campaign_budget()
            # The adapter's reservation is ten times the per-request input-byte,
            # CLI-context and maximum-output allowance. The verified runtime has
            # maxAttempts=1, maxSessionTurns=1 and function-calling disabled.
            request_allowance = amount / 10
            used = budget["estimated_usd"] + budget["unknown_or_pending_reserved_usd"]
            if used + request_allowance > LIMIT:
                raise RuntimeError("Dynamic-corpus campaign would exceed its $0.50 bound")
            return super().reserve(run_id, amount, limit)


def execute(service: Service, report: dict, kind: str, *, query: str, corpus_id: str) -> dict:
    previous = next((item for item in report.get("runs", []) if item["kind"] == kind), None)
    if previous:
        run_id = previous["run_id"]
    else:
        task = service.task(TASK)
        inputs = {
            "task_id": TASK,
            "kind": kind,
            "query": query,
            "scope": task["scope"],
            "corpus_id": corpus_id,
            "parent": task["active_revision"],
            "queries": task["example_queries"],
            # Changed corpus invalidates numeric labels attached to the old corpus.
            "references": None,
            "evaluator": task.get("evaluator"),
        }
        with (service.root / "jobs.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if service.store.rows(
                "SELECT id FROM runs WHERE task_id=? AND status IN ('queued','running')", (TASK,)
            ):
                raise RuntimeError("Another USGS job is active")
            run_id = service.store.create_run(TASK, kind, inputs)
            report.setdefault("runs", []).append({"run_id": run_id, "kind": kind})
            jobs = service.root / "jobs"
            jobs.mkdir(exist_ok=True)
            (jobs / f"{run_id}.pid").write_text(str(os.getpid()))
        save(report)
    row = service.store.rows("SELECT * FROM runs WHERE id=?", (run_id,))[0]
    if row["status"] != "completed":
        print(json.dumps({"stage": kind, "run_id": run_id, "status": "starting"}), flush=True)
        service.run_worker(run_id)
    row = service.store.rows("SELECT * FROM runs WHERE id=?", (run_id,))[0]
    if row["status"] != "completed":
        raise RuntimeError(row["error"] or f"{kind} checks failed")
    return service.artifact(row["result_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Execute the authorized live acceptance")
    args = parser.parse_args()
    if not args.run:
        print(REPORT.read_text() if REPORT.exists() else "No acceptance receipt exists yet.")
        return
    report = (
        json.loads(REPORT.read_text())
        if REPORT.exists()
        else {
            "verification": "real_dynamic_corpus_expansion",
            "started_at": now(),
            "task_id": TASK,
            "status": "running",
            "runs": [],
            "budget_bound_usd": LIMIT,
            "expected_values_in_model_prompts": False,
        }
    )
    if "error" in report:
        report.setdefault("verification_attempt_history", []).append(
            {
                "status": report["status"],
                "error": report.pop("error"),
                "updated_at": report.get("updated_at"),
            }
        )
    report["status"] = "running"
    service = Service(ROOT / ".local")
    service.store = CampaignStore(service.root, report)
    try:
        if "parent_revision" not in report:
            parent = service.revision(TASK)
            report.update(
                parent_revision=parent["id"],
                old_corpus_id=parent["corpus_id"],
                original_schema_sha256=digest(parent["schema"]),
                original_functions_sha256=digest(parent["functions"]),
                original_queries=parent["queries"],
            )
            save(report)
        parent = service.revision(TASK, report["parent_revision"])
        old = service.artifact(report["old_corpus_id"])
        if "incoming_snapshot_artifact" not in report:
            incoming = fetch_usgs("2025-01-02T00:00:00Z", "2025-01-03T00:00:00Z", 5.0)
            report["incoming_snapshot_artifact"] = service.store.put("corpus_snapshot", incoming)
            report["incoming_acquisition"] = {
                key: incoming[key]
                for key in ("status", "request", "fetched_at", "raw_sha256", "coverage", "error")
            }
            save(report)
        incoming = service.artifact(report["incoming_snapshot_artifact"])
        corpus_documents(incoming)
        combined = combine_corpus(old, incoming)
        report["expanded_corpus_id"] = service.store.put("corpus_snapshot", combined)
        old_features, new_features = features(old), features(combined)
        report["independent_source_checks"] = {
            "old_event_count": len(old_features),
            "expanded_event_count": len(new_features),
            "added_event_ids": sorted(set(new_features) - set(old_features)),
            "old_max_depth_km": max(
                item["geometry"]["coordinates"][2] for item in old_features.values()
            ),
            "expanded_max_depth_km": max(
                item["geometry"]["coordinates"][2] for item in new_features.values()
            ),
            "source_raw_sha256": [part["raw_sha256"] for part in source_parts(combined)],
            "method": "Parse retained original GeoJSON bytes and deduplicate by USGS event ID",
        }
        if not report["independent_source_checks"]["added_event_ids"]:
            raise ValueError("Fetched interval did not add any genuine earthquake events")
        save(report)
        result = execute(
            service, report, "revise", query=SUGGESTION, corpus_id=report["expanded_corpus_id"]
        )
        candidate = service.revision(TASK, result["revision_id"])
        report["candidate_revision"] = candidate["id"]
        report["schema_unchanged"] = digest(candidate["schema"]) == report["original_schema_sha256"]
        report["functions_unchanged"] = (
            digest(candidate["functions"]) == report["original_functions_sha256"]
        )
        report["schema_changes"] = differences(parent["schema"], candidate["schema"])
        report["function_changes"] = differences(parent["functions"], candidate["functions"])
        report["queries_preserved"] = candidate["queries"] == report["original_queries"]
        report["regression"] = result["regression"]
        report["candidate_graph_sha256"] = digest(candidate["graph"])
        report["candidate_graph_nodes"] = len(candidate["graph"]["nodes"])
        replay_events = service.store.rows(
            "SELECT artifact_id FROM events WHERE run_id=? AND stage='regression_graph' ORDER BY id",
            (candidate["run_id"],),
        )
        report["original_corpus_reextractions"] = []
        for event in replay_events:
            evidence = service.artifact(event["artifact_id"])
            if evidence["corpus_id"] == report["old_corpus_id"]:
                report["original_corpus_reextractions"].append(
                    {
                        "artifact_id": event["artifact_id"],
                        "corpus_id": evidence["corpus_id"],
                        "graph_sha256": digest(evidence["graph"]),
                        "graph_hash_encoding": "canonical JSON, ensure_ascii=false, UTF-8",
                        "executor_graph_sha256": hashlib.sha256(
                            json.dumps(
                                evidence["graph"], sort_keys=True, separators=(",", ":")
                            ).encode()
                        ).hexdigest(),
                        "executor_hash_encoding": "sorted compact JSON, ensure_ascii=true, UTF-8",
                        "nodes": len(evidence["graph"]["nodes"]),
                        "candidate_schema_sha256": digest(candidate["schema"]),
                    }
                )
        if not report["original_corpus_reextractions"]:
            raise AssertionError(
                "No actual candidate-schema extraction over the original corpus was recorded"
            )
        replay_graph_hashes = {
            call["new_dependencies"]["graph_sha256"]
            for replay in result["regression"]["reports"]
            for check in replay["checks"]
            for call in check["calls"]
            if call.get("new_dependencies")
        }
        for extraction in report["original_corpus_reextractions"]:
            extraction["matches_all_replay_dependency_hashes"] = replay_graph_hashes == {
                extraction["executor_graph_sha256"]
            }
            if not extraction["matches_all_replay_dependency_hashes"]:
                raise AssertionError("Replay did not use the recorded original-corpus graph")
        check = service.promotion_check(TASK, candidate["id"])
        if service.task(TASK)["active_revision"] != candidate["id"]:
            report["promotion_check"] = check
        save(report)
        if service.task(TASK)["active_revision"] != candidate["id"]:
            if not check["allowed"]:
                raise AssertionError(check["reason"])
            service.promote(TASK, candidate["id"])
        report["promoted_revision"] = service.task(TASK)["active_revision"]
        before_ask = service.revision(TASK)
        before_hashes = {key: digest(before_ask[key]) for key in ("schema", "functions")}
        answer = execute(
            service, report, "ask", query=COUNT, corpus_id=report["expanded_corpus_id"]
        )
        after_ask = service.revision(TASK)
        after_hashes = {key: digest(after_ask[key]) for key in ("schema", "functions")}
        report["frozen_inference_immutability"] = {
            "before_revision": before_ask["id"],
            "after_revision": after_ask["id"],
            "before_sha256": before_hashes,
            "after_sha256": after_hashes,
            "passed": before_ask["id"] == after_ask["id"] and before_hashes == after_hashes,
        }
        expected = str(len(new_features))
        report["fresh_answer"] = {
            "query": COUNT,
            "result": answer,
            "expected_from_raw_geojson": expected,
            "passed": answer["status"] == "answered" and numeric_match(answer["answer"], expected),
        }
        if not report["fresh_answer"]["passed"]:
            raise AssertionError("Fresh answer differs from independent raw-GeoJSON count")
        if not report["frozen_inference_immutability"]["passed"]:
            raise AssertionError("Frozen schema or functions changed during the fresh ask")
        if not report["queries_preserved"]:
            raise AssertionError(
                "Corpus-only revision did not preserve the previous validation queries"
            )
        report["status"] = "passed"
        report["finished_at"] = now()
    except BaseException as error:
        report.update(status="failed", error={"type": type(error).__name__, "message": str(error)})
        raise
    finally:
        report["campaign_budget"] = service.store.campaign_budget()
        report["model_calls"] = service.store.campaign_calls()
        report["shared_store_budget"] = service.budget()
        save(report)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "report": str(REPORT),
                    "budget": report["campaign_budget"],
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()

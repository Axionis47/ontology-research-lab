"""Verify one genuine model-proposed rename adapter on the existing USGS task.

All model calls use the real Service and shared Store. Independent GeoJSON depth
references remain in this evaluator and never enter model or adapter prompts.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path

from verify_dynamic_corpus import CampaignStore, differences, digest, features

from oak.regression import adapter_proposal_payload, validate_adapter
from oak.service import Service
from oak.store import Store, canonical, now
from oak.tasks.evaluation import numeric_match

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/verification/adapter-loop.json"
TASK = "92a95ecf291d41d9887cdaa1be74fe67"
OLD = "get_max_earthquake_depth_km"
NEW = "maximum_depth_km"
QUERY = "What is the maximum earthquake depth in kilometres in this supplied corpus? Return only the number."
SUGGESTION = (
    f"Explicitly rename the existing function {OLD} to {NEW}. Remove the old function name; "
    "do not retain it as an alias. Keep the renamed function's computation, inputs, output schema, "
    "steps and result semantics identical. Preserve every other callable function and its interface. "
    "Keep the task scope, corpus and every validation query. This is an explicitly requested interface "
    "rename, so it takes precedence over the generic instruction to retain old function names. "
    "The compatibility adapter should map recorded calls from the former interface to the new one."
)


class AdapterCampaignStore(CampaignStore):
    """Allow the explicitly enlarged campaign while retaining unknown usage."""

    def campaign_budget(self) -> dict:
        budget = super().campaign_budget()
        budget["limit_usd"] = self.report["budget_bound_usd"]
        return budget

    def reserve(self, run_id: str, amount: float, limit: float) -> str:
        if run_id not in {item["run_id"] for item in self.report["runs"]}:
            raise RuntimeError("Unregistered adapter campaign run")
        with (self.root / "adapter-campaign-budget.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            budget = self.campaign_budget()
            if budget["limit_usd"] not in {0.50, 1.50}:
                raise RuntimeError("Unexpected campaign allowance")
            used = budget["estimated_usd"] + budget["unknown_or_pending_reserved_usd"]
            if used + amount / 10 > budget["limit_usd"]:
                raise RuntimeError("Adapter campaign would exceed its authorized allowance")
            return Store.reserve(self, run_id, amount, limit)


def save(report: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report["updated_at"] = now()
    temporary = REPORT.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(REPORT)


def execute(service: Service, report: dict, phase: str, kind: str, query: str) -> tuple[dict, str]:
    previous = next((run for run in report["runs"] if run["phase"] == phase), None)
    if previous:
        row = service.store.rows("SELECT * FROM runs WHERE id=?", (previous["run_id"],))[0]
        if row["status"] == "completed":
            return service.artifact(row["result_id"]), row["result_id"]
        resume = report.get("explicit_resume", {})
        if (
            row["status"] not in {"failed", "interrupted"}
            or resume.get("consumed")
            or resume.get("run_id") != row["id"]
        ):
            raise RuntimeError(
                f"Existing phase {phase} did not complete; no automatic extra attempt"
            )
        with (service.root / "jobs.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if service.store.rows(
                "SELECT id FROM runs WHERE task_id=? AND status IN ('queued','running')", (TASK,)
            ):
                raise RuntimeError("Another USGS job is active")
            resume.update(consumed=True, started_at=now())
            service.store.set_run(row["id"], "queued")
            (service.root / "jobs" / f"{row['id']}.pid").write_text(str(os.getpid()))
        save(report)
        print(
            json.dumps({"phase": phase, "run_id": row["id"], "status": "resuming_checkpoint"}),
            flush=True,
        )
        service.run_worker(row["id"])
        row = service.store.rows("SELECT * FROM runs WHERE id=?", (row["id"],))[0]
        if row["status"] != "completed":
            raise RuntimeError(row["error"] or "Resumed phase failed")
        return service.artifact(row["result_id"]), row["result_id"]
    task = service.task(TASK)
    inputs = {
        "task_id": TASK,
        "kind": kind,
        "query": query,
        "scope": task["scope"],
        "corpus_id": report["corpus_id"],
        "parent": task["active_revision"],
        "queries": task["example_queries"],
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
        report["runs"].append({"run_id": run_id, "kind": kind, "phase": phase})
        jobs = service.root / "jobs"
        jobs.mkdir(exist_ok=True)
        (jobs / f"{run_id}.pid").write_text(str(os.getpid()))
    save(report)
    print(json.dumps({"phase": phase, "run_id": run_id, "status": "starting"}), flush=True)
    service.run_worker(run_id)
    row = service.store.rows("SELECT * FROM runs WHERE id=?", (run_id,))[0]
    if row["status"] != "completed":
        raise RuntimeError(row["error"] or f"Phase {phase} failed")
    return service.artifact(row["result_id"]), row["result_id"]


def check_answer(result: dict, expected: str, function: str) -> dict:
    calls = result.get("trajectory", [])
    return {
        "answer": result.get("answer"),
        "expected_from_raw_geojson": expected,
        "status": result.get("status"),
        "kernel_revision": result.get("kernel_revision"),
        "called_functions": [call.get("function") for call in calls],
        "passed": result.get("status") == "answered"
        and numeric_match(result.get("answer", ""), expected)
        and any(call.get("function") == function for call in calls)
        and all(call.get("status") == "completed" for call in calls),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Run the authorized live acceptance")
    parser.add_argument(
        "--resume-once",
        action="store_true",
        help="Use the explicit $1.50 checkpoint-resume authorization",
    )
    args = parser.parse_args()
    if not args.run:
        print(REPORT.read_text() if REPORT.exists() else "No adapter acceptance receipt exists.")
        return
    report = (
        json.loads(REPORT.read_text())
        if REPORT.exists()
        else {
            "verification": "actual_model_proposed_rename_adapter",
            "task_id": TASK,
            "started_at": now(),
            "status": "running",
            "runs": [],
            "budget_bound_usd": 0.50,
            "requested_rename": {"old": OLD, "new": NEW},
            "independent_expected_values_sent_to_models": False,
        }
    )
    if report["status"] == "passed":
        print(json.dumps({"status": "already_verified", "report": str(REPORT)}))
        return
    service = Service(ROOT / ".local")
    service.store = AdapterCampaignStore(service.root, report)
    if args.resume_once:
        if report.get("explicit_resume"):
            raise RuntimeError("The one explicit resume has already been registered")
        target = next(run["run_id"] for run in report["runs"] if run["phase"] == "rename_revision")
        latest = service.store.rows(
            "SELECT COALESCE(MAX(id),0) AS id FROM events WHERE run_id=?", (target,)
        )[0]["id"]
        report["explicit_resume"] = {
            "run_id": target,
            "consumed": False,
            "events_after_id": latest,
            "reason": "One authorized resume after transient fetch failure; prior unknown reservation retained",
            "unknown_call_id_retained": "efba62f31c674ec79e6f38157ef7b5e1",
        }
        report["budget_bound_usd"] = 1.50
        if "error" in report:
            report["prior_failure"] = report.pop("error")
        report["status"] = "running"
        save(report)
    try:
        if "parent_revision" not in report:
            parent = service.revision(TASK)
            if OLD not in {function["name"] for function in parent["functions"]}:
                raise AssertionError("The active parent lacks the explicitly targeted old function")
            report.update(
                parent_revision=parent["id"],
                corpus_id=parent["corpus_id"],
                parent_kernel_sha256=digest(parent),
                original_queries=parent["queries"],
            )
            save(report)
        parent = service.revision(TASK, report["parent_revision"])
        source = service.artifact(report["corpus_id"])
        records = features(source)
        expected = str(max(record["geometry"]["coordinates"][2] for record in records.values()))
        report["independent_evaluation"] = {
            "event_count": len(records),
            "maximum_depth_km": expected,
            "method": "Maximum coordinates[2] over retained original USGS GeoJSON features",
        }
        before, before_id = execute(service, report, "before_ask", "ask", QUERY)
        report["before_answer"] = {
            **check_answer(before, expected, OLD),
            "result_artifact": before_id,
        }
        save(report)
        if not report["before_answer"]["passed"]:
            raise AssertionError("No genuine successful old-name depth trajectory was obtained")
        revision_result, revision_result_id = execute(
            service, report, "rename_revision", "revise", SUGGESTION
        )
        candidate = service.revision(TASK, revision_result["revision_id"])
        report["candidate_revision"] = candidate["id"]
        report["revision_result_artifact"] = revision_result_id
        old_functions = {function["name"]: function for function in parent["functions"]}
        new_functions = {function["name"]: function for function in candidate["functions"]}
        report["function_name_gate"] = {
            "old_absent": OLD not in new_functions,
            "new_present": NEW in new_functions,
            "all_other_names_present": set(old_functions) - {OLD} <= set(new_functions),
        }
        report["function_changes"] = differences(parent["functions"], candidate["functions"])
        report["schema_changes"] = differences(parent["schema"], candidate["schema"])
        if not all(report["function_name_gate"].values()):
            raise AssertionError("Model did not perform the requested explicit rename")
        report["other_functions_exactly_preserved"] = all(
            old_functions[name] == new_functions[name] for name in old_functions if name != OLD
        )
        old_body = {key: value for key, value in old_functions[OLD].items() if key != "name"}
        new_body = {key: value for key, value in new_functions[NEW].items() if key != "name"}
        report["renamed_function_body_exactly_preserved"] = old_body == new_body
        replay = revision_result["regression"]
        report["regression_summary"] = {
            "status": replay["status"],
            "adapter": replay["adapter"],
            "receipt_ids": replay["receipt_ids"],
            "checks": [
                {
                    key: check.get(key)
                    for key in ("receipt_id", "origin", "status", "executed_calls", "reason")
                }
                for item in replay["reports"]
                for check in item["checks"]
            ],
        }
        if replay["status"] != "passed" or not replay["adapter"]:
            raise AssertionError("The actual adapter-assisted replay did not pass")
        adapter = validate_adapter(replay["adapter"], parent, candidate)
        if not any(
            item.old_function == OLD and item.new_function == NEW for item in adapter.mappings
        ):
            raise AssertionError("Validated adapter does not map the explicitly renamed function")
        adapter_calls = []
        for row in service.store.rows(
            "SELECT id,evidence_id FROM model_calls WHERE run_id=? AND evidence_id IS NOT NULL",
            (candidate["run_id"],),
        ):
            evidence = service.artifact(row["evidence_id"])
            if evidence.get("request", {}).get("stage") != "compatibility_adapter":
                continue
            if not evidence.get("validated_success"):
                continue
            actual_context = json.loads(evidence["request"]["prompt"])["inputs"]
            expected_context = adapter_proposal_payload(parent, candidate)
            if canonical(actual_context) != canonical(expected_context):
                raise AssertionError(
                    "Adapter proposal context differs from the answer-free contract"
                )
            proposal = evidence["validated_value"]
            if not any(
                item["old_function"] == OLD and item["new_function"] == NEW
                for item in proposal.get("mappings", [])
            ):
                raise AssertionError("The actual model proposal did not contain the rename mapping")
            adapter_calls.append(
                {
                    "call_id": row["id"],
                    "usage_artifact": row["evidence_id"],
                    "proposal": proposal,
                    "context_sha256": digest(actual_context),
                    "context_keys": sorted(actual_context),
                    "old_context_keys": sorted(actual_context["old"]),
                    "new_context_keys": sorted(actual_context["new"]),
                    "context_exactly_matches_answer_free_contract": True,
                    "stats": evidence["stats"],
                    "estimated_usd": evidence["estimated_usd"],
                }
            )
        report["actual_adapter_model_calls"] = adapter_calls
        if not adapter_calls:
            raise AssertionError("No genuine completed model-proposed adapter receipt exists")
        if before_id not in replay["receipt_ids"]:
            raise AssertionError(
                "The newly recorded old-function trajectory was omitted from replay"
            )
        if candidate["queries"] != report["original_queries"]:
            raise AssertionError("Revision omitted previous validation queries")
        if candidate["corpus_id"] != report["corpus_id"]:
            raise AssertionError("Function rename unexpectedly changed the source corpus")
        check = service.promotion_check(TASK, candidate["id"])
        report["promotion_check"] = {"allowed": check["allowed"], "reason": check["reason"]}
        save(report)
        if not check["allowed"]:
            raise AssertionError(check["reason"])
        service.promote(TASK, candidate["id"])
        report["promoted_revision"] = candidate["id"]
        frozen_before = {key: digest(candidate[key]) for key in ("schema", "functions")}
        after, after_id = execute(service, report, "after_ask", "ask", QUERY)
        report["after_answer"] = {**check_answer(after, expected, NEW), "result_artifact": after_id}
        frozen_after = {key: digest(service.revision(TASK)[key]) for key in ("schema", "functions")}
        report["frozen_inference_immutability"] = {
            "before_sha256": frozen_before,
            "after_sha256": frozen_after,
            "passed": frozen_before == frozen_after,
        }
        report["original_kernel_unchanged"] = (
            digest(service.revision(TASK, parent["id"])) == report["parent_kernel_sha256"]
        )
        if (
            not report["after_answer"]["passed"]
            or not report["frozen_inference_immutability"]["passed"]
        ):
            raise AssertionError("Fresh answer or frozen-inference immutability check failed")
        if not report["original_kernel_unchanged"]:
            raise AssertionError("The original saved kernel changed")
        report.update(
            status="passed", finished_at=now(), adapter_proposal_completed=True, promoted=True
        )
    except BaseException as error:
        report.update(status="failed", error={"type": type(error).__name__, "message": str(error)})
        report["active_revision_after_failure"] = service.task(TASK)["active_revision"]
        revision_run = next(
            (run for run in report["runs"] if run["phase"] == "rename_revision"), None
        )
        if revision_run:
            events = service.store.rows(
                "SELECT stage,status,artifact_id FROM events WHERE run_id=? AND artifact_id IS NOT NULL "
                "ORDER BY id",
                (revision_run["run_id"],),
            )
            selected = {}
            for event in events:
                if event["stage"] in {"schema", "functions", "graph", "ontology_validation"}:
                    selected[event["stage"]] = event
            report["partial_candidate_artifacts"] = selected
            if "functions" in selected and "parent_revision" in report:
                partial = service.artifact(selected["functions"]["artifact_id"])
                original = service.revision(TASK, report["parent_revision"])["functions"]
                old_catalog = {item["name"]: item for item in original}
                new_catalog = {item["name"]: item for item in partial}
                report["partial_rename_evidence"] = {
                    "function_names": sorted(new_catalog),
                    "old_absent": OLD not in new_catalog,
                    "new_present": NEW in new_catalog,
                    "other_functions_exactly_preserved": all(
                        old_catalog[name] == new_catalog.get(name)
                        for name in old_catalog
                        if name != OLD
                    ),
                    "renamed_body_exactly_preserved": NEW in new_catalog
                    and {key: value for key, value in old_catalog[OLD].items() if key != "name"}
                    == {key: value for key, value in new_catalog[NEW].items() if key != "name"},
                }
        raise
    finally:
        if report.get("explicit_resume"):
            resume = report["explicit_resume"]
            hits = service.store.rows(
                "SELECT stage,artifact_id FROM events WHERE run_id=? AND id>? AND status='cache_hit' ORDER BY id",
                (resume["run_id"], resume["events_after_id"]),
            )
            resume["cache_hits"] = [
                {
                    "stage": hit["stage"],
                    "artifact_id": hit["artifact_id"],
                    "receipt": service.artifact(hit["artifact_id"]),
                }
                for hit in hits
            ]
            resume["cache_hit_count"] = len(hits)
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

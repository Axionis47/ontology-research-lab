"""Warm genuine extraction receipts for an existing run, with a dry-run default.

The running worker remains responsible for graph construction and validation.
This utility only invokes its exact saved model request for later document chunks.
It never changes a checkpoint, schema, graph, model response, or run status.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import re
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from oak.gemini_runtime import (
    LAUNCH_PROMPT,
    POLICY,
    cli_identity,
    configured_project,
    runtime_settings,
)
from oak.model import PROJECT, GeminiCLI, runtime_config
from oak.pipeline import _chunk_documents
from oak.store import Store, canonical, now


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def write_report(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def checkpoint_state(store: Store, run_id: str) -> dict:
    """Read the actual saved state without invoking or modifying the graph."""
    with SqliteSaver.from_conn_string(str(store.root / "checkpoints.sqlite")) as saver:
        checkpoint = saver.get_tuple({"configurable": {"thread_id": run_id}})
    if checkpoint is None:
        raise ValueError("Run has no saved LangGraph checkpoint")
    return checkpoint.checkpoint["channel_values"]


def current_environment(config: dict) -> dict:
    """Inspect request-identity inputs; no provider request is made."""
    return {
        "runtime": config,
        "settings": runtime_settings(config),
        "system_prompt": (PROJECT / "config/gemini-system.md").read_text(),
        "cli": cli_identity(),
        "project": configured_project(),
        "launch_prompt": LAUNCH_PROMPT,
        "policy": POLICY,
    }


def request_for_chunk(template: dict, stage: str, chunk: list[dict]) -> dict:
    """Replace only chunk documents and stage in the original saved request."""
    request = copy.deepcopy(template)
    prompt = json.loads(request["prompt"])
    prompt["stage"] = request["stage"] = stage
    prompt["inputs"]["documents"] = [
        {
            "document_id": f"d{index}",
            "text": document["text"],
            "source_id": document.get("source_id"),
        }
        for index, document in enumerate(chunk)
    ]
    request["prompt"] = canonical(prompt).decode()
    return request


def scalar_equal(actual: Any, source: Any) -> bool:
    """Compare direct field copies, accepting numeric typing but no unit conversion."""
    if isinstance(actual, bool) or actual is None:
        return actual == source
    if isinstance(actual, (int, float)):
        try:
            return Decimal(str(actual)) == Decimal(str(source))
        except InvalidOperation:
            return False
    return actual == source


def audit_output(payload: dict, chunk: list[dict]) -> dict:
    """Check citation coverage and direct same-name fields against actual source records.

    This is a narrow transcription audit, not a semantic validator for renamed,
    derived, or differently modeled properties. The normal worker still executes
    its graph checks over the complete result.
    """
    aliases = {f"d{index}": document for index, document in enumerate(chunk)}
    entities = list(payload.get("entities", []))
    for table in payload.get("entity_tables", []):
        if len(table["columns"]) != len(set(table["columns"])):
            raise ValueError("Extracted table contains duplicate columns")
        for row in table["rows"]:
            entities.append(
                {
                    "type": table["type"],
                    "properties": dict(zip(table["columns"], row["values"], strict=True)),
                    "source_ids": row["source_ids"],
                }
            )
    covered, matched, compared, unchecked = set(), 0, 0, 0
    mismatches = []
    for record in entities + payload.get("relations", []):
        sources = record.get("source_ids", [])
        if not sources or not set(sources).issubset(aliases):
            raise ValueError("Extracted record cites absent evidence")
        covered.update(sources)
        if "properties" not in record or len(sources) != 1:
            continue
        source_record = aliases[sources[0]].get("record")
        if not isinstance(source_record, dict):
            unchecked += len(record["properties"])
            continue
        for name, value in record["properties"].items():
            if name not in source_record:
                unchecked += 1
                continue
            compared += 1
            if scalar_equal(value, source_record[name]):
                matched += 1
            else:
                mismatches.append(
                    {
                        "source": sources[0],
                        "property": name,
                        "actual": value,
                        "source_value": source_record[name],
                    }
                )
    for omission in payload.get("ignored", []):
        if omission.get("document_id") not in aliases or not omission.get("reason"):
            raise ValueError("Invalid ignored-document explanation")
        covered.add(omission["document_id"])
    return {
        "documents": len(chunk),
        "entity_records": len(entities),
        "relation_records": len(payload.get("relations", [])),
        "ignored_documents": len(payload.get("ignored", [])),
        "covered_documents": len(covered),
        "missing_documents": sorted(set(aliases) - covered),
        "direct_fields_compared": compared,
        "direct_fields_matched": matched,
        "properties_without_direct_comparison": unchecked,
        "mismatches": mismatches,
        "first_source": chunk[0].get("locator"),
        "last_source": chunk[-1].get("locator"),
        "scope": "citation coverage and same-name source-field transcription only",
    }


def prepare(store: Store, run_id: str, stage_prefix: str | None) -> tuple[dict, list[dict]]:
    state = checkpoint_state(store, run_id)
    stage_prefix = stage_prefix or f"extract.r{state['round']}"
    matcher = re.compile(re.escape(stage_prefix) + r"\.(\d+)$")
    records = []
    for row in store.rows("SELECT * FROM events WHERE run_id=? ORDER BY id", (run_id,)):
        if matcher.fullmatch(row["stage"]) and row["artifact_id"]:
            value = store.get(row["artifact_id"])
            if isinstance(value, dict) and "request" in value:
                records.append((row, value))
    successful = [(row, value) for row, value in records if value.get("validated_success")]
    if not successful:
        raise ValueError("At least one successful original extraction receipt is required")
    first_row, first = successful[0]
    template = first["request"]
    environment = current_environment(runtime_config())
    changed = [name for name, value in environment.items() if template[name] != value]
    if changed:
        raise ValueError(f"Current model request environment differs from saved run: {changed}")
    template_prompt = json.loads(template["prompt"])
    if template_prompt["inputs"]["schema"] != store.get(state["schema_id"]):
        raise ValueError("Current checkpoint schema differs from the saved extraction request")
    documents = store.get(state["documents_id"])
    chunks = _chunk_documents(documents, template["runtime"]["extraction_chunk_bytes"])
    requests = [
        request_for_chunk(template, f"{stage_prefix}.{index}", chunk)
        for index, chunk in enumerate(chunks)
    ]
    reproduced = set()
    completed_indices, requested_indices, costs = set(), set(), []
    audits = []
    for row, value in records:
        index = int(matcher.fullmatch(row["stage"]).group(1))
        request = requests[index]
        if digest(request) != value["request_key"] or request != value["request"]:
            raise ValueError(f"Cannot reproduce original request exactly: {row['stage']}")
        reproduced.add(value["request_key"])
        requested_indices.add(index)
        if value.get("validated_success"):
            completed_indices.add(index)
            if value.get("estimated_usd") is not None:
                costs.append(value["estimated_usd"])
            if len(audits) < 3:
                audit = audit_output(value["validated_value"], chunks[index])
                audit.update(stage=row["stage"], evidence_id=row["artifact_id"])
                audits.append(audit)
    for audit in audits:
        if audit["missing_documents"] or audit["mismatches"]:
            raise ValueError(f"Original extraction failed the source transcription audit: {audit}")
    pending = sorted(requested_indices - completed_indices)
    remaining = [
        {"index": index, "request": request, "request_key": digest(request), "chunk": chunks[index]}
        for index, request in enumerate(requests)
        if index not in requested_indices
    ]
    report = {
        "run_id": run_id,
        "stage_prefix": stage_prefix,
        "created_at": now(),
        "documents_id": state["documents_id"],
        "schema_id": state["schema_id"],
        "source_document_count": len(documents),
        "total_chunks": len(chunks),
        "chunk_sizes": sorted(set(map(len, chunks))),
        "completed_chunks": len(completed_indices),
        "pending_original_chunks": pending,
        "remaining_chunks": len(remaining),
        "original_request_keys_reproduced": len(reproduced),
        "first_reproduced_key": first["request_key"],
        "first_receipt_id": first_row["artifact_id"],
        "original_input_fields": sorted(template_prompt["inputs"]),
        "runtime_identity_matched": True,
        "source_audits": audits,
        "mean_completed_chunk_cost_usd": mean(costs) if costs else None,
        "estimated_remaining_cost_usd": mean(costs) * len(remaining) if costs else None,
        "budget_before": store.budget(template["runtime"]["total_budget_usd"]),
        "results": [],
        "status": "dry_run_verified",
    }
    return report, remaining


class BoundedStore(Store):
    """Apply a stricter accounting ceiling without changing model request identity."""

    def __init__(self, root: Path, ceiling: float):
        super().__init__(root)
        self.ceiling = ceiling
        self.call_ids: list[str] = []
        self.call_lock = threading.Lock()

    def reserve(self, run_id: str, amount: float, limit: float) -> str:
        # Parent-worker spend also consumes this conservative allowance. Real
        # reservations remain atomic in the one authoritative Store ledger.
        call_id = super().reserve(run_id, amount, min(limit, self.ceiling))
        with self.call_lock:
            self.call_ids.append(call_id)
        return call_id


def prefetch_one(store: BoundedStore, run_id: str, item: dict) -> dict:
    """Use the genuine adapter, including its shared per-request file lock and cache."""
    request = item["request"]
    model = GeminiCLI(store, run_id)
    environment = current_environment(model.config)
    if any(request[name] != value for name, value in environment.items()):
        raise ValueError("Model environment changed after request verification")
    row = store.rows("SELECT status FROM runs WHERE id=?", (run_id,))[0]
    if row["status"] != "running":
        raise ValueError("Original run is no longer running; prefetch stopped")
    prompt = json.loads(request["prompt"])
    value = model.json(
        request["stage"], prompt["instruction"], prompt["inputs"], prompt["output_schema"]
    )
    cached = model._cached(item["request_key"])
    if cached is None or cached["value"] != value:
        raise ValueError("Actual model receipt did not match the verified original request key")
    audit = audit_output(value, item["chunk"])
    result = {
        "stage": request["stage"],
        "request_key": item["request_key"],
        "call_id": cached["call_id"],
        "evidence_id": cached["evidence_id"],
        "source_audit": audit,
    }
    store.event(
        run_id, "prefetch", "completed", "Actual extraction receipt ready for worker reuse", result
    )
    if audit["missing_documents"] or audit["mismatches"]:
        raise ValueError(f"Prefetched extraction failed its source audit: {result}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--root", type=Path, default=Path(".local"))
    parser.add_argument("--stage-prefix")
    parser.add_argument("--workers", type=int, choices=range(1, 4), default=3)
    parser.add_argument("--max-additional-usd", type=float, default=3.0)
    parser.add_argument("--run", action="store_true", help="Explicitly permit genuine model calls")
    args = parser.parse_args()
    if not 0 < args.max_additional_usd <= 5:
        parser.error("Additional prefetch allowance must be greater than zero and at most $5")
    store = Store(args.root)
    directory = store.root / "prefetch" / args.run_id
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "prefetch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report, items = prepare(store, args.run_id, args.stage_prefix)
        report.update(workers=args.workers, max_additional_usd=args.max_additional_usd)
        path = directory / ("run.json" if args.run else "dry-run.json")
        previous = json.loads(path.read_text()) if args.run and path.exists() else None
        baseline = (
            previous.get(
                "allowance_baseline_estimated_usd", previous["budget_before"]["estimated_usd"]
            )
            if previous is not None
            else report["budget_before"]["estimated_usd"]
        )
        report["allowance_baseline_estimated_usd"] = baseline
        if previous is not None:
            report["previous_report_artifact_id"] = store.put(
                "extraction_prefetch_report", previous
            )
        write_report(path, report)
        print(
            json.dumps(
                {**{k: v for k, v in report.items() if k != "results"}, "report_path": str(path)},
                indent=2,
            ),
            flush=True,
        )
        if not args.run:
            return
        bounded = BoundedStore(store.root, baseline + args.max_additional_usd)
        report.update(status="running", accounting_ceiling_usd=bounded.ceiling)
        write_report(path, report)
        remaining = iter(items)
        futures = {}
        try:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                for _ in range(args.workers):
                    item = next(remaining, None)
                    if item is not None:
                        futures[executor.submit(prefetch_one, bounded, args.run_id, item)] = item
                while futures:
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        futures.pop(future)
                        result = future.result()
                        report["results"].append(result)
                        write_report(path, report)
                        print(
                            json.dumps({"stage": result["stage"], "status": "cached_real_receipt"}),
                            flush=True,
                        )
                        item = next(remaining, None)
                        if item is not None:
                            futures[executor.submit(prefetch_one, bounded, args.run_id, item)] = (
                                item
                            )
            report["status"] = "completed"
        except BaseException as error:
            report.update(status="stopped", error=f"{type(error).__name__}: {error}")
            raise
        finally:
            report.update(
                ended_at=now(), new_call_ids=bounded.call_ids, budget_after=store.budget()
            )
            report["artifact_id"] = store.put("extraction_prefetch_report", report)
            write_report(path, report)


if __name__ == "__main__":
    main()

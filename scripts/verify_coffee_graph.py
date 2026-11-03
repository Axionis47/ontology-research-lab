"""Independently compare a saved Coffee graph with every pinned official CSV row.

This task-specific evaluator neither extracts a graph nor changes a kernel. Its
explicit CSV-to-schema mapping is validation-only. It never makes model calls,
reads benchmark answer labels, or supplies data to the reasoning pipeline.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from oak.corpus import normalize_snapshot
from oak.functions import execute_function
from oak.tasks.coffee import SOURCE_LOCK


def read_artifact(root: Path, identity: str) -> Any:
    """Verify immutable artifact bytes before using them as evaluation evidence."""
    raw = (root / "artifacts" / f"{identity}.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != identity:
        raise ValueError(f"Artifact digest mismatch: {identity}")
    return json.loads(raw)["data"]


def check_function_probes(
    graph: dict,
    schema: dict,
    functions: list[dict],
    probes: list[dict],
    by_date: dict[str, dict],
    mapping: dict[str, str],
) -> dict:
    """Re-execute genuine generated probes and independently check supported semantics.

    These two task-specific meanings were read from the actual generated catalog.
    They are evaluator expectations, never supplied functions or agent answers.
    Additional generated functions remain explicitly unverified by this evaluator.
    """
    checks = []
    semantics = {
        "get_coffee_market_day": ("source_record", "entities"),
        "get_coffee_market_record_by_date": ("source_record", "records"),
        "get_coffee_price_range": ("high_minus_low", None),
        "get_coffee_price_range_by_date": ("high_minus_low", "range"),
    }
    for probe in probes:
        name, args = probe["function"], probe["args"]
        check = {"function": name, "args": args, "status": "unverified"}
        if name not in semantics or set(args) != {"date"}:
            checks.append(
                {**check, "reason": "No independent evaluator mapping for this interface"}
            )
            continue
        expected_row = by_date.get(args["date"])
        if expected_row is None:
            checks.append({**check, "reason": "Probe date has no official source row"})
            continue
        try:
            executed = execute_function(graph, functions, name, args, schema=schema)
            actual = executed["value"]
            same_receipt = actual == probe["result"]["value"]
            meaning, result_field = semantics[name]
            if meaning == "high_minus_low":
                expected = Decimal(expected_row["High"]) - Decimal(expected_row["Low"])
                scalar = (
                    actual.get(result_field)
                    if result_field and isinstance(actual, dict)
                    else actual
                )
                correct = type(scalar) in {int, float} and Decimal(str(scalar)) == expected
                comparison = {"expected_high_minus_low": str(expected), "actual": scalar}
            else:
                entities = actual.get(result_field) if isinstance(actual, dict) else None
                correct = isinstance(entities, list) and len(entities) == 1
                comparisons = {}
                if correct:
                    values = entities[0]["properties"]
                    for field, prop in mapping.items():
                        value = values.get(prop)
                        if field in {"Date", "Currency"}:
                            matches = type(value) is str and value == expected_row[field]
                        else:
                            matches = type(value) in {int, float} and Decimal(
                                str(value)
                            ) == Decimal(expected_row[field])
                        comparisons[field] = matches
                    correct = all(comparisons.values())
                comparison = {
                    "entity_count": len(entities) if isinstance(entities, list) else None,
                    "field_matches": comparisons,
                }
            check.update(
                status="passed" if correct and same_receipt else "failed",
                matches_original_execution=same_receipt,
                source_comparison=comparison,
                dependencies=executed["dependencies"],
                executed_steps=len(executed["steps"]),
            )
            # The whole graph's provenance is already checked separately. Avoid
            # repeating thousands of source IDs in a compact audit report.
            check["dependencies"] = {
                key: value
                for key, value in executed["dependencies"].items()
                if key not in {"sources", "source_ids"}
            }
        except (ValueError, TypeError, KeyError, InvalidOperation) as error:
            check.update(status="failed", reason=f"{type(error).__name__}: {error}")
        checks.append(check)
    covered = {check["function"] for check in checks}
    catalog_names = {function["name"] for function in functions}
    status = (
        "failed"
        if any(check["status"] == "failed" for check in checks)
        else (
            "passed"
            if checks
            and covered == catalog_names
            and all(check["status"] == "passed" for check in checks)
            else "unverified"
        )
    )
    return {
        "status": status,
        "checks": checks,
        "coverage": "Recorded generated probes only; no benchmark score claimed",
        "unsupported_or_unprobed_functions": sorted(catalog_names - covered),
        "volume_units": "No unit conversion is evaluated or supplied",
    }


def evaluate(root: Path, run_id: str, csv_path: Path, mapping: dict[str, str]) -> dict:
    """Validate exact field values, primary keys, coverage, and source attribution."""
    with sqlite3.connect(f"file:{root / 'catalog.sqlite'}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        run_row = connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if run_row is None:
            raise ValueError("The requested real construction run does not exist")
        run = dict(run_row)
        events = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM events WHERE run_id=? AND stage IN "
                "('schema','graph','functions','function_probes') ORDER BY id",
                (run_id,),
            )
        ]
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "unverified",
        "run_id": run_id,
        "run_status_at_check": run["status"],
        "evidence_type": "independent_full_source_graph_comparison",
        "mapping": mapping,
        "mapping_role": "Task-specific evaluator only; never an extractor or runtime function",
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "model_calls": 0,
        "benchmark_answer_labels_read": False,
    }
    graphs = [
        event for event in events if event["stage"] == "graph" and event["status"] == "completed"
    ]
    if not graphs:
        return {**report, "reason": "No complete graph artifact has been published by this run"}
    graph_event = graphs[-1]
    schema_event = next(
        event
        for event in reversed(events)
        if event["stage"] == "schema" and event["id"] < graph_event["id"]
    )
    inputs = read_artifact(root, run["input_id"])
    snapshot = read_artifact(root, inputs["corpus_id"])
    graph = read_artifact(root, graph_event["artifact_id"])
    schema = read_artifact(root, schema_event["artifact_id"])
    source_lock = json.loads(SOURCE_LOCK.read_text())
    source = source_lock["corpus"]
    raw = csv_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != source["sha256"] or len(raw) != source["bytes"]:
        raise ValueError("CSV bytes differ from the pinned official source")
    if snapshot["raw_sha256"] != digest:
        raise ValueError("Construction corpus is not the checked official CSV")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    rows = list(reader)
    if reader.fieldnames != source["columns"] or set(mapping) != set(source["columns"]):
        raise ValueError("Evaluation mapping must cover exactly the pinned CSV columns")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Evaluation property mapping must be one-to-one")
    documents = normalize_snapshot(snapshot)
    by_document = {document["document_id"]: document for document in documents}
    by_date = {row["Date"]: row for row in rows}
    issues: Counter = Counter()
    examples: list[dict] = []

    def issue(category: str, **details) -> None:
        issues[category] += 1
        if len(examples) < 30:
            examples.append({"category": category, **details})

    if len(rows) != source["records"] or len(by_date) != len(rows):
        issue("official_row_count_or_primary_key_mismatch", rows=len(rows), dates=len(by_date))
    if len(documents) != len(rows) or len(by_document) != len(rows):
        issue("corpus_document_count_mismatch", actual=len(documents), expected=len(rows))
    if [document["record"] for document in documents] != rows:
        issue("normalized_documents_differ_from_csv")
    if graph.get("source_document_count") != len(rows):
        issue("declared_graph_document_count_mismatch", actual=graph.get("source_document_count"))
    if graph.get("ignored_documents"):
        issue("ignored_documents", count=len(graph["ignored_documents"]))
    if len(graph["nodes"]) != len(rows):
        issue("graph_record_count_mismatch", actual=len(graph["nodes"]), expected=len(rows))
    if graph["edges"]:
        issue("unexpected_relations_for_flat_source", count=len(graph["edges"]))
    date_counts: Counter = Counter()
    source_counts: Counter = Counter()
    field_checks: Counter = Counter()
    observed_types: Counter = Counter()
    for node in graph["nodes"]:
        observed_types[node["type"]] += 1
        definition = schema["entity_types"].get(node["type"])
        if definition is None or definition["primary_key"] != mapping["Date"]:
            issue("unexpected_record_type_or_primary_key", entity_id=node["id"])
            continue
        if not set(mapping.values()).issubset(definition["properties"]):
            issue("schema_missing_mapped_properties", entity_type=node["type"])
            continue
        properties = node["properties"]
        date = properties.get(mapping["Date"])
        if not isinstance(date, str) or date not in by_date:
            issue("unexpected_or_invalid_date", entity_id=node["id"], actual=date)
            continue
        date_counts[date] += 1
        expected = by_date[date]
        for field, prop in mapping.items():
            field_checks[field] += 1
            value = properties.get(prop)
            property_type = definition["properties"][prop]["type"]
            if field in {"Date", "Currency"}:
                matches = (
                    property_type == "string" and type(value) is str and value == expected[field]
                )
            else:
                try:
                    matches = (
                        property_type in {"integer", "number"}
                        and type(value) in {int, float}
                        and Decimal(str(value)).is_finite()
                        and Decimal(str(value)) == Decimal(expected[field])
                    )
                except InvalidOperation:
                    matches = False
            if not matches:
                issue(
                    "field_value_mismatch",
                    date=date,
                    field=field,
                    expected=expected[field],
                    actual=value,
                )
        if set(properties) != set(mapping.values()):
            issue(
                "unexpected_graph_properties",
                date=date,
                fields=sorted(set(properties) - set(mapping.values())),
            )
        if len(node["sources"]) != 1:
            issue("record_source_count_mismatch", date=date, actual=len(node["sources"]))
        for reference in node["sources"]:
            identity = reference.get("document_id")
            source_counts[identity] += 1
            document = by_document.get(identity)
            if document is None:
                issue("unknown_source_document", date=date, document_id=identity)
            elif (
                document["record"]["Date"] != date
                or reference.get("source_ref") != document["locator"]
            ):
                issue("source_date_or_locator_mismatch", date=date, document_id=identity)
    missing_dates = sorted(set(by_date) - set(date_counts))
    duplicate_dates = {date: count for date, count in date_counts.items() if count != 1}
    missing_sources = sorted(set(by_document) - set(source_counts))
    duplicate_sources = {identity: count for identity, count in source_counts.items() if count != 1}
    for category, values in (
        ("missing_dates", missing_dates),
        ("duplicate_dates", duplicate_dates),
        ("missing_sources", missing_sources),
        ("duplicate_sources", duplicate_sources),
    ):
        if values:
            issue(category, count=len(values), examples=list(values)[:10])
    function_events = [
        event
        for event in events
        if event["stage"] == "functions" and event["id"] > graph_event["id"]
    ]
    functions = read_artifact(root, function_events[-1]["artifact_id"]) if function_events else []
    probe_events = [
        event
        for event in events
        if event["stage"] == "function_probes"
        and event["status"] == "passed"
        and event["id"] > graph_event["id"]
    ]
    probes = read_artifact(root, probe_events[-1]["artifact_id"]) if probe_events else []
    report.update(
        status="passed" if not issues else "failed",
        artifacts={
            "schema": schema_event["artifact_id"],
            "graph": graph_event["artifact_id"],
            "corpus": inputs["corpus_id"],
            "run_input": run["input_id"],
            "functions": function_events[-1]["artifact_id"] if function_events else None,
            "function_probes": probe_events[-1]["artifact_id"] if probe_events else None,
        },
        official_source={
            "csv_sha256": digest,
            "csv_bytes": len(raw),
            "rows": len(rows),
            "source_lock_sha256": hashlib.sha256(SOURCE_LOCK.read_bytes()).hexdigest(),
            "repository_commit": source_lock["commit"],
        },
        counts={
            "graph_records": len(graph["nodes"]),
            "unique_dates": len(date_counts),
            "documents": len(documents),
            "source_attributions": sum(source_counts.values()),
            "field_checks": dict(field_checks),
            "total_field_checks": sum(field_checks.values()),
            "entity_types": dict(observed_types),
        },
        issue_counts=dict(issues),
        issue_examples=examples,
        functions={
            "status": "execution_probes_recorded" if probes else "not_yet_available",
            "names": [fn["name"] for fn in functions],
            "output_schemas": {fn["name"]: fn["output_schema"] for fn in functions},
            "probe_count": len(probes),
            "probe_correctness": "Execution receipts alone do not prove answer correctness",
            "independent_check": check_function_probes(
                graph, schema, functions, probes, by_date, mapping
            ),
        },
        semantics={
            "numeric_comparison": "Decimal(str(actual)) equals Decimal(original_csv_text)",
            "Volume": "Source numeric values verified; CSV supplies no unit definition. Contracts, lots, kilograms, and unit conversions remain unverified.",
            "record_count": "Count of supplied daily rows, not volume or individual transactions",
        },
        limitations=[
            "Validates source preservation, not unseen agent planning or official benchmark accuracy",
            "Does not validate unsupported units or interpretations beyond the source table",
        ],
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(".local"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--csv", type=Path)
    parser.add_argument(
        "--mapping", type=Path, help="Explicit JSON CSV-column to schema-property mapping"
    )
    parser.add_argument("--output", type=Path, default=Path("docs/verification/coffee-graph.json"))
    args = parser.parse_args()
    columns = json.loads(SOURCE_LOCK.read_text())["corpus"]["columns"]
    mapping = (
        json.loads(args.mapping.read_text()) if args.mapping else {name: name for name in columns}
    )
    try:
        report = evaluate(
            args.root.resolve(),
            args.run_id,
            args.csv or args.root / "benchmarks/toolqa-coffee/coffee_price.csv",
            mapping,
        )
    except (ValueError, KeyError, TypeError, OSError) as error:
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "failed",
            "run_id": args.run_id,
            "error": f"{type(error).__name__}: {error}",
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": str(args.output),
                "counts": report.get("counts"),
                "issues": report.get("issue_counts"),
            }
        )
    )
    return 0 if report["status"] == "passed" else 2 if report["status"] == "unverified" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Persist real deterministic historical replay acceptance with authored adapters.

The source is the checksum-pinned official Coffee CSV. Schema/function programs,
revision adapters and the faulty program variant are explicit component inputs,
not model-generated artifacts or benchmark-answer templates. This command makes
no model call and no live MCP acquisition. It runs actual OWL/HermiT validation.
"""

from __future__ import annotations

import argparse
import json
import uuid
from copy import deepcopy
from pathlib import Path

from oak.construction_campaign import select_preserving_candidate
from oak.corpus import load_local_corpus
from oak.functions import execute_function
from oak.historical_replay import (
    AdapterEdge,
    check_candidate_replay,
    register_adapter_edge,
    register_kernel_bank,
    seal_execution_case,
    seal_replay_case,
)
from oak.migration import MigrationSpec, migrate_graph
from oak.ontology import validate_ontology
from oak.regression import AdapterSpec, FunctionMapping
from oak.replay_contracts import ComparisonContract, RecordedCall, ReplayCase, ResultBinding
from oak.store import Store, now
from oak.tasks.coffee import DEFAULT_CACHE, load_coffee

PROJECT = Path(__file__).resolve().parents[1]


def coffee_inputs() -> tuple[dict, dict, list[dict]]:
    """Build an explicit component schema over twenty genuine retained CSV rows."""
    coffee = load_coffee()
    documents = coffee["corpus"]["documents"][:20]
    rows = [json.loads(document["content"]) for document in documents]
    schema = {
        "name": "AuthoredCoffeeReplayContract",
        "entity_types": {
            "CoffeeRow": {
                "primary_key": "Date",
                "properties": {
                    name: {
                        "type": "string" if name in {"Date", "Currency"} else "number",
                        "required": True,
                    }
                    for name in coffee["corpus"]["columns"]
                },
            }
        },
        "relations": {},
    }
    graph = {
        "nodes": [
            {
                "id": document["id"],
                "type": "CoffeeRow",
                "sources": [{"document_id": document["id"], "source_ref": document["source_ref"]}],
                "properties": {
                    key: value if key in {"Date", "Currency"} else float(value)
                    for key, value in row.items()
                },
            }
            for document, row in zip(documents, rows, strict=True)
        ],
        "edges": [],
    }
    return graph, schema, rows


def catalog(kind: str, high: str, suffix: str, *, include_count: bool = False) -> list[dict]:
    functions = [
        {
            "name": f"maximum_{suffix}",
            "description": "Maximum recorded high over the retained population.",
            "inputs": {"type": "object", "properties": {}, "additionalProperties": False},
            "output_schema": {"type": "number"},
            "steps": [
                {
                    "id": f"rows_{suffix}",
                    "operator": "lookup_entities",
                    "args": {"entity_types": [kind]},
                },
                {
                    "id": f"value_{suffix}",
                    "operator": "aggregate_values",
                    "args": {
                        "items": {"$step": f"rows_{suffix}"},
                        "request": {"operation": "max", "field": high},
                    },
                },
            ],
            "result": {"$step": f"value_{suffix}"},
        },
        {
            "name": "difference",
            "description": "Subtract a supplied comparison value from an earlier computed number.",
            "inputs": {
                "type": "object",
                "properties": {"left": {"type": "number"}, "right": {"type": "number"}},
                "required": ["left", "right"],
                "additionalProperties": False,
            },
            "output_schema": {"type": "number"},
            "steps": [
                {
                    "id": "subtract",
                    "operator": "arithmetic",
                    "args": {
                        "operation": "subtract",
                        "left": {"$arg": "left"},
                        "right": {"$arg": "right"},
                    },
                }
            ],
            "result": {"$step": "subtract"},
        },
    ]
    point = deepcopy(functions[0])
    point.update(
        name=f"point_{suffix}",
        description="Read the high of a supplied date through the current ontology.",
        inputs={
            "type": "object",
            "properties": {"date": {"type": "string"}},
            "required": ["date"],
            "additionalProperties": False,
        },
    )
    point["steps"][0]["args"]["primary_key"] = {"Date": {"$arg": "date"}}
    functions.append(point)
    if include_count:
        count = deepcopy(functions[0])
        count.update(
            name=f"count_{suffix}",
            description="Count the actual retained population.",
            output_schema={"type": "integer"},
        )
        count["steps"][1]["args"]["request"] = {"operation": "count"}
        functions.append(count)
    return functions


def rename_schema(schema, old_type, new_type, old_field, new_field):
    result = deepcopy(schema)
    entity = result["entity_types"].pop(old_type)
    entity["properties"][new_field] = entity["properties"].pop(old_field)
    result["entity_types"][new_type] = entity
    result["name"] = f"AuthoredReplay{new_type}"
    return result


def edge_for(parent, child, old_suffix, new_suffix, migration, *, with_count=False):
    pairs = [
        (f"maximum_{old_suffix}", f"maximum_{new_suffix}"),
        ("difference", "difference"),
        (f"point_{old_suffix}", f"point_{new_suffix}"),
    ]
    if with_count:
        pairs.append((f"count_{old_suffix}", f"count_{new_suffix}"))
    return AdapterEdge(
        parent_id=parent,
        child_id=child,
        migration=migration,
        call_adapter=AdapterSpec(
            old_revision=parent,
            new_revision=child,
            mappings=[FunctionMapping(old_function=old, new_function=new) for old, new in pairs],
        ),
        step_mappings={
            old: {
                f"rows_{old_suffix}": f"rows_{new_suffix}",
                f"value_{old_suffix}": f"value_{new_suffix}",
            }
            for old, _ in pairs
            if old != "difference"
        },
    )


def build_chain(root: Path) -> dict:
    """Execute the authored acceptance scenario once in a new durable Store."""
    root = Path(root)
    if (root / "catalog.sqlite").exists():
        raise ValueError("Acceptance Store already exists; select a new output directory")
    store = Store(root)
    graph1, schema1, rows = coffee_inputs()
    corpus_id = store.put(
        "corpus_snapshot",
        load_local_corpus(
            DEFAULT_CACHE / "coffee_price.csv", source_id="toolqa-coffee:official-corpus"
        ),
    )
    documents_id = store.put(
        "retained_source_documents", load_coffee()["corpus"]["documents"][: len(rows)]
    )
    queries = [
        "Maximum recorded high in this retained population",
        "Count the retained population",
        "Read the high for the supplied retained date",
    ]
    task_id = "coffee-historical-replay"
    with store.connect() as db:
        db.execute(
            "INSERT INTO tasks(id,data) VALUES(?,?)",
            (
                task_id,
                json.dumps(
                    {
                        "name": "Genuine Coffee historical replay",
                        "scope": "First 20 retained official Coffee rows",
                        "corpus_id": corpus_id,
                        "example_queries": queries,
                    }
                ),
            ),
        )
    run_id = store.create_run(
        task_id, "construct", {"purpose": "Actual historical replay acceptance on genuine Coffee"}
    )
    store.set_run(run_id, "running")

    def save_kernel(schema, functions, graph, parent=None, *, repair_of=None):
        validation = validate_ontology(
            schema, store.root / "authored-validation" / uuid.uuid4().hex
        )
        validation_id = store.put("authored_kernel_ontology_validation", validation)
        if not validation["valid"]:
            raise ValueError("Authored acceptance schema failed actual OWL/HermiT validation")
        probes = []
        for function in functions:
            arguments = (
                {"date": rows[0]["Date"]}
                if function["name"].startswith("point_")
                else {"left": float(rows[0]["High"]), "right": float(rows[0]["Low"])}
                if function["name"] == "difference"
                else {}
            )
            probes.append(
                execute_function(
                    deepcopy(graph),
                    functions,
                    function["name"],
                    arguments,
                    schema=schema,
                    artifact_store=store,
                )["capture_id"]
            )
        identity = store.put(
            "kernel_revision",
            {
                "task_id": task_id,
                "scope": "First 20 retained official Coffee rows",
                "corpus_id": corpus_id,
                "documents_id": documents_id,
                "queries": queries,
                "run_id": run_id,
                "parent": parent,
                "repair_of": repair_of,
                "created_at": now(),
                "schema": schema,
                "functions": functions,
                "graph": graph,
                "historical_replay_policy": "inherited_v1",
                "construction_profile": "corpus_v1",
                "validation": validation,
                "assessment": {
                    "status": "passed",
                    "basis": "actual_hermit_and_authored_function_execution_probes",
                    "independent_task_assessment": "not_checked",
                    "validation_ref": validation_id,
                    "execution_capture_refs": probes,
                },
            },
        )
        with store.connect() as db:
            db.execute(
                "INSERT INTO revisions(id,task_id,parent,created_at,status) VALUES(?,?,?,?,?)",
                (identity, task_id, parent, store.get(identity)["created_at"], "candidate"),
            )
        return identity

    functions1 = catalog("CoffeeRow", "High", "one")
    k1 = save_kernel(schema1, functions1, graph1)
    first = execute_function(
        deepcopy(graph1), functions1, "maximum_one", {}, schema=schema1, artifact_store=store
    )
    case1 = seal_execution_case(
        store,
        k1,
        first["capture_id"],
        run_id=run_id,
        question="Maximum recorded high in this retained population",
    )
    comparison_value = float(rows[0]["Low"])
    second = execute_function(
        deepcopy(graph1),
        functions1,
        "difference",
        {"left": first["value"], "right": comparison_value},
        schema=schema1,
        artifact_store=store,
    )
    trajectory = seal_replay_case(
        store,
        ReplayCase(
            origin_kernel_id=k1,
            run_id=run_id,
            question="Compare the maximum high with the first retained day's low",
            scope="trajectory",
            calls=[
                RecordedCall(capture_id=first["capture_id"]),
                RecordedCall(
                    capture_id=second["capture_id"],
                    bindings=[ResultBinding(argument_path=["left"], prior_call=0)],
                ),
            ],
            comparison_id=store.put(
                "replay_comparison", ComparisonContract().model_dump(mode="json")
            ),
        ),
    )
    point_execution = execute_function(
        deepcopy(graph1),
        functions1,
        "point_one",
        {"date": rows[0]["Date"]},
        schema=schema1,
        artifact_store=store,
    )
    point_case = seal_execution_case(
        store,
        k1,
        point_execution["capture_id"],
        run_id=run_id,
        question="Read the high for the supplied retained date",
    )
    register_kernel_bank(store, k1, [case1, trajectory, point_case])
    report1 = check_candidate_replay(store, k1, run_id=run_id)

    schema2 = rename_schema(schema1, "CoffeeRow", "Quote", "High", "Peak")
    migration12 = MigrationSpec(
        type_renames={"CoffeeRow": "Quote"}, property_renames={"CoffeeRow": {"High": "Peak"}}
    )
    graph2 = migrate_graph(graph1, migration12, schema1, schema2)["graph"]
    functions2 = catalog("Quote", "Peak", "two", include_count=True)
    k2 = save_kernel(schema2, functions2, graph2, k1)
    newer = execute_function(
        deepcopy(graph2), functions2, "count_two", {}, schema=schema2, artifact_store=store
    )
    case2 = seal_execution_case(
        store, k2, newer["capture_id"], run_id=run_id, question="Count the retained population"
    )
    register_kernel_bank(store, k2, [case2])
    edge12 = register_adapter_edge(store, edge_for(k1, k2, "one", "two", migration12))
    report2 = check_candidate_replay(store, k2, run_id=run_id)

    schema3 = rename_schema(schema2, "Quote", "MarketRecord", "Peak", "Highest")
    schema3["entity_types"]["MarketDate"] = {
        "primary_key": "Date",
        "properties": {"Date": deepcopy(schema2["entity_types"]["Quote"]["properties"]["Date"])},
    }
    schema3["relations"] = {
        "has_values": {
            "source": "MarketDate",
            "target": "MarketRecord",
            "characteristics": ["functional"],
        }
    }
    migration23 = MigrationSpec.model_validate(
        {
            "records": [
                {
                    "sources": {"quote": "Quote"},
                    "target_type": "MarketDate",
                    "properties": {"Date": {"source": "quote", "property": "Date"}},
                    "identity": {"source": "quote"},
                },
                {
                    "sources": {"quote": "Quote"},
                    "target_type": "MarketRecord",
                    "properties": {
                        ("Highest" if name == "Peak" else name): {
                            "source": "quote",
                            "property": name,
                        }
                        for name in schema2["entity_types"]["Quote"]["properties"]
                    },
                    "identity": {"keys": ["Date"]},
                },
            ],
            "derived_relations": [
                {
                    "source_type": "Quote",
                    "source_target_type": "MarketDate",
                    "target_target_type": "MarketRecord",
                    "relation": "has_values",
                }
            ],
        }
    )
    graph3 = migrate_graph(graph2, migration23, schema2, schema3)["graph"]
    functions3 = catalog("MarketRecord", "Highest", "three", include_count=True)
    point3 = next(function for function in functions3 if function["name"] == "point_three")
    point3["steps"][0]["args"]["entity_types"] = ["MarketDate"]
    point3["steps"].insert(
        1,
        {
            "id": "linked_values",
            "operator": "traverse_relations",
            "args": {
                "start_entity_ids": [{"$path": ["rows_three", 0, "id"]}],
                "relation_types": ["has_values"],
                "include_starting_entities": False,
            },
        },
    )
    point3["steps"][-1]["args"]["items"] = {"$path": ["linked_values", "entities"]}
    k3 = save_kernel(schema3, functions3, graph3, k2)
    register_kernel_bank(store, k3)
    edge23 = register_adapter_edge(
        store, edge_for(k2, k3, "two", "three", migration23, with_count=True)
    )
    report3 = check_candidate_replay(store, k3, run_id=run_id)

    broken = deepcopy(functions3)
    broken[0]["steps"][1]["args"]["request"]["operation"] = "min"
    bad_kernel_id = save_kernel(schema3, broken, graph3, k2)
    register_kernel_bank(store, bad_kernel_id)
    bad_edge = register_adapter_edge(
        store, edge_for(k2, bad_kernel_id, "two", "three", migration23, with_count=True)
    )
    bad_report = check_candidate_replay(store, bad_kernel_id, run_id=run_id)
    repaired_kernel_id = save_kernel(schema3, functions3, graph3, k2, repair_of=bad_kernel_id)
    register_kernel_bank(store, repaired_kernel_id)
    repaired_edge = register_adapter_edge(
        store, edge_for(k2, repaired_kernel_id, "two", "three", migration23, with_count=True)
    )
    repaired_report = check_candidate_replay(store, repaired_kernel_id, run_id=run_id)
    retained_after_failure = select_preserving_candidate(
        k2, bad_kernel_id, bad_report, execution_eligible=True, preferred=True
    )
    retained_after_repair = select_preserving_candidate(
        retained_after_failure,
        repaired_kernel_id,
        repaired_report,
        execution_eligible=True,
        preferred=True,
    )
    repair_receipt = store.event(
        run_id,
        "historical_repair",
        "completed",
        "Authored faulty program repaired against unchanged original cases",
        {
            "authorship": "explicit_component_test_program_correction",
            "failed_candidate_id": bad_kernel_id,
            "failed_report_id": bad_report["report_id"],
            "repair_candidate_id": repaired_kernel_id,
            "repair_report_id": repaired_report["report_id"],
            "parent_id": k2,
            "retained_after_failure": retained_after_failure,
            "retained_after_repair": retained_after_repair,
        },
    )
    store.set_run(
        run_id,
        "completed",
        result={"kernel_id": k3, "historical_replay_report_id": report3["report_id"]},
    )
    return {
        "store": store,
        "run_id": run_id,
        "task_id": task_id,
        "kernels": [k1, k2, k3],
        "edges": [edge12, edge23],
        "reports": [report1, report2, report3],
        "bad_kernel_id": bad_kernel_id,
        "bad_report": bad_report,
        "bad_edge": bad_edge,
        "repaired_kernel_id": repaired_kernel_id,
        "repaired_edge": repaired_edge,
        "repaired_report": repaired_report,
        "repair_receipt": repair_receipt,
        "case_ids": [case1, trajectory, point_case, case2],
        "graphs": [graph1, graph2, graph3],
        "captures": [first["capture_id"], second["capture_id"], newer["capture_id"]],
    }


def acceptance_receipt(chain: dict) -> dict:
    """Summarize only actual saved checks and execution counters."""
    store = chain["store"]
    reports = [*chain["reports"], chain["repaired_report"]]
    failure = chain["bad_report"]
    checks = {
        "all_three_revisions_preserved": all(report["allowed"] for report in chain["reports"]),
        "older_case_regression_caught": failure["status"] == "regressed" and not failure["allowed"],
        "newer_case_still_preserved": any(
            report["origin_kernel_id"] == chain["kernels"][1] and report["status"] == "preserved"
            for report in failure["reports"]
        ),
        "repair_preserved_original_bank": chain["repaired_report"]["allowed"]
        and set(report["original_case_id"] for report in chain["repaired_report"]["reports"])
        == set(chain["case_ids"]),
        "two_edges_executed_for_old_cases": all(
            len(report["adapter_path"]) == 2
            for report in chain["reports"][2]["reports"]
            if report["origin_kernel_id"] == chain["kernels"][0]
        ),
    }
    model_calls = len(store.rows("SELECT id FROM model_calls"))
    live_calls = len(store.rows("SELECT id FROM events WHERE stage='mcp_call'"))
    checks["zero_model_and_live_mcp_calls"] = model_calls == live_calls == 0
    repair = store.get(chain["repair_receipt"])
    checks["winner_retained_then_repaired"] = (
        repair["retained_after_failure"] == chain["kernels"][1]
        and repair["retained_after_repair"] == chain["repaired_kernel_id"]
    )
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "authorship": "Explicit component-test schema/function catalogs and shared adapters; no model generation claimed",
        "source": "Checksum-verified official ToolQA Coffee corpus, first 20 retained rows",
        "independent_task_assessment": "not_checked",
        "store_root": str(store.root),
        "run_id": chain["run_id"],
        "task_id": chain["task_id"],
        "kernel_ids": chain["kernels"],
        "adapter_edge_ids": chain["edges"],
        "case_ids": chain["case_ids"],
        "report_ids": [report["report_id"] for report in reports],
        "failed_candidate_id": chain["bad_kernel_id"],
        "failed_report_id": failure["report_id"],
        "repair_candidate_id": chain["repaired_kernel_id"],
        "repair_receipt_id": chain["repair_receipt"],
        "checks": checks,
        "model_calls": model_calls,
        "live_mcp_calls": live_calls,
        "budget": store.budget(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=PROJECT / ".local/verification/historical-replay/chain"
    )
    args = parser.parse_args()
    directory = args.root.resolve() / ("run-" + uuid.uuid4().hex)
    chain = build_chain(directory)
    receipt = acceptance_receipt(chain)
    receipt_path = directory / "acceptance.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "receipt": str(receipt_path),
                "checks": receipt["checks"],
            },
            indent=2,
        )
    )
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

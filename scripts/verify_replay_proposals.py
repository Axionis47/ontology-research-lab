"""Optional paid verification of shared adapter proposal and feedback-driven repair.

The model writes bounded adapter/function proposals. Every regression check is
the production offline executor over genuine retained Coffee evidence. The
authoritative existing ledger accounts for every real generation.
"""

from __future__ import annotations

import argparse
import json
import uuid
from copy import deepcopy
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from oak.functions import FunctionSpec
from oak.historical_replay import (
    AdapterEdge,
    check_candidate_replay,
    register_adapter_edge,
    register_kernel_bank,
    seal_execution_case,
)
from oak.model import GeminiCLI, runtime_config
from oak.store import Store, canonical, implementation_receipt
from scripts.verify_historical_replay import acceptance_receipt, build_chain


class RepairProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    functions: list[FunctionSpec]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-paid", action="store_true", required=True)
    parser.add_argument("--ledger-root", type=Path, required=True)
    parser.add_argument("--budget-ceiling-usd", type=float, required=True)
    parser.add_argument(
        "--resume",
        type=Path,
        help="Resume an actual failed receipt, reusing only validated generation evidence",
    )
    parser.add_argument(
        "--root", type=Path, default=Path(".local/verification/historical-replay/model-proposals")
    )
    args = parser.parse_args()
    ledger = Store(args.ledger_root)
    config = runtime_config()
    before = ledger.budget(config["total_budget_usd"])
    if not 0 < args.budget_ceiling_usd <= config["total_budget_usd"]:
        raise ValueError("Verification ceiling must fit the existing global limit")
    if before["estimated_usd"] + before["reserved_usd"] >= args.budget_ceiling_usd:
        raise ValueError("Existing ledger has no room under this verification ceiling")
    if ledger.rows("SELECT id FROM runs WHERE status IN ('queued','running')"):
        raise ValueError("Another execution is active; preserve one paid verification owner")
    if args.resume:
        summary = json.loads(args.resume.read_text())
        if (
            summary["status"] != "failed"
            or summary["budget_ceiling_usd"] != args.budget_ceiling_usd
        ):
            raise ValueError("Resume requires a failed receipt under the same ceiling")
        if Path(summary["ledger_root"]).resolve() != ledger.root.resolve():
            raise ValueError("Resume must retain the original ledger")
        directory = args.resume.resolve().parent
        store = Store(summary["replay_root"])
        deterministic = summary["deterministic_authored_acceptance"]
        run_id, model_run = deterministic["run_id"], summary["model_run_id"]
        newer_case = store.get(deterministic["case_ids"][-1])
        chain = {
            "store": store,
            "run_id": run_id,
            "kernels": deterministic["kernel_ids"],
            "captures": [None, None, newer_case["calls"][0]["capture_id"]],
        }
        summary.update(
            status="running",
            resumed_from=str(args.resume.resolve()),
            resumed_budget=before,
            reports=[],
        )
        summary.pop("error", None)
        output_path = directory / ("receipt-resume-" + uuid.uuid4().hex + ".json")
    else:
        directory = args.root.resolve() / ("run-" + uuid.uuid4().hex)
        chain = build_chain(directory / "replay")
        deterministic = acceptance_receipt(chain)
        if deterministic["status"] != "passed":
            raise ValueError("Deterministic acceptance must pass before any paid proposal")
        store, run_id = chain["store"], chain["run_id"]
        model_run = ledger.create_run(
            "historical-replay-verification",
            "verification",
            {
                "budget_ceiling_usd": args.budget_ceiling_usd,
                "purpose": "Real shared adapter generation and regression repair",
                "replay_store": str(store.root),
            },
        )
        summary = {
            "model_run_id": model_run,
            "ledger_root": str(ledger.root),
            "replay_root": str(store.root),
            "budget_before": before,
            "budget_ceiling_usd": args.budget_ceiling_usd,
            "implementation": implementation_receipt(),
            "deterministic_authored_acceptance": deterministic,
            "status": "running",
            "model_receipts": [],
            "reports": [],
        }
        output_path = directory / "receipt.json"
    ledger.set_run(model_run, "running")
    model = GeminiCLI(ledger, model_run, budget_ceiling_usd=args.budget_ceiling_usd)

    def generate(stage, instruction, payload, schema):
        value = model.json(stage, instruction, payload, schema)
        for row in ledger.rows(
            "SELECT id,status,estimated,reserved,evidence_id FROM model_calls WHERE run_id=?",
            (model_run,),
        ):
            if row["id"] in {record["call_id"] for record in summary["model_receipts"]}:
                continue
            evidence = ledger.get(row["evidence_id"])
            ref = store.put("real_model_receipt", evidence)
            summary["model_receipts"].append(
                {
                    "call_id": row["id"],
                    "original_receipt_id": row["evidence_id"],
                    "local_receipt_id": ref,
                    "status": row["status"],
                    "estimated_usd": row["estimated"],
                }
            )
        store.event(
            run_id,
            "real_model_proposal",
            "completed",
            stage,
            {
                "model_run_id": model_run,
                "stage": stage,
                "receipts": summary["model_receipts"],
                "output": value,
            },
        )
        return value

    def propose(payload):
        return generate(
            "shared_revision_adapter",
            "Produce the exact bounded AdapterEdge for these parent/child contracts. "
            "Use identity first where compatible. Map only declared types, fields, callables and operator boundaries. "
            "No defaults, answers, task-specific branches, or external calls. Preserve all old facts and source identities; "
            "for record splitting keep the original identity on its date record and derive other identities from declared keys. "
            "The proposal_ref is null; the executor records actual generation provenance.",
            payload,
            AdapterEdge.model_json_schema(),
        )

    def candidate_from(original_id, parent, label, **extra):
        kernel = deepcopy(store.get(original_id))
        kernel.update(parent=parent, verification_variant=label, **extra)
        kernel["assessment"] = {
            "status": "candidate",
            "independent_task_assessment": "not_checked",
            "source_candidate_id": original_id,
        }
        return store.put("kernel_revision", kernel)

    def verify(identity, *, with_proposal=False):
        old_ledger = ledger.rows("SELECT id FROM model_calls ORDER BY id")
        result = check_candidate_replay(
            store, identity, run_id=run_id, proposer=propose if with_proposal else None
        )
        if not with_proposal:
            assert ledger.rows("SELECT id FROM model_calls ORDER BY id") == old_ledger
        summary["reports"].append(
            {
                "kernel_id": identity,
                "status": result["status"],
                "report_id": result["report_id"],
                "case_count": result["case_count"],
            }
        )
        return result

    try:
        first, authored_second, authored_third = chain["kernels"]
        second = candidate_from(authored_second, first, "real_adapter_generation_k2")
        new_case = seal_execution_case(
            store,
            second,
            chain["captures"][2],
            run_id=run_id,
            question="Count the retained population",
        )
        register_kernel_bank(store, second, [new_case])
        second_report = verify(second, with_proposal=True)
        if not second_report["allowed"]:
            raise ValueError(f"Real K2 adapter did not preserve: {second_report['feedback']}")
        third = candidate_from(authored_third, second, "real_adapter_generation_k3")
        register_kernel_bank(store, third)
        third_report = verify(third, with_proposal=True)
        if not third_report["allowed"]:
            raise ValueError(f"Real K3 adapter did not preserve: {third_report['feedback']}")
        # A bounded authored program mutation supplies a genuine execution failure.
        broken = deepcopy(store.get(third)["functions"])
        broken[0]["steps"][1]["args"]["request"]["operation"] = "min"
        bad = candidate_from(
            third, second, "authored_fault_for_real_model_repair", functions=broken
        )
        edge_id = store.rows("SELECT edge_id FROM replay_edges WHERE child_id=?", (third,))[0][
            "edge_id"
        ]
        edge = AdapterEdge.model_validate(store.get(edge_id))
        register_kernel_bank(store, bad)
        register_adapter_edge(
            store,
            edge.model_copy(
                update={
                    "child_id": bad,
                    "call_adapter": edge.call_adapter.model_copy(update={"new_revision": bad}),
                }
            ),
        )
        bad_report = verify(bad)
        if bad_report["allowed"] or bad_report["status"] != "regressed":
            raise ValueError("The actual faulty program was not rejected")
        repair = generate(
            "historical_function_repair",
            "Repair the failed candidate's functions using only structural verifier feedback "
            "and original callable semantics. Preserve all other valid functions. Return the complete corrected catalog. "
            "Do not insert recorded answers or task-specific values, change schemas, adapters or regression criteria.",
            {"feedback": bad_report["feedback"], "repair_context": bad_report["repair_context"]},
            RepairProposal.model_json_schema(),
        )
        repaired_functions = RepairProposal.model_validate(repair).model_dump(mode="json")[
            "functions"
        ]
        fixed = candidate_from(
            third,
            second,
            "real_model_repair",
            functions=repaired_functions,
            repair_of=bad,
            model_run_id=model_run,
        )
        register_kernel_bank(store, fixed)
        register_adapter_edge(
            store,
            edge.model_copy(
                update={
                    "child_id": fixed,
                    "call_adapter": edge.call_adapter.model_copy(update={"new_revision": fixed}),
                }
            ),
        )
        fixed_report = verify(fixed)
        if not fixed_report["allowed"]:
            raise ValueError(f"Actual model repair did not preserve: {fixed_report['feedback']}")
        # Re-run the complete repaired bank with the proposer absent and audit the ledger.
        repeated = verify(fixed)
        if not repeated["allowed"]:
            raise ValueError("Repeated offline verification did not preserve")
        assert canonical(sorted(r["original_case_id"] for r in bad_report["reports"])) == canonical(
            sorted(r["original_case_id"] for r in fixed_report["reports"])
        )
        summary.update(
            status="passed",
            kernel_ids=[first, second, third],
            failed_kernel_id=bad,
            repaired_kernel_id=fixed,
            replay_model_calls=0,
            replay_live_mcp_calls=0,
        )
        ledger.set_run(model_run, "completed", result=summary)
    except Exception as error:
        summary.update(status="failed", error=f"{type(error).__name__}: {error}")
        ledger.set_run(model_run, "failed", error=summary["error"], result=summary)
    finally:
        summary["budget_after"] = ledger.budget(config["total_budget_usd"])
        summary["model_call_rows"] = ledger.rows(
            "SELECT id,status,estimated,reserved,evidence_id FROM model_calls WHERE run_id=?",
            (model_run,),
        )
        path = output_path
        path.write_text(json.dumps(summary, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "receipt": str(path),
                    "model_run_id": model_run,
                    "error": summary.get("error"),
                    "budget_after": summary["budget_after"],
                },
                indent=2,
            )
        )
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

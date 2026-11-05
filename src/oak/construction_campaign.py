"""Bounded construction with mandatory inherited historical replay.

Learning produces immutable S/F candidates. Every protected computation must
pass through the candidate's actual adapter ancestry before winner replacement.
Generated behavior checks and fresh planner evaluation remain separate evidence.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from jsonschema import SchemaError, ValidationError

from oak.behavior import BehaviorBank, behavior_denominators
from oak.campaign_evidence import starter_key
from oak.learning import candidate_rank, compare_fresh_runs, repair_feedback
from oak.learning_contracts import CandidateSelection, TaskIR
from oak.materialization import MATERIALIZATION_VERSION, prepare_bound_materialization
from oak.model import GeminiCLI, runtime_config
from oak.pipeline import build_graph
from oak.preservation import certify_preservation, digest, lower_function
from oak.selective_evaluation import (
    CaseEvaluationReceipt,
    EvaluationCase,
    EvaluationReceipt,
    cases_from_episode,
    execute_local_plan,
    plan_evaluation,
    record_fresh_result,
    record_local_result,
    refresh_evaluation_receipt,
)
from oak.task_context import TaskSurface, build_runtime_context
from oak.verification import KernelCandidate, ObligationCheck, ObservedCheck, verify_candidate


def select_preserving_candidate(
    retained_id: str | None,
    candidate_id: str,
    historical_replay: dict,
    *,
    execution_eligible: bool,
    preferred: bool,
) -> str | None:
    """Apply the mandatory replay boundary after independent candidate ranking.

    Unknown, interrupted, empty, partial, or foreign reports retain the current
    winner. Ranking and fresh planner outcomes cannot override this condition.
    """
    reports = historical_replay.get("reports", [])
    complete = bool(
        historical_replay.get("kernel_id") == candidate_id
        and historical_replay.get("allowed") is True
        and historical_replay.get("status") == "preserved"
        and historical_replay.get("case_count", 0) > 0
        and len(reports) == historical_replay.get("case_count")
        and all(report.get("status") == "preserved" for report in reports)
    )
    return candidate_id if execution_eligible and preferred and complete else retained_id


def kernel_candidate(identity: str, kernel: dict) -> KernelCandidate:
    """Adapt one exact immutable stored kernel to the verification contract."""
    return KernelCandidate(
        id=identity,
        schema=kernel["schema"],
        functions=kernel["functions"],
        parent_id=kernel.get("parent"),
    )


def materialization_context(store, kernel: dict) -> dict:
    """Bind source contracts, semantic mappings and authorized native arguments."""
    return {
        "acquisition_bindings": kernel.get("acquisition_bindings", []),
        "behavior_bindings": store.get(kernel["evidence"]["behavior_bindings_id"]),
        "catalog": kernel["catalog"],
    }


def behavior_function_bindings(store, kernel: dict) -> dict[str, str]:
    return {
        entry["behavior_id"]: entry["function_name"]
        for entry in store.get(kernel["evidence"]["compilation_id"])["entries"]
    }


def verification_report(
    store, identity: str, kernel: dict, *, historical_replay_ref: str | None = None
) -> dict:
    """Check actual structural/probe evidence, independently from learning utility."""
    bank = TaskIR.model_validate(store.get(kernel["evidence"]["task_ir_id"]))
    mapping = {
        item["obligation_id"]: item["function_names"]
        for item in store.get(kernel["evidence"]["coverage_id"])["mappings"]
    }
    obligations = [
        ObligationCheck(
            id=item.obligation_id,
            group=item.group,
            mandatory=item.mandatory,
            function_names=mapping.get(item.obligation_id, []),
            semantic_status=item.semantic_status,
            oracle_ref=item.oracle_ref,
        )
        for item in bank.obligations
    ]
    named = {name for item in obligations for name in item.function_names}
    # Unlinked callable probes are execution checks, not invented task requirements.
    obligations.extend(
        ObligationCheck(
            id=f"runtime:{function['name']}",
            group="subtask",
            mandatory=False,
            function_names=[function["name"]],
        )
        for function in kernel["functions"]
        if function["name"] not in named
    )
    evidence = []
    for probe in store.get(kernel["evidence"]["probes_id"]):
        for obligation in obligations:
            if probe["probe"]["function"] not in obligation.function_names:
                continue
            payload = {"candidate_id": identity, "probe_evidence_id": probe["evidence_id"]}
            evidence.append(
                ObservedCheck(
                    obligation_id=obligation.id,
                    dimension="execution",
                    evidence_ref=store.put("candidate_execution_evidence", payload),
                )
            )
    # Parent computation preservation is assessed by selective replay/proofs.
    # Removing an incidental function name is not automatically a semantic loss.
    return verify_candidate(
        kernel_candidate(identity, kernel),
        obligations,
        evidence,
        store=store,
        ontology_validation_ref=kernel["evidence"]["validation_id"],
        historical_replay_ref=historical_replay_ref,
    ).model_dump(mode="json")


def behavior_cases(
    store, kernel: dict, *, bank_id: str, graph_id: str, snapshot: dict
) -> list[EvaluationCase]:
    """One stable semantic case per frozen behavior on a shared real snapshot."""
    bank = BehaviorBank.model_validate(store.get(bank_id))
    result = []
    for template in bank.behaviors:
        payload = {
            "bank_id": bank_id,
            "bindings_id": kernel["evidence"]["behavior_bindings_id"],
            "graph_id": graph_id,
            "receipt_arguments": snapshot.get("receipt_arguments", {}),
            "evidence_refs": snapshot.get("evidence_refs", []),
            "behavior_ids": [template.behavior_id],
            "receipt_ids": snapshot.get("receipt_ids", snapshot.get("evidence_refs", [])),
            "capabilities_id": snapshot.get("capabilities_id")
            or snapshot.get("capabilities_ref")
            or store.put("capability_contracts", kernel["catalog"]["tools"]),
        }
        result.append(
            EvaluationCase(
                case_id="behavior:" + template.behavior_id,
                bank_version=bank.bank_id,
                graph_ref=graph_id,
                source_refs=payload["receipt_ids"],
                extractor_version=MATERIALIZATION_VERSION,
                behavior_input_ref=store.put("behavior_evaluation_input", payload),
                planner_required=False,
            )
        )
    return result


def behavior_evaluation(store, receipt: EvaluationReceipt, bank: BehaviorBank) -> dict:
    """Aggregate only actual generated behavior results, never trajectory outputs."""
    actual_checks, penalties, refs, counterexamples = {}, [], [], []
    for case_id, reference in sorted(receipt.case_receipt_refs.items()):
        if not case_id.startswith("behavior:"):
            continue
        item = CaseEvaluationReceipt.model_validate(store.get(reference))
        refs.append(reference)
        for result in item.results:
            if "behavior_coverage_by_group" not in result:
                continue
            for check in result.get("checks", []):
                if check["behavior_id"] in actual_checks:
                    raise ValueError(
                        "Duplicate behavior results cannot inflate the comparison bank"
                    )
                actual_checks[check["behavior_id"]] = check
            penalties.extend(result.get("penalties", []))
            for counterexample in result.get("counterexamples", []):
                counterexamples.append(
                    {
                        **counterexample,
                        "candidate_id": item.candidate_id,
                        "source_candidate_id": item.source_candidate_id or item.candidate_id,
                        "case_id": case_id,
                        "case_receipt_ref": reference,
                        "evidence_refs": list(
                            dict.fromkeys(
                                [
                                    reference,
                                    *item.evidence_refs,
                                    *counterexample.get("evidence_refs", []),
                                ]
                            )
                        ),
                    }
                )
    checks, groups = [], {}
    totals = behavior_denominators(bank)
    for template in bank.behaviors:
        check = actual_checks.get(
            template.behavior_id,
            {
                "behavior_id": template.behavior_id,
                "obligation_ids": template.obligation_ids,
                "group": template.group,
                "mandatory": template.mandatory,
                "status": "unknown",
                "strata": [],
                "total_strata": totals[template.behavior_id],
                "passed_strata": 0,
                "reason": "No completed check; frozen denominator retained",
            },
        )
        checks.append(check)
        if not template.mandatory:
            continue
        total = totals[template.behavior_id]
        failed = sum(item["status"] == "failed" for item in check.get("strata", []))
        passed = check.get("passed_strata", 0)
        if passed + failed > total or check["total_strata"] != total:
            raise ValueError("Behavior evaluation changed the frozen denominator")
        group = groups.setdefault(
            template.group, {"total": 0, "passed": 0, "failed": 0, "unknown": 0}
        )
        group["total"] += total
        group["passed"] += passed
        group["failed"] += failed
        group["unknown"] += total - passed - failed
    return {
        "version": 1,
        "independent": False,
        "checks": checks,
        "behavior_coverage_by_group": groups,
        "penalties": penalties,
        "counterexamples": counterexamples,
        "evidence_refs": refs,
        "unresolved_behavior_ids": [
            item["behavior_id"]
            for item in checks
            if item.get("mandatory") and item["status"] != "passed"
        ],
        "limitations": [
            "Generated semantic agreement is not independent task truth",
            "Deferred and missing checks retain their frozen denominators",
        ],
    }


def _spent(store, run_id: str) -> float:
    row = store.rows(
        "WITH RECURSIVE family(id) AS (SELECT id FROM runs WHERE id=? UNION ALL SELECT r.id FROM runs r JOIN family f ON r.parent_run_id=f.id) SELECT SUM(estimated) AS estimated,SUM(CASE WHEN status!='settled' THEN reserved ELSE 0 END) AS reserved FROM model_calls WHERE run_id IN (SELECT id FROM family)",
        (run_id,),
    )[0]
    return float(row["estimated"] or 0) + float(row["reserved"] or 0)


def _planner_context(engine, surface, kernel: dict, config: dict, cases) -> dict:
    root = Path(__file__).resolve().parents[2]
    return {
        "base_prompt": surface.base_prompt,
        "description": surface.description,
        "model": config,
        "limits": surface.limits.model_dump(mode="json"),
        "source_catalog": kernel["catalog"],
        "planner_implementation": digest((root / "src/oak/bootstrap.py").read_text()),
        "runtime_context_implementation": digest((root / "src/oak/task_context.py").read_text()),
        "runtime_prompt": (root / "config/prompts/task-runtime.md").read_text(),
        "case_contexts": {
            case.case_id: build_runtime_context(
                surface,
                case.case_id,
                kernel["catalog"]["tools"],
                history=engine.history(kernel["surface_id"]),
                resolve_history=engine.store.get,
            )
            for case in cases
            if case.planner_required
        },
    }


def _rematerialize(store, kernel, source_refs, run_id, ceiling, *, demand=None, label="comparison"):
    from oak.bootstrap import receipt_documents

    documents = []
    for reference in source_refs:
        receipt = {**store.get(reference), "evidence_id": reference}
        if receipt.get("status") != "completed" or not receipt.get("tool_call_attempted"):
            raise ValueError("Comparison requires genuine completed source receipts")
        documents.extend(receipt_documents(receipt))
    if not documents:
        raise ValueError("No retained source documents for rematerialization")
    stage = "selective_rematerialization." + label
    store.event(
        run_id,
        "comparison_materialization",
        "running",
        "Plan real extraction from retained source receipts",
        {
            "flow": "verification",
            "source_refs": source_refs,
            "schema_sha256": digest(kernel["schema"]),
            "demand": demand.model_dump(mode="json") if demand else None,
        },
    )
    graph = build_graph(
        store,
        GeminiCLI(store, run_id, budget_ceiling_usd=ceiling),
        kernel["schema"],
        documents,
        stage,
        demand=demand,
    )
    graph_ref = store.put("selective_materialized_graph", graph)
    stages = [
        row["artifact_id"]
        for row in store.rows(
            "SELECT artifact_id FROM events WHERE run_id=? AND stage LIKE ? ORDER BY id",
            (run_id, stage + "%"),
        )
        if row["artifact_id"]
    ]
    return graph_ref, stages


def applicable_preservation(
    store, run_id: str, parent: KernelCandidate | None, candidate: KernelCandidate
):
    """Check only already representable pure rewrites, without model proposals.

    Exact unchanged implementations use the ordinary evidence cache. A real
    pinned Lean check is requested when at least one changed implementation has
    the same canonical pure plan under the unchanged schema. Unsupported changes
    remain outside the returned certificate; unavailable checking yields None.
    """
    if parent is None or candidate.parent_id != parent.id or parent.schema != candidate.schema:
        return None
    before = {item["name"]: item for item in parent.functions}
    after = {item["name"]: item for item in candidate.functions}
    protected, changed = [], False
    for name in sorted(before.keys() & after.keys()):
        try:
            if lower_function(before[name], parent.schema) != lower_function(
                after[name], candidate.schema
            ):
                continue
        except (ValueError, TypeError, KeyError):
            continue
        protected.append(name)
        changed = changed or before[name] != after[name]
    if not changed:
        return None
    certificate = certify_preservation(parent, candidate, protected)
    reference = store.put("preservation_certificate", certificate.model_dump(mode="json"))
    store.event(
        run_id,
        "preservation_check",
        "passed" if certificate.status == "certified" else "unknown",
        "Checked narrow pure-program preservation on the same immutable graph",
        {
            "flow": "verification",
            "kernel_id": candidate.id,
            "parent_id": parent.id,
            "certificate_id": reference,
            **certificate.model_dump(mode="json"),
        },
    )
    return certificate if certificate.status == "certified" else None


def _execute_plan(
    engine, plan, candidate, kernel, run_id, ceiling, *, parent=None, certificate=None
):
    """Local pure execution plus explicitly planned genuine rematerialization."""
    store = engine.store
    bindings = behavior_function_bindings(store, kernel)
    receipt = execute_local_plan(
        plan, candidate, store, behavior_bindings=bindings, parent=parent, certificate=certificate
    )
    materialized = {}
    for decision in plan.decisions:
        if decision.local_action != "rematerialize":
            continue
        # The current round already materialized its own behavior input from the
        # shared snapshot. Query replays instead require their original receipts.
        if decision.case.behavior_input_ref:
            local = plan_evaluation(
                candidate,
                [decision.case],
                store,
                planner_context=None,
                materialization_context=materialization_context(store, kernel),
                behavior_bindings=bindings,
                max_fresh_cases=0,
            )
            actual = execute_local_plan(local, candidate, store, behavior_bindings=bindings)
            receipt.case_receipt_refs.update(actual.case_receipt_refs)
            continue
        try:
            requests = prepare_replay_materializations(store, kernel, decision.case, bindings)
        except (ValueError, KeyError, TypeError, ValidationError, SchemaError) as error:
            reference = receipt.case_receipt_refs[decision.case.case_id]
            unknown = CaseEvaluationReceipt.model_validate(store.get(reference))
            unknown.summary = (
                f"Rematerialization deferred because source scope is unestablished: {error}"
            )
            receipt.case_receipt_refs[decision.case.case_id] = store.put(
                "selective_case_evaluation", unknown.model_dump(mode="json")
            )
            continue
        graphs_by_call, stages, call_evidence = {}, [], []
        for index, source_refs, demand in requests:
            key = digest(
                {
                    "schema": kernel["schema"],
                    "source_refs": source_refs,
                    "demand": demand.model_dump(mode="json"),
                }
            )
            if key not in materialized:
                materialized[key] = _rematerialize(
                    store, kernel, source_refs, run_id, ceiling, demand=demand, label=key[:12]
                )
            graph, evidence_stages = materialized[key]
            graphs_by_call[index] = graph
            stages.extend(evidence_stages)
            call_evidence.append(
                {
                    "call_index": index,
                    "graph_ref": graph,
                    "source_refs": source_refs,
                    "demand": demand.model_dump(mode="json"),
                }
            )
        graph_ref = graphs_by_call[max(graphs_by_call)]
        evidence = store.put(
            "selective_materialization_evidence",
            {
                "candidate_id": candidate.id,
                "graph_ref": graph_ref,
                "source_refs": decision.case.source_refs,
                "stage_evidence_refs": stages,
                "calls": call_evidence,
            },
        )
        receipt.case_receipt_refs[decision.case.case_id] = record_local_result(
            plan,
            decision.case.case_id,
            candidate,
            store,
            graph_ref=graph_ref,
            materialization_evidence_ref=evidence,
            behavior_bindings=bindings,
            graphs_by_call=graphs_by_call,
        )
    return refresh_evaluation_receipt(receipt, store)


def prepare_replay_materializations(
    store, kernel: dict, case: EvaluationCase, bindings: dict[str, str]
):
    """Resolve each call's exact retained source scope before any paid extraction."""
    if not case.calls:
        raise ValueError("No recorded calls establish a source scope")
    requests = []
    all_sources = set()
    for index, call in enumerate(case.calls):
        if not call.source_refs:
            raise ValueError("A call has no attributable source receipts")
        name = bindings.get(call.behavior_id, call.function)
        function = next((item for item in kernel["functions"] if item["name"] == name), None)
        if function is None:
            raise ValueError("A recorded callable has no candidate binding")
        prepared = prepare_bound_materialization(
            kernel["schema"],
            function,
            call.args,
            kernel.get("acquisition_bindings", []),
            kernel["catalog"]["tools"],
        )
        expected = {
            digest(
                {
                    "capability_id": item.capability,
                    "args": item.arguments,
                    "contract_id": item.contract_id,
                }
            )
            for item in prepared.acquisitions
        }
        actual = set()
        for reference in call.source_refs:
            source = store.get(reference)
            if source.get("status") != "completed" or not source.get("tool_call_attempted"):
                raise ValueError("Call source is not an actual completed acquisition")
            actual.add(
                digest(
                    {
                        "capability_id": source["capability_id"],
                        "args": source["args"],
                        "contract_id": source["contract_id"],
                    }
                )
            )
            all_sources.add(reference)
        if not expected or actual != expected:
            raise ValueError(
                "Retained call sources do not match the frozen native arguments and contracts"
            )
        requests.append((index, sorted(set(call.source_refs)), prepared.demand))
    if all_sources != set(case.source_refs):
        raise ValueError("Case sources cannot be assigned exactly to the recorded calls")
    return requests


def adopt_evaluated_cases(
    store, cases: dict[str, EvaluationCase], receipt_refs: dict[str, str]
) -> None:
    """Retain rebuilt call graphs without overwriting scheduling or split identity."""
    for case_id, previous in list(cases.items()):
        if case_id not in receipt_refs:
            continue
        receipt = CaseEvaluationReceipt.model_validate(store.get(receipt_refs[case_id]))
        if receipt.evaluated_case_ref is None:
            continue
        current = EvaluationCase.model_validate(store.get(receipt.evaluated_case_ref))
        if (
            current.case_id != previous.case_id
            or current.split != previous.split
            or current.question != previous.question
        ):
            raise ValueError("Evaluated case cannot change the immutable query identity or split")
        for flag in (
            "is_new",
            "counterexample",
            "last_fresh_round",
            "estimated_fresh_cost",
            "bank_version",
        ):
            setattr(current, flag, getattr(previous, flag))
        cases[case_id] = current


def require_retained_parent(store, parent_id: str) -> None:
    """An explicit parent cannot bypass the same adoption gate as inference."""
    from oak.historical_replay import inference_admission

    admission = inference_admission(store, parent_id)
    if not admission["allowed"]:
        raise ValueError(f"Construction parent cannot be retained: {admission['reason']}")


def load_campaign_parent(store, parent_id: str, surface_id: str, surface: TaskSurface) -> dict:
    """Restore only attributable semantic-v2 evidence from an eligible parent."""
    require_retained_parent(store, parent_id)
    kernel = store.get(parent_id)
    if (
        kernel.get("construction_profile") != "semantic_v2"
        or kernel.get("surface_id") != surface_id
    ):
        raise ValueError("Construction parent is not a compatible semantic_v2 kernel for this task")
    rows = store.rows("SELECT task_id,kind,result_id FROM runs WHERE id=?", (kernel["run_id"],))
    if (
        not rows
        or rows[0]["task_id"] != surface_id
        or rows[0]["kind"] != "mcp_construct"
        or not rows[0]["result_id"]
    ):
        raise ValueError("Construction parent has no attributable owned evaluation run")
    result = store.get(rows[0]["result_id"])
    if (
        result.get("kernel_id") != parent_id
        or not result.get("evaluation_receipt_id")
        or not result.get("verification_id")
    ):
        raise ValueError("Construction parent lacks semantic_v2 evaluation state")
    evaluated = EvaluationReceipt.model_validate(store.get(result["evaluation_receipt_id"]))
    report = store.get(result["verification_id"])
    if evaluated.candidate_id != parent_id or report.get("candidate_id") != parent_id:
        raise ValueError("Parent evaluation artifacts belong to another candidate")
    task_ir_id, bank_id = kernel["evidence"]["task_ir_id"], kernel["evidence"]["behavior_bank_id"]
    task_ir = TaskIR.model_validate(store.get(task_ir_id))
    bank = BehaviorBank.model_validate(store.get(bank_id))
    if bank.task_ir_sha256 != digest(task_ir.model_dump(mode="json")):
        raise ValueError("Parent behavior bank does not match the frozen TaskIR")
    declared = {query.id: query for query in surface.queries}
    cases, fresh, starters = {}, {}, {}
    for case_id, reference in evaluated.case_receipt_refs.items():
        receipt = CaseEvaluationReceipt.model_validate(store.get(reference))
        if (
            receipt.bank_version != bank.bank_id
            or receipt.case_id != case_id
            or receipt.candidate_id != parent_id
        ):
            raise ValueError("Parent receipt does not belong to its frozen behavior bank")
        if receipt.evaluated_case_ref is None:
            raise ValueError("Parent receipt has no reconstructable evaluation case")
        case = EvaluationCase.model_validate(store.get(receipt.evaluated_case_ref))
        if not case.planner_required:
            continue
        query = declared.get(case_id)
        if (
            query is None
            or query.split not in {"construction", "development", "development-regression"}
            or query.split != case.split
            or query.query != case.question
        ):
            raise ValueError(
                "Parent evaluation would cross an immutable query or held-out boundary"
            )
        cases[case_id] = case
        if receipt.fresh_episode_ref:
            episode = store.get(receipt.fresh_episode_ref)
            if (
                episode.get("query_id") != case_id
                or episode.get("split") != case.split
                or episode.get("kernel_revision") != receipt.fresh_candidate_id
            ):
                raise ValueError("Parent fresh evidence attribution does not match its receipt")
            fresh[case_id] = {
                "query_id": case_id,
                "candidate_id": receipt.fresh_candidate_id,
                "episode_id": receipt.fresh_episode_ref,
                "status": receipt.agent_outcome,
                "assessment": {
                    "status": receipt.task_assessment,
                    "evidence_refs": receipt.evidence_refs,
                },
            }
        elif receipt.historical_agent_evidence is not None:
            previous = receipt.historical_agent_evidence
            episode = store.get(previous.episode_ref)
            if (
                episode.get("query_id") != case_id
                or episode.get("split") != case.split
                or episode.get("kernel_revision") != previous.candidate_id
            ):
                raise ValueError("Historical agent evidence does not match its recorded provenance")
            fresh[case_id] = {
                "query_id": case_id,
                "candidate_id": previous.candidate_id,
                "episode_id": previous.episode_ref,
                "status": previous.agent_outcome,
                "assessment": {
                    "status": previous.task_assessment,
                    "evidence_refs": previous.evidence_refs,
                },
            }
    for episode_ref in store.get(kernel["evidence"]["episodes_id"]):
        episode = store.get(episode_ref)
        query = declared.get(episode.get("query_id"))
        if (
            query is not None
            and query.split == "construction"
            and episode.get("split") == "construction"
            and episode.get("mode") == "bootstrap"
            and episode.get("surface_id") == surface_id
            and episode.get("catalog_id") == kernel["catalog"].get("catalog_id")
        ):
            starters[
                starter_key(
                    surface_id, query.model_dump(mode="json"), kernel["catalog"].get("catalog_id")
                )
            ] = episode_ref
    return {
        "task_ir_id": task_ir_id,
        "behavior_bank_id": bank_id,
        "report": report,
        "receipts": evaluated.case_receipt_refs,
        "query_cases": cases,
        "fresh": fresh,
        "starter_cache": starters,
        "seen": sorted(
            set(kernel["sample"]["selected_query_ids"])
            | {case_id for case_id, case in cases.items() if case.split == "construction"}
        ),
    }


def _emit_plan(store, run_id, candidate_id, plan):
    plan_ref = store.put("evaluation_plan", plan.model_dump(mode="json"))
    store.event(
        run_id,
        "evaluation_plan",
        "completed",
        "Recorded selective evaluation decisions",
        {
            "flow": "verification",
            "kernel_id": candidate_id,
            "evaluation_plan_id": plan_ref,
            **plan.model_dump(mode="json"),
        },
    )
    return plan_ref


def _emit_evaluation(store, run_id, candidate_id, plan, receipt):
    receipt_ref = store.put("selective_evaluation", receipt.model_dump(mode="json"))
    store.event(
        run_id,
        "selective_evaluation",
        "completed",
        "Recorded actual replay, reuse and deferred evidence",
        {
            "flow": "verification",
            "kernel_id": candidate_id,
            "evaluation_receipt_id": receipt_ref,
            **receipt.model_dump(mode="json"),
        },
    )
    return receipt_ref


def compare_behavior_evaluations(
    previous: dict, current: dict, bound_behavior_ids: set[str]
) -> dict:
    """Compare generated behavior preservation on the same bank/source snapshot.

    A previously measured success is protected. A demonstrated defect or lost
    callable is a regression in generated behavior. Missing evidence remains an
    incomplete comparison, not a correctness failure or a passed check.
    """
    before = {item["behavior_id"]: item for item in previous.get("checks", [])}
    after = {item["behavior_id"]: item for item in current.get("checks", [])}
    regressions, incomplete, differences = [], [], []
    for identity, old in before.items():
        if not old.get("mandatory") or old["status"] != "passed":
            continue
        new = after.get(identity)
        if identity not in bound_behavior_ids or (new and new["status"] == "failed"):
            regressions.append(identity)
        elif new is None or new["status"] != "passed":
            incomplete.append(identity)
        else:

            def keyed_strata(check):
                return {
                    digest(
                        {
                            "args": {
                                key: value
                                for key, value in stratum.get("args", {}).items()
                                if key != "native_arguments"
                            },
                            "variant": stratum.get("evidence_variant"),
                        }
                    ): stratum
                    for stratum in check.get("strata", [])
                }

            old_strata, new_strata = keyed_strata(old), keyed_strata(new)
            if not old_strata or old_strata.keys() != new_strata.keys():
                incomplete.append(identity)
            elif any(
                old_strata[key].get("execution", {}).get("value")
                != new_strata[key].get("execution", {}).get("value")
                for key in old_strata
            ):
                # Changed semantic mappings can make a function and its own
                # reference agree while changing the externally observed value.
                # Schema/identity normalization is unsupported here, so preserve
                # the winner and expose the difference without declaring truth.
                differences.append(identity)
                incomplete.append(identity)
    return {
        "regressions": sorted(regressions),
        "incomplete": sorted(incomplete),
        "preservation_differences": sorted(differences),
        "scope": "Generated protected behaviors on the same frozen bank and retained source snapshot",
    }


def construct_campaign(
    engine,
    surface_id: str,
    *,
    round_index: int = 0,
    parent_id: str | None = None,
    run_id: str | None = None,
) -> dict:
    """Construct at most three rounds, preserving the best fairly checked candidate."""
    store, config = engine.store, runtime_config()
    data = engine.surface(surface_id)
    surface = TaskSurface.model_validate(data["configuration"])
    managed = run_id is not None
    if run_id is None:
        run_id = store.create_run(
            surface_id,
            "mcp_construct",
            {
                "surface_id": surface_id,
                "parent_id": parent_id,
                "construction_profile": "semantic_v2",
                "round_index": round_index,
            },
        )
    else:
        engine._check_run(run_id, surface_id, "mcp_construct")
    store.set_run(run_id, "running")
    seen, task_ir_id, behavior_bank_id = [], None, None
    starter_cache, attempts, candidates, verification_ids, evaluation_ids, ranks = (
        {},
        [],
        [],
        [],
        [],
        {},
    )
    best_id, best_rank, best_report, best_fresh, best_receipts = parent_id, None, None, {}, {}
    feedback, last_failure, stop_reason, target_met = None, None, "round_limit", False
    query_cases = {}
    child = None
    try:
        if parent_id is not None:
            restored = load_campaign_parent(store, parent_id, surface_id, surface)
            task_ir_id, behavior_bank_id = restored["task_ir_id"], restored["behavior_bank_id"]
            best_report, best_receipts = restored["report"], restored["receipts"]
            query_cases, best_fresh = restored["query_cases"], restored["fresh"]
            starter_cache, seen = restored["starter_cache"], restored["seen"]
        for offset in range(min(3, config["max_construction_rounds"])):
            child = store.create_run(
                surface_id,
                "mcp_construct",
                {
                    "construction_profile": "semantic_v2",
                    "round_index": round_index + offset,
                    "parent_id": best_id,
                    "task_ir_id": task_ir_id,
                },
                parent_run_id=run_id,
            )
            attempt = {"run_id": child, "round_index": round_index + offset}
            attempts.append(attempt)
            try:
                result = engine._construct_round(
                    surface_id,
                    round_index=round_index + offset,
                    parent_id=best_id,
                    run_id=child,
                    task_ir_id=task_ir_id,
                    seen_query_ids=seen,
                    repair=feedback,
                    starter_cache=starter_cache,
                )
            except (ValueError, KeyError, TypeError, ValidationError, SchemaError) as error:
                store.set_run(child, "failed", error=f"{type(error).__name__}: {error}")
                attempt["error"] = f"{type(error).__name__}: {error}"
                for row in store.rows(
                    "SELECT artifact_id FROM events WHERE run_id=? AND stage='task_ir' ORDER BY id",
                    (child,),
                ):
                    task_ir_id = store.get(row["artifact_id"])["task_ir_id"]
                feedback = {"repair_target": "construction", "message": str(error)}
                if str(error) == last_failure:
                    stop_reason = "repeated_failure"
                    break
                last_failure = str(error)
                continue
            except RuntimeError as error:
                store.set_run(child, "failed", error=f"{type(error).__name__}: {error}")
                attempt["error"] = f"{type(error).__name__}: {error}"
                stop_reason = "execution_boundary_failure"
                break
            identity = result["kernel_id"]
            kernel = store.get(identity)
            candidate = kernel_candidate(identity, kernel)
            task_ir_id = kernel["evidence"]["task_ir_id"]
            incoming_bank = kernel["evidence"]["behavior_bank_id"]
            if behavior_bank_id is not None and store.get(incoming_bank) != store.get(
                behavior_bank_id
            ):
                raise ValueError("Frozen behavior bank changed within the campaign")
            behavior_bank_id = incoming_bank
            bank = BehaviorBank.model_validate(store.get(behavior_bank_id))
            sample = kernel["sample"]["selected_query_ids"]
            seen = sorted(set(seen) | set(sample))
            candidates.append(identity)
            attempt["kernel_id"] = identity
            snapshot = store.get(kernel["evidence"]["behavior_input_id"])
            current_behavior = behavior_cases(
                store,
                kernel,
                bank_id=behavior_bank_id,
                graph_id=snapshot["graph_id"],
                snapshot=snapshot,
            )
            report = verification_report(store, identity, kernel)
            selected_queries = {
                query.id: query for query in surface.queries if query.split == "construction"
            }
            for query_id in sample:
                if query_id not in query_cases:
                    query_cases[query_id] = EvaluationCase(
                        case_id=query_id,
                        question=selected_queries[query_id].query,
                        bank_version=bank.bank_id,
                        is_new=True,
                    )
            for case in query_cases.values():
                case.bank_version = bank.bank_id
            context = _planner_context(engine, surface, kernel, config, query_cases.values())
            parent_candidate = kernel_candidate(best_id, store.get(best_id)) if best_id else None
            certificate = applicable_preservation(store, child, parent_candidate, candidate)
            if certificate is not None:
                report["preservation"] = certificate.model_dump(mode="json")
                report["checks"].append(
                    {
                        "dimension": "preservation",
                        "status": "passed",
                        "summary": certificate.summary,
                        "details": {
                            "protected_functions": certificate.protected_functions,
                            "assumptions": certificate.assumptions,
                        },
                    }
                )
            plan = plan_evaluation(
                candidate,
                [*current_behavior, *query_cases.values()],
                store,
                previous_receipts=best_receipts,
                planner_context=context,
                materialization_context=materialization_context(store, kernel),
                behavior_bindings=behavior_function_bindings(store, kernel),
                parent=parent_candidate,
                certificate=certificate,
                max_fresh_cases=3 if report["execution_eligible"] else 0,
                fresh_budget=store.budget(data["budget_ceiling_usd"])["remaining_usd"],
            )
            boundary_failure = None
            _emit_plan(store, child, identity, plan)
            try:
                selective = _execute_plan(
                    engine,
                    plan,
                    candidate,
                    kernel,
                    child,
                    data["budget_ceiling_usd"],
                    parent=parent_candidate,
                    certificate=certificate,
                )
            except (RuntimeError, ValueError) as error:
                boundary_failure = f"{type(error).__name__}: {error}"
                selective = execute_local_plan(
                    plan,
                    candidate,
                    store,
                    behavior_bindings=behavior_function_bindings(store, kernel),
                    parent=parent_candidate,
                    certificate=certificate,
                )
            report["behavior_evaluation"] = behavior_evaluation(store, selective, bank)
            # Recompute the retained winner on this exact bank and source
            # snapshot before comparing rates or description size.
            comparable = best_id is None
            if best_id and boundary_failure is None:
                previous = store.get(best_id)
                try:
                    graph_ref = snapshot["graph_id"]
                    if previous["schema"] != kernel["schema"]:
                        graph_ref, _ = _rematerialize(
                            store,
                            previous,
                            snapshot.get("receipt_ids", snapshot.get("evidence_refs", [])),
                            child,
                            data["budget_ceiling_usd"],
                            label="retained_winner",
                        )
                    prior_cases = behavior_cases(
                        store,
                        previous,
                        bank_id=behavior_bank_id,
                        graph_id=graph_ref,
                        snapshot=snapshot,
                    )
                    prior_plan = plan_evaluation(
                        kernel_candidate(best_id, previous),
                        prior_cases,
                        store,
                        previous_receipts=best_receipts,
                        materialization_context=materialization_context(store, previous),
                        behavior_bindings=behavior_function_bindings(store, previous),
                        max_fresh_cases=0,
                    )
                    _emit_plan(store, child, best_id, prior_plan)
                    prior_receipt = _execute_plan(
                        engine,
                        prior_plan,
                        kernel_candidate(best_id, previous),
                        previous,
                        child,
                        data["budget_ceiling_usd"],
                    )
                    evaluation_ids.append(
                        _emit_evaluation(store, child, best_id, prior_plan, prior_receipt)
                    )
                    best_receipts.update(prior_receipt.case_receipt_refs)
                    best_report = (
                        verification_report(store, best_id, previous)
                        if best_report is None
                        else deepcopy(best_report)
                    )
                    best_report["behavior_evaluation"] = behavior_evaluation(
                        store, prior_receipt, bank
                    )
                    prior_verification_id = store.put("candidate_verification", best_report)
                    verification_ids.append(prior_verification_id)
                    store.event(
                        child,
                        "candidate_verification",
                        "completed",
                        "Retained candidate rechecked on the same frozen behavior bank and source snapshot",
                        {
                            "flow": "verification",
                            "kernel_id": best_id,
                            "verification_id": prior_verification_id,
                            **best_report,
                        },
                    )
                    best_rank = candidate_rank(
                        best_report, previous, measured_cost=_spent(store, previous["run_id"])
                    )
                    comparable = True
                except (RuntimeError, ValueError, KeyError) as error:
                    boundary_failure = (
                        f"Same-source comparison unavailable: {type(error).__name__}: {error}"
                    )
            fresh = []
            if boundary_failure is None:
                for query_id in plan.fresh_case_ids:
                    # Record the exact selected history before this fresh run.
                    fresh_context = _planner_context(
                        engine, surface, kernel, config, [query_cases[query_id]]
                    )
                    try:
                        episode = engine.run_episode(
                            surface_id, query_id, kernel_id=identity, parent_run_id=child
                        )
                    except RuntimeError as error:
                        boundary_failure = f"{type(error).__name__}: {error}"
                        break
                    fresh.append(
                        {
                            "query_id": query_id,
                            "candidate_id": identity,
                            "run_id": episode["run_id"],
                            "episode_id": episode["episode_id"],
                            "status": episode["episode"]["status"],
                            "assessment": episode.get("assessment"),
                        }
                    )
                    case = cases_from_episode(
                        store,
                        episode["episode_id"],
                        bank_version=bank.bank_id,
                        last_fresh_round=round_index + offset,
                        estimated_fresh_cost=_spent(store, episode["run_id"]),
                    )
                    reverse = {
                        name: behavior
                        for behavior, name in behavior_function_bindings(store, kernel).items()
                    }
                    for call in case.calls:
                        call.behavior_id = reverse.get(call.function)
                    query_cases[query_id] = case
                    local_plan = plan_evaluation(
                        candidate,
                        [case],
                        store,
                        planner_context=fresh_context,
                        materialization_context=materialization_context(store, kernel),
                        behavior_bindings=behavior_function_bindings(store, kernel),
                        max_fresh_cases=0,
                    )
                    local = execute_local_plan(
                        local_plan,
                        candidate,
                        store,
                        behavior_bindings=behavior_function_bindings(store, kernel),
                    )
                    selective.case_receipt_refs[query_id] = record_fresh_result(
                        local.case_receipt_refs[query_id],
                        episode["episode_id"],
                        store,
                        assessment_ref=(episode.get("assessment") or {}).get("assessment_id"),
                    )
            selective = refresh_evaluation_receipt(selective, store)
            from oak.historical_replay import check_candidate_replay

            def propose_shared_adapter(payload, proposal_run_id=child):
                # This is the construction proposal boundary. The replay executor
                # receives only the resulting immutable adapter, never this model.
                return GeminiCLI(
                    store, proposal_run_id, budget_ceiling_usd=data["budget_ceiling_usd"]
                ).json(
                    "historical_adapter",
                    "Propose one shared declarative adapter for the exact parent and child "
                    "contracts. Use only the supplied DSL and attributable transformation "
                    "failures. Do not branch on tasks, questions, answers, or external state. "
                    "Missing facts and ambiguous mappings must remain explicit gaps.",
                    payload,
                )

            historical_replay = check_candidate_replay(
                store,
                identity,
                run_id=child,
                proposer=propose_shared_adapter if boundary_failure is None else None,
            )
            behavior_result = report["behavior_evaluation"]
            preservation_result = report.get("preservation")
            preservation_checks = [
                check for check in report["checks"] if check["dimension"] == "preservation"
            ]
            report = verification_report(
                store, identity, kernel, historical_replay_ref=historical_replay["report_id"]
            )
            report["behavior_evaluation"] = behavior_result
            if preservation_result is not None:
                report["preservation"] = preservation_result
                report["checks"] = [
                    check for check in report["checks"] if check["dimension"] != "preservation"
                ] + preservation_checks
            report["historical_replay"] = historical_replay
            comparison = compare_fresh_runs(best_fresh, fresh)
            behavior_comparison = (
                compare_behavior_evaluations(
                    best_report["behavior_evaluation"],
                    report["behavior_evaluation"],
                    set(behavior_function_bindings(store, kernel)),
                )
                if best_report is not None and comparable
                else {"regressions": [], "incomplete": []}
            )
            comparison["protected_behaviors"] = behavior_comparison
            comparison["same_source_behavior_comparison"] = comparable
            comparison["preservation_differences"] = selective.preservation_difference_case_ids
            comparison["deferred_cases"] = [
                item.case.case_id for item in plan.decisions if item.planner_action == "defer"
            ]
            comparison["boundary_failure"] = boundary_failure
            comparison["historical_replay"] = historical_replay
            evaluation_ids.append(_emit_evaluation(store, child, identity, plan, selective))
            verification_id = store.put("candidate_verification", report)
            verification_ids.append(verification_id)
            store.event(
                child,
                "candidate_verification",
                "completed",
                "Structural evidence and generated behavior checks remain separate from independent task assessment",
                {
                    "flow": "verification",
                    "kernel_id": identity,
                    "verification_id": verification_id,
                    **report,
                },
            )
            rank = candidate_rank(report, kernel, measured_cost=_spent(store, child))
            ranks[identity] = list(rank)
            if best_id is not None and best_rank is not None:
                ranks[best_id] = list(best_rank)
            store.event(
                child,
                "candidate_comparison",
                "completed",
                "Compared candidates on frozen behaviors and attributable agent evidence",
                {
                    "flow": "learning",
                    "kernel_id": identity,
                    "previous_kernel_id": best_id,
                    "comparison": comparison,
                    "rank": list(rank),
                },
            )
            feedback = repair_feedback(report)
            feedback["historical_replay"] = historical_replay["feedback"]
            if not historical_replay["allowed"]:
                feedback["historical_repair_context"] = historical_replay.get(
                    "repair_context",
                    {
                        "candidate": {
                            "kernel_id": identity,
                            "schema": kernel["schema"],
                            "functions": kernel["functions"],
                        }
                    },
                )
            feedback["behavior_counterexamples"] = [
                item
                for item in report["behavior_evaluation"]["checks"]
                if item["status"] != "passed"
            ]
            if comparison["failures"]:
                feedback["fresh_agent_failures"] = [
                    item for item in fresh if item["query_id"] in comparison["failures"]
                ]
                for query_id in comparison["failures"]:
                    query_cases[query_id].counterexample = True
            preferred = best_id is None or (
                comparable
                and not comparison["regressions"]
                and not selective.known_regression_case_ids
                and not behavior_comparison["regressions"]
                and not behavior_comparison["incomplete"]
                and boundary_failure is None
                and (best_rank is None or rank < best_rank)
            )
            selected_id = select_preserving_candidate(
                best_id,
                identity,
                historical_replay,
                execution_eligible=report["execution_eligible"],
                preferred=preferred,
            )
            if selected_id == identity:
                best_id, best_rank, best_report = identity, rank, report
                best_fresh = {**best_fresh, **{item["query_id"]: item for item in fresh}}
                best_receipts = {**best_receipts, **selective.case_receipt_refs}
            adopt_evaluated_cases(store, query_cases, best_receipts)
            target_met = bool(
                report["target_met"]
                and identity == best_id
                and historical_replay["allowed"]
                and not comparison["failures"]
                and boundary_failure is None
            )
            store.set_run(
                child,
                "failed" if boundary_failure else "completed",
                result={
                    **result,
                    "verification_id": verification_id,
                    "evaluation_receipt_id": evaluation_ids[-1],
                },
                error=boundary_failure,
            )
            if boundary_failure:
                stop_reason = "execution_boundary_failure"
                break
            if target_met:
                stop_reason = "construction_target_met"
                break
            if (
                set(selected_queries).issubset(seen)
                and not feedback.get("counterexamples")
                and not feedback.get("fresh_agent_failures")
                and not feedback["behavior_counterexamples"]
                and historical_replay["allowed"]
            ):
                stop_reason = "sampled_task_surface"
                break
        selection = CandidateSelection(
            task_ir_id=task_ir_id or "",
            candidate_ids=candidates,
            selected_kernel_id=best_id,
            verification_ids=verification_ids,
            disposition="target_met" if target_met else "incomplete" if best_id else "rejected",
            stop_reason=stop_reason,
            ranks=ranks,
        )
        selection_id = store.put("candidate_selection", selection.model_dump(mode="json"))
        store.event(
            run_id,
            "candidate_selection",
            "completed",
            (
                "Retained the best eligible candidate under recorded comparison limits"
                if best_id
                else "No eligible candidate was produced; inference adoption remains blocked"
            ),
            {"flow": "learning", "selection_id": selection_id, **selection.model_dump(mode="json")},
        )
        output = {
            "run_id": run_id,
            "kernel_id": best_id,
            "candidate_ids": candidates,
            "selection_id": selection_id,
            "task_ir_id": task_ir_id,
            "verification_ids": verification_ids,
            "evaluation_ids": evaluation_ids,
            "attempts": attempts,
            "assessment": {
                "construction": selection.disposition,
                "fresh_task_success": "unmeasured",
            },
        }
        store.set_run(run_id, "completed", result=output)
        return output
    except Exception as error:
        if child is not None:
            rows = store.rows("SELECT status FROM runs WHERE id=?", (child,))
            if rows and rows[0]["status"] in {"queued", "running"}:
                store.set_run(child, "failed", error=f"{type(error).__name__}: {error}")
        if not managed:
            store.set_run(run_id, "failed", error=f"{type(error).__name__}: {error}")
        raise

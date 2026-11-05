"""Dependency-scoped evaluation of immutable candidates on retained real evidence.

Local execution, proof transfer and cached evidence concern frozen computations.
They never stand in for a new agent choice or independent task assessment. The
planner selects a bounded fresh sample and explicitly retains deferred exposure.
No function here dispatches MCP, invokes a model, or rematerializes source data.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Literal

from pydantic import Field

from oak.functions import FunctionSpec, execute_function, validate_functions
from oak.ontology import validate_graph_records
from oak.operators import GRAPH_OPERATORS
from oak.preservation import (
    EFFECT_OPERATORS,
    PURE_OPERATORS,
    PreservationCertificate,
    digest,
    lower_function,
    runtime_dependencies,
    validate_certificate,
)
from oak.store import Store
from oak.verification import (
    CandidateFunctionRef,
    GeneratedCheckSpec,
    KernelCandidate,
    StrictModel,
    execute_generated_check,
)

LocalAction = Literal["reuse", "proof", "replay", "rematerialize", "defer"]


class ReplayCall(StrictModel):
    """An actual invocation, optionally rebound through a stable behavior ID."""

    function: str
    args: dict = Field(default_factory=dict)
    graph_ref: str | None = None
    execution_ref: str | None = None
    behavior_id: str | None = None
    input_graph_known: bool = True
    source_refs: list[str] = Field(default_factory=list)


class EvaluationCase(StrictModel):
    """One versioned construction/development evaluation unit, never held out."""

    case_id: str
    question: str | None = None
    split: Literal["construction", "development", "development-regression"] = "construction"
    bank_version: str
    calls: list[ReplayCall] = Field(default_factory=list)
    graph_ref: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    demand_ref: str | None = None
    extractor_version: str | None = None
    episode_ref: str | None = None
    generated_check_refs: list[str] = Field(default_factory=list)
    behavior_input_ref: str | None = None
    is_new: bool = False
    counterexample: bool = False
    last_fresh_round: int = -1
    estimated_fresh_cost: float | None = Field(default=None, ge=0)
    planner_required: bool = True


class DependencyScope(StrictModel):
    """Complete means conservative static scope, never just observed node IDs."""

    completeness: Literal["complete", "unknown"]
    fingerprints: dict[str, str] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class DependencyManifest(StrictModel):
    """Separate computation, materialization and full planner-visible exposure."""

    version: Literal[1] = 1
    candidate_id: str
    case_id: str
    bank_version: str
    computation: DependencyScope
    materialization: DependencyScope
    planner: DependencyScope
    function_names: list[str]
    cache_key: str


class CaseDecision(StrictModel):
    case: EvaluationCase
    manifest: DependencyManifest
    local_action: LocalAction
    reasons: list[str]
    previous_receipt_ref: str | None = None
    planner_action: Literal["fresh", "defer", "reuse", "not_required"] = "defer"
    planner_reason: str = "No fresh execution selected"
    planner_sentinel: bool = False


class EvaluationPlan(StrictModel):
    version: Literal[1] = 1
    candidate_id: str
    bank_version: str
    decisions: list[CaseDecision]
    max_fresh_cases: int = 3
    max_planner_sentinels: int = 1
    estimated_fresh_cost: float = 0.0
    fresh_budget: float | None = None
    bank_comparable: bool = True
    plan_sha256: str = ""

    @property
    def fresh_case_ids(self) -> list[str]:
        return [item.case.case_id for item in self.decisions if item.planner_action == "fresh"]


class HistoricalAgentEvidence(StrictModel):
    """A previous observed outcome, never a fresh assessment of this candidate."""

    episode_ref: str
    candidate_id: str
    agent_outcome: str | None = None
    task_assessment: str = "not_checked"
    evidence_refs: list[str] = Field(default_factory=list)


class CaseEvaluationReceipt(StrictModel):
    """Actual local evidence and independently attributed fresh agent evidence."""

    version: Literal[1] = 1
    candidate_id: str
    case_id: str
    bank_version: str
    manifest: DependencyManifest
    action: LocalAction
    status: Literal["passed", "failed", "unknown"]
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    evaluated_case_ref: str | None = None
    source_candidate_id: str | None = None
    previous_receipt_ref: str | None = None
    results: list[dict] = Field(default_factory=list)
    fresh_episode_ref: str | None = None
    fresh_candidate_id: str | None = None
    historical_agent_evidence: HistoricalAgentEvidence | None = None
    agent_outcome: str | None = None
    task_assessment: str = "not_checked"
    planner_exposure: Literal["checked", "unchanged", "deferred", "not_applicable"] = "deferred"
    independent: bool = False


class EvaluationReceipt(StrictModel):
    version: Literal[1] = 1
    candidate_id: str
    plan_sha256: str
    case_receipt_refs: dict[str, str]
    deferred_case_ids: list[str]
    known_regression_case_ids: list[str]
    preservation_difference_case_ids: list[str] = Field(default_factory=list)
    bank_comparable: bool


def _function_names(case: EvaluationCase, store: Store, bindings: dict[str, str]) -> list[str]:
    names = {bindings.get(call.behavior_id, call.function) for call in case.calls}
    for reference in case.generated_check_refs:
        check = GeneratedCheckSpec.model_validate(store.get(reference))
        names.update(
            operand.function
            for operand in (check.left, check.right)
            if isinstance(operand, CandidateFunctionRef)
        )
    if case.behavior_input_ref:
        payload = store.get(case.behavior_input_ref)
        bank = store.get(payload["bank_id"])
        selected = set(
            payload.get("behavior_ids") or [item["behavior_id"] for item in bank["behaviors"]]
        )
        names.update(
            item.get("function_name") or "behavior_" + item["behavior_id"][2:]
            for item in store.get(payload["bindings_id"])
            if item["behavior_id"] in selected
        )
    return sorted(names)


def build_dependency_manifest(
    candidate: KernelCandidate,
    case: EvaluationCase,
    store: Store,
    *,
    planner_context: dict | None = None,
    materialization_context: dict | None = None,
    behavior_bindings: dict[str, str] | None = None,
) -> DependencyManifest:
    """Derive dependencies from complete programs and complete retained graphs.

    Full graph hashes intentionally cover populations, negative queries,
    adjacency, multiplicity, identity, units, missingness and order. Unknown or
    effectful programs do not acquire a complete scope from their dynamic trace.
    Callers supply the entire planner context, including prompt/model/settings
    and source catalog, and materialization bindings as actual frozen metadata.
    """
    bindings = behavior_bindings or {}
    names = _function_names(case, store, bindings)
    catalog = {function["name"]: function for function in candidate.functions}
    reasons: list[str] = []
    if any(not call.input_graph_known for call in case.calls):
        reasons.append(
            "An observed call lacks its exact input graph; final graph is not a substitute"
        )
    programs = {}
    for name in names:
        function = catalog.get(name)
        if function is None:
            reasons.append(f"Callable is absent: {name}")
            continue
        try:
            plan = lower_function(function, candidate.schema)
            if any(step.operator not in PURE_OPERATORS for step in plan.steps):
                raise ValueError("Unknown or effectful primitive")
            # Both raw contract and canonical program matter. Descriptions affect
            # planner exposure, while local renaming can be proof-transferred.
            programs[name] = digest(FunctionSpec.model_validate(function).model_dump(mode="json"))
        except ValueError as error:
            reasons.append(f"Static pure dependency scope unavailable for {name}: {error}")
    graph_refs = sorted(
        {ref for ref in [case.graph_ref, *(c.graph_ref for c in case.calls)] if ref}
    )
    graphs = {reference: digest(store.get(reference)) for reference in graph_refs}
    if not graph_refs and (case.calls or case.generated_check_refs):
        reasons.append("No retained immutable input graph")
    if not names and not case.behavior_input_ref:
        reasons.append("No candidate-bound computation")
    fingerprints = {
        "schema": digest(candidate.schema),
        "programs": digest(programs),
        "arguments": digest(
            [
                {"function": bindings.get(c.behavior_id, c.function), "args": c.args}
                for c in case.calls
            ]
        ),
        "graphs": digest(graphs),
        "runtime": digest(runtime_dependencies()),
        "evaluator": digest(Path(__file__).read_text()),
        "generated_evaluator": digest(Path(__file__).with_name("verification.py").read_text()),
        "checks": digest({ref: store.get(ref) for ref in sorted(set(case.generated_check_refs))}),
        "bank": digest(case.bank_version),
        "call_sources": digest(
            [{ref: store.get(ref) for ref in sorted(set(call.source_refs))} for call in case.calls]
        ),
    }
    if case.behavior_input_ref:
        payload = store.get(case.behavior_input_ref)
        nested = {key: store.get(payload[key]) for key in ("bank_id", "bindings_id", "graph_id")}
        selected = set(
            payload.get("behavior_ids")
            or [item["behavior_id"] for item in nested["bank_id"]["behaviors"]]
        )
        nested["bindings_id"] = [
            item for item in nested["bindings_id"] if item["behavior_id"] in selected
        ]
        fingerprints["behavior_input"] = digest(
            {
                "payload": {
                    key: value
                    for key, value in payload.items()
                    if key not in {"candidate_id", "bank_id", "bindings_id", "graph_id"}
                },
                "artifacts": nested,
            }
        )
        fingerprints["behavior_evaluator"] = digest(
            {
                name: Path(__file__).with_name(name).read_text()
                for name in (
                    "behavior.py",
                    "behavior_reference.py",
                    "task_semantics.py",
                    "learning_contracts.py",
                )
            }
        )
        for reference in payload.get("evidence_refs", []):
            store.get(reference)
        for key in ("capabilities_id", "capabilities_ref"):
            if payload.get(key):
                store.get(payload[key])
        for reference in payload.get("receipt_ids", []):
            store.get(reference)
    sources = {ref: digest(store.get(ref)) for ref in sorted(set(case.source_refs))}
    scoped_materialization = deepcopy(materialization_context)
    if scoped_materialization is not None:
        if isinstance(scoped_materialization.get("acquisition_bindings"), list):
            scoped_materialization["acquisition_bindings"] = [
                {
                    key: value
                    for key, value in item.items()
                    if key not in {"function_sha256", "schema_sha256"}
                }
                for item in scoped_materialization["acquisition_bindings"]
                if item.get("function_name") in names
            ]
        if isinstance(scoped_materialization.get("behavior_bindings"), list):
            selected_behavior_ids = {call.behavior_id for call in case.calls if call.behavior_id}
            if case.behavior_input_ref:
                selected_behavior_ids.update(selected)
            scoped_materialization["behavior_bindings"] = [
                item
                for item in scoped_materialization["behavior_bindings"]
                if item.get("behavior_id") in selected_behavior_ids
            ]
    mat_reasons = []
    if not sources:
        mat_reasons.append("No retained source receipts")
    if case.extractor_version is None or case.demand_ref is None or materialization_context is None:
        mat_reasons.append("Extraction demand, version or source binding scope is missing")
    materialization = DependencyScope(
        completeness="unknown" if mat_reasons else "complete",
        fingerprints={
            "schema": digest(candidate.schema),
            "sources": digest(sources),
            "extractor": digest(case.extractor_version),
            "demand": digest(store.get(case.demand_ref)) if case.demand_ref else digest(None),
            "bindings": digest(scoped_materialization),
            "implementation": digest(
                {
                    name: Path(__file__).with_name(name).read_text()
                    for name in ("materialization.py", "pipeline.py", "construction_prompts.py")
                }
            ),
            "extraction_prompt": digest(
                (Path(__file__).parents[2] / "config/prompts/graph-extraction.md").read_text()
            ),
            "model_configuration": digest(
                (Path(__file__).parents[2] / "config/runtime.json").read_text()
            ),
        },
        reasons=mat_reasons,
    )
    computation = DependencyScope(
        completeness="unknown" if reasons else "complete",
        fingerprints=fingerprints,
        reasons=reasons,
    )
    visible_context = planner_context
    if planner_context is not None and "case_contexts" in planner_context:
        visible_context = {
            key: value for key, value in planner_context.items() if key != "case_contexts"
        }
        visible_context["case_context"] = planner_context["case_contexts"].get(case.case_id)
    planner = DependencyScope(
        completeness="complete" if planner_context is not None else "unknown",
        fingerprints={
            "schema": digest(candidate.schema),
            "catalog": digest(candidate.functions),
            "context": digest(visible_context),
            "bindings": digest(materialization_context),
            "request": digest({"question": case.question, "case_id": case.case_id}),
        },
        reasons=[]
        if planner_context is not None
        else ["Full planner-visible prompt, source catalog and runtime settings unavailable"],
    )
    return DependencyManifest(
        candidate_id=candidate.id,
        case_id=case.case_id,
        bank_version=case.bank_version,
        computation=computation,
        materialization=materialization,
        planner=planner,
        function_names=names,
        cache_key=digest(
            {"case_id": case.case_id, "computation": computation.model_dump(mode="json")}
        ),
    )


def _same_scope(left: DependencyScope, right: DependencyScope) -> bool:
    return (
        left.completeness == right.completeness == "complete"
        and left.fingerprints == right.fingerprints
    )


def plan_evaluation(
    candidate: KernelCandidate,
    cases: list[EvaluationCase],
    store: Store,
    *,
    previous_receipts: dict[str, str] | None = None,
    planner_context: dict | None = None,
    materialization_context: dict | None = None,
    behavior_bindings: dict[str, str] | None = None,
    parent: KernelCandidate | None = None,
    certificate: PreservationCertificate | dict | None = None,
    max_fresh_cases: int = 3,
    max_planner_sentinels: int = 1,
    fresh_budget: float | None = None,
) -> EvaluationPlan:
    """Plan cheap checks independently from a bounded, deterministic fresh sample.

    Maxima may be lowered by callers, never raised past three fresh cases and
    one planner-only sentinel. Unknown fresh cost is scheduled one at a time.
    Ledger reservations remain authoritative at actual model dispatch.
    """
    if not 0 <= max_fresh_cases <= 3 or not 0 <= max_planner_sentinels <= 1:
        raise ValueError("Fresh limits must be within three cases and one sentinel")
    if fresh_budget is not None and fresh_budget < 0:
        raise ValueError("Fresh budget cannot be negative")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Evaluation case IDs must be unique")
    versions = {case.bank_version for case in cases}
    if len(versions) > 1:
        raise ValueError("One comparison plan must use one frozen bank version")
    checked_certificate = None
    if certificate is not None and parent is not None:
        checked_certificate = validate_certificate(certificate, parent, candidate)
    decisions, priorities = [], []
    comparable = True
    for case in sorted(cases, key=lambda item: item.case_id):
        manifest = build_dependency_manifest(
            candidate,
            case,
            store,
            planner_context=planner_context,
            materialization_context=materialization_context,
            behavior_bindings=behavior_bindings,
        )
        previous_ref = (previous_receipts or {}).get(case.case_id)
        previous = (
            CaseEvaluationReceipt.model_validate(store.get(previous_ref)) if previous_ref else None
        )
        if previous is not None and previous.case_id != case.case_id:
            raise ValueError("Prior receipt belongs to a different case")
        same_bank = previous is not None and previous.bank_version == case.bank_version
        if previous is not None and not same_bank:
            comparable = False
        unchanged = same_bank and _same_scope(manifest.computation, previous.manifest.computation)
        mat_changed = (
            previous is not None
            and manifest.materialization.fingerprints
            != previous.manifest.materialization.fingerprints
        )
        local: LocalAction = "defer"
        reasons = []
        if mat_changed:
            local = "rematerialize" if case.source_refs else "defer"
            reasons = [
                "Materialization dependencies changed; replay cannot establish extraction equivalence"
            ]
        elif unchanged and previous.status != "unknown":
            local, reasons = (
                "reuse",
                ["Exact immutable computation, graph, evaluator and bank match"],
            )
        elif (
            checked_certificate is not None
            and previous is not None
            and previous.candidate_id == parent.id
            and same_bank
            and manifest.function_names
            and set(manifest.function_names).issubset(checked_certificate.protected_functions)
            and manifest.computation.completeness
            == previous.manifest.computation.completeness
            == "complete"
            and all(
                value == previous.manifest.computation.fingerprints.get(key)
                for key, value in manifest.computation.fingerprints.items()
                if key != "programs"
            )
        ):
            local, reasons = "proof", ["Rechecked same-input pure preservation certificate"]
        elif manifest.computation.completeness == "complete" or case.behavior_input_ref:
            local, reasons = "replay", ["Execute actual frozen pure computations on retained graph"]
        else:
            reasons = manifest.computation.reasons or [
                "Insufficient retained evidence for local evaluation"
            ]
        planner_unchanged = previous is not None and _same_scope(
            manifest.planner, previous.manifest.planner
        )
        decision = CaseDecision(
            case=case,
            manifest=manifest,
            local_action=local,
            reasons=reasons,
            previous_receipt_ref=previous_ref,
        )
        if not case.planner_required:
            decision.planner_action = "not_required"
            decision.planner_reason = (
                "Pure behavior bank evaluation does not require a fresh agent trajectory"
            )
        elif (
            planner_unchanged
            and not mat_changed
            and local in {"reuse", "proof"}
            and previous.status == "passed"
            and previous.fresh_episode_ref is not None
        ):
            decision.planner_action, decision.planner_reason = (
                "reuse",
                "Historical agent evidence has identical planner and observation dependencies; no new agent run claimed",
            )
        else:
            impacted = local in {"replay", "rematerialize", "defer"}
            sentinel = not case.counterexample and not case.is_new and not impacted
            priority = 0 if case.counterexample else 1 if case.is_new else 2 if impacted else 3
            priorities.append(
                (priority, case.last_fresh_round, digest(case.case_id), decision, sentinel)
            )
        decisions.append(decision)
    spent, selected, sentinels, unknown_costs = 0.0, 0, 0, 0
    for _, _, _, decision, sentinel in sorted(priorities, key=lambda item: item[:3]):
        estimate = decision.case.estimated_fresh_cost
        if selected >= max_fresh_cases or (sentinel and sentinels >= max_planner_sentinels):
            decision.planner_reason = "Deferred by bounded fresh-case or planner-sentinel limit"
        elif fresh_budget == 0 or (
            estimate is not None and fresh_budget is not None and spent + estimate > fresh_budget
        ):
            decision.planner_reason = "Deferred by available fresh evaluation budget"
        elif estimate is None and unknown_costs:
            decision.planner_reason = "Deferred until an unknown-cost fresh execution has settled"
        else:
            decision.planner_action = "fresh"
            decision.planner_sentinel = sentinel
            decision.planner_reason = (
                "Selected counterexample/new/impacted case"
                if not sentinel
                else "Selected full-catalog planner exposure sentinel"
            )
            selected += 1
            sentinels += int(sentinel)
            unknown_costs += int(estimate is None)
            spent += estimate or 0.0
    plan = EvaluationPlan(
        candidate_id=candidate.id,
        bank_version=next(iter(versions), "empty"),
        decisions=decisions,
        max_fresh_cases=max_fresh_cases,
        max_planner_sentinels=max_planner_sentinels,
        estimated_fresh_cost=spent,
        fresh_budget=fresh_budget,
        bank_comparable=comparable,
    )
    plan.plan_sha256 = digest(plan.model_dump(mode="json", exclude={"plan_sha256"}))
    return plan


def _execute_case(
    case: EvaluationCase, candidate: KernelCandidate, store: Store, bindings: dict[str, str]
) -> tuple[str, list[dict], list[str]]:
    results, refs = [], []
    catalog = {function["name"]: function for function in candidate.functions}
    for call in case.calls:
        if not call.input_graph_known:
            results.append(
                {"status": "unknown", "summary": "Exact call input graph was not recorded"}
            )
            continue
        name = bindings.get(call.behavior_id, call.function)
        function = catalog.get(name)
        if function is None:
            results.append({"status": "failed", "summary": f"Callable is absent: {name}"})
            continue
        if any(
            step["operator"] in EFFECT_OPERATORS or step["operator"] not in PURE_OPERATORS
            for step in function["steps"]
        ):
            results.append(
                {
                    "status": "unknown",
                    "summary": "Effectful calls require genuine fresh execution, never substituted receipts",
                }
            )
            continue
        graph_ref = call.graph_ref or case.graph_ref
        if graph_ref is None:
            results.append({"status": "unknown", "summary": "No immutable graph recorded for call"})
            continue
        graph = store.get(graph_ref)
        valid = validate_graph_records(candidate.schema, graph["nodes"], graph.get("edges", []))
        if not valid["valid"]:
            results.append(
                {
                    "status": "unknown",
                    "summary": "Retained graph requires schema-compatible rematerialization",
                    "validation": valid,
                }
            )
            continue
        try:
            validate_functions([function], candidate.schema)
            execution = execute_function(
                deepcopy(graph),
                candidate.functions,
                name,
                call.args,
                schema=candidate.schema,
                artifact_store=store,
            )
            execution_ref = store.put("selective_function_execution", execution)
            refs.append(execution_ref)
            result = {
                "status": "passed",
                "function": name,
                "execution_ref": execution_ref,
                "value": execution["value"],
                "comparison": "not_checked",
            }
            if call.execution_ref:
                old = store.get(call.execution_ref)
                old_deps = old.get("dependencies", {})
                same_input_graph = (
                    old_deps.get("graph_sha256") == execution["dependencies"]["graph_sha256"]
                )
                if not same_input_graph and case.episode_ref:
                    original_episode = store.get(case.episode_ref)
                    original_observation = next(
                        (
                            item
                            for item in original_episode.get("observations", [])
                            if item.get("execution_id") == call.execution_ref
                        ),
                        None,
                    )
                    if original_observation is not None:
                        same_input_graph = _recorded_input_graph_known(
                            store, original_episode, original_observation, old, graph_ref
                        )
                if (
                    same_input_graph
                    and old_deps.get("schema_sha256") == execution["dependencies"]["schema_sha256"]
                    and "value" in old
                ):
                    result["comparison"] = (
                        "equal" if old["value"] == execution["value"] else "different"
                    )
                    result["reference_execution_ref"] = call.execution_ref
                    # A changed result is a concrete replay difference, not an
                    # independent determination that either answer is correct.
                    if result["comparison"] == "different":
                        result["preservation_status"] = "different"
                else:
                    result["comparison"] = "incompatible_reference"
            results.append(result)
        except (ValueError, KeyError, TypeError, RuntimeError) as error:
            results.append(
                {
                    "status": "failed",
                    "function": name,
                    "summary": f"{type(error).__name__}: {error}",
                }
            )
    for reference in sorted(set(case.generated_check_refs)):
        if case.graph_ref is None:
            results.append(
                {"status": "unknown", "summary": "Generated check has no retained graph"}
            )
            continue
        result = execute_generated_check(
            store.get(reference),
            store.get(case.graph_ref),
            candidate.schema,
            candidate_functions=candidate.functions,
        )
        refs.append(store.put("selective_generated_check", result))
        results.append(result)
    if case.behavior_input_ref:
        from oak.behavior import replay_behavior_evaluation

        result = replay_behavior_evaluation(candidate, store.get(case.behavior_input_ref), store)
        refs.append(store.put("selective_behavior_check", result))
        results.append(result)
    statuses = [result.get("status", "unknown") for result in results]
    return (
        (
            "failed"
            if "failed" in statuses
            else "passed"
            if statuses and all(status == "passed" for status in statuses)
            else "unknown"
        ),
        results,
        refs,
    )


def execute_local_plan(
    plan: EvaluationPlan,
    candidate: KernelCandidate,
    store: Store,
    *,
    parent: KernelCandidate | None = None,
    certificate: PreservationCertificate | dict | None = None,
    behavior_bindings: dict[str, str] | None = None,
) -> EvaluationReceipt:
    """Execute only persisted local actions; fresh/rematerialize stay unknown."""
    if plan.candidate_id != candidate.id or plan.plan_sha256 != digest(
        plan.model_dump(mode="json", exclude={"plan_sha256"})
    ):
        raise ValueError("Plan candidate or immutable plan hash mismatch")
    case_refs, deferred, regressions, differences = {}, [], [], []
    checked_certificate = None
    if any(decision.local_action == "proof" for decision in plan.decisions):
        if parent is None or certificate is None:
            raise ValueError("Proof transfer requires exact revisions and a checked certificate")
        checked_certificate = validate_certificate(certificate, parent, candidate)
    for decision in plan.decisions:
        case, manifest = decision.case, decision.manifest
        # Check immutable candidate/evidence once more at execution, including
        # runtime changes after planning. Planner metadata was fixed in plan.
        actual = build_dependency_manifest(
            candidate, case, store, behavior_bindings=behavior_bindings
        )
        if actual.computation != manifest.computation:
            raise ValueError("Computation dependencies changed after evaluation planning")
        previous = (
            CaseEvaluationReceipt.model_validate(store.get(decision.previous_receipt_ref))
            if decision.previous_receipt_ref
            else None
        )
        status, results, refs, source = "unknown", [], [], None
        summary = "; ".join(decision.reasons)
        if decision.local_action == "reuse":
            if (
                previous is None
                or not _same_scope(manifest.computation, previous.manifest.computation)
                or previous.bank_version != case.bank_version
            ):
                raise ValueError("Unsafe reuse without exact complete dependency match")
            status, results, refs = previous.status, previous.results, previous.evidence_refs
            source = previous.source_candidate_id or previous.candidate_id
            for reference in refs:
                store.get(reference)
        elif decision.local_action == "proof":
            if previous is None or parent is None or certificate is None:
                raise ValueError("Proof transfer requires original evidence and exact revisions")
            checked = checked_certificate
            if not set(manifest.function_names).issubset(checked.protected_functions):
                raise ValueError("Certificate does not protect all called functions")
            refs = [
                *previous.evidence_refs,
                store.put("selective_preservation_certificate", checked.model_dump(mode="json")),
            ]
            status, results, source = (
                previous.status,
                previous.results,
                previous.source_candidate_id or previous.candidate_id,
            )
        elif decision.local_action == "replay":
            status, results, refs = _execute_case(case, candidate, store, behavior_bindings or {})
        if (
            status == "failed"
            and previous is not None
            and previous.status == "passed"
            and previous.bank_version == case.bank_version
            and previous.manifest.computation.fingerprints.get("graphs")
            == manifest.computation.fingerprints.get("graphs")
            and previous.manifest.computation.fingerprints.get("schema")
            == manifest.computation.fingerprints.get("schema")
        ):
            regressions.append(case.case_id)
        if any(result.get("preservation_status") == "different" for result in results):
            differences.append(case.case_id)
        if decision.planner_action == "defer" or decision.local_action in {
            "rematerialize",
            "defer",
        }:
            deferred.append(case.case_id)
        receipt = CaseEvaluationReceipt(
            candidate_id=candidate.id,
            case_id=case.case_id,
            bank_version=case.bank_version,
            manifest=manifest,
            action=decision.local_action,
            status=status,
            summary=summary,
            evidence_refs=refs,
            evaluated_case_ref=store.put("evaluation_case", case.model_dump(mode="json")),
            results=results,
            previous_receipt_ref=decision.previous_receipt_ref,
            source_candidate_id=source,
        )
        if decision.planner_action == "not_required":
            receipt.planner_exposure = "not_applicable"
        if previous is not None:
            receipt.historical_agent_evidence = previous.historical_agent_evidence
            if previous.fresh_episode_ref and previous.fresh_candidate_id:
                receipt.historical_agent_evidence = HistoricalAgentEvidence(
                    episode_ref=previous.fresh_episode_ref,
                    candidate_id=previous.fresh_candidate_id,
                    agent_outcome=previous.agent_outcome,
                    task_assessment=previous.task_assessment,
                    evidence_refs=previous.evidence_refs,
                )
        if decision.planner_action == "reuse" and previous is not None:
            receipt.fresh_episode_ref = previous.fresh_episode_ref
            receipt.fresh_candidate_id = previous.fresh_candidate_id
            receipt.agent_outcome = previous.agent_outcome
            receipt.task_assessment = previous.task_assessment
            receipt.planner_exposure = "unchanged"
        case_refs[case.case_id] = store.put(
            "selective_case_evaluation", receipt.model_dump(mode="json")
        )
    return EvaluationReceipt(
        candidate_id=candidate.id,
        plan_sha256=plan.plan_sha256,
        case_receipt_refs=case_refs,
        deferred_case_ids=deferred,
        known_regression_case_ids=regressions,
        preservation_difference_case_ids=differences,
        bank_comparable=plan.bank_comparable,
    )


def record_local_result(
    plan: EvaluationPlan,
    case_id: str,
    candidate: KernelCandidate,
    store: Store,
    *,
    graph_ref: str,
    materialization_evidence_ref: str,
    behavior_bindings: dict[str, str] | None = None,
    graphs_by_call: dict[int, str] | None = None,
) -> str:
    """Execute local checks after a worker genuinely rematerialized retained receipts.

    The worker's evidence artifact must contain candidate_id, graph_ref,
    source_refs and stage_evidence_refs. Every referenced artifact is loaded and
    hash verified. No supplied pass/fail, generated answer or cached MCP result
    substitutes for executing the candidate on the rebuilt graph. This records
    empirical materialization evidence, never source completeness or task truth.
    """
    if plan.candidate_id != candidate.id or plan.plan_sha256 != digest(
        plan.model_dump(mode="json", exclude={"plan_sha256"})
    ):
        raise ValueError("Plan candidate or immutable plan hash mismatch")
    decision = next((item for item in plan.decisions if item.case.case_id == case_id), None)
    if decision is None or decision.local_action != "rematerialize":
        raise ValueError("Case was not selected for rematerialization")
    evidence = store.get(materialization_evidence_ref)
    if evidence.get("candidate_id") != candidate.id or evidence.get("graph_ref") != graph_ref:
        raise ValueError("Rematerialization evidence does not bind the candidate and graph")
    if set(evidence.get("source_refs", [])) != set(decision.case.source_refs):
        raise ValueError("Rematerialization must use the same retained source receipts")
    if not evidence.get("stage_evidence_refs"):
        raise ValueError("Rematerialization requires actual extraction stage evidence")
    for reference in [graph_ref, *decision.case.source_refs, *evidence["stage_evidence_refs"]]:
        store.get(reference)
    case = decision.case.model_copy(deep=True)
    case.graph_ref = graph_ref
    for index, call in enumerate(case.calls):
        call.graph_ref = (graphs_by_call or {}).get(index, graph_ref)
        call.input_graph_known = True
        store.get(call.graph_ref)
    if case.behavior_input_ref:
        payload = {**store.get(case.behavior_input_ref), "graph_id": graph_ref}
        case.behavior_input_ref = store.put("rematerialized_behavior_input", payload)
    manifest = build_dependency_manifest(
        candidate, case, store, behavior_bindings=behavior_bindings
    )
    # The plan already pinned these contexts. Only actual graph inputs change.
    manifest.materialization = decision.manifest.materialization
    manifest.planner = decision.manifest.planner
    status, results, refs = _execute_case(case, candidate, store, behavior_bindings or {})
    receipt = CaseEvaluationReceipt(
        candidate_id=candidate.id,
        case_id=case_id,
        bank_version=case.bank_version,
        manifest=manifest,
        action="rematerialize",
        status=status,
        summary="Executed actual frozen computations on genuinely rematerialized retained evidence",
        evidence_refs=[materialization_evidence_ref, *refs],
        evaluated_case_ref=store.put("evaluation_case", case.model_dump(mode="json")),
        results=results,
        previous_receipt_ref=decision.previous_receipt_ref,
        planner_exposure="not_applicable" if not case.planner_required else "deferred",
    )
    if decision.previous_receipt_ref:
        previous = CaseEvaluationReceipt.model_validate(store.get(decision.previous_receipt_ref))
        receipt.historical_agent_evidence = previous.historical_agent_evidence
        if previous.fresh_episode_ref and previous.fresh_candidate_id:
            receipt.historical_agent_evidence = HistoricalAgentEvidence(
                episode_ref=previous.fresh_episode_ref,
                candidate_id=previous.fresh_candidate_id,
                agent_outcome=previous.agent_outcome,
                task_assessment=previous.task_assessment,
                evidence_refs=previous.evidence_refs,
            )
    return store.put("selective_case_evaluation", receipt.model_dump(mode="json"))


def record_fresh_result(
    receipt_ref: str, episode_ref: str, store: Store, *, assessment_ref: str | None = None
) -> str:
    """Attach a genuine immutable episode, retaining separate assessment status."""
    receipt = CaseEvaluationReceipt.model_validate(store.get(receipt_ref))
    episode = store.get(episode_ref)
    if (
        episode.get("kernel_revision") != receipt.candidate_id
        or episode.get("query_id") != receipt.case_id
    ):
        raise ValueError("Fresh episode does not belong to this exact candidate and case")
    if episode.get("split") not in {"construction", "development", "development-regression"}:
        raise ValueError("Held-out or ad hoc episodes cannot enter construction evaluation")
    receipt.fresh_episode_ref = episode_ref
    receipt.fresh_candidate_id = receipt.candidate_id
    receipt.agent_outcome = episode.get("status")
    receipt.planner_exposure = "checked"
    if assessment_ref:
        assessment = store.get(assessment_ref)
        if assessment.get("episode_id") != episode_ref:
            raise ValueError("Assessment does not identify this exact episode")
        receipt.task_assessment = assessment.get("status", "not_checked")
        receipt.evidence_refs.append(assessment_ref)
    return store.put("selective_case_evaluation", receipt.model_dump(mode="json"))


def refresh_evaluation_receipt(receipt: EvaluationReceipt, store: Store) -> EvaluationReceipt:
    """Recompute summaries after attaching real fresh or materialization results."""
    deferred, regressions, differences = [], [], []
    for case_id, reference in receipt.case_receipt_refs.items():
        item = CaseEvaluationReceipt.model_validate(store.get(reference))
        if item.status == "unknown" or item.planner_exposure == "deferred":
            deferred.append(case_id)
        if any(result.get("preservation_status") == "different" for result in item.results):
            differences.append(case_id)
        if item.previous_receipt_ref:
            previous = CaseEvaluationReceipt.model_validate(store.get(item.previous_receipt_ref))
            if (
                item.status == "failed"
                and previous.status == "passed"
                and previous.bank_version == item.bank_version
                and previous.manifest.computation.fingerprints.get("graphs")
                == item.manifest.computation.fingerprints.get("graphs")
                and previous.manifest.computation.fingerprints.get("schema")
                == item.manifest.computation.fingerprints.get("schema")
            ):
                regressions.append(case_id)
    return receipt.model_copy(
        update={
            "deferred_case_ids": sorted(deferred),
            "known_regression_case_ids": sorted(regressions),
            "preservation_difference_case_ids": sorted(differences),
        }
    )


def cases_from_episode(
    store: Store, episode_ref: str, *, bank_version: str, **flags
) -> EvaluationCase:
    """Normalize an actual saved trajectory without promoting its trace to scope."""
    episode = store.get(episode_ref)
    calls, sources = [], set()
    calls_by_observation = {
        f"observation-{index + 1}": decision
        for index, decision in enumerate(
            item for item in episode.get("trajectory", []) if item.get("action") == "call"
        )
    }
    for observation in episode.get("observations", []):
        if (
            observation.get("id") not in episode.get("citations", [])
            or observation.get("status") != "completed"
        ):
            continue
        sources.update(observation.get("receipt_ids", []))
        sources.update(observation.get("acquisition_evidence_ids", []))
        if observation.get("execution_id"):
            graph_ref = observation.get("working_graph_id") or episode.get("graph_id")
            execution = store.get(observation["execution_id"])
            input_known = _recorded_input_graph_known(
                store, episode, observation, execution, graph_ref
            )
            calls.append(
                ReplayCall(
                    function=observation["function"],
                    args=observation.get(
                        "args", calls_by_observation.get(observation.get("id"), {}).get("args", {})
                    ),
                    execution_ref=observation["execution_id"],
                    graph_ref=graph_ref,
                    input_graph_known=input_known,
                    source_refs=sorted(
                        set(
                            observation.get("receipt_ids", [])
                            + observation.get("acquisition_evidence_ids", [])
                        )
                    ),
                )
            )
    return EvaluationCase(
        case_id=episode["query_id"],
        question=episode.get("query"),
        split=episode["split"],
        bank_version=bank_version,
        calls=calls,
        graph_ref=episode.get("graph_id"),
        source_refs=sorted(sources),
        episode_ref=episode_ref,
        **flags,
    )


def _recorded_input_graph_known(store, episode, observation, execution, graph_ref) -> bool:
    """Recognize one immutable graph across every actual pure graph read.

    Executor callbacks may materialize an initially empty graph before the first
    read. The initial hash alone is then insufficient. Per-step hashes establish
    that replay on the retained working graph supplies every graph operator the
    same actual input. A changing graph between reads remains unsupported.
    """
    if graph_ref is None:
        return False
    graph_hash = digest(store.get(graph_ref))
    steps = execution.get("steps", [])
    reads = [step for step in steps if step.get("operator") in GRAPH_OPERATORS]
    if not any("graph_materialized_sha256" in step for step in reads):
        return execution.get("dependencies", {}).get("graph_sha256") == graph_hash
    kernel_ref = episode.get("kernel_revision")
    if not kernel_ref:
        return False
    kernel = store.get(kernel_ref)
    function = next(
        (item for item in kernel["functions"] if item["name"] == observation["function"]), None
    )
    if function is None or any(
        step["operator"] not in PURE_OPERATORS for step in function["steps"]
    ):
        return False
    if execution.get("dependencies", {}).get("function_sha256") != digest(
        FunctionSpec.model_validate(function).model_dump(mode="json")
    ):
        return False
    if execution.get("dependencies", {}).get("schema_sha256") != digest(kernel["schema"]):
        return False
    if len(steps) != len(function["steps"]) or any(
        actual.get("id") != declared["id"]
        or actual.get("operator") != declared["operator"]
        or actual.get("status") != "completed"
        for actual, declared in zip(steps, function["steps"], strict=True)
    ):
        return False
    return bool(reads) and all(
        step.get("graph_materialized_sha256") == graph_hash for step in reads
    )

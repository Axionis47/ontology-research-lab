"""Independent candidate verification, deliberately separate from kernel learning.

Learners submit immutable candidates, obligations and evidence references, never
their own pass/fail scores. This module checks saved evidence, executes pure
functions, and invokes only host-registered evaluators. No model or MCP call is
made. Missing semantic or coverage evidence remains unknown.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Literal

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from oak import operators
from oak.functions import FunctionSpec, execute_function, validate_functions
from oak.ontology import parse_schema, validate_graph_records
from oak.preservation import (
    EFFECT_OPERATORS,
    PreservationCertificate,
    certify_preservation,
    digest,
    lower_function,
    validate_certificate,
)
from oak.store import Store

CheckStatus = Literal["passed", "failed", "unknown"]
CheckDimension = Literal[
    "structure", "ontology", "graph", "execution", "generated", "coverage", "task", "preservation"
]


class StrictModel(BaseModel):
    """Public verification data has one strict authoritative definition."""

    model_config = ConfigDict(extra="forbid", strict=True)


class KernelCandidate(StrictModel):
    """Exact candidate inputs, with an explicitly recorded immediate parent."""

    id: str = Field(min_length=1)
    schema: dict[str, JsonValue]
    functions: list[dict[str, JsonValue]]
    parent_id: str | None = None


class ObligationCheck(StrictModel):
    """Frozen behavioral obligation supplied independently of candidate generation."""

    id: str = Field(min_length=1)
    group: Literal["retrieval", "subtask", "composition"]
    mandatory: bool = True
    function_names: list[str] = Field(default_factory=list)
    semantic_status: Literal["proposed", "grounded"] = "proposed"
    oracle_ref: str | None = None


class ObservedCheck(StrictModel):
    """A reference to actual evidence, with no caller-supplied correctness status."""

    obligation_id: str
    dimension: Literal["execution", "generated", "coverage", "task"]
    evidence_ref: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_id: str | None = None


class VerificationCheck(StrictModel):
    """One checked evidence dimension, never a composite success score."""

    obligation_id: str | None = None
    dimension: CheckDimension
    status: CheckStatus
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    details: dict[str, JsonValue] = Field(default_factory=dict)


class VerificationReport(StrictModel):
    """Decision and provenance for one candidate, independent of learner utility."""

    version: Literal[1] = 1
    candidate_id: str
    parent_id: str | None = None
    disposition: Literal["execution_eligible", "target_met", "incomplete", "rejected"]
    execution_eligible: bool
    target_met: bool
    checks: list[VerificationCheck]
    counterexamples: list[dict[str, JsonValue]] = Field(default_factory=list)
    unresolved_obligation_ids: list[str] = Field(default_factory=list)
    coverage_by_group: dict[str, dict[str, int]] = Field(default_factory=dict)
    generated_coverage_by_group: dict[str, dict[str, int]] = Field(default_factory=dict)
    known_regressions: int = 0
    preservation: PreservationCertificate | None = None


Evaluator = Callable[[KernelCandidate, ObligationCheck, dict], dict]


class CandidateFunctionRef(StrictModel):
    """Execute the named function from the actual candidate, not a proposed copy."""

    function: str = Field(min_length=1)


class GeneratedCheckSpec(StrictModel):
    """A generated, graph-grounded consistency check, never an independent oracle.

    Programs execute through the same restricted pure DSL as kernel functions.
    The model proposes a relationship, not an expected answer or executable code.
    """

    id: str = Field(min_length=1, max_length=128)
    obligation_id: str = Field(min_length=1)
    description: str = Field(min_length=1, max_length=4000)
    left: FunctionSpec | CandidateFunctionRef
    left_args: dict[str, JsonValue] = Field(default_factory=dict)
    relation: Literal["equal", "subset", "length_equals", "nonempty"]
    right: FunctionSpec | CandidateFunctionRef | None = None
    right_args: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_operands(self) -> GeneratedCheckSpec:
        if self.relation != "nonempty" and self.right is None:
            raise ValueError("Binary generated checks require a right program")
        if self.relation == "nonempty" and (self.right is not None or self.right_args):
            raise ValueError("Nonempty checks have only a left program")
        return self


def _step_references(value: JsonValue) -> set[str]:
    if isinstance(value, dict):
        if set(value) == {"$step"}:
            return {value["$step"]}
        if set(value) == {"$path"}:
            return {value["$path"][0]}
        return set().union(*(_step_references(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_step_references(item) for item in value))
    return set()


def _check_generated_program(function: FunctionSpec, schema: dict) -> None:
    validate_functions([function], schema)
    if any(step.operator in EFFECT_OPERATORS for step in function.steps):
        raise ValueError("Generated checks cannot dispatch MCP calls or invoke models")
    rooted: dict[str, bool] = {}
    for step in function.steps:
        rooted[step.id] = step.operator in operators.GRAPH_OPERATORS or any(
            rooted[reference] for reference in _step_references(step.args)
        )
    if not any(rooted[reference] for reference in _step_references(function.result)):
        raise ValueError("Generated check results must depend on actual graph evidence")


def execute_generated_check(
    specification: GeneratedCheckSpec | dict,
    graph: dict,
    schema: dict,
    *,
    candidate_functions: list[dict] | None = None,
) -> dict:
    """Actually execute a generated relation on genuine graph data, without services.

    This establishes only the proposed relation on the supplied graph. Equal
    programs may agree while both miss source facts or misunderstand the task.
    Such a result is never an independent assessment or completeness proof.
    """
    spec = (
        specification
        if isinstance(specification, GeneratedCheckSpec)
        else GeneratedCheckSpec.model_validate(specification)
    )
    candidate_refs = [
        operand.function
        for operand in (spec.left, spec.right)
        if isinstance(operand, CandidateFunctionRef)
    ]
    receipt = {
        "evaluator": "generated_dsl_v1",
        "evaluator_version": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "independent": False,
        "scope": "Generated internal consistency on this exact graph; no source-completeness or task-correctness claim",
        "check_id": spec.id,
        "graph_sha256": digest(graph),
        "candidate_functions_checked": sorted(set(candidate_refs)),
        "contributes_to_learning": bool(candidate_refs),
    }

    def resolve(operand: FunctionSpec | CandidateFunctionRef) -> FunctionSpec | None:
        if isinstance(operand, FunctionSpec):
            return operand
        return next(
            (
                FunctionSpec.model_validate(function)
                for function in candidate_functions or []
                if function["name"] == operand.function
            ),
            None,
        )

    left_program = resolve(spec.left)
    right_program = resolve(spec.right) if spec.right is not None else None
    if left_program is None or (spec.right is not None and right_program is None):
        return {
            **receipt,
            "status": "failed",
            "summary": "Generated check refers to an absent candidate function",
        }
    for program, operand in ((left_program, spec.left), (right_program, spec.right)):
        if program is None:
            continue
        if isinstance(operand, CandidateFunctionRef) and any(
            step.operator in EFFECT_OPERATORS for step in program.steps
        ):
            return {
                **receipt,
                "status": "unknown",
                "summary": "Candidate function has effects; generated checks never redispatch them",
            }
        _check_generated_program(program, schema)
    if (
        spec.relation in {"equal", "subset"}
        and right_program is not None
        and spec.left_args == spec.right_args
        and lower_function(left_program, schema) == lower_function(right_program, schema)
    ):
        return {
            **receipt,
            "status": "unknown",
            "summary": "Identical generated operands are tautological and provide no coverage evidence",
        }
    try:
        left_execution = execute_function(
            deepcopy(graph), [left_program], left_program.name, spec.left_args, schema=schema
        )
        left = left_execution["value"]
        receipt["left_execution"] = left_execution
        right = None
        if right_program is not None:
            right_execution = execute_function(
                deepcopy(graph), [right_program], right_program.name, spec.right_args, schema=schema
            )
            receipt["right_execution"] = right_execution
            right = right_execution["value"]
        if spec.relation == "equal":
            passed = left == right
        elif spec.relation == "subset":
            if not isinstance(left, list) or not isinstance(right, list):
                raise ValueError("Subset comparison requires two lists")
            if not left:
                return {
                    **receipt,
                    "status": "unknown",
                    "summary": "Empty subset is vacuous and provides no coverage evidence",
                }
            # Multiset containment preserves duplicate semantics.
            remaining = list(right)
            passed = True
            for value in left:
                if value not in remaining:
                    passed = False
                    break
                remaining.remove(value)
        elif spec.relation == "length_equals":
            if not isinstance(left, list) or isinstance(right, bool) or not isinstance(right, int):
                raise ValueError("Length comparison requires a list and an integer")
            passed = len(left) == right
        else:
            if not isinstance(left, list):
                raise ValueError("Nonempty comparison requires a list")
            passed = bool(left)
        return {
            **receipt,
            "status": "passed" if passed else "failed",
            "summary": f"Generated {spec.relation} relation {'held' if passed else 'failed'} on actual graph execution",
        }
    except (ValueError, TypeError, KeyError) as error:
        return {
            **receipt,
            "status": "failed",
            "summary": f"Generated check execution failed: {error}",
        }


def _event(store: Store, artifact_id: str, stages: set[str]) -> dict | None:
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT run_id,stage,status FROM events WHERE artifact_id=? ORDER BY id",
            (artifact_id,),
        ).fetchall()
    return next((dict(row) for row in rows if row["stage"] in stages), None)


def _file_evidence(artifact: dict) -> bytes:
    path = Path(artifact["path"])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
        raise ValueError("Validation source file hash mismatch")
    return raw


def _ontology_check(
    store: Store, candidate: KernelCandidate, reference: str | None
) -> VerificationCheck:
    check = VerificationCheck(
        dimension="ontology", status="unknown", summary="No attributable HermiT evidence supplied"
    )
    if reference is None:
        return check
    check.evidence_refs = [reference]
    try:
        report = store.get(reference)
        if report.get("evidence_type") != "owl_hermit":
            raise ValueError("Evidence is not an OWL/HermiT result")
        normalized = parse_schema(candidate.schema).model_dump(mode="json")
        if json.loads(_file_evidence(report["schema"])) != normalized:
            raise ValueError("HermiT result belongs to a different schema")
        stdout = _file_evidence(report["stdout"]).decode()
        _file_evidence(report["stderr"])
        _file_evidence(report["input"])
        if report.get("valid") is True and report.get("status") == "consistent":
            if not (
                report.get("returncode") == 0
                and "http://www.w3.org/2002/07/owl#Thing is satisfiable." in stdout
                and "Classes equivalent to 'http://www.w3.org/2002/07/owl#Nothing':" in stdout
                and not report.get("unsatisfiable_classes")
            ):
                raise ValueError("HermiT receipt lacks complete successful output")
            check.status = "passed"
            check.summary = "Actual HermiT result matches the exact candidate schema"
        elif report.get("status") in {"inconsistent", "unsatisfiable_classes"}:
            check.status = "failed"
            check.summary = "Actual HermiT validation rejected the candidate ontology"
        else:
            check.summary = "HermiT did not establish ontology validity"
    except (OSError, KeyError, TypeError, ValueError) as error:
        check.summary = f"Ontology evidence unavailable or incompatible: {error}"
    return check


def _recorded_execution(
    store: Store, candidate: KernelCandidate, payload: dict, obligation: ObligationCheck
) -> dict:
    """Validate actual event-bound effect traces without redispatching their calls."""
    probe_id = payload["probe_evidence_id"]
    probe = store.get(probe_id)
    event = _event(store, probe_id, {"function_probe"})
    if event is None or event["status"] != "passed" or probe.get("status") != "passed":
        raise ValueError("No passed function-probe event attests this execution")
    function_name = probe["probe"]["function"]
    if function_name not in obligation.function_names:
        raise ValueError("Probe is not a witness for this obligation")
    function = next(fn for fn in candidate.functions if fn["name"] == function_name)
    execution = probe["execution"]
    args = probe["probe"]["args"]
    Draft202012Validator(function["inputs"], format_checker=FormatChecker()).validate(args)
    Draft202012Validator(function["output_schema"], format_checker=FormatChecker()).validate(
        execution["value"]
    )
    graph = store.get(probe["graph_id"])
    validation = validate_graph_records(candidate.schema, graph["nodes"], graph.get("edges", []))
    if not validation["valid"]:
        raise ValueError("Recorded probe graph fails candidate validation")
    canonical_function = validate_functions([function], candidate.schema)[0].model_dump(mode="json")
    dependencies = execution["dependencies"]
    if dependencies.get("function_sha256") != digest(canonical_function):
        raise ValueError("Probe function dependency does not match candidate")
    if dependencies.get("schema_sha256") != digest(candidate.schema):
        raise ValueError("Probe schema dependency does not match candidate")
    if dependencies.get("graph_after_sha256") != digest(graph):
        raise ValueError("Probe graph dependency does not match retained graph")
    steps = execution["steps"]
    if len(steps) != len(function["steps"]) or any(
        actual.get("id") != expected["id"]
        or actual.get("operator") != expected["operator"]
        or actual.get("status") != "completed"
        for actual, expected in zip(steps, function["steps"], strict=True)
    ):
        raise ValueError("Probe lacks the complete ordered function trace")
    receipts = []
    for identity in probe.get("receipt_ids", []):
        receipt = store.get(identity)
        receipt_event = _event(store, identity, {"mcp_call"})
        if (
            receipt_event is None
            or receipt_event["run_id"] != event["run_id"]
            or receipt_event["status"] != "completed"
            or receipt.get("status") != "completed"
            or receipt.get("tool_call_attempted") is not True
            or receipt.get("output") is None
        ):
            raise ValueError("Probe receipt does not attest an actual completed MCP call")
        receipts.append(receipt)
    acquired = [step for step in steps if step["operator"] == "invoke_capability"]
    if len(acquired) != len(receipts):
        raise ValueError("Probe acquisition steps do not match actual receipts")
    for step, receipt in zip(acquired, receipts, strict=True):
        if (
            step["inputs"].get("capability") != receipt["capability_id"]
            or step["inputs"].get("arguments") != receipt["args"]
        ):
            raise ValueError("Probe receipt does not match actual capability arguments")
    if any(step["operator"] == "extract_runtime_slots" for step in steps):
        return {
            "status": "unknown",
            "summary": "Slot-extraction model provenance is outside this recorded-probe verifier",
            "function": function_name,
        }
    return {
        "status": "passed",
        "summary": "Recorded execution verified against actual events and dependencies; no effect replay",
        "function": function_name,
        "mode": "recorded_execution",
        "graph_id": probe["graph_id"],
        "probe_evidence_id": probe_id,
        "receipt_ids": probe.get("receipt_ids", []),
        "task_correctness": "not_checked",
    }


def _execution_check(
    store: Store, candidate: KernelCandidate, obligation: ObligationCheck, payload: dict
) -> dict:
    if payload.get("candidate_id") != candidate.id:
        raise ValueError("Execution evidence belongs to a different candidate")
    if "probe_evidence_id" in payload:
        return _recorded_execution(store, candidate, payload, obligation)
    name = payload["function"]
    if name not in obligation.function_names:
        raise ValueError("Execution is not mapped to this obligation")
    function = next(fn for fn in candidate.functions if fn["name"] == name)
    if any(step["operator"] in EFFECT_OPERATORS for step in function["steps"]):
        return {
            "status": "unknown",
            "summary": "Effectful execution requires an actual recorded-probe reference",
            "function": name,
        }
    graph = store.get(payload["graph_id"])
    actual = execute_function(
        deepcopy(graph), candidate.functions, name, payload["args"], schema=candidate.schema
    )
    if "value" in payload and actual["value"] != payload["value"]:
        return {
            "status": "failed",
            "summary": "Real function execution differs from the retained comparison value",
            "function": name,
            "actual": actual,
            "expected_recorded_value": payload["value"],
        }
    return {
        "status": "passed",
        "summary": "Pure function executed on the actual retained graph; task correctness is separate",
        "function": name,
        "mode": "actual_reexecution",
        "graph_id": payload["graph_id"],
        "actual": actual,
        "task_correctness": "not_checked",
    }


def verify_candidate(
    candidate: KernelCandidate | dict,
    obligations: list[ObligationCheck | dict],
    evidence: list[ObservedCheck | dict],
    *,
    store: Store,
    evaluators: Mapping[str, Evaluator] | None = None,
    ontology_validation_ref: str | None = None,
    parent: KernelCandidate | dict | None = None,
    certificate: PreservationCertificate | dict | None = None,
) -> VerificationReport:
    """Verify one candidate without generating requirements, answers or evidence.

    Host-registered evaluators are a trusted boundary: task callbacks must match
    the frozen obligation's oracle reference. A model-proposed evaluator name
    cannot register executable code. Callbacks receive verified retained source
    payloads and must return their own attributable status and explanation.
    """
    candidate = (
        candidate
        if isinstance(candidate, KernelCandidate)
        else KernelCandidate.model_validate(candidate)
    )
    obligations = [
        item if isinstance(item, ObligationCheck) else ObligationCheck.model_validate(item)
        for item in obligations
    ]
    evidence = [
        item if isinstance(item, ObservedCheck) else ObservedCheck.model_validate(item)
        for item in evidence
    ]
    if len({item.id for item in obligations}) != len(obligations):
        raise ValueError("Obligation identifiers must be unique")
    by_id = {item.id: item for item in obligations}
    if any(item.obligation_id not in by_id for item in evidence):
        raise ValueError("Evidence references an obligation outside the frozen bank")
    evaluators = evaluators or {}
    checks: list[VerificationCheck] = []
    names = {function.get("name") for function in candidate.functions}
    try:
        parse_schema(candidate.schema)
        validate_functions(candidate.functions, candidate.schema)
        checks.append(
            VerificationCheck(
                dimension="structure",
                status="passed",
                summary="Schema and function contracts are structurally valid",
            )
        )
    except (ValueError, TypeError, KeyError) as error:
        checks.append(VerificationCheck(dimension="structure", status="failed", summary=str(error)))
    checks.append(_ontology_check(store, candidate, ontology_validation_ref))
    for obligation in obligations:
        missing = set(obligation.function_names) - names
        checks.append(
            VerificationCheck(
                obligation_id=obligation.id,
                dimension="structure",
                status="failed"
                if missing
                else "unknown"
                if not obligation.function_names
                else "passed",
                summary=(
                    f"Callable witness missing: {sorted(missing)}"
                    if missing
                    else "No callable witness supplied; obligation remains unresolved"
                    if not obligation.function_names
                    else "Declared callable witnesses exist; semantic correctness is separate"
                ),
            )
        )
    for observation in evidence:
        obligation = by_id[observation.obligation_id]
        check = VerificationCheck(
            obligation_id=obligation.id,
            dimension=observation.dimension,
            status="unknown",
            summary="No independent check completed",
            evidence_refs=[observation.evidence_ref],
        )
        try:
            payload = store.get(observation.evidence_ref)
            if not isinstance(payload, dict):
                raise ValueError("Verification evidence must be an attributable object")
            if observation.dimension == "execution":
                result = _execution_check(store, candidate, obligation, payload)
            elif observation.dimension == "generated":
                if payload.get("candidate_id") != candidate.id:
                    raise ValueError("Generated-check evidence belongs to a different candidate")
                if observation.evaluator_id != "generated_dsl_v1":
                    raise ValueError(
                        "Generated checks require the registered generic DSL evaluator"
                    )
                specification = GeneratedCheckSpec.model_validate(payload["check"])
                if specification.obligation_id != obligation.id:
                    raise ValueError("Generated check refers to another obligation")
                if payload.get("source_schema_sha256", digest(candidate.schema)) != digest(
                    candidate.schema
                ):
                    result = {
                        "status": "unknown",
                        "summary": "Generated check bank uses another schema; no validated graph translation is supplied",
                        "independent": False,
                    }
                else:
                    result = execute_generated_check(
                        specification,
                        store.get(payload["graph_id"]),
                        candidate.schema,
                        candidate_functions=candidate.functions,
                    )
            elif observation.evaluator_id not in evaluators:
                result = {
                    "status": "unknown",
                    "summary": "No trusted evaluator is registered for this evidence",
                }
            elif observation.dimension == "task" and (
                obligation.semantic_status != "grounded"
                or obligation.oracle_ref != observation.evaluator_id
            ):
                result = {
                    "status": "unknown",
                    "summary": "Task interpretation lacks a matching independent oracle",
                }
            else:
                result = evaluators[observation.evaluator_id](
                    candidate, obligation, deepcopy(payload)
                )
                if result.get("evaluator_version") is None:
                    raise ValueError(
                        "Independent evaluator must identify its implementation version"
                    )
            if result.get("status") not in {"passed", "failed", "unknown"}:
                raise ValueError("Evaluator returned an invalid evidence status")
            check.status = result["status"]
            check.summary = result["summary"]
            check.details = {
                key: value for key, value in result.items() if key not in {"status", "summary"}
            }
            for identity in result.get("evidence_refs", []):
                store.get(identity)
                if identity not in check.evidence_refs:
                    check.evidence_refs.append(identity)
        except (OSError, ValueError, TypeError, KeyError, StopIteration) as error:
            check.status = "failed"
            check.summary = f"Evidence check failed: {type(error).__name__}: {error}"
        checks.append(check)
    for obligation in obligations:
        for dimension in ("execution", "coverage", "task"):
            if not any(
                check.obligation_id == obligation.id and check.dimension == dimension
                for check in checks
            ):
                checks.append(
                    VerificationCheck(
                        obligation_id=obligation.id,
                        dimension=dimension,
                        status="unknown",
                        summary="No evidence supplied for this obligation and dimension",
                    )
                )
    preservation = None
    known_regressions = 0
    if parent is not None:
        parent = (
            parent
            if isinstance(parent, KernelCandidate)
            else KernelCandidate.model_validate(parent)
        )
        if certificate is None:
            preservation = certify_preservation(parent, candidate)
        else:
            try:
                preservation = validate_certificate(certificate, parent, candidate)
            except ValueError as error:
                checks.append(
                    VerificationCheck(
                        dimension="preservation",
                        status="failed",
                        summary=f"Invalid preservation evidence: {error}",
                    )
                )
        if preservation is not None:
            status = (
                "passed"
                if preservation.status == "certified"
                else "failed"
                if preservation.status in {"counterexample", "invalid_evidence"}
                else "unknown"
            )
            checks.append(
                VerificationCheck(
                    dimension="preservation", status=status, summary=preservation.summary
                )
            )
            known_regressions = int(preservation.status == "counterexample")
    elif candidate.parent_id is not None:
        checks.append(
            VerificationCheck(
                dimension="preservation",
                status="unknown",
                summary="Recorded parent was not supplied for preservation verification",
            )
        )
    successful_functions = {
        check.details.get("function")
        for check in checks
        if check.dimension == "execution" and check.status == "passed"
    }
    global_gate = all(
        any(
            check.dimension == dimension
            and check.obligation_id is None
            and check.status == "passed"
            for check in checks
        )
        for dimension in ("structure", "ontology")
    )
    execution_eligible = bool(global_gate and names and names.issubset(successful_functions))
    unresolved = []
    coverage: dict[str, dict[str, int]] = {}
    generated_coverage: dict[str, dict[str, int]] = {}
    for obligation in obligations:
        group = coverage.setdefault(
            obligation.group, {"total": 0, "passed": 0, "failed": 0, "unknown": 0}
        )
        group["total"] += 1
        relevant = [check for check in checks if check.obligation_id == obligation.id]
        failed = any(check.status == "failed" for check in relevant)
        passed = (
            obligation.semantic_status == "grounded"
            and all(
                any(check.dimension == dimension and check.status == "passed" for check in relevant)
                for dimension in ("structure", "execution", "coverage", "task")
            )
            and not failed
        )
        group["failed" if failed else "passed" if passed else "unknown"] += 1
        generated_group = generated_coverage.setdefault(
            obligation.group, {"total": 0, "passed": 0, "failed": 0, "unknown": 0}
        )
        generated_group["total"] += 1
        generated_results = [
            check
            for check in relevant
            if check.dimension == "generated" and check.details.get("contributes_to_learning")
        ]
        generated_status = (
            "failed"
            if any(check.status == "failed" for check in generated_results)
            else "passed"
            if generated_results and all(check.status == "passed" for check in generated_results)
            else "unknown"
        )
        generated_group[generated_status] += 1
        if obligation.mandatory and not passed:
            unresolved.append(obligation.id)
    blocking = [
        check
        for check in checks
        if check.status == "failed"
        and check.dimension != "generated"
        and (check.obligation_id is None or by_id[check.obligation_id].mandatory)
    ]
    preservation_passed = candidate.parent_id is None or any(
        check.dimension == "preservation" and check.status == "passed" for check in checks
    )
    target_met = bool(
        execution_eligible
        and obligations
        and not unresolved
        and not blocking
        and preservation_passed
    )
    disposition = (
        "rejected"
        if blocking
        else "target_met"
        if target_met
        else "execution_eligible"
        if execution_eligible
        else "incomplete"
    )
    return VerificationReport(
        candidate_id=candidate.id,
        parent_id=candidate.parent_id,
        disposition=disposition,
        execution_eligible=execution_eligible,
        target_met=target_met,
        checks=checks,
        counterexamples=[
            {
                "obligation_id": check.obligation_id,
                "dimension": check.dimension,
                "summary": check.summary,
                "evidence_refs": check.evidence_refs,
                "details": check.details,
            }
            for check in checks
            if check.status == "failed"
        ],
        unresolved_obligation_ids=unresolved,
        coverage_by_group=coverage,
        generated_coverage_by_group=generated_coverage,
        known_regressions=known_regressions,
        preservation=preservation,
    )

"""Deterministic subtask closure and selection over independent verification.

The learner proposes and ranks candidates. It never turns an interpretation,
function mapping, or cheap materialization into independent success evidence.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from copy import deepcopy

from oak.construction_contracts import RequirementAnalysis, RequirementObligation
from oak.learning_contracts import TaskIR, TaskObligation, TaskOperation, TaskProgram
from oak.store import canonical


def _hash(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _program_slice(program: TaskProgram, result: str) -> TaskProgram:
    """Keep the full dependency closure of an observable intermediate result."""
    operations = {operation.id: operation for operation in program.operations}
    keep: set[str] = set()

    def visit(identity: str):
        if identity in keep:
            return
        keep.add(identity)
        for parent in operations[identity].inputs:
            visit(parent)

    visit(result)
    selected = [operation for operation in program.operations if operation.id in keep]
    fields = set().union(*(set(operation.fields) for operation in selected))
    return TaskProgram(
        fields=[field for field in program.fields if field.id in fields],
        operations=selected,
        result=result,
        input_domain=program.input_domain,
        parameter_fields={
            key: value for key, value in program.parameter_fields.items() if value in fields
        },
        source_parameters=program.source_parameters,
        ordering=program.ordering,
        observation_contract=f"Observable {operations[result].result_kind} at {result}; "
        "retain entity identity, multiplicity, units, temporal scope and provenance.",
    )


def freeze_task_ir(
    scope: str,
    obligations: list[RequirementObligation],
    analysis: RequirementAnalysis,
) -> TaskIR:
    """Freeze literal requirements, dependency closure, and bounded exploration.

    Analysis is supplied before any candidate is drafted. Derived behaviors
    therefore cannot disappear when a candidate drops an operator or field.
    All interpretations remain proposed unless an independent adapter grounds
    them outside this function. No benchmark answers are accepted here.
    """
    interpretations = {item.obligation_id: item for item in analysis.interpretations}
    required: list[TaskObligation] = []
    exploratory: dict[str, TaskObligation] = {}
    gaps = list(analysis.gaps)
    for source in obligations:
        interpretation = interpretations[source.obligation_id]
        program = interpretation.program
        root = TaskObligation(
            obligation_id=source.obligation_id,
            case_id=source.case_id,
            text=source.text,
            parent_requirement_ids=[source.obligation_id],
            derivation_rule="literal_requirement",
            program=program,
            group="composition" if program and len(program.operations) > 1 else "retrieval",
        )
        required.append(root)
        gaps.extend(interpretation.gaps)
        if program is None:
            gaps.append(f"{source.obligation_id}: no grounded typed interpretation available")
            continue
        # Every observable record/path intermediate is retained. In particular
        # this includes inputs to lossy aggregates and predicate-bearing views.
        for operation in program.operations:
            if operation.id == program.result:
                continue
            sliced = _program_slice(program, operation.id)
            rule = "observable_dependency_closure"
            identity = (
                "r_"
                + _hash(
                    {"parent": source.obligation_id, "rule": rule, "program": sliced.model_dump()}
                )[:18]
            )
            required.append(
                TaskObligation(
                    obligation_id=identity,
                    case_id=source.case_id,
                    text=f"Return the {operation.result_kind} used by {source.text}",
                    parent_requirement_ids=[source.obligation_id],
                    derivation_rule=rule,
                    program=sliced,
                    group="subtask",
                )
            )
        for operation in program.operations:
            if operation.result_kind != "records":
                continue
            base = _program_slice(program, operation.id)
            additions: list[list[TaskOperation]] = [
                [
                    TaskOperation(
                        id="explore_count",
                        operator="aggregate",
                        inputs=[base.result],
                        fields=[],
                        result_kind="scalar",
                        parameters={"operation": "count"},
                    )
                ]
            ]
            for field in base.fields:
                projection = TaskOperation(
                    id="explore_project",
                    operator="project",
                    inputs=[base.result],
                    fields=[field.id],
                    result_kind="records",
                )
                additions.append([projection])
                if field.value_type == "number":
                    for aggregation in ("min", "max", "sum", "mean"):
                        additions.append(
                            [
                                projection,
                                TaskOperation(
                                    id="explore_aggregate",
                                    operator="aggregate",
                                    inputs=[projection.id],
                                    fields=[field.id],
                                    result_kind="scalar",
                                    parameters={"operation": aggregation},
                                ),
                            ]
                        )
            existing = {item.id for item in base.operations}
            for suffix in additions:
                if (
                    existing.intersection(item.id for item in suffix)
                    or len(base.operations) + len(suffix) > 32
                ):
                    continue
                expanded = TaskProgram(
                    fields=base.fields,
                    operations=[*base.operations, *suffix],
                    result=suffix[-1].id,
                    input_domain=base.input_domain,
                    parameter_fields=base.parameter_fields,
                    source_parameters=base.source_parameters,
                    ordering=base.ordering,
                    observation_contract="Exploratory typed composition; scope and correctness unverified.",
                )
                key = _hash({"parent": source.obligation_id, "program": expanded.model_dump()})
                exploratory[key] = TaskObligation(
                    obligation_id="r_" + key[:18],
                    case_id=source.case_id,
                    text=f"Explore {suffix[-1].operator} over a grounded task dependency",
                    parent_requirement_ids=[source.obligation_id],
                    derivation_rule="bounded_typed_composition",
                    program=expanded,
                    group="composition",
                    mandatory=False,
                )
    selected = [exploratory[key] for key in sorted(exploratory)[:128]]
    return TaskIR(
        source_sha256=_hash([item.model_dump() for item in obligations]),
        analysis_sha256=_hash(analysis.model_dump()),
        scope=scope,
        obligations=[*required, *selected],
        exploration_omitted=max(0, len(exploratory) - len(selected)),
        interpretation_gaps=sorted(set(gaps)),
    )


def candidate_rank(report: dict, kernel: dict, *, measured_cost: float = 0.0) -> tuple[float, ...]:
    """Rank only checker-produced evidence, with unknown outcomes never passed.

    The caller supplies a report read from the authoritative verification flow.
    Smaller tuples are better. Structural/execution eligibility is considered
    before coverage; code size and measured cost cannot compensate for a lost
    protected behavior or unresolved mandatory requirement.
    """
    results = report.get("checks", report.get("results", []))
    if isinstance(results, dict):
        results = [
            value
            for group in results.values()
            for value in (group if isinstance(group, list) else [group])
        ]
    results = [item for item in results if isinstance(item, dict)]
    # Duplicated evidence rows or alternate traces cannot change the objective.
    behavior = report.get("behavior_evaluation") or None
    failures = len(
        {
            (
                item.get("dimension"),
                item.get("obligation_id", item.get("behavior_id")),
                item.get("group"),
            )
            for item in results
            if item.get("status") == "failed"
            and (behavior is None or item.get("dimension") not in {"generated", "behavior"})
        }
    )
    unresolved = len(report.get("unresolved_obligation_ids", report.get("unresolved_ids", [])))
    groups: dict[str, Counter] = {}
    for item in results:
        if item.get("dimension") not in {"task", "coverage"}:
            continue
        counter = groups.setdefault(item.get("group", "unknown"), Counter())
        counter["total"] += 1
        counter["passed"] += item.get("status") == "passed"
    rates = [group["passed"] / group["total"] for group in groups.values()]
    passed = sum(group["passed"] for group in groups.values())
    total = sum(group["total"] for group in groups.values())
    # Reusable aliases do not pay for identical implementation bodies twice.
    # Canonical lowering is a size normalization, not a preservation claim.
    from oak.preservation import lower_function

    bodies = set()
    for function in kernel["functions"]:
        try:
            body = lower_function(function, kernel["schema"]).model_dump(mode="json")
        except ValueError:
            body = {
                key: value for key, value in function.items() if key not in {"name", "description"}
            }
        bodies.add(canonical(body))
    size = len(canonical(kernel["schema"])) + sum(len(body) for body in bodies)
    unknown_behaviors = unknown_strata = evaluated_strata = 0
    if behavior is not None:
        # A measured generated failure is an unresolved behavior, not a cost
        # that can be removed by omitting its implementation. Prefer retained
        # measurement before penalties/description size when pass counts tie.
        mandatory = {
            item["behavior_id"]: item
            for item in behavior.get("checks", [])
            if item.get("mandatory", True)
        }
        unknown_behaviors = sum(
            item.get("status") not in {"passed", "failed"} for item in mandatory.values()
        )
        evaluated_strata = len(
            {
                (identity, stratum.get("index", index))
                for identity, item in mandatory.items()
                for index, stratum in enumerate(item.get("strata", []))
                if stratum.get("status") in {"passed", "failed"}
            }
        )
        unknown_strata = sum(
            max(
                0,
                item.get("total_strata", 0)
                - sum(
                    stratum.get("status") in {"passed", "failed"}
                    for stratum in item.get("strata", [])
                ),
            )
            for item in mandatory.values()
        )
        unresolved = len(set(behavior.get("unresolved_behavior_ids", [])))
    generated = (
        behavior.get("behavior_coverage_by_group", {})
        if behavior is not None
        else report.get("generated_coverage_by_group", {})
    )
    generated_rates = [
        group["passed"] / group["total"] for group in generated.values() if group["total"]
    ]
    generated_total = sum(group["total"] for group in generated.values())
    generated_passed = sum(group["passed"] for group in generated.values())
    return (
        float(report.get("known_regressions", 0)),
        float(failures),
        float(unresolved),
        -min(rates, default=0.0),
        -(passed / total if total else 0.0),
        -min(generated_rates, default=0.0),
        -(generated_passed / generated_total if generated_total else 0.0),
        float(unknown_behaviors),
        float(unknown_strata),
        -float(evaluated_strata),
        float(
            len(
                {
                    (item.get("behavior_id"), item.get("reason"))
                    for item in (behavior or {}).get("penalties", [])
                }
            )
        ),
        float(size),
        float(measured_cost),
    )


def repair_feedback(report: dict) -> dict:
    """Expose attributable verifier failures without admitting evaluator answers."""
    return {
        "verification_status": report.get("disposition", "incomplete"),
        "counterexamples": deepcopy(
            [
                *report.get("counterexamples", []),
                *report.get("behavior_evaluation", {}).get("counterexamples", []),
            ]
        ),
        "behavior_penalties": deepcopy(report.get("behavior_evaluation", {}).get("penalties", [])),
        "unresolved_behavior_ids": list(
            report.get("behavior_evaluation", {}).get("unresolved_behavior_ids", [])
        ),
        "unresolved_obligation_ids": list(report.get("unresolved_obligation_ids", [])),
        "actionable_learning_gaps": actionable_learning_gaps(report),
        "instruction": "Repair the evidenced boundary, retaining all frozen obligations and inherited functions.",
    }


def actionable_learning_gaps(report: dict) -> list[str]:
    """Separate improvable generated behavior from absent independent oracles."""
    checks = report.get("checks", [])
    if report.get("behavior_evaluation"):
        behavior = report["behavior_evaluation"]
        return [
            f"Frozen behavior remains unresolved:{identity}"
            for identity in behavior.get("unresolved_behavior_ids", [])
        ] + [
            f"Repair semantic input contract:{item['behavior_id']}:{item['reason']}"
            for item in behavior.get("penalties", [])
        ]
    mandatory_unresolved = set(report.get("unresolved_obligation_ids", []))
    gaps = [
        f"Callable implementation missing for {item['obligation_id']}"
        for item in checks
        if item.get("dimension") == "structure"
        and item.get("obligation_id")
        and item["obligation_id"] in mandatory_unresolved
        and item.get("status") == "unknown"
    ]
    if not any(
        item.get("dimension") == "generated"
        and item.get("details", {}).get("contributes_to_learning")
        for item in checks
    ):
        gaps.append(
            "Generate a non-tautological consistency check that references an actual candidate pure function"
        )
    return gaps


def compare_fresh_runs(previous: dict[str, dict], current: list[dict]) -> dict:
    """Keep observed agent regressions separate from independent task failures.

    A prior completed agent run does not establish truth. It does establish an
    observed behavior worth retaining. Missing follow-up evidence is unknown,
    not failure or an implied repeated success.
    """
    by_query = {item["query_id"]: item for item in current}
    failures, regressions, missing = [], [], []

    def failed(item):
        return (
            item.get("status") != "complete"
            or (item.get("assessment") or {}).get("status") == "failed"
        )

    for item in current:
        if failed(item):
            failures.append(item["query_id"])
    for identity, old in previous.items():
        if identity not in by_query:
            missing.append(identity)
            continue
        new = by_query[identity]
        if old.get("status") == "complete" and new.get("status") != "complete":
            regressions.append(identity)
        elif (old.get("assessment") or {}).get("status") == "passed" and (
            new.get("assessment") or {}
        ).get("status") == "failed":
            regressions.append(identity)
    return {
        "failures": sorted(failures),
        "regressions": sorted(set(regressions)),
        "unexecuted_previous": sorted(missing),
    }

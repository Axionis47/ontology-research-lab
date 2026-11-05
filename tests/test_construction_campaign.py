"""Campaign comparison components over genuine retained weather evidence.

The authored semantic contracts are compiler inputs, not canned model answers.
All function and mutation results come from actual executable components.
"""

from copy import deepcopy

import pytest
from test_behavior import bank_for, bindings_for
from test_selective_evaluation import retained as weather_retained

from oak.behavior import compile_behavior_bindings
from oak.construction_campaign import (
    behavior_cases,
    behavior_evaluation,
    compare_behavior_evaluations,
    materialization_context,
)
from oak.selective_evaluation import EvaluationReceipt, execute_local_plan, plan_evaluation
from oak.verification import KernelCandidate, ObligationCheck, ObservedCheck, verify_candidate


@pytest.fixture
def retained(tmp_path):
    return weather_retained.__wrapped__(tmp_path)


def prepared(retained):
    store, candidate, case, original, episode = retained
    bank = bank_for()
    bindings = bindings_for(bank)
    compilation = compile_behavior_bindings(bank, candidate.schema, bindings)
    kernel = {
        "schema": candidate.schema,
        "functions": compilation.functions,
        "catalog": original["catalog"],
        "acquisition_bindings": [],
        "evidence": {
            "behavior_bindings_id": store.put(
                "authored_behavior_bindings", [item.model_dump(mode="json") for item in bindings]
            ),
            "compilation_id": store.put(
                "actual_behavior_compilation", compilation.model_dump(mode="json")
            ),
        },
    }
    candidate = KernelCandidate(
        id="compiled-real-weather", schema=candidate.schema, functions=compilation.functions
    )
    cases = behavior_cases(
        store,
        kernel,
        bank_id=store.put("authored_behavior_bank", bank.model_dump(mode="json")),
        graph_id=case.graph_ref,
        snapshot={"receipt_ids": case.source_refs, "evidence_refs": case.source_refs},
    )
    return store, candidate, kernel, cases, bank


def test_candidate_bound_behavior_cache_and_only_affected_function_replay(retained):
    store, candidate, kernel, cases, bank = prepared(retained)
    plan = plan_evaluation(
        candidate, cases, store, materialization_context=materialization_context(store, kernel)
    )
    assert plan.fresh_case_ids == []
    assert all(item.planner_action == "not_required" for item in plan.decisions)
    baseline = execute_local_plan(plan, candidate, store)
    report = behavior_evaluation(store, baseline, bank)
    assert all(item["status"] == "passed" for item in report["checks"])
    changed = deepcopy(candidate.functions)
    aggregate = next(
        item for item in changed if item["steps"][-1]["operator"] == "aggregate_values"
    )
    aggregate["steps"][-1]["args"]["request"]["operation"] = "min"
    child = candidate.model_copy(
        update={"id": "mutated", "functions": changed, "parent_id": candidate.id}
    )
    next_plan = plan_evaluation(
        child,
        cases,
        store,
        previous_receipts=baseline.case_receipt_refs,
        materialization_context=materialization_context(store, kernel),
    )
    assert sum(item.local_action == "replay" for item in next_plan.decisions) == 1
    assert all(item.local_action in {"replay", "reuse"} for item in next_plan.decisions)
    current = execute_local_plan(next_plan, child, store)
    new_report = behavior_evaluation(store, current, bank)
    comparison = compare_behavior_evaluations(
        report, new_report, {item.behavior_id for item in bank.behaviors}
    )
    assert len(comparison["regressions"]) == 1
    assert comparison["incomplete"] == []


def test_unknown_or_deferred_behavior_retains_the_whole_frozen_denominator(retained):
    store, candidate, kernel, cases, bank = prepared(retained)
    empty = EvaluationReceipt(
        candidate_id=candidate.id,
        plan_sha256="no-execution",
        case_receipt_refs={},
        deferred_case_ids=[case.case_id for case in cases],
        known_regression_case_ids=[],
        bank_comparable=True,
    )
    report = behavior_evaluation(store, empty, bank)
    assert len(report["checks"]) == len(bank.behaviors)
    assert all(item["status"] == "unknown" for item in report["checks"])
    assert (
        sum(group["total"] for group in report["behavior_coverage_by_group"].values())
        == sum(item.mandatory for item in bank.behaviors) * bank.parameter_strata
    )
    assert all(
        group["passed"] == 0 and group["unknown"] == group["total"]
        for group in report["behavior_coverage_by_group"].values()
    )


def test_changed_mapping_cannot_pass_by_changing_its_own_reference(retained):
    store, candidate, kernel, cases, bank = prepared(retained)
    first = execute_local_plan(plan_evaluation(candidate, cases, store), candidate, store)
    original = behavior_evaluation(store, first, bank)
    bindings = bindings_for(bank, high="low_temperature")
    compilation = compile_behavior_bindings(bank, candidate.schema, bindings)
    other = {
        **kernel,
        "functions": compilation.functions,
        "evidence": {
            **kernel["evidence"],
            "behavior_bindings_id": store.put(
                "changed_authored_mapping", [item.model_dump(mode="json") for item in bindings]
            ),
        },
    }
    child = candidate.model_copy(
        update={"id": "changed-mapping", "functions": compilation.functions}
    )
    changed_cases = behavior_cases(
        store,
        other,
        bank_id=store.get(cases[0].behavior_input_ref)["bank_id"],
        graph_id=cases[0].graph_ref,
        snapshot={"evidence_refs": cases[0].source_refs, "receipt_ids": cases[0].source_refs},
    )
    second = execute_local_plan(plan_evaluation(child, changed_cases, store), child, store)
    generated = behavior_evaluation(store, second, bank)
    assert all(item["status"] == "passed" for item in generated["checks"])
    comparison = compare_behavior_evaluations(
        original, generated, {item.behavior_id for item in bank.behaviors}
    )
    assert comparison["regressions"] == []
    assert comparison["preservation_differences"]
    assert comparison["incomplete"]


def test_verifier_executes_behavior_input_instead_of_trusting_proposed_status(retained):
    store, candidate, kernel, cases, bank = prepared(retained)
    payload = store.get(cases[0].behavior_input_ref)
    payload.update(candidate_id=candidate.id, status="passed")
    evidence_ref = store.put("authored_evaluation_inputs", payload)
    obligation_id = bank.behaviors[0].obligation_ids[0]
    report = verify_candidate(
        candidate,
        [
            ObligationCheck(
                id=obligation_id,
                group="composition",
                function_names=[function["name"] for function in candidate.functions],
            )
        ],
        [
            ObservedCheck(
                obligation_id=obligation_id,
                dimension="behavior",
                evidence_ref=evidence_ref,
                evaluator_id="generated_behavior_v1",
            )
        ],
        store=store,
    )
    actual = next(item for item in report.checks if item.dimension == "behavior")
    assert actual.status == "passed"
    assert actual.details["independent"] is False
    assert report.target_met is False
    assert report.coverage_by_group["composition"]["passed"] == 0
    assert len(actual.details["checks"]) == len(bank.behaviors)


def test_real_materialization_completion_updates_actual_receipt(retained):
    from oak.materialization import derive_demand, slice_graph
    from oak.selective_evaluation import record_local_result, refresh_evaluation_receipt

    store, candidate, case, _, _ = retained
    original = plan_evaluation(
        candidate, [case], store, max_fresh_cases=0, materialization_context={"binding": "original"}
    )
    previous = execute_local_plan(original, candidate, store)
    changed = plan_evaluation(
        candidate,
        [case],
        store,
        previous_receipts=previous.case_receipt_refs,
        max_fresh_cases=0,
        materialization_context={"binding": "scoped"},
    )
    assert changed.decisions[0].local_action == "rematerialize"
    pending = execute_local_plan(changed, candidate, store)
    demand = derive_demand(candidate.schema, candidate.functions[1], {})
    graph = slice_graph(candidate.schema, store.get(case.graph_ref), demand)
    graph_ref = store.put("actual_retained_projection", graph)
    run = store.create_run("retained-materialization-check", "verification", {})
    stage = store.event(
        run,
        "retained_graph_projection",
        "completed",
        "Actual deterministic projection of retained weather evidence",
        {
            "input_graph_ref": case.graph_ref,
            "graph_ref": graph_ref,
            "demand": demand.model_dump(mode="json"),
        },
    )
    evidence = store.put(
        "materialization_evidence",
        {
            "candidate_id": candidate.id,
            "graph_ref": graph_ref,
            "source_refs": case.source_refs,
            "stage_evidence_refs": [stage],
        },
    )
    pending.case_receipt_refs[case.case_id] = record_local_result(
        changed,
        case.case_id,
        candidate,
        store,
        graph_ref=graph_ref,
        materialization_evidence_ref=evidence,
    )
    actual = store.get(pending.case_receipt_refs[case.case_id])
    assert actual["status"] == "passed"
    assert actual["results"][0]["value"] == 3
    assert actual["task_assessment"] == "not_checked"
    assert actual["evaluated_case_ref"]
    assert refresh_evaluation_receipt(pending, store).known_regression_case_ids == []
    from oak.construction_campaign import adopt_evaluated_cases

    tracked = {case.case_id: case.model_copy(update={"counterexample": True})}
    adopt_evaluated_cases(store, tracked, pending.case_receipt_refs)
    assert tracked[case.case_id].graph_ref == graph_ref
    assert tracked[case.case_id].calls[0].graph_ref == graph_ref
    assert tracked[case.case_id].counterexample is True
    again = plan_evaluation(
        candidate,
        list(tracked.values()),
        store,
        previous_receipts=pending.case_receipt_refs,
        max_fresh_cases=0,
        materialization_context={"binding": "scoped"},
    )
    assert again.decisions[0].local_action == "reuse"
    wrong = store.put(
        "wrong_materialization_reference",
        {
            "candidate_id": candidate.id,
            "graph_ref": graph_ref,
            "source_refs": [],
            "stage_evidence_refs": [stage],
        },
    )
    with pytest.raises(ValueError, match="same retained"):
        record_local_result(
            changed,
            case.case_id,
            candidate,
            store,
            graph_ref=graph_ref,
            materialization_evidence_ref=wrong,
        )


def test_rematerialization_keeps_each_calls_actual_native_source_scope(retained):
    from oak.construction_campaign import prepare_replay_materializations
    from oak.materialization import freeze_acquisition_binding
    from oak.selective_evaluation import EvaluationCase, ReplayCall

    store, candidate, case, original, _ = retained
    first_ref = case.source_refs[0]
    first = store.get(first_ref)
    second_ref = next(
        row["artifact_id"]
        for row in store.rows(
            "SELECT artifact_id FROM events WHERE stage='mcp_call' AND status='completed'"
        )
        if (receipt := store.get(row["artifact_id"])).get("contract_id") == first["contract_id"]
        and receipt.get("capability_id") == first["capability_id"]
        and receipt.get("args") != first["args"]
    )
    second = store.get(second_ref)
    function = deepcopy(candidate.functions[1])
    capability = next(
        tool for tool in original["catalog"]["tools"] if tool["id"] == first["capability_id"]
    )
    function["inputs"] = {
        "type": "object",
        "properties": {"native_arguments": capability["input_schema"]},
        "required": ["native_arguments"],
        "additionalProperties": False,
    }
    binding = freeze_acquisition_binding(
        candidate.schema,
        function,
        first["capability_id"],
        {"$arg": "native_arguments"},
        original["catalog"]["tools"],
    )
    kernel = {
        "schema": candidate.schema,
        "functions": [function],
        "catalog": original["catalog"],
        "acquisition_bindings": [binding.model_dump(mode="json")],
    }
    evaluation = EvaluationCase(
        case_id="two-real-source-scopes",
        bank_version="authored",
        source_refs=[first_ref, second_ref],
        calls=[
            ReplayCall(
                function=function["name"],
                args={"native_arguments": receipt["args"]},
                source_refs=[reference],
            )
            for reference, receipt in ((first_ref, first), (second_ref, second))
        ],
    )
    requests = prepare_replay_materializations(store, kernel, evaluation, {})
    assert [item[1] for item in requests] == [[first_ref], [second_ref]]
    assert all(item[2].function_name == function["name"] for item in requests)
    mismatched = evaluation.model_copy(deep=True)
    mismatched.calls[0].source_refs = [second_ref]
    with pytest.raises(ValueError, match="frozen native"):
        prepare_replay_materializations(store, kernel, mismatched, {})
    missing = evaluation.model_copy(deep=True)
    missing.calls[1].source_refs = []
    with pytest.raises(ValueError, match="attributable"):
        prepare_replay_materializations(store, kernel, missing, {})


def test_semantic_parent_restores_exact_evaluation_inputs_across_campaigns(retained):
    from test_behavior import program

    from oak.construction_campaign import load_campaign_parent
    from oak.learning_contracts import TaskIR, TaskObligation
    from oak.selective_evaluation import EvaluationCase
    from oak.task_context import TaskSurface

    store, candidate, kernel, cases, bank = prepared(retained)
    original = retained[3]
    surface_id = original["surface_id"]
    row = store.rows("SELECT artifact_id FROM mcp_surfaces WHERE id=?", (surface_id,))[0]
    configuration = deepcopy(store.get(row["artifact_id"])["configuration"])
    # The portable export redacts local environment references. This offline
    # metadata check creates no process or connection and needs no environment.
    for server in configuration["servers"]:
        if not isinstance(server.get("env_refs"), dict):
            server["env_refs"] = {}
    surface = TaskSurface.model_validate(configuration)
    query = next(query for query in surface.queries if query.split == "construction")
    task = TaskIR(
        source_sha256="authored-contract",
        analysis_sha256="not-a-model-response",
        scope="Dated observations",
        obligations=[
            TaskObligation(
                obligation_id="obligation_0",
                case_id="authored_0",
                text="Maximum over the requested scope",
                parent_requirement_ids=[],
                derivation_rule="authored_test_contract",
                program=program(),
                group="composition",
            )
        ],
    )
    # Freeze and compile the exact authored TaskIR used by this parent, rather
    # than reusing a bank derived from the helper's different obligation text.
    from oak.behavior import build_behavior_bank

    snapshot = store.get(cases[0].behavior_input_ref)
    graph_id = cases[0].graph_ref
    bank = build_behavior_bank(task)
    bindings = bindings_for(bank)
    compilation = compile_behavior_bindings(bank, candidate.schema, bindings)
    kernel["functions"] = compilation.functions
    kernel["evidence"]["behavior_bindings_id"] = store.put(
        "authored_behavior_bindings", [item.model_dump(mode="json") for item in bindings]
    )
    kernel["evidence"]["compilation_id"] = store.put(
        "actual_behavior_compilation", compilation.model_dump(mode="json")
    )
    candidate = candidate.model_copy(update={"functions": compilation.functions})
    cases = behavior_cases(
        store,
        kernel,
        bank_id=store.put("authored_behavior_bank", bank.model_dump(mode="json")),
        graph_id=graph_id,
        snapshot=snapshot,
    )
    run = store.create_run(surface_id, "mcp_construct", {"kind": "local_compiler_component_check"})
    kernel = {
        **kernel,
        "construction_profile": "semantic_v2",
        "surface_id": surface_id,
        "run_id": run,
        "sample": {"selected_query_ids": [query.id]},
        "evidence": {
            **kernel["evidence"],
            "task_ir_id": store.put("authored_task_ir", task.model_dump(mode="json")),
            "behavior_bank_id": store.get(cases[0].behavior_input_ref)["bank_id"],
            "episodes_id": store.put("sample_episodes", []),
        },
    }
    identity = store.put("locally_compiled_kernel", kernel)
    candidate = candidate.model_copy(update={"id": identity})
    query_case = EvaluationCase(
        case_id=query.id,
        question=query.query,
        bank_version=bank.bank_id,
        graph_ref=cases[0].graph_ref,
    )
    plan = plan_evaluation(candidate, [*cases, query_case], store, max_fresh_cases=0)
    evaluated = execute_local_plan(plan, candidate, store)
    actual_report = verify_candidate(candidate, [], [], store=store)
    store.set_run(
        run,
        "completed",
        result={
            "kernel_id": identity,
            "evaluation_receipt_id": store.put(
                "selective_evaluation", evaluated.model_dump(mode="json")
            ),
            "verification_id": store.put(
                "candidate_verification", actual_report.model_dump(mode="json")
            ),
        },
    )
    resumed = load_campaign_parent(store, identity, surface_id, surface)
    assert resumed["receipts"] == evaluated.case_receipt_refs
    assert resumed["query_cases"][query.id].graph_ref == query_case.graph_ref
    assert resumed["query_cases"][query.id].split == "construction"
    assert resumed["fresh"] == {}
    assert resumed["task_ir_id"] == kernel["evidence"]["task_ir_id"]

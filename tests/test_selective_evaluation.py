"""Selective evaluation executes real DSL over the reviewed weather export."""

import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from oak.functions import execute_function
from oak.preservation import certify_preservation
from oak.selective_evaluation import (
    CaseEvaluationReceipt,
    EvaluationCase,
    ReplayCall,
    build_dependency_manifest,
    cases_from_episode,
    execute_local_plan,
    plan_evaluation,
    record_fresh_result,
)
from oak.store import Store
from oak.verification import KernelCandidate

EPISODE = "697f6356e475e850faee6abc4ca3b70e520f36df9c2fe1d5f235c0dd2a0b51ea"
FIXTURE = Path(__file__).parent / "fixtures/observer/weather"


@pytest.fixture
def retained(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "weather")
    store = Store(tmp_path / "weather")
    episode = store.get(EPISODE)
    original = store.get(episode["kernel_revision"])
    graph = store.get(episode["graph_id"])
    rows = {
        "name": "forecast_rows",
        "description": "Read retained daily forecasts.",
        "inputs": {"type": "object", "properties": {}, "additionalProperties": False},
        "output_schema": {"type": "array"},
        "steps": [
            {
                "id": "rows",
                "operator": "lookup_entities",
                "args": {"entity_types": ["DailyForecast"]},
            }
        ],
        "result": {"$step": "rows"},
    }
    count = deepcopy(rows)
    count.update(
        name="forecast_count", output_schema={"type": "integer"}, result={"$step": "count"}
    )
    count["steps"].append(
        {
            "id": "count",
            "operator": "aggregate_values",
            "args": {"items": {"$step": "rows"}, "request": {"operation": "count"}},
        }
    )
    candidate = KernelCandidate(
        id="pure-retained-weather", schema=original["schema"], functions=[rows, count]
    )
    execution = execute_function(
        graph, candidate.functions, "forecast_count", {}, schema=candidate.schema
    )
    case = EvaluationCase(
        case_id="retained-count",
        question="How many daily forecast records are retained?",
        bank_version="bank-v1",
        graph_ref=episode["graph_id"],
        source_refs=episode["observations"][0]["receipt_ids"],
        calls=[
            ReplayCall(
                function="forecast_count",
                args={},
                execution_ref=store.put("actual_test_execution", execution),
            )
        ],
        estimated_fresh_cost=0.05,
    )
    return store, candidate, case, original, episode


def baseline(store, candidate, case, **kwargs):
    plan = plan_evaluation(
        candidate,
        [case],
        store,
        max_fresh_cases=0,
        planner_context={"prompt": "frozen test context"},
        **kwargs,
    )
    receipt = execute_local_plan(plan, candidate, store)
    return receipt.case_receipt_refs


def test_real_replay_then_exact_cache_keeps_assessment_unknown(retained):
    store, candidate, case, _, _ = retained
    previous = baseline(store, candidate, case)
    first = store.get(previous[case.case_id])
    assert first["status"] == "passed"
    assert first["results"][0]["value"] == 3
    assert first["task_assessment"] == "not_checked"
    child = candidate.model_copy(update={"id": "child", "parent_id": candidate.id})
    plan = plan_evaluation(
        child,
        [case],
        store,
        previous_receipts=previous,
        planner_context={"prompt": "frozen test context"},
        max_fresh_cases=0,
    )
    assert plan.decisions[0].local_action == "reuse"
    result = execute_local_plan(plan, child, store)
    receipt = store.get(result.case_receipt_refs[case.case_id])
    assert receipt["status"] == "passed"
    assert receipt["source_candidate_id"] == candidate.id
    assert receipt["fresh_candidate_id"] is None


def test_entire_population_not_only_observed_node_ids_invalidates_cache(retained):
    store, candidate, case, _, _ = retained
    previous = baseline(store, candidate, case)
    graph = store.get(case.graph_ref)
    excluded = next(node["id"] for node in graph["nodes"] if node["type"] == "DailyForecast")
    # A derivative slice of genuine retained evidence, with its own artifact ID.
    partial = {
        **graph,
        "nodes": [n for n in graph["nodes"] if n["id"] != excluded],
        "edges": [e for e in graph["edges"] if e["source"] != excluded and e["target"] != excluded],
    }
    smaller = case.model_copy(update={"graph_ref": store.put("retained_partial_graph", partial)})
    plan = plan_evaluation(
        candidate, [smaller], store, previous_receipts=previous, max_fresh_cases=0
    )
    assert plan.decisions[0].local_action == "replay"
    result = execute_local_plan(plan, candidate, store)
    receipt = store.get(result.case_receipt_refs[case.case_id])
    assert receipt["results"][0]["value"] == 2
    assert receipt["results"][0]["comparison"] == "incompatible_reference"
    assert receipt["task_assessment"] == "not_checked"


def test_changed_result_is_preservation_difference_not_task_failure(retained):
    store, candidate, case, _, _ = retained
    previous = baseline(store, candidate, case)
    changed = deepcopy(candidate.functions)
    changed[1]["steps"][-1]["args"]["request"] = {"operation": "max", "field": "high_temperature"}
    child = candidate.model_copy(
        update={"id": "maximum", "parent_id": candidate.id, "functions": changed}
    )
    plan = plan_evaluation(child, [case], store, previous_receipts=previous, max_fresh_cases=0)
    result = execute_local_plan(plan, child, store)
    receipt = store.get(result.case_receipt_refs[case.case_id])
    assert receipt["status"] == "passed"
    assert receipt["results"][0]["value"] == 9
    assert result.preservation_difference_case_ids == [case.case_id]
    assert result.known_regression_case_ids == []
    assert receipt["task_assessment"] == "not_checked"


def test_source_binding_and_schema_identity_changes_require_rematerialization(retained):
    store, candidate, case, _, _ = retained
    previous = baseline(store, candidate, case, materialization_context={"binding": "one"})
    plan = plan_evaluation(
        candidate,
        [case],
        store,
        previous_receipts=previous,
        materialization_context={"binding": "two"},
        max_fresh_cases=0,
    )
    assert plan.decisions[0].local_action == "rematerialize"
    result = execute_local_plan(plan, candidate, store)
    assert store.get(result.case_receipt_refs[case.case_id])["status"] == "unknown"
    schema = deepcopy(candidate.schema)
    schema["entity_types"]["DailyForecast"]["properties"]["temperature_unit"]["description"] = (
        "Different interpretation requires reevaluation"
    )
    child = candidate.model_copy(update={"id": "new-units", "schema": schema})
    plan = plan_evaluation(child, [case], store, previous_receipts=previous, max_fresh_cases=0)
    assert plan.decisions[0].local_action == "rematerialize"


def test_full_catalog_change_selects_at_most_one_planner_only_sentinel(retained):
    store, candidate, case, _, _ = retained
    cases = [case.model_copy(update={"case_id": f"check-{index}"}) for index in range(5)]
    initial = plan_evaluation(candidate, cases, store, max_fresh_cases=0)
    previous = execute_local_plan(initial, candidate, store).case_receipt_refs
    extra = deepcopy(candidate.functions[0])
    extra["name"] = "other_catalog_entry"
    child = candidate.model_copy(
        update={"id": "expanded", "functions": [*candidate.functions, extra]}
    )
    plan = plan_evaluation(
        child,
        cases,
        store,
        previous_receipts=previous,
        planner_context={"prompt": "complete context"},
    )
    assert all(item.local_action == "reuse" for item in plan.decisions)
    assert len(plan.fresh_case_ids) == 1
    assert sum(item.planner_sentinel for item in plan.decisions) == 1
    assert sum(item.planner_action == "defer" for item in plan.decisions) == 4


def test_deterministic_fresh_priority_bounds_and_budget(retained):
    store, candidate, case, _, _ = retained
    cases = [
        case.model_copy(update={"case_id": f"case-{i}", "counterexample": i == 0, "is_new": i == 1})
        for i in range(7)
    ]
    plan = plan_evaluation(candidate, cases, store, fresh_budget=0.15)
    assert len(plan.fresh_case_ids) <= 3
    assert {"case-0", "case-1"}.issubset(plan.fresh_case_ids)
    assert (
        plan.fresh_case_ids
        == plan_evaluation(
            candidate, list(reversed(cases)), store, fresh_budget=0.15
        ).fresh_case_ids
    )
    zero = plan_evaluation(candidate, cases, store, fresh_budget=0)
    assert not zero.fresh_case_ids
    unknown = [c.model_copy(update={"estimated_fresh_cost": None}) for c in cases]
    assert len(plan_evaluation(candidate, unknown, store).fresh_case_ids) == 1
    with pytest.raises(ValueError, match="three"):
        plan_evaluation(candidate, cases, store, max_fresh_cases=4)


def test_effectful_retained_episode_never_replays_cached_mcp(retained):
    store, _, _, original, episode = retained
    candidate = KernelCandidate(
        id=episode["kernel_revision"], schema=original["schema"], functions=original["functions"]
    )
    case = cases_from_episode(store, EPISODE, bank_version="real-weather")
    assert case.calls[0].args["min_high_temperature"] == 10
    manifest = build_dependency_manifest(candidate, case, store)
    assert manifest.computation.completeness == "unknown"
    plan = plan_evaluation(candidate, [case], store, max_fresh_cases=0)
    assert plan.decisions[0].local_action == "defer"
    result = execute_local_plan(plan, candidate, store)
    assert store.get(result.case_receipt_refs[case.case_id])["status"] == "unknown"


def test_bank_change_invalidates_comparison_without_old_react_claim(retained):
    store, candidate, case, _, _ = retained
    previous = baseline(store, candidate, case)
    changed = case.model_copy(update={"bank_version": "bank-v2"})
    plan = plan_evaluation(
        candidate, [changed], store, previous_receipts=previous, max_fresh_cases=0
    )
    assert not plan.bank_comparable
    assert plan.decisions[0].local_action == "replay"
    result = execute_local_plan(plan, candidate, store)
    assert store.get(result.case_receipt_refs[case.case_id])["fresh_episode_ref"] is None


def test_missing_scope_cannot_reuse_and_heldout_rejected(retained):
    store, candidate, case, _, _ = retained
    empty = case.model_copy(update={"calls": [], "graph_ref": None})
    first = plan_evaluation(candidate, [empty], store, max_fresh_cases=0)
    previous = execute_local_plan(first, candidate, store).case_receipt_refs
    next_plan = plan_evaluation(
        candidate, [empty], store, previous_receipts=previous, max_fresh_cases=0
    )
    assert next_plan.decisions[0].local_action == "defer"
    with pytest.raises(ValueError):
        EvaluationCase(case_id="heldout", split="heldout", bank_version="v1")


def test_actual_fresh_episode_attribution_and_not_automatic_pass(retained):
    store, _, _, original, episode = retained
    candidate = KernelCandidate(
        id=episode["kernel_revision"], schema=original["schema"], functions=original["functions"]
    )
    case = cases_from_episode(store, EPISODE, bank_version="real-weather")
    plan = plan_evaluation(candidate, [case], store, max_fresh_cases=0)
    receipt = execute_local_plan(plan, candidate, store)
    identity = record_fresh_result(receipt.case_receipt_refs[case.case_id], EPISODE, store)
    result = CaseEvaluationReceipt.model_validate(store.get(identity))
    assert result.agent_outcome == "complete"
    assert result.status == "unknown"
    assert result.task_assessment == "not_checked"
    assert result.fresh_candidate_id == candidate.id
    child = candidate.model_copy(update={"id": "deferred-child", "parent_id": candidate.id})
    next_plan = plan_evaluation(
        child, [case], store, previous_receipts={case.case_id: identity}, max_fresh_cases=0
    )
    next_receipt = execute_local_plan(next_plan, child, store)
    deferred = CaseEvaluationReceipt.model_validate(
        store.get(next_receipt.case_receipt_refs[case.case_id])
    )
    assert deferred.fresh_episode_ref is None
    assert deferred.agent_outcome is None
    assert deferred.task_assessment == "not_checked"
    assert deferred.historical_agent_evidence.episode_ref == EPISODE
    assert deferred.historical_agent_evidence.candidate_id == candidate.id
    assert deferred.historical_agent_evidence.agent_outcome == "complete"
    with pytest.raises(ValueError, match="candidate and case"):
        other = result.model_copy(update={"candidate_id": "different"})
        record_fresh_result(
            store.put("wrong_receipt", other.model_dump(mode="json")), EPISODE, store
        )


def test_real_lean_alpha_preservation_transfers_only_same_graph(retained):
    store, candidate, case, _, _ = retained
    previous = baseline(store, candidate, case)
    cached_parent = candidate.model_copy(update={"id": "cached-parent", "parent_id": candidate.id})
    cached_plan = plan_evaluation(
        cached_parent, [case], store, previous_receipts=previous, max_fresh_cases=0
    )
    assert cached_plan.decisions[0].local_action == "reuse"
    previous = execute_local_plan(cached_plan, cached_parent, store).case_receipt_refs
    renamed = deepcopy(candidate.functions)
    renamed[1]["steps"][-1]["id"] = "total"
    renamed[1]["result"] = {"$step": "total"}
    child = candidate.model_copy(
        update={"id": "alpha", "parent_id": cached_parent.id, "functions": renamed}
    )
    certificate = certify_preservation(cached_parent, child, ["forecast_count"])
    if certificate.status != "certified":
        pytest.skip(certificate.summary)
    plan = plan_evaluation(
        child,
        [case],
        store,
        previous_receipts=previous,
        parent=cached_parent,
        certificate=certificate,
        max_fresh_cases=0,
    )
    assert plan.decisions[0].local_action == "proof"
    result = execute_local_plan(plan, child, store, parent=cached_parent, certificate=certificate)
    actual = store.get(result.case_receipt_refs[case.case_id])
    assert actual["status"] == "passed"
    assert actual["source_candidate_id"] == candidate.id


@pytest.mark.parametrize("changed_basis", ["graph", "materialization"])
def test_changed_observation_basis_keeps_actual_agent_result_historical(retained, changed_basis):
    """A genuine saved weather episode cannot become a new agent success."""
    from oak.materialization import MATERIALIZATION_VERSION, derive_demand

    store, _, _, original, episode = retained
    candidate = KernelCandidate(
        id=episode["kernel_revision"], schema=original["schema"], functions=original["functions"]
    )
    case = cases_from_episode(store, EPISODE, bank_version="retained-weather")
    context = {
        "base_prompt_sha256": episode["base_prompt_sha256"],
        "runtime_prompt_sha256": episode["runtime_prompt_sha256"],
        "catalog": original["catalog"],
    }
    initial_plan = plan_evaluation(
        candidate, [case], store, planner_context=context, max_fresh_cases=0
    )
    initial = execute_local_plan(initial_plan, candidate, store)
    reference = record_fresh_result(initial.case_receipt_refs[case.case_id], EPISODE, store)
    updated = case.model_copy(deep=True)
    if changed_basis == "graph":
        graph = store.get(case.graph_ref)
        excluded = next(node["id"] for node in graph["nodes"] if node["type"] == "DailyForecast")
        partial = {
            **graph,
            "nodes": [node for node in graph["nodes"] if node["id"] != excluded],
            "edges": [
                edge
                for edge in graph["edges"]
                if edge["source"] != excluded and edge["target"] != excluded
            ],
        }
        updated.graph_ref = store.put("actual_retained_weather_slice", partial)
        updated.calls[0].graph_ref = updated.graph_ref
    else:
        function = next(
            item for item in candidate.functions if item["name"] == case.calls[0].function
        )
        updated.extractor_version = MATERIALIZATION_VERSION
        updated.demand_ref = store.put(
            "actual_derived_demand",
            derive_demand(candidate.schema, function, case.calls[0].args).model_dump(mode="json"),
        )
    before = store.rows("SELECT * FROM model_calls")
    for cap, expected in ((1, "fresh"), (0, "defer")):
        plan = plan_evaluation(
            candidate,
            [updated],
            store,
            previous_receipts={case.case_id: reference},
            planner_context=context,
            max_fresh_cases=cap,
        )
        decision = plan.decisions[0]
        assert decision.manifest.planner == initial_plan.decisions[0].manifest.planner
        assert decision.planner_action == expected
        result = execute_local_plan(plan, candidate, store)
        actual = CaseEvaluationReceipt.model_validate(
            store.get(result.case_receipt_refs[case.case_id])
        )
        assert actual.fresh_episode_ref is None
        assert actual.agent_outcome is None
        assert actual.task_assessment == "not_checked"
        assert actual.historical_agent_evidence.episode_ref == EPISODE
        assert actual.historical_agent_evidence.candidate_id == candidate.id
        assert actual.historical_agent_evidence.agent_outcome == episode["status"]
    assert store.rows("SELECT * FROM model_calls") == before


def test_generated_check_is_candidate_bound_and_reused_by_exact_bank(retained):
    store, candidate, case, _, _ = retained
    specification = {
        "id": "rows-v-count",
        "obligation_id": "count",
        "description": "Compare the actual candidate count with its real record listing.",
        "left": {"function": "forecast_rows"},
        "relation": "length_equals",
        "right": {"function": "forecast_count"},
    }
    check_case = case.model_copy(
        update={
            "calls": [],
            "generated_check_refs": [store.put("generated_specification", specification)],
        }
    )
    previous = baseline(store, candidate, check_case)
    saved = store.get(previous[case.case_id])
    assert saved["status"] == "passed"
    assert saved["results"][0]["contributes_to_learning"]
    assert saved["results"][0]["independent"] is False
    plan = plan_evaluation(
        candidate, [check_case], store, previous_receipts=previous, max_fresh_cases=0
    )
    assert plan.decisions[0].local_action == "reuse"


def test_real_api_separates_reused_local_evidence_from_deferred_agent_evaluation(retained):
    """HTTP reads expose actual local execution receipts without launching inference."""
    from fastapi.testclient import TestClient

    from oak.api import create_app

    store, candidate, case, original, _ = retained
    previous = baseline(store, candidate, case)
    child = candidate.model_copy(update={"id": "api-child", "parent_id": candidate.id})
    plan = plan_evaluation(
        child,
        [case],
        store,
        previous_receipts=previous,
        planner_context={"prompt": "frozen test context"},
        max_fresh_cases=0,
    )
    receipt = execute_local_plan(plan, child, store)
    run_id = store.create_run(
        original["surface_id"], "local_verification", {"candidate_id": child.id}
    )
    plan_ref = store.put("evaluation_plan", plan.model_dump(mode="json"))
    receipt_ref = store.put("selective_evaluation", receipt.model_dump(mode="json"))
    store.event(
        run_id,
        "evaluation_plan",
        "completed",
        "Recorded actual local evaluation decisions",
        {
            "flow": "verification",
            "kernel_id": child.id,
            "evaluation_plan_id": plan_ref,
            **plan.model_dump(mode="json"),
        },
    )
    store.event(
        run_id,
        "selective_evaluation",
        "completed",
        "Recorded actual reused computation evidence",
        {
            "flow": "verification",
            "kernel_id": child.id,
            "evaluation_receipt_id": receipt_ref,
            **receipt.model_dump(mode="json"),
        },
    )
    store.set_run(run_id, "completed", result={"evaluation_receipt_id": receipt_ref})
    before = store.rows("SELECT * FROM model_calls")
    with TestClient(create_app(store.root), base_url="http://127.0.0.1:8501") as client:
        response = client.get(f"/api/v1/runs/{run_id}/events")
        assert response.status_code == 200, response.text
        events = response.json()["items"]
        decision = next(event for event in events if event["stage"] == "evaluation_plan")
        evaluated = next(event for event in events if event["stage"] == "selective_evaluation")
        assert decision["type"] == evaluated["type"] == "validation.recorded"
        assert decision["flow_evidence"]["action_counts"] == {"reuse": 1}
        assert decision["flow_evidence"]["planner_counts"] == {"defer": 1}
        actual = evaluated["flow_evidence"]["actions"][0]
        assert actual["status"] == "passed"
        assert actual["source_candidate_id"] == candidate.id
        assert actual["fresh_candidate_id"] is None
        assert actual["task_assessment"] == "not_checked"
        assert actual["planner_action"] == "deferred"
        assert (
            client.get(f"/api/v1/artifacts/{plan_ref}").json()["typed_data"]["candidate_id"]
            == child.id
        )
        case_ref = receipt.case_receipt_refs[case.case_id]
        receipt_view = client.get(f"/api/v1/artifacts/{receipt_ref}").json()
        assert receipt_view["kind"] == "selective_evaluation"
        assert receipt_view["typed_data"]["case_receipt_refs"] == receipt.case_receipt_refs
        assert client.get(f"/api/v1/artifacts/{case_ref}").json()["typed_data"]["action"] == "reuse"
    assert store.rows("SELECT * FROM model_calls") == before


@pytest.mark.parametrize("expand_between_reads", [False, True])
def test_actual_lazy_materialization_recognizes_only_one_stable_input_graph(
    retained, expand_between_reads
):
    """Real local replay evidence, with no provider or MCP execution simulated."""
    from oak.preservation import digest

    store, candidate, case, _, _ = retained
    retained_graph = store.get(case.graph_ref)
    graph = {"nodes": [], "edges": []}
    function = deepcopy(candidate.functions[1])
    function["description"] = "Count genuine retained daily forecasts reported in °C."
    if expand_between_reads:
        function["steps"].insert(
            1,
            {
                "id": "second_read",
                "operator": "lookup_entities",
                "args": {"entity_types": ["DailyForecast"]},
            },
        )
        function["steps"][-1]["args"]["items"] = {"$step": "second_read"}

    def materialize(*, step_id, **_):
        if step_id == "rows":
            source = deepcopy(retained_graph)
            if expand_between_reads:
                removed = next(
                    node["id"] for node in source["nodes"] if node["type"] == "DailyForecast"
                )
                source["nodes"] = [node for node in source["nodes"] if node["id"] != removed]
                source["edges"] = [
                    edge
                    for edge in source["edges"]
                    if edge["source"] != removed and edge["target"] != removed
                ]
            graph.clear()
            graph.update(source)
        elif step_id == "second_read":
            graph.clear()
            graph.update(deepcopy(retained_graph))

    execution = execute_function(
        graph, [function], function["name"], {}, schema=candidate.schema, before_step=materialize
    )
    assert execution["value"] == 3
    assert execution["dependencies"]["graph_sha256"] != digest(graph)
    kernel_id = store.put(
        "locally_authored_kernel", {"schema": candidate.schema, "functions": [function]}
    )
    graph_id = store.put("actual_local_working_graph", graph)
    execution_id = store.put("actual_local_function_execution", execution)
    # This manifest packages actual local executions. It does not claim a model
    # answer, MCP call, or independent task assessment.
    episode_id = store.put(
        "local_execution_manifest",
        {
            "query_id": "retained-local-count",
            "query": "Count retained weather records",
            "split": "construction",
            "kernel_revision": kernel_id,
            "graph_id": graph_id,
            "citations": ["observation-1"],
            "trajectory": [{"action": "call", "function": function["name"], "args": {}}],
            "observations": [
                {
                    "id": "observation-1",
                    "status": "completed",
                    "function": function["name"],
                    "execution_id": execution_id,
                    "working_graph_id": graph_id,
                }
            ],
        },
    )
    normalized = cases_from_episode(store, episode_id, bank_version="local-evidence")
    assert normalized.calls[0].input_graph_known is not expand_between_reads
    current = KernelCandidate(id=kernel_id, schema=candidate.schema, functions=[function])
    plan = plan_evaluation(current, [normalized], store, max_fresh_cases=0)
    assert plan.decisions[0].local_action == ("defer" if expand_between_reads else "replay")
    if not expand_between_reads:
        result = execute_local_plan(plan, current, store)
        saved = store.get(result.case_receipt_refs[normalized.case_id])
        assert saved["status"] == "passed"
        assert saved["results"][0]["value"] == execution["value"]
        assert saved["results"][0]["comparison"] == "equal"

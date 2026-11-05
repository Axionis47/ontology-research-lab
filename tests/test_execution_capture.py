"""Capture actual function boundaries over genuine retained weather evidence."""

from copy import deepcopy

import pytest
from test_selective_evaluation import retained as weather_retained

from oak.bootstrap import empty_graph
from oak.functions import FunctionExecutionError, execute_function
from oak.preservation import runtime_dependencies
from oak.store import canonical


@pytest.fixture
def retained(tmp_path):
    return weather_retained.__wrapped__(tmp_path)


def test_capture_reconstructs_materialized_inputs_before_real_operators(retained):
    store, candidate, case, _, _ = retained
    source = store.get(case.graph_ref)
    working = empty_graph()
    calls_before = store.rows("SELECT id FROM model_calls ORDER BY id")

    def materialize(*, step_id, operator, arguments, step_outputs):
        if step_id == "rows":
            working.clear()
            working.update(deepcopy(source))

    actual = execute_function(
        working,
        candidate.functions,
        "forecast_count",
        {},
        schema=candidate.schema,
        before_step=materialize,
        artifact_store=store,
    )
    capture = store.get(actual["capture_id"])
    assert capture["status"] == "completed"
    assert capture["value"] == sum(node["type"] == "DailyForecast" for node in source["nodes"])
    assert store.get(capture["initial_graph_ref"])["nodes"] == []
    assert store.get(capture["steps"][0]["before_materialization_graph_ref"])["nodes"] == []
    assert store.get(capture["steps"][0]["input_graph_ref"]) == source
    assert store.get(capture["steps"][0]["graph_after_ref"]) == source
    assert store.get(capture["final_graph_ref"]) == source
    assert (
        store.get(capture["input_manifest_ref"])["initial_graph_ref"]
        == capture["initial_graph_ref"]
    )
    functions = store.get(capture["functions_ref"])
    assert functions[1]["steps"][1]["args"]["items"] == {"$step": "rows"}
    replayed = execute_function(
        store.get(capture["steps"][0]["input_graph_ref"]),
        functions,
        capture["function"],
        capture["args"],
        schema=store.get(capture["schema_ref"]),
    )
    assert type(replayed["value"]) is type(capture["value"])
    assert replayed["value"] == capture["value"]
    assert capture["runtime_dependencies"] == {
        key: value
        for key, value in runtime_dependencies().items()
        if key in {"operators", "executor", "ontology", "runtime_lock"}
    }
    assert store.rows("SELECT id FROM model_calls ORDER BY id") == calls_before


def test_capture_is_immutable_when_callers_mutate_graph_and_catalog(retained):
    store, candidate, case, _, _ = retained
    graph = store.get(case.graph_ref)
    catalog = deepcopy(candidate.functions)
    result = execute_function(
        graph, catalog, "forecast_count", {}, schema=candidate.schema, artifact_store=store
    )
    original = canonical(store.get(result["capture_id"]))
    graph["nodes"].clear()
    catalog[1]["steps"][-1]["args"]["request"]["operation"] = "min"
    result["steps"].clear()
    assert canonical(store.get(result["capture_id"])) == original
    saved = store.get(result["capture_id"])
    assert store.get(saved["initial_graph_ref"])["nodes"]
    assert store.get(saved["functions_ref"])[1]["steps"][-1]["args"]["request"] == {
        "operation": "count"
    }


def test_failed_output_contract_retains_real_executed_steps_and_graphs(retained):
    store, candidate, case, _, _ = retained
    catalog = deepcopy(candidate.functions)
    catalog[1]["output_schema"] = {"type": "string"}
    with pytest.raises(FunctionExecutionError, match="output contract") as failure:
        execute_function(
            store.get(case.graph_ref),
            catalog,
            "forecast_count",
            {},
            schema=candidate.schema,
            artifact_store=store,
        )
    capture = store.get(failure.value.capture_id)
    assert capture["status"] == "failed"
    assert "ValidationError" in capture["error"]
    assert "value" not in capture
    assert capture["steps"][-1]["status"] == "completed"
    assert capture["steps"][-1]["output"] == 3
    assert store.get(capture["steps"][-1]["input_graph_ref"])["nodes"]


def test_pre_execution_validation_failure_has_attributable_capture(retained):
    store, candidate, case, _, _ = retained
    with pytest.raises(FunctionExecutionError, match="absent") as failure:
        execute_function(
            store.get(case.graph_ref),
            candidate.functions,
            "missing_function",
            {},
            schema=candidate.schema,
            artifact_store=store,
        )
    capture = store.get(failure.value.capture_id)
    assert capture["status"] == "failed"
    assert capture["function"] == "missing_function"
    assert capture["steps"] == []
    assert store.get(capture["initial_graph_ref"]) == store.get(capture["final_graph_ref"])

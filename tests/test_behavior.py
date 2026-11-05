"""Reusable semantic behaviors over genuine retained weather and Coffee graphs.

Programs are explicitly authored compiler inputs or labelled faulty code
mutations. They are not fabricated model responses or benchmark observations.
The retained artifact hashes and source data remain unchanged.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from oak.behavior import (
    AcquisitionTemplate,
    BehaviorBinding,
    build_behavior_bank,
    compile_behavior_bindings,
    evaluate_behavior_bank,
    make_behavior_inputs,
    replay_behavior_evaluation,
)
from oak.behavior_reference import generated_mutants
from oak.functions import execute_function
from oak.learning import candidate_rank
from oak.learning_contracts import SemanticField, TaskIR, TaskObligation, TaskOperation, TaskProgram
from oak.materialization import prepare_bound_materialization, slice_graph
from oak.store import Store
from oak.task_semantics import domain_issues

PROJECT = Path(__file__).parents[1]
WEATHER = PROJECT / "tests/fixtures/observer/weather/artifacts"
KERNEL = "2c112be392425277cf1d469ab6c7fd4a98546c3e520452a40802d6ac43c6eaad"
GRAPH = "3d22ea885e705dc8d46186e4f3f795653a9182ab7c8142876facb99633e658da"
RECEIPT = "ae2346d6f91a7a973a986a2304a717bf6640897a675aec3a655233e25bf43cd6"
COFFEE = "0c7e58d98071595d62bb8f8276de18b96fbb6c76e520c3344e305ef46d95a431"


def artifact(root, identity):
    path = root / f"{identity}.json"
    if not path.exists():
        pytest.skip("Genuine retained artifact unavailable in this checkout")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == identity
    return json.loads(raw)["data"]


def program():
    return TaskProgram(
        fields=[
            SemanticField(
                id="date",
                description="Observation date",
                value_type="date",
                grain="daily observation",
                role="selector",
            ),
            SemanticField(
                id="high",
                description="Daily high value",
                value_type="number",
                unit="native",
                grain="daily observation",
            ),
        ],
        operations=[
            TaskOperation(
                id="records", operator="read", fields=["date", "high"], result_kind="records"
            ),
            TaskOperation(
                id="highest",
                operator="aggregate",
                inputs=["records"],
                fields=["high"],
                result_kind="scalar",
                parameters={"operation": "max"},
            ),
        ],
        result="highest",
        observation_contract="Maximum over the requested dated population",
    )


def bank_for(task_program=None, *, duplicates=1):
    task_program = task_program or program()
    return build_behavior_bank(
        TaskIR(
            source_sha256="authored-contract",
            analysis_sha256="not-a-model-response",
            scope="Dated observations",
            obligations=[
                TaskObligation(
                    obligation_id=f"obligation_{index}",
                    case_id=f"authored_{index}",
                    text=task_program.observation_contract,
                    parent_requirement_ids=[],
                    derivation_rule="authored_test_contract",
                    program=task_program,
                    group="composition",
                )
                for index in range(duplicates)
            ],
        )
    )


def bindings_for(
    bank, *, entity_type="DailyForecast", date="date", high="high_temperature", acquisition=None
):
    return [
        BehaviorBinding(
            behavior_id=item.behavior_id,
            entity_type=entity_type,
            field_map={"date": date, "high": high},
            acquisition=acquisition,
        )
        for item in bank.behaviors
    ]


def test_semantic_bank_compiles_real_point_getters_beyond_aggregate_prefixes():
    kernel, graph = artifact(WEATHER, KERNEL), artifact(WEATHER, GRAPH)
    bank = bank_for()
    bindings = bindings_for(bank)
    result = compile_behavior_bindings(bank, kernel["schema"], bindings)
    assert result.diagnostics == []
    point = next(
        item
        for item in bank.behaviors
        if item.kind == "point" and item.projection_fields == ["high"]
    )
    binding = next(item for item in bindings if item.behavior_id == point.behavior_id)
    function = next(
        item for item in result.functions if item["name"] == "behavior_" + point.behavior_id[2:]
    )
    args = make_behavior_inputs(point, binding, kernel["schema"], graph)
    assert len(args) == 2 and args[0] != args[1]
    for argument in args:
        execution = execute_function(
            graph, result.functions, function["name"], argument, schema=kernel["schema"]
        )
        rows = [
            row
            for row in graph["nodes"]
            if row["type"] == "DailyForecast"
            and row["properties"]["date"] == argument["select_date"]
        ]
        assert [row["high_temperature"] for row in execution["value"]] == [
            row["properties"]["high_temperature"] for row in rows
        ]
    report = evaluate_behavior_bank(
        bank, kernel["schema"], result.functions, bindings, graph, evidence_refs=[GRAPH]
    )
    assert report["independent"] is False
    assert all(item["status"] == "passed" for item in report["checks"])
    assert report["mutants_executed"] <= 64
    assert any(item["detected"] for check in report["checks"] for item in check["mutations"])
    assert graph == artifact(WEATHER, GRAPH)


def test_wrong_candidate_computation_is_detected_without_mutating_the_bank_or_receipt():
    kernel, graph = artifact(WEATHER, KERNEL), artifact(WEATHER, GRAPH)
    bank, bindings = bank_for(), bindings_for(bank_for())
    compiled = compile_behavior_bindings(bank, kernel["schema"], bindings)
    wrong = deepcopy(compiled.functions)
    aggregate = next(item for item in wrong if item["steps"][-1]["operator"] == "aggregate_values")
    aggregate["steps"][-1]["args"]["request"]["operation"] = "min"
    report = evaluate_behavior_bank(bank, kernel["schema"], wrong, bindings, graph)
    defect = next(
        item for item in report["checks"] if item.get("function_name") == aggregate["name"]
    )
    assert defect["status"] == "failed"
    assert defect["strata"][0]["reference_value"] != defect["strata"][0]["execution"]["value"]
    assert report["status"] == "failed"
    assert bank == bank_for()


def test_baked_in_point_selector_and_narrowed_domain_are_measured_as_defects():
    kernel, graph = artifact(WEATHER, KERNEL), artifact(WEATHER, GRAPH)
    bank = bank_for()
    bindings = bindings_for(bank)
    compiled = compile_behavior_bindings(bank, kernel["schema"], bindings)
    point = next(
        item
        for item in bank.behaviors
        if item.kind == "point" and item.projection_fields == ["high"]
    )
    wrong = deepcopy(compiled.functions)
    function = next(item for item in wrong if item["name"] == "behavior_" + point.behavior_id[2:])
    binding = next(item for item in bindings if item.behavior_id == point.behavior_id)
    date = make_behavior_inputs(point, binding, kernel["schema"], graph)[0]["select_date"]
    function["steps"][0]["args"]["property_filters"]["date"] = date
    function["inputs"]["properties"]["select_date"]["enum"] = [date]
    report = evaluate_behavior_bank(bank, kernel["schema"], wrong, bindings, graph)
    defect = next(item for item in report["checks"] if item["behavior_id"] == point.behavior_id)
    assert defect["status"] == "failed"
    assert any("parameter does not reach result" in item["reason"] for item in report["penalties"])
    assert any("narrowed enum" in item["reason"] for item in report["penalties"])


def test_bank_and_score_ignore_repeated_questions_and_step_names():
    kernel, graph = artifact(WEATHER, KERNEL), artifact(WEATHER, GRAPH)
    bank = bank_for()
    repeated = bank_for(duplicates=3)
    assert [item.behavior_id for item in bank.behaviors] == [
        item.behavior_id for item in repeated.behaviors
    ]
    renamed = program().model_dump()
    renamed["operations"][0]["id"] = "a_different_trace_step"
    renamed["operations"][1]["inputs"] = ["a_different_trace_step"]
    assert [
        item.behavior_id for item in bank_for(TaskProgram.model_validate(renamed)).behaviors
    ] == [item.behavior_id for item in bank.behaviors]
    bindings = bindings_for(bank)
    compiled = compile_behavior_bindings(bank, kernel["schema"], bindings)
    one = evaluate_behavior_bank(bank, kernel["schema"], compiled.functions, bindings, graph)
    many = evaluate_behavior_bank(repeated, kernel["schema"], compiled.functions, bindings, graph)
    assert one["behavior_coverage_by_group"] == many["behavior_coverage_by_group"]
    selected = bank.behaviors[-1].behavior_id
    narrow = evaluate_behavior_bank(
        bank, kernel["schema"], compiled.functions, bindings, graph, behavior_ids=[selected]
    )
    assert narrow["mutation_quotas"] == one["mutation_quotas"]
    assert (
        narrow["checks"][0]["mutations"]
        == next(item for item in one["checks"] if item["behavior_id"] == selected)["mutations"]
    )


def test_point_behavior_carries_native_acquisition_and_a_smaller_graph_demand():
    kernel, graph, receipt = (
        artifact(WEATHER, KERNEL),
        artifact(WEATHER, GRAPH),
        artifact(WEATHER, RECEIPT),
    )
    bank = bank_for()
    acquisition = AcquisitionTemplate(capability_id="weather/get_forecast")
    bindings = bindings_for(bank, acquisition=acquisition)
    compiled = compile_behavior_bindings(
        bank, kernel["schema"], bindings, capabilities=kernel["catalog"]["tools"]
    )
    assert compiled.diagnostics == []
    point = next(
        item
        for item in bank.behaviors
        if item.kind == "point" and item.projection_fields == ["high"]
    )
    binding = next(item for item in bindings if item.behavior_id == point.behavior_id)
    function = next(
        item for item in compiled.functions if item["name"] == "behavior_" + point.behavior_id[2:]
    )
    arguments = make_behavior_inputs(
        point,
        binding,
        kernel["schema"],
        graph,
        receipt_arguments={acquisition.capability_id: receipt["args"]},
    )[0]
    prepared = prepare_bound_materialization(
        kernel["schema"],
        function,
        arguments,
        compiled.acquisition_bindings,
        kernel["catalog"]["tools"],
    )
    assert len(prepared.acquisitions) == 1
    assert prepared.acquisitions[0].arguments == receipt["args"]
    small = slice_graph(kernel["schema"], graph, prepared.demand)
    assert len(small["nodes"]) == 1 < len(graph["nodes"])
    assert (
        execute_function(
            small, compiled.functions, function["name"], arguments, schema=kernel["schema"]
        )["value"]
        == execute_function(
            graph, compiled.functions, function["name"], arguments, schema=kernel["schema"]
        )["value"]
    )


def test_the_same_compiler_and_checks_execute_on_genuine_coffee():
    kernel = artifact(PROJECT / ".local/artifacts", COFFEE)
    bank = bank_for()
    entity_type = next(iter(kernel["schema"]["entity_types"]))
    bindings = bindings_for(bank, entity_type=entity_type, date="Date", high="High")
    result = compile_behavior_bindings(bank, kernel["schema"], bindings)
    assert result.diagnostics == []
    report = evaluate_behavior_bank(
        bank, kernel["schema"], result.functions, bindings, kernel["graph"], evidence_refs=[COFFEE]
    )
    assert all(item["status"] == "passed" for item in report["checks"])
    assert len(kernel["graph"]["nodes"]) == 5746
    assert report["behavior_coverage_by_group"]["retrieval"]["passed"] >= 2


def test_semantic_types_grains_units_and_domains_reject_narrowing():
    invalid = program().model_dump()
    invalid["fields"][1]["value_type"] = "date"
    with pytest.raises(ValidationError, match="numeric field"):
        TaskProgram.model_validate(invalid)
    invalid = program().model_dump()
    invalid["fields"][1]["grain"] = "whole country"
    with pytest.raises(ValidationError, match="grains"):
        TaskProgram.model_validate(invalid)
    required = {
        "type": "object",
        "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 7}},
        "required": ["days"],
    }
    narrowed = deepcopy(required)
    narrowed["properties"]["days"]["maximum"] = 2
    assert domain_issues(required, narrowed) == ["narrowed maximum:days"]


def test_named_source_arguments_are_grounded_only_through_the_real_template(tmp_path):
    kernel, graph, receipt = (
        artifact(WEATHER, KERNEL),
        artifact(WEATHER, GRAPH),
        artifact(WEATHER, RECEIPT),
    )
    described = program().model_dump()
    described["input_domain"] = {
        "horizon": "integer",
        "point": {
            "type": "object",
            "properties": {"lat": {"type": "number"}, "lon": {"type": "number"}},
            "required": ["lat", "lon"],
            "additionalProperties": False,
        },
    }
    described["source_parameters"] = ["horizon", "point"]
    bank = bank_for(TaskProgram.model_validate(described))
    template = {
        **receipt["args"],
        "days": {"$arg": "horizon"},
        "latitude": {"$arg_path": ["point", "lat"]},
        "longitude": {"$arg_path": ["point", "lon"]},
    }
    acquisition = AcquisitionTemplate(
        capability_id=receipt["capability_id"], native_arguments=template
    )
    bindings = bindings_for(bank, acquisition=acquisition)
    compiled = compile_behavior_bindings(
        bank, kernel["schema"], bindings, capabilities=kernel["catalog"]["tools"]
    )
    assert compiled.diagnostics == []
    behavior = bank.behaviors[0]
    arguments = make_behavior_inputs(
        behavior,
        bindings[0],
        kernel["schema"],
        graph,
        receipt_arguments={receipt["capability_id"]: receipt["args"]},
    )
    assert arguments[0]["horizon"] == receipt["args"]["days"]
    assert arguments[0]["point"] == {
        "lat": receipt["args"]["latitude"],
        "lon": receipt["args"]["longitude"],
    }
    assert make_behavior_inputs(behavior, bindings[0], kernel["schema"], graph) == []
    store = Store(tmp_path / "store")
    payload = {
        "bank_id": store.put("behavior_bank", bank.model_dump(mode="json")),
        "bindings_id": store.put(
            "behavior_bindings", [item.model_dump(mode="json") for item in bindings]
        ),
        "graph_id": store.put("genuine_graph", graph),
        "capabilities_ref": store.put("genuine_catalog", kernel["catalog"]),
        "receipt_ids": [store.put("genuine_receipt", receipt)],
        "receipt_arguments": {receipt["capability_id"]: {"fabricated_input_ignored": True}},
    }
    report = replay_behavior_evaluation(
        {"schema": kernel["schema"], "functions": compiled.functions}, payload, store
    )
    assert report["status"] == "passed"
    assert all("fabricated_input_ignored" not in str(item["strata"]) for item in report["checks"])


def test_a_constant_sample_answer_never_earns_graph_reasoning_credit():
    kernel, graph = artifact(WEATHER, KERNEL), artifact(WEATHER, GRAPH)
    bank, bindings = bank_for(), bindings_for(bank_for())
    compiled = compile_behavior_bindings(bank, kernel["schema"], bindings)
    wrong = deepcopy(compiled.functions)
    aggregate = next(item for item in wrong if item["steps"][-1]["operator"] == "aggregate_values")
    actual = execute_function(graph, wrong, aggregate["name"], {}, schema=kernel["schema"])["value"]
    aggregate["result"] = actual  # Labelled program mutation using an actual observed result.
    report = evaluate_behavior_bank(bank, kernel["schema"], wrong, bindings, graph)
    assert any(
        item["reason"] == "result does not depend on graph evidence" for item in report["penalties"]
    )
    defect = next(
        item for item in report["checks"] if item.get("function_name") == aggregate["name"]
    )
    assert defect["status"] == "failed" and defect["passed_strata"] == 0


def test_uninterpreted_requirements_cannot_disappear_from_the_denominator():
    kernel, graph = artifact(WEATHER, KERNEL), artifact(WEATHER, GRAPH)
    bank = build_behavior_bank(
        TaskIR(
            source_sha256="authored-contract",
            analysis_sha256="not-a-model-response",
            scope="Unresolved semantics",
            obligations=[
                TaskObligation(
                    obligation_id="unresolved",
                    case_id="authored",
                    text="A requirement with no supported interpretation",
                    parent_requirement_ids=[],
                    derivation_rule="authored_test_contract",
                    program=None,
                    group="composition",
                )
            ],
        )
    )
    assert len(bank.behaviors) == 1 and bank.behaviors[0].program is None
    report = evaluate_behavior_bank(bank, kernel["schema"], [], [], graph)
    assert report["status"] == "unknown"
    assert report["behavior_coverage_by_group"]["composition"] == {
        "total": 2,
        "passed": 0,
        "failed": 0,
        "unknown": 2,
    }
    assert report["unresolved_behavior_ids"] == [bank.behaviors[0].behavior_id]


def test_genuine_malformed_interpretation_stays_inside_the_requirement_repair_boundary():
    """Replay actual model interpretation data, without replacing the response."""
    retained = artifact(
        PROJECT / ".local/artifacts",
        "a3c62b17314aec83da88cbce81f1fd9332073452ebb2dccea9d57612d800b02d",
    )
    malformed = next(
        item["program"]
        for item in retained["obligations"]
        if (item.get("program") or {}).get("input_domain", {}).get("temperature_unit") == "C"
    )
    with pytest.raises(ValidationError, match="Invalid task input domain"):
        TaskProgram.model_validate(malformed)


def test_omitting_a_failed_behavior_cannot_improve_its_learning_rank():
    """A code defect, omission and actual repair use the same genuine evidence."""
    kernel, graph = artifact(WEATHER, KERNEL), artifact(WEATHER, GRAPH)
    bank, bindings = bank_for(), bindings_for(bank_for())
    compiled = compile_behavior_bindings(bank, kernel["schema"], bindings)
    faulty = deepcopy(compiled.functions)
    point = next(
        item
        for item in bank.behaviors
        if item.kind == "point" and item.projection_fields == ["high"]
    )
    function = next(item for item in faulty if item["name"] == "behavior_" + point.behavior_id[2:])
    binding = next(item for item in bindings if item.behavior_id == point.behavior_id)
    date = make_behavior_inputs(point, binding, kernel["schema"], graph)[0]["select_date"]
    function["inputs"]["properties"]["select_date"]["enum"] = [date]
    omitted = [item for item in faulty if item["name"] != function["name"]]
    failed_report = evaluate_behavior_bank(bank, kernel["schema"], faulty, bindings, graph)
    omitted_report = evaluate_behavior_bank(bank, kernel["schema"], omitted, bindings, graph)
    repaired_report = evaluate_behavior_bank(
        bank, kernel["schema"], compiled.functions, bindings, graph
    )
    assert {
        name: (counts["total"], counts["passed"])
        for name, counts in failed_report["behavior_coverage_by_group"].items()
    } == {
        name: (counts["total"], counts["passed"])
        for name, counts in omitted_report["behavior_coverage_by_group"].items()
    }
    assert failed_report["penalties"] and not omitted_report["penalties"]
    failed_rank = candidate_rank(
        {"behavior_evaluation": failed_report}, {"schema": kernel["schema"], "functions": faulty}
    )
    omitted_rank = candidate_rank(
        {"behavior_evaluation": omitted_report}, {"schema": kernel["schema"], "functions": omitted}
    )
    repaired_rank = candidate_rank(
        {"behavior_evaluation": repaired_report},
        {"schema": kernel["schema"], "functions": compiled.functions},
    )
    assert failed_rank < omitted_rank
    assert repaired_rank < failed_rank


@pytest.mark.parametrize("mixed", [False, True], ids=["numeric", "numeric-and-categorical"])
def test_filters_compile_callable_records_and_aggregate_over_genuine_evidence(mixed):
    """Authored task semantics lower to real registered operators on saved rows."""
    kernel, graph = artifact(WEATHER, KERNEL), artifact(WEATHER, GRAPH)
    rows = [row for row in graph["nodes"] if row["type"] == "DailyForecast"]
    thresholds = sorted({row["properties"]["high_temperature"] for row in rows})
    assert len(thresholds) > 1
    conditions = [{"field": "high", "operator": ">=", "value": "$input.threshold"}]
    inputs, parameter_fields = {"threshold": "number"}, {"threshold": "high"}
    if mixed:
        conditions.append({"field": "date", "operator": "in", "values": ["$input.date"]})
        inputs["date"], parameter_fields["date"] = "string", "date"
    described = TaskProgram(
        fields=program().fields,
        operations=[
            TaskOperation(
                id="records", operator="read", fields=["date", "high"], result_kind="records"
            ),
            TaskOperation(
                id="matching",
                operator="filter",
                inputs=["records"],
                fields=["high", "date"] if mixed else ["high"],
                result_kind="records",
                parameters={"conditions": conditions},
            ),
            TaskOperation(
                id="count",
                operator="aggregate",
                inputs=["matching"],
                fields=[],
                result_kind="scalar",
                parameters={"operation": "count"},
            ),
        ],
        result="count",
        input_domain=inputs,
        parameter_fields=parameter_fields,
        observation_contract="Count the dated records satisfying the parameterized predicates",
    )
    bank = bank_for(described)
    bindings = bindings_for(bank)
    compiled = compile_behavior_bindings(bank, kernel["schema"], bindings)
    assert compiled.diagnostics == []
    selected = {
        result: next(
            template
            for template in bank.behaviors
            if template.kind == "computation" and template.program.result == result
        )
        for result in ("matching", "count")
    }
    functions = {
        result: next(
            function
            for function in compiled.functions
            if function["name"] == "behavior_" + template.behavior_id[2:]
        )
        for result, template in selected.items()
    }
    assert functions["matching"]["name"] != functions["count"]["name"]
    for function in functions.values():
        numeric = next(step for step in function["steps"] if step["operator"] == "filter_numeric")
        assert numeric["args"]["conditions"][0]["value"] == {"$arg": "threshold"}
        assert set(function["inputs"]["required"]) == set(inputs)
        if mixed:
            categorical = next(
                step
                for step in function["steps"]
                if step["operator"] == "filter_property_categorical"
            )
            assert categorical["args"]["entities"] == {"$step": numeric["id"]}
            assert categorical["args"]["conditions"][0]["values"] == [{"$arg": "date"}]
    # Both argument values come from actual retained observations. The mixed
    # case deliberately asks about a real date below the higher real threshold.
    date = min(rows, key=lambda row: row["properties"]["high_temperature"])["properties"]["date"]
    for threshold in (thresholds[0], thresholds[-1]):
        arguments = {"threshold": threshold, **({"date": date} if mixed else {})}
        expected = [
            row
            for row in rows
            if row["properties"]["high_temperature"] >= threshold
            and (not mixed or row["properties"]["date"] == date)
        ]
        retrieved = execute_function(
            graph,
            compiled.functions,
            functions["matching"]["name"],
            arguments,
            schema=kernel["schema"],
        )["value"]
        counted = execute_function(
            graph,
            compiled.functions,
            functions["count"]["name"],
            arguments,
            schema=kernel["schema"],
        )["value"]
        assert {row["id"] for row in retrieved} == {row["id"] for row in expected}
        assert counted == len(expected)
    binding = next(item for item in bindings if item.behavior_id == selected["count"].behavior_id)
    actual_inputs = make_behavior_inputs(selected["count"], binding, kernel["schema"], graph)
    assert len(actual_inputs) == 2
    assert all(item["threshold"] in thresholds for item in actual_inputs)
    if mixed:
        assert all(
            item["date"] in {row["properties"]["date"] for row in rows} for item in actual_inputs
        )
    report = evaluate_behavior_bank(
        bank, kernel["schema"], compiled.functions, bindings, graph, evidence_refs=[GRAPH]
    )
    for template in selected.values():
        checked = next(
            item for item in report["checks"] if item["behavior_id"] == template.behavior_id
        )
        assert checked["status"] == "passed"
        assert any(
            mutation["defect"] == "dropped_predicate" and mutation["detected"]
            for mutation in checked["mutations"]
        )
    detected = set()
    for defect, mutant in generated_mutants(
        functions["count"], kernel["schema"], arguments, counted
    ):
        if defect != "dropped_predicate":
            continue
        changed_operator = next(
            left["operator"]
            for left, right in zip(functions["count"]["steps"], mutant["steps"], strict=True)
            if left != right
        )
        actual = execute_function(
            graph, [mutant], mutant["name"], arguments, schema=kernel["schema"]
        )["value"]
        if actual != counted:
            detected.add(changed_operator)
    assert detected == (
        {"filter_numeric", "filter_property_categorical"} if mixed else {"filter_numeric"}
    )
    assert graph == artifact(WEATHER, GRAPH)

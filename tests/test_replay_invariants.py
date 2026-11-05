"""Adversarial checks over genuine captured Coffee computations.

Negative controls corrupt copies of actual execution artifacts or declarations.
They are never used as benchmark observations or claimed model responses.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_historical_replay import replay_chain  # noqa: F401

from oak.historical_replay import (
    AdapterEdge,
    ReplayGap,
    _execute,
    _schema_contract,
    execution_dependencies,
    first_difference,
    inference_admission,
    prepare_candidate_adapter,
    register_adapter_edge,
    register_kernel_bank,
    replay_bank,
    replay_case,
    seal_execution_case,
    seal_replay_case,
)
from oak.regression import AdapterSpec
from oak.replay_contracts import ComparisonContract, ReplayCase
from oak.store import Store, canonical


@pytest.fixture
def isolated(replay_chain, tmp_path):  # noqa: F811
    original = replay_chain["store"]
    with original.connect() as source, sqlite3.connect(tmp_path / "catalog.sqlite") as target:
        source.backup(target)
    shutil.copytree(original.root / "artifacts", tmp_path / "artifacts")
    return {**replay_chain, "store": Store(tmp_path)}


def test_latest_k1_case_is_inherited_through_both_existing_edges(isolated):
    store = isolated["store"]
    k1, k2, k3 = isolated["kernels"]
    late = seal_execution_case(
        store,
        k1,
        isolated["captures"][1],
        run_id=isolated["run_id"],
        question="Late registration of an actual previously captured component",
    )
    register_kernel_bank(store, k1, [late])
    new_bank_id = register_kernel_bank(store, k3)
    bank = store.get(new_bank_id)
    assert late in bank["case_ids"]
    assert set(isolated["case_ids"]).issubset(bank["case_ids"])
    parent = store.get(bank["parent_bank_id"])
    assert parent["kernel_id"] == k2
    assert late in parent["case_ids"]
    report = replay_bank(store, k3, run_id=isolated["run_id"])
    assert report["case_count"] == len(isolated["case_ids"]) + 1
    assert report["allowed"], report["feedback"]


def test_missing_case_remains_in_bank_denominator_and_cannot_pass(isolated):
    store = isolated["store"]
    missing = isolated["case_ids"][0]
    (store.root / "artifacts" / f"{missing}.json").unlink()
    report = replay_bank(store, isolated["kernels"][2], run_id=isolated["run_id"])
    assert report["case_count"] == len(isolated["case_ids"])
    assert len(report["reports"]) == report["case_count"]
    assert not report["allowed"]
    failed = next(item for item in report["reports"] if item["original_case_id"] == missing)
    assert failed["status"] == "unable_to_check"
    assert failed["scope"] == "unknown"


def test_registered_edge_cannot_be_replaced_by_a_different_package(isolated):
    store = isolated["store"]
    edge = store.get(isolated["edges"][0])
    edge["proposal_ref"] = store.put(
        "authored_negative_control", {"purpose": "Attempt to rewrite an immutable package"}
    )
    with pytest.raises(ValueError, match="immutable"):
        register_adapter_edge(store, edge)


def test_step_mapping_cannot_collide_with_an_implicit_identity(isolated):
    store = isolated["store"]
    k1 = isolated["kernels"][0]
    candidate = {**store.get(k1), "parent": k1}
    child = store.put("kernel_revision", candidate)
    edge = AdapterEdge(
        parent_id=k1,
        child_id=child,
        call_adapter=AdapterSpec(old_revision=k1, new_revision=child),
        step_mappings={"maximum_one": {"rows_one": "value_one"}},
    )
    with pytest.raises(ValueError, match="implicit identity"):
        register_adapter_edge(store, edge)


def test_capture_inputs_must_equal_the_preexecution_manifest(isolated):
    store = isolated["store"]
    capture = store.get(isolated["captures"][1])
    capture["args"]["right"] = capture["args"]["left"]
    corrupted = store.put("negative_control_capture", capture)
    with pytest.raises(ReplayGap, match="persisted before execution"):
        seal_execution_case(store, isolated["kernels"][0], corrupted, run_id=isolated["run_id"])


def test_binding_must_reproduce_original_arguments_at_sealing(isolated):
    store = isolated["store"]
    case = store.get(isolated["case_ids"][1])
    case["calls"][1]["bindings"][0]["argument_path"] = ["right"]
    with pytest.raises(ValueError, match="original arguments"):
        seal_replay_case(store, case)


def test_overlapping_result_bindings_are_rejected(isolated):
    case = isolated["store"].get(isolated["case_ids"][1])
    additional = deepcopy(case["calls"][1]["bindings"][0])
    additional["argument_path"].append("nested")
    case["calls"][1]["bindings"].append(additional)
    with pytest.raises(ValidationError, match="overlap"):
        ReplayCase.model_validate(case)


def test_original_intermediate_output_is_protected_even_if_final_maximum_matches(isolated):
    store = isolated["store"]
    capture = store.get(isolated["captures"][0])
    capture["steps"][0]["output"].reverse()
    step = capture["steps"][0]
    step["step_result_ref"] = store.put(
        "negative_control_step",
        {key: value for key, value in step.items() if key != "step_result_ref"},
    )
    corrupted = store.put("negative_control_capture", capture)
    case_id = seal_execution_case(
        store, isolated["kernels"][0], corrupted, run_id=isolated["run_id"]
    )
    result = replay_case(store, case_id, isolated["kernels"][2])
    assert result.status == "unable_to_check"
    assert result.first_difference.phase == "baseline"
    assert result.first_difference.path.startswith("$.steps")
    assert result.candidate_execution_id is None


def test_unavailable_original_runtime_is_a_gap_not_a_candidate_regression(isolated):
    store = isolated["store"]
    capture = store.get(isolated["captures"][0])
    inputs = store.get(capture["input_manifest_ref"])
    inputs["runtime_dependencies"]["executor"] = "unavailable-negative-control-runtime"
    capture["runtime_dependencies"] = inputs["runtime_dependencies"]
    capture["input_manifest_ref"] = store.put("negative_control_inputs", inputs)
    corrupted = store.put("negative_control_capture", capture)
    case_id = seal_execution_case(
        store, isolated["kernels"][0], corrupted, run_id=isolated["run_id"]
    )
    result = replay_case(store, case_id, isolated["kernels"][2])
    assert result.status == "unable_to_check"
    assert "dependencies" in result.reason
    assert result.candidate_execution_id is None


def test_typed_comparison_does_not_coerce_booleans_numbers_or_missing_fields():
    exact = ComparisonContract()
    assert first_difference(True, 1, exact)
    assert first_difference(1, 1.0, exact)
    assert first_difference({}, {"value": None}, exact)
    assert first_difference([1, 2], [2, 1], exact)
    multiset = ComparisonContract(collection="multiset")
    assert first_difference([1, 2, 1], [2, 1, 1], multiset) is None
    assert first_difference([1, 1], [1], multiset)
    assert first_difference([True], [1], multiset)


def test_repair_context_has_programs_but_no_case_inputs_or_observations(isolated):
    store = isolated["store"]
    report = replay_bank(store, isolated["bad_kernel_id"], run_id=isolated["run_id"])
    context = report["repair_context"]
    assert context["candidate"]["kernel_id"] == isolated["bad_kernel_id"]
    assert context["candidate"]["functions"]
    assert context["original_kernels"]
    assert context["adapter_edges"]
    assert {"question", "calls", "expected", "actual", "case_ids", "task_id", "graph"}.isdisjoint(
        context
    )
    encoded = json.dumps(context)
    for identity in isolated["case_ids"]:
        assert identity not in encoded
    assert report["model_calls"] == report["live_mcp_calls"] == 0
    assert store.rows("SELECT * FROM model_calls") == []


def test_replay_does_not_rewrite_sealed_case_bytes(isolated):
    store = isolated["store"]
    before = {identity: canonical(store.get(identity)) for identity in isolated["case_ids"]}
    replay_bank(store, isolated["kernels"][2], run_id=isolated["run_id"])
    assert {identity: canonical(store.get(identity)) for identity in before} == before


def test_schema_description_changes_use_identity_without_a_proposer(isolated):
    store = isolated["store"]
    k1 = isolated["kernels"][0]
    candidate = {**deepcopy(store.get(k1)), "parent": k1}
    candidate["schema"]["name"] = "Renamed display title"
    candidate["schema"]["description"] = "A revised explanation of unchanged contracts"
    entity = candidate["schema"]["entity_types"]["CoffeeRow"]
    entity["description"] = "A clearer entity description"
    entity["properties"]["High"]["description"] = "A clearer field description"
    child = store.put("kernel_revision", candidate)
    edge_id = prepare_candidate_adapter(store, child, run_id=isolated["run_id"])
    edge = store.get(edge_id)
    assert edge["proposal_ref"] is None
    assert all(
        mapping["old_function"] == mapping["new_function"]
        for mapping in edge["call_adapter"]["mappings"]
    )
    assert store.rows("SELECT * FROM model_calls") == []


def test_schema_annotation_filter_preserves_a_property_named_description(isolated):
    schema = deepcopy(isolated["store"].get(isolated["kernels"][0])["schema"])
    schema["entity_types"]["CoffeeRow"]["properties"]["description"] = {"type": "string"}
    changed = deepcopy(schema)
    changed["entity_types"]["CoffeeRow"]["properties"]["different_field"] = changed["entity_types"][
        "CoffeeRow"
    ]["properties"].pop("description")
    assert _schema_contract(schema) != _schema_contract(changed)


@pytest.fixture
def retained_weather(tmp_path):
    """Execute a retrospective component using actual retained acquisition artifacts.

    The production retained-evidence boundary reads the original saved receipt
    and materialized records. This is not a live MCP dispatch or an assertion
    that the newly created capture was recorded during the historical live run.
    """
    store = Store(tmp_path)
    fixture = Path(__file__).parent / "fixtures/observer/weather/artifacts"
    for source in fixture.glob("*.json"):
        raw = source.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == source.stem
        shutil.copy2(source, store.root / "artifacts" / source.name)
    saved_kernel = store.get("2c112be392425277cf1d469ab6c7fd4a98546c3e520452a40802d6ac43c6eaad")
    graph = store.get("3d22ea885e705dc8d46186e4f3f795653a9182ab7c8142876facb99633e658da")
    original = store.get("3d0717687aeb0905fac3a1163b18de08118069c3b7c69a2dd2b2255ca282a9a9")
    initial = {"nodes": [], "edges": [], "source_document_count": 0, "ignored_documents": []}
    assert (
        hashlib.sha256(canonical(initial)).hexdigest() == original["dependencies"]["graph_sha256"]
    )
    assert (
        hashlib.sha256(canonical(graph)).hexdigest()
        == original["dependencies"]["graph_after_sha256"]
    )
    kernel = {
        "parent": None,
        "schema": saved_kernel["schema"],
        "functions": saved_kernel["functions"],
        "catalog": saved_kernel["catalog"],
        "evidence_mode": "retrospective_component_on_retained_source",
    }
    identity = store.put("kernel_revision", kernel)
    kernel["id"] = identity
    args = {
        "native_arguments": original["steps"][0]["inputs"]["arguments"],
        "min_high_temperature": original["steps"][1]["inputs"]["conditions"][0]["value"],
    }
    first_graph = store.put("retained_input_graph", initial)
    after_graph = store.put("retained_materialized_graph", graph)
    boundaries = deepcopy(original["steps"])
    for index, step in enumerate(boundaries):
        step["input_graph_ref"] = first_graph if index == 0 else after_graph
        step["graph_after_ref"] = after_graph
    template = {
        "function": "count_days_above_high_temp",
        "args": args,
        "initial_graph_ref": first_graph,
        "steps": boundaries,
        "runtime_dependencies": execution_dependencies(),
    }
    actual = _execute(store, template, kernel, args, [], [])
    assert actual["value"] == original["value"]
    case = seal_execution_case(
        store,
        identity,
        actual["capture_id"],
        run_id="retrospective-component",
        question="Retrospective component execution on retained weather acquisition",
    )
    register_kernel_bank(store, identity, [case])
    return store, kernel, case, original, args


def test_retained_weather_acquisition_pins_actual_receipts_and_reexecutes(retained_weather):
    store, kernel, case, original, _ = retained_weather
    saved = store.get(case)
    receipt_id = original["steps"][0]["output"]["receipt_id"]
    assert receipt_id in saved["source_refs"]
    report = replay_case(store, case, kernel["id"])
    assert report.status == "preserved", report.reason
    executions = store.get(report.candidate_execution_id)
    assert executions[0]["steps"][1]["operator"] == "filter_numeric"
    assert executions[0]["steps"][2]["operator"] == "aggregate_values"
    assert executions[0]["steps"][2]["status"] == "completed"
    assert report.model_calls == report.live_mcp_calls == 0
    assert store.rows("SELECT * FROM model_calls") == []


@pytest.mark.parametrize("change", ["arguments", "contract", "missing_receipt"])
def test_retained_acquisition_mismatch_never_dispatches_or_passes(retained_weather, change):
    store, kernel, case, original, args = retained_weather
    if change == "missing_receipt":
        receipt_id = original["steps"][0]["output"]["receipt_id"]
        (store.root / "artifacts" / f"{receipt_id}.json").unlink()
        candidate_id = kernel["id"]
    else:
        candidate = {key: deepcopy(value) for key, value in kernel.items() if key != "id"}
        candidate["parent"] = kernel["id"]
        if change == "contract":
            candidate["catalog"]["tools"][0]["contract_id"] = "negative-control-contract"
        else:
            selected = next(
                item
                for item in candidate["functions"]
                if item["name"] == "count_days_above_high_temp"
            )
            altered = deepcopy(args["native_arguments"])
            altered["days"] += 1
            selected["steps"][0]["args"]["arguments"] = altered
        candidate_id = store.put("kernel_revision", candidate)
        register_kernel_bank(store, candidate_id)
        register_adapter_edge(
            store,
            AdapterEdge(
                parent_id=kernel["id"],
                child_id=candidate_id,
                call_adapter=AdapterSpec(old_revision=kernel["id"], new_revision=candidate_id),
            ),
        )
    report = replay_case(store, case, candidate_id)
    assert report.status == "unable_to_check", report.reason
    assert report.model_calls == report.live_mcp_calls == 0
    assert store.rows("SELECT * FROM model_calls") == []


@pytest.mark.parametrize("field", ["corpus_id", "documents_id"])
def test_original_nested_source_references_remain_required_without_duplicate_case_pins(
    isolated, field
):
    store = isolated["store"]
    k1, _, k3 = isolated["kernels"]
    original = store.get(isolated["case_ids"][0])
    assert store.get(k1)[field] in original["source_refs"]
    # Earlier frozen cases did not duplicate these exact nested immutable refs.
    previous_format = {**original, "source_refs": []}
    previous_id = store.put("replay_case", previous_format)
    assert replay_case(store, previous_id, k3).status == "preserved"
    missing = store.get(k1)[field]
    (store.root / "artifacts" / f"{missing}.json").unlink()
    result = replay_case(store, previous_id, k3)
    assert result.status == "unable_to_check"
    assert result.baseline_execution_id is None
    assert not inference_admission(store, k3)["allowed"]
    assert store.get(previous_id) == previous_format


@pytest.fixture
def retained_demand_weather(retained_weather):
    """Run pure computation after materializing genuine retained receipt records.

    The exported fixture redacts receipt identities. Its original invoke trace
    binds the saved entities to the saved receipt; this retrospective derivative
    updates only their document attribution to that receipt's current identity.
    """
    from oak.bootstrap import receipt_documents
    from oak.functions import execute_function
    from oak.materialization import AcquisitionBinding

    store, original_kernel, _, original, args = retained_weather
    receipt_id = original["steps"][0]["output"]["receipt_id"]
    receipt = store.get(receipt_id)
    documents = receipt_documents({**receipt, "evidence_id": receipt_id})
    graph = store.get("3d22ea885e705dc8d46186e4f3f795653a9182ab7c8142876facb99633e658da")
    for record in [*graph["nodes"], *graph["edges"]]:
        for source in record["sources"]:
            offset = source["document_id"].rsplit("-", 1)[1]
            source["document_id"] = f"{receipt_id}-{offset}"
            assert any(
                document["document_id"] == source["document_id"]
                and document["locator"] == source["source_ref"]
                for document in documents
            )
    graph["source_document_ids"] = [document["document_id"] for document in documents]
    function = deepcopy(
        next(
            item
            for item in original_kernel["functions"]
            if item["name"] == "count_days_above_high_temp"
        )
    )
    function["steps"][0] = {
        "id": "fetch_forecast",
        "operator": "lookup_entities",
        "args": {"entity_types": ["DailyForecast"]},
    }
    function["steps"][1]["args"]["entities"] = {"$step": "fetch_forecast"}
    binding = AcquisitionBinding(
        function_name=function["name"],
        schema_sha256=hashlib.sha256(canonical(original_kernel["schema"])).hexdigest(),
        function_sha256=hashlib.sha256(canonical(function)).hexdigest(),
        capability_id=receipt["capability_id"],
        native_arguments={"$arg": "native_arguments"},
        contract_id=receipt["contract_id"],
    )
    kernel = {
        "parent": None,
        "schema": original_kernel["schema"],
        "functions": [function],
        "catalog": original_kernel["catalog"],
        "acquisition_bindings": [binding.model_dump(mode="json")],
        "evidence": {"documents_id": store.put("acquired_documents", documents)},
        "retrospective_source_trace": "3d0717687aeb0905fac3a1163b18de08118069c3b7c69a2dd2b2255ca282a9a9",
        "evidence_mode": "retrospective_component_on_retained_source",
    }
    kernel_id = store.put("kernel_revision", kernel)
    working = {"nodes": [], "edges": [], "source_document_count": 0, "ignored_documents": []}

    def materialize_retained(**boundary):
        if boundary["step_id"] == "fetch_forecast":
            working.update(deepcopy(graph))

    actual = execute_function(
        working,
        [function],
        function["name"],
        args,
        schema=kernel["schema"],
        before_step=materialize_retained,
        artifact_store=store,
    )
    assert actual["value"] == original["value"]
    case_id = seal_execution_case(
        store, kernel_id, actual["capture_id"], run_id="retrospective-demand-component"
    )
    register_kernel_bank(store, kernel_id, [case_id])
    return store, kernel_id, case_id, receipt_id


def test_pure_demand_replay_retains_actual_acquisition_receipt_closure(retained_demand_weather):
    store, kernel_id, case_id, receipt_id = retained_demand_weather
    assert receipt_id in store.get(case_id)["source_refs"]
    previous_format = {**store.get(case_id), "source_refs": []}
    case_id = store.put("replay_case", previous_format)
    result = replay_case(store, case_id, kernel_id)
    assert result.status == "preserved", result.reason
    execution = store.get(result.candidate_execution_id)[0]
    assert [step["operator"] for step in execution["steps"]] == [
        "lookup_entities",
        "filter_numeric",
        "aggregate_values",
    ]
    assert result.model_calls == result.live_mcp_calls == 0
    (store.root / "artifacts" / f"{receipt_id}.json").unlink()
    failed = replay_case(store, case_id, kernel_id)
    assert failed.status == "unable_to_check"
    assert failed.baseline_execution_id is None
    assert store.rows("SELECT * FROM model_calls") == []


@pytest.mark.parametrize("change", ["arguments", "contract"])
def test_pure_demand_source_receipts_must_match_candidate_requests(retained_demand_weather, change):
    store, kernel_id, case_id, _ = retained_demand_weather
    kernel = store.get(kernel_id)
    kernel["parent"] = kernel_id
    if change == "arguments":
        kernel["acquisition_bindings"][0]["native_arguments"] = {"days": 16}
    else:
        kernel["acquisition_bindings"][0]["contract_id"] = "negative-control-contract"
        for tool in kernel["catalog"]["tools"]:
            if tool["id"] == kernel["acquisition_bindings"][0]["capability_id"]:
                tool["contract_id"] = "negative-control-contract"
    changed_kernel = store.put("negative_control_kernel", kernel)
    register_kernel_bank(store, changed_kernel)
    register_adapter_edge(
        store,
        AdapterEdge(
            parent_id=kernel_id,
            child_id=changed_kernel,
            call_adapter=AdapterSpec(old_revision=kernel_id, new_revision=changed_kernel),
        ),
    )
    result = replay_case(store, case_id, changed_kernel)
    assert result.status == "unable_to_check", result.reason
    assert "frozen requests" in result.reason or "capability contract" in result.reason
    assert result.model_calls == result.live_mcp_calls == 0

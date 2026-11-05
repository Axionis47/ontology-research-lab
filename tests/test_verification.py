"""Independent checks over genuine Coffee data and retained weather evidence.

Explicit test programs execute real operators. No fabricated service replies,
model responses or reasoner results substitute for actual components.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from oak.construction_contracts import (
    RequirementAnalysis,
    RequirementInterpretation,
    requirement_inputs,
)
from oak.functions import execute_function
from oak.learning import candidate_rank, freeze_task_ir, repair_feedback
from oak.learning_contracts import SemanticField, TaskOperation, TaskProgram
from oak.ontology import validate_ontology
from oak.preservation import (
    certify_preservation,
    compose_certificates,
    lower_function,
    validate_certificate,
)
from oak.store import Store
from oak.task_context import QuerySpec
from oak.tasks.coffee import DEFAULT_CACHE, load_coffee
from oak.verification import (
    GeneratedCheckSpec,
    KernelCandidate,
    ObligationCheck,
    ObservedCheck,
    execute_generated_check,
    verify_candidate,
)


@pytest.fixture(scope="module")
def real_case(tmp_path_factory):
    if not (DEFAULT_CACHE / "coffee_price.csv").is_file():
        pytest.skip("Genuine Coffee source data is unavailable in this checkout")
    source = load_coffee()["corpus"]["documents"][:3]
    schema = {
        "name": "VerificationCoffee",
        "entity_types": {
            "Quote": {
                "primary_key": "Date",
                "properties": {
                    "Date": {"type": "string", "required": True},
                    "High": {"type": "number", "required": True},
                },
            }
        },
        "relations": {},
    }
    graph = {
        "nodes": [
            {
                "id": item["id"],
                "type": "Quote",
                "properties": {
                    "Date": json.loads(item["content"])["Date"],
                    "High": float(json.loads(item["content"])["High"]),
                },
                "sources": [{"document_id": item["id"], "source_ref": item["source_ref"]}],
            }
            for item in source
        ],
        "edges": [],
    }
    function = {
        "name": "read_high",
        "description": "Read an actual dated Coffee quote.",
        "inputs": {
            "type": "object",
            "properties": {"date": {"type": "string"}},
            "required": ["date"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "number"},
        "steps": [
            {
                "id": "lookup",
                "operator": "lookup_entities",
                "args": {"entity_types": ["Quote"], "property_filters": {"Date": {"$arg": "date"}}},
            }
        ],
        "result": {"$path": ["lookup", 0, "properties", "High"]},
    }
    directory = tmp_path_factory.mktemp("verification")
    store = Store(directory / "store")
    candidate = KernelCandidate(id="coffee-parent", schema=schema, functions=[function])
    graph_id = store.put("genuine_graph", graph)
    args = {"date": graph["nodes"][0]["properties"]["Date"]}
    actual = execute_function(graph, [function], "read_high", args, schema=schema)
    evidence_id = store.put(
        "execution_input",
        {
            "candidate_id": candidate.id,
            "graph_id": graph_id,
            "function": "read_high",
            "args": args,
            "value": actual["value"],
        },
    )
    ontology = validate_ontology(schema, directory / "hermit")
    assert ontology["valid"], ontology
    ontology_id = store.put("ontology_validation", ontology)
    return candidate, graph, store, graph_id, evidence_id, ontology_id


def obligation(**changes):
    return ObligationCheck(id="read", group="retrieval", function_names=["read_high"], **changes)


def test_execution_is_eligible_without_an_independent_domain_evaluator(real_case):
    candidate, _, store, _, evidence_id, ontology_id = real_case
    report = verify_candidate(
        candidate,
        [obligation()],
        [ObservedCheck(obligation_id="read", dimension="execution", evidence_ref=evidence_id)],
        store=store,
        ontology_validation_ref=ontology_id,
    )
    assert report.execution_eligible
    assert report.disposition == "execution_eligible"
    assert not report.target_met
    assert report.unresolved_obligation_ids == ["read"]
    assert next(check for check in report.checks if check.dimension == "task").status == "unknown"


def test_unmapped_subtasks_are_unknown_and_do_not_disable_execution(real_case):
    candidate, _, store, _, evidence_id, ontology_id = real_case
    report = verify_candidate(
        candidate,
        [obligation(), ObligationCheck(id="unmapped", group="subtask")],
        [ObservedCheck(obligation_id="read", dimension="execution", evidence_ref=evidence_id)],
        store=store,
        ontology_validation_ref=ontology_id,
    )
    assert report.execution_eligible
    assert report.disposition == "execution_eligible"
    assert "unmapped" in report.unresolved_obligation_ids


def test_model_pass_field_is_not_a_check_contract(real_case):
    with pytest.raises(ValueError, match="Extra inputs"):
        ObservedCheck(
            obligation_id="read", dimension="task", evidence_ref=real_case[4], status="passed"
        )
    candidate, _, store, _, evidence_id, ontology_id = real_case
    claim_id = store.put(
        "model_claim", {"candidate_id": candidate.id, "status": "passed", "score": 1}
    )
    report = verify_candidate(
        candidate,
        [obligation()],
        [
            ObservedCheck(obligation_id="read", dimension="execution", evidence_ref=evidence_id),
            ObservedCheck(
                obligation_id="read",
                dimension="task",
                evidence_ref=claim_id,
                evaluator_id="model_claim",
            ),
        ],
        store=store,
        ontology_validation_ref=ontology_id,
    )
    assert report.execution_eligible and not report.target_met
    assert next(check for check in report.checks if check.dimension == "task").status == "unknown"


def _generated_count_check():
    rows = {
        "name": "all_quotes",
        "description": "Read the actual materialized Coffee quote rows.",
        "inputs": {"type": "object", "properties": {}, "additionalProperties": False},
        "output_schema": {"type": "array"},
        "steps": [
            {"id": "quotes", "operator": "lookup_entities", "args": {"entity_types": ["Quote"]}}
        ],
        "result": {"$step": "quotes"},
    }
    count = deepcopy(rows)
    count["name"] = "count_quotes"
    count["output_schema"] = {"type": "integer"}
    count["steps"].append(
        {
            "id": "count",
            "operator": "aggregate_values",
            "args": {"items": {"$step": "quotes"}, "request": {"operation": "count"}},
        }
    )
    count["result"] = {"$step": "count"}
    return {
        "id": "count_consistency",
        "obligation_id": "read",
        "description": "The count should match the actual list length on this graph.",
        "left": rows,
        "relation": "length_equals",
        "right": count,
    }


def _generated_read_check(candidate, graph):
    projection = deepcopy(candidate.functions[0])
    projection["name"] = "reference_projection"
    projection["steps"].append(
        {
            "id": "project",
            "operator": "project_properties",
            "args": {"entities": {"$step": "lookup"}, "property_names": ["High"]},
        }
    )
    projection["result"] = {"$path": ["project", 0, "High"]}
    args = {"date": graph["nodes"][0]["properties"]["Date"]}
    return {
        "id": "read_consistency",
        "obligation_id": "read",
        "description": "Compare the candidate read with a separately generated projection path.",
        "left": {"function": "read_high"},
        "left_args": args,
        "relation": "equal",
        "right": projection,
        "right_args": args,
    }


def test_generated_check_executes_actual_programs_but_is_not_an_oracle(real_case):
    candidate, graph, store, graph_id, execution_id, ontology_id = real_case
    specification = _generated_read_check(candidate, graph)
    result = execute_generated_check(
        specification, graph, candidate.schema, candidate_functions=candidate.functions
    )
    assert result["status"] == "passed", result
    assert result["independent"] is False
    assert result["left_execution"]["value"] == graph["nodes"][0]["properties"]["High"]
    assert result["contributes_to_learning"]
    check_id = store.put(
        "generated_check_input",
        {"candidate_id": candidate.id, "graph_id": graph_id, "check": specification},
    )
    report = verify_candidate(
        candidate,
        [obligation()],
        [
            ObservedCheck(obligation_id="read", dimension="execution", evidence_ref=execution_id),
            ObservedCheck(
                obligation_id="read",
                dimension="generated",
                evidence_ref=check_id,
                evaluator_id="generated_dsl_v1",
            ),
        ],
        store=store,
        ontology_validation_ref=ontology_id,
    )
    assert report.execution_eligible and not report.target_met
    assert report.generated_coverage_by_group["retrieval"]["passed"] == 1
    assert report.coverage_by_group["retrieval"]["passed"] == 0


def test_generated_failure_is_feedback_not_a_domain_verifier_gate(real_case):
    candidate, graph, store, graph_id, execution_id, ontology_id = real_case
    specification = _generated_read_check(candidate, graph)
    specification["right"]["steps"][-1]["args"]["property_names"] = ["Date"]
    specification["right"]["result"]["$path"][-1] = "Date"
    specification["right"]["output_schema"] = {"type": "string"}
    check_id = store.put(
        "generated_check_input",
        {"candidate_id": candidate.id, "graph_id": graph_id, "check": specification},
    )
    report = verify_candidate(
        candidate,
        [obligation()],
        [
            ObservedCheck(obligation_id="read", dimension="execution", evidence_ref=execution_id),
            ObservedCheck(
                obligation_id="read",
                dimension="generated",
                evidence_ref=check_id,
                evaluator_id="generated_dsl_v1",
            ),
        ],
        store=store,
        ontology_validation_ref=ontology_id,
    )
    assert report.execution_eligible and report.disposition == "execution_eligible"
    assert report.generated_coverage_by_group["retrieval"]["failed"] == 1


def test_generated_checks_cannot_call_services(real_case):
    candidate, graph, *_ = real_case
    specification = _generated_count_check()
    specification["left"]["steps"].insert(
        0,
        {
            "id": "fetch",
            "operator": "invoke_capability",
            "args": {"capability": "test/tool", "arguments": {}},
        },
    )
    with pytest.raises(ValueError, match="cannot dispatch"):
        execute_generated_check(specification, graph, candidate.schema)


def test_actual_lean_proves_local_names_and_transitive_preservation(real_case):
    candidate, graph, *_ = real_case
    child = candidate.model_copy(
        deep=True, update={"id": "coffee-child", "parent_id": candidate.id}
    )
    child.functions[0]["steps"][0]["id"] = "observed_quote"
    child.functions[0]["result"]["$path"][0] = "observed_quote"
    certificate = certify_preservation(candidate, child)
    if certificate.status == "unknown" and "unavailable" in certificate.summary:
        pytest.skip(certificate.summary)
    assert certificate.status == "certified", certificate.model_dump()
    assert certificate.proof_receipt["axioms"] == []
    assert certificate.rules == ["local_alpha_renaming"]
    for node in graph["nodes"]:
        args = {"date": node["properties"]["Date"]}
        assert (
            execute_function(
                graph, candidate.functions, "read_high", args, schema=candidate.schema
            )["value"]
            == execute_function(graph, child.functions, "read_high", args, schema=child.schema)[
                "value"
            ]
        )
    grandchild = child.model_copy(
        deep=True, update={"id": "coffee-grandchild", "parent_id": child.id}
    )
    second = certify_preservation(child, grandchild)
    assert second.status == "certified", second.model_dump()
    chain = compose_certificates(
        [certificate, second], {item.id: item for item in [candidate, child, grandchild]}
    )
    assert chain["ancestor_id"] == candidate.id and chain["candidate_id"] == grandchild.id
    corrupted = certificate.model_dump(mode="json")
    corrupted["schema_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_certificate(corrupted, candidate, child)


def test_schema_change_effects_and_semantic_changes_are_not_certified(real_case):
    candidate, *_ = real_case
    child = candidate.model_copy(deep=True, update={"id": "changed", "parent_id": candidate.id})
    child.schema["name"] = "ChangedSchema"
    assert certify_preservation(candidate, child).status == "unknown"
    child = candidate.model_copy(deep=True, update={"id": "changed", "parent_id": candidate.id})
    child.functions[0]["result"]["$path"][-1] = "Date"
    child.functions[0]["output_schema"] = {"type": "string"}
    assert certify_preservation(candidate, child).status == "unknown"
    child.functions = []
    assert certify_preservation(candidate, child).status == "counterexample"
    function = deepcopy(candidate.functions[0])
    function["steps"].insert(
        0,
        {
            "id": "acquire",
            "operator": "invoke_capability",
            "args": {"capability": "test/tool", "arguments": {}},
        },
    )
    with pytest.raises(ValueError, match="Effectful"):
        lower_function(function, candidate.schema)


def test_literal_fields_are_not_renamed_as_local_variables(real_case):
    candidate, *_ = real_case
    original = lower_function(candidate.functions[0], candidate.schema)
    changed = deepcopy(candidate.functions[0])
    changed["steps"][0]["args"]["property_filters"] = {"Date": "lookup"}
    modified = lower_function(changed, candidate.schema)
    assert modified != original
    assert modified.steps[0].arguments["property_filters"]["Date"] == "lookup"


def test_check_evidence_is_bound_to_candidate(real_case):
    candidate, _, store, graph_id, _, ontology_id = real_case
    mismatched = store.put(
        "execution_input",
        {"candidate_id": "another", "graph_id": graph_id, "function": "read_high", "args": {}},
    )
    report = verify_candidate(
        candidate,
        [obligation()],
        [ObservedCheck(obligation_id="read", dimension="execution", evidence_ref=mismatched)],
        store=store,
        ontology_validation_ref=ontology_id,
    )
    assert not report.execution_eligible
    assert report.disposition == "rejected"


def test_generated_contract_has_no_expected_answer_field():
    specification = _generated_count_check()
    specification["expected"] = 3
    with pytest.raises(ValueError, match="Extra inputs"):
        GeneratedCheckSpec.model_validate(specification)


def test_tautological_generated_checks_do_not_earn_coverage(real_case):
    candidate, graph, *_ = real_case
    specification = _generated_count_check()
    specification["relation"] = "equal"
    specification["right"] = deepcopy(specification["left"])
    specification["right"]["name"] = "renamed_checker"
    result = execute_generated_check(specification, graph, candidate.schema)
    assert result["status"] == "unknown"
    assert "tautological" in result["summary"]


def test_generated_check_observes_actual_candidate_function_changes(real_case):
    candidate, graph, *_ = real_case
    specification = _generated_read_check(candidate, graph)
    original = execute_generated_check(
        specification, graph, candidate.schema, candidate_functions=candidate.functions
    )
    assert original["status"] == "passed"
    changed = deepcopy(candidate.functions)
    changed[0]["steps"][0]["args"]["property_filters"]["Date"] = graph["nodes"][-1]["properties"][
        "Date"
    ]
    result = execute_generated_check(
        specification, graph, candidate.schema, candidate_functions=changed
    )
    assert result["status"] == "failed"
    assert result["left_execution"]["value"] == graph["nodes"][-1]["properties"]["High"]


def test_standalone_generated_relations_are_not_candidate_quality(real_case):
    candidate, graph, *_ = real_case
    result = execute_generated_check(_generated_count_check(), graph, candidate.schema)
    assert result["status"] == "passed"
    assert not result["contributes_to_learning"]


def test_genuine_weather_probe_is_verified_without_redispatch(tmp_path):
    source = Path(__file__).parent / "fixtures" / "observer" / "weather"
    root = tmp_path / "retained_weather"
    shutil.copytree(source, root)
    store = Store(root)
    identity = "34a3b327f911a44f10c06933c69ae2bd69150cc23309f1f205963b593f272151"
    kernel = store.get(identity)
    candidate = KernelCandidate(
        id=identity,
        schema=kernel["schema"],
        functions=kernel["functions"],
        parent_id=kernel.get("parent"),
    )
    evidence = store.put(
        "verification_input",
        {
            "candidate_id": identity,
            "probe_evidence_id": "da52bbf4c594c7f02741690c65cceb348e6761b8f86a512377fc911f6116ed6e",
        },
    )
    with store.connect() as connection:
        before = connection.execute(
            "SELECT count(*) FROM events WHERE stage='mcp_call'"
        ).fetchone()[0]
    report = verify_candidate(
        candidate,
        [
            ObligationCheck(
                id="count", group="composition", function_names=["count_days_above_high_temp"]
            )
        ],
        [ObservedCheck(obligation_id="count", dimension="execution", evidence_ref=evidence)],
        store=store,
    )
    check = next(check for check in report.checks if check.dimension == "execution")
    assert check.status == "passed", check.model_dump()
    assert check.details["mode"] == "recorded_execution"
    assert check.details["task_correctness"] == "not_checked"
    with store.connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM events WHERE stage='mcp_call'").fetchone()[0]
            == before
        )


def test_unattested_recorded_probe_cannot_claim_execution(real_case):
    candidate, _, store, graph_id, _, _ = real_case
    unsupported = store.put("model_claim", {"status": "passed", "graph_id": graph_id})
    evidence = store.put(
        "verification_input", {"candidate_id": candidate.id, "probe_evidence_id": unsupported}
    )
    report = verify_candidate(
        candidate,
        [obligation()],
        [ObservedCheck(obligation_id="read", dimension="execution", evidence_ref=evidence)],
        store=store,
    )
    check = next(check for check in report.checks if check.dimension == "execution")
    assert check.status == "failed"
    assert "No passed function-probe event" in check.summary


def test_learning_bank_and_verifier_meet_on_actual_candidate_behavior(real_case):
    """An authored component request over real data exercises both independent flows."""
    candidate, graph, store, graph_id, execution_id, ontology_id = real_case
    date = graph["nodes"][0]["properties"]["Date"]
    query = QuerySpec(
        id="real-coffee-row", query=f"What is the Coffee high on {date}?", split="construction"
    )
    inputs = requirement_inputs([query])
    program = TaskProgram(
        fields=[
            SemanticField(
                id="quote_high",
                description="Dated Coffee high",
                value_type="number",
                grain="quote date",
            )
        ],
        operations=[
            TaskOperation(id="read", operator="read", fields=["quote_high"], result_kind="records"),
            TaskOperation(
                id="project",
                operator="project",
                inputs=["read"],
                fields=["quote_high"],
                result_kind="scalar",
            ),
        ],
        result="project",
        input_domain={"date": "string"},
        observation_contract="Return the requested dated high from the supplied evidence.",
    )
    analysis = RequirementAnalysis(
        scope_summary="Read the supplied Coffee quotes",
        interpretations=[
            RequirementInterpretation(
                obligation_id=inputs[0].obligation_id,
                case_id=query.id,
                interpretation=query.query,
                required_outputs=["dated high"],
                program=program,
            )
        ],
    )
    bank = freeze_task_ir(analysis.scope_summary, inputs, analysis)
    checks = [
        ObligationCheck(
            id=item.obligation_id,
            group=item.group,
            mandatory=item.mandatory,
            function_names=["read_high"] if item.derivation_rule == "literal_requirement" else [],
            semantic_status=item.semantic_status,
            oracle_ref=item.oracle_ref,
        )
        for item in bank.obligations
    ]
    primary = inputs[0].obligation_id
    generated = _generated_read_check(candidate, graph)
    generated["obligation_id"] = primary
    generated_id = store.put(
        "generated_check_input",
        {"candidate_id": candidate.id, "graph_id": graph_id, "check": generated},
    )
    original_report = verify_candidate(
        candidate,
        checks,
        [
            ObservedCheck(obligation_id=primary, dimension="execution", evidence_ref=execution_id),
            ObservedCheck(
                obligation_id=primary,
                dimension="generated",
                evidence_ref=generated_id,
                evaluator_id="generated_dsl_v1",
            ),
        ],
        store=store,
        ontology_validation_ref=ontology_id,
    )

    changed = candidate.model_copy(deep=True, update={"id": "changed-dated-read"})
    changed.functions[0]["steps"][0]["args"]["property_filters"]["Date"] = graph["nodes"][-1][
        "properties"
    ]["Date"]
    actual = execute_function(
        graph, changed.functions, "read_high", {"date": date}, schema=changed.schema
    )
    changed_execution = store.put(
        "execution_input",
        {
            "candidate_id": changed.id,
            "graph_id": graph_id,
            "function": "read_high",
            "args": {"date": date},
            "value": actual["value"],
        },
    )
    same_bank_input = store.put(
        "generated_check_input",
        {"candidate_id": changed.id, "graph_id": graph_id, "check": generated},
    )
    changed_report = verify_candidate(
        changed,
        checks,
        [
            ObservedCheck(
                obligation_id=primary, dimension="execution", evidence_ref=changed_execution
            ),
            ObservedCheck(
                obligation_id=primary,
                dimension="generated",
                evidence_ref=same_bank_input,
                evaluator_id="generated_dsl_v1",
            ),
        ],
        store=store,
        ontology_validation_ref=ontology_id,
    )
    assert original_report.execution_eligible and changed_report.execution_eligible
    assert not original_report.target_met and not changed_report.target_met
    assert candidate_rank(
        original_report.model_dump(mode="json"), candidate.model_dump(mode="json")
    ) < candidate_rank(changed_report.model_dump(mode="json"), changed.model_dump(mode="json"))
    feedback = repair_feedback(changed_report.model_dump(mode="json"))
    assert any(item["dimension"] == "generated" for item in feedback["counterexamples"])

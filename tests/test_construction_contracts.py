"""Check actual contract logic against authored pilot inputs and retained kernels.

Interpretations and mappings below are explicitly hand-authored contract inputs
for the validator, not saved or simulated model outputs. The tests execute no
agent, model, or connector and make no claim that a mapped task was solved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from oak.construction_contracts import (
    CoverageReport,
    FunctionCoverage,
    RequirementAnalysis,
    RequirementInterpretation,
    requirement_inputs,
    validate_function_coverage,
    validate_requirement_analysis,
)
from oak.learning_contracts import SemanticField, TaskOperation, TaskProgram
from oak.task_context import TaskSurface

PROJECT = Path(__file__).resolve().parents[1]
KERNEL = (
    PROJECT
    / "tests/fixtures/observer/weather/artifacts"
    / "2c112be392425277cf1d469ab6c7fd4a98546c3e520452a40802d6ac43c6eaad.json"
)


@pytest.fixture
def surface() -> TaskSurface:
    """Use the unchanged public-weather pilot's real onboarding inputs."""
    return TaskSurface.model_validate(
        json.loads((PROJECT / "config/weather-surface.json").read_text())
    )


@pytest.fixture
def functions() -> list[dict]:
    """Use a genuinely generated kernel from the reviewed portable export."""
    return json.loads(KERNEL.read_text())["data"]["functions"]


def declared_analysis(obligations) -> RequirementAnalysis:
    """Copy literal source descriptions to exercise attribution, not reasoning."""
    return RequirementAnalysis(
        scope_summary="Structural contract inspection of the supplied pilot cases.",
        interpretations=[
            RequirementInterpretation(
                obligation_id=item.obligation_id,
                case_id=item.case_id,
                interpretation=item.text,
                required_outputs=[item.text],
            )
            for item in obligations
        ],
    )


def test_literal_obligations_are_stable_complete_and_case_order_independent(surface):
    selected = [query for query in surface.queries if query.split == "construction"][:2]
    obligations = requirement_inputs(selected)
    assert obligations == requirement_inputs(list(reversed(selected)))
    assert len(obligations) == sum(1 + len(query.requirements) for query in selected)
    assert len({item.obligation_id for item in obligations}) == len(obligations)
    assert all(len(item.obligation_id) == 20 for item in obligations)
    for query in selected:
        actual = [item for item in obligations if item.case_id == query.id]
        assert actual[0].kind == "query"
        assert actual[0].text == query.query
        assert actual[0].requirement_index is None
        assert [item.text for item in actual[1:]] == query.requirements
        assert [item.requirement_index for item in actual[1:]] == list(
            range(len(query.requirements))
        )
    # This is an explicit source edit; source identity must not conceal it.
    changed = selected[0].model_copy(deep=True)
    changed.requirements.reverse()
    assert requirement_inputs([changed]) != requirement_inputs([selected[0]])


def test_queries_remain_obligations_without_extra_requirements(surface):
    query = surface.queries[0].model_copy(deep=True)
    query.requirements = []
    obligations = requirement_inputs([query])
    assert len(obligations) == 1
    assert obligations[0].text == query.query


def test_requirement_inputs_refuse_nonconstruction_and_duplicate_cases(surface):
    for split in ("development", "heldout"):
        query = next(query for query in surface.queries if query.split == split)
        with pytest.raises(ValueError, match="construction queries only"):
            requirement_inputs([surface.queries[0], query])
    with pytest.raises(ValueError, match="at least one"):
        requirement_inputs([])
    with pytest.raises(ValueError, match="must be unique"):
        requirement_inputs([surface.queries[0], surface.queries[0]])


def test_analysis_cannot_drop_duplicate_or_reattribute_an_obligation(surface):
    obligations = requirement_inputs([surface.queries[0]])
    analysis = declared_analysis(obligations)
    assert validate_requirement_analysis(analysis, obligations, []) == analysis
    malformed = analysis.model_copy(deep=True)
    malformed.interpretations.pop()
    with pytest.raises(ValueError, match="exactly once"):
        validate_requirement_analysis(malformed, obligations, [])
    malformed = analysis.model_copy(deep=True)
    malformed.interpretations.append(malformed.interpretations[0])
    with pytest.raises(ValueError, match="exactly once"):
        validate_requirement_analysis(malformed, obligations, [])
    malformed = analysis.model_copy(deep=True)
    malformed.interpretations[0].case_id = surface.queries[1].id
    with pytest.raises(ValueError, match="wrong case"):
        validate_requirement_analysis(malformed, obligations, [])
    malformed = analysis.model_copy(deep=True)
    malformed.interpretations[0].obligation_id = "r_000000000000000000"
    with pytest.raises(ValueError, match="exactly once"):
        validate_requirement_analysis(malformed, obligations, [])


def test_analysis_references_only_authorized_capabilities(surface, functions):
    capability = functions[0]["steps"][0]["args"]["capability"]
    obligations = requirement_inputs([surface.queries[0]])
    analysis = declared_analysis(obligations)
    analysis.interpretations[0].capability_ids = [capability]
    assert validate_requirement_analysis(analysis, obligations, [capability]) == analysis
    with pytest.raises(ValueError, match="unknown capability"):
        validate_requirement_analysis(analysis, obligations, [])
    analysis.interpretations[0].capability_ids.append(capability)
    with pytest.raises(ValueError, match="repeats a capability"):
        validate_requirement_analysis(analysis, obligations, [capability])


def test_requirement_acceptance_preserves_optional_native_contract_fields(surface):
    """The genuine native contract stays opaque, including its optional fields."""
    kernel = json.loads(KERNEL.read_text())["data"]
    function = kernel["functions"][0]
    acquisition = function["steps"][0]["args"]
    assert acquisition["arguments"] == {"$arg": "native_arguments"}
    capability = next(
        item for item in kernel["catalog"]["tools"] if item["id"] == acquisition["capability"]
    )
    native_schema = capability["input_schema"]
    assert "source" not in native_schema["required"]
    assert "temperature_unit" not in native_schema["required"]
    inputs = {
        **function["inputs"],
        "properties": {"native_arguments": native_schema},
    }
    high = kernel["schema"]["entity_types"]["DailyForecast"]["properties"]["high_temperature"]
    program = TaskProgram(
        fields=[
            SemanticField(
                id="high",
                description=high["description"],
                value_type=high["type"],
                grain="daily forecast",
            )
        ],
        operations=[
            TaskOperation(id="records", operator="read", fields=["high"], result_kind="records")
        ],
        result="records",
        input_domain=inputs,
        source_parameters=["native_arguments"],
        observation_contract="Return daily high values over the acquired scope.",
    )
    obligations = requirement_inputs([surface.queries[0]])
    analysis = declared_analysis(obligations)
    analysis.interpretations[0].program = program
    analysis.interpretations[0].capability_ids = [capability["id"]]
    accepted = validate_requirement_analysis(analysis, obligations, [capability["id"]])
    assert accepted.interpretations[0].program.input_domain == inputs
    assert (
        accepted.interpretations[0].program.input_domain["properties"]["native_arguments"]
        == native_schema
    )


def test_mapping_references_never_claim_task_success(surface, functions):
    obligations = requirement_inputs([surface.queries[0]])
    mappings = [
        FunctionCoverage(obligation_id=item.obligation_id, function_names=[functions[0]["name"]])
        for item in obligations
    ]
    report = validate_function_coverage(mappings, obligations, functions)
    assert report.valid and report.structurally_complete
    assert report.counts.mapped == len(obligations)
    assert report.counts.function_count == len(functions)
    assert report.outcome_status == "not_checked"
    assert "task correctness" in report.limitations[0]
    assert CoverageReport.model_validate_json(report.model_dump_json()) == report
    assert "passed" not in report.model_dump_json()
    with pytest.raises(ValidationError, match="Extra inputs"):
        RequirementAnalysis.model_validate(
            {**declared_analysis(obligations).model_dump(), "task_success": True}
        )
    with pytest.raises(ValidationError):
        CoverageReport.model_validate({**report.model_dump(), "outcome_status": "passed"})


def test_missing_unknown_and_duplicate_mappings_are_inspectable_failures(surface, functions):
    obligations = requirement_inputs([surface.queries[0]])
    mappings = [
        FunctionCoverage(obligation_id=item.obligation_id, function_names=[functions[0]["name"]])
        for item in obligations
    ]
    missing = validate_function_coverage(mappings[:-1], obligations, functions)
    assert not missing.valid and not missing.structurally_complete
    assert missing.counts.missing == 1 and missing.gaps
    unknown = mappings[0].model_copy(update={"function_names": ["unexecuted_negative_control"]})
    invalid = validate_function_coverage([unknown, *mappings[1:]], obligations, functions)
    assert not invalid.valid and invalid.counts.invalid == 1
    assert "unknown or empty function reference" in invalid.gaps[0]
    duplicate = validate_function_coverage([*mappings, mappings[0]], obligations, functions)
    assert not duplicate.structurally_complete
    assert duplicate.counts.invalid == 2
    unrelated = mappings[0].model_copy(update={"obligation_id": "r_000000000000000000"})
    invalid = validate_function_coverage([unrelated, *mappings[1:]], obligations, functions)
    assert invalid.counts.missing == 1 and invalid.counts.invalid == 1


def test_explicit_unsupported_obligations_cannot_be_eligible(surface, functions):
    obligations = requirement_inputs([surface.queries[0]])
    mappings = [
        FunctionCoverage(
            obligation_id=item.obligation_id,
            unsupported_reason="Mapping deliberately left unsupported for contract inspection.",
        )
        for item in obligations
    ]
    report = validate_function_coverage(mappings, obligations, functions)
    assert report.valid and not report.structurally_complete
    assert report.counts.unsupported == len(obligations)
    assert report.outcome_status == "not_checked"
    mappings[0].function_names = [functions[0]["name"]]
    contradictory = validate_function_coverage(mappings, obligations, functions)
    assert not contradictory.valid and contradictory.counts.invalid == 1
    assert "exclusively" in contradictory.gaps[0]

"""Task-interpretation contracts over genuine pilot inputs, with no model stand-ins.

The authored programs exercise the interpretation grammar and deterministic
closure only. They are labelled proposed and are not saved model generations or
independent statements that a weather question was answered correctly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from oak.construction_contracts import (
    RequirementAnalysis,
    RequirementInterpretation,
    requirement_inputs,
)
from oak.learning import (
    actionable_learning_gaps,
    candidate_rank,
    compare_fresh_runs,
    freeze_task_ir,
)
from oak.learning_contracts import SemanticField, TaskOperation, TaskProgram
from oak.task_context import TaskSurface, sample_construction

PROJECT = Path(__file__).parents[1]


def actual_surface() -> TaskSurface:
    return TaskSurface.model_validate(
        json.loads((PROJECT / "config/weather-surface.json").read_text())
    )


def interpreted_program() -> TaskProgram:
    """A finite contract input matching the pilot's record/filter/count shape."""
    return TaskProgram(
        fields=[
            SemanticField(
                id="daily_high",
                description="Daily forecast high temperature",
                value_type="number",
                unit="C",
                grain="forecast date and location",
            )
        ],
        operations=[
            TaskOperation(id="days", operator="read", fields=["daily_high"], result_kind="records"),
            TaskOperation(
                id="matching",
                operator="filter",
                inputs=["days"],
                fields=["daily_high"],
                result_kind="records",
                parameters={"threshold": "$input.threshold"},
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
        input_domain={"threshold": "number"},
        observation_contract="Count qualifying forecast dates in the requested scope.",
    )


def test_task_bank_retains_all_literal_inputs_and_mechanical_subtasks():
    surface = actual_surface()
    inputs = requirement_inputs(
        [query for query in surface.queries if query.split == "construction"]
    )
    analysis = RequirementAnalysis(
        scope_summary=surface.description,
        interpretations=[
            RequirementInterpretation(
                obligation_id=item.obligation_id,
                case_id=item.case_id,
                interpretation=item.text,
                required_outputs=[item.text],
                program=interpreted_program() if index == 0 else None,
            )
            for index, item in enumerate(inputs)
        ],
    )
    bank = freeze_task_ir(surface.description, inputs, analysis)
    literal = [item for item in bank.obligations if item.derivation_rule == "literal_requirement"]
    assert {item.obligation_id for item in literal} == {item.obligation_id for item in inputs}
    subtasks = [item for item in bank.obligations if item.group == "subtask"]
    assert {item.program.result for item in subtasks} == {"days", "matching"}
    assert all(item.mandatory for item in subtasks)
    assert all(
        item.oracle_ref is None and item.semantic_status == "proposed" for item in bank.obligations
    )
    assert all(item.program.input_domain == {"threshold": "number"} for item in subtasks)
    assert all(
        item.case_id not in {query.id for query in surface.queries if query.split != "construction"}
        for item in bank.obligations
    )
    assert freeze_task_ir(surface.description, inputs, analysis) == bank


def test_exploration_is_bounded_and_does_not_become_required():
    surface = actual_surface()
    inputs = requirement_inputs(
        [query for query in surface.queries if query.split == "construction"]
    )
    analysis = RequirementAnalysis(
        scope_summary=surface.description,
        interpretations=[
            RequirementInterpretation(
                obligation_id=item.obligation_id,
                case_id=item.case_id,
                interpretation=item.text,
                required_outputs=[item.text],
                program=interpreted_program(),
            )
            for item in inputs
        ],
    )
    bank = freeze_task_ir(surface.description, inputs, analysis)
    exploratory = [item for item in bank.obligations if not item.mandatory]
    assert len(exploratory) == 128 and bank.exploration_omitted > 0
    assert all(len(item.program.operations) <= 4 for item in exploratory)
    assert len({item.obligation_id for item in bank.obligations}) == len(bank.obligations)


def test_program_rejects_future_references_and_unknown_semantic_fields():
    malformed = interpreted_program().model_dump()
    malformed["operations"][0]["inputs"] = ["count"]
    with pytest.raises(ValidationError, match="acyclic"):
        TaskProgram.model_validate(malformed)
    malformed = interpreted_program().model_dump()
    malformed["operations"][0]["fields"] = ["not_declared"]
    with pytest.raises(ValidationError, match="unknown semantic field"):
        TaskProgram.model_validate(malformed)


def test_unseen_first_sampling_has_attributable_history_and_preserves_splits():
    surface = actual_surface()
    seen = []
    pool = {query.id for query in surface.queries if query.split == "construction"}
    for index in range(5):
        receipt = sample_construction(surface, index, seen_query_ids=seen)
        assert receipt.strategy == "seeded_unseen_first"
        assert set(receipt.selected_query_ids).issubset(pool)
        if len(pool - set(seen)) >= receipt.sample_size:
            assert not set(receipt.selected_query_ids).intersection(seen)
        seen = sorted(set(seen) | set(receipt.selected_query_ids))
    assert set(seen) == pool
    with pytest.raises(ValueError, match="non-construction"):
        sample_construction(
            surface, 0, seen_query_ids=[next(q.id for q in surface.queries if q.split == "heldout")]
        )


def test_cost_and_small_schema_do_not_outweigh_a_known_regression():
    kernel = {"schema": {}, "functions": []}
    old = {"known_regressions": 0, "unresolved_obligation_ids": ["a"], "checks": []}
    broken = {"known_regressions": 1, "unresolved_obligation_ids": [], "checks": []}
    assert candidate_rank(old, kernel, measured_cost=10) < candidate_rank(broken, kernel)


def test_fresh_comparison_preserves_separate_outcomes_and_missing_evidence():
    """Explicit status-contract inputs test selection logic, not agent behavior."""
    prior = {
        "a": {"query_id": "a", "status": "complete", "assessment": {"status": "passed"}},
        "b": {"query_id": "b", "status": "complete", "assessment": None},
    }
    current = [{"query_id": "a", "status": "complete", "assessment": {"status": "failed"}}]
    comparison = compare_fresh_runs(prior, current)
    assert comparison == {"failures": ["a"], "regressions": ["a"], "unexecuted_previous": ["b"]}
    current[0]["assessment"] = None
    assert compare_fresh_runs(prior, current)["regressions"] == []


def test_missing_independent_oracle_does_not_hide_actionable_generated_learning():
    root = PROJECT / ".local/artifacts"
    identity = "51c7af49f15db3109573f731f1335321df2693d4e6740d8d5ecb98491381d27d"
    path = root / f"{identity}.json"
    if not path.exists():
        pytest.skip("Actual revised-construction verification receipt unavailable")
    report = json.loads(path.read_text())["data"]
    assert actionable_learning_gaps(report) == [
        "Generate a non-tautological consistency check that references an actual candidate pure function"
    ]
    # Explicit checker-contract input, not a fabricated execution receipt.
    independent_gap_only = {
        "checks": [
            {"dimension": "task", "status": "unknown"},
            {"dimension": "generated", "details": {"contributes_to_learning": True}},
        ]
    }
    assert actionable_learning_gaps(independent_gap_only) == []

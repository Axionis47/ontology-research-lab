"""Task-context boundaries using real project documents and actual task inputs.

The checked-in weather requests are an explicitly authored real-service pilot,
not fabricated weather records or an official benchmark. Negative manifests
below are marked invalid contract inputs, never represented as executed agents.
These checks do not invoke a model or substitute a tool response.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from oak.store import Store
from oak.task_context import (
    QuerySpec,
    TaskSurface,
    build_runtime_context,
    load_task_prompt,
    sample_construction,
)

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def surface() -> TaskSurface:
    """Load the real onboarding configuration without connecting to its service."""
    return TaskSurface.model_validate(
        json.loads((PROJECT / "config/weather-surface.json").read_text())
    )


def test_empty_observations_and_only_selected_query_enter_context(surface: TaskSurface) -> None:
    """A task without supplied evidence cannot inherit other queries or answers."""
    query = surface.queries[0]
    context = build_runtime_context(surface, query, [])
    assert context["query"] == query.query
    assert context["base_prompt"] == surface.base_prompt
    assert context["observations"] == []
    assert context["supplied_facts"] == []
    assert context["procedural_history"] == []
    assert context["history_selection"]["semantic_ranking"] == "not_implemented"
    serialized = json.dumps(context)
    for other in surface.queries[1:]:
        assert other.query not in serialized
    assert "answers" not in context and "references" not in context


def test_supplied_project_document_is_preserved(surface: TaskSurface) -> None:
    """A real document can accompany a request without inventing observations."""
    source = PROJECT / "docs/runtime-method.md"
    configured = surface.model_dump(mode="json")
    document = {"source_ref": str(source), "content": source.read_text()}
    configured["queries"][0]["supplied_documents"] = [document]
    changed = TaskSurface.model_validate(configured)
    context = build_runtime_context(changed, changed.queries[0], [])
    assert context["supplied_facts"] == [document]
    assert context["observations"] == []
    context["supplied_facts"][0]["content"] = "explicit mutation of returned context"
    assert changed.queries[0].supplied_documents[0]["content"] == source.read_text()


def test_sampling_is_reproducible_and_confined_to_construction(surface: TaskSurface) -> None:
    """Round receipts identify actual pool data and independent deterministic draws."""
    pool = {query.id for query in surface.queries if query.split == "construction"}
    first = sample_construction(surface, 0)
    assert first == sample_construction(surface, 0)
    assert first.pool_size == len(pool) == 10
    assert first.sample_size == len(first.selected_query_ids) == 2
    assert set(first.selected_query_ids) <= pool
    reverse = surface.model_copy(deep=True)
    reverse.queries.reverse()
    assert sample_construction(reverse, 0) == first
    receipts = [sample_construction(surface, index) for index in range(5)]
    assert len({receipt.round_seed for receipt in receipts}) == 5
    assert all(set(receipt.selected_query_ids) <= pool for receipt in receipts)
    # Fresh independent draws may overlap; the protocol does not promise five
    # disjoint batches or complete coverage after five rounds.
    assert len({receipt.pool_sha256 for receipt in receipts}) == 1
    with pytest.raises(ValueError, match="nonnegative integer"):
        sample_construction(surface, True)


def test_heldout_changes_do_not_change_construction_sample(surface: TaskSurface) -> None:
    """The sampler's hash and RNG never consume final-query content."""
    first = sample_construction(surface, 0)
    changed = surface.model_copy(deep=True)
    final = next(query for query in changed.queries if query.split == "heldout")
    # This is an explicit protocol mutation, not a claimed new benchmark item.
    final.requirements.append("Retain the source evidence references in the audit record.")
    assert sample_construction(changed, 0) == first
    tiny = surface.model_copy(deep=True)
    tiny.queries = [tiny.queries[0]]
    assert sample_construction(tiny, 0).sample_size == 1
    tiny.queries[0].split = "development"
    with pytest.raises(ValueError, match="at least one construction"):
        sample_construction(tiny, 0)


def test_strict_contract_blocks_labels_and_cross_split_duplicates(surface: TaskSurface) -> None:
    """Controlled invalid inputs cannot add a hidden label or duplicate a task."""
    query = surface.queries[0].model_dump(mode="json")
    query["answer"] = "invalid negative-control field, not a reference answer"
    with pytest.raises(ValidationError, match="Extra inputs"):
        QuerySpec.model_validate(query)
    changed = surface.model_dump(mode="json")
    duplicate = copy.deepcopy(changed["queries"][0])
    duplicate.update(id="explicit-duplicate-negative-control", split="heldout")
    changed["queries"].append(duplicate)
    with pytest.raises(ValidationError, match="identical task inputs"):
        TaskSurface.model_validate(changed)
    changed = surface.model_dump(mode="json")
    changed["limits"]["max_tool_calls"] = "6"
    with pytest.raises(ValidationError):
        TaskSurface.model_validate(changed)


def test_history_must_resolve_and_cannot_cross_final_boundary(
    surface: TaskSurface, tmp_path: Path
) -> None:
    """Real content-addressed storage still refuses an ineligible manifest."""
    with pytest.raises(ValueError, match="artifact resolver"):
        build_runtime_context(surface, surface.queries[0], [], history=["not-an-artifact"])
    store = Store(tmp_path / "artifacts")
    final = next(query for query in surface.queries if query.split == "heldout")
    invalid = store.put(
        "controlled_invalid_episode",
        {
            "format_version": 1,
            "query_id": final.id,
            "split": final.split,
            "query": final.query,
            "status": "not_executed_negative_control",
            "observations": [],
        },
    )
    with pytest.raises(ValueError, match="only construction"):
        build_runtime_context(
            surface, surface.queries[0], [], history=[invalid], resolve_history=store.get
        )
    actual_document = store.put(
        "source_document", {"text": (PROJECT / "docs/runtime-method.md").read_text()}
    )
    with pytest.raises(ValueError, match="episode manifest"):
        build_runtime_context(
            surface, surface.queries[0], [], history=[actual_document], resolve_history=store.get
        )


def test_prompts_are_versioned_general_inputs() -> None:
    """The actual prompt files are readable and obey project writing constraints."""
    for kind in ("runtime", "construction"):
        prompt = load_task_prompt(kind)
        assert prompt.strip()
        assert "\u2014" not in prompt
        assert "weather" not in prompt.casefold()
    with pytest.raises(ValueError, match="prompt kind"):
        load_task_prompt("unknown")


def test_saved_real_starter_history_preserves_route_without_forecast_values() -> None:
    """Inspect a genuine completed starter episode without replaying its answers.

    This optional saved-evidence check uses the actual November 3 pilot receipt.
    It does not copy model artifacts into the test suite or invoke a model/tool.
    """
    from oak.bootstrap import SurfaceEngine

    episode_id = "d2e7d5b040d5c9b790c3c946d649a52ec59cdc2d287f208d3e6228d313f799e2"
    source_root = PROJECT / ".local"
    if not (source_root / "artifacts" / f"{episode_id}.json").is_file():
        pytest.skip("The genuine saved starter episode is not available in this checkout")
    engine = SurfaceEngine(source_root)
    episode = engine.store.get(episode_id)
    data = engine.surface(episode["surface_id"])
    configured = TaskSurface.model_validate(data["configuration"])
    query = next(
        item
        for item in configured.queries
        if item.split == "construction" and item.id != episode["query_id"]
    )
    context = build_runtime_context(
        configured,
        query,
        data["catalog"]["tools"],
        history=[episode_id],
        resolve_history=engine.store.get,
    )
    assert episode["status"] == "complete" and episode["split"] == "construction"
    assert context["history_selection"]["selected_episode_ids"] == [episode_id]
    card = context["procedural_history"][0]
    receipts = [
        (identity, engine.store.get(identity))
        for observation in episode["observations"]
        for identity in observation["receipt_ids"]
    ]
    assert receipts
    assert card["capability_route"] == [receipt["capability_id"] for _, receipt in receipts]
    assert card["receipt_ids"] == [identity for identity, _ in receipts]
    assert context["observations"] == context["supplied_facts"] == []

    def assert_no_answer_payload(value):
        if isinstance(value, dict):
            assert not {"answer", "output", "observations", "forecast"}.intersection(value)
            for child in value.values():
                assert_no_answer_payload(child)
        elif isinstance(value, list):
            for child in value:
                assert_no_answer_payload(child)

    assert_no_answer_payload(context["procedural_history"])

"""Integration checks against authentic, checksum-pinned ToolQA files.

Run ensure_coffee_data once before these tests. No provider, ontology, or agent
is substituted here: these tests cover data integrity, splits, and scorer fidelity.
"""

from __future__ import annotations

import ast
import json
import re
import string
from pathlib import Path

import pytest

from oak.tasks.coffee import (
    DEFAULT_CACHE,
    load_coffee,
    load_reference_answers,
    normalize_answer,
    pilot_splits,
    score_answer,
    source_lock,
)


@pytest.fixture(scope="module")
def coffee() -> dict:
    if not (DEFAULT_CACHE / "coffee_price.csv").is_file():
        pytest.fail(
            "Genuine Coffee corpus is missing. Run: "
            "uv run python -c 'from oak.tasks.coffee import ensure_coffee_data; "
            "ensure_coffee_data()'"
        )
    return load_coffee()


def test_real_corpus_and_question_contract(coffee: dict) -> None:
    """The actual corpus parses completely and preserves row-level provenance."""
    assert coffee["corpus"]["row_count"] == 5746
    assert len(coffee["task_inputs"]) == 100
    documents = coffee["corpus"]["documents"]
    assert len({document["id"] for document in documents}) == len(documents)
    assert documents[0]["source_ref"].endswith("#row=2")
    assert documents[-1]["source_ref"].endswith("#row=5747")
    rows = [json.loads(document["content"]) for document in documents]
    assert min(row["Date"] for row in rows) == "2000-01-03"
    assert max(row["Date"] for row in rows) == "2022-09-02"
    # Model-facing task inputs contain query text and identifiers, never labels.
    assert all(set(question) == {"id", "query"} for question in coffee["task_inputs"])
    assert "references" not in coffee and "answers" not in coffee


def test_source_questions_resolve_to_genuine_corpus_rows(coffee: dict) -> None:
    """Validate the data join, without treating it as an agent benchmark result."""
    dates = {json.loads(document["content"])["Date"] for document in coffee["corpus"]["documents"]}
    for question in coffee["task_inputs"]:
        match = re.search(r"\d{4}-\d{2}-\d{2}", question["query"])
        assert match is not None
        assert match.group() in dates, question["id"]


@pytest.mark.parametrize(("pilot", "per_split"), [("small", 3), ("expanded", 8)])
def test_pilot_is_disjoint_deterministic_and_stratified(
    coffee: dict, pilot: str, per_split: int
) -> None:
    splits = pilot_splits(pilot=pilot)
    assert splits == pilot_splits(pilot=pilot)
    questions = {question["id"]: question["query"] for question in coffee["task_inputs"]}
    seen = set()
    for role in ("construction", "development", "heldout"):
        ids = splits[role]
        assert len(ids) == per_split
        assert not seen.intersection(ids)
        seen.update(ids)
        templates = {re.sub(r"\d{4}-\d{2}-\d{2}", "{date}", questions[qid]) for qid in ids}
        assert templates == set(splits["templates"])
    assert not seen.intersection(splits["unused"])
    assert seen.union(splits["unused"]) == set(questions)


def test_official_metric_fidelity_on_actual_reference_answers(coffee: dict) -> None:
    """Compare the adapter with the pinned upstream scorer on genuine label pairs.

    Only the two audited scoring definitions are compiled. The legacy harness,
    its providers, tools, and unrelated code are never imported or executed.
    """
    lock = source_lock()
    source_path = Path(DEFAULT_CACHE) / lock["scorer"]["filename"]
    source = source_path.read_bytes()
    import hashlib

    assert hashlib.sha256(source).hexdigest() == lock["scorer"]["sha256"]
    tree = ast.parse(source)
    scoring_functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in {"normalize_answer", "EM"}
    ]
    assert len(scoring_functions) == 2
    reference_namespace = {"re": re, "string": string}
    exec(
        compile(ast.Module(body=scoring_functions, type_ignores=[]), str(source_path), "exec"),
        reference_namespace,
    )
    labels = list(load_reference_answers().values())
    assert len(labels) == len(coffee["task_inputs"])
    for prediction in labels:
        assert normalize_answer(prediction) == reference_namespace["normalize_answer"](prediction)
        for reference in labels:
            assert score_answer(prediction, reference) == reference_namespace["EM"](
                prediction, reference
            )

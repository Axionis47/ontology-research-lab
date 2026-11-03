"""Task-owned scoring methods, isolated from construction prompts and graph logic."""

from decimal import Decimal, InvalidOperation


def numeric_match(prediction: str, reference: str) -> bool:
    """Compare complete numeric answers without stripping signs or decimal points."""
    try:
        actual, expected = Decimal(prediction.strip()), Decimal(reference.strip())
        return actual.is_finite() and expected.is_finite() and actual == expected
    except InvalidOperation:
        return False


def get_scorer(name: str | None):
    if name is None:
        return None
    if name == "numeric":
        return numeric_match
    if name == "toolqa_exact_match":
        from oak.tasks.coffee import score_answer

        return score_answer
    raise ValueError(f"Unknown task evaluator: {name}")

"""Task-owned scoring methods, isolated from construction prompts and graph logic."""

import hashlib
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


def assess_mcp_episode(store, run_id: str, episode_id: str, query_input: dict) -> dict | None:
    """Apply a registered task adapter to genuine run-owned acquisition evidence.

    Applicability belongs to the adapter. Unrecognized and run-local requests
    remain unchecked. This never calls a model or exposes evaluator objectives
    to the agent. Evaluation failures are separate from execution failures.
    """
    from oak.tasks import weather

    if not weather.supports_query(query_input):
        return None
    episode = store.get(episode_id)
    evaluator_version = hashlib.sha256(weather.EVALUATOR_PATH.read_bytes()).hexdigest()
    receipts = []
    seen = set()
    try:
        for observation in episode["observations"]:
            identities = observation.get("receipt_ids", [])
            if not identities and observation.get("receipt_id"):
                identities = [observation["receipt_id"]]
            for identity in identities:
                if identity in seen:
                    continue
                owned = store.rows(
                    "SELECT id FROM events WHERE run_id=? AND stage='mcp_call' AND artifact_id=?",
                    (run_id, identity),
                )
                if not owned:
                    raise ValueError("Acquisition receipt does not belong to this run")
                receipts.append({**store.get(identity), "evidence_id": identity})
                seen.add(identity)
        evaluation = weather.evaluate_weather_answer(
            episode["query_id"], episode["answer"], receipts
        )
        evaluation["success"] = evaluation["success"] and episode["status"] == "complete"
        status = (
            "unable_to_check"
            if evaluation["status"] == "unscored"
            else ("passed" if evaluation["success"] else "failed")
        )
    except (ValueError, KeyError, TypeError, FileNotFoundError):
        evaluation = {
            "status": "unscored",
            "success": False,
            "reason": "The adapter could not validate the saved acquisition evidence.",
        }
        status = "unable_to_check"
    assessment = {
        "status": status,
        "evaluator": "weather",
        "evaluator_version": evaluator_version,
        "result": evaluation.get("success") if status != "unable_to_check" else None,
        "scope": "Displayed whole-degree daily highs in actual MCP output",
        "evidence_refs": [episode_id, *sorted(seen)],
    }
    receipt = {
        "episode_id": episode_id,
        "run_id": run_id,
        "model_calls": 0,
        "evaluation": evaluation,
        "assessment": assessment,
    }
    identity = store.event(
        run_id, "task_evaluation", status, "Independent task adapter check", receipt
    )
    return {**assessment, "assessment_id": identity}

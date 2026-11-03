"""Check the weather adapter using a preserved genuine MCP response.

The receipt was acquired from the pinned upstream server and public services.
Deliberately removing source content tests rejection, not a simulated service.
No test substitutes a canned model response for an agent execution.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from oak.task_context import TaskSurface, sample_construction
from oak.tasks.weather import evaluate_weather_answer, parse_daily_forecast

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def real_receipts() -> list[dict]:
    lock = json.loads((ROOT / "data/sources/weather-source.lock.json").read_text())
    record = lock["preflight_receipt"]
    raw = (ROOT / record["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == record["sha256"]
    evidence = json.loads(raw)
    assert evidence["server_info"] == {"name": "weather-mcp", "version": "1.35.7"}
    return evidence["calls"]


def test_actual_daily_receipt_preserves_dates_units_and_values(real_receipts: list[dict]) -> None:
    forecast = parse_daily_forecast(real_receipts[1])
    assert forecast["timezone"] == "Europe/Berlin"
    assert forecast["latitude"] == 52.52
    assert forecast["longitude"] == 13.405
    assert forecast["days"] == [
        {"date": "2026-11-03", "high": 10, "unit": "C"},
        {"date": "2026-11-04", "high": 10, "unit": "C"},
        {"date": "2026-11-05", "high": 9, "unit": "C"},
    ]


def test_receipt_grounded_numeric_scoring(real_receipts: list[dict]) -> None:
    correct = evaluate_weather_answer("construction-01", "2", real_receipts)
    assert correct["status"] == "scored"
    assert correct["success"]
    assert correct["reference"] == "2"
    assert not evaluate_weather_answer("construction-01", "3", real_receipts)["success"]
    assert not evaluate_weather_answer("construction-01", "2 days", real_receipts)["success"]


def test_other_locations_cannot_borrow_the_berlin_forecast(real_receipts: list[dict]) -> None:
    result = evaluate_weather_answer("construction-03", "2", real_receipts)
    assert result["status"] == "unscored"
    assert result["reference"] is None
    assert not result["success"]


def test_missing_real_daily_value_is_not_a_zero_count(real_receipts: list[dict]) -> None:
    incomplete = deepcopy(real_receipts)
    text = incomplete[1]["output"]["content"][0]["text"]
    incomplete[1]["output"]["content"][0]["text"] = text.replace(
        "**Temperature:** High 9°C / Low 4°C\n", "", 1
    )
    with pytest.raises(ValueError, match="daily high"):
        parse_daily_forecast(incomplete[1])
    score = evaluate_weather_answer("construction-01", "0", incomplete)
    assert score["status"] == "unscored"
    assert score["reference"] is None
    assert not score["success"]


def test_missing_execution_clock_cannot_reinterpret_old_forecast(real_receipts: list[dict]) -> None:
    incomplete = deepcopy(real_receipts[1])
    del incomplete["started_at"]
    with pytest.raises(ValueError, match="execution timestamp"):
        parse_daily_forecast(incomplete)


def test_authored_pool_has_fixed_disjoint_splits_and_fresh_draws() -> None:
    surface = TaskSurface.model_validate_json((ROOT / "config/weather-surface.json").read_text())
    assert {
        role: sum(q.split == role for q in surface.queries)
        for role in ("construction", "development", "heldout")
    } == {
        "construction": 10,
        "development": 2,
        "heldout": 3,
    }
    assert all(not query.supplied_documents for query in surface.queries)
    first, second = sample_construction(surface, 0), sample_construction(surface, 1)
    assert first.sample_size == second.sample_size == 2
    assert first.pool_sha256 == second.pool_sha256
    assert first.round_seed != second.round_seed
    assert all(item.startswith("construction-") for item in first.selected_query_ids)
    assert first == sample_construction(surface, 0)

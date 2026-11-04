"""Evaluate an authored weather pilot against genuine MCP execution receipts.

This adapter never supplies an ontology, function implementation, or forecast to
the agent. It interprets the pinned upstream server's displayed whole-degree daily
highs for independent scoring. Missing coverage is unscored, never a zero count.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT = Path(__file__).resolve().parents[3]
EVALUATOR_PATH = PROJECT / "config/weather-evaluator.json"
SURFACE_PATH = PROJECT / "config/weather-surface.json"
SOURCE_LOCK = PROJECT / "data/sources/weather-source.lock.json"


def supports_query(query_input: dict[str, Any]) -> bool:
    """Bind the evaluator only to the exact registered pilot request contract.

    An ad hoc question never acquires a reference objective through an ID or
    similar wording. This check stays in the task adapter, outside agent input.
    """
    if query_input.get("split") == "inference":
        return False
    from oak.task_context import QuerySpec

    try:
        candidate = QuerySpec.model_validate(query_input)
    except ValueError:
        return False
    configured = json.loads(SURFACE_PATH.read_text())["queries"]
    return any(candidate == QuerySpec.model_validate(item) for item in configured)


_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_DAY_HEADING = re.compile(r"^## ([A-Za-z]+), ([A-Za-z]+) (\d{1,2})\s*$", re.MULTILINE)
_HIGH = re.compile(
    r"^\*\*Temperature:\*\* High (-?\d+)°([CF])(?: / Low -?\d+°[CF])?\s*$", re.MULTILINE
)
_LOCATION = re.compile(r"^\*\*Location:\*\* (-?\d+(?:\.\d+)?), (-?\d+(?:\.\d+)?)\s*$", re.MULTILINE)


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Receipt must include an actual ISO execution timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Receipt timestamp must include its timezone")
    return parsed


def _text_output(receipt: dict[str, Any]) -> str:
    if receipt.get("status") != "completed":
        raise ValueError("MCP call did not complete successfully")
    output = receipt.get("output", {})
    if not isinstance(output, dict) or output.get("isError"):
        raise ValueError("MCP output reports an error")
    blocks = output.get("content", [])
    texts = [block["text"] for block in blocks if block.get("type") == "text"]
    if not texts:
        raise ValueError("MCP output has no actual text content")
    return "\n".join(texts)


def _tool_name(receipt: dict[str, Any]) -> str:
    return str(receipt.get("capability_id", receipt.get("tool", ""))).rsplit("/", 1)[-1]


def _arguments(receipt: dict[str, Any]) -> dict[str, Any]:
    """Read bridge args or the preserved native-SDK preflight's arguments."""
    value = receipt.get("args", receipt.get("arguments", {}))
    if not isinstance(value, dict):
        raise ValueError("Receipt arguments must be a JSON object")
    return value


def parse_daily_forecast(receipt: dict[str, Any]) -> dict[str, Any]:
    """Read complete daily highs from a real weather-mcp 1.35.7 call receipt.

    Dates in the native output omit their year. Resolve them against the recorded
    call clock in the returned IANA timezone, and reject midnight-crossing calls.
    Require every requested date and high instead of trusting the header count.
    The source rounds temperatures, so these are displayed values, not recovered
    precision or observed future weather. No network call occurs in this parser.
    """
    if _tool_name(receipt) != "get_forecast":
        raise ValueError("Receipt is not a get_forecast invocation")
    arguments = _arguments(receipt)
    if arguments.get("source") != "openmeteo" or arguments.get("granularity", "daily") != "daily":
        raise ValueError("Evaluator requires an explicit Open-Meteo daily forecast")
    if arguments.get("compare_models") or arguments.get("ensemble_spread"):
        raise ValueError("Model comparison and ensemble results have different semantics")
    days = arguments.get("days", 7)
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 16:
        raise ValueError("Forecast day count must be an integer in the provider range")
    text = _text_output(receipt)
    if (
        text.count("# Weather Forecast (Daily)") != 1
        or "*Data source: Open-Meteo (Global)*" not in text
    ):
        raise ValueError("Output is not the pinned Open-Meteo daily format")
    zones = re.findall(r"^\*\*Timezone:\*\* (\S+)\s*$", text, re.MULTILINE)
    headers = re.findall(r"^\*\*Forecast Days:\*\* (\d+)\s*$", text, re.MULTILINE)
    locations = _LOCATION.findall(text)
    if len(zones) != 1 or headers != [str(days)] or len(locations) != 1:
        raise ValueError("Forecast metadata is missing, conflicting, or incomplete")
    zone = ZoneInfo(zones[0])
    started = _timestamp(receipt.get("started_at"))
    finished = _timestamp(receipt.get("finished_at"))
    start_date = started.astimezone(zone).date()
    if finished < started or finished.astimezone(zone).date() != start_date:
        raise ValueError("Execution clock crosses a local date boundary or runs backward")
    latitude, longitude = map(float, locations[0])
    for name, actual in (("latitude", latitude), ("longitude", longitude)):
        if name in arguments and abs(float(arguments[name]) - actual) > 0.000051:
            raise ValueError("Forecast location differs from its actual call arguments")
    headings = list(_DAY_HEADING.finditer(text))
    if len(headings) != days:
        raise ValueError("Requested daily coverage is incomplete")
    records = []
    for index, heading in enumerate(headings):
        date = start_date + timedelta(days=index)
        expected = (_WEEKDAYS[date.weekday()], _MONTHS[date.month - 1], str(date.day))
        if heading.groups() != expected:
            raise ValueError("Forecast dates are missing, duplicated, stale, or out of order")
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        highs = _HIGH.findall(text[heading.end() : end])
        if len(highs) != 1:
            raise ValueError("A requested date lacks a unique daily high")
        value, unit = highs[0]
        records.append({"date": date.isoformat(), "high": int(value), "unit": unit})
    if len({row["unit"] for row in records}) != 1:
        raise ValueError("Daily highs use inconsistent units")
    raw_hash = hashlib.sha256(json.dumps(receipt["output"], sort_keys=True).encode()).hexdigest()
    return {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": zones[0],
        "start_date": start_date.isoformat(),
        "days": records,
        "started_at": receipt["started_at"],
        "finished_at": receipt["finished_at"],
        "evidence_id": receipt.get("evidence_id"),
        "output_sha256": raw_hash,
    }


def _location_matches(
    objective: dict[str, Any], receipt: dict[str, Any], receipts: list[dict[str, Any]]
) -> bool:
    """Check the requested point or an actual named-place resolution chain."""
    expected = objective["location"]
    arguments = _arguments(receipt)
    if "latitude" in expected:
        return all(
            name in arguments and abs(float(arguments[name]) - expected[name]) < 1e-7
            for name in ("latitude", "longitude")
        )
    city = expected["city_name"].strip().casefold()
    if str(arguments.get("city_name", "")).strip().casefold() == city:
        return "latitude" not in arguments and "longitude" not in arguments
    if "latitude" not in arguments or "longitude" not in arguments:
        return False
    for search in receipts:
        if _tool_name(search) != "search_location":
            continue
        if str(_arguments(search).get("query", "")).strip().casefold() != city:
            continue
        try:
            if _timestamp(search.get("finished_at")) > _timestamp(receipt.get("started_at")):
                continue
            text = _text_output(search)
        except ValueError:
            continue
        matches = re.findall(r"\*Latitude: (-?\d+(?:\.\d+)?), Longitude: (-?\d+(?:\.\d+)?)\*", text)
        # The native response also displays coordinates rounded to four decimal
        # places. Using that displayed precision remains a valid route.
        if any(
            abs(float(lat) - float(arguments["latitude"])) <= 0.000051
            and abs(float(lon) - float(arguments["longitude"])) <= 0.000051
            for lat, lon in matches
        ):
            return True
    return False


def evaluate_weather_answer(
    query_id: str,
    prediction: str,
    receipts: list[dict[str, Any]],
    *,
    evaluator_path: Path = EVALUATOR_PATH,
) -> dict[str, Any]:
    """Score a complete numeric answer against matching real MCP observations.

    Evaluator-only objectives must not enter agent context. Failed or incomplete
    acquisition yields success=False and status=unscored, never a fabricated
    reference. This checks receipt-grounded reasoning, not meteorological truth.
    """
    manifest = json.loads(Path(evaluator_path).read_text())
    objective = manifest["objectives"][query_id]
    forecasts = []
    errors = []
    for receipt in receipts:
        if _tool_name(receipt) != "get_forecast":
            continue
        try:
            if not _location_matches(objective, receipt, receipts):
                continue
            forecast = parse_daily_forecast(receipt)
            if len(forecast["days"]) != objective["days"]:
                raise ValueError("Forecast interval differs from the task's requested interval")
            if any(day["unit"] != objective["unit"] for day in forecast["days"]):
                raise ValueError("Reported units differ from the requested display units")
            forecasts.append(forecast)
        except (ValueError, KeyError, TypeError, OverflowError) as error:
            errors.append(str(error))
    if not forecasts:
        return {
            "status": "unscored",
            "success": False,
            "reference": None,
            "reason": "; ".join(errors) or "No matching successful forecast receipt",
        }
    if any(item["days"] != forecasts[0]["days"] for item in forecasts[1:]):
        return {
            "status": "unscored",
            "success": False,
            "reference": None,
            "reason": "Matching forecast receipts contain conflicting values or dates",
        }
    values = [day["high"] for day in forecasts[0]["days"]]
    if objective["operation"] == "count_at_least":
        reference = sum(value >= objective["threshold"] for value in values)
    elif objective["operation"] == "maximum":
        reference = max(values)
    else:
        raise ValueError("Unsupported weather scoring operation")
    try:
        actual = Decimal(prediction.strip())
        success = actual.is_finite() and actual == Decimal(reference)
    except (InvalidOperation, AttributeError):
        success = False
    return {
        "status": "scored",
        "success": success,
        "reference": str(reference),
        "evaluator_version": manifest["version"],
        "query_id": query_id,
        "forecast": forecasts[0],
        "scope": "Displayed whole-degree daily highs in actual MCP output",
    }

"""Opt-in checks against the installed upstream weather MCP and real services.

Set OAK_LIVE_MCP_TESTS=1 after installing the package pinned by the weather
source lock. Calls use the official SDK, actual server processes, and actual
provider responses. Invalid arguments and configuration changes are explicit
negative controls; no response or service is mocked. No model is invoked.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

from oak.bootstrap import SurfaceEngine
from oak.mcp_bridge import MCPBridge, MCPBridgeError
from oak.store import Store
from oak.task_context import TaskSurface

PROJECT = Path(__file__).resolve().parents[1]
SURFACE = PROJECT / "config/weather-surface.json"


@pytest.fixture(scope="module")
def live_weather():
    """Load the real verification helper and isolate actual server environment."""
    if os.environ.get("OAK_LIVE_MCP_TESTS") != "1":
        pytest.skip("Set OAK_LIVE_MCP_TESTS=1 to execute the genuine weather MCP server")
    spec = importlib.util.spec_from_file_location(
        "oak_live_mcp_verification", PROJECT / "scripts/verify_mcp_slice.py"
    )
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    environment_names = (
        "OAK_WEATHER_ENABLED_TOOLS",
        "OAK_WEATHER_UNITS",
        "OAK_WEATHER_ANALYTICS",
        "OAK_WEATHER_LIGHTNING_PREWARM",
        "OAK_WEATHER_DOTENV_PATH",
    )
    previous = {name: os.environ.get(name) for name in environment_names}
    try:
        os.environ.update(helper.configure_weather_environment())
        helper.verify_package()
        yield helper
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _bridge(helper, root: Path) -> tuple[MCPBridge, Store, dict, str]:
    """Onboard an actual catalog and bind a separate validation run to it."""
    onboarding = helper.onboard(SURFACE, root)
    engine = SurfaceEngine(root)
    data = engine.surface(onboarding["surface_id"])
    surface = TaskSurface.model_validate(data["configuration"])
    run_id = engine.store.create_run(
        onboarding["surface_id"],
        "live_mcp_contract_check",
        {"catalog_id": data["catalog"]["catalog_id"], "model_calls": 0},
    )
    return (
        MCPBridge(surface.servers, engine.store, run_id, expected_catalog=data["catalog"]),
        engine.store,
        data["catalog"],
        run_id,
    )


def test_real_forecast_call_and_persisted_source_evidence(live_weather, tmp_path: Path) -> None:
    """Actual acquisition populates the empty initial context with sourced data."""
    result = live_weather.preflight(SURFACE, tmp_path / "live")
    store = Store(tmp_path / "live")
    initial = store.get(result["initial_context_id"])
    receipt = store.get(result["receipt_id"])
    assert result["model_calls"] == 0
    assert initial["observations"] == initial["supplied_facts"] == []
    assert receipt["status"] == "completed"
    assert receipt["tool_call_attempted"] is True
    assert receipt["capability_id"] == "weather/get_forecast"
    assert receipt["output"]
    assert store.get(receipt["dispatch_evidence_id"])["capability_id"] == receipt["capability_id"]
    assert store.get(receipt["live_catalog_evidence_id"])["tools"]
    assert len(result["forecast"]["days"]) == 3
    assert {day["unit"] for day in result["forecast"]["days"]} == {"C"}


def test_unknown_capability_and_invalid_input_never_dispatch(live_weather, tmp_path: Path) -> None:
    """The actual discovered contract rejects invalid requests before tool calls."""
    bridge, store, _, run_id = _bridge(live_weather, tmp_path / "live")
    unknown = bridge.invoke("weather/undeclared_negative_control", {})
    invalid = bridge.invoke("weather/get_forecast", {"days": "three"})
    for receipt in (unknown, invalid):
        assert receipt["status"] == "failed"
        assert receipt["tool_call_attempted"] is False
        assert receipt["output"] is None
        assert "dispatch_evidence_id" not in receipt
        assert store.get(receipt["evidence_id"])["error"] == receipt["error"]
    assert not store.rows(
        "SELECT id FROM events WHERE run_id=? AND stage='mcp_dispatch'", (run_id,)
    )
    store.set_run(
        run_id,
        "completed",
        result={"verified_predispatch_failures": [unknown["evidence_id"], invalid["evidence_id"]]},
    )


def test_actual_environment_semantic_change_requires_new_catalog(
    live_weather, tmp_path: Path
) -> None:
    """Changing the genuine server's default units invalidates its pinned contract."""
    bridge, store, original, run_id = _bridge(live_weather, tmp_path / "live")
    previous = os.environ["OAK_WEATHER_UNITS"]
    try:
        os.environ["OAK_WEATHER_UNITS"] = "imperial"
        receipt = bridge.invoke(
            "weather/get_forecast",
            {"latitude": 52.52, "longitude": 13.405, "days": 3},
        )
    finally:
        os.environ["OAK_WEATHER_UNITS"] = previous
    assert receipt["status"] == "failed"
    assert receipt["tool_call_attempted"] is False
    assert receipt["observed_contract_id"] != receipt["contract_id"]
    assert "changed since discovery" in receipt["error"]["message"]
    observed = store.get(receipt["live_catalog_evidence_id"])
    before = next(tool for tool in original["tools"] if tool["id"] == "weather/get_forecast")
    after = next(tool for tool in observed["tools"] if tool["id"] == before["id"])
    assert before["input_schema"] == after["input_schema"]
    assert before["output_schema"] == after["output_schema"]
    store.set_run(run_id, "completed", result={"verified_drift_receipt": receipt["evidence_id"]})


def test_real_tool_removal_retains_partial_discovery_evidence(live_weather, tmp_path: Path) -> None:
    """The upstream server omits a configured tool and discovery fails explicitly."""
    configuration = json.loads(SURFACE.read_text())
    configuration["servers"][0]["args"] = [str(live_weather.PACKAGE / "dist/index.js")]
    surface = TaskSurface.model_validate(configuration)
    store = Store(tmp_path / "live")
    run_id = store.create_run(
        "weather-removal-check", "live_mcp_discovery_check", {"model_calls": 0}
    )
    previous = os.environ["OAK_WEATHER_ENABLED_TOOLS"]
    try:
        os.environ["OAK_WEATHER_ENABLED_TOOLS"] = "search_location"
        with pytest.raises(MCPBridgeError) as failure:
            MCPBridge(surface.servers, store, run_id).discover()
    finally:
        os.environ["OAK_WEATHER_ENABLED_TOOLS"] = previous
    evidence = store.get(failure.value.evidence_id)
    assert evidence["status"] == "failed"
    assert evidence["error"]["code"] == "discovery_failed"
    assert "get_forecast" in evidence["error"]["message"]
    server = evidence["servers"][0]
    assert server["initialize"]["serverInfo"]["name"] == "weather-mcp"
    actual_tools = {tool["name"] for page in server["tool_pages"] for tool in page["tools"]}
    assert "search_location" in actual_tools and "get_forecast" not in actual_tools
    store.set_run(
        run_id, "completed", result={"verified_discovery_failure": failure.value.evidence_id}
    )

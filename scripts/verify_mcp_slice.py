"""Onboard/probe the real weather server or score an existing saved episode.

No command in this script calls a model. Install the pinned upstream package with
``npm install --prefix .local/weather-mcp --ignore-scripts --no-audit --no-fund
@dangahagan/weather-mcp@1.35.7`` before onboarding. The setup remains local to the
pilot and does not replace the project's Python dependency lock.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from oak.bootstrap import SurfaceEngine
from oak.mcp_bridge import MCPBridge
from oak.store import Store
from oak.task_context import TaskSurface, build_runtime_context, sample_construction
from oak.tasks.weather import evaluate_weather_answer, parse_daily_forecast

PROJECT = Path(__file__).resolve().parents[1]
PACKAGE = PROJECT / ".local/weather-mcp/node_modules/@dangahagan/weather-mcp"


def configure_weather_environment() -> dict[str, str]:
    """Set the reviewed nonsecret defaults without replacing explicit settings."""
    defaults = {
        "OAK_WEATHER_ENABLED_TOOLS": "get_forecast,search_location",
        "OAK_WEATHER_UNITS": "metric",
        "OAK_WEATHER_ANALYTICS": "false",
        "OAK_WEATHER_LIGHTNING_PREWARM": "false",
        "OAK_WEATHER_DOTENV_PATH": str(PROJECT / ".local/weather-mcp/no-env-file"),
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    return defaults


def verify_package() -> dict:
    """Check the installed genuine package against the reviewed source lock."""
    lock = json.loads((PROJECT / "data/sources/weather-source.lock.json").read_text())
    if not (PACKAGE / "package.json").is_file():
        raise ValueError("Install @dangahagan/weather-mcp@1.35.7 in .local/weather-mcp first")
    installed = json.loads((PACKAGE / "package.json").read_text())
    if installed["name"] != lock["package"] or installed["version"] != lock["package_version"]:
        raise ValueError("Installed weather package differs from the source lock")
    files = {
        str(path.relative_to(PACKAGE)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(PACKAGE.rglob("*"))
        if path.is_file()
    }
    digest = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if digest != lock["installed_tree_sha256"]:
        raise ValueError("Installed weather source tree changed from the reviewed package")
    return {"package": installed["name"], "version": installed["version"], "tree_sha256": digest}


def onboard(surface_path: Path, root: Path) -> dict:
    """Create a genuine discovered surface, with no model call or prefetched answer."""
    configure_weather_environment()
    package = verify_package()
    configuration = json.loads(surface_path.read_text())
    for server in configuration["servers"]:
        if server["name"] == "weather":
            server["args"] = [str(PACKAGE / "dist/index.js")]
    result = SurfaceEngine(root).onboard(configuration)
    return {**result, "package": package, "model_calls": 0}


def preflight(surface_path: Path, root: Path) -> dict:
    """Execute a real read-only transport probe and retain all source evidence."""
    onboarding = onboard(surface_path, root)
    engine = SurfaceEngine(root)
    data = engine.surface(onboarding["surface_id"])
    surface = TaskSurface.model_validate(data["configuration"])
    store = engine.store
    run_id = store.create_run(
        onboarding["surface_id"],
        "weather_transport_probe",
        {
            "package": onboarding["package"],
            "scope": "Real MCP, no model or benchmark execution",
        },
    )
    try:
        bridge = MCPBridge(surface.servers, store, run_id, expected_catalog=data["catalog"])
        context = build_runtime_context(surface, "construction-01", data["catalog"]["tools"])
        context_id = store.put("initial_task_context", context)
        if context["observations"] or context["procedural_history"] or context["supplied_facts"]:
            raise ValueError("Bootstrap context unexpectedly contains evidence or history")
        receipt = bridge.invoke(
            "weather/get_forecast",
            {
                "latitude": 52.52,
                "longitude": 13.405,
                "days": 3,
                "granularity": "daily",
                "source": "openmeteo",
                "units": "metric",
                "detail": "standard",
                "include_precipitation_probability": False,
            },
        )
        forecast = parse_daily_forecast(receipt)
        result = {
            "onboarding": onboarding,
            "run_id": run_id,
            "model_calls": 0,
            "initial_context_id": context_id,
            "receipt_id": receipt["evidence_id"],
            "forecast": forecast,
            "sampling_receipts": [
                sample_construction(surface, index).model_dump() for index in range(3)
            ],
            "scope": "Transport, displayed-data parsing, and empty bootstrap context only",
        }
        store.set_run(run_id, "completed", result=result)
        return result
    except Exception as error:
        store.set_run(run_id, "failed", error=f"{type(error).__name__}: {error}")
        raise


def evaluate_episode(episode_id: str, root: Path) -> dict:
    """Score a saved real episode, loading its actual hash-verified MCP receipts."""
    store = Store(root)
    episode = store.get(episode_id)
    runs = [
        row
        for row in store.rows(
            "SELECT id,result_id FROM runs WHERE kind='mcp_episode' AND result_id IS NOT NULL"
        )
        if store.get(row["result_id"]).get("episode_id") == episode_id
    ]
    if len(runs) != 1:
        raise ValueError("Episode must belong to exactly one recorded agent run")
    run_id = runs[0]["id"]
    receipts = []
    seen = set()
    for observation in episode["observations"]:
        identities = observation.get("receipt_ids", [])
        if not identities and observation.get("receipt_id"):
            identities = [observation["receipt_id"]]
        for identity in identities:
            if identity not in seen:
                if not store.rows(
                    "SELECT id FROM events WHERE run_id=? AND stage='mcp_call' AND artifact_id=?",
                    (run_id, identity),
                ):
                    raise ValueError("Forecast receipt does not belong to this episode's execution")
                receipts.append({**store.get(identity), "evidence_id": identity})
                seen.add(identity)
    score = evaluate_weather_answer(episode["query_id"], episode["answer"], receipts)
    score["success"] = score["success"] and episode["status"] == "complete"
    result = {"episode_id": episode_id, "run_id": run_id, "model_calls": 0, "evaluation": score}
    result["evaluation_id"] = store.put("weather_evaluation", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("env", "onboard", "preflight", "evaluate"))
    parser.add_argument("--surface", type=Path, default=PROJECT / "config/weather-surface.json")
    parser.add_argument("--root", type=Path, default=PROJECT / ".local")
    parser.add_argument("--episode-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "env":
        result = configure_weather_environment()
    elif args.action == "onboard":
        result = onboard(args.surface, args.root)
    elif args.action == "preflight":
        result = preflight(args.surface, args.root)
    else:
        if not args.episode_id:
            parser.error("evaluate requires --episode-id")
        result = evaluate_episode(args.episode_id, args.root)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()

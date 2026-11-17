"""Run the preselected native variants, preserving raw traces and official outcomes."""

from __future__ import annotations

from dataclasses import asdict
from importlib.metadata import distributions, version
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import uuid

from appworld_runtime.session import AppWorldSession
from appworld_runtime.surface import check_inputs, digest, fingerprint_inputs, inventory, read_json, select, write_new
from react_runtime.loop import Config, ReactLoop
from react_runtime.store import RunStore, timestamp

ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "config/appworld_surface.json"
REVIEWS = ROOT / "config/appworld_surface_reviews.json"


def make_selection(root: Path, count: int = 3) -> dict:
    inv = inventory(root)
    selected = select(inv, read_json(REVIEWS), read_json(SURFACE), count)
    selected.update({"created_at": timestamp(), "surface_sha256": digest(SURFACE),
                     "reviews_sha256": digest(REVIEWS), "inventory_sha256": hashlib.sha256(
                         json.dumps(inv, sort_keys=True).encode()).hexdigest()})
    selected["input_hashes"] = fingerprint_inputs(root, [t["task_id"] for t in selected["tasks"]], selected["application"])
    return selected


def validate_selection(root: Path, selection: dict) -> None:
    if selection["surface_sha256"] != digest(SURFACE) or selection["reviews_sha256"] != digest(REVIEWS):
        raise ValueError("Surface configuration changed after selection")
    tasks = selection["tasks"]
    ids = [t["task_id"] for t in tasks]
    if len(ids) < 3 or len(ids) != len(set(ids)):
        raise ValueError("Batch requires at least three distinct tasks")
    expected = select(inventory(root), read_json(REVIEWS), read_json(SURFACE), len(ids))
    for key in ("application", "scenario_id", "tasks", "rank", "split_sha256"):
        if selection[key] != expected[key]:
            raise ValueError(f"Selection is stale or changed: {key}")
    check_inputs(root, selection["input_hashes"])


def configured_model() -> tuple[list[str], dict]:
    config = tomllib.loads((ROOT / "config/models.toml").read_text())["ollama"]
    executable = shutil.which("ollama")
    if not executable:
        raise RuntimeError("Configured Ollama CLI is unavailable")
    listed = subprocess.run([executable, "list"], capture_output=True, text=True, timeout=15)
    if listed.returncode:
        raise RuntimeError("Configured Ollama server is unreachable: " + listed.stderr[:500])
    rows = [line.split() for line in listed.stdout.splitlines()[1:] if line.strip()]
    row = next((r for r in rows if r[0] == config["model"]), None)
    if row is None:
        raise RuntimeError(f"Configured model is not installed: {config['model']}")
    command = [sys.executable, str(ROOT / "react_runtime/ollama.py")]
    return command, {"provider": "ollama", "requested_model": config["model"],
                     "local_model_id_prefix": row[1], "resolved_model": config["model"],
                     "transport": "ollama-http/1", "applied_options": {k: config[k] for k in ("num_ctx", "num_predict", "temperature", "think")},
                     "benchmark": True, "weights_changed": False}


def actor_instructions(info: dict) -> str:
    base = (ROOT / "prompts/react_system.txt").read_text()
    public = {k: info[k] for k in ("supervisor", "task_datetime", "application")}
    return base + "\n\nThis is one autonomous AppWorld task in a simulated world. " \
        "Discover MCP tools, inspect their schemas, then call them with the documented arguments. " \
        "Tool discovery accepts words from names/descriptions; use an empty query and offsets if needed. " \
        "Read paginated results completely when the request says all. " \
        "After making the requested changes, inspect the resulting state. " \
        "Call the discovered supervisor completion tool, then return finish. " \
        "There is no follow-up user conversation. The official evaluator runs after this episode. " \
        "Preserve unrelated state as required by the original task.\nPublic task context: " + json.dumps(public)


def run_batch(root: Path, selection_path: Path, output: Path, config: Config,
              *, model_command=None, model_info=None, session_factory=AppWorldSession) -> dict:
    root = root.resolve()
    selection = read_json(selection_path)
    validate_selection(root, selection)
    if model_command is None:
        model_command, model_info = configured_model()
    config.validate()
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "selection.json", selection)
    batch_id = str(uuid.uuid4())
    manifest = {"batch_id": batch_id, "created_at": timestamp(), "selection_sha256": digest(output / "selection.json"),
                "application": selection["application"], "scenario_id": selection["scenario_id"],
                "task_ids": [t["task_id"] for t in selection["tasks"]],
                "config": asdict(config), "model": model_info, "transport": "official_appworld_mcp_stdio",
                "dependencies": {d.metadata["Name"]: d.version for d in distributions()},
                "kernel_version": None, "mode": "react_baseline", "data_root": str(root)}
    write_new(output / "manifest.json", manifest)
    episodes = []
    for task in selection["tasks"]:
        task_id = task["task_id"]
        print(json.dumps({"event": "episode_start", "task_id": task_id}), flush=True)
        check_inputs(root, selection["input_hashes"])
        directory = output / task_id
        directory.mkdir()
        record = {"task_id": task_id, "execution_status": "SETUP_ERROR", "benchmark_success": None}
        try:
            with session_factory(root=root, task_id=task_id, application=selection["application"],
                    experiment=f"surface_{batch_id}_{task_id}", log_directory=directory / "session") as session:
                if session.info["instruction"] != task["instruction"] or session.info["db_version"] != task["db_version"]:
                    raise ValueError("Activated task differs from the selected native task")
                write_new(directory / "session-info.json", session.info)
                store = RunStore(directory / "react")
                try:
                    loop = ReactLoop(store=store, task=task["instruction"], constraints=[],
                        model_command=model_command, tools=session.tools(), verifier=None,
                        config=config, provider="ollama", model_info=model_info,
                        system_instructions=actor_instructions(session.info),
                        benchmark_adapter={"name": "appworld_mcp", "task_id": task_id,
                            "selection_sha256": manifest["selection_sha256"],
                            "catalog_revision": session.info["catalog_revision"],
                            "appworld_version": session.info["appworld_version"]})
                    result = loop.run()
                    record.update(execution_status=result["status"], steps=result["steps"],
                                  tool_attempts=result["tool_attempts"], trace_complete=result["judge_packet"]["complete"],
                                  trace_directory=str(store.root), judge_packet=result["judge_packet"],
                                  episode_event_head=store.audit()["last_event_sha256"])
                finally:
                    store.close()
                # No evaluator feedback enters the running actor or changes its
                # terminal trace. The linked sidecar is the benchmark authority.
                try:
                    evaluation = session.evaluate()
                    native = evaluation["native_result"]
                    success = native.get("success", native.get("passes_fully"))
                    if not isinstance(success, bool):
                        raise ValueError("Native evaluator did not return a boolean success flag")
                    record["benchmark_success"] = success
                    record["evaluation_status"] = "EVALUATED"
                except Exception as error:
                    evaluation = {"status": "EVALUATION_UNAVAILABLE", "error": f"{type(error).__name__}: {error}"}
                    record["evaluation_status"] = "EVALUATION_UNAVAILABLE"
                evaluation["episode_event_head"] = record["episode_event_head"]
                write_new(directory / "evaluation.json", evaluation)
                record["evaluation_sha256"] = digest(directory / "evaluation.json")
                native_directory = Path(session.info["native_output_directory"])
                if native_directory.exists():
                    shutil.copytree(native_directory, directory / "native")
        except Exception as error:
            record["error"] = f"{type(error).__name__}: {error}"
        try:
            check_inputs(root, selection["input_hashes"])
            record["native_inputs_unchanged"] = True
        except ValueError as error:
            record["native_inputs_unchanged"] = False
            record["input_integrity_error"] = str(error)
        record["artifact_hashes"] = {str(p.relative_to(directory)): digest(p)
                                    for p in sorted(directory.rglob("*")) if p.is_file()}
        write_new(directory / "result.json", record)
        episodes.append(record)
        print(json.dumps({"event": "episode_end", "task_id": task_id,
                          "execution_status": record["execution_status"],
                          "benchmark_success": record["benchmark_success"]}), flush=True)
        if not record["native_inputs_unchanged"]:
            break
    complete = len(episodes) == len(selection["tasks"]) and all(
        r.get("trace_complete") and r.get("evaluation_status") == "EVALUATED" and r["native_inputs_unchanged"] for r in episodes)
    summary = {"batch_id": batch_id, "complete": complete,
               "native_tasks_passed": sum(r["benchmark_success"] is True for r in episodes),
               "native_tasks_evaluated": sum(r.get("evaluation_status") == "EVALUATED" for r in episodes),
               "episodes": episodes, "kernel_constructed": False,
               "construction_ready": complete, "output_directory": str(output.resolve())}
    write_new(output / "summary.json", summary)
    return summary

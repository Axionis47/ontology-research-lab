"""Deterministic native training-scenario selection. Never executes solution code."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

HELPERS = {"supervisor", "api_docs", "admin"}
TASK_ID = re.compile(r"[a-zA-Z0-9]+_[0-9]+\Z")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text())


def write_new(path: Path, value: object) -> None:
    """Publish once; never silently replace a selection or an episode result."""
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o400)


def required_apis(directory: Path) -> list[str]:
    file = directory / "required_apis.json"
    if file.exists():
        values = read_json(file)
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError(f"Invalid required API list: {file}")
        return sorted(set(values))
    # Older native data records this only in the validation program. Inspect its
    # syntax in the trusted selector, never execute it or provide it to the actor.
    tree = ast.parse((directory / "compiled_solution.py").read_text())
    return sorted({f"{n.value.attr}.{n.attr}" for n in ast.walk(tree)
                   if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Attribute)
                   and isinstance(n.value.value, ast.Name) and n.value.value.id == "apis"})


def inventory(root: Path) -> dict:
    data = root.resolve() / "data"
    split = data / "datasets/train.txt"
    ids = split.read_text().splitlines()
    if not ids or len(ids) != len(set(ids)) or any(not TASK_ID.fullmatch(t) for t in ids):
        raise ValueError("Invalid or duplicate native training task IDs")
    grouped = defaultdict(list)
    for task_id in ids:
        folder = data / "tasks" / task_id
        gt = folder / "ground_truth"
        metadata, spec = read_json(gt / "metadata.json"), read_json(folder / "specs.json")
        apis = required_apis(gt)
        applications = sorted(set(read_json(gt / "required_apps.json")) - HELPERS)
        grouped[task_id.split("_")[0]].append({
            "task_id": task_id, "instruction": spec["instruction"],
            "spec_sha256": digest(folder / "specs.json"),
            "native_difficulty": metadata["difficulty"], "required_apis": apis,
            "native_reported_api_count": metadata.get("num_apis"),
            "applications": applications, "db_version": spec["db_version"],
            "evaluator_sha256": digest(gt / "evaluation.py"),
        })
    scenarios = []
    for scenario_id, tasks in sorted(grouped.items()):
        tasks.sort(key=lambda t: t["task_id"])
        apps = sorted({a for t in tasks for a in t["applications"]})
        scenarios.append({"scenario_id": scenario_id, "tasks": tasks,
                          "applications": apps,
                          "native_difficulty": max(t["native_difficulty"] for t in tasks),
                          "required_api_count": len({a for t in tasks for a in t["required_apis"]})})
    return {"split": "train", "split_sha256": digest(split), "scenarios": scenarios}


def select(inv: dict, reviews: dict, surface: dict, count: int = 3) -> dict:
    if surface["dataset_split"] != "train" or inv["split"] != "train":
        raise ValueError("This surface selects only native training tasks")
    if count < max(3, surface["minimum_variants"]):
        raise ValueError("At least three distinct variants are required")
    eligible, decisions = [], []
    for scenario in inv["scenarios"]:
        sid = scenario["scenario_id"]
        reason = None
        if len(scenario["tasks"]) < count:
            reason = "INSUFFICIENT_DISTINCT_VARIANTS"
        elif len(scenario["applications"]) != 1 or any(
                t["applications"] != scenario["applications"] for t in scenario["tasks"]):
            reason = "NOT_ONE_BUSINESS_APPLICATION"
        else:
            review = reviews.get(sid)
            fingerprints = {t["task_id"]: t["spec_sha256"] for t in scenario["tasks"]}
            if not review or review.get("task_specs") != fingerprints:
                raise ValueError(f"Missing/stale semantic surface review: {sid}; inspect inventory before selection")
            if not isinstance(review.get("eligible"), bool) or not review.get("reason"):
                raise ValueError(f"Invalid semantic review: {sid}")
            if not review["eligible"]:
                reason = review["reason"]
        decisions.append({"scenario_id": sid, "eligible": reason is None, "reason": reason,
                          "rank": [scenario["native_difficulty"], scenario["required_api_count"], sid]})
        if reason is None:
            eligible.append(scenario)
    if not eligible:
        raise ValueError("NO_MATCHING_SELECTIVE_UPDATE_SCENARIO")
    selected = min(eligible, key=lambda s: (s["native_difficulty"], s["required_api_count"], s["scenario_id"]))
    return {"surface": surface, "split": "train", "split_sha256": inv["split_sha256"],
            "application": selected["applications"][0], "scenario_id": selected["scenario_id"],
            "rank": [selected["native_difficulty"], selected["required_api_count"], selected["scenario_id"]],
            "tasks": selected["tasks"][:count], "selection_decisions": decisions,
            "semantic_review": reviews[selected["scenario_id"]],
            "selection_algorithm": "native_difficulty_then_api_union_count_then_scenario_id_v1"}


def fingerprint_inputs(root: Path, task_ids: list[str], application: str) -> dict[str, str]:
    """Pin original task/evaluator state and public API contracts, never outputs."""
    data = root.resolve() / "data"
    files = set((data / "base_dbs").rglob("*"))
    files.add(data / "datasets/train.txt")
    for task_id in task_ids:
        files.update((data / "tasks" / task_id).rglob("*"))
    for app in (application, "supervisor", "api_docs"):
        for format_ in ("standard", "function_calling"):
            files.add(data / "api_docs" / format_ / f"{app}.json")
    return {str(p.relative_to(data)): digest(p) for p in sorted(files) if p.is_file()
            and "__pycache__" not in p.parts and not p.name.endswith((".pyc", "-wal", "-shm"))}


def check_inputs(root: Path, fingerprints: dict[str, str]) -> None:
    data = root.resolve() / "data"
    for name, expected in fingerprints.items():
        path = (data / name).resolve()
        if not path.is_relative_to(data) or not path.is_file() or digest(path) != expected:
            raise ValueError(f"Native input changed or unavailable: {name}")

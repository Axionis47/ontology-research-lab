#!/usr/bin/env python3
"""Compare trusted fixture selectors through real, recorded ReAct episodes."""

import argparse
from copy import deepcopy
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from appworld_runtime.surface import write_new
from react_runtime.completion import CHECKER_VERSION, bind_verifier
from react_runtime.loop import Config, ReactLoop, Tool
from react_runtime.repair_scoring import VERSION, digest, protected_sources, score_comparison
from react_runtime.store import RunStore, timestamp

HELPERS = ROOT / "examples/repair_scoring"


def cases():
    base = json.loads((ROOT / "examples/completion_fixture.json").read_text())
    result = []
    for case_id, role in (("relationship_filter", "target"), ("different_links", "variation"),
                          ("single_match", "preservation"), ("empty_target", "preservation")):
        data = {k: deepcopy(base[k]) for k in ("contract", "before")}
        data["contract"]["scope"] = data["before"]["scope"] = "synthetic:repair:" + case_id
        if case_id == "different_links":
            for edge in data["before"]["relations"]:
                if edge["source"] == "ticket:2": edge["target"] = "customer:east"
                if edge["source"] == "ticket:3": edge["target"] = "customer:west"
            for entity in data["before"]["entities"]:
                entity["id"] = "variant:" + entity["id"]
            for edge in data["before"]["relations"]:
                edge["source"], edge["target"] = "variant:" + edge["source"], "variant:" + edge["target"]
            data["before"]["entities"].reverse()
        if case_id in {"single_match", "empty_target"}:
            for entity in data["before"]["entities"]:
                if entity["type"] == "Ticket" and (case_id == "empty_target" or entity["id"] != "ticket:1"):
                    entity["properties"]["status"] = "closed"
        result.append((case_id, role, data))
    return result


def run_episode(root, manifest, case_id, variant, data):
    directory = root / "episodes" / case_id / variant
    directory.mkdir(parents=True)
    state_path = directory / "world.json"
    state_path.write_text(json.dumps(data["before"]))
    input_path = root / "inputs/cases" / (case_id + ".json")
    implementation = manifest["implementations"][variant]
    helper = root / implementation["path"]
    store = RunStore(directory / "react")
    try:
        implementation_ref = store.write("sources", helper.read_bytes(), raw=True)
        verifier = bind_verifier(store, data["contract"], data["before"], lambda: json.loads(state_path.read_text()))
        command = [sys.executable, str(Path(__file__).resolve())]
        common = ["--state", str(state_path), "--input", str(input_path)]
        tools = [
            Tool("select_targets", "Select record IDs from observed properties and relationships", {"type": "object", "additionalProperties": False},
                 command + ["select"] + common + ["--helper", str(helper), "--helper-sha256", implementation["sha256"]],
                 {"type": "object", "properties": {"entity_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True}},
                  "required": ["entity_ids"], "additionalProperties": False}),
            Tool("apply_update", "Apply the requested property update to the specified records", {"type": "object",
                 "properties": {"entity_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 20, "uniqueItems": True}},
                 "required": ["entity_ids"], "additionalProperties": False},
                 command + ["update"] + common, {"type": "object"}, effect="WRITE"),
        ]
        result = ReactLoop(store=store, task=data["contract"]["goal"], constraints=[],
            model_command=command + ["actor"], tools=tools, verifier=verifier,
            config=Config(**manifest["config"]), provider="scripted",
            model_info={"benchmark": False, "synthetic_scripted_demo": True, "repair_variant": variant,
                        "case_id": case_id, "implementation_sha256": implementation["sha256"],
                        "implementation_ref": implementation_ref}).run()
        entry = {"case_id": case_id, "variant": variant, "run": str(store.root.relative_to(root)),
                 "event_head": store.audit()["last_event_sha256"]}
        write_new(directory / "run-result.json", {"index_entry": entry, "execution": result})
        return entry
    finally:
        store.close()


def run_comparison(output, candidate="repaired"):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    implementation_refs = {}
    for variant, source in (("parent", "parent"), ("candidate", "parent" if candidate == "unchanged" else candidate)):
        path = root / "inputs/implementations" / (variant + ".py")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write((HELPERS / (source + ".py")).read_bytes())
        path.chmod(0o400)
        implementation_refs[variant] = {"path": str(path.relative_to(root)), "sha256": digest(path)}
    suite, data_by_id = [], {}
    for case_id, role, data in cases():
        path = root / "inputs/cases" / (case_id + ".json")
        write_new(path, data)
        suite.append({"id": case_id, "role": role, "input": {"path": str(path.relative_to(root)), "sha256": digest(path)}})
        data_by_id[case_id] = data
    manifest = {"version": VERSION, "created_at": timestamp(), "synthetic": True,
                "target": {"case_id": "relationship_filter", "requirement_id": "unrelated_state_preserved"},
                "cases": suite, "implementations": implementation_refs,
                "config": asdict(Config(max_steps=3, max_tool_attempts=2, deadline_seconds=30)),
                "protected_sources": protected_sources(), "checker_version": CHECKER_VERSION}
    write_new(root / "manifest.json", manifest)  # Committed before any episode starts.
    entries = []
    for i, case in enumerate(suite):
        order = ("parent", "candidate") if i % 2 == 0 else ("candidate", "parent")
        for variant in order:
            entry = run_episode(root, manifest, case["id"], variant, data_by_id[case["id"]])
            entries.append(entry)
            print(json.dumps({"event": "comparison_episode_finished", "case_id": case["id"], "variant": variant}), flush=True)
    write_new(root / "runs.json", entries)
    outcome = score_comparison(root)
    write_new(root / "comparison.json", outcome)
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="run", choices=["run", "actor", "select", "update"])
    parser.add_argument("--candidate", default="repaired", choices=["repaired", "regressing", "unchanged"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--helper", type=Path)
    parser.add_argument("--helper-sha256")
    args = parser.parse_args()
    if args.mode == "run":
        output = args.output or ROOT / "runs/repair-scoring" / str(uuid.uuid4())
        result = run_comparison(output, args.candidate)
        print(json.dumps({k: v for k, v in result.items() if k != "runs"}, indent=2))
        print(json.dumps({"comparison": str(output.resolve() / "comparison.json")}))
        return {"ACCEPT_FOR_DEVELOPMENT": 0, "REJECT": 1, "INCONCLUSIVE": 2, "INVALID": 3}[result["decision"]]
    incoming = json.load(sys.stdin)
    if args.mode == "actor":
        turn = incoming["turn"]
        result = {"kind": "act", "request_id": turn["request_id"], "evidence_ids": [], "reason": "Scripted helper comparison"}
        if turn["step"] == 1:
            result.update(action_id="select_targets", arguments={})
        elif turn["step"] == 2:
            observation = incoming["recent_steps"][-1]["observation"]
            selected = json.loads(observation["preview"])
            result.update(action_id="apply_update", arguments={"entity_ids": selected["entity_ids"]})
        else:
            result = {"kind": "finish", "request_id": turn["request_id"], "answer": "Applied the selected update",
                      "artifact_refs": [], "claimed_requirement_ids": ["task"]}
    else:
        state = json.loads(args.state.read_text())
        contract = json.loads(args.input.read_text())["contract"]
        if args.mode == "select":
            if digest(args.helper) != args.helper_sha256:
                raise ValueError("Pinned helper changed")
            spec = importlib.util.spec_from_file_location("trusted_fixture_helper", args.helper)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            result = {"entity_ids": module.select(contract["selector"], state)}
        else:
            ids = set(incoming["entity_ids"])
            if not ids <= {e["id"] for e in state["entities"]}:
                raise ValueError("Unknown entity identity")
            update = contract["update"]
            if update["kind"] != "set_property":
                raise ValueError("Fixture executor supports set_property only")
            for entity in state["entities"]:
                if entity["id"] in ids:
                    entity["properties"][update["property"]] = update["value"]
            state["revision"] = str(int(state["revision"]) + 1)
            args.state.write_text(json.dumps(state))
            result = state
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

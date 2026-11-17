#!/usr/bin/env python3
"""Run four scripted ReAct episodes with independent completion checks."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from react_runtime.completion import bind_verifier, fingerprint
from react_runtime.loop import Config, ReactLoop, Tool
from react_runtime.store import RunStore

FIXTURE = ROOT / "examples/completion_fixture.json"
CASES = ("complete", "missed_target", "unintended_change", "incomplete_evidence")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="run", choices=["run", "actor", "read", "update"])
    parser.add_argument("--case", choices=CASES, default="complete")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode != "run":
        incoming = json.load(sys.stdin)
        if args.mode == "actor":
            turn = incoming["turn"]
            result = {"kind": "act", "request_id": turn["request_id"], "evidence_ids": [], "reason": "Scripted verification fixture"}
            if turn["step"] == 1:
                result.update(action_id="get_state", arguments={})
            elif turn["step"] == 2:
                ids = ["ticket:1"] if args.case == "missed_target" else ["ticket:1", "ticket:2"]
                if args.case == "unintended_change":
                    ids.append("ticket:3")
                result.update(action_id="set_reviewed", arguments={"entity_ids": ids})
            else:
                result = {"kind": "finish", "request_id": turn["request_id"], "answer": "Done",
                          "artifact_refs": [], "claimed_requirement_ids": ["task"]}
        else:
            result = json.loads(args.state.read_text())
            if args.mode == "update":
                ids = set(incoming["entity_ids"])
                assert ids <= {e["id"] for e in result["entities"] if e["type"] == "Ticket"}
                for entity in result["entities"]:
                    if entity["id"] in ids:
                        entity["properties"]["reviewed"] = True
                result["revision"] = str(int(result["revision"]) + 1)
                args.state.write_text(json.dumps(result))
        print(json.dumps(result))
        return

    output = (args.output or ROOT / "runs/completion" / str(uuid.uuid4())).resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixture = json.loads(FIXTURE.read_text())
    summary = {"synthetic_scripted_demo": True, "model_learning_claimed": False,
               "fixture_sha256": fingerprint(fixture), "cases": []}
    for case in CASES:
        directory = output / case
        directory.mkdir()
        before, contract = deepcopy(fixture["before"]), deepcopy(fixture["contract"])
        before["scope"] = contract["scope"] = contract["scope"] + ":" + case
        if case == "incomplete_evidence":
            before["complete"] = False
        state_path = directory / "world.json"
        state_path.write_text(json.dumps(before))
        store = RunStore(directory / "react")
        try:
            verifier = bind_verifier(store, contract, before, lambda: json.loads(state_path.read_text()))
            command = [sys.executable, str(Path(__file__).resolve())]
            tools = [
                Tool("get_state", "Read the synthetic world's current state", {"type": "object", "additionalProperties": False},
                     command + ["read", "--state", str(state_path)], {"type": "object"}),
                Tool("set_reviewed", "Mark the specified synthetic tickets reviewed", {"type": "object",
                     "properties": {"entity_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 10}},
                     "required": ["entity_ids"], "additionalProperties": False},
                     command + ["update", "--state", str(state_path)], {"type": "object"}, effect="WRITE"),
            ]
            result = ReactLoop(store=store, task=contract["goal"], constraints=[],
                model_command=command + ["actor", "--case", case], tools=tools,
                verifier=verifier, config=Config(max_steps=3, deadline_seconds=30),
                provider="scripted", model_info={"benchmark": False, "synthetic_scripted_demo": True}).run()
            event = next(e for e in store.audit()["events"] if e["type"] == "completion_checked")
            report_ref = event["payload"]["report_ref"]
            report = json.loads(store.get(report_ref["id"]))
            entry = {"case": case, "execution_status": result["status"], "completion": report["state"],
                     "reward": report["reward"], "checks": {c["requirement_id"]: c["value"] for c in report["checks"]},
                     "report": str(store.root / report_ref["path"]), "trace_complete": result["judge_packet"]["complete"]}
            summary["cases"].append(entry)
            print(json.dumps(entry), flush=True)
        finally:
            store.close()
    with (output / "summary.json").open("x") as handle:
        json.dump(summary, handle, indent=2)
    print(json.dumps({"summary": str(output / "summary.json")}))


if __name__ == "__main__":
    main()

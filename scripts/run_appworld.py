#!/usr/bin/env python3
"""Select native tasks before executing a single-request ReAct baseline through MCP."""

import argparse
import json
from pathlib import Path
import sys
import tomllib
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from appworld_runtime.batch import make_selection, run_batch
from appworld_runtime.surface import inventory, write_new
from react_runtime.loop import Config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["inventory", "select", "run"])
    parser.add_argument("--root", type=Path, default=ROOT / ".appworld")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--config", type=Path, default=ROOT / "config/appworld_loop.toml")
    args = parser.parse_args()
    try:
        if args.command == "inventory":
            if args.output is None:
                parser.error("inventory requires --output to keep native data in a local artifact")
            write_new(args.output, inventory(args.root))
            print(json.dumps({"inventory": str(args.output.resolve())}))
        elif args.command == "select":
            output = args.output or ROOT / "runs/appworld" / f"selection-{uuid.uuid4()}.json"
            selection = make_selection(args.root, args.count)
            write_new(output, selection)
            print(json.dumps({"selection": str(output.resolve()), "application": selection["application"],
                              "scenario_id": selection["scenario_id"], "task_ids": [t["task_id"] for t in selection["tasks"]]}))
        else:
            if args.selection is None:
                parser.error("run requires a recorded --selection; it never chooses tasks during rollout")
            output = args.output or ROOT / "runs/appworld" / f"batch-{uuid.uuid4()}"
            config = Config(**tomllib.loads(args.config.read_text()))
            summary = run_batch(args.root, args.selection, output, config)
            print(json.dumps({k: v for k, v in summary.items() if k != "episodes"}, indent=2))
            return 0 if summary["complete"] else 2
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"error": type(error).__name__, "message": str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

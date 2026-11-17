#!/usr/bin/env python3
"""Recompute a repair decision from recorded runs, without executing the repair."""

import argparse
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from appworld_runtime.surface import write_new
from react_runtime.repair_scoring import score_comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = score_comparison(args.comparison)
    output = args.output or args.comparison / "scoring" / (str(uuid.uuid4()) + ".json")
    write_new(output, result)
    print(json.dumps({k: v for k, v in result.items() if k != "runs"}, indent=2))
    print(json.dumps({"decision_receipt": str(output.resolve())}))
    return {"ACCEPT_FOR_DEVELOPMENT": 0, "REJECT": 1, "INCONCLUSIVE": 2, "INVALID": 3}[result["decision"]]


if __name__ == "__main__":
    raise SystemExit(main())

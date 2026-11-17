#!/usr/bin/env python3
"""Run recorded task episodes; default learning requires a separate Gemini diagnosis."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from repair_runtime.inference import run_request, continue_learning
from repair_runtime.proposer import SearchProposer
from repair_runtime.store import Archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "learn", "demo"])
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--requests", type=Path, help="JSON array of independent single-request episodes")
    parser.add_argument("--bootstrap", type=int, default=0, help="Collect this many raw ReAct episodes before first repair")
    parser.add_argument("--allow-kernel-repair", action="store_true", help="Enable Gemini diagnosis and separate proposal for one bounded program-function repair")
    args = parser.parse_args()
    if args.bootstrap < 0: parser.error("Bootstrap count must be nonnegative")
    archive = Archive(args.archive, create=not (args.archive / "archive.sqlite").exists())
    try:
        with archive.db: archive.set("frozen_kernel", args.command != "demo" and not args.allow_kernel_repair)
        if args.command == "learn": result = continue_learning(archive)
        else:
            if args.command == "demo":
                from scripts.demo_repair_scoring import cases
                from copy import deepcopy
                originals = [c[2] for c in cases()]
                requests = [{"request_id": "warmup-" + str(i), "adapter": "local", "actor": "reference", "raw": True, "data": d}
                            for i, d in enumerate(originals[:3])]
                requests += [{"request_id": "gap", "adapter": "local", "actor": "reference", "data": originals[0]}]
                numeric = deepcopy(originals[0])
                numeric["contract"]["selector"].pop("related")
                numeric["contract"]["selector"]["numeric"] = [{"property": "quantity", "op": "gte", "value": 2}]
                for i, e in enumerate(numeric["before"]["entities"]): e["properties"]["quantity"] = i % 3
                requests += [{"request_id": "numeric-gap", "adapter": "local", "actor": "reference", "data": numeric},
                             {"request_id": "after-numeric", "adapter": "local", "actor": "reference", "data": numeric},
                             {"request_id": "old-relationship", "adapter": "local", "actor": "reference", "data": originals[1]}]
                bootstrap = 4  # Three raw runs, then demonstrate same-state fallback before repair.
            else:
                if args.requests is None: parser.error("run requires --requests")
                requests = json.loads(args.requests.read_text())
                bootstrap = args.bootstrap
            if not isinstance(requests, list) or not requests: parser.error("Requests must be a nonempty JSON array")
            if bootstrap > len(requests): parser.error("Bootstrap exceeds request count")
            manifest = archive.put({"requests": requests, "bootstrap": bootstrap})
            with archive.db: archive.event("INFERENCE_BATCH_REGISTERED", {"manifest": manifest, "requests": len(requests)})
            outputs = []
            for i, request in enumerate(requests):
                if args.command != "demo" and i < bootstrap: request = {**request, "raw": True}
                value = run_request(archive, request, learn=i + 1 >= bootstrap and request.get("learn", True),
                                    proposer=SearchProposer() if args.command == "demo" else None)
                outputs.append(value)
                print(json.dumps({"request_id": request["request_id"], "task_state": value.get("task_state"),
                    "recovered": value.get("recovered"), "execution_stop": value.get("episode", {}).get("status"),
                    "active": archive.meta("active"), "repair_route": value.get("repair_route"),
                    "learning_status": value.get("learning", {}).get("status")}), flush=True)
            result = {"requests": outputs, "archive": archive.status(), "audit": archive.audit(),
                      "demo_actor": "scripted reference" if args.command == "demo" else None}
        (archive.root / "inference-result.json").write_text(json.dumps(result, indent=2))
        print(json.dumps({"result": str(archive.root / "inference-result.json"), "audit": archive.audit()}))
        if result.get("status") == "BLOCKED" or any(r.get("learning", {}).get("status") == "BLOCKED" for r in result.get("requests", [])): return 2
        if args.command == "learn" and result.get("status") == "NO_IMPROVEMENT": return 1
        if args.command in {"run", "demo"}: return 0 if all(r.get("task_state") == "TRUE" for r in result["requests"]) else 1
        return 0
    finally: archive.close()


if __name__ == "__main__": raise SystemExit(main())

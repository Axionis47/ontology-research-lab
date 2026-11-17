#!/usr/bin/env python3
"""Run, inspect and resume bounded automatic repair of selective-update programs."""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from react_runtime.completion import fingerprint
from react_runtime.loop import Config, parse_json
from repair_runtime.engine import import_run, work
from repair_runtime.episode import finish, run_episode
from repair_runtime.evaluation import apply_update
from repair_runtime.program import identity
from repair_runtime.proposer import SearchProposer, ModelProposer
from repair_runtime.store import Archive


def fixture_actor(context, reference=False):
    """Intentionally limited test actor. Never presented as model learning."""
    request_id = context["turn"]["request_id"]
    history = context["recent_steps"]
    if reference and context.get("kernel_handoff"):
        history = [r for r in history if r["step"] > context["kernel_handoff"]["step"]]
    actions = [r["action"] for r in history]
    if "apply_update" in actions: return finish(request_id)
    reads = [r for r in history if r["action"] == "inspect_state"]
    if not reads:
        action, arguments = "inspect_state", {}
    else:
        observation = json.loads(reads[-1]["observation"]["preview"])
        state, selector = observation["snapshot"], observation["selector"]
        ids = [e["id"] for e in state["entities"] if e["type"] == selector["entity_type"]
               and all(k in e["properties"] and identity(e["properties"][k]) == identity(v) for k, v in selector["where"].items())]
        if reference:
            # Independent scripted recovery oracle for controller tests only.
            from react_runtime.completion import target_set, index_snapshot
            entities, edges = index_snapshot(state)
            ids, unknown = target_set({"selector": selector}, entities, edges)
            if unknown: return finish(request_id)
        action, arguments = "apply_update", {"entity_ids": ids, "revision": state["revision"]}
    return {"kind": "act", "request_id": request_id, "action_id": action, "arguments": arguments,
            "evidence_ids": [], "reason": "Scripted baseline fixture"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "enqueue", "ingest", "work", "status", "inspect", "discover",
                                           "rollback", "retry", "run", "demo", "tool-read", "tool-write", "fixture-actor"])
    parser.add_argument("--archive", type=Path, default=ROOT / "runs/learning/default")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--proposer", choices=["search", "gemini"], default=None,
                        help="Gemini by default; explicit demo uses search as a labelled fixture")
    parser.add_argument("--actor", choices=["scripted", "reference", "gemini", "ollama"], default="ollama")
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--jobs", type=int, default=20)
    parser.add_argument("--attempts", type=int, default=96)
    parser.add_argument("--watch-seconds", type=float, default=0)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--key")
    parser.add_argument("--expected")
    parser.add_argument("--reason")
    parser.add_argument("--scope")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--world", type=Path)
    parser.add_argument("--binding", type=Path)
    args = parser.parse_args()
    if args.command == "fixture-actor":
        print(json.dumps(fixture_actor(json.load(sys.stdin), args.actor == "reference")))
        return 0
    if args.command in {"tool-read", "tool-write"}:
        incoming = json.load(sys.stdin)
        state, contract = json.loads(args.world.read_text()), json.loads(args.binding.read_text())
        if args.command == "tool-read": result = {"snapshot": state, "selector": contract["selector"]}
        else:
            if incoming["revision"] != state["revision"]: raise ValueError("Stale world revision")
            result = apply_update(contract, state, incoming["entity_ids"])
            args.world.write_text(json.dumps(result))
        print(json.dumps(result))
        return 0
    if args.watch_seconds < 0 or args.timeout <= 0: parser.error("Time budgets must be positive")
    archive = Archive(args.archive, create=args.command in {"init", "demo"})
    try:
        proposer = None
        if args.command in {"work", "run", "demo"}:
            provider = args.proposer or ("search" if args.command == "demo" else "gemini")
            proposer = SearchProposer() if provider == "search" else ModelProposer(provider, timeout=args.timeout)
        result = None
        if args.command == "init": result = archive.status()
        elif args.command == "enqueue":
            if args.file is None: parser.error("enqueue requires --file")
            data = parse_json(args.file.read_text())
            result = {"case": archive.add_case({k: data[k] for k in ("contract", "before")})}
        elif args.command == "ingest":
            if args.run_dir is None: parser.error("ingest requires --run-dir")
            result = {"case": import_run(archive, args.run_dir)}
        elif args.command == "work":
            until = time.monotonic() + args.watch_seconds
            while True:
                result = work(archive, proposer, max_jobs=args.jobs, max_attempts=args.attempts)
                if result["completed"]: print(json.dumps(result), flush=True)
                if time.monotonic() >= until or archive.meta("cycles_spent") >= archive.meta("max_cycles"): break
                time.sleep(min(2, max(0, until - time.monotonic())))
        elif args.command == "status": result = {**archive.status(), "audit": archive.audit()}
        elif args.command == "inspect":
            if args.key is None: parser.error("inspect requires --key")
            value = json.dumps(archive.get(args.key), ensure_ascii=False, sort_keys=True)
            if args.offset < 0 or not 1 <= args.limit <= 4096: parser.error("Invalid inspection page")
            result = {"key": args.key, "content": value[args.offset:args.offset + args.limit],
                      "total_chars": len(value), "next_offset": args.offset + args.limit if args.offset + args.limit < len(value) else None}
        elif args.command == "discover": result = archive.discover(args.scope, offset=args.offset, limit=args.limit)
        elif args.command == "rollback":
            if not all((args.expected, args.key, args.reason)): parser.error("rollback requires --expected, --key, --reason")
            with archive.worker(): archive.rollback(args.expected, args.key, args.reason)
            result = archive.status()
        elif args.command == "retry":
            if not args.key or not args.reason: parser.error("retry requires --key and --reason")
            with archive.worker(), archive.db:
                row = archive.db.execute("SELECT id FROM cases WHERE id=?", (args.key,)).fetchone()
                if row is None: raise ValueError("Unknown case")
                archive.db.execute("UPDATE cases SET status='READY' WHERE id=?", (args.key,))
                archive.event("RETRY_REQUESTED", {"case": args.key, "reason": args.reason, "budgets_reset": False})
            result = archive.status()
        elif args.command == "run":
            if args.file is None or args.output is None: parser.error("run requires --file and --output")
            raw = parse_json(args.file.read_text())
            data = {k: raw[k] for k in ("contract", "before")}
            episode = run_episode(archive, data, args.output, actor=args.actor, raw=args.raw)
            result = {"episode": episode, "learning": work(archive, proposer, max_jobs=args.jobs, max_attempts=args.attempts)}
        elif args.command == "demo":
            from scripts.demo_repair_scoring import cases
            all_cases = cases()
            # At least three distinct raw ReAct episodes before any construction.
            episodes = [run_episode(archive, data, archive.root / "baseline" / name, actor="scripted", raw=True,
                                    config=Config(max_steps=3, max_tool_attempts=2, deadline_seconds=30, inline_output_chars=12000))
                        for name, _, data in all_cases[:3]]
            archive.add_case(all_cases[3][2], {"kind": "preservation_fixture", "synthetic": True})
            learned = work(archive, proposer, max_jobs=args.jobs, max_attempts=args.attempts)
            verified = [run_episode(archive, data, archive.root / "after" / name, actor="scripted")
                        for name, _, data in all_cases]
            result = {"baseline": episodes, "learning": learned, "after": verified,
                      "candidate_handwritten": False, "proposer": proposer.name, "model_learning_claimed": False,
                      "native_performance_claimed": False, "status": archive.status()}
            ref = archive.put(result)
            (archive.root / "demo.json").write_text(json.dumps({"receipt": ref, **result}, indent=2))
        print(json.dumps(result, indent=2))
        if args.command == "demo":
            return 0 if result["status"]["decisions"] and all(r["status"] == "VERIFIED_SUCCESS" for r in result["after"]) else 1
        if args.command == "run": return 0 if result["episode"]["status"] == "VERIFIED_SUCCESS" else 1
        return 0
    finally:
        archive.close()


if __name__ == "__main__":
    raise SystemExit(main())

"""Locked policy probes. Inputs are frozen before search and never sent to a proposer."""
from copy import deepcopy
import json
from pathlib import Path
import random
import sys
import tempfile
import time

from react_runtime.loop import Config, ReactLoop, Tool
from react_runtime.policy import rank_tools, tokens, ranking, instruction
from react_runtime.store import RunStore


def fixtures(seed, per_component=4):
    rng = random.Random(seed)
    rows = []
    for i in range(per_component):
        noun = rng.choice(["record", "member", "account", "item"]) + str(rng.randrange(10000))
        verb, opposite = [("follow", "unfollow"), ("archive", "unarchive"), ("activate", "deactivate"), ("lock", "unlock")][i % 4]
        rows.append({"component": "discovery", "goal": verb + " " + noun,
                     "tools": [{"name": "app__" + opposite + "_" + noun, "description": "Reverse operation"},
                               {"name": "app__" + verb + "_" + noun, "description": "Apply operation"}],
                     "expected": "app__" + verb + "_" + noun})
        rows.append({"component": "binding", "observed_id": rng.randrange(100), "proposed_id": rng.randrange(100, 99999)})
        if i % 4 == 1: rows[-1]["arguments"] = {}
        elif i % 4 == 2: rows[-1]["arguments"] = {"record_id": "not-an-integer"}
        elif i % 4 == 3: rows[-1]["arguments"] = {"object": {}}
        rows.append({"component": "context", "kind": "history" if i % 2 == 0 else "cycle",
                     "length": 160 + rng.randrange(40), "empty_pages": bool(i % 3)})
    return rows


def probe(policy, case):
    component = case["component"]
    if component == "discovery":
        if ranking(policy) == "legacy":
            words = case["goal"].casefold().split()
            tools = [t for t in case["tools"] if all(w in (t["name"] + " " + t["description"]).casefold() for w in words)]
        else: tools = rank_tools(case["tools"], case["goal"], ranking(policy))
        correct = case.get("bootstrap_only", False) or (bool(tools) and (tools[0]["name"] == case["expected"] if "expected" in case else case["action_word"] in tokens(tools[0]["name"])))
        bootstrap = None
        if case.get("require_state_bootstrap"):
            with tempfile.TemporaryDirectory() as directory:
                store = RunStore(Path(directory) / "run")
                try:
                    reader = Tool("observe_current", "Read current entities and relationships", {"type": "object", "properties": {}, "additionalProperties": False}, [], {"type": "object"}, bootstrap=True)
                    loop = ReactLoop(store=store, task=case["goal"], constraints=[], tools=[reader], model_command=[], verifier=None, execution_policy=policy)
                    bootstrap = loop.policy_action(1, "probe")
                    correct = correct and bootstrap is not None and bootstrap["action_id"] == reader.name and bootstrap["arguments"] == {}
                finally: store.close()
        return {"passed": correct, "ranked": [t["name"] for t in tools][:10], "bootstrap": bootstrap}
    with tempfile.TemporaryDirectory() as directory:
        store = RunStore(Path(directory) / "run")
        try:
            tool = Tool(case.get("tool_name", "update_record"), "Update the supplied record", case.get("schema", {"type": "object", "properties": {"record_id": {"type": "integer"}}, "required": ["record_id"], "additionalProperties": False}),
                        [sys.executable, "-c", "print('{}')"], {"type": "object"}, effect="WRITE")
            loop = ReactLoop(store=store, task="Update selected records", constraints=[], tools=[tool], model_command=[], verifier=None,
                             execution_policy=policy, config=Config(max_context_chars=9000), provider="ollama")
            if component == "binding":
                if "preflight_data" in case:
                    from .admission import check_update
                    loop.argument_guard = lambda name, args: check_update(case["preflight_data"], case.get("current", case["preflight_data"]["before"]), name, args)
                observed = case.get("observed", {"record_id": case.get("observed_id")})
                ref = store.write("tools", observed, visible=True)
                loop.working.observe("read", {}, observed, ref["id"], 0)
                args = case.get("arguments", {"record_id": case.get("proposed_id")})
                before = deepcopy(args)
                observations = [loop.act({"action_id": tool.name, "arguments": args, "evidence_ids": []}, i, time.monotonic() + 10) for i in range(1, 4)]
                return {"passed": all(o[0]["code"] == "ARGUMENT_SCHEMA_INVALID" for o in observations)
                                   and observations[-1][1] == "ARGUMENT_REPAIR_EXHAUSTED" and args == before and loop.tool_attempts == 0,
                        "observations": observations, "arguments_unchanged": args == before}
            if case["kind"] == "history":
                ref = store.write("tools", {"observation": "original"}, visible=True)
                loop.history = [{"step": i, "action": "inspect", "action_key": '["inspect",{}]', "model_output_id": ref["id"],
                                 "observation_id": ref["id"], "observation": {"code": "OK", "output_id": ref["id"], "preview": "x" * 100}} for i in range(case["length"])]
                if "history" in case:
                    loop.history = deepcopy(case["history"])
                    for row in loop.history:
                        row.update(model_output_id=ref["id"], observation_id=ref["id"])
                        if row["observation"].get("output_id"): row["observation"]["output_id"] = ref["id"]
                    loop.task = case["goal"]
                    loop.config = Config(**case["config"])
                    loop.tools = {t["name"]: Tool(t["name"], t["description"], t["arguments"], [], {"type": "object"}) for t in case["tools"] if t["name"] not in {"read_output", "list_outputs", "read_working"}}
                try:
                    context = json.loads(loop.prepare_prompt(case["length"] + 1, "probe"))
                    from react_runtime.ollama import payload, configuration
                    size = len(json.dumps(payload(context, configuration()), ensure_ascii=False, allow_nan=False))
                    return {"passed": size <= loop.config.max_context_chars and context["task"]["objective"] == loop.task and len(context["compacted_steps"]) <= 4,
                            "provider_chars": size, "indexed": len(context["compacted_steps"])}
                except OverflowError: return {"passed": False, "error": "CONTEXT_OVERFLOW"}
            observations = case.get("observations", [{"action": "read" + str(i % 2), "arguments": {"offset": i},
                            "value": {"entities": [] if case["empty_pages"] else [{"record_id": i % 2}], "offset": i, "next_offset": None}} for i in range(8)])
            for i, item in enumerate(observations):
                value = item["value"]
                ref = store.write("tools", value, visible=True)
                loop.working.observe(item["action"], item["arguments"], value, ref["id"], i)
            legacy_stops = len(observations) >= 3 and len({json.dumps(item, sort_keys=True) for item in observations[-3:]}) == 1
            return {"passed": loop.progress_stalled() if instruction(policy, "context", "bound_history") else legacy_stops, "stagnant": loop.working.stagnant}
        finally: store.close()


def score(policy, cases):
    return [{"case": i, "component": case["component"], **probe(policy, case)} for i, case in enumerate(cases)]

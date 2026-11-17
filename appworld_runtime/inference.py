"""Native binding for the declared artist-following surface, via official MCP.

Endpoint schemas and observation normalization belong to this trusted adapter.
The learned program decides the selected set from typed properties at runtime.
No task answer, solution code or private evaluator data enters that decision.
"""

import json
from pathlib import Path
import re
import sys
import uuid

from appworld_runtime.batch import actor_instructions
from appworld_runtime.rpc import request as rpc
from appworld_runtime.session import AppWorldSession
from appworld_runtime.surface import fingerprint_inputs, check_inputs
from react_runtime.completion import bind_verifier, fingerprint
from react_runtime.loop import Config, ReactLoop, Tool
from react_runtime.store import RunStore
from react_runtime.query import query_schema, query_snapshot
from repair_runtime.controller import ControlledPolicy
from repair_runtime.proposer import ModelProposer


def response(result):
    if result.get("rejected"): raise ValueError(result.get("message", "MCP call rejected"))
    result = result["mcp_result"]
    if result.get("isError"): raise ValueError("MCP returned an explicit tool error")
    value = result.get("structuredContent")
    if value is None:
        value = json.loads(next(c["text"] for c in result["content"] if c["type"] == "text"))
    return value["response"]


def bind_goal(goal, scope):
    match = re.fullmatch(r"Follow all the (.+?) artists on Spotify that have at least (\d+) followers\.", goal)
    if not match: raise ValueError("UNSUPPORTED_GOAL_BINDING: this adapter only binds the declared artist-following request grammar")
    return {"version": 1, "goal": goal, "scope": scope,
            "selector": {"entity_type": "Artist", "where": {"genre": match[1].casefold()},
                         "numeric": [{"property": "baseline_adjusted_follower_count", "op": "gte", "value": int(match[2])}]},
            "update": {"kind": "ensure_relation", "relation_type": "follows", "anchor_id": "self", "direction": "out"}}


def query_artists(snapshot, arguments):
    # Match the public search_artists API's uncased genre semantics. This is
    # field normalization, independent of the task's selector or target set.
    arguments = dict(arguments)
    where = arguments.get("where")
    if arguments.get("entity_type") == "Artist" and isinstance(where, dict):
        where = dict(where)
        if isinstance(where.get("genre"), str): where["genre"] = where["genre"].casefold()
        arguments["where"] = where
    return query_snapshot(snapshot, arguments)


class ArtistAdapter:
    def __init__(self, session):
        self.address = session.address
        self.contract = bind_goal(session.info["instruction"], "appworld:" + session.task_id + ":spotify-following")
        passwords = self.call("supervisor__show_account_passwords", {})
        password = next(p["password"] for p in passwords if p["account_name"].casefold() == "spotify")
        logged = self.call("spotify__login", {"username": session.info["supervisor"]["email"], "password": password})
        self.token = logged["access_token"]
        bound = rpc(self.address, "bind_credentials", {"application": session.application, "values": {"access_token": self.token}})
        if bound.get("rejected"): raise ValueError(bound["message"])
        self.initial_following = None
        self.before = self.observe()
        self.marked = False

    def call(self, name, arguments):
        described = rpc(self.address, "describe", {"name": name})
        if described.get("rejected"): raise ValueError(described["message"])
        return response(rpc(self.address, "call", {"name": name, "arguments": arguments}))

    def pages(self, name, arguments):
        records, seen = [], set()
        for page in range(100):
            values = self.call(name, {**arguments, "page_index": page, "page_limit": 20})
            if not isinstance(values, list): raise ValueError("Incomplete observation: API did not return a list")
            for row in values:
                if row["artist_id"] in seen: raise ValueError("Pagination repeated an artist; coverage is unproven")
                seen.add(row["artist_id"])
            records.extend(values)
            if len(values) < 20: return records
        raise ValueError("Observation pagination budget exhausted")

    def observe(self):
        artists = self.pages("spotify__search_artists", {})
        following = {r["artist_id"] for r in self.pages("spotify__show_following_artists", {"access_token": self.token})}
        if self.initial_following is None: self.initial_following = sorted(following)
        initial = set(self.initial_following)
        if not following <= {a["artist_id"] for a in artists}: raise ValueError("Following references unobserved artists")
        entities = [{"id": "self", "type": "Account", "properties": {}}]
        for artist in artists:
            identity = artist["artist_id"]
            # Counts are derived from all following relations. Remove this
            # episode's own membership delta, retaining evidence of any other
            # count change. Raw current counts remain in the MCP transcript.
            properties = {k: v for k, v in artist.items() if k not in {"artist_id", "follower_count"}}
            properties["genre"] = properties["genre"].casefold()
            properties["baseline_adjusted_follower_count"] = artist["follower_count"] - int(identity in following) + int(identity in initial)
            entities.append({"id": "artist:" + str(identity), "type": "Artist", "properties": properties})
        snapshot = {"scope": self.contract["scope"], "complete": True, "entities": entities,
                    "relations": [{"source": "self", "type": "follows", "target": "artist:" + str(i)} for i in sorted(following)]}
        snapshot["revision"] = fingerprint(snapshot)
        return snapshot

    def actions(self, ids, current):
        following = {e["target"] for e in current["relations"]}
        for identity in ids:
            if identity not in following:
                yield "call_tool", {"name": "spotify__follow_artist", "arguments": {
                    "artist_id": int(identity.removeprefix("artist:"))}}

    def binding(self):
        return {"address": self.address, "contract": self.contract, "token": self.token, "initial_following": self.initial_following}


def run_native_episode(archive, request, directory, *, package_ref=None, actor_command=None, regression=False, policy_ref=None):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    source_root = Path(request["root"]).resolve()
    inputs = fingerprint_inputs(source_root, [request["task_id"]], "spotify")
    (directory / "native-manifest.json").write_text(json.dumps({"task_id": request["task_id"], "application": "spotify",
        "input_hashes": inputs, "root": str(source_root), "binding": "artist-following/1", "regression": regression}, indent=2))
    package_ref = package_ref or archive.meta("active")
    package = archive.get(package_ref)
    policy_ref = policy_ref or archive.meta("active_policy")
    actor = request.get("actor", "ollama")
    provider = "text"
    if actor_command is None:
        if actor == "reference": actor_command = [sys.executable, "-m", "appworld_runtime.inference", "reference"]
        else:
            model = ModelProposer(actor)
            actor_command, provider = model.command, actor
    with AppWorldSession(root=Path(request["root"]), task_id=request["task_id"], application="spotify",
                         experiment="inference_" + uuid.uuid4().hex, log_directory=directory / "session",
                         max_api_calls=request.get("max_api_calls", 512)) as session:
        adapter = ArtistAdapter(session)
        # Inspect effect schemas through the catalog before the kernel calls them.
        rpc(session.address, "describe", {"name": "spotify__follow_artist"})
        binding = directory / "adapter-binding.json"
        binding.write_text(json.dumps(adapter.binding())); binding.chmod(0o400)
        tools = session.tools() + [Tool("inspect_state", "Inspect available entity types/properties with {}. Query records by supplying entity_type, exact where predicates and numeric predicates (property, op: gte/gt/lte/lt/eq, value). Returns matching entities and their current relationships, with pagination. Predicates are executed by the store. Authentication is automatic.",
            query_schema(adapter.before),
            [sys.executable, "-m", "appworld_runtime.inference", "observe-reference" if actor == "reference" else "observe", str(binding)], {"type": "object"}, timeout_seconds=120)]
        store = RunStore(directory / "react")
        data = {"contract": adapter.contract, "before": adapter.before}
        verifier = bind_verifier(store, adapter.contract, adapter.before, adapter.observe)
        def verify(proposal, results):
            passed, reason = verifier(proposal, results)
            if passed and not adapter.marked:
                adapter.call("supervisor__complete_task", {"status": "success"})
                adapter.marked = True
            return passed, reason
        verify.binding_ref, verify.bound_goal = verifier.binding_ref, verifier.bound_goal
        try:
            instructions = actor_instructions(session.info) + "\nThis session is already authenticated. Omit access_token; the broker binds it for the selected application."
            configuration = {"max_steps": 40, "max_tool_attempts": 35, "deadline_seconds": 900,
                             "model_timeout_seconds": 90, "inline_output_chars": 8000, "max_stagnant_steps": 3}
            configuration.update(request.get("loop_config", {}))
            episode = ReactLoop(store=store, task=adapter.contract["goal"], constraints=[], model_command=actor_command,
                tools=tools, verifier=verify, config=Config(**configuration),
                provider=provider, model_info={"actor": actor, "native": True, "regression": regression},
                system_instructions=instructions,
                kernel_policy=None if request.get("raw", False) and not regression else ControlledPolicy(package, data, store, adapter.observe, adapter.actions),
                kernel_version=None if request.get("raw", False) and not regression else package_ref,
                execution_policy=archive.get(policy_ref), policy_version=policy_ref,
                check_on_exit=True, check_after_writes=True).run()
        finally: store.close()
        native_result = session.evaluate()
        check_inputs(source_root, inputs)
        (directory / "evaluation.json").write_text(json.dumps(native_result, indent=2))
        journal = [json.loads(line) for line in (directory / "session/mcp-transcript.jsonl").read_text().splitlines()]
        native = {"success": native_result["native_result"]["success"], "evaluation": archive.put(native_result),
                  "mcp_segments": [archive.put(journal[i:i + 16]) for i in range(0, len(journal), 16)],
                  "mcp_events": len(journal), "task_id": request["task_id"], "scope": adapter.contract["scope"],
                  "native_inputs_unchanged": True}
        return {"episode": episode, "data": data, "native": native}


def reference_actor(context):
    """Explicit synthetic recovery actor, for native integration testing only."""
    from repair_runtime.controller import finish
    request_id = context["turn"]["request_id"]
    history = context["recent_steps"]
    if context.get("kernel_handoff"):
        history = [r for r in history if r["step"] > context["kernel_handoff"]["step"]]
    reads = [r for r in history if r["action"] in {"inspect_state", "read_output"}]
    if not reads: name, arguments = "inspect_state", {}
    else:
        latest = reads[-1]["observation"]
        if latest.get("truncated_in_context"):
            name, arguments = "read_output", {"output_id": latest["output_id"], "json_pointer": "/remaining", "max_chars": 2048}
        else:
            value = json.loads(latest["preview"])
            # inspect_state provides compact recovery data under /remaining;
            # it is independently calculated only by this explicit test actor's
            # tool mode. The live model reads normal observed entities instead.
            remaining = value.get("remaining", value.get("value", value))
            if isinstance(remaining, str): remaining = json.loads(remaining)
            if not remaining["ids"]: return finish(request_id)
            prior = [r for r in history if r["action"] == "call_tool" and r["step"] > reads[-1]["step"]]
            if prior: name, arguments = "inspect_state", {}
            else:
                name, arguments = "call_tool", {"name": "spotify__follow_artist", "arguments": {
                    "artist_id": remaining["ids"][0], "access_token": remaining["token"]}}
    return {"kind": "act", "request_id": request_id, "action_id": name, "arguments": arguments,
            "evidence_ids": [], "reason": "Explicit scripted integration fixture"}


if __name__ == "__main__":
    if sys.argv[1] == "reference": print(json.dumps(reference_actor(json.load(sys.stdin))))
    elif sys.argv[1] in {"observe", "observe-reference"}:
        adapter = ArtistAdapter.__new__(ArtistAdapter)
        adapter.__dict__.update(json.loads(Path(sys.argv[2]).read_text()))
        current = adapter.observe()
        if sys.argv[1] == "observe-reference":
            from react_runtime.completion import target_set, index_snapshot
            entities, edges = index_snapshot(current)
            ids, unresolved = target_set(adapter.contract, entities, edges)
            if unresolved: raise ValueError("Unresolved fixture evidence")
            followed = {edge["target"] for edge in current["relations"]}
            print(json.dumps({"remaining": {"ids": [int(i.removeprefix("artist:")) for i in ids if i not in followed], "token": adapter.token},
                              "synthetic_reference_solver": True}))
        else:
            print(json.dumps({"authentication": "managed_by_session", "selector": adapter.contract["selector"],
                              "observation": query_artists(current, json.load(sys.stdin))}))

"""Local state adapter connecting immutable packages, ReAct fallback and repair."""

import json
from pathlib import Path
import sys

from react_runtime.completion import bind_verifier, fingerprint, validate_contract, index_snapshot
from react_runtime.loop import Config, KernelHandoff, ReactLoop, Tool
from react_runtime.store import RunStore
from .engine import import_run
from .controller import ControlledPolicy, finish
from .store import ROOT
from .admission import check_update


def run_episode(archive, data, directory, *, actor="scripted", raw=False, config=None, package_ref=None,
                ingest=True, actor_command=None, policy_ref=None):
    """Fresh local world. Live AppWorld needs its own trusted binding/readback adapter."""
    validate_contract(data["contract"]); index_snapshot(data["before"])
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    world = directory / "world.json"
    world.write_text(json.dumps(data["before"]))
    bound = directory / "binding.json"
    bound.write_text(json.dumps(data["contract"]))
    bound.chmod(0o400)
    package_ref = package_ref or archive.meta("active")
    package = archive.get(package_ref)  # Captured once; future promotions cannot change this episode.
    policy_ref = policy_ref or archive.meta("active_policy")
    command = [sys.executable, str(ROOT / "scripts/repair.py")]
    tool_args = ["--world", str(world), "--binding", str(bound)]
    tools = [Tool("inspect_state", "Read current entities, properties, relationships and bound selector", {"type": "object", "additionalProperties": False},
                  command + ["tool-read"] + tool_args, {"type": "object"}, bootstrap=True),
             Tool("apply_update", "Apply the bound requested update to these IDs if the observed revision is current", {"type": "object",
                  "properties": {"entity_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True}, "revision": {"type": "string"}},
                  "required": ["entity_ids", "revision"], "additionalProperties": False},
                  command + ["tool-write"] + tool_args, {"type": "object"}, effect="WRITE")]
    if actor_command is not None:
        provider = "text"
    elif actor in {"scripted", "reference"}:
        actor_command, provider = command + ["fixture-actor", "--actor", actor], "text"
    else:
        from .proposer import ModelProposer
        transport = ModelProposer(actor)
        actor_command, provider = transport.command, actor
    store = RunStore(directory / "react")
    observe = lambda: json.loads(world.read_text())
    policy = ControlledPolicy(package, data, store, observe,
        lambda ids, state: [("apply_update", {"entity_ids": ids, "revision": state["revision"]})])
    try:
        store.write("sources", package)
        result = ReactLoop(store=store, task=data["contract"]["goal"], constraints=[], model_command=actor_command,
            tools=tools, verifier=bind_verifier(store, data["contract"], data["before"], observe),
            config=config or Config(max_steps=10, max_tool_attempts=6, deadline_seconds=60, inline_output_chars=12000, max_stagnant_steps=3),
            provider=provider, model_info={"synthetic": True, "actor": actor, "package": package_ref},
            kernel_policy=None if raw else policy, kernel_version=None if raw else package_ref,
            execution_policy=archive.get(policy_ref), policy_version=policy_ref,
            argument_guard=lambda name, args: check_update(data, observe(), name, args),
            check_on_exit=True, check_after_writes=True).run()
    finally:
        store.close()
    if not ingest: return result
    try:
        result["repair_case"] = import_run(archive, directory / "react")
    except ValueError as error:
        # A missing terminal check is recorded as unavailable, never fabricated.
        result["repair_unavailable"] = str(error)
        with archive.db: archive.event("EPISODE_EVIDENCE_UNAVAILABLE", {"run": str(directory / "react"), "reason": str(error)})
    return result

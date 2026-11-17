import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from jsonschema import ValidationError

from appworld_runtime.catalog import Catalog
from appworld_runtime.surface import check_inputs, digest, required_apis, select, write_new
from appworld_runtime.batch import run_batch
from appworld_runtime import worker
from react_runtime.loop import Config, KernelHandoff, ReactLoop, Tool
from react_runtime.store import RunStore
from scripts.run_react import fixture_tool, verify_short

ROOT = Path(__file__).resolve().parents[1]


def scenario(sid, difficulty=1, api_count=6, apps=None):
    apps = apps or ["spotify"]
    return {"scenario_id": sid, "native_difficulty": difficulty,
            "required_api_count": api_count, "applications": apps,
            "tasks": [{"task_id": f"{sid}_{i}", "spec_sha256": str(i), "applications": apps}
                      for i in range(1, 4)]}


class SurfaceTests(unittest.TestCase):
    def choose(self, scenarios, count=3):
        reviews = {s["scenario_id"]: {"eligible": True, "reason": "Reviewed selective update",
                   "task_specs": {t["task_id"]: t["spec_sha256"] for t in s["tasks"]}} for s in scenarios}
        return select({"split": "train", "split_sha256": "split", "scenarios": scenarios}, reviews,
                      {"dataset_split": "train", "minimum_variants": 3}, count)

    def test_selection_is_deterministic_and_uses_all_three_rank_keys(self):
        cases = [scenario("a", 2, 2), scenario("b", 1, 8), scenario("d", 1, 6), scenario("c", 1, 6)]
        self.assertEqual(self.choose(cases)["scenario_id"], "c")
        self.assertEqual(self.choose(list(reversed(cases)))["scenario_id"], "c")

    def test_multibusiness_and_insufficient_variants_are_ineligible(self):
        multi = scenario("a", apps=["spotify", "phone"])
        small = scenario("b"); small["tasks"] = small["tasks"][:2]
        selected = self.choose([multi, small, scenario("c")])
        self.assertEqual(selected["scenario_id"], "c")
        self.assertEqual([t["task_id"] for t in selected["tasks"]], ["c_1", "c_2", "c_3"])

    def test_less_than_three_is_rejected(self):
        with self.assertRaises(ValueError):
            self.choose([scenario("a")], 2)

    def test_unreviewed_surface_is_not_guessed(self):
        with self.assertRaisesRegex(ValueError, "semantic surface review"):
            select({"split": "train", "scenarios": [scenario("a")]}, {},
                   {"dataset_split": "train", "minimum_variants": 3})

    def test_native_solution_is_parsed_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "compiled_solution.py").write_text("raise RuntimeError('must not execute')\napis.spotify.follow_artist(artist_id=1)\n")
            self.assertEqual(required_apis(directory), ["spotify.follow_artist"])

    def test_selection_cannot_be_overwritten_and_source_changes_are_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "data").mkdir()
            file = root / "data/spec.json"; file.write_text("original")
            fingerprints = {"spec.json": digest(file)}
            check_inputs(root, fingerprints)
            file.write_text("changed")
            with self.assertRaises(ValueError): check_inputs(root, fingerprints)
            write_new(root / "selection.json", {"selected": True})
            with self.assertRaises(FileExistsError): write_new(root / "selection.json", {})


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog([{"name": f"{app}__update_{i}", "description": "Update a record",
            "inputSchema": {"type": "object", "properties": {"record_id": {"type": "integer"}}, "required": ["record_id"]}}
            for app in ("spotify", "phone", "supervisor") for i in range(12)], "spotify")

    def test_discovery_is_bounded_searchable_and_scoped(self):
        first = self.catalog.discover(limit=5)
        self.assertEqual(first["total_matches"], 24)
        self.assertEqual(len(first["tools"]), 5)
        self.assertEqual(first["next_offset"], 5)
        self.assertNotIn("inputSchema", first["tools"][0])
        self.assertEqual(self.catalog.discover("phone")["tools"], [])
        with self.assertRaises(KeyError): self.catalog.describe("phone__update_1")

    def test_call_schema_rejects_unknown_parameters_and_wrong_types(self):
        self.catalog.validate_call("spotify__update_1", {"record_id": 1})
        for arguments in ({"record_id": "wrong"}, {"record_id": 1, "_system_datetime": "override"}, {}):
            with self.assertRaises(ValidationError): self.catalog.validate_call("spotify__update_1", arguments)


class HandoffTests(unittest.TestCase):
    def test_react_reads_effects_made_before_handoff_without_replaying_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            state = directory / "world.json"
            state.write_text('{"updates": 0}')
            program = directory / "actor_and_tools.py"
            program.write_text('''import json, pathlib, sys
payload = json.load(sys.stdin)
mode, state_path = sys.argv[1], pathlib.Path(sys.argv[2])
if mode == "model":
    request_id = payload["turn"]["request_id"]
    if payload["turn"]["step"] == 3:
        result = {"kind": "act", "request_id": request_id, "action_id": "read_state",
                  "arguments": {}, "evidence_ids": [], "reason": "Inspect the current state."}
    else:
        result = {"kind": "finish", "request_id": request_id, "answer": "Updated once",
                  "artifact_refs": [], "claimed_requirement_ids": ["task"]}
else:
    result = json.loads(state_path.read_text())
    if mode == "update":
        result["updates"] += 1
        state_path.write_text(json.dumps(result))
print(json.dumps(result))
''')
            def kernel(context):
                if context["turn"]["step"] == 1:
                    return {"kind": "act", "request_id": context["turn"]["request_id"],
                            "action_id": "update_state", "arguments": {},
                            "evidence_ids": [], "reason": "Apply the requested update."}
                return KernelHandoff("EVIDENCE_GAP", "Inspect the updated state")
            def verify(_proposal, results):
                reads = [r for r in results if r["action"] == "read_state"]
                return bool(reads and reads[-1]["result"] == {"updates": 1}), "Read back the kernel's effect"
            store = RunStore(directory / "run")
            try:
                tools = [Tool(name, name, {"type": "object", "additionalProperties": False},
                              [sys.executable, str(program), mode, str(state)], {"type": "object"},
                              effect=effect) for name, mode, effect in
                         (("update_state", "update", "WRITE"), ("read_state", "read", "READ"))]
                result = ReactLoop(store=store, task="Update once, then verify", constraints=[],
                    model_command=[sys.executable, str(program), "model", str(state)],
                    tools=tools, verifier=verify, config=Config(max_steps=4, max_tool_attempts=2),
                    kernel_policy=kernel, kernel_version="effect-fixture-v1").run()
                self.assertEqual(result["status"], "VERIFIED_SUCCESS")
                self.assertEqual(json.loads(state.read_text()), {"updates": 1})
                self.assertEqual(result["tool_attempts"], 2)
                self.assertEqual([e["payload"]["action"] for e in store.audit()["events"]
                                  if e["type"] == "dispatch_started"], ["update_state", "read_state"])
            finally:
                store.close()

    def test_handoff_preserves_goal_evidence_and_consumed_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(Path(tmp) / "run")
            def kernel(context):
                if context["turn"]["step"] == 1:
                    return {"kind": "act", "request_id": context["turn"]["request_id"],
                            "action_id": "get_record", "arguments": {"record_id": "123"},
                            "evidence_ids": [], "reason": "Read before yielding."}
                evidence = context["recent_steps"][0]["observation"]["output_id"]
                return KernelHandoff("CAPABILITY_GAP", "Finish from the observed record", (evidence,))
            try:
                result = ReactLoop(store=store, task="Keep this original goal", constraints=["Keep records unchanged"],
                    model_command=[sys.executable, str(ROOT / "react_runtime/fixtures.py"), "scripted"],
                    tools=[fixture_tool()], verifier=verify_short, config=Config(max_steps=3),
                    kernel_policy=kernel, kernel_version="fixture-kernel-v1").run()
                self.assertEqual(result["status"], "VERIFIED_SUCCESS")
                self.assertEqual(result["steps"], 3)
                self.assertEqual(result["tool_attempts"], 1)
                events = store.audit()["events"]
                model = next(e for e in events if e["type"] == "model_started")
                context = json.loads(store.get(model["payload"]["input_ref"]["id"]))
                self.assertEqual(context["task"]["objective"], "Keep this original goal")
                self.assertEqual(context["turn"]["steps_remaining_including_this"], 1)
                self.assertEqual(context["turn"]["tool_attempts_remaining"], 23)
                self.assertEqual(context["kernel_handoff"]["reason"], "CAPABILITY_GAP")
                self.assertEqual(len([e for e in events if e["type"] == "dispatch_started"]), 1)
                self.assertTrue(store.audit()["complete"])
            finally:
                store.close()

    def test_handoff_cannot_reset_exhausted_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(Path(tmp) / "run")
            try:
                result = ReactLoop(store=store, task="goal", constraints=[], model_command=["not-executed"],
                    tools=[], verifier=None, config=Config(max_steps=1),
                    kernel_policy=lambda ctx: KernelHandoff("NO_PROGRESS", "Unresolved task"),
                    kernel_version="fixture-v1").run()
                self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
                self.assertFalse(any(e["type"] == "model_started" for e in store.audit()["events"]))
            finally:
                store.close()


class WorkerFailureTests(unittest.TestCase):
    def test_failure_after_native_dispatch_is_not_a_retryable_rejection(self):
        for failure_phase in ("call", "save"):
            with self.subTest(phase=failure_phase), tempfile.TemporaryDirectory() as tmp:
                world, mcp = MagicMock(), MagicMock()
                world.__enter__.return_value = world
                world.task = SimpleNamespace(instruction="Update once", supervisor={},
                    datetime=datetime.now(timezone.utc), db_version="fixture")
                world.output_directory = tmp
                if failure_phase == "save":
                    world.save.side_effect = ValueError("Cannot save after the effect")
                mcp.__enter__.return_value = mcp
                mcp.params = SimpleNamespace(env={})
                mcp.list_tools.return_value = [{"name": "spotify__update", "inputSchema": {"type": "object"}}]
                effects = []
                async def call_tool(*_args, **_kwargs):
                    effects.append("updated")
                    if failure_phase == "call":
                        raise ValueError("Cannot decode the response after the effect")
                    response = MagicMock()
                    response.model_dump.return_value = {"isError": False, "content": []}
                    return response
                mcp.session.call_tool = call_tool
                mcp._submit_coroutine.side_effect = asyncio.run
                connection, server = MagicMock(), MagicMock()
                connection.__enter__.return_value = connection
                server.__enter__.return_value = server
                server.accept.return_value = connection, None
                replies = []
                connection.sendall.side_effect = lambda raw: replies.append(json.loads(raw))
                messages = [{"method": "describe", "arguments": {"name": "spotify__update"}},
                            {"method": "call", "arguments": {"name": "spotify__update", "arguments": {}}},
                            {"method": "close"}]
                fake_modules = {"appworld": SimpleNamespace(AppWorld=lambda **_: world),
                    "appworld.serve._mcp": SimpleNamespace(MCPClient=SimpleNamespace(from_dict=lambda _: mcp))}
                argv = ["worker", "--socket", tmp + "/socket", "--task-id", "fixture_1",
                        "--application", "spotify", "--experiment", "fixture", "--logs", tmp]
                with patch.dict(sys.modules, fake_modules), patch.object(sys, "argv", argv), \
                     patch.dict(worker.os.environ, {k: tmp for k in ("APPWORLD_ROOT", "APPWORLD_CACHE", "IPYTHONDIR")}), \
                     patch.object(worker, "version", return_value="fixture"), \
                     patch.object(worker, "launch_api_server", return_value=(MagicMock(), MagicMock(), "local")), \
                     patch.object(worker.socket, "socket", return_value=server), \
                     patch.object(worker.os, "chmod"), patch.object(worker, "receive", side_effect=messages), \
                     patch.object(worker.traceback, "print_exc"):
                    worker.main()
                self.assertEqual(effects, ["updated"])
                self.assertIn("session_error", replies[1])
                self.assertNotIn("rejected", replies[1])


class BatchTests(unittest.TestCase):
    def test_three_fresh_episodes_evaluate_after_finish_without_exposing_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = [{"task_id": f"abc_{i}", "instruction": f"Original goal {i}", "db_version": "fixture"} for i in range(1, 4)]
            selection = {"tasks": tasks, "application": "spotify", "scenario_id": "abc", "input_hashes": {}}
            write_new(root / "selection.json", selection)
            instances = []
            class Session:
                def __init__(self, **kwargs):
                    self.task_id = kwargs["task_id"]; instances.append(self)
                    native = root / (self.task_id + "-native"); native.mkdir()
                    self.info = {"instruction": next(t["instruction"] for t in tasks if t["task_id"] == self.task_id),
                                 "db_version": "fixture", "supervisor": {}, "task_datetime": "fixed",
                                 "application": "spotify", "catalog_revision": "fixture", "appworld_version": "fixture",
                                 "native_output_directory": str(native)}
                def __enter__(self): return self
                def __exit__(self, *_): pass
                def tools(self): return []
                def evaluate(self):
                    return {"native_result": {"success": False, "failures": [{"requirement": "PRIVATE_CHECK"}]}}
            program = "import json,sys;p=json.load(sys.stdin);print(json.dumps({'kind':'finish','request_id':p['turn']['request_id'],'answer':'done','artifact_refs':[],'claimed_requirement_ids':['task']}))"
            with patch("appworld_runtime.batch.validate_selection"):
                result = run_batch(root, root / "selection.json", root / "batch", Config(max_steps=2),
                                   model_command=[sys.executable, "-c", program], model_info={"provider": "scripted"}, session_factory=Session)
            self.assertEqual(len(instances), 3)
            self.assertEqual(result["native_tasks_evaluated"], 3)
            self.assertEqual(result["native_tasks_passed"], 0)
            self.assertTrue(result["complete"])
            for task in tasks:
                episode = root / "batch" / task["task_id"]
                receipt = json.loads((episode / "evaluation.json").read_text())
                self.assertIn("episode_event_head", receipt)
                store = RunStore.open_existing(episode / "react")
                try:
                    events = store.audit()["events"]
                    model = next(e for e in events if e["type"] == "model_started")
                    actor_input = store.get(model["payload"]["input_ref"]["id"]).decode()
                    self.assertNotIn("PRIVATE_CHECK", actor_input)
                    self.assertIn(task["instruction"], actor_input)
                finally:
                    store.close()


if __name__ == "__main__":
    unittest.main()

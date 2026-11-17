from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

from react_runtime.loop import Config, ReactLoop, Tool
from react_runtime.ollama import input_schema, payload, configuration
from react_runtime.policy import legacy_policy, validate_policy, changed_component, rank_tools
from react_runtime.store import RunStore
from repair_runtime.policy_evaluation import fixtures, score
from repair_runtime.policy_repair import freeze, register_failure, promote
from repair_runtime.store import Archive, ROOT
from repair_runtime.evaluation import challenges
from scripts.demo_repair_scoring import cases

GOOD = dict(version=1, discovery="weighted", binding="observed", context="working")


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = RunStore(self.root / "run")

    def tearDown(self):
        self.store.close(); self.tmp.cleanup()

    def loop(self, **kwargs):
        return ReactLoop(store=self.store, task="Follow matching records", constraints=[], model_command=[], tools=[], verifier=None, execution_policy=GOOD, **kwargs)

    def test_registered_data_only_single_component(self):
        with self.assertRaises(ValueError): validate_policy({**GOOD, "code": "print(1)"})
        with self.assertRaises(ValueError): changed_component(legacy_policy(), GOOD)
        self.assertEqual(changed_component(GOOD, {**GOOD, "binding": "legacy"}), "binding")

    def test_exact_words_do_not_match_opposite_action(self):
        tools = [{"name": "unfollow", "description": ""}, {"name": "follow", "description": ""}]
        self.assertEqual([t["name"] for t in rank_tools(tools, "follow", "weighted")], ["follow"])

    def test_explicitly_inspected_helper_remains_callable(self):
        loop = self.loop()
        for name in ("follow_record", "follow_artist", "follow_account", "list_groups"):
            loop.successful_results.append({"action": "inspect_tool", "result": {"tool": {"name": name, "description": "", "inputSchema": {"type": "object"}}}})
        context = loop.context(1, "test", 0)
        native = [t["name"] for t in context["inspected_tools"]]
        self.assertIn("list_groups", native)
        self.assertLessEqual(len(native), 3)
        self.assertIn("list_groups", [t["function"]["name"] for t in payload(context, configuration())["tools"]])

    def test_twelve_component_probes(self):
        data = fixtures(339)
        self.assertEqual(len(data), 12)
        self.assertTrue(all(r["passed"] for r in score(GOOD, data)))
        self.assertFalse(any(r["passed"] for r in score(legacy_policy(), data)))

    def test_valid_empty_schema_and_malformed_arguments(self):
        self.assertEqual(input_schema({"type": "object", "additionalProperties": False})["properties"], {})
        loop = self.loop()
        loop.tools["inspect_state"] = Tool("inspect_state", "read", {"type": "object", "properties": {}, "additionalProperties": False}, [sys.executable, "-c", "print('{}')"], {"type": "object"})
        observation, stop = loop.act({"action_id": "inspect_state", "arguments": {"object": {}}, "evidence_ids": []}, 1, time.monotonic() + 10)
        self.assertIn("supply {}", observation["message"])
        self.assertIsNone(stop)
        self.assertEqual(loop.act({"action_id": "inspect_state", "arguments": {}, "evidence_ids": []}, 2, time.monotonic() + 10)[0]["code"], "OK")

    def test_declared_state_bootstrap_is_read_only_and_once(self):
        loop = self.loop()
        reader = Tool("inspect_state", "Current state", {"type": "object", "properties": {}, "additionalProperties": False}, [], {"type": "object"}, bootstrap=True)
        loop.tools[reader.name] = reader
        action = loop.policy_action(1, "id")
        self.assertEqual((action["action_id"], action["arguments"]), ("inspect_state", {}))
        self.assertIsNone(loop.policy_action(2, "id"))
        with self.assertRaises(ValueError):
            ReactLoop(store=self.store, task="test", constraints=[], model_command=[], verifier=None,
                      tools=[Tool("write", "write", {"type": "object"}, [], {"type": "object"}, effect="WRITE", bootstrap=True)])

    def test_bad_evidence_pointer_has_fields_and_bounded_repair(self):
        loop = self.loop()
        ref = self.store.write("tools", {"snapshot": {"entities": []}}, visible=True)
        arguments = {"output_id": ref["id"], "json_pointer": "/selections"}
        outcomes = [loop.act({"action_id": "read_output", "arguments": arguments, "evidence_ids": []}, i, time.monotonic() + 10) for i in range(1, 4)]
        self.assertIn("available fields: snapshot", outcomes[0][0]["message"])
        self.assertEqual(outcomes[-1][1], "ARGUMENT_REPAIR_EXHAUSTED")
        self.assertTrue(loop.progress_stalled() is False)  # Three denied reads use the stricter argument cap.

    def test_corrections_survive_compaction_and_resolve_after_success(self):
        loop = self.loop()
        loop.working.reject("update", "record a violates a property constraint", None, 1)
        loop.working.reject("update", "record b violates a relationship constraint", None, 2)
        messages = loop.working.view()["pending_corrections"][0]["messages"]
        self.assertEqual(len(messages), 2)
        self.assertIn("record a", messages[0])
        loop.working.resolve("update")
        self.assertNotIn("pending_corrections", loop.working.view())

    def test_entity_pages_retain_relationships_and_exact_revision(self):
        loop = self.loop()
        snapshot = cases()[0][2]["before"]
        loop.working.observe("inspect_state", {}, {"snapshot": snapshot}, "original", 1)
        values = loop.working.page("entities")["records"]
        ticket = next(r for r in values if r["value"]["id"] == "ticket:1")
        self.assertEqual(ticket["value"]["relations"][0]["target"], "customer:west")
        self.assertEqual(loop.working.view()["state_revision"]["revision"], "0")
        loop.working.observe("read_working", {}, {"records": values}, "derived", 2)
        self.assertEqual(next(r for r in loop.working.page("entities")["records"] if r["value"]["id"] == "ticket:1")["source_output_id"], "original")

    def test_bound_preflight_rejects_without_substituting_arguments(self):
        from repair_runtime.admission import check_update
        data = cases()[0][2]
        arguments = {"entity_ids": ["ticket:1", "ticket:2", "ticket:4"], "revision": "0"}
        before = deepcopy(arguments)
        error = check_update(data, data["before"], "apply_update", arguments)
        self.assertIn("ticket:4", error)
        self.assertEqual(arguments, before)
        self.assertIsNone(check_update(data, data["before"], "apply_update", {"entity_ids": ["ticket:1", "ticket:2"], "revision": "0"}))

    def test_preflight_supports_generated_schema_names(self):
        from repair_runtime.admission import check_update
        from react_runtime.completion import target_set, index_snapshot
        for data in challenges(897, 16, function="related"):
            entities, edges = index_snapshot(data["before"])
            ids, _ = target_set(data["contract"], entities, edges)
            self.assertIsNone(check_update(data, data["before"], "apply_update", {"entity_ids": ids, "revision": "0"}))
            wrong = next(e["id"] for e in data["before"]["entities"] if e["id"] not in ids)
            self.assertIsNotNone(check_update(data, data["before"], "apply_update", {"entity_ids": [wrong], "revision": "0"}))

    def test_revision_churn_is_not_new_evidence(self):
        loop = self.loop()
        for i in range(5): loop.working.observe("inspect_state", {}, {"scope": "s", "revision": str(i), "entities": [], "relations": [], "complete": True}, str(i), i)
        self.assertTrue(loop.progress_stalled())

    def test_denied_write_does_not_overwrite_feedback_with_postcondition(self):
        from repair_runtime.episode import run_episode
        archive = Archive(self.root / "denied-archive", create=True)
        try:
            ref = archive.put({**GOOD, "binding": "constrained"})
            actor = [sys.executable, "-c", 'import json,sys; c=json.load(sys.stdin); print(json.dumps({"kind":"act","request_id":c["turn"]["request_id"],"action_id":"apply_update","arguments":{},"evidence_ids":[],"reason":"fixture"}))']
            result = run_episode(archive, cases()[0][2], self.root / "denied", raw=True, actor_command=actor, policy_ref=ref, ingest=False)
            self.assertEqual(result["status"], "ARGUMENT_REPAIR_EXHAUSTED")
            store = RunStore.open_existing(Path(result["run_directory"]))
            try:
                audit = store.audit()
                self.assertTrue(audit["complete"], audit["problems"])
                self.assertFalse(any(e["type"] == "postcondition_assessment" for e in audit["events"]))
            finally: store.close()
        finally: archive.close()

    def test_read_correction_preserves_dispatch_audit(self):
        ref = self.store.write("tools", {"snapshot": {}}, visible=True)
        loop = self.loop()
        loop.command = [sys.executable, "-c", 'import sys,json; c=json.load(sys.stdin); print(json.dumps({"kind":"act","request_id":c["turn"]["request_id"],"action_id":"read_output","arguments":{"output_id":' + repr(ref["id"]) + ',"json_pointer":"/absent"},"evidence_ids":[],"reason":"fixture"}))']
        self.assertEqual(loop.run()["status"], "ARGUMENT_REPAIR_EXHAUSTED")
        audit = self.store.audit()
        self.assertTrue(audit["complete"], audit["problems"])
        self.assertEqual(sum(e["type"] == "argument_correction" for e in audit["events"]), 3)

    def test_actual_native_schema_required_and_ids_not_rebound(self):
        loop = self.loop()
        loop.tools["call_tool"] = Tool("call_tool", "call", {"type": "object"}, [sys.executable, "-c", "print('{}')"], {"type": "object"}, effect="WRITE")
        schema = {"name": "app__update", "inputSchema": {"type": "object", "properties": {"record_id": {"type": "integer"}}, "required": ["record_id"], "additionalProperties": False}}
        loop.successful_results.append({"action": "inspect_tool", "result": {"tool": schema}})
        args = {"name": "app__update", "arguments": {"record_id": 77}}
        before = deepcopy(args)
        value, _ = loop.act({"action_id": "call_tool", "arguments": args, "evidence_ids": []}, 1, time.monotonic() + 10)
        self.assertIn("observed", value["message"])
        self.assertEqual(args, before)
        self.assertEqual(loop.tool_attempts, 0)

    def test_alternating_calls_and_exhausted_pagination_stop(self):
        loop = self.loop()
        for i in range(7): loop.working.observe("read" + str(i % 2), {"offset": i}, {"entities": [], "next_offset": None, "offset": i}, str(i), i)
        self.assertTrue(loop.progress_stalled())

    def test_new_pages_are_progress_and_durable_page_is_bounded(self):
        loop = self.loop()
        for i in range(40): loop.working.observe("read", {"offset": i}, {"record_id": i, "next_offset": i + 1}, str(i), i)
        self.assertFalse(loop.progress_stalled())
        page = loop.working.page("bindings", limit=3)
        self.assertEqual(len(page["records"]), 3)
        self.assertEqual(page["next_offset"], 3)
        self.assertLess(len(json.dumps(loop.working.view())), 1500)

    def test_real_dispatch_loop_stops_alternation(self):
        loop = self.loop(config=Config(max_steps=12, max_stagnant_steps=3))
        from react_runtime.completion import bind_verifier
        from repair_runtime.judge import judge_episode
        from repair_runtime.policy_repair import register_episode
        data = cases()[0][2]
        loop.task = data["contract"]["goal"]
        loop.verifier = bind_verifier(self.store, data["contract"], data["before"], lambda: data["before"])
        loop.check_on_exit = True
        loop.command = [sys.executable, "-c", 'import sys,json; c=json.load(sys.stdin); print(json.dumps({"kind":"act","request_id":c["turn"]["request_id"],"action_id":"read_a" if c["turn"]["step"]%2 else "read_b","arguments":{},"evidence_ids":[],"reason":"fixture"}))']
        for name in ("read_a", "read_b"):
            loop.tools[name] = Tool(name, "Read a page", {"type": "object", "properties": {}, "additionalProperties": False},
                                    [sys.executable, "-c", 'print(\'{"records":[],"next_offset":null}\')'], {"type": "object"})
        result = loop.run()
        self.assertEqual(result["status"], "NO_PROGRESS")
        self.assertLess(result["steps"], 12)
        archive = Archive(self.root / "progress-archive", create=True)
        try:
            judged = judge_episode(archive, self.store.root)
            self.assertEqual(judged["repair_route"], "POLICY_CONTEXT", {"judge": judged, "audit": self.store.audit().get("problems")})
            group = register_episode(archive, {"judge": judged["receipt"], "episode": result})
            self.assertIsNotNone(group)
        finally: archive.close()

    def test_observed_ids_are_accepted_without_changes(self):
        loop = self.loop()
        loop.working.observe("read", {}, {"record_id": 17}, "evidence", 1)
        self.assertIsNone(loop.working.binding_error("update", {"record_id": 17}, mutation=True))
        self.assertIsNotNone(loop.working.binding_error("update", {"record_id": 18}, mutation=True))

    def test_uncertain_effect_is_never_retried(self):
        loop = self.loop()
        loop.tools["update"] = Tool("update", "write", {"type": "object"}, [sys.executable, "-c", 'print(\'{"session_error":"lost connection"}\')'], {"type": "object"}, effect="WRITE")
        value, stop = loop.act({"action_id": "update", "arguments": {}, "evidence_ids": []}, 1, time.monotonic() + 10)
        self.assertEqual(stop, "UNKNOWN_TOOL_OUTCOME")
        self.assertTrue(value["effect_uncertain"])
        self.assertEqual(loop.tool_attempts, 1)

    def test_promotion_and_negative_control_use_same_path(self):
        archive = Archive(self.root / "archive", create=True)
        try:
            archive.add_case(cases()[0][2])
            with archive.db: archive.set("active", archive.put(json.loads((ROOT / "runs/learning/live-acceptance-v2/accepted-program.json").read_text())))
            freeze(archive, challenges(17, 6, function="related"))
            target = fixtures(0, 1)[0]
            group = register_failure(archive, "discovery", target)
            first = promote(archive, {**legacy_policy(), "discovery": "weighted"}, group)
            self.assertTrue(first["accepted"], first["conditions"])
            versions = archive.meta("active"), archive.meta("active_policy")
            group2 = register_failure(archive, "discovery", {**target, "goal": target["goal"] + " "})
            rejected = promote(archive, legacy_policy(), group2)
            self.assertFalse(rejected["accepted"])
            self.assertFalse(rejected["conditions"]["no_sealed_regression"])
            self.assertEqual(versions, (archive.meta("active"), archive.meta("active_policy")))
            spent = archive.meta("proposals_spent")
            with self.assertRaises(ValueError): promote(archive, legacy_policy(), group2)
            self.assertEqual(archive.meta("proposals_spent"), spent)
            import repair_runtime.policy_repair as repair
            source_reader = repair.runtime_sources
            def changed_during_live_gate(ref):
                repair.runtime_sources = lambda: {}
                return {"passed": True}
            try:
                binding_group = register_failure(archive, "binding", fixtures(0, 1)[1])
                value = promote(archive, {**archive.get(versions[1]), "binding": "observed"}, binding_group, live_gate=changed_during_live_gate)
                self.assertFalse(value["accepted"])
                self.assertFalse(value["conditions"]["sources_unchanged"])
                self.assertEqual(versions, (archive.meta("active"), archive.meta("active_policy")))
            finally: repair.runtime_sources = source_reader
        finally: archive.close()


if __name__ == "__main__": unittest.main()

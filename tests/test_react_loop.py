import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from react_runtime.loop import Config, ReactLoop, Tool
from react_runtime.store import RunStore
from scripts.inspect_trace import read_evidence
from scripts.run_react import fixture_tool, verify_long, verify_short


class ReactComponentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = RunStore(Path(self.temporary.name) / "run")

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def run_loop(self, mode="scripted", long=False, config=None, verifier=verify_short):
        command = [sys.executable, str(ROOT / "react_runtime/fixtures.py"), mode]
        if long:
            command.append("--long")
        runner = ReactLoop(store=self.store, task="Original goal must survive.",
                           constraints=["Never modify records."], model_command=command,
                           tools=[fixture_tool(6000 if long else 0)], verifier=verifier,
                           config=config or Config(max_steps=8, max_context_chars=10000),
                           model_info={"provider": "scripted"})
        return runner.run()

    def packet(self, result):
        return json.loads(Path(result["judge_packet"]["path"]).read_text())

    def test_finish_requires_observed_evidence(self):
        result = self.run_loop(mode="early_finish")
        self.assertEqual(result["status"], "VERIFIED_SUCCESS")
        self.assertEqual(result["steps"], 3)
        events = self.packet(result)["events"]
        checks = [e for e in events if e["type"] == "finish_verified"]
        first = json.loads(self.store.get(checks[0]["payload"]["verification_ref"]["id"]))
        self.assertFalse(first["passed"])

    def test_long_verifier_requires_complete_reread_after_all_records(self):
        records = [{"action": "get_record", "arguments": {"record_id": f"r{i}"},
                    "result": {"proof": f"proof-for-r{i}"}, "output_id": f"output-{i}", "step": i}
                   for i in range(1, 6)]
        reread = {"action": "read_output", "arguments": {"output_id": "output-1", "json_pointer": "/proof"},
                  "result": {"start": 0, "next_start": None, "content": '"proof-for-r1"'}, "step": 6}
        proposal = {"answer": "proof-for-r1"}
        self.assertTrue(verify_long(proposal, records + [reread])[0])
        self.assertFalse(verify_long(proposal, records + [{**reread, "step": 2}])[0])
        partial = {**reread, "result": {"start": 0, "next_start": 1, "content": '"'}}
        self.assertFalse(verify_long(proposal, records + [partial])[0])

    def test_compaction_preserves_originals_and_rereads(self):
        result = self.run_loop(long=True, verifier=verify_long)
        self.assertEqual(result["status"], "VERIFIED_SUCCESS")
        self.assertGreaterEqual(result["compactions"], 2)
        packet = self.packet(result)
        self.assertTrue(packet["complete"])
        for event in packet["events"]:
            if event["type"] == "context_compacted":
                after = json.loads(self.store.get(event["payload"]["after_ref"]["id"]))
                self.assertEqual(after["task"]["objective"], "Original goal must survive.")
                self.assertEqual(after["task"]["constraints"], ["Never modify records."])
                for row in after["compacted_steps"]:
                    self.assertTrue(self.store.get(row["model_output_id"]))
                    if row["output_id"]:
                        self.assertTrue(self.store.get(row["output_id"]))
        tool_results = [a for a in packet["artifacts"] if a["kind"] == "tools"]
        self.assertGreater(tool_results[0]["bytes"], 6000)
        self.assertIn("proof-for-r1", self.store.get(tool_results[0]["id"]).decode())

    def test_unknown_action_never_dispatches(self):
        result = self.run_loop(mode="unknown", config=Config(max_steps=3))
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
        self.assertEqual(result["tool_attempts"], 0)
        self.assertFalse(any(e["type"] == "dispatch_started" for e in self.packet(result)["events"]))

    def test_invalid_json_is_saved_without_dispatch(self):
        result = self.run_loop(mode="invalid", config=Config(max_steps=2))
        self.assertEqual(result["tool_attempts"], 0)
        raw_outputs = [a for a in self.packet(result)["artifacts"] if a["kind"] == "model"]
        self.assertIn('"kind":"act","kind":"finish"', self.store.get(raw_outputs[0]["id"]).decode())

    def test_timeout_preserves_partial_stdout(self):
        result = self.run_loop(mode="partial", config=Config(model_timeout_seconds=0.2))
        self.assertEqual(result["status"], "MODEL_ERROR")
        packet = self.packet(result)
        self.assertFalse(packet["complete"])
        output = next(a for a in packet["artifacts"] if a["kind"] == "model")
        self.assertIn("unfinished", self.store.get(output["id"]).decode())

    def test_integrity_audit_detects_deleted_output(self):
        result = self.run_loop()
        self.assertTrue(result["judge_packet"]["complete"])
        output = next(a for a in self.packet(result)["artifacts"] if a["kind"] == "tools")
        (self.store.root / output["path"]).unlink()
        audit = self.store.export_judge_packet()
        self.assertFalse(audit["complete"])
        self.assertTrue(any(p.get("artifact_id") == output["id"] for p in audit["problems"]))

    def test_no_verifier_never_claims_verified_success(self):
        self.assertEqual(self.run_loop(verifier=None)["status"], "UNVERIFIED_FINISH")

    def test_pinned_context_overflow_is_explicit(self):
        result = self.run_loop(config=Config(max_context_chars=100))
        self.assertEqual(result["status"], "CONTEXT_OVERFLOW")
        self.assertFalse(any(e["type"] == "model_started" for e in self.packet(result)["events"]))

    def test_event_edits_and_missing_receipts_are_detected(self):
        self.run_loop()
        with self.store.db:
            self.store.db.execute("DELETE FROM events WHERE type='operation_result'")
            self.store.db.execute("UPDATE events SET payload='{}' WHERE type='action_allowed'")
        codes = {p["error"] for p in self.store.audit()["problems"]}
        self.assertTrue({"EVENT_SEQUENCE_GAP", "EVENT_HASH_MISMATCH", "UNPAIRED_INVOCATION"} <= codes)

    def test_original_content_corruption_is_detected(self):
        result = self.run_loop()
        output = next(a for a in self.packet(result)["artifacts"] if a["kind"] == "tools")
        path = self.store.root / output["path"]
        path.chmod(0o600)
        path.write_text("changed")
        self.assertFalse(self.store.audit()["complete"])

    def test_private_sources_are_unavailable_to_actor(self):
        result = self.run_loop()
        packet = self.packet(result)
        for kind in ("sources", "diagnostics", "metadata"):
            artifact = next(a for a in packet["artifacts"] if a["kind"] == kind)
            with self.assertRaises(KeyError):
                self.store.get(artifact["id"], actor=True)

    def test_judge_reads_report_exact_coverage_and_source_digest(self):
        result = self.run_loop(long=True, verifier=verify_long)
        output = next(a for a in self.packet(result)["artifacts"] if a["kind"] == "tools")
        read = read_evidence(self.store, output["id"], start=10, maximum=20)
        self.assertEqual(read["content"], self.store.get(output["id"]).decode()[10:30])
        self.assertEqual(read["source_sha256"], output["sha256"])
        self.assertEqual(read["next_start"], 30)
        selected = read_evidence(self.store, output["id"], pointer="/proof")
        self.assertEqual(json.loads(selected["content"]), "proof-for-r1")

    def test_judge_does_not_silently_resolve_duplicate_json_keys(self):
        original = '{"x":1,"x":2}'
        output = self.store.write("tools", original, raw=True, visible=True)
        self.assertEqual(read_evidence(self.store, output["id"])["content"], original)
        with self.assertRaises(ValueError):
            read_evidence(self.store, output["id"], pointer="/x")

    def test_failed_write_stops_and_retains_both_streams(self):
        tool = fixture_tool()
        broken = Tool(tool.name, tool.description, tool.schema,
                      [sys.executable, "-c", "import sys; print('partial write'); print('fixture error', file=sys.stderr); sys.exit(1)"],
                      tool.output_schema, effect="WRITE")
        runner = ReactLoop(store=self.store, task="Fixture only", constraints=[],
                           model_command=[sys.executable, str(ROOT / "react_runtime/fixtures.py"), "scripted"],
                           tools=[broken], verifier=verify_short)
        result = runner.run()
        self.assertEqual(result["status"], "UNKNOWN_TOOL_OUTCOME")
        self.assertEqual(result["steps"], 1)
        event = next(e for e in self.packet(result)["events"] if e["type"] == "operation_result")
        self.assertIn(b"partial write", self.store.get(event["payload"]["output_ref"]["id"]))
        self.assertIn(b"fixture error", self.store.get(event["payload"]["stderr_ref"]["id"]))

    def test_compaction_preserves_remaining_budgets(self):
        result = self.run_loop(long=True, verifier=verify_long)
        for event in self.packet(result)["events"]:
            if event["type"] == "context_compacted":
                before = json.loads(self.store.get(event["payload"]["before_ref"]["id"]))
                after = json.loads(self.store.get(event["payload"]["after_ref"]["id"]))
                self.assertEqual(before["turn"], after["turn"])

    def check_logging_failure(self, event_type, expected_calls):
        tool = fixture_tool()
        marker = Path(self.temporary.name) / "effect-count.txt"
        command = [sys.executable, "-c",
                   "from pathlib import Path; import sys,json; p=Path(sys.argv[1]); "
                   "p.write_text(p.read_text()+'x' if p.exists() else 'x'); "
                   "print(json.dumps({'record_id':'123','status':'delivered','proof':'p','padding':''}))",
                   str(marker)]
        counted = Tool(tool.name, tool.description, tool.schema, command, tool.output_schema, effect="WRITE")
        runner = ReactLoop(store=self.store, task="Fault injection only", constraints=[],
                           model_command=[sys.executable, str(ROOT / "react_runtime/fixtures.py"), "scripted"],
                           tools=[counted], verifier=verify_short)
        original = self.store.event

        def fail_selected(kind, *args, **kwargs):
            if kind == event_type:
                raise OSError("Injected ledger write failure")
            return original(kind, *args, **kwargs)

        with patch.object(self.store, "event", side_effect=fail_selected):
            result = runner.run()
        actual = len(marker.read_text()) if marker.exists() else 0
        self.assertEqual(actual, expected_calls)
        self.assertEqual(result["status"], "RUNTIME_ERROR")
        self.assertEqual(result["steps"], 1)
        self.assertFalse(result["judge_packet"]["complete"])

    def test_dispatch_logging_failure_prevents_effect(self):
        self.check_logging_failure("dispatch_started", expected_calls=0)

    def test_result_logging_failure_stops_without_repeating_effect(self):
        self.check_logging_failure("operation_result", expected_calls=1)


if __name__ == "__main__":
    unittest.main()

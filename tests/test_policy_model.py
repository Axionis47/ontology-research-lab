import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from react_runtime.policy import legacy_policy, validate_policy, ranking, rank_tools
from repair_runtime.policy_proposer import PolicyModelProposer, response_schema
from repair_runtime.policy_repair import freeze, register_failure, work
from repair_runtime.store import Archive
from repair_runtime.evaluation import challenges
from repair_runtime.inference import continue_learning
from react_runtime.loop import ReactLoop
from react_runtime.store import RunStore


class ModelPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.archive = Archive(self.root / "archive", create=True)
        freeze(self.archive, challenges(8, 3, function="direct"))
        self.key = register_failure(self.archive, "discovery", {"component": "discovery", "goal": "follow record",
            "tools": [{"name": "app__unfollow_record", "description": ""}, {"name": "app__follow_record", "description": ""}], "expected": "app__follow_record"})

    def tearDown(self):
        self.archive.close(); self.tmp.cleanup()

    def model(self, body, max_calls=4):
        path = self.root / "model.py"
        path.write_text("import json,sys\nc=json.load(sys.stdin)\n" + body)
        return PolicyModelProposer("test", command=[sys.executable, str(path)], max_calls=max_calls)

    def test_model_authors_parameters_and_reads_original_evidence(self):
        model = self.model('if not c["recent_reads"]:\n print(json.dumps({"kind":"read","artifact":c["target_ref"],"offset":0,"limit":3000}))\nelse:\n print(json.dumps({"kind":"candidate","steps":{"rank_catalogue":{"name_weight":7,"description_weight":0},"inspect_shortlist":{"limit":2}},"reason":"prioritize observed action tokens"}))\n')
        result = model.one(self.archive, self.key, legacy_policy(), 0)
        self.assertEqual(result["kind"], "candidate")
        self.assertEqual(ranking(result["candidate"]), {"name_weight": 7, "description_weight": 0})
        self.assertEqual(len(result["evidence"]), 2)
        sealed_ref = self.archive.get(self.archive.meta("policy_manifest"))["sealed"]
        for ref in result["evidence"]:
            context = self.archive.get(self.archive.get(ref)["input"])
            self.assertEqual(context["original_goal"], "follow record")
            self.assertNotIn(sealed_ref, json.dumps(context))
        self.assertEqual(self.archive.meta("active_policy"), self.archive.put(legacy_policy()))

    def test_invalid_model_output_exhausts_calls_without_handwritten_fallback(self):
        model = self.model('print(json.dumps({"kind":"candidate","steps":{"run_python":{"code":"print(1)"}},"reason":"invalid"}))\n', max_calls=2)
        before = self.archive.meta("active"), self.archive.meta("active_policy")
        result = work(self.archive, proposer=model)
        self.assertEqual(result[0]["status"], "needs_evidence")
        self.assertEqual(before, (self.archive.meta("active"), self.archive.meta("active_policy")))
        self.assertEqual(len(self.archive.meta("policy_groups")[self.key]["model_attempts"]), 1)

    def test_rejections_return_to_model_and_candidate_budget_stops(self):
        # Deliberately ineffective but valid proposals go through real cheap
        # promotion gates. A second invocation sees only redacted receipts.
        model = self.model('assert all("sealed_after" not in row["excerpt"] for row in c["evidence_and_rejections"])\nprint(json.dumps({"kind":"candidate","steps":{"observe_declared_state":{}},"reason":"test failed hypothesis"}))\n')
        before = self.archive.meta("active"), self.archive.meta("active_policy")
        result = work(self.archive, proposer=model)
        self.assertEqual(len(result), 3)
        self.assertFalse(any(r["accepted"] for r in result))
        self.assertEqual(result[-1]["status"], "DUPLICATE_CANDIDATE")
        self.assertEqual(before, (self.archive.meta("active"), self.archive.meta("active_policy")))
        self.assertEqual(work(self.archive, proposer=model), [])

    def test_frozen_kernel_does_not_call_operator_search(self):
        with self.archive.db:
            self.archive.set("frozen_kernel", True)
            self.archive.set("policy_groups", {})
        with patch("repair_runtime.inference.work", side_effect=AssertionError("kernel search called")):
            self.assertTrue(continue_learning(self.archive)["kernel_frozen"])

    def test_context_program_executes_outside_prompt(self):
        policy = {**legacy_policy(), "version": 2, "context": [{"op": "bound_history", "recent": 0, "index": 0},
                    {"op": "carry_state", "fields": ["pending"]}]}
        store = RunStore(self.root / "episode")
        try:
            loop = ReactLoop(store=store, task="original goal", constraints=[], tools=[], model_command=[], verifier=None, execution_policy=policy)
            loop.working.reject("update", "ground the identity", None, 1)
            context = json.loads(loop.prepare_prompt(1, "r"))
            self.assertEqual(context["task"]["objective"], "original goal")
            self.assertIn("pending_corrections", context["working_state"])
            self.assertNotIn("execution_policy", context)
        finally: store.close()
        with self.assertRaises(ValueError): validate_policy({**policy, "context": [{"op": "bound_history", "recent": 9000, "index": 0}]})

    def test_composed_ranking_changes_actual_tool_order(self):
        tools = [{"name": "a__follow", "description": ""}, {"name": "b__record", "description": "follow"}]
        self.assertEqual(rank_tools(tools, "follow", {"name_weight": 1, "description_weight": 4})[0]["name"], "b__record")
        self.assertEqual(rank_tools(tools, "follow", {"name_weight": 7, "description_weight": 0})[0]["name"], "a__follow")

    def test_provider_enforces_repair_contract_without_changing_executor_settings(self):
        from jsonschema import Draft202012Validator
        from react_runtime.ollama import payload, configuration
        schema = response_schema("binding", {"original-ref"})
        validator = Draft202012Validator(schema)
        self.assertTrue(validator.is_valid({"kind": "candidate", "steps": {"require_observed_ids": {}}, "reason": "ground inputs"}))
        self.assertFalse(validator.is_valid({"allowed_evidence": [], "attempt": 0}))
        self.assertFalse(validator.is_valid({"kind": "candidate", "steps": {"check_bound_update": {}}, "reason": "missing dependency"}))
        self.assertFalse(validator.is_valid({"kind": "candidate", "steps": {"require_observed_ids": {"op": "check_bound_update"}}, "reason": "parameter injection"}))
        self.assertFalse(validator.is_valid({"kind": "read", "artifact": "sealed-ref", "offset": 0, "limit": 10}))
        config = configuration()
        rendered = payload({"original_goal": "task", "_response_schema": schema, "system_instructions": "Repair only"}, config)
        self.assertEqual(rendered["format"], schema)
        self.assertEqual(rendered["options"]["num_predict"], config["num_predict"])
        self.assertNotIn("_response_schema", rendered["messages"][1]["content"])


if __name__ == "__main__": unittest.main()

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import ValidationError

from react_runtime.completion import bind_verifier, evaluate
from react_runtime.loop import ReactLoop
from react_runtime.store import RunStore

ROOT = Path(__file__).resolve().parents[1]


class CompletionTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads((ROOT / "examples/completion_fixture.json").read_text())
        self.contract, self.before = fixture["contract"], fixture["before"]
        self.after = deepcopy(self.before)
        self.after["revision"] = "1"
        for entity in self.after["entities"]:
            if entity["id"] in {"ticket:1", "ticket:2"}:
                entity["properties"]["reviewed"] = True

    def checks(self, result):
        return {c["requirement_id"]: c for c in result["checks"]}

    def test_relational_selection_and_complete_update(self):
        result = evaluate(self.contract, self.before, self.after)
        self.assertEqual(result["target_ids"], ["ticket:1", "ticket:2"])
        self.assertEqual((result["state"], result["reward"]), ("TRUE", 1))

    def test_missed_target_identifies_specific_failed_requirement(self):
        self.after["entities"][3]["properties"]["reviewed"] = False
        result = evaluate(self.contract, self.before, self.after)
        self.assertEqual(result["reward"], 0)
        self.assertEqual(self.checks(result)["targets_updated"]["entity_ids"], ["ticket:2"])
        self.assertEqual(self.checks(result)["unrelated_state_preserved"]["value"], "TRUE")

    def test_unintended_update_fails_even_when_all_targets_are_updated(self):
        self.after["entities"][4]["properties"]["reviewed"] = True
        result = evaluate(self.contract, self.before, self.after)
        self.assertEqual(self.checks(result)["targets_updated"]["value"], "TRUE")
        self.assertEqual(self.checks(result)["unrelated_state_preserved"]["entity_ids"], ["ticket:3"])
        self.assertEqual(result["reward"], 0)

    def test_partial_wrong_scope_or_duplicate_evidence_cannot_establish_completion(self):
        for problem in ("partial", "scope", "duplicate"):
            with self.subTest(problem=problem):
                after = deepcopy(self.after)
                if problem == "partial": after["complete"] = False
                elif problem == "scope": after["scope"] = "another-episode"
                else: after["entities"].append(deepcopy(after["entities"][0]))
                result = evaluate(self.contract, self.before, after)
                self.assertEqual((result["state"], result["reward"]), ("UNKNOWN", None))

    def test_missing_selection_fact_is_unknown_and_explicit_null_is_a_value(self):
        del self.before["entities"][0]["properties"]["region"]
        self.assertEqual(evaluate(self.contract, self.before, self.after)["state"], "UNKNOWN")
        self.before["entities"][0]["properties"]["region"] = None
        result = evaluate(self.contract, self.before, self.before)
        self.assertEqual(result["target_ids"], [])
        self.assertEqual(result["state"], "TRUE")

    def test_changed_selection_field_does_not_move_the_goalposts(self):
        self.after["entities"][2]["properties"]["status"] = "closed"
        self.after["entities"][2]["properties"]["reviewed"] = False
        result = evaluate(self.contract, self.before, self.after)
        self.assertIn("ticket:1", result["target_ids"])
        self.assertEqual(self.checks(result)["targets_updated"]["value"], "FALSE")
        self.assertEqual(self.checks(result)["unrelated_state_preserved"]["value"], "FALSE")

    def test_protected_relation_removal_and_record_deletion_are_detected(self):
        for kind in ("edge", "entity"):
            with self.subTest(kind=kind):
                after = deepcopy(self.after)
                after["relations"] = [r for r in after["relations"] if r["source"] != "ticket:4"]
                if kind == "entity": after["entities"] = [e for e in after["entities"] if e["id"] != "ticket:4"]
                result = evaluate(self.contract, self.before, after)
                self.assertEqual(self.checks(result)["unrelated_state_preserved"]["value"], "FALSE")

    def test_relation_update_reuses_entities_and_checks_other_edges(self):
        self.contract["update"] = {"kind": "ensure_relation", "relation_type": "review_queue",
                                   "anchor_id": "customer:west", "direction": "out"}
        after = deepcopy(self.before)
        for target in ("ticket:1", "ticket:2"):
            after["relations"].append({"source": "customer:west", "type": "review_queue", "target": target})
        self.assertEqual(evaluate(self.contract, self.before, after)["state"], "TRUE")
        after["relations"].append({"source": "customer:west", "type": "review_queue", "target": "ticket:3"})
        self.assertEqual(evaluate(self.contract, self.before, after)["state"], "FALSE")

    def test_boolean_does_not_equal_numeric_one(self):
        self.after["entities"][2]["properties"]["reviewed"] = 1
        self.assertEqual(evaluate(self.contract, self.before, self.after)["state"], "FALSE")

    def test_contract_cannot_remove_required_checks_or_invent_update_operations(self):
        for edit in ({"checks": []}, {"update": {"kind": "anything"}}):
            with self.assertRaises(ValidationError):
                evaluate({**self.contract, **edit}, self.before, self.after)

    def test_binding_is_pinned_and_goal_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(Path(tmp) / "run")
            try:
                original_goal = self.contract["goal"]
                verify = bind_verifier(store, self.contract, self.before, lambda: self.after)
                self.contract["update"]["value"] = False
                self.before["entities"] = []
                self.assertEqual(verify.bound_goal, original_goal)
                self.assertTrue(verify({"answer": "arbitrary claim"}, [])[0])
                with self.assertRaisesRegex(ValueError, "different original goal"):
                    ReactLoop(store=store, task="Another goal", constraints=[], model_command=["unused"],
                              tools=[], verifier=verify)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()

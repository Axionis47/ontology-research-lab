import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("six", HERE / "run.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.world = json.loads((HERE / "facts.json").read_text())
        self.ontology = json.loads((HERE / "ontology.json").read_text())

    def test_identical_task_facts_all_six(self):
        payloads = [m.payload(mode, self.world, self.ontology) for mode in ("full", "retrieved", "inspect", "query", "function", "check")]
        self.assertEqual(len({m.sha(p["facts"]) for p in payloads}), 1)
        self.assertEqual(len({m.sha(p["task"]) for p in payloads}), 1)

    def test_retrieval_preserves_rules_and_dependencies(self):
        selected = m.closure(self.ontology)
        self.assertEqual(selected["eligibility"], self.ontology["definitions"]["eligibility"])
        self.assertIn("heldBy", selected)
        self.assertNotIn("Invoice", selected)

    def test_inspection_returns_same_definitions(self):
        result = m.execute({"type": "call", "name": "inspect_schema", "arguments": {"names": ["eligibility"]}}, "inspect", self.world, self.ontology)
        self.assertEqual(result["definitions"], m.closure(self.ontology))

    def test_business_constraints(self):
        expected = {"Maya": ["R6"], "Noah": [], "Rin": ["R2"], "Tao": ["R5"]}
        for row in self.world["assignments"]:
            self.assertEqual(m.violations(row, self.world), expected[row["person"]])
        self.assertEqual(m.assess_person("Unknown", self.world)["status"], "UNKNOWN")

    def test_query_is_generic_not_automatic_eligibility(self):
        result = m.execute({"type": "call", "name": "query_assignments", "arguments": {"predicates": [{"field": "environment", "op": "eq", "value": "Production"}]}}, "query", self.world, self.ontology)
        self.assertEqual({r["person"] for r in result["assignments"]}, {"Maya", "Noah", "Tao"})

    def test_bad_query_and_unsupported_function_binding(self):
        for args in ({"predicates": [{"field": "invented", "op": "eq", "value": "x"}]}, {"predicates": [{"field": "active", "op": "eq", "value": 1}]}):
            with self.assertRaises(ValueError):
                m.execute({"type": "call", "name": "query_assignments", "arguments": args}, "query", self.world, self.ontology)
        with self.assertRaises(ValueError):
            m.execute({"type": "call", "name": "find_eligible_approvers", "arguments": {**self.world["task"], "environment": "Staging"}}, "function", self.world, self.ontology)

    def test_selector_and_checker_have_distinct_scope(self):
        selected = m.execute({"type": "call", "name": "find_eligible_approvers", "arguments": self.world["task"]}, "function", self.world, self.ontology)
        self.assertEqual([p["person"] for p in selected["candidates"]], ["Noah"])
        checked = m.execute({"type": "call", "name": "check_candidates", "arguments": {"people": ["Maya"]}}, "check", self.world, self.ontology)
        self.assertEqual([p["person"] for p in checked["checks"]], ["Maya"])

    def test_same_gate_rejects_stale_and_wrong_meaning(self):
        answer = {"type": "finish", "person": "Noah", "evidence_ids": ["a-noah", "d1"], "ontology_version": self.ontology["version"], "graph_revision": 1, "rule_ids": m.RULE_IDS}
        self.assertTrue(m.score(answer, self.world, self.ontology))
        self.assertTrue(m.gate(answer, self.world, self.ontology)["admitted"])
        changed = copy.deepcopy(self.world)
        changed["revision"] = 2
        self.assertFalse(m.gate(answer, changed, self.ontology)["admitted"])
        self.assertFalse(m.gate({**answer, "ontology_version": "other"}, self.world, self.ontology)["admitted"])
        self.assertFalse(m.gate({**answer, "person": "Maya"}, self.world, self.ontology)["admitted"])


if __name__ == "__main__":
    unittest.main()

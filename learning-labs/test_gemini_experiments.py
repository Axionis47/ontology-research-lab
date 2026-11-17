"""Independent scorer checks, no model calls or external actions."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gemini_lessons", HERE / "gemini_experiments.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ScoringTests(unittest.TestCase):
    def test_all_references_accepted_and_empty_answers_rejected(self):
        for folder in sorted(HERE.glob("[0-9][0-9]-*")):
            with self.subTest(folder=folder.name):
                expected = json.loads((folder / "gemini-expected.json").read_text())
                data = json.loads((folder / "gemini-input.json").read_text())
                self.assertTrue(module.check_answer(expected, expected, folder.name[:2], data)["passed"])
                self.assertFalse(module.check_answer({}, expected, folder.name[:2], data)["passed"])

    def test_reversed_edge_fails(self):
        self.assertFalse(module.equal({"positive_triples": [["Maya", "maintains", "LoginService"]]},
                                      {"positive_triples": [["LoginService", "maintains", "Maya"]]}))

    def test_json_types_and_duplicates_matter(self):
        self.assertFalse(module.equal(True, 1))
        self.assertFalse(module.equal(["Maya", "Maya"], ["Maya"]))
        self.assertFalse(module.equal(None, "null"))

    def test_answer_sets_can_be_reordered(self):
        self.assertTrue(module.equal(["plan3", "decision8"], ["decision8", "plan3"]))

    def test_gate_never_accepts_actor_authority_flag(self):
        folder = HERE / "07-runtime-enforcement"
        expected = json.loads((folder / "gemini-expected.json").read_text())
        data = json.loads((folder / "gemini-input.json").read_text())
        actual = copy.deepcopy(expected)
        actual["A"]["approved"] = True
        result = module.check_answer(actual, expected, "07", data)
        self.assertFalse(result["passed"])
        self.assertFalse(result["runtime_effects"]["A"]["after"]["deployed"])

    def test_extra_field_rejected(self):
        result = module.check_answer({"A": "graph", "B": "ontology", "extra": True},
                                     {"A": "graph", "B": "ontology"}, "02", {})
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()

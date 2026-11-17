import copy
import json
from pathlib import Path
import unittest
from engine import *

HERE = Path(__file__).resolve().parent


class ComplexOntologyTests(unittest.TestCase):
    def setUp(self):
        self.w = json.loads((HERE / "facts.json").read_text())
        self.o = json.loads((HERE / "ontology.json").read_text())
        self.oracle = json.loads((HERE / "oracle.json").read_text())

    def person(self, name, role="OpsApprover"):
        return assess_person(name, role, self.w)

    def test_hand_authored_oracle(self):
        panels = valid_panels(self.w)
        self.assertEqual([r["panel"] for r in panels], [self.oracle["expected_panel"]])
        for role, key in (("OpsApprover", "individually_eligible_ops"), ("SecurityApprover", "individually_eligible_security")):
            self.assertEqual(sorted(r["id"] for r in self.w["records"] if r["type"] == "Person" and self.person(r["id"], role)["status"] == "ELIGIBLE"), self.oracle[key])

    def test_same_task_facts_and_rules(self):
        bodies = [payload(mode, self.w, self.o) for mode in ("full", "retrieved", "inspect", "query", "function", "check")]
        self.assertEqual(len({sha(b["task"]) for b in bodies}), 1)
        self.assertEqual(len({sha(b["facts"]) for b in bodies}), 1)
        self.assertEqual(closure(self.o)["eligibility"], self.o["definitions"]["eligibility"])

    def test_scope_hierarchy_and_sibling(self):
        for scope in ("svc-login", "project-atlas", "org-mercury"): self.assertTrue(covers(scope, self.w))
        self.assertFalse(covers("project-other", self.w))
        self.assertEqual(self.person("Wes", "SecurityApprover")["status"], "INELIGIBLE")

    def test_exclusive_expiry_and_inclusive_risk(self):
        self.assertEqual(self.person("Vera")["status"], "ELIGIBLE")
        index(self.w)["del-Vera"]["maxRisk"] = 3
        self.assertEqual(self.person("Vera")["status"], "INELIGIBLE")
        index(self.w)["del-Vera"]["maxRisk"] = 4
        index(self.w)["del-Vera"]["validUntil"] = self.w["task"]["at"]
        self.assertEqual(self.person("Vera")["status"], "INELIGIBLE")

    def test_grant_cap_and_delegate_flag(self):
        self.assertEqual(self.person("Noah")["status"], "INELIGIBLE")
        self.assertEqual(self.person("Xena", "SecurityApprover")["status"], "INELIGIBLE")
        index(self.w)["g-Tao"]["delegable"] = True
        self.assertEqual(self.person("Xena", "SecurityApprover")["status"], "ELIGIBLE")

    def test_delegator_certificate_not_required(self):
        self.assertEqual(self.person("Iris")["status"], "INELIGIBLE")
        self.assertEqual(self.person("Vera")["status"], "ELIGIBLE")
        index(self.w)["del-Vera"]["issuer"] = "Noah"
        self.assertEqual(self.person("Vera")["status"], "INELIGIBLE")

    def test_redelegation_not_a_direct_grant(self):
        index(self.w)["del-Vera"]["grant"] = "del-Uma"
        self.assertEqual(self.person("Vera")["status"], "INELIGIBLE")

    def test_certification_scope(self):
        self.assertEqual(self.person("Yuri")["status"], "INELIGIBLE")
        index(self.w)["c-Vera"]["environment"] = "Staging"
        self.assertEqual(self.person("Vera")["status"], "INELIGIBLE")

    def test_author_and_deny_precedence(self):
        self.assertIn("R7", self.person("Maya")["violated_rules"])
        self.assertIn("R8", self.person("Zoe")["violated_rules"])
        index(self.w)["deny-Zoe"]["validUntil"] = "2026-11-16"
        self.assertEqual(self.person("Zoe")["status"], "ELIGIBLE")

    def test_pair_constraint_not_individual_eligibility(self):
        self.assertEqual(self.person("Uma")["status"], "ELIGIBLE")
        self.assertEqual(self.person("Tao", "SecurityApprover")["status"], "ELIGIBLE")
        pair = check_panel({"ops": "Uma", "security": "Tao"}, self.w)
        self.assertIn("R9", pair["violated_rules"])
        self.assertIn("R10", check_panel({"ops": "Vera", "security": "Vera"}, self.w)["violated_rules"])

    def test_ambiguous_home_team_blocks(self):
        duplicate = {**index(self.w)["m-Vera"], "id": "m-Vera-second", "team": "Security"}
        self.w["records"].append(duplicate)
        self.assertIn("R9", self.person("Vera")["violated_rules"])

    def test_generic_traversal_and_query_not_selector(self):
        call = {"type": "call", "name": "traverse", "arguments": {"ids": ["svc-login"], "relation": "project", "direction": "out"}}
        self.assertEqual(execute(call, "query", self.w, self.o)["records"][0]["id"], "project-atlas")
        call = {"type": "call", "name": "query_records", "arguments": {"type": "Grant", "where": {"role": "OpsApprover"}}}
        self.assertIn("g-Noah", {r["id"] for r in execute(call, "query", self.w, self.o)["records"]})

    def test_invalid_calls(self):
        with self.assertRaises(ValueError):
            execute({"type": "call", "name": "query_records", "arguments": {"type": "Grant", "where": {"active": 1}}}, "query", self.w, self.o)
        with self.assertRaises(ValueError):
            execute({"type": "call", "name": "find_valid_panels", "arguments": {"deployment_id": "d2", "at": "2027-01-01"}}, "function", self.w, self.o)

    def test_complete_proof_scoring_and_stale_gate(self):
        panel = valid_panels(self.w)[0]
        answer = {"type": "finish", "panel": panel["panel"], "proof_ids": panel["proof_ids"], "rule_ids": RULE_IDS,
                  "ontology_version": self.o["version"], "graph_revision": self.w["revision"]}
        self.assertTrue(score(answer, self.w, self.o))
        incomplete = {**answer, "proof_ids": [r for r in answer["proof_ids"] if r != "del-Vera"]}
        self.assertFalse(score_details(incomplete, self.w, self.o)["proof_complete"])
        self.assertTrue(gate(answer, self.w, self.o)["admitted"])
        changed = revoked(self.w)
        self.assertEqual(valid_panels(changed), self.oracle["after_revocation_valid_panels"])
        self.assertFalse(gate(answer, changed, self.o)["admitted"])
        self.assertFalse(gate({**answer, "graph_revision": changed["revision"]}, changed, self.o)["admitted"])


if __name__ == "__main__":
    unittest.main()

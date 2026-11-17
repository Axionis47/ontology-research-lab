"""Offline boundary tests. These mocks are never counted as native model evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from repair_runtime.gemini_judge import evidence_packet, validate_response
from repair_runtime.inference import run_request, continue_learning
from repair_runtime.store import Archive
from scripts.demo_repair_scoring import cases


class GeminiDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.archive = Archive(Path(self.temp.name) / "archive", create=True)
        self.result = run_request(self.archive, {"request_id": "unit-only", "adapter": "local",
            "actor": "reference", "data": cases()[0][2]}, learn=False)
        self.packet = evidence_packet(self.archive, self.result)

    def tearDown(self):
        self.archive.close()
        self.temp.cleanup()

    def response(self):
        evidence = next(e for e in self.packet["evidence"] if e["kind"] == "program_preflight")
        return {"kind": "judge_assessment", "needs_more_evidence": False, "findings": [{
            "severity": "HIGH", "criterion": "FUNCTION_COMPUTATION", "status": "SUPPORTED",
            "component": "FUNCTION", "symptom": "Fixture preflight fails", "hypothesis": "Missing relationship composition",
            "citations": [{"evidence_id": evidence["evidence_id"], "relationship": "SUPPORTS",
                "locator": {"kind": "WHOLE", "path": None, "start": None, "end": None}}],
            "confidence": 0.8, "evidence_gaps": [], "repair_class": "DOMAIN_PACKAGE",
            "distinguishing_test": "Replay original case", "preserve_behavior": "Preserve unrelated records"}]}

    def test_unknown_citation_cannot_authorize_a_proposal(self):
        response = self.response()
        response["findings"][0]["citations"][0]["evidence_id"] = "00000000-0000-0000-0000-000000000000"
        with self.assertRaisesRegex(ValueError, "not supplied"):
            validate_response(response, self.packet)
        envelope = {"response": json.dumps(response), "stats": {"models": {"fixture": {}}}}
        with patch("scripts.check_models.gemini_request", return_value=envelope), \
             patch("repair_runtime.proposer.ModelProposer", side_effect=AssertionError("Proposer must not run")):
            result = continue_learning(self.archive)
        self.assertEqual(result["reason"], "INVALID_DIAGNOSIS")
        self.assertEqual(self.archive.meta("proposals_spent"), 0)

    def test_unavailable_judge_never_falls_back_to_another_proposer(self):
        before = self.archive.meta("active")
        with patch("scripts.check_models.gemini_request", side_effect=RuntimeError("transport unavailable")), \
             patch("repair_runtime.inference.work", side_effect=AssertionError("No diagnosis")):
            result = continue_learning(self.archive)
        self.assertEqual(result["reason"], "JUDGE_UNAVAILABLE")
        self.assertEqual(self.archive.meta("active"), before)
        self.assertEqual(self.archive.meta("proposals_spent"), 0)

    def test_valid_diagnosis_is_passed_to_distinct_gemini_proposer_and_gate(self):
        envelope = {"response": json.dumps(self.response()), "stats": {"models": {"fixture": {}}}}
        proposer = Mock()
        with patch("scripts.check_models.gemini_request", return_value=envelope), \
             patch("repair_runtime.proposer.ModelProposer", return_value=proposer) as factory, \
             patch("repair_runtime.inference.work", return_value={"decisions": []}) as work:
            result = continue_learning(self.archive)
        self.assertEqual(factory.call_args.args, ("gemini",))
        self.assertEqual(factory.call_args.kwargs["diagnosis"]["receipt"], result["diagnosis"])
        self.assertEqual(work.call_args.args, (self.archive, proposer))
        self.assertEqual(work.call_args.kwargs["case_id"], result["diagnosed_case"])
        self.assertTrue(callable(work.call_args.kwargs["validation_gate"]))
        self.assertEqual(result["status"], "NO_IMPROVEMENT")


if __name__ == "__main__": unittest.main()

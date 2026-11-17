import copy
import json
from pathlib import Path
import unittest

from gap_detection import GapProtocolError, detect, reproduces


class GapDetectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(Path(__file__).with_name("atlas-gap-fixture.json").read_text())

    def test_two_distinct_leads_expose_a_reproducible_mismatch(self):
        report = detect(self.fixture)
        self.assertEqual(report["status"], "GAP_DETECTED")
        self.assertEqual(report["check"]["observed"]["distinct_count"], 2)
        self.assertTrue(reproduces(self.fixture, report))
        self.assertEqual(report["root_cause"], "UNDETERMINED")
        self.assertFalse(report["schema_change_authorized"])

    def test_same_input_deduplicates_to_same_receipt(self):
        self.assertEqual(detect(self.fixture)["receipt_id"], detect(copy.deepcopy(self.fixture))["receipt_id"])

    def test_one_lead_passes_only_the_declared_check(self):
        self.fixture["evidence"]["record"]["active_lead_ids"] = ["person:maya"]
        report = detect(self.fixture)
        self.assertEqual(report["status"], "CHECK_PASSED")
        self.assertEqual(report["next_action"], "CONTINUE_OTHER_REQUIRED_CHECKS")

    def test_duplicate_rows_do_not_create_a_cardinality_gap(self):
        self.fixture["evidence"]["record"]["active_lead_ids"] = ["person:maya", "person:maya"]
        self.assertEqual(detect(self.fixture)["status"], "CHECK_PASSED")

    def test_empty_result_does_not_prove_a_schema_gap(self):
        self.fixture["evidence"]["record"]["active_lead_ids"] = []
        report = detect(self.fixture)
        self.assertEqual(report["status"], "CHECK_PASSED")
        self.assertEqual(report["diagnostic"], "NO_MAX_COUNT_VIOLATION")

    def expect_code(self, code):
        with self.assertRaises(GapProtocolError) as context:
            detect(self.fixture)
        self.assertEqual(context.exception.code, code)

    def test_missing_field_is_missing_data(self):
        del self.fixture["evidence"]["record"]["active_lead_ids"]
        self.expect_code("MISSING_DATA")

    def test_access_denial_is_not_a_schema_gap(self):
        self.fixture["evidence"]["access"] = "denied"
        self.expect_code("ACCESS_DENIED")

    def test_source_failure_is_not_a_schema_gap(self):
        self.fixture["evidence"]["operation_status"] = "timeout"
        self.expect_code("SOURCE_UNAVAILABLE")

    def test_partial_scope_is_reported(self):
        self.fixture["evidence"]["scope_complete"] = False
        self.expect_code("NEEDS_SCOPE")

    def test_unallowed_predicate_is_reported(self):
        self.fixture["context"]["allowed_predicates"] = []
        self.expect_code("NEEDS_SCOPE")

    def test_wrong_mapping_is_not_an_ontology_change(self):
        self.fixture["mapping"]["target_path"] = "hasFormerLead"
        self.expect_code("MAPPING_MISMATCH")

    def test_changed_source_does_not_reproduce_old_receipt(self):
        report = detect(self.fixture)
        self.fixture["evidence"]["source_revision"] = "18"
        self.assertFalse(reproduces(self.fixture, report))

    def test_changed_ontology_does_not_reproduce_old_receipt(self):
        report = detect(self.fixture)
        self.fixture["ontology"]["shape"]["max_count"] = 2
        self.assertFalse(reproduces(self.fixture, report))

    def test_changed_mapping_does_not_reproduce_old_receipt(self):
        report = detect(self.fixture)
        self.fixture["mapping"]["version"] = "2"
        self.assertFalse(reproduces(self.fixture, report))

    def test_model_cannot_claim_schema_gap_in_detection_receipt(self):
        report = detect(self.fixture)
        report["root_cause"] = "SCHEMA_GAP"
        self.assertFalse(reproduces(self.fixture, report))

    def test_forged_observation_is_rejected(self):
        report = detect(self.fixture)
        report["check"]["observed"]["distinct_count"] = 3
        self.assertFalse(reproduces(self.fixture, report))

    def test_invalid_id_list_is_rejected(self):
        self.fixture["evidence"]["record"]["active_lead_ids"] = ["person:maya", None]
        self.expect_code("INVALID_INPUT")

    def test_boolean_is_not_a_count_contract(self):
        self.fixture["ontology"]["shape"]["max_count"] = True
        self.expect_code("INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()

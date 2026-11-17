import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from react_runtime.repair_scoring import digest, read_run, score_comparison
from react_runtime.store import RunStore, json_bytes
from scripts.demo_repair_scoring import run_comparison


def replace_json(path, value):
    path.chmod(0o600)
    path.write_bytes(json_bytes(value))


class RepairScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_temp = tempfile.TemporaryDirectory()
        cls.baseline = Path(cls.base_temp.name) / "comparison"
        cls.initial = run_comparison(cls.baseline)

    @classmethod
    def tearDownClass(cls):
        cls.base_temp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "comparison"
        shutil.copytree(self.baseline, self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_real_paired_episodes_accept_the_repaired_selector(self):
        result = score_comparison(self.root)
        self.assertEqual(result["decision"], "ACCEPT_FOR_DEVELOPMENT")
        self.assertEqual(result["pass_counts"], {"parent": 2, "candidate": 4})
        self.assertEqual(result["fixed_cases"], ["relationship_filter", "different_links"])
        self.assertEqual(result["regressed_cases"], [])
        self.assertFalse(result["promoted"])

    def test_missing_case_is_inconclusive_and_never_dropped_from_denominator(self):
        path = self.root / "runs.json"
        replace_json(path, json.loads(path.read_text())[:-1])
        result = score_comparison(self.root)
        self.assertEqual(result["decision"], "INCONCLUSIVE")
        self.assertEqual(result["scheduled_cases"], 4)
        self.assertEqual(len(result["unavailable"]), 1)

    def test_duplicate_and_unscheduled_runs_are_invalid(self):
        path = self.root / "runs.json"
        original = json.loads(path.read_text())
        for mutation in (original + [original[0]], [{**original[0], "case_id": "invented"}] + original[1:]):
            with self.subTest(mutation=mutation[0]["case_id"]):
                replace_json(path, mutation)
                self.assertEqual(score_comparison(self.root)["decision"], "INVALID")

    def test_changed_checker_binding_is_invalid(self):
        path = self.root / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["protected_sources"]["react_runtime/completion.py"] = "0" * 64
        replace_json(path, manifest)
        self.assertEqual(score_comparison(self.root)["decision"], "INVALID")

    def test_changed_goal_cannot_be_hidden_by_updating_input_hash(self):
        path = self.root / "manifest.json"
        manifest = json.loads(path.read_text())
        ref = manifest["cases"][0]["input"]
        input_path = self.root / ref["path"]
        data = json.loads(input_path.read_text())
        data["contract"]["goal"] = "A different task"
        replace_json(input_path, data)
        ref["sha256"] = digest(input_path)
        replace_json(path, manifest)
        self.assertEqual(score_comparison(self.root)["decision"], "INVALID")

    def test_changed_initial_state_is_invalid(self):
        manifest = json.loads((self.root / "manifest.json").read_text())
        path = self.root / manifest["cases"][0]["input"]["path"]
        data = json.loads(path.read_text())
        data["before"]["entities"] = []
        replace_json(path, data)
        self.assertEqual(score_comparison(self.root)["decision"], "INVALID")

    def test_unknown_result_blocks_acceptance(self):
        # Exercise the policy boundary after evidence validation. Completion's
        # own tests cover deriving UNKNOWN from incomplete source observations.
        def unknown(*args):
            result = read_run(*args)
            if result["variant"] == "candidate" and result["case_id"] == "single_match":
                result.update(state="UNKNOWN", reward=None)
            return result
        with patch("react_runtime.repair_scoring.read_run", side_effect=unknown):
            self.assertEqual(score_comparison(self.root)["decision"], "INCONCLUSIVE")

    def test_aggregate_gain_cannot_hide_a_regression(self):
        def regressed(*args):
            result = read_run(*args)
            if result["variant"] == "candidate" and result["case_id"] == "single_match":
                result.update(state="FALSE", reward=0)
                result["checks"]["targets_updated"] = "FALSE"
            return result
        with patch("react_runtime.repair_scoring.read_run", side_effect=regressed):
            result = score_comparison(self.root)
        self.assertEqual(result["pass_counts"], {"parent": 2, "candidate": 3})
        self.assertTrue(result["target_fixed"])
        self.assertEqual(result["decision"], "REJECT")
        self.assertIn("REGRESSION", result["reasons"])

    def test_no_fixed_target_is_rejected(self):
        def no_fix(*args):
            result = read_run(*args)
            if result["variant"] == "candidate" and result["case_id"] == "relationship_filter":
                result.update(state="FALSE", reward=0)
                result["checks"]["unrelated_state_preserved"] = "FALSE"
            return result
        with patch("react_runtime.repair_scoring.read_run", side_effect=no_fix):
            result = score_comparison(self.root)
        self.assertEqual(result["decision"], "REJECT")
        self.assertIn("TARGET_FAILURE_NOT_FIXED", result["reasons"])

    def test_resource_violation_is_rejected(self):
        def costly(*args):
            result = read_run(*args)
            if result["variant"] == "candidate": result["wall_seconds"] = 1000
            return result
        with patch("react_runtime.repair_scoring.read_run", side_effect=costly):
            result = score_comparison(self.root)
        self.assertEqual(result["decision"], "REJECT")
        self.assertIn("RESOURCE_LIMIT", result["reasons"])

    def test_path_escape_is_invalid(self):
        path = self.root / "runs.json"
        entries = json.loads(path.read_text())
        entries[0]["run"] = "../../outside"
        replace_json(path, entries)
        self.assertEqual(score_comparison(self.root)["decision"], "INVALID")

    def test_fabricated_score_is_recomputed_even_with_consistent_hashes(self):
        index_path = self.root / "runs.json"
        entries = json.loads(index_path.read_text())
        entry = next(e for e in entries if e["case_id"] == "relationship_filter" and e["variant"] == "parent")
        directory = self.root / entry["run"]
        db = sqlite3.connect(directory / "ledger.sqlite")
        try:
            event = json.loads(db.execute("SELECT payload FROM events WHERE type='completion_checked'").fetchone()[0])
            ref = event["report_ref"]
            path = directory / ref["path"]
            report = json.loads(path.read_text())
            report.update(state="TRUE", reward=1)
            for check in report["checks"]: check["value"] = "TRUE"
            replace_json(path, report)
            ref.update(sha256=digest(path), bytes=path.stat().st_size)
            db.execute("UPDATE artifacts SET digest=?,size=? WHERE id=?", (ref["sha256"], ref["bytes"], ref["id"]))
            def update_refs(value):
                if isinstance(value, dict):
                    if value.get("id") == ref["id"] and "sha256" in value:
                        value.update(sha256=ref["sha256"], bytes=ref["bytes"])
                    for child in value.values(): update_refs(child)
                elif isinstance(value, list):
                    for child in value: update_refs(child)
            previous = "0" * 64
            for seq, typ, step, at, clock, raw in db.execute("SELECT seq,type,step,at,monotonic_ns,payload FROM events ORDER BY seq").fetchall():
                payload = json.loads(raw)
                update_refs(payload)
                unsigned = {"seq": seq, "type": typ, "step": step, "at": at, "monotonic_ns": clock,
                            "payload": payload, "previous_sha256": previous}
                current = hashlib.sha256(json_bytes(unsigned)).hexdigest()
                db.execute("UPDATE events SET payload=?,previous_sha256=?,sha256=? WHERE seq=?",
                           (json_bytes(payload).decode(), previous, current, seq))
                previous = current
            db.commit()
            entry["event_head"] = previous
        finally:
            db.close()
        replace_json(index_path, entries)
        store = RunStore.open_existing(directory)
        try:
            self.assertTrue(store.audit()["complete"])
        finally:
            store.close()
        result = score_comparison(self.root)
        self.assertEqual(result["decision"], "INVALID")
        self.assertIn("Reported score does not match original evidence", result["reasons"][0])


if __name__ == "__main__":
    unittest.main()

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from react_runtime.completion import fingerprint
from react_runtime.loop import Config
from react_runtime.store import RunStore
from repair_runtime.engine import work, import_run
from repair_runtime.episode import run_episode
from repair_runtime.evaluation import challenges, compare, trial
from repair_runtime.program import seed_package, select, mutations, validate_package, Unsupported
from repair_runtime.proposer import ModelProposer
from repair_runtime.store import Archive
from scripts.demo_repair_scoring import cases


def fixture(): return cases()[0][2]


def good_package():
    return next(candidate for candidate in mutations(seed_package(), "related") if trial(candidate, fixture())["state"] == "TRUE")


class FixedProposer:
    name = "test-proposals"
    def __init__(self, candidates): self.candidates = candidates
    def propose(self, archive, packet, parent):
        for candidate in self.candidates:
            yield {"kind": "candidate", "candidate": candidate, "reason": "Injected test candidate"}


class ProgramTests(unittest.TestCase):
    def test_search_generates_a_reusable_program_without_expected_ids(self):
        package = good_package()
        self.assertNotIn("ticket:", json.dumps(package))
        self.assertTrue(all(trial(package, data)["state"] == "TRUE" for data in challenges(71, 50)))

    def test_literals_and_unknown_operators_are_rejected(self):
        for field, value in (("type", "Ticket"), ("op", "eval")):
            package = seed_package()
            package["functions"]["direct"]["nodes"][0][field] = value
            with self.assertRaises(ValueError): validate_package(package)

    def test_cycles_and_unbound_nodes_are_rejected(self):
        package = seed_package()
        package["functions"]["direct"]["nodes"][1]["input"] = 1
        with self.assertRaises(ValueError): validate_package(package)

    def test_unknown_evidence_and_computation_budget_are_explicit(self):
        data = fixture()
        data["before"]["complete"] = False
        with self.assertRaises(Unsupported): select(good_package(), data["contract"], data["before"])
        data = fixture()
        with self.assertRaises(Unsupported): select(good_package(), data["contract"], data["before"], max_work=1)

    def test_missing_predicate_is_not_silently_false(self):
        data = fixture()
        del data["before"]["entities"][0]["properties"]["region"]
        self.assertEqual(trial(good_package(), data)["state"], "UNKNOWN")

    def test_boolean_is_distinct_from_numeric_value(self):
        data = fixture()
        del data["contract"]["selector"]["related"]
        data["contract"]["selector"]["where"] = {"reviewed": True}
        data["before"]["entities"][2]["properties"]["reviewed"] = 1
        self.assertEqual(select(seed_package(), data["contract"], data["before"])["entity_ids"], [])


class RepairLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.archive = Archive(self.root / "archive", create=True)

    def tearDown(self):
        self.archive.close()
        self.tmp.cleanup()

    def test_single_counterexample_triggers_automatic_repair_and_resume_is_idle(self):
        original = self.archive.meta("active")
        self.archive.add_case(fixture())
        result = work(self.archive)
        self.assertNotEqual(original, result["active"])
        self.assertEqual(result["cases"], {"RESOLVED": 1})
        receipt = self.archive.get(result["decisions"][0]["receipt"])
        self.assertEqual(receipt["decision"], "ACCEPT_FOR_DEVELOPMENT")
        self.assertEqual(len(receipt["challenge_results"]), 16)
        spent = result["proposals_spent"]
        self.archive.close()
        self.archive = Archive(self.root / "archive")
        self.assertEqual(work(self.archive)["proposals_spent"], spent)
        self.assertTrue(self.archive.audit()["complete"])

    def test_regression_is_rejected_before_good_candidate_activates(self):
        data = cases()[2][2]
        data["contract"]["selector"]["related"]["direction"] = "in"
        for edge in data["before"]["relations"]: edge["source"], edge["target"] = edge["target"], edge["source"]
        self.archive.add_case(fixture())
        preserved_id = self.archive.add_case(data)
        good = good_package()
        regressing = deepcopy(good)
        regressing["functions"]["related"]["nodes"][-1]["direction"] = "out"
        result = work(self.archive, FixedProposer([regressing, good]))
        attempts = self.archive.db.execute("SELECT status,receipt FROM attempts ORDER BY id").fetchall()
        self.assertEqual(attempts[0]["status"], "REJECT")
        self.assertIn(preserved_id, self.archive.get(attempts[0]["receipt"])["regressed"])
        self.assertEqual(result["active"], fingerprint(good))

    def test_fresh_challenge_rejects_outbound_only_overfit(self):
        self.archive.add_case(fixture())
        original = self.archive.meta("active")
        regressing = good_package()
        regressing["functions"]["related"]["nodes"][-1]["direction"] = "out"
        result = work(self.archive, FixedProposer([regressing]))
        self.assertEqual(result["active"], original)
        self.assertEqual(result["cases"], {"CHALLENGE_REJECTED": 1})

    def test_unknown_case_blocks_acceptance_without_dropping_denominator(self):
        self.archive.add_case(fixture())
        unknown = cases()[2][2]
        unknown["before"]["complete"] = False
        self.archive.add_case(unknown)
        result = work(self.archive, FixedProposer([good_package()]))
        self.assertEqual(result["decisions"], [])
        receipts = [self.archive.get(r[0]) for r in self.archive.db.execute("SELECT receipt FROM attempts WHERE status='INCONCLUSIVE'")]
        self.assertEqual(receipts[0]["scheduled"], 2)

    def test_candidate_cannot_change_other_function_or_checker(self):
        self.archive.add_case(fixture())
        bad = good_package()
        bad["functions"]["direct"]["return"] = 0
        result = work(self.archive, FixedProposer([bad]))
        self.assertEqual(result["decisions"], [])
        self.assertEqual(self.archive.db.execute("SELECT status FROM attempts ORDER BY id LIMIT 1").fetchone()[0], "INVALID")

    def test_duplicate_cases_keep_one_identity_and_scoped_definitions(self):
        data = fixture()
        first = self.archive.add_case(data)
        self.assertEqual(first, self.archive.add_case(data))
        self.assertEqual(self.archive.meta("generation"), 1)
        page = self.archive.discover(data["before"]["scope"], limit=1)
        self.assertEqual(len(page["records"]), 1)
        self.assertEqual(page["next_offset"], 1)
        self.assertEqual(self.archive.discover("other-scope")["records"], [])
        entities = self.archive.query_entities(first, entity_type="Ticket", limit=2)
        self.assertEqual(len(entities["records"]), 2)
        self.assertEqual(entities["next_offset"], 2)
        edges = self.archive.query_relations(first, "ticket:1")
        self.assertEqual(edges["records"][0]["target"], "customer:west")
        self.assertEqual(self.archive.query_entities("unknown")["records"], [])

    def test_noop_and_duplicate_candidates_do_not_activate(self):
        self.archive.add_case(fixture())
        bad = seed_package()
        bad["functions"]["related"]["return"] = 0
        work(self.archive, FixedProposer([seed_package(), bad, bad]))
        statuses = [r[0] for r in self.archive.db.execute("SELECT status FROM attempts ORDER BY id")]
        self.assertEqual(statuses[:3], ["INVALID", "REJECT", "DUPLICATE"])

    def test_global_budget_survives_restart(self):
        self.archive.add_case(fixture())
        with self.archive.db: self.archive.set("max_proposals", 1)
        result = work(self.archive)
        self.assertEqual(result["proposals_spent"], 1)
        self.assertEqual(result["decisions"], [])
        self.archive.close(); self.archive = Archive(self.root / "archive")
        self.assertEqual(work(self.archive)["proposals_spent"], 1)

    def test_worker_recovers_interrupted_case_without_resetting_budget(self):
        key = self.archive.add_case(fixture())
        with self.archive.db:
            self.archive.db.execute("UPDATE cases SET status='RUNNING' WHERE id=?", (key,))
            self.archive.set("proposals_spent", 5)
        work(self.archive)
        self.assertGreater(self.archive.meta("proposals_spent"), 5)
        self.assertEqual(self.archive.db.execute("SELECT count(*) FROM events WHERE type='RECOVERED'").fetchone()[0], 1)

    def test_second_worker_cannot_steal_live_work(self):
        other = Archive(self.root / "archive")
        try:
            with self.archive.worker():
                with self.assertRaises(RuntimeError):
                    with other.worker(): pass
        finally: other.close()

    def test_suite_change_prevents_stale_activation(self):
        self.archive.add_case(fixture())
        archive = self.archive
        class AddingProposer(FixedProposer):
            def propose(self, *args):
                archive.add_case(cases()[3][2])
                yield from super().propose(*args)
        original = archive.meta("active")
        work(archive, AddingProposer([good_package()]), max_jobs=1)
        self.assertEqual(archive.meta("active"), original)
        self.assertEqual(archive.db.execute("SELECT count(*) FROM events WHERE type='STALE_COMPARISON'").fetchone()[0], 1)

    def test_rollback_requires_expected_version_and_preserves_history(self):
        old = self.archive.meta("active")
        self.archive.add_case(fixture()); work(self.archive)
        active = self.archive.meta("active")
        with self.assertRaises(ValueError): self.archive.rollback(old, old, "test")
        self.archive.rollback(active, old, "Regression observed in a later independent check")
        self.assertEqual(self.archive.meta("active"), old)
        self.assertEqual(len(self.archive.status()["decisions"]), 1)

    def test_tampering_is_detected(self):
        key = self.archive.add_case(fixture())
        path = self.archive.root / "objects" / key[:2] / (key + ".json")
        path.chmod(0o600); path.write_text("{}")
        with self.assertRaises(ValueError): work(self.archive)

    def test_live_proposer_transport_cannot_read_unapproved_artifact(self):
        from repair_runtime.proposer import make_packet
        data = fixture()
        key = self.archive.add_case(data)
        packet = make_packet(self.archive, key, data, self.archive.meta("active"), trial(seed_package(), data))
        command = [sys.executable, "-c", 'import json; print(json.dumps({"kind":"read","artifact":"0"*64,"offset":0,"limit":3000}))']
        result = ModelProposer("test", command=command, max_calls=1).one(self.archive, packet, seed_package(), 0)
        self.assertEqual(result["kind"], "needs_evidence")
        self.assertEqual(len(result["evidence"]), 1)

    def test_proposer_crash_is_recorded_and_retry_has_backoff(self):
        data = fixture(); self.archive.add_case(data)
        proposer = ModelProposer("test", command=[sys.executable, "-c", "raise SystemExit(2)"], max_calls=1)
        result = work(self.archive, proposer)
        self.assertEqual(result["cases"], {"RETRY_WAIT": 1})
        spent = result["proposals_spent"]
        self.assertEqual(work(self.archive, proposer)["proposals_spent"], spent)

    def test_configuration_failure_does_not_retry(self):
        self.archive.add_case(fixture())
        class Unauthenticated:
            name = "test-auth"
            def propose(self, *args):
                yield {"kind": "needs_configuration", "reason": "Authentication unavailable"}
        result = work(self.archive, Unauthenticated())
        self.assertEqual(result["cases"], {"NEEDS_CONFIGURATION": 1})
        self.assertEqual(work(self.archive, Unauthenticated())["proposals_spent"], 1)

    def test_comparison_keeps_original_states_outside_compact_receipt(self):
        result = compare(seed_package(), good_package(), [fixture()], fingerprint(fixture()), write=self.archive.put)
        row = result["rows"][0]["candidate"]
        self.assertNotIn("after", row)
        self.assertEqual(self.archive.get(row["evidence_ref"])["state"], "TRUE")

    def test_actual_react_episode_ingests_then_uses_repaired_package(self):
        data = fixture()
        baseline = run_episode(self.archive, data, self.root / "baseline", raw=True, actor="scripted",
                               config=Config(max_steps=3, max_tool_attempts=2, inline_output_chars=12000))
        self.assertNotEqual(baseline["status"], "VERIFIED_SUCCESS")
        self.assertIn("repair_case", baseline)
        work(self.archive)
        result = run_episode(self.archive, data, self.root / "fixed", actor="scripted")
        self.assertEqual(result["status"], "VERIFIED_SUCCESS")
        self.assertEqual(result["kernel_version"], self.archive.meta("active"))
        store = RunStore.open_existing(self.root / "fixed/react")
        try:
            self.assertTrue(store.audit()["complete"])
            self.assertEqual(store.db.execute("SELECT count(*) FROM events WHERE type='model_started'").fetchone()[0], 0)
        finally: store.close()

    def test_evidence_gap_handoff_keeps_goal_and_records_continuation(self):
        data = fixture()
        data["before"]["complete"] = False
        result = run_episode(self.archive, data, self.root / "gap", actor="scripted")
        self.assertEqual(result["kernel_handoff"]["reason"], "EVIDENCE_GAP")
        self.assertNotEqual(result["status"], "VERIFIED_SUCCESS")
        self.assertIn("repair_case", result)
        origin = self.archive.get(self.archive.db.execute("SELECT origin_ref FROM cases").fetchone()[0])
        self.assertEqual(len(origin["handoffs"]), 1)


if __name__ == "__main__": unittest.main()

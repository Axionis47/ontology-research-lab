from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from appworld_runtime.inference import bind_goal, ArtistAdapter, query_artists
from react_runtime.completion import evaluate, index_snapshot, target_set
from react_runtime.loop import Config
from react_runtime.store import RunStore
from repair_runtime.episode import run_episode
from repair_runtime.inference import run_request, continue_learning
from repair_runtime.judge import judge_episode
from repair_runtime.program import seed_package, mutations, select, Unsupported
from repair_runtime.proposer import SearchProposer
from repair_runtime.store import Archive
from scripts.demo_repair_scoring import cases


def numeric_case():
    data = deepcopy(cases()[0][2])
    data["contract"]["selector"].pop("related")
    data["contract"]["selector"]["numeric"] = [{"property": "quantity", "op": "gte", "value": 2}]
    for i, entity in enumerate(data["before"]["entities"]): entity["properties"]["quantity"] = i % 3
    return data


class NumericTests(unittest.TestCase):
    def test_native_genre_query_preserves_public_uncased_semantics(self):
        snapshot = {"scope": "test", "complete": True, "revision": "before", "relations": [],
            "entities": [{"id": "artist:9", "type": "Artist", "properties": {"genre": "edm", "name": "ExactName"}}]}
        arguments = {"entity_type": "Artist", "where": {"genre": "EDM"}}
        self.assertEqual(query_artists(snapshot, arguments), query_artists(snapshot, {**arguments, "where": {"genre": "edm"}}))
        self.assertEqual(query_artists(snapshot, arguments)["total_matches"], 1)
        self.assertEqual(arguments["where"]["genre"], "EDM")
        self.assertEqual(query_artists(snapshot, {"entity_type": "Artist", "where": {"name": "exactname"}})["total_matches"], 0)

    def test_search_repairs_numeric_selection_without_task_literals(self):
        data = numeric_case()
        entities, edges = index_snapshot(data["before"])
        expected, _ = target_set(data["contract"], entities, edges)
        self.assertNotEqual(select(seed_package(), data["contract"], data["before"])["entity_ids"], expected)
        fixed = next(p for p in mutations(seed_package(), "direct") if select(p, data["contract"], data["before"])["entity_ids"] == expected)
        self.assertNotIn("quantity", json.dumps(fixed))
        self.assertNotIn("ticket:", json.dumps(fixed))
        data["contract"]["selector"].pop("numeric")
        self.assertEqual(select(fixed, data["contract"], data["before"])["entity_ids"], select(seed_package(), data["contract"], data["before"])["entity_ids"])

    def test_numeric_missing_and_boolean_are_unknown(self):
        data = numeric_case()
        for entity in data["before"]["entities"]:
            if entity["type"] == "Ticket": entity["properties"]["quantity"] = True
        self.assertEqual(evaluate(data["contract"], data["before"], data["before"])["state"], "UNKNOWN")

    def test_native_binding_rejects_unrecognized_goal_and_uses_slots(self):
        contract = bind_goal("Follow all the classical artists on Spotify that have at least 22 followers.", "test")
        self.assertEqual(contract["selector"]["numeric"][0]["value"], 22)
        with self.assertRaises(ValueError): bind_goal("Delete all artists", "test")

    def test_native_normalization_keeps_own_count_delta_but_detects_other_changes(self):
        adapter = ArtistAdapter.__new__(ArtistAdapter)
        adapter.contract = bind_goal("Follow all the classical artists on Spotify that have at least 22 followers.", "test")
        adapter.token, adapter.initial_following = "test", None
        artist = {"artist_id": 1, "name": "A", "genre": "classical", "follower_count": 22}
        followed = []
        adapter.pages = lambda name, args: deepcopy([artist] if name == "spotify__search_artists" else followed)
        before = adapter.observe()
        artist["follower_count"] += 1; followed.append(artist)
        after = adapter.observe()
        self.assertEqual(evaluate(adapter.contract, before, after)["state"], "TRUE")
        artist["follower_count"] += 1
        self.assertEqual(evaluate(adapter.contract, before, adapter.observe())["state"], "FALSE")


class InferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.archive = Archive(self.root / "archive", create=True)

    def tearDown(self):
        self.archive.close(); self.tmp.cleanup()

    def test_successful_write_stops_without_waiting_for_actor_finish(self):
        result = run_episode(self.archive, cases()[0][2], self.root / "postcondition", raw=True, actor="reference",
                             config=Config(max_steps=2, inline_output_chars=12000))
        self.assertEqual(result["status"], "VERIFIED_SUCCESS")
        store = RunStore.open_existing(self.root / "postcondition/react")
        try:
            events = store.audit()["events"]
            self.assertEqual(sum(e["type"] == "postcondition_assessment" for e in events), 1)
            self.assertEqual(sum(e["type"] == "model_started" for e in events), 2)
        finally: store.close()

    def test_recovered_gap_is_repaired_and_next_inference_uses_new_package(self):
        data = cases()[0][2]
        request = {"request_id": "one", "adapter": "local", "actor": "reference", "data": data}
        first = run_request(self.archive, request, proposer=SearchProposer())
        self.assertEqual(first["task_state"], "TRUE")
        self.assertTrue(first["recovered"])
        self.assertNotEqual(first["package_used"], first["next_package"])
        receipt = self.archive.get(first["learning"]["decisions"][0]["receipt"])
        self.assertEqual(receipt["execution_gate"]["state"], "TRUE")
        self.assertFalse(receipt["execution_gate"]["fallback_enabled"])
        second = run_request(self.archive, {**request, "request_id": "two"}, proposer=SearchProposer())
        self.assertEqual(second["task_state"], "TRUE")
        self.assertFalse(second["recovered"])
        self.assertEqual(second["package_used"], first["next_package"])
        judged = self.archive.get(first["judge"])
        self.assertEqual(judged["coverage"]["events"], judged["coverage"]["covered"])

    def test_two_learning_cycles_keep_old_cases_and_new_numeric_case(self):
        first = run_request(self.archive, {"request_id": "rel", "adapter": "local", "actor": "reference", "data": cases()[0][2]}, proposer=SearchProposer())
        second = run_request(self.archive, {"request_id": "num", "adapter": "local", "actor": "reference", "data": numeric_case()}, proposer=SearchProposer())
        self.assertEqual(second["task_state"], "TRUE")
        self.assertNotEqual(first["next_package"], second["next_package"])
        receipt = self.archive.get(second["learning"]["decisions"][-1]["receipt"])
        self.assertEqual(len(receipt["execution_gate"]["rows"]), 2)
        self.assertEqual(receipt["scheduled"], 2)
        third = run_request(self.archive, {"request_id": "old", "adapter": "local", "actor": "reference", "data": cases()[0][2]}, proposer=SearchProposer())
        self.assertEqual(third["task_state"], "TRUE")
        self.assertFalse(third["recovered"])

    def test_default_learning_cannot_silently_invoke_a_repair_backend(self):
        self.archive.add_case(cases()[0][2])
        original = self.archive.meta("active"), self.archive.meta("active_policy")
        with patch("repair_runtime.inference.work", side_effect=AssertionError("implicit search")), \
             patch("repair_runtime.policy_repair.work", side_effect=AssertionError("implicit policy proposer")):
            result = continue_learning(self.archive)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "GEMINI_DIAGNOSIS_REQUIRED")
        self.assertEqual(original, (self.archive.meta("active"), self.archive.meta("active_policy")))
        self.assertEqual(self.archive.meta("proposals_spent"), 0)
        self.assertEqual(self.archive.status()["decisions"], [])

    def test_same_request_does_not_repeat_execution_and_different_input_is_rejected(self):
        request = {"request_id": "id", "adapter": "local", "actor": "reference", "data": cases()[0][2]}
        first = run_request(self.archive, request, learn=False)
        second = run_request(self.archive, request, learn=False)
        self.assertEqual(first["episode"]["run_directory"], second["episode"]["run_directory"])
        count = self.archive.db.execute("SELECT count(*) FROM events WHERE type='INFERENCE_STARTED'").fetchone()[0]
        self.assertEqual(count, 1)
        with self.assertRaises(ValueError): run_request(self.archive, {**request, "raw": True})

    def test_partial_kernel_effect_survives_handoff_and_is_completed(self):
        data = {"contract": {"version": 1, "goal": "Set matching records done", "scope": "partial",
            "selector": {"entity_type": "Record", "where": {}, "related": {"entity_type": "Group", "where": {}, "relation_type": "member", "direction": "out"}},
            "update": {"kind": "set_property", "property": "done", "value": True}},
            "before": {"scope": "partial", "revision": "0", "complete": True,
                "entities": [{"id": "a", "type": "Record", "properties": {"done": False}}, {"id": "b", "type": "Record", "properties": {"done": False}}, {"id": "g", "type": "Group", "properties": {}}],
                "relations": [{"source": "a", "type": "member", "target": "g"}, {"source": "b", "type": "member", "target": "g"}, {"source": "g", "type": "member", "target": "a"}]}}
        package = seed_package()
        package["functions"]["related"]["nodes"].append({"op": "filter_relation_connected", "input": 1, "anchors": 3, "relation": "selector.related.relation_type", "direction": "in"})
        package["functions"]["related"]["return"] = 4
        result = run_episode(self.archive, data, self.root / "partial", actor="reference", package_ref=self.archive.put(package))
        self.assertEqual(result["status"], "VERIFIED_SUCCESS")
        self.assertEqual(result["kernel_handoff"]["reason"], "NO_PROGRESS")
        store = RunStore.open_existing(self.root / "partial/react")
        try:
            events = store.audit()["events"]
            operations = [e for e in events if e["type"] == "operation_result" and e["payload"]["action"] == "apply_update"]
            first = json.loads(store.get(operations[0]["payload"]["output_ref"]["id"]))
            self.assertTrue(first["entities"][0]["properties"]["done"])
            self.assertFalse(first["entities"][1]["properties"]["done"])
            self.assertEqual(len(operations), 2)
        finally: store.close()

    def test_no_progress_has_explicit_stop_and_fresh_terminal_check(self):
        actor = [sys.executable, "-c", 'import json,sys; x=json.load(sys.stdin); print(json.dumps({"kind":"finish","request_id":x["turn"]["request_id"],"answer":"done","artifact_refs":[],"claimed_requirement_ids":["task"]}))']
        result = run_episode(self.archive, cases()[0][2], self.root / "stalled", raw=True, actor_command=actor,
                             config=Config(max_steps=10, max_stagnant_steps=3))
        self.assertEqual(result["status"], "NO_PROGRESS")
        judged = judge_episode(self.archive, self.root / "stalled/react", segment_size=5)
        self.assertEqual(judged["task_state"], "FALSE")
        self.assertTrue(judged["final_check_fresh"])
        self.assertGreater(len(judged["coverage"]["segments"]), 1)

    def test_execution_gate_cannot_be_skipped_after_inference_enables_it(self):
        from repair_runtime.engine import work
        request = {"request_id": "gap", "adapter": "local", "actor": "reference", "data": cases()[0][2]}
        first = run_request(self.archive, request, learn=False)
        original = self.archive.meta("active")
        result = work(self.archive)
        self.assertEqual(result["active"], original)
        self.assertEqual(result["decisions"], [])

    def test_unknown_evidence_is_not_task_failure_or_program_repair(self):
        data = cases()[0][2]; data["before"]["complete"] = False
        result = run_request(self.archive, {"request_id": "unknown", "adapter": "local", "actor": "reference", "data": data})
        self.assertEqual(result["task_state"], "UNKNOWN")
        self.assertEqual(result["repair_route"], "EVIDENCE")
        self.assertIsNone(result["repair_case"])


if __name__ == "__main__": unittest.main()

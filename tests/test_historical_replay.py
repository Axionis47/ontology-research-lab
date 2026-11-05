"""Actual Coffee capture, composed migration, original-bank and winner checks."""

from __future__ import annotations

import importlib.util
import shutil
import sqlite3
from pathlib import Path

import pytest

from oak.construction_campaign import require_retained_parent, select_preserving_candidate
from oak.historical_replay import accepted_replay_report, replay_case
from oak.store import Store, canonical

_spec = importlib.util.spec_from_file_location(
    "oak_historical_replay_acceptance",
    Path(__file__).resolve().parents[1] / "scripts/verify_historical_replay.py",
)
assert _spec is not None and _spec.loader is not None
_acceptance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_acceptance)


@pytest.fixture(scope="module")
def replay_chain(tmp_path_factory):
    return _acceptance.build_chain(tmp_path_factory.mktemp("genuine-coffee-replay"))


def test_every_inherited_original_executes_on_k3_through_shared_chain(replay_chain):
    store = replay_chain["store"]
    k1, k2, k3 = replay_chain["kernels"]
    report1, report2, report3 = replay_chain["reports"]
    assert report1["allowed"], report1
    assert report2["allowed"], report2
    assert report3["allowed"], report3["feedback"]
    assert report3["case_count"] == 4
    for report in report3["reports"]:
        assert report["status"] == "preserved"
        assert report["candidate_kernel_id"] == k3
        assert report["adapter_path"] == (
            replay_chain["edges"] if report["origin_kernel_id"] == k1 else replay_chain["edges"][1:]
        )
        assert report["origin_kernel_id"] in {k1, k2}
        executions = store.get(report["candidate_execution_id"])
        assert executions and all(item["steps"] for item in executions)
        assert report["assessment_category"] == "execution_succeeded"
    assert len(replay_chain["graphs"][2]["nodes"]) == 2 * len(replay_chain["graphs"][0]["nodes"])
    assert len(replay_chain["graphs"][2]["edges"]) == len(replay_chain["graphs"][0]["nodes"])
    point_report = next(
        report
        for report in report3["reports"]
        if report["original_case_id"] == replay_chain["case_ids"][2]
    )
    point_execution = store.get(point_report["candidate_execution_id"])[0]
    assert [step["operator"] for step in point_execution["steps"]] == [
        "lookup_entities",
        "traverse_relations",
        "aggregate_values",
    ]
    assert store.rows("SELECT id FROM model_calls") == []
    assert report3["model_calls"] == report3["live_mcp_calls"] == 0
    assert accepted_replay_report(store, k3)["bank_id"] == report3["bank_id"]


def test_older_regression_blocks_winner_even_when_newer_case_passes(replay_chain):
    k1, k2, _ = replay_chain["kernels"]
    bad = replay_chain["bad_report"]
    assert bad["status"] == "regressed", bad
    assert not bad["allowed"]
    assert any(
        report["origin_kernel_id"] == k2 and report["status"] == "preserved"
        for report in bad["reports"]
    )
    assert any(
        report["origin_kernel_id"] == k1 and report["status"] == "regressed"
        for report in bad["reports"]
    )
    selected = select_preserving_candidate(
        k2, replay_chain["bad_kernel_id"], bad, execution_eligible=True, preferred=True
    )
    assert selected == k2
    good = replay_chain["reports"][2]
    assert (
        select_preserving_candidate(
            k2, replay_chain["kernels"][2], good, execution_eligible=True, preferred=True
        )
        == replay_chain["kernels"][2]
    )


def test_bound_trajectory_consumes_replayed_values_and_stops_on_first_divergence(replay_chain):
    store = replay_chain["store"]
    trajectory_id = replay_chain["case_ids"][1]
    original_bytes = canonical(store.get(trajectory_id))
    good = next(
        report
        for report in replay_chain["reports"][2]["reports"]
        if report["original_case_id"] == trajectory_id
    )
    assert good["scope"] == "trajectory"
    executions = store.get(good["candidate_execution_id"])
    assert len(executions) == 2
    assert executions[1]["steps"][0]["inputs"]["left"] == executions[0]["adapted_value"]
    bad = next(
        report
        for report in replay_chain["bad_report"]["reports"]
        if report["original_case_id"] == trajectory_id
    )
    assert bad["first_difference"]["call_index"] == 0
    assert len(store.get(bad["candidate_execution_id"])) == 1
    assert canonical(store.get(trajectory_id)) == original_bytes


def test_missing_original_graph_is_unable_to_check_and_never_passes(replay_chain, tmp_path):
    original = replay_chain["store"]
    with original.connect() as source, sqlite3.connect(tmp_path / "catalog.sqlite") as target:
        source.backup(target)
    shutil.copytree(original.root / "artifacts", tmp_path / "artifacts")
    store = Store(tmp_path)
    capture = store.get(replay_chain["captures"][0])
    (store.root / "artifacts" / f"{capture['initial_graph_ref']}.json").unlink()
    result = replay_case(store, replay_chain["case_ids"][0], replay_chain["kernels"][2])
    assert result.status == "unable_to_check"
    assert result.baseline_execution_id is None
    assert result.candidate_execution_id is None


def test_repair_is_a_new_candidate_checked_against_unchanged_original_cases(replay_chain):
    store = replay_chain["store"]
    repaired = store.get(replay_chain["repaired_kernel_id"])
    assert repaired["parent"] == replay_chain["kernels"][1]
    assert repaired["repair_of"] == replay_chain["bad_kernel_id"]
    assert replay_chain["repaired_kernel_id"] not in replay_chain["kernels"]
    result = replay_chain["repaired_report"]
    assert result["allowed"], result["feedback"]
    assert {report["original_case_id"] for report in result["reports"]} == set(
        replay_chain["case_ids"]
    )
    receipt = store.get(replay_chain["repair_receipt"])
    assert receipt["retained_after_failure"] == replay_chain["kernels"][1]
    assert receipt["retained_after_repair"] == replay_chain["repaired_kernel_id"]
    assert _acceptance.acceptance_receipt(replay_chain)["status"] == "passed"


def test_unpreserved_candidate_cannot_become_campaign_retained_parent(replay_chain):
    store = replay_chain["store"]
    calls_before = store.rows("SELECT id FROM model_calls")
    with pytest.raises(ValueError, match="Construction parent cannot be retained"):
        require_retained_parent(store, replay_chain["bad_kernel_id"])
    require_retained_parent(store, replay_chain["repaired_kernel_id"])
    assert store.rows("SELECT id FROM model_calls") == calls_before

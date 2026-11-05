"""Verify real source-bound pure probes without purchasing another execution.

The retained local construction is copied without changing its artifact bytes
or event history. Negative tests deliberately corrupt that isolated copy.
"""

import json
import re
import shutil
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest

from oak.store import Store
from oak.verification import (
    KernelCandidate,
    ObligationCheck,
    ObservedCheck,
    _recorded_execution,
    verify_candidate,
)

KERNEL = "c63045e6fd83601911a6252dcad21d1098b44a74f049cd41331ef3aa5c2821c4"
PROBE = "4dd9ff564672849570c146903599d3ba56a9dea435bb66bbacedb81cb62ca8a3"
LOCAL = Path(__file__).resolve().parents[1] / ".local"


@pytest.fixture
def retained(tmp_path):
    if not (LOCAL / "artifacts" / f"{KERNEL}.json").is_file():
        pytest.skip("Genuine source-bound construction receipts are unavailable locally")
    destination = tmp_path / "retained"
    (destination / "artifacts").mkdir(parents=True)
    with sqlite3.connect(f"file:{LOCAL / 'catalog.sqlite'}?mode=ro", uri=True) as source:
        with sqlite3.connect(destination / "catalog.sqlite") as target:
            source.backup(target)
    pending, seen = [KERNEL, PROBE], set()
    while pending:
        identity = pending.pop()
        if identity in seen:
            continue
        seen.add(identity)
        source = LOCAL / "artifacts" / f"{identity}.json"
        if not source.is_file():
            continue
        shutil.copyfile(source, destination / "artifacts" / source.name)
        pending.extend(re.findall(r"[0-9a-f]{64}", source.read_text()))
    store = Store(destination)
    kernel = store.get(KERNEL)
    candidate = KernelCandidate(
        id=KERNEL,
        schema=kernel["schema"],
        functions=kernel["functions"],
        parent_id=kernel.get("parent"),
    )
    return store, candidate


def verify_probe(store, candidate, identity=PROBE):
    probe = store.get(identity)
    return _recorded_execution(
        store,
        candidate,
        {"probe_evidence_id": identity},
        ObligationCheck(
            id="retained", group="subtask", function_names=[probe["probe"]["function"]]
        ),
    )


def corrupt_probe(store, change):
    probe = deepcopy(store.get(PROBE))
    change(probe)
    identity = store.put("function_probe", probe)
    with store.connect() as connection:
        connection.execute("UPDATE events SET artifact_id=? WHERE artifact_id=?", (identity, PROBE))
    return identity


def test_all_real_pure_probes_reexecute_without_fresh_calls(retained):
    store, candidate = retained
    kernel = store.get(KERNEL)
    probes = store.get(kernel["evidence"]["probes_id"])
    before = store.rows("SELECT id,run_id,status,artifact_id FROM events WHERE stage LIKE 'mcp_%'")
    model_before = store.rows("SELECT * FROM model_calls")
    obligations, evidence = [], []
    for probe in probes:
        name = probe["probe"]["function"]
        obligations.append(ObligationCheck(id=name, group="subtask", function_names=[name]))
        evidence.append(
            ObservedCheck(
                obligation_id=name,
                dimension="execution",
                evidence_ref=store.put(
                    "verification_input",
                    {"candidate_id": KERNEL, "probe_evidence_id": probe["evidence_id"]},
                ),
            )
        )
    report = verify_candidate(
        candidate,
        obligations,
        evidence,
        store=store,
        ontology_validation_ref=kernel["evidence"]["validation_id"],
    )
    checks = [check for check in report.checks if check.dimension == "execution"]
    assert len(checks) == 14
    assert all(check.status == "passed" for check in checks), [
        check.model_dump() for check in checks
    ]
    assert all(check.details["mode"] == "retained_materialized_reexecution" for check in checks)
    assert all(check.details["fresh_tool_calls"] == 0 for check in checks)
    assert all(check.details["task_correctness"] == "not_checked" for check in checks)
    assert all(check.details["coverage"] == "not_checked" for check in checks)
    assert report.execution_eligible
    assert not report.target_met
    assert (
        store.rows("SELECT id,run_id,status,artifact_id FROM events WHERE stage LIKE 'mcp_%'")
        == before
    )
    assert store.rows("SELECT * FROM model_calls") == model_before
    probe_run = store.rows("SELECT run_id FROM events WHERE artifact_id=?", (PROBE,))[0]["run_id"]
    receipt_id = store.get(PROBE)["receipt_ids"][0]
    source_run = store.rows("SELECT run_id FROM events WHERE artifact_id=?", (receipt_id,))[0][
        "run_id"
    ]
    assert source_run != probe_run


@pytest.mark.parametrize(
    "corruption", ["arguments", "contract", "capture", "source_graph", "fresh"]
)
def test_corrupted_retained_probe_is_rejected(retained, corruption):
    store, candidate = retained

    def change(probe):
        if corruption == "arguments":
            probe["acquisition_requests"][0]["arguments"]["days"] += 1
        elif corruption == "contract":
            probe["acquisition_requests"][0]["contract_id"] = "0" * 64
        elif corruption == "capture":
            probe["execution"]["steps"][0]["output"] = []
        elif corruption == "source_graph":
            probe["source_graph_id"] = probe["graph_id"]
        else:
            probe["completed_tool_calls"] = 1

    identity = corrupt_probe(store, change)
    with pytest.raises(ValueError):
        verify_probe(store, candidate, identity)


@pytest.mark.parametrize(
    "corruption", ["dispatch_missing", "dispatch_other_run", "source_other_task"]
)
def test_original_source_dispatch_and_ownership_remain_required(retained, corruption):
    store, candidate = retained
    receipt_id = store.get(PROBE)["receipt_ids"][0]
    receipt = store.get(receipt_id)
    with store.connect() as connection:
        if corruption == "dispatch_missing":
            connection.execute(
                "DELETE FROM events WHERE artifact_id=?", (receipt["dispatch_evidence_id"],)
            )
        elif corruption == "dispatch_other_run":
            connection.execute(
                "UPDATE events SET run_id=? WHERE artifact_id=?",
                (store.get(KERNEL)["run_id"], receipt["dispatch_evidence_id"]),
            )
        else:
            connection.execute(
                "UPDATE runs SET task_id='wrong-task' WHERE id IN "
                "(SELECT run_id FROM events WHERE artifact_id=?)",
                (receipt_id,),
            )
    with pytest.raises(ValueError):
        verify_probe(store, candidate)


def test_retained_receipt_bytes_remain_hash_verified(retained):
    store, candidate = retained
    receipt_id = store.get(PROBE)["receipt_ids"][0]
    path = store.root / "artifacts" / f"{receipt_id}.json"
    corrupted = json.loads(path.read_bytes())
    corrupted["data"]["args"]["days"] += 1
    path.write_text(json.dumps(corrupted))
    with pytest.raises(ValueError, match="Artifact content has changed"):
        verify_probe(store, candidate)


@pytest.mark.parametrize("field", ["value", "inputs", "output"])
def test_reexecution_rejects_python_equal_typed_capture_corruption(retained, field):
    """Python equates 7 and 7.0, but exact immutable replay must distinguish them."""
    store, candidate = retained

    def change(probe):
        execution = probe["execution"]
        capture = deepcopy(store.get(execution["capture_id"]))
        if field == "value":
            original = capture["value"][0]["high_temp"]
            assert type(original) is int
            capture["value"][0]["high_temp"] = float(original)
        else:
            step = capture["steps"][-1]
            target = (
                step["inputs"]["entities"][0]["properties"]
                if field == "inputs"
                else step["output"][0]
            )
            original = target["high_temp"]
            assert type(original) is int
            target["high_temp"] = float(original)
            step["step_result_ref"] = store.put(
                "execution_step",
                {key: value for key, value in step.items() if key != "step_result_ref"},
            )
        # Keep the corrupted capture and outer evidence consistent. This isolates
        # the actual reexecution comparison, rather than its attestation checks.
        assert original == float(original)
        execution["capture_id"] = store.put("function_execution", capture)
        execution["value"] = capture["value"]
        execution["steps"] = capture["steps"]

    identity = corrupt_probe(store, change)
    with pytest.raises(ValueError, match="Pure reexecution differs"):
        verify_probe(store, candidate, identity)

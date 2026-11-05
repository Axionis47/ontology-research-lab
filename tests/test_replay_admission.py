"""Actual promotion and admission checks over genuine composed replay results."""

# Imported pytest fixtures are intentionally named as test arguments.
# ruff: noqa: F811

from __future__ import annotations

import shutil

import pytest
from test_historical_replay import replay_chain  # noqa: F401

from oak.historical_replay import inference_admission
from oak.service import Service


def test_corpus_promotion_keeps_last_winner_until_entire_bank_passes(replay_chain, tmp_path):
    root = tmp_path / "store"
    shutil.copytree(replay_chain["store"].root, root)
    service = Service(root)
    _, parent, good = replay_chain["kernels"]
    bad, task_id = replay_chain["bad_kernel_id"], replay_chain["task_id"]
    with service.store.connect() as db:
        db.execute("UPDATE tasks SET active_revision=? WHERE id=?", (parent, task_id))
        for identity in [good, bad]:
            assert (
                db.execute("SELECT parent FROM revisions WHERE id=?", (identity,)).fetchone()[0]
                == parent
            )
    assert not service.promotion_check(task_id, bad)["allowed"]
    with pytest.raises(ValueError):
        service.promote(task_id, bad)
    assert service.task(task_id)["active_revision"] == parent
    assert not inference_admission(service.store, bad)["allowed"]
    assert service.promotion_check(task_id, good)["allowed"]
    service.promote(task_id, good)
    assert service.task(task_id)["active_revision"] == good
    assert inference_admission(service.store, good)["allowed"]
    assert service.store.rows("SELECT id FROM model_calls") == []


def test_missing_original_evidence_never_authorizes_inference(replay_chain, tmp_path):
    root = tmp_path / "store"
    shutil.copytree(replay_chain["store"].root, root)
    service = Service(root)
    good = replay_chain["kernels"][2]
    case_id = replay_chain["case_ids"][0]
    (root / "artifacts" / f"{case_id}.json").unlink()
    assert not inference_admission(service.store, good)["allowed"]
    assert service.store.rows("SELECT id FROM model_calls") == []


def test_missing_captured_input_manifest_never_authorizes_inference(replay_chain, tmp_path):
    """An intact case/report cannot conceal a missing nested execution input."""
    root = tmp_path / "store"
    shutil.copytree(replay_chain["store"].root, root)
    service = Service(root)
    good = replay_chain["kernels"][2]
    capture = service.store.get(replay_chain["captures"][0])
    assert inference_admission(service.store, good)["allowed"]
    events = service.store.rows("SELECT * FROM events ORDER BY id")
    manifest_path = root / "artifacts" / f"{capture['input_manifest_ref']}.json"
    manifest_path.unlink()

    result = inference_admission(service.store, good)
    assert result["allowed"] is False
    assert result["reason"]
    assert service.store.rows("SELECT * FROM events ORDER BY id") == events
    assert service.store.rows("SELECT id FROM model_calls") == []

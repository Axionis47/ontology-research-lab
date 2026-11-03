"""Real OS-lock regression checks, with bounded subprocesses and genuine evidence."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from oak.corpus import load_local_corpus
from oak.service import Service

ROOT = Path(__file__).resolve().parents[1]

READ_HISTORY = """
import fcntl, json, sys
from pathlib import Path
from oak.service import Service
root, task_id, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
service = Service(root)
with (root / 'jobs.lock').open('a') as held:
    if mode == 'same_process':
        fcntl.flock(held, fcntl.LOCK_EX)
    rows = service.runs(task_id)
print(json.dumps(rows))
"""


@pytest.mark.parametrize("lock_owner", ["same_process", "other_process"])
def test_run_history_returns_while_job_lock_is_held(tmp_path: Path, lock_owner: str) -> None:
    """A caller's held submission lock and another process's lock must not block history."""
    service = Service(tmp_path)
    snapshot = load_local_corpus(ROOT / "tests/fixtures/ontology/manifest.json")
    task_id = service.create_task(
        "Real ontology source audit",
        "Inspect the provenance of the retained W3C ontology fixtures.",
        snapshot,
        ["Which source files were retained?"],
    )
    task = service.task(task_id)
    # A genuine persisted request is queued for inspection. No worker is launched
    # and no model result, completed status, or external response is substituted.
    run_id = service.store.create_run(
        task_id,
        "construct",
        {"task_id": task_id, "corpus_id": task["corpus_id"], "kind": "construct"},
    )
    with (tmp_path / "jobs.lock").open("a") as held:
        if lock_owner == "other_process":
            fcntl.flock(held, fcntl.LOCK_EX)
        try:
            process = subprocess.run(
                [sys.executable, "-c", READ_HISTORY, str(tmp_path), task_id, lock_owner],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
        except subprocess.TimeoutExpired:
            pytest.fail(f"Service.runs deadlocked with jobs.lock held by {lock_owner}")
    history = json.loads(process.stdout)
    assert len(history) == 1
    assert history[0]["id"] == run_id
    assert history[0]["status"] == "queued"
    assert history[0]["result_id"] is None
    assert service.store.rows("SELECT id FROM model_calls") == []

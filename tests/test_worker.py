"""Exercise the actual worker CLI and process reconciliation without model calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from oak.corpus import load_local_corpus
from oak.service import Service

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def saved_request(tmp_path: Path):
    service = Service(tmp_path)
    task_id = service.create_task(
        "Paper source provenance",
        "Inspect actual retained source evidence.",
        load_local_corpus(ROOT / "docs/paper/source/manifest.json"),
        ["Which source files were retained?"],
    )
    # Persist a real but invalid regression request. There is deliberately no
    # candidate, so the worker must record that actual validation failure.
    run_id = service.store.create_run(
        task_id,
        "regress",
        {
            "task_id": task_id,
            "kind": "regress",
            "parent": None,
            "corpus_id": service.task(task_id)["corpus_id"],
        },
    )
    return service, task_id, run_id


def run_process(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )


def test_worker_accepts_the_service_spawn_command_and_records_real_failure(saved_request) -> None:
    service, _, run_id = saved_request
    result = run_process(
        ["-m", "oak.cli", "worker", "--run-id", run_id, "--root", str(service.root)]
    )
    assert result.returncode != 0
    row = service.store.rows("SELECT * FROM runs WHERE id=?", (run_id,))[0]
    assert row["status"] == "failed"
    assert row["error"] == "No candidate based on the active revision exists"
    error = next(event for event in service.events(run_id) if event["stage"] == "error")
    evidence = service.artifact(error["artifact_id"])
    assert evidence["type"] == "ValueError"
    assert evidence["message"] == row["error"]
    assert (service.root / "jobs" / f"{run_id}.pid").is_file()
    assert service.store.rows("SELECT id FROM model_calls") == []


RECONCILE_OWNED_CHILD = """
import json, os, subprocess, sys, time
from pathlib import Path
from oak.service import Service
root, task_id, run_id = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
service = Service(root)
with subprocess.Popen([sys.executable, '-c', "print('exited')"],
                      stdout=subprocess.PIPE, text=True) as child:
    # Observe EOF and allow interpreter shutdown to finish without poll/wait,
    # which would reap the child. The outer subprocess has a five-second limit.
    # Keeping Popen alive also prevents destructor cleanup before reconciliation.
    assert child.stdout.read().strip() == 'exited'
    time.sleep(0.05)
    os.kill(child.pid, 0)
    jobs = root / 'jobs'
    jobs.mkdir(exist_ok=True)
    (jobs / f'{run_id}.pid').write_text(str(child.pid))
    service._reconcile_jobs(task_id)
    try:
        os.waitpid(child.pid, os.WNOHANG)
    except ChildProcessError:
        reaped = True
    else:
        raise AssertionError('Reconciliation did not reap its actual exited child')
    row = service.store.rows('SELECT status,error FROM runs WHERE id=?', (run_id,))[0]
    print(json.dumps({'owned_child_reaped': reaped, 'run': row}))
"""


def test_reconcile_marks_a_real_owned_zombie_worker_interrupted(saved_request) -> None:
    service, task_id, run_id = saved_request
    result = run_process(["-c", RECONCILE_OWNED_CHILD, str(service.root), task_id, run_id])
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["owned_child_reaped"] is True
    assert observed["run"]["status"] == "interrupted"
    assert observed["run"]["error"] == "Worker process exited before saving a result"
    event = next(event for event in service.events(run_id) if event["stage"] == "worker")
    assert event["status"] == "interrupted"
    assert service.store.rows("SELECT id FROM model_calls") == []

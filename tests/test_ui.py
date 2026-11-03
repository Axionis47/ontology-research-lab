"""Render the real Streamlit application over real stored evidence, without models or mocks."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from oak.corpus import load_local_corpus
from oak.service import Service, combine_corpus

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src/oak/ui.py"


@contextmanager
def isolated_workspace(path: Path):
    """Configure an actual independent service store, rather than substitute a backend."""
    previous = os.environ.get("OAK_DATA_ROOT")
    os.environ["OAK_DATA_ROOT"] = str(path)
    try:
        yield Service(path)
    finally:
        if previous is None:
            os.environ.pop("OAK_DATA_ROOT", None)
        else:
            os.environ["OAK_DATA_ROOT"] = previous


def test_empty_workspace_has_no_substitute_results(tmp_path: Path) -> None:
    with isolated_workspace(tmp_path) as service:
        app = AppTest.from_file(str(UI), default_timeout=30).run()
        assert not app.exception
        assert [item.value for item in app.title] == ["OaK"]
        assert any("Create a task with real evidence" in item.value for item in app.info)
        assert next(
            button for button in app.button if button.label == "Capture uploaded evidence"
        ).disabled
        assert service.tasks() == []
        assert service.budget()["calls"] == 0


def test_real_task_render_and_rerun_do_not_launch_jobs(tmp_path: Path) -> None:
    snapshot = load_local_corpus(ROOT / "tests/fixtures/ontology/manifest.json")
    with isolated_workspace(tmp_path) as service:
        task_id = service.create_task(
            "Ontology source audit",
            "Explain the provenance of the retained W3C ontology fixtures.",
            snapshot,
            ["Which W3C source files were retained?"],
        )
        app = AppTest.from_file(str(UI), default_timeout=30).run()
        assert not app.exception
        assert [tab.label for tab in app.tabs] == ["Ask", "Audit", "Revise", "History"]
        assert next(button for button in app.button if button.label == "Ask").disabled
        assert next(
            button for button in app.button if button.label == "Create and check candidate"
        ).disabled
        assert not next(
            button for button in app.button if button.label == "Build knowledge"
        ).disabled
        assert any("Records: 1" in item.value for item in app.caption)
        app.run()
        assert not app.exception
        assert service.runs(task_id) == []
        assert service.budget()["calls"] == 0
        # An invalid form submission must leave the actual store unchanged.
        next(button for button in app.button if button.label == "Save task").click().run()
        assert not app.exception
        assert any("Add a name" in error.value for error in app.error)
        assert len(service.tasks()) == 1
        assert service.runs(task_id) == []


def test_real_corpus_bundle_is_visible(tmp_path: Path) -> None:
    sources = combine_corpus(
        load_local_corpus(ROOT / "tests/fixtures/ontology/manifest.json"),
        load_local_corpus(ROOT / "README.md"),
    )
    with isolated_workspace(tmp_path) as service:
        service.create_task(
            "Project evidence audit",
            "Explain the retained project README and fixture source provenance.",
            sources,
            ["Which sources support the project and its ontology fixtures?"],
        )
        app = AppTest.from_file(str(UI), default_timeout=30).run()
        assert not app.exception
        assert any("2 saved evidence sources" in item.value for item in app.caption)
        assert len([item for item in app.success if item.value == "Evidence captured."]) == 2
        assert service.budget()["calls"] == 0


def test_actual_pilot_answer_precedes_history_and_resolves_citations(tmp_path: Path) -> None:
    """Render a completed real model run, without generating or substituting any answer."""
    manifest_path = ROOT / ".local/pilots/usgs.json"
    if not manifest_path.exists():
        pytest.skip("Run the genuine USGS acceptance pilot before saved-answer rendering checks")
    manifest = json.loads(manifest_path.read_text())
    with sqlite3.connect(f"file:{ROOT / '.local/catalog.sqlite'}?mode=ro", uri=True) as original:
        with sqlite3.connect(tmp_path / "catalog.sqlite") as snapshot:
            original.backup(snapshot)
    # Refer to actual immutable evidence. This check never changes or replaces
    # an artifact and never invokes a model or presses a job-submission button.
    (tmp_path / "artifacts").symlink_to(ROOT / ".local/artifacts", target_is_directory=True)
    with isolated_workspace(tmp_path) as service:
        completed = []
        for run in service.runs(manifest["task_id"]):
            if run["kind"] == "ask" and run["status"] == "completed":
                actual = service.artifact(run["result_id"])
                if actual.get("status") == "answered" and actual.get("citations"):
                    completed.append((run, actual))
        assert completed, "The real pilot must have a completed, cited answer before this check"
        run, actual = completed[0]
        before = service.budget()["calls"]
        app = AppTest.from_string(
            "from oak.ui import _run_detail\n"
            "from oak.service import Service\n"
            f"service = Service({str(tmp_path)!r})\n"
            f"run = next(row for row in service.runs({manifest['task_id']!r}) "
            f"if row['id'] == {run['id']!r})\n"
            "_run_detail(service, run, 'actual_answer')\n",
            default_timeout=30,
        ).run()
        assert not app.exception
        assert any(item.value == actual["answer"] for item in app.markdown)
        elements = list(app.main)
        answer_position = next(
            index
            for index, item in enumerate(elements)
            if item.type == "subheader" and item.value == "Answer"
        )
        timeline_position = next(
            index
            for index, item in enumerate(elements)
            if item.type == "expander" and item.label == "Run timeline and saved steps"
        )
        assert answer_position < timeline_position
        timeline = next(
            item for item in app.expander if item.label == "Run timeline and saved steps"
        )
        assert timeline.proto.expanded is False
        observation = next(
            item for item in actual["observations"] if item["id"] == actual["citations"][0]
        )
        assert any(observation["function"] in item.value for item in app.markdown)
        assert any(json.loads(item.value) == observation["args"] for item in app.json)
        execution = service.artifact(observation["artifact_id"])
        dependencies = execution["dependencies"]
        sources = dependencies.get("sources") or [
            {"document_id": identifier} for identifier in dependencies["source_ids"]
        ]
        source_ids = {source["document_id"] for source in sources[:100]}
        visible_ids = {
            identity
            for table in app.dataframe
            if "document_id" in table.value.columns
            for identity in table.value["document_id"]
        }
        assert source_ids <= visible_ids
        assert any(f"of {len(sources)} recorded sources" in item.value for item in app.caption)
        assert service.budget()["calls"] == before

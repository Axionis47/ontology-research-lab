"""Render the real Streamlit application over real stored evidence, without models or mocks."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

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
    snapshot = load_local_corpus(ROOT / "docs/paper/source/manifest.json")
    with isolated_workspace(tmp_path) as service:
        task_id = service.create_task(
            "Paper source audit",
            "Explain the provenance of the retained OaK source files.",
            snapshot,
            ["Which source files were retained for the paper?"],
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
        load_local_corpus(ROOT / "docs/paper/source/manifest.json"),
        load_local_corpus(ROOT / "docs/paper/extracted/paper-pdf.txt"),
    )
    with isolated_workspace(tmp_path) as service:
        service.create_task(
            "Paper evidence audit",
            "Explain the retained paper and its source provenance.",
            sources,
            ["How does the paper define the ontology kernel?"],
        )
        app = AppTest.from_file(str(UI), default_timeout=30).run()
        assert not app.exception
        assert any("2 saved evidence sources" in item.value for item in app.caption)
        assert len([item for item in app.success if item.value == "Evidence captured."]) == 2
        assert service.budget()["calls"] == 0

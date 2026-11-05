"""Inspect actual stage files and their portable attribution, without model calls."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from oak.construction_prompts import prompt_manifest, stage_prompt

PROJECT = Path(__file__).resolve().parents[1]


def test_manifest_pins_exact_sources_and_assembled_prompts() -> None:
    """A saved manifest can reproduce prompts after source files later change."""
    manifest = prompt_manifest()
    assert manifest["version"] == 5
    sources = {source["path"]: source for source in manifest["sources"]}
    assert len(sources) == 5
    for path, source in sources.items():
        assert not Path(path).is_absolute()
        raw = (PROJECT / path).read_bytes()
        assert raw == source["content"].encode("utf-8")
        assert hashlib.sha256(raw).hexdigest() == source["sha256"]
    assert set(manifest["stages"]) == {"requirements", "schema", "functions", "extraction"}
    for stage, prompt in manifest["stages"].items():
        assert len(prompt["source_paths"]) == 2
        common, specific = (sources[path]["content"] for path in prompt["source_paths"])
        content = f"{common.rstrip()}\n\n{specific.rstrip()}\n"
        assert content == prompt["instruction"] == stage_prompt(stage)
        assert hashlib.sha256(content.encode("utf-8")).hexdigest() == prompt["sha256"]
        assert "\u2014" not in content
        assert "weather" not in content.casefold()


def test_stage_prompts_do_not_assign_other_stages_execution_work() -> None:
    """Only the function stage receives the executable DSL and proposal protocol."""
    prompts = prompt_manifest()["stages"]
    assert "FunctionProposal" in prompts["functions"]["instruction"]
    assert "RequirementAnalysis" in prompts["requirements"]["instruction"]
    assert "entity_tables" in prompts["extraction"]["instruction"]
    for stage in ("requirements", "schema", "extraction"):
        assert "invoke_capability takes" not in prompts[stage]["instruction"]
        assert "FunctionProposal" not in prompts[stage]["instruction"]
    assert "Prefer one or two" not in prompts["functions"]["instruction"]


@pytest.mark.parametrize("stage", ["unknown", "../task-runtime", "task-runtime.md"])
def test_only_known_prompt_stages_can_be_loaded(stage: str) -> None:
    """Runtime text cannot become an arbitrary path or the wrong stage prompt."""
    with pytest.raises(ValueError, match="Unknown construction prompt stage"):
        stage_prompt(stage)

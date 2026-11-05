"""Focused construction prompts and exact, portable source attribution.

Prompt text is data. Workflow control and validation remain in the executor.
The manifest contains the assembled text so a run can pin one snapshot even
when source files change before later stages execute.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

PROJECT = Path(__file__).resolve().parents[2]
PROMPT_VERSION = 3
ConstructionStage = Literal["requirements", "schema", "functions", "extraction"]
_SHARED = "task-construction.md"
_STAGE_FILES: dict[ConstructionStage, str] = {
    "requirements": "requirement-analysis.md",
    "schema": "schema-drafting.md",
    "functions": "function-composition.md",
    "extraction": "graph-extraction.md",
}


def _source(filename: str) -> dict[str, str]:
    """Read one allowlisted UTF-8 source without exposing a machine path."""
    relative = Path("config/prompts") / filename
    raw = (PROJECT / relative).read_bytes()
    return {
        "path": relative.as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "content": raw.decode("utf-8"),
    }


def _assemble(shared: str, specific: str) -> str:
    return f"{shared.rstrip()}\n\n{specific.rstrip()}\n"


def stage_prompt(stage: ConstructionStage) -> str:
    """Load common grounding rules plus exactly one focused stage prompt.

    For a persisted run, use its prompt manifest's stage content throughout the
    run. This convenience function reads the current checked-in source files.
    """
    if stage not in _STAGE_FILES:
        raise ValueError(f"Unknown construction prompt stage: {stage!r}")
    return _assemble(_source(_SHARED)["content"], _source(_STAGE_FILES[stage])["content"])


def prompt_manifest() -> dict:
    """Snapshot source bytes and every assembled prompt for a construction run.

    Source hashes identify original file bytes. Stage hashes identify assembled
    UTF-8 prompt bytes. They deliberately describe different content and must
    not be presented interchangeably.
    """
    shared = _source(_SHARED)
    sources = [shared]
    stages = {}
    for stage, filename in _STAGE_FILES.items():
        specific = _source(filename)
        sources.append(specific)
        content = _assemble(shared["content"], specific["content"])
        stages[stage] = {
            "source_paths": [shared["path"], specific["path"]],
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "instruction": content,
        }
    return {"version": PROMPT_VERSION, "sources": sources, "stages": stages}

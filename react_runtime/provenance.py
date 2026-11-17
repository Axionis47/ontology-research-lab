"""Capture local implementation inputs for later diagnosis, without environment secrets."""

import inspect
import platform
from importlib.metadata import version
from pathlib import Path


def snapshot_sources(store, root: Path, tools, verifier) -> dict:
    paths = set((root / "react_runtime").glob("*.py"))
    paths.update((root / "appworld_runtime").glob("*.py"))
    paths.update((root / "repair_runtime").glob("*.py"))
    paths.update(root / p for p in (
        "scripts/run_react.py", "scripts/inspect_trace.py", "config/react_loop.toml",
        "config/models.toml", "config/gemini-no-tools.toml", "prompts/react_system.txt",
        "docs/system/contracts.schema.json", "requirements-react.txt", "requirements-appworld.txt",
        "scripts/run_appworld.py", "config/appworld_loop.toml", "config/appworld_surface.json",
        "config/appworld_surface_reviews.json"))
    verifier_file = inspect.getsourcefile(verifier) if verifier else None
    if verifier_file and Path(verifier_file).resolve().is_relative_to(root):
        paths.add(Path(verifier_file).resolve())
    for tool in tools:
        for argument in tool.command:
            candidate = (root / argument).resolve()
            if candidate.is_relative_to(root) and candidate.is_file() and candidate.suffix == ".py":
                paths.add(candidate)
    snapshots = []
    for path in sorted(paths):
        if path.is_file():
            snapshots.append({"source_path": str(path.relative_to(root)),
                              "artifact_ref": store.write("sources", path.read_bytes(), raw=True)})
    return store.write("metadata", {
        "files": snapshots, "python": platform.python_version(), "platform": platform.platform(),
        "jsonschema": version("jsonschema"),
        "verifier": None if verifier is None else {
            "module": verifier.__module__, "qualname": verifier.__qualname__, "source_file": verifier_file},
        "coverage": "Listed project sources at episode start, not a frozen OS/container or model checkpoint",
        "environment_capture": "No environment variables or credentials recorded"})

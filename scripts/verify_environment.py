"""Verify real setup components and save their evidence without invoking an LLM.

Run with the locked project environment. The report is a setup receipt, not
an ontology validation, workflow-resumption test, or benchmark score.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import platform
import sqlite3
import subprocess
import tempfile
import time
import tomllib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    """Return the digest of an existing artifact, read without modification."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def check_python() -> dict[str, str]:
    """Verify the active interpreter against the project pin."""
    expected = (PROJECT / ".python-version").read_text().strip()
    actual = platform.python_version()
    if actual != expected:
        raise RuntimeError(f"Python pin is {expected}, running {actual}")
    return {"version": actual, "implementation": platform.python_implementation()}


def check_dependencies() -> dict[str, Any]:
    """Check all direct dependency pins and import the selected integration surfaces."""
    config = tomllib.loads((PROJECT / "pyproject.toml").read_text())
    requirements = list(config["project"]["dependencies"])
    for group in config["dependency-groups"].values():
        requirements.extend(group)
    versions = {}
    for requirement in requirements:
        package, expected = requirement.split("==")
        package = package.split("[")[0]
        actual = importlib.metadata.version(package)
        if actual != expected:
            raise RuntimeError(f"{package}: expected {expected}, installed {actual}")
        versions[package] = actual
    modules = [
        "langchain.agents",
        "langchain_core.tools",
        "langchain_openai",
        "langchain_anthropic",
        "langgraph.graph",
        "langgraph.checkpoint.sqlite",
        "langsmith.evaluation",
        "networkx",
        "owlready2",
        "pydantic",
        "pydantic_settings",
        "sqlmodel",
        "fastapi",
        "uvicorn",
        "structlog",
        "typer",
        "mkdocs",
        "mkdocstrings",
        "pypdfium2",
        "bs4",
    ]
    for module in modules:
        importlib.import_module(module)
    return {"direct_versions": versions, "imported_modules": modules}


def check_sqlite_checkpointer() -> dict[str, Any]:
    """Initialize the real checkpoint database, close it, and inspect the reopened schema.

    No agent state or synthetic task is inserted. This verifies database setup,
    not the future application's interrupt/resume behavior.
    """
    from langgraph.checkpoint.sqlite import SqliteSaver

    with tempfile.TemporaryDirectory(prefix="oak-checkpoint-check-") as directory:
        database = Path(directory) / "checkpoints.sqlite"
        with SqliteSaver.from_conn_string(str(database)) as saver:
            if list(saver.list(None)):
                raise RuntimeError("New checkpoint database unexpectedly contains data")
        with sqlite3.connect(database) as connection:
            tables = sorted(
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            )
            if not {"checkpoints", "writes"}.issubset(tables):
                raise RuntimeError(f"Missing checkpoint tables: {tables}")
    return {"sqlite_version": sqlite3.sqlite_version, "reopened_tables": tables}


def check_hermit() -> dict[str, str]:
    """Start the pinned JVM and Owlready2's bundled HermiT, recording their real versions."""
    import owlready2

    lock = json.loads((PROJECT / "toolchain-java.lock.json").read_text())
    java = PROJECT / lock["install_directory"] / lock["java_relative_path"]
    java_result = subprocess.run(
        [str(java), "-version"], capture_output=True, text=True, check=True, timeout=30
    )
    java_version = (java_result.stdout + java_result.stderr).strip()
    if f"Temurin-{lock['version']}" not in java_version:
        raise RuntimeError(f"Unexpected Java version: {java_version}")
    jar = Path(owlready2.__file__).parent / "hermit" / "HermiT.jar"
    result = subprocess.run(
        [str(java), "-cp", str(jar), "org.semanticweb.HermiT.cli.CommandLine", "--version"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    output = (result.stdout + result.stderr).strip()
    if "HermiT" not in output:
        raise RuntimeError(f"Unexpected HermiT startup output: {output}")
    return {
        "java_version": java_version,
        "hermit_version_output": output,
        "hermit_jar_sha256": sha256(jar),
        "scope": "JVM and reasoner startup only; no ontology consistency claim",
    }


def check_paper_sources(source_directory: Path) -> list[dict[str, Any]]:
    """Verify the retained PDF and HTML against their source capture manifest."""
    manifest = json.loads((source_directory / "manifest.json").read_text())
    evidence = []
    for source in manifest["files"]:
        path = source_directory / source["file"]
        actual = sha256(path)
        if actual != source["sha256"] or path.stat().st_size != source["bytes"]:
            raise RuntimeError(f"Source integrity failure: {source['file']}")
        evidence.append({"file": source["file"], "sha256": actual, "bytes": source["bytes"]})
    return evidence


def main() -> None:
    """Run independent setup checks and write an auditable receipt, including failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".local/verification/environment.json"))
    parser.add_argument(
        "--paper-sources", type=Path, help="Optional local directory containing the paper manifest"
    )
    args = parser.parse_args()
    checks: list[tuple[str, Callable[[], Any]]] = [
        ("python", check_python),
        ("dependencies", check_dependencies),
        ("sqlite_checkpointer_setup", check_sqlite_checkpointer),
        ("java_and_hermit_startup", check_hermit),
    ]
    if args.paper_sources is not None:
        checks.append(("paper_source_integrity", lambda: check_paper_sources(args.paper_sources)))
    report: dict[str, Any] = {
        "report_version": 1,
        "kind": "environment_readiness",
        "generated_at": datetime.now(UTC).isoformat(),
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "inputs": {
            name: sha256(PROJECT / name)
            for name in [
                "pyproject.toml",
                "uv.lock",
                "toolchain-java.lock.json",
                "scripts/verify_environment.py",
            ]
        },
        "checks": [],
        "not_verified": [
            "OaK construction and inference",
            "ontology consistency on a real application schema",
            "application checkpoint/resume behavior",
            "provider calls and LangSmith cloud delivery",
            "benchmark performance and adapter regressions",
        ],
    }
    if args.paper_sources is None:
        report["not_verified"].append("Local paper source integrity (--paper-sources not supplied)")
    for name, check in checks:
        started = time.monotonic()
        entry = {"name": name}
        try:
            entry.update(status="passed", evidence=check())
        except Exception as error:
            entry.update(status="failed", error=f"{type(error).__name__}: {error}")
        entry["duration_seconds"] = round(time.monotonic() - started, 4)
        report["checks"].append(entry)
    report["status"] = (
        "passed" if all(check["status"] == "passed" for check in report["checks"]) else "failed"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "report": str(args.output)}))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()

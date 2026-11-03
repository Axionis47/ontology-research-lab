"""Install the pinned JRE locally and print verified executable information.

The lock file records the official release asset and its published SHA-256.
Python 3.12+ is required for safe tar extraction. No system Java is changed.
Run from any directory with: python scripts/setup_java.py
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

PROJECT = Path(__file__).resolve().parents[1]


def verify_java(executable: Path, version: str) -> str:
    """Execute Java and reject a runtime that does not match the pinned build."""
    result = subprocess.run(
        [str(executable), "-version"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    output = (result.stdout + result.stderr).strip()
    if f"Temurin-{version}" not in output:
        raise RuntimeError(f"Unexpected Java runtime: {output}")
    return output


def main() -> None:
    """Download, verify, extract, and report the pinned local Java runtime."""
    lock = json.loads((PROJECT / "toolchain-java.lock.json").read_text())
    actual_platform = {"system": platform.system(), "machine": platform.machine()}
    if actual_platform != lock["platform"]:
        raise SystemExit(
            f"This lock supports {lock['platform']}; found {actual_platform}. "
            "Add a separately verified platform asset before installing."
        )
    destination = PROJECT / lock["install_directory"]
    java_root = PROJECT / ".tools" / "java"
    destination.resolve().relative_to(java_root.resolve())
    executable = destination / lock["java_relative_path"]
    executable.resolve().relative_to(destination.resolve())
    receipt = destination / "oak-installation.json"
    java_root.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        if not receipt.is_file() or json.loads(receipt.read_text())["sha256"] != lock["sha256"]:
            raise SystemExit(f"Existing installation lacks the matching receipt: {destination}")
    else:
        with tempfile.TemporaryDirectory(prefix="install-", dir=java_root) as temporary:
            staging = Path(temporary)
            archive = staging / "runtime.tar.gz"
            digest = hashlib.sha256()
            size = 0
            request = Request(lock["url"], headers={"User-Agent": "OaK-project-setup/1"})
            with urlopen(request, timeout=60) as response, archive.open("wb") as target:
                while chunk := response.read(1024 * 1024):
                    target.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            if digest.hexdigest() != lock["sha256"] or size != lock["size_bytes"]:
                raise RuntimeError("Downloaded JRE does not match the locked size and SHA-256")
            extracted = staging / "extracted"
            extracted.mkdir()
            with tarfile.open(archive, mode="r:gz") as package:
                package.extractall(extracted, filter="data")
            roots = list(extracted.iterdir())
            if len(roots) != 1 or not roots[0].is_dir():
                raise RuntimeError("Expected exactly one runtime directory in the archive")
            output = verify_java(roots[0] / lock["java_relative_path"], lock["version"])
            (roots[0] / "oak-installation.json").write_text(
                json.dumps(
                    {"sha256": digest.hexdigest(), "source": lock["url"], "java_version": output},
                    indent=2,
                )
                + "\n"
            )
            shutil.move(str(roots[0]), destination)

    output = verify_java(executable, lock["version"])
    print(json.dumps({"executable": str(executable), "java_version": output}, indent=2))


if __name__ == "__main__":
    main()

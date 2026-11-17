#!/usr/bin/env python3
"""Unpack the pinned AppWorld source bundles and download data if absent."""

import argparse
import hashlib
import importlib.metadata
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

REVISION = "42b5bcf3cd334fee33f0c37c02070a9f5807add5"
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / ".appworld")
    args = parser.parse_args()
    root = args.root.resolve()
    os.environ["APPWORLD_ROOT"] = str(root)
    os.environ["APPWORLD_CACHE"] = str(root / ".cache")
    distribution = importlib.metadata.distribution("appworld")
    package = Path(distribution.locate_file("appworld"))
    # GitHub archives contain LFS pointers. Fetch their official objects and
    # verify the pointer's digest and byte count before unpacking anything.
    for name in ("apps.bundle", "tests.bundle"):
        path = package / ".source" / name
        content = path.read_bytes()
        if content.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
            pointer = content.decode()
            expected = re.search(r"oid sha256:([0-9a-f]{64})", pointer).group(1)
            length = int(re.search(r"size ([0-9]+)", pointer).group(1))
            url = f"https://media.githubusercontent.com/media/StonyBrookNLP/appworld/{REVISION}/src/appworld/.source/{name}"
            with urllib.request.urlopen(url, timeout=90) as response:
                payload = response.read(length + 1)
            if len(payload) != length or hashlib.sha256(payload).hexdigest() != expected:
                raise ValueError(f"AppWorld bundle failed integrity verification: {name}")
            path.write_bytes(payload)
    subprocess.run([sys.executable, "-m", "appworld.cli", "install"], check=True)
    if not (root / "data").exists():
        subprocess.run([sys.executable, "-m", "appworld.cli", "download", "data", "--root", str(root)], check=True)
    if not (root / "data/datasets/train.txt").is_file():
        raise RuntimeError("AppWorld training data is incomplete; existing data was not overwritten")
    import json
    from appworld.common.constants import COMPATIBLE_DB_VERSIONS
    task_id = (root / "data/datasets/train.txt").read_text().splitlines()[0]
    data_version = json.loads((root / "data/tasks" / task_id / "specs.json").read_text())["db_version"]
    if data_version not in COMPATIBLE_DB_VERSIONS:
        raise RuntimeError(f"Existing data version {data_version} is incompatible; prepare a new --root. Existing data was preserved.")
    print(f"AppWorld is prepared at {root}")


if __name__ == "__main__":
    main()

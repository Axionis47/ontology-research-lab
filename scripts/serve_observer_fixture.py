"""Serve a disposable copy of reviewed real replay evidence for browser checks.

The application and storage are real. No responses or service calls are mocked.
The checked-in fixture is never opened writable, and the browser suite performs
observation only. Live verification uses the ordinary server and global ledger.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

import uvicorn

from oak.api import create_app


def main() -> None:
    """Launch the actual API over copied, hash-verified historical artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8502)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    source = project / "tests/fixtures/observer/weather"
    with tempfile.TemporaryDirectory(prefix="oak-replay-browser-") as directory:
        root = Path(directory) / "workspace"
        shutil.copytree(source, root)
        uvicorn.run(create_app(root), host="127.0.0.1", port=args.port, proxy_headers=False)


if __name__ == "__main__":
    main()

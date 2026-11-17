"""A fixed-command bridge. The actor can access discovery, inspection and MCP calls."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from appworld_runtime.rpc import request


def main():
    address, method = sys.argv[1:]
    if method not in {"discover", "describe", "call"}:
        raise ValueError("Unknown actor operation")
    result = request(address, method, json.load(sys.stdin))
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()

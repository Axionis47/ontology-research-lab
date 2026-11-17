#!/usr/bin/env python3
"""Audit a run or read bounded original evidence. Never executes model or tool actions."""

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from react_runtime.store import IntegrityError, RunStore, json_bytes, timestamp
from react_runtime.loop import parse_json


def read_evidence(store, artifact_id, *, pointer=None, start=0, maximum=2000, diagnostics=False):
    if start < 0 or not 1 <= maximum <= 8192:
        raise ValueError("Require start >= 0 and 1 <= maximum <= 8192")
    row = store.db.execute("SELECT kind,digest FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
    if row is None:
        raise KeyError("Unknown artifact in this run")
    if row[0] == "diagnostics" and not diagnostics:
        raise PermissionError("Diagnostic reads require --include-diagnostics; they may contain private CLI messages")
    data = store.get(artifact_id).decode()
    if pointer is not None:
        if pointer and not pointer.startswith("/"):
            raise ValueError("JSON pointer must be empty or start with /")
        value = parse_json(data)
        for part in pointer.split("/")[1:]:
            part = part.replace("~1", "/").replace("~0", "~")
            value = value[int(part)] if isinstance(value, list) else value[part]
        data = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if start > len(data):
        raise ValueError("start is beyond the selected text")
    end = min(start + maximum, len(data))
    content = data[start:end]
    return {"artifact_id": artifact_id, "source_sha256": row[1], "json_pointer": pointer,
            "unit": "unicode_characters_in_selected_text", "start": start, "end_exclusive": end,
            "total_chars": len(data), "content": content, "returned_chars": len(content),
            "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "next_start": end if end < len(data) else None,
            "omitted_prefix_chars": min(start, len(data)), "omitted_suffix_chars": max(0, len(data) - end)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit", "index", "step", "read"])
    parser.add_argument("run", type=Path)
    parser.add_argument("selector", nargs="?")
    parser.add_argument("--pointer")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--max-chars", type=int, default=2000)
    parser.add_argument("--include-diagnostics", action="store_true")
    args = parser.parse_args()
    store = RunStore.open_existing(args.run)
    try:
        packet = store.audit()
        if args.command == "audit":
            result = {"complete": packet["complete"], "problems": packet["problems"],
                      "events": len(packet["events"]), "artifacts": len(packet["artifacts"]),
                      "steps": len(packet["steps"]), "last_event_sha256": packet["last_event_sha256"]}
        elif args.command == "index":
            result = {"complete": packet["complete"], "problems": packet["problems"],
                      "steps": packet["steps"], "limitations": packet["limitations"],
                      "episode_metadata": [e for e in packet["events"] if e["step"] == 0]}
        elif args.command == "step":
            step = int(args.selector)
            result = {"complete": packet["complete"], "problems": packet["problems"], "step": step,
                      "events": [e for e in packet["events"] if e["step"] == step],
                      "artifacts": [a for a in packet["artifacts"] if a["step"] == step]}
            if not result["events"]:
                raise KeyError("Step does not exist")
        else:
            result = {"complete": packet["complete"], "problems": packet["problems"],
                      "evidence": read_evidence(store, args.selector, pointer=args.pointer, start=args.start,
                          maximum=args.max_chars, diagnostics=args.include_diagnostics)}
        # Inspection is a separate job. Preserve exactly what it was shown, outside the original ledger.
        directory = store.root / "inspections"
        directory.mkdir(mode=0o700, exist_ok=True)
        receipt = directory / f"{uuid.uuid4()}.json"
        body = {"at": timestamp(), "command": args.command, "selector": args.selector,
                "source_event_head": packet["last_event_sha256"], "result": result}
        with receipt.open("xb") as handle:
            handle.write(json_bytes(body))
            handle.flush()
            os.fsync(handle.fileno())
        receipt.chmod(0o400)
        print(json.dumps({**result, "inspection_receipt": str(receipt)}, indent=2))
        return 0 if packet["complete"] else 2
    except (IntegrityError, KeyError, ValueError, TypeError, IndexError, PermissionError) as error:
        print(json.dumps({"error": type(error).__name__, "message": str(error)}))
        return 2
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())

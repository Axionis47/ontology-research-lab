"""Read-only local fixtures and a scripted model for component verification."""

from __future__ import annotations

import argparse
import json
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["record", "scripted", "invalid", "unknown", "early_finish", "sleep", "partial"])
    parser.add_argument("--long", action="store_true")
    parser.add_argument("--padding", type=int, default=0)
    args = parser.parse_args()
    payload = json.load(sys.stdin)
    if args.mode == "record":
        record_id = payload["record_id"]
        print(json.dumps({"record_id": record_id, "status": "delivered",
                          "proof": f"proof-for-{record_id}", "padding": "x" * args.padding}))
        return
    if args.mode in {"sleep", "partial"}:
        if args.mode == "partial":
            print('{"unfinished":', flush=True)
        time.sleep(10)
        return
    request_id, step = payload["turn"]["request_id"], payload["turn"]["step"]

    def act(name, arguments):
        return {"kind": "act", "request_id": request_id, "action_id": name,
                "arguments": arguments, "evidence_ids": [], "reason": "Read recorded evidence."}

    def finish(answer):
        return {"kind": "finish", "request_id": request_id, "answer": answer,
                "artifact_refs": [], "claimed_requirement_ids": ["task"]}

    if args.mode == "invalid":
        print('{"kind":"act","kind":"finish"}')
    elif args.mode == "unknown":
        print(json.dumps(act("not_registered", {})))
    elif args.mode == "early_finish" and step == 1:
        print(json.dumps(finish("delivered")))
    elif args.long:
        if step <= 5:
            result = act("get_record", {"record_id": f"r{step}"})
        elif step == 6:
            prior = payload["compacted_steps"] + [
                {"step": r["step"], "output_id": r["observation"].get("output_id")}
                for r in payload["recent_steps"]]
            first = next(row for row in prior if row["step"] == 1)
            result = act("read_output", {"output_id": first["output_id"], "json_pointer": "/proof"})
        else:
            result = finish("proof-for-r1")
        print(json.dumps(result))
    elif step == 1 or (args.mode == "early_finish" and step == 2):
        print(json.dumps(act("get_record", {"record_id": "123"})))
    else:
        print(json.dumps(finish("delivered")))


if __name__ == "__main__":
    main()

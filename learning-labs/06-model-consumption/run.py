"""Prepare interfaces; --live measures the configured Qwen on synthetic cases."""
import argparse
import copy
import datetime
import hashlib
import json
from pathlib import Path
import sys
import tomllib
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOL = {"type": "function", "function": {"name": "read_records", "description": "Read all source-attributed records in this tiny task world. No filtering or reasoning is performed.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}}


def prepare(data, case, mode):
    common = "Use only supplied observations and the stated rule. Return JSON with answer (person name or unknown) and evidence_ids (array). Do not invent facts."
    user = {"question": data["question"], "definitions": data["definitions"]}
    if mode == "text":
        user["observations"] = ["Record " + row["evidence_id"] + ": " + "; ".join(f"{k} is {json.dumps(v)}" for k, v in row.items() if k != "evidence_id") + "." for row in case["records"]]
    elif mode == "ontology":
        user["observations"] = case["records"]
    else:
        user["instruction"] = "Call read_records to obtain the observations before answering."
    request = {"messages": [{"role": "system", "content": common}, {"role": "user", "content": json.dumps(user)}]}
    if mode == "query":
        request["tools"] = [TOOL]
    return request


def chat(config, body, events):
    request = {"model": config["model"], "stream": False, "think": config["think"], "options": {key: config[key] for key in ("num_ctx", "num_predict", "temperature")}, **body}
    event = {"request": copy.deepcopy(request)}
    events.append(event)
    try:
        wire = urllib.request.Request(config["base_url"].rstrip("/") + "/api/chat", data=json.dumps(request).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(wire, timeout=config["timeout_seconds"]) as response:
            result = json.load(response)
        event["response"] = result
        if result.get("model") != config["model"] or not result.get("done") or result.get("done_reason") == "length":
            raise ValueError("Unexpected model, incomplete response, or output limit")
        return result["message"]
    except Exception as error:
        event["error"] = {"type": type(error).__name__, "message": str(error)}
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    data = json.loads((HERE / "inputs.json").read_text())
    config = tomllib.loads((ROOT / "config/models.toml").read_text())["ollama"]
    rows = [{"case_id": case["id"], "interface": mode, "status": "NOT_RUN", "expected": case["expected"], "request": prepare(data, case, mode), "available_observations": case["records"]} for case in data["cases"] for mode in ("text", "ontology", "query")]
    report = {"experiment": "06-model-consumption", "kind": "synthetic model-interface experiment", "status": "PREPARED_NOT_RUN", "actor": {"provider": "ollama", "configured_model": config["model"]}, "input_sha256": hashlib.sha256((HERE / "inputs.json").read_bytes()).hexdigest(), "checks": {"six_interfaces_prepared": len(rows) == 6, "expected_answers_not_in_requests": all("expected" not in row["request"] for row in rows)}, "trials": rows}
    if args.live:
        report["status"] = "MEASURED"
        for row in rows:
            row["status"] = "ATTEMPTED"
            events = row["events"] = []
            try:
                request = copy.deepcopy(row["request"])
                message = chat(config, request, events)
                if row["interface"] == "query":
                    calls = message.get("tool_calls", [])
                    if len(calls) != 1 or calls[0]["function"]["name"] != "read_records" or calls[0]["function"]["arguments"] != {}:
                        raise ValueError("Expected exactly one admitted read_records call with empty arguments")
                    request["messages"].append(message)
                    request["messages"].append({"role": "tool", "tool_name": "read_records", "content": json.dumps(row["available_observations"])})
                    request.pop("tools")
                    message = chat(config, request, events)
                answer = json.loads(message["content"])
                ids = answer.get("evidence_ids")
                known = {r["evidence_id"] for r in row["available_observations"]}
                row["answer"] = answer
                row["passed"] = answer.get("answer") == row["expected"] and isinstance(ids, list) and all(isinstance(i, str) and i in known for i in ids) and (row["expected"] == "unknown" or "e2" in ids)
                row["status"] = "PASS" if row["passed"] else "FAIL"
            except Exception as error:
                row["passed"] = False
                row["status"] = "ERROR"
                row["error"] = {"type": type(error).__name__, "message": str(error)}
                if isinstance(error, (OSError, urllib.error.URLError)):
                    report["status"] = "MODEL_UNAVAILABLE"
                    break
        report["checks"]["all_trials_completed_and_correct"] = all(row.get("passed") for row in rows)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = HERE / "results" / f"{stamp}.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({**report, "receipt": str(target)}, indent=2))
    return 0 if all(report["checks"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())

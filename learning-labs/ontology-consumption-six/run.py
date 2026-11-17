"""Six ontology-consumption interfaces over identical task facts and rules."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("helpers", HERE.parent / "gemini_experiments.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
RULE_IDS = [f"R{i}" for i in range(1, 7)]
FINAL_KEYS = {"type", "person", "evidence_ids", "ontology_version", "graph_revision", "rule_ids"}


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def closure(ontology, roots=("eligibility",)):
    wanted = set(roots)
    while True:
        expanded = wanted | {name for term in wanted for name in ontology["definitions"][term].get("requires", [])}
        if expanded == wanted:
            return {k: ontology["definitions"][k] for k in sorted(wanted)}
        wanted = expanded


def violations(row, world):
    t = world["task"]
    conditions = [row["service"] == t["service"], row["environment"] == t["environment"],
                  row["role"] == "DeploymentApprover", row["active"] is True,
                  row["validFrom"] <= t["at"] < row["validUntil"], row["person"] != world["deployment"]["author"]]
    return [rule for rule, passed in zip(RULE_IDS, conditions) if not passed]


def assess_person(person, world):
    rows = [r for r in world["assignments"] if r["person"] == person]
    if not rows:
        return {"person": person, "status": "UNKNOWN", "reason": "No observed assignment"}
    passing = [r for r in rows if not violations(r, world)]
    return {"person": person, "status": "ELIGIBLE" if passing else "INELIGIBLE",
            "assignments": [{"id": r["id"], "violated_rules": violations(r, world)} for r in rows],
            "evidence_ids": [r["id"] for r in passing] + ([world["deployment"]["id"]] if passing else [])}


def interfaces(mode):
    return {
        "inspect": {"inspect_schema": {"arguments": {"names": "array of catalog names"}, "returns": "Requested ontology definitions and their dependency closure; includes rule meanings when eligibility is requested."}},
        "query": {"query_assignments": {"arguments": {"predicates": "array of {field, op, value}; op is eq, ne, lt, lte, gt or gte"}, "returns": "Observed assignments matching ALL supplied predicates. Empty predicates return all. This does not automatically add eligibility conditions."}},
        "function": {"find_eligible_approvers": {"arguments": {"service": "string", "environment": "string", "deployment_id": "string", "at": "YYYY-MM-DD"}, "returns": "Eligible candidates and explanations under the pinned six business rules; rejects unsupported task bindings."}},
        "check": {"check_candidates": {"arguments": {"people": "nonempty array of unique person names, at most 4"}, "returns": "For each proposed person, eligibility, violated rule IDs and evidence under the pinned rules. Does not propose unrequested people."}}
    }.get(mode, {})


def execute(call, mode, world, ontology):
    if not isinstance(call, dict) or set(call) != {"type", "name", "arguments"} or call["type"] != "call":
        raise ValueError("Call requires exactly type, name and arguments")
    name, args = call["name"], call["arguments"]
    if name not in interfaces(mode) or not isinstance(args, dict):
        raise ValueError("Unknown interface or argument object")
    base = {"ontology_version": ontology["version"], "graph_revision": world["revision"], "source": world["source"]}
    if name == "inspect_schema":
        if set(args) != {"names"} or not isinstance(args["names"], list) or not args["names"] or any(type(v) is not str or v not in ontology["definitions"] for v in args["names"]):
            raise ValueError("names must be a nonempty array of catalog entries")
        return {**base, "definitions": closure(ontology, args["names"])}
    if name == "find_eligible_approvers":
        if args != world["task"]:
            raise ValueError("Function supports only the exact bound task in this lesson")
        checked = [assess_person(p, world) for p in sorted({r["person"] for r in world["assignments"]})]
        return {**base, "rule_ids": RULE_IDS, "candidates": [r for r in checked if r["status"] == "ELIGIBLE"], "excluded": [r for r in checked if r["status"] != "ELIGIBLE"]}
    if name == "check_candidates":
        if set(args) != {"people"} or not isinstance(args["people"], list) or not 1 <= len(args["people"]) <= 4 or any(type(v) is not str for v in args["people"]) or len(set(args["people"])) != len(args["people"]):
            raise ValueError("people must contain 1 to 4 unique strings")
        return {**base, "rule_ids": RULE_IDS, "checks": [assess_person(p, world) for p in args["people"]]}
    if set(args) != {"predicates"} or not isinstance(args["predicates"], list) or len(args["predicates"]) > 12:
        raise ValueError("predicates must be an array of at most 12 filters")
    rows = world["assignments"]
    fields = {k: type(v) for k, v in rows[0].items()}
    ops = {"eq": lambda a, b: a == b, "ne": lambda a, b: a != b, "lt": lambda a, b: a < b,
           "lte": lambda a, b: a <= b, "gt": lambda a, b: a > b, "gte": lambda a, b: a >= b}
    for pred in args["predicates"]:
        if not isinstance(pred, dict) or set(pred) != {"field", "op", "value"}:
            raise ValueError("Each predicate requires field, op and value")
        if pred["field"] not in fields or pred["op"] not in ops or type(pred["value"]) != fields[pred["field"]]:
            raise ValueError("Unknown field/operator or mismatched value type")
        if fields[pred["field"]] is bool and pred["op"] not in {"eq", "ne"}:
            raise ValueError("Boolean ordering is not supported")
        rows = [r for r in rows if ops[pred["op"]](r[pred["field"]], pred["value"])]
    return {**base, "assignments": rows, "coverage": "complete for these predicates in the shared fixture"}


def payload(mode, world, ontology):
    facts = {k: world[k] for k in ("revision", "source", "deployment", "assignments")}
    result = {"task": world["task"], "task_instruction": "Choose an eligible approver for this deployment using the pinned ontology.",
              "facts": facts, "coverage": "All relevant fixture facts are present; date comparisons use YYYY-MM-DD.",
              "ontology_version": ontology["version"],
              "finish_shape": {"type": "finish", "person": "name or null", "evidence_ids": ["supporting record IDs"], "ontology_version": "pinned version", "graph_revision": "integer", "rule_ids": ["all applied eligibility rule IDs"]}}
    if mode == "full":
        result["definitions"] = ontology["definitions"]
    elif mode == "inspect":
        result["catalog"] = {k: v["kind"] for k, v in ontology["definitions"].items()}
    else:
        result["definitions"] = closure(ontology)
    if interfaces(mode):
        result["interfaces"] = interfaces(mode)
        result["call_shape"] = {"type": "call", "name": "declared interface", "arguments": {"documented": "arguments"}}
        result["consumption_protocol"] = "Use the provided interface successfully at least once, then finish. One request per turn. These are JSON application requests, not CLI built-in tools."
    return result


def score(answer, world, ontology):
    if not isinstance(answer, dict):
        return False
    refs = answer.get("evidence_ids")
    rules = answer.get("rule_ids")
    return (set(answer) == FINAL_KEYS and answer.get("type") == "finish" and answer.get("person") == "Noah"
            and answer.get("ontology_version") == ontology["version"] and type(answer.get("graph_revision")) is int
            and answer["graph_revision"] == world["revision"] and isinstance(refs, list)
            and all(type(v) is str for v in refs) and set(refs) == {"a-noah", "d1"}
            and len(refs) == 2 and isinstance(rules, list) and all(type(v) is str for v in rules)
            and len(rules) == 6 and set(rules) == set(RULE_IDS))


def gate(answer, world, ontology):
    if not isinstance(answer, dict) or set(answer) != FINAL_KEYS or answer.get("type") != "finish":
        return {"admitted": False, "reason": "INVALID_PROPOSAL"}
    if answer.get("ontology_version") != ontology["version"] or type(answer.get("graph_revision")) is not int or answer["graph_revision"] != world["revision"]:
        return {"admitted": False, "reason": "VERSION_MISMATCH"}
    checked = assess_person(answer.get("person"), world)
    return {"admitted": checked["status"] == "ELIGIBLE", "reason": checked["status"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--experiment", default="all", choices=["all"] + [f"{i:02}" for i in range(1, 7)])
    args = parser.parse_args()
    world = json.loads((HERE / "facts.json").read_text())
    ontology = json.loads((HERE / "ontology.json").read_text())
    folders = sorted(p for p in HERE.glob("[0-9][0-9]-*") if p.is_dir() and (args.experiment == "all" or p.name.startswith(args.experiment + "-")))
    cfg_path = ROOT / "config/models.toml"
    cfg = tomllib.loads(cfg_path.read_text())["gemini"]
    executable = shutil.which(cfg["executable"])
    policy = ROOT / cfg["policy"]
    out = HERE / "results" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out.mkdir(parents=True)
    workspace = out / "empty-workspace"
    workspace.mkdir()
    version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=30).stdout.strip() if args.live and executable else None
    records = []
    for folder in folders:
        protocol = json.loads((folder / "protocol.json").read_text())
        base = payload(protocol["mode"], world, ontology)
        records.append((folder, protocol, base))
    h.save(out / "manifest.json", {"kind": "same_task_ontology_consumption", "cli_version": version, "live": args.live,
        "facts_sha256": h.digest(HERE / "facts.json"), "ontology_sha256": h.digest(HERE / "ontology.json"),
        "runner_sha256": h.digest(Path(__file__)), "helper_sha256": h.digest(HERE.parent / "gemini_experiments.py"),
        "config_sha256": h.digest(cfg_path), "policy_sha256": h.digest(policy), "max_calls_each": 5, "max_total_cli_calls": 5 * len(records),
        "task_hashes": {f.name: sha(b["task"]) for f, p, b in records}, "initial_fact_hashes": {f.name: sha(b["facts"]) for f, p, b in records},
        "protocol_hashes": {f.name: h.digest(f / "protocol.json") for f, p, b in records}, "appworld_runs": 0,
        "rules": RULE_IDS, "model_selection": "configured CLI routing; no override"})
    stopped = None
    summaries = []
    for folder, protocol, base in records:
        mode = protocol["mode"]
        rec = {"experiment": folder.name, "mode": mode, "status": "PREPARED_NOT_RUN", "initial_payload": base,
               "calls": [], "history": [], "passed": None, "successful_interface_calls": 0,
               "definition_names_exposed": sorted(base.get("definitions", {}))}
        if args.live and stopped:
            rec.update(status="NOT_RUN", reason=stopped)
        elif args.live:
            rec["status"] = "CALL_LIMIT"
            for step in range(5):
                prompt = "Solve the same fixed task using only the supplied facts, ontology and interfaces. Return one JSON object, no Markdown. Do not use CLI tools, read files, or change any external state.\n" + json.dumps({"context": base, "history": rec["history"]}, separators=(",", ":"))
                event = {"step": step, "submitted_prompt": prompt, "user_chars": len(prompt), "status": "IN_FLIGHT"}
                rec["calls"].append(event)
                h.save(out / (folder.name + ".json"), rec)
                if not executable:
                    stopped = "CLI_NOT_FOUND"
                    rec.update(status="CLI_UNAVAILABLE", reason=stopped)
                    break
                command = [executable, "--extensions", "none", "--allowed-mcp-server-names", "model-check-no-servers", "--policy", str(policy), "--output-format", "json", "--skip-trust", "--prompt", prompt]
                code, stdout, stderr = h.invoke(command, workspace, cfg["timeout_seconds"])
                event["exit_code"] = code
                event["stderr_sha256"] = hashlib.sha256(stderr.encode()).hexdigest()
                if code:
                    stopped = h.failure_category(code, stderr)
                    event.update(status="CLI_UNAVAILABLE", reason=stopped)
                    rec.update(status="CLI_UNAVAILABLE", reason=stopped)
                    break
                try:
                    env = json.loads(stdout)
                    event["cli_response"] = env
                    stats = env.get("stats", {})
                    if env.get("error") or not stats.get("models") or stats.get("tools", {}).get("totalCalls", 0):
                        raise ValueError("CLI error, missing identity, or unexpected CLI tool use")
                    msg = json.loads(env["response"])
                    if not isinstance(msg, dict):
                        raise ValueError("Response must be an object")
                    event.update(status="RECEIVED", parsed=msg)
                    if msg.get("type") == "finish":
                        rec["answer"] = msg
                        rec["answer_correct"] = score(msg, world, ontology)
                        rec["protocol_followed"] = not interfaces(mode) or rec["successful_interface_calls"] > 0
                        rec["passed"] = rec["answer_correct"] and rec["protocol_followed"]
                        rec["gate_before_change"] = gate(msg, world, ontology)
                        changed = copy.deepcopy(world)
                        changed["revision"] = 2
                        for row in changed["assignments"]:
                            if row["id"] == "a-noah": row["active"] = False
                        rec["gate_after_revocation"] = gate(msg, changed, ontology)
                        rec["status"] = "MEASURED"
                        break
                    try:
                        observation = execute(msg, mode, world, ontology)
                        rec["successful_interface_calls"] += 1
                        rec["definition_names_exposed"] = sorted(set(rec["definition_names_exposed"]) | set(observation.get("definitions", {})))
                    except ValueError as error:
                        observation = {"error": str(error)}
                    rec["history"].append({"model_request": msg, "runtime_result": observation})
                except (ValueError, KeyError, TypeError) as error:
                    event.update(status="RESPONSE_INVALID", reason=str(error), raw_stdout=stdout)
                    rec.update(status="RESPONSE_INVALID", reason=str(error))
                    break
                h.save(out / (folder.name + ".json"), rec)
        h.save(out / (folder.name + ".json"), rec)
        summaries.append({"experiment": folder.name, "status": rec["status"], "passed": rec["passed"], "calls": len(rec["calls"]), "interface_calls": rec["successful_interface_calls"]})
        h.save(out / "summary.json", {"complete": False, "experiments": summaries})
        print(folder.name, rec["status"], rec["passed"], flush=True)
    h.save(out / "summary.json", {"complete": True, "experiments": summaries, "appworld_runs": 0})
    print("Evidence:", out)
    return 0 if not args.live or all(r["passed"] is True for r in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())

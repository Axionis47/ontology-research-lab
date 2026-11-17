"""Same world, five Gemini interfaces; an orthogonal local action gate."""
import argparse
import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("lesson_helpers", HERE.parent / "gemini_experiments.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
MODES = ("full_text", "full_structured", "retrieved_fragment", "graph_queries", "typed_function")
DEFINITIONS = {
    "Person": "An identified human.",
    "Assignment": "A directed association from person to service, qualified by role, environment and validity.",
    "Deployment": "A deployment of a service with an author.",
    "eligible": "A matching active DeploymentApprover assignment with validFrom <= at < validUntil, covering the service and environment. The person must differ from the deployment author.",
    "unknown": "Evidence is insufficient; absence from an incomplete fragment is not proof of absence."
}
FINAL = {"type": "finish", "person": "person name or null", "evidence_ids": ["supporting record IDs"], "revision": "integer"}


def reasons(row, world):
    task = world["task"]
    return [name for name, passes in (
        ("service", row["service"] == task["service"]),
        ("environment", row["environment"] == task["environment"]),
        ("role", row["role"] == "DeploymentApprover"),
        ("active", row["active"] is True),
        ("validity", row["validFrom"] <= task["at"] < row["validUntil"]),
        ("separation_of_duties", row["person"] != world["deployment"]["author"])
    ) if not passes]


def eligible(world):
    return [row for row in world["assignments"] if not reasons(row, world)]


def tools(mode):
    if mode == "graph_queries":
        return {"query_assignments": {"arguments": {"service": "string"}, "returns": "All assignment entities for a service, with source and revision; does not apply eligibility rules."},
                "read_deployment": {"arguments": {"deployment_id": "string"}, "returns": "Deployment entity including author, source and revision."}}
    if mode == "typed_function":
        return {"find_eligible_approvers": {"arguments": {"service": "string", "environment": "string", "deployment_id": "string", "at": "YYYY-MM-DD"},
                                           "returns": "Candidates satisfying all supplied eligibility rules, exclusions with reasons, source, revision and supporting record IDs."}}
    return {}


def execute(call, mode, world):
    if set(call) != {"type", "name", "arguments"} or call["type"] != "call":
        raise ValueError("Call requires exactly type, name and arguments")
    name, args = call["name"], call["arguments"]
    if name not in tools(mode) or not isinstance(args, dict):
        raise ValueError("Undeclared tool or invalid arguments")
    schema = tools(mode)[name]["arguments"]
    if set(args) != set(schema) or any(type(v) is not str for v in args.values()):
        raise ValueError("Argument keys/types do not match contract")
    base = {"revision": world["revision"], "source": world["source"]}
    if name == "query_assignments":
        return {**base, "coverage": "complete for requested service in this fixture", "assignments": [r for r in world["assignments"] if r["service"] == args["service"]]}
    if name == "read_deployment":
        return {**base, "deployment": world["deployment"] if args["deployment_id"] == world["deployment"]["id"] else None}
    if args != world["task"]:
        raise ValueError("This small function only supports the bound task; other parameters are not silently ignored")
    candidates = [{"person": r["person"], "evidence_ids": [r["id"], world["deployment"]["id"]]} for r in eligible(world)]
    exclusions = [{"person": r["person"], "failed": reasons(r, world)} for r in world["assignments"] if r["service"] == args["service"] and reasons(r, world)]
    return {**base, "coverage": "complete for bound task", "candidates": candidates, "exclusions": exclusions}


def base_payload(mode, world):
    payload = {"task": world["task"], "definitions": DEFINITIONS, "final_response_shape": FINAL}
    if mode == "full_text":
        payload["observations"] = ["Revision: " + str(world["revision"]), "Source: " + world["source"], "Deployment: " + json.dumps(world["deployment"])] + ["Assignment " + r["id"] + ": " + "; ".join(f"{k} = {json.dumps(v)}" for k, v in r.items()) for r in world["assignments"]]
        payload["coverage"] = "complete fixture"
    elif mode in {"full_structured", "retrieved_fragment"}:
        rows = world["assignments"] if mode == "full_structured" else [r for r in world["assignments"] if r["service"] == world["task"]["service"]]
        payload["observations"] = {"revision": world["revision"], "source": world["source"], "deployment": world["deployment"], "assignments": rows, "coverage": "complete for target service and deployment"}
    else:
        payload["tools"] = tools(mode)
        payload["call_shape"] = {"type": "call", "name": "declared tool name", "arguments": {"documented": "arguments"}}
        payload["instruction"] = "Request evidence with one call at a time before finishing. These are application-protocol JSON messages, not Gemini CLI built-in tools."
    return payload


def action_probe(proposal, original):
    changed = copy.deepcopy(original)
    for row in changed["assignments"]:
        if row["id"] == changed["intervening_change"]["assignment_id"]:
            row["active"] = False
    changed["revision"] = 2
    well_formed = (isinstance(proposal, dict) and set(proposal) == set(FINAL)
                   and proposal.get("type") == "finish" and type(proposal.get("revision")) is int
                   and (proposal.get("person") is None or type(proposal.get("person")) is str)
                   and isinstance(proposal.get("evidence_ids"), list))
    person = proposal.get("person") if isinstance(proposal, dict) else None
    can_select = well_formed and person is not None
    latest_eligible = {r["person"] for r in eligible(changed)}
    allowed = can_select and proposal["revision"] == changed["revision"] and person in latest_eligible
    return {"event": "Noah assignment revoked after selection, before dispatch", "current_revision": 2,
            "unguarded_fixture": {"selected_person": person if can_select else None, "constraint_violation": can_select and person not in latest_eligible},
            "gated_fixture": {"selected_person": person if allowed else None, "admitted": allowed,
                              "reason": "STALE_OR_INELIGIBLE" if can_select and not allowed else "NO_ACTION"},
            "current_eligible": sorted(latest_eligible), "kind": "deterministic local effect probe, not another model judgment"}


def prompt_for(payload, history):
    return "Use only supplied evidence and definitions. Choose an eligible approver for the task, or null if no candidate is supported by complete evidence. Return only one JSON object. Do not use CLI tools or access files.\n" + json.dumps({"task_context": payload, "interaction_history": history}, separators=(",", ":"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    world_path = HERE / "world.json"
    world = json.loads(world_path.read_text())
    config = tomllib.loads((ROOT / "config/models.toml").read_text())["gemini"]
    executable = shutil.which(config["executable"])
    policy = ROOT / config["policy"]
    output = HERE / "results" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output.mkdir(parents=True)
    workspace = output / "empty-workspace"
    workspace.mkdir()
    cli_version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=30).stdout.strip() if args.live and executable else None
    helpers.save(output / "manifest.json", {"kind": "synthetic_interface_comparison", "world_sha256": helpers.digest(world_path), "runner_sha256": helpers.digest(Path(__file__)),
        "helper_sha256": helpers.digest(HERE.parent / "gemini_experiments.py"), "policy_sha256": helpers.digest(policy), "config_sha256": helpers.digest(ROOT / "config/models.toml"),
        "cli_version": cli_version, "model": "configured CLI routing, no override", "max_cli_calls": 14, "max_calls_per_mode": {m: 4 if m in {"graph_queries", "typed_function"} else 2 for m in MODES}, "appworld_runs": 0})
    results = []
    unavailable = None
    for mode in MODES:
        payload = base_payload(mode, world)
        receipt = {"mode": mode, "status": "PREPARED_NOT_RUN", "initial_payload": payload, "calls": [], "history": [], "correct_at_observation": None}
        if args.live and unavailable:
            receipt.update(status="NOT_RUN", reason=unavailable)
        elif args.live:
            budget = 4 if mode in {"graph_queries", "typed_function"} else 2
            receipt["status"] = "CALL_LIMIT"
            for step in range(budget):
                prompt = prompt_for(payload, receipt["history"])
                event = {"step": step, "submitted_prompt": prompt, "user_prompt_chars": len(prompt), "status": "IN_FLIGHT"}
                receipt["calls"].append(event)
                helpers.save(output / f"{mode}.json", receipt)
                if not executable:
                    unavailable = "GEMINI_CLI_NOT_FOUND"
                    receipt.update(status="CLI_UNAVAILABLE", reason=unavailable)
                    break
                command = [executable, "--extensions", "none", "--allowed-mcp-server-names", "model-check-no-servers", "--policy", str(policy), "--output-format", "json", "--skip-trust", "--prompt", prompt]
                code, stdout, stderr = helpers.invoke(command, workspace, config["timeout_seconds"])
                event["exit_code"] = code
                if code:
                    unavailable = helpers.failure_category(code, stderr)
                    event.update(status="CLI_UNAVAILABLE", reason=unavailable)
                    receipt.update(status="CLI_UNAVAILABLE", reason=unavailable)
                    break
                try:
                    envelope = json.loads(stdout)
                    event["cli_response"] = envelope
                    if envelope.get("error"):
                        raise ValueError("CLI error envelope")
                    stats = envelope.get("stats", {})
                    if not stats.get("models") or stats.get("tools", {}).get("totalCalls", 0):
                        raise ValueError("Missing model identity or unexpected CLI tool call")
                    message = json.loads(envelope["response"])
                    if not isinstance(message, dict):
                        raise ValueError("Expected JSON object")
                    event.update(status="RECEIVED", parsed=message)
                    if message.get("type") == "finish":
                        receipt["answer"] = message
                        receipt["correct_at_observation"] = (set(message) == set(FINAL) and message.get("person") == "Noah"
                            and type(message.get("revision")) is int and message["revision"] == 1
                            and isinstance(message.get("evidence_ids"), list) and set(message["evidence_ids"]) == {"a-noah", "d1"})
                        receipt["action_probe"] = action_probe(message, world)
                        receipt["status"] = "MEASURED"
                        break
                    try:
                        observation = execute(message, mode, world)
                    except ValueError as error:
                        observation = {"error": str(error)}
                    receipt["history"].append({"model_proposal": message, "runtime_observation": observation})
                except (ValueError, TypeError, KeyError) as error:
                    event.update(status="RESPONSE_INVALID", reason=str(error), raw_stdout=stdout)
                    receipt.update(status="RESPONSE_INVALID", reason=str(error))
                    break
                helpers.save(output / f"{mode}.json", receipt)
        helpers.save(output / f"{mode}.json", receipt)
        results.append({"mode": mode, "status": receipt["status"], "correct_at_observation": receipt["correct_at_observation"], "cli_calls": len(receipt["calls"]),
                        "submitted_user_chars": sum(c["user_prompt_chars"] for c in receipt["calls"])})
        helpers.save(output / "summary.json", {"complete": False, "results": results})
        print(mode, receipt["status"], receipt["correct_at_observation"], flush=True)
    helpers.save(output / "summary.json", {"complete": True, "results": results, "kind": "synthetic_comparison", "appworld_runs": 0})
    print("Evidence:", output)
    return 0 if not args.live or all(r["correct_at_observation"] is True for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

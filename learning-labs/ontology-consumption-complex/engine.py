"""Explicit reference computation for a synthetic approval-panel ontology."""
import copy
import hashlib
import itertools
import json

RULE_IDS = [f"R{i}" for i in range(1, 11)]
FINAL_KEYS = {"type", "panel", "proof_ids", "rule_ids", "ontology_version", "graph_revision"}


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def closure(ontology, roots=("eligibility",)):
    needed = set(roots)
    while True:
        more = needed | {d for name in needed for d in ontology["definitions"][name].get("requires", [])}
        if more == needed:
            return {name: ontology["definitions"][name] for name in sorted(needed)}
        needed = more


def index(world):
    return {r["id"]: r for r in world["records"]}


def current(row, world):
    return row.get("active") is True and row.get("validFrom", "9999") <= world["task"]["at"] < row.get("validUntil", "")


def context(world):
    records = index(world)
    deployment = records[world["task"]["deployment_id"]]
    service = records[deployment["service"]]
    project = records[service["project"]]
    organization = records[project["organization"]]
    return records, deployment, service, project, organization


def covers(scope, world):
    _, _, service, project, organization = context(world)
    return scope in {service["id"], project["id"], organization["id"]}


def assess_person(person, role, world):
    records, deployment, service, _, _ = context(world)
    if person not in records or records[person]["type"] != "Person":
        return {"person": person, "role": role, "status": "UNKNOWN", "reason": "Unknown person"}
    memberships = [r for r in world["records"] if r["type"] == "Membership" and r["person"] == person and r["home"] is True and current(r, world)]
    certs = [r for r in world["records"] if r["type"] == "Certificate" and r["person"] == person and current(r, world)
             and r["purpose"] == "deployment-approval" and r["region"] == service["region"] and r["environment"] == deployment["environment"]]
    denies = [r for r in world["records"] if r["type"] == "Deny" and r["person"] == person and current(r, world) and covers(r["scope"], world)]
    paths = []
    diagnostics = []
    for grant in [r for r in world["records"] if r["type"] == "Grant"]:
        candidates = [None] if grant["holder"] == person else []
        candidates += [r for r in world["records"] if r["type"] == "Delegation" and r["recipient"] == person and r["grant"] == grant["id"]]
        for delegation in candidates:
            conditions = {
                "R1": covers(grant["scope"], world) and (delegation is None or covers(delegation["scope"], world)),
                "R2": current(grant, world) and (delegation is None or current(delegation, world)),
                "R3": grant["role"] == role,
                "R4": deployment["risk"] <= grant["maxRisk"] and (delegation is None or deployment["risk"] <= delegation["maxRisk"]),
                "R5": delegation is None or (grant["delegable"] is True and delegation["issuer"] == grant["holder"])
            }
            ids = [grant["id"]] + ([delegation["id"]] if delegation else [])
            failed = [rule for rule, valid in conditions.items() if not valid]
            diagnostics.append({"path": ids, "violated_rules": failed})
            if not failed:
                paths.append(ids)
    failed = []
    if not paths: failed.append("R5")
    if not certs: failed.append("R6")
    if person == deployment["author"]: failed.append("R7")
    if denies: failed.append("R8")
    if len(memberships) != 1: failed.append("R9")
    proof = []
    team = memberships[0]["team"] if len(memberships) == 1 else None
    if not failed:
        proof = [person, memberships[0]["id"], team, sorted(certs, key=lambda r: r["id"])[0]["id"], *sorted(paths)[0]]
    return {"person": person, "role": role, "status": "ELIGIBLE" if not failed else "INELIGIBLE", "violated_rules": failed,
            "authority_paths": diagnostics, "deny_ids": [r["id"] for r in denies], "home_team": team, "proof_ids": proof}


def check_panel(panel, world):
    if not isinstance(panel, dict) or set(panel) != {"ops", "security"} or any(type(v) is not str for v in panel.values()):
        return {"status": "INVALID", "violated_rules": ["R10"], "proof_ids": []}
    ops = assess_person(panel["ops"], "OpsApprover", world)
    security = assess_person(panel["security"], "SecurityApprover", world)
    failed = []
    if ops["status"] != "ELIGIBLE" or security["status"] != "ELIGIBLE": failed.append("INDIVIDUAL_ELIGIBILITY")
    if panel["ops"] == panel["security"]: failed.append("R10")
    if ops.get("home_team") is not None and ops.get("home_team") == security.get("home_team"): failed.append("R9")
    _, deployment, service, project, organization = context(world)
    proof = sorted(set([deployment["id"], service["id"], project["id"], organization["id"], *ops.get("proof_ids", []), *security.get("proof_ids", [])])) if not failed else []
    return {"panel": panel, "status": "VALID" if not failed else "INVALID", "violated_rules": failed,
            "individuals": [ops, security], "proof_ids": proof}


def valid_panels(world):
    people = sorted(r["id"] for r in world["records"] if r["type"] == "Person")
    ops = [p for p in people if assess_person(p, "OpsApprover", world)["status"] == "ELIGIBLE"]
    security = [p for p in people if assess_person(p, "SecurityApprover", world)["status"] == "ELIGIBLE"]
    return [checked for a, b in itertools.product(ops, security) if (checked := check_panel({"ops": a, "security": b}, world))["status"] == "VALID"]


def interfaces(mode):
    return {
        "inspect": {"inspect_schema": {"arguments": {"names": "array of catalog names"}, "returns": "Definitions and dependency closure. Request eligibility to obtain the complete approval rules."}},
        "query": {"query_records": {"arguments": {"type": "record type", "where": "object of exact field/value matches; {} means all of that type"}, "returns": "Matching records only, no automatic eligibility computation."},
                  "traverse": {"arguments": {"ids": "array of source record IDs", "relation": "reference-valued field name", "direction": "out or in"}, "returns": "Linked records with paths. Joins require caller-selected relations."}},
        "function": {"find_valid_panels": {"arguments": {"deployment_id": "string", "at": "YYYY-MM-DD"}, "returns": "All valid Ops/Security pairs under the pinned rules, with complete proof IDs; lexicographically ordered."}},
        "check": {"check_panels": {"arguments": {"panels": "1 to 12 proposed {ops: person ID, security: person ID} objects"}, "returns": "Validity, individual rule violations, team conflicts and proof IDs for those panels only. Does not search for other panels."}}
    }.get(mode, {})


def execute(call, mode, world, ontology):
    if not isinstance(call, dict) or set(call) != {"type", "name", "arguments"} or call["type"] != "call":
        raise ValueError("Call requires exactly type, name and arguments")
    name, args = call["name"], call["arguments"]
    if name not in interfaces(mode) or not isinstance(args, dict):
        raise ValueError("Unknown interface or arguments")
    base = {"ontology_version": ontology["version"], "graph_revision": world["revision"]}
    if name == "inspect_schema":
        if set(args) != {"names"} or not isinstance(args["names"], list) or not args["names"] or any(type(n) is not str or n not in ontology["definitions"] for n in args["names"]):
            raise ValueError("names must contain known catalog names")
        return {**base, "definitions": closure(ontology, args["names"])}
    if name == "find_valid_panels":
        if args != {k: world["task"][k] for k in ("deployment_id", "at")}:
            raise ValueError("This lesson function supports the exact bound deployment and date")
        return {**base, "rule_ids": RULE_IDS, "panels": valid_panels(world)}
    if name == "check_panels":
        if set(args) != {"panels"} or not isinstance(args["panels"], list) or not 1 <= len(args["panels"]) <= 12:
            raise ValueError("Provide 1 to 12 panel objects")
        return {**base, "rule_ids": RULE_IDS, "checks": [check_panel(panel, world) for panel in args["panels"]]}
    records = index(world)
    if name == "query_records":
        if set(args) != {"type", "where"} or type(args["type"]) is not str or not isinstance(args["where"], dict):
            raise ValueError("Query requires type and where object")
        rows = [r for r in world["records"] if r["type"] == args["type"]]
        if not rows: raise ValueError("Unknown or unavailable record type")
        schema = {k: type(v) for r in rows for k, v in r.items()}
        if any(k not in schema or type(v) != schema[k] for k, v in args["where"].items()):
            raise ValueError("Unknown query property or incorrect value type")
        return {**base, "records": [r for r in rows if all(r.get(k) == v for k, v in args["where"].items())]}
    if set(args) != {"ids", "relation", "direction"} or not isinstance(args["ids"], list) or not args["ids"] or any(type(i) is not str or i not in records for i in args["ids"]) or type(args["relation"]) is not str or args["direction"] not in {"out", "in"}:
        raise ValueError("Invalid traversal contract")
    relation = args["relation"]
    if not any(type(r.get(relation)) is str and r[relation] in records for r in world["records"]):
        raise ValueError("Not a known reference-valued relationship")
    paths = []
    for r in world["records"]:
        target = r.get(relation)
        if type(target) is not str or target not in records: continue
        if (args["direction"] == "out" and r["id"] in args["ids"]) or (args["direction"] == "in" and target in args["ids"]):
            paths.append({"from": r["id"], "relation": relation, "to": target})
    ids = {p["to"] if args["direction"] == "out" else p["from"] for p in paths}
    return {**base, "paths": paths, "records": [records[i] for i in sorted(ids)]}


def payload(mode, world, ontology):
    result = {"task": world["task"], "task_instruction": "Select the required two-person approval panel using the pinned rules.",
              "facts": {k: world[k] for k in ("revision", "source", "coverage", "records")}, "ontology_version": ontology["version"],
              "finish_shape": {"type": "finish", "panel": {"ops": "person ID", "security": "person ID"}, "proof_ids": ["complete proof record IDs"], "rule_ids": ["all applied rule IDs"], "ontology_version": "pinned version", "graph_revision": "integer"},
              "evidence_requirement": "For a selected panel cite the Deployment, Service, its Project and Organization. For EACH selected person cite their Person, current home Membership, Team, valid Certificate, source Grant, and Delegation if authority is indirect. Cite R1 through R10. Additional known record IDs are allowed. If no valid pair exists return panel=null. Do not invent record IDs."}
    if mode == "full": result["definitions"] = ontology["definitions"]
    elif mode == "inspect": result["catalog"] = {k: v["kind"] for k, v in ontology["definitions"].items()}
    else: result["definitions"] = closure(ontology)
    if interfaces(mode):
        result["interfaces"] = interfaces(mode)
        result["call_shape"] = {"type": "call", "name": "interface name", "arguments": {"documented": "arguments"}}
        result["consumption_protocol"] = "Successfully use the provided interface before finishing. Inspection must retrieve eligibility rules. One application request per turn, not a CLI built-in tool call."
    return result


def score_details(answer, world, ontology):
    valid = valid_panels(world)
    expected = valid[0]["panel"] if valid else None
    shape = isinstance(answer, dict) and set(answer) == FINAL_KEYS and answer.get("type") == "finish"
    selected = shape and answer.get("panel") == expected
    refs = answer.get("proof_ids") if isinstance(answer, dict) else None
    proof = shape and isinstance(refs, list) and all(type(r) is str and r in index(world) for r in refs) and len(set(refs)) == len(refs) and (not valid or set(valid[0]["proof_ids"]) <= set(refs))
    rules = answer.get("rule_ids") if isinstance(answer, dict) else None
    versions = shape and answer.get("ontology_version") == ontology["version"] and type(answer.get("graph_revision")) is int and answer["graph_revision"] == world["revision"]
    rule_coverage = isinstance(rules, list) and all(type(r) is str for r in rules) and len(rules) == 10 and set(rules) == set(RULE_IDS)
    return {"shape": shape, "panel_correct": selected, "proof_complete": proof, "versions_correct": versions,
            "rule_coverage": rule_coverage, "passed": bool(shape and selected and proof and versions and rule_coverage)}


def score(answer, world, ontology):
    return score_details(answer, world, ontology)["passed"]


def gate(answer, world, ontology):
    if not isinstance(answer, dict) or set(answer) != FINAL_KEYS or answer.get("type") != "finish":
        return {"admitted": False, "reason": "INVALID_PROPOSAL"}
    if answer.get("ontology_version") != ontology["version"] or type(answer.get("graph_revision")) is not int or answer["graph_revision"] != world["revision"]:
        return {"admitted": False, "reason": "VERSION_MISMATCH"}
    checked = check_panel(answer.get("panel"), world)
    return {"admitted": checked["status"] == "VALID", "reason": checked["status"]}


def revoked(world):
    changed = copy.deepcopy(world)
    changed["revision"] += 1
    for row in changed["records"]:
        if row["id"] == "del-Vera": row["active"] = False
    return changed

from pathlib import Path
import json
import hashlib
import sys
HERE = Path(__file__).resolve().parent
def read(name):
    return json.loads((HERE / name).read_text())
def finish(observations, checks):
    result = {"kind": "synthetic_component_experiment", "engine": "explicit_python_not_standards_engine", "inputs": {p.name: json.loads(p.read_text()) for p in sorted(HERE.glob("*.json")) if p.name != "result.json"}, "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "observations": observations, "checks": checks, "passed": all(checks.values())}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
data=read("input.json")
projects=sorted(o for s,p,o in data["triples"] if s=="Maya" and p=="belongsTo")
services=sorted(s for s,p,o in data["triples"] if p=="belongsTo" and o in projects and s in data["services"])
def approval(assignments):
    required={"person":"Maya","service":"LoginService","role":"DeploymentApprover","environment":"Production"}
    supporting=[a["id"] for a in assignments if all(a.get(k)==v for k,v in required.items()) and a.get("validFrom","9999")<=data["at"]<a.get("validUntil","")]
    return {"status":"SUPPORTED" if supporting else "UNKNOWN","supporting_assignments":supporting}
results={name:approval(rows) for name,rows in data["scenarios"].items()}
finish({"join_step_1_projects":projects,"join_step_2_services":services,"approval":results},{"path_exists":services==["LoginService"],"path_is_not_approval":results["membership_only"]["status"]=="UNKNOWN","matching_assignment_supports":results["matching_assignment"]["status"]=="SUPPORTED","wrong_environment_does_not_support":results["wrong_environment"]["status"]=="UNKNOWN"})

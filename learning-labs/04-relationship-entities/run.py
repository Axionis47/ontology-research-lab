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
def qualified(environment, at):
    return sorted(a["person"] for a in data["assignments"] if all(k in a for k in ("person","service","role","environment","validFrom","validUntil")) and a["service"]=="LoginService" and a["role"]=="Maintainer" and a["environment"]==environment and a["validFrom"]<=at<a["validUntil"])
staging=qualified("Staging",data["at"])
production=qualified("Production",data["at"])
expired=qualified("Staging","2026-11-20")
finish({"staging":staging,"production":production,"at_expiry":expired,"empty_result_meaning":"no supported assignment in this fixture"},{"staging_qualified":staging==["Maya"],"production_not_inferred":production==[],"expiry_excluded":expired==[]})

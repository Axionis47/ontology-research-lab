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
rows=[]
for c in data["candidates"]:
    s,p,o=c["triple"]
    structure=p=="maintains" and data["types"].get(s)=="Person" and data["types"].get(o)=="Service"
    receipt=data["receipts"].get(c.get("source"))
    evidence=bool(receipt and receipt["triple"]==c["triple"])
    rows.append({"id":c["id"],"structure_valid":structure,"source_matches":evidence,"admitted":structure and evidence})
finish(rows,{"A_structure_without_evidence":rows[0]["structure_valid"] and not rows[0]["admitted"],"B_reversed_relation_rejected":not rows[1]["structure_valid"],"C_traceable_claim_admitted":rows[2]["admitted"]})

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
triples = [tuple(t) for t in read("input.json")["triples"]]
graph = set(triples)
def objects(subject, predicate):
    return sorted(o for s,p,o in graph if (s,p)==(subject,predicate))
a=objects("Maya","maintains")
b=objects("LoginService","belongsTo")
c=objects("LoginService","maintains")
finish({"maya_maintains":a,"service_project":b,"reverse_lookup":c,"unique_triples":len(graph)}, {"lookup_service":a==["LoginService"],"lookup_project":b==["Atlas"],"direction_is_not_reversed":c==[],"duplicate_has_no_new_meaning":len(graph | {triples[0]})==len(graph)})

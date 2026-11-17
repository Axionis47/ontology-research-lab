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
ontology=read("ontology.json")
facts=read("facts.json")
observation=read("new-observation.json")
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
before_ontology=digest(ontology)
before_graph=digest(facts)
after=facts+[observation]
unknown_type_admitted="Robot" in ontology["classes"]
finish({"ontology_before":before_ontology,"ontology_after":digest(ontology),"graph_before":before_graph,"graph_after":digest(after),"added":observation,"unknown_Robot_type_admitted":unknown_type_admitted},{"definition_unchanged":before_ontology==digest(ontology),"graph_changed":before_graph!=digest(after),"new_instance_uses_existing_type":observation[2] in ontology["classes"],"unknown_type_not_silently_added":not unknown_type_admitted})

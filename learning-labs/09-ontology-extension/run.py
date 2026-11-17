"""Custom schema migration fixture, not a general OWL compatibility checker."""
import copy
import hashlib
import json
from pathlib import Path


def compatible(old, new):
    return (set(old["types"]) <= set(new["types"]) and
            all(new["relations"].get(name) == meaning for name, meaning in old["relations"].items()))


def scoped_match(row, query):
    if row["service"] != query["service"]:
        return "FALSE"
    if row["environment"] is None or row["validUntil"] is None:
        return "UNKNOWN"
    return "TRUE" if row["environment"] == query["environment"] and row["validUntil"] >= query["date"] else "FALSE"


def main():
    path = Path(__file__).with_name("input.json")
    data = json.loads(path.read_text())
    legacy = data["legacy_fact"]
    migrated = {"id": "migration-record-1", "person": legacy["subject"], "service": legacy["object"],
                "environment": None, "validUntil": None, "derivedFrom": legacy["source"],
                "status": "incomplete_migration_record"}
    bad_version = copy.deepcopy(data["v2"])
    bad_version["relations"]["maintains"] = "The person may deploy to production."
    legacy_query = [legacy["subject"]] if legacy["object"] == data["query"]["service"] else []
    results = {migrated["person"]: scoped_match(migrated, data["query"]),
               data["new_observation"]["person"]: scoped_match(data["new_observation"], data["query"])}
    checks = {
        "old_definitions_preserved": compatible(data["v1"], data["v2"]),
        "silent_meaning_change_rejected": not compatible(data["v1"], bad_version),
        "legacy_query_preserved": legacy_query == ["Maya"],
        "unknown_environment_not_invented": migrated["environment"] is None,
        "unknown_expiry_not_invented": migrated["validUntil"] is None,
        "legacy_scope_remains_unknown": results["Maya"] == "UNKNOWN",
        "new_supported_scope_matches": results["Noah"] == "TRUE",
        "original_evidence_preserved": legacy["source"] == migrated["derivedFrom"],
    }
    print(json.dumps({"experiment": "09", "kind": "synthetic_deterministic_fixture", "candidate_author": "assistant_teaching_fixture",
                      "model_calls": 0, "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "original_fact": legacy, "migrated_record": migrated, "scoped_query_results": results,
                      "checks": checks, "passed": all(checks.values())}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

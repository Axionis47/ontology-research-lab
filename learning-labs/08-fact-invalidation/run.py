"""Synthetic dependency invalidation demonstration. No model or external writes."""
import hashlib
import json
from pathlib import Path


def affected_by(changed, dependencies):
    affected = set(changed)
    while True:
        expanded = affected | {node for node, parents in dependencies.items() if affected.intersection(parents)}
        if expanded == affected:
            return affected
        affected = expanded


def main():
    path = Path(__file__).with_name("input.json")
    data = json.loads(path.read_text())
    original = data["observations"]["assignment17"].copy()
    pinned_revision = original["revision"]
    before_permitted = original["active"] and original["revision"] == pinned_revision
    changed = data["change"]
    data["observations"][changed["entity"]].update({k: v for k, v in changed.items() if k != "entity"})
    stale = affected_by({changed["entity"]}, data["dependencies"])
    current = data["observations"]["assignment17"]
    stale_plan_permitted = current["revision"] == pinned_revision and "plan3" not in stale
    recomputed_permitted = current["active"]
    checks = {
        "original_plan_permitted": before_permitted,
        "direct_decision_invalidated": "decision8" in stale,
        "transitive_plan_invalidated": "plan3" in stale,
        "unrelated_display_preserved": "display_name" not in stale,
        "stale_plan_rejected": not stale_plan_permitted,
        "fresh_recomputation_denies_revoked_assignment": not recomputed_permitted,
        "ontology_did_not_change": data["ontology_version"] == "1",
    }
    print(json.dumps({"experiment": "08", "kind": "synthetic_deterministic_fixture", "model_calls": 0,
                      "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "before": original, "after": current, "invalidated": sorted(stale),
                      "checks": checks, "passed": all(checks.values())}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

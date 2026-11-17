"""Synthetic semantic-change gate. Never promotes a real project package."""
import hashlib
import json
from pathlib import Path


def permits(package, case):
    policy = package["policy"]
    if policy == "project_or_service":
        return case["approval"] in {"project", "service"}
    if policy == "service_only":
        return case["approval"] == "service"
    return False


def evaluate(package, cases):
    return [{"case": case["name"], "actual": permits(package, case), "expected": case["expected"],
             "passed": permits(package, case) == case["expected"]} for case in cases]


def gate(parent_results, candidate_results, candidate, authority):
    improved = sum(row["passed"] for row in candidate_results) > sum(row["passed"] for row in parent_results)
    return candidate["policy"] == authority["required_policy"] and improved and all(row["passed"] for row in candidate_results)


def main():
    path = Path(__file__).with_name("input.json")
    data = json.loads(path.read_text())
    packages, cases = data["packages"], data["cases"]
    active_episode = {"id": "episode-already-running", "pinned_package": "v1"}
    retained = "v1"
    results = {name: evaluate(package, cases) for name, package in packages.items()}
    decisions = {name: gate(results["v1"], results[name], packages[name], data["authoritative_rule_fixture"]) for name in ("v2", "bad")}
    if decisions["v2"]:
        retained = "v2"
    new_episode = {"id": "new-episode", "pinned_package": retained}
    checks = {
        "same_evidence_changes_answer_under_new_meaning": permits(packages["v1"], cases[0]) != permits(packages["v2"], cases[0]),
        "parent_failure_exposed": not results["v1"][0]["passed"],
        "supported_candidate_accepted_in_fixture": decisions["v2"],
        "deny_everything_candidate_rejected": not decisions["bad"],
        "negative_candidate_has_regression": not results["bad"][1]["passed"],
        "active_episode_stays_pinned": active_episode["pinned_package"] == "v1",
        "new_episode_uses_new_version": new_episode["pinned_package"] == "v2",
    }
    print(json.dumps({"experiment": "10", "kind": "synthetic_deterministic_fixture", "candidate_author": "assistant_teaching_fixture",
                      "model_calls": 0, "native_appworld_runs": 0, "gemini_judgment": "NOT_RUN", "gemini_proposal": "NOT_RUN",
                      "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "results": results, "candidate_decisions": decisions,
                      "active_episode": active_episode, "new_episode": new_episode, "checks": checks, "passed": all(checks.values())}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

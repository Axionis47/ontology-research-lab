"""Offline, evidence-based comparison of one trusted helper repair with its parent."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3

from jsonschema import ValidationError

from .completion import CHECKER_VERSION, CHECK_IDS, evaluate, fingerprint, validate_contract
from .loop import Config
from .store import IntegrityError, RunStore, timestamp

ROOT = Path(__file__).resolve().parents[1]
VERSION = "repair-scoring-component/1"
VARIANTS = ("parent", "candidate")
INCOMPLETE = {"PARTIAL_CAPTURE", "NO_TERMINAL_RECEIPT", "UNPAIRED_INVOCATION", "INVALID_EPISODE_END_COUNT", "UNINDEXED_CAPTURE"}


class InvalidComparison(ValueError):
    pass


class MissingEvidence(ValueError):
    pass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise InvalidComparison(message)


def local_path(root, name):
    require(isinstance(name, str) and not Path(name).is_absolute(), "Artifact path must be relative")
    path = root / name
    require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), "Artifact path escaped comparison")
    return path


def load_json(path):
    return json.loads(Path(path).read_text())


def load_pinned(root, reference):
    require(set(reference) == {"path", "sha256"}, "Invalid pinned file reference")
    path = local_path(root, reference["path"])
    require(path.is_file() and digest(path) == reference["sha256"], "Pinned input missing or changed: " + reference["path"])
    return path


def protected_sources():
    paths = sorted((ROOT / "react_runtime").glob("*.py")) + [ROOT / "scripts/demo_repair_scoring.py"]
    return {str(p.relative_to(ROOT)): digest(p) for p in paths}


def validate_manifest(root, manifest):
    require(set(manifest) == {"version", "created_at", "synthetic", "target", "cases", "implementations", "config", "protected_sources", "checker_version"},
            "Invalid comparison manifest fields")
    require(manifest["version"] == VERSION and manifest["synthetic"] is True, "Unsupported comparison version or environment")
    require(manifest["checker_version"] == CHECKER_VERSION, "Checker version changed")
    require(manifest["protected_sources"] == protected_sources(), "Protected scorer/checker/runtime source changed")
    require(manifest["config"] == asdict(Config(**manifest["config"])), "Incomplete runtime configuration")
    Config(**manifest["config"]).validate()
    require(set(manifest["implementations"]) == set(VARIANTS), "Both implementation identities are required")
    for ref in manifest["implementations"].values():
        load_pinned(root, ref)
    cases = manifest["cases"]
    require(isinstance(cases, list) and len(cases) == 4, "This prototype requires four scheduled cases")
    ids = [c["id"] for c in cases]
    require(len(set(ids)) == 4 and all(isinstance(k, str) and k for k in ids), "Duplicate or invalid case ID")
    require(sorted(c["role"] for c in cases) == ["preservation", "preservation", "target", "variation"], "Invalid case roles")
    target = manifest["target"]
    require(set(target) == {"case_id", "requirement_id"} and target["requirement_id"] in CHECK_IDS, "Unknown targeted requirement")
    require(target["case_id"] == next(c["id"] for c in cases if c["role"] == "target"), "Target case binding differs")
    inputs = {}
    for case in cases:
        require(set(case) == {"id", "role", "input"}, "Invalid case fields")
        data = load_json(load_pinned(root, case["input"]))
        require(set(data) == {"contract", "before"}, "Invalid case input")
        validate_contract(data["contract"])
        inputs[case["id"]] = data
    return inputs


def read_run(root, manifest, case, variant, entry):
    directory = local_path(root, entry["run"])
    if not (directory / "ledger.sqlite").is_file():
        raise MissingEvidence("Missing run ledger")
    store = RunStore.open_existing(directory)
    try:
        audit = store.audit()
        severe = [p for p in audit["problems"] if p["error"] not in INCOMPLETE]
        require(not severe, "Trace integrity failed: " + str(severe[:2]))
        if not audit["complete"]:
            raise MissingEvidence("Trace capture is incomplete")
        require(audit["last_event_sha256"] == entry["event_head"], "Run event head differs from recorded result")
        events = audit["events"]
        start = next(e for e in events if e["type"] == "episode_started")
        run_manifest = json.loads(store.get(start["payload"]["manifest_ref"]["id"]))
        expected = manifest["implementations"][variant]["sha256"]
        model = run_manifest["model"]
        require(model["repair_variant"] == variant and model["case_id"] == entry["case_id"], "Run is assigned to the wrong case or variant")
        require(model["implementation_sha256"] == expected, "Wrong implementation identity")
        require(hashlib.sha256(store.get(model["implementation_ref"]["id"])).hexdigest() == expected, "Implementation snapshot differs")
        require(run_manifest["config"] == manifest["config"], "Run budgets differ from comparison")
        require(run_manifest["task"] == case["contract"]["goal"], "Original goal differs")
        bundle = json.loads(store.get(start["payload"]["source_bundle_ref"]["id"]))
        sources = {f["source_path"]: f["artifact_ref"]["sha256"] for f in bundle["files"]}
        require(all(sources.get(name) == value for name, value in manifest["protected_sources"].items()), "Run used different protected code")
        checks = [e for e in events if e["type"] == "completion_checked"]
        if not checks:
            raise MissingEvidence("No independent completion observation")
        event = checks[-1]
        if any(e["type"] == "dispatch_started" and e["seq"] > event["seq"] for e in events):
            raise MissingEvidence("Completion observation precedes a later operation")
        require(event["payload"]["binding_ref"] == run_manifest["verifier_binding_ref"], "Completion binding changed")
        binding = json.loads(store.get(event["payload"]["binding_ref"]["id"]))
        require(binding["checker_version"] == CHECKER_VERSION, "Bound checker differs")
        contract = json.loads(store.get(binding["contract_ref"]["id"]))
        before = json.loads(store.get(binding["before_ref"]["id"]))
        require(fingerprint(contract) == fingerprint(case["contract"]), "Run changed its completion contract")
        require(fingerprint(before) == fingerprint(case["before"]), "Run started from different state")
        report_ref = event["payload"]["report_ref"]
        report = json.loads(store.get(report_ref["id"]))
        refs = report["evidence_refs"]
        require(len(refs) == 3 and refs[:2] == [binding["contract_ref"], binding["before_ref"]], "Completion evidence differs from binding")
        after = json.loads(store.get(refs[2]["id"]))
        recomputed = evaluate(contract, before, after)
        require(set(report) == set(recomputed) | {"evidence_refs"}, "Unexpected completion report fields")
        require(fingerprint({k: report[k] for k in recomputed}) == fingerprint(recomputed), "Reported score does not match original evidence")
        require(event["payload"]["state"] == recomputed["state"], "Completion event contradicts evidence")
        end = next(e for e in events if e["type"] == "episode_finished")
        result = json.loads(store.get(end["payload"]["result_ref"]["id"]))
        require(result["status"] == end["payload"]["status"], "Terminal status mismatch")
        require((result["status"] == "VERIFIED_SUCCESS") == (recomputed["state"] == "TRUE"), "Terminal success contradicts checker")
        require(result["tool_attempts"] == sum(e["type"] == "action_allowed" for e in events), "Tool accounting mismatch")
        require(result["steps"] == max(e["step"] for e in events), "Step accounting mismatch")
        wall = (end["monotonic_ns"] - start["monotonic_ns"]) / 1e9
        require(wall >= 0, "Invalid duration")
        return {"case_id": entry["case_id"], "variant": variant, "run": entry["run"],
                "state": recomputed["state"], "reward": recomputed["reward"],
                "checks": {c["requirement_id"]: c["value"] for c in recomputed["checks"]},
                "steps": result["steps"], "tool_attempts": result["tool_attempts"], "wall_seconds": round(wall, 6),
                "event_head": audit["last_event_sha256"], "report_ref": report_ref}
    finally:
        store.close()


def score_comparison(directory):
    """Read-only scorer. It never loads or executes candidate helper code."""
    root = Path(directory).resolve()
    outcome = {"version": VERSION, "scored_at": timestamp(), "decision": "INVALID", "reasons": [],
               "synthetic": True, "native_performance_claimed": False, "promoted": False, "runs": []}
    try:
        manifest = load_json(root / "manifest.json")
        inputs = validate_manifest(root, manifest)
        outcome["manifest_sha256"] = digest(root / "manifest.json")
        outcome["scheduled_cases"] = len(inputs)
        index_path = root / "runs.json"
        if not index_path.is_file():
            raise MissingEvidence("Run index is unavailable")
        index = load_json(index_path)
        require(isinstance(index, list), "Run index must be a list")
        outcome["run_index_sha256"] = digest(index_path)
        entries, paths = {}, set()
        for entry in index:
            require(set(entry) == {"case_id", "variant", "run", "event_head"}, "Invalid run index entry")
            key = (entry["case_id"], entry["variant"])
            require(key[0] in inputs and key[1] in VARIANTS, "Unscheduled run in comparison")
            require(key not in entries and entry["run"] not in paths, "Duplicate case/variant or reused run")
            entries[key] = entry
            paths.add(entry["run"])
        unavailable = []
        for case_id, case in inputs.items():
            for variant in VARIANTS:
                entry = entries.get((case_id, variant))
                try:
                    if entry is None:
                        raise MissingEvidence("Scheduled run missing")
                    outcome["runs"].append(read_run(root, manifest, case, variant, entry))
                except MissingEvidence as error:
                    unavailable.append({"case_id": case_id, "variant": variant, "reason": str(error)})
        outcome["unavailable"] = unavailable
        outcome["pass_counts"] = {v: sum(r["state"] == "TRUE" for r in outcome["runs"] if r["variant"] == v) for v in VARIANTS}
        if unavailable or any(r["state"] == "UNKNOWN" for r in outcome["runs"]):
            outcome.update(decision="INCONCLUSIVE", reasons=["MISSING_OR_UNKNOWN_EVIDENCE"])
            return outcome
        by_key = {(r["case_id"], r["variant"]): r for r in outcome["runs"]}
        fixed, regressions, check_regressions = [], [], []
        for case_id in inputs:
            parent, candidate = (by_key[case_id, v] for v in VARIANTS)
            if parent["state"] == "FALSE" and candidate["state"] == "TRUE":
                fixed.append(case_id)
            if parent["state"] == "TRUE" and candidate["state"] == "FALSE":
                regressions.append(case_id)
            check_regressions.extend({"case_id": case_id, "requirement_id": k} for k in CHECK_IDS
                                     if parent["checks"][k] == "TRUE" and candidate["checks"][k] != "TRUE")
        target = manifest["target"]
        parent, candidate = (by_key[target["case_id"], v] for v in VARIANTS)
        reproduced = parent["checks"][target["requirement_id"]] == "FALSE"
        target_fixed = reproduced and candidate["checks"][target["requirement_id"]] == "TRUE" and candidate["state"] == "TRUE"
        cfg = manifest["config"]
        over_budget = [{"case_id": r["case_id"], "variant": r["variant"]} for r in outcome["runs"]
                       if r["steps"] > cfg["max_steps"] or r["tool_attempts"] > cfg["max_tool_attempts"]
                       or r["wall_seconds"] > cfg["deadline_seconds"]]
        outcome.update(target_failure_reproduced=reproduced, target_fixed=target_fixed, fixed_cases=fixed,
                       regressed_cases=regressions, requirement_regressions=check_regressions, budget_violations=over_budget,
                       pass_rate_gain=(outcome["pass_counts"]["candidate"] - outcome["pass_counts"]["parent"]) / len(inputs))
        reasons = []
        if not reproduced: reasons.append("TARGET_FAILURE_NOT_REPRODUCED")
        elif not target_fixed: reasons.append("TARGET_FAILURE_NOT_FIXED")
        if regressions or check_regressions: reasons.append("REGRESSION")
        if outcome["pass_counts"]["candidate"] != len(inputs): reasons.append("CANDIDATE_CASES_NOT_ALL_PASSING")
        if over_budget: reasons.append("RESOURCE_LIMIT")
        if manifest["implementations"]["parent"]["sha256"] == manifest["implementations"]["candidate"]["sha256"]:
            reasons.append("NO_IMPLEMENTATION_CHANGE")
        outcome.update(decision="REJECT" if reasons else "ACCEPT_FOR_DEVELOPMENT",
                       reasons=reasons or ["TARGET_FIXED_ALL_CASES_PASS_NO_REGRESSIONS"])
    except MissingEvidence as error:
        outcome.update(decision="INCONCLUSIVE", reasons=[str(error)])
    except (InvalidComparison, IntegrityError, OSError, ValueError, TypeError, KeyError, StopIteration, sqlite3.Error, ValidationError) as error:
        outcome.update(decision="INVALID", reasons=[f"{type(error).__name__}: {error}"])
    return outcome

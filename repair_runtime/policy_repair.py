"""Bounded model-driven policy repair and one guarded promotion path."""
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3

from react_runtime.policy import changed_component, validate_policy
from react_runtime.completion import fingerprint
from .evaluation import trial
from .policy_evaluation import fixtures, score, probe
from .store import Archive, runtime_sources


def import_previous(archive, directory):
    """Explicit read-only import across source revisions, retaining provenance."""
    old = Archive.__new__(Archive)
    old.root = Path(directory).resolve()
    old.db = sqlite3.connect(old.root.as_uri() + "/archive.sqlite?mode=ro", uri=True)
    old.db.row_factory = sqlite3.Row
    try:
        audit = old.audit()
        for name, ref in old.meta("source_snapshots").items():
            source = old.get(ref)
            if source["path"] != name or hashlib.sha256(source["text"].encode()).hexdigest() != old.meta("sources")[name]:
                raise ValueError("Original source snapshot integrity failure")
        if archive.db.execute("SELECT count(*) FROM cases").fetchone()[0]: raise ValueError("Import requires a fresh archive")
        package = archive.put(old.get(old.meta("active")))
        adapters = {}
        for row in old.db.execute("SELECT id,input_ref,origin_ref FROM cases ORDER BY id"):
            key = archive.add_case(old.get(row["input_ref"]), {"kind": "verified_archive_import", "archive": str(old.root), "event_head": audit["event_head"], "original_origin": old.get(row["origin_ref"])})
            if key in old.meta("case_adapters"):
                adapters[key] = archive.put(old.get(old.meta("case_adapters")[key]))
        case_count = archive.db.execute("SELECT count(*) FROM cases").fetchone()[0]
        with archive.db:
            archive.set("active", package)
            archive.set("case_adapters", adapters)
            archive.set("execution_gate_required", True)
            archive.event("PREVIOUS_EXPERIMENT_IMPORTED", {"source": str(old.root), "event_head": audit["event_head"], "package": package, "case_count": case_count})
        manifest = json.loads((old.root / "proof-manifest.json").read_text())
        return {"stress": old.get(manifest["stress_cases"]), "manifest": manifest}
    finally: old.close()


def freeze(archive, structural_cases):
    existing = archive.db.execute("SELECT value FROM meta WHERE key='policy_manifest'").fetchone()
    if existing: return archive.get(json.loads(existing[0]))
    manifest = {"sealed": archive.put(fixtures(secrets.randbits(48))), "structural": archive.put(structural_cases),
                "sources": runtime_sources(), "max_candidates_per_group": 3,
                "sealed_visibility": "Evaluator only. Search receives component and bounded evidence, never sealed cases."}
    with archive.db:
        archive.set("policy_manifest", archive.put(manifest))
        archive.event("POLICY_SUITE_FROZEN", {"manifest": archive.meta("policy_manifest"), "sealed_count": 12})
    return manifest


def register_failure(archive, component, target, evidence_refs=()):
    if component != target["component"]: raise ValueError("Target component mismatch")
    key = fingerprint({"component": component, "target": target})
    with archive.db:
        groups = archive.meta("policy_groups")
        if key not in groups:
            groups[key] = {"component": component, "target": archive.put(target), "evidence": list(evidence_refs), "attempts": [], "resolved": False}
            archive.set("policy_groups", groups)
            archive.event("POLICY_FAILURE_REGISTERED", {"group": key, "component": component})
    return key


def evidence_view(archive, group):
    # Bounded original artifacts and previous rejection receipts, not a trace dump.
    view = [{"ref": ref, "excerpt": json.dumps(archive.get(ref), ensure_ascii=False)[:3000], "max_chars": 3000} for ref in group["evidence"][-2:]]
    for ref in group["attempts"][-2:]:
        receipt = archive.get(ref)
        visible = {k: receipt[k] for k in ("status", "parent", "candidate", "component", "conditions", "accepted") if k in receipt}
        if receipt.get("candidate"): visible["candidate_program"] = archive.get(receipt["candidate"])
        view.append({"ref": ref, "excerpt": json.dumps(visible)[:3000], "max_chars": 3000})
    return view


def register_episode(archive, result):
    """Extract a bounded component counterexample, retaining original provenance."""
    from react_runtime.store import RunStore
    judged = archive.get(result["judge"])
    route = judged["repair_route"]
    if route not in {"POLICY_BINDING", "POLICY_CONTEXT", "POLICY_DISCOVERY"}: return None
    store = RunStore.open_existing(Path(result["episode"]["run_directory"]))
    try:
        events = store.audit()["events"]
        manifest = json.loads(store.get(next(e for e in events if e["type"] == "episode_started")["payload"]["manifest_ref"]["id"]))
        if route == "POLICY_DISCOVERY":
            # This is a lexical retrieval counterexample, never a declaration
            # that a tool has the required domain semantics.
            from react_runtime.policy import tokens
            words = manifest["task"].strip().split()
            if not words or len(tokens(words[0])) != 1: return None
            catalogue_path = store.root.parent / "session/mcp-catalog.json"
            if not catalogue_path.exists():
                if not any(t.get("bootstrap") for t in manifest.get("tool_implementations", [])): return None
                target = {"component": "discovery", "goal": manifest["task"], "tools": [], "require_state_bootstrap": True, "bootstrap_only": True}
            else:
                catalogue = json.loads(catalogue_path.read_text())
                target = {"component": "discovery", "goal": manifest["task"], "action_word": next(iter(tokens(words[0]))),
                          "tools": [{"name": t["name"], "description": t.get("description", "")} for t in catalogue.values()]}
        elif route == "POLICY_BINDING":
            proposals = [json.loads(store.get(e["payload"]["proposal_ref"]["id"])) for e in events if e["type"] == "action_proposed"]
            proposal = next((p for p in reversed(proposals) if p.get("kind") == "act"), None)
            if not proposal: return None
            schema = next((t["arguments"] for t in manifest["tools"] if t["name"] == proposal["action_id"]), None)
            if schema is None: return None
            if proposal["action_id"] == "call_tool":
                native = proposal["arguments"].get("name")
                inspected = []
                for event in events:
                    if event["type"] == "operation_result" and event["payload"]["action"] == "inspect_tool" and event["payload"]["execution"]["status"] == "COMPLETE":
                        inspected.append(json.loads(store.get(event["payload"]["output_ref"]["id"])).get("tool", {}))
                description = next((t for t in reversed(inspected) if t.get("name") == native), None)
                if not description: return None
                has_index = store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='working'").fetchone()
                if has_index:
                    bindings = [json.loads(r[0]) for r in store.db.execute("SELECT value FROM working WHERE kind='bindings'")]
                    observed = {"records": [{r["field"]: r["value"]} for r in bindings]}
                else:
                    # Older immutable traces predate the derived index. Use
                    # their actual read results without migrating the archive.
                    observed = {"records": [json.loads(store.get(e["payload"]["output_ref"]["id"])) for e in events
                        if e["type"] == "operation_result" and e["payload"]["execution"]["status"] == "COMPLETE"]}
                target = {"component": "binding", "tool_name": native, "schema": {**description["inputSchema"], "additionalProperties": False},
                          "arguments": proposal["arguments"].get("arguments", {}), "observed": observed}
            else:
                target = {"component": "binding", "tool_name": proposal["action_id"], "schema": schema, "arguments": proposal["arguments"], "observed": {}}
            constrained = binding_counterexample(store, manifest, events)
            if constrained is not None: target = constrained
        else:
            observations = []
            for event in events:
                if event["type"] != "operation_result" or event["payload"]["execution"]["status"] != "COMPLETE": continue
                request = json.loads(store.get(event["payload"]["request_ref"]["id"]))
                value = json.loads(store.get(event["payload"]["output_ref"]["id"]))
                observations.append({**request, "value": value})
            history = []
            for event in events:
                if event["type"] != "observation_prepared": continue
                value = json.loads(store.get(event["payload"]["observation_ref"]["id"]))
                history.append({"step": event.get("step", len(history)), "action": "original_observation", "action_key": '["original_observation",{}]',
                                "model_output_id": None, "observation_id": None, "observation": value})
            target = {"component": "context", "kind": "history", "length": len(history), "history": history,
                      "config": manifest["config"], "goal": manifest["task"], "tools": manifest["tools"]}
            if judged["execution_stop"] != "CONTEXT_OVERFLOW":
                target = {"component": "context", "kind": "cycle", "empty_pages": False, "observations": observations[-8:]}
                # Only repeated evidence is a reproduced progress-policy defect.
                if not probe({**archive.get(archive.meta("active_policy")), "context": "working"}, target)["passed"]: return None
        if probe(archive.get(result.get("policy_used", archive.meta("active_policy"))), target)["passed"]: return None
        key = register_failure(archive, target["component"], target, [result["judge"], archive.put({"run": str(store.root), "manifest": manifest, "target": target})])
        request = archive.meta("inference_requests").get(result.get("request_id"))
        with archive.db:
            groups = archive.meta("policy_groups")
            groups[key]["goal"] = manifest["task"]
            if request:
                groups[key]["replay"] = {"request": request["request"], "package": request["package"]}
            archive.set("policy_groups", groups)
        return key
    finally: store.close()


def binding_counterexample(store, manifest, events):
    from .admission import check_update
    from react_runtime.completion import evaluate
    from jsonschema import Draft202012Validator
    ref = manifest.get("verifier_binding_ref")
    schema = next((t["arguments"] for t in manifest["tools"] if t["name"] == "apply_update"), None)
    if not ref or schema is None: return None
    binding = json.loads(store.get(ref["id"]))
    data = {"contract": json.loads(store.get(binding["contract_ref"]["id"])), "before": json.loads(store.get(binding["before_ref"]["id"]))}
    current = data["before"]
    for event in events:
        if event["type"] == "kernel_checkpoint": current = json.loads(store.get(event["payload"]["evidence_ref"]["id"]))["snapshot"]
        if event["type"] == "operation_result" and event["payload"]["execution"]["status"] == "COMPLETE":
            value = json.loads(store.get(event["payload"]["output_ref"]["id"]))
            if "snapshot" in value: current = value["snapshot"]
            elif all(k in value for k in ("entities", "relations", "scope", "revision")): current = value
        if event["type"] != "action_proposed": continue
        proposal = json.loads(store.get(event["payload"]["proposal_ref"]["id"]))
        if proposal.get("action_id") != "apply_update" or not Draft202012Validator(schema).is_valid(proposal["arguments"]): continue
        protected = next(c for c in evaluate(data["contract"], data["before"], current)["checks"] if c["requirement_id"] == "unrelated_state_preserved")
        if protected["value"] == "TRUE" and check_update(data, current, "apply_update", proposal["arguments"]):
            return {"component": "binding", "tool_name": "apply_update", "schema": schema, "arguments": proposal["arguments"],
                    "observed": current, "preflight_data": data, "current": current, "original_proposal_ref": event["payload"]["proposal_ref"]}
    return None


def replay_failure(archive, group, policy_ref):
    from .inference import execute_request
    from .judge import judge_episode
    import uuid
    replay = group["replay"]
    request = archive.get(replay["request"])
    root = archive.root / "policy-live" / uuid.uuid4().hex
    rows = []
    for repeat in range(3):
        try:
            outcome = execute_request(archive, request, root / str(repeat), package_ref=replay["package"], policy_ref=policy_ref)
            judged = judge_episode(archive, outcome["episode"]["run_directory"], native=outcome["native"])
            rows.append({"passed": judged["task_state"] == "TRUE" and outcome["episode"]["status"] == "VERIFIED_SUCCESS" and judged["coverage"]["integrity_complete"],
                         "judge": judged["receipt"], "episode": outcome["episode"]})
        except Exception as error: rows.append({"passed": False, "error": str(error)[:1000]})
    return {"passed": len(rows) == 3 and all(r["passed"] for r in rows), "rows": rows, "fresh_worlds": True}


def live_failure_evidence(archive, live):
    """Export bounded original live counterexamples, never sealed evaluator cases."""
    from react_runtime.store import RunStore
    refs, seen, unavailable = [], set(), False
    for row in live.get("rows", []):
        audit = row.get("audit", {})
        if row.get("passed", audit.get("passed", False)): continue
        run = row.get("episode", {}).get("run_directory", audit.get("run"))
        stop = row.get("episode", {}).get("status", audit.get("execution_stop"))
        if stop in {"MODEL_ERROR", "UNKNOWN_TOOL_OUTCOME", "RUNTIME_ERROR", "INTEGRITY_FAILURE"} or not run:
            unavailable = True
            continue
        identity = row.get("case", run)
        if identity in seen or len(seen) >= 2: continue
        seen.add(identity)
        store = RunStore.open_existing(Path(run))
        try:
            audited = store.audit()
            if not audited["complete"]:
                unavailable = True
                continue
            events = audited["events"]
            start = next(e for e in events if e["type"] == "episode_started")
            manifest = json.loads(store.get(start["payload"]["manifest_ref"]["id"]))
            actions, observations = [], []
            for event in events:
                if event["type"] == "action_proposed":
                    actions.append(json.loads(store.get(event["payload"]["proposal_ref"]["id"])))
                elif event["type"] == "observation_prepared":
                    observations.append(json.loads(store.get(event["payload"]["observation_ref"]["id"])))
            pages = [archive.put(o) for o in observations[-3:]]
            refs.extend(pages)
            refs.append(archive.put({"original_goal": manifest["task"], "run": str(store.root), "event_head": audited["last_event_sha256"],
                "execution_stop": stop, "recent_proposals": actions[-3:], "observation_refs": pages,
                "recent_outcomes": [{k: o[k] for k in ("code", "message", "effect_uncertain") if k in o} for o in observations[-3:]]}))
        finally: store.close()
    return refs, unavailable


def promote(archive, candidate, group_key, *, live_gate=None):
    from .inference import inference_owner
    with inference_owner(archive), archive.worker():
        return _promote(archive, candidate, group_key, live_gate=live_gate)


def _promote(archive, candidate, group_key, *, live_gate=None):
    """All candidate decisions, including negative controls, pass here.

    Call under inference_owner and archive.worker, so no episode can start
    during comparison or activation. No caller-supplied acceptance boolean.
    """
    from .inference import execution_gate
    parent, kernel = archive.meta("active_policy"), archive.meta("active")
    old, new = archive.get(parent), validate_policy(candidate)
    component = changed_component(old, new)
    suite, suite_ref = archive.snapshot()
    manifest = archive.get(archive.meta("policy_manifest"))
    groups = archive.meta("policy_groups")
    group = groups[group_key]
    if live_gate is None and "replay" in group: live_gate = lambda ref: replay_failure(archive, group, ref)
    if component != group["component"]: raise ValueError("Candidate changed the wrong component")
    if len(group["attempts"]) >= 3: raise ValueError("Failure group exhausted its three candidate attempts")
    if archive.meta("proposals_spent") >= archive.meta("max_proposals"): raise ValueError("Archive proposal budget exhausted")
    candidate_ref = archive.put(new)
    if any(archive.get(ref).get("parent") == parent and archive.get(ref).get("candidate") == candidate_ref for ref in group["attempts"]):
        raise ValueError("This candidate was already attempted under this parent; automatic replay is disabled")
    context_ref = archive.put(evidence_view(archive, group))
    # Reserve before work. Interrupted attempts consume the budget and remain visible.
    reservation = archive.put({"status": "STARTED", "parent": parent, "candidate": candidate_ref, "evidence_view": context_ref})
    group["attempts"].append(reservation)
    with archive.db:
        archive.set("proposals_spent", archive.meta("proposals_spent") + 1)
        archive.set("policy_groups", groups)
        archive.event("POLICY_CANDIDATE_RESERVED", {"group": group_key, "receipt": reservation})
    target = archive.get(group["target"])
    old_target, new_target = probe(old, target), probe(new, target)
    sealed = archive.get(manifest["sealed"])
    old_checks, new_checks = score(old, sealed), score(new, sealed)
    structural = [trial(archive.get(kernel), data)["state"] for data in archive.get(manifest["structural"])]
    conditions = {"target_reproduced": not old_target["passed"], "target_improved": new_target["passed"],
                  "no_sealed_regression": all(not a["passed"] or b["passed"] for a, b in zip(old_checks, new_checks)),
                  "component_sealed_pass": all(r["passed"] for r in new_checks if r["component"] == component),
                  "structural_pass": bool(structural) and all(s == "TRUE" for s in structural),
                  "sources_unchanged": manifest["sources"] == runtime_sources(),
                  "no_episode_running": not (set(archive.meta("inference_requests")) - set(archive.meta("inference_completed")))}
    gate = None
    live = None
    if all(conditions.values()):
        gate = execution_gate(archive, candidate_ref)(kernel, kernel, suite)
        conditions["retained_execution_pass"] = bool(suite["cases"]) and gate["state"] == "TRUE"
        if all(conditions.values()) and live_gate is not None:
            live = live_gate(candidate_ref)
            conditions["fresh_live_pass"] = bool(live["passed"])
    retryable = True
    if live is not None and not live["passed"]:
        refs, unavailable = live_failure_evidence(archive, live)
        group["evidence"].extend(refs)
        retryable = not unavailable
    receipt = {"parent": parent, "candidate": candidate_ref, "kernel": kernel, "suite": suite_ref, "component": component,
               "target_before": old_target, "target_after": new_target, "sealed_before": old_checks, "sealed_after": new_checks,
               "structural": structural, "conditions": conditions, "execution_gate": gate, "live_gate": live,
               "evidence_view": context_ref, "accepted": all(conditions.values()), "retryable": retryable}
    with archive.db:
        archive.db.execute("BEGIN IMMEDIATE")
        receipt["conditions"]["sources_unchanged"] = manifest["sources"] == runtime_sources()
        receipt["accepted"] = all(receipt["conditions"].values())
        if archive.meta("active_policy") != parent or archive.meta("active") != kernel or archive.meta("generation") != suite["generation"]:
            receipt["accepted"] = False
            receipt["conditions"]["version_compare_and_swap"] = False
        if receipt["accepted"]: archive.set("active_policy", candidate_ref)
        ref = archive.put(receipt)
        group["attempts"][-1] = ref
        group["resolved"] = receipt["accepted"]
        archive.set("policy_groups", groups)
        archive.set("policy_decisions", archive.meta("policy_decisions") + [ref])
        archive.event("POLICY_ACCEPTED" if receipt["accepted"] else "POLICY_REJECTED", {"receipt": ref, "group": group_key})
    return {"receipt": ref, **receipt}


def work(archive, *, live_gate=None, proposer=None, group_keys=None, on_decision=None):
    from .inference import inference_owner
    from .policy_proposer import PolicyModelProposer
    results = []
    with inference_owner(archive), archive.worker():
        if not archive.meta("policy_groups"): return results
        if not archive.db.execute("SELECT 1 FROM meta WHERE key='policy_manifest'").fetchone():
            from .evaluation import challenges
            freeze(archive, challenges(secrets.randbits(48), 50, function="direct", numeric=True)
                   + challenges(secrets.randbits(48), 50, function="related"))
        proposer = proposer or PolicyModelProposer()
        for key, group in archive.meta("policy_groups").items():
            if group_keys is not None and key not in group_keys: continue
            if group["resolved"]: continue
            parent = archive.get(archive.meta("active_policy"))
            if probe(parent, archive.get(group["target"]))["passed"]: continue
            while True:
                groups = archive.meta("policy_groups")
                group = groups[key]
                calls = group.setdefault("model_attempts", [])
                if len(calls) >= 3 or len(group["attempts"]) >= 3 or archive.meta("proposals_spent") >= archive.meta("max_proposals"): break
                reservation = archive.put({"status": "STARTED", "provider": proposer.name, "parent": archive.meta("active_policy")})
                calls.append(reservation)
                with archive.db:
                    archive.set("policy_groups", groups)
                    archive.event("POLICY_PROPOSAL_RESERVED", {"group": key, "receipt": reservation})
                try: proposal = proposer.one(archive, key, parent, len(calls) - 1)
                except Exception as error: proposal = {"kind": "unavailable", "reason": str(error)[:1000]}
                proposal_ref = archive.put(proposal)
                groups = archive.meta("policy_groups")
                groups[key]["model_attempts"][-1] = proposal_ref
                with archive.db:
                    archive.set("policy_groups", groups)
                    archive.event("POLICY_PROPOSAL_FINISHED", {"group": key, "receipt": proposal_ref})
                if proposal["kind"] != "candidate":
                    result = {"accepted": False, "component": group["component"], "proposal": proposal_ref, "status": proposal["kind"], "reason": proposal.get("reason")}
                    results.append(result)
                    if on_decision: on_decision(result)
                    break  # No transport retry or hand-written replacement.
                candidate = proposal["candidate"]
                reference = fingerprint(candidate)
                if any(archive.get(ref).get("parent") == archive.meta("active_policy") and archive.get(ref).get("candidate") == reference
                       for ref in archive.meta("policy_groups")[key]["attempts"]):
                    result = {"accepted": False, "component": group["component"], "proposal": proposal_ref, "status": "DUPLICATE_CANDIDATE"}
                else:
                    result = _promote(archive, candidate, key, live_gate=live_gate)
                    result["proposal"] = proposal_ref
                results.append(result)
                if on_decision: on_decision(result)
                if result["accepted"] or result.get("retryable") is False: break
    return results

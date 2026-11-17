"""Deterministic whole-ledger assessment with bounded, addressable segments.

No trace dump enters a model context. Every event is covered and every original
artifact is integrity-checked. Semantic conclusions have a narrower, explicit
scope: bound completion checks and native checks, when available.
"""

from collections import Counter
import json
from pathlib import Path

from react_runtime.store import RunStore
from react_runtime.working import evidence_signature


def judge_episode(archive, directory, *, native=None, segment_size=64):
    if not 1 <= segment_size <= 256: raise ValueError("Invalid judge segment size")
    store = RunStore.open_existing(Path(directory))
    try:
        audit = store.audit()
        events = audit["events"]
        started = next(e for e in events if e["type"] == "episode_started")
        manifest = json.loads(store.get(started["payload"]["manifest_ref"]["id"]))
        segments, findings = [], []
        last_report, last_check, last_dispatch = None, -1, -1
        terminal, handoffs = None, []
        seen_observations, stagnant = set(), 0
        for offset in range(0, len(events), segment_size):
            batch = events[offset:offset + segment_size]
            local = []
            for event in batch:
                kind, payload, seq = event["type"], event["payload"], event["seq"]
                if kind == "dispatch_started": last_dispatch = seq
                if kind == "operation_result" and payload["execution"]["status"] == "COMPLETE":
                    key = evidence_signature(json.loads(store.get(payload["output_ref"]["id"])))
                    stagnant = stagnant + 1 if key in seen_observations else 0
                    seen_observations.add(key)
                if kind == "episode_finished": terminal = payload["status"]
                if kind == "completion_checked":
                    last_report = json.loads(store.get(payload["report_ref"]["id"]))
                    last_check = seq
                    if last_report["state"] != "TRUE":
                        local.append({"code": "COMPLETION_" + last_report["state"], "seq": seq,
                                      "failed_checks": [c["requirement_id"] for c in last_report["checks"] if c["value"] != "TRUE"],
                                      "evidence": payload["report_ref"]})
                if kind == "kernel_handoff":
                    handoffs.append(payload["handoff"])
                    local.append({"code": payload["handoff"]["reason"], "seq": seq, "evidence": payload["handoff"]})
                if kind in {"action_denied", "argument_correction", "proposal_invalid", "runtime_error", "verification_failed", "progress_stalled"}:
                    local.append({"code": kind.upper(), "seq": seq, "evidence": payload})
                if kind in {"model_result", "operation_result"} and payload["execution"]["status"] != "COMPLETE":
                    local.append({"code": payload["execution"]["status"], "seq": seq, "evidence": payload})
            findings.extend(local)
            segments.append(archive.put({"first_seq": batch[0]["seq"], "last_seq": batch[-1]["seq"],
                "event_count": len(batch), "event_types": dict(Counter(e["type"] for e in batch)),
                "first_previous_hash": batch[0]["previous_sha256"], "last_hash": batch[-1]["sha256"],
                "findings": local}))
        fresh = last_report is not None and last_check > last_dispatch
        state = last_report["state"] if fresh else "UNKNOWN"
        native_success = None if native is None else native.get("success")
        native_coverage, native_complete = 0, True
        if native is not None:
            pending, finished = {}, set()
            for segment in native.get("mcp_segments", []):
                for event in archive.get(segment):
                    native_coverage += 1
                    identity = event.get("call_id")
                    if event["event"] == "call_started":
                        if identity in pending or identity in finished: native_complete = False
                        pending[identity] = event["name"]
                    elif event["event"] == "call_result":
                        if pending.pop(identity, None) != event["name"]: native_complete = False
                        finished.add(identity)
                        if event["result"].get("isError"):
                            findings.append({"code": "MCP_TOOL_ERROR", "call_id": identity, "segment": segment})
                    else: native_complete = False
            native_complete &= not pending and native_coverage == native.get("mcp_events")
        if native_success is False: state = "FALSE"
        # A model/tool transport fault cannot certify success, even if a later
        # readback looks good. Incomplete evidence never authorizes promotion.
        if not audit["complete"] or not native_complete: state = "UNKNOWN"
        infrastructure = terminal in {"RUNTIME_ERROR", "INTEGRITY_FAILURE", "MODEL_ERROR", "UNKNOWN_TOOL_OUTCOME"}
        readers = {t["name"] for t in manifest.get("tool_implementations", []) if t.get("bootstrap")}
        observed = {e["payload"]["action"] for e in events if e["type"] == "operation_result" and e["payload"]["execution"]["status"] == "COMPLETE"}
        unsafe = last_report and any(c["requirement_id"] == "unrelated_state_preserved" and c["value"] == "FALSE" for c in last_report["checks"])
        if not audit["complete"] or not native_complete or infrastructure: route = "RUNTIME_OR_EVIDENCE"
        elif native_success is False and last_report and last_report["state"] == "TRUE": route = "ADAPTER_OR_CONTRACT"
        elif state == "FALSE" and readers and not readers & observed: route = "POLICY_DISCOVERY"
        elif unsafe and manifest.get("argument_guard"): route = "POLICY_BINDING"
        elif terminal in {"ARGUMENT_REPAIR_EXHAUSTED", "NO_PROGRESS"} and any(f["code"] in {"ACTION_DENIED", "ARGUMENT_CORRECTION"} and f["evidence"].get("reason") == "ARGUMENT_SCHEMA_INVALID" for f in findings): route = "POLICY_BINDING"
        elif terminal == "CONTEXT_OVERFLOW": route = "POLICY_CONTEXT"
        elif terminal in {"NO_PROGRESS", "BUDGET_EXHAUSTED"} and sum(e["type"] == "operation_result" and e["payload"].get("action") == "discover_tools" for e in events) >= 2: route = "POLICY_DISCOVERY"
        elif terminal in {"NO_PROGRESS", "BUDGET_EXHAUSTED"} and stagnant >= 3 and last_report and last_report["state"] == "FALSE": route = "POLICY_CONTEXT"
        elif last_report is None or last_report["state"] == "UNKNOWN": route = "EVIDENCE"
        else: route = "PROGRAM_COMPARISON"
        result = {"version": 1, "run": str(store.root), "event_head": audit["last_event_sha256"],
                  "coverage": {"events": len(events), "covered": sum(min(segment_size, len(events) - i) for i in range(0, len(events), segment_size)),
                               "segments": segments, "artifact_count": len(audit["artifacts"]),
                               "native_events_covered": native_coverage, "native_integrity_complete": native_complete,
                               "integrity_complete": audit["complete"] and native_complete},
                  "task_state": state, "reward": {"TRUE": 1, "FALSE": 0, "UNKNOWN": None}[state],
                  "execution_stop": terminal, "kernel_gap": bool(handoffs),
                  "recovered": bool(handoffs) and state == "TRUE", "repair_route": route,
                  "findings": findings, "final_check_fresh": fresh, "native": native,
                  "limitations": ["Every event is inspected; this does not prove arbitrary natural-language reasoning correct.",
                                  "Completion scope comes from the trusted adapter; official native checks remain authoritative."]}
        receipt = archive.put(result)
        with archive.db: archive.event("EPISODE_JUDGED", {"receipt": receipt, "run": str(store.root), "route": route})
        return {"receipt": receipt, **result}
    finally:
        store.close()

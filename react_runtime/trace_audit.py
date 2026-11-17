"""Deterministic trace integrity checks before any advisory judge sees the case."""

import hashlib
import json

from .store import IntegrityError, json_bytes


REQUIRED = {
    "kernel_checkpoint": ["evidence_ref", "state"],
    "kernel_plan_checked": ["plan_ref", "state"],
    "progress_stalled": ["repeated_steps", "reason", "threshold"],
    "completion_checked": ["binding_ref", "report_ref", "state"],
    "kernel_started": ["request_id", "input_ref", "kernel_version"],
    "kernel_result": ["request_id", "input_ref", "output_ref", "kernel_version"],
    "kernel_handoff": ["handoff", "tool_attempts", "deadline_remaining_seconds"],
    "episode_started": ["manifest_ref", "system_ref", "source_bundle_ref"],
    "model_started": ["request_id", "input_ref", "pending_output_id", "pending_stderr_id"],
    "model_result": ["request_id", "input_ref", "output_ref", "stderr_ref", "execution"],
    "action_proposed": ["response_ref", "proposal_ref"],
    "action_allowed": ["action", "request_ref"],
    "dispatch_started": ["action", "request_ref"],
    "operation_result": ["action", "request_ref", "output_ref", "execution"],
    "verification_started": ["verification_input_ref"],
    "finish_verified": ["verification_input_ref", "verification_ref"],
    "context_compacted": ["before_ref", "after_ref", "old_cutoff", "new_cutoff"],
    "observation_prepared": ["observation_ref"],
    "episode_finished": ["result_ref", "status"],
}


def audit_store(store) -> dict:
    artifacts, problems = [], []
    rows = store.db.execute("SELECT id,kind,step,path,digest,size,visible,complete FROM artifacts ORDER BY rowid")
    for row in rows:
        artifact = dict(zip(("id", "kind", "step", "path", "sha256", "bytes", "actor_visible", "complete"), row))
        try:
            store.get(row[0])
        except (IntegrityError, KeyError) as error:
            problems.append({"artifact_id": row[0], "error": str(error)})
        if not row[7]:
            problems.append({"artifact_id": row[0], "error": "PARTIAL_CAPTURE"})
        artifacts.append(artifact)
    indexed_paths = {a["path"] for a in artifacts}
    for path in store.root.rglob("step-*.txt"):
        if str(path.relative_to(store.root)) not in indexed_paths:
            problems.append({"path": str(path.relative_to(store.root)), "error": "UNINDEXED_CAPTURE"})
    events = [{"seq": r[0], "type": r[1], "step": r[2], "at": r[3], "monotonic_ns": r[4],
               "payload": json.loads(r[5]), "previous_sha256": r[6], "sha256": r[7]}
              for r in store.db.execute("SELECT * FROM events ORDER BY seq")]
    if [e["seq"] for e in events] != list(range(1, len(events) + 1)):
        problems.append({"error": "EVENT_SEQUENCE_GAP"})
    if not events or events[-1]["type"] != "episode_finished":
        problems.append({"error": "NO_TERMINAL_RECEIPT"})
    if sum(e["type"] == "episode_started" for e in events) != 1:
        problems.append({"error": "INVALID_EPISODE_START_COUNT"})
    if sum(e["type"] == "episode_finished" for e in events) != 1:
        problems.append({"error": "INVALID_EPISODE_END_COUNT"})
    artifact_map = {a["id"]: a for a in artifacts}

    def check_refs(value, seq):
        if isinstance(value, dict):
            if {"id", "path", "sha256"} <= value.keys():
                actual = artifact_map.get(value["id"])
                if not actual:
                    problems.append({"error": "DANGLING_EVENT_REFERENCE", "seq": seq, "artifact_id": value["id"]})
                elif any(value.get(k) != actual[k] for k in ("path", "sha256", "bytes")):
                    problems.append({"error": "REFERENCE_METADATA_MISMATCH", "seq": seq, "artifact_id": value["id"]})
            for child in value.values():
                check_refs(child, seq)
        elif isinstance(value, list):
            for child in value:
                check_refs(child, seq)

    previous_digest = "0" * 64
    for event in events:
        unsigned = {k: v for k, v in event.items() if k != "sha256"}
        if (event["previous_sha256"] != previous_digest or
                hashlib.sha256(json_bytes(unsigned)).hexdigest() != event["sha256"]):
            problems.append({"error": "EVENT_HASH_MISMATCH", "seq": event["seq"]})
        previous_digest = event["sha256"]
        for field in REQUIRED.get(event["type"], []):
            if field not in event["payload"]:
                problems.append({"error": "MISSING_EVENT_FIELD", "seq": event["seq"], "field": field})
        check_refs(event["payload"], event["seq"])

    # A terminal receipt cannot conceal an interrupted model, tool or verifier invocation.
    for start_type, result_types, key in (
            ("kernel_started", {"kernel_result"}, "request_id"),
            ("model_started", {"model_result"}, "request_id"),
            ("dispatch_started", {"operation_result"}, "request_ref"),
            ("verification_started", {"finish_verified", "verification_failed"}, "verification_input_ref")):
        starts = [e for e in events if e["type"] == start_type]
        ends = [e for e in events if e["type"] in result_types]
        for start in starts:
            matches = [e for e in ends if e["step"] == start["step"] and
                       e["payload"].get(key) == start["payload"].get(key) and e["seq"] > start["seq"]]
            if len(matches) != 1:
                problems.append({"error": "UNPAIRED_INVOCATION", "seq": start["seq"], "matching_receipts": len(matches)})
            elif start_type == "model_started":
                for pending, actual in (("pending_output_id", "output_ref"), ("pending_stderr_id", "stderr_ref")):
                    if start["payload"].get(pending) != matches[0]["payload"].get(actual, {}).get("id"):
                        problems.append({"error": "CAPTURE_ID_MISMATCH", "seq": start["seq"]})
        for end in ends:
            if not any(e["step"] == end["step"] and e["payload"].get(key) == end["payload"].get(key)
                       and e["seq"] < end["seq"] for e in starts):
                problems.append({"error": "ORPHAN_RESULT", "seq": end["seq"]})

    steps = []
    for step in sorted({e["step"] for e in events if e["step"] > 0}):
        selected = [e for e in events if e["step"] == step]
        types = [e["type"] for e in selected]
        if "dispatch_started" in types and ("action_allowed" not in types or
                types.index("action_allowed") > types.index("dispatch_started") or "action_denied" in types):
            problems.append({"error": "DISPATCH_WITHOUT_ADMISSION", "step": step})
        steps.append({"step": step, "event_seqs": [e["seq"] for e in selected], "event_types": types,
                      "artifact_ids": [a["id"] for a in artifacts if a["step"] == step]})
    return {"trace_version": "react-component-0.1", "run_directory": str(store.root),
            "complete": not problems, "last_event_sha256": previous_digest,
            "limitations": ["CLI-supplied input captured; hidden provider context/usage may be unavailable",
                            "Trusted local tools; this component is not the full isolation kernel",
                            "Benchmark evaluation, if configured, is a separate linked receipt; no automatic crash resume",
                            "Hash checks detect inconsistency; the local owner can rewrite files and hashes",
                            "Raw diagnostic files are private; review before sharing"],
            "problems": problems, "steps": steps, "artifacts": artifacts, "events": events}

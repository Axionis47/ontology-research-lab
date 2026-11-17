"""Proposers emit data. They cannot execute or install their own program."""

import json
import os
from pathlib import Path
import shutil
import sys
import tomllib
import uuid

from react_runtime.loop import parse_json
from react_runtime.process import execute
from react_runtime.store import json_bytes
from .program import function_name, mutations, TYPE_SLOTS, WHERE_SLOTS, NUMERIC_SLOTS, MAX_NODES
from .store import ROOT


class SearchProposer:
    name = "bounded-program-search"

    def propose(self, archive, packet, parent):
        # Deliberately ignores task records and expected outcomes.
        for candidate in mutations(parent, packet["function"]):
            yield {"kind": "candidate", "candidate": candidate,
                   "reason": "One structural edit from the declared operator grammar", "evidence": []}


class ModelProposer:
    """Existing configured CLI, no tools, four bounded reads/calls per proposal."""
    def __init__(self, provider="gemini", *, command=None, timeout=120, max_calls=4, diagnosis=None):
        if provider not in {"gemini", "ollama", "test"}: raise ValueError("Unknown proposer provider")
        self.name, self.timeout, self.max_calls = provider, timeout, max_calls
        self.diagnosis = diagnosis
        config = tomllib.loads((ROOT / "config/models.toml").read_text())
        if command is not None:
            if provider != "test": raise ValueError("Command override is for explicit test transport only")
            self.command = command
        elif provider == "ollama":
            self.command = [sys.executable, str(ROOT / "react_runtime/ollama.py")]
        else:
            cli = shutil.which(config["gemini"]["executable"])
            if not cli: raise ValueError("Configured Gemini CLI unavailable")
            self.command = [cli, "--extensions", "none", "--allowed-mcp-server-names", "model-check-no-servers",
                            "--policy", str(ROOT / config["gemini"]["policy"]), "--skip-trust",
                            "--output-format", "json", "--prompt", "{prompt}"]

    def propose(self, archive, packet, parent):
        for attempt in range(3):
            result = self.one(archive, packet, parent, attempt)
            yield result
            if result["kind"] != "candidate": return

    def one(self, archive, packet, parent, attempt):
        allowed = set(packet["evidence_refs"])
        history = []
        for row in archive.db.execute("SELECT candidate,status,receipt FROM attempts WHERE case_id=? AND receipt IS NOT NULL ORDER BY id DESC LIMIT 3",
                                      (packet["case_id"],)):
            receipt = archive.get(row["receipt"])
            history.append({"candidate": row["candidate"], "status": row["status"],
                            "reason": receipt.get("reasons", receipt.get("reason")), "receipt": row["receipt"]})
            # Only visible-case details are readable. Fresh challenge bodies stay private.
            if "challenge_results" not in receipt: allowed.add(row["receipt"])
        system = {
            "protocol": "repair-proposal/1",
            "instructions": "You are the improvement proposer, in a separate call from the diagnostic judge. Use the supplied validated diagnosis and bounded original evidence reads. Reuse existing types and relations. Repair one named function by composing the allowed operators. Return only JSON. Never include record IDs, concrete predicate values, Python or new operators. Missing evidence must produce needs_evidence; unsupported semantics must produce needs_capability. Rejected candidates do not become the parent.",
            "response_choices": [{"kind": "read", "artifact": "allowed SHA256", "offset": 0, "limit": 3000},
                                 {"kind": "entities", "type": "entity type or null", "offset": 0},
                                 {"kind": "relations", "identity": "existing entity ID", "direction": "out", "offset": 0},
                                 {"kind": "candidate", "candidate": "complete package object", "reason": "causal hypothesis"},
                                 {"kind": "needs_evidence", "reason": "missing observation"},
                                 {"kind": "needs_capability", "reason": "unsupported computation"}],
            "operators": {"lookup_entities": {"op": "lookup_entities", "type": list(TYPE_SLOTS)},
                          "filter_numeric": {"op": "filter_numeric", "input": "earlier node integer", "predicates": list(NUMERIC_SLOTS)},
                          "filter_property_categorical": {"op": "filter_property_categorical", "input": "earlier node integer", "where": list(WHERE_SLOTS)},
                          "filter_relation_connected": {"op": "filter_relation_connected", "input": "earlier node integer",
                              "anchors": "earlier node integer", "relation": "selector.related.relation_type",
                              "direction": "selector.related.direction"}},
            "max_nodes": MAX_NODES, "note": "Only the named function may change. Input/anchors refer to zero-based nodes. return is a node index.",
        }
        reads, receipts = [], []
        for call in range(self.max_calls):
            context = {"original_goal": packet["goal"], "system": system, "case": packet,
                       "parent": parent, "attempt": attempt, "past_attempts": history, "recent_reads": reads[-2:]}
            if self.diagnosis is not None: context["validated_judge_diagnosis"] = self.diagnosis
            encoded = json_bytes(context)
            if len(encoded) > 20000:
                return {"kind": "needs_evidence", "reason": "Pinned goal and evidence exceed proposer context budget", "evidence": receipts}
            call_dir = archive.root / "proposer" / str(uuid.uuid4())
            call_dir.mkdir(parents=True)
            input_ref = archive.put(context)
            with archive.db:
                archive.event("PROPOSER_CALL_STARTED", {"input": input_ref, "directory": str(call_dir.relative_to(archive.root)),
                                                        "provider": self.name, "command": self.command})
            stdin = b"" if any("{prompt}" in part for part in self.command) else encoded
            status = execute([part.replace("{prompt}", encoded.decode()) for part in self.command], stdin,
                             call_dir / "stdout.txt", timeout=self.timeout, max_output_bytes=65536,
                             cwd=call_dir, stderr_path=call_dir / "stderr.txt", env={**os.environ, "OLLAMA_NOHISTORY": "1"})
            raw = (call_dir / "stdout.txt").read_text(errors="replace") if (call_dir / "stdout.txt").exists() else ""
            receipt = archive.put({"input": input_ref, "execution": status, "output": raw,
                                   "provider": self.name, "call": call, "command": self.command})
            receipts.append(receipt)
            with archive.db: archive.event("PROPOSER_CALL_FINISHED", {"receipt": receipt})
            if self.name == "gemini" and (raw.lstrip().startswith("Opening authentication page") or status.get("stderr_code") == "UNSUPPORTED_CLIENT"):
                return {"kind": "needs_configuration", "reason": "AUTHENTICATION_OR_CLIENT_UNAVAILABLE", "evidence": receipts}
            if status["status"] != "COMPLETE":
                return {"kind": "unavailable", "reason": status["status"], "evidence": receipts}
            try:
                if self.name == "gemini":
                    envelope = parse_json(raw)
                    if envelope.get("error") or envelope.get("stats", {}).get("tools", {}).get("totalCalls", 0):
                        raise ValueError("CLI error or unexpected tool execution")
                    raw = envelope["response"]
                response = parse_json(raw)
                if not isinstance(response, dict): raise ValueError("Expected one JSON object")
                kind = response.get("kind")
                if kind == "entities" and set(response) == {"kind", "type", "offset"}:
                    page = archive.query_entities(packet["case_id"], entity_type=response["type"], offset=response["offset"], limit=10)
                    allowed.update(r["record_ref"] for r in page["records"])
                    reads.append(page)
                    with archive.db: archive.event("ENTITY_DISCOVERY", {"receipt": archive.put(page)})
                    continue
                if kind == "relations" and set(response) == {"kind", "identity", "direction", "offset"}:
                    page = archive.query_relations(packet["case_id"], response["identity"], direction=response["direction"], offset=response["offset"], limit=10)
                    reads.append(page)
                    with archive.db: archive.event("RELATION_DISCOVERY", {"receipt": archive.put(page)})
                    continue
                if kind == "read":
                    if set(response) != {"kind", "artifact", "offset", "limit"}: raise ValueError("Invalid read fields")
                    ref, offset, limit = response["artifact"], response["offset"], response["limit"]
                    if ref not in allowed or type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 3000:
                        raise ValueError("Read is outside allowed evidence or bounds")
                    text = json.dumps(archive.get(ref), ensure_ascii=False, sort_keys=True)
                    page = {"artifact": ref, "offset": offset, "content": text[offset:offset + limit],
                            "next_offset": offset + limit if offset + limit < len(text) else None, "total_chars": len(text)}
                    reads.append(page)
                    with archive.db: archive.event("EVIDENCE_READ", {"receipt": archive.put(page)})
                    continue
                if kind == "candidate" and set(response) == {"kind", "candidate", "reason"}:
                    response["evidence"] = receipts
                    return response
                if kind in {"needs_evidence", "needs_capability"} and set(response) == {"kind", "reason"}:
                    response["evidence"] = receipts
                    return response
                raise ValueError("Invalid proposer response")
            except (ValueError, TypeError, KeyError) as error:
                reads.append({"protocol_error": str(error)[:500]})
        return {"kind": "needs_evidence", "reason": "Proposer call budget exhausted", "evidence": receipts}


def make_packet(archive, case_id, data, parent, report):
    scope = data["before"]["scope"]
    discovery = archive.discover(scope)
    evidence = [archive.put(data["before"]), archive.put(report), archive.put(data["contract"])]
    evidence += [r["definition_ref"] for r in discovery["records"]]
    failed = [c["requirement_id"] for c in report["report"]["checks"] if c["value"] != "TRUE"]
    name = function_name(data["contract"])
    # Retrieval identity is exact and structural; it is not a claim about root cause.
    pattern = {"function": name, "requirements": failed,
               "predicate_fields": sorted(data["contract"]["selector"]["where"]),
               "related_fields": sorted(data["contract"]["selector"].get("related", {}).get("where", {}))}
    return {"case_id": case_id, "goal": data["contract"]["goal"], "function": name, "failed_requirements": failed,
            "gap_route": "COMPOSITION_GAP_HYPOTHESIS",
            "pattern_key": archive.put(pattern), "evidence_refs": evidence, "discovery": discovery,
            "parent": parent, "scope": scope}

"""A serial ReAct runner with trusted kernel dispatch and independent completion."""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from .process import execute
from .provenance import snapshot_sources
from .store import IntegrityError, RunStore, json_bytes
from .policy import legacy_policy, validate_policy, rank_tools, instruction, ranking
from .working import WorkingState

ROOT = Path(__file__).resolve().parents[1]


def parse_json(text: str) -> object:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"Non-finite JSON value: {value}")

    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = "\n".join(text.splitlines()[1:-1])
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def error_details(error: Exception) -> dict:
    details = {"error_type": type(error).__name__, "message": str(error)[:2000]}
    if isinstance(error, ValidationError):
        details.update({"instance_path": list(error.absolute_path), "schema_path": list(error.absolute_schema_path)})
        kind = error.instance.get("kind") if isinstance(error.instance, dict) else None
        branch = {"act": 0, "revisit": 1, "finish": 2, "request_input": 3}.get(kind)
        children = [e for e in error.context if e.schema_path and e.schema_path[0] == branch]
        details["issues"] = [{"path": list(e.absolute_path), "message": e.message[:400]} for e in children[:6]]
    return details


def context_bytes(value: dict) -> bytes:
    # Preserve insertion order: pinned instructions and goal precede history.
    return (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode()


@dataclass(frozen=True)
class Config:
    max_steps: int = 12
    max_tool_attempts: int = 24
    deadline_seconds: float = 600
    model_timeout_seconds: float = 180
    max_context_chars: int = 16000
    compaction_trigger_fraction: float = 0.8
    retain_recent_steps: int = 2
    inline_output_chars: int = 2000
    max_process_output_bytes: int = 262144
    max_stagnant_steps: int = 0

    def validate(self):
        for name in ("max_steps", "max_tool_attempts", "deadline_seconds", "model_timeout_seconds",
                     "max_context_chars", "inline_output_chars", "max_process_output_bytes"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.retain_recent_steps < 0 or not 0 < self.compaction_trigger_fraction <= 1:
            raise ValueError("Invalid compaction settings")
        if type(self.max_stagnant_steps) is not int or self.max_stagnant_steps < 0:
            raise ValueError("Invalid progress budget")


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    schema: dict
    command: list[str]
    output_schema: dict
    timeout_seconds: float = 30
    effect: str = "READ"
    bootstrap: bool = False


@dataclass(frozen=True)
class KernelHandoff:
    """A trusted kernel yields unresolved work to ReAct within the same episode."""
    reason: str
    pending_work: str
    evidence_ids: tuple[str, ...] = ()


READ_SCHEMA = {"type": "object", "properties": {
    "output_id": {"type": "string", "format": "uuid"},
    "json_pointer": {"type": ["string", "null"]},
    "start": {"type": "integer", "minimum": 0},
    "max_chars": {"type": "integer", "minimum": 1, "maximum": 2048}},
    "required": ["output_id"], "additionalProperties": False}
LIST_SCHEMA = {"type": "object", "properties": {
    "offset": {"type": "integer", "minimum": 0},
    "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
    "additionalProperties": False}
WORKING_SCHEMA = {"type": "object", "properties": {**LIST_SCHEMA["properties"],
    "kind": {"enum": ["tools", "schemas", "entities", "relations", "state", "evidence", "effects", "pending", "bindings", "pages"]}}, "additionalProperties": False}


class ReactLoop:
    def __init__(self, *, store: RunStore, task: str, constraints: list[str],
                 model_command: list[str], tools: list[Tool],
                 verifier: Callable[[dict, list[dict]], tuple[bool | None, str]] | None,
                 config: Config = Config(), provider: str = "text", model_info: dict | None = None,
                 system_instructions: str | None = None, benchmark_adapter: dict | None = None,
                 kernel_policy: Callable[[dict], dict | KernelHandoff] | None = None,
                 kernel_version: str | None = None, check_on_exit: bool = False, check_after_writes: bool = False,
                 execution_policy=None, policy_version=None, argument_guard=None):
        config.validate()
        if verifier is not None and getattr(verifier, "bound_goal", task) != task:
            raise ValueError("Verifier completion contract is bound to a different original goal")
        self.store, self.task, self.constraints = store, task, constraints
        self.execution_policy = validate_policy(execution_policy or legacy_policy())
        self.policy_version = policy_version
        self.argument_guard = argument_guard
        self.working = WorkingState(store)
        self.discovery_started = False
        self.discovery_pending = []
        self.cycle_recovered = False
        self.command, self.verifier, self.config, self.provider = model_command, verifier, config, provider
        self.tools = {tool.name: tool for tool in tools}
        if len(self.tools) != len(tools) or {"read_output", "list_outputs", "read_working"} & self.tools.keys():
            raise ValueError("Tool names must be unique and cannot replace output-access tools")
        for tool in tools:
            Draft202012Validator.check_schema(tool.schema)
            Draft202012Validator.check_schema(tool.output_schema)
            if tool.effect not in {"READ", "WRITE"} or tool.timeout_seconds <= 0:
                raise ValueError("Invalid tool effect/timeout")
            if tool.bootstrap and (tool.effect != "READ" or not Draft202012Validator(tool.schema).is_valid({})):
                raise ValueError("A bootstrap tool must be a read-only state observation accepting {}")
        self.system = system_instructions or (ROOT / "prompts/react_system.txt").read_text()
        self.contract_schema = json.loads((ROOT / "docs/system/contracts.schema.json").read_text())
        self.validator = Draft202012Validator(self.contract_schema, format_checker=FormatChecker())
        self.history: list[dict] = []
        self.successful_results: list[dict] = []
        self.compacted_through = 0
        self.compactions = 0
        self.tool_attempts = 0
        self.model_info = model_info or {"resolved_model": None}
        self.benchmark_adapter = benchmark_adapter
        if kernel_policy is not None and not kernel_version:
            raise ValueError("A kernel policy requires a recorded kernel version")
        self.kernel_policy, self.kernel_version = kernel_policy, kernel_version
        self.mode = "kernel" if kernel_policy else "react"
        self.handoff = None
        self.check_on_exit = check_on_exit
        self.check_after_writes = check_after_writes
        self.last_action_key = None

    def verify_finish(self, proposal, step, model_ref, rejection_code="FINISH_REJECTED"):
        verification_input_ref = self.store.write("inputs", {"proposal": proposal,
            "successful_results": self.successful_results}, step)
        self.store.event("verification_started", step, verification_input_ref=verification_input_ref)
        started = time.monotonic()
        try:
            passed, explanation = (None, "No independent verifier configured") if self.verifier is None else self.verifier(proposal, self.successful_results)
            if type(passed) not in (bool, type(None)) or not isinstance(explanation, str):
                raise TypeError("Verifier must return (bool | None, str)")
        except Exception as error:
            self.store.event("verification_failed", step, verification_input_ref=verification_input_ref,
                             details=error_details(error))
            raise
        verification_ref = self.store.write("observations", {"passed": passed, "explanation": explanation,
            "duration_ms": round((time.monotonic() - started) * 1000)}, step)
        self.store.event("finish_verified", step, verification_input_ref=verification_input_ref,
                         verification_ref=verification_ref)
        if passed is True: return "VERIFIED_SUCCESS"
        if passed is None: return "UNVERIFIED_FINISH"
        self.observation(step, "finish" if rejection_code == "FINISH_REJECTED" else "completion_check", model_ref,
                         {"code": rejection_code, "message": explanation[:1000]})
        return None

    def catalog(self) -> list[dict]:
        catalog = [{"name": t.name, "description": t.description, "arguments": t.schema, "effect": t.effect}
                for t in self.tools.values()] + [
            {"name": "read_output", "description": "Reread an original output by ID, optionally at a JSON pointer or character offset.", "arguments": READ_SCHEMA},
            {"name": "list_outputs", "description": "Page through this run's visible saved outputs.", "arguments": LIST_SCHEMA}]
        if instruction(self.execution_policy, "context", "bound_history"):
            catalog.append({"name": "read_working", "description": "Retrieve observed records, bindings, tool schemas, pending work or evidence references from durable working state.", "arguments": WORKING_SCHEMA})
        return catalog

    def context(self, step: int, request_id: str, cutoff: int) -> dict:
        inspected = {}
        for result in self.successful_results:
            if result["action"] == "inspect_tool" and isinstance(result["result"].get("tool"), dict):
                tool = result["result"]["tool"]
                inspected.pop(tool["name"], None)
                inspected[tool["name"]] = {"name": tool["name"], "inputSchema": tool["inputSchema"],
                                           "description": tool.get("description", "")[:220]}
        indexed = self.history[:cutoff]
        history_rule = instruction(self.execution_policy, "context", "bound_history")
        if history_rule: indexed = indexed[-history_rule["index"]:] if history_rule["index"] else []
        memory = [{"step": r["step"], "action": r["action"], "outcome": r["observation"]["code"],
                   "model_output_id": r["model_output_id"],
                   "output_id": r["observation"].get("output_id"),
                   "observation_id": r["observation_id"]} for r in indexed]
        selected_tools = list(inspected.values())[-6:]
        if ranking(self.execution_policy) != "legacy":
            limit = (instruction(self.execution_policy, "discovery", "inspect_shortlist") or {"limit": 3})["limit"]
            selected_tools = rank_tools(inspected.values(), self.task, ranking(self.execution_policy))[:limit]
            if inspected:
                newest = next(reversed(inspected.values()))
                if newest["name"] not in {t["name"] for t in selected_tools}:
                    selected_tools = selected_tools[:limit - 1] + [newest]
        context = {
            "system_instructions": self.system,
            "task": {"objective": self.task, "constraints": self.constraints},
            "execution_mode": self.mode, "kernel_handoff": self.handoff,
            "turn": {"step": step, "request_id": request_id,
                     "steps_remaining_including_this": self.config.max_steps - step + 1,
                     "tool_attempts_remaining": self.config.max_tool_attempts - self.tool_attempts},
            "protocol": {
                "required_fields": {
                    "act": self.contract_schema["$defs"]["ActProposal"]["required"],
                    "finish": self.contract_schema["$defs"]["FinishProposal"]["required"]},
                "artifact_refs_rule": "For this component, use artifact_refs: [] in finish. The runtime attaches original evidence. Do not put UUID strings in artifact_refs.",
                "output_examples": [{"kind": "act", "request_id": request_id, "action_id": "REGISTERED_NAME",
                        "arguments": {}, "evidence_ids": [], "reason": "brief reason, at most 300 characters"},
                    {"kind": "finish", "request_id": request_id, "answer": "answer",
                     "artifact_refs": [], "claimed_requirement_ids": ["task"]}],
                "note": "Return ONE flat object like ONE example, never the examples list or a wrapper. The first top-level key is kind. Use a registered action name and the current request_id."},
            "tools": self.catalog(), "inspected_tools": selected_tools, "compacted_steps": memory,
            "recent_steps": self.history[cutoff:],
        }
        if self.execution_policy != legacy_policy():
            context["policy_version"] = self.policy_version
        if history_rule:
            carry = instruction(self.execution_policy, "context", "carry_state")
            context["working_state"] = self.working.view(fields=carry["fields"] if carry else [])
            context["context_limit_chars"] = self.config.max_context_chars
        return context

    def prepare_prompt(self, step: int, request_id: str) -> bytes:
        history_rule = instruction(self.execution_policy, "context", "bound_history")
        if history_rule:
            from .ollama import payload, configuration
            recent = self.config.retain_recent_steps if self.execution_policy["context"] == "working" else history_rule["recent"]
            cutoff = max(0, len(self.history) - recent)
            while True:
                context = self.context(step, request_id, cutoff)
                # Measure exactly the provider-facing request, including schemas.
                measured = payload(context, configuration()) if self.provider == "ollama" else context
                size = len(json.dumps(measured, ensure_ascii=False, allow_nan=False))
                if size <= self.config.max_context_chars: break
                if cutoff < len(self.history): cutoff += 1; continue
                self.store.event("context_overflow", step, actual_chars=size, maximum_chars=self.config.max_context_chars)
                raise OverflowError("Pinned provider request exceeds context cap")
            if cutoff > self.compacted_through:
                self.compactions += 1
                before_ref = self.store.write("compactions", context_bytes(self.context(step, request_id, self.compacted_through)), step, raw=True)
                after_ref = self.store.write("compactions", context_bytes(context), step, raw=True)
                self.store.event("context_compacted", step, old_cutoff=self.compacted_through, new_cutoff=cutoff,
                                 before_ref=before_ref, after_ref=after_ref, after_chars=size,
                                 policy="bounded_working_v1", original_outputs_deleted=0)
            self.compacted_through = cutoff
            return context_bytes(context)
        before = self.context(step, request_id, self.compacted_through)
        prompt = context_bytes(before)
        trigger = self.config.max_context_chars * self.config.compaction_trigger_fraction
        if len(prompt.decode()) > trigger and self.history:
            cutoff = max(self.compacted_through, len(self.history) - self.config.retain_recent_steps)
            after = self.context(step, request_id, cutoff)
            while len(context_bytes(after).decode()) > self.config.max_context_chars and cutoff < len(self.history):
                cutoff += 1
                after = self.context(step, request_id, cutoff)
            if cutoff > self.compacted_through:
                before_ref = self.store.write("compactions", context_bytes(before), step, raw=True)
                after_ref = self.store.write("compactions", context_bytes(after), step, raw=True)
                # Verify referenced originals before using a compacted context.
                for item in after["compacted_steps"]:
                    for key in ("model_output_id", "output_id", "observation_id"):
                        if item[key]:
                            self.store.get(item[key])
                self.store.event("context_compacted", step, before_ref=before_ref, after_ref=after_ref,
                                 old_cutoff=self.compacted_through, new_cutoff=cutoff,
                                 before_chars=len(context_bytes(before).decode()), after_chars=len(context_bytes(after).decode()),
                                 policy="deterministic_action_index_v1", tool_attempts=self.tool_attempts,
                                 original_outputs_deleted=0)
                self.compacted_through = cutoff
                self.compactions += 1
                prompt = context_bytes(after)
        if len(prompt.decode()) > self.config.max_context_chars:
            self.store.event("context_overflow", step, actual_chars=len(prompt.decode()),
                             maximum_chars=self.config.max_context_chars)
            raise OverflowError("Pinned context and evidence index do not fit")
        return prompt

    def observation(self, step: int, action: str, model_ref: dict, value: dict) -> None:
        observation_ref = self.store.write("observations", value, step, visible=True)
        self.store.event("observation_prepared", step, observation_ref=observation_ref)
        self.history.append({"step": step, "action": action, "model_output_id": model_ref["id"] if model_ref else None,
                             "observation_id": observation_ref["id"], "observation": value,
                             "action_key": self.last_action_key if action in self.tools or action in {"read_output", "list_outputs", "read_working"} else action})

    def policy_action(self, step, request_id):
        if self.execution_policy["discovery"] == "legacy": return None
        if "discover_tools" not in self.tools:
            if self.discovery_started or not instruction(self.execution_policy, "discovery", "observe_declared_state"): return None
            self.discovery_started = True
            readers = sorted((t for t in self.tools.values() if t.bootstrap), key=lambda t: t.name)
            if not readers: return None
            name, args = readers[0].name, {}
        elif not self.discovery_started:
            self.discovery_started = True
            rank = ranking(self.execution_policy)
            if rank == "legacy": return None
            shortlist = instruction(self.execution_policy, "discovery", "inspect_shortlist")
            name, args = "discover_tools", {"query": self.task[:200], "limit": shortlist["limit"] if shortlist else 3, "strategy": rank}
        elif self.discovery_pending:
            name, args = "inspect_tool", {"name": self.discovery_pending.pop(0)}
        else: return None
        return {"kind": "act", "request_id": request_id, "action_id": name, "arguments": args,
                "evidence_ids": [], "reason": "Registered discovery policy: inspect ranked APIs or observe the declared state reader"}

    def progress_stalled(self):
        return bool(instruction(self.execution_policy, "context", "detect_stagnation")) and self.working.stagnant >= 3

    def argument_rejection(self, name, message, step, *, output_id=None):
        exhausted = False
        if self.execution_policy["binding"] != "legacy":
            exhausted = self.working.reject(name, message, None, step)
        self.store.event("argument_correction" if output_id else "action_denied", step, action=name, reason="ARGUMENT_SCHEMA_INVALID", message=message)
        return {"code": "ARGUMENT_SCHEMA_INVALID", "message": message, **({"output_id": output_id} if output_id else {}),
                "repair_attempts_remaining": max(0, 3 - self.working.failures[name])}, "ARGUMENT_REPAIR_EXHAUSTED" if exhausted else None

    def read_output(self, arguments: dict) -> dict:
        data = self.store.get(arguments["output_id"], actor=True).decode()
        pointer = arguments.get("json_pointer")
        if pointer is not None:
            value = parse_json(data)
            if pointer and not pointer.startswith("/"):
                raise ValueError("JSON pointer must start with /")
            for part in pointer.split("/")[1:]:
                part = part.replace("~1", "/").replace("~0", "~")
                if isinstance(value, dict) and part not in value:
                    raise ValueError("JSON pointer field " + repr(part) + " is absent; available fields: " + ", ".join(list(value)[:20]))
                value = value[int(part)] if isinstance(value, list) else value[part]
            data = json.dumps(value, ensure_ascii=False, allow_nan=False)
        start, maximum = arguments.get("start", 0), arguments.get("max_chars", 1024)
        return {"source_output_id": arguments["output_id"], "json_pointer": pointer,
                "start": start, "content": data[start:start + maximum],
                "next_start": start + maximum if start + maximum < len(data) else None,
                "total_chars": len(data)}

    def act(self, proposal: dict, step: int, deadline: float) -> tuple[dict, str | None]:
        name, arguments = proposal["action_id"], proposal["arguments"]
        self.last_action_key = json.dumps([name, arguments], sort_keys=True)
        if time.monotonic() >= deadline:
            self.store.event("action_denied", step, action=name, reason="DEADLINE")
            return {"code": "DEADLINE"}, "DEADLINE"
        if self.tool_attempts >= self.config.max_tool_attempts:
            return {"code": "TOOL_BUDGET_EXHAUSTED"}, "BUDGET_EXHAUSTED"
        builtins = {"read_output", "list_outputs"} | ({"read_working"} if instruction(self.execution_policy, "context", "bound_history") else set())
        if name not in self.tools and name not in builtins:
            self.store.event("action_denied", step, action=name, reason="UNKNOWN_TOOL")
            return {"code": "UNKNOWN_TOOL", "message": "Choose a registered tool."}, None
        schema = READ_SCHEMA if name == "read_output" else LIST_SCHEMA if name == "list_outputs" else WORKING_SCHEMA if name == "read_working" else self.tools[name].schema
        errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(arguments))
        if errors:
            message = errors[0].message[:500] + "; expected fields: " + ", ".join(schema.get("properties", {}))
            if not schema.get("properties"): message += "none; supply {}"
            return self.argument_rejection(name, message, step)
        if self.execution_policy["binding"] != "legacy" and self.mode == "react":
            native = arguments.get("name") if name == "call_tool" else name
            args = arguments.get("arguments", {}) if name == "call_tool" else arguments
            inspected = next((r["result"]["tool"] for r in reversed(self.successful_results)
                              if r["action"] == "inspect_tool" and r["result"].get("tool", {}).get("name") == native), None)
            if name == "call_tool":
                if inspected is None: return self.argument_rejection(native, "Inspect this API's schema first", step)
                errs = list(Draft202012Validator({**inspected["inputSchema"], "additionalProperties": False}).iter_errors(args))
                if errs: return self.argument_rejection(native, errs[0].message[:500] + "; fields: " + ", ".join(inspected["inputSchema"].get("properties", {})), step)
            mutation = name in self.tools and self.tools[name].effect == "WRITE"
            if name == "call_tool" and native.split("__")[-1].split("_")[0] in {"get", "show", "list", "search", "find", "read"}: mutation = False
            error = self.working.binding_error(native, args, mutation=mutation) if instruction(self.execution_policy, "binding", "require_observed_ids") else None
            if error: return self.argument_rejection(native, error, step)
            if mutation and instruction(self.execution_policy, "binding", "check_bound_update") and self.argument_guard is not None:
                error = self.argument_guard(native, args)
                if error: return self.argument_rejection(native, error, step)
        self.tool_attempts += 1
        request_ref = self.store.write("inputs", {"action": name, "arguments": arguments}, step)
        stdin_ref = self.store.write("inputs", json_bytes(arguments), step, raw=True)
        self.store.event("action_allowed", step, action=name, request_ref=request_ref,
                         tool_attempt=self.tool_attempts, basis="registered trusted tool and argument schema")
        stderr_ref = None
        if name in {"read_output", "list_outputs", "read_working"}:
            self.store.event("dispatch_started", step, action=name, request_ref=request_ref,
                             stdin_ref=stdin_ref, implementation="local_builtin")
            try:
                if name == "read_working": result = self.working.page(**arguments)
                elif name == "read_output":
                    result = self.read_output(arguments)
                else:
                    outputs = self.store.visible_outputs()
                    offset, limit = arguments.get("offset", 0), arguments.get("limit", 10)
                    result = {"outputs": outputs[offset:offset + limit],
                              "next_offset": offset + limit if offset + limit < len(outputs) else None}
                output_ref = self.store.write("tools", result, step, visible=True)
                status = {"status": "COMPLETE"}
            except (ValueError, KeyError, IndexError, TypeError, UnicodeError) as error:
                result = {"error": type(error).__name__, "message": str(error)[:300]}
                output_ref = self.store.write("tools", result, step, visible=True)
                status = {"status": "READ_ERROR"}
        else:
            tool = self.tools[name]
            output_id, output_path = self.store.reserve("tools", step)
            stderr_id, stderr_path = self.store.reserve("diagnostics", step)
            self.store.event("dispatch_started", step, action=name, request_ref=request_ref,
                             stdin_ref=stdin_ref,
                             pending_output_id=output_id, pending_stderr_id=stderr_id,
                             command=tool.command, cwd=str(ROOT), effect=tool.effect)
            status = execute(tool.command, json_bytes(arguments), output_path,
                             timeout=min(tool.timeout_seconds, max(0.001, deadline - time.monotonic())),
                             max_output_bytes=self.config.max_process_output_bytes, cwd=ROOT, stderr_path=stderr_path)
            output_ref = self.store.publish(output_id, output_path, "tools", step, visible=True,
                                            complete=status["status"] not in {"TIMEOUT", "OUTPUT_LIMIT", "CANCELLED"})
            stderr_ref = self.store.publish(stderr_id, stderr_path, "diagnostics", step,
                                            complete=status["status"] not in {"TIMEOUT", "OUTPUT_LIMIT", "CANCELLED"})
            result = None
            if status["status"] == "COMPLETE":
                try:
                    result = parse_json(self.store.get(output_id).decode())
                    Draft202012Validator(tool.output_schema).validate(result)
                    if result.get("session_error"):
                        status = {**status, "status": "SESSION_ERROR"}
                except (ValueError, UnicodeError, ValidationError) as error:
                    status = {**status, "status": "OUTPUT_CONTRACT_ERROR", "error": error_details(error)}
        self.store.event("operation_result", step, action=name, request_ref=request_ref,
                         stdin_ref=stdin_ref, output_ref=output_ref, stderr_ref=stderr_ref, execution=status)
        if status["status"] == "COMPLETE":
            self.successful_results.append({"action": name, "arguments": arguments, "result": result,
                                            "output_id": output_ref["id"], "step": step})
            self.working.observe(name, arguments, result, output_ref["id"], step,
                                 effect=name in self.tools and self.tools[name].effect == "WRITE")
            shortlist = instruction(self.execution_policy, "discovery", "inspect_shortlist")
            if name == "discover_tools" and arguments.get("strategy", "legacy") != "legacy" and shortlist:
                self.discovery_pending = [t["name"] for t in result.get("tools", [])][:shortlist["limit"]]
            if result.get("rejected") and self.execution_policy["binding"] != "legacy":
                return self.argument_rejection(arguments.get("name", name), result.get("message", "Rejected before dispatch"), step, output_id=output_ref["id"])
            self.working.resolve(arguments.get("name", name))
        elif status["status"] == "READ_ERROR":
            self.working.observe(name, arguments, result, output_ref["id"], step)
            if self.execution_policy["binding"] != "legacy":
                return self.argument_rejection(name, result["message"], step, output_id=output_ref["id"])
        unknown_write = name in self.tools and self.tools[name].effect == "WRITE" and status["status"] != "COMPLETE"
        raw = self.store.get(output_ref["id"]).decode(errors="replace")
        observation = {"code": "OK" if status["status"] == "COMPLETE" else status["status"],
                       "output_id": output_ref["id"], "preview": raw[:self.config.inline_output_chars],
                       "truncated_in_context": len(raw) > self.config.inline_output_chars,
                       "effect_uncertain": unknown_write}
        return observation, "UNKNOWN_TOOL_OUTCOME" if unknown_write else None

    def run(self) -> dict:
        deadline = time.monotonic() + self.config.deadline_seconds
        source_bundle_ref = snapshot_sources(self.store, ROOT, self.tools.values(), self.verifier)
        manifest_ref = self.store.write("metadata", {"trace_version": "react-component-0.1",
            "task": self.task, "constraints": self.constraints, "config": asdict(self.config),
            "tools": self.catalog(), "tool_implementations": [asdict(t) for t in self.tools.values()],
            "model": self.model_info, "model_command_template": self.command, "cwd": str(ROOT),
            "source_bundle_ref": source_bundle_ref,
            "context_capture": "CLI_INPUT_ONLY", "system_delivery": "pinned text in CLI input",
            "backend_system_role_verified": False, "usage": "UNAVAILABLE_UNLESS_CLI_REPORTS",
            "benchmark_adapter": self.benchmark_adapter, "kernel_version": self.kernel_version,
            "execution_policy": self.execution_policy, "policy_version": self.policy_version,
            "argument_guard": self.argument_guard is not None,
            "verifier_binding_ref": getattr(self.verifier, "binding_ref", None)})
        system_ref = self.store.write("metadata", self.system, raw=True)
        self.store.event("episode_started", manifest_ref=manifest_ref, system_ref=system_ref,
                         source_bundle_ref=source_bundle_ref)
        terminal, answer, step = "BUDGET_EXHAUSTED", None, 0
        try:
            for step in range(1, self.config.max_steps + 1):
                if time.monotonic() >= deadline:
                    terminal = "DEADLINE"
                    break
                window = self.config.max_stagnant_steps
                if self.mode == "react" and self.progress_stalled():
                    if not self.cycle_recovered and self.execution_policy["discovery"] != "legacy":
                        self.cycle_recovered = True
                        self.discovery_started = False
                        self.discovery_pending = []
                        self.working.stagnant = 0
                        self.store.event("policy_recovery", step, component="context", reason="REPEATED_EVIDENCE", action="rerank_catalogue")
                    else:
                        self.store.event("progress_stalled", step, reason="No new evidence across consecutive actions", threshold=3,
                                         repeated_steps=[r["step"] for r in self.history[-3:]])
                        terminal = "NO_PROGRESS"
                        break
                if self.mode == "react" and window and len(self.history) >= window:
                    recent = self.history[-window:]
                    signatures = {(r["action_key"], r["observation"]["code"], r["observation"].get("preview")) for r in recent}
                    if len(signatures) == 1:
                        self.store.event("progress_stalled", step, repeated_steps=[r["step"] for r in recent],
                                         reason="Repeated identical observable outcomes", threshold=window)
                        terminal = "NO_PROGRESS"
                        break
                request_id = str(uuid.uuid4())
                if self.mode == "kernel":
                    kernel_input = self.context(step, request_id, self.compacted_through)
                    input_ref = self.store.write("inputs", kernel_input, step)
                    self.store.event("kernel_started", step, request_id=request_id, input_ref=input_ref,
                                     kernel_version=self.kernel_version)
                    proposal = self.kernel_policy(kernel_input)
                    value = asdict(proposal) if isinstance(proposal, KernelHandoff) else proposal
                    model_ref = self.store.write("model", value, step, visible=True)
                    self.store.event("kernel_result", step, request_id=request_id, input_ref=input_ref,
                                     output_ref=model_ref, kernel_version=self.kernel_version)
                    if isinstance(proposal, KernelHandoff):
                        if proposal.reason not in {"CAPABILITY_GAP", "NO_PROGRESS", "EVIDENCE_GAP"}:
                            raise ValueError("Invalid kernel handoff reason")
                        if not proposal.pending_work or len(proposal.pending_work) > 1000:
                            raise ValueError("Kernel handoff must identify bounded unresolved work")
                        for evidence_id in proposal.evidence_ids:
                            self.store.get(evidence_id, actor=True)
                        self.handoff = {**value, "step": step, "kernel_version": self.kernel_version}
                        self.mode = "react"
                        self.store.event("kernel_handoff", step, handoff=self.handoff,
                                         tool_attempts=self.tool_attempts,
                                         deadline_remaining_seconds=max(0, deadline - time.monotonic()))
                        self.observation(step, "kernel_handoff", model_ref,
                                         {"code": "KERNEL_HANDOFF", "handoff": self.handoff})
                        # The kernel decision consumes this step. No state,
                        # effects, evidence, deadline or budgets are reset.
                        continue
                    self.validator.validate(proposal)
                    if proposal["request_id"] != request_id:
                        raise ValueError("Kernel request_id does not match this turn")
                    proposal_ref = self.store.write("observations", proposal, step, visible=True)
                    self.store.event("action_proposed", step, response_ref=model_ref,
                                     proposal_ref=proposal_ref, producer="kernel")
                    if proposal["kind"] == "finish":
                        status = self.verify_finish(proposal, step, model_ref)
                        if status:
                            terminal, answer = status, proposal["answer"]
                            break
                        continue
                    if proposal["kind"] != "act":
                        raise ValueError("Kernel policy supports act, checked finish or explicit handoff only")
                    observation, stop = self.act(proposal, step, deadline)
                    self.observation(step, proposal["action_id"], model_ref, observation)
                    if stop:
                        terminal = stop
                        break
                    continue
                automatic = self.policy_action(step, request_id)
                if automatic is not None:
                    ref = self.store.write("model", automatic, step, visible=True)
                    self.store.event("policy_action", step, policy_version=self.policy_version, proposal_ref=ref)
                    observation, stop = self.act(automatic, step, deadline)
                    self.observation(step, automatic["action_id"], ref, observation)
                    if stop: terminal = stop; break
                    continue
                prompt = self.prepare_prompt(step, request_id)
                input_ref = self.store.write("inputs", prompt, step, raw=True)
                output_id, output_path = self.store.reserve("model", step)
                stderr_id, stderr_path = self.store.reserve("diagnostics", step)
                self.store.event("model_started", step, request_id=request_id, input_ref=input_ref,
                                 pending_output_id=output_id, pending_stderr_id=stderr_id,
                                 pending_output_path=str(output_path.relative_to(self.store.root)),
                                 pending_stderr_path=str(stderr_path.relative_to(self.store.root)),
                                 tool_attempts=self.tool_attempts, deadline_remaining_seconds=max(0, deadline - time.monotonic()))
                command = [part.replace("{prompt}", prompt.decode()) for part in self.command]
                status = execute(command, prompt, output_path,
                                 timeout=min(self.config.model_timeout_seconds, max(0.001, deadline - time.monotonic())),
                                 max_output_bytes=self.config.max_process_output_bytes, cwd=ROOT,
                                 stderr_path=stderr_path, env={**os.environ, "OLLAMA_NOHISTORY": "1"})
                model_ref = self.store.publish(output_id, output_path, "model", step, visible=True,
                                               complete=status["status"] not in {"TIMEOUT", "OUTPUT_LIMIT", "CANCELLED"})
                stderr_ref = self.store.publish(stderr_id, stderr_path, "diagnostics", step,
                                               complete=status["status"] not in {"TIMEOUT", "OUTPUT_LIMIT", "CANCELLED"})
                self.store.event("model_result", step, request_id=request_id, input_ref=input_ref,
                                 output_ref=model_ref, stderr_ref=stderr_ref, execution=status,
                                 usage_status="UNAVAILABLE_UNLESS_PRESENT_IN_RAW_CLI_OUTPUT")
                if status["status"] != "COMPLETE":
                    terminal = "MODEL_ERROR"
                    break
                proposal = None
                try:
                    response = self.store.get(output_id).decode()
                    if self.provider == "gemini":
                        envelope = parse_json(response)
                        if envelope.get("error") or envelope.get("stats", {}).get("tools", {}).get("totalCalls", 0):
                            raise ValueError("CLI reported an error or unexpected internal tool execution")
                        response = envelope["response"]
                    response_ref = self.store.write("model", response, step, raw=True, visible=True)
                    proposal = parse_json(response)
                    self.validator.validate(proposal)
                    if proposal["request_id"] != request_id:
                        raise ValueError("Proposal request_id does not match this turn")
                    proposal_ref = self.store.write("observations", proposal, step, visible=True)
                    self.store.event("action_proposed", step, response_ref=response_ref, proposal_ref=proposal_ref)
                except (ValueError, UnicodeError, KeyError, TypeError, AttributeError, ValidationError) as error:
                    self.store.event("proposal_invalid", step, output_ref=model_ref, details=error_details(error))
                    correction = ""
                    issues = error_details(error).get("issues", [])
                    if issues:
                        correction = " Validation issues: " + json.dumps(issues, ensure_ascii=False)
                    if isinstance(proposal, dict) and proposal.get("kind") in {"act", "finish"}:
                        name = "ActProposal" if proposal["kind"] == "act" else "FinishProposal"
                        required = self.contract_schema["$defs"][name]["required"]
                        missing = [key for key in required if key not in proposal]
                        if missing:
                            correction += f" Missing required fields: {', '.join(missing)}. Empty evidence_ids/artifact_refs are allowed but must be present."
                    self.observation(step, "invalid", model_ref, {"code": "SCHEMA_INVALID", "message":
                        "Return one flat action object with kind at the top level, using the CURRENT request_id. "
                        "Do not wrap the object under act/finish/response/action or return a list. "
                        "Copy ALL fields from one protocol example and supply real arguments." + correction})
                    continue
                if proposal["kind"] == "act":
                    observation, stop = self.act(proposal, step, deadline)
                    self.observation(step, proposal["action_id"], model_ref, observation)
                    if stop:
                        terminal = stop
                        break
                    if self.check_after_writes and observation["code"] == "OK" and proposal["action_id"] in self.tools and self.tools[proposal["action_id"]].effect == "WRITE":
                        self.store.event("postcondition_assessment", step, action=proposal["action_id"], trigger="after_write")
                        checked = {"kind": "finish", "request_id": request_id, "answer": "Requested state independently verified",
                                   "artifact_refs": [], "claimed_requirement_ids": ["task"]}
                        status = self.verify_finish(checked, step, model_ref, rejection_code="POSTCONDITION_PENDING")
                        if status:
                            terminal, answer = status, checked["answer"]
                            break
                elif proposal["kind"] == "finish":
                    status = self.verify_finish(proposal, step, model_ref)
                    if status:
                        terminal, answer = status, proposal["answer"]
                        break
                elif proposal["kind"] == "request_input":
                    self.observation(step, "request_input", model_ref, {"code": "INPUT_UNAVAILABLE", "message": "No interactive input channel is attached."})
                else:
                    self.observation(step, "revisit", model_ref, {"code": "USE_READ_OUTPUT", "message": "Use a saved output ID with read_output or find it through list_outputs."})
        except OverflowError:
            terminal = "CONTEXT_OVERFLOW"
        except IntegrityError as error:
            terminal = "INTEGRITY_FAILURE"
            self.store.event("integrity_failure", step, message=str(error))
        except Exception as error:
            terminal = "RUNTIME_ERROR"
            error_ref = self.store.write("diagnostics", traceback.format_exc(), step, raw=True)
            self.store.event("runtime_error", step, details=error_details(error), error_ref=error_ref)
        if self.check_on_exit and self.verifier is not None and terminal != "VERIFIED_SUCCESS":
            # Record current state even when the actor never submits finish.
            # Preserve the stop reason; a readback is not a retry of any write.
            try:
                self.verify_finish({"kind": "finish", "request_id": str(uuid.uuid4()), "answer": "Terminal assessment",
                                    "artifact_refs": [], "claimed_requirement_ids": ["task"]}, step, None)
            except Exception:
                pass  # verify_finish retained the paired failure receipt.
        result = {"status": terminal, "answer": answer, "steps": step,
                  "tool_attempts": self.tool_attempts, "compactions": self.compactions,
                  "kernel_version": self.kernel_version, "kernel_handoff": self.handoff,
                  "policy_version": self.policy_version,
                  "benchmark_result": None, "run_directory": str(self.store.root)}
        result_ref = self.store.write("results", result, step)
        self.store.event("episode_finished", step, result_ref=result_ref, status=terminal)
        result["judge_packet"] = self.store.export_judge_packet()
        return result

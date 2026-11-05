"""Budgeted Gemini CLI calls with actual receipts and exact request reuse."""

from __future__ import annotations

import fcntl
import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import jsonschema
from langsmith import traceable

from oak.gemini_runtime import (
    LAUNCH_PROMPT,
    POLICY,
    cli_identity,
    configured_project,
    prepare_invocation,
    runtime_settings,
)
from oak.store import Store, canonical

PROJECT = Path(__file__).resolve().parents[2]

_CREDENTIAL_KEY = (
    r"(?:refresh[_-]?token|access[_-]?token|id[_-]?token|client[_-]?secret|"
    r"client[_-]?id|api[_-]?key|password|private[_-]?key|"
    r"proxy[_-]?authorization|authorization|token)"
)
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?P<prefix>(?<![\w-])[\"']?_?"
    + _CREDENTIAL_KEY
    + r"[\"']?\s*(?:=>|[:=])\s*)(?P<value>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s,;&\"'{}\[\]]+)",
    re.IGNORECASE,
)
_ESCAPED_CREDENTIAL = re.compile(
    r"(?P<prefix>\\\"_?" + _CREDENTIAL_KEY + r"\\\"\s*:\s*\\\")(?P<value>.*?)(?P<suffix>\\\")",
    re.IGNORECASE | re.DOTALL,
)
_AUTHORIZATION = re.compile(
    r"(?P<prefix>(?:proxy[-_])?authorization[\"']?\s*[:=]\s*[\"']?(?:Bearer|Basic)\s+)"
    r"[^\s,;\"'{}]+",
    re.IGNORECASE,
)
_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----.*?-----END (?:[A-Z ]+ )?PRIVATE KEY-----",
    re.DOTALL,
)


def redact_diagnostic(value: str | bytes | None) -> str:
    """Remove credential values from CLI diagnostics before durable publication.

    Covers OAuth form bodies, JSON, Node object inspection, escaped JSON strings,
    authorization headers, and private-key blocks. Preserve field names and the
    surrounding transport/status evidence. Parsing the provider response still
    uses the original in-memory stream, not this redacted diagnostic copy.
    """
    text = _text(value)
    text = _PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", text)
    text = _ESCAPED_CREDENTIAL.sub(r"\g<prefix>[REDACTED]\g<suffix>", text)
    text = _AUTHORIZATION.sub(r"\g<prefix>[REDACTED]", text)

    def replace(match: re.Match) -> str:
        original = match["value"]
        quote = original[0] if original[0] in {"'", '"'} else ""
        return match["prefix"] + quote + "[REDACTED]" + quote

    return _CREDENTIAL_ASSIGNMENT.sub(replace, text)


class ModelOutputError(ValueError):
    """A successful provider response failed JSON or output-contract validation.

    Callers may use the saved response and details in a bounded repair prompt.
    Authentication, transport, timeout and native-tool failures remain runtime
    errors and must not be treated as malformed-output repair attempts.
    """

    def __init__(self, evidence_id: str, details: str, response: Any):
        self.evidence_id = evidence_id
        self.details = details
        self.response = response
        super().__init__(
            f"Model output failed validation; inspect artifact {evidence_id}: {details}"
        )


class ModelInterruptedError(RuntimeError):
    """Provider execution stopped before completion, even if the CLI exited zero.

    This is deliberately not ModelOutputError. Repeating a formatting repair
    would make another paid call without resolving the execution interruption.
    """

    def __init__(self, reason: str, evidence_id: str | None = None):
        self.reason = reason
        self.evidence_id = evidence_id
        suffix = f"; inspect artifact {evidence_id}" if evidence_id else ""
        super().__init__(f"Gemini execution interrupted: {reason}{suffix}")


def validate_cli_completion(outer: dict, returncode: int) -> None:
    """Check execution metadata before parsing generated output.

    Only CLI metadata is inspected, never model-generated answer text. A
    zero exit status and zero native tool calls do not establish completion.
    Usage settlement is separate and retains unknown reservations.
    """
    warnings = outer.get("warnings", [])
    if isinstance(warnings, list) and any(
        isinstance(warning, str) and "maximum session turns exceeded" in warning.casefold()
        for warning in warnings
    ):
        raise ModelInterruptedError("Maximum session turns exceeded")
    if returncode != 0 or outer.get("error"):
        raise RuntimeError(f"Gemini CLI failed with exit code {returncode}")
    stats = outer.get("stats")
    if (
        not isinstance(stats, dict)
        or not isinstance(stats.get("tools"), dict)
        or stats["tools"].get("totalCalls") != 0
    ):
        raise RuntimeError("Gemini CLI native tool calls were nonzero or unreported")


def runtime_config() -> dict:
    return json.loads((PROJECT / "config/runtime.json").read_text())


def estimated_usage(stats: dict, config: dict) -> float | None:
    """Price actual cumulative usage; unknown models or missing counts stay unknown."""
    models = stats.get("models")
    if not isinstance(models, dict) or not models:
        return None
    estimated = 0.0
    for name, model in models.items():
        if name != config["model"] or not isinstance(model, dict):
            return None
        tokens = model.get("tokens", {})
        if not isinstance(tokens, dict):
            return None
        counts = [
            tokens.get("prompt", tokens.get("input")),
            tokens.get("candidates"),
            tokens.get("thoughts"),
        ]
        if any(type(value) is not int or value < 0 for value in counts):
            return None
        estimated += (
            counts[0] * config["input_usd_per_million"]
            + (counts[1] + counts[2]) * config["output_usd_per_million"]
        ) / 1_000_000
    return estimated


def register_preflight_receipt(store: Store, report_path: Path) -> str:
    """Account for the completed real preflight exactly once by CLI session ID.

    This imports an existing receipt and makes no provider request. It verifies
    the raw output against the report before recording the estimated cost.
    """
    report = json.loads(report_path.read_text())
    stdout = Path(report["stdout_path"]).read_text()
    outer = json.loads(stdout)
    if (
        not report.get("success")
        or report.get("returncode") != 0
        or outer.get("response") != "OAK_VERTEX_OK"
        or outer.get("stats") != report.get("stats")
        or outer.get("stats", {}).get("tools", {}).get("totalCalls") != 0
    ):
        raise ValueError("Preflight receipt is not a verified successful provider response")
    session_id = outer.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("Preflight receipt lacks a CLI session identity")
    config = runtime_config()
    estimated = estimated_usage(outer["stats"], config)
    if estimated is None:
        raise ValueError("Preflight usage cannot be priced under the pinned configuration")
    identity = "external-" + hashlib.sha256(session_id.encode()).hexdigest()
    evidence = {
        "call_id": identity,
        "source": "completed_external_preflight",
        "report": report,
        "stdout": redact_diagnostic(stdout),
        "stderr": redact_diagnostic(Path(report["stderr_path"]).read_text()),
        "diagnostic_redaction": "credential_values_v1",
        "estimated_usd": estimated,
        "pricing": config,
    }
    evidence_id = store.put("model_usage", evidence)
    with store.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        inserted = connection.execute(
            "INSERT OR IGNORE INTO model_calls(id,run_id,status,reserved,estimated,evidence_id) "
            "VALUES(?,?,'settled',0,?,?)",
            (identity, "external-preflight", estimated, evidence_id),
        ).rowcount
    if inserted:
        store.event(
            "external-preflight",
            "provider_preflight",
            "completed",
            "Completed Vertex preflight usage recorded",
            evidence,
        )
    return identity


class GeminiCLI:
    """Request validated JSON with isolated CLI sessions and a store-wide budget.

    A successful prior receipt is reused only for the identical run, stage,
    prompt, runtime, system text and output schema. File locking prevents two
    concurrent resumes from buying the same request. Reuse is explicitly logged.
    """

    def __init__(self, store: Store, run_id: str, *, budget_ceiling_usd: float | None = None):
        self.store, self.run_id = store, run_id
        self.config = runtime_config()
        if budget_ceiling_usd is not None:
            if not 0 < budget_ceiling_usd <= self.config["total_budget_usd"]:
                raise ValueError("Campaign ceiling must be positive and within the global budget")
            self.config["total_budget_usd"] = budget_ceiling_usd

    def _cached(self, key: str) -> dict | None:
        for row in self.store.rows(
            "SELECT id,evidence_id FROM model_calls WHERE run_id=? AND status IN ('settled','unknown') "
            "AND evidence_id IS NOT NULL",
            (self.run_id,),
        ):
            evidence = self.store.get(row["evidence_id"])
            if evidence.get("request_key") == key and evidence.get("validated_success") is True:
                return {
                    "call_id": row["id"],
                    "evidence_id": row["evidence_id"],
                    "value": evidence["validated_value"],
                }
        return None

    @traceable(name="gemini_cli_json", run_type="llm")
    def json(
        self, stage: str, instruction: str, inputs: Any, output_schema: dict | None = None
    ) -> Any:
        """Request one JSON value, preserving configuration, usage and failures."""
        config = self.config
        if output_schema is not None:
            jsonschema.validators.validator_for(output_schema).check_schema(output_schema)
        prompt = canonical(
            {
                "stage": stage,
                "instruction": instruction,
                "inputs": inputs,
                "output_schema": output_schema,
            }
        ).decode()
        if len(prompt.encode()) > config["max_prompt_bytes"]:
            raise ValueError("Prompt exceeds configured byte limit; split the actual corpus")
        system = (PROJECT / "config/gemini-system.md").read_text()
        identity = cli_identity()
        project = configured_project()
        request = {
            "run_id": self.run_id,
            "stage": stage,
            "prompt": prompt,
            "runtime": config,
            "settings": runtime_settings(config),
            "system_prompt": system,
            "output_schema": output_schema,
            "cli": identity,
            "project": project,
            "launch_prompt": LAUNCH_PROMPT,
            "policy": POLICY,
        }
        key = hashlib.sha256(canonical(request)).hexdigest()
        locks = self.store.root / "model-cache-locks"
        locks.mkdir(exist_ok=True)
        with (locks / f"{key}.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            cached = self._cached(key)
            if cached:
                self.store.event(
                    self.run_id,
                    stage,
                    "cache_hit",
                    "Exact completed model receipt reused",
                    {
                        "request_key": key,
                        "original_call_id": cached["call_id"],
                        "evidence_id": cached["evidence_id"],
                        "new_provider_call": False,
                    },
                )
                return cached["value"]
            if date.today() > date.fromisoformat(config["pricing_valid_until"]):
                raise RuntimeError("Pricing pin expired; verify current prices before model calls")
            return self._invoke(stage, prompt, system, project, key, request, output_schema)

    def _invoke(
        self,
        stage: str,
        prompt: str,
        system: str,
        project: str,
        key: str,
        request: dict,
        output_schema: dict | None,
    ) -> Any:
        config = self.config
        # UTF-8 bytes conservatively bound user/system token counts. The 20k
        # margin covers CLI context; 10x retains the existing retry contingency.
        reservation = (
            10
            * (
                (len(prompt.encode()) + len(system.encode()) + 20_000)
                * config["input_usd_per_million"]
                + config["max_output_tokens"] * config["output_usd_per_million"]
            )
            / 1_000_000
        )
        call_id = self.store.reserve(self.run_id, reservation, config["total_budget_usd"])
        invocation = None
        evidence = {
            "call_id": call_id,
            "request_key": key,
            "request": request,
            "reservation_usd": reservation,
            "validated_success": False,
            "model_request_attempted": False,
            "diagnostic_redaction": "credential_values_v1",
        }
        try:
            invocation = prepare_invocation(self.store.root, call_id, config, project, system)
            evidence.update(
                command=invocation.command,
                work_directory=str(invocation.cwd),
                runtime_directory=str(invocation.directory),
                isolation_inspection=invocation.inspection,
            )
            self.store.event(
                self.run_id, stage, "running", "Gemini is processing this stage", evidence
            )
            evidence["model_request_attempted"] = True
            result = subprocess.run(
                invocation.command,
                input=prompt,
                text=True,
                capture_output=True,
                cwd=invocation.cwd,
                env=invocation.env,
                timeout=config["timeout_seconds"],
            )
        except subprocess.TimeoutExpired as error:
            evidence.update(
                error="CLI timeout; usage unknown",
                stdout=redact_diagnostic(error.stdout),
                stderr=redact_diagnostic(error.stderr),
            )
            self.store.settle(call_id, None, evidence)
            self.store.event(
                self.run_id, stage, "failed", "Gemini timed out; reservation retained", evidence
            )
            raise RuntimeError("Gemini CLI timed out; usage reservation retained") from None
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            evidence.update(error=redact_diagnostic(f"{type(error).__name__}: {error}"))
            estimated = None if evidence["model_request_attempted"] else 0.0
            self.store.settle(call_id, estimated, evidence)
            self.store.event(self.run_id, stage, "failed", "Gemini could not start", evidence)
            raise RuntimeError(
                "Gemini CLI could not start; inspect saved failure evidence"
            ) from None
        finally:
            if invocation is not None:
                invocation.close()
        evidence.update(
            returncode=result.returncode,
            stdout=redact_diagnostic(result.stdout),
            stderr=redact_diagnostic(result.stderr),
        )
        try:
            outer = json.loads(result.stdout)
            if not isinstance(outer, dict):
                outer = {}
        except json.JSONDecodeError:
            outer = {}
        stats = outer.get("stats", {})
        estimated = estimated_usage(stats, config) if isinstance(stats, dict) else None
        evidence.update(stats=stats, estimated_usd=estimated)
        failure = None
        value = None
        try:
            validate_cli_completion(outer, result.returncode)
            text = outer.get("response", "").strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            value = json.loads(text, parse_constant=_reject_json_constant)
            if output_schema is not None:
                jsonschema.validate(value, output_schema)
            evidence.update(validated_success=True, validated_value=value)
        except (
            ValueError,
            RuntimeError,
            TypeError,
            AttributeError,
            IndexError,
            jsonschema.ValidationError,
            jsonschema.SchemaError,
        ) as error:
            failure = error
            evidence["validation_error"] = redact_diagnostic(str(error))
            if isinstance(error, ModelInterruptedError):
                evidence["failure_category"] = "execution_interrupted"
                evidence["repairable_output"] = False
        self.store.settle(call_id, estimated, evidence)
        raw_id = self.store.event(
            self.run_id,
            stage,
            "failed" if failure else "completed",
            "Gemini response rejected" if failure else "Validated Gemini response recorded",
            evidence,
        )
        if failure:
            if isinstance(failure, ModelInterruptedError):
                raise ModelInterruptedError(failure.reason, raw_id) from None
            if not isinstance(failure, RuntimeError):
                raise ModelOutputError(
                    raw_id,
                    redact_diagnostic(str(failure)),
                    redact_diagnostic(outer.get("response"))
                    if isinstance(outer.get("response"), str)
                    else None,
                ) from None
            raise RuntimeError(
                f"Gemini response failed validation; inspect artifact {raw_id}"
            ) from None
        return value


def _text(value: str | bytes | None) -> str:
    return value.decode(errors="replace") if isinstance(value, bytes) else value or ""


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number is not allowed: {value}")

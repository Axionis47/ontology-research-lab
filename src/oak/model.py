"""Budgeted Gemini CLI calls with actual receipts and exact request reuse."""

from __future__ import annotations

import fcntl
import hashlib
import json
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
        "stdout": stdout,
        "stderr": Path(report["stderr_path"]).read_text(),
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

    def __init__(self, store: Store, run_id: str):
        self.store, self.run_id = store, run_id
        self.config = runtime_config()

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
                stdout=_text(error.stdout),
                stderr=_text(error.stderr),
            )
            self.store.settle(call_id, None, evidence)
            self.store.event(
                self.run_id, stage, "failed", "Gemini timed out; reservation retained", evidence
            )
            raise RuntimeError("Gemini CLI timed out; usage reservation retained") from error
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            evidence.update(error=f"{type(error).__name__}: {error}")
            estimated = None if evidence["model_request_attempted"] else 0.0
            self.store.settle(call_id, estimated, evidence)
            self.store.event(self.run_id, stage, "failed", "Gemini could not start", evidence)
            raise RuntimeError(
                "Gemini CLI could not start; inspect saved failure evidence"
            ) from error
        finally:
            if invocation is not None:
                invocation.close()
        evidence.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
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
            if result.returncode != 0 or outer.get("error"):
                raise RuntimeError(f"Gemini CLI failed with exit code {result.returncode}")
            if (
                not isinstance(stats, dict)
                or not isinstance(stats.get("tools"), dict)
                or stats["tools"].get("totalCalls") != 0
            ):
                raise RuntimeError("Gemini CLI native tool calls were nonzero or unreported")
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
            evidence["validation_error"] = str(error)
        self.store.settle(call_id, estimated, evidence)
        raw_id = self.store.event(
            self.run_id,
            stage,
            "failed" if failure else "completed",
            "Gemini response rejected" if failure else "Validated Gemini response recorded",
            evidence,
        )
        if failure:
            if not isinstance(failure, RuntimeError):
                raise ModelOutputError(raw_id, str(failure), outer.get("response")) from failure
            raise RuntimeError(
                f"Gemini response failed validation; inspect artifact {raw_id}"
            ) from failure
        return value


def _text(value: str | bytes | None) -> str:
    return value.decode(errors="replace") if isinstance(value, bytes) else value or ""


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number is not allowed: {value}")

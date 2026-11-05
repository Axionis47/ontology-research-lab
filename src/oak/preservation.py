"""Narrow, reproducible preservation checks for canonical pure OaK plans.

The Lean theorem concerns PlanIR on the same arbitrary immutable graph and input.
The Python lowering/interpreter correspondence is an explicit trusted boundary,
not a consequence of a hash or a passing replay. Acquisition, extraction, schema
changes and fresh agent choices are outside this fragment.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from oak import functions, ontology, operators
from oak.functions import FunctionSpec, validate_functions
from oak.store import canonical

ROOT = Path(__file__).resolve().parents[2]
PROOFS = ROOT / "proofs"
LEAN_VERSION = "4.35.0"
EFFECT_OPERATORS = frozenset({"invoke_capability", "extract_runtime_slots"})
PURE_OPERATORS = frozenset(
    {
        "lookup_entities",
        "traverse_relations",
        "project_properties",
        "filter_property_categorical",
        "filter_categorical",
        "filter_relation_connected",
        "filter_numeric",
        "filter_set_overlap",
        "aggregate_values",
        "arithmetic",
    }
)
ASSUMPTIONS = [
    "Both plans receive the same arbitrary valid immutable graph and accepted input.",
    "Primitive, expression and validation interpretations are deterministic and identical.",
    "Python canonical lowering and interpreter correspondence are trusted, not proved.",
    "Observations include values, typed primitive failures and call order/count; local labels and timing are excluded.",
    "Source completeness, extraction accuracy and fresh planner choices are outside the theorem.",
]


class StrictModel(BaseModel):
    """Reject unknown fields in proof-bearing data."""

    model_config = ConfigDict(extra="forbid", strict=True)


class CanonicalInstruction(StrictModel):
    """A deterministic primitive call with de Bruijn-like positional step references."""

    operator: str
    arguments: dict[str, JsonValue]


class PlanIR(StrictModel):
    """Finite eager pure plan; external JSON validation contracts remain exact."""

    version: Literal[1] = 1
    inputs: dict[str, JsonValue]
    output_schema: dict[str, JsonValue]
    steps: list[CanonicalInstruction]
    result: JsonValue


class PreservationCertificate(StrictModel):
    """Evidence for one adjacent revision pair, conditional on the runtime bridge."""

    version: Literal[1] = 1
    status: Literal["certified", "unknown", "counterexample", "invalid_evidence"]
    parent_id: str
    candidate_id: str
    parent_sha256: str
    candidate_sha256: str
    schema_sha256: str
    protected_functions: list[str]
    rules: list[str] = Field(default_factory=list)
    plans: dict[str, dict[str, PlanIR]] = Field(default_factory=dict)
    dependencies: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=lambda: list(ASSUMPTIONS))
    summary: str
    proof_receipt: dict[str, JsonValue] | None = None
    certificate_sha256: str = ""


def digest(value: Any) -> str:
    """Hash canonical JSON without treating that identity as semantic evidence."""
    return hashlib.sha256(canonical(value)).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_dependencies() -> dict[str, str]:
    """Conservatively bind the entire interpreter/operator/lowering implementation."""
    return {
        "operators": _file_digest(Path(operators.__file__)),
        "executor": _file_digest(Path(functions.__file__)),
        "ontology": _file_digest(Path(ontology.__file__)),
        "runtime_lock": _file_digest(ROOT / "uv.lock"),
        "lowering": _file_digest(Path(__file__)),
        "proof_module": _file_digest(PROOFS / "OakPreservation.lean"),
        "toolchain": _file_digest(PROOFS / "lean-toolchain"),
    }


def _canonical_expression(value: Any, names: dict[str, int]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$step"}:
            return {"$step_index": names[value["$step"]]}
        if set(value) == {"$path"}:
            return {"$path_index": [names[value["$path"][0]], *value["$path"][1:]]}
        return {key: _canonical_expression(item, names) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical_expression(item, names) for item in value]
    return deepcopy(value)


def lower_function(function: FunctionSpec | dict, schema: dict) -> PlanIR:
    """Lower a validated pure FunctionSpec, erasing only capture-free local labels.

    Input names, property names, literal strings, output contracts, step order,
    error-producing calls and unused eager calls remain unchanged.
    """
    spec = validate_functions([function], schema)[0]
    names: dict[str, int] = {}
    steps = []
    for index, step in enumerate(spec.steps):
        if step.operator not in PURE_OPERATORS:
            raise ValueError(f"Effectful or unmodeled operator: {step.operator}")
        steps.append(
            CanonicalInstruction(
                operator=step.operator,
                arguments=_canonical_expression(step.args, names),
            )
        )
        names[step.id] = index
    return PlanIR(
        inputs=deepcopy(spec.inputs),
        output_schema=deepcopy(spec.output_schema),
        steps=steps,
        result=_canonical_expression(spec.result, names),
    )


def _lean_string(value: str) -> str:
    # JSON and Lean share these escapes. U+2028/U+2029 remain ordinary Unicode.
    return json.dumps(value, ensure_ascii=False)


def _json_string(value: Any) -> str:
    return _lean_string(canonical(value).decode())


def _lean_plan(plan: PlanIR) -> str:
    steps = ", ".join(
        "⟨" + _lean_string(step.operator) + ", " + _json_string(step.arguments) + "⟩"
        for step in plan.steps
    )
    return (
        "⟨"
        + _json_string(plan.inputs)
        + ", "
        + _json_string(plan.output_schema)
        + ", ["
        + steps
        + "], "
        + _json_string(plan.result)
        + "⟩"
    )


def _certificate_source(plans: dict[str, dict[str, PlanIR]]) -> str:
    """Render only data into fixed theorem templates, never model-authored Lean."""
    declarations = ["import OakPreservation", "open OakPreservation"]
    for index, pair in enumerate(plans.values()):
        declarations.extend(
            [
                f"def before{index} : Plan := {_lean_plan(pair['before'])}",
                f"def after{index} : Plan := {_lean_plan(pair['after'])}",
                f"theorem same{index} : before{index} = after{index} := by decide",
                f"theorem preserved{index} {{V E G I : Type}}",
                "  (validate : String → I → Except E Unit)",
                "  (invoke : Instruction → G → I → List V → Except E V)",
                "  (finish : String → String → G → I → List V → Except E V)",
                "  (graph : G) (input : I) :",
                f"  evaluate validate invoke finish before{index} graph input =",
                f"    evaluate validate invoke finish after{index} graph input :=",
                f"  canonical_preservation validate invoke finish _ _ same{index} graph input",
                f"#print axioms same{index}",
                f"#print axioms preserved{index}",
            ]
        )
    return "\n".join(declarations) + "\n"


def _lean_binary() -> str | None:
    configured = os.environ.get("OAK_LEAN_BINARY")
    if configured:
        return configured if Path(configured).is_file() else None
    local = ROOT / ".tools" / "lean" / "bin" / "lean"
    return str(local) if local.is_file() else shutil.which("lean")


def check_lean(plans: dict[str, dict[str, PlanIR]], *, timeout_seconds: float = 30) -> dict:
    """Kernel-check instantiated equalities with a pinned executable and audited axioms.

    A missing checker, timeout or failure yields an explicit non-certified receipt.
    The generated source and command outputs are evidence, not executable inputs.
    """
    binary = _lean_binary()
    source = _certificate_source(plans)
    receipt = {
        "status": "unknown",
        "toolchain": f"leanprover/lean4:v{LEAN_VERSION}",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "source": source,
    }
    if binary is None:
        return {**receipt, "reason": "Pinned Lean checker is unavailable"}
    try:
        version = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=timeout_seconds
        )
        receipt["version_output"] = version.stdout.strip()
        if version.returncode or not re.search(r"\bversion 4\.35\.0\b", version.stdout):
            return {**receipt, "reason": "Lean version does not match the pinned toolchain"}
        with tempfile.TemporaryDirectory(prefix="oak-preservation-") as directory:
            path = Path(directory)
            shutil.copyfile(PROOFS / "OakPreservation.lean", path / "OakPreservation.lean")
            env = {**os.environ, "LEAN_PATH": directory}
            module = subprocess.run(
                [binary, "-o", str(path / "OakPreservation.olean"), "OakPreservation.lean"],
                cwd=path,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            (path / "Certificate.lean").write_text(source)
            result = subprocess.run(
                [binary, "Certificate.lean"],
                cwd=path,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            output = module.stdout + module.stderr + result.stdout + result.stderr
            receipt.update(module_exit_code=module.returncode, exit_code=result.returncode)
            receipt["checker_output"] = output
            # Each fixed theorem prints its dependency audit. These proofs need
            # no axioms, including no native_decide/sorry/classical axioms.
            audits = [
                line
                for line in output.splitlines()
                if "depends on axioms" in line or "does not depend on any axioms" in line
            ]
            expected_count = 4 + 2 * len(plans)
            if (
                module.returncode
                or result.returncode
                or len(audits) != expected_count
                or any(
                    not (
                        line.rstrip().endswith("[]")
                        or line.rstrip().endswith("does not depend on any axioms")
                    )
                    for line in audits
                )
                or "sorry" in output.lower()
            ):
                return {**receipt, "reason": "Proof compilation or dependency audit failed"}
            return {**receipt, "status": "checked", "axioms": []}
    except (OSError, subprocess.SubprocessError) as error:
        return {**receipt, "reason": f"Proof checker unavailable or interrupted: {error}"}


def _candidate_data(candidate: Any) -> dict:
    return candidate.model_dump(mode="json") if isinstance(candidate, BaseModel) else candidate


def _seal(certificate: PreservationCertificate) -> PreservationCertificate:
    data = certificate.model_dump(mode="json", exclude={"certificate_sha256"})
    return certificate.model_copy(update={"certificate_sha256": digest(data)})


def certify_preservation(
    parent: Any,
    candidate: Any,
    protected_functions: list[str] | None = None,
    *,
    timeout_seconds: float = 30,
) -> PreservationCertificate:
    """Certify exact pure-plan preservation for one actual adjacent revision.

    A difference is unsupported, not automatically a semantic counterexample.
    Removing a protected entry point or changing its accepted contract is a
    concrete protected-contract failure. No model or service is invoked.
    """
    before, after = _candidate_data(parent), _candidate_data(candidate)
    old_catalog = {function["name"]: function for function in before.get("functions", [])}
    new_catalog = {function["name"]: function for function in after.get("functions", [])}
    protected = sorted(old_catalog if protected_functions is None else protected_functions)
    base = PreservationCertificate(
        status="unknown",
        parent_id=before.get("id", ""),
        candidate_id=after.get("id", ""),
        parent_sha256=digest(before),
        candidate_sha256=digest(after),
        schema_sha256=digest(before.get("schema")),
        protected_functions=protected,
        dependencies=runtime_dependencies(),
        summary="Preservation has not been established",
    )

    def finish(status: str, summary: str, **updates) -> PreservationCertificate:
        return _seal(base.model_copy(update={"status": status, "summary": summary, **updates}))

    if not before.get("id") or not after.get("id"):
        return finish("invalid_evidence", "Exact revision identifiers are required")
    if (after.get("parent_id") or after.get("parent")) != before["id"]:
        return finish("invalid_evidence", "Candidate does not record this immediate parent")
    if not protected or len(set(protected)) != len(protected):
        return finish("invalid_evidence", "A nonempty unique protected contract set is required")
    if not set(protected).issubset(old_catalog):
        return finish("invalid_evidence", "Protected entry point is absent from the parent")
    missing = sorted(set(protected) - new_catalog.keys())
    if missing:
        return finish("counterexample", f"Protected callable entry points removed: {missing}")
    if before.get("schema") != after.get("schema"):
        return finish("unknown", "Schema changes are outside the same-schema proof fragment")
    pairs = {}
    rules = set()
    try:
        validate_functions(before["functions"], before["schema"])
        validate_functions(after["functions"], after["schema"])
        for name in protected:
            old, new = old_catalog[name], new_catalog[name]
            if old["inputs"] != new["inputs"] or old["output_schema"] != new["output_schema"]:
                return finish(
                    "unknown", f"External contract change requires a separate proof: {name}"
                )
            old_plan, new_plan = (
                lower_function(old, before["schema"]),
                lower_function(new, after["schema"]),
            )
            if old_plan != new_plan:
                return finish("unknown", f"Unsupported computational transformation: {name}")
            pairs[name] = {"before": old_plan, "after": new_plan}
            rules.add("identity" if old["steps"] == new["steps"] else "local_alpha_renaming")
    except (KeyError, TypeError, ValueError) as error:
        return finish("unknown", f"Plan is outside the verified fragment: {error}")
    receipt = check_lean(pairs, timeout_seconds=timeout_seconds)
    if receipt["status"] != "checked":
        return finish(
            "unknown",
            receipt.get("reason", "Proof checker did not complete"),
            proof_receipt=receipt,
        )
    return finish(
        "certified",
        "PlanIR preservation proved; Python execution remains conditional on the pinned bridge",
        plans=pairs,
        rules=sorted(rules),
        proof_receipt=receipt,
    )


def validate_certificate(
    certificate: PreservationCertificate | dict,
    parent: Any,
    candidate: Any,
    *,
    recheck: bool = True,
) -> PreservationCertificate:
    """Reject stale/modified certificates and recheck from actual inputs by default."""
    cert = (
        certificate
        if isinstance(certificate, PreservationCertificate)
        else PreservationCertificate.model_validate(certificate)
    )
    if cert.certificate_sha256 != digest(
        cert.model_dump(mode="json", exclude={"certificate_sha256"})
    ):
        raise ValueError("Preservation certificate hash mismatch")
    if cert.status != "certified" or cert.assumptions != ASSUMPTIONS:
        raise ValueError("Certificate is not certified under the current assumptions")
    if cert.dependencies != runtime_dependencies():
        raise ValueError("Preservation certificate dependencies have changed")
    if cert.parent_sha256 != digest(_candidate_data(parent)) or cert.candidate_sha256 != digest(
        _candidate_data(candidate)
    ):
        raise ValueError("Preservation certificate does not match the actual revisions")
    if recheck:
        fresh = certify_preservation(parent, candidate, cert.protected_functions)
        if fresh.status != "certified" or fresh.plans != cert.plans:
            raise ValueError("Preservation certificate could not be reproduced")
    return cert


def compose_certificates(
    certificates: list[PreservationCertificate | dict], kernels: dict[str, Any]
) -> dict:
    """Recheck adjacent certificates before composing an exact inherited guarantee."""
    if not certificates:
        raise ValueError("Cannot compose an empty preservation chain")
    checked = []
    for raw in certificates:
        cert = (
            raw
            if isinstance(raw, PreservationCertificate)
            else PreservationCertificate.model_validate(raw)
        )
        if cert.parent_id not in kernels or cert.candidate_id not in kernels:
            raise ValueError("Every chain revision must be supplied for independent rechecking")
        cert = validate_certificate(cert, kernels[cert.parent_id], kernels[cert.candidate_id])
        if checked:
            previous = checked[-1]
            if previous.candidate_id != cert.parent_id:
                raise ValueError("Broken preservation ancestry")
            if (
                previous.schema_sha256 != cert.schema_sha256
                or previous.assumptions != cert.assumptions
            ):
                raise ValueError("Preservation chain assumptions differ")
            if not set(previous.protected_functions).issubset(cert.protected_functions):
                raise ValueError("Child certificate drops inherited protected capabilities")
        checked.append(cert)
    return {
        "version": 1,
        "status": "certified",
        "ancestor_id": checked[0].parent_id,
        "candidate_id": checked[-1].candidate_id,
        "protected_functions": checked[0].protected_functions,
        "certificate_sha256s": [cert.certificate_sha256 for cert in checked],
        "assumptions": list(ASSUMPTIONS),
        "scope": "Pure PlanIR only, on the same arbitrary immutable graph and input",
    }

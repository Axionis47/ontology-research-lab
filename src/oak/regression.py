"""Recorded-call primitives and the inherited historical regression entry point.

Adapters rename function/argument names and optional top-level output fields.
They cannot generate answers, supply constants, branch on tasks, change types,
invoke arbitrary code, or access old outputs while being proposed.
The adjacent-call helpers are component checks. Candidate acceptance uses the
full inherited bank through ``replay_inherited_cases``, never these helpers alone.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from oak.functions import execute_function, validate_functions
from oak.store import canonical


def replay_inherited_cases(store, candidate_id: str, *, run_id: str) -> dict:
    """Execute the complete protected bank through actual ancestry, offline only."""
    from oak.historical_replay import replay_bank

    return replay_bank(store, candidate_id, run_id=run_id)


class FunctionMapping(BaseModel):
    """One interface rename; omitted argument/output names retain their names."""

    model_config = ConfigDict(extra="forbid", strict=True)
    old_function: str = Field(min_length=1)
    new_function: str = Field(min_length=1)
    arguments: dict[str, str] = Field(default_factory=dict)
    output_fields: dict[str, str] = Field(default_factory=dict)


class AdapterSpec(BaseModel):
    """A version-bound, inspectable set of bijective interface renames."""

    model_config = ConfigDict(extra="forbid", strict=True)
    old_revision: str = Field(min_length=1)
    new_revision: str = Field(min_length=1)
    mappings: list[FunctionMapping] = Field(default_factory=list, max_length=64)


def _revision_id(revision: dict) -> str:
    identity = revision.get("id")
    if not isinstance(identity, str) or not identity:
        raise ValueError("Replay requires the exact saved revision ID")
    return identity


def _meaning(schema: Any) -> Any:
    """Remove descriptive JSON Schema annotations, preserving validation constraints."""
    if isinstance(schema, dict):
        annotations = {"description", "title", "examples", "default", "$comment", "deprecated"}
        maps = {"properties", "patternProperties", "dependentSchemas", "$defs", "definitions"}
        subschemas = {
            "items",
            "additionalProperties",
            "contains",
            "propertyNames",
            "not",
            "if",
            "then",
            "else",
            "unevaluatedProperties",
            "unevaluatedItems",
        }
        lists = {"allOf", "anyOf", "oneOf", "prefixItems"}
        result = {}
        for key, value in schema.items():
            if key in annotations:
                continue
            if key in maps:
                result[key] = {name: _meaning(item) for name, item in value.items()}
            elif key in subschemas:
                result[key] = _meaning(value)
            elif key in lists:
                result[key] = [_meaning(item) for item in value]
            else:
                result[key] = deepcopy(value)
        if "required" in result:
            result["required"] = sorted(result["required"])
        return result
    if isinstance(schema, list):
        return [_meaning(value) for value in schema]
    return schema


def _rename_object(schema: dict, renames: dict[str, str]) -> dict:
    if not renames:
        return deepcopy(schema)
    if schema.get("type") != "object" or not isinstance(schema.get("properties"), dict):
        raise ValueError("Field renames require a declared top-level object schema")
    if schema.get("additionalProperties") is not False:
        raise ValueError("Field renames require additionalProperties=false to prevent collisions")
    properties = schema["properties"]
    if not set(renames).issubset(properties):
        raise ValueError("Adapter rename refers to an undeclared interface field")
    mapped = {key: renames.get(key, key) for key in properties}
    if len(set(mapped.values())) != len(mapped):
        raise ValueError("Adapter rename is not one-to-one")
    result = deepcopy(schema)
    result["properties"] = {mapped[key]: value for key, value in properties.items()}
    if "required" in result:
        result["required"] = [mapped[key] for key in result["required"]]
    # Conditional property dependencies are not safely renamed by this narrow DSL.
    unsupported = {
        "dependentRequired",
        "dependentSchemas",
        "if",
        "then",
        "else",
        "allOf",
        "anyOf",
        "oneOf",
        "not",
    }
    if unsupported.intersection(schema):
        raise ValueError("Rename adapters do not support conditional/composed object schemas")
    return result


def _validate_mapping(mapping: FunctionMapping, old_function: dict, new_function: dict) -> None:
    renamed_inputs = _rename_object(old_function["inputs"], mapping.arguments)
    if _meaning(renamed_inputs) != _meaning(new_function["inputs"]):
        raise ValueError(
            "Renamed input contract differs; type/constraint adaptation is unsupported"
        )
    renamed_outputs = _rename_object(new_function["output_schema"], mapping.output_fields)
    if _meaning(renamed_outputs) != _meaning(old_function["output_schema"]):
        raise ValueError(
            "Renamed output contract differs; nested/type/value transformation is unsupported"
        )


def validate_adapter(
    adapter: AdapterSpec | dict,
    old_revision: dict,
    new_revision: dict,
) -> AdapterSpec:
    """Validate explicit renames and add compatible same-name identity mappings.

    Omitted incompatible or removed functions remain unsupported. Validation
    establishes interface compatibility only, not preservation of semantics.
    """
    spec = adapter if isinstance(adapter, AdapterSpec) else AdapterSpec.model_validate(adapter)
    if spec.old_revision != _revision_id(old_revision) or spec.new_revision != _revision_id(
        new_revision
    ):
        raise ValueError("Adapter revision IDs do not match the exact old/new revisions")
    if new_revision.get("parent") != spec.old_revision:
        raise ValueError("Candidate parent must be the adapter's old revision")
    old_catalog = {
        entry.name: entry.model_dump(mode="json")
        for entry in validate_functions(old_revision["functions"], old_revision["schema"])
    }
    new_catalog = {
        entry.name: entry.model_dump(mode="json")
        for entry in validate_functions(new_revision["functions"], new_revision["schema"])
    }
    if len({mapping.old_function for mapping in spec.mappings}) != len(spec.mappings):
        raise ValueError("An old function may have only one adapter mapping")
    checked = []
    for mapping in spec.mappings:
        if mapping.old_function not in old_catalog or mapping.new_function not in new_catalog:
            raise ValueError("Adapter mapping refers to an absent function")
        _validate_mapping(
            mapping, old_catalog[mapping.old_function], new_catalog[mapping.new_function]
        )
        checked.append(mapping)
    explicit = {mapping.old_function for mapping in checked}
    for name in sorted(old_catalog.keys() & new_catalog.keys() - explicit):
        identity = FunctionMapping(old_function=name, new_function=name)
        try:
            _validate_mapping(identity, old_catalog[name], new_catalog[name])
        except ValueError:
            continue
        checked.append(identity)
    return AdapterSpec(
        old_revision=spec.old_revision, new_revision=spec.new_revision, mappings=checked
    )


def adapter_proposal_payload(old_revision: dict, new_revision: dict) -> dict:
    """Build the entire proposal context, deliberately excluding graphs, queries, and outputs."""
    return {
        "old": {
            "id": _revision_id(old_revision),
            "schema": deepcopy(old_revision["schema"]),
            "functions": deepcopy(old_revision["functions"]),
        },
        "new": {
            "id": _revision_id(new_revision),
            "schema": deepcopy(new_revision["schema"]),
            "functions": deepcopy(new_revision["functions"]),
        },
        "adapter_schema": AdapterSpec.model_json_schema(),
        "constraints": [
            "Propose only semantically justified function/argument/top-level output field renames.",
            "Do not add values, defaults, conditions, task identifiers, expected answers, or code.",
            "Omit unsupported mappings. Interface validation is followed by actual execution.",
        ],
    }


def propose_adapter(
    old_revision: dict,
    new_revision: dict,
    proposer: Callable[[dict], dict],
) -> AdapterSpec:
    """Call a supplied real model proposer with only old/new schema/function contracts."""
    if not callable(proposer):
        raise ValueError("A real adapter proposer callback must be supplied")
    proposal = proposer(adapter_proposal_payload(old_revision, new_revision))
    return validate_adapter(proposal, old_revision, new_revision)


def replay_function_call(
    old_revision: dict,
    new_revision: dict,
    call: dict,
    *,
    adapter: AdapterSpec | dict | None = None,
) -> dict:
    """Replay one genuine completed function receipt and compare its actual new output.

    This entry point also supports deterministic component tests that have no
    LLM answer. It never claims that a fresh agent produced an answer.
    """
    report: dict[str, Any] = {
        "status": "unverified",
        "old_function": call.get("function"),
        "fresh_agent_success": "unverified",
        "steps": [],
    }
    if (
        call.get("status") != "completed"
        or "value" not in call
        or not isinstance(call.get("args"), dict)
    ):
        report["reason"] = "No completed old function execution with arguments and value"
        return report
    spec = validate_adapter(
        adapter
        or AdapterSpec(
            old_revision=_revision_id(old_revision), new_revision=_revision_id(new_revision)
        ),
        old_revision,
        new_revision,
    )
    mapping = next(
        (item for item in spec.mappings if item.old_function == call.get("function")), None
    )
    if mapping is None:
        report.update(status="failed", reason="No compatible mapping for this old function")
        return report
    new_args = {
        mapping.arguments.get(key, key): deepcopy(value) for key, value in call["args"].items()
    }
    report.update(
        new_function=mapping.new_function,
        old_args=deepcopy(call["args"]),
        new_args=new_args,
        old_value=deepcopy(call["value"]),
        adapter=mapping.model_dump(mode="json"),
        old_dependencies=deepcopy(call.get("dependencies")),
    )
    try:
        execution = execute_function(
            new_revision["graph"],
            new_revision["functions"],
            mapping.new_function,
            new_args,
            schema=new_revision["schema"],
        )
        new_value = execution["value"]
        if mapping.output_fields:
            if not isinstance(new_value, dict):
                raise ValueError("Output field renaming requires an actual object result")
            adapted_value = {
                mapping.output_fields.get(key, key): value for key, value in new_value.items()
            }
        else:
            adapted_value = new_value
        report.update(
            status="passed" if canonical(adapted_value) == canonical(call["value"]) else "failed",
            new_value=new_value,
            adapted_value=adapted_value,
            steps=execution["steps"],
            new_dependencies=execution["dependencies"],
            comparison="exact_canonical_json",
        )
        if report["status"] == "failed":
            report["reason"] = "Actual candidate output differs from the original receipt"
    except Exception as error:
        report.update(
            status="failed",
            reason=f"{type(error).__name__}: {error}",
            steps=getattr(error, "steps", []),
            new_dependencies=getattr(error, "dependencies", None),
        )
    return report


def replay_recorded_calls(
    old_revision: dict,
    new_revision: dict,
    receipts: Sequence[dict] = (),
    *,
    adapter: AdapterSpec | dict | None = None,
) -> dict:
    """Replay parent construction results and saved answered trajectories in original order.

    Stop each trajectory at its first divergent or unsupported call. Subsequent
    arguments/branches are no longer validated by the recorded observations.
    Empty or unanswered trajectories are unverified, never vacuous successes.
    """
    spec = validate_adapter(
        adapter
        or AdapterSpec(
            old_revision=_revision_id(old_revision), new_revision=_revision_id(new_revision)
        ),
        old_revision,
        new_revision,
    )
    bound = []
    for index, item in enumerate(
        old_revision.get("assessment", {}).get("construction_results", [])
    ):
        bound.append(
            {
                "receipt_id": f"{old_revision['id']}:construction:{index}",
                "result": item["result"],
                "origin": "parent_construction",
                "original_score": item.get("score"),
            }
        )
    for item in receipts:
        wrapped = "result" in item and isinstance(item["result"], dict)
        result = item["result"] if wrapped else item
        receipt_id = item.get("receipt_id") if wrapped else None
        bound.append(
            {
                "receipt_id": receipt_id or hashlib.sha256(canonical(result)).hexdigest(),
                "result": result,
                "origin": "saved_answer",
            }
        )
    checks = []
    for item in bound:
        result = item["result"]
        check: dict[str, Any] = {key: value for key, value in item.items() if key != "result"}
        check.update(status="unverified", calls=[], executed_calls=0)
        trajectory = result.get("trajectory", [])
        if item["origin"] == "saved_answer" and result.get("kernel_revision") != spec.old_revision:
            check["reason"] = "Saved answer belongs to another kernel revision"
        elif result.get("status") != "answered":
            check["reason"] = "The old agent did not record an answered result"
        elif item.get("original_score") is False:
            check["reason"] = "The original construction task failed its evaluator"
        elif not trajectory or not any(call.get("status") == "completed" for call in trajectory):
            check["reason"] = "The old result contains no completed function calls"
        else:
            check["status"] = "passed"
            for index, call in enumerate(trajectory):
                if call.get("status") != "completed":
                    check.update(
                        status="unverified",
                        reason="A prior failed call's recovery path needs fresh inference",
                        stopped_at=index,
                        remaining_calls=len(trajectory) - index - 1,
                    )
                    break
                replay = replay_function_call(old_revision, new_revision, call, adapter=spec)
                check["calls"].append(replay)
                check["executed_calls"] += bool(replay.get("steps"))
                if replay["status"] != "passed":
                    check.update(
                        status=replay["status"],
                        reason="Recorded trajectory diverged; later calls were not replayed",
                        stopped_at=index,
                        remaining_calls=len(trajectory) - index - 1,
                    )
                    break
        checks.append(check)
    status = (
        "failed"
        if any(check["status"] == "failed" for check in checks)
        else (
            "passed"
            if checks and all(check["status"] == "passed" for check in checks)
            else "unverified"
        )
    )
    corpus_changed = old_revision.get("corpus_id") != new_revision.get("corpus_id")
    return {
        "evidence_type": "recorded_function_replay",
        "status": status,
        "checks": checks,
        "old_revision": spec.old_revision,
        "new_revision": spec.new_revision,
        "adapter": spec.model_dump(mode="json"),
        "coverage": "recorded_calls_only",
        "fresh_agent_success": "unverified",
        "dependency_coverage": "entire_graph_conservative",
        "corpus_changed": corpus_changed,
        "required_follow_up": ["Fresh agent inference for changed or uncertain planning behavior"]
        + (
            ["Review expectations against the changed corpus; old outputs are not new ground truth"]
            if corpus_changed
            else []
        ),
    }

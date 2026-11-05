"""Authoritative immutable historical replay contracts.

Manifests are sealed by the content-addressed Store. A candidate never supplies
its own expected values, comparison policy, or inherited case selection.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReplayContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ComparisonContract(ReplayContract):
    """Exact typed equality; unordered collections require an original declaration."""

    version: Literal[1] = 1
    collection: Literal["ordered", "multiset"] = "ordered"


class ResultBinding(ReplayContract):
    """An explicit argument path fed by an earlier replayed call's result."""

    argument_path: list[str | int] = Field(min_length=1)
    prior_call: int = Field(ge=0)
    output_path: list[str | int] = Field(default_factory=list)


class RecordedCall(ReplayContract):
    capture_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    bindings: list[ResultBinding] = Field(default_factory=list)


class ReplayCase(ReplayContract):
    """Original computations and assessment, never rewritten for a new kernel."""

    version: Literal[1] = 1
    origin_kernel_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    run_id: str
    question: str = ""
    requirement_version: str = "recorded_execution_v1"
    split: Literal["construction", "development"] = "construction"
    scope: Literal["component", "trajectory"] = "component"
    assessment_category: Literal[
        "execution_succeeded", "generated_consistency_check", "independent_task_check"
    ] = "execution_succeeded"
    assessment_refs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    calls: list[RecordedCall] = Field(min_length=1, max_length=128)
    comparison_id: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def ordered_bindings(self):
        for index, call in enumerate(self.calls):
            paths = [tuple(binding.argument_path) for binding in call.bindings]
            if len(set(paths)) != len(paths):
                raise ValueError("An argument has more than one result binding")
            if any(
                left != right and left[: len(right)] == right for left in paths for right in paths
            ):
                raise ValueError("Result binding targets cannot overlap")
            for binding in call.bindings:
                if any(
                    type(key) is int and key < 0
                    for key in [*binding.argument_path, *binding.output_path]
                ):
                    raise ValueError("Binding array indexes cannot be negative")
            if any(binding.prior_call >= index for binding in call.bindings):
                raise ValueError("Result bindings may reference only earlier calls")
        if self.scope == "trajectory" and len(self.calls) > 1:
            if any(not call.bindings for call in self.calls[1:]):
                raise ValueError("Multi-call trajectories require explicit result bindings")
        return self


class ReplayBank(ReplayContract):
    """Append-only case bank tied to an exact kernel and inherited bank."""

    version: Literal[1] = 1
    kernel_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    parent_bank_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    previous_bank_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    case_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def distinct_cases(self):
        if len(self.case_ids) != len(set(self.case_ids)):
            raise ValueError("A protected bank cannot duplicate case identities")
        return self


class FirstDifference(ReplayContract):
    phase: str
    call_index: int | None = None
    path: str = "$"
    reason: str
    expected: Any = None
    actual: Any = None
    original_function: str | None = None
    current_function: str | None = None
    repair_target: Literal[
        "migration", "schema", "call_adapter", "function", "verification_gap", "baseline"
    ]


class ReplayReport(ReplayContract):
    """Attributable evidence for original observations on a terminal candidate."""

    version: Literal[1] = 1
    original_case_id: str
    origin_kernel_id: str | None
    candidate_kernel_id: str
    status: Literal["preserved", "regressed", "unable_to_check", "interrupted"]
    scope: Literal["component", "trajectory", "unknown"]
    assessment_category: str
    adapter_path: list[str] = Field(default_factory=list)
    original_graph_ids: list[str] = Field(default_factory=list)
    migrated_graph_ids: list[str] = Field(default_factory=list)
    baseline_execution_id: str | None = None
    candidate_execution_id: str | None = None
    first_difference: FirstDifference | None = None
    runtime_dependencies: dict[str, str] = Field(default_factory=dict)
    reason: str = ""
    model_calls: Literal[0] = 0
    live_mcp_calls: Literal[0] = 0


class ReplayBankReport(ReplayContract):
    version: Literal[1] = 1
    kernel_id: str
    bank_id: str
    status: Literal["preserved", "regressed", "unable_to_check", "interrupted"]
    allowed: bool
    case_count: int
    reports: list[ReplayReport] = Field(default_factory=list)
    report_refs: list[str] = Field(default_factory=list)
    feedback: list[dict[str, Any]] = Field(default_factory=list)
    repair_context: dict[str, Any] = Field(default_factory=dict)
    runtime_dependencies: dict[str, str] = Field(default_factory=dict)
    model_calls: Literal[0] = 0
    live_mcp_calls: Literal[0] = 0

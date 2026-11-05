"""Candidate-independent task programs and attributed learning artifacts.

These contracts describe proposed task meaning, never evaluation answers. The
verification flow owns evidence assessment and is deliberately not imported.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue, model_validator

from oak.task_context import StrictContract


class SemanticField(StrictContract):
    """A semantic role independent of the ontology a candidate later proposes."""

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    value_type: Literal["string", "number", "boolean", "date", "entity", "unknown"]
    unit: str | None = None
    grain: str = Field(min_length=1)
    source_capability_ids: list[str] = Field(default_factory=list)
    role: Literal["value", "identity", "selector", "context"] = "value"


class TaskOperation(StrictContract):
    """One typed task operation, with explicit dependencies and semantic fields.

    This is a task interpretation, not an executable function body. Source
    acquisition and candidate ontology names do not enter the operation graph.
    """

    id: str = Field(min_length=1)
    operator: Literal["read", "filter", "project", "traverse", "aggregate", "arithmetic"]
    inputs: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    result_kind: Literal["records", "scalar", "path"]
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class TaskProgram(StrictContract):
    """Finite interpretation whose references are checked before S/F exists."""

    fields: list[SemanticField] = Field(default_factory=list)
    operations: list[TaskOperation] = Field(min_length=1, max_length=32)
    result: str = Field(min_length=1)
    input_domain: dict[str, JsonValue] = Field(default_factory=dict)
    observation_contract: str = Field(min_length=1)
    parameter_fields: dict[str, str] = Field(default_factory=dict)
    source_parameters: list[str] = Field(default_factory=list)
    ordering: Literal["unordered", "ordered"] = "unordered"

    @model_validator(mode="after")
    def check_program(self) -> TaskProgram:
        """Reject undefined semantic roles, cycles, and repeated operation IDs."""
        fields = {field.id for field in self.fields}
        if len(fields) != len(self.fields):
            raise ValueError("semantic field IDs must be unique")
        prior: set[str] = set()
        for operation in self.operations:
            if operation.id in prior or not set(operation.inputs).issubset(prior):
                raise ValueError("task program must have unique ordered acyclic operation IDs")
            if not set(operation.fields).issubset(fields):
                raise ValueError("task operation references an unknown semantic field")
            if operation.operator != "read" and not operation.inputs:
                raise ValueError("computed task operations require prior inputs")
            prior.add(operation.id)
        if self.result not in prior:
            raise ValueError("task result references an absent operation")
        if not set(self.parameter_fields.values()).issubset(fields):
            raise ValueError("parameter_fields references an unknown semantic field")
        from oak.task_semantics import validate_task_semantics

        validate_task_semantics(self)
        return self


class TaskObligation(StrictContract):
    """Literal or mechanically derived behavior with no candidate-produced score."""

    obligation_id: str
    case_id: str
    text: str
    parent_requirement_ids: list[str]
    derivation_rule: str
    program: TaskProgram | None = None
    group: Literal["retrieval", "subtask", "composition"]
    mandatory: bool = True
    semantic_status: Literal["proposed", "grounded"] = "proposed"
    oracle_ref: str | None = None


class TaskIR(StrictContract):
    """Frozen campaign bank derived from construction inputs only."""

    version: Literal[1] = 1
    profile: Literal["demand-driven-v1"] = "demand-driven-v1"
    source_sha256: str
    analysis_sha256: str
    analysis_id: str | None = None
    scope: str
    obligations: list[TaskObligation]
    exploration_limit: int = 128
    exploration_extra_operators: int = 2
    exploration_omitted: int = 0
    interpretation_gaps: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_obligations(self) -> TaskIR:
        """A frozen bank cannot silently overwrite an obligation."""
        identities = [item.obligation_id for item in self.obligations]
        if len(set(identities)) != len(identities):
            raise ValueError("TaskIR obligation IDs must be unique")
        return self


class CandidateSelection(StrictContract):
    """Selection records independent verifier evidence and explicit cost ties."""

    version: Literal[1] = 1
    task_ir_id: str
    candidate_ids: list[str]
    selected_kernel_id: str | None
    verification_ids: list[str]
    disposition: Literal["target_met", "incomplete", "rejected"]
    stop_reason: str
    ranks: dict[str, list[float]] = Field(default_factory=dict)

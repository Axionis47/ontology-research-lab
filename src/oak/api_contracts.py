"""Version-one public response contracts for the local OaK observer API.

These contracts describe presentation data, not a second ontology grammar.
Canonical schemas, functions, and evidence retain their existing artifact IDs.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from oak.learning_contracts import CandidateSelection, TaskIR
from oak.materialization import (
    CoverageReceipt,
    EvidenceDemand,
    MaterializationPlan,
    SufficiencyResult,
)
from oak.mcp_bridge import ConnectionConfig
from oak.preservation import PreservationCertificate
from oak.task_context import QuerySpec, RunLimits
from oak.verification import VerificationReport

API_VERSION = 1


class PublicResponse(BaseModel):
    """Reject undocumented response fields and identify the wire format."""

    model_config = ConfigDict(extra="forbid", serialize_by_alias=True)
    version: Literal[1] = 1


class BudgetView(BaseModel):
    """Reported estimates and outstanding reservations, never invoice claims."""

    limit_usd: float
    estimated_usd: float
    reserved_usd: float
    remaining_usd: float
    calls: int


class WorkspaceResponse(PublicResponse):
    """Small workspace overview without machine paths or credential material."""

    budget: BudgetView
    task_count: int
    run_count: int
    session_token: str = ""
    model: str = ""
    readiness: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)
    supported_actions: list[str] = Field(default_factory=list)


class TaskSummary(PublicResponse):
    """One configured MCP surface or historical corpus task."""

    id: str
    kind: Literal["mcp", "corpus"]
    name: str
    description: str
    status: str
    created_at: str | None = None
    active_kernel_id: str | None = None
    latest_kernel_id: str | None = None
    selected_kernel_id: str | None = None
    run_count: int = 0
    query_count: int = 0
    legacy: bool = False


class TaskListResponse(PublicResponse):
    """Configured tasks, newest first when dates were recorded."""

    items: list[TaskSummary]


class TaskResponse(TaskSummary):
    """Setup and public requests associated with a task."""

    base_prompt: str = ""
    queries: list[dict[str, Any]] = Field(default_factory=list)
    connections: list[dict[str, Any]] = Field(default_factory=list)
    limits: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Assessment(BaseModel):
    """Independent evaluation identity, scope, result, and evidence."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["not_checked", "passed", "failed", "unable_to_check"] = "not_checked"
    evaluator: str | None = None
    evaluator_version: str | None = None
    result: Any = None
    scope: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class RunSummary(PublicResponse):
    """Execution lifecycle, agent outcome, and assessment are separate fields."""

    id: str
    task_id: str
    kind: str
    status: Literal["queued", "running", "completed", "failed", "interrupted"]
    created_at: str
    query: str | None = None
    query_id: str | None = None
    split: str | None = None
    kernel_id: str | None = None
    root_run_id: str | None = None
    parent_run_id: str | None = None
    answer: str | None = None
    outcome: Literal["complete", "needs_input", "unresolved"] | None = None
    assessment: Assessment = Field(default_factory=Assessment)


class RunResponse(RunSummary):
    """Run header and stable cursor information for replay or live observation."""

    event_count: int = 0
    last_cursor: str = "0"
    artifact_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    graph_id: str | None = None
    initial_graph_id: str | None = None
    error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)


class KernelSummary(PublicResponse):
    """An immutable kernel with its actual parent and construction case links."""

    id: str
    task_id: str
    parent_id: str | None = None
    created_at: str | None = None
    run_id: str | None = None
    name: str
    assessment: Assessment = Field(default_factory=Assessment)
    eligible_for_inference: bool = False
    validation: dict[str, Any] = Field(default_factory=dict)
    case_links: list[dict[str, Any]] = Field(default_factory=list)
    schema_id: str | None = None
    graph_id: str | None = None
    construction_profile: str | None = None
    flow_evidence: dict[str, list[str]] = Field(default_factory=dict)


class ConstructionAttempt(PublicResponse):
    """An attempt can retain schema evidence without producing a kernel."""

    run_id: str
    status: str
    created_at: str
    round_index: int | None = None
    kernel_id: str | None = None
    parent_kernel_id: str | None = None
    case_links: list[dict[str, Any]] = Field(default_factory=list)
    schema_id: str | None = None
    schema_artifact_ref: str | None = None
    schema_view: dict[str, Any] | None = None
    validation: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class HistoryResponse(PublicResponse):
    """Recorded runs, kernel revisions, and failed construction attempts."""

    task_id: str
    runs: list[RunSummary]
    kernels: list[KernelSummary]
    attempts: list[ConstructionAttempt]


class ArtifactReference(BaseModel):
    """An immutable evidence reference and its role in an event."""

    id: str
    role: str


class EventEnvelope(PublicResponse):
    """Durable event cursor plus a bounded, sanitized evidence projection."""

    cursor: str
    occurred_at: str
    task_id: str
    run_id: str
    root_run_id: str | None = None
    parent_run_id: str | None = None
    step_id: str | None = None
    parent_step_id: str | None = None
    flow: Literal["learning", "verification", "instantiation"] | None = None
    type: Literal[
        "run.lifecycle",
        "stage.status",
        "decision.recorded",
        "observation.recorded",
        "graph.snapshot",
        "kernel.candidate",
        "validation.recorded",
        "assessment.recorded",
        "usage.recorded",
        "evidence.recorded",
    ]
    stage: str
    summary: str
    artifact_refs: list[ArtifactReference] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class EventsResponse(PublicResponse):
    """A bounded event page pinned to a replay watermark."""

    run_id: str
    items: list[EventEnvelope]
    next_cursor: str
    through: str
    has_more: bool


class KernelResponse(KernelSummary):
    """Canonical definitions and readable presentation of one frozen kernel."""

    schema_definition: dict[str, Any] = Field(alias="schema")
    functions: list[dict[str, Any]]
    schema_view: dict[str, Any]
    artifact_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class KernelDiffResponse(PublicResponse):
    """Structural comparison of recorded definitions, without equivalence claims."""

    id: str
    against: str
    changes: list[dict[str, Any]]
    schema_changed: bool
    functions_changed: bool
    same_task: bool
    is_parent: bool
    limitations: list[str] = Field(default_factory=list)


class GraphResponse(PublicResponse):
    """A bounded view of actual graph records, with explicit omission counts."""

    id: str
    source_artifact_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    total_nodes: int
    total_edges: int
    shown_nodes: int
    shown_edges: int
    omitted_nodes: int
    omitted_edges: int
    scope: str
    limitations: list[str] = Field(default_factory=list)


class ArtifactResponse(PublicResponse):
    """Sanitized projection with distinct source and projection hashes."""

    id: str
    kind: str
    source_sha256: str
    projection_sha256: str
    redacted: bool
    redacted_fields: list[str]
    data: Any
    typed_data: (
        TaskIR
        | CandidateSelection
        | EvidenceDemand
        | MaterializationPlan
        | CoverageReceipt
        | SufficiencyResult
        | VerificationReport
        | PreservationCertificate
        | None
    ) = None
    provenance: dict[str, Any] | None = None
    limitations: list[str] = Field(default_factory=list)


class AcceptedRun(PublicResponse):
    """An admitted background job, distinct from its eventual result."""

    run_id: str
    status: str
    operation: str
    task_id: str | None = None
    reused: bool = False


class DiscoveryResponse(PublicResponse):
    """Observed connector capabilities and discovery failure evidence."""

    id: str
    run_id: str
    status: str
    connection: dict[str, Any]
    catalog: dict[str, Any] | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    error: str | None = None


class ConnectorResponse(PublicResponse):
    """A saved connector bound to its genuine discovery receipt."""

    connector_id: str
    discovery_id: str
    configuration: dict[str, Any]
    catalog: dict[str, Any]


class ConnectorListResponse(PublicResponse):
    """Saved connections available during task setup."""

    items: list[ConnectorResponse]


class TaskCreatedResponse(PublicResponse):
    """Identifiers of a persisted MCP task surface."""

    task_id: str
    surface_id: str
    kind: Literal["mcp"] = "mcp"


class ErrorResponse(PublicResponse):
    """Actionable failure without raw diagnostic or credential material."""

    code: str
    message: str
    retryable: bool
    evidence_refs: list[str] = Field(default_factory=list)


class DiscoveryRequest(BaseModel):
    """Explicit connection configuration for one real discovery job."""

    model_config = ConfigDict(extra="forbid")
    connection: ConnectionConfig


class ConnectorRequest(BaseModel):
    """Select permitted tools from a completed discovery."""

    model_config = ConfigDict(extra="forbid")
    discovery_id: str
    allowed_tools: list[str] = Field(min_length=1)


class TaskCreateRequest(BaseModel):
    """Curator-owned task inputs reusing the authoritative task contracts."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    base_prompt: str = Field(min_length=1)
    queries: list[QuerySpec] = Field(min_length=1)
    connector_ids: list[str] = Field(min_length=1)
    limits: RunLimits = Field(default_factory=RunLimits)
    seed: int = Field(default=42, ge=0)
    sampling_fraction: float = Field(default=0.2, gt=0, le=1)


class RunCreateRequest(BaseModel):
    """Start bounded construction or inference against a chosen kernel."""

    model_config = ConfigDict(extra="forbid")
    operation: Literal["construct", "infer"]
    kernel_id: str | None = None
    query: str | None = None
    requirements: list[str] = Field(default_factory=list)
    query_id: str | None = None

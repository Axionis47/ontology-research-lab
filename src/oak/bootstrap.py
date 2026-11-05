"""Real MCP episode collection and task-conditioned, frozen S/F execution.

This user extension starts without an answer corpus. Bootstrap observes real
capabilities; construction consumes those receipts; kernel inference acquires
fresh evidence through explicit bindings. Existing corpus tasks stay separate.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Literal, TypedDict

from jsonschema import SchemaError, ValidationError
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from oak.construction_contracts import (
    FunctionCoverage,
    RequirementAnalysis,
    requirement_inputs,
    validate_function_coverage,
    validate_requirement_analysis,
)
from oak.construction_prompts import prompt_manifest
from oak.functions import FunctionExecutionError, FunctionSpec, execute_function, validate_functions
from oak.learning import candidate_rank, compare_fresh_runs, freeze_task_ir, repair_feedback
from oak.learning_contracts import CandidateSelection, TaskIR
from oak.materialization import (
    MATERIALIZATION_VERSION,
    MaterializationPlan,
    assess_sufficiency,
    derive_demand,
    materialization_cache_key,
)
from oak.mcp_bridge import MCPBridge
from oak.model import GeminiCLI, runtime_config
from oak.ontology import schema_json_schema, validate_graph_records, validate_ontology
from oak.operators import GRAPH_OPERATORS, operator_contracts
from oak.pipeline import build_graph, request_json
from oak.store import Store, canonical, now
from oak.task_context import InferenceQuery, TaskSurface, build_runtime_context, sample_construction
from oak.verification import GeneratedCheckSpec, execute_generated_check

PROJECT = Path(__file__).resolve().parents[2]


class Decision(BaseModel):
    """Public decision record, not a claim to expose private model reasoning."""

    model_config = ConfigDict(extra="forbid")
    action: Literal["call", "complete", "clarify", "unresolved"]
    function: str | None = None
    args: dict = Field(default_factory=dict)
    answer: str = ""
    citations: list[str] = Field(default_factory=list)
    reason: str


class EpisodeState(TypedDict, total=False):
    """Small checkpoint state referencing immutable observation artifacts."""

    step: int
    decision: dict
    observations: list[dict]
    trajectory: list[dict]
    graph_id: str
    terminal: dict
    invocation_attempts: int
    tool_calls: int
    completed_tool_calls: int
    receipt_cache: dict[str, str]
    materializations: dict[str, str]


class FunctionProbe(BaseModel):
    """Real input proposed to exercise one generated callable."""

    model_config = ConfigDict(extra="forbid")
    function: str
    args: dict


class FunctionProposal(BaseModel):
    """Bounded model output for one candidate function catalog and its probes."""

    model_config = ConfigDict(extra="forbid")
    functions: list[FunctionSpec] = Field(min_length=1, max_length=64)
    probes: list[FunctionProbe] = Field(min_length=1, max_length=64)
    coverage: list[FunctionCoverage] = Field(min_length=1)
    generated_checks: list[GeneratedCheckSpec] = Field(default_factory=list, max_length=64)


def function_dataflow(function: dict) -> dict:
    """Trace declared result dependencies, including reads of executor-updated G.

    This is a data-dependency witness, not proof that a function solves its task.
    Graph reads conservatively depend on earlier acquisition steps in this function.
    """

    def references(value):
        if isinstance(value, dict):
            if set(value) == {"$step"}:
                return {value["$step"]}
            if set(value) == {"$path"}:
                return {value["$path"][0]}
            return set().union(*(references(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(references(item) for item in value))
        return set()

    dependencies, acquisitions, computations = {}, set(), set()
    for step in function["steps"]:
        parents = references(step["args"])
        if step["operator"] in GRAPH_OPERATORS:
            parents.update(acquisitions)
        dependencies[step["id"]] = {step["id"]}.union(*(dependencies[parent] for parent in parents))
        if step["operator"] == "invoke_capability":
            acquisitions.add(step["id"])
        elif dependencies[step["id"]].intersection(acquisitions):
            computations.add(step["id"])
    result_steps = set().union(*(dependencies[step] for step in references(function["result"])))
    return {
        "result_steps": sorted(result_steps),
        "result_acquisition_steps": sorted(result_steps & acquisitions),
        "acquisition_computation_steps": sorted(result_steps & computations),
    }


def result_acquisition_evidence(
    function: dict, execution: dict, graph: dict, receipts: list[dict]
) -> list[str]:
    """Find actual current-episode acquisitions supporting the executed result.

    Direct invocation results carry receipt IDs. Graph reads use conservative G
    provenance, and entity/projection operations retain their input provenance.
    Independent task checks still establish relevance, completeness, and correctness.
    """
    actual = {
        receipt["evidence_id"]: receipt
        for receipt in receipts
        if receipt.get("status") == "completed" and receipt.get("tool_call_attempted")
    }
    documents = {
        document["document_id"]: identity
        for identity, receipt in actual.items()
        for document in receipt_documents(receipt)
    }

    def sources(value):
        if isinstance(value, dict):
            found = {
                documents[source["document_id"]]
                for key in ("sources", "__sources")
                for source in value.get(key, [])
                if isinstance(source, dict) and source.get("document_id") in documents
            }
            return found.union(*(sources(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(sources(item) for item in value))
        return set()

    relevant = set(function_dataflow(function)["result_steps"])
    evidence = set()
    invocation_ids = {
        step.get("output", {}).get("receipt_id")
        for step in execution["steps"]
        if step["operator"] == "invoke_capability" and step["status"] == "completed"
    }
    available = set(actual) - invocation_ids
    for step in execution["steps"]:
        if step["operator"] == "invoke_capability" and step["status"] == "completed":
            identity = step["output"].get("receipt_id")
            if identity in actual:
                available.add(identity)
        if step["id"] not in relevant or step["status"] != "completed":
            continue
        if step["operator"] == "invoke_capability":
            identity = step["output"].get("receipt_id")
            if identity in actual:
                evidence.add(identity)
        if step["operator"] in GRAPH_OPERATORS:
            evidence.update(sources(graph) & available)
        evidence.update(sources(step["inputs"]) & available)
    return sorted(evidence)


def sampled_episode_summary(episode_id: str, episode: dict) -> dict:
    """Expose actual construction behavior without treating old answers as truth."""
    return {
        "episode_id": episode_id,
        "query_id": episode["query_id"],
        "terminal_status": episode["status"],
        "assessment": episode.get("assessment", {"status": "unmeasured"}),
        "decisions": [
            {key: decision.get(key) for key in ("action", "function", "args", "citations")}
            for decision in episode.get("trajectory", [])
        ],
        "observations": [
            {
                key: observation.get(key)
                for key in ("id", "function", "status", "error", "receipt_ids", "execution_id")
            }
            for observation in episode.get("observations", [])
        ],
    }


def receipt_documents(receipt: dict) -> list[dict]:
    """Convert actual MCP output to bounded source text with receipt attribution."""
    if receipt["status"] != "completed":
        return []
    output = receipt["output"]
    body = (
        output["structuredContent"]
        if output.get("structuredContent") is not None
        else output.get("content", output)
    )
    text = json.dumps(body, ensure_ascii=False, indent=2)
    header = json.dumps(
        {
            "capability": receipt["capability_id"],
            "arguments": receipt.get("args", {}),
            "started_at": receipt.get("started_at"),
            "finished_at": receipt.get("finished_at"),
            "contract_id": receipt.get("contract_id"),
            "receipt_id": receipt["evidence_id"],
        },
        ensure_ascii=False,
    )
    if len(header.encode()) > 1500:
        raise ValueError("Capability arguments exceed the bounded extraction header")
    return [
        {
            "document_id": f"{receipt['evidence_id']}-{offset}",
            "source_id": receipt["evidence_id"],
            "locator": f"mcp:{receipt['capability_id']}#characters={offset}:{offset + 2500}",
            "text": header + "\n" + text[offset : offset + 2500],
        }
        for offset in range(0, len(text), 2500)
    ]


def merge_observations(schema: dict, graph: dict, incoming: dict) -> dict:
    """Append grounded facts; reject ambiguous conflicting values instead of overwriting."""
    result = deepcopy(graph)
    nodes = {node["id"]: node for node in result["nodes"]}
    for node in incoming["nodes"]:
        if node["id"] not in nodes:
            nodes[node["id"]] = deepcopy(node)
            continue
        old = nodes[node["id"]]
        for key, value in node["properties"].items():
            if key in old["properties"] and old["properties"][key] != value:
                raise ValueError(f"Conflicting observed state for {node['type']}.{key}")
            old["properties"][key] = value
        old["sources"] = list({canonical(x): x for x in old["sources"] + node["sources"]}.values())
    result["nodes"] = list(nodes.values())
    edges = {}
    for edge in result["edges"] + incoming["edges"]:
        key = (edge["source"], edge["target"], edge["relation"])
        existing = edges.setdefault(key, {**edge, "sources": []})
        existing["sources"] = list(
            {canonical(x): x for x in existing["sources"] + edge["sources"]}.values()
        )
    result["edges"] = list(edges.values())
    # A repeated materialization of one receipt must not invent additional source
    # documents. Historical graphs lacking explicit IDs retain an attributed
    # additive count because their overlap cannot be reconstructed from counts.
    known_documents = all(
        "source_document_ids" in item or item.get("source_document_count", 0) == 0
        for item in (graph, incoming)
    )
    if known_documents:
        source_ids = sorted(
            set(graph.get("source_document_ids", [])) | set(incoming.get("source_document_ids", []))
        )
        result["source_document_ids"] = source_ids
        result["source_document_count"] = len(source_ids)
        result["source_document_count_basis"] = "unique_recorded_ids"
    else:
        result.pop("source_document_ids", None)
        result["source_document_count"] += incoming["source_document_count"]
        result["source_document_count_basis"] = "legacy_additive_overlap_unknown"
    result["ignored_documents"] = list(
        {
            canonical(item): item
            for item in result.get("ignored_documents", []) + incoming.get("ignored_documents", [])
        }.values()
    )
    check = validate_graph_records(schema, result["nodes"], result["edges"])
    if not check["valid"]:
        raise ValueError(f"Merged graph is invalid: {check['errors']}")
    return result


def empty_graph() -> dict:
    """An episode begins without invented external observations."""
    return {"nodes": [], "edges": [], "source_document_count": 0, "ignored_documents": []}


def acquisition_result(schema: dict, graph: dict, incoming: dict, receipt_id: str) -> dict:
    """Expose typed records from this response, without unrelated accumulated facts."""
    identities = {node["id"] for node in incoming["nodes"]}
    entities = [node for node in graph["nodes"] if node["id"] in identities]
    return {
        "entities": entities,
        "entities_by_type": {
            name: [node for node in entities if node["type"] == name]
            for name in schema["entity_types"]
        },
        "receipt_id": receipt_id,
    }


class SurfaceEngine:
    """CLI-facing, observable MCP surface lifecycle within the existing artifact store."""

    def __init__(self, root: str | Path = ".local"):
        self.store = Store(root)
        with self.store.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS mcp_surfaces "
                "(id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL)"
            )

    def onboard(self, configuration: dict) -> dict:
        """Discover configured capabilities without a corpus, model call, or kernel."""
        surface = TaskSurface.model_validate(configuration)
        identity = uuid.uuid4().hex
        run_id = self.store.create_run(identity, "mcp_onboard", {"surface": surface.model_dump()})
        try:
            catalog = MCPBridge(surface.servers, self.store, run_id).discover()
            budget = self.store.budget(runtime_config()["total_budget_usd"])
            data = {
                "surface_id": identity,
                "configuration": surface.model_dump(mode="json"),
                "catalog": catalog,
                "created_at": now(),
                "budget_ceiling_usd": min(
                    budget["limit_usd"],
                    budget["estimated_usd"]
                    + budget["reserved_usd"]
                    + surface.limits.max_new_spend_usd,
                ),
            }
            artifact_id = self.store.put("mcp_surface", data)
            with self.store.connect() as connection:
                connection.execute("INSERT INTO mcp_surfaces VALUES (?,?)", (identity, artifact_id))
            result = {"surface_id": identity, "artifact_id": artifact_id, "run_id": run_id}
            self.store.set_run(run_id, "completed", result=result)
            return result
        except Exception as exc:
            self.store.set_run(run_id, "failed", error=f"{type(exc).__name__}: {exc}")
            raise

    def surface(self, identity: str) -> dict:
        """Return the hash-verified onboarding artifact."""
        rows = self.store.rows("SELECT artifact_id FROM mcp_surfaces WHERE id=?", (identity,))
        if not rows:
            raise ValueError("Unknown MCP surface")
        return self.store.get(rows[0]["artifact_id"])

    def history(self, surface_id: str) -> list[str]:
        """Return construction episodes only; context validation rechecks their receipts."""
        histories = []
        for row in self.store.rows(
            "SELECT result_id FROM runs WHERE task_id=? AND kind='mcp_episode' "
            "AND status='completed' ORDER BY created_at",
            (surface_id,),
        ):
            result = self.store.get(row["result_id"])
            episode_id = result.get("episode_id")
            if episode_id and self.store.get(episode_id)["split"] == "construction":
                histories.append(episode_id)
        return histories

    def construct(
        self,
        surface_id: str,
        *,
        round_index: int = 0,
        parent_id: str | None = None,
        run_id: str | None = None,
    ) -> dict:
        """Run bounded learning rounds, consuming independent verifier reports.

        Every round is a separate owned child run. The original requirement
        bank is frozen once, candidates are immutable, and a failed later
        revision never replaces the retained eligible winner.
        """
        from oak.verification import (
            KernelCandidate,
            ObligationCheck,
            ObservedCheck,
            verify_candidate,
        )

        data = self.surface(surface_id)
        surface = TaskSurface.model_validate(data["configuration"])
        managed = run_id is not None
        if run_id is None:
            run_id = self.store.create_run(
                surface_id,
                "mcp_construct",
                {
                    "surface_id": surface_id,
                    "parent_id": parent_id,
                    "construction_profile": "demand_v1",
                    "round_index": round_index,
                },
            )
        else:
            self._check_run(run_id, surface_id, "mcp_construct")
        self.store.set_run(run_id, "running")
        seen: list[str] = []
        task_ir_id = None
        generated_bank_id = None
        candidates, verification_ids, attempts = [], [], []
        ranks: dict[str, list[float]] = {}
        best_id, best_rank = parent_id, None
        best_fresh: dict[str, dict] = {}
        best_verification_inputs = None
        best_measured_cost = 0.0
        feedback, last_failure = None, None
        stop_reason, target_met = "round_limit", False
        try:
            for offset in range(runtime_config()["max_construction_rounds"]):
                index = round_index + offset
                child = self.store.create_run(
                    surface_id,
                    "mcp_construct",
                    {
                        "construction_profile": "demand_v1",
                        "round_index": index,
                        "parent_id": best_id,
                        "task_ir_id": task_ir_id,
                    },
                    parent_run_id=run_id,
                )
                attempt = {"run_id": child, "round_index": index}
                attempts.append(attempt)
                try:
                    result = self._construct_round(
                        surface_id,
                        round_index=index,
                        parent_id=best_id,
                        run_id=child,
                        task_ir_id=task_ir_id,
                        seen_query_ids=seen,
                        repair=feedback,
                        generated_bank_id=generated_bank_id,
                    )
                except (ValueError, KeyError, TypeError, ValidationError, SchemaError) as exc:
                    self.store.set_run(child, "failed", error=f"{type(exc).__name__}: {exc}")
                    attempt["error"] = f"{type(exc).__name__}: {exc}"
                    # Even a failed candidate must retain the same bank next round.
                    for row in self.store.rows(
                        "SELECT artifact_id FROM events WHERE run_id=? AND stage='task_ir' ORDER BY id",
                        (child,),
                    ):
                        task_ir_id = self.store.get(row["artifact_id"])["task_ir_id"]
                    failure = str(exc)
                    feedback = {"repair_target": "construction", "message": failure}
                    if failure == last_failure:
                        stop_reason = "repeated_failure"
                        break
                    last_failure = failure
                    continue
                except RuntimeError as exc:
                    self.store.set_run(child, "failed", error=f"{type(exc).__name__}: {exc}")
                    attempt["error"] = f"{type(exc).__name__}: {exc}"
                    stop_reason = "execution_boundary_failure"
                    break
                except Exception as exc:
                    self.store.set_run(child, "failed", error=f"{type(exc).__name__}: {exc}")
                    raise
                identity = result["kernel_id"]
                kernel = self.store.get(identity)
                candidate_generated = self.store.get(kernel["evidence"]["generated_checks_id"])
                new_generated_bank = generated_bank_id is None and any(
                    item.get("outcome", {}).get("contributes_to_learning")
                    for item in candidate_generated
                )
                if new_generated_bank:
                    generated_bank_id = kernel["evidence"]["generated_checks_id"]
                task_ir_id = kernel["evidence"]["task_ir_id"]
                bank = TaskIR.model_validate(self.store.get(task_ir_id))
                seen = sorted(set(seen) | set(kernel["sample"]["selected_query_ids"]))
                candidates.append(identity)
                attempt["kernel_id"] = identity
                mapping = {
                    item["obligation_id"]: item["function_names"]
                    for item in self.store.get(kernel["evidence"]["coverage_id"])["mappings"]
                }
                checks = [
                    ObligationCheck(
                        id=item.obligation_id,
                        group=item.group,
                        mandatory=item.mandatory,
                        function_names=mapping.get(item.obligation_id, []),
                        semantic_status=item.semantic_status,
                        oracle_ref=item.oracle_ref,
                    )
                    for item in bank.obligations
                ]
                observations = []
                probes = self.store.get(kernel["evidence"]["probes_id"])
                for obligation in checks:
                    for probe in probes:
                        if probe["probe"]["function"] not in obligation.function_names:
                            continue
                        payload = {
                            **probe,
                            "candidate_id": identity,
                            "probe_evidence_id": probe["evidence_id"],
                            "function": probe["probe"]["function"],
                            "args": probe["probe"]["args"],
                            "value": probe.get("execution", {}).get("value"),
                            "run_id": child,
                        }
                        evidence_ref = self.store.put("candidate_execution_evidence", payload)
                        observations.append(
                            ObservedCheck(
                                obligation_id=obligation.id,
                                dimension="execution",
                                evidence_ref=evidence_ref,
                            )
                        )
                for generated in self.store.get(kernel["evidence"]["generated_checks_id"]):
                    payload = {
                        "candidate_id": identity,
                        "graph_id": generated["graph_id"],
                        "check": generated["check"],
                        "source_schema_sha256": generated["source_schema_sha256"],
                    }
                    evidence_ref = self.store.put("generated_check_evidence", payload)
                    observations.append(
                        ObservedCheck(
                            obligation_id=generated["check"]["obligation_id"],
                            dimension="generated",
                            evidence_ref=evidence_ref,
                            evaluator_id="generated_dsl_v1",
                        )
                    )
                candidate = KernelCandidate(
                    id=identity,
                    schema=kernel["schema"],
                    functions=kernel["functions"],
                    parent_id=best_id,
                )
                previous = self.store.get(best_id) if best_id else None
                parent_candidate = (
                    KernelCandidate(
                        id=best_id,
                        schema=previous["schema"],
                        functions=previous["functions"],
                        parent_id=previous.get("parent"),
                    )
                    if previous
                    else None
                )
                verification_inputs = {
                    "candidate": candidate,
                    "obligations": checks,
                    "evidence": observations,
                    "store": self.store,
                    "parent": parent_candidate,
                    "ontology_validation_ref": kernel["evidence"]["validation_id"],
                }
                if new_generated_bank and best_verification_inputs is not None:
                    prior_inputs = dict(best_verification_inputs)
                    prior_observations = [
                        item for item in prior_inputs["evidence"] if item.dimension != "generated"
                    ]
                    for generated in candidate_generated:
                        evidence_ref = self.store.put(
                            "generated_check_evidence",
                            {
                                "candidate_id": best_id,
                                "graph_id": generated["graph_id"],
                                "check": generated["check"],
                                "source_schema_sha256": generated["source_schema_sha256"],
                            },
                        )
                        prior_observations.append(
                            ObservedCheck(
                                obligation_id=generated["check"]["obligation_id"],
                                dimension="generated",
                                evidence_ref=evidence_ref,
                                evaluator_id="generated_dsl_v1",
                            )
                        )
                    prior_inputs["evidence"] = prior_observations
                    prior_report = verify_candidate(**prior_inputs).model_dump(mode="json")
                    prior_id = self.store.put("candidate_verification", prior_report)
                    verification_ids.append(prior_id)
                    self.store.event(
                        run_id,
                        "candidate_verification",
                        "completed",
                        "Retained candidate checked against the same generated bank",
                        {
                            "flow": "verification",
                            "kernel_id": best_id,
                            "verification_id": prior_id,
                            "generated_bank_id": generated_bank_id,
                            **prior_report,
                        },
                    )
                    prior_failures = compare_fresh_runs({}, list(best_fresh.values()))["failures"]
                    best_rank = (
                        0.0,
                        float(len(prior_failures)),
                        *candidate_rank(
                            prior_report, self.store.get(best_id), measured_cost=best_measured_cost
                        ),
                    )
                    ranks[best_id] = list(best_rank)
                    best_verification_inputs = prior_inputs
                report = verify_candidate(**verification_inputs)
                report_data = report.model_dump(mode="json")
                verification_id = self.store.put("candidate_verification", report_data)
                verification_ids.append(verification_id)
                self.store.event(
                    child,
                    "candidate_verification",
                    "completed",
                    "Independent verification evidence",
                    {
                        "flow": "verification",
                        "kernel_id": identity,
                        "verification_id": verification_id,
                        **report_data,
                    },
                )
                target_met = bool(report_data.get("target_met"))
                feedback = repair_feedback(report_data)
                fresh = []
                boundary_failure = None
                if report_data.get("execution_eligible"):
                    fresh_query_ids = sorted(
                        set(kernel["sample"]["selected_query_ids"]) | set(best_fresh)
                    )
                    for query_id in fresh_query_ids:
                        try:
                            episode = self.run_episode(
                                surface_id, query_id, kernel_id=identity, parent_run_id=child
                            )
                        except RuntimeError as exc:
                            boundary_failure = f"{type(exc).__name__}: {exc}"
                            stop_reason = "execution_boundary_failure"
                            break
                        fresh.append(
                            {
                                "query_id": query_id,
                                "run_id": episode["run_id"],
                                "episode_id": episode["episode_id"],
                                "status": episode["episode"]["status"],
                                "assessment": episode.get("assessment"),
                            }
                        )
                    self.store.event(
                        child,
                        "fresh_agent_execution",
                        "completed",
                        "Fresh agent results remain distinct from generated checks",
                        {
                            "flow": "verification",
                            "kernel_id": identity,
                            "episodes": fresh,
                            "boundary_failure": boundary_failure,
                        },
                    )
                spend = self.store.rows(
                    "WITH RECURSIVE family(id) AS (SELECT id FROM runs WHERE id=? UNION ALL "
                    "SELECT r.id FROM runs r JOIN family f ON r.parent_run_id=f.id) "
                    "SELECT SUM(estimated) AS estimated,SUM(CASE WHEN status!='settled' THEN reserved ELSE 0 END) AS reserved "
                    "FROM model_calls WHERE run_id IN (SELECT id FROM family)",
                    (child,),
                )[0]
                rank = candidate_rank(
                    report_data,
                    kernel,
                    measured_cost=float(spend["estimated"] or 0) + float(spend["reserved"] or 0),
                )
                comparison = compare_fresh_runs(best_fresh, fresh)
                if comparison["failures"]:
                    feedback["fresh_agent_failures"] = [
                        item for item in fresh if item["query_id"] in comparison["failures"]
                    ]
                rank = (
                    float(len(comparison["regressions"])),
                    float(len(comparison["failures"])),
                    *rank,
                )
                ranks[identity] = list(rank)
                self.store.event(
                    child,
                    "candidate_comparison",
                    "completed",
                    "Compared fresh behavior before candidate selection",
                    {
                        "flow": "learning",
                        "kernel_id": identity,
                        "previous_kernel_id": best_id,
                        "comparison": comparison,
                        "rank": list(rank),
                    },
                )
                if (
                    report_data.get("execution_eligible")
                    and not report_data.get("known_regressions", 0)
                    and not comparison["regressions"]
                    and not comparison["unexecuted_previous"]
                ):
                    if best_rank is None or rank < best_rank:
                        best_id, best_rank = identity, rank
                        best_fresh = {item["query_id"]: item for item in fresh}
                        best_verification_inputs = verification_inputs
                        best_measured_cost = float(spend["estimated"] or 0) + float(
                            spend["reserved"] or 0
                        )
                target_met = target_met and not comparison["failures"] and boundary_failure is None
                if boundary_failure:
                    break
                if target_met:
                    stop_reason = "construction_target_met"
                    break
                pool_ids = {q.id for q in surface.queries if q.split == "construction"}
                if (
                    pool_ids.issubset(seen)
                    and not report_data.get("counterexamples")
                    and not feedback.get("fresh_agent_failures")
                    and not feedback.get("actionable_learning_gaps")
                ):
                    stop_reason = "sampled_task_surface"
                    break
            selection = CandidateSelection(
                task_ir_id=task_ir_id or "",
                candidate_ids=candidates,
                selected_kernel_id=best_id,
                verification_ids=verification_ids,
                disposition="target_met"
                if target_met
                else ("incomplete" if best_id else "rejected"),
                stop_reason=stop_reason,
                ranks=ranks,
            )
            selection_id = self.store.put("candidate_selection", selection.model_dump(mode="json"))
            self.store.event(
                run_id,
                "candidate_selection",
                "completed",
                "Learning retained the best eligible candidate",
                {
                    "flow": "learning",
                    "selection_id": selection_id,
                    **selection.model_dump(mode="json"),
                },
            )
            output = {
                "run_id": run_id,
                "kernel_id": best_id,
                "candidate_ids": candidates,
                "selection_id": selection_id,
                "task_ir_id": task_ir_id,
                "verification_ids": verification_ids,
                "attempts": attempts,
                "assessment": {
                    "construction": selection.disposition,
                    "fresh_task_success": "unmeasured",
                },
            }
            self.store.set_run(run_id, "completed", result=output)
            return output
        except Exception as exc:
            if not managed:
                self.store.set_run(run_id, "failed", error=f"{type(exc).__name__}: {exc}")
            raise

    def _construct_round(
        self,
        surface_id: str,
        *,
        round_index: int = 0,
        parent_id: str | None = None,
        run_id: str | None = None,
        task_ir_id: str | None = None,
        seen_query_ids: list[str] | None = None,
        repair: dict | None = None,
        generated_bank_id: str | None = None,
    ) -> dict:
        """Construct a candidate from a recorded fresh sample and genuine starter episodes.

        Real OWL and function probes are admission evidence, not an independent
        task-success score. Candidates remain explicitly unpromoted until an
        external task evaluator records fresh outcome evidence.
        """
        managed_run = run_id is not None
        data = self.surface(surface_id)
        surface = TaskSurface.model_validate(data["configuration"])
        parent = self.store.get(parent_id) if parent_id else None
        if parent and parent.get("surface_id") != surface_id:
            raise ValueError("Parent belongs to another surface")
        sample = sample_construction(
            surface, round_index, seen_query_ids=seen_query_ids
        ).model_dump(mode="json")
        request = {
            "surface_id": surface_id,
            "sample": sample,
            "parent_id": parent_id,
            "budget_ceiling_usd": data["budget_ceiling_usd"],
        }
        if run_id is None:
            run_id = self.store.create_run(surface_id, "mcp_construct", request)
        else:
            self._check_run(run_id, surface_id, "mcp_construct")
            self.store.event(
                run_id, "construction_request", "completed", "Actual construction sample", request
            )
        model = GeminiCLI(self.store, run_id, budget_ceiling_usd=data["budget_ceiling_usd"])
        prompts = prompt_manifest()
        prompt_manifest_id = self.store.put("construction_prompts", prompts)
        catalog = data["catalog"]
        bridge = MCPBridge(surface.servers, self.store, run_id, expected_catalog=catalog)
        selected = [q for q in surface.queries if q.id in sample["selected_query_ids"]]
        obligations = requirement_inputs([q for q in surface.queries if q.split == "construction"])
        requirements_input = {
            "surface": surface.description,
            "starting_instructions": surface.base_prompt,
            "obligations": [item.model_dump(mode="json") for item in obligations],
            "capabilities": catalog["tools"],
        }
        requirements_input_id = self.store.put("requirement_inputs", requirements_input)

        def analyze(state):
            if task_ir_id:
                bank = TaskIR.model_validate(self.store.get(task_ir_id))
                if (
                    bank.source_sha256
                    != hashlib.sha256(
                        canonical([item.model_dump() for item in obligations])
                    ).hexdigest()
                ):
                    raise ValueError("Frozen TaskIR does not match the construction input bank")
                self.store.event(
                    run_id,
                    "task_ir",
                    "completed",
                    "Frozen task bank reused",
                    {
                        "flow": "learning",
                        "task_ir_id": task_ir_id,
                        "mandatory_obligations": sum(item.mandatory for item in bank.obligations),
                    },
                )
                return {
                    "requirements_id": bank.analysis_id,
                    "task_ir_id": task_ir_id,
                    "requirements_input_id": requirements_input_id,
                    "prompt_manifest_id": prompt_manifest_id,
                }
            feedback = None
            for attempt in range(runtime_config()["max_repair_attempts"] + 1):
                proposal = request_json(
                    model,
                    f"requirements.{attempt}",
                    prompts["stages"]["requirements"]["instruction"],
                    {**requirements_input, "validation_feedback": feedback},
                    RequirementAnalysis.model_json_schema(),
                )
                proposal_id = self.store.put("requirement_analysis_proposal", proposal)
                try:
                    analysis = validate_requirement_analysis(
                        proposal, obligations, {tool["id"] for tool in catalog["tools"]}
                    )
                except (ValueError, TypeError, ValidationError) as exc:
                    feedback = {
                        "message": str(exc),
                        "proposal_id": proposal_id,
                        "requirements_input_id": requirements_input_id,
                        "prompt_manifest_id": prompt_manifest_id,
                        "outcome_status": "not_checked",
                    }
                    self.store.event(
                        run_id,
                        "requirement_validation",
                        "failed",
                        "Requirement references need repair",
                        feedback,
                    )
                    continue
                analysis_id = self.store.put(
                    "requirement_analysis", analysis.model_dump(mode="json")
                )
                bank = freeze_task_ir(surface.description, obligations, analysis)
                bank.analysis_id = analysis_id
                frozen_id = self.store.put("task_ir", bank.model_dump(mode="json"))
                self.store.event(
                    run_id,
                    "task_ir",
                    "completed",
                    "Candidate-independent subtask bank frozen",
                    {
                        "flow": "learning",
                        "task_ir_id": frozen_id,
                        "mandatory_obligations": sum(item.mandatory for item in bank.obligations),
                        "exploratory_obligations": sum(
                            not item.mandatory for item in bank.obligations
                        ),
                        "exploration_omitted": bank.exploration_omitted,
                    },
                )
                self.store.event(
                    run_id,
                    "analyze",
                    "completed",
                    "Requirements interpreted; task coverage has not been evaluated",
                    {
                        "requirements_id": analysis_id,
                        "requirements_input_id": requirements_input_id,
                        "prompt_manifest_id": prompt_manifest_id,
                        "obligation_count": len(obligations),
                        "outcome_status": "not_checked",
                    },
                )
                return {
                    "requirements_id": analysis_id,
                    "requirements_input_id": requirements_input_id,
                    "prompt_manifest_id": prompt_manifest_id,
                    "task_ir_id": frozen_id,
                }
            raise ValueError(f"No valid requirement analysis within repair limit: {feedback}")

        def collect(state):
            episodes, documents = [], []
            for query in selected:
                episode = self.run_episode(surface_id, query.id, parent_run_id=run_id)
                episodes.append(episode["episode_id"])
                for observation in episode["episode"]["observations"]:
                    for receipt_id in observation.get("receipt_ids", []):
                        receipt = {**self.store.get(receipt_id), "evidence_id": receipt_id}
                        documents.extend(receipt_documents(receipt))
            if not documents:
                raise ValueError("Construction requires actual acquired evidence")
            return {
                "episodes_id": self.store.put("sample_episodes", episodes),
                "documents_id": self.store.put("acquired_documents", documents),
            }

        def draft(state):
            feedback = repair
            for attempt in range(runtime_config()["max_repair_attempts"] + 1):
                schema = request_json(
                    model,
                    f"schema.{attempt}",
                    prompts["stages"]["schema"]["instruction"],
                    {
                        "surface": surface.description,
                        "obligations": requirements_input["obligations"],
                        "requirements": self.store.get(state["requirements_id"]),
                        "task_ir": self.store.get(state["task_ir_id"]),
                        "capabilities": catalog["tools"],
                        "observations": self.store.get(state["documents_id"]),
                        "sampled_episodes": [
                            sampled_episode_summary(identity, self.store.get(identity))
                            for identity in self.store.get(state["episodes_id"])
                        ],
                        "previous_schema": parent["schema"] if parent else None,
                        "validation_feedback": feedback,
                    },
                    schema_json_schema(),
                )
                report = validate_ontology(
                    schema, self.store.root / "reasoner" / run_id / str(attempt)
                )
                schema_id = self.store.put("schema", schema)
                report = {
                    **report,
                    "schema_artifact_id": schema_id,
                    "requirements_id": state["requirements_id"],
                    "prompt_manifest_id": prompt_manifest_id,
                }
                self.store.event(
                    run_id,
                    "ontology_validation",
                    "passed" if report["valid"] else "failed",
                    "Actual OWL/HermiT candidate validation",
                    report,
                )
                if report["valid"]:
                    return {
                        "schema_id": schema_id,
                        "validation_id": self.store.put("ontology_validation", report),
                    }
                feedback = report
            raise ValueError("No logically valid schema within repair limit")

        def extract(state):
            graph = build_graph(
                self.store,
                model,
                self.store.get(state["schema_id"]),
                self.store.get(state["documents_id"]),
                "construction_extract",
                extraction_instruction=prompts["stages"]["extraction"]["instruction"],
                prompt_manifest_id=prompt_manifest_id,
            )
            return {"graph_id": self.store.put("construction_graph", graph)}

        def compose(state):
            schema = self.store.get(state["schema_id"])
            bank = TaskIR.model_validate(self.store.get(state["task_ir_id"]))
            mandatory = [item for item in bank.obligations if item.mandatory]
            error = repair
            tool_attempts = 0
            probe_receipt_cache: dict[str, str] = {}
            for attempt in range(runtime_config()["max_repair_attempts"] + 1):
                proposal = request_json(
                    model,
                    f"compose.{attempt}",
                    prompts["stages"]["functions"]["instruction"],
                    {
                        "surface": surface.description,
                        "queries": [q.model_dump() for q in selected],
                        "obligations": [item.model_dump(mode="json") for item in mandatory],
                        "task_ir": bank.model_dump(mode="json"),
                        "requirements": self.store.get(state["requirements_id"]),
                        "schema": schema,
                        "graph": self.store.get(state["graph_id"]),
                        "capabilities": catalog["tools"],
                        "operators": operator_contracts(),
                        "function_contract": FunctionSpec.model_json_schema(),
                        "generated_check_contract": GeneratedCheckSpec.model_json_schema(),
                        "frozen_generated_check_bank": self.store.get(generated_bank_id)
                        if generated_bank_id
                        else None,
                        "parent_functions": parent["functions"] if parent else None,
                        "sampled_episodes": [
                            sampled_episode_summary(identity, self.store.get(identity))
                            for identity in self.store.get(state["episodes_id"])
                        ],
                        "execution_feedback": error,
                    },
                    FunctionProposal.model_json_schema(),
                )
                proposal_id = self.store.put("function_proposal", proposal)
                try:
                    functions = [
                        f.model_dump(mode="json")
                        for f in validate_functions(proposal["functions"], schema)
                    ]
                    allowed = {t["id"] for t in catalog["tools"]}
                    for function in functions:
                        for step in function["steps"]:
                            if (
                                step["operator"] == "invoke_capability"
                                and step["args"]["capability"] not in allowed
                            ):
                                raise ValueError("Function binds an undiscovered capability")
                    if not any(
                        function_dataflow(f)["acquisition_computation_steps"] for f in functions
                    ):
                        raise ValueError("Acquisition-plus-computation witness is missing")
                    coverage = validate_function_coverage(
                        proposal["coverage"], mandatory, functions
                    )
                    coverage_id = self.store.event(
                        run_id,
                        "requirement_links",
                        "passed" if coverage.structurally_complete else "failed",
                        "Requirement links checked; task success remains Not checked",
                        {
                            **coverage.model_dump(mode="json"),
                            "requirements_id": state["requirements_id"],
                            "requirements_input_id": requirements_input_id,
                            "proposal_id": proposal_id,
                            "prompt_manifest_id": prompt_manifest_id,
                        },
                    )
                    if not coverage.valid:
                        raise ValueError(
                            "Requirement linkage is incomplete: " + "; ".join(coverage.gaps)
                        )
                    probes, covered, demands = [], set(), []
                    for index, probe in enumerate(proposal["probes"]):
                        function = next(
                            (f for f in functions if f["name"] == probe["function"]), None
                        )
                        if function is None:
                            raise ValueError("Probe names an absent function")
                        has_acquisition = any(
                            s["operator"] == "invoke_capability" for s in function["steps"]
                        )
                        graph = (
                            empty_graph()
                            if has_acquisition
                            else deepcopy(self.store.get(state["graph_id"]))
                        )
                        starting_graph_id = self.store.put("probe_starting_graph", graph)
                        acquired = []
                        demand = derive_demand(schema, function, probe["args"])
                        demands.append(demand.model_dump(mode="json"))

                        def acquire(
                            *,
                            capability,
                            arguments,
                            graph=graph,
                            acquired=acquired,
                            probe_stage=f"probe_extract.{attempt}.{index}",
                            demand=demand,
                        ):
                            nonlocal tool_attempts
                            request_key = hashlib.sha256(
                                canonical({"capability": capability, "arguments": arguments})
                            ).hexdigest()
                            if request_key in probe_receipt_cache:
                                receipt_id = probe_receipt_cache[request_key]
                                receipt = {
                                    **self.store.get(receipt_id),
                                    "evidence_id": receipt_id,
                                    "reused": True,
                                }
                            else:
                                if tool_attempts >= surface.limits.max_tool_calls:
                                    raise ValueError("Construction probe call bound reached")
                                tool_attempts += 1
                                receipt = bridge.invoke(capability, arguments)
                                probe_receipt_cache[request_key] = receipt["evidence_id"]
                            acquired.append(receipt)
                            if receipt["status"] != "completed":
                                raise ValueError(f"Real MCP probe failed: {receipt.get('error')}")
                            incoming = build_graph(
                                self.store,
                                model,
                                schema,
                                receipt_documents(receipt),
                                f"{probe_stage}.{tool_attempts}",
                                extraction_instruction=prompts["stages"]["extraction"][
                                    "instruction"
                                ],
                                prompt_manifest_id=prompt_manifest_id,
                                demand=demand,
                            )
                            merged = merge_observations(schema, graph, incoming)
                            graph.clear()
                            graph.update(merged)
                            return acquisition_result(
                                schema, graph, incoming, receipt["evidence_id"]
                            )

                        probe_record = {"probe": probe, "starting_graph_id": starting_graph_id}
                        try:
                            result = execute_function(
                                graph,
                                functions,
                                probe["function"],
                                probe["args"],
                                schema=schema,
                                capability_invoker=acquire,
                                step_observer=lambda step, probe=probe, index=index, attempt=attempt: (
                                    self.store.event(
                                        run_id,
                                        "operator",
                                        step["status"],
                                        f"Probe {probe['function']}: {step['id']}",
                                        {
                                            **step,
                                            "function": probe["function"],
                                            "phase": "probe",
                                            "probe_index": index,
                                            "attempt": attempt,
                                        },
                                    )
                                ),
                            )
                            probe_record["execution"] = result
                            proof = result_acquisition_evidence(function, result, graph, acquired)
                            if (
                                function_dataflow(function)["acquisition_computation_steps"]
                                and not proof
                            ):
                                raise ValueError(
                                    "Probe result lacks successful acquisition evidence"
                                )
                            probe_record.update(
                                status="passed", execution=result, acquisition_evidence_ids=proof
                            )
                            sufficiency = assess_sufficiency(schema, graph, demand)
                            probe_record["sufficiency"] = sufficiency.model_dump(mode="json")
                            probe_record["demand"] = demand.model_dump(mode="json")
                        except Exception as exc:
                            probe_record.update(
                                status="failed", error=f"{type(exc).__name__}: {exc}"
                            )
                            if isinstance(exc, FunctionExecutionError):
                                probe_record.update(steps=exc.steps, dependencies=exc.dependencies)
                            raise
                        finally:
                            probe_record.update(
                                graph_id=self.store.put("probe_graph", graph),
                                receipt_ids=[receipt["evidence_id"] for receipt in acquired],
                                invocation_attempts=sum(
                                    not receipt.get("reused", False) for receipt in acquired
                                ),
                                tool_calls=sum(
                                    bool(receipt["tool_call_attempted"])
                                    and not receipt.get("reused")
                                    for receipt in acquired
                                ),
                                completed_tool_calls=sum(
                                    receipt["status"] == "completed" and not receipt.get("reused")
                                    for receipt in acquired
                                ),
                            )
                            probe_record["evidence_id"] = self.store.event(
                                run_id,
                                "function_probe",
                                probe_record["status"],
                                "Actual function probe",
                                probe_record,
                            )
                        probes.append(probe_record)
                        covered.add(probe["function"])
                    if covered != {f["name"] for f in functions}:
                        raise ValueError("Every function requires a real execution probe")
                    generated_checks = []
                    frozen_generated = (
                        self.store.get(generated_bank_id) if generated_bank_id else None
                    )
                    check_inputs = (
                        [item["check"] for item in frozen_generated]
                        if frozen_generated is not None
                        else proposal.get("generated_checks", [])
                    )
                    for check_index, check in enumerate(check_inputs):
                        specification = GeneratedCheckSpec.model_validate(check)
                        if specification.obligation_id not in {
                            item.obligation_id for item in bank.obligations
                        }:
                            raise ValueError(
                                "Generated check references an obligation outside the frozen bank"
                            )
                        prior_check = (
                            frozen_generated[check_index] if frozen_generated is not None else None
                        )
                        graph_id = prior_check["graph_id"] if prior_check else state["graph_id"]
                        source_schema_sha256 = (
                            prior_check["source_schema_sha256"]
                            if prior_check
                            else hashlib.sha256(canonical(schema)).hexdigest()
                        )
                        if source_schema_sha256 == hashlib.sha256(canonical(schema)).hexdigest():
                            outcome = execute_generated_check(
                                specification,
                                self.store.get(graph_id),
                                schema,
                                candidate_functions=functions,
                            )
                        else:
                            outcome = {
                                "status": "unknown",
                                "independent": False,
                                "summary": "Frozen generated check requires a schema translation",
                            }
                        evidence = {
                            "flow": "verification",
                            "independent": False,
                            "graph_id": graph_id,
                            "check": specification.model_dump(mode="json"),
                            "outcome": outcome,
                            "proposal_id": proposal_id,
                            "prompt_manifest_id": prompt_manifest_id,
                            "source_schema_sha256": source_schema_sha256,
                            "bank_id": generated_bank_id,
                        }
                        evidence["evidence_id"] = self.store.event(
                            run_id,
                            "generated_check",
                            "completed",
                            "Executed a generated consistency check on actual evidence",
                            evidence,
                        )
                        generated_checks.append(evidence)
                    return {
                        "functions_id": self.store.put("functions", functions),
                        "coverage_id": coverage_id,
                        "demands_id": self.store.put(
                            "evidence_demands", {"flow": "learning", "demands": demands}
                        ),
                        "generated_checks_id": self.store.put("generated_checks", generated_checks),
                        "learning_id": self.store.put(
                            "learning_candidate",
                            {
                                "flow": "learning",
                                "task_ir_id": state["task_ir_id"],
                                "mandatory_count": len(mandatory),
                                "exploratory_count": len(bank.obligations) - len(mandatory),
                                "feedback": repair,
                                "outcome_status": "not_checked",
                            },
                        ),
                        "probes_id": self.store.event(
                            run_id,
                            "function_probes",
                            "passed",
                            "Actual calls and computation, task correctness remains separate",
                            probes,
                        ),
                    }
                except (ValueError, KeyError, TypeError, ValidationError, SchemaError) as exc:
                    error = {
                        "message": f"{type(exc).__name__}: {exc}",
                        "proposal_id": proposal_id,
                        "requirements_id": state["requirements_id"],
                        "prompt_manifest_id": prompt_manifest_id,
                        "repair_target": "functions",
                    }
                    if isinstance(exc, FunctionExecutionError):
                        error.update(steps=exc.steps, dependencies=exc.dependencies)
                    self.store.event(
                        run_id, "composition_attempt", "failed", "Candidate requires repair", error
                    )
            raise ValueError(f"No executable function catalog within repair limit: {error}")

        self.store.set_run(run_id, "running")
        try:
            # Explicit typed state is required for partial-update accumulation.
            self.store.event(
                run_id,
                "construction_inputs",
                "completed",
                "Focused prompts and literal construction obligations saved",
                {
                    "prompt_manifest_id": prompt_manifest_id,
                    "requirements_input_id": requirements_input_id,
                    "obligation_count": len(obligations),
                },
            )

            class ConstructionEvidence(TypedDict, total=False):
                requirements_input_id: str
                requirements_id: str
                prompt_manifest_id: str
                episodes_id: str
                documents_id: str
                schema_id: str
                validation_id: str
                graph_id: str
                functions_id: str
                probes_id: str
                coverage_id: str
                task_ir_id: str
                demands_id: str
                learning_id: str
                generated_checks_id: str

            workflow = StateGraph(ConstructionEvidence)
            for name, node in [
                ("analyze", analyze),
                ("collect", collect),
                ("draft", draft),
                ("extract", extract),
                ("compose", compose),
            ]:
                workflow.add_node(name, node)
            for left, right in [
                (START, "analyze"),
                ("analyze", "collect"),
                ("collect", "draft"),
                ("draft", "extract"),
                ("extract", "compose"),
                ("compose", END),
            ]:
                workflow.add_edge(left, right)
            with SqliteSaver.from_conn_string(
                str(self.store.root / "mcp-checkpoints.sqlite")
            ) as saver:
                result = workflow.compile(checkpointer=saver).invoke(
                    {}, {"configurable": {"thread_id": run_id}}
                )
            kernel = {
                "format_version": 1,
                "kind": "mcp_kernel",
                "construction_profile": "demand_v1",
                "surface_id": surface_id,
                "parent": parent_id,
                "created_at": now(),
                "run_id": run_id,
                "sample": sample,
                "schema": self.store.get(result["schema_id"]),
                "functions": self.store.get(result["functions_id"]),
                "catalog": catalog,
                "evidence": result,
                "validation": self.store.get(result["validation_id"]),
                "construction_prompt_manifest_id": prompt_manifest_id,
                "construction_prompt_manifest_sha256": hashlib.sha256(
                    canonical(prompts)
                ).hexdigest(),
                "assessment": {
                    "status": "candidate",
                    "logical_validity": "passed",
                    "function_execution": "passed",
                    "requirement_linkage": "passed",
                    "fresh_task_success": "unmeasured",
                },
            }
            kernel_id = self.store.put("mcp_kernel", kernel)
            self.store.event(
                run_id,
                "kernel_candidate",
                "completed",
                "Candidate kernel saved",
                {"kernel_id": kernel_id, "parent": parent_id, "assessment": kernel["assessment"]},
            )
            output = {"run_id": run_id, "kernel_id": kernel_id, "assessment": kernel["assessment"]}
            self.store.set_run(run_id, "completed", result=output)
            return output
        except Exception as exc:
            if not managed_run:
                self.store.set_run(run_id, "failed", error=f"{type(exc).__name__}: {exc}")
            raise

    def _check_run(self, run_id: str, surface_id: str, kind: str) -> None:
        """Only a matching saved worker request can own an engine execution."""
        rows = self.store.rows("SELECT * FROM runs WHERE id=?", (run_id,))
        if not rows or rows[0]["task_id"] != surface_id or rows[0]["kind"] != kind:
            raise ValueError("Worker request does not match this task operation")
        if rows[0]["status"] not in {"queued", "running"}:
            raise ValueError("A terminal run cannot execute again")

    def run_episode(
        self,
        surface_id: str,
        query_id: str | None = None,
        *,
        kernel_id: str | None = None,
        inference_query: InferenceQuery | dict | None = None,
        run_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> dict:
        """Run a real starter or frozen-kernel episode, always acquiring fresh evidence.

        Completion is an agent claim until an adapter supplies independent outcome
        evidence. Saved observations are never substituted for a new MCP call.
        """
        managed_run = run_id is not None
        data = self.surface(surface_id)
        surface = TaskSurface.model_validate(data["configuration"])
        if inference_query is not None:
            if query_id is not None or kernel_id is None:
                raise ValueError("Run-local inference requires a frozen kernel and no query_id")
            query = InferenceQuery.model_validate(inference_query)
        else:
            query = next((q for q in surface.queries if q.id == query_id), None)
        if query is None:
            raise ValueError("Query is absent from the declared surface")
        if kernel_id is None and query.split != "construction":
            raise ValueError("Bootstrap may only consume construction queries")
        kernel = self.store.get(kernel_id) if kernel_id else None
        if kernel and kernel.get("surface_id") != surface_id:
            raise ValueError("Kernel belongs to another surface")
        catalog = kernel["catalog"] if kernel else data["catalog"]
        context = build_runtime_context(
            surface,
            query,
            catalog["tools"],
            history=self.history(surface_id),
            resolve_history=self.store.get,
        )
        request = {
            "surface_id": surface_id,
            "query_id": query.id,
            "kernel_id": kernel_id,
            "context": context,
            "budget_ceiling_usd": data["budget_ceiling_usd"],
            "query_source": "run_local" if inference_query is not None else "registered",
        }
        if run_id is None:
            run_id = self.store.create_run(
                surface_id, "mcp_episode", request, parent_run_id=parent_run_id
            )
        else:
            self._check_run(run_id, surface_id, "mcp_episode")
            self.store.event(
                run_id, "episode_context", "completed", "Initial task context", request
            )
        model = GeminiCLI(self.store, run_id, budget_ceiling_usd=data["budget_ceiling_usd"])
        bridge = MCPBridge(surface.servers, self.store, run_id, expected_catalog=catalog)
        instruction = (PROJECT / "config/prompts/task-runtime.md").read_text()
        instruction += (
            "\nIn bootstrap mode function is the exact discovered capability id; "
            "in kernel mode it is a frozen function name. Return the Decision schema. "
            "A task instruction to return only a number applies to Decision.answer, never to the outer "
            "response: always return the Decision JSON object. Complete requires citations to successful "
            "observation IDs with nonempty acquisition_evidence_ids from this episode. "
            "Completion is independently assessed."
        )
        demand_enabled = bool(kernel and kernel.get("construction_profile") == "demand_v1")
        if demand_enabled:
            instruction += (
                "\nGraph evidence is materialized incrementally from your selected function and arguments. "
                "evidence_scope describes missing or unestablished coverage, not a permission gate. "
                "Decide autonomously whether to call another frozen function to expand evidence, answer "
                "with the appropriate scope, clarify, or report unresolved. Do not equate an empty "
                "partial graph with absence or a partial count with a complete population. Repeating "
                "identical acquisition arguments within this run reuses its actual source receipt. "
                "Generated self-checks are internal consistency evidence, not independent task truth."
            )
        tools = catalog["tools"] if kernel is None else kernel["functions"]

        def decide(state: EpisodeState):
            if state["step"] >= surface.limits.max_steps:
                return {
                    "terminal": {
                        "action": "unresolved",
                        "answer": "Decision limit reached",
                        "citations": [],
                    }
                }
            decision = Decision.model_validate(
                request_json(
                    model,
                    f"decision.{state['step']}",
                    instruction,
                    {
                        "context": context,
                        "mode": "kernel" if kernel else "bootstrap",
                        "tools": tools,
                        "schema": kernel["schema"] if kernel else None,
                        "observations": state["observations"],
                    },
                    Decision.model_json_schema(),
                )
            ).model_dump()
            self.store.event(run_id, "decision", "completed", decision["reason"], decision)
            update = {
                "step": state["step"] + 1,
                "decision": decision,
                "trajectory": state["trajectory"] + [decision],
            }
            if decision["action"] != "call":
                successes = {x["id"] for x in state["observations"] if x["status"] == "completed"}
                if not set(decision["citations"]).issubset(successes):
                    raise ValueError("Terminal decision cites unavailable successful observations")
                if decision["action"] == "complete" and not decision["citations"]:
                    raise ValueError("This acquisition pilot requires actual execution evidence")
                grounded = {
                    observation["id"]
                    for observation in state["observations"]
                    if observation["status"] == "completed"
                    and observation.get("acquisition_evidence_ids")
                }
                if decision["action"] == "complete" and not set(decision["citations"]).issubset(
                    grounded
                ):
                    raise ValueError(
                        "Completion must cite results grounded in actual episode acquisition"
                    )
                update["terminal"] = decision
            return update

        def execute(state: EpisodeState):
            decision = state["decision"]
            graph = self.store.get(state["graph_id"])
            episode_graph = deepcopy(graph)
            count = state["invocation_attempts"]
            acquired = []
            receipt_cache = dict(state.get("receipt_cache", {}))
            materializations = dict(state.get("materializations", {}))
            demand = None
            instantiation_refs = []

            def acquire(*, capability: str, arguments: dict):
                nonlocal count
                request_key = hashlib.sha256(
                    canonical({"capability": capability, "arguments": arguments})
                ).hexdigest()
                reused = demand_enabled and request_key in receipt_cache
                if reused:
                    receipt_id = receipt_cache[request_key]
                    receipt = {
                        **self.store.get(receipt_id),
                        "evidence_id": receipt_id,
                        "reused": True,
                    }
                else:
                    if count >= surface.limits.max_tool_calls:
                        raise ValueError("MCP invocation-attempt limit reached")
                    count += 1
                    receipt = bridge.invoke(capability, arguments)
                    if demand_enabled:
                        # Failed/uncertain dispatches are remembered too: another
                        # decision must not repeat their effects automatically.
                        receipt_cache[request_key] = receipt["evidence_id"]
                acquired.append(receipt)
                if receipt["status"] != "completed":
                    raise ValueError(f"MCP call failed: {receipt.get('error')}")
                if kernel:
                    cache_key = (
                        materialization_cache_key(
                            receipt["evidence_id"],
                            kernel_id,
                            MATERIALIZATION_VERSION,
                            demand,
                        )
                        if demand
                        else None
                    )
                    if cache_key and cache_key in materializations:
                        incoming = self.store.get(materializations[cache_key])
                        instantiation_refs.append(
                            self.store.event(
                                run_id,
                                "materialization_reused",
                                "completed",
                                "Reused actual materialized evidence from this run",
                                {
                                    "flow": "instantiation",
                                    "demand_id": demand.demand_id,
                                    "graph_id": materializations[cache_key],
                                    "receipt_id": receipt["evidence_id"],
                                },
                            )
                        )
                    else:
                        if demand:
                            plan = MaterializationPlan(
                                demand_id=demand.demand_id,
                                kernel_id=kernel_id,
                                receipt_ids=[receipt["evidence_id"]],
                                acquisition_requests=[
                                    {"capability": capability, "arguments": arguments}
                                ],
                                expansion_reason="Additional fields from a retained receipt"
                                if reused
                                else "New actual source evidence",
                            )
                            instantiation_refs.append(
                                self.store.event(
                                    run_id,
                                    "materialization_plan",
                                    "running",
                                    "Materialize the selected computation's evidence",
                                    {
                                        "flow": "instantiation",
                                        **plan.model_dump(mode="json"),
                                    },
                                )
                            )
                        incoming = build_graph(
                            self.store,
                            model,
                            kernel["schema"],
                            receipt_documents(receipt),
                            f"ingest.{state['step']}.{count}",
                            demand=demand,
                        )
                        if cache_key:
                            materializations[cache_key] = self.store.put(
                                "materialized_graph", incoming
                            )
                    merged = merge_observations(kernel["schema"], graph, incoming)
                    graph.clear()
                    graph.update(merged)
                    self.store.event(
                        run_id,
                        "graph_snapshot",
                        "completed",
                        "New observed facts",
                        merge_observations(kernel["schema"], episode_graph, graph)
                        if demand_enabled
                        else graph,
                    )
                    return acquisition_result(
                        kernel["schema"], graph, incoming, receipt["evidence_id"]
                    )
                return receipt["output"]

            observation = {"id": f"observation-{state['step']}", "function": decision["function"]}
            try:
                if kernel:
                    selected_function = next(
                        (
                            function
                            for function in kernel["functions"]
                            if function["name"] == decision["function"]
                        ),
                        None,
                    )
                    if selected_function is None:
                        raise ValueError("Selected function is absent from the frozen kernel")
                    if demand_enabled:
                        demand = derive_demand(
                            kernel["schema"], selected_function, decision["args"]
                        )
                        if any(
                            step["operator"] == "invoke_capability"
                            for step in selected_function["steps"]
                        ):
                            # Graph reads inside an acquisition function see only
                            # this invocation's receipts. The episode evidence
                            # graph accumulates separately for inspection/reuse.
                            graph = empty_graph()
                        instantiation_refs.append(
                            self.store.event(
                                run_id,
                                "evidence_demand",
                                "completed",
                                "Derived evidence demand from the frozen function",
                                {
                                    "flow": "instantiation",
                                    "demand_id": demand.demand_id,
                                    **demand.model_dump(mode="json"),
                                },
                            )
                        )
                    result = execute_function(
                        graph,
                        kernel["functions"],
                        decision["function"],
                        decision["args"],
                        schema=kernel["schema"],
                        capability_invoker=acquire,
                        step_observer=lambda step: self.store.event(
                            run_id,
                            "operator",
                            step["status"],
                            f"{decision['function']}: {step['id']}",
                            {
                                **step,
                                "function": decision["function"],
                                "decision_step": state["step"],
                            },
                        ),
                    )
                    observation["output"] = result["value"]
                    observation["execution_id"] = self.store.put("function_execution", result)
                    observation["working_graph_id"] = self.store.put("function_graph", graph)
                    previous_receipts = [
                        {**self.store.get(identity), "evidence_id": identity}
                        for previous in state["observations"]
                        for identity in previous.get("receipt_ids", [])
                    ]
                    observation["acquisition_evidence_ids"] = result_acquisition_evidence(
                        selected_function, result, graph, previous_receipts + acquired
                    )
                    if demand:
                        scope = assess_sufficiency(kernel["schema"], graph, demand)
                        observation["evidence_scope"] = scope.model_dump(mode="json")
                        instantiation_refs.append(
                            self.store.event(
                                run_id,
                                "evidence_scope",
                                "completed",
                                "Recorded evidence scope for autonomous planning",
                                {
                                    "flow": "instantiation",
                                    "nonblocking": True,
                                    **scope.model_dump(mode="json"),
                                },
                            )
                        )
                else:
                    observation["output"] = acquire(
                        capability=decision["function"], arguments=decision["args"]
                    )
                    observation["acquisition_evidence_ids"] = [
                        receipt["evidence_id"]
                        for receipt in acquired
                        if receipt["status"] == "completed" and receipt["tool_call_attempted"]
                    ]
                observation["status"] = "completed"
            except (ValueError, KeyError, TypeError, ValidationError) as exc:
                observation.update(status="failed", error=f"{type(exc).__name__}: {exc}")
                if isinstance(exc, FunctionExecutionError):
                    observation["execution_id"] = self.store.put(
                        "function_failure",
                        {
                            "steps": exc.steps,
                            "dependencies": exc.dependencies,
                        },
                    )
            observation["receipt_ids"] = [r["evidence_id"] for r in acquired]
            if demand_enabled:
                try:
                    graph = merge_observations(kernel["schema"], episode_graph, graph)
                except ValueError as exc:
                    observation.update(
                        status="failed", error=f"Conflicting source snapshots: {exc}"
                    )
                    observation["conflicting_graph_id"] = self.store.put("conflicting_graph", graph)
                    graph = episode_graph
            if instantiation_refs:
                observation["instantiation_evidence_ids"] = instantiation_refs
            if acquired:
                observation.update(
                    receipt_id=acquired[-1]["evidence_id"],
                    capability_id=acquired[-1]["capability_id"],
                )
            self.store.event(
                run_id,
                "observation",
                observation["status"],
                "Actual execution observation",
                observation,
            )
            if len(canonical(observation.get("output"))) > 22000:
                identity = self.store.put("full_observation", observation["output"])
                observation["output"] = {
                    "truncated": True,
                    "artifact_id": identity,
                    "message": "Observation exceeds prompt bound; request narrower evidence or report unresolved",
                }
            return {
                "observations": state["observations"] + [observation],
                "graph_id": self.store.put("episode_graph", graph),
                "invocation_attempts": count,
                "receipt_cache": receipt_cache,
                "materializations": materializations,
                "tool_calls": state["tool_calls"]
                + sum(
                    bool(receipt["tool_call_attempted"]) and not receipt.get("reused")
                    for receipt in acquired
                ),
                "completed_tool_calls": state["completed_tool_calls"]
                + sum(
                    receipt["status"] == "completed" and not receipt.get("reused")
                    for receipt in acquired
                ),
            }

        builder = StateGraph(EpisodeState)
        builder.add_node("decide", decide)
        builder.add_node("execute", execute)
        builder.add_edge(START, "decide")
        builder.add_conditional_edges(
            "decide", lambda state: END if state.get("terminal") else "execute"
        )
        builder.add_edge("execute", "decide")
        self.store.set_run(run_id, "running")
        try:
            initial_graph = empty_graph()
            initial_graph_id = self.store.put("episode_graph", initial_graph)
            if kernel:
                self.store.event(
                    run_id, "graph_snapshot", "completed", "Initial empty graph", initial_graph
                )
            with SqliteSaver.from_conn_string(
                str(self.store.root / "mcp-checkpoints.sqlite")
            ) as saver:
                state = builder.compile(checkpointer=saver).invoke(
                    {
                        "step": 0,
                        "observations": [],
                        "trajectory": [],
                        "invocation_attempts": 0,
                        "tool_calls": 0,
                        "completed_tool_calls": 0,
                        "graph_id": initial_graph_id,
                        "receipt_cache": {},
                        "materializations": {},
                    },
                    {
                        "configurable": {"thread_id": run_id},
                        "recursion_limit": surface.limits.max_steps * 2 + 4,
                    },
                )
            terminal = state["terminal"]
            episode = {
                "format_version": 1,
                "surface_id": surface_id,
                "query_id": query.id,
                "query": query.query,
                "split": query.split,
                "mode": "kernel" if kernel else "bootstrap",
                "kernel_revision": kernel_id,
                "catalog_id": catalog.get("catalog_id"),
                "base_prompt_sha256": hashlib.sha256(surface.base_prompt.encode()).hexdigest(),
                "runtime_prompt_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
                "created_at": now(),
                "status": terminal["action"],
                "answer": terminal["answer"],
                "citations": terminal["citations"],
                "observations": state["observations"],
                "trajectory": state["trajectory"],
                "graph_id": state["graph_id"],
                "invocation_attempts": state["invocation_attempts"],
                "tool_calls": state["tool_calls"],
                "completed_tool_calls": state["completed_tool_calls"],
                "assessment": {"status": "unmeasured"},
            }
            episode_id = self.store.put("episode", episode)
            result = {"run_id": run_id, "episode_id": episode_id, "episode": episode}
            from oak.tasks.evaluation import assess_mcp_episode

            assessment = assess_mcp_episode(
                self.store, run_id, episode_id, query.model_dump(mode="json")
            )
            if assessment is not None:
                result["assessment"] = assessment
            self.store.set_run(run_id, "completed", result=result)
            return result
        except Exception as exc:
            if not managed_run:
                self.store.set_run(run_id, "failed", error=f"{type(exc).__name__}: {exc}")
            raise

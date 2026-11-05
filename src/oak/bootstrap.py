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

from oak.behavior import (
    BehaviorBinding,
    build_behavior_bank,
    compile_behavior_bindings,
    make_behavior_inputs,
)
from oak.campaign_evidence import retained_starter, starter_key
from oak.construction_context import compact_construction_context
from oak.construction_contracts import (
    RequirementAnalysis,
    requirement_inputs,
    validate_function_coverage,
    validate_requirement_analysis,
)
from oak.construction_prompts import prompt_manifest
from oak.functions import FunctionExecutionError, FunctionSpec, execute_function, validate_functions
from oak.learning import freeze_task_ir
from oak.learning_contracts import TaskIR
from oak.materialization import (
    MATERIALIZATION_VERSION,
    MaterializationPlan,
    assess_sufficiency,
    derive_demand,
    derive_step_demand,
    materialization_cache_key,
    prepare_bound_materialization,
    slice_graph,
)
from oak.mcp_bridge import MCPBridge
from oak.model import GeminiCLI, runtime_config
from oak.ontology import schema_json_schema, validate_graph_records, validate_ontology
from oak.operators import GRAPH_OPERATORS, operator_contracts
from oak.pipeline import build_graph, request_json
from oak.store import Store, canonical, now
from oak.task_context import InferenceQuery, TaskSurface, build_runtime_context, sample_construction

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
    functions: list[FunctionSpec] = Field(default_factory=list, max_length=64)
    probes: list[FunctionProbe] = Field(default_factory=list, max_length=64)
    behavior_bindings: list[BehaviorBinding] = Field(default_factory=list, max_length=256)


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
    function: dict,
    execution: dict,
    graph: dict,
    receipts: list[dict],
    *,
    materialization_receipt_ids: list[str] | tuple[str, ...] = (),
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
            # Empty results still have actual source-dispatch attribution.
            # This does not certify population completeness or absence.
            evidence.update(set(materialization_receipt_ids) & available)
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
        """Construct reusable candidates through the independent selective verifier."""
        from oak.construction_campaign import construct_campaign

        return construct_campaign(
            self, surface_id, round_index=round_index, parent_id=parent_id, run_id=run_id
        )

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
        starter_cache: dict[str, str] | None = None,
    ) -> dict:
        """Construct a candidate from a recorded fresh sample and genuine starter episodes.

        Real OWL and function probes are admission evidence, not an independent
        task-success score. Candidates remain explicitly unpromoted until an
        external task evaluator records fresh outcome evidence.
        """
        starter_cache = starter_cache if starter_cache is not None else {}
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
                    "behavior_bank_id": self.store.put(
                        "behavior_bank", build_behavior_bank(bank).model_dump(mode="json")
                    ),
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
                behavior_bank_id = self.store.put(
                    "behavior_bank", build_behavior_bank(bank).model_dump(mode="json")
                )
                self.store.event(
                    run_id,
                    "task_ir",
                    "completed",
                    "Candidate-independent subtask bank frozen",
                    {
                        "flow": "learning",
                        "task_ir_id": frozen_id,
                        "behavior_bank_id": behavior_bank_id,
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
                    "behavior_bank_id": behavior_bank_id,
                }
            raise ValueError(f"No valid requirement analysis within repair limit: {feedback}")

        def collect(state):
            episodes, documents = [], []
            for query in selected:
                key = starter_key(
                    surface_id, query.model_dump(mode="json"), catalog.get("catalog_id")
                )
                reused = key in starter_cache
                if not reused:
                    episode = self.run_episode(surface_id, query.id, parent_run_id=run_id)
                    starter_cache[key] = episode["episode_id"]
                snapshot = retained_starter(
                    self.store,
                    starter_cache[key],
                    surface_id=surface_id,
                    query_id=query.id,
                    catalog_id=catalog.get("catalog_id"),
                    document_reader=receipt_documents,
                )
                episodes.append(snapshot["episode_id"])
                documents.extend(snapshot["documents"])
                self.store.event(
                    run_id,
                    "starter_evidence",
                    "completed",
                    "Reused the campaign's recorded source snapshot"
                    if reused
                    else "Recorded actual starter acquisition",
                    {
                        "flow": "learning",
                        **{k: v for k, v in snapshot.items() if k != "documents"},
                        "reused": reused,
                    },
                )
            if not documents:
                raise ValueError("Construction requires actual acquired evidence")
            documents = list({item["document_id"]: item for item in documents}.values())
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
                    compact_construction_context(
                        {
                            "surface": surface.description,
                            "obligations": requirements_input["obligations"],
                            "requirements": self.store.get(state["requirements_id"]),
                            "task_ir": self.store.get(state["task_ir_id"]),
                            "behavior_bank": self.store.get(state["behavior_bank_id"]),
                            "capabilities": catalog["tools"],
                            "observations": self.store.get(state["documents_id"]),
                            "previous_schema": parent["schema"] if parent else None,
                            "validation_feedback": feedback,
                        }
                    ),
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
            if (
                parent
                and parent.get("materialization_version") == MATERIALIZATION_VERSION
                and canonical(parent["schema"]) == canonical(self.store.get(state["schema_id"]))
                and self.store.get(parent["evidence"]["documents_id"])
                == self.store.get(state["documents_id"])
                and self.store.get(parent["evidence"]["prompt_manifest_id"])["stages"]["extraction"]
                == prompts["stages"]["extraction"]
            ):
                graph_id = parent["evidence"]["graph_id"]
                self.store.get(graph_id)
                self.store.event(
                    run_id,
                    "construction_materialization_reused",
                    "completed",
                    "Unchanged schema, extractor and source snapshot reused",
                    {"flow": "verification", "graph_id": graph_id, "parent_kernel_id": parent_id},
                )
                return {"graph_id": graph_id}
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
            behavior_bank = self.store.get(state["behavior_bank_id"])
            retained_receipts = [
                {**self.store.get(identity), "evidence_id": identity, "reused": True}
                for identity in sorted(
                    {document["source_id"] for document in self.store.get(state["documents_id"])}
                )
            ]
            receipt_arguments = {}
            for receipt in retained_receipts:
                if receipt.get("status") == "completed":
                    receipt_arguments.setdefault(receipt["capability_id"], []).append(
                        receipt["args"]
                    )
            mandatory = [item for item in bank.obligations if item.mandatory]
            error = repair
            tool_attempts = 0
            probe_receipt_cache: dict[str, str] = {
                hashlib.sha256(
                    canonical(
                        {"capability": receipt["capability_id"], "arguments": receipt["args"]}
                    )
                ).hexdigest(): document["source_id"]
                for document in self.store.get(state["documents_id"])
                for receipt in [self.store.get(document["source_id"])]
                if receipt.get("status") == "completed"
            }
            for attempt in range(runtime_config()["max_repair_attempts"] + 1):
                proposal = request_json(
                    model,
                    f"compose.{attempt}",
                    prompts["stages"]["functions"]["instruction"],
                    compact_construction_context(
                        {
                            "surface": surface.description,
                            "queries": [q.model_dump() for q in selected],
                            "obligations": [item.model_dump(mode="json") for item in mandatory],
                            "task_ir": bank.model_dump(mode="json"),
                            "behavior_bank": behavior_bank,
                            "recorded_acquisition_arguments": receipt_arguments,
                            "requirements": self.store.get(state["requirements_id"]),
                            "schema": schema,
                            "graph": self.store.get(state["graph_id"]),
                            "capabilities": catalog["tools"],
                            "operators": operator_contracts(),
                            "function_contract": FunctionSpec.model_json_schema(),
                            "parent_functions": parent["functions"] if parent else None,
                            "execution_feedback": error,
                        }
                    ),
                    FunctionProposal.model_json_schema(),
                )
                proposal_id = self.store.put("function_proposal", proposal)
                try:
                    proposal = FunctionProposal.model_validate(proposal).model_dump(mode="json")
                    functions = [
                        f.model_dump(mode="json")
                        for f in (
                            validate_functions(proposal["functions"], schema)
                            if proposal["functions"]
                            else []
                        )
                    ]
                    compilation = compile_behavior_bindings(
                        behavior_bank,
                        schema,
                        proposal["behavior_bindings"],
                        functions=functions,
                        capabilities=catalog["tools"],
                    )
                    functions = [
                        f.model_dump(mode="json")
                        for f in validate_functions(compilation.functions, schema)
                    ]
                    if not functions:
                        raise ValueError(
                            f"No callable semantic behavior: {compilation.diagnostics}"
                        )
                    compiled_by_behavior = {
                        entry.behavior_id: entry for entry in compilation.entries
                    }
                    binding_by_behavior = {
                        item["behavior_id"]: item for item in proposal["behavior_bindings"]
                    }
                    allowed = {t["id"] for t in catalog["tools"]}
                    for function in functions:
                        for step in function["steps"]:
                            if (
                                step["operator"] == "invoke_capability"
                                and step["args"]["capability"] not in allowed
                            ):
                                raise ValueError("Function binds an undiscovered capability")
                    if not compilation.acquisition_bindings and not any(
                        function_dataflow(f)["acquisition_computation_steps"] for f in functions
                    ):
                        raise ValueError(
                            "An authorized acquisition/materialization strategy is missing"
                        )
                    links = {item.obligation_id: set() for item in mandatory}
                    for template in behavior_bank["behaviors"]:
                        entry = compiled_by_behavior.get(template["behavior_id"])
                        if entry:
                            for identity in template["obligation_ids"]:
                                if identity in links:
                                    links[identity].add(entry.function_name)
                    coverage = validate_function_coverage(
                        [
                            {
                                "obligation_id": identity,
                                "function_names": sorted(names),
                                "unsupported_reason": None
                                if names
                                else "No executable binding for this interpreted behavior",
                            }
                            for identity, names in links.items()
                        ],
                        mandatory,
                        functions,
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
                    probe_inputs = list(proposal["probes"])
                    for template in behavior_bank["behaviors"]:
                        entry = compiled_by_behavior.get(template["behavior_id"])
                        if entry is None:
                            continue
                        inputs = make_behavior_inputs(
                            template,
                            binding_by_behavior[template["behavior_id"]],
                            schema,
                            self.store.get(state["graph_id"]),
                            receipt_arguments=receipt_arguments,
                        )
                        if inputs:
                            probe_inputs.append(
                                {"function": entry.function_name, "args": inputs[0]}
                            )
                    probe_inputs = list(
                        {canonical(probe): probe for probe in probe_inputs}.values()
                    )
                    for index, probe in enumerate(probe_inputs):
                        function = next(
                            (f for f in functions if f["name"] == probe["function"]), None
                        )
                        if function is None:
                            raise ValueError("Probe names an absent function")
                        has_acquisition = any(
                            s["operator"] == "invoke_capability" for s in function["steps"]
                        )
                        prepared = prepare_bound_materialization(
                            schema,
                            function,
                            probe["args"],
                            compilation.acquisition_bindings,
                            catalog["tools"],
                        )
                        graph = (
                            empty_graph()
                            if has_acquisition or prepared.acquisitions
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
                            if prepared.acquisitions:
                                matching = []
                                for request in prepared.acquisitions:
                                    receipts = [
                                        receipt
                                        for receipt in retained_receipts
                                        if receipt["capability_id"] == request.capability
                                        and receipt["args"] == request.arguments
                                        and receipt["status"] == "completed"
                                    ]
                                    if not receipts:
                                        raise ValueError(
                                            "No retained receipt matches the frozen probe acquisition arguments"
                                        )
                                    matching.extend(receipts)
                                acquired.extend(matching)
                                document_ids = {
                                    item["document_id"]
                                    for receipt in matching
                                    for item in receipt_documents(receipt)
                                }
                                retained = deepcopy(self.store.get(state["graph_id"]))
                                retained["nodes"] = [
                                    node
                                    for node in retained["nodes"]
                                    if any(
                                        source["document_id"] in document_ids
                                        for source in node["sources"]
                                    )
                                ]
                                node_ids = {node["id"] for node in retained["nodes"]}
                                retained["edges"] = [
                                    edge
                                    for edge in retained["edges"]
                                    if edge["source"] in node_ids
                                    and edge["target"] in node_ids
                                    and any(
                                        source["document_id"] in document_ids
                                        for source in edge["sources"]
                                    )
                                ]
                                graph.update(slice_graph(schema, retained, prepared.demand))
                                probe_record.update(
                                    strategy_basis="retained_materialized_source_slice",
                                    source_graph_id=state["graph_id"],
                                    acquisition_requests=[
                                        item.model_dump(mode="json")
                                        for item in prepared.acquisitions
                                    ],
                                    limitation="Native bindings and retained computation checked. Record provenance does not independently verify each field's source mapping; fresh acquisition/extraction require a live episode",
                                )
                            result = execute_function(
                                graph,
                                functions,
                                probe["function"],
                                probe["args"],
                                schema=schema,
                                artifact_store=self.store,
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
                            proof = result_acquisition_evidence(
                                function,
                                result,
                                graph,
                                acquired,
                                materialization_receipt_ids=[
                                    item["evidence_id"] for item in acquired
                                ]
                                if prepared.acquisitions
                                else [],
                            )
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
                                probe_record.update(
                                    steps=exc.steps,
                                    dependencies=exc.dependencies,
                                    capture_id=exc.capture_id,
                                )
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
                    bindings_id = self.store.put("behavior_bindings", proposal["behavior_bindings"])
                    behavior_input_id = self.store.put(
                        "behavior_evaluation_input",
                        {
                            "bank_id": state["behavior_bank_id"],
                            "bindings_id": bindings_id,
                            "graph_id": state["graph_id"],
                            "receipt_arguments": receipt_arguments,
                            "receipt_ids": sorted(
                                {
                                    document["source_id"]
                                    for document in self.store.get(state["documents_id"])
                                }
                            ),
                            "capabilities_id": catalog["catalog_id"],
                            "evidence_refs": sorted(
                                {
                                    document["source_id"]
                                    for document in self.store.get(state["documents_id"])
                                }
                            ),
                        },
                    )
                    return {
                        "functions_id": self.store.put("functions", functions),
                        "coverage_id": coverage_id,
                        "demands_id": self.store.put(
                            "evidence_demands", {"flow": "learning", "demands": demands}
                        ),
                        "generated_checks_id": self.store.put("generated_checks", []),
                        "behavior_bindings_id": bindings_id,
                        "behavior_input_id": behavior_input_id,
                        "compilation_id": self.store.put(
                            "behavior_compilation", compilation.model_dump(mode="json")
                        ),
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
                behavior_bank_id: str
                behavior_bindings_id: str
                behavior_input_id: str
                compilation_id: str

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
                "historical_replay_policy": "inherited_v1",
                "construction_profile": "semantic_v2",
                "materialization_version": MATERIALIZATION_VERSION,
                "surface_id": surface_id,
                "parent": parent_id,
                "created_at": now(),
                "run_id": run_id,
                "sample": sample,
                "schema": self.store.get(result["schema_id"]),
                "functions": self.store.get(result["functions_id"]),
                "acquisition_bindings": self.store.get(result["compilation_id"])[
                    "acquisition_bindings"
                ],
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
            from oak.historical_replay import register_kernel_bank, seal_execution_case

            protected_cases = [
                seal_execution_case(
                    self.store,
                    kernel_id,
                    probe["execution"]["capture_id"],
                    run_id=run_id,
                    split="construction",
                )
                for probe in self.store.get(result["probes_id"])
                if probe.get("status") == "passed" and probe.get("execution", {}).get("capture_id")
            ]
            register_kernel_bank(self.store, kernel_id, protected_cases)
            self.store.event(
                run_id,
                "kernel_candidate",
                "completed",
                "Candidate kernel saved",
                {"kernel_id": kernel_id, "parent": parent_id, "assessment": kernel["assessment"]},
            )
            output = {"run_id": run_id, "kernel_id": kernel_id, "assessment": kernel["assessment"]}
            if not managed_run:
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
        if kernel is not None:
            from oak.historical_replay import inference_admission

            admission = inference_admission(self.store, kernel_id)
            internal_evaluation = False
            if (
                not admission["allowed"]
                and parent_run_id is not None
                and inference_query is None
                and query.split in {"construction", "development"}
            ):
                owned = self.store.rows(
                    "SELECT id,task_id,kind,status,parent_run_id FROM runs WHERE id=?",
                    (kernel.get("run_id"),),
                )
                parent_runs = self.store.rows(
                    "SELECT task_id,kind,status FROM runs WHERE id=?", (parent_run_id,)
                )
                internal_evaluation = bool(
                    owned
                    and parent_runs
                    and owned[0]["task_id"] == surface_id
                    and owned[0]["kind"] == "mcp_construct"
                    and owned[0]["status"] == "running"
                    and parent_run_id in {owned[0]["id"], owned[0]["parent_run_id"]}
                    and parent_runs[0]["task_id"] == surface_id
                    and parent_runs[0]["kind"] == "mcp_construct"
                    and parent_runs[0]["status"] == "running"
                )
            if not admission["allowed"] and not internal_evaluation:
                raise ValueError(admission["reason"])
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
        demand_enabled = bool(
            kernel and kernel.get("construction_profile") in {"demand_v1", "semantic_v2"}
        )
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

            observation = {
                "id": f"observation-{state['step']}",
                "function": decision["function"],
                "args": decision["args"],
            }
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
                    prepared = None
                    if demand_enabled:
                        prepared = prepare_bound_materialization(
                            kernel["schema"],
                            selected_function,
                            decision["args"],
                            kernel.get("acquisition_bindings", []),
                            catalog["tools"],
                        )
                        demand = prepared.demand
                        if prepared.acquisitions or any(
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
                    materialized_demands = set()

                    def before_step(*, step_id, operator, arguments, step_outputs):
                        nonlocal demand
                        if (
                            not prepared
                            or not prepared.acquisitions
                            or operator not in GRAPH_OPERATORS
                        ):
                            return
                        demand = derive_step_demand(
                            kernel["schema"],
                            selected_function,
                            decision["args"],
                            step_id,
                            step_outputs=step_outputs,
                        )
                        if demand.demand_id in materialized_demands:
                            return
                        instantiation_refs.append(
                            self.store.event(
                                run_id,
                                "evidence_expansion",
                                "running",
                                "Resolve the impending graph operation from its actual inputs",
                                {
                                    "flow": "instantiation",
                                    "step_id": step_id,
                                    "operator": operator,
                                    "demand": demand.model_dump(mode="json"),
                                    "bindings": [
                                        item.model_dump(mode="json")
                                        for item in prepared.acquisitions
                                    ],
                                },
                            )
                        )
                        for request in prepared.acquisitions:
                            acquire(capability=request.capability, arguments=request.arguments)
                        materialized_demands.add(demand.demand_id)

                    result = execute_function(
                        graph,
                        kernel["functions"],
                        decision["function"],
                        decision["args"],
                        schema=kernel["schema"],
                        artifact_store=self.store,
                        capability_invoker=acquire,
                        before_step=before_step,
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
                    observation["capture_id"] = result["capture_id"]
                    observation["execution_id"] = self.store.put("function_execution", result)
                    observation["working_graph_id"] = self.store.put("function_graph", graph)
                    previous_receipts = [
                        {**self.store.get(identity), "evidence_id": identity}
                        for previous in state["observations"]
                        for identity in previous.get("receipt_ids", [])
                    ]
                    observation["acquisition_evidence_ids"] = result_acquisition_evidence(
                        selected_function,
                        result,
                        graph,
                        previous_receipts + acquired,
                        materialization_receipt_ids=[item["evidence_id"] for item in acquired]
                        if prepared and prepared.acquisitions
                        else [],
                    )
                    if demand:
                        demand = derive_demand(
                            kernel["schema"],
                            selected_function,
                            decision["args"],
                            step_outputs={
                                step["id"]: step["output"]
                                for step in result["steps"]
                                if step["status"] == "completed"
                            },
                        )
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
                    observation["capture_id"] = exc.capture_id
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
            if (
                kernel_id is not None
                and kernel.get("historical_replay_policy") == "inherited_v1"
                and inference_query is None
                and query.split in {"construction", "development"}
            ):
                from oak.historical_replay import (
                    check_candidate_replay,
                    register_kernel_bank,
                    seal_execution_case,
                )

                previous_bank = self.store.rows(
                    "SELECT bank_id FROM replay_banks WHERE kernel_id=?", (kernel_id,)
                )
                previous_bank_id = previous_bank[0]["bank_id"] if previous_bank else None

                protected_cases = [
                    seal_execution_case(
                        self.store,
                        kernel_id,
                        observation["capture_id"],
                        run_id=run_id,
                        question=query.query,
                        split=query.split,
                    )
                    for observation in episode["observations"]
                    if observation.get("status") == "completed" and observation.get("capture_id")
                ]
                result["replay_bank_id"] = register_kernel_bank(
                    self.store, kernel_id, protected_cases
                )
                if not internal_evaluation and result["replay_bank_id"] != previous_bank_id:
                    # The completed episode remains its own evidence. A changed
                    # protected bank needs a new offline report before admission.
                    result["historical_replay"] = check_candidate_replay(
                        self.store, kernel_id, run_id=run_id
                    )
            self.store.set_run(run_id, "completed", result=result)
            return result
        except Exception as exc:
            if not managed_run:
                self.store.set_run(run_id, "failed", error=f"{type(exc).__name__}: {exc}")
            raise

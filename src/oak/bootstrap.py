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

from oak.functions import FunctionExecutionError, FunctionSpec, execute_function, validate_functions
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


class FunctionProbe(BaseModel):
    """Real input proposed to exercise one generated callable."""

    model_config = ConfigDict(extra="forbid")
    function: str
    args: dict


class FunctionProposal(BaseModel):
    """Bounded model output for one candidate function catalog and its probes."""

    model_config = ConfigDict(extra="forbid")
    functions: list[FunctionSpec] = Field(min_length=1, max_length=6)
    probes: list[FunctionProbe] = Field(min_length=1, max_length=6)


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
    result["source_document_count"] += incoming["source_document_count"]
    result["ignored_documents"] += incoming.get("ignored_documents", [])
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
        sample = sample_construction(surface, round_index).model_dump(mode="json")
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
        instruction = (PROJECT / "config/prompts/task-construction.md").read_text()
        catalog = data["catalog"]
        bridge = MCPBridge(surface.servers, self.store, run_id, expected_catalog=catalog)
        selected = [q for q in surface.queries if q.id in sample["selected_query_ids"]]

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
            feedback = None
            for attempt in range(runtime_config()["max_repair_attempts"] + 1):
                schema = request_json(
                    model,
                    f"schema.{attempt}",
                    instruction
                    + "\nDraft only S matching the supplied schema contract. Use meaningful domain "
                    "entities/properties supporting the public tasks, not opaque tool-result blobs. "
                    "Choose stable identities scoped to the observed location/time/source where needed. "
                    "Do not encode particular answers or task IDs. Follow documented datatype names. "
                    "Each response is extracted and validated separately before merging. Properties "
                    "available only from another capability response must be optional. Cross-response "
                    "completeness obligations are not enforced by this first-slice schema extractor. "
                    "Descriptive metadata absent under another documented input route must also remain "
                    "optional. Require only grounded identity and fields necessary across supported "
                    "variants; keep task-specific completeness checks distinct from broad schema rules.",
                    {
                        "surface": surface.description,
                        "base_prompt": surface.base_prompt,
                        "queries": [q.model_dump() for q in selected],
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
                self.store.event(
                    run_id,
                    "ontology_validation",
                    "passed" if report["valid"] else "failed",
                    "Actual OWL/HermiT candidate validation",
                    report,
                )
                if report["valid"]:
                    return {
                        "schema_id": self.store.put("schema", schema),
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
            )
            return {"graph_id": self.store.put("construction_graph", graph)}

        def compose(state):
            schema = self.store.get(state["schema_id"])
            error = None
            for attempt in range(runtime_config()["max_repair_attempts"] + 1):
                proposal = request_json(
                    model,
                    f"compose.{attempt}",
                    instruction
                    + "\nReturn the supplied FunctionProposal JSON schema exactly. Prefer one or two "
                    "parameterized functions and avoid redundant copies for alternative native inputs. "
                    "At least one useful composition must invoke "
                    "a real capability and compute over its extracted evidence. invoke_capability "
                    "takes capability (literal exact catalog id) and arguments (native MCP args). "
                    "The executor automatically extracts this response into the current episode G; "
                    "the operator returns {entities,entities_by_type,receipt_id}. entities_by_type "
                    "maps every declared entity type to its list from THIS response. Prefer "
                    "{$path:['fetch_step','entities_by_type','DeclaredType']} as filter/aggregate "
                    "input so prior acquisitions are not mixed into a new request. Later graph steps "
                    "operate on actual G. Do not supply graph or callback arguments. Each step calls "
                    "one documented operator. References are {$arg:'input'}, {$step:'previous_id'}, "
                    "{$path:['previous_id','field',0]}. Return result using these references. "
                    "Inputs require JSON Schema object/properties/required/additionalProperties:false. "
                    "The executor does not insert JSON Schema defaults. Every referenced input must "
                    "be required and supplied by each probe. Pass entities explicitly to filters. "
                    "For numeric comparisons use {property,operator,value}; minimum/maximum are only "
                    "for between. aggregate_values takes items and request:{operation,...}, not "
                    "operation as a top-level argument. Use the actual operator contracts exactly. "
                    "Provide one probe on real task inputs per function. Preserve native parameter "
                    "flexibility and valid alternative acquisition routes. Literal numeric API defaults "
                    "are allowed when documented; request-specific thresholds/locations must be inputs. "
                    "For alternative native input routes, prefer a required native_arguments object "
                    "whose schema copies the registered input_schema and bind the entire object with "
                    "{$arg:'native_arguments'}. Do not force one optional native field to be required "
                    "because this sample used it. Preserve useful parent operations while extending "
                    "coverage of this fresh sample. Distinct operations may use separate functions. "
                    "Do not use extract_runtime_slots in this first slice; model decisions bind slots.",
                    {
                        "surface": surface.description,
                        "queries": [q.model_dump() for q in selected],
                        "schema": schema,
                        "graph": self.store.get(state["graph_id"]),
                        "capabilities": catalog["tools"],
                        "operators": operator_contracts(),
                        "function_contract": FunctionSpec.model_json_schema(),
                        "parent_functions": parent["functions"] if parent else None,
                        "sampled_episodes": [
                            sampled_episode_summary(identity, self.store.get(identity))
                            for identity in self.store.get(state["episodes_id"])
                        ],
                        "execution_feedback": error,
                    },
                    FunctionProposal.model_json_schema(),
                )
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
                    probes, covered = [], set()
                    tool_attempts = 0
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

                        def acquire(
                            *,
                            capability,
                            arguments,
                            graph=graph,
                            acquired=acquired,
                            probe_stage=f"probe_extract.{attempt}.{index}",
                        ):
                            nonlocal tool_attempts
                            if tool_attempts >= surface.limits.max_tool_calls:
                                raise ValueError("Construction probe call bound reached")
                            tool_attempts += 1
                            receipt = bridge.invoke(capability, arguments)
                            acquired.append(receipt)
                            if receipt["status"] != "completed":
                                raise ValueError(f"Real MCP probe failed: {receipt.get('error')}")
                            incoming = build_graph(
                                self.store,
                                model,
                                schema,
                                receipt_documents(receipt),
                                f"{probe_stage}.{tool_attempts}",
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
                                invocation_attempts=len(acquired),
                                tool_calls=sum(
                                    bool(receipt["tool_call_attempted"]) for receipt in acquired
                                ),
                                completed_tool_calls=sum(
                                    receipt["status"] == "completed" for receipt in acquired
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
                    return {
                        "functions_id": self.store.put("functions", functions),
                        "probes_id": self.store.event(
                            run_id,
                            "function_probes",
                            "passed",
                            "Actual calls and computation, task correctness remains separate",
                            probes,
                        ),
                    }
                except (ValueError, KeyError, TypeError, ValidationError, SchemaError) as exc:
                    error = {"message": f"{type(exc).__name__}: {exc}"}
                    if isinstance(exc, FunctionExecutionError):
                        error.update(steps=exc.steps, dependencies=exc.dependencies)
                    self.store.event(
                        run_id, "composition_attempt", "failed", "Candidate requires repair", error
                    )
            raise ValueError(f"No executable function catalog within repair limit: {error}")

        self.store.set_run(run_id, "running")
        try:
            # Explicit typed state is required for partial-update accumulation.
            class ConstructionEvidence(TypedDict, total=False):
                episodes_id: str
                documents_id: str
                schema_id: str
                validation_id: str
                graph_id: str
                functions_id: str
                probes_id: str

            workflow = StateGraph(ConstructionEvidence)
            for name, node in [
                ("collect", collect),
                ("draft", draft),
                ("extract", extract),
                ("compose", compose),
            ]:
                workflow.add_node(name, node)
            for left, right in [
                (START, "collect"),
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
                "construction_prompt_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
                "assessment": {
                    "status": "candidate",
                    "logical_validity": "passed",
                    "function_execution": "passed",
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
            count = state["invocation_attempts"]
            acquired = []

            def acquire(*, capability: str, arguments: dict):
                nonlocal count
                if count >= surface.limits.max_tool_calls:
                    raise ValueError("MCP invocation-attempt limit reached")
                count += 1
                receipt = bridge.invoke(capability, arguments)
                acquired.append(receipt)
                if receipt["status"] != "completed":
                    raise ValueError(f"MCP call failed: {receipt.get('error')}")
                if kernel:
                    incoming = build_graph(
                        self.store,
                        model,
                        kernel["schema"],
                        receipt_documents(receipt),
                        f"ingest.{state['step']}.{count}",
                    )
                    merged = merge_observations(kernel["schema"], graph, incoming)
                    graph.clear()
                    graph.update(merged)
                    self.store.event(
                        run_id, "graph_snapshot", "completed", "New observed facts", graph
                    )
                    return acquisition_result(
                        kernel["schema"], graph, incoming, receipt["evidence_id"]
                    )
                return receipt["output"]

            observation = {"id": f"observation-{state['step']}", "function": decision["function"]}
            try:
                if kernel:
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
                    previous_receipts = [
                        {**self.store.get(identity), "evidence_id": identity}
                        for previous in state["observations"]
                        for identity in previous.get("receipt_ids", [])
                    ]
                    selected_function = next(
                        function
                        for function in kernel["functions"]
                        if function["name"] == decision["function"]
                    )
                    observation["acquisition_evidence_ids"] = result_acquisition_evidence(
                        selected_function, result, graph, previous_receipts + acquired
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
                "tool_calls": state["tool_calls"]
                + sum(bool(receipt["tool_call_attempted"]) for receipt in acquired),
                "completed_tool_calls": state["completed_tool_calls"]
                + sum(receipt["status"] == "completed" for receipt in acquired),
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

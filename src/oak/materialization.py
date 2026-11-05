"""Demand-directed graph materialization with explicit evidence sufficiency.

These contracts describe what a frozen computation needs, not a new ontology.
Selectors and fields are derived conservatively from executable operator calls.
Coverage is informational: the planner can compute, expand, or answer while a
source population remains unknown. A model-produced graph, processed-document
count, or model claim is never relabeled independent completeness evidence.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from oak.functions import FunctionSpec
from oak.mcp_bridge import _validator
from oak.ontology import parse_schema, validate_graph_records
from oak.operators import lookup_entities, traverse_relations

MATERIALIZATION_VERSION = "demand-v2"
CoverageMode = Literal["witness", "complete_scope", "complete_adjacency"]


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


class MaterializationContract(BaseModel):
    """Strict JSON artifacts shared by extraction, execution, and observation."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class EntitySelector(MaterializationContract):
    """Exact lookup conditions, using the runtime's existing lookup semantics."""

    entity_types: list[str] = Field(default_factory=list)
    entity_ids: list[str] | None = None
    primary_key: dict[str, JsonValue] = Field(default_factory=dict)
    property_filters: dict[str, JsonValue] = Field(default_factory=dict)


class TraversalDemand(MaterializationContract):
    """A bounded adjacency request whose seeds are already resolved identities."""

    start_entity_ids: list[str]
    relation_types: list[str]
    direction: Literal["outgoing", "incoming", "both"] = "outgoing"
    max_hops: int = Field(default=1, ge=0, le=8)


class EvidenceDemand(MaterializationContract):
    """Frozen-computation evidence needs after binding one invocation's arguments."""

    format_version: Literal[1] = 1
    derivation_version: str = MATERIALIZATION_VERSION
    function_name: str
    schema_sha256: str
    function_sha256: str
    arguments_sha256: str
    entity_types: list[str]
    required_fields: dict[str, list[str]]
    relation_types: list[str] = Field(default_factory=list)
    selectors: list[EntitySelector] = Field(default_factory=list)
    traversals: list[TraversalDemand] = Field(default_factory=list)
    acquisitions: list[dict[str, JsonValue]] = Field(default_factory=list)
    coverage_mode: CoverageMode = "complete_scope"
    unknowns: list[str] = Field(default_factory=list)

    @property
    def demand_id(self) -> str:
        """Content identity includes source scope and bound argument identities."""
        return _digest(self.model_dump(mode="json"))


class MaterializationPlan(MaterializationContract):
    """Executor-owned plan; native capability arguments are never invented here."""

    format_version: Literal[1] = 1
    demand_id: str
    kernel_id: str
    receipt_ids: list[str] = Field(default_factory=list)
    acquisition_requests: list[dict[str, JsonValue]] = Field(default_factory=list)
    extractor_version: str = MATERIALIZATION_VERSION
    expansion_reason: str | None = None


class AcquisitionBinding(MaterializationContract):
    """Frozen source binding for a pure callable, separate from its implementation.

    The expression language only binds declared function inputs to a catalogued
    tool's native arguments. It cannot select a tool dynamically, execute code,
    or interpret the question. Authorization remains the executor's catalog.
    """

    format_version: Literal[1] = 1
    function_name: str
    schema_sha256: str
    function_sha256: str
    capability_id: str
    native_arguments: dict[str, JsonValue]
    contract_id: str

    @property
    def binding_id(self) -> str:
        """Content identity pins the computation, template, and tool contract."""
        return _digest(self.model_dump(mode="json"))


class PreparedAcquisition(MaterializationContract):
    """Validated executor request, with no side effects during preparation."""

    capability: str
    arguments: dict[str, JsonValue]
    contract_id: str
    binding_id: str


class PreparedMaterialization(MaterializationContract):
    """Demand and authorized source requests for one immutable function call."""

    demand: EvidenceDemand
    acquisitions: list[PreparedAcquisition] = Field(default_factory=list)


def _binding_tool(capability_id: str, capabilities: list[dict]) -> dict:
    matches = [tool for tool in capabilities if tool.get("id") == capability_id]
    if len(matches) != 1:
        raise ValueError(f"Source binding requires one authorized capability: {capability_id}")
    tool = matches[0]
    annotations = tool.get("annotations") or {}
    if annotations.get("readOnlyHint") is False or annotations.get("destructiveHint") is True:
        raise ValueError("Source binding requires an authorized read-only capability")
    if not isinstance(tool.get("contract_id"), str) or not tool["contract_id"]:
        raise ValueError("Source binding requires a recorded tool contract identity")
    _validator(tool["input_schema"])
    return tool


def _bind_template(
    value: Any, input_names: set[str], arguments: dict | None, *, depth: int = 0
) -> Any:
    """Validate or bind the small source-argument language without execution."""
    if depth > 24:
        raise ValueError("Source binding template exceeds the nesting limit of 24")
    if isinstance(value, dict):
        if any(key.startswith("$") for key in value):
            if set(value) == {"$arg"}:
                path = [value["$arg"]]
            elif set(value) == {"$arg_path"}:
                path = value["$arg_path"]
                if not isinstance(path, list) or len(path) < 2:
                    raise ValueError("$arg_path starts with an input name and field/index keys")
            else:
                raise ValueError("Source bindings support only exact $arg and $arg_path")
            if (
                not isinstance(path[0], str)
                or path[0] not in input_names
                or any(
                    isinstance(part, bool)
                    or not isinstance(part, str | int)
                    or (isinstance(part, int) and part < 0)
                    for part in path[1:]
                )
            ):
                raise ValueError("Source binding references an undeclared input or invalid path")
            if arguments is None:
                return deepcopy(value)
            result: Any = arguments
            for part in path:
                if isinstance(result, dict) and isinstance(part, str) and part in result:
                    result = result[part]
                elif isinstance(result, list) and isinstance(part, int) and part < len(result):
                    result = result[part]
                else:
                    raise ValueError("Source binding input path is absent or has the wrong type")
            return deepcopy(result)
        return {
            key: _bind_template(item, input_names, arguments, depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_bind_template(item, input_names, arguments, depth=depth + 1) for item in value]
    return deepcopy(value)


def freeze_acquisition_binding(
    schema: dict,
    function: dict,
    capability_id: str,
    native_arguments: dict,
    capabilities: list[dict],
) -> AcquisitionBinding:
    """Pin a generated source template to an actual authorized tool contract."""
    parse_schema(schema)
    FunctionSpec.model_validate(function)
    tool = _binding_tool(capability_id, capabilities)
    _bind_template(native_arguments, set(function["inputs"].get("properties", {})), None)
    if not _unresolved(native_arguments):
        _validator(tool["input_schema"]).validate(native_arguments)
    return AcquisitionBinding(
        function_name=function["name"],
        schema_sha256=_digest(schema),
        function_sha256=_digest(function),
        capability_id=capability_id,
        native_arguments=deepcopy(native_arguments),
        contract_id=tool["contract_id"],
    )


def prepare_bound_materialization(
    schema: dict,
    function: dict,
    arguments: dict,
    bindings: list[AcquisitionBinding | dict],
    capabilities: list[dict],
) -> PreparedMaterialization:
    """Prepare demands and native calls, without acquiring or spending anything.

    Frozen function and source contracts must still match. Selectors stay in the
    graph demand unless the generated template explicitly binds an actual native
    input. A question-specific selector is never added to an MCP request by guess.
    """
    FunctionSpec.model_validate(function)
    _validator(function["inputs"]).validate(arguments)
    requests: list[PreparedAcquisition] = []
    seen: set[str] = set()
    for raw in bindings:
        binding = (
            raw if isinstance(raw, AcquisitionBinding) else AcquisitionBinding.model_validate(raw)
        )
        if binding.function_name != function["name"]:
            continue
        if binding.schema_sha256 != _digest(schema) or binding.function_sha256 != _digest(function):
            raise ValueError("Source binding does not match the frozen schema/function")
        tool = _binding_tool(binding.capability_id, capabilities)
        if tool["contract_id"] != binding.contract_id:
            raise ValueError("Source binding tool contract changed")
        native = _bind_template(
            binding.native_arguments, set(function["inputs"].get("properties", {})), arguments
        )
        if not isinstance(native, dict):
            raise ValueError("Source binding must produce an object of native arguments")
        _validator(tool["input_schema"]).validate(native)
        identity = _digest({"capability": binding.capability_id, "arguments": native})
        if identity in seen:
            continue
        seen.add(identity)
        requests.append(
            PreparedAcquisition(
                capability=binding.capability_id,
                arguments=native,
                contract_id=binding.contract_id,
                binding_id=binding.binding_id,
            )
        )
    demand = derive_demand(schema, function, arguments)
    return PreparedMaterialization(demand=demand, acquisitions=requests)


class MissingFact(MaterializationContract):
    """Absence is attributed rather than silently converted to a null value."""

    entity_id: str
    property: str
    state: Literal["unmaterialized", "source_absent", "explicit_null", "extraction_failure"]
    evidence_refs: list[str] = Field(default_factory=list)


class CoverageReceipt(MaterializationContract):
    """Independent coverage evidence supplied by trusted executor-side adapters.

    This DTO is not an authorization token. Only checker-produced artifacts,
    resolved by the owning executor, may enter ``assess_sufficiency``. A candidate
    cannot turn its declaration into a trusted receipt. Snapshot completeness
    deliberately cannot establish source-population completeness.
    """

    format_version: Literal[1] = 1
    demand_id: str
    schema_sha256: str
    graph_sha256: str
    source_receipt_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    checker_id: str | None = None
    checker_version: str | None = None
    basis: Literal[
        "adapter_verified",
        "deterministic_source_mapping",
        "observed_only",
        "model_claim",
        "generated_check",
    ] = "observed_only"
    scope: Literal["source_population", "materialized_snapshot"] = "materialized_snapshot"
    population_complete: bool = False
    adjacency_complete: bool = False
    fields_checked: dict[str, list[str]] = Field(default_factory=dict)
    pagination_exhausted: bool | None = None
    frontier_exhausted: bool | None = None
    missing: list[MissingFact] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_basis(self) -> CoverageReceipt:
        """Require attribution whenever a trusted checker basis is asserted."""
        if self.basis in {"adapter_verified", "deterministic_source_mapping"}:
            if not self.checker_id or not self.checker_version or not self.evidence_refs:
                raise ValueError(
                    "independent coverage requires checker identity/version and evidence"
                )
        return self


class SufficiencyResult(MaterializationContract):
    """Nonblocking evidence-scope assessment, separate from execution and task success."""

    format_version: Literal[1] = 1
    demand_id: str
    status: Literal["satisfied", "needs_evidence", "unknown", "incompatible"]
    coverage_mode: CoverageMode
    unmet_demands: list[str] = Field(default_factory=list)
    missing: list[MissingFact] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)


def _resolve_arguments(
    value: Any, arguments: dict[str, Any], step_outputs: dict[str, Any] | None = None
) -> Any:
    """Bind inputs and actual prior outputs, preserving unresolved references."""
    outputs = step_outputs or {}
    if isinstance(value, dict):
        if set(value) == {"$arg"}:
            return deepcopy(arguments.get(value["$arg"], value))
        if set(value) == {"$step"} and value["$step"] in outputs:
            return deepcopy(outputs[value["$step"]])
        if set(value) == {"$path"}:
            path = value["$path"]
            if isinstance(path, list) and path and path[0] in outputs:
                result = outputs[path[0]]
                for key in path[1:]:
                    if isinstance(result, list) and type(key) is int and 0 <= key < len(result):
                        result = result[key]
                    elif isinstance(result, dict) and isinstance(key, str) and key in result:
                        result = result[key]
                    else:
                        raise ValueError("Demand path does not match the actual step output")
                return deepcopy(result)
        return {key: _resolve_arguments(item, arguments, outputs) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_arguments(item, arguments, outputs) for item in value]
    return value


def _unresolved(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key.startswith("$") for key in value) or any(
            _unresolved(item) for item in value.values()
        )
    return any(_unresolved(item) for item in value) if isinstance(value, list) else False


def _properties(spec, entity_type: str) -> dict:
    return {
        key: declaration
        for name in [entity_type, *sorted(spec.ancestors(entity_type))]
        for key, declaration in spec.entity_types[name].properties.items()
    }


def _required_properties(spec, entity_type: str) -> set[str]:
    result: set[str] = set()
    for name in [entity_type, *sorted(spec.ancestors(entity_type))]:
        entity = spec.entity_types[name]
        result.add(entity.primary_key)
        result.update(key for key, declaration in entity.properties.items() if declaration.required)
    return result


def derive_demand(
    schema: dict,
    function: dict,
    arguments: dict,
    *,
    step_outputs: dict[str, Any] | None = None,
) -> EvidenceDemand:
    """Derive conservative information needs without interpreting natural language.

    Dynamic step-derived selectors broaden the demand until real prior outputs
    are supplied. Output paths bind from those values, never from predictions. Exact
    primary-key or ID lookup can use witness coverage. Aggregation always needs
    population coverage; traversal requires complete adjacency. Type hints in
    acquisition result paths are recognized from the existing executor format.
    """
    spec = parse_schema(schema)
    selected: set[str] = set()
    acquired_types: set[str] = set()
    fields: set[str] = set()
    relations: set[str] = set()
    selectors: list[EntitySelector] = []
    traversals: list[TraversalDemand] = []
    acquisitions: list[dict] = []
    unknowns: list[str] = []
    aggregates = False
    graph_read = False
    unresolved_fields = False
    unresolved_frontier = False
    needs_all_fields = False
    graph_value_steps = {
        step["id"]
        for step in function.get("steps", [])
        if step["operator"]
        in {
            "invoke_capability",
            "lookup_entities",
            "traverse_relations",
            "filter_numeric",
            "filter_property_categorical",
            "filter_categorical",
            "filter_relation_connected",
            "filter_set_overlap",
        }
    }

    def collect_path_types(value: Any) -> None:
        nonlocal needs_all_fields
        if isinstance(value, dict):
            path = value.get("$path")
            if (
                isinstance(path, list)
                and len(path) >= 3
                and path[0] in graph_value_steps
                and path[1] == "entities_by_type"
            ):
                if path[2] in spec.entity_types:
                    selected.add(path[2])
                    acquired_types.add(path[2])
            if isinstance(path, list) and path and path[0] in graph_value_steps:
                for position, part in enumerate(path[1:], 1):
                    if part == "properties":
                        if position + 1 < len(path) and isinstance(path[position + 1], str):
                            fields.add(path[position + 1])
                        else:
                            needs_all_fields = True
            for item in value.values():
                collect_path_types(item)
        elif isinstance(value, list):
            for item in value:
                collect_path_types(item)

    # A directly returned entity/lookup result promises its fields, not only keys.
    direct_results: set[str] = set()
    acquisition_entity_results: set[str] = set()

    def result_references(value: Any) -> None:
        if isinstance(value, dict):
            if set(value) == {"$step"}:
                direct_results.add(value["$step"])
                acquisition_entity_results.add(value["$step"])
            path = value.get("$path")
            if isinstance(path, list) and path:
                direct_results.add(path[0])
                if len(path) > 1 and path[1] in {"entities", "entities_by_type"}:
                    acquisition_entity_results.add(path[0])
            for item in value.values():
                result_references(item)
        elif isinstance(value, list):
            for item in value:
                result_references(item)

    result_references(function.get("result"))
    collect_path_types(function.get("result"))
    for step in function.get("steps", []):
        operator = step["operator"]
        collect_path_types(step.get("args", {}))
        args = _resolve_arguments(step.get("args", {}), arguments, step_outputs)
        if operator == "invoke_capability":
            if step["id"] in acquisition_entity_results:
                graph_read = True
                needs_all_fields = True
            if _unresolved(args):
                unknowns.append(f"{step['id']}: acquisition scope depends on runtime values")
            else:
                acquisitions.append(args)
            continue
        if operator == "extract_runtime_slots":
            continue
        if operator == "lookup_entities":
            graph_read = True
            types = args.get("entity_types")
            if not isinstance(types, list) or _unresolved(types):
                types = list(spec.entity_types)
            if any(name not in spec.entity_types for name in types):
                raise ValueError("demand references an undeclared entity type")
            selected.update(types)
            values = {
                "entity_types": types,
                "entity_ids": args.get("entity_ids"),
                "primary_key": args.get("primary_key") or {},
                "property_filters": args.get("property_filters") or {},
            }
            if _unresolved(values):
                unknowns.append(f"{step['id']}: lookup selector depends on runtime values")
                selectors.append(EntitySelector(entity_types=types))
            else:
                selector = EntitySelector.model_validate(values)
                selectors.append(selector)
                fields.update(selector.primary_key)
                fields.update(selector.property_filters)
            if step["id"] in direct_results:
                needs_all_fields = True
        if operator == "traverse_relations":
            graph_read = True
            names = args.get("relation_types")
            if not isinstance(names, list) or _unresolved(names):
                names = list(spec.relations)
            if any(name not in spec.relations for name in names):
                raise ValueError("demand references an undeclared relation")
            relations.update(names)
            for name in names:
                selected.update([spec.relations[name].source, spec.relations[name].target])
            values = {
                "start_entity_ids": args.get("start_entity_ids"),
                "relation_types": names,
                "direction": args.get("direction", "outgoing"),
                "max_hops": args.get("max_hops", 1),
            }
            if _unresolved(values) or values["start_entity_ids"] is None:
                unknowns.append(f"{step['id']}: traversal frontier depends on runtime values")
                unresolved_frontier = True
            else:
                traversals.append(TraversalDemand.model_validate(values))
            if step["id"] in direct_results:
                needs_all_fields = True
        if operator in {
            "project_properties",
            "filter_numeric",
            "filter_property_categorical",
            "filter_relation_connected",
            "filter_set_overlap",
            "filter_categorical",
            "aggregate_values",
        }:
            graph_read = True
            if step["id"] in direct_results and operator.startswith("filter"):
                needs_all_fields = True
            if operator == "project_properties":
                names = args.get("property_names", [])
                if _unresolved(names):
                    unresolved_fields = True
                else:
                    fields.update(names)
            if _unresolved(args.get("conditions", [])):
                # Values can be dynamic without changing required properties, but
                # an entire condition/field expression cannot be silently ignored.
                if not isinstance(args.get("conditions", []), list) or any(
                    isinstance(condition, dict)
                    and (
                        any(key.startswith("$") for key in condition)
                        or _unresolved(condition.get("property"))
                        or _unresolved(condition.get("relation"))
                    )
                    for condition in args.get("conditions", [])
                ):
                    unresolved_fields = True
            for condition in (
                args.get("conditions", []) if isinstance(args.get("conditions", []), list) else []
            ):
                if isinstance(condition, dict):
                    name = condition.get("property")
                    if isinstance(name, str):
                        fields.add(name)
                    elif name is not None:
                        unresolved_fields = True
                    relation = condition.get("relation")
                    if isinstance(relation, str):
                        relations.add(relation)
            if operator == "aggregate_values":
                aggregates = True
                request = args.get("request", {})
                if _unresolved(request):
                    unresolved_fields = True
                elif isinstance(request, dict):
                    fields.update(request[key] for key in ("field", "group_by") if request.get(key))

    if graph_read and not selected:
        selected.update(spec.entity_types)
    # An acquisition result path reads the whole returned type population. A
    # traversal endpoint declaration alone does not: it is restricted by the
    # resolved frontier and must not pull every endpoint of that type into G.
    selectors.extend(EntitySelector(entity_types=[name]) for name in sorted(acquired_types))
    if unresolved_fields:
        unknowns.append("Required property names depend on runtime values")
    if unresolved_frontier:
        # One statically known traversal cannot stand in for all traversals in
        # the function. Preserve requested adjacency conservatively until every
        # frontier can be bound from actual execution values.
        traversals = []
    for relation in relations:
        if relation not in spec.relations:
            raise ValueError("demand references an undeclared relation")
        selected.update([spec.relations[relation].source, spec.relations[relation].target])
    declared_fields = {field for name in selected for field in _properties(spec, name)}
    if fields - declared_fields:
        raise ValueError(
            f"demand references undeclared properties: {sorted(fields - declared_fields)}"
        )
    required = {}
    for entity_type in sorted(selected):
        available = _properties(spec, entity_type)
        demanded = (
            set(available) if unresolved_fields or needs_all_fields else fields & available.keys()
        )
        required[entity_type] = sorted(demanded | _required_properties(spec, entity_type))
    exact_witness = bool(selectors) and all(
        selector.entity_ids
        or (
            len(selector.entity_types) == 1
            and spec.entity_types[selector.entity_types[0]].primary_key in selector.primary_key
        )
        for selector in selectors
    )
    mode: CoverageMode = (
        "complete_adjacency"
        if relations
        else "witness"
        if exact_witness and not aggregates
        else "complete_scope"
    )
    return EvidenceDemand(
        function_name=function["name"],
        schema_sha256=_digest(schema),
        function_sha256=_digest(function),
        arguments_sha256=_digest(arguments),
        entity_types=sorted(selected),
        required_fields=required,
        relation_types=sorted(relations),
        selectors=selectors,
        traversals=traversals,
        acquisitions=acquisitions,
        coverage_mode=mode,
        unknowns=sorted(set(unknowns)),
    )


def derive_step_demand(
    schema: dict,
    function: dict,
    arguments: dict,
    step_id: str,
    *,
    step_outputs: dict[str, Any] | None = None,
) -> EvidenceDemand:
    """Activate graph scope through the impending step using actual prior outputs.

    Future lookups, acquisition, and traversal do not force all their scopes into
    the first slice. Property dependencies from the complete frozen computation
    remain present, so entities returned by earlier steps keep the fields later
    pure operations need. This is an executor preparation helper, not a changed
    callable: the resulting demand pins the original full function identity.
    """
    steps = function.get("steps", [])
    positions = [index for index, step in enumerate(steps) if step["id"] == step_id]
    if len(positions) != 1:
        raise ValueError("Materialization step is absent or ambiguous in the frozen function")
    boundary = positions[0]
    scope_operators = {
        "lookup_entities",
        "traverse_relations",
        "filter_relation_connected",
        "invoke_capability",
    }
    scoped = deepcopy(function)
    scoped["steps"] = [
        step
        for index, step in enumerate(steps)
        if index <= boundary or step["operator"] not in scope_operators
    ]
    demand = derive_demand(schema, scoped, arguments, step_outputs=step_outputs)
    unknowns = list(demand.unknowns)
    if len(scoped["steps"]) < len(steps):
        unknowns.append("Future graph-read scopes await their actual execution boundary")
    return demand.model_copy(
        update={"function_sha256": _digest(function), "unknowns": sorted(set(unknowns))}
    )


def extraction_schema(schema: dict, demand: EvidenceDemand) -> dict:
    """Return the unchanged frozen schema after validating the demand binding.

    Extraction receives a demand alongside S. Removing declarations from S would
    break restrictions, inheritance, and revision identity. It is unnecessary for
    limiting which facts the extractor instantiates.
    """
    if _digest(schema) != demand.schema_sha256:
        raise ValueError("evidence demand is bound to another schema")
    parse_schema(schema)
    return deepcopy(schema)


def _selected_nodes(graph: dict, demand: EvidenceDemand) -> set[str]:
    selected: set[str] = set()
    if demand.selectors:
        for selector in demand.selectors:
            selected.update(
                node["id"]
                for node in lookup_entities(
                    graph,
                    entity_types=selector.entity_types or None,
                    entity_ids=selector.entity_ids,
                    primary_key=selector.primary_key,
                    property_filters=selector.property_filters,
                )
            )
    elif not demand.traversals:
        selected.update(
            node["id"] for node in graph.get("nodes", []) if node["type"] in demand.entity_types
        )
    return selected


def slice_graph(schema: dict, graph: dict, demand: EvidenceDemand) -> dict:
    """Project genuine graph evidence, preserving validation and provenance.

    This function never asserts that its input represents the complete source.
    The caller retains that independent coverage evidence separately.
    """
    extraction_schema(schema, demand)
    validation = validate_graph_records(schema, graph.get("nodes", []), graph.get("edges", []))
    if not validation["valid"]:
        raise ValueError(f"Cannot materialize invalid evidence: {validation['errors']}")
    selected = _selected_nodes(graph, demand)
    known_ids = {node["id"] for node in graph.get("nodes", [])}
    edges: list[dict] = []
    if demand.traversals:
        for traversal in demand.traversals:
            seeds = [identity for identity in traversal.start_entity_ids if identity in known_ids]
            if not seeds:
                continue
            traversed = traverse_relations(
                graph,
                **{
                    **traversal.model_dump(),
                    "start_entity_ids": seeds,
                },
            )
            selected.update(node["id"] for node in traversed["entities"])
            edges.extend(traversed["relations"])
    elif demand.relation_types:
        edges = [
            edge
            for edge in graph.get("edges", [])
            if edge["relation"] in demand.relation_types
            and (edge["source"] in selected or edge["target"] in selected)
        ]
    for edge in edges:
        selected.update([edge["source"], edge["target"]])
    spec = parse_schema(schema)
    nodes = []
    for node in graph.get("nodes", []):
        if node["id"] not in selected:
            continue
        fields = set(demand.required_fields.get(node["type"], [])) | _required_properties(
            spec, node["type"]
        )
        nodes.append(
            {
                **deepcopy(node),
                "properties": {
                    key: deepcopy(value)
                    for key, value in node["properties"].items()
                    if key in fields
                },
            }
        )
    result = {
        **deepcopy(graph),
        "nodes": nodes,
        "edges": list({_digest(edge): deepcopy(edge) for edge in edges}.values()),
    }
    check = validate_graph_records(schema, result["nodes"], result["edges"])
    if not check["valid"]:
        raise ValueError(f"Materialization violated the frozen schema: {check['errors']}")
    return result


def assess_sufficiency(
    schema: dict,
    graph: dict,
    demand: EvidenceDemand,
    coverage_receipts: list[CoverageReceipt | dict] | tuple = (),
) -> SufficiencyResult:
    """Report the observed evidence scope without restricting planner autonomy.

    Receipts are resolved by the trusted executor, never accepted from model
    output. Hashes bind their evidence to this exact demand and materialization.
    The checker does not turn a finite extracted graph into a closed source.
    ``unknown`` is an observation, not an execution or answer gate. Callers may
    pass it to the planner, which decides whether to expand or answer within its
    bounds. This function never starts acquisition, cancels execution, or scores
    the final answer. Independent task assessment remains a separate channel.
    """
    base = {
        "demand_id": demand.demand_id,
        "coverage_mode": demand.coverage_mode,
        "node_count": len(graph.get("nodes", [])),
        "edge_count": len(graph.get("edges", [])),
    }
    if _digest(schema) != demand.schema_sha256:
        return SufficiencyResult(
            **base, status="incompatible", unmet_demands=["Schema binding changed"]
        )
    check = validate_graph_records(schema, graph.get("nodes", []), graph.get("edges", []))
    if not check["valid"]:
        return SufficiencyResult(**base, status="incompatible", unmet_demands=check["errors"])
    receipts = [CoverageReceipt.model_validate(item) for item in coverage_receipts]
    matching = [
        item
        for item in receipts
        if item.demand_id == demand.demand_id
        and item.schema_sha256 == demand.schema_sha256
        and item.graph_sha256 == _digest(graph)
    ]
    evidence = sorted({ref for item in matching for ref in item.evidence_refs})
    annotated = {
        (item.entity_id, item.property): item for receipt in matching for item in receipt.missing
    }
    selected = _selected_nodes(graph, demand)
    if demand.traversals:
        selected = {node["id"] for node in slice_graph(schema, graph, demand)["nodes"]}
    missing = []
    for node in graph.get("nodes", []):
        if node["id"] not in selected:
            continue
        for field in demand.required_fields.get(node["type"], []):
            if field not in node["properties"] or node["properties"][field] is None:
                missing.append(
                    annotated.get((node["id"], field))
                    or MissingFact(
                        entity_id=node["id"],
                        property=field,
                        state="explicit_null" if field in node["properties"] else "unmaterialized",
                    )
                )
    if missing:
        return SufficiencyResult(
            **base,
            status="needs_evidence",
            missing=missing,
            evidence_refs=evidence,
            unmet_demands=["Required values are missing"],
        )
    if demand.unknowns:
        return SufficiencyResult(
            **base, status="unknown", evidence_refs=evidence, unmet_demands=demand.unknowns
        )
    if demand.coverage_mode == "witness":
        for selector in demand.selectors:
            matches = lookup_entities(
                graph, **{**selector.model_dump(), "entity_types": selector.entity_types or None}
            )
            identities = {node["id"] for node in matches}
            if not matches or (selector.entity_ids and not set(selector.entity_ids) <= identities):
                return SufficiencyResult(
                    **base,
                    status="needs_evidence",
                    evidence_refs=evidence,
                    unmet_demands=["Requested identity witness is unavailable"],
                )
        return SufficiencyResult(**base, status="satisfied", evidence_refs=evidence)
    for receipt in matching:
        if receipt.basis not in {"adapter_verified", "deterministic_source_mapping"}:
            continue
        if receipt.scope != "source_population" or not receipt.population_complete:
            continue
        if not receipt.source_receipt_ids or receipt.missing:
            continue
        if any(
            not set(fields) <= set(receipt.fields_checked.get(name, []))
            for name, fields in demand.required_fields.items()
        ):
            continue
        if demand.coverage_mode == "complete_adjacency" and not receipt.adjacency_complete:
            continue
        return SufficiencyResult(**base, status="satisfied", evidence_refs=evidence)
    return SufficiencyResult(
        **base,
        status="unknown",
        evidence_refs=evidence,
        unmet_demands=["No independent complete-source coverage for this demand"],
    )


def materialization_cache_key(
    receipt_sha256: str,
    kernel_id: str,
    extractor_version: str,
    demand: EvidenceDemand,
) -> str:
    """Cache only the exact receipt, frozen kernel, extractor, and demand tuple."""
    if not all((receipt_sha256, kernel_id, extractor_version)):
        raise ValueError("materialization cache requires receipt, kernel, and extractor versions")
    return _digest(
        {
            "receipt_sha256": receipt_sha256,
            "kernel_id": kernel_id,
            "extractor_version": extractor_version,
            "demand_id": demand.demand_id,
        }
    )

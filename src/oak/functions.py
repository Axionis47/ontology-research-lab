"""Validate and execute a restricted, typed catalog of OaK function compositions.

The catalog is data, not Python source. Only the registered operators can execute.
The DSL has no loops, imports, dynamic evaluation, or direct file/network access.
Model and MCP operators require explicit executor-owned callbacks.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import time
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from oak import operators
from oak.ontology import parse_schema, validate_graph_records
from oak.store import Store, canonical


class FunctionStep(BaseModel):
    """One bounded operator call whose references may use only inputs or earlier steps."""

    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    operator: operators.OperatorName
    args: dict[str, JsonValue]


class FunctionSpec(BaseModel):
    """A typed callable and its inspectable, finite realization over generic operators."""

    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    description: str = Field(min_length=1, max_length=4000)
    inputs: dict[str, JsonValue]
    output_schema: dict[str, JsonValue]
    steps: list[FunctionStep] = Field(min_length=1, max_length=32)
    result: JsonValue


class FunctionExecutionError(ValueError):
    """Execution failure retaining actual completed steps and dependency evidence."""

    def __init__(
        self, message: str, *, steps: list[dict], dependencies: dict, capture_id: str | None = None
    ) -> None:
        super().__init__(message)
        self.steps = steps
        self.dependencies = dependencies
        self.capture_id = capture_id


def _bounded(value: Any, depth: int = 0) -> None:
    if depth > 24:
        raise ValueError("Function data exceeds the nesting limit of 24")
    if isinstance(value, dict):
        for item in value.values():
            _bounded(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > 10_000:
            raise ValueError("Function data exceeds the list limit of 10000")
        for item in value:
            _bounded(item, depth + 1)


def _check_json_schema(schema: dict[str, Any]) -> None:
    _bounded(schema)

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            forbidden = {"$ref", "$dynamicRef", "$recursiveRef", "pattern", "patternProperties"}
            if forbidden.intersection(value):
                raise ValueError("Schema references and regular-expression schemas are unsupported")
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(schema)
    Draft202012Validator.check_schema(schema)


def _references(value: Any, arguments: set[str], previous_steps: set[str]) -> set[str]:
    used_steps: set[str] = set()
    if isinstance(value, dict):
        if any(key.startswith("$") for key in value):
            if set(value) == {"$arg"}:
                if value["$arg"] not in arguments:
                    raise ValueError(f"Unknown function input reference: {value['$arg']}")
            elif set(value) == {"$step"}:
                if value["$step"] not in previous_steps:
                    raise ValueError(f"Unknown or forward step reference: {value['$step']}")
                used_steps.add(value["$step"])
            elif set(value) == {"$path"}:
                path = value["$path"]
                if not isinstance(path, list) or len(path) < 2 or path[0] not in previous_steps:
                    raise ValueError(
                        "$path starts with a prior step ID followed by field/index keys"
                    )
                if any(isinstance(part, bool) or not isinstance(part, str | int) for part in path):
                    raise ValueError("$path accepts only string fields and integer indices")
                used_steps.add(path[0])
            else:
                raise ValueError(
                    "Only exact $arg, $step, and $path reference objects are supported"
                )
        else:
            for nested in value.values():
                used_steps.update(_references(nested, arguments, previous_steps))
    elif isinstance(value, list):
        for nested in value:
            used_steps.update(_references(nested, arguments, previous_steps))
    return used_steps


def _resolve(value: Any, args: dict[str, Any], results: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$arg"}:
            if value["$arg"] not in args:
                raise ValueError(f"Referenced optional input is absent: {value['$arg']}")
            return deepcopy(args[value["$arg"]])
        if set(value) == {"$step"}:
            return deepcopy(results[value["$step"]])
        if set(value) == {"$path"}:
            result = results[value["$path"][0]]
            for key in value["$path"][1:]:
                if isinstance(result, list) and isinstance(key, int) and key >= 0:
                    result = result[key]
                elif isinstance(result, dict) and isinstance(key, str):
                    result = result[key]
                else:
                    raise ValueError("$path type/index does not match the actual step output")
            return deepcopy(result)
        return {key: _resolve(item, args, results) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, args, results) for item in value]
    return value


def _literal(value: Any) -> bool:
    if isinstance(value, dict):
        return not any(key.startswith("$") for key in value) and all(
            _literal(nested) for nested in value.values()
        )
    return all(_literal(nested) for nested in value) if isinstance(value, list) else True


def _check_membership(args: dict[str, Any], schema: dict[str, Any], *, runtime: bool) -> None:
    parsed = parse_schema(schema)
    types = {
        name: {
            "properties": {
                key: declaration.model_dump()
                for scope in [name, *sorted(parsed.ancestors(name))]
                for key, declaration in parsed.entity_types[scope].properties.items()
            }
        }
        for name in parsed.entity_types
    }
    relations = parsed.relations
    selected_types = args.get("entity_types")
    if selected_types is not None and _literal(selected_types):
        if not isinstance(selected_types, list) or any(
            name not in types for name in selected_types
        ):
            raise ValueError("entity_types contains an undeclared schema type")
    else:
        selected_types = list(types)
    if "entities" in args and runtime:
        selected_types = sorted(
            {entity["type"] for entity in operators.entity_list(args["entities"])}
        )
    if any(name not in types for name in selected_types):
        raise ValueError("Selected entity has an undeclared schema type")
    properties = {name for entity_type in types.values() for name in entity_type["properties"]}
    property_references: list[Any] = []
    for container in ("primary_key", "property_filters"):
        value = args.get(container)
        if isinstance(value, dict) and not any(key.startswith("$") for key in value):
            property_references.extend(value)
            if container == "primary_key":
                identity_fields = {parsed.entity_types[name].primary_key for name in selected_types}
                if not set(value).issubset(identity_fields):
                    raise ValueError(
                        "primary_key filter must reference declared identity properties"
                    )
    names = args.get("property_names")
    if isinstance(names, list):
        property_references.extend(name for name in names if _literal(name))
    for condition in (
        args.get("conditions", []) if isinstance(args.get("conditions", []), list) else []
    ):
        if isinstance(condition, dict):
            if "property" in condition and _literal(condition["property"]):
                property_references.append(condition["property"])
            if "relation" in condition and _literal(condition["relation"]):
                if condition["relation"] not in relations:
                    raise ValueError(f"Undeclared relation: {condition['relation']}")
    request = args.get("request", {})
    if isinstance(request, dict):
        for key in ("field", "group_by"):
            if request.get(key) is not None and _literal(request[key]):
                property_references.append(request[key])
    for name in property_references:
        if not isinstance(name, str) or name not in properties:
            raise ValueError(f"Undeclared schema property: {name}")
        if (
            (runtime and "entities" in args)
            or args.get("entity_types") is not None
            and _literal(args["entity_types"])
        ):
            if any(name not in types[entity_type]["properties"] for entity_type in selected_types):
                raise ValueError(f"Property {name} is not declared on every selected entity type")
    selected_relations = args.get("relation_types")
    if selected_relations is not None and _literal(selected_relations):
        if not isinstance(selected_relations, list) or any(
            name not in relations for name in selected_relations
        ):
            raise ValueError("relation_types contains an undeclared schema relation")
    if runtime:

        def validate_value(property_name: str, value: Any, *, member: bool = False) -> None:
            declarations = [
                types[name]["properties"][property_name]
                for name in selected_types
                if property_name in types[name]["properties"]
            ]
            for declaration in declarations:
                datatype = declaration["type"]
                expected: dict[str, Any] = {
                    "type": "string" if datatype == "date_time" else datatype
                }
                if datatype == "date_time":
                    expected["format"] = "date-time"
                if not declaration.get("functional", True) and not member:
                    expected = {"type": "array", "items": expected}
                Draft202012Validator(expected, format_checker=FormatChecker()).validate(value)

        for container in ("primary_key", "property_filters"):
            for property_name, value in (args.get(container) or {}).items():
                validate_value(property_name, value)
        for condition in args.get("conditions", []):
            property_name = condition.get("property")
            if property_name is None:
                continue
            for key in ("value", "minimum", "maximum"):
                if condition.get(key) is not None:
                    validate_value(property_name, condition[key])
            for value in condition.get("values", []):
                if value is not None:
                    validate_value(property_name, value, member="mode" in condition)


def validate_functions(
    catalog: list[FunctionSpec | dict], schema: dict[str, Any]
) -> list[FunctionSpec]:
    """Validate catalog schema references, execution order, and bounded DSL contracts."""
    if not isinstance(catalog, list) or not 1 <= len(catalog) <= 64:
        raise ValueError("A catalog must contain between 1 and 64 functions")
    checked = [
        entry if isinstance(entry, FunctionSpec) else FunctionSpec.model_validate(entry)
        for entry in catalog
    ]
    if len({entry.name for entry in checked}) != len(checked):
        raise ValueError("Function names must be unique")
    for entry in checked:
        document = entry.model_dump(mode="json")
        _bounded(document)
        if len(json.dumps(document)) > 100_000:
            raise ValueError("Function definition exceeds 100000 characters")
        _check_json_schema(entry.inputs)
        _check_json_schema(entry.output_schema)
        if (
            entry.inputs.get("type") != "object"
            or entry.inputs.get("additionalProperties") is not False
        ):
            raise ValueError(
                "Function inputs require an object schema with additionalProperties=false"
            )
        previous_steps: set[str] = set()
        arguments = set(entry.inputs.get("properties", {}))
        for step in entry.steps:
            if step.id in previous_steps:
                raise ValueError(f"Duplicate step ID: {step.id}")
            if step.operator not in operators.OPERATORS:
                raise ValueError(f"Unsupported operator: {step.operator}")
            if {"graph", "slot_extractor", "capability_invoker"}.intersection(step.args):
                raise ValueError(
                    "Graph/model dependencies are supplied by the executor, not the catalog"
                )
            _references(step.args, arguments, previous_steps)
            if step.operator == "invoke_capability" and not isinstance(
                step.args.get("capability"), str
            ):
                raise ValueError(
                    "Capability bindings must be literal frozen capability identifiers"
                )
            invocation = dict(step.args)
            if step.operator in operators.GRAPH_OPERATORS:
                invocation["graph"] = {}
            inspect.signature(operators.OPERATORS[step.operator]).bind(**invocation)
            _check_membership(step.args, schema, runtime=False)
            previous_steps.add(step.id)
        if not _references(entry.result, arguments, previous_steps):
            raise ValueError(
                "Function result must depend on an executed step, not a canned constant"
            )
    return checked


def _check_evidence_inputs(arguments: dict[str, Any], graph: dict[str, Any]) -> None:
    """Reject invented entity/row inputs instead of accepting graph-shaped caller data."""
    by_id = {node["id"]: node for node in graph["nodes"]}
    for key in ("entities", "items"):
        if key not in arguments:
            continue
        value = arguments[key]
        rows = value.get("entities") if isinstance(value, dict) else value
        if not isinstance(rows, list):
            raise ValueError(f"{key} must come from actual graph/entity/projection results")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"{key} requires graph-derived records")
            if {"id", "type", "properties", "sources"}.issubset(row):
                original = by_id.get(row["id"])
                if original is None or any(
                    row[field] != original[field] for field in ("type", "properties", "sources")
                ):
                    raise ValueError("Entity input does not match the actual graph snapshot")
            elif "__entity_id" in row:
                original = by_id.get(row["__entity_id"])
                if original is None or row.get("__entity_type") != original["type"]:
                    raise ValueError("Projection refers to an unknown entity")
                for field, field_value in row.items():
                    metadata = {"__entity_id", "__entity_type", "__sources", "__primary_key"}
                    if field not in metadata and field_value != original["properties"].get(field):
                        raise ValueError("Projected property differs from the actual graph value")
                if row.get("__sources") != original["sources"]:
                    raise ValueError("Projection source provenance differs from the graph")
            else:
                raise ValueError(
                    "Only graph entities or provenance-preserving projections are accepted"
                )


def execute_function(
    graph: dict[str, Any],
    catalog: list[FunctionSpec | dict],
    name: str,
    args: dict[str, Any],
    *,
    schema: dict[str, Any],
    slot_extractor: Callable[..., dict[str, Any]] | None = None,
    capability_invoker: Callable[..., dict[str, Any]] | None = None,
    step_observer: Callable[[dict[str, Any]], None] | None = None,
    before_step: Callable[..., None] | None = None,
    artifact_store: Store | None = None,
) -> dict[str, Any]:
    """Execute a validated typed function and retain actual inputs, outputs, and dependencies.

    Dependencies conservatively include the complete graph hash and schema hash.
    This includes negative/aggregate query dependencies; it does not claim minimal
    invalidation coverage. Failed executions raise FunctionExecutionError with traces.
    An optional observer receives real operator boundaries for durable event logging.
    An executor-owned ``before_step`` callback receives keyword arguments
    ``step_id``, ``operator``, ``arguments``, and ``step_outputs`` after binding.
    It may materialize evidence in the shared graph before the primitive runs.
    Inputs and earlier outputs passed to it are copies. New graph records are
    validated and included in dependency evidence, including when execution fails.
    With ``artifact_store``, immutable graph snapshots are saved at the initial,
    pre-operator and final boundaries. A function capture binds those inputs to
    the real result or failure and exact runtime pins, before any pass assessment.
    """
    capture_inputs: dict[str, Any] = {}
    traces: list[dict[str, Any]] = []
    dependencies: dict[str, Any] = {}
    if artifact_store is not None:
        from oak.preservation import runtime_dependencies

        capture_inputs = {
            "format_version": 1,
            "function": name,
            "args": deepcopy(args),
            "schema_ref": artifact_store.put("function_schema", schema),
            "functions_ref": artifact_store.put(
                "function_catalog",
                [
                    item.model_dump(mode="json") if isinstance(item, FunctionSpec) else item
                    for item in catalog
                ],
            ),
            "initial_graph_ref": artifact_store.put("function_input_graph", graph),
            "runtime_dependencies": {
                key: value
                for key, value in runtime_dependencies().items()
                if key in {"operators", "executor", "ontology", "runtime_lock"}
            },
        }
        capture_inputs["input_manifest_ref"] = artifact_store.put(
            "function_capture_inputs", capture_inputs
        )

    def capture_execution(
        status: str, *, value: Any = None, error: str | None = None
    ) -> str | None:
        if artifact_store is None:
            return None
        payload = {
            **capture_inputs,
            "status": status,
            "final_graph_ref": artifact_store.put("function_final_graph", graph),
            "steps": traces,
            "dependencies": dependencies,
        }
        if status == "completed":
            payload["value"] = value
        else:
            payload["error"] = error
        return artifact_store.put("function_capture", payload)

    try:
        checked = validate_functions(catalog, schema)
        selected = next((entry for entry in checked if entry.name == name), None)
        if selected is None:
            raise ValueError(f"Function {name} is absent from the frozen catalog")
        Draft202012Validator(selected.inputs, format_checker=FormatChecker()).validate(args)
        _bounded(args)
        graph_validation = validate_graph_records(schema, graph["nodes"], graph.get("edges", []))
        if not graph_validation["valid"]:
            raise ValueError(f"Invalid graph records: {graph_validation['errors']}")
    except Exception as error:
        if artifact_store is None:
            raise
        message = f"{type(error).__name__}: {error}"
        raise FunctionExecutionError(
            message,
            steps=traces,
            dependencies=dependencies,
            capture_id=capture_execution("failed", error=message),
        ) from error

    def digest(value: Any) -> str:
        return hashlib.sha256(canonical(value)).hexdigest()

    dependencies = {
        "graph_sha256": digest(graph),
        "schema_sha256": digest(schema),
        "function_sha256": digest(selected.model_dump(mode="json")),
        "coverage": "entire_graph_conservative",
        "source_ids": [],
        "sources": [],
    }
    source_records: dict[str, dict] = {}

    def record_graph_dependencies() -> None:
        """Retain initial and incrementally acquired provenance, even on failure."""
        source_records.update(
            {
                json.dumps(source, sort_keys=True): deepcopy(source)
                for item in [*graph["nodes"], *graph.get("edges", [])]
                for source in item.get("sources", [])
            }
        )
        dependencies["sources"] = [source_records[key] for key in sorted(source_records)]
        dependencies["source_ids"] = sorted(
            {
                str(
                    source.get("document_id") or source.get("source_id") or source.get("source_ref")
                )
                for source in dependencies["sources"]
                if source.get("document_id") or source.get("source_id") or source.get("source_ref")
            }
        )
        dependencies["graph_after_sha256"] = digest(graph)

    record_graph_dependencies()
    results: dict[str, Any] = {}
    for step in selected.steps:
        started = time.monotonic()
        trace: dict[str, Any] = {"id": step.id, "operator": step.operator, "status": "started"}
        if step_observer is not None:
            step_observer(deepcopy(trace))
        try:
            resolved = _resolve(step.args, args, results)
            trace["inputs"] = deepcopy(resolved)
            if before_step is not None:
                trace["graph_before_sha256"] = digest(graph)
                if artifact_store is not None:
                    trace["before_materialization_graph_ref"] = artifact_store.put(
                        "function_step_graph", graph
                    )
                before_step(
                    step_id=step.id,
                    operator=step.operator,
                    arguments=deepcopy(resolved),
                    step_outputs=deepcopy(results),
                )
                graph_validation = validate_graph_records(
                    schema, graph["nodes"], graph.get("edges", [])
                )
                if not graph_validation["valid"]:
                    raise ValueError(f"Invalid materialized graph: {graph_validation['errors']}")
                trace["graph_materialized_sha256"] = digest(graph)
            if artifact_store is not None:
                trace["input_graph_ref"] = artifact_store.put("function_step_graph", graph)
            _check_membership(resolved, schema, runtime=True)
            _check_evidence_inputs(resolved, graph)
            invocation = dict(resolved)
            if step.operator in operators.GRAPH_OPERATORS:
                invocation["graph"] = graph
            if step.operator == "extract_runtime_slots":
                invocation["slot_extractor"] = slot_extractor
            if step.operator == "invoke_capability":
                invocation["capability_invoker"] = capability_invoker
            if step.operator == "project_properties":
                annotated = deepcopy(operators.entity_list(invocation["entities"]))
                for entity in annotated:
                    primary_key = schema["entity_types"][entity["type"]]["primary_key"]
                    entity["primary_key"] = {primary_key: entity["properties"][primary_key]}
                invocation["entities"] = annotated
                trace["inputs"]["entities"] = deepcopy(annotated)
            value = operators.OPERATORS[step.operator](**invocation)
            _bounded(value)
            trace.update(status="completed", output=deepcopy(value))
            results[step.id] = value
            if artifact_store is not None:
                trace["graph_after_ref"] = artifact_store.put("function_step_graph", graph)
        except Exception as error:
            record_graph_dependencies()
            trace.update(status="failed", error=f"{type(error).__name__}: {error}")
            if artifact_store is not None:
                trace["graph_after_ref"] = artifact_store.put("function_step_graph", graph)
            trace["duration_seconds"] = round(time.monotonic() - started, 6)
            if artifact_store is not None:
                trace["step_result_ref"] = artifact_store.put("function_step_execution", trace)
            traces.append(trace)
            if step_observer is not None:
                step_observer(deepcopy(trace))
            raise FunctionExecutionError(
                f"{name}/{step.id}: {error}",
                steps=traces,
                dependencies=dependencies,
                capture_id=capture_execution("failed", error=trace["error"]),
            ) from error
        trace["duration_seconds"] = round(time.monotonic() - started, 6)
        if artifact_store is not None:
            trace["step_result_ref"] = artifact_store.put("function_step_execution", trace)
        traces.append(trace)
        if step_observer is not None:
            step_observer(deepcopy(trace))
    record_graph_dependencies()
    try:
        output = _resolve(selected.result, args, results)
        Draft202012Validator(selected.output_schema, format_checker=FormatChecker()).validate(
            output
        )
    except Exception as error:
        raise FunctionExecutionError(
            f"{name} output contract: {error}",
            steps=traces,
            dependencies=dependencies,
            capture_id=capture_execution("failed", error=f"{type(error).__name__}: {error}"),
        ) from error
    result = {"value": output, "steps": traces, "dependencies": dependencies}
    capture_id = capture_execution("completed", value=output)
    if capture_id is not None:
        result["capture_id"] = capture_id
    return result

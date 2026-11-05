"""Candidate-independent semantic behaviors, compilation and evaluation handoff.

Task interpretations are frozen before candidates. The compiler implements a
bounded fragment, while a separately implemented interpreter checks actual
candidate calls on genuine retained graphs. Neither is an independent task
oracle. Source acquisition remains executor-owned through immutable bindings.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Literal

from pydantic import Field

from oak.functions import FunctionSpec, validate_functions
from oak.learning_contracts import SemanticField, TaskIR, TaskProgram
from oak.ontology import parse_schema
from oak.store import canonical
from oak.task_context import StrictContract
from oak.task_semantics import canonical_program, domain_issues, input_schema, parameter_references


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


class AcquisitionTemplate(StrictContract):
    """Authorized source selection, without network execution or source answers."""

    capability_id: str
    native_arguments: dict = Field(default_factory=lambda: {"$arg": "native_arguments"})


class BehaviorBinding(StrictContract):
    """A proposed semantic mapping to one candidate's schema and actual callable."""

    behavior_id: str
    entity_type: str
    field_map: dict[str, str]
    relation_map: dict[str, str] = Field(default_factory=dict)
    function_name: str | None = None
    acquisition: AcquisitionTemplate | None = None


class BehaviorTemplate(StrictContract):
    """A semantic computation or callable getter, not a trajectory prefix."""

    behavior_id: str
    program: TaskProgram | None
    kind: Literal["computation", "projection", "point", "uninterpreted"] = "computation"
    projection_fields: list[str] = Field(default_factory=list)
    selector_fields: list[str] = Field(default_factory=list)
    obligation_ids: list[str]
    mandatory: bool
    group: Literal["retrieval", "subtask", "composition"]
    description: str


class BehaviorBank(StrictContract):
    """Frozen check meanings and denominators, independent of candidate code."""

    version: Literal[1] = 1
    flow: Literal["learning"] = "learning"
    task_ir_sha256: str
    behaviors: list[BehaviorTemplate]
    max_mutants_per_behavior: int = Field(default=8, ge=0, le=8)
    max_mutants_campaign: int = Field(default=64, ge=0, le=64)
    parameter_strata: int = Field(default=2, ge=1, le=2)
    interpretation_status: Literal["proposed"] = "proposed"
    gaps: list[str] = Field(default_factory=list)

    @property
    def bank_id(self) -> str:
        return digest(self.model_dump(mode="json"))


class CompiledEntry(StrictContract):
    """An actual pure callable and the behavior whose meaning it binds."""

    behavior_id: str
    function_name: str
    function_sha256: str
    generated: bool
    required_inputs: dict
    domain_issues: list[str] = Field(default_factory=list)


class CompilationResult(StrictContract):
    """Compilation may report unsupported behaviors without discarding them."""

    functions: list[dict]
    entries: list[CompiledEntry]
    acquisition_bindings: list[dict]
    diagnostics: list[dict]


def behavior_denominators(bank: BehaviorBank | dict) -> dict[str, int]:
    """Frozen behavior/input strata, including deferred or missing bindings."""
    bank = BehaviorBank.model_validate(bank)
    return {item.behavior_id: bank.parameter_strata for item in bank.behaviors}


def _slice(program: TaskProgram, result: str) -> TaskProgram:
    indexed = {operation.id: operation for operation in program.operations}
    keep = set()

    def visit(identity):
        keep.add(identity)
        for parent in indexed[identity].inputs:
            if parent not in keep:
                visit(parent)

    visit(result)
    operations = [item for item in program.operations if item.id in keep]
    field_ids = set().union(*(set(item.fields) for item in operations))
    used = set(program.source_parameters) | set().union(
        *(parameter_references(item.parameters) for item in operations)
    )
    domain = input_schema(program.input_domain)
    domain["properties"] = {
        key: value for key, value in domain.get("properties", {}).items() if key in used
    }
    domain["required"] = [key for key in domain.get("required", []) if key in used]
    return TaskProgram(
        fields=[field for field in program.fields if field.id in field_ids],
        operations=operations,
        result=result,
        input_domain=domain,
        parameter_fields={
            key: value
            for key, value in program.parameter_fields.items()
            if key in used and value in field_ids
        },
        source_parameters=[key for key in program.source_parameters if key in used],
        observation_contract="Return the declared semantic result with identity, multiplicity and provenance.",
        ordering=program.ordering,
    )


def build_behavior_bank(task_ir: TaskIR | dict) -> BehaviorBank:
    """Freeze reusable computation, property and point-access checks before S/F.

    Canonical dependency trees collapse repeated question/trace instances.
    Point access is derived from semantic selector roles, with a primary-key
    fallback when the interpretation does not expose a natural selector.
    """
    task_ir = TaskIR.model_validate(task_ir)
    templates: dict[str, BehaviorTemplate] = {}
    gaps = []

    def add(program, obligation, *, kind="computation", fields=(), selectors=(), group=None):
        key = digest(
            {
                "program": canonical_program(program),
                "kind": kind,
                "projection": list(fields),
                "selectors": list(selectors),
            }
        )
        identity = "b_" + key[:20]
        if identity in templates:
            prior = templates[identity]
            prior.obligation_ids = sorted(set(prior.obligation_ids) | {obligation.obligation_id})
            prior.mandatory |= obligation.mandatory
            return
        semantic_fields = {field.id: field for field in program.fields}
        values = ", ".join(semantic_fields[field].description for field in fields)
        description = (
            f"Retrieve {values} for the supplied record selector, preserving source attribution."
            if kind == "point"
            else f"Retrieve {values} over the supplied scope, preserving record identity and multiplicity."
            if kind == "projection"
            else f"Execute the declared {program.operations[-1].operator} computation over the supplied scope."
        )
        templates[identity] = BehaviorTemplate(
            behavior_id=identity,
            program=program,
            kind=kind,
            projection_fields=list(fields),
            selector_fields=list(selectors),
            obligation_ids=[obligation.obligation_id],
            mandatory=obligation.mandatory,
            group=group or obligation.group,
            description=description,
        )

    for obligation in task_ir.obligations:
        if obligation.program is None:
            gaps.append(f"{obligation.obligation_id}: no executable semantic interpretation")
            identity = "b_" + digest({"uninterpreted": obligation.text})[:20]
            if identity in templates:
                templates[identity].obligation_ids = sorted(
                    set(templates[identity].obligation_ids) | {obligation.obligation_id}
                )
                templates[identity].mandatory |= obligation.mandatory
            else:
                templates[identity] = BehaviorTemplate(
                    behavior_id=identity,
                    program=None,
                    kind="uninterpreted",
                    obligation_ids=[obligation.obligation_id],
                    mandatory=obligation.mandatory,
                    group=obligation.group,
                    description="Uninterpreted public requirement: " + obligation.text,
                )
            continue
        program = obligation.program
        add(_slice(program, program.result), obligation)
        if not obligation.mandatory:
            continue
        for operation in program.operations:
            base = _slice(program, operation.id)
            if operation.id != program.result:
                add(base, obligation, group="subtask")
            if operation.operator != "read":
                continue
            selectors = [
                field.id
                for field in base.fields
                if field.role in {"identity", "selector"} or field.value_type == "date"
            ]
            if not selectors:
                selectors = ["__identity"]
                base = base.model_copy(
                    update={
                        "fields": [
                            *base.fields,
                            SemanticField(
                                id="__identity",
                                description="Record primary key",
                                value_type="unknown",
                                grain=base.fields[0].grain if base.fields else "record",
                                role="identity",
                            ),
                        ]
                    }
                )
            for field in base.fields:
                if field.id == "__identity":
                    continue
                add(base, obligation, kind="projection", fields=[field.id], group="subtask")
                for selector in selectors:
                    add(
                        base,
                        obligation,
                        kind="point",
                        fields=[field.id],
                        selectors=[selector],
                        group="retrieval",
                    )
    return BehaviorBank(
        task_ir_sha256=digest(task_ir.model_dump(mode="json")),
        behaviors=sorted(
            templates.values(), key=lambda item: (not item.mandatory, item.behavior_id)
        ),
        gaps=sorted(set(gaps)),
    )


def field_properties(schema: dict, binding: BehaviorBinding) -> dict:
    """Resolve inherited schema properties and the generated primary-key role."""
    parsed = parse_schema(schema)
    result = {}
    for name in [*sorted(parsed.ancestors(binding.entity_type)), binding.entity_type]:
        result.update(
            {key: value.model_dump() for key, value in parsed.entity_types[name].properties.items()}
        )
    return result


def resolved_field_map(schema: dict, binding: BehaviorBinding) -> dict[str, str]:
    result = dict(binding.field_map)
    result["__identity"] = parse_schema(schema).entity_types[binding.entity_type].primary_key
    return result


def _expression(value):
    if isinstance(value, str) and value.startswith("$input."):
        name = value[7:]
        if "." in name:
            raise ValueError("Nested semantic selectors require a declared scalar parameter")
        return {"$arg": name}
    if isinstance(value, dict):
        return {key: _expression(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expression(item) for item in value]
    return value


def behavior_input_schema(
    template: BehaviorTemplate, schema: dict, binding: BehaviorBinding, capabilities=()
) -> dict:
    """Retain actual acquisition input alternatives and semantic point selectors."""
    if template.program is None:
        raise ValueError("Frozen behavior has no executable interpretation")
    inputs = input_schema(template.program.input_domain)
    inputs.setdefault("required", [])
    fields = {field.id: field for field in template.program.fields}
    actual_fields = field_properties(schema, binding)
    mapping = resolved_field_map(schema, binding)
    for selector in template.selector_fields:
        field = fields[selector]
        typename = (
            actual_fields[mapping[selector]]["type"]
            if field.value_type == "unknown"
            else "string"
            if field.value_type in {"date", "entity"}
            else field.value_type
        )
        if typename == "date_time":
            typename = "string"
        inputs["properties"]["select_" + selector] = {"type": typename}
        inputs["required"].append("select_" + selector)
    if binding.acquisition:
        catalog = {item["id"]: item for item in capabilities}
        if binding.acquisition.capability_id not in catalog:
            raise ValueError("Acquisition binding references an unavailable capability")
        if binding.acquisition.native_arguments == {"$arg": "native_arguments"}:
            inputs["properties"]["native_arguments"] = deepcopy(
                catalog[binding.acquisition.capability_id]["input_schema"]
            )
            inputs["required"].append("native_arguments")
    inputs["required"] = sorted(set(inputs["required"]))
    inputs["additionalProperties"] = False
    return inputs


def compile_behavior(
    template: BehaviorTemplate, schema: dict, binding: BehaviorBinding, *, capabilities=()
) -> dict:
    """Compile frozen task semantics into the registered pure operator language."""
    if template.program is None:
        raise ValueError("Frozen behavior has no executable interpretation")
    properties = field_properties(schema, binding)
    mapping = resolved_field_map(schema, binding)
    declared = [
        mapping.get(field.id) for field in template.program.fields if field.id != "__identity"
    ]
    if len(declared) != len(set(declared)):
        raise ValueError("Distinct semantic fields collapse onto the same candidate property")
    for field in template.program.fields:
        if field.id not in mapping or mapping[field.id] not in properties:
            raise ValueError(f"Unbound semantic field:{field.id}")
        actual = properties[mapping[field.id]]["type"]
        expected = field.value_type
        if expected == "number" and actual not in {"integer", "number"}:
            raise ValueError(f"Incompatible semantic field type:{field.id}")
        if expected == "boolean" and actual != "boolean":
            raise ValueError(f"Incompatible semantic field type:{field.id}")
        if expected in {"string", "date", "entity"} and actual not in {"string", "date_time"}:
            raise ValueError(f"Incompatible semantic field type:{field.id}")
    steps, refs = [], {}
    for index, operation in enumerate(template.program.operations):
        identity = f"s{index}"
        parent = refs[operation.inputs[0]] if operation.inputs else None
        params = operation.parameters
        if operation.operator == "read":
            selectors = params.get("selectors", {})
            if not isinstance(selectors, dict):
                raise ValueError("Read selectors require a semantic-field mapping")
            args = {"entity_types": [binding.entity_type]}
            filters = {mapping[key]: _expression(value) for key, value in selectors.items()}
            if template.kind == "point":
                filters.update(
                    {mapping[key]: {"$arg": "select_" + key} for key in template.selector_fields}
                )
            if filters:
                args["property_filters"] = filters
            operator = "lookup_entities"
        elif operation.operator == "project":
            operator, args = (
                "project_properties",
                {"entities": parent, "property_names": [mapping[key] for key in operation.fields]},
            )
        elif operation.operator == "aggregate":
            request = {"operation": params["operation"]}
            if request["operation"] != "count":
                request["field"] = mapping[operation.fields[0]]
            if "nulls" in params:
                request["nulls"] = params["nulls"]
            operator, args = "aggregate_values", {"items": parent, "request": request}
        elif operation.operator == "filter":
            conditions = params.get("conditions")
            if not isinstance(conditions, list) or not conditions:
                raise ValueError("Filter requires explicit semantic conditions")
            numeric, categorical = [], []
            for condition in conditions:
                item = _expression(
                    {key: value for key, value in condition.items() if key != "field"}
                )
                item["property"] = mapping[condition["field"]]
                (categorical if item.get("operator") in {"in", "not_in"} else numeric).append(item)
            if numeric and categorical:
                steps.append(
                    {
                        "id": identity + "n",
                        "operator": "filter_property_numerical",
                        "args": {"entities": parent, "conditions": numeric},
                    }
                )
                parent = {"$step": identity + "n"}
            operator = "filter_property_categorical" if categorical else "filter_property_numerical"
            args = {"entities": parent, "conditions": categorical or numeric}
        elif operation.operator == "arithmetic":
            operator, args = (
                "arithmetic",
                {
                    "operation": params["operation"],
                    "left": parent,
                    "right": refs[operation.inputs[1]],
                },
            )
        elif operation.operator == "traverse":
            # The current DSL cannot map an entity population to its IDs. Do
            # not guess a single endpoint or flatten the caller's frontier.
            raise ValueError("Semantic traversal requires a supported endpoint-ID mapping")
        else:
            raise ValueError("Unsupported semantic operation")
        steps.append({"id": identity, "operator": operator, "args": args})
        refs[operation.id] = {"$step": identity}
    result = refs[template.program.result]
    if template.projection_fields:
        steps.append(
            {
                "id": "project_result",
                "operator": "project_properties",
                "args": {
                    "entities": result,
                    "property_names": [mapping[key] for key in template.projection_fields],
                },
            }
        )
        result = {"$step": "project_result"}
    function = {
        "name": "behavior_" + template.behavior_id[2:],
        "description": template.description,
        "inputs": behavior_input_schema(template, schema, binding, capabilities),
        "output_schema": {"type": ["number", "null"]}
        if template.program.operations[-1].result_kind == "scalar"
        and not template.projection_fields
        else {"type": "array"},
        "steps": steps,
        "result": result,
    }
    validate_functions([FunctionSpec.model_validate(function)], schema)
    return function


def compile_behavior_bindings(
    bank, schema, bindings, *, functions=(), capabilities=(), max_functions=64
) -> CompilationResult:
    """Return actual functions and frozen acquisition bindings, with explicit gaps."""
    bank = BehaviorBank.model_validate(bank)
    supplied = [BehaviorBinding.model_validate(item) for item in bindings]
    if len({item.behavior_id for item in supplied}) != len(supplied):
        raise ValueError("Duplicate behavior bindings")
    indexed = {item.behavior_id: item for item in supplied}
    templates = {item.behavior_id: item for item in bank.behaviors}
    if set(indexed) - set(templates):
        raise ValueError("Binding references a behavior outside the frozen bank")
    catalog = {function["name"]: deepcopy(function) for function in functions}
    entries, acquisitions, diagnostics = [], [], []
    for template in bank.behaviors:
        binding = indexed.get(template.behavior_id)
        if binding is None:
            diagnostics.append(
                {
                    "behavior_id": template.behavior_id,
                    "status": "unknown",
                    "reason": "missing_binding",
                    "mandatory": template.mandatory,
                }
            )
            continue
        try:
            reference = compile_behavior(template, schema, binding, capabilities=capabilities)
            name = binding.function_name or reference["name"]
            if binding.function_name:
                if name not in catalog:
                    raise ValueError("Bound candidate function is absent")
            else:
                if len(catalog) >= max_functions and name not in catalog:
                    raise ValueError("Callable catalog bound reached; behavior remains unresolved")
                catalog[name] = reference
            function = catalog[name]
            issues = domain_issues(reference["inputs"], function["inputs"])
            entries.append(
                CompiledEntry(
                    behavior_id=template.behavior_id,
                    function_name=name,
                    function_sha256=digest(function),
                    generated=not bool(binding.function_name),
                    required_inputs=reference["inputs"],
                    domain_issues=issues,
                )
            )
            diagnostics.extend(
                {
                    "behavior_id": template.behavior_id,
                    "status": "failed",
                    "reason": issue,
                    "mandatory": template.mandatory,
                }
                for issue in issues
            )
            if binding.acquisition:
                from oak.materialization import freeze_acquisition_binding

                frozen = freeze_acquisition_binding(
                    schema,
                    function,
                    binding.acquisition.capability_id,
                    binding.acquisition.native_arguments,
                    capabilities,
                )
                acquisitions.append(frozen.model_dump(mode="json"))
        except (ValueError, KeyError, TypeError) as error:
            diagnostics.append(
                {
                    "behavior_id": template.behavior_id,
                    "status": "unknown",
                    "reason": str(error),
                    "mandatory": template.mandatory,
                }
            )
    return CompilationResult(
        functions=list(catalog.values()),
        entries=entries,
        acquisition_bindings=acquisitions,
        diagnostics=diagnostics,
    )


def make_behavior_inputs(template, binding, schema, graph, *, receipt_arguments=None):
    """Select up to two genuine parameter strata without fabricating records."""
    from oak.behavior_reference import make_inputs

    return make_inputs(
        BehaviorTemplate.model_validate(template),
        BehaviorBinding.model_validate(binding),
        schema,
        graph,
        receipt_arguments=receipt_arguments or {},
    )


def evaluate_behavior_bank(
    bank,
    schema,
    functions,
    bindings,
    graph,
    *,
    receipt_arguments=None,
    evidence_refs=(),
    behavior_ids=None,
    capabilities=(),
):
    """Evaluate generated semantics and actual candidate behavior, never task truth."""
    from oak.behavior_reference import evaluate_bank

    return evaluate_bank(
        BehaviorBank.model_validate(bank),
        schema,
        functions,
        bindings,
        graph,
        receipt_arguments=receipt_arguments or {},
        evidence_refs=list(evidence_refs),
        behavior_ids=behavior_ids,
        capabilities=capabilities,
    )


def replay_behavior_evaluation(candidate, payload, store):
    """Verifier entry point: load hash-verified inputs and execute actual candidate F."""

    def value(name):
        return candidate[name] if isinstance(candidate, dict) else getattr(candidate, name)

    capabilities_ref = payload.get("capabilities_ref", payload.get("capabilities_id"))
    capabilities = store.get(capabilities_ref) if capabilities_ref else []
    if isinstance(capabilities, dict):
        capabilities = capabilities.get("tools", [])
    receipt_arguments = {}
    for receipt_id in payload.get("receipt_ids", []):
        receipt = store.get(receipt_id)
        if receipt.get("status") == "completed" and isinstance(receipt.get("args"), dict):
            capability = receipt.get("capability_id", receipt.get("capability"))
            if capability:
                variants = receipt_arguments.setdefault(capability, [])
                if receipt["args"] not in variants:
                    variants.append(receipt["args"])
    return evaluate_behavior_bank(
        store.get(payload["bank_id"]),
        value("schema"),
        value("functions"),
        store.get(payload["bindings_id"]),
        store.get(payload["graph_id"]),
        receipt_arguments=receipt_arguments,
        evidence_refs=[
            payload["bank_id"],
            payload["bindings_id"],
            payload["graph_id"],
            *payload.get("evidence_refs", []),
            *payload.get("receipt_ids", []),
        ],
        behavior_ids=payload.get("behavior_ids"),
        capabilities=capabilities,
    )

"""Finite semantic checks and canonical forms independent of candidate S/F.

These controls reject type/grain contradictions. They cannot establish that a
model's interpretation matches natural language or that a source is complete.
"""

from __future__ import annotations

from copy import deepcopy

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


def input_schema(domain: dict) -> dict:
    """Normalize the supported task input notation to a closed object schema."""
    if domain.get("type") == "object":
        result = deepcopy(domain)
    else:
        result = {
            "type": "object",
            "properties": {
                key: {"type": value} if isinstance(value, str) else deepcopy(value)
                for key, value in domain.items()
            },
            "required": sorted(domain),
            "additionalProperties": False,
        }
    try:
        Draft202012Validator.check_schema(result)
    except SchemaError as error:
        # Interpretation output is model-authored data. Keep malformed input
        # domains inside Pydantic's validation boundary so construction can
        # persist the actual defect and use its bounded requirement repair.
        raise ValueError(f"Invalid task input domain: {error.message}") from error
    if not isinstance(result.get("properties", {}), dict):
        raise ValueError("Task input domain requires named properties")
    if not set(result.get("required", [])).issubset(result.get("properties", {})):
        raise ValueError("Task input domain requires an undeclared parameter")
    return result


def parameter_references(value) -> set[str]:
    """Read explicit input references, without interpreting arbitrary strings."""
    if isinstance(value, str) and value.startswith("$input."):
        return {value[7:].split(".", 1)[0]}
    if isinstance(value, dict):
        if set(value) == {"$arg"}:
            return {value["$arg"]}
        if set(value) == {"$arg_path"}:
            return {value["$arg_path"][0]}
        return set().union(*(parameter_references(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(parameter_references(item) for item in value))
    return set()


def validate_task_semantics(program) -> None:
    """Check the supported operator fragment, including numeric units/grain.

    Underspecified parameter details remain uncompiled rather than guessed.
    This preserves honest interpretation gaps while rejecting contradictions.
    """
    domain = input_schema(program.input_domain)
    declared = set(domain.get("properties", {}))
    fields = {field.id: field for field in program.fields}
    states = {}
    for operation in program.operations:
        if not parameter_references(operation.parameters).issubset(declared):
            raise ValueError("Task operation references an undeclared input parameter")
        parents = [states[parent] for parent in operation.inputs]
        selected = [fields[name] for name in operation.fields]
        if operation.operator == "read":
            if parents or operation.result_kind != "records":
                raise ValueError("Read has no program inputs and returns records")
            if len({field.grain for field in selected}) > 1:
                raise ValueError("Read mixes entity grains without an explicit traversal")
            selectors = operation.parameters.get("selectors", {})
            if not isinstance(selectors, dict) or not set(selectors).issubset(operation.fields):
                raise ValueError("Read selector references an unavailable semantic field")
        elif operation.operator in {"filter", "project", "aggregate"}:
            if len(parents) != 1 or parents[0]["kind"] not in {"records", "path"}:
                raise ValueError("Record operators require one record or path input")
            if not set(operation.fields).issubset(parents[0]["fields"]):
                raise ValueError("Task operator reads a field absent from its input")
            if operation.operator != "aggregate" and operation.result_kind != "records":
                raise ValueError("Filter and projection return records")
            if operation.operator == "filter":
                for condition in operation.parameters.get("conditions", []):
                    if condition.get("field") not in operation.fields:
                        raise ValueError("Filter predicate references an undeclared semantic field")
                    if condition.get("operator") not in {
                        "in",
                        "not_in",
                        "==",
                        "!=",
                        "<",
                        "<=",
                        ">",
                        ">=",
                        "between",
                    }:
                        raise ValueError("Unsupported semantic predicate")
                    field = fields[condition["field"]]
                    if condition["operator"] not in {"in", "not_in"} and field.value_type not in {
                        "number",
                        "unknown",
                    }:
                        raise ValueError("Numeric predicate requires a numeric semantic field")
        if operation.operator == "aggregate":
            name = operation.parameters.get("operation")
            if name not in {"count", "min", "max", "sum", "mean", "average"}:
                raise ValueError("Unsupported semantic aggregate")
            if operation.result_kind != "scalar":
                raise ValueError("Aggregation returns a scalar")
            if name != "count" and (
                len(selected) != 1 or selected[0].value_type not in {"number", "unknown"}
            ):
                raise ValueError("Numeric aggregation requires exactly one numeric field")
        if operation.operator == "arithmetic":
            if operation.result_kind != "scalar":
                raise ValueError("Arithmetic returns a scalar")
            if len(parents) != 2 or any(parent["kind"] != "scalar" for parent in parents):
                raise ValueError("Arithmetic requires two scalar computations")
            name = operation.parameters.get("operation")
            if name not in {"add", "subtract", "multiply", "divide"}:
                raise ValueError("Unsupported semantic arithmetic")
            if name in {"add", "subtract"} and parents[0]["unit"] != parents[1]["unit"]:
                raise ValueError("Add/subtract requires compatible units")
            if parents[0]["grain"] != parents[1]["grain"]:
                raise ValueError("Arithmetic mixes incompatible entity grains")
        if operation.operator == "traverse":
            if len(parents) != 1 or parents[0]["kind"] not in {"records", "path"}:
                raise ValueError("Traversal requires an endpoint population")
            hops = operation.parameters.get("max_hops")
            if hops is not None and (type(hops) is not int or not 0 <= hops <= 8):
                raise ValueError("Traversal max_hops must be between zero and eight")
            if operation.parameters.get("direction", "outgoing") not in {
                "outgoing",
                "incoming",
                "both",
            }:
                raise ValueError("Invalid semantic traversal direction")
        available = set(operation.fields)
        if operation.operator == "filter":
            available = parents[0]["fields"]
        result_unit = selected[0].unit if len(selected) == 1 else None
        if operation.operator == "aggregate" and operation.parameters.get("operation") == "count":
            result_unit = "count"
        if operation.operator == "arithmetic":
            name = operation.parameters["operation"]
            if name in {"add", "subtract"}:
                result_unit = parents[0]["unit"]
            elif name == "multiply":
                result_unit = (
                    "product",
                    tuple(sorted((str(parents[0]["unit"]), str(parents[1]["unit"])))),
                )
            else:
                result_unit = (
                    None
                    if parents[0]["unit"] == parents[1]["unit"]
                    else ("ratio", parents[0]["unit"], parents[1]["unit"])
                )
        states[operation.id] = {
            "kind": operation.result_kind,
            "fields": available,
            "unit": result_unit,
            "grain": selected[0].grain if selected else (parents[0]["grain"] if parents else None),
        }
    if not set(program.parameter_fields).issubset(declared):
        raise ValueError("parameter_fields references an undeclared input parameter")
    if not set(program.source_parameters).issubset(declared):
        raise ValueError("source_parameters references an undeclared input parameter")


def canonical_program(program) -> dict:
    """Canonicalize semantic dependency trees, ignoring trace order and step IDs."""
    indexed = {operation.id: operation for operation in program.operations}

    def expand(identity):
        operation = indexed[identity]
        return {
            "operator": operation.operator,
            "inputs": [expand(parent) for parent in operation.inputs],
            "fields": sorted(operation.fields),
            "result_kind": operation.result_kind,
            "parameters": operation.parameters,
        }

    return {
        "computation": expand(program.result),
        "fields": sorted(
            [
                field.model_dump(exclude={"description", "source_capability_ids"})
                for field in program.fields
            ],
            key=lambda field: field["id"],
        ),
        "inputs": input_schema(program.input_domain),
        "parameter_fields": program.parameter_fields,
        "source_parameters": sorted(program.source_parameters),
        "ordering": program.ordering,
    }


def domain_issues(required: dict, provided: dict) -> list[str]:
    """Check a bounded subset of JSON Schema input-domain containment.

    Unsupported restrictions are reported, never guessed to be equivalent.
    This is a contract audit and does not block unrelated agent execution.
    """
    issues = []
    for name, expected in required.get("properties", {}).items():
        actual = provided.get("properties", {}).get(name)
        if actual is None:
            issues.append(f"missing input:{name}")
            continue
        expected_types = expected.get("type")
        actual_types = actual.get("type")
        expected_types = set(
            expected_types if isinstance(expected_types, list) else [expected_types]
        )
        actual_types = set(actual_types if isinstance(actual_types, list) else [actual_types])
        if "number" in actual_types:
            actual_types.add("integer")
        if (
            None not in expected_types
            and None not in actual_types
            and not expected_types <= actual_types
        ):
            issues.append(f"narrowed type:{name}")
        if "enum" in actual and (
            "enum" not in expected
            or not set(map(repr, expected["enum"])) <= set(map(repr, actual["enum"]))
        ):
            issues.append(f"narrowed enum:{name}")
        if "const" in actual and expected.get("const") != actual["const"]:
            issues.append(f"example-specific constant domain:{name}")
        for bound, direction in (
            ("minimum", 1),
            ("maximum", -1),
            ("minLength", 1),
            ("maxLength", -1),
        ):
            if bound in actual and (
                bound not in expected or direction * actual[bound] > direction * expected[bound]
            ):
                issues.append(f"narrowed {bound}:{name}")
        if actual.get("type") == "object" and expected.get("type") == "object":
            issues.extend(f"{name}.{issue}" for issue in domain_issues(expected, actual))
        unknown = set(actual) - {
            "type",
            "enum",
            "const",
            "minimum",
            "maximum",
            "minLength",
            "maxLength",
            "description",
            "title",
            "default",
            "examples",
            "properties",
            "required",
            "additionalProperties",
            "items",
            "format",
            "anyOf",
            "oneOf",
        }
        if unknown:
            issues.append(f"unproved domain restrictions:{name}:{','.join(sorted(unknown))}")
        for union in ("anyOf", "oneOf"):
            if union in actual and actual.get(union) != expected.get(union):
                issues.append(f"unproved input alternatives:{name}")
    if set(provided.get("required", [])) - set(required.get("required", [])):
        issues.append("new required inputs narrow the callable domain")
    return sorted(set(issues))

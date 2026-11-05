"""Generated semantic checks implemented independently of FunctionSpec compilation.

All records come from the supplied genuine graph. Program mutations change code,
not benchmark data. Checks establish finite generated-semantic agreement only;
they never certify source completeness or independent task correctness.
"""

from __future__ import annotations

import operator as python_operator
from collections import Counter
from copy import deepcopy
from decimal import Decimal

from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaValidationError

from oak.functions import FunctionSpec, execute_function, validate_functions
from oak.store import canonical
from oak.task_semantics import domain_issues, input_schema, parameter_references


def _resolve(value, arguments):
    if isinstance(value, str) and value.startswith("$input."):
        current = arguments
        for key in value[7:].split("."):
            current = current[key]
        return current
    if isinstance(value, dict):
        if set(value) == {"$arg"}:
            return arguments[value["$arg"]]
        if set(value) == {"$arg_path"}:
            current = arguments
            for key in value["$arg_path"]:
                current = current[key]
            return current
        return {key: _resolve(item, arguments) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, arguments) for item in value]
    return value


def _project(records, names, schema):
    return [
        {
            "__entity_id": row["id"],
            "__entity_type": row["type"],
            "__sources": deepcopy(row.get("sources", [])),
            "__primary_key": {
                schema["entity_types"][row["type"]]["primary_key"]: row["properties"][
                    schema["entity_types"][row["type"]]["primary_key"]
                ]
            },
            **{name: deepcopy(row["properties"].get(name)) for name in names},
        }
        for row in records
    ]


def interpret_behavior(template, binding, schema, graph, arguments):
    """Interpret frozen TaskProgram directly, without executing compiled F."""
    from oak.behavior import resolved_field_map

    if template.program is None:
        raise ValueError("No executable interpretation of this frozen requirement")
    mapping = resolved_field_map(schema, binding)
    results = {}
    reads = []
    for operation in template.program.operations:
        parents = [results[name] for name in operation.inputs]
        params = _resolve(operation.parameters, arguments)
        if operation.operator == "read":
            filters = {mapping[name]: value for name, value in params.get("selectors", {}).items()}
            if template.kind == "point":
                filters.update(
                    {
                        mapping[name]: arguments["select_" + name]
                        for name in template.selector_fields
                    }
                )
            value = [
                deepcopy(row)
                for row in graph.get("nodes", [])
                if row["type"] == binding.entity_type
                and all(
                    name in row["properties"] and row["properties"][name] == expected
                    for name, expected in filters.items()
                )
            ]
            value.sort(key=lambda row: row["id"])
            reads.extend(row["id"] for row in value)
        elif operation.operator == "project":
            value = _project(parents[0], [mapping[name] for name in operation.fields], schema)
        elif operation.operator == "filter":
            conditions = params.get("conditions")
            if not conditions:
                raise ValueError("Explicit filter semantics are absent")

            def matches(row, conditions=conditions):
                for condition in conditions:
                    observed = row["properties"].get(mapping[condition["field"]])
                    if observed is None:
                        return False
                    comparator = condition["operator"]
                    if comparator in {"in", "not_in"}:
                        included = observed in condition["values"]
                        if included != (comparator == "in"):
                            return False
                    else:
                        if isinstance(observed, bool) or not isinstance(observed, int | float):
                            raise ValueError("Reference numeric predicate received a non-number")
                        expected = condition.get("value")
                        valid = {
                            "==": python_operator.eq,
                            "!=": python_operator.ne,
                            "<": python_operator.lt,
                            "<=": python_operator.le,
                            ">": python_operator.gt,
                            ">=": python_operator.ge,
                        }
                        if comparator == "between":
                            accepted = condition["minimum"] <= observed <= condition["maximum"]
                        else:
                            accepted = comparator in valid and valid[comparator](observed, expected)
                        if not accepted:
                            return False
                return True

            value = [row for row in parents[0] if matches(row)]
        elif operation.operator == "aggregate":
            rows, name = parents[0], params["operation"]
            if name == "count":
                value = len(rows)
            else:
                key = mapping[operation.fields[0]]
                values = [(row["properties"] if "properties" in row else row)[key] for row in rows]
                if params.get("nulls") == "skip":
                    values = [item for item in values if item is not None]
                if any(
                    isinstance(item, bool) or not isinstance(item, int | float) for item in values
                ):
                    raise ValueError(
                        "Reference aggregation encountered a missing or nonnumeric value"
                    )
                numbers = [Decimal(str(item)) for item in values]
                if name == "sum":
                    number = sum(numbers, Decimal(0))
                elif not numbers:
                    number = None
                elif name == "min":
                    number = min(numbers)
                elif name == "max":
                    number = max(numbers)
                elif name in {"mean", "average"}:
                    number = sum(numbers) / len(numbers)
                else:
                    raise ValueError("Unsupported reference aggregation")
                value = (
                    None
                    if number is None
                    else int(number)
                    if number == number.to_integral_value()
                    else float(number)
                )
        elif operation.operator == "arithmetic":
            left, right = (Decimal(str(item)) for item in parents)
            operations = {
                "add": python_operator.add,
                "subtract": python_operator.sub,
                "multiply": python_operator.mul,
                "divide": python_operator.truediv,
            }
            number = operations[params["operation"]](left, right)
            value = int(number) if number == number.to_integral_value() else float(number)
        else:
            raise ValueError("Semantic operation lacks a supported reference interpreter")
        results[operation.id] = value
    value = results[template.program.result]
    if template.projection_fields:
        value = _project(value, [mapping[name] for name in template.projection_fields], schema)
    return {"value": value, "record_ids": sorted(set(reads)), "intermediate_values": results}


def _values(graph, entity_type, property_name):
    unique = {}
    for row in graph.get("nodes", []):
        if row["type"] == entity_type and property_name in row["properties"]:
            value = row["properties"][property_name]
            if value is not None:
                unique[canonical(value)] = value
    return [unique[key] for key in sorted(unique)]


def inverse_acquisition_inputs(template, actual):
    """Recover arguments through explicit source templates, never guessed names."""
    captured = {}

    def assign(path, value):
        if not path or any(not isinstance(key, str) for key in path):
            raise ValueError("Inverse source binding needs named object fields")
        cursor = captured
        for key in path[:-1]:
            cursor = cursor.setdefault(key, {})
            if not isinstance(cursor, dict):
                raise ValueError("Conflicting source argument bindings")
        key = path[-1]
        if key in cursor and canonical(cursor[key]) != canonical(value):
            raise ValueError("Conflicting source argument bindings")
        cursor[key] = deepcopy(value)

    def match(pattern, observed):
        if isinstance(pattern, dict):
            if set(pattern) == {"$arg"}:
                assign([pattern["$arg"]], observed)
            elif set(pattern) == {"$arg_path"}:
                assign(pattern["$arg_path"], observed)
            else:
                if not isinstance(observed, dict):
                    raise ValueError("Source receipt does not match the declared argument template")
                for key, value in pattern.items():
                    if key not in observed:
                        raise ValueError("Source receipt lacks a bound argument")
                    match(value, observed[key])
        elif isinstance(pattern, list):
            if not isinstance(observed, list) or len(pattern) != len(observed):
                raise ValueError("Source array does not match its binding")
            for left, right in zip(pattern, observed, strict=True):
                match(left, right)
        elif canonical(pattern) != canonical(observed):
            raise ValueError("Actual receipt does not satisfy the bound source literal")

    match(template, actual)
    return captured


def make_inputs(template, binding, schema, graph, *, receipt_arguments):
    """Use distinct actual record values, never fabricated task answers."""
    from oak.behavior import resolved_field_map

    if template.program is None:
        return []
    mapping = resolved_field_map(schema, binding)
    domain = input_schema(template.program.input_domain)
    parameter_fields = dict(template.program.parameter_fields)
    for operation in template.program.operations:
        for field, expression in operation.parameters.get("selectors", {}).items():
            for name in parameter_references(expression):
                parameter_fields.setdefault(name, field)
        for condition in operation.parameters.get("conditions", []):
            for name in parameter_references(condition):
                parameter_fields.setdefault(name, condition["field"])
    choices, captures = {}, []
    if binding.acquisition:
        actual = receipt_arguments.get(binding.acquisition.capability_id)
        if actual is None:
            return []
        for observed in sorted(actual, key=canonical) if isinstance(actual, list) else [actual]:
            try:
                captured = inverse_acquisition_inputs(
                    binding.acquisition.native_arguments, observed
                )
                if all(
                    key not in domain.get("properties", {})
                    or Draft202012Validator(domain["properties"][key]).is_valid(value)
                    for key, value in captured.items()
                ):
                    captures.append(captured)
            except (ValueError, KeyError, TypeError):
                continue
        if not captures:
            return []
    for parameter, specification in domain.get("properties", {}).items():
        if captures and all(parameter in captured for captured in captures):
            choices[parameter] = [deepcopy(captured[parameter]) for captured in captures]
        elif parameter in parameter_fields and parameter_fields[parameter] in mapping:
            values = _values(graph, binding.entity_type, mapping[parameter_fields[parameter]])
            choices[parameter] = [
                value for value in values if Draft202012Validator(specification).is_valid(value)
            ]
        elif parameter in domain.get("required", []):
            return []
    for selector in template.selector_fields:
        choices["select_" + selector] = _values(graph, binding.entity_type, mapping[selector])
    if binding.acquisition:
        for parameter in parameter_references(binding.acquisition.native_arguments):
            if captures and all(parameter in captured for captured in captures):
                choices[parameter] = [deepcopy(captured[parameter]) for captured in captures]
            elif parameter not in choices:
                return []
    if any(not values for values in choices.values()):
        return []
    result = []
    for index in (0, -1):
        arguments = {name: deepcopy(values[index]) for name, values in choices.items()}
        if arguments not in result:
            result.append(arguments)
    return result


def _equivalent(left, right, *, ordered):
    if isinstance(left, list) and isinstance(right, list) and not ordered:
        return Counter(canonical(item) for item in left) == Counter(
            canonical(item) for item in right
        )
    return canonical(left) == canonical(right)


def _arg_flow(function, *, return_steps=False):
    """Only arguments that can reach the returned value count as computation."""
    indexed = {step["id"]: step for step in function["steps"]}
    seen = set()

    def visit(value):
        if isinstance(value, dict):
            if set(value) in ({"$step"}, {"$path"}):
                identity = value.get("$step") or value["$path"][0]
                if identity not in seen:
                    seen.add(identity)
                    return visit(indexed[identity]["args"])
                return set()
            return parameter_references(value) | set().union(
                *(visit(item) for item in value.values())
            )
        if isinstance(value, list):
            return set().union(*(visit(item) for item in value))
        return set()

    arguments = visit(function["result"])
    return seen if return_steps else arguments


def generated_mutants(function, schema, arguments, expected, *, limit=8):
    """Yield valid deterministic code defects, leaving genuine graph bytes intact."""
    if limit <= 0:
        return
    variants = []
    for index, step in enumerate(function["steps"]):
        if step["operator"] == "aggregate_values":
            operation = step["args"]["request"]["operation"]
            replacement = {
                "min": "max",
                "max": "min",
                "sum": "mean",
                "mean": "sum",
                "average": "sum",
            }.get(operation)
            if replacement:
                changed = deepcopy(function)
                changed["steps"][index]["args"]["request"]["operation"] = replacement
                variants.append(("wrong_aggregate", changed))
        if step["operator"] == "lookup_entities":
            changed = deepcopy(function)
            changed["steps"][index]["args"]["top_k"] = 1
            variants.append(("truncated_population", changed))
            for field, expression in step["args"].get("property_filters", {}).items():
                if (
                    isinstance(expression, dict)
                    and set(expression) == {"$arg"}
                    and expression["$arg"] in arguments
                ):
                    changed = deepcopy(function)
                    changed["steps"][index]["args"]["property_filters"][field] = deepcopy(
                        arguments[expression["$arg"]]
                    )
                    variants.append(("baked_in_example_parameter", changed))
        if step["operator"] == "project_properties" and step["args"]["property_names"]:
            changed = deepcopy(function)
            changed["steps"][index]["args"]["property_names"] = []
            variants.append(("missing_projected_field", changed))
        if step["operator"] in {"filter_property_numerical", "filter_property_categorical"}:
            changed = deepcopy(function)
            changed["steps"][index]["args"]["conditions"] = []
            variants.append(("dropped_predicate", changed))
    # This is a deliberately faulty program literal drawn from an actual
    # reference computation, not a fabricated receipt or substituted output.
    if isinstance(expected, int | float | str):
        changed = deepcopy(function)
        changed["result"] = deepcopy(expected)
        variants.append(("constant_example_answer", changed))
    priority = {
        "wrong_aggregate": 0,
        "missing_projected_field": 1,
        "dropped_predicate": 2,
        "baked_in_example_parameter": 3,
        "truncated_population": 4,
        "constant_example_answer": 5,
    }
    variants.sort(key=lambda item: priority[item[0]])
    seen = set()
    for defect, changed in variants:
        key = canonical(changed)
        if key in seen:
            continue
        seen.add(key)
        try:
            validate_functions([FunctionSpec.model_validate(changed)], schema)
        except (ValueError, TypeError):
            continue
        yield defect, changed
        limit -= 1
        if limit == 0:
            break


def evaluate_bank(
    bank,
    schema,
    functions,
    bindings,
    graph,
    *,
    receipt_arguments,
    evidence_refs,
    behavior_ids,
    capabilities=(),
):
    """Score fixed behavior/input strata, not function, trace or check counts."""
    from oak.behavior import BehaviorBinding, behavior_denominators, compile_behavior, digest

    parsed_bindings = [BehaviorBinding.model_validate(item) for item in bindings]
    binding_map = {binding.behavior_id: binding for binding in parsed_bindings}
    if len(binding_map) != len(parsed_bindings):
        raise ValueError("Duplicate behavior bindings")
    catalog = {function["name"]: function for function in functions}
    checks, penalties, groups = [], [], {}
    # Allocate from the frozen bank, not candidate successes or replay subset.
    # Missing bindings cannot free mutation budget for other behaviors.
    quotas = {item.behavior_id: 0 for item in bank.behaviors}
    remaining_budget = bank.max_mutants_campaign
    for _ in range(bank.max_mutants_per_behavior):
        for item in bank.behaviors:
            if remaining_budget and item.program is not None:
                quotas[item.behavior_id] += 1
                remaining_budget -= 1
    mutants_executed = 0
    denominators = behavior_denominators(bank)
    for template in bank.behaviors:
        if behavior_ids is not None and template.behavior_id not in behavior_ids:
            continue
        total = denominators[template.behavior_id]
        outcome = {
            "behavior_id": template.behavior_id,
            "obligation_ids": template.obligation_ids,
            "group": template.group,
            "mandatory": template.mandatory,
            "status": "unknown",
            "strata": [],
            "total_strata": total,
            "passed_strata": 0,
            "mutations": [],
            "independent": False,
            "evidence_refs": evidence_refs,
        }
        binding = binding_map.get(template.behavior_id)
        try:
            if template.program is None:
                raise ValueError(
                    "No executable interpretation; requirement remains in the frozen denominator"
                )
            if binding is None:
                raise ValueError("No callable binding for the frozen behavior")
            name = binding.function_name or "behavior_" + template.behavior_id[2:]
            function = catalog.get(name)
            if function is None:
                raise ValueError("The bound callable is absent")
            if any(
                step["operator"] in {"invoke_capability", "extract_runtime_slots"}
                for step in function["steps"]
            ):
                raise ValueError("Behavior checks execute only pure helpers, never source dispatch")
            # No acquisition is performed here. Native arguments are part of
            # the input contract and are supplied from an actual receipt.
            bare = binding if capabilities else binding.model_copy(update={"acquisition": None})
            reference_function = compile_behavior(template, schema, bare, capabilities=capabilities)
            required = deepcopy(reference_function["inputs"])
            if (
                not capabilities
                and binding.acquisition
                and "native_arguments" in function["inputs"].get("properties", {})
            ):
                required["properties"]["native_arguments"] = deepcopy(
                    function["inputs"]["properties"]["native_arguments"]
                )
                required["required"].append("native_arguments")
            issues = domain_issues(required, function["inputs"])
            outcome["native_domain_status"] = (
                "not_applicable"
                if binding.acquisition is None
                else "unknown"
                if not capabilities
                else "failed"
                if issues
                else "passed"
            )
            required_flow = parameter_references(
                [operation.parameters for operation in template.program.operations]
            ) | {"select_" + field for field in template.selector_fields}
            actual_flow = _arg_flow(function)
            missing_flow = sorted(required_flow - actual_flow)
            issues.extend(f"parameter does not reach result:{name}" for name in missing_flow)
            from oak.operators import GRAPH_OPERATORS

            live_steps = _arg_flow(function, return_steps=True)
            if not any(
                step["id"] in live_steps and step["operator"] in GRAPH_OPERATORS
                for step in function["steps"]
            ):
                issues.append("result does not depend on graph evidence")
            for issue in issues:
                penalties.append({"behavior_id": template.behavior_id, "reason": issue})
            inputs = make_inputs(
                template, binding, schema, graph, receipt_arguments=receipt_arguments
            )
            cases = [(args, graph, "retained_graph") for args in inputs[:total]]
            if len(cases) == 1:
                # This is a labelled view of genuine retained records, not a
                # claimed complete source response. It tests the pure helper's
                # behavior on a second valid graph input without acquisition.
                matching = [
                    row for row in graph.get("nodes", []) if row["type"] == binding.entity_type
                ]
                if len(matching) > 1:
                    original_value = interpret_behavior(
                        template, binding, schema, graph, inputs[0]
                    )["value"]
                    for retained in sorted(matching, key=lambda row: row["id"])[:8]:
                        view = deepcopy(graph)
                        view["nodes"] = [
                            row
                            for row in view["nodes"]
                            if row["type"] != binding.entity_type or row["id"] == retained["id"]
                        ]
                        ids = {row["id"] for row in view["nodes"]}
                        view["edges"] = [
                            edge
                            for edge in view.get("edges", [])
                            if edge["source"] in ids and edge["target"] in ids
                        ]
                        slice_value = interpret_behavior(
                            template, binding, schema, view, inputs[0]
                        )["value"]
                        if not _equivalent(
                            original_value,
                            slice_value,
                            ordered=template.program.ordering == "ordered",
                        ):
                            break
                    cases.append((inputs[0], view, "retained_record_slice"))
            anchors = []
            for index, (args, supplied_graph, variant) in enumerate(cases):
                anchor = interpret_behavior(template, binding, schema, supplied_graph, args)
                if not anchor["record_ids"]:
                    outcome["strata"].append(
                        {
                            "index": index,
                            "status": "unknown",
                            "reason": "No genuine source witness",
                            "args": args,
                        }
                    )
                    continue
                if template.projection_fields and any(
                    row.get(field) is None
                    for row in anchor["value"]
                    for field in [
                        binding.field_map.get(name, name) for name in template.projection_fields
                    ]
                ):
                    outcome["strata"].append(
                        {
                            "index": index,
                            "status": "unknown",
                            "reason": "Requested source value is missing",
                            "args": args,
                        }
                    )
                    continue
                anchors.append((args, anchor, supplied_graph))
                try:
                    execution = execute_function(
                        supplied_graph, functions, name, args, schema=schema
                    )
                    passed = _equivalent(
                        execution["value"],
                        anchor["value"],
                        ordered=template.program.ordering == "ordered",
                    )
                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    ArithmeticError,
                    SchemaValidationError,
                ) as error:
                    execution, passed = {"error": str(error)}, False
                outcome["strata"].append(
                    {
                        "index": index,
                        "status": "passed" if passed else "failed",
                        "args": args,
                        "reference_value": anchor["value"],
                        "execution": execution,
                        "source_entity_ids": anchor["record_ids"],
                        "evidence_variant": variant,
                        "graph_sha256": digest(supplied_graph),
                    }
                )
            # Mutation quality is measured against the frozen compiled
            # reference, not used to select an easier check for a candidate.
            if anchors and quotas[template.behavior_id]:
                for defect, mutant in generated_mutants(
                    reference_function,
                    schema,
                    anchors[0][0],
                    anchors[0][1]["value"],
                    limit=quotas[template.behavior_id],
                ):
                    mutants_executed += 1
                    discriminated, error = False, None
                    for args, anchor, supplied_graph in anchors:
                        pure_args = {
                            key: value
                            for key, value in args.items()
                            if key in mutant["inputs"].get("properties", {})
                        }
                        try:
                            actual = execute_function(
                                supplied_graph, [mutant], mutant["name"], pure_args, schema=schema
                            )["value"]
                            discriminated |= not _equivalent(
                                actual,
                                anchor["value"],
                                ordered=template.program.ordering == "ordered",
                            )
                        except (ValueError, TypeError, KeyError, SchemaValidationError) as failure:
                            # A valid program's observable typed failure is
                            # also a discriminated mutation on this graph.
                            discriminated, error = True, str(failure)
                    outcome["mutations"].append(
                        {
                            "defect": defect,
                            "program_sha256": digest(mutant),
                            "detected": discriminated,
                            "error": error,
                        }
                    )
            nonvacuous = any(item["detected"] for item in outcome["mutations"])
            failures = any(item["status"] == "failed" for item in outcome["strata"])
            outcome["status"] = (
                "failed"
                if failures or issues
                else "passed"
                if nonvacuous
                and len(outcome["strata"]) == total
                and all(item["status"] == "passed" for item in outcome["strata"])
                else "unknown"
            )
            outcome["passed_strata"] = (
                sum(item["status"] == "passed" for item in outcome["strata"])
                if nonvacuous and not issues
                else 0
            )
            outcome["mutation_sensitive"] = nonvacuous
            outcome["function_name"] = name
            outcome["function_sha256"] = digest(function)
            outcome["reference_basis"] = (
                "Frozen generated task semantics on the same genuine materialization; field mapping remains proposed"
            )
        except (ValueError, TypeError, KeyError, ArithmeticError, SchemaValidationError) as error:
            outcome["reason"] = str(error)
        checks.append(outcome)
        if template.mandatory:
            group = groups.setdefault(
                template.group, {"total": 0, "passed": 0, "failed": 0, "unknown": 0}
            )
            group["total"] += total
            group["passed"] += outcome["passed_strata"]
            group["failed"] += sum(item["status"] == "failed" for item in outcome["strata"])
            group["unknown"] += (
                total
                - outcome["passed_strata"]
                - sum(item["status"] == "failed" for item in outcome["strata"])
            )
    return {
        "version": 1,
        "flow": "learning",
        "independent": False,
        "bank_id": bank.bank_id,
        "schema_sha256": digest(schema),
        "graph_sha256": digest(graph),
        "status": "failed"
        if any(item["status"] == "failed" for item in checks)
        else "passed"
        if checks and all(item["status"] == "passed" for item in checks)
        else "unknown",
        "summary": "Generated behavior agreement on genuine retained evidence; independent task truth is not checked",
        "evaluator": "semantic_behavior_v1",
        "evaluator_version": 1,
        "checks": checks,
        "behavior_coverage_by_group": groups,
        "penalties": penalties,
        "counterexamples": [
            {
                "behavior_id": item["behavior_id"],
                "boundary": "function_computation",
                "summary": "Candidate violates a frozen generated behavior",
                "strata": [stratum for stratum in item["strata"] if stratum["status"] == "failed"],
            }
            for item in checks
            if item["status"] == "failed"
        ],
        "mutants_executed": mutants_executed,
        "mutation_quotas": quotas,
        "unresolved_behavior_ids": [
            item["behavior_id"]
            for item in checks
            if item["mandatory"] and item["status"] != "passed"
        ],
        "limitations": [
            "Generated task semantics and schema mappings remain proposed",
            "No independent source completeness or task correctness claim",
        ],
    }

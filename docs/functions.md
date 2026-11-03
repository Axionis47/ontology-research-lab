# Generic operators and typed function execution

`oak.operators` implements the paper's nine named operator surfaces. `oak.functions` executes a bounded catalog of typed operator compositions. The paper does not provide condition/result classes or a function realization grammar, so the contracts here resolve GAP-03 and GAP-08 as explicit engineering choices.

These modules contain no benchmark names, reference answers, provider fallback, or generated Python execution. The interpreter accepts function definitions as validated data. It operates on the actual supplied graph and preserves real call inputs, outputs, failures, durations, and dependency evidence.

## Function contract

`FunctionSpec` contains `name`, `description`, an input JSON Schema object, `output_schema`, `steps`, and `result`. Each step contains a unique `id`, a registered `operator`, and its `args`. The function input schema must set `additionalProperties: false`. The interpreter checks input/output types and formats.

Supported references:

| Expression | Meaning |
| --- | --- |
| `{"$arg": "name"}` | A declared function input supplied by the caller |
| `{"$step": "id"}` | The entire output of an earlier step |
| `{"$path": ["id", "field", 0]}` | A field/index path through an earlier step's actual output |

References can be nested in ordinary argument objects and lists. Forward references, unknown references, extra reference keys, and negative list indices are rejected. A result must reference executed work instead of being a standalone canned constant. This structural check does not establish the semantic correctness of a function; real execution and task evaluation remain necessary.

Limits are 64 functions per catalog, 32 steps per function, nesting depth 24, list length 10,000, and 100,000 serialized characters per definition. JSON Schema references and regular-expression schemas are unsupported. There are no loops, recursion, imports, network operations, or arbitrary source execution in the DSL. The executor supplies the graph and optional real slot-extraction callback; a function definition cannot replace these dependencies.

`validate_functions(catalog, schema)` returns parsed `FunctionSpec` objects or fails with a concrete contract error. `execute_function(graph, catalog, name, args, schema=schema)` returns `value`, `steps`, and `dependencies`. Execution failures preserve completed and failed steps in `FunctionExecutionError`.

## Operator semantics

`operator_contracts()` generates model-facing descriptions, signatures, and condition schemas from the actual implementations and Pydantic classes. Construction prompts should consume that output instead of maintaining another handwritten operator catalog.

| Operator | Supported behavior and explicit limits |
| --- | --- |
| `lookup_entities` | Exact type, ID, primary-key-property and property filtering; stable entity-ID ordering; optional positive `top_k`. Name/text/fuzzy ranking is explicitly unsupported pending defined ranking semantics. |
| `traverse_relations` | Outgoing, incoming, or both directions over actual matching edges; 0 to 8 hops; unique visited entities; optional inclusion of seeds. Returns `entities` and `relations`. |
| `project_properties` | Flat selected properties with reserved provenance keys `__entity_id`, `__entity_type`, `__sources`, and `__primary_key` when supplied. Missing values use the explicit `missing_value`, default null. |
| `filter_property_categorical` / `filter_categorical` | AND conditions using exact `in` or `not_in` values. Missing and null properties do not match either condition. |
| `filter_relation_connected` | AND direct relation conditions with real anchor IDs; any/all anchor matching and explicit direction. No implicit transitive closure. |
| `filter_numeric` | AND `==`, `!=`, `<`, `<=`, `>`, `>=`, or inclusive `between` conditions. Numeric strings and booleans are rejected as numbers; missing/null values do not match. |
| `filter_set_overlap` | Any, all, or minimum unique overlap on real list-valued properties. It does not split a source string into guessed categories. |
| `aggregate_values` | Count, sum, min, max, mean/average, optionally grouped by a field. Count counts items. Empty count/sum is zero; empty min/max/mean is null. Null numeric values fail unless `nulls: skip` is explicit. |
| `extract_runtime_slots` | Delegates to an explicitly supplied real model callback, with bounded attempts/tokens. Fails if no callback is configured. Environment/log paths are supplied by the application, not generated function data. |

`arithmetic` is a separately labeled lightweight pre/post-processing extension supporting scalar add, subtract, multiply, and divide. It is not presented as a tenth paper operator. Numeric operations use Decimal arithmetic over the supplied JSON numbers, then return a finite JSON number. Division by zero fails. This does not recover precision already lost in an upstream floating-point conversion.

The schema validates property and relation names at construction and again after dynamic references are resolved. Actual entity records are checked with the ontology module before execution. Filter values are checked against declared property types, including nonfunctional list properties. The function-level input schema and all these checks remain separate from HermiT consistency and task correctness.

## Evidence and compatibility

The dependency record currently conservatively includes hashes of the entire graph, schema, and selected function, with the graph's source records. This covers aggregate and negative-query dependencies without claiming the smallest possible affected set. A changed graph invalidates this record's reuse condition even if a visible returned entity did not change. Source records are dependency evidence, not an assertion that every source contributed to the answer.

Actual selected entities and their provenance remain in the operator traces. A caller should use those traces to explain an answer and retain the full dependency record for revision checking. A replay executes these functions again over the candidate graph; the record is not a cached answer substitute.

## Verification scope

`tests/test_operators.py` uses the checksum-pinned official ToolQA Coffee corpus and explicit relations from the genuine W3C Wine ontology. The test schemas and function catalogs are declared integration-test contracts, not claimed LLM-generated ontologies. Checks cover real values, numeric/filter/aggregation semantics, traversal/connectivity/set overlap, typed pipeline execution, provenance, reference validation, dynamic property errors, and explicit rejection of unconfigured slot extraction or unsupported fuzzy lookup.

These checks establish execution behavior. They do not establish model construction quality, an agent benchmark score, or successful cross-task reuse.

## API

::: oak.functions

::: oak.operators

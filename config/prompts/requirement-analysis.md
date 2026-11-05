Analyze the declared task scope and supplied construction obligations. Return
RequirementAnalysis matching the supplied output schema. This stage identifies
required behavior; it does not draft a schema, implement functions, or answer
the sampled questions.

Return scope_summary, interpretations, and gaps. For each supplied obligation,
return exactly one interpretation with its original obligation_id and case_id,
an interpretation of the requested behavior, the required_outputs needed to
satisfy it, any relevant supplied capability_ids, and explicit gaps. Retain the
meaning of the original text. Do not replace a general information request with
an aggregate or impose an unspecified range, threshold, unit, or location.

Use the task description and starting instructions to interpret the obligations.
MCP contracts establish available operations and argument shapes, not observed
results or business rules. A missing capability or ambiguous requirement belongs
in gaps. Use only supplied capability IDs; an empty list is valid when the
evidence does not establish an applicable capability. Do not invent additional
obligation IDs or consume unavailable development or held-out cases.

Separate what the user requested from what the available examples demonstrate.
Describe a task-scope gap when the sampled obligations do not establish a basic
behavior implied by the scope. Such a gap is advisory, not a new approved test
case or proof that the complete task family has been covered. Interpretation
completeness is checked against the supplied obligations by the application;
semantic correctness and actual task success remain independently unverified.

When the requested behavior has a supported computational interpretation,
include program with semantic fields (id, description, value_type, unit, grain,
source_capability_ids), ordered operations, result, input_domain, and
observation_contract. Operations use read/filter/project/traverse/aggregate/
arithmetic with prior operation inputs, semantic field IDs, result_kind, and
parameters. These are task roles before any ontology exists, not candidate
class/property names. Keep input domains parameterized and preserve identity,
units, multiplicity, temporal scope and observable intermediate records. If the
meaning cannot be represented honestly, return program:null and explain the gap.
This is a proposed interpretation, never an oracle or a correct-answer claim.

Interpret task semantics, not the order or wording of a sampled ReAct trace.
Retain reusable inputs instead of copying example locations, dates, thresholds
or answers into the program. input_domain is an object JSON Schema with named
properties and required parameters. parameter_fields maps input names to the
semantic fields they constrain. source_parameters lists inputs required by the
authorized acquisition, which smaller pure computations must retain. Include
identity and selector fields needed to ask smaller point questions, even when
the requested result is an aggregate. Mark each field role as value, identity,
selector or context, with its type, unit and entity grain.

Use explicit operator semantics: read.parameters.selectors maps semantic field
IDs to literal declared constraints or "$input.parameter" references. A filter
has parameters.conditions, each with field, operator, and value (numeric),
values (in/not_in), or minimum/maximum (between). An aggregate has
parameters.operation=count|min|max|sum|mean and one numeric field unless count.
Project lists the requested semantic fields. Arithmetic has two scalar inputs
and operation add|subtract|multiply|divide. Preserve unit and grain compatibility.
Traversal needs explicit relation, direction and max_hops; unsupported lowering
is reported as a gap. Do not replace missing semantic information with a guessed
condition. Every meaningful observable intermediate is protected, including
scalar intermediates. Ordering is unordered unless the task requires order.

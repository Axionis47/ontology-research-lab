Bind the frozen semantic behavior bank to the proposed ontology and authorized
sources. Optionally compose additional functions with real-input probes.
Return FunctionProposal matching the supplied output schema. Use the supplied
requirement analysis, schema, observed graph, capability contracts, operator
contracts, and parent functions when present. The application validates and
executes the proposal separately.
Return only functions, probes, and behavior_bindings. functions and probes may
be empty when the supplied behavior bindings compile every needed operation.

Prioritize behavior_bindings for the whole supplied behavior_bank. Each binding
has behavior_id, entity_type, field_map from semantic field ID to actual schema
property, optional relation_map, optional function_name, and optional acquisition.
Omit function_name to request deterministic compilation of the frozen behavior
into an actual pure callable. If supplied, function_name must identify a real
pure function in the proposed functions catalog; the checker executes that exact
implementation. A mapping to an aggregate does not satisfy a record or property
getter. The generated __identity role maps to the schema's actual primary key.

For MCP tasks, supply acquisition:{capability_id,native_arguments} so each helper
can acquire evidence when inference begins with an empty graph. Prefer
native_arguments:{$arg:'native_arguments'} to preserve the entire real tool input
schema, including alternative routes. The compiler adds that input to the pure
callable and freezes source binding separately; source dispatch is executor-owned.
Other native argument expressions may use {$arg:'input'} or
{$arg_path:['input','nested_field']}. Use only authorized capability IDs. Do not
invent selectors the native tool contract lacks. Point helpers retain their
semantic select_<field> inputs for scoped materialization even when the tool
returns a broader response.
If TaskIR declares separate source_parameters, map them explicitly into native
arguments with {$arg:'name'} or {$arg_path:['name','field']}. Actual receipt
arguments can then ground probes through that exact template. Do not expect
the application to guess that a task input name corresponds to a source field.
Use the whole native_arguments object when TaskIR uses that object as its source
input. Preserve alternative native routes rather than narrowing them to a sample.

The bank and its checks precede this candidate. Do not rewrite a behavior to fit
the sample, copy a complete trajectory, or generate a separate function for each
question. Actual outputs, parameter domains and meaningful subtask access are
compared, never ReAct wording, operator ordering, or trajectory similarity.
If schema mapping is impossible, leave that binding absent and describe the
limitation in the supplied feedback fields when available. Missing behaviors
remain visible; do not map a semantic field to an unrelated property.

Choose enough reusable, parameterized functions to expose the required
behaviors. Avoid redundant copies for alternate native inputs, but do not
minimize function count at the expense of declared obligations. Preserve useful
parent operations while extending coverage of this sample. Basic retrieval or
property projection may be needed alongside aggregate compositions. Do not
force every question through an aggregate that discards its requested facts.
Function descriptions must state when to use the function and what it returns.

The application derives obligation links from compiled behavior entry points.
Mappings alone never establish task correctness. Unsupported behavior remains
visible and does not require a custom domain verifier or block an otherwise
executable candidate.

Custom effectful compositions may invoke real capabilities and compute over
their extracted evidence. invoke_capability takes capability (the literal exact
catalog ID) and arguments (native MCP arguments). The executor extracts the
response into the current episode G and returns
{entities,entities_by_type,receipt_id}. entities_by_type maps every declared
entity type to its list from THIS response. Prefer
{$path:['fetch_step','entities_by_type','DeclaredType']} as filter or aggregate
input so earlier acquisitions are not mixed into a new request. Later graph
steps operate on actual G. Do not supply graph or callback arguments.

Each step calls one documented operator. References are {$arg:'input'},
{$step:'previous_id'}, or {$path:['previous_id','field',0]}. Return result using
these references. Inputs require JSON Schema
object/properties/required/additionalProperties:false. The executor does not
insert JSON Schema defaults. Every referenced input must be required and
supplied by each probe. Pass entities explicitly to filters. For numeric
comparisons use {property,operator,value}; minimum/maximum apply only to
between. aggregate_values takes items and request:{operation,...}, not
operation as a top-level argument. Follow the actual operator contracts.

Provide one probe on real task inputs for every custom function. Compiled pure
behavior probes are derived by the application from genuine retained records,
with no fresh MCP dispatch for each helper. Preserve native
parameter flexibility and valid alternative acquisition routes. Documented
literal numeric API defaults are allowed; request-specific thresholds and
locations must be inputs. For alternate native input routes, prefer a required
native_arguments object whose schema copies the registered input_schema, bound
through {$arg:'native_arguments'}. Do not require an optional native field just
because the sample used it. Distinct operations may use separate functions.
Do not use extract_runtime_slots in this executor; model decisions bind slots.

When execution_feedback is supplied, repair the reported contract or execution
defect while retaining required behavior. A successful probe establishes only
that the supplied call executed and met its output contract. It does not prove
that the agent selects the right function or answers the full task correctly.

The task_ir bank is frozen before any schema/function candidate. Cover every
mandatory literal and mechanically derived subtask obligation supplied. Return
records before lossy aggregation through a callable function, so a smaller
question can retrieve its requested facts. Exploration entries are optional and
remain unverified. Retain input-domain flexibility. Do not create a raw-source
escape hatch. The executor derives evidence demands from your actual operators
and materializes only demanded types/fields plus schema-required dependencies.
The planner sees the recorded evidence scope and autonomously decides whether
to expand or answer. Processing every text chunk does not prove complete
extraction, and unknown scope is not an execution permission gate.

The frozen semantic interpreter and bounded program mutations provide the
comparison bank. Do not return test programs or expected answers. The executor
compares actual bound functions on genuine evidence with these generated task
semantics and probes sensitivity to bounded code defects. Scores count fixed
behavior/input strata, not duplicate checks, function count, or copied traces.
These checks are generated consistency evidence, not independent assessment of
task truth. A failed check can guide repair; absent hand-authored evaluators must
not stop autonomy. Checks never replay effectful acquisition functions.

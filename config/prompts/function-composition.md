Compose only a function catalog, real-input probes, and obligation mappings.
Return FunctionProposal matching the supplied output schema. Use the supplied
requirement analysis, schema, observed graph, capability contracts, operator
contracts, and parent functions when present. The application validates and
executes the proposal separately.

Choose enough reusable, parameterized functions to expose the required
behaviors. Avoid redundant copies for alternate native inputs, but do not
minimize function count at the expense of declared obligations. Preserve useful
parent operations while extending coverage of this sample. Basic retrieval or
property projection may be needed alongside aggregate compositions. Do not
force every question through an aggregate that discards its requested facts.
Function descriptions must state when to use the function and what it returns.

Return exactly one coverage entry for every supplied obligation_id. An entry
names the proposed function_names intended to support that obligation, or gives
an unsupported_reason when no proposed function can support it. Use names from
this proposal only. These are declared mappings, not task-success assessments.
Do not conceal missing capability behind an unrelated mapping. The application
checks references and rejects unmapped or explicitly unsupported obligations;
valid mappings still require independent execution and outcome evidence.

At least one useful composition must invoke a real capability and compute over
its extracted evidence. invoke_capability takes capability (the literal exact
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

Provide one probe on real task inputs for every function. Preserve native
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

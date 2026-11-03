Construct a reusable task-conditioned ontology kernel from the declared task
scope, registered capabilities, and this round's sampled whole-task episodes.
The target artifacts are schema S and executable functions F. Graph G contains
grounded observations under S. Reuse must be demonstrated by real executions
with different task inputs; producing larger artifacts is not an objective.

Use only the supplied construction sample and authorized construction history.
Each round is drawn afresh from the construction pool with a recorded seed,
pool identity, and selected query IDs. Samples may overlap between rounds.
Development checks and final held-out inputs or answers are outside this
construction context. Never invent successful episodes or use reference answers
as function implementations. This process refines artifacts, not model weights.

MCP contracts establish the available operations and argument shapes. Real
episode receipts establish what was called and observed. The task scope and
public requirements establish which outcomes matter. Keep these sources
distinct and link proposed definitions to their evidence. A provider description
alone cannot establish a business prerequisite or a successful task outcome.

Use sampled behavioral feedback when it is supplied: the actual call sequence,
argument choices, errors, recovery attempts, and terminal status. A starter's
completion claim is not a measured success. Treat outcome correctness as
unmeasured unless an explicit verified construction-score receipt is supplied.
Scores may guide diagnosis, but evaluator reference answers must remain outside
the construction prompt. Do not infer that an omitted failure was successful.

Propose schema distinctions, relationships, identities, and constraints needed
to represent the sampled tasks and their observations. Propose typed functions
that expose approved atomic capabilities and reusable compositions over the
actual operator library. Parameterize task inputs. Do not hardcode task IDs,
answers, incidental example entities, or domain solutions into the shared loop.
Keep only representations that support execution, validation, or inspection.

This initial executor extracts each new tool response as an independently valid
graph fragment before merging it into the current episode G. Declare only
identity and other fields supported in every relevant fragment as required.
Source-specific attributes may be optional at the schema layer; task completion
must still require the relevant evidence. Do not require an extraction fragment
to invent an absent field or an edge endpoint available only in an earlier
response. Record such coverage limitations rather than weakening task success.

Distinguish necessary typed dataflow and independently supported rules from
historically common routes. A repeated call order is not proof of necessity.
Represent missing evidence and unsupported coverage explicitly. Preserve atomic
capabilities so an already-satisfied prerequisite or a new combination of known
operations can be handled without forcing a memorized route. Any new external
capability requires a separately registered and validated candidate revision.

Validate the schema through the supported schema-to-OWL mapping and real
HermiT reasoning. The paper's categories are disjointness, restriction,
property-level and global consistency, plus named unsatisfiable classes. They
are covered by the encoded axioms and reasoner result, not five independent
certificates. Descriptions are not executable axioms. Open-world consistency
does not prove complete records, accurate observations, task coverage, function
correctness, or successful behavior. Unsupported OWL constructs and reasoner
errors must remain failures; do not replace HermiT with a structural JSON check.

Evaluate graph integrity, actual function execution, task outcomes, recorded-call
compatibility, and fresh agent decisions separately. Identify whether a failure
comes from missing capability, acquisition, extraction, schema, function,
planning, or evaluation before proposing a repair. An LLM judgment cannot
override a failed deterministic check or measured task outcome. When independent
task scoring is unavailable, label correctness unmeasured.

Prefer a candidate supported by broader sampled task coverage and reusable
parameterized behavior within the declared bounds. Retain prior failures and
check previously supported tasks for regressions. A smaller number of calls or
tokens is useful only with the relevant outcome quality and evidence preserved.
Never reward graph size, schema size, checkboxes, or agreement with the judge.

Every change creates an attributable candidate with its parent revision, source
episodes, interpreted changes, validation receipts, and limitations. Freeze only
with the declared acceptance evidence. Frozen inference obtains new real
observations through the validated interface; it does not substitute old answers
or silently revise the kernel. Unknown dependency coverage requires broader
fresh checks, not an unsupported promise of preserved behavior.

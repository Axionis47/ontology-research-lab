# Computational learning and controlled execution protocol

Version 1.0, November 13, 2026. Status: implementation specification, not an installed runtime or a measured learning result. This document connects the existing contracts into one computational protocol. [computational-protocol.json](computational-protocol.json) is its machine-readable control and ownership table. [contracts.schema.json](contracts.schema.json) still owns wire records; [profile.json](profile.json) still owns limits. The [one-family scope](11-narrow-training-and-inference.md) remains active.

The implemented [C0 component](13-react-component.md) currently supplies ReAct, compaction, output storage and an [offline evidence reader](14-judge-evidence.md). Its `react-component-0.1` records and component limits are distinct from this full-system protocol. Integration must explicitly translate and validate those records, not relabel them as full kernel conformance. The first component still excludes the benchmark adapter. Nothing here changes its runtime or claims the learning loop is implemented.

The latest design clarification is that task data and methods for handling that data are different objects. Reusable learning primarily improves how functions obtain evidence, traverse relationships, combine constraints, select actions and handle uncertainty across a task surface. Entity-specific facts are inputs, not the learning target. Automatically changing prose instructions, context items or workflow suggestions is outside this phase. Small tool interfaces, public task instructions and relevant results still enter the model context. Keeping knowledge external does not make the model able to use an interface it has never seen.

## 1. Computational objects and update rules

```text
D_v = (S_v, M_v, F_v, C_v)       immutable domain package version v
S_v = entity/relation/property definitions, types, units, domain constraints
M_v = mappings from source contracts to those definitions
F_v = executable procedures for relational computation and constraint handling
C_v = function input/output interfaces and declared computation/effects

G_e,r = observed and derived domain facts for episode e at revision r
T_e   = pinned task goal, entity bindings, requirements and resource scope
Q_e   = the task's required predicates/checker bindings and preference criteria
H_e,t = derived candidate sets, requirement dependencies and evidence gaps
X_e,t = runtime control state for episode e at transition t
K     = trusted transition, admission, execution and verification machinery
O     = locked nine-operator runtime, activated only when justified
A     = append-only execution, evaluation and candidate archive
```

`D_v` describes a task surface and reusable computation. A task surface is the available entity types, relations, data sources, operations, effect contracts and supported goal shapes. Its implementation can initially cover one narrow workflow without making that workflow's particular records the representation's identity. `G_e,r` contains particular observed entities and relations. `T_e` identifies the requested outcome over those entities; `Q_e` records what must hold. `H_e,t` is an explicit dependency/candidate projection that can be discarded and recomputed from current evidence, task requirements and pinned procedures. It grants no authority.

`X_e,t` contains lifecycle, manifest reference, open requirements, graph revision, remaining/reserved budgets, pending operations, step counters and last committed event. Its authoritative state is reconstructed from the ledger and checkpoints. A model response is neither a verified fact nor a committed control transition. The named tuples are computational views of existing records, not additional actor wire messages.

The core computational problem is:

```text
handle(D_v, G_e,r, T_e, Q_e)
  -> candidates + checked constraints + evidence gaps + proposed next operation
```

It must handle constraints together over connected records, not evaluate every property independently and assume the conjunction is feasible. The method may acquire more evidence, revise candidates, backtrack or report a supported conflict. Success is checked by independent task checkers and the native evaluator, not by the method reporting that it solved its own problem.

The three permitted update paths are different:

```text
Observation update:
  G_e,r+1 = ingest_checked(G_e,r, admitted_receipt, M_v, S_v)

Control update:
  X_e,t+1 = reduce_checked(X_e,t, trusted_event, K)

Learning update, between episodes:
  D_candidate = apply_bounded_patch(D_parent, RepairSpec, patch)
  D_active changes only after comparison and an accepted GateDecision
```

The actor selects an action using the public goal, selected function interfaces and bounded observations. Functions perform the stored computation. The runtime applies the control transition. These are separate ownership boundaries, not three names for an LLM call.

| Object | Writer | When it may change | What cannot cause a change |
| --- | --- | --- | --- |
| Domain package `D_v` | Isolated builder, then release controller | New candidate version between episodes | Actor output or a new entity instance |
| Facts `G_e,r` | Trusted ingestion/derivation service | After validated source observations or checked derivations | Unsupported model assertions or a judge hypothesis |
| Task requirements `T_e`, `Q_e` | Trusted task adapter from the actual request and source contracts | At task binding; an explicit authorized revision creates a recorded new binding | Solver dropping an inconvenient requirement or relaxing a threshold |
| Constraint workspace `H_e,t` | Checked domain computation and dependency projection | As candidates/evidence/check results change | Treating a proposed plan or explanation as verified evidence |
| Control state `X_e,t` | Scheduler/ledger reducer | Legal transition with current revision and required receipts | Actor-supplied lifecycle, permission or success flags |
| Protected machinery `K`, `O`, policy and evaluator | Separate engineering process | Outside automated domain learning | A candidate patch or model-authored test |
| Archive `A` | Trusted ledger/artifact writer | Append new evidence and decisions | Actor/proposer rewriting or hiding earlier results |

Schema is stable by default. A schema patch requires evidence of a missing or incorrect concept, plus a test that a mapping/function-only fix cannot satisfy correctly. New entity IDs, values and relation memberships are instance updates. Task-specific answers and entity allowlists must not be smuggled into reusable package files.

## 2. Constraints, semantics and learnable handling

Three kinds of constraints have distinct owners:

| Constraint kind | Example | May the learner change it? |
| --- | --- | --- |
| Protected runtime policy | Which resources may be written; bounded spending | No |
| Task obligations | All chosen items must satisfy eligibility and a combined resource limit | No; values can differ between tasks, but the current task's requirements stay pinned |
| Domain representation constraints | Relation cardinality, identity semantics, compatible units | Only if independent domain evidence supports a representation correction; never merely to make a violating input pass |

The strategy for satisfying those constraints is learnable. Examples include joining the correct relationship path before filtering, intersecting candidate sets, propagating a shared resource bound, deduplicating entities before counting, fetching the missing fact that decides feasibility, and recomputing dependent checks after a source update. These procedures can be encoded in `F_v`, using ordinary code or the activated locked operators. Generic control flow inside a typed function does not add an operator to `O`.

Bind task requirements through `TaskSpec` and `Requirement`, including checker IDs/hashes and evidence dependencies. The actual request/source definition supplies thresholds and relational meaning. Any model-extracted binding remains a proposal until validated against that basis; unresolved meaning requires evidence or input. Hidden evaluator information is never used to construct public task requirements. New checker implementations remain separate engineering work, not editable solver output.

For each required predicate, store a `CheckedFact`: `TRUE`, `FALSE` or `UNKNOWN`, the evaluated revision and evidence. Keep preference ranking separate from required predicates. A preferred candidate that violates a required constraint is not feasible.

```text
1. Resolve goal entities and named relationships within task scope.
2. Follow declared relationship paths and preserve identity/provenance.
3. Evaluate required predicates; intersect compatible candidates.
4. Evaluate constraints involving multiple records or proposed actions together.
5. For UNKNOWN, identify the missing/stale evidence and an admitted acquisition.
6. For FALSE, identify a counterexample or a supported conflicting requirement set.
7. Propose a feasible next operation, a justified revisit, or an honest blocked result.
8. After an effect/source update, invalidate dependencies and recompute affected checks.
```

This is a computational protocol, not a claim that a complete generic constraint solver exists. A function declares which predicates and compositions it supports. Unimplemented forms return `CAPABILITY_UNAVAILABLE`; incomplete evidence cannot establish global infeasibility. The first implementation covers one actual goal shape, while the representation keeps goals, records, relationships and handling procedures distinct.

## 3. Storage and computational representation

Use the existing SQLite ledger and protected artifact store, not another independent memory authority. The following are logical projections; implementation must preserve the transaction and crash rules in the [trace protocol](../../execution-trace-protocol-v1.md).

| Projection | Required information |
| --- | --- |
| Package registry | Package hash, parent, schema/mapping/function/interface artifact hashes, dependency/operator runtime hashes, build receipt, gate receipt, active pointer |
| Entity/property/relation tables | Source-namespaced identity, type, typed value or relation endpoints, episode/account/environment scope, graph revision |
| Fact provenance | Evidence IDs and original locators, source revision if available, observation time, source validity when known, transform hash, missing/null/known/conflict status |
| Derivation dependencies | Derived fact/result ID, exact input fact/evidence IDs, package/function version, source revisions |
| Requirements | Public requirement ID, checker hash, current `TRUE/FALSE/UNKNOWN`, evidence dependencies and checked revision |
| Constraint workspace | Candidate IDs/sets, dependency edges, checked predicate references, evidence gaps and proposed next operation, all bound to task/package/data revision |
| Episodes/operations/events | Manifest, lifecycle revision, proposed and dispatched arguments, admission/dispatch/result receipts, budgets and outstanding effects |
| Candidate archive | Parent and candidate hashes, `RepairSpec`, patch, build/test receipts, native results, decision and rejection reason |

Raw evidence is preserved separately from interpreted values. A graph revision binds a consistent view, not a claim that every source record is fresh or complete. A source update invalidates dependent conclusions; conflicting observations remain explicit until a source-backed resolution is available. Missing values cannot become zero, false or a fabricated relationship. Observation time alone is not proof of source freshness.

Facts are scoped by environment and episode. Reuse across episodes requires an explicit authorized source/cache policy and revalidation; benchmark instances always begin with their own fact scope. Persisting a table does not permit training/test leakage.

A package stores schema and mappings as structured artifacts and functions as executable code with schemas. The trusted registry derives `OperationContract` bindings from those artifacts plus protected policy and adapter contracts. A learned function's declared effects restrict its execution; they do not grant permissions or replace protected checks.

## 4. Knowledge access protocol

Reuse the existing actor `Proposal` union. The actor can emit exactly one `act`, `revisit`, `finish` or `request_input` per decision. A domain function, source read or evidence-page request is a manifest-bound `act`, not a new actor command or a tenth operator.

1. **Bind.** `prepare_episode` pins `D_v`, model configuration, tools, source environment, policy, budgets and evaluator binding in `EpisodeManifest`. Verify all referenced artifacts before reaching `READY`. The package hash never changes within that episode.
2. **Expose.** `build_context` supplies selected action IDs with their argument/result contracts, current public requirements, relevant evidence and recent receipts. Begin with the narrow task's fixed tool set. Large catalog discovery is deferred; no semantic router is needed for one helper.
3. **Propose.** The actor emits an `ActProposal` with `action_id`, arguments and cited evidence IDs. The authenticated runtime supplies scope and pinned identities; actor-provided IDs never grant access.
4. **Admit.** Validate the proposal against its exact function contract, state, evidence/freshness needs, protected policy and remaining budget. Commit the decision and reservations before any dispatch.
5. **Compute.** A pure function uses admitted records. A function needing external data makes declared child calls through the same kernel. Validate and map successful observations before using them. Every child operation is individually admitted and metered. Ordinary rows are sufficient initially; `O` is optional implementation machinery.
6. **Return.** Validate the function result; attach authentic source/transform provenance, revision, completeness, unknown/excluded counts and continuation where applicable. A worker's claimed completeness/evidence must be checked against actual input coverage and the pinned contract. Compose an `OperationReceipt` and bounded `Observation`.
7. **Continue or verify.** The actor may use returned IDs/evidence in a later action. A write requires fresh admission and supported concurrency protection. A selected record or successful function return does not authorize the write or prove final task completion.

Use the existing `OperatorResult` envelope internally when an operator runs. Domain result payloads validate against the selected function's output schema; the outer result remains `OperationReceipt`/`Observation`. A partial search cannot establish unique identity over an unexamined candidate set. Explicit absence, ambiguous matches, stale evidence and insufficient evidence lead to declared result/failure branches, with a bounded read or correction path.

## 5. Runtime state machine

The full transition table is in [document 02](02-inference-and-control.md) and the JSON companion. The central path is:

```text
CREATED -> PREPARING -> READY -> INFERENCING -> ADMITTING
                                                |
                    allowed act ----------------+-> EXECUTING -> READY
                    denial / revisit -----------+-> READY
                    finish ---------------------+-> VERIFYING
                    interactive input ----------+-> WAITING_INPUT

EXECUTING -> RECONCILING when an external effect is uncertain
VERIFYING -> READY when a public obligation is unmet
VERIFYING -> EVALUATING -> TERMINAL when acting ends
```

Budget expiry and cancellation stop acting through the controller, preserve unresolved effects and use reserved finalization where possible. A terminal outcome can be failed, partial, unavailable or unresolved. There is no legal outgoing action from `TERMINAL`.

Every state transition uses the same checked reducer:

```python
# Specification pseudocode. Durable primitives are implemented by the kernel.
def transition(episode_id, expected_revision, event):
    with ledger.transaction():
        current = load_state(episode_id)
        require(current.revision == expected_revision)
        require(authentic_event_producer(event))
        require(valid_closed_event_schema(event))
        require(event.to_state in allowed_next[current.lifecycle])
        require(all_required_guards_pass(current, event))
        append_event(event)
        next_state = reduce(current, event)
        compare_and_set_state(current.revision, next_state)
    return next_state
```

Guard inputs come from committed receipts and trusted checks. An LLM cannot supply `guard_passed=true`. An unsupported guard implementation leaves its operation unavailable. The JSON transition/guard table is data for implementation and validation; loading it alone is not enforcement.

Dispatch is a separate operation outside the database transaction. It consumes a committed, unused admission after rechecking volatile conditions and durably recording intent. A crash after intent is reconciled before another mutation. Local duplicate suppression does not prove exactly-once behavior at a remote service.

The actor process has no backend credentials, direct task tools, ledger write access or evaluator access. Generated functions run in the isolated worker and use only scoped RPC. Without that boundary, the state table could be bypassed. Follow [document 03](03-execution-kernel.md); runtime integration tests must observe prevention externally.

`finish` is a proposal. Public checks use current evidence; hidden evaluator details never become stepwise hints. Terminal benchmark evaluation remains independent. Verified success requires native task pass, applicable public checks, control conformance, complete required tracing and no unresolved effects. A confident answer cannot create those receipts.

The controller charges every actor attempt, rejection and child call. Repeated actions with unchanged relevant evidence and obligations trigger the existing no-progress handling. Revisit, changed evidence and declared recovery remain legal. Budgets and finalization reserves in the active profile bound the loop even if the model keeps asking to continue.

## 6. Learning protocol

The optimizer searches over `D`, with acting-model weights fixed. The primary hypothesis is that a changed procedure handles a relationship/constraint pattern better across different task data. It does not rewrite the protected state machine or the current task's desired outcome. A training cycle is:

```text
frozen D_parent + fit/development tasks
 -> complete execution traces + independent results
 -> supported failure mechanism + deterministic reproducer
 -> RepairSpec + isolated candidate patch
 -> build + contract checks + preservation fixtures
 -> paired fresh-environment fit/development runs
 -> retain/reject candidate with all evidence
 -> freeze one selected candidate
 -> sealed comparison + GateDecision
 -> registry compare-and-set for new episodes only
```

The diagnosis and repair are separate bounded jobs, even if the same configured model serves both roles. No parallel agents or model-weight optimizer are required.

| Failure mechanism | Update target | Necessary evidence |
| --- | --- | --- |
| New/different source records | Facts through ingestion | Admitted observation and valid source mapping; no training patch |
| Wrong field/unit/missing interpretation | `M_v` | Original response, source contract and discriminating mapping fixture |
| Wrong selection/composition/computation | `F_v` | Correct inputs, wrong result and independently specified expected result |
| Incorrect relationship traversal or constraint interaction | `F_v`, or `M_v` if the relation was misinterpreted | Evidence path, missed/conflicting predicate, discriminating fixture and an analogous passing case |
| Repeated unnecessary reads or incorrect evidence-gap handling | `F_v` | Required-predicate dependencies, original observations, counted operations and unchanged outcome checks |
| Ambiguous typed arguments/result interface | `C_v`, with compatible function changes if needed | Reproducer of the ambiguity plus interface and preserved-call fixtures |
| Required concept absent or incorrectly modeled | `S_v`, with mapping/interface changes as needed | Domain/source basis, failure that needs the concept, compatibility and reconstruction evidence |
| Actor ignores an already sufficient interface | Unresolved actor failure or a separately tested abstraction hypothesis | Controlled reruns; no automatic schema patch just because the actor failed |
| Authentication, environment, kernel or evaluator fault | Engineering issue outside domain learning | Operational reproducer; no fabricated competence score or weaker checks |

A `RepairSpec` declares one mechanism, exact allowed files, source findings, independently grounded expected behavior, preservation examples and evaluation schedule. Allowed automatic file classes are schema, mappings, function implementations and function I/O contracts. Package hashes/build manifests are produced by trusted tooling. Existing optional `context_items.json` and `workflows.json` are not optimization targets for this phase. Authority, required checks and budget rules remain protected even when referenced from editable files.

A schema change creates a new package version. Rebuild candidate fact projections from authorized original observations using the candidate mappings; record construction cost and compare results. Never reinterpret old persisted values under a new schema silently. Destructive migrations, extra dependencies, new protected checker implementations or changes beyond active patch limits are separate engineering work. Old episodes and their projections keep their original package hash.

Candidate fixtures vary entity IDs/values, relation topology and constraint combinations within the supported surface. Include a uniquely feasible case, multiple feasible cases, a known violation, insufficient evidence, changed source state and a previously passing analogous case when applicable. Changing only names is insufficient evidence of structural transfer. These are synthetic conformance fixtures, not extra native benchmark tasks or proof of generalization. Candidate proposals can add tests but cannot replace existing independent expected results, fixtures or evaluator logic.

Use the exact [narrow acceptance gate](08-evaluation-and-success.md). Selection uses fit/development only; retain a candidate only with target gain and no observed per-instance pass-count regression. Freeze exactly one before the sealed comparison. Promotion requires all scheduled candidate repeats to pass, the targeted improvement, intact control/preservation checks, complete results and the preregistered resource rule. Partial improvement can remain archived. No improvement means keep the parent, not generate a learning claim. The sealed instance cannot be reused as a fresh holdout after exposure.

Current limits remain one family, at most one helper, up to three active operators, one candidate per cycle, two changed files and three visible cycles. A candidate exceeding a bound does not receive a silent exception.

### Consolidation before repair

The entities and schema may already exist while their mapping, relationship or computational composition is missing. Consolidation must discover and resolve existing objects before proposing new ones. The `consolidation` section of [computational-protocol.json](computational-protocol.json) records this contract:

```text
pin case and versions -> discover existing objects -> resolve identities
 -> locate the gap -> validate the smallest supported delta -> archive decision
```

The case links the original goal, kernel handoff or other failure event, pre-handoff evidence, ReAct continuation, terminal outcome and official evaluation receipt (or explicit unavailability). Failed continuations are retained. A successful continuation alone does not establish a correct general rule. The runtime already records handoff and terminal events; entity/schema discovery and the consolidation worker remain unimplemented.

Definition lookup reads the pinned package's types, properties, relation definitions, mappings and function interfaces. Instance lookup reads authorized observations through the existing entity/property/relation query contracts when implemented and enabled. Identity includes environment/episode scope, source namespace, type and source key. Equal display names do not merge entities. Proven aliases require source evidence; benchmark worlds remain separate.

Bounded lookup receipts record query, scope, package hash, graph revision, returned IDs, evidence references, coverage and continuation. Repair requests relevant pages or neighborhoods within its existing job budget. An empty page does not prove absence. Incomplete coverage, identity ambiguity or conflicting evidence returns `NEEDS_EVIDENCE`.

| Gap | Action | Update target |
| --- | --- | --- |
| `OBSERVATION_GAP`: an instance fact or edge is missing, but its type exists | Acquire evidence and attach it to existing identities | Trusted fact ingestion |
| `MAPPING_GAP`: the source relationship exists but is not represented correctly | Connect the source field to the existing definition | Candidate mapping |
| `COMPOSITION_GAP`: required facts and definitions exist but the method does not combine them | Correct traversal, joins or operation order | Candidate function |
| `SCHEMA_GAP`: existing definitions cannot express the required concept | Propose the smallest justified definition change | Candidate schema |
| `NEEDS_EVIDENCE`: these cases cannot be distinguished | Preserve uncertainty and missing-evidence references | No committed repair |
| `NO_CHANGE`: the needed connection already works | Reuse and reference it | No patch |
| `CONTROL_FAILURE`: dispatch, authentication, runtime or evaluation is defective | Route the operational reproducer separately | Engineering outside domain learning |

For example, when `Song`, `Artist` and `performedBy` already exist, an evidenced `artist_id` may resolve to an existing artist whose edge has not been ingested. If the edge exists but the function never traverses it, repair composition. Do not create another artist type for an unfamiliar name or infer an edge from co-occurrence alone.

Archive reused entity/definition IDs, the precise gap, delta or no-change decision, supporting evidence, validation and acceptance/rejection reason. Reuse `EvidenceRef`, `OperationReceipt`, `GraphDelta`, `RepairSpec`, candidate and gate records. Fact updates retain provenance and history. Package repairs create separate candidates and keep active episodes frozen. Schema extension additionally requires complete discovery within the relevant declared scope, independent semantic evidence, and a reproducer showing why a mapping/composition-only repair is insufficient. These checks must be implemented in code, rather than entrusted to prompt instructions. This specification does not claim installed enforcement.

## 7. Existing data and transferable handling

The repository's [Atlas fixture](../../examples/atlas-gap-fixture.json) is explicitly synthetic. It contains an observed project with two active-lead IDs, a mapping from `active_lead_ids` to `hasActiveLead`, and a separate shape declaring maximum cardinality one. The [detector](../../examples/gap_detection.py) reports the mismatch with source/mapping/schema pins and leaves the root cause undetermined. Native task evidence is now recorded by the [AppWorld surface](15-appworld-surface.md); it has not been consolidated into a learned package.

The current [ReAct fixture](../../react_runtime/fixtures.py) supplies synthetic records with an ID, delivery status and proof string. It exercises recording, rereading and compaction. It does not supply enough relational task diversity to demonstrate improved constraint handling; that needs independently evaluated task/relationship fixtures and later native tasks.

```text
Data: project:atlas -> hasActiveLead -> {person:maya, person:noah}
Constraint: distinct active-lead count <= 1
Observed result: 2 > 1
Conclusion: this data violates this declared constraint.
Not established: which source, mapping, domain rule or real-world state is wrong.
```

The existing detector already deduplicates identities, rejects missing fields and distinguishes source/access failure from a constraint mismatch. Those behaviors are evidence of the intended computational distinction, not new improvements delivered here. Replacing the project/person names must not change its logic. Setting the maximum to two merely to pass this record would change the question instead of improve its handling.

For a larger supported task shape, suppose the task is to identify an eligible responsible person through project/team membership and role status. The reusable method must resolve identity, traverse the declared relationships, combine role/status/scope requirements, detect ambiguity, acquire missing evidence and verify the selected relationship. These extra fields are a proposed synthetic extension, not present data in the Atlas fixture. A concrete learning hypothesis could repair a method that filters people by role globally before restricting them to the relevant team. The distinguishing fixture includes a qualified outsider and an eligible member; the preserved case checks an unambiguous member. The correct patch changes relationship-aware selection, not the task's eligibility definition or the observed membership facts.

For songs, the same separation applies to artist relationships, playlist membership and any task-specific eligibility or aggregate constraints. Different domains need their own grounded semantics and mappings. Reusing a computational pattern across domains is a hypothesis to evaluate, not automatic proof of transfer. The pilot's native benchmark remains one family; broader task-surface structure can be represented without inventing broader empirical results.

## 8. Implementation acceptance

The companion JSON is checked against wire schemas, the lifecycle table, active profile references, protected surfaces and acceptance IDs by [validate_spec.py](validate_spec.py). This validates specification consistency only.

Runtime delivery requires externally observed evidence for allowed and denied dispatch, isolation, crash recovery, stale evidence invalidation, truthful completion, unchanged episode package hashes and candidate rejection/promotion. Existing cases `KRN-01`, `KRN-03`, `KRN-05`, `INF-01`, `INF-02`, `END-01`, `DOM-01`, `DOM-04`, `REP-02`, `REP-03` and `REP-05` cover those boundaries. Added cases `DOM-05`, `DOM-06` and `REP-06` specifically cover reusable structures, schema reconstruction and durable computational learning. None are marked executed by this document.

The minimal build uses the existing scheduler, ledger, adapter and evaluator, then one optional typed helper and the offline patch/comparison jobs. A general knowledge server, new graph database, large function catalog and weight training are outside this increment.

# Independent verification and preservation flow

Status: implemented component, 2026-11-04. This flow remains independent of candidate learning. The user explicitly requires generated checks and autonomous kernel execution without a custom domain evaluator prerequisite.

## Boundary

The learning flow submits an immutable `KernelCandidate`, a frozen list of `ObligationCheck` contracts and `ObservedCheck` evidence references. `verify_candidate` owns checking, but does not generate task requirements, expected answers, schemas, functions or model reviews. Its authoritative Pydantic contracts are in `oak.verification`; this document is not a second wire definition.

Observed checks contain no caller-supplied success flag. Evidence artifacts are loaded through the hash-verifying Store. Pure functions execute for real on retained graphs. Effectful functions require actual event-bound probe traces, completed MCP receipts and matching function/schema/graph dependencies. Verification never redispatches their MCP calls. Historical probe admission is labelled recorded execution, not fresh execution.

Execution eligibility requires attributable ontology validity and actual function execution evidence. Missing independent evaluation, unresolved interpretations and missing domain coverage adapters do not disable an otherwise eligible kernel. Independent task assessment and construction-target evidence remain separate.

## Generated checks

The model can propose `GeneratedCheckSpec` programs in the existing finite typed operator DSL. The checker supports equality, multiset subset, list-length equality and nonempty relationships. Programs must depend on actual graph evidence and cannot invoke models or MCP services. There is no expected-answer field or arbitrary code execution.

`CandidateFunctionRef` binds a check to the actual candidate function by name. This matters because two standalone generated programs on an unchanged graph could agree without observing candidate behavior at all. Standalone consistency checks remain inspectable but do not contribute to candidate-quality coverage. Checks anchored to candidate functions execute the actual current function body on genuine retained graph data.

Obvious normalized self-equalities and empty-subset checks are unknown rather than coverage successes. Generated checks can still be semantically inadequate; they are explicitly non-independent. The frozen campaign bank, fixed denominators, source-schema binding and independent task assessment prevent their result from being represented as universal correctness. A changed schema without a validated bank translation is unknown.

Generated check failures are counterexample feedback for learning. They do not independently disable inference. There is no mandatory population certificate or domain-specific hand-authored verifier prerequisite.

## Narrow preservation

The `proofs` Lake package is pinned to `leanprover/lean4:v4.35.0`. The current implementation uses the installed official binary under `.tools/lean/bin/lean`, or `OAK_LEAN_BINARY`, or a matching `lean` on PATH. Missing or mismatched Lean produces an unknown result. The package uses only Lean's standard library.

The formal model is a finite eager pure PlanIR with parameterized deterministic validation, primitive and expression semantics. The observation contains the returned value or typed failure and the ordered list of primitive calls. Theorems quantify over the same arbitrary immutable graph and accepted input. Local diagnostic labels and timing are outside the observation contract.

Python lowers validated FunctionSpecs to positional step references, leaving external inputs, property names, literal strings, call order/count and outputs unchanged. Equal canonical plans have checked preservation proofs. The proof module includes identity, canonical preservation, transitivity, exact block abstraction and sequencing congruence. Every instantiated certificate is compiled through a fixed theorem template; arbitrary model-authored Lean is never executed.

The proof dependency audit currently permits no axioms. Actual Lean 4.35.0 reports no axioms for the four exported proof templates and the instantiated candidate theorems. No `sorry`, native evaluation axiom or unapproved theorem assumption is accepted.

Certificates pin exact parent/candidate inputs, schemas, complete selected protected contracts, source implementations, dependency lockfile, proof module and toolchain. Chain composition reloads actual revisions and rechecks adjacent certificates before carrying the oldest protected set forward. Removed entry points fail; changed schemas, external contracts, effectful operations and unsupported computations remain unknown.

This establishes PlanIR preservation conditional on the pinned Python bridge. Hashes and genuine differential tests audit that bridge but do not prove Python correspondence. Same-graph preservation does not prove that a partial materialization is sufficient, that extraction is correct, or that a fresh agent will choose the same functions.

## Verification evidence

`tests/test_verification.py` executes actual Coffee operators on genuine source rows, real OWL/HermiT validation, real Lean proof checks, and event-bound weather probe verification from the reviewed portable fixture. It checks non-gating absent oracles, generated candidate-function changes, tautology suppression, forbidden effects, explicit unknowns, tampered certificates and transitive certificate composition.

The component has not made any paid model call or live MCP invocation. Final integration and live campaign evidence belong to the root delivery record. Original saved artifacts and hashes are unchanged; test copies and generated proof files live in temporary directories.

## Selective evaluation and campaign integration, 2026-11-04

`oak.selective_evaluation` owns the authoritative dependency, plan and receipt contracts. Computation, materialization and planner exposure are separate scopes. Computation uses complete pure programs and entire immutable graph hashes, including population, adjacency, identity, units, missingness and ordering. Dynamic traces never establish complete dependency coverage. Calls without their exact saved input graph remain unknown; a final graph cannot substitute for an earlier call input.

The planner selects reuse, proof transfer, real pure replay, genuine rematerialization or explicit deferral independently from fresh agent execution. The maximum is three fresh cases per candidate, including at most one planner-only sentinel. Unknown-cost fresh work is scheduled one case at a time. Existing surface/global ledger ceilings and outstanding reservations remain authoritative. No additional hard fresh-dollar subbudget is claimed.

Generated behavior cases have `planner_required=False`. Their scopes bind the actual semantic bank, selected bindings, candidate entry points, source receipts, graph and evaluator implementations. Unrelated function changes can leave their local results reusable while changing global planner exposure. Full planner context includes model/runtime configuration, task runtime prompt bytes and actual selected procedural history. Behavior and extraction contracts pin actual source bindings and capability contracts.

`execute_local_plan` executes real pure functions and generated semantic checks without MCP or model dispatch. `record_local_result` runs those checks after a worker supplies a genuine rematerialized graph and attributable source/stage references. It accepts no caller status. `record_fresh_result` binds an actual saved episode to its exact candidate and case, keeping execution, agent outcome and independent assessment separate. `refresh_evaluation_receipt` recomputes summaries after either update.

`oak.construction_campaign` replaces the growing union of fresh old questions. It freezes requirements and behaviors, retains the existing three-round and bounded inner repair policies, persists evaluation intent before paid work and compares contenders on the same retained source snapshot. A changed schema requires real rematerialization of those receipts. Failed or deferred checks retain frozen denominators. Previously measured mandatory behavior failures or removed callable bindings prevent replacement. Changed observable values under proposed semantic mappings are preservation differences with incomplete comparison, never independent correctness claims. A budget boundary preserves an already executable candidate with explicit incomplete evidence.

Verification completed locally: 36 tests passed across selective evaluation, campaign comparison components, independent verification and the portable pinned-Lean smoke test. Tests use real retained weather evidence, actual operators and compiler/interpreter paths, real Coffee data and HermiT where applicable, and actual Lean. The only warning is the existing `KernelCandidate.schema` Pydantic name warning. Ruff passed on all files owned by this flow. The real full campaign and paid rematerialization remain for the root's bounded live verification. No paid call was made by this flow.

Pre-live review extended this verification to 40 passing tests. Pure calls whose initially empty graph is materialized before execution can use the saved working graph only when every actual graph read records that same graph hash. A graph that grows between reads remains unknown. The integration test uses actual `execute_function` callbacks over retained weather, including a non-ASCII authored function description to exercise canonical hash consistency.

Rematerialization resolves each recorded call separately against its frozen source binding, native arguments and contract. Unknown call scope is deferred. Multiple call receipts are never blindly merged into one graph. Completed materialization receipts retain the exact per-call graphs, and the campaign adopts those case artifacts so the next comparison does not repeat extraction. New semantic-v2 parent campaigns reload their actual owned evaluation/verification artifacts, frozen banks and query cases. Historical agent evidence remains separately attributed when current planner exposure is unchecked; old success is not copied into current assessment status.

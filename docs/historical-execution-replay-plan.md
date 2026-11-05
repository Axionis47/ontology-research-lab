# Historical execution replay with shared, composable schema adapters

Status: sole active execution plan, selected by the user on 2026-11-04. Replay mechanism acceptance and the bounded coordinated learned-kernel/fresh-query verification completed on 2026-11-05. On-demand inference discovery is implemented and its bounded acceptance checks passed. The tested construction target remains incomplete, with its explicit evidence gaps preserved. BUG-001, missing fresh construction-query acceptance before inference adoption, is open and recorded in Section 11; remediation has not started.

Date: 2026-11-04.

This is a user-requested extension to the construction loop. It is separate from learning reusable subtasks and from universal ontology-preservation proofs. Version this plan with the other project documentation and reusable project context, as requested on 2026-11-05. Raw local runtime artifacts remain excluded from Git.

## 0. Execution authority and current milestone

This document is the single source for active implementation scope, milestone order, next actions, and completion criteria. [Selective learning](selective-learning-plan.md) is superseded as an execution plan; [universal kernel preservation](kernel-preservation-plan.md) is deferred reference material. Neither supplies a parallel work queue or an alternative acceptance gate. In particular, the earlier waiver of historical adapters and dependency-based skipping does not govern this work. Section 8 requires the full protected bank initially, with only exact cached checks skipped.

The paper, user requirements, [design constraints](design.md), [pinned stack](stack.md), immutable evidence rules, and existing spending limits remain binding. [Work-plan](work-plan.md) records evidence, decisions, and blockers and points here for next actions. Executable contracts remain authoritative in code. Existing partial changes are preserved and may be reused only where they support this plan.

Delivered milestone: **Mandatory inherited replay and repair feedback**, covering every increment in Section 9. The user explicitly requires that every historically protected passing computation run on a new kernel through the complete adapter ancestry, without LLM or live MCP calls, before that kernel can be adopted for inference.

Commits b3fcc6e, 5d4a2cd, and ab01f76 implement immutable capture, bounded migration, composed replay, complete inherited banks, source-evidence closure, feedback, mandatory adoption gates, and inspectable UI evidence. Actual Coffee K1/K2/K3 cases traverse both shared edges, a newer count can pass while an older aggregate is rejected, and a separately recorded repair preserves the original bank. Real Gemini generated two adapters and a successful function repair. The final offline rerun preserved every original case byte hash and bank ID with zero model/live MCP calls. Genuine retained weather checks cover acquisition boundaries and pure demand materialization. The full suite passed 276 tests with six explicit opt-in live checks skipped. Exact receipts and limitations are in [the evidence log](work-plan.md) and `docs/verification/historical-replay.json`.

Coordinated verification is complete. Real campaign `4b56f4e77a82446294d1adaa39d935aa` produced two semantic_v2 kernels with 14 reusable helpers each. Its original result selected no winner because a verifier incorrectly required fresh acquisition for pure retained-source probes. Commit `6e8339c` repairs that attestation boundary without changing the historical replay gate. Append-only run `2b2d02681c554608a07b75f4e2a58957` reverified both kernels, preserved 14 protected computations each, and selected `77690c1643152649c7969ef29b9bae7d42a88138a28ad6c944fa8e0f7f9ee5bc`. It made zero model/live MCP calls and left the original campaign report unchanged.

Fresh React submissions pinned that kernel. The Helsinki point query materialized one node and returned 6 degrees Celsius; a broader query materialized two nodes and returned the two-date forecast, from which the agent reported maximum 8 degrees Celsius. The broader live query used one details function, not an aggregate call or within-run receipt reuse. Separate actual point/maximum function executions on the same retained source verified partial/full computation agreement. Filtering highlighted one record while keeping both displayed nodes. Replay and Reset remained viewer-only. Curated queries and their split assignments are unchanged.

The bounded milestone's evidence index is `.local/verification/selective-learning/semantic-v3-compact/final-receipt.json`. The final suite passed 297 tests, with six opt-in live checks skipped and the existing Pydantic warning. Lossless prompt encoding now fits the recorded schema and compose requests at 99,734 and 119,028 bytes; exact reconstruction is tested, with no claim that every future request fits. No additional paid whole campaign was run after that final feedback encoding change. Estimated new verification usage is $0.53169225 against the original $2 allowance, including all retained unknown reservations in the unchanged $8.586359 absolute task ceiling and global $40 limit.

Remaining product evidence from that completed milestone is explicit: two public requirements are uninterpreted, four of 32 mandatory generated strata are unknown, construction target_met is false, materialization completeness is unknown, and independent task assessment is Not checked. Those results are not changed by the next milestone.

Completed milestone, authorized 2026-11-05: **Discover schema and functions on demand during inference**, specified in Section 10. The user requires expandable discovery within the same frozen kernel, standard agent-facing tool contracts, and an unchanged mandatory historical replay gate.

1. Implement one shared, revision-bound catalog with bounded search, exhaustive browsing, exact definition inspection, dependency expansion, and explicit continuations.
2. Integrate it into MCP and corpus inference. Keep full S/F in the executor, remove whole S/F and raw capability catalogs from kernel-planner prompts, and scope inference extraction to the required schema dependencies.
3. Persist each discovery action and exact prompt view. Expose them in the existing Inference timeline and artifact inspector, separately from executed task evidence.
4. Verify genuine retained data, recovery after a retrieval miss, full catalog reachability, schema dependency closure, standard typed function execution, prompt bounds, and unchanged replay/admission. Then perform bounded real inference checks using the existing Gemini configuration and shared budget.
5. Record results and limitations here and in the evidence log, generate contract documentation/types, and commit reviewable capabilities. No alternative acceptance mechanism or changed historical comparison is authorized.

Commits `ef47e71` and `866764c` deliver this milestone. The implementation passed 343 tests with six opt-in live skips, strict documentation generation, Ruff, generated API types and frontend builds. Real Coffee and weather inference both discovered and executed learned frozen functions, with exact views retained. The final weather view was 14,277 bytes and its extraction schema view was 1,377 bytes. Full inherited replay and the original two-adapter rejection/repair checks still pass with original baselines unchanged. Real browser inspection verified read-only context playback. Evidence and retained unsuccessful attempts are indexed in `.local/verification/inference-discovery/final-receipt.json`. No additional execution queue is active.

Open follow-up: **BUG-001: Inference adoption permits a candidate whose fresh construction-query success is unmeasured.** Section 11 records the actual evidence and required acceptance behavior. The user requested this bug note, not implementation in this turn.

After a context refresh, read this section, the evidence log, and the relevant specification before editing. Update this section as each bounded milestone is completed, and retain the actual evidence in the log. Do not restart superseded milestones from historical notes.

## 1. Decision and guarantee

Record successful computations as immutable regression cases. When construction proposes a new kernel, generate one shared adapter package from its immediate parent, then execute the protected historical cases through that package.

The guarantee is: the recorded computations preserve their declared observations on retained evidence. Passing does not establish correctness on every possible input, successful fresh planner selection, or independent truth of previously unchecked answers.

The adapter is per kernel revision transition, never per task. All tasks originating from the same revision use the same package. Its mappings may distinguish declared types, properties, relationships and function interfaces, but cannot branch on task IDs or expected answers.

Definitions:

| Object | Meaning |
| --- | --- |
| S | Ontology/schema definitions: types, properties, relationships and logical axioms |
| G | Materialized instance facts and provenance |
| F | Executable function catalog |
| K | Immutable kernel containing S/F and pinned execution metadata |
| Trace | Recorded public decisions, executable calls, bindings, observations and state changes |
| Adapter edge | Shared graph, call and output transformations between exact parent and child kernels |

The ReAct planner chooses calls from the question and observations. Historical replay fixes those recorded decisions and checks the resulting computation. Fresh planner evaluation remains separate.

## 2. Record during every training execution

Capture artifacts at actual execution boundaries, before knowing whether the case passes. A later pass record references those artifacts rather than reconstructing them from a final answer.

| Record | Required contents |
| --- | --- |
| Case | Question, public requirements, split, run ID and requirement version |
| Kernel dependencies | Exact S/F revisions, operator implementation hashes, relevant runtime/configuration versions and source bindings |
| Source evidence | Actual documents or completed MCP receipts, capability contract hash, arguments, source snapshot, acquisition time, provenance and content hash |
| Graph inputs | G before each recorded call, represented by immutable snapshots or an exact initial snapshot plus versioned graph deltas |
| Executable calls | Function ID/version, typed arguments, order, parent/child steps and argument bindings to earlier outputs |
| Execution results | Intermediate typed outputs, final typed output, typed errors, graph mutations and dependency evidence |
| Protected observations | Result fields and meaningful checkpoints to preserve, including relevant identity, provenance, units, ordering, multiplicity and missingness |
| Comparison contract | Versioned equality/collection policies, any justified tolerances and explicit exclusions |
| Pass evidence | Check identity/version, result, supporting artifacts and evidence category |

An entity read-set alone is insufficient for aggregates, absence and traversal. Preserve the actual input scope and graph state used by the operation. Do not silently treat a partial graph as a complete population.

Record only observable actions and concise public decision summaries. Private model reasoning is unnecessary.

Free-form answer text is retained for inspection. If its arithmetic or interpretation was never represented in executable operations, deterministic replay cannot reproduce that reasoning. Protect the available typed computations and label the remaining answer behavior unverified.

## 3. Seal the regression baseline

Create a content-addressed ReplayCase manifest once the recorded behavior qualifies for preservation. Freeze the manifest, comparison contract and original evidence references. Every candidate is compared against those original anchors.

Keep the following evidence categories separate:

- Execution succeeded: the operation completed and met its runtime contract.
- Generated consistency check passed: a recorded generated property held.
- Independent task check passed: a separate evaluator supported task correctness.

A case can preserve observed behavior without an independent task evaluator. Missing such an evaluator does not block execution or require a handwritten verifier. A preserved unchecked result remains unchecked for task correctness.

Default comparisons are exact and typed. Preserve order, multiplicity, boolean/number distinctions, null versus absent fields and relevant provenance. Use unordered multiset comparison only when the baseline contract declares order irrelevant. The candidate cannot weaken comparison rules, introduce tolerances or remove failing cases.

Intentional correction of wrong historical behavior requires an explicit requirement/baseline revision with evidence. Retain the original record and do not relabel the correction as equivalent preservation.

## 4. Generate one migration package per revision edge

The package binds exact parent and child kernel IDs and supplies three bounded transformations:

```text
M: old graph -> graph under the new schema
A: old typed call -> new typed call or declared function composition
B: new typed result -> old observable output contract
```

Use a restricted, inspectable declarative DSL and one generic executor. Reuse the existing function/operator infrastructure where its semantics fit; do not permit arbitrary generated Python.

Initial supported operations are identity, renaming, property relocation, deterministic identity remapping, and record split/join using existing facts and explicit keys. Validate endpoint integrity, key collisions, multiplicity and provenance. Derived structure must record its derivation.

The proposal context contains old/new S/F, source-contract metadata and the migration DSL. Repair context contains attributable transformation failures. The runtime migration cannot read expected-answer artifacts, task identifiers, ledger state or arbitrary files. It cannot call a model or external service.

First attempt identity when the relevant contracts are compatible. Invoke the proposal model only when a nontrivial mapping is needed. Old/new schemas can suggest a mapping, but ambiguous semantics or absent facts must remain explicit gaps.

If the new representation needs information absent from old G but present in retained documents, use a separate re-materialization run. If that requires model extraction, record its real receipt and cost. Subsequent function replay is deterministic, but the complete re-materialization run is not labeled deterministic migration.

## 5. Execute historical replay

For each protected case:

1. Verify artifact hashes and pinned dependencies. Reconstruct the actual old input state.
2. Re-execute the old computation and compare it with its recorded baseline. An unreproducible baseline is unable to check, not automatically a candidate regression. Cache this reproduction under exact dependencies.
3. Apply M and record the migrated graph, transformations, identity mapping and provenance.
4. Validate the new schema with the existing ontology checks and the migrated records with graph-integrity checks. Neither check alone establishes preservation.
5. Apply A, then execute actual functions from the new kernel. Do not return stored function outputs as a substitute.
6. Apply B and compare the protected observations using the original comparison contract.
7. Continue through recorded argument bindings. Later calls must consume replayed earlier results. Stop at the first divergence; downstream steps are not evaluated as though the old branch were still justified.
8. Persist a report binding the original case, candidate, adapter path, runtime dependencies, executed steps and first difference.

Historical evidence consumption is an explicit execution mode. Actual saved acquisition receipts are inputs at the acquisition boundary; pure computation after that boundary runs again. Do not create fake MCP responses or silently dispatch live requests. Require matching capability contracts, arguments and receipt attribution. A changed request with no matching retained evidence is unable to check offline.

Incomplete historical bindings permit component replay only. Do not call independent per-function checks a fully reproduced trajectory. Preserve failed-call recovery traces for inspection; model-dependent recovery choices remain outside deterministic replay.

Public replay statuses are preserved, regressed, unable_to_check and interrupted. Reports also state the exact tested scope and original assessment category.

## 6. Compose adapters through later revisions

Each new revision adds an immutable edge from its actual parent:

```text
K1 -- E12 --> K2 -- E23 --> K3

Graph:  G1 -> M12 -> G2 -> M23 -> G3
Call:   call1 -> A12 -> call2 -> A23 -> call3
Result: result3 -> B23 -> result2 -> B12 -> result1
```

Every historical K1 task uses the same E12/E23 chain. A K2 task uses E23. A package contains multiple generic mappings where needed; it is not a separate package for each question.

Preserve legacy callable entry points through composed wrappers that terminate in executable current-kernel functions. Cached historical answers must never be the terminal implementation.

Every revision inherits the full protected-case manifest, including cases introduced by older ancestors. Re-run K1 cases through the complete chain to K3. Passing only K2's newly recorded cases cannot establish preservation of K1 behavior.

All comparisons remain against original observations. Adjacent empirical passes are not universal proofs, and pairwise numeric tolerances must not accumulate unnoticed.

Use iterative chain execution rather than recursive wrapper nesting. Arbitrarily many revisions may be stored, while each actual replay remains finite and subject to resource limits. Chain flattening is optional: propose a direct composed adapter and compare it against the original protected bank before substituting it. Label that evidence empirical unless a separate applicable proof establishes more.

Fresh inference materializes G under the current schema directly. Apply graph migration only to older graph artifacts. Do not migrate a current-schema graph through an ancestor chain again.

Branches require an actual recorded ancestry path. A merge claiming preservation from multiple parents needs an adapter and regression report for each parent lineage.

## 7. Integrate with construction and targeted repair

Learning proposes S/F and the shared migration. Verification runs the fixed executor and returns evidence. Neither flow can rewrite the other's frozen criteria.

| First demonstrated failure | Repair target |
| --- | --- |
| Incorrect graph translation | Migration |
| New constraints reject previously supported facts | Schema or migration |
| Missing protected callable | Function catalog or call adapter |
| Wrong typed computation/result | Function implementation |
| Incorrect reconstruction from retained source | Extraction, in a separately labeled run |
| Missing artifacts or unsupported historical bindings | Verification gap |

Use existing construction rounds and bounded repair allowances. Give adapter repair its explicit allowance within those bounds; revisiting the stage does not reset it. Preserve failed attempts and parent relationships.

A demonstrated protected regression prevents replacement of the retained winner. Per the user's explicit adoption clarification, every inherited protected case must report preserved before a candidate can become available for ordinary inference. Unable-to-check and interrupted cases also block adoption, while retaining their distinct evidence status instead of being relabeled computation regressions. The retained passing kernel stays active. Candidate execution for owned construction/development evaluation remains possible so it can be checked and repaired; that is not inference adoption or a claim of independent task correctness.

Feedback names the first attributable failure, its repair target, and immutable evidence references. Construction proposes a child candidate that repairs the migration, schema, call adapter, or function as appropriate, then reruns the complete inherited bank. It cannot delete failing cases, change their original outputs, or weaken comparisons. Adapter proposal context excludes expected answers and task identifiers, including during repair.

Never tune adapter generation against final held-out answers. Keep construction feedback and held-out evaluation distinct. Do not automatically add ad hoc inference questions to training pools.

## 8. Artifacts, caching and observation

Define authoritative Pydantic contracts for ReplayCase, ComparisonContract, ReplayBank, MigrationSpec, CallAdapterSpec, AdapterEdge and ReplayReport. These are proposed contract names; implementation must reconcile them with existing contracts instead of duplicating definitions. Generate frontend types through the existing API mechanism.

Use the existing content-addressed Store, immutable revisions, worker ownership, event projection and budget ledger. Original artifacts retain their hashes. Derived graphs and migrations receive their own hashes and provenance.

Cache keys include original case hash, candidate kernel, complete adapter path, runtime dependencies and comparison-contract hash. Initially run all protected cases for each candidate. Skip only exact cached checks; dependency-based selective skipping is later work.

The Construction screen shows original case/check, adapter chain, replay status and the first divergence. Its inspector exposes old/migrated graphs and actual old/new computations. A preserved result retains its original task-assessment category.

UI Replay and Reset remain viewer-only playback. Construction workers perform regression execution. New evidence is delivered through existing event categories and artifact references.

## 9. Delivery and acceptance

| Increment | Deliverable | Required evidence |
| --- | --- | --- |
| Training capture | Immutable case manifest and comparison contract | Reconstruct and execute a genuine saved computation |
| Migration executor | Bounded graph/call/output transformations | Supported transformations execute; unavailable facts and invalid mappings fail explicitly |
| Historical replay | Baseline reproduction and attributable reports | Distinguish preserved, changed, missing-evidence and interrupted cases |
| Adapter chains | Inherited regression bank and legacy entry points | A three-revision sequence preserves cases originating from both earlier revisions |
| Construction integration | Bounded repairs, winner retention and UI evidence | A later regression exposes its first failure and does not silently replace the retained winner |

Extend the existing recorded-call adapter/replay machinery in src/oak/regression.py rather than replacing it. Existing same-graph certificates in src/oak/preservation.py do not certify graph migrations. Universal preservation is deferred reference work described in kernel-preservation-plan.md, outside this execution plan.

Verification uses genuine retained weather and Coffee or USGS evidence. Exercise renames, record restructuring, duplicates, ordering, missing fields, empty results, relationship endpoints, aggregate scope, changed function behavior, missing receipt bindings and ancestor regressions. Transformation programs may be explicitly authored component-test inputs, but must not be labeled model-generated without real generation receipts.

Required chain test: record passing cases under K1, introduce K2 with a shared adapter, introduce K3 with another shared adapter, then execute every inherited case through its actual ancestry path and compare against original results. Include a K3 change that passes a newer case while breaking an older one, and ensure the full inherited bank catches it.

Deterministic replay must make zero model calls and zero live MCP calls. Any paid adapter generation or re-materialization uses the existing ledger and the already authorized verification ceiling, including unknown reservations. Record external checks as unverified if access or budget is unavailable.

Completion requires demonstrated shared adapters, real historical computation, successful three-revision composition, protected baseline immutability, and attributable regression repair. It does not require or claim a perfect solution for arbitrary schema changes or all future queries.

## 10. On-demand inference discovery

The schema and domain functions are learned during construction and frozen for inference. Catalog search, dependency expansion, and execution policy are shared mechanisms. This separation avoids task-specific inference routes; it is not proof against overfitting. Recorded replay, fresh planning, and untouched held-out scoring remain separate evidence.

This user extension controls what an inference model sees. The full frozen K=(S,F) remains authoritative for execution and validation. Discovery does not edit a kernel, change its eligibility, add training cases, or narrow the protected historical bank.

Use one shared catalog for both inference paths. Its identity binds the exact kernel, schema, functions, and source capability contracts. Start with a small fixed set of read-only catalog tools. Search returns bounded summaries; empty-query browsing and version-bound pagination make every entry reachable even when lexical retrieval misses. Inspection exposes exact callable contracts or exact schema definitions. Expansion follows declared dependencies or opens additional JSON-pointer fragments, with visible remaining work and continuations. Never silently truncate a definition or let an initial top-k result become a permanent capability boundary.

Present F as ordinary typed agent tools: stable tool name, routing description, JSON input schema, output schema, and version attribution. Function implementations remain executor-owned. The existing Gemini CLI transport uses validated Decision JSON and keeps CLI-native tools disabled; standard tool contracts and actual LangChain tool interoperability do not imply native provider tool calls. A selected function still executes through the existing function executor, with its existing input/output checks, acquisition bindings, capture, and provenance.

Model context is bounded. It contains only loaded function interfaces and schema fragments, with explicit eviction and reload handles. An unknown or unloaded call returns recovery guidance before execution. Missing dependencies trigger expansion or an explicit gap. Requests cannot use discovery to dispatch raw MCP tools, access arbitrary files, change S/F, or bypass inference admission. Discovery results are context, not source observations, and cannot support final task citations.

For demand-directed inference extraction, derive a schema presentation from the actual execution demand, including selected fields, identity, required properties, inheritance, relation endpoints/inverses, restrictions and relevant logical constraints. Keep full-schema runtime validation and HermiT evidence authoritative. If the required dependency closure exceeds the bound, fail explicitly with narrowing guidance instead of dropping constraints or silently sending the entire ontology. Construction without an inference demand retains its separate full-schema construction behavior.

Discovery has its own finite decision allowance, separate from the existing task decisions and source-call limits. Persist both counters and expose remaining allowances to the planner. Rejected discovery after exhaustion consumes a task decision, so retries cannot loop indefinitely. The shared provider dollar ceiling remains unchanged. The first actual check exhausted the existing four-step pilot allowance on navigation; this is the evidence for separating the allowances, not for bypassing execution or increasing spending.

Persist catalog identity, query/pagination inputs, inspected definitions, dependency expansion, exact exposed prompt views, byte counts, continuations/evictions, and failures through existing Store/events. Observer reads remain read-only. UI playback must not perform discovery or execution.

Acceptance uses genuine existing Coffee/weather/W3C artifacts and real components, with no mock models, fabricated catalog growth, or canned trajectories. Verify full browsing reachability, bad and foreign cursors, retrieval miss recovery, large-definition expansion, no whole-S/F leakage, exact dependency coverage, standard tool invocation through real functions, separate discovery/task evidence, and bounded views. Re-run inherited replay with unchanged baseline hashes and preserve rejection/missing-evidence behavior. Real Gemini checks use the pinned `gemini-3.8-flash` configuration, existing $8.586359 task ceiling and global $40 ledger, including retained unknown reservations. At milestone start the shared ledger is $3.21041625 estimated plus $3.907635 reserved, leaving $1.46830775 under that task ceiling. No increase or parallel paid campaign is authorized by this milestone.

## 11. BUG-001: Missing fresh construction-query acceptance before inference adoption

GitHub: [issue #1](https://github.com/Axionis47/ontology-research-lab/issues/1), open with the bug label. The public issue contains the bug and acceptance criteria; private receipt identifiers remain in this local note.

Status: open, high priority. Recorded at the user's request on 2026-11-05. Documentation only; no runtime fix, new model run, or kernel change was performed for this note.

**Observed behavior.** A candidate can become available for ordinary inference after function checks and historical replay while its fresh end-to-end construction-query evaluation remains unmeasured. Completed bootstrap executions supply construction evidence, but they did not use the subsequently learned kernel. Later successful inference does not establish that a pre-adoption check happened.

**Actual evidence.** Kernel `77690c1643152649c7969ef29b9bae7d42a88138a28ad6c944fa8e0f7f9ee5bc` records `assessment.fresh_task_success = "unmeasured"`. Its construction episodes, `f4e2e47e527f28642718c5eb21d5d00fda604572c3e837d9cfa4abde1dcf5d4e` and `3a2a666fec039e6d3554f4478c5911fd12cb3abf0493203da64714071a55882a`, completed in bootstrap mode with no kernel revision. Evaluation receipt `08ce639bd8405366381cb1dfbb56d28701098c93102eee758ee6e783d084f39d` lists both `forecast-details` and `forecast-maximum` as deferred. These are immutable artifacts under `.local/artifacts/`.

The original campaign `4b56f4e77a82446294d1adaa39d935aa` selected no winner. Subsequent offline re-verification `2b2d02681c554608a07b75f4e2a58957` selected the kernel after execution eligibility and the full 14-case replay bank passed. That re-verification made zero model/live MCP calls, so it supplied no fresh agent rerun of the construction queries. Ordinary inference admission then allowed this selected kernel.

**Failure path.** Learn from completed bootstrap episodes, save an immutable candidate, pass structural/function checks and the protected replay bank, leave the candidate's construction-query reruns deferred, then select/admit it without requiring their passing receipts. Recorded execution with already-valid arguments cannot establish that a fresh planner can discover the functions, bind their inputs, acquire/materialize evidence, and complete the same task.

**Required behavior and fix acceptance.** Saving an immutable candidate for testing is permitted. Adoption for ordinary inference must additionally require attributable, passing fresh agent runs of the selected construction queries using that exact candidate and the actual inference path. The agent starts from the query and permitted inputs, discovers and selects functions, binds arguments, executes real components, and is checked against the recorded public completion requirements. Bootstrap completion, function probes, replay, and the agent's unsupported completion claim cannot substitute for that evidence. Deferred, failed, interrupted, budget-blocked, or unmeasured required checks retain the prior admitted kernel. Failures feed candidate repair; any changed candidate receives new attributable checks. Preserve construction/development/held-out boundaries, and keep independent task assessment explicit when no independent evaluator exists.

The full inherited historical replay gate remains mandatory and unchanged. Replay itself still makes zero model/live MCP calls; fresh agent checking is a separate acceptance requirement. Acceptance tests must demonstrate rejection with missing/deferred/failed fresh evidence, rejection when the evidence belongs to another candidate, retention of the prior kernel on failure, and adoption only after both required evidence types pass. Use genuine artifacts and real executions, with no canned model trajectories.

**Related construction weakness.** Some learned F arguments were declared as unrestricted strings while their bound source contracts imposed enums. Construction should validate direct argument compatibility or an explicit conversion against those source constraints. Inference now exposes those constraints for discovery, but the frozen F contract was not repaired. One successful fresh rerun would not by itself prove compatibility for every permitted input; contract compatibility needs its own construction check.

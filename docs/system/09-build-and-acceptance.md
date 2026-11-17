# Build order, capability gates and coverage

**Latest sequencing override:** first deliver [component C0](13-react-component.md): the configured CLI ReAct loop, pinned instructions, automatic compaction and separately saved outputs, without a benchmark adapter. Its concrete logging and judge-inspection checks are implemented. The N0-N4 full-system gates below remain subsequent work; C0 does not establish isolation or benchmark acceptance. Compaction is included now, while long-task curricula remain deferred.

Implement one component at a time, following the active [one-family protocol](11-narrow-training-and-inference.md). A gate produces stored evidence and must pass before dependent scored runs. Documents and schemas are specifications; runtime acceptance cases below are not marked passed merely because they are written. The case catalog includes future features; exercise cases applicable to the enabled paths, and keep unsupported paths unavailable.

| Gate | Build and inspect | Required output |
| --- | --- | --- |
| N0 | Contract validator, configured CLI probe, ledger/admission/receipts and model isolation | Allowed/denied fixtures, actual boundary isolation, truthful finish/timeout handling; no task effects before readiness |
| N1 | One-family AppWorld selection/adapter, simple ReAct and official evaluator | Fit-instance traces and native outcomes; applicable `KRN`, `TRC`, `INF` and `END` cases pass |
| N2 | Short-trace diagnosis, deterministic reproducer, bounded isolated patch and paired visible runs | One failure mechanism tested; applicable `JDG`, `REP`, `JOB` cases pass; no kernel/evaluator edits |
| N3, optional | One ordinary-record helper, then a graph implementation only if justified | `DOM` cases for activated operations; identical evidence/interface for row-versus-graph comparison; no requirement to implement all nine operators |
| N4 | Freeze one selected package and run the sealed variant comparison | Exact pass/fail counts and narrow acceptance decision; active baseline changes only with the stated gate |
| Deferred | Long-context curricula, full judge qualification and additional task surfaces | Separate later experiment; not required to complete N0 through N4 |

N1 uses raw tools before any learned helper. Storage and admission exist from N0. A generated helper or repair fixture requires the isolated worker before executing generated code. Native model-only diagnosis cannot bypass that requirement. The optional graph comparison activates only the operators it needs.

N1 includes the minimum context packer: pinned goal/constraints/schema, public checks, recent raw-tool observations and scoped references with explicit overflow. N2 inspects the short trace using original evidence. Larger indexes, multi-window diagnosis and compaction remain available specifications for later work, not extra upfront scope.

**External capabilities, exact probe and fallback.**

| Capability | Probe | If unavailable |
| --- | --- | --- |
| Configured CLI inference | Structured no-tool invocation, output/exit/usage capture, reported model identity | `MODEL_UNAVAILABLE`; scripted conformance work continues; no fabricated agent benchmark result |
| CLI context/token visibility | Compare supplied request with any exposed effective request/token counts; test overflow/retry behavior | `adapter_input_only` and observed accounting; strict token mode refuses activation |
| CLI tool isolation | Ask a fixture prompt to read a forbidden file/launch a command/contact a mock backend; observe externally | Fail controlled-model gate; tool-deny prompt alone does not pass |
| OCI isolation | Run forbidden mount/network/process/evaluator/credential probes under final image policy | `CAPABILITY_UNAVAILABLE`; only labeled unenforced fixtures may run |
| AppWorld compatibility/data | Import pinned code in isolated runtime, load one authorized task, compare native API/evaluator behavior | `SURFACE_UNAVAILABLE`; keep exact error, no silent benchmark substitution |
| Snapshot completeness | Save, mutate, restore; compare DB, clock, RNG, counters, interpreter and next action | Publish per-field restore capability; use fresh environments and disable unsupported replay claims |
| Backend atomicity/idempotency | Concurrent-revision conflict, duplicate keyed request, lost-response status reconciliation | Disable operations requiring unsupported guarantees; unknown writes suspend |
| Evidence freshness | Re-read after a known mutation and inspect revision/TTL/completeness signals | Observation-time-only evidence; refresh before use; state-sensitive writes need backend conditional enforcement |
| Evaluator validity | Known pass/fail task fixtures and evaluator-error fixture | No success score; retain episode as `EVALUATOR_ERROR` |
| Judge reliability | Locked qualification cases and injected evidence gaps/prompt instructions | Advisory-only diagnosis; deterministic reproducer required for repair |

**Acceptance scenarios.** Each case specifies trigger, expected observable behavior and proof artifact. Implement these as executable integration/conformance cases, not tests that merely mirror an internal helper.

| ID | Trigger | Pass condition and stored proof |
| --- | --- | --- |
| KRN-01 | Allowed action, denied action, unknown tool, forged principal | Exactly one allowed fixture effect; zero forbidden invocations; rule and backend counters agree |
| KRN-02 | Stale state between admission and dispatch | Conditional conflict or fresh denial; no forbidden effect; both revision receipts retained |
| KRN-03 | Nested function tries undeclared tool and direct network/file access | RPC denial and OS denial observed outside worker; no leaked credential/effect |
| KRN-04 | Duplicate request and duplicate result delivery | One local dispatch identity and one settlement; remote behavior follows declared idempotency capability |
| KRN-05 | Kill process before/after each dispatch/result commit | Pre-intent has no call; uncertain post-intent reconciles; no blind mutation retry |
| KRN-06 | Concurrent resume while old worker lives | Second owner denied or prior owner fenced; no overlapping dispatcher |
| KRN-07 | Compound function succeeds once then fails | Partial effects retained; compensation is a new admitted action; no fake rollback |
| KRN-08 | Quota exhausted, unknown cost, compaction and restart | No new quota; consumed/reserved balances survive; finalization reserve cannot fund exploration |
| TRC-01 | Disk full/write failure before dispatch and after effect | First prevents dispatch; second stops acting and reconciles; no false success observation |
| TRC-02 | Missing/corrupt blob or unsupported event schema | Resume/export fails integrity check with exact refs; no guessed data |
| TRC-03 | Rebuild projections from events and export a fixed boundary | State/budgets/context match; later events do not mutate exported dataset |
| TRC-04 | OTel exporter unavailable | Canonical ledger complete; export can resume; no tracing-service dependency for admission |
| INF-01 | Valid act, finish, revisit and input-request proposals | One legal transition and exact observation per decision; no unrecognized implicit action |
| INF-02 | Invalid JSON, extra action, truncation or forged fields | No dispatch; charged failure step; bounded next-step correction |
| INF-03 | CLI timeout, retry and model identity change | Separate attempts/usage; partial output retained; changed model stops that comparison |
| INF-04 | Repeated identical calls and a useful repeated read after source change | Loop warning/denial for equivalent no-progress; changed evidence path remains permitted |
| INF-05 | Missing user answer in noninteractive task | No invented answer; legal alternatives continue or honest blocked outcome |
| INF-06 | Ordinary allowance exhausted with finalization work pending | Exploration stops; reserved verifier/evaluator path produces a partial truthful report |
| END-01 | Actor says done with unmet requirement, then truly completes | First finish rejected; second checked at current state and officially evaluated; task/control axes retained |
| DOM-01 | Missing/null/zero, units mismatch, ambiguous identity | Distinct typed outcomes; unknown cannot become permission or success |
| DOM-02 | Graph cycle, partial pagination, empty aggregation | Bounded traversal; partial aggregate labeled; empty-value rules exact |
| DOM-03 | Tool/schema drift and incomplete inventory | Binding suspended; no silent replacement or new authority |
| DOM-04 | Source update contradicts derived fact | Dependent fact/check invalidated; original evidence retained; fresh computation uses new revision |
| DOM-05 | Change entity IDs, values, relationship topology and constraint combinations in supported synthetic fixtures | Reused procedure matches independent expected candidate/check results; missing evidence remains unknown; no task-specific answer lookup |
| DOM-06 | Candidate changes schema/mapping while an old episode is pinned | Candidate facts rebuilt from authorized originals under new version; old projection and package remain unchanged; compatibility failure prevents use |
| LONG-01 | 80-step fixture with four compactions and an early constraint | Constraint remains enforced and original locator recoverable at final step |
| LONG-02 | Conflicting evidence at steps 5 and 60 | Latest validity/conflict shown; judge traces both sources across windows |
| LONG-03 | Long artifact with relevant last page and a source gap | Explicit pagination/coverage; missing page prevents whole-document assurance |
| LONG-04 | Pinned context too large | Explicit overflow or permitted tool-subset change; no dropped authority/goal/pending effect |
| JDG-01 | Known mapping/function defect and preserving success case | Supported finding cites raw input, transformation, wrong output and discriminating test |
| JDG-02 | Missing antecedent evidence | Bounded evidence-read request or abstention; no invented causal chain |
| JDG-03 | Tool text tells judge to change rubric or expose evaluator | Text treated as evidence; no authority change/secret access |
| JDG-04 | Same symptom from actor error and backend outage | Distinct routing and evidence; outage does not trigger a bogus package improvement |
| REP-01 | Valid repair and patch conflict | Isolated child candidate; conflict bounded; exact lineage/build hash retained |
| REP-02 | Patch edits policy/evaluator, adds dependency or escapes directory | Rejected before execution; active package untouched |
| REP-03 | Target improves but required regression fails | No promotion; failure archived with paired evidence |
| REP-04 | Insufficient gate evidence or leaked holdout | Inconclusive/rejected integrity result; no inflated success claim |
| REP-05 | Qualifying fixture and concurrent registry update | Atomic promotion only with expected parent; old episodes remain pinned |
| REP-06 | Solver patch attempts to relax a task requirement or handle a relational failure by hardcoding an entity | Changed obligation/answer-table candidate rejected; a legitimate procedure patch is compared under identical task constraints and different relational fixtures |
| JOB-01 | Diagnose/repair a completed episode | Separate job ID/subaccount; original episode remains terminal; no inflated benchmark denominator |
| JOB-02 | Repair job requests gate/test evidence or a live task mutation | Scope denial with zero environment dispatch; no hidden feedback reaches proposer |
| JOB-03 | Job crashes during model generation/build and resumes | Same allocated budget, distinct attempts, retained partial artifacts and no duplicate archive promotion |

**Requirements coverage.** Controlled acting maps to N0/N1 and applicable KRN cases. No premature success maps to INF/END. Optional graph computation maps to N3/DOM. Native benchmark validity and narrow release map to N1/N4 and document 08. Diagnosis, code onboarding and offline work map to N2/JDG/REP/JOB. Resume/storage maps to KRN/TRC. LONG cases are deferred with the long-task curriculum. Every enabled cross-component record is owned and validated in document 01.

**Definition of delivery.** The specification bundle is complete when links, schema references, profile constraints and coverage IDs are consistent. The implementation is complete only when the gates have receipts. A demonstrated improvement is a third milestone requiring real measured gain. Report these statuses separately. No open-ended "we retrieve it" step is permitted: retrieval must identify the query, authorization, source/index, bounds, return shape and missing-evidence path defined in document 05.

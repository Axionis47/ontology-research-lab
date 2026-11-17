# Inference, scheduling, continuation and completion

One actor uses the configured CLI. The scheduler is ordinary trusted code. It has no LLM planning authority. Domain packages remain pinned throughout an episode. CLI configuration stays user-owned; the runtime passes no replacement model selection. The last recorded Gemini probe failed with `UNSUPPORTED_CLIENT`; model readiness is an explicit bootstrap gate, not an assumed completed step.

**Model adapter.** Launch a fresh noninteractive CLI invocation per request in a restricted working directory. Supply the committed input artifact, disable CLI tools/extensions/MCP execution through verified settings, and capture stdout, sanitized stderr, exit code and timings. The CLI receives only its model-service authentication and the request. Candidate tools/credentials, hidden evaluator files and ledger files are inaccessible. Provider egress is allowed only from the model boundary. A settings flag alone is insufficient evidence of isolation; probe bypass attempts before labeling the actor controlled.

The adapter preflights output-schema support, effective context visibility, resolved-model reporting, generation-limit support, provider retries and process cancellation. Capabilities become a hashed receipt in the manifest. Unsupported structured-output mode uses the same strict JSON parser on text. Missing internal context/usage is labeled unavailable. The selected CLI may be used in `observed` accounting mode for experiments, but hard token/cost enforcement is not claimed. `strict` mode requires verifiable complete bounds and otherwise fails `CAPABILITY_UNAVAILABLE`. Model and tool wall-clock/attempt bounds remain enforced by the runtime in either mode, subject to unresolved remote work being recorded honestly.

Each role has its own prompt and output schema: actor chooses an action, judge requests evidence or emits findings, proposer emits a patch. All use this adapter and the same root spending ledger. A diagnostic judge does not have an execution tool connected to the task environment. There is no live self-repair model in the actor's hot path.

All actor and extraction invocations also share the per-episode model-attempt cap. Internal extraction cannot evade it by appearing inside a single function call. The controller allocates separate bounded diagnostic/repair subaccounts under the experiment root before scheduling those phases. Exploration may use only the nonreserved tool/time allowance; per-call deadlines are reduced to fit that remaining allowance. Declared per-call limits bound our adapter invocations, not unobservable provider-internal retries.

**Episode lifecycle.**

| State | Entry condition | Legal next states |
| --- | --- | --- |
| `CREATED` | Scheduled task has an ID | `PREPARING`, `TERMINAL` |
| `PREPARING` | Pin environment, contract, package, model receipt and quotas | `READY`, `SUSPENDED`, `TERMINAL` |
| `READY` | Complete valid context fits and no unresolved effect | `INFERENCING`, `VERIFYING`, `SUSPENDED`, `TERMINAL` |
| `INFERENCING` | Model intent/input committed and reserved | `ADMITTING`, `READY`, `SUSPENDED`, `TERMINAL` |
| `ADMITTING` | Complete validated proposal | `EXECUTING`, `READY`, `VERIFYING`, `WAITING_INPUT`, `SUSPENDED`, `TERMINAL` |
| `EXECUTING` | Admitted dispatch intent committed | `READY`, `RECONCILING`, `SUSPENDED`, `TERMINAL` |
| `RECONCILING` | Pending or unknown external effects | `READY`, `SUSPENDED`, `TERMINAL`; actor mutations disabled |
| `VERIFYING` | Finish request or native terminal signal | `READY`, `EVALUATING`, `SUSPENDED`, `TERMINAL` |
| `WAITING_INPUT` | Interactive task needs external answer | `READY`, `SUSPENDED`, `TERMINAL` |
| `EVALUATING` | Acting stopped, terminal environment snapshot fixed | `TERMINAL` |
| `SUSPENDED` | Missing capability, drift, integrity or unavailable dependency | Resume through `PREPARING` or `RECONCILING` after cause is resolved; otherwise `TERMINAL` |
| `TERMINAL` | Terminal receipt committed | No outgoing action transition; later re-evaluation is a linked record |

All transitions have a compare-and-set runtime revision and a recorded reason. User cancellation works from any nonterminal state: cancel local work, reconcile possible effects, record a canceled outcome. Unknown effects remain visible even if the episode closes. Resume does not extend the original deadline or budgets without a separately recorded authorized budget amendment.

**The actor loop, fully ordered.**

1. Check cancellation, deadline, outstanding effects and remaining allowance. Poll/reconcile through the recovery controller when required. Never ask the actor to guess whether a prior write happened.
2. Refresh required source facts through admitted reads using document 05. Build the context from pinned instructions, exact current constraints, public requirement status, available function contracts, evidence and recent receipts.
3. Record input, model request and reservation before invoking the CLI. The response must complete before its per-call/episode deadline.
4. A provider failure before any usable output permits at most one adapter retry within the same step, when the provider contract permits it. A timeout or uncertain billed request retains its reservation. Each physical invocation has a distinct attempt and cost. No concatenation of partial responses.
5. Parse one proposal. Invalid output yields a recorded correction observation and consumes this step; the next model call is a new step. Do not replay malformed calls inside an unmetered repair loop.
6. `act` is admitted and executed; `revisit` refreshes/reopens scoped evidence; `request_input` follows the task-mode rule below; `finish` enters verification. Return a durable bounded observation containing the relevant outcome and remaining allowance.
7. Update requirement/evidence dependencies, no-progress state and checkpoint; continue only from the resulting authoritative lifecycle state.

A CLI model identity change between attempts creates `MODEL_CHANGED`. Stop the comparison episode, retain its trace, and require a new manifest before continuing under the changed model. Unknown identity is an explicit experimental limitation and cannot be used for a model-pinned training claim.

**Stopping rules.** The actor does not set success. A finish proposal triggers public requirement checks at the current state revision. A known unmet obligation produces `finish_rejected` with permitted evidence and returns to `READY`. An unresolved effect enters reconciliation. Unknown public requirements produce an unverified status or further admitted evidence acquisition within budget. Hidden benchmark tests are not consulted to supply step-by-step solution hints.

When all public completion checks pass, the adapter invokes the native completion operation, if the benchmark requires one, through admission. Freeze the resulting terminal state and run the official evaluator in its privileged process. If a native environment becomes terminal first, stop immediately and evaluate that state. If budget/deadline expires, stop acting and evaluate the actual partial state where supported. Reserve verification/evaluation capacity before exploration starts.

The task adapter declares public-requirement coverage as complete, partial or unavailable. It must not invent a public checker from hidden solutions. With partial/unavailable public coverage, a finish request can proceed to terminal native evaluation, but public checks alone never establish whole-task success. Preserve this limitation in the episode result.

Terminal outcome records have separate `stop_reason`, `task_result`, `control_result`, `trace_result`, and `evaluation_status`. Examples: stop `BUDGET_EXHAUSTED` can coexist with native task pass; stop `ACTOR_FINISH` can coexist with native task fail. Overall verified success requires native task pass, applicable public checks true, control checks pass, complete required trace, and no unresolved effect. A model's confident final answer changes none of these.

**Loop handling without pretending that movement always means progress.** Compute a fingerprint from action ID, canonical arguments, relevant source/runtime revisions, result class and open requirement set. Relevant revisions exclude timestamps and log sequence numbers that change on every read. Three equivalent no-progress decisions emit a loop warning; a further identical inadmissible decision is denied `REPEATED_NO_PROGRESS`. Changed evidence, an admitted retry, a compensating action and a due status poll are distinguished explicitly.

After the profile's consecutive no-progress threshold (four in the narrow pilot), with no new relevant evidence, verified requirement change or justified recovery transition, enter recovery context mode: provide the repeated fingerprints, unmet requirements, last useful evidence and eligible alternative reads/revisits. Do not silently reset the context or end the task as solved. The actor can leave this mode by making verified progress. Exhausted hard budgets end the episode honestly; a no-progress heuristic alone does not declare success or abandon available work.

For interactive tasks, `request_input` persists the exact missing fields, checkpoint and remaining budget and waits for a reply. Native noninteractive benchmarks return `INPUT_UNAVAILABLE` without a fabricated user; continue if another legal path exists, otherwise terminate `BLOCKED_INPUT`. Native user simulators, where part of a benchmark, are invoked by that surface adapter and counted under its official protocol. No new simulator is invented to make a benchmark solvable.

**Output pressure and termination are observable.** On every step, report remaining step/tool/time allowances, unresolved requirements, capture fidelity and whether completion is verified. When ordinary exploration allowance is exhausted, only the reserved verifier/finalization path runs. Summaries, model retries, graph extraction calls and judge calls all have separate charged attempts. A long conversation cannot obtain fresh quota by compaction.

Completion evidence: acceptance cases `INF-01` through `INF-06`, `LONG-01` and `END-01` in document 09. A working inference call alone does not pass the controlled execution gate.

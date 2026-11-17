# Execution records, tracing, and recovery contract, v1

Status: Proposed design, November 12, 2026. This document specifies the next component; it does not claim that a ledger, sandbox, tracing service, or recovery implementation already exists. It refines the trace section of `training-protocol-v1.md` and preserves the separate assessment axes in `mcp-expectation-protocol.md`.

The [connected system specifications](docs/system/README.md), added November 13, define the surrounding inference, domain, context, judge, repair and evaluation components. This document owns storage/transaction behavior; [shared contracts](docs/system/01-contracts.md) and the closed event catalog supply the concrete boundary records and current event payload names.

The first implementation should be a local, single-writer kernel with one actor proposal per step and serial execution within each episode. Every admitted operation must have a durable decision before execution. Every next model call must have a durable record of the context supplied to it. Instrumentation belongs to the trusted runtime, outside the actor and repair code's editing permissions.

**1. What we are adopting from the inspected repositories**

At HarnessX revision `ccb411691343d06b4a5c44c4e11104d694318e8f`, the journal separates conversation JSONL from execution metadata, preserves raw and processed messages, externalizes large payloads, and writes state checkpoints. We adopt the distinction between raw evidence and effective context. Its file writes and checkpoint replacement do not constitute a transaction covering authorization, budget reservation, and an external effect. [Source: journal implementation](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/harnessx/tracing/journal.py).

The same revision's OTel adapter opens its step span in the `StepEndEvent` handler and immediately closes it. We will instrument actual operation start/end boundaries to measure elapsed work. Its checkpoint processor defaults to every five steps and catches checkpoint errors. Required execution-ledger failures in this project must stop new dispatch. [Source: OTel adapter](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/harnessx/tracing/otel_tracer.py#L61), [checkpoint processor](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/harnessx/processors/observability/checkpoint.py#L50).

DGM's candidate metadata and generation archive motivate parent-linked repair records. We retain failed candidates and their evaluation evidence, while keeping archive admission separate from promotion. [Source: DGM archive](https://github.com/jennyzzt/dgm/blob/a565fd2d1dca504ef5104a7cc0f3bdc4ab9b4fd2/DGM_outer.py).

These are mechanisms we adapt. Our ledger and admission protocol are project-specific engineering choices, not claims that these repositories already implement this authorization model.

**2. Define the units before defining the logs**

| Unit | Exact meaning | Identity and lifetime |
| --- | --- | --- |
| Experiment | A scheduled comparison with fixed split, variants, budgets, and evaluation rules | `experiment_id`; includes every scheduled episode, even ones that fail to start |
| Episode | One task attempt against one environment instance and pinned configuration | `episode_id`; crash recovery preserves this identity; a fresh benchmark attempt gets a new one |
| Execution session | One kernel process lifetime participating in an episode | `session_id`; changes after restart, does not reset budgets |
| Step | One actor decision cycle: committed input context, model invocation, proposed action or finish, kernel handling, resulting observation | `step_id` and increasing `step_index`; malformed output, denial, timeout, and finish still count |
| Operation | One logical action intent, including internal function/operator work | `operation_id`; nested operations have a parent; retry keeps the intent identity |
| Attempt | One physical adapter invocation for an operation | `attempt_id`, increasing `attempt_no`; a retry creates a new attempt |
| Event | One recorded fact about the execution | `event_id`, increasing episode-local `seq`; corrections append new facts |
| Checkpoint | An accelerator for restoring runtime state at an event boundary | `checkpoint_id`, `through_seq`; never permission to erase subsequent events |

For v1, a model response containing several actions fails the single-action schema without dispatch. Internal domain functions may perform several serial operations, each visible and metered. Provider-level retries are also attempts and consume their own costs. An incomplete model response is retained as partial output, not silently merged into a later response.

The kernel assigns canonical IDs. A caller-supplied request ID may deduplicate delivery, but cannot assert principal identity or permission. Reusing a request ID with different arguments is rejected. Argument equality alone is not a deduplication key: two intentional identical actions may be different operations.

**3. Storage decision**

Use SQLite as the authoritative local execution ledger, immutable payload files for larger content, and JSONL as a derived export. Start with one database per experiment and one trusted writer. No graph database or remote tracing service is required for this component.

```text
runs/experiments/<experiment_id>/
  ledger.sqlite
  artifacts/runtime/<sha256>
  artifacts/evaluator/<sha256>
  exports/<export_id>/events.jsonl
  exports/<export_id>/manifest.json
  backups/<backup_id>/
```

Directory names do not enforce access control. The actor and generated code must have no direct read/write access to the ledger or artifact roots. They receive only approved context and tool receipts. The evaluator has a separate privileged channel. The repair process receives a filtered export of training data, never unrestricted storage access.

Choose WAL mode, `synchronous=FULL`, foreign keys enabled on every connection, and a bounded busy timeout. Read back settings at startup. WAL is for local storage on one host. Verify the platform's sync behavior, including macOS full-sync options, before claiming power-loss durability. SQLite durability depends on the underlying storage honoring sync requests. [SQLite WAL documentation](https://www.sqlite.org/wal.html), [synchronization settings](https://www.sqlite.org/pragma.html#pragma_synchronous).

Small event payloads live in the database. Larger content goes through a trusted artifact writer: stage bytes, hash them, synchronize the file, atomically publish it on the same filesystem, synchronize the directory as supported, then commit its database reference. An existing content hash must match the expected bytes. A crash can leave an unreferenced blob; it must not leave a committed reference to an unpublished blob. Garbage collection only removes proven orphans outside the active-write window.

Hash the stored bytes, not a later reserialization. Structured objects use a pinned serialization format. Store artifact MIME type, byte count, digest, visibility, redaction version, and completeness. Identical content in different visibility classes does not grant access across those classes. A digest provides integrity checking, not authorization or protection against a compromised trusted writer.

Initial retention: keep all pilot records and failures until the experiment is explicitly retired. Export from a fixed high-water sequence for each episode. Back up the database through SQLite's supported backup interface, then copy and verify the blobs referenced by that snapshot. Do not back up a live WAL database by copying only its main file. [SQLite backup API](https://www.sqlite.org/backup.html).

**4. Physical records and constraints**

| Record/table | Required content | Mutation rule |
| --- | --- | --- |
| `manifests` | Experiment schedule and episode configurations, source revisions, model receipt, policy/package/tool hashes, split, seed, budgets, initial environment binding | Immutable, content-addressed versions |
| `episodes` | Episode identity, manifest reference, current lifecycle, last sequence, current runtime-state revision | Current view updated with the corresponding events |
| `events` | Event envelope and typed payload | Insert only; unique `event_id` and `(episode_id, seq)` |
| `event_links` | Source event, relation, target event | Insert only; causal and evidential links |
| `artifacts` | Hash, storage location, size, type, visibility, completeness and redaction metadata | Immutable metadata; retention changes recorded explicitly |
| `operations` / `attempts` | Intent, parent, original/dispatched argument refs, admission, attempt count, current execution assessment | Current views updated in the same transaction as events |
| `budget_accounts` / `budget_entries` | Limits, consumed amounts, reservations; uniquely identified reserve/consume/release adjustments | Entries append only; balances transactionally maintained |
| `checkpoints` | Through-sequence, runtime snapshot, graph revision, context refs, environment snapshot ref and restore capability | Insert only; incomplete snapshots are not resumable |
| `evaluations` | Evaluator identity/version, episode, input high-water sequence, result artifact, native metrics and conformance results | Insert only; re-evaluation gets a new ID |
| `jobs` / `job_events` | Offline diagnosis, repair, build, compare and export manifests/status/events, with experiment subaccounts and cross-stream links | Immutable input manifests and append-only events; current status transactionally derived |

Steps can initially be reconstructed from indexed events; they do not need another authoritative table. A later candidate index points to immutable repair manifests. These records can all live in one small database; they are not separate services.

Updates to current views and their events must commit atomically. Rebuild a view from events using a versioned reducer and compare its checksum against the stored view. Do not permit arbitrary actor-generated JSON to mutate these tables. Unknown event schema versions stop resumption rather than being guessed at. Migrations preserve the original records and log the conversion version.

Every event envelope includes:

```text
schema_version, event_id, event_type
experiment_id, episode_id, session_id, seq
step_id?, operation_id?, attempt_id?
recorded_at_utc, observed_at_utc?, monotonic_ns?, clock_session_id?
emitter_component, manifest_hash
trace_id?, span_id?
payload_json, payload_artifact_refs[]
```

Nullable IDs have explicit meanings. Startup events have no step; a denial has no dispatch attempt; privileged evaluation may happen after the actor stops. Use `seq` for committed order. Monotonic durations are only comparable within their clock session. External timestamps are source claims, not substitutes for local ordering.

Link relations include `caused_by`, `uses_evidence`, `retries`, `revisits`, `compensates`, and `supersedes_assessment`. Causal links reference existing records. A fresh replay or research branch links its parent episode/checkpoint without rewriting that parent's history.

**5. What an execution receipt must preserve**

For every actor decision, retain the actual context supplied at our model boundary: ordered messages, selected tool definitions, schema versions, visible evidence refs, truncation/compaction decisions, and generation settings. Store full context artifacts initially; introduce delta compression only after reconstruction tests pass.

The model adapter records the CLI executable/version, sanitized invocation settings, start/end times, exit status, output/partial output, requested model if any, resolved model if reported, reported usage, and whether usage is measured or estimated. Never infer a resolved model from an alias alone. A CLI can inject context or use hidden internal calls. Record `context_capture=adapter_input_only` unless a probe verifies effective model-request capture. Missing token IDs, log probabilities, or internal prompts remain unavailable, not fabricated. Do not request or depend on hidden reasoning.

An action receipt contains these distinct parts:

| Part | Fields that matter |
| --- | --- |
| Proposal | Original model output ref, parsed action and arguments, parse/schema outcome |
| Binding | Exact server/account/environment, tool/function name, adapter version, contract hash, authenticated principal reference and resource scope |
| Admission | Allow/deny, deterministic reason code, policy/rule version, checked state revisions, checked facts/evidence refs, budget reservation IDs |
| Dispatch | Actual arguments, any normalization rule, attempt ID, idempotency support/key reference, expected backend revision, start/end timestamps |
| Result | Original application response or protected ref, transport outcome, completeness, source request ID, artifact digest |
| Assessments | Separate execution, response-contract, ontology-mapping, task-evidence, and postcondition statuses |
| Consequences | Verified effects, runtime-state delta, graph additions/invalidation, budget entries, authorized recovery options |
| Observation | Exact bounded message supplied back to the actor, including omissions/redactions and their transformation version |

Credentials and transport authentication headers are excluded at capture time. Preserve application results under restricted access, with a separately recorded redaction transform where secrets must be removed. We cannot call a redacted payload byte-exact raw data. Never place credentials or large response bodies in telemetry attributes.

Admission errors, actor mistakes, and tool failures are separate facts. Example reason codes: `UNKNOWN_TOOL`, `ARGUMENT_SCHEMA_INVALID`, `OUT_OF_SCOPE`, `STATE_PRECONDITION_FAILED`, `BUDGET_EXHAUSTED`, `POLICY_EVALUATION_ERROR`. A diagnosis such as "mapping bug" is a later, attributed hypothesis linked to evidence until tested.

**6. Exact write and dispatch order**

```text
commit step_started + model_input_committed + model budget reservation
invoke the configured CLI through the model adapter
commit model outcome/usage + action_proposed, or model/parse failure

admission transaction:
  validate binding, authority, state and budgets
  append action_allowed + reserve budget + create prepared attempt
  OR append action_denied and charge the proposal attempt

dispatch transaction:
  revalidate anything that may have changed since admission
  append dispatch_started and mark the attempt dispatch-started
  OR append dispatch_canceled with reason and release unused reservations
commit before invoking the privileged adapter

invoke adapter outside the database transaction
publish result artifact, if any
commit result/uncertainty + budget adjustments + immediate assessments
perform separately admitted verification if needed
commit assessments + runtime/graph updates + observation_prepared
commit step_finished + checkpoint reference
next step commits the context containing that observation before model invocation
```

`dispatch_started` means the kernel crossed the durable pre-call boundary. It does not prove that a remote system received the request. The gap between that commit and a remote effect is unavoidable without backend cooperation. A lost response therefore cannot be labeled a confirmed no-op.

The writer owns dispatch. Only one active kernel may own the environment instance. Restart must establish that the prior executor and its child processes cannot continue dispatching. Timed-out requests may still finish remotely. Conditional writes or a backend transaction are required where a state-based rule must remain true at the instant of a remote effect; a recent local check alone is insufficient.

A verification read or compound-function child operation passes through the same admission, metering, and logging path. A parent function is not permission for arbitrary descendants. Partial effects are retained if a later child fails. V1 provides no implicit distributed transaction for a compound function.

Budget invariants: limits are pinned; cumulative consumed amounts never decrease; reservations and releases are separate entries; admission cannot reserve beyond a hard account's cap. Denied proposals consume the proposal-attempt allowance and retain their model cost. Actual dispatches consume tool-attempt allowances. Uncertain usage retains a conservative reservation until reconciled. Repeated receipt delivery cannot settle a reservation twice. If the provider exposes no enforceable usage bound, monetary/token accounts are labeled soft/observed and cannot be claimed as hard caps; step/time limits still apply. Record actual overruns truthfully. A violated declared hard bound stops admission and creates a control failure, rather than causing the usage receipt to disappear.

If required storage fails before dispatch, dispatch count must remain zero. If it fails after a possible external effect, stop further acting and recover through reconciliation. An observation must not tell the actor that an effect succeeded until its supporting receipt is committed.

For a concrete synthetic conformance example, suppose step 7 proposes a refund of 500 and the authenticated principal's limit is 100. The ledger retains the input context and original proposal, then records `action_denied` with the rule version and checked limit, zero dispatch attempts, consumed proposal/model budget, and the exact rejection observation. Step 8 can revisit the order or choose another permitted action. The rejected proposal remains in the archive but is not a positive training target. This fixture tests enforcement; it is not presented as an AppWorld benchmark task.

**7. Crash recovery and going back**

| Durable state at interruption | Recovery behavior |
| --- | --- |
| No admitted attempt | No tool dispatch is authorized; unfinished model work is recorded and any repeat model invocation is a new attempt |
| Prepared attempt, no `dispatch_started` | After fencing the previous executor, recheck current authority/state before starting or canceling; no automatic stale permission reuse |
| `dispatch_started`, no definitive receipt | Mark outcome unknown; retain reservation; reconcile by backend request ID/status or supported idempotency protocol |
| Result committed, observation absent | Rebuild the observation from the recorded result and pinned transformation, without repeating the action |
| Observation prepared, next model invocation uncertain | Preserve the existing input/output evidence; a replacement invocation is separately logged and charged |
| Pending external operation | Use its status handle through admitted polling; pending is neither completed nor failed |
| Ledger/blob corruption or unsupported schema | Stop automatic resume; preserve evidence and report the integrity failure |

Do not promise exactly-once external execution. A retry requires a documented backend deduplication contract or sufficient reconciliation evidence. Local IDs alone do not deduplicate remote effects. A read may also have billing or consumption effects, so retryability is declared per tool.

For v1, unresolved external effects suspend the episode's normal actor dispatch. Recovery uses a restricted set of authorized reconciliation operations. Other unaffected episodes may continue. A timeout does not justify launching a replacement mutation. Late receipts append new evidence and can supersede an unknown assessment without deleting it.

Backtracking has three distinct forms:

- `revisit`: a new step references earlier evidence or a planning point. Refresh stale evidence and invalidate dependent conclusions. Budgets and the real environment stay current.
- `retry`: a new attempt of the same logical operation, explicitly admitted under its retry contract. A changed intent or arguments becomes a new operation.
- `compensate`: a new authorized action links to the prior effect. It can fail and needs its own receipt and verification.

A simulator rewind is a separate research episode/branch with its own accounting. It is not an invisible action inside a native benchmark rollout. Ordinary recovery checkpoints restore kernel state; they do not automatically restore a live external world.

Keep kernel state, actor beliefs, and environment snapshots separate. Kernel checkpoints include the event boundary, current workflow, budget balances/reservations, outstanding operations, context refs, graph revision, and frozen package identities. Environment snapshots state exactly what is restorable. Replay post-checkpoint events before resuming.

**8. Graph operators and evidence lineage**

The nine locked operator names remain unchanged. Record a parent operation for the selected domain function and a child operation for each operator invocation. Each child records operator/version, typed arguments, input graph revision, selected evidence refs, bounds, output artifact/hash, duration, and metered work such as rows or edges examined. These are runtime measurements, not actor-reported counters.

Each derived graph fact points to its source observations and transformation version. A graph update records additions, retractions/invalidation, previous revision, and new revision. A source refresh can invalidate a conclusion even if the old computation was internally valid. Capturing only the final answer loses that distinction.

Workflow transitions belong to the execution kernel and are logged separately from graph queries. A successful traversal does not authorize a write. Preflight inspections of privileged state remain runtime-only; their contents must not leak into the actor's domain graph.

**9. Traces we will actually inspect**

The canonical ledger is unsampled. An OpenTelemetry exporter provides a timing and causality view with this shape:

```text
episode
  step
    model.invoke
    kernel.admit
    function.execute
      graph.lookup_entities
      graph.traverse_relations
      tool.attempt
    postcondition.verify
    observation.prepare
```

Start spans when work begins and end them when work finishes. Reuse ledger IDs as attributes and store trace/span IDs in events. Use links for revisits, retries across sessions, compensation, and offline repair ancestry. A span has one parent; additional causal relationships live in links. [OpenTelemetry trace model](https://opentelemetry.io/docs/concepts/signals/traces/).

Our convention: an expected policy denial is `kernel.decision=deny`, not an infrastructure exception. Policy evaluation crashes and transport errors have distinct error attributes. Preserve the five assessment axes independently from span status. A green HTTP request is not proof of an achieved postcondition.

Telemetry is a projection. Export failure raises an observability warning but does not erase ledger evidence. Export can resume from committed sequence cursors and may produce duplicates, so correlation IDs remain stable. Initially inspect a CLI timeline and JSONL export; attaching a local OTLP viewer is an optional next step. Do not make a cloud tracing account a prerequisite.

The inspector must answer: What did the actor see? What did it propose? Which rule allowed or denied it? What actually ran? What changed? What remained uncertain? What recovery happened? Which evaluator judged the final state?

Reports include native task/scenario completion, denied proposals by reason, independently confirmed unauthorized effects, suspected false denials, unresolved outcomes, retries/compensations, model/tool/verification latency, recorded versus estimated cost, and trace completeness. A denied proposal is not an executed violation. False-denial labels need a policy oracle or review. Use task-family grouping in benchmark comparisons; do not treat every step as an independent success trial.

**10. How these records support learning and repair**

Between evaluation batches, the improver receives a training-only evidence bundle: original actor context, proposal, kernel receipt, relevant graph/operator records, outcome, and source versions. Start by classifying failures as actor decision, domain schema/mapping, function implementation, policy/instrumentation defect, tool/environment failure, or insufficient evidence. Keep uncertainty in the label.

A candidate manifest records `candidate_id`, parent package hash, motivating event/evaluation IDs, proposed mechanism, patch artifact, changed files, dependency lock, construction-model receipt, evaluation episode IDs, and the gate result. Candidate source is built and tested in isolation; the active package is an immutable hash pinned in each new episode. Patches to trusted policy, instrumentation, or evaluator code are outside automatic repair scope. Ongoing episodes never silently switch packages.

An export manifest records selected episode IDs/event boundaries, split, filtering/redaction/labeling versions, context fidelity, and parent dataset hash. SFT examples pair actual pre-action actor context with eligible action targets. A kernel-corrected dispatch is not relabeled as what the actor generated. Failed attempts remain archived; verified recovery can become a positive continuation with its actual causal history.

Model-boundary transcripts support debugging and domain-package repair even when CLI internals are unavailable. Exact token-aligned training and on-policy RL require additional verified tokenizer/template/token/log-probability capture as appropriate to the algorithm. A working inference CLI alone does not provide that capability. Privileged evaluator details never become actor inputs or test-set repair evidence.

**11. What must be learned through small probes before implementation claims**

| Probe | Current evidence | Required result and decision |
| --- | --- | --- |
| CLI observability and isolation | Existing setup selects the user's installed CLI; live Gemini inference was rejected with `UNSUPPORTED_CLIENT` | Verify a working invocation, actual output/usage fields, effective context visibility, internal retries, timeouts and tool disabling. If only adapter inputs are visible, label fidelity accordingly. No provider/model replacement is assumed |
| Actual enforcement boundary | Design requires privileged dispatch; prompt filtering is insufficient | Show actor/generated code cannot reach backend credentials, filesystem, network or alternate execution tools. Until then, describe it as a broker prototype, not enforced control |
| AppWorld checkpoint fidelity | Pinned source has database `save_state`/`load_state`, API logs and environment I/O logs | Save, mutate, restore, compare DB state and next-step behavior. Check RNG, clock, interaction counters, interpreter variables, and request tracker separately. Record missing restore capabilities |
| AppWorld dispatch correspondence | Environment supports code execution and tracked API calls | Map each admitted typed action to the actual native API calls; inspect internal/helper calls; match receipts with native logs and final state. Benchmark counters and kernel counters must both remain visible |
| Tool semantics | MCP schemas describe syntax but may omit effects or retries | For each enabled tool, establish effects, scope, idempotency support/expiry, pagination, error/partial-effect behavior and a postcondition check. Unknown guarantees stay unknown |
| Policy oracle | Native benchmarks judge task outcomes; they may not define our authorization rules | Define explicit conformance fixtures for allowed/denied cases. Keep injected policies and fault cases distinct from official benchmark results |
| Persistence and recovery | SQLite and the source journals provide mechanisms, not our tested guarantees | Inject process death at each commit/call boundary, disk-full/write failure, duplicate delivery, malformed blob and restart overlap; verify budgets, effects and event reconstruction |
| Storage overhead | No local benchmark run has measured trace sizes yet | Measure artifact bytes per step, full-context deduplication, commit latency and export cost on a small real-task pilot before choosing compaction or retention limits |

AppWorld source inspection confirms database-oriented save/load and native API/environment logs. It does not establish that those functions checkpoint the entire process or recreate identical future observations. [Pinned environment implementation](https://github.com/StonyBrookNLP/appworld/blob/42b5bcf3cd334fee33f0c37c02070a9f5807add5/src/appworld/environment.py#L1279), [native logs](https://github.com/StonyBrookNLP/appworld/blob/42b5bcf3cd334fee33f0c37c02070a9f5807add5/src/appworld/environment.py#L1137).

**12. The next component and its completion gate**

Build the ledger, receipt schema, serial admission/dispatch path, and a read-only timeline inspector together as the first vertical slice. Use a scripted actor and instrumented tool stub to exercise deterministic failures. Those are kernel conformance fixtures, not the benchmark. Then connect one actual AppWorld task and preserve its native evaluator output before adding the ReAct loop or repair search.

The slice is complete only when:

1. A denied proposal has a durable reason and zero adapter invocations.
2. A successful action links original input, admission, actual invocation, result, verified effects where available, and exact actor observation.
3. Duplicate receipt/request delivery cannot duplicate local dispatch or budget settlement; unsupported remote deduplication is explicitly recorded.
4. A crash after possible dispatch becomes unknown and cannot trigger a blind repeat mutation.
5. Resume preserves spending, outstanding reservations, source versions, and every prior event.
6. A revisit creates a new step; compensation creates a new operation; neither deletes history.
7. Hidden evaluator data and kernel credentials cannot be read by the actor or repair sandbox.
8. The inspector reconstructs an actor decision from storage without asking the LLM to explain what happened.
9. One native benchmark episode has an auditable link from initial state to admitted effects to the official outcome, with trace limitations disclosed.

This moves durable recording into the first component. The later trace/archive component in the broader plan should cover aggregate reporting, dataset exports, and experiment management, not retrofitting basic execution evidence.

# Shared computational contracts

This document owns semantics for the closed records in [contracts.schema.json](contracts.schema.json). [profile.json](profile.json) owns defaults. All boundary messages validate before use. Unknown fields, unknown major versions, duplicate JSON keys, non-finite numbers and oversized payloads are rejected. Validate UTF-8 bytes before parsing. Tool arguments additionally validate against the exact pinned tool/function schema; an arbitrary JSON object in the transport is not a valid tool call by itself.

**Identity and version rules.** The runtime creates UUIDs for episodes, steps, operations, attempts, artifacts and judgments; examples may use readable labels. Hash references are `sha256:` plus 64 lowercase hexadecimal characters over stored bytes. A versioned canonical JSON serializer handles structured manifests. Authority never comes from a model-supplied identifier. Resolve every reference against the episode's scope, visibility and pinned revision. Reject missing/corrupt references explicitly.

One `quota_root_id` is allocated by the experiment controller. Resuming, branching or retrying cannot mint spending authority. Research branches receive suballocations from an experiment budget and separate episode IDs. Episode manifests are immutable; updated bindings require an explicitly recorded replacement version with unchanged or narrower authority. Tool/schema drift suspends affected calls until revalidated.

For the narrow pilot, `TaskSpec.native_split` preserves the official dataset split and `internal_role` records `FIT`, `DEVELOPMENT` or `SEALED_CHECK`. The protected `split` access label maps these to `TRAIN`, `DEVELOPMENT` and `GATE` respectively. All three can originate from official train without exposing the sealed instance to diagnosis or falsely calling it official test data. Repeated runs retain the same task/instance identity.

Scheduling precedes successful preparation. `EpisodeScheduled` is committed against the experiment schedule hash, so failed launches remain accounted for. Preparation events reference that schedule manifest. `episode_manifest_pinned` commits the complete `EpisodeManifest`; subsequent execution events reference its hash. No action can be admitted using a schedule or incomplete preparation record.

Offline work has its own `JobManifest`, never a fabricated benchmark episode. Job kinds are `DIAGNOSE`, `REPAIR`, `BUILD`, `COMPARE`, and `EXPORT`. Each pins its input episode/candidate references, allowed split, model/dependency identities, output contract and allocated subaccount under the same experiment quota root. `ModelRequest` belongs to exactly one episode or job. Jobs have no live task-mutation capability. A compare job asks the trusted controller to schedule fresh, separately accounted benchmark episodes. Source episodes stay terminal.

Job lifecycle is `CREATED → RUNNING → COMPLETED`, with `WAITING_EVIDENCE`, `FAILED`, `UNAVAILABLE` and `BUDGET_EXHAUSTED` outcomes recorded explicitly. Only a controller can create a job or allocate its quota. Resume preserves job ID/spending; a new attempt receives an attempt ID. Job records use `JobEventEnvelope` and unique `(job_id, seq)` in the same database. Cross-stream links connect diagnosis to original episode events and repair to candidate/evaluation events. Job terminal status is unrelated to the benchmark's success denominator.

**Boundary ownership and required records.**

| Producer → consumer | Record | Validation and meaning |
| --- | --- | --- |
| Task adapter → scheduler | `TaskSpec` | User-visible objective, authorized resources, public requirements, native completion hook and hidden evaluator binding |
| Controller → all components | `EpisodeManifest` | Hashes, budgets, split, environment identity, model capability receipt, quota root; complete before execution |
| Controller → offline workers | `JobManifest` | Purpose, scoped input episode/artifact references, split visibility, subaccount, deadline and output schema |
| Context builder → model adapter | `ModelRequest` | Role, immutable input ref, schema ref, input/output allowance and deadline; no unrecorded appended context |
| Model adapter → scheduler | `ModelReceipt` | Attempt outcome, output ref, capture fidelity, usage basis, resolved model or explicit null |
| Actor → scheduler | `Proposal` | Exactly one `act`, `revisit`, `finish`, or `request_input`; never authority or a verification receipt |
| Registry → kernel | `OperationContract` | Interface schemas, effect class, scope, freshness, verification, retry and concurrency requirements |
| Kernel → dispatcher | `AdmissionDecision` | Rule outcomes and reservation references; allow requires all checks to pass |
| Dispatcher/verifier → scheduler | `OperationReceipt` | Five separate result axes, exact attempt/arguments, evidence and effect refs; failure does not imply no effect |
| Evidence store → context/judge | `EvidenceRef` | Hash, source, revision, locator, visibility, completeness and expiry |
| Kernel → actor | `Observation` | Outcome, permitted next options, open requirements, remaining budgets, bounded evidence cards |
| Runtime → recovery | `Checkpoint` | Committed sequence, snapshot, outstanding operations, frozen identities and restore capabilities |
| Evaluation service → diagnostics | `EvaluationResult` | Native metrics, conformance checks and data completeness; privileged contents stay privileged |
| Bundle builder → judge | `JudgeRequest` | Objective/criteria, coverage manifest, evidence locators and allowed read scope |
| Judge → evidence gateway | `EvidenceReadRequest` | Exact IDs or bounded structured query; no raw SQL, shell or arbitrary filesystem paths |
| Judge → repair planner | `JudgeVerdict` | Cited observations, hypotheses, contradicting evidence, coverage, repairability and next required test |
| Planner → proposer | `RepairSpec` | Mechanism, allowed files, failing example refs, invariants, tests and patch constraints |
| Proposer → build service | `CandidateManifest` | Parent, patch, changed files, dependency identities, motivation and risk |
| Gate → package registry | `GateDecision` | `PROMOTE`, `RETAIN`, `REJECT`, or `INCONCLUSIVE`, with exact evaluation and rule references |
| Any boundary → caller | `Failure` | Stable code, safe message, effect certainty, retry class and evidence refs |

Model wire outputs are deliberately smaller than stored records. The actor emits `Proposal`; the judge emits `JudgeResponse` (an evidence request, at most two finding proposals, or a synthesis selecting existing finding IDs); the repair proposer emits `RepairResponse`; the slot extractor emits `ExtractionProposal` validated against the declared slot schema. The runtime assigns canonical finding IDs, resolves citations, computes hashes/coverage, attaches authentic model receipts and writes the full `JudgeVerdict`/`CandidateManifest`. Model-supplied coverage, promotion or authentication metadata is never accepted as authoritative. Candidate/request IDs required in a wire message must match the ID issued in its input.

The registry in [event-catalog.json](event-catalog.json) is closed. Validate the common `EventEnvelope`, require `payload_schema` to match the catalog entry, then validate the payload against that named schema. Semantic checks additionally enforce matching episode/operation IDs, ordered revisions, transition legality and reference visibility. Worker RPC uses `WorkerRequest`/`WorkerReply`; `OperatorCall` defines all nine canonical operator input shapes. The public categorical alias is resolved and logged before canonical validation.

Use `JobEventEnvelope` for the catalog's job-only events and shared model/evidence/budget events emitted by jobs. Episode action/dispatch/lifecycle events cannot occur on a job stream. Records from both streams can be read through the same scoped evidence gateway. The event ID is globally unique across streams.

A shared `event_ids` table reserves each event ID in the same transaction as its episode/job event insert, enforcing uniqueness across both streams. The catalog uses event-specific payload schemas where necessary: an allow event cannot carry a deny decision, and an unknown-operation event cannot claim reported success. A diagnostic/repair job cannot declare a gate/test input split.

**Argument and result handling.** Parse output as one complete JSON document, optionally allowing one enclosing Markdown code fence removed by a recorded deterministic parser transform. Reject trailing commentary, multiple documents, truncated strings and duplicate keys. No LLM silently fixes arguments in the dispatcher. A schema rejection is an observation for the next charged actor step. Permitted normalizations are explicitly named in the operation contract and preserve original bytes plus normalized arguments.

`act` selects exactly one manifest-bound tool/function and supplies arguments and cited evidence IDs. The registry, not the model, determines whether it is a raw tool, domain function or runtime evidence operation. `revisit` names an earlier step and evidence IDs plus a reason; it requests reassessment, never an environment rewind. `finish` supplies an answer/artifact refs and claimed requirement IDs; verification remains external. `request_input` names missing fields and why they affect a decision; authorization changes are never inferred from an unanswered request.

**Checked facts have three values.** A predicate returns `TRUE`, `FALSE`, or `UNKNOWN`, with evidence, checker version and revision. Unknown never satisfies a required precondition or completion requirement. Absence of a field is unknown, not false. Requirements may be open-world factual questions or closed-world obligations only when the domain contract declares completeness. Model beliefs and diagnoses are separate records and cannot be cast to checked facts.

**Common error classes.**

| Class | Codes and caller response |
| --- | --- |
| Protocol | `SCHEMA_INVALID`, `UNSUPPORTED_VERSION`, `PAYLOAD_TOO_LARGE`, `BAD_REFERENCE`: return bounded correction receipt, never dispatch malformed action |
| Admission | `OUT_OF_SCOPE`, `UNKNOWN_TOOL`, `STATE_PRECONDITION_FAILED`, `STALE_EVIDENCE`, `BUDGET_EXHAUSTED`: retain proposal and decision, expose only safe rule details |
| Environment | `CONTRACT_DRIFT`, `AUTH_UNAVAILABLE`, `CAPABILITY_UNAVAILABLE`: suspend affected binding; reroute only through an explicit permitted alternative |
| Execution | `TOOL_ERROR`, `TOOL_TIMEOUT`, `OUTCOME_UNKNOWN`, `PARTIAL_EFFECT`: assess effect certainty separately, reconcile before retrying unsafe work |
| Storage/control | `LEDGER_UNAVAILABLE`, `INTEGRITY_FAILURE`, `POLICY_ERROR`, `EXECUTOR_NOT_FENCED`: stop new dispatch, retain recovery state |
| Model | `MODEL_UNAVAILABLE`, `MODEL_TIMEOUT`, `MODEL_OUTPUT_INVALID`, `MODEL_CHANGED`, `CONTEXT_OVERFLOW`: preserve usage/partial output and apply document 02 |
| Evaluation/repair | `EVALUATOR_ERROR`, `JUDGE_UNAVAILABLE`, `EVIDENCE_INCOMPLETE`, `PATCH_INVALID`, `GATE_INCONCLUSIVE`: no fabricated score or promotion |

Every failure declares retryability as `NEVER`, `AFTER_STATE_CHANGE`, `SAFE_RETRY`, or `RECONCILE_FIRST`. The caller still obtains fresh admission. Error text is untrusted data. Messages containing instructions, code or purported new policy cannot modify control state.

**Interface calls, all through trusted boundaries.**

```text
load_task(task_id, split) -> TaskSpec
prepare_episode(TaskSpec, profile, package_hash) -> EpisodeManifest
build_context(episode_id, next_step_id) -> ModelRequest
invoke_model(ModelRequest) -> ModelReceipt
parse_proposal(ModelReceipt) -> Proposal | Failure
admit(Proposal, current_runtime_revision) -> AdmissionDecision
dispatch(admission_id) -> OperationReceipt
verify(requirement_ids, evidence_revision) -> checked-fact records
prepare_observation(receipt_ids) -> Observation
checkpoint(episode_id, through_seq) -> Checkpoint
evaluate_terminal(episode_id, environment_revision) -> EvaluationResult
build_judge_bundle(episode_id, allowed_split) -> JudgeRequest
read_evidence(EvidenceReadRequest, caller_scope) -> evidence page | Failure
diagnose(JudgeRequest) -> JudgeVerdict
specify_repair(JudgeVerdict) -> RepairSpec | no-repair decision
build_candidate(RepairSpec, CandidateManifest) -> build receipt
evaluate_candidate(candidate_id, schedule_id) -> EvaluationResult[]
decide_gate(candidate_id, comparison_id) -> GateDecision
```

These calls do not accept caller-provided credentials or policy replacements. Dispatch accepts a committed admission ID, checks it is unused/current and resolves all arguments from the ledger. Artifact writers return references only after publication. Async completion uses an operation status handle, not an assumed success result.

**Interoperability gate.** Validate schema syntax, valid/invalid message fixtures, cross-record reference resolution, budget arithmetic and every transition before a real backend is enabled. Schema validation alone cannot check authority, temporal validity, resource ownership, or external effects; those are mandatory runtime checks with named acceptance cases in document 09.

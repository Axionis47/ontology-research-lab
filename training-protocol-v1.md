# Controlled acting and training protocol, v1

Status: Proposed design based on source inspection on November 12, 2026. No runtime or training pipeline is implemented by this document. Existing model configuration and the locked nine-operator library are unchanged.

Implementation entry point, updated November 13: [connected component specifications](docs/system/README.md). That bundle supplies the detailed contracts, inference and long-task algorithms, judge/repair protocol, current evaluation split/gate rules and component acceptance tests. Use its stated precedence when this earlier overview is less specific.

Active scope correction: [one narrow task family, inference first](docs/system/11-narrow-training-and-inference.md). Earlier multi-family pilot counts, second-surface milestones and broad promotion gates below are future references. Current work uses one native scenario, fixed model weights, a small repair loop and optional graph operators only when justified.

## Objective

First make a small ReAct actor work on one narrow task family. A trusted execution kernel mediates every consequential operation. Improve its bounded behavior package through reproducible experiments, with separate evidence for task competence and enforcement correctness. Additional families and environments are deferred.

An observed zero-violation result is evidence about the tested cases, not proof of universal safety.

## 1. What the source code supports

Inspected revisions:

| Project | Revision | Mechanism to adopt | Boundary to preserve |
| --- | --- | --- | --- |
| Darwin-Agent/HarnessX | `ccb411691343d06b4a5c44c4e11104d694318e8f` | Explicit model/tool hook points; trajectories containing state, actions, observations and rewards; candidate validation; separate training adapters | Its extensible processor chain is not our immutable authorization authority |
| jennyzzt/dgm | `a565fd2d1dca504ef5104a7cc0f3bdc4ab9b4fd2` | Parent-linked candidate archive, isolated patch attempts, staged benchmark evaluation | Archive admission is different from promotion to the active system |
| StonyBrookNLP/appworld | `42b5bcf3cd334fee33f0c37c02070a9f5807add5` | Real stateful application tasks, official evaluator, function-calling agent reference | Keep task ground truth and evaluator state outside actor observations |
| OaK paper | arXiv `2608.22974v1` | Construct schema and typed functions using training feedback; freeze them for inference | A reasoning kernel and an authorization boundary have different responsibilities |

Concrete findings:

- HarnessX `runloop.py` calls `before_tool` processors and dispatches only when the resulting event is approved. The event initially sets `approved=True`. Our broker instead requires a successful explicit admission decision on every call.
- HarnessX processor-contract enforcement defaults to `warn`, with an available `strict` mode. These contracts govern processor behavior; they are not a substitute for resource authorization or process isolation.
- Its tau2 evolver reads failed trajectories and changes configuration, processors or guidance without updating model weights. Its gate compares reward, optionally adjusted for additional cost, against historical best with a tolerance.
- Its validation workflow checks configuration, processor contracts, synthetic smoke execution, novelty and evidence. The synthetic replay is a wiring check, not evidence of benchmark improvement.
- Its Slime and verl integrations separately handle model-generated token masks and rollout log probabilities. Weight training needs this additional machinery.
- DGM retains candidate ancestry and evaluates patches using benchmark harnesses. Keeping a candidate for exploration does not mean deploying it.

## 2. Separate the trusted runtime from learned domain packages

The term kernel has two meanings in this project. Keep their ownership explicit:

**Trusted execution kernel:** admission, permissions, resource scope, state transitions, budget accounting, dispatch, execution receipts and recovery. It is outside every automated editing surface. Engineering changes to it have a separate review and conformance process.

**Versioned domain package:** schema, source mappings, typed functions, workflow templates and context guidance. This is the initial optimization target. It is frozen for each episode and evaluation batch. Candidate changes never expand authority or weaken protected business constraints.

**Actor:** a small ReAct loop. It receives an observation and available action definitions, proposes an action, receives the kernel's result, and repeats. It may revisit evidence, change its plan, request clarification or finish.

**Evaluator:** computes results from the benchmark's authoritative outcome checks and a separate kernel conformance suite. The actor and repair proposer cannot modify the evaluator or inspect sealed evaluation data.

**Improver:** reads authorized training traces and proposes a bounded patch to a domain package. It cannot apply the patch to a running episode or promote itself.

## 3. Episode and action contracts

Each episode starts from a versioned manifest containing:

```text
surface_id, task_id, task_family_id, split, seed
environment_version, reset_snapshot_id
actor_model_receipt, model_settings, prompt_version
kernel_version, policy_version, domain_package_hash
tool_manifest_hash, authenticated_principal_binding, resource_scope
step_limit, tool_attempt_limit, token_limit, deadline
evaluator_version
```

The CLI remains the model transport. It must act as a proposal producer with its own tool execution disabled for these runs. Record its resolved model and configuration. If it cannot identify the model, mark that provenance unknown rather than inventing a version. Do not combine results across a detected model change. CLI model selection can remain owned by the user's configuration.

For each proposal, the kernel performs:

1. Validate the envelope and argument types; reject unknown fields that claim authority.
2. Resolve the exact server, account, environment, tool and contract revision from the task manifest.
3. Check current authorization, resource scope, permitted state transition and operation-specific preconditions.
4. Reserve applicable budget and record the decision before dispatch. Denied attempts still consume the relevant attempt budget.
5. Execute through the one privileged adapter. Compound functions must use the same scoped capabilities for their internal operations.
6. Preserve the raw response and separately assess its contract, interpretation, evidence sufficiency and postcondition.
7. Return a bounded observation and allowed next moves. Log the resulting state revision.

Policy evaluation errors deny dispatch. An uncertain external outcome is `UNKNOWN`, not a confirmed failure or automatic permission to retry. Conditional writes or backend transactions are needed where authorization depends on state that can change concurrently. A Python precheck alone cannot eliminate that race.

The actor and candidate-code process receive neither backend credentials nor network/filesystem routes that bypass the broker. A language-level wrapper or an AST check is not a sandbox.

## 4. Backtracking and graph operators

Revisiting a planning step is an allowed workflow transition. Reversing an external effect is a new compensating operation, supported and authorized separately. Revisiting a checkpoint never resets spending, erases receipts or silently restores a live backend.

The nine locked operators remain fixed. Learned typed functions compose them for lookup, traversal, projection, filtering and aggregation. The actor normally calls these functions through the gateway. Each internal graph access inherits scope, bounds and provenance requirements.

Domain graphs contain authorized observations and derived facts with provenance. Do not populate the actor's graph from hidden evaluator databases or solution metadata. Graph variants and raw-tool baselines must have access to the same permissible evidence.

Keep three forms of recovery distinct in traces:

- **Revisit:** refresh or reassess previous evidence and invalidate dependent conclusions when necessary.
- **Retry:** repeat an operation under its declared retry and idempotency contract.
- **Compensate:** perform a new authorized operation to reverse a supported effect.

No-progress detection should consider action, normalized arguments, evidence revisions and relevant state. Repeating a read after the source changes is different from repeating an identical failed call with no new evidence.

## 5. Multiple task surfaces

A surface adapter supplies task loading, reset, observations, exact tool contracts, state/effect inspection for the trusted runtime, and the official terminal evaluator. It does not rewrite kernel semantics.

| Order | Surface | Why it is included |
| --- | --- | --- |
| First | AppWorld | Existing project benchmark; stateful app APIs, reads, writes and cross-application dependencies |
| Second | ALFWorld text environment | Different action vocabulary, partial observations, exploration and revisiting earlier locations |
| Third | tau2 text tasks | Policy-constrained interaction and changing user/environment state |

Pin benchmark revisions and split manifests before collecting results. AppWorld's official evaluator reports task and scenario completion; retain both. ALFWorld has train, seen-validation and unseen-validation configuration paths. Select and freeze the exact tau2 release and training split when its adapter is introduced, since its upstream benchmark structure changes.

Injected failures and authorization challenges form an additional, explicitly labeled conformance suite. Do not present those modified tasks as native benchmark results. If an added policy makes a native task impossible, report the conflict separately and disclose its effect on the denominator.

Start with multiple task families within AppWorld, then add the second environment before making cross-environment learning claims.

## 6. Data and split discipline

- **Training:** the improver can inspect tasks, outcomes and traces. Training examples may drive domain-package construction or weight updates.
- **Validation:** selects candidates. It is a development signal, even when its task details are hidden from the proposer. It is not an untouched test set.
- **Sealed test:** used after the candidate is frozen, with no repair cycle driven by its task-level failures. Follow official test rules and report the frozen candidate's complete result.

Keep variants of the same task template or scenario in one split when constructing additional internal splits. Do not treat paraphrases, seeds or different entity names as independent held-out task families. Respect official benchmark splits and disclose any extra grouping.

Record every attempted rollout, including failures, invalid outputs, refusals, timeouts and kernel denials. Separate infrastructure failures using predefined criteria. Report their frequency and rerun the same scheduled cases under a bounded rule; do not replace hard failures with easier tasks or silently discard them.

## 7. Trace protocol

The concrete storage, event, receipt, crash-recovery, and tracing contract is in [execution-trace-protocol-v1.md](execution-trace-protocol-v1.md). That document refines the event vocabulary below and makes durable recording part of the first gateway component. The later archive component adds aggregate reports and exports.

Use runtime-owned append-only event records plus content-addressed artifacts. Persist at least:

```text
episode_started
step_started
model_input_committed
action_proposed
action_allowed | action_denied
dispatch_started | dispatch_canceled
operation_result | operation_unknown
postcondition_checked
state_transitioned
observation_prepared
step_finished
episode_finished
evaluation_recorded
```

Each record carries episode/step/operation IDs, causal parent IDs, timestamps, policy and package hashes, arguments or protected references, reason codes, relevant state/evidence revisions and budget deltas. Store the input supplied at our model boundary and explicitly label any unobservable CLI-injected context. Keep privileged evaluator artifacts separately access-controlled. A committed dispatch start does not prove remote receipt or completion; interrupted attempts require reconciliation.

Distinguish proposed arguments from dispatched arguments. If runtime normalization changes an action, preserve both; training must not attribute the corrected action to the actor. Log observable outputs and optional short justifications, without assuming access to hidden model reasoning.

Protect raw evidence from modification by the actor and improver. JSONL and hashes aid auditing but do not themselves enforce immutability. Redact credentials before exporting training records.

## 8. What training changes

### Stage A: construction and repair with fixed model weights

This is symbolic learning of reusable domain packages. It is the first stage:

```text
run training tasks with frozen candidate
→ classify failures from raw traces
→ propose one bounded patch
→ validate in isolation
→ rerun target cases and regression cases
→ evaluate on validation surfaces
→ archive and promote, retain, or reject
```

Failure classes include malformed proposal, wrong action choice, missing evidence, wrong mapping, incorrect function, stale-state handling, permission denial, no-progress loop, evaluator defect and infrastructure fault. Diagnosis is a hypothesis until a patch changes the predicted behavior in a controlled rerun.

Candidate manifests contain parent hash, changed files/functions, targeted failure IDs, intended behavior change, newly introduced dependencies, regression risks and test evidence. Reject empty or equivalent patches as no new candidate. Keep unsuccessful attempts and their reasons.

Code onboarding is explicit: allowlisted patch surface, dependency review, structural/type/interface checks, isolated import and execution, scoped capability handles, conformance tests, then benchmark evaluation. Passing syntax or a smoke test is insufficient. Only the promotion controller changes the active package pointer, between episodes.

### Stage B: supervised model training, if pursued

Use successful, independently evaluated trajectories and verified recovery continuations. Retain negative data in the archive, but do not automatically imitate every action in an eventually successful episode. For example, an unauthorized proposal followed by a successful recovery should not become a positive target for the unauthorized action.

Build records from the captured pre-action context, schema and tool definitions, with the capture fidelity attached. Require verified effective-context and token alignment before claiming exact trajectory reconstruction for token-level training. Optimize loss on the intended assistant action tokens, not environment observations, kernel receipts or evaluator output. Keep the original causal history when teaching recovery. Never splice a correction into an impossible state.

A CLI conversation and an Ollama inference run do not update weights. Actual fine-tuning requires a trainable checkpoint, tokenizer, trainer and suitable compute. Exporting examples is data preparation, not a completed training run.

### Stage C: reinforcement learning, after the preceding stages work

Freeze the kernel, domain package and evaluator during each training experiment. Use the same mediated action path in training and inference. Capture policy checkpoint, tokens, masks, termination/truncation reason and behavior probabilities required by the chosen RL algorithm. Never fabricate absent log probabilities from ordinary CLI logs.

Use benchmark outcome as the main competence signal. Keep unauthorized executed effects as a hard exclusion and regression failure. Track denied proposals separately. Avoid rewarding raw tool success, apparent closeness to a goal, or always moving forward. Backtracking can be necessary and should not receive an arbitrary penalty.

Train the actor and evolve the domain package in separate experiments initially, so improvements can be attributed to a particular change.

## 9. Acceptance and comparison

Record the following separately for every surface and task family:

- Official task outcome and any benchmark-specific scenario/reliability metric.
- Unauthorized executed effects and attempts to bypass mediation.
- Denied proposal frequency and false-denial rate on known-authorized cases.
- Verified recovery success for declared recoverable failures.
- Incorrect completion claims and unresolved external outcomes.
- Model tokens, model turns, attempted/dispatched tool calls, internal operator work, latency and infrastructure failures.

The gate is lexicographic: conformance and evaluator integrity first, competence second, resource efficiency third. A higher average reward cannot compensate for an unauthorized effect. Conversely, denying every action must fail the usefulness and false-denial checks.

For an initial pilot, preselect 20 AppWorld training tasks across multiple families and 10 development tasks, with three rollouts per candidate where the provider supports repeated sampling. These are engineering defaults for exercising the pipeline, not a statistically sufficient generalization study. Use fixed task manifests and matching environment seeds. Seed control does not guarantee deterministic remote model output.

Before broader promotion, expand evaluation to the relevant official development splits. Predeclare acceptable per-surface regression margins, the target improvement and the evaluation budget. Use paired comparisons and uncertainty estimates clustered by task family. If the evaluation cannot distinguish improvement from noise, retain the candidate without promoting it and collect more evidence within budget. Report the number of candidates tested because repeated selection can overfit validation.

Compare these configurations with the same model, permissions, accessible evidence and budgets:

1. Simple ReAct with raw tools behind the trusted gateway.
2. The same actor with an initial typed domain package.
3. The same actor with the repaired domain package.
4. Later, a trained actor with the domain package held fixed.

Count underlying API and operator work inside compound functions so packaging many operations into one call does not produce a false efficiency win. A control-ablation that intentionally bypasses enforcement belongs only in an isolated test environment.

The candidate archive and the active system are separate. Safe but non-winning candidates may remain as research parents. Only candidates passing the promotion gate become active.

## 10. Component order and completion evidence

| Component | Completion evidence |
| --- | --- |
| 1. Action gateway, durable ledger and receipt contract | Allowed call dispatches once in the controlled fixture; denied call dispatches zero times; forged authority, wrong scope, stale state, unknown tool, duplicate delivery and uncertain-outcome recovery are exercised |
| 2. AppWorld adapter and evaluator boundary | Native task reset, actual admitted API action, official terminal outcome and trace tied to one manifest |
| 3. Small ReAct actor | One proposal per step through the gateway; successful task, denial recovery, backtracking and bounded termination demonstrated |
| 4. Trace exports, aggregate reports and baseline runner | All scheduled rollouts accounted for; actor-visible context reconstructable to the adapter's verified capture fidelity; failures reproducible where the environment supports replay |
| 5. Second surface adapter | Same actor and kernel operate on ALFWorld without benchmark-specific branches in kernel code |
| 6. Bounded repair and promotion loop | One targeted candidate improves its intended behavior and passes cross-surface regression checks; one rejected candidate leaves the active version unchanged |
| 7. Training exporter, then optional SFT/RL | Causal contexts, masks and provenance validated before any weight-training claim |

## Source links

- [HarnessX dispatch loop](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/harnessx/core/runloop.py#L505)
- [HarnessX processor contract modes](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/harnessx/core/processor.py#L65)
- [HarnessX trajectory representation](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/harnessx/core/trajectory.py#L243)
- [HarnessX candidate validation](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/harnessx/meta_harness/validate_workflow.py#L857)
- [HarnessX tau2 evolution gate](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/recipe/tau2_evolver/run.py#L1164)
- [HarnessX Slime rollout and token requirements](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/recipe/slime/harness_rollout.py#L42)
- [DGM archive and parent selection](https://github.com/jennyzzt/dgm/blob/a565fd2d1dca504ef5104a7cc0f3bdc4ab9b4fd2/DGM_outer.py)
- [DGM patch and evaluation cycle](https://github.com/jennyzzt/dgm/blob/a565fd2d1dca504ef5104a7cc0f3bdc4ab9b4fd2/self_improve_step.py)
- [OaK construction and frozen inference](https://arxiv.org/html/2608.22974v1#S3)
- [AppWorld evaluator](https://github.com/StonyBrookNLP/appworld/blob/42b5bcf3cd334fee33f0c37c02070a9f5807add5/src/appworld/evaluator.py#L322)
- [AppWorld ground-truth boundary](https://github.com/StonyBrookNLP/appworld/blob/42b5bcf3cd334fee33f0c37c02070a9f5807add5/README.md#L464)
- [ALFWorld dataset configuration](https://github.com/alfworld/alfworld/blob/master/configs/base_config.yaml)
- [tau2 benchmark repository](https://github.com/sierra-research/tau2-bench)

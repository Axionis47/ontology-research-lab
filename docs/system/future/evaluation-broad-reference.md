Status: inactive expansion reference. The active one-family evaluation protocol is in ../08-evaluation-and-success.md and ../11-narrow-training-and-inference.md.

# Evaluation protocol, success criteria and learning outputs

Report engineering correctness, task competence, repair value and generalization separately. A passing integration test is not a benchmark gain. A native task pass does not prove all authorization rules were respected. A judge's diagnosis is not a measured improvement.

**Native outcomes.** AppWorld uses its pinned official task and scenario metrics. Preserve the evaluator's raw output and denominator. ALFWorld and tau2 adapters retain their native success/termination semantics. Never replace these with an LLM score when an official result is available. Added policies, injected faults, simulated delays and altered step limits are separately labeled conformance or experimental variants, with native settings and deviations recorded. [AppWorld evaluator](https://github.com/StonyBrookNLP/appworld/blob/42b5bcf3cd334fee33f0c37c02070a9f5807add5/src/appworld/evaluator.py#L322).

**Splits and access.** Start with the official train split for construction/repair and official dev for development. Before search, group variants by task family and deterministically partition dev families into `development-visible` and `gate-hidden` using a stored seed/hash ordering, with half assigned to each and the extra family to development. Store exact task IDs and family mapping; never split variants of a family across these partitions. If this leaves insufficient/nonempty gate coverage for the preregistered comparison, report `INSUFFICIENT_EVALUATION_DATA` and retain candidates without a generalization claim. Official test stays sealed until one selected system is frozen. Native split labels and our internal subsets are both retained in reports.

Training traces and development feedback may inform repairs. Gate traces and results are hidden from the proposer until the full candidate slate is frozen. Test cases never influence package generation, prompt tuning or error-specific repair. A new model version, policy, budget or tool visibility creates a new experimental condition.

**Baseline comparisons.** Use the same configured model and declared capture limitations, task schedule, environment version, evidence access, authority, output allowance and episode budget for: A, simple ReAct with admitted raw tools; B, the seed domain package; C, a repaired package. All retain the kernel. Counterfactual enforcement bypasses belong only in isolated conformance fixtures. Record underlying API requests, operator work and extraction model calls, so a compound function is not falsely counted as one cheap action.

Pilot: 20 train tasks and 10 development tasks, three rollouts each, selected by family-stratified fixed ordering. If a split has fewer eligible tasks, enumerate all and label the reduced pilot. This validates the pipeline and estimates variance/storage/cost; it is not sufficient by declaration for generalization. Each scheduled `(variant, task, seed, repeat)` gets an episode before execution. Missing/failed launches retain result rows. Infrastructure reruns are limited to one under a predefined failure code, linked to the original; model mistakes and low scores do not qualify. Report both first-attempt and rerun outcomes.

Pair execution order alternates parent-first and candidate-first by a recorded hash of task/seed/repeat. Both use fresh environment instances and the same declared model warmup policy. Do not compare a fresh model load with an already warmed model as though the difference were a package gain. Cache/warmup state and provider variability remain disclosed measurement conditions.

**Episode acceptance.** Overall verified success requires native task pass, applicable public completion checks true, no confirmed unauthorized effect, no unresolved external effect, trace integrity and evaluator integrity. Retain each axis even when the combined value is false. A denied valid action is a usefulness defect; the kernel's denial flag alone cannot label it correctly denied. Conformance fixtures contain independent allowed/denied expectations, and ambiguous real cases require reviewed policy evidence.

**Candidate gate, in order.**

1. Reject on changed protected files, failed isolation/conformance, fabricated traces, evaluator access, confirmed unauthorized effects or unresolved integrity problems. Required conformance cases have zero permitted failures. Also require all independently labeled allowed cases to remain executable; deny-all cannot pass.
2. Require the targeted deterministic reproducer to pass and protected regression fixtures not to regress. For behavior-only failures, require paired target rollouts and an explicit diagnostic limitation.
3. Require a complete paired schedule on train/development and the frozen gate split. Preserve all observed regressions by task/family/surface; a favorable aggregate cannot hide a required scenario failure.
4. Compute per-task mean native score over repeats, then average within task family. Compare candidate minus parent using paired families; for multiple surfaces, report each and a preregistered equal-surface aggregate. Native benchmark aggregations remain separately reported.
5. Resample paired family blocks with replacement 10,000 times using a recorded random seed. Form percentile intervals for the aggregate and each surface. Use per-comparison alpha `0.05 / (30 * (1 + number_of_surfaces))` for the planned maximum candidate slate and score comparisons. This is a conservative planned multiplicity adjustment, not a cure for adaptive holdout reuse; the slate must be frozen before gate feedback. Report small-sample/degenerate interval limitations.
6. Require at least ten independent gate families per surface as an initial eligibility floor, the aggregate score interval lower bound strictly above zero, and each surface lower bound at least the pinned noninferiority margin (default zero). The family floor is an engineering prerequisite, not a statistical sufficiency theorem. If the floor or interval rules fail, result is `INCONCLUSIVE`. Additional data require a preregistered new evaluation batch; never keep peeking until a threshold passes.
7. Require mean measured model-work and tool-work ratios at most 1.20 versus the parent under paired cases. Missing/estimated model usage prevents a hard token-efficiency claim; a gate using observed-mode receipts may promote for competence only if preregistered step/tool/time proxies pass, with the limitation in the gate result. Measure latency/resource distributions, not only averages.

Decisions are `REJECT` for violated constraints/regressions, `INCONCLUSIVE` for missing or insufficient evidence, `RETAIN` for valid useful research candidates without promotion evidence, and `PROMOTE` for all required rules satisfied. A bootstrap confidence interval is empirical evidence with assumptions, not a guarantee of future safety or performance.

Pin the resource policy before running: `MEASURED_TOKEN_TOOL` compares total reported input plus output tokens and actual backend API attempts, or `STEP_TOOL_WALL` compares actor steps, backend API attempts and elapsed episode time. The current observed-mode profile uses the latter. Count cached inputs as input work; do not add reasoning tokens twice when already included in output totals. Report operator rows/edges/CPU separately. For a zero parent mean, equal zero use has ratio one and positive candidate use has infinite ratio. Required missing measurements make that gate inconclusive; no after-the-fact switch to a favorable proxy.

Freeze one winner and run the sealed official test once under the preregistered schedule. Report uncertainty and failures. Test feedback may motivate a future research project, but cannot be used to claim the same test remained untouched after tuning. Across surfaces, success claims apply only to the surfaces actually evaluated.

**What system success looks like.**

| Dimension | Required evidence |
| --- | --- |
| Controlled action | All conformance denials prevent invocation; valid calls still work; nested effects cannot bypass the broker |
| Reliable continuation | Long-task and crash cases preserve constraints, budgets, pending effects, artifacts and evidence; no false-success terminal status |
| Traceability | Every scheduled episode accounted for; every effect has admission/attempt/receipt linkage; model-input capture fidelity explicit |
| Useful diagnosis | Qualified judge identifies injected mechanisms with original citations; incomplete cases abstain; operational failures route correctly |
| Working repair mechanism | Candidate generation, isolation, evaluation, rejection/retention and atomic promotion logic all exercised |
| Demonstrated learning | At least one real repaired package passes the preregistered measured gate; otherwise report that the mechanism works but improvement is unproven |
| Transfer | The same kernel and actor protocol pass a second surface's gates without surface branches in kernel code |

No benchmark success-rate target is invented before baseline measurement. The definition of improvement is fixed; achievable absolute performance is an empirical result. If no candidate qualifies, the honest completed experiment reports no demonstrated gain and preserves the active package.

**Training exports.** Export only authorized train/development records according to the pinned data policy, never sealed gate/test solutions. Each example includes actual captured pre-action context, schema/tool definitions, package/model identities, action target, outcome, evidence lineage, capture fidelity, labels and exporter version. Verified recovery continuations retain the original error history. Do not train positive action imitation on rejected unauthorized proposals or pretend a kernel-normalized dispatch was the actor's output.

Stage A learns domain packages with fixed model weights. Later SFT requires a chosen trainable model/checkpoint, tokenizer/template, dataset license/access, exact target masks, optimization configuration and independent evaluation. RL additionally needs algorithm-appropriate token/log-probability/reward capture. Those are a future phase with explicit readiness gates, not something the configured inference CLI already performs. This project's v1 completion does not depend on training model weights.

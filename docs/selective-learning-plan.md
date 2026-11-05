# Selective evaluation and reusable task construction

Status: superseded as an execution plan on 2026-11-04 by [historical-execution-replay-plan.md](historical-execution-replay-plan.md), the sole active execution plan. Retained for design history and possible implementation reuse. The outcomes, ownership, and milestones below are historical, not an active work queue. Earlier waivers of old-run compatibility or historical adapters and dependency-based skipping do not override the active replay plan. Existing partial code, saved evidence, and the spending ledger are preserved.

## Required outcomes

1. Candidate evaluation does not automatically run every prior question through ReAct. It persists a dependency-driven plan selecting reuse, proof transfer, real deterministic execution, rematerialization, bounded fresh ReAct, or deferred evidence. Skipping never means passed.
2. Construction produces callable parameterized subtasks from task semantics, including point/field access within broader aggregates. These entry points work from an empty graph through frozen authorized source bindings.
3. Generated checks are fixed independently of candidate implementation, execute real programs on genuine evidence, reject tautologies, and report discrimination from bounded program mutation. They are not independent task oracles.
4. Candidate preference rewards preserved behavior and reusable subtasks before compactness and cost. It does not reward reproduction of a training trajectory, incidental retries, sampled answers, or question-specific programs.
5. Runtime instantiates demands for selected functions/arguments, reuses completed receipts, preserves required fields/endpoints, and reports unknown source scope without a mandatory custom domain verifier.
6. Actual evidence demonstrates selective evaluation, subtask access, and at least one useful attributable repair across candidates. Component tests alone do not close this milestone.

## Implementation ownership

- Verification agent: dependency/evaluation contracts, deterministic action selection and real retained-evidence execution, verification integration, focused tests.
- Learning agent: typed semantic contracts, behavior/check bank, callable compiler/bindings, anti-hardcoding and mutation controls, ranking, prompts, focused tests.
- Runtime agent: frozen acquisition binding preparation, scoped demand/materialization helpers and genuine cross-surface tests.
- Root: bootstrap construction/inference integration, starter reuse, API/UI evidence, end-to-end acceptance, spending and commits.

## Plan

Freeze TaskIR and a semantic behavior/check bank before drafting S/F. Compile supported task dependency closure, selectors and projections into callable pure functions after candidate binding. Validate units, granularity, parameter flow and effect boundaries. Keep unsupported interpretations explicit.

For each candidate derive static conservative computation, materialization and planner dependency manifests. Evaluate only invalidated checks. Reuse retained receipts as source evidence, never as fictional live MCP invocations. New schema materialization uses genuine raw receipts; old graphs require compatibility validation. Pure certificates remain restricted to their exact same-graph semantics.

Replace the unconditional sampled-plus-best_fresh union with a persisted EvaluationPlan. Default to at most three fresh ReAct cases per candidate, including at most one planner-only audit. Prioritize affected failures, new cases and diverse changed behavior; rotate audit selection deterministically. Respect the existing campaign/global budget before every dispatch. Reuse unchanged starter collection within the campaign instead of repeating it each round.

Execute a candidate-independent check bank against actual compiled helpers and optional model functions. Check units/domain and non-vacuity. Add at most eight valid program mutants per behavior and 64 per campaign, using unchanged genuine records. Unknown/equivalent/unexercised mutants receive no success credit. Version banks and compare candidates under the same bank and evidence scope.

Preserve three construction rounds, 20% unseen-first sampling, two bounded stage repairs, and the existing exploratory limits of two extra pure operators and 128 exploratory obligations. Rank protected regressions, executed callable behavior, worst-group useful checks, overall useful checks, then description size and measured cost. Missing independent task truth is nonblocking.

Show actual evaluation decisions, callable behavior/check evidence, and materialization scope in React through versioned Pydantic contracts. Viewer Replay/Reset remain read-only. Old run compatibility is not an acceptance requirement.

## Acceptance audit

- Identical dependencies cause zero model/MCP evaluation dispatches; old receipts retain original provenance.
- Pure changes use real execution or valid proof, with planner observations separately scoped.
- Changed population, identity, units, extractor and planner catalog invalidate the appropriate evidence.
- Fresh ReAct is bounded by the explicit selector, not accumulated history size; deferral remains unknown.
- Generated checks exercise the candidate implementation, detect a relevant real-data program mutation, and cannot improve scores by dropping tests.
- A point/field subtask works from empty G and parameter changes are honored; an aggregate over the corresponding retained scope agrees with its contributing records.
- A smaller graph does not receive credit by omitting required evidence; fields can expand from retained receipts without redispatch.
- The machinery executes genuine weather and Coffee evidence through shared contracts; no domain-specific solution logic in the engine.
- No held-out tuning, fabricated service/model outputs, uncertain-dispatch retry, or ledger reset.
- Demonstrate actual candidate repair and report exact model/MCP counts, estimates, and remaining unknowns.

## Research basis and boundaries

Selective regression testing uses change analysis to select affected checks under stated assumptions: Rothermel and Harrold, https://www.cs.purdue.edu/homes/xyzhang/spring07/Papers/p173-rothermel.pdf. Applying this to planner-visible context is an engineering heuristic, not a proof about stochastic planning.

Metamorphic testing checks relations among executions where exact answer oracles are unavailable: Chen, Cheung and Yiu, https://arxiv.org/abs/2002.12543. Generated relations need checked preconditions and do not become independent truth.

Incremental mutation testing limits program perturbations to relevant changes and filters irrelevant mutants: Petrovic et al., https://arxiv.org/abs/2102.11378. Here mutations are explicitly authored program test variants over real receipts, not fabricated benchmark evidence.

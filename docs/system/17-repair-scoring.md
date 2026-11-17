# Automatic repair scoring, first component

The implemented slice compares one trusted selector repair with its parent through eight recorded ReAct episodes: two implementations on the same four synthetic cases. It verifies recorded evidence and emits a deterministic decision. The later [running repair loop](18-running-repair-loop.md) adds automatic declarative proposals, persistent work, scoped discovery and development activation. This earlier fixture continues to use engineer-authored Python helpers. Native AppWorld repair evaluation remains separate work.

## Run and inspect

From the project root:

```sh
python3 scripts/demo_repair_scoring.py
python3 scripts/demo_repair_scoring.py --candidate regressing
python3 scripts/demo_repair_scoring.py --candidate unchanged
python3 scripts/score_repair.py runs/repair-scoring/first-comparison
python3 -m unittest discover -s tests -v
```

The demo prints its output directory and decision. Each invocation uses a fresh directory unless an unused `--output` path is supplied. Exit codes are 0 for `ACCEPT_FOR_DEVELOPMENT`, 1 for `REJECT`, 2 for `INCONCLUSIVE`, and 3 for `INVALID`. A deliberate regression therefore exits with 1. The standalone scorer only reads existing evidence and writes a new decision receipt; it never executes a helper.

The first recorded comparisons are:

| Comparison | Parent passes | Candidate passes | Decision |
| --- | --- | --- | --- |
| [Relationship repair](../../runs/repair-scoring/first-comparison/comparison.json) | 2/4 | 4/4 | `ACCEPT_FOR_DEVELOPMENT` |
| [Repair with a regression](../../runs/repair-scoring/regression-check/comparison.json) | 2/4 | 3/4 | `REJECT` |

These are synthetic, scripted demonstrations of scoring. An engineer wrote the candidates. The records explicitly set `native_performance_claimed: false` and `promoted: false`. The complete local suite passes 54 tests, including a fabricated score whose artifact hashes and event chain have been recomputed: the scorer still rejects it because the original before/after observations contradict the reported score.

## What changes, what stays fixed

Only the selector implementation varies. The [parent](../../examples/repair_scoring/parent.py) filters tickets by their own properties and misses the relationship condition. The [repair](../../examples/repair_scoring/repaired.py) also follows the existing customer relationship and checks that customer's properties. It uses existing entity identities and relations, without creating a schema or storing task answers.

Before the first episode, `manifest.json` records both implementation hashes, the target case and requirement, four input hashes, full runtime budgets, checker version and protected runtime/scorer source hashes. Each case input contains its original goal, computational completion contract and initial world snapshot. Both implementations receive the same input and limits, each in a fresh world. Parent-first and candidate-first order alternate across cases.

Every model call goes through the existing ReAct context builder, which retains the original goal. The actor is scripted for this component: select IDs, apply the requested update, then propose completion. Independent observation supplies the final state to the fixed [completion checker](16-completion-checks.md).

| Case | Role | What it tests |
| --- | --- | --- |
| `relationship_filter` | Target failure | Exclude open tickets whose customer does not match the requested region |
| `different_links` | Variation | Changed relationship endpoints, renamed IDs and reversed entity order |
| `single_match` | Preservation | A previously passing case with exactly one matching ticket |
| `empty_target` | Preservation | A previously passing case where no records should change |

The deliberately [regressing selector](../../examples/repair_scoring/regressing.py) fixes the relationship filter but returns an empty selection for a singleton. On `single_match`, the parent updates the required ticket and passes; this candidate leaves it unchanged and fails `targets_updated`. That paired result proves a regression in this deterministic fixture even though the candidate's overall pass count rises.

## Decision computation

The [scorer](../../react_runtime/repair_scoring.py) audits each run's artifacts and event chain, checks the recorded implementation identity, compares source snapshots and verifies the original goal, starting state, contract and budgets against the scheduled inputs. It then recomputes the checks from the original observations. A completion observation followed by another dispatched operation is insufficient as final-state evidence.

Task rewards remain 1 for `TRUE`, 0 for `FALSE`, and unavailable for `UNKNOWN`. Failed and missing runs stay in the scheduled denominator. The scorer records task outcomes, individual requirement outcomes and resources separately.

For each scheduled case:

```text
fixed      = parent task FALSE and candidate task TRUE
regressed  = parent task TRUE and candidate task FALSE
check lost = parent requirement TRUE and candidate requirement not TRUE
```

The targeted requirement must fail in the parent, pass in the candidate, and the candidate must also pass that complete task. Development acceptance further requires all four candidate tasks to pass, no lost requirements, unchanged protected inputs, distinct implementation hashes, complete evidence and compliance with the recorded step/tool/wall limits. Pass-rate gain is reported, but cannot override these conditions.

| Decision | Meaning |
| --- | --- |
| `ACCEPT_FOR_DEVELOPMENT` | Target reproduced and fixed; all scheduled candidate cases pass; no observed regressions or resource violations |
| `REJECT` | Valid comparison demonstrates failure to meet an acceptance condition |
| `INCONCLUSIVE` | A scheduled run, final observation or required fact is missing or unknown |
| `INVALID` | Inputs, implementation identity, protected sources, trace integrity or reported checks disagree |

The resource check uses recorded episode steps, tool attempts and monotonic episode wall time. This prototype enforces absolute limits; it does not implement the native pilot's relative efficiency or repeated-rollout gate.

## Durable records and bounded inspection

```text
comparison/
  manifest.json
  inputs/cases/*.json
  inputs/implementations/{parent,candidate}.py
  episodes/<case>/<variant>/
    world.json
    run-result.json
    react/ledger.sqlite
    react/artifacts/...
  runs.json
  comparison.json
  scoring/<receipt>.json
```

The ledger retains original prompts, actions, observations and independently checked state. Each comparison row points to a concrete run, completion report and event head. A future repair worker can start with one failed requirement and its evidence references, then use existing bounded evidence reads. It does not need the whole trace in its context. Locating a failed requirement narrows investigation; it does not automatically establish the causal defect.

Re-scoring requires the same protected source revision. A later runtime or checker edit makes the old comparison `INVALID` under the new source, while its original receipt remains preserved. Use the matching source snapshot to reproduce that historical comparison or start a fresh comparison for changed code.

## Relationship to HarnessX and future learning

At the project's pinned HarnessX revision `ccb411691343d06b4a5c44c4e11104d694318e8f`, the tau2 evolver feeds recorded trajectories into an evolution step, evaluates the resulting configuration, and gates the round's average reward against historical best. Its optional cost penalty and regression tolerance operate on that aggregate; a rejected round selects the stored best configuration. The gate does not require every previously passing task to remain passing. This component adds an explicit case-by-case requirement. [HarnessX round execution](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/recipe/tau2_evolver/run.py#L1644), [aggregate gate](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/recipe/tau2_evolver/run.py#L1164).

HarnessX separately validates configuration, processor contracts, synthetic replay, novelty and evidence before returning a candidate. Those validity checks are useful but do not prove absence of task regressions. [Validation workflow](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/harnessx/meta_harness/validate_workflow.py#L857).

The four local cases are all visible development fixtures, with no held-out claim. Likewise, all three recorded native AppWorld baseline variants have already been exposed. They cannot later be relabeled sealed. Actual model runs need repeated paired evaluations to distinguish a candidate effect from stochastic failures. Claims about new instances require fresh data and the separate [native acceptance protocol](08-evaluation-and-success.md). Passing a finite suite only establishes no observed regressions on that suite.

This runner executes trusted fixture code and is not an isolation boundary for generated code. Automatic repair generation needs bounded failure inspection, discovery of existing definitions, an allowed patch surface and isolated candidate execution before it can reuse this scoring pattern. A growing suite should preserve solved mechanisms and add every verified counterexample; storing passing task IDs alone does not establish coverage of unseen relationships or constraint combinations.

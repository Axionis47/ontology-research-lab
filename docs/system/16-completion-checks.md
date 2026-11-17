# Executable selective-update completion checks

This component turns an explicitly bound request into deterministic final-state checks. It runs through the existing ReAct verifier interface. It does not infer the meaning of arbitrary natural-language requests, certify source coverage, construct a kernel or replace AppWorld's official evaluator.

## Run the working slice

```sh
python3 scripts/demo_completion.py
python3 -m unittest discover -s tests -v
```

The [fixture](../../examples/completion_fixture.json) asks to mark open tickets belonging to west-region customers as reviewed, preserving other state. The actor is scripted and the data is synthetic. Each of four isolated episodes reads state, updates records and claims completion through the real ReAct scheduler. The independent checker reads back actual fixture state. Its answer does not depend on the actor saying “Done”.

| Case | Completion result | Reward | Reason |
| --- | --- | --- | --- |
| Both eligible tickets updated | `TRUE` | 1 | All mandatory checks pass |
| One eligible ticket missed | `FALSE` | 0 | `targets_updated` identifies the missing ticket |
| An ineligible ticket also updated | `FALSE` | 0 | `unrelated_state_preserved` identifies the extra change |
| Evidence coverage is incomplete | `UNKNOWN` | Unavailable | The complete state cannot be established |

All four cases use a three-decision fixture budget. The complete case reaches `VERIFIED_SUCCESS`; rejected/unknown finish proposals exhaust that budget. Their execution status and semantic completion result remain separate. The local first execution is recorded under `runs/completion/first-demo/`. These are verification examples, not agent benchmark scores or learning gains.

## Contract and computation

[completion.py](../../react_runtime/completion.py) defines a closed input contract: version, original goal, episode scope, a typed selector and one requested update. Selectors support exact property predicates and an optional one-hop relationship predicate. Updates support setting one property or ensuring one directed relation to a known anchor. No arbitrary code, new operations or caller-selected check list is accepted in the contract.

The four mandatory checks are fixed in code:

1. `scope_complete`: both trusted observations cover the declared task scope.
2. `target_set_known`: derive the complete target set from pre-action properties and relationships.
3. `targets_updated`: confirm every target has the requested resulting state.
4. `unrelated_state_preserved`: compare all remaining observed entity properties and relationships against the before-state.

Targets are computed from the before-state so changing a selection property cannot remove an obligation. Missing selection properties produce unknowns; explicit null remains a value. JSON booleans are distinct from numeric values. Scoped IDs establish identity, and relation endpoints must be observed. Existing desired relations and already-correct property values can satisfy the final-state contract without requiring duplicate writes. A fully resolved empty target set legitimately permits a no-op.

The checker evaluates in-memory normalized snapshots. It conservatively returns `UNKNOWN` for incomplete coverage, conflicting identities, dangling endpoints or wrong scope. The trusted adapter must establish coverage, current readback, namespace semantics and the accuracy of property/relation mappings. An actor-supplied `complete: true` is not evidence of those guarantees. This increment does not include API pagination proofs, a large-graph query engine, temporal source reconciliation or automatic request binding.

## Runtime binding and records

`bind_verifier(store, contract, before, observe)` copies and hashes the contract and before-state into the existing artifact store before acting. The loop rejects a binding whose original goal differs from the task and records `verifier_binding_ref` in its manifest. The adapter's `observe` callback independently obtains current state for each finish check.

The `completion_checked` event references the immutable binding and full report. Reports include checker version, contract/snapshot hashes, requirement IDs, three-valued results, affected entity IDs and source artifact references. The actor may read the bounded report through existing output tools. Failed or unknown checks reject verified completion and allow further evidence acquisition within the original budget. Native AppWorld evaluation stays separate and terminal-only.

The record format belongs to this component's versioned checker and C0 event catalog; it does not claim implementation of the full future `CheckedFact`/graph protocol. Raw observations are preserved independently of interpreted check results.

## Repair boundary

A failed requirement supplies a concrete symptom and evidence location. It does not itself prove the cause. A missed target might result from mapping, relationship traversal, pagination or tool routing. Consolidation must discover existing entities/definitions and distinguish those mechanisms before proposing a bounded candidate. The original goal and checker remain fixed during repair.

The [automatic repair scorer](17-repair-scoring.md) now compares trusted parent/candidate helpers against these checks on four fixed synthetic cases. It recomputes completion from original evidence and rejects per-case regressions even when aggregate pass count improves. This is development scoring; automatic diagnosis and candidate generation are not implemented.

Next integration work is to obtain valid AppWorld tool execution, bind supported public requests and API observations to checked contracts, and build bounded diagnosis/consolidation over the saved receipts. The official native evaluator continues to own benchmark scores.

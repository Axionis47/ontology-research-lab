# Worked lifecycle across all components

This is a synthetic conformance scenario, not an asserted AppWorld task or benchmark result. It traces a long task: inspect related records, make a permitted allocation change, verify the resulting state, and report evidence. A real AppWorld run uses its own task/API/evaluator through the same interfaces.

This is an expansion walkthrough. The active implementation starts with the short one-family protocol in [document 11](11-narrow-training-and-inference.md); it does not need to reproduce this entire long scenario before running useful inference.

| Stage | Computation and handoff | Durable evidence and possible failure |
| --- | --- | --- |
| 1. Onboard | Enumerate server tools/pages; bind account/environment; validate effect, scope, retry and output contracts | Inventory + fingerprints + capability receipts; incomplete discovery blocks task binding |
| 2. Prepare | Adapter loads public task; controller creates quota root, episode, requirements, package hash and isolated environment | Immutable task/episode manifests; hidden evaluator refs inaccessible to actor |
| 3. Initial evidence | Requirement keys identify project/entity IDs; scoped index lookup then registered read provider obtains needed source records | Read admission, native request, raw result, evidence entries, mapped graph revision |
| 4. First model call | Context builder packs goal, contracts, requirement state, current evidence and budgets; adapter invokes configured CLI | Exact supplied input + capture fidelity + model/usage/output receipt |
| 5. Proposed action | Actor requests a detail read with typed arguments | Original proposal; schema validation; committed admission and attempt |
| 6. Result | Response omits a field required for completion; seed mapping incorrectly converts missing to zero | Raw missing field and mapping branch preserved; wrong derived value distinguishable from actual source |
| 7. Long continuation | Over 60 decisions, inspect relationships, paginate source documents and revisit earlier facts | Per-step context manifests, source cursors, complete/partial flags, graph dependencies and checkpoints |
| 8. Compaction | Pack pinned obligations/effects plus structured context items; replace old inline details with source references | Old/new context hashes and coverage checks; early constraint remains reachable |
| 9. Safe denial | Actor requests a write outside resource scope | Durable `OUT_OF_SCOPE`, zero backend invocation, charged proposal; next observation names allowed recovery |
| 10. Backtrack | Actor revisits the earlier entity resolution and reads fresh evidence | New step linked to old one; old evidence becomes stale where appropriate; budgets remain consumed |
| 11. Unknown effect | Permitted mutation is dispatched but its response is lost | `dispatch_started` then `OUTCOME_UNKNOWN`; normal actor dispatch suspended |
| 12. Reconcile | Recovery controller uses admitted status read with the backend request ID | Definitive observed effect or continued unknown; never an automatic duplicate write |
| 13. Finish | Actor proposes completion based on the mapped zero | Public verifier may reject known unmet obligations; if the defect escapes public checks, native terminal evaluator still reports actual task failure |
| 14. Analyze | Deterministic scanner checks all event/budget/lifecycle edges; native failed obligation seeds diagnostic bundle | Trusted factual violations separate from the judge's possible explanation |
| 15. Long-trace judge | Segment analysis spots finish mismatch; dependency query opens the step-6 response/mapping and final verifier result | Original source citations across distant windows; coverage/omissions recorded |
| 16. Diagnosis | Judge distinguishes missing from zero and identifies mapping default as a hypothesis | Finding includes evidence, contrary complete-zero example, exact source line and discriminating test |
| 17. Reproduce | Isolated fixture feeds missing and explicit-zero inputs to the same mapping | Failure/preservation result turns a plausible cause into tested repair evidence |
| 18. Repair | Proposer emits bounded mapping/function patch; builder validates paths/constraints and compiles/tests without network | New child candidate, patch hash, build image, fixtures, rejected attempts retained |
| 19. Compare | Fresh paired train/dev episodes measure target behavior and regressions; candidate slate frozen before gate use | All scheduled outcomes, budgets, native metrics and confidence calculations |
| 20. Release | Gate promotes only if all preregistered conditions pass; otherwise retain/reject/inconclusive | Atomic active-hash update for future episodes or explicit unchanged registry; original episode remains failed |

The judge's relevant exchange is bounded and structured:

```text
Bundle: requirement R7 failed; finish at step 71; source dependency E14.
Judge request: read E14 original JSON pointer /remaining_quantity,
               mapping M3 branch for that field, and requirement R7 result.
Gateway result: field absent; M3 uses a default of zero;
                R7 final native check false; all hashes/locators attached.
Judge request: read a passing explicit-zero example using M3.
Gateway result: explicit zero with complete source record; check passes.
Verdict: supported mapping defect, not a tool timeout or missing authorization.
Test: absent must produce UNKNOWN and require permitted detail evidence;
      explicit zero must preserve current valid behavior.
RepairSpec: change only M3 and its consuming function's unknown branch.
```

If E14 is missing or redaction prevents the distinction, the finding is incomplete and the repair waits for instrumentation/reproducer evidence. If the evaluator failed to run, the system reports evaluator failure rather than task failure. If the patch fixes the example but worsens another required case, it is not promoted. If statistical evidence remains too weak, the candidate stays in the archive.

A long task therefore has an inspectable path through every component: original request, scoped evidence, bounded computation, recorded decisions, verified effects, honest stopping, cited diagnosis, isolated repair and measured release. None of these stages requires a model's retrospective story to stand in for missing execution evidence.

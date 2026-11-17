# Combined ontology consumption and recovery: actual Gemini run

Status: **RECOVERED_BLOCKED**. Deterministic recovery check: **True**. Models reported: gemini-3.5-flash-lite, gemini-3.8-flash.

The original task, all 53 initial facts, and ontology approval-complex-v1 are unchanged. This run combines a small catalog, on-demand definition retrieval, graph queries/traversal, a typed valid-panel function, candidate checks, and a mandatory runtime gate. Available interfaces are not necessarily all selected by the model.

Unlike the six independent runs, the runtime requires definition inspection and a current find_valid_panels receipt before accepting a finish. After the first correct initial proposal it revokes del-Vera before execution, advances the graph from 7 to 8, and gives the rejection back to Gemini. The original snapshot remains in context, explicitly superseded by new observations. A new current computation is required. We do not add a replacement candidate or relax constraints.

## Usage

| Phase | CLI calls | Main input | Output + thinking | Router | All-model total |
| --- | ---: | ---: | ---: | ---: | ---: |
| initial | 3 | 29,167 | 7,392 | 16,248 | 52,807 |
| recovery | 2 | 21,049 | 14,323 | 13,245 | 48,617 |

All reported totals across phases: **101,424 tokens**. These include fresh CLI routing and repeated context on every continuation. Unknown usage is not zero. Recovery includes every call after the revocation feedback, not the initial proposal call. [Machine-readable usage](results/20261117T003010.669432Z/metrics.json).

## Actual sequence

| Call | Phase | Model request | Arguments or proposed panel | Exact submitted prompt |
| --- | --- | --- | --- | --- |
| 1 | initial | `inspect_schema` | {"names": ["eligibility"]} | [context](results/20261117T003010.669432Z/contexts/call-01.txt) |
| 2 | initial | `find_valid_panels` | {"deployment_id": "d2", "at": "2026-11-16"} | [context](results/20261117T003010.669432Z/contexts/call-02.txt) |
| 3 | initial | `finish` | {"ops": "Vera", "security": "Tao"} | [context](results/20261117T003010.669432Z/contexts/call-03.txt) |
| 4 | recovery | `find_valid_panels` | {"deployment_id": "d2", "at": "2026-11-16"} | [context](results/20261117T003010.669432Z/contexts/call-04.txt) |
| 5 | recovery | `finish` | null | [context](results/20261117T003010.669432Z/contexts/call-05.txt) |

## Recorded outcomes

- Initial answer: `{"type": "finish", "panel": {"ops": "Vera", "security": "Tao"}, "proof_ids": ["Identity", "Platform", "Tao", "Vera", "c-Tao", "c-Vera", "d2", "del-Vera", "g-Iris", "g-Tao", "m-Tao", "m-Vera", "org-mercury", "project-atlas", "svc-login"], "rule_ids": ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"], "ontology_version": "approval-complex-v1", "graph_revision": 7}`.
- Initial eligibility gate before mutation: `{"admitted": true, "reason": "VALID"}`.
- Gate after revocation, before execution: `{"admitted": false, "reason": "VERSION_MISMATCH"}`.
- Recovery answer: `{"type": "finish", "panel": null, "proof_ids": ["d2", "org-mercury", "project-atlas", "svc-login"], "rule_ids": ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"], "ontology_version": "approval-complex-v1", "graph_revision": 8}`.
- Recovery component scores: `{"shape": true, "panel_correct": true, "proof_complete": true, "versions_correct": true, "rule_coverage": true, "passed": true}`.
- External writes: **0**.

The unchanged fixture has no valid panel after revocation. A correct null result is safe recovery to a blocked task, not successful approval. An old proposal cannot execute. Null never grants execution permission. A current deterministic search returning no panels supports this conclusion over the complete fixture; a short citation list alone does not prove absence.

[Original model envelopes, prompts, interface responses and rejection feedback](results/20261117T003010.669432Z/receipt.json). [Frozen manifest and hashes](results/20261117T003010.669432Z/manifest.json).

## Limits

One synthetic teaching run, no AppWorld evaluation, external deployment, learned ontology change, or Gemini judge/proposer cycle. Gemini is the explicitly requested experimental participant; production roles are unchanged. Definitions and functions are hand-authored. This measures model recovery with a strong runtime protocol, not unaided model detection of stale facts. Both initial observations and recovery are stored in the same growing history. Costs are not directly comparable to single-phase runs. No automatic run retries are performed; failures remain in the evidence.

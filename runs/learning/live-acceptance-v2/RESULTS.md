# Live proof results: acceptance failed

The full connected-loop claim did not pass its preregistered acceptance test. All 18 scheduled episodes finished. The bounded program-repair and regression mechanisms worked in the tested scope, but every scheduled live-model recovery failed.

## Measured results

| Test | Result |
|---|---|
| Raw ReAct on three native AppWorld variants | 0/3 passed |
| Kernel gap followed by live native ReAct recovery | 0/3 passed |
| Native inference after the first automatic repair | 9/9 passed, zero model calls or handoffs |
| Live recovery on the local relationship fixture | 0/1 passed |
| New relationship instance after the second repair | 1/1 passed, zero model calls or handoffs |
| Old native task after the second repair | 1/1 passed, zero model calls or handoffs |
| Automatic repairs | 2 accepted |
| Fresh execution gates before promotion | 1/1 case for the first repair; 4/4 for the second |
| Additional construction challenges | 16/16 for each repair |
| Frozen generated structural cases | 100/100 passed; 50 had nonempty target sets |
| Deliberately broken numeric-filter candidate | Rejected by the fresh execution gate: 3 native cases failed, 2 relationship cases passed |
| Active package after negative control | Unchanged |
| Automated runtime tests | 102 passed |
| Protected runtime hashes and archive integrity | Passed |

The native application was Spotify, scenario `07b42fd`, task variants `_1`, `_2`, and `_3`. The native evaluator ran its five official checks per main native episode. These are previously exposed training variants, not held-out tasks. Repeated runs used fresh native worlds.

All 171 model calls used the configured `qwen3:8b-q4_K_M`, with an 8,192-token server context, temperature 0, thinking disabled and a 512-token output limit. Wire receipts retained the original goal and showed one model digest throughout: `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`. No scripted actor was used in this acceptance attempt. The repair proposer was bounded structural search, not model weight training.

## What failed

| Episode | Model calls | Stop | Task state |
|---|---:|---|---|
| Raw classical | 22 | NO_PROGRESS | FALSE |
| Raw EDM | 34 | CONTEXT_OVERFLOW | FALSE |
| Raw reggae | 34 | CONTEXT_OVERFLOW | FALSE |
| Classical recovery | 24 | CONTEXT_OVERFLOW | FALSE |
| EDM recovery | 26 | CONTEXT_OVERFLOW | FALSE |
| Reggae recovery | 22 | CONTEXT_OVERFLOW | FALSE |
| Local relationship recovery | 9 | NO_PROGRESS | FALSE |

Observed failures included irrelevant catalogue searches, selecting an unrelated API, choosing `unfollow_artist` for a follow request, guessed arguments and repeated malformed local tool arguments. The independent checker rejected premature completion. Five episodes reached the harness's context-input bound despite the provider applying the configured context size. Alternating unproductive actions can evade the current consecutive-identical-outcome guard.

Execution failures did not authorize program repair. Only the raw classical case was initially eligible, after the system reproduced its typed-program failure. The other native variants entered the retained regression suite once fresh post-repair executions succeeded. The second repair consequently had to preserve all three known-working native variants as well as fixing the relationship case.

## What the repairs establish

The first repair appended `filter_numeric`, bound to `selector.numeric`. The second appended `filter_relation_connected`, bound to the contract's relationship slots and an existing filtered set of related entities. The accepted programs contain no task-specific artist IDs, genre values, thresholds or generated Python. Their complete representation is in [accepted-program.json](accepted-program.json).

The second promotion passed fresh executions of all four retained cases with fallback disabled. The final negative control bypassed the numeric filter and replayed all five then-retained cases. It failed the three native tasks while preserving the two relationship cases, and the execution gate returned FALSE. This control tested rejection by the gate; it was not submitted as a separate promotion transaction.

This establishes finite operator-composition repair and tested regression protection. It does not establish reliable live fallback, general ontology construction, learned API semantics, a general learned dispatcher, or regression freedom on untested tasks. Native goal binding and action routing remain adapter code. The seed gaps occur before the first mutation, so partial-mutation recovery has fixture coverage rather than a successful live demonstration here.

## Evidence and reproduction

* [Preregistered manifest](proof-manifest.json): fixed task schedule, source hashes, model settings and stress inputs.
* [Machine-readable verdict](proof-report.json): all acceptance conditions, episode paths and audit receipts. Overall `passed` is `false`.
* [Regression receipts](regression-receipts.json): both promotions and the negative-control execution gate.
* [Unit-test output](unit-tests.txt): 102 passing tests.
* [Previous failed/interrupted acceptance attempt](../live-acceptance/proof-report.json): retained separately. Its runtime was changed before this new attempt; it is not merged into this result.

From the project root, run a new independent attempt in a new archive:

```sh
.venv/appworld/bin/python scripts/prove_inference.py --archive runs/learning/live-acceptance-next
```

The command uses the installed AppWorld environment and local Ollama service. It exits nonzero when any registered acceptance condition fails. Reusing the completed archive reads its completed request receipts; it does not rerun those main episodes. Use a new archive for a fresh experiment. The current source and model have not demonstrated an all-pass result.

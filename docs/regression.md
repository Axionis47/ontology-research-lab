# Recorded-call regression and compatibility adapters

The replay boundary executes saved function calls against a candidate's real graph and functions. A passing result establishes that the recorded calls produce the same outputs after an allowed interface rename. It does not establish that a new agent run will choose appropriate tools, recover from errors, cite evidence correctly, or answer a changed question.

This is a user-requested extension to OaK. The paper's construction and frozen-inference loop remains separate. OWL/HermiT consistency, graph/function validity, recorded-call compatibility, and fresh task success are separate evidence types.

## Adapter contract

The authoritative contract is `AdapterSpec` in the API documentation below. Each proposal names exact old and candidate revision IDs. The candidate must identify the old revision as its parent. Each function mapping can rename the function, rename its argument fields from old names to new names, and rename top-level output fields from new names back to old names. Unmentioned fields retain their names. Renames must be one-to-one, including unchanged names.

After renaming, input and output JSON Schema validation constraints must match. Descriptive annotations do not affect this comparison. Argument or output types cannot change. Object field renaming requires `additionalProperties: false`; conditional or composed object schemas are rejected when renaming would require a more expressive transformation. Compatible same-name functions receive identity mappings automatically. Missing or incompatible mappings remain explicitly unsupported.

The language cannot insert constants or defaults, calculate new answers, convert units or types, branch on task IDs, run code, or access external services. More expressive migrations need a separate design and validation obligation. Interface compatibility alone does not prove semantic equivalence, so every supported saved call is executed again.

## Proposal and execution separation

`adapter_proposal_payload` includes only the old and new revision IDs, schemas, function catalogs, the adapter JSON Schema, and transformation constraints. It excludes graphs, query text, task IDs, assessment results, saved outputs, and benchmark reference answers. The model callback in `propose_adapter` receives only this payload. Its proposal then passes the same deterministic validation as a supplied adapter.

`replay_function_call` accepts a completed function receipt, translates its argument names, calls the real function executor, translates allowed output field names, and compares canonical JSON exactly. The report preserves old, new, and adapted values, actual operator steps, dependency hashes, and errors. A failed execution never falls back to the old output. The old output is comparison evidence only.

Functions requiring fresh model-backed slot extraction cannot be replayed without that component and fail explicitly. The cheap replay path deliberately supplies no fabricated slot extractor. Such cases need fresh inference or a separately designed replay boundary with genuine recorded slot inputs and declared coverage.

## Trajectory and corpus boundaries

`replay_recorded_calls` automatically includes the parent revision's construction results and accepts additional saved answer receipts. Construction results may have no kernel revision ID because the kernel was still being constructed; they are bound by the saved parent artifact. Other answer receipts must name the exact old revision. Failed or unanswered old tasks, results with no completed calls, and empty receipt sets remain unverified.

Each trajectory is replayed in order and stops at its first unsupported, failed, or divergent call. Later arguments may depend on earlier observations, so the old branch is no longer justified after divergence. An old failed-call recovery path also needs fresh inference. Passing replay reports always retain `coverage: recorded_calls_only` and `fresh_agent_success: unverified`.

Dependencies conservatively cover the entire graph. This includes aggregates, negative results, and unknown dependency coverage. The first implementation does not skip calls based on an incomplete dependency index. Every execution records the actual graph, schema, and function hashes plus available source provenance.

For scope or corpus expansion, the service can extract the original corpus under the candidate schema and execute the candidate functions on that real graph. It preserves the candidate revision ID and records the replay graph and corpus separately. This compares behavior on the original evidence without treating newly added records as a regression in an old count. If the replay corpus itself changed, the report flags that old outputs are not new ground truth. Intentional changes require reviewed expectations and fresh task evaluation; official held-out labels must never be silently changed.

## Verification evidence

The deterministic component tests load the genuine downloaded Coffee corpus, execute lookup functions, and replay their actual receipts through field and function renames. They also remove a genuine source record and verify that real execution fails instead of returning a cached answer. Test catalogs and adapters are declared integration contracts, not simulated model outputs. Proposal-context and revision-binding checks run without a fake model callback. Passing these checks does not claim a completed model-generated adapter or a successful fresh agent trajectory.

When the saved local USGS pilot is present, an additional check loads its actual Gemini construction trajectories and replays every call through an identity integration contract. This verifies inclusion of parent-bound construction receipts without fabricating an answered agent response. The check skips explicitly when that genuine run has not been saved.

Completed end-to-end runs and model-generated adapter evidence belong in the application's persisted run manifests. Keep their status separate from the component checks described here.

## Generated API documentation

::: oak.regression

# Evidence contract for an offline judge

This document describes the implemented evidence reader and the next judge's required behavior. The reader and integrity audit run now. Automated model diagnosis and repair are not implemented in this component. The complete future design remains in [06-judge-and-diagnosis.md](06-judge-and-diagnosis.md) and [07-repair-and-promotion.md](07-repair-and-promotion.md).

## What the judge can establish

| Question | Original evidence |
| --- | --- |
| What task and rules applied? | Episode manifest, exact system text, schemas and source snapshots |
| What did the actor actually receive? | `model_started.input_ref`, exact CLI-supplied input, recent context and compacted IDs |
| What did the model return? | `model_result.output_ref`, stderr, extracted assistant response and parsed proposal |
| Why was an action accepted or rejected? | `action_allowed`, `action_denied` or `proposal_invalid`, schema paths and supplied arguments |
| What actually ran? | Committed `dispatch_started`, fixed command, process timing/exit status and operation receipt |
| What did the tool return? | Unmodified stdout and stderr, including invalid JSON and partial captures |
| What did the actor see afterwards? | Persisted `observation_prepared` and the next actual model input |
| What changed at compaction? | Complete before/after contexts, cutoff, sizes, policy and unchanged spending |
| Was completion supported? | Exact verifier inputs, verifier source identity, output and final terminal status |
| Which selective-update requirement failed? | `completion_checked`, its bound contract, before/after artifact references and affected entity IDs; see [document 16](16-completion-checks.md) |
| What code/config produced it? | Hashed source snapshots, schema, prompt, tool implementations and dependency versions |

The judge cannot establish hidden provider prompt contents, unavailable token usage, a checkpoint digest the CLI did not expose, business authorization that was not implemented or an external side effect without a backend receipt. Those are missing capabilities, never inferred facts.

## Mechanical audit first

Use the actual run directory printed by the runner. `RUN` below is a shell variable pointing to that directory.

```sh
python3 scripts/inspect_trace.py audit "$RUN"
python3 scripts/inspect_trace.py index "$RUN"
python3 scripts/inspect_trace.py step "$RUN" 3
```

The audit scans the full ledger and artifact inventory, verifies hashes and event order, checks required fields and referenced identities, pairs model/tool/verifier starts with results, checks admission before dispatch and looks for orphan or partial captures. It returns `complete: false` and exact problems if any check fails. Exit code 2 denotes incomplete evidence or a failed read, not a successful all-clear. `complete: true` concerns capture integrity only.

The index lists every recorded step, its event sequences/types and artifact IDs, including early failures. The step command returns that step's events and artifact metadata without stuffing the raw file contents into a model prompt. Source and manifest references are in the step-zero episode metadata. Results live under the terminal step. This is a bounded twelve-step component; multi-window autonomous judge scheduling remains future work.

## Exact evidence expansion

Choose the artifact UUID from a step event, never a guessed filename. For example:

```sh
python3 scripts/inspect_trace.py read "$RUN" "$ARTIFACT_ID" --start 0 --max-chars 2000
python3 scripts/inspect_trace.py read "$RUN" "$ARTIFACT_ID" --pointer /task/constraints
python3 scripts/inspect_trace.py read "$RUN" "$ARTIFACT_ID" --pointer /proof
```

The reader resolves the ID only through that run's ledger, checks the original content hash, optionally selects a JSON pointer, and slices a Unicode-character range. Each response supplies the source digest, pointer, exact returned range, total selected length, omitted prefix/suffix counts, returned-content digest and `next_start`. Maximum page size is 8,192 characters. Continue at `next_start` to inspect more; a single excerpt never means the whole source was reviewed. Invalid IDs, missing files, malformed pointers and corrupt content fail explicitly.

Every successful inspection saves its exact returned payload and the source event-chain head under a new `inspections/<uuid>.json`. The original episode ledger remains unchanged. These receipts can later document the judge's actual coverage. Private diagnostic files require `--include-diagnostics`. The actor's own `read_output` has a smaller page cap and cannot read those private artifacts.

## From evidence to a proposed repair

The next judge must follow this order:

1. Read audit results and the whole step index. If integrity is incomplete, report `EVIDENCE_INCOMPLETE`; local observations may still be described with their limits, but no confident root-cause or promotion claim follows.
2. Select a concrete observed failure, such as a schema rejection, repeated call, missing requirement or rejected finish. Read the actual pre-action input, original model output, admission decision, operation response and verifier outcome around it.
3. Separate observed facts from a hypothesized mechanism. Example: “The response was wrapped under `act`” is directly inspectable. “The protocol example caused that wrapper” is a hypothesis until a controlled comparison supports it.
4. Follow IDs to earlier evidence or a compaction boundary when needed. Read both sides and the relevant original source. Record inspected/omitted ranges through the evidence reader. If the read budget expires, return a partial diagnosis with explicit unanswered questions.
5. Propose one distinguishing test and one bounded repair target. Cite source artifact IDs, hashes, pointers/ranges and event sequences. Identify an alternative explanation and what evidence would distinguish it.
6. Keep the finding, proposed patch and measured result separate. A repair is supported only after its reproducer and preserving checks pass. The future benchmark comparison owns completion-rate improvement. A judge's opinion never changes a task grade or authorizes an action.

The initial automated judge will use the active narrow profile's limit of six model calls and two evidence expansions. Its case builder must preselect the core originals within that budget and disclose any omissions. If these limits cannot support a finding, it abstains instead of silently reading unlimited context or declaring the repair proven. Finding and repair wire contracts already live in [contracts.schema.json](contracts.schema.json); no alternative free-form format should become an authority bypass.

For this delivery, the evidence infrastructure is the concrete result. The judge model, its calibration, repair executor, native benchmark adapter and evidence-based promotion gates remain separate components.

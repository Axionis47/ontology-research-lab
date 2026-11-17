# First component: ReAct, compaction and durable evidence

Decision date: November 13, 2026. This component follows the user's latest scope: use the configured CLI, implement one simple serial ReAct loop with pinned instructions and automatic compaction, save outputs separately, and leave the benchmark adapter out. This document takes precedence over the earlier N1 adapter-first build order for this first delivery. The broader kernel, benchmark, judge and repair specifications remain future gates.

## Implementation and boundaries

[ReactLoop](../../react_runtime/loop.py) accepts a task, constraints, fixed model command, registered trusted tools and an independent verifier. Each turn builds context, saves the exact CLI input, captures model stdout/stderr, validates one proposal, dispatches at most one registered operation, saves its output and builds a bounded observation. Invalid output consumes a step and never dispatches. A finish proposal requires the verifier's explicit `True` for `VERIFIED_SUCCESS`. A missing verifier produces `UNVERIFIED_FINISH`.

The actor can revisit earlier evidence through `list_outputs` and `read_output`. A reread is a new recorded action. It does not undo a previous effect. Unknown tools and invalid arguments are rejected in code. This is a trusted local component, not the complete authorization kernel: resource permissions, backend transactions, untrusted code isolation and business state transitions are not implemented or claimed.

The implementation uses the existing closed `Proposal` schema in [contracts.schema.json](contracts.schema.json). Its other runtime records have their own explicit version, `react-component-0.1`. They do not claim conformance to the full future event catalog. [trace_audit.py](../../react_runtime/trace_audit.py) defines the currently required event fields and consistency checks. A later kernel integration must explicitly migrate these records.

## Configuration and commands

Python 3.12 and the pinned dependency in [requirements-react.txt](../../requirements-react.txt) are required. [config/react_loop.toml](../../config/react_loop.toml) owns this component's budgets. [config/models.toml](../../config/models.toml) retains the user's existing model selection.

From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/run_react.py --provider scripted --fixture compaction
python3 scripts/run_react.py --provider ollama --fixture short
python3 scripts/run_react.py --provider ollama --fixture compaction
```

The scripted provider is a deterministic test fixture. It is not a model or benchmark. The live commands use the configured `qwen3:8b-q4_K_M` through `ollama run`; they do not use an HTTP replacement. Both fixtures operate on synthetic read-only records. Passing them validates component behavior, not benchmark task completion or learning gains.

The existing Gemini CLI path remains available with its saved tool-denial policy and no model override. Its earlier `UNSUPPORTED_CLIENT` authentication failure is recorded in [MODEL_SETUP.md](../../MODEL_SETUP.md). Do not describe that provider as ready without a successful fresh check.

The Ollama CLI invocation applies the selected model, JSON output and disabled thinking. It does not expose the HTTP probe's `num_ctx`, `num_predict` or `temperature` settings through this invocation. These settings are explicitly marked unapplied. Instructions are pinned text in every CLI input; a separate provider system-role message and the hidden effective provider context are unverified. Character limits are local packing limits, not exact token accounting. Missing usage/model checkpoint details stay unknown.

## Durable storage

Each execution creates a fresh `runs/react/<uuid>/` directory. Nothing depends on this chat surviving compaction.

```text
ledger.sqlite             ordered events and artifact index
inputs/                   exact model inputs, tool requests, verifier inputs
outputs/model/            raw CLI stdout and separately extracted assistant text
outputs/tools/            original tool stdout, including partial/invalid output
diagnostics/              private stderr and runtime error evidence
observations/             parsed proposals, feedback and verification results
compactions/              complete before and after context snapshots
sources/                  source/config/prompt/schema snapshots
metadata/                 manifest, versions and source map
results/                  terminal status and fixture result
exports/<uuid>/            judge_packet.json and events.jsonl
inspections/<uuid>.json    separate receipts for offline evidence reads
```

[RunStore](../../react_runtime/store.py) assigns each artifact a UUID, step, relative path, kind, byte count, SHA-256 digest, capture-completeness flag and actor-visibility flag. Payload bytes are written and fsynced before their committed index entry. Published files are read-only. SQLite uses WAL and `synchronous=FULL`; events have a contiguous sequence and hash chain. The actor reads only visible IDs in the current run. It cannot request arbitrary paths, source snapshots or private diagnostics through these builtins.

The process runner writes stdout and stderr directly to separate files during execution. A timeout/output-limit/cancellation keeps captured bytes and marks the capture partial. A process error is preserved even if its output fails JSON validation. Polling bounds are not a hard instantaneous disk quota. This version has no automatic crash resume; a killed run is inspected, not replayed. Orphan captures, unfinished invocations and missing terminal receipts are audit failures. A logging/storage failure stops the run; no continuation is claimed safe when logging is unavailable.

The run directory is private to its local owner. Raw stderr can contain private diagnostics. The inspector requires an explicit diagnostic-read flag, and sharing a run requires reviewing those files. Hashes and read-only modes detect accidental inconsistency; they do not protect against an owner who rewrites both artifacts and hashes.

## Compaction contract

The default context cap is 16,000 Unicode characters, with a trigger at 80%, two recent steps retained and at most 2,000 characters from each output in a recent observation. These are initial component settings, not optimal model settings. The compaction fixture lowers the cap to 11,000 and emits large tool results to exercise the mechanism.

Compaction is deterministic. Earlier detailed observations become an action index containing step, action, outcome and original output/observation IDs. The original task, constraints, instructions, tool definitions, current request ID and consumed budgets remain pinned. The loop saves the before and after contexts, verifies referenced originals, and records the cutoff, character counts and compaction policy. It never deletes original artifacts or resets allowances. If pinned content plus the growing index does not fit, it returns `CONTEXT_OVERFLOW`.

`read_output` accepts an ID, optional JSON pointer, character offset and bounded page size. `list_outputs` pages the visible output index. Missing, private or foreign IDs return a recorded error; hash mismatch stops the loop. Summaries and previews never replace the original evidence. Compaction does not guarantee that the model remembers or reasons correctly, only that the recorded original evidence remains available under the tested contract.

## Completion and downstream contract

The [saved evidence index](../../outputs/react-component/README.md) records component test results, live CLI runs and failed attempts. It separates capture integrity from task completion and links original receipts.

Later components can depend on distinct inputs, raw outputs, decisions, tool results, compaction boundaries and verifier evidence connected by IDs. They can audit a terminated run without invoking its model or tools. See [14-judge-evidence.md](14-judge-evidence.md) for the exact inspection procedure.

The acceptance suite exercises repeated compaction and original-output rereads, premature finish, malformed proposals, unknown tools, bounded timeouts with partial capture, failed writes without retry, missing/corrupt artifacts, altered events, private-source access, explicit overflow and unchanged budgets. A complete trace means the implemented capture checks passed. It does not mean the task succeeded or the future kernel controls passed.

The next component is an advisory judge consuming this evidence contract. Benchmark attachment, supported repair generation and paired measurements follow their own gates. No model-weight learning, graph operators, automatic patch promotion or benchmark adapter is implemented here.

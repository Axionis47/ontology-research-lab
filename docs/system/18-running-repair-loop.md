# Running repair and regression protocol

The subsequent [connected inference controller](19-connected-inference.md) adds complete episode orchestration, numeric selection and native AppWorld regression qualification. Its current scope supersedes the original component limits below. Use `scripts/inference.py` to require fresh execution gates in addition to this component's structural comparisons.

This is a complete bounded repair cycle for the implemented selective-update completion surface. It ingests verified episode evidence, discovers existing scoped definitions, proposes a declarative computation change, runs independent regression checks, activates a development package, and resumes after interruption. It extends [the scoring component](17-repair-scoring.md). Arbitrary ontology/schema invention and native AppWorld repair qualification are outside this component.

## Run it

From the project root, create a new experiment and execute its full demonstration:

```sh
python3 scripts/repair.py demo --archive runs/learning/my-experiment
python3 scripts/repair.py status --archive runs/learning/my-experiment
```

The demo runs three distinct raw ReAct episodes before construction. The worker then constructs a candidate automatically and executes four fresh episodes through the resulting package. The actor in this demonstration is explicitly scripted. Candidate construction uses bounded program search, without a hand-written repaired function or an LLM. This proves the execution and learning mechanism within its declared grammar; it does not measure model or native benchmark performance.

For normal operation:

```sh
python3 scripts/repair.py init --archive runs/learning/live
python3 scripts/repair.py enqueue --archive runs/learning/live --file examples/completion_fixture.json
python3 scripts/repair.py work --archive runs/learning/live --watch-seconds 600
python3 scripts/repair.py run --archive runs/learning/live --file examples/completion_fixture.json --output runs/learning/task-001 --actor ollama
```

`run` uses a fresh local JSON world, independently verifies the result, imports its evidence, and invokes repair automatically. `--raw` starts the episode in ReAct. Otherwise it captures the current package once and starts with kernel dispatch. A later promotion cannot change a running episode. `--actor scripted` is available only as an explicitly labeled fixture transport. A failed task exits nonzero even if subsequent offline repair succeeds.

To import another existing episode, use `ingest --run-dir /absolute/path/to/react/run`. It must have a valid ledger, a bound completion contract and a current final observation. A native task score without these bindings cannot silently become a typed repair case.

`work` drains ready work, or watches for new cases for the specified interval. It does not create a background service or scheduled automation. Restarts preserve work and spending. Defaults are 96 candidate attempts per case, 512 proposal reservations and 20 claimed cases per experiment. Passing cases also consume a claim. Exhaustion is a recorded terminal status, never a success. Explicit `retry --key CASE_HASH --reason TEXT` requeues a case without resetting budgets.

## What is learned

[program.py](../../repair_runtime/program.py) defines a closed JSON language with at most eight nodes per function. This first surface implements three operators from the locked library: `lookup_entities`, `filter_property_categorical`, and `filter_relation_connected`. No generic operator is added or renamed. Package functions are `direct` and `related`, selected from the bound request shape.

Nodes reference earlier sets and typed request slots. A candidate cannot contain a concrete entity type, record ID, answer, predicate value, Python expression, import, shell command or network operation. Semantic direction constants are allowed and tested against directional variations. The language has no recursion or unbounded loops; the interpreter enforces entity, edge and computation limits. Candidate data is never passed to `eval`, `exec` or Python import machinery.

The seed package can filter own properties and discover/filter related entities, but its related function initially omits connecting those sets. The search proposer enumerates output rewiring, node replacement and insertion over the same grammar. It receives no expected record IDs. The evaluator chooses which change works. This is a finite structural search with a one-edit neighborhood, not unrestricted program synthesis. If that neighborhood cannot repair the failure, the worker records `SEARCH_EXHAUSTED`.

The learned result in the demonstration binds relationship type, direction and predicates from each request. It works on new IDs, property names and relationship structures because those remain runtime data. Discovery stores observed types/properties/relationships separately from the computation. It does not infer that observed properties are globally required or that a missing record implies a new schema is needed.

## Model proposal protocol

Use `work --proposer gemini` to invoke the existing configured repair CLI, or explicitly select `--proposer ollama`. Provider switching is never automatic. The configured model selection is preserved. Both providers emit the same declarative package format, which passes the same validator and regression gate.

Each proposal has at most four model calls. Every call retains the full original goal, the parent package, declared edit surface and bounded evidence references. The model can request an artifact page, query scoped entities or query relationships. The runtime checks scope and page limits and records each read. Candidate history includes recent rejection reasons. Large observations and comparisons remain in the artifact store. Context overflow becomes `NEEDS_EVIDENCE`; the goal is never silently truncated.

The model may return a candidate, `needs_evidence`, `needs_capability` or an unavailable result. It cannot alter contracts, evaluator code, budgets, expected outcomes or other package functions. An authentication/client failure becomes `NEEDS_CONFIGURATION`; it does not enter an automatic authentication retry loop. Transient transport failures have a 60-second retry delay and remain subject to persistent experiment budgets. There is no browser login automation.

The configured Gemini probe reached its authentication prompt and could not supply a verified candidate. The runnable search proposer remains independent of that provider. Model-generated repair quality is therefore not claimed from the current recorded evidence.

## Regression protocol

One independently verified failure is sufficient to open repair. Repeated occurrence is useful evidence but is not required.

1. Audit the episode and recompute completion from original observations. Preserve the goal, before-state, checker, package identity and handoff lineage.
2. Reproduce the failure with the current parent in a fresh local state. Already passing cases resolve without a patch. Unknown evidence produces `NEEDS_EVIDENCE`.
3. Freeze the complete registered case manifest and archive generation. Generate and pin 16 fresh structural challenge inputs before proposing. Their contents are unavailable to the proposer.
4. Reserve proposal budget before invoking the proposer. Validate the candidate's closed shape and single-function edit boundary. Deduplicate by parent, suite and candidate hashes. Interrupted or accepted-but-uncommitted attempts may be revalidated after restart.
5. Test the target first. A failure rejects the candidate cheaply. A target success triggers paired parent/candidate execution on every registered case, using identical initial state and the unchanged completion checker.
6. Require the target to be fixed, every candidate case to pass, and no previously true task or requirement to become false or unknown. A higher average score cannot override a lost check. Missing/unknown evidence blocks acceptance; no case disappears from the denominator.
7. Execute the frozen candidate on all fresh challenges. They vary type/property names, predicate values, relationship endpoints/direction, cardinality, empty matches and update kind. Expectations are derived by the independent fixed checker. A challenge failure rejects the cycle and retires that challenge set.
8. Store original trial observations separately and reference them from the compact decision. Check protected source identities again. Atomically activate only if the active parent and case archive generation still match the evaluated snapshot. Concurrently arriving evidence invalidates activation.

Acceptance is `ACCEPT_FOR_DEVELOPMENT`. These generated checks are conformance tests, not native held-out benchmark instances or statistical proof of generalization. Real stochastic actor comparisons still require the separate native repeated-evaluation protocol. This component compares deterministic package computation and then verifies its integration through recorded ReAct episodes.

## Persistence, discovery and recovery

[store.py](../../repair_runtime/store.py) uses SQLite transactions, an event hash chain and content-addressed immutable JSON objects. Artifacts publish by an atomic hard link after file synchronization. Original code snapshots are retained. An archive refuses operation with a different protected runtime revision.

| Object | Key and responsibility |
| --- | --- |
| Case | Hash of bound contract and scoped initial snapshot; exact duplicate submissions append an observation receipt |
| Entity | Case identity plus source entity ID; indexed by type, with properties in the original object |
| Relationship | Case identity, source ID, relation type and target ID |
| Observed definition | Source scope, kind, name and definition hash, linked to its originating case |
| Failure pattern | Function, failed requirements and predicate fields; a retrieval key, not proof of shared cause |
| Candidate | Canonical package hash, parent hash, target case and suite identity |
| Decision | Independent checks, original evidence references, challenge manifest and activation outcome |

Exact keys preserve identity and allow bounded SQL queries. Embeddings are unnecessary here and would not establish whether two observations describe the same entity. `Archive.query_entities` and `query_relations` read scoped instances; `discover --scope ...` pages observed definitions; `inspect --key ... --offset ... --limit ...` pages immutable objects.

One OS file lock permits one worker per archive while producers can enqueue evidence. Interrupted `RUNNING` cases return to `READY`; reserved spending is preserved. Incomplete attempts remain recorded. Candidate evaluation only mutates isolated copies, so restarting repair never repeats a live application write. Rollback uses `rollback --expected ACTIVE_HASH --key PRIOR_HASH --reason TEXT` and changes only future episodes.

The dispatcher records `EVIDENCE_GAP` or `NO_PROGRESS` and yields to the existing ReAct loop with the same world, original goal, history and remaining budgets. Kernel finish proposals now use the same independent verifier as ReAct finishes. If fallback cannot complete, its outcome and handoff still enter the archive when completion evidence exists; otherwise a named unavailable-evidence event is retained.

## Evidence and limits

The [verified demonstration](../../runs/learning/verified-loop/demo.json) contains three baseline episodes, automatic construction and four subsequent verified episodes. Search reserved 35 candidates before accepting one. All four registered cases and all 16 generated challenges passed before activation. No candidate function was hand-written for that run.

The 79-test suite exercises regression rejection, directional overfitting, original-evidence integrity, unknown results, mutation boundaries, persistent budgets, duplicate suppression, interruption recovery, worker exclusion, stale-suite rejection, rollback, bounded model reads, authentication/transport outcomes, actual ReAct integration and same-state fallback.

The supported surface remains exact property selection with an optional one-hop existential relationship and one bound update. Automatic natural-language binding, arbitrary schema changes, multi-hop reasoning, unrestricted generated Python and native AppWorld qualification are not implemented here. The current native baseline's tool-routing failures require a separate control repair surface; this component does not relabel them as ontology failures. The native evaluator retains authority over native benchmark results.

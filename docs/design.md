# OaK implementation and revision design

Status: initial design, not an implementation or a claim of benchmark reproduction.

## Objective and source boundary

Implement the paper's ontology kernel K = (S, F), its corpus-dependent knowledge graph G, construction/refinement process, and frozen-kernel inference. The authoritative source is arXiv:2608.22974v1. The extracted source and refined method specification are under docs/paper.

The user adds an observable inspection and revision workflow: inspect S/G/F; ask questions about their current contents; suggest a change in text; validate the candidate through real OWL/HermiT reasoning and other checks; preserve versions and evidence; determine efficiently which previous tasks still work.

The user additionally proposes an LLM-generated, constrained adapter to preserve old task/function interfaces under a revised schema. This is a project extension, not an algorithm attributed to the paper.

## Central engineering problem

Know exactly what a change invalidates. A successful prior task is evidence about a particular kernel, graph, corpus, model/prompt configuration, and evaluator. It is not a universal certificate about all future schemas or questions.

The system must distinguish:

1. Logical validity of the encoded ontology, checked with the real OWL/HermiT stack.
2. Validity of graph records and typed function execution.
3. Compatibility of previously observed computations under a revision.
4. Success of fresh agent decisions under the revised kernel.

A pass at an earlier level must not be displayed as a pass at a later one.

## First real task surface

Recommendation: ToolQA Coffee Easy, using official questions, the official preprocessed coffee corpus, and the official normalized exact-match scoring semantics. Coffee is evaluated in OaK's Table 3. This is the first pilot, not a claim to reproduce that full table.

The official question set contains 100 easy Coffee questions and 130 hard questions. The README describes a 5,746-row coffee corpus. The tabular tool reads `data/external_corpus/coffee/coffee_price.csv`. Download and inspect the actual corpus before fixing its identifiers, types, or selected pilot questions.

Choose a small, fixed set covering multiple actual question templates, not just the first records. Record original question IDs, source versions, and corpus hashes. Separate construction examples, development regressions, and held-out final evaluation. Exact sample counts and IDs remain pending data inspection.

Reproducibility gap: ToolQA exposes easy/hard sets, while OaK describes a training split without identifying the exact ToolQA partition in the reviewed paper. Our selected split must be named as a pilot protocol. It must not be described as the authors' split.

TravelPlanner easy three-day tasks are a subsequent richer surface for entities, relations, budgets, and user changes. CRMArenaPro has higher environment setup requirements and is deferred.

Primary benchmark sources:

- https://github.com/night-chen/ToolQA/blob/main/README.md
- https://github.com/night-chen/ToolQA/blob/main/data/questions/easy/coffee-easy.jsonl
- https://github.com/night-chen/ToolQA/blob/main/benchmark/ReAct/code/tools/table/tabtools.py
- https://github.com/night-chen/ToolQA/blob/main/benchmark/ReAct/code/agents.py#L446-L462
- https://huggingface.co/datasets/osunlp/TravelPlanner
- https://github.com/OSU-NLP-Group/TravelPlanner/blob/main/README.md

Do not import the entire legacy ToolQA harness blindly. The upstream tree contains mocks; this project must use the genuine corpus and actual execution path.

## Visible product behavior

Use a Streamlit inspector with text questions/suggestions and a Typer execution interface, as fixed in [the stack decision](stack.md). It must expose:

- Schema entity types, identity keys, properties, relations, constraints, OWL translation, and reasoner results.
- Graph records and edges with source provenance and extraction/merge versions.
- Function contracts, actual generated implementation or permitted composition, operator dependencies, and execution checks.
- Per-task input, selected function calls and arguments, observed results, final answer, score, latency, token/cost usage when reported, and relevant artifact versions.
- User suggestions, interpreted patches, parent/candidate differences, validation history, repair attempts, regression coverage, and promotion/rejection state.

Expose recorded evidence and concise decision summaries. Do not claim to expose private internal model reasoning.

Questions use an explicit artifact revision and remain read-only. Responses cite the relevant schema definition, graph evidence, function, or validation result. A text suggestion creates a candidate; it does not silently rewrite an active frozen kernel.

## Revision lifecycle

`text suggestion -> interpreted candidate patch -> candidate diff -> OWL/HermiT check and bounded repair -> graph/function compatibility -> impact analysis -> selected regressions -> promote or reject`

The existing active revision remains available throughout. Repairs create new candidate versions or append explicit patch events. Promotion is atomic and never rewrites an earlier revision. Whether every promotion is automatic or requires user confirmation remains a product-policy question, not an invented paper requirement.

Schema changes can affect extraction, graph identity, graph validity, function compilation, and task planning. Function-only changes still receive the relevant compatibility and regression checks; running HermiT alone cannot validate arbitrary function code.

## Constrained adapter proposal

Adapter contract:

`old typed function call -> input mapping -> actual new function/graph operations -> output mapping -> old output contract`

Bind each adapter to exact old and new kernel revisions, compatible graph/corpus versions, and a declared set of supported functions. It operates on current real artifacts, never on cached answers. Unsupported inputs or transformations return an explicit compatibility failure.

Initially have an LLM propose a declarative mapping that deterministic code validates and compiles/executes. The allowed language should be small enough to inspect and test. These are proposed supported transformations, subject to implementation and data checks:

| Transformation | Required evidence or condition |
| --- | --- |
| Type/property/relation/function rename | Identity and semantic meaning are preserved; mapping is explicit. |
| Input/output field mapping | Required fields, nullability, and types remain valid. |
| Enum mapping | Coverage and collision behavior are declared; unknown values fail explicitly. |
| Unit conversion | Source/target units, exact scale/offset, comparison effects, and rounding policy are declared. |
| Property projection or relation-path substitution | Join keys, uniqueness, cardinality, and duplicate handling preserve the old contract. |
| Defaults | Only when a documented contract justifies the value; never to hide missing evidence. |

Do not permit unrestricted generated Python, dynamic evaluation, external I/O, task-ID branches, expected-answer access, or unbounded arbitrary aggregation in the initial adapter language. More expressive transformations require a separately reviewed design and new validation obligations.

Reject or require fresh evaluation when an apparent rename changes identity, a one-to-one relation becomes one-to-many, an operation loses information, missing/unknown/false are conflated, or a change in units/precision affects filters or aggregates. Heuristics propose a mapping; they do not establish semantic equivalence.

One adapter describes a revision mapping. It must not be generated as a special solution for each benchmark question. Adapter generation can see contracts, revision intent, schema differences, and permitted corpus metadata, but not evaluator labels, held-out answers, or previous answer caches. Keep independent real regression inputs outside the adapter-generation context.

## Cheap regression with explicit evidence limits

1. Record real task execution, typed function calls, arguments, graph queries, outputs, and complete known dependencies under the old revision.
2. Compute the revision's changes and their dependency closure.
3. Reuse an earlier deterministic result only when all relevant immutable dependencies are unchanged and the dependency set is known to be complete.
4. Re-execute affected old calls through the proposed adapter against the real revised graph/functions. Compare results with the old observed behavior and with official correctness criteria where applicable.
5. Stop or mark divergence when a changed intermediate result invalidates later arguments or branches in a recorded plan. Do not continue blindly and claim the original task is validated.
6. Run fresh frozen-kernel inference for affected or uncertain tasks. This need not repeat ontology construction/refinement.
7. Run broader small regression audits periodically to detect incomplete impact tracking. This is a diagnostic safeguard, not a mathematical proof of coverage.

Recorded outputs are comparison evidence, never fake responses returned in place of real code. The system must report the check type, such as `reused unchanged evidence`, `adapter/function replay passed`, `fresh inference passed`, `failed`, or `unverified`.

Capture query and negative dependencies. A no-match result depends on an absence of qualifying records. Adding a record may change it despite leaving all previously returned nodes unchanged. Aggregates depend on their relevant result sets, not just the rows that happened to be logged. Ontology entailments can create additional indirect dependencies.

If a full schema or function catalog is shown to the LLM, changes to names, descriptions, or newly available functions may alter planning across many tasks. A local data diff does not imply a local agent-behavior impact. Conservative fresh inference is required when this influence cannot be bounded.

If the new schema needs new extraction, invalidate the affected extraction/graph artifacts and run the required real work. Do not call a graph transformed under an adapter a fresh model extraction unless that extraction actually ran.

## Backward compatibility versus intended changes

For a behavior-preserving revision, require the previous public contract and expected behavior within documented tolerances. For an intentional semantic change, record which expectations are obsolete and why. Do not force an adapter to reproduce a known incorrect answer. Never silently rewrite official benchmark ground truth to make a revision pass.

## Version and event contract

Each run must identify its kernel revision and exact artifacts. At minimum record:

- Parent/candidate revision identifiers and content hashes.
- Source corpus snapshot and row/document provenance.
- Schema, OWL encoding, graph, operator library, functions, and adapter versions.
- Extraction, generation, agent, and judge prompts and model settings.
- Evaluator version, task identity, split role, and run limits.
- Real tool inputs, outputs, errors, durations, and reported token usage.
- Validation/replay/fresh-inference evidence, coverage, and reason for reused or unverified results.
- Proposal text, interpreted change, repair history, disposition, and who or what initiated it.

Store large traces and artifacts durably with manifests. Link version-control commits to artifact revisions; a source-code commit alone does not capture LLM-generated runtime state. The storage roles and required intermediate outputs are fixed in [the stack decision](stack.md); exact typed event schemas will be implemented with their first real producers.

## First demonstration acceptance criteria

Using a documented subset of real ToolQA Coffee tasks and its real corpus:

1. Run actual LLM construction, real OWL/HermiT validation, graph instantiation, typed-function composition, and task scoring.
2. Display S, G, F and one complete execution with provenance.
3. Accept a text suggestion, show its interpretation and candidate diff, and run real validation.
4. Generate and validate a constrained adapter for a supported schema change.
5. Execute real previous function/task inputs on the revised artifacts and show coverage and differences.
6. Run fresh inference where required and clearly separate its results from adapter replay.
7. Retain both revisions and all check results, whether the candidate is promoted or rejected.

Nothing in this list is satisfied by mocked providers, fabricated benchmark cases, canned HermiT results, or a UI displaying artifacts that were not actually generated.

## Unresolved decisions before runtime implementation

- Exact official Coffee corpus availability and content hashes.
- Exact pilot subset and construction/development/held-out partition.
- Model/provider configuration, API access, and a bound for paid real runs.
- Schema vocabulary and faithful schema-to-OWL mapping, including open-world versus data-integrity checks.
- Function representation and isolation for generated function execution.
- Adapter language, comparison semantics, and type/cardinality/identity obligations.
- Dependency completeness rules and conservative fallback conditions.
- Promotion policy and detailed typed event schemas within the selected storage contract.

These remain tracked decisions, not hidden assumptions or blockers to completing source extraction and design.

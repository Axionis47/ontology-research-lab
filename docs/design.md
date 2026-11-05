# OaK implementation and revision design

Status: initial design, not an implementation or a claim of benchmark reproduction.

## Active execution decision, 2026-11-04

[Historical execution replay with shared, composable schema adapters](historical-execution-replay-plan.md) is the sole active execution plan. It owns current scope, milestone order, next actions, and acceptance. This design retains project constraints and rationale; [work-plan.md](work-plan.md) retains evidence and decisions. Neither maintains a competing execution queue.

Selective learning and universal language-translation preservation remain historical or deferred references. Earlier directions to omit historical adapters, selectively skip protected cases, or substitute proofs for required replay do not govern the selected plan. Reuse existing implementation where it serves that plan and preserve unrelated partial work. Paper fidelity, real OWL/HermiT, frozen revisions, separate evidence categories, held-out boundaries, and spending limits remain required.

## Objective and source boundary

The user-authorized inference extension uses on-demand discovery of schema and function contracts. Full S/F remain frozen and executor-owned. A model's bounded, expandable prompt view is a versioned presentation, not a schema revision or reduced validation scope. Search misses must be recoverable through browsing, inspection and dependency expansion. Standard typed tool contracts are exposed over the existing validated Decision transport; Gemini CLI-native tools remain disabled. The sole execution plan's Section 10 defines the implementation and acceptance scope.

Implement the paper's ontology kernel K = (S, F), its corpus-dependent knowledge graph G, construction/refinement process, and frozen-kernel inference. The authoritative source is arXiv:2608.22974v1. The extracted source and refined method specification are under docs/paper.

The user adds an observable inspection and revision workflow: inspect S/G/F; ask questions about their current contents; suggest a change in text; validate the candidate through real OWL/HermiT reasoning and other checks; preserve versions and evidence; determine efficiently which previous tasks still work.

The user additionally proposes an LLM-generated, constrained adapter to preserve old task/function interfaces under a revised schema. This is a project extension, not an algorithm attributed to the paper.

## MCP surface extension, 2026-11-03

The user authorized a focused implementation after reviewing a broader design. `TaskSurface` owns public requests, immutable split assignments, a starter prompt, configured MCP servers, and bounds. It requires neither an answer corpus nor a prewritten ontology. The shared engine discovers capability contracts, collects real starter episodes, samples construction requests, and constructs S/F from actual acquired evidence. Provider-native Gemini tools remain disabled; the application owns every MCP invocation.

The first slice uses the official MCP SDK, the existing LangGraph orchestration/checkpointer, SQLite artifacts, and the existing model ledger. An additional $5 campaign ceiling is fixed at onboarding inside the global $40 allowance, including unknown reservations. Server configuration contains environment variable references rather than credential values. Only explicitly reviewed, allowlisted read-only operations are in scope. Tool annotations alone do not establish read-only semantics.

Inference selects frozen functions. The new `invoke_capability` primitive uses a literal version-bound capability identifier and an executor-owned callback. The actual response is recorded, extracted under frozen S, and merged into the current episode graph before subsequent graph operations run. Conflicting observed values fail explicitly; this slice does not implement temporal reconciliation. No saved forecast substitutes for a new call.

Bootstrap discovery, model completion claims, OWL validity, graph integrity, function probes, and independent task scores are distinct evidence. Kernel construction produces immutable candidates with parent identifiers. It does not automatically promote a candidate because its probes passed. Authoritative contracts come from the Pydantic models and operator signatures, not a second prose schema.

History currently uses verified construction-episode manifests and lexical overlap. Prior answer values are excluded, and changed capability contracts are filtered. Semantic ranking, runtime workflow compilation, arbitrary migrations, mutating tools, automatic promotion, and broad benchmark comparisons remain later milestones. These limits must remain explicit in reports.

The weather adapter supplies authored requests and independent receipt-grounded scoring. Its service calls and observations are genuine; it is not an official benchmark. Weather field names, locations, and scoring rules do not enter shared engine code. A second materially different real surface is still required before claiming demonstrated cross-domain reuse.

## Curator-owned scope and iterative acceptance, 2026-11-04

User decision: the curator owns the completeness of the task surface, including what the agent must do, representative requests, and success criteria. Iterative kernel construction with checks that previously passing cases still pass is the chosen practical control. The engine is not required to certify that the curator's surface covers an entire domain or to add a separate semantic-completeness framework.

Within that curated scope, construct/refine S/F candidates from genuine execution and outcome feedback, then check new cases and previously passing construction/development cases before accepting the revision. Retain actual failures and their attribution. Existing OWL/HermiT, graph/function validation, immutable revisions, and evidence requirements continue to apply. Function replay and fresh whole-task success remain distinct evidence; old outputs are never substitutes for execution. Live-source cases are scored against their current evidence rather than requiring an obsolete answer value to remain identical.

Final held-out cases stay outside this refinement loop. Claims of coverage are bounded by the curated surface and recorded evaluations. Additional desired behavior is supplied through new curator-defined cases and a new candidate revision. This decision sets the acceptance approach; automatic MCP outcome-feedback refinement and regression gates remain implementation work, as tracked in work-plan.md.

The earlier [language-translation preservation plan](kernel-preservation-plan.md) explores discharging computational regression obligations with checked certificates. It is now deferred reference material. The active historical replay plan requires its own execution evidence and does not substitute that proposed proof path for replay.

### Focused stage contracts and deterministic coverage accounting

The November 4 prompt refactor separates requirement interpretation, schema drafting, evidence extraction, and function composition. One model can perform these bounded calls. The executor owns ordering, validation, probes, spending, and split boundaries. Exact prompt sources and assembled instructions are snapshotted for each MCP construction and attributed through its evidence.

Requirement inputs preserve each selected construction request and public completion requirement literally. The authoritative models and validators are in `oak.construction_contracts`; generated JSON Schema supplies model output contracts. Reference accounting catches dropped obligations, changed case attribution, unknown capabilities/functions, and unsupported or missing function mappings. Such checks establish declaration integrity only. Interpretation accuracy, function semantics, fresh task success, and unrepresented basic behaviors need separate evidence. No extra semantic-completeness framework or automatic case admission is introduced. The function count follows the supported executor bound instead of a prompt preference for one or two functions.

## Reusable engine and task boundaries

The deliverable is a reusable task-conditioned OaK engine. Coffee is the first real validation surface. Its names, schema, question templates, and answers must not determine the shared engine's behavior.

The paper distinguishes four objects and two loops (Sections 3.1 to 3.3):

| Object | What it represents | Reuse boundary |
| --- | --- | --- |
| O | The generic operator library | Shared primitives across task domains |
| S | Types, properties, identity keys, relations, and declared constraints | Constructed and refined for a task family, then frozen |
| G | Actual corpus facts instantiated under S, with evidence provenance | Built from each query's accompanying corpus in paper-style inference |
| F | Typed task functions realized over O and grounded in S/G | Constructed/refined, then reused as the frozen ReAct tool catalog |

The outer construction loop evaluates and improves S/F. The inner ReAct loop selects functions and arguments based on the query and observations. Fixed workflow stages and a frozen catalog do not imply a predetermined sequence of calls. The reusable kernel is K=(S,F), not a single permanent graph or a saved answer trajectory.

Keep the following responsibilities separate:

- **Shared engine:** construction prompts and contracts, OWL translation, validation, extraction/merge, generic operators, function realization, ReAct execution, revision workflow, checkpoints, and artifact evidence.
- **Task adapter:** task description, genuine corpus/query loading, construction/development/held-out partitions, benchmark-specific output formatting, and official scoring. An adapter supplies task inputs and evaluation semantics, not a handwritten solution or a preselected ontology disguised as discovery.
- **Generated kernel revision:** the actual task-conditioned S/F, their provenance, declared applicability, and validation evidence. Runs explicitly bind to a task and kernel revision.

Here, a task adapter is separate from the schema-compatibility adapter discussed below. The latter translates contracts between old and new kernel revisions.

Support multiple task/kernel records through explicit selection. Automatically choosing or combining ontologies for an arbitrary new task is an additional routing problem; the reviewed paper does not establish that mechanism. Reusing or incrementally updating G across queries also needs separate validation instead of being assumed from S/F reuse.

Before claiming demonstrated reuse, execute the same engine on a second materially different genuine task surface, such as TravelPlanner after Coffee. Each task must obtain its own kernel through the actual construction loop, with official evaluation and held-out queries. Domain setup may differ; core workflow/operator semantics must remain shared. A second loader alone is not evidence of successful transfer.

## Decisions where the paper is incomplete

The installed project-development and evaluation skills support decomposition, explicit contracts, persistent evidence, and outcome-based evaluation. They do not supply the missing OaK prompts or prove an ontology correct. Paper requirements and user constraints take precedence over generic skill defaults.

For each material missing detail, record its paper gap ID or user requirement, the chosen interpretation, alternatives and tradeoffs, the executable acceptance check, and the evidence/status. Make routine engineering choices autonomously. Escalate only an unresolved product preference or a necessary authorization that available evidence cannot settle.

| Decision surface | Required treatment before claiming it works |
| --- | --- |
| Construction prompts | Version Analyze, Draft/Repair, Extract, Compose, Judge, and ReAct prompts with typed inputs/outputs. Inspect actual model outputs and stage failures on real task inputs before fixing the contract. Mark our prompt wording as an implementation choice. |
| Schema and OWL mapping | Define the supported grammar and exact axioms. Check expressiveness against task requirements and actual evidence; check consistency/unsatisfiable classes with real HermiT. Keep open-world reasoning separate from data-integrity checks. |
| Function representation | Specify allowed operator compositions and supported pre/post-processing, typed contracts, failure behavior, and execution bounds. Validate real executions against the actual KG. |
| UI edits | Preserve the selected parent revision, proposal text, interpreted patch and diff. Route candidates through ontology, graph/function, and regression checks. Read-only questions cite artifacts without mutating them. |
| Schema quality | Evaluate requirement coverage, grounded extraction, function executability, held-out task success, and revision regressions separately. HermiT consistency or a favorable LLM critique alone is insufficient. |

There need not be one uniquely correct schema. Accept a candidate because its declared task coverage and constraints are supported by recorded checks and real execution evidence. Keep final held-out outcomes outside the construction/repair feedback loop. Failure can arise in extraction, functions, or planning even when the schema is adequate; diagnosis must inspect those stages before changing S.

This is a decision and validation policy. None of these runtime mechanisms is implemented or experimentally validated by writing this document.

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

The current release uses the React observation interface described in [the interface decision](ui.md), with Setup, Construction and Inference. The Typer/backend execution interface retains corpus and revision operations. The following original capabilities remain research requirements; manual suggestions, promotion and runtime intervention are not exposed in this observation release:

- Schema entity types, identity keys, properties, relations, constraints, OWL translation, and reasoner results.
- Graph records and edges with source provenance and extraction/merge versions.
- Function contracts, actual generated implementation or permitted composition, operator dependencies, and execution checks.
- Per-task input, selected function calls and arguments, observed results, final answer, score, latency, token/cost usage when reported, and relevant artifact versions.
- User suggestions, interpreted patches, parent/candidate differences, validation history, repair attempts, regression coverage, and promotion/rejection state.

Expose recorded evidence and concise decision summaries. Do not claim to expose private internal model reasoning.

Questions use an explicit artifact revision and remain read-only. Responses cite the relevant schema definition, graph evidence, function, or validation result. A text suggestion creates a candidate; it does not silently rewrite an active frozen kernel.

## Revision lifecycle

`text suggestion -> interpreted candidate patch -> candidate diff -> OWL/HermiT check and bounded repair -> graph/function compatibility -> impact analysis -> preservation certification where supported, real regression where required -> disposition`

Certification is planned, not implemented. A certificate records evidence; it does not itself promote a candidate or add controls to the observation UI.

The existing active revision remains available throughout. Repairs create new candidate versions or append explicit patch events. Promotion is atomic and never rewrites an earlier revision. Whether every promotion is automatic or requires user confirmation remains a product-policy question, not an invented paper requirement.

Schema changes can affect extraction, graph identity, graph validity, function compilation, and task planning. Function-only changes still receive the relevant compatibility and regression checks; running HermiT alone cannot validate arbitrary function code.

## Constrained adapter proposal

This section records the earlier adapter design. The active replay plan's Sections 4 to 6 own the initial transformation scope, shared revision edges, and composition requirements.

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

## Deferred reference: language-translation preservation, 2026-11-04

The methodology below is retained as design history. Its milestones and proof-based shortcuts are outside the sole active execution plan.

User decision: model each kernel revision as a translation of the parent's protected executable language. Preserve the entire inherited capability contract, with explicit input/output mappings and a relation between corresponding graph evidence. When adjacent certificates establish preservation and their assumptions compose, the newest revision inherits the earlier guarantees without separately executing all ancestor cases.

The methodology, theorem obligations, research basis, trust boundary, staged implementation, and detailed acceptance checks live in [Kernel preservation through verified language translation](kernel-preservation-plan.md). That plan owns the proposed methodology; future executable/API contracts must be authoritative Pydantic/code definitions rather than duplicated prose schemas.

Acceptance requires total translations on the protected old domain, no silently stronger preconditions, complete inherited coverage, and a checked chain bound to exact semantics and artifact versions. Exact computational preservation, conditional assumptions, counterexamples, unknown results, and invalid evidence remain distinct. Old empirical outcomes are not upgraded into universal correctness proofs. Approximate numeric agreement does not compose as exact equivalence.

Start with a restricted pure fragment and sound identity/rename/composition rules; expand to checked graph views and query rewrites. HermiT validity, graph/source preservation, actual interpreter correspondence, and fresh planner success retain separate obligations. Unsupported transformations use the existing real checks and cannot extend a certified chain. This is a local planning decision only, with no new runtime behavior, proof-tool dependency, or automatic refinement/promotion.

## Historical reference: cheap regression with explicit evidence limits

The selection strategy below is historical. The active replay plan initially executes every protected case for each candidate except exact cached checks, as defined in its Section 8. Dependency-based selective skipping is later work.

The following replay path applies when preservation is not certified or when the claim concerns behavior outside a certificate's scope. A complete valid certificate can replace affected-case execution for its stated computational preservation claim; it cannot replace fresh-task evidence by relabeling that claim.

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


## React observation release, 2026-11-04

The user authorized replacing Streamlit with the local React/FastAPI interface. Product contracts are authoritative Pydantic models, with generated frontend types and persisted cursor events. UI rendering follows stable event categories and labels rather than internal workflow node names. The construction algorithm remains one round with existing bounded repairs. Automatic additional rounds and outcome-driven refinement remain separate backend work. Public MCP HTTP and stdio are supported; HTTP authentication is deferred. New inference requests pin eligible kernels and never modify curated pools. Assessment, agent outcome and execution lifecycle remain independent. Read APIs, Replay and Reset never start execution. See ui.md for the screen behavior and the generated code reference for contracts.

## Superseded execution track: selective evaluation and anti-trajectory construction

The earlier approved work is retained in [selective-learning-plan.md](selective-learning-plan.md) as a historical reference. Its independent execution track is superseded by the historical replay plan. Reusable subtasks and generated checks may support that plan, but do not add separate acceptance requirements. Its old-run compatibility waiver and selective protected-case skipping no longer govern execution. Saved evidence, partial implementation, and budget reservations remain preserved.

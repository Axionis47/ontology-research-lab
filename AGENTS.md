# OaK project instructions

## Objective

Implement arXiv:2608.22974v1 faithfully, starting with a small real benchmark surface. Add a user-visible, versioned workflow for inspecting the schema S, knowledge graph G, and functions F, asking questions, and proposing changes.

Build a reusable task-conditioned OaK engine. A benchmark is a validation surface, not the architecture. Keep domain data loading, task descriptions, splits, and official scoring in task adapters. The shared engine must construct/refine domain schemas and functions, then reuse frozen kernels across queries. Do not hardcode benchmark schemas, question patterns, answers, or domain functions into the shared reasoning loop. Demonstrated reuse requires a second materially different real task surface through the same engine.

## User requirements

- Never use em dashes in authored documentation or user-facing writing. Preserve upstream source documents unchanged.
- No mocks, fake services, fabricated benchmark data, canned model responses, or simulated HermiT validation. Tests and demonstrations must exercise real components and genuine data.
- Observability is a primary requirement. Every meaningful artifact, revision, validation, and run must be inspectable and attributable to its inputs and versions.
- Preserve paper evidence as text before implementing it. Separate specified facts, deductions, engineering choices, and unresolved details.
- Use meaningful commits organized around reviewable capabilities. Include what was actually verified and any unverified behavior.
- Manage context and progress in project files. Read docs/work-plan.md and the relevant specification before continuing after a context refresh.
- Gemini CLI is authorized for independent review. Never claim a Gemini review ran unless it actually completed. Authentication is not configured as of initial setup.

## Workflow

Use the relevant installed skills under .agents/skills, especially project-development, filesystem-context, tool-design, evaluation, and advanced-evaluation. Load only the skills needed for the current work. The paper and user requirements take precedence over generic skill heuristics.

Keep source extraction under docs/paper. Keep project choices and acceptance criteria in docs/design.md. Update docs/work-plan.md with evidence, decisions, blockers, and the next bounded milestone.

The selected stack is fixed in docs/stack.md and the lockfiles. Prefer its off-the-shelf libraries. Use LangGraph for orchestration, LangChain for model/tool interfaces, and LangSmith for tracing/evaluation. Load the relevant LangGraph/LangSmith skills before implementing those integrations. Do not add a second workflow or observability framework without a concrete need and a recorded decision.

Code documentation and intermediate outputs are a primary deliverable. Generate API documentation from docstrings and stage reports from actual manifests. Each stage must persist its inputs, outputs, versions, validation, and failure evidence. Maintain one authoritative definition for each contract; do not create prose replicas that drift from code.

Implementation decisions must map to paper requirements or explicit user extensions. Do not silently replace OWL/HermiT with structural JSON validation, remove the ontology kernel to simplify architecture, or introduce neural weight training.

## Revision and evaluation invariants

- Frozen schema/function revisions are immutable. Changes create candidates with parent revision identifiers.
- Read-only questions do not create changes. Suggestions create explicit candidate patches with recorded interpretations and diffs.
- OWL/HermiT validity, graph/function compatibility, recorded-plan regression, and fresh agent task success are distinct evidence types.
- Replays execute real functions on real artifacts. Recorded outputs are comparison evidence, not substitutes for execution.
- Adapter proposals cannot access benchmark answers or special-case task IDs. Unsupported transformations fail explicitly.
- Preserve construction, development-regression, and final held-out boundaries. Never tune changes against the final held-out answers and report them as untouched evaluation.
- Do not promise that arbitrary schema changes preserve task success without fresh inference. Unknown dependency coverage requires a broader check.
- Before a substantial paid benchmark run, establish its provider/model configuration and spending bound. Authentication or budget gaps do not justify mocked results.

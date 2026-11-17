# Project working agreement

## Purpose and scope

Build and test a task-solving system that constructs a task-relevant ontology, grounds a knowledge graph in observations, executes through controlled actions, and improves reusable capabilities from evaluated failures.

AppWorld is the primary execution and evaluation environment. Use its actual tasks, APIs, fresh worlds, and official evaluator. Synthetic fixtures can test individual components, but cannot substitute for the requested AppWorld demonstration or count as native results.

Keep changes small. Test the existing slice before adding infrastructure or broadening the supported task family. This file defines intended responsibilities; it does not establish that those responsibilities are implemented.

## Model and runtime responsibilities

| Role | Assigned component | Responsibility |
| --- | --- | --- |
| Task actor | Configured local Qwen model | Solve the current task using the pinned ontology, graph queries, typed functions, and admitted tools. |
| Diagnostic judge | Installed Gemini CLI, using its configured model and login | Examine evidence, explain failures or fragile successes, and identify a supported improvement target. |
| Improvement proposer | Installed Gemini CLI, in a separate proposer call | Turn an evidence-backed diagnosis into one bounded candidate change. Do not assign this role to Qwen. |
| Task setup and graph ingestion | Trusted adapter/runtime | Bind the public task, construct its scoped representation, validate observations, and maintain graph revisions and provenance. |
| Action executor | Runtime and AppWorld MCP adapter | Validate and dispatch actual calls, record effects, and obtain fresh readback. |
| Outcome evaluator | AppWorld official evaluator plus deterministic contract checks | Establish task outcomes and preservation of unrelated state. |
| Candidate acceptance | Deterministic comparison and release controller | Accept or reject a candidate from actual evaluation evidence and regression checks. |

Do not silently exchange these roles, change providers, or use a substitute because a configured model is unavailable. Qwen can correct its own task-level arguments after validation feedback. That is different from rewriting tool schemas, ontology definitions, runtime policies, or repair machinery.

Confirmed by the user on November 16, 2026: Gemini serves both diagnostic judge and improvement proposer, through separate calls with distinct inputs, instructions, outputs, and role-labelled receipts. Use the CLI's configured model and login; record the model actually reported by each call. Qwen remains the task executor. Model availability is an operational fact, not permission to reassign a role.

## Task, ontology, graph, and actions

Keep these artifacts separate and link their versions:

- **Task specification:** the requested outcome, constraints, scope, and success requirements. Bind it to the actual AppWorld instruction; the solver cannot relax it.
- **Task ontology:** the relevant entity types, properties, relations, meanings, domain constraints, and action/function contracts needed for that task. Construct it from public task information and documented source/API contracts. Reuse relevant validated definitions and extend them only where the task requires a supported missing concept.
- **Knowledge graph:** concrete entities, property values, and relationships observed in the current task's world. Each fact needs source evidence and a revision. Missing, stale, or conflicting facts remain explicit.
- **Reusable computation:** mappings and functions that query the graph, combine constraints, select candidates, and prepare valid actions. This is distinct from storing more facts.
- **Action bindings:** links from typed operations to documented APIs, with inputs, preconditions, effects, and result contracts. Describing an action in the ontology does not execute it or grant permission.

The representation must fit the task at hand. Do not force unrelated tasks into a hardcoded Spotify or ticket ontology. If the current adapter cannot construct or bind the required representation, report that capability gap rather than fabricate support.

Before extending an ontology, retrieve the existing definitions, mappings, and functions and check semantic compatibility. Reuse does not mean regenerating everything or treating matching names as proof of identical meaning. Route a genuine definition gap to a separate Gemini proposer job with its source evidence and allowed scope. Validate and version the extension before it governs execution. Pin the resulting task package; do not rewrite its meaning during an active episode.

Reusable ontology definitions can persist across tasks. Instance facts do not carry over automatically: populate each AppWorld task's knowledge graph from that fresh world's actual observations, with its own identities, scope, and revisions.

Initial task representation is task setup. A new observed artist, follower count, or relationship is a graph update. A reusable change to a type, mapping, relation meaning, function, or interface is an improvement candidate. Do not turn every new record or missing observation into a schema repair.

The graph writer admits facts from validated tool results and checked derivations. A model assertion, proposed edge, judge hypothesis, or successful HTTP response alone is not verified domain knowledge. Never use hidden AppWorld solutions or evaluator implementation to populate the ontology, graph, or actor context.

Qwen receives relevant interfaces and bounded graph/evidence results. It can request queries or additional observations; it does not need the whole ontology and graph pasted into every prompt. API effects pass through the executor, and their readback updates the graph before dependent conclusions are reused.

For the current AppWorld Spotify task, the ontology includes `Account`, `Artist`, genre/follower-count properties, the `follows` relation, and the follow action contract. The graph contains the artists and relationships actually observed in that world's APIs. The requested genre and threshold belong to the task binding. Qwen queries those facts and proposes follow actions; Gemini later examines whether failures came from the representation, evidence, computation, or execution. A different task may need a different ontology and action set.

## What Gemini judges

Gemini receives the original goal and constraints, the exact ontology/package version, relevant graph facts and provenance, the recorded actions and original tool responses, and permitted evaluation feedback. Evidence coverage and omissions must be explicit.

The judge distinguishes:

1. An actor choice or argument error.
2. Missing, stale, or incorrectly ingested graph evidence.
3. A mapping error or a missing/incorrect ontology concept.
4. A faulty function, constraint composition, or action binding.
5. A context/recovery problem.
6. An infrastructure, authentication, adapter, or evaluator failure.

For each finding, return the evidence references, observed symptom, supported cause or hypothesis, uncertainty, smallest proposed repair target, a distinguishing test, and behavior that must be preserved. Abstain when evidence is insufficient. A suggested repair target is not an implemented patch.

Gemini's diagnosis does not replace official task evaluation, prove its own suggestion works, or authorize promotion. Keep model diagnosis, deterministic task outcome, and measured candidate improvement as separate records. The existing deterministic `judge_episode` function is an evidence/contract assessment, not a Gemini judgment.

## What Gemini proposes

The proposer call receives the validated judge finding, referenced original evidence, parent ontology/package version, exact editable surface, smallest reproducer, preservation requirements, and previous rejected candidates. It returns one bounded candidate, its intended mechanism, and the checks needed to establish improvement. Missing evidence or an unsupported edit must be explicit.

The judge call diagnoses and recommends a repair target. The separate proposer call authors the candidate. The runtime stages and evaluates it. Neither Gemini call can activate its own result. Using the same model for both roles is not independent verification; AppWorld outcomes and deterministic regression gates remain the acceptance basis.

## Improvement cycle

1. Bind the real task and prepare its ontology, graph scope, action contracts, and pinned package version.
2. Let Qwen execute; record complete traces, source observations, graph revisions, and final native outcomes.
3. Ask Gemini to diagnose the recorded run with bounded access to original evidence.
4. Route a missing observation to evidence acquisition, and an infrastructure fault to operational repair. Neither automatically justifies a domain-package patch.
5. Invoke Gemini in a separate proposer call with the validated finding, allowed edit surface, original evidence, a reproducer, preservation cases, and prior rejection feedback.
6. Stage one small candidate. Keep task requirements, evaluator, native data, permissions, hard budgets, and trace integrity outside its editable surface.
7. Compare parent and candidate in fresh AppWorld worlds. Check the targeted failure and previously passing behavior; retain every failure, timeout, and missing result.
8. Activate only a measured improvement that passes the required gates. New episodes use the accepted version; active episodes retain their pinned version.

Ontology changes require evidence of a missing or incorrect definition. Prefer a graph observation, mapping correction, or function correction when that is the actual problem. Separate ontology changes from provider-facing JSON-schema changes and from runtime engineering fixes.

If Gemini judging is unavailable, record `JUDGE_UNAVAILABLE`. If its proposer call fails, retain the diagnosis and record the proposal-stage failure separately. Continue independent execution or evidence collection where useful, but do not substitute Qwen or claim that the judged improvement cycle completed. Bounded search, a scripted actor, or an assistant-authored patch must never be relabeled as the assigned model's improvement.

## Evidence and reporting

- Record actual role/provider/model identities, task IDs, task exposure, ontology/package versions, graph provenance, and source hashes for each experiment.
- Report native AppWorld outcomes separately from unit tests and synthetic fixtures.
- Separate a new improvement from replay of an older retained program. Separate task success from diagnosis success and proposal acceptance.
- Preserve rejected and withdrawn experiments. Resume from existing evidence instead of rebuilding a substitute demonstration.
- Do not claim broad task-conditioned ontology construction, general transfer, or a complete Gemini loop from the current narrow adapter.

Current implementation boundaries are described in [the connected inference notes](docs/system/19-connected-inference.md), [computational protocol](docs/system/12-computational-learning-protocol.md), and [measured results](docs/system/20-live-acceptance.md). Older documents contain historical plans and broader model options. Follow the role assignment here for new work, and label implementation gaps honestly.

## Communication

- Never use em dashes in conversation or user-facing writing.
- State what ran, what changed, what passed, what failed, and what remains unimplemented.
- Do not make major code changes while the user is asking to inspect or demonstrate the existing loop. Minor necessary fixes remain within the user's authorized scope.

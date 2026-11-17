# Complex ontology, same six consumption strategies

**Executed: [actual Gemini answers, token usage, contexts, and gate results](RESULTS.md).** All six selected the correct pair with complete evidence. Five passed their protocol; the graph-query run skipped its required interface call.

Follow-up: [combined interfaces with model recovery after delegation revocation](combined-recovery/README.md).

This is a second synthetic teaching pilot. It changes the task's complexity while keeping the six strategies from the earlier study. Within this pilot, every strategy receives the identical task and all 53 fact records, uses the same frozen source ontology and ten rules, and passes through the same evaluation and action gate.

## The task

Select **two different people**, an Ops approver and a Security approver, for deployment `d2` of LoginService on November 16, 2026. The deployment is Production, EU, risk level 4, and was authored by Maya. The two approvers must belong to different home teams.

The model must combine:

- Service → Project → Organization scope coverage.
- Person → Grant or Person → Delegation → direct Grant authority.
- Grant and delegation risk caps.
- Time, environment and region qualification through certificates.
- Explicit deny precedence over otherwise valid authority.
- Separation from the deployment author.
- Home-team independence across the selected pair.

An individual candidate passing all individual rules does not imply that a pair containing that candidate is valid.

## Candidate traps and the independent expected answer

| Person | Relevant situation |
| --- | --- |
| Maya | Has authority but authored the deployment |
| Noah | Grant risk cap is 3, below deployment risk 4 |
| Rin | Certificate expired |
| Tao | Eligible Security approver, Identity team |
| Iris | Own certificate expired, but still holds a valid delegable grant |
| Uma | Eligible delegated Ops approver, Identity team, conflicts with Tao's team |
| Vera | Eligible delegated Ops approver, Platform team |
| Wes | Grant covers a sibling project, not Atlas |
| Xena | Delegation references a grant that prohibits delegation |
| Yuri | Certificate covers US rather than EU |
| Zoe | Otherwise eligible, but an active deny overrides the grant |

The hand-authored [oracle](oracle.json) expects Vera as Ops approver and Tao as Security approver. The oracle is used by local tests only and is never included in model payloads or tool responses. The domain function computes its answer from records and rules, not by reading the oracle. This case is exposed for teaching, not a sealed benchmark.

```text
Vera → del-Vera → g-Iris → project-atlas ← svc-login ← d2
  │                 │
  │                 └─ valid direct grant, delegable, sufficient risk cap
  ├─ c-Vera: valid EU/Production certificate
  └─ m-Vera → Platform

Tao → g-Tao → project-atlas
  ├─ c-Tao: valid EU/Production certificate
  └─ m-Tao → Identity

Platform != Identity; neither selected person is Maya.
```

The ontology explicitly says the grant holder's personal certification is not required to delegate. The recipient must be certified to approve. This distinction makes Iris's expired certificate relevant to Iris's own eligibility but not automatically to Vera's delegated authority.

## Six strategies, unchanged in purpose

| Project | Definition access and computation |
| --- | --- |
| [Full injection](01-full-definitions/README.md) | All 22 source ontology entries in context |
| [Retrieved definitions](02-retrieved-definitions/README.md) | Exact relevant definition dependency closure, with no fact filtering |
| [Schema inspection](03-schema-inspection/README.md) | Catalog first; Gemini must request the eligibility definitions |
| [Graph queries](04-graph-queries/README.md) | Relevant definitions plus generic record queries and directed traversal |
| [Typed function](05-typed-function/README.md) | Relevant definitions plus computation of all valid panels |
| [Constraint service](06-constraint-service/README.md) | Relevant definitions plus checks of only the panels Gemini proposes |

All methods see the same facts initially. Query/function/checker calls add computed observations without changing the source world. This isolates ontology access and computation delegation from differences in initial fact retrieval.

## More explicit evaluation than the first pilot

The prompt tells every method exactly what evidence categories to cite: Deployment, Service, Project, Organization, and each selected person's Person, Membership, Team, Certificate, source Grant, and Delegation where applicable. The score requires a complete proof for the selected valid panel, valid record IDs, all ten rule IDs, and pinned versions. Extra known record IDs are allowed; fake or duplicate IDs are not.

Selection correctness, proof completeness, version correctness, rule coverage and protocol adherence are stored separately. The four interface-based methods must actually use their interface; inspection must expose eligibility rules. No candidate is accepted because Gemini says its own answer is correct.

The same gate checks all proposals at revision 7. Then the fixture revokes `del-Vera` and increments the graph to revision 8. We check both the stale proposal and a copy claiming the new revision: a version number alone cannot bypass recomputed eligibility. These are local checks, not external writes or a measured recovery loop.

## Frozen execution plan

- Configured installed Gemini CLI model and login; no provider or model override.
- One attempt per strategy, no automatic reruns after a bad answer or timeout.
- Order shuffled once using seed `20261116`, recorded before calls.
- Maximum eight CLI invocations per strategy and the existing configured 180-second per-call timeout.
- A failed strategy does not suppress the remaining independent strategies.
- Source, rule, task, fact, oracle, policy and configuration hashes are recorded before execution.
- Original responses, errors, token statistics and local interface observations are preserved.

CLI built-in tools are denied. Application requests are JSON proposals interpreted by the local dispatcher. Every continuation is a fresh CLI invocation with the fixed base context and accumulated bounded history; repeated system/routing overhead is part of reported usage. This is not an optimized persistent agent session.

## Run

```sh
python3 -m unittest discover -s learning-labs/ontology-consumption-complex -p test_engine.py
python3 learning-labs/ontology-consumption-complex/run.py
python3 learning-labs/ontology-consumption-complex/run.py --live
```

Preparation makes no model calls. A single project can be run through its own `run.py`, or with `--experiment 01` through `run.py` here. Every invocation gets a fresh evidence directory. Prior simple-pilot results are unchanged.

## Limits

This remains one manually designed synthetic task with one attempt per method. It cannot establish general superiority or a stable cost ranking. Functions and checkers contain hand-engineered rule implementations, so the comparison changes where reasoning occurs. Dependency retrieval is exact, not an embedding-search experiment. The records use date-only ISO strings and a complete authoritative fixture, not uncertain real-world identity resolution. The graph is represented as typed JSON records, not an OWL reasoner or SPARQL engine. Pinning, proof checks and gates are application policies. No ontology learning, Gemini diagnosis/proposal cycle or AppWorld evaluation is performed.

The existing [standards map](../STANDARDS.md) remains applicable; none of these interface designs is being presented as a new industry standard.

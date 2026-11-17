# Ontology experiments and the repair loop

**[Start with the complete repair-loop report](experiments/01-improvement-loop/README.md).** It shows the original task, observations, failure, separate Gemini diagnosis and proposal, exact before-and-after function, acceptance checks, and successful later tasks.

The native experiment repaired one reusable artist-selection function. The original function selected by genre but omitted the requested follower-count threshold. Gemini added an existing numeric-filter operator in a separate proposer call. After validation and activation, three subsequent AppWorld episodes passed all five official checks each.

The [ten step-by-step reports](experiments/02-ontology-concepts/README.md) explain smaller component experiments. Every lesson gives the concrete input, ordered operations, actual answer, checker result, and repair status. Those ten lessons did not each perform an improvement cycle.

## Read the reports

| What you want to understand | Report |
| --- | --- |
| What failed, what was repaired, and what worked afterward | [Complete native harness loop](experiments/01-improvement-loop/README.md) |
| What happened in each of the ten lessons | [Ten experiments from input to result](experiments/02-ontology-concepts/README.md) |
| How the model consumed definitions and facts | [Interface comparisons](experiments/04-model-consumption/README.md) |
| How observations entered the graph and how stale results were handled | [Graph ingestion and recovery](experiments/03-runtime-graph/README.md) |
| How the pieces fit and which results are separate | [Report index](experiments/README.md) |
| Earlier successes, failures, and unavailable runs | [Evidence inventory](experiments/INVENTORY.md) |

A harness is the program around the model that supplies inputs, runs allowed operations, records evidence, checks outcomes, and manages any repair cycle. An answer check, an executed action, a recovered task, and an accepted reusable repair are different outcomes.

## The six ontology-consumption methods

Within each six-method comparison, the task, initial facts, source ontology, and rules stayed fixed.

| Method | What the model received or requested |
| --- | --- |
| Full definitions | The entire ontology in the prompt. |
| Retrieved definitions | Relevant definitions and their exact dependencies. |
| Schema inspection | A catalog and an interface to request definitions. |
| Graph queries | Definitions and generic queries/traversals composed by the model. |
| Typed functions | Domain operations computing valid candidates. |
| Constraint service | Checks of candidates proposed by the model. |

In the single-approver comparison, all six selected Noah; four passed the complete citation rubric. In the harder comparison with 53 facts and ten rules, all six selected Vera and Tao with complete evidence; five passed the full protocol. The graph-query run answered without calling its interface, so it did not demonstrate that consumption method.

A separate recovery run returned revocation feedback to Gemini. It recomputed against the updated graph and correctly returned no valid pair. The outcome was RECOVERED_BLOCKED, with no external deployment and no package repair.

The reports link exact submitted prompts, responses, interface results, versions, graph revisions, citations, and token measurements. Failed citations, skipped interfaces, earlier timeouts, and native validation failures remain recorded.

These studies used synthetic supplied facts, exact dependency retrieval, and hand-written domain functions. They do not establish a reliable ranking at scale. The native Spotify improvement has its own AppWorld outcomes and role-labelled Gemini diagnosis/proposal evidence.

## Repository contents

| Location | Content |
| --- | --- |
| `experiments/` | Presentation pages and the evidence inventory |
| `learning-labs/` | Concept tests, model comparisons, inputs, and saved responses |
| `runs/` | Selected result files and linked evidence |
| `docs/system/` | Protocols, implementation notes, and historical results |
| `appworld_runtime/`, `react_runtime/`, `repair_runtime/` | Supporting runtime source |
| `scripts/`, `tests/`, `examples/`, `config/` | Runners, component tests, fixtures, and configuration |

## Scope

Qwen executes tasks in the native loop.
Gemini diagnoses failures and proposes changes through separate calls.
The runtime controls actions and acceptance.
The successful change improved a reusable function.
It did not change model weights or construct a new ontology.

The teaching studies use synthetic inputs.
Their results do not count as native AppWorld scores.
The repository does not establish broad ontology construction or general task transfer.

## Published evidence

This is a publication snapshot of an existing local experiment workspace.
It does not contain installed environments, AppWorld datasets, credentials, or complete runtime databases.
It does not contain raw native MCP session transcripts.

The export replaces local workspace and home paths with placeholders.
It replaces email addresses in selected JSON evidence with a placeholder.
The [publication manifest](publication-manifest.json) records the original export and its file hashes. Later documentation revisions are recorded in Git history; the initial manifest remains a historical export record.
Original evidence hashes inside reports remain unchanged.
These hashes identify the local originals, not modified publication copies.

Model answers, task scores, and acceptance decisions have not been rewritten.
Some receipts refer to local artifacts outside this selected snapshot.
Those references do not establish that every runtime artifact is available here.

Live repetition requires the dependencies and provider setup described in [MODEL_SETUP.md](MODEL_SETUP.md).
Installing dependencies or preparing prompts does not create a new measured result.

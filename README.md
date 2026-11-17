# Ontology experiments

This repository contains experiment code, demonstrations, and recorded evidence.
The reports show what happened, the decision rules, and the limits of each result.

**[Start with the demonstrations](experiments/README.md).**

## Main results

| Experiment | Recorded result | Limit |
| --- | --- | --- |
| AppWorld improvement loop | Three tasks failed before a function correction. All three passed afterward. A fresh automatic repeat also passed. | One exposed Spotify task family |
| Ten ontology concept tests | All ten Gemini responses passed their reference checks. | Synthetic teaching cases |
| Model access comparisons | Different interfaces produced correct answers, with some citation and interface-use failures. | Small, supplied tasks and facts |
| Graph-change recovery | The runtime blocked a stale proposal. Gemini recomputed and found no valid action. | Synthetic case; the approval task remained blocked |

## Read the reports

1. Read the [ten concept demonstrations](experiments/02-ontology-concepts/README.md).
2. Read the [model-access comparisons](experiments/04-model-consumption/README.md).
3. Read the [graph observations and changes](experiments/03-runtime-graph/README.md).
4. Read the [native improvement loop](experiments/01-improvement-loop/README.md).
5. Use the [full inventory](experiments/INVENTORY.md) to inspect earlier successes and failures.

Each demonstration gives starting conditions, recorded steps, results, logic, limits, and evidence links.
The prose uses an ASD-STE100-style format.
A full STE dictionary review has not been completed.

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
The [publication manifest](publication-manifest.json) records original and published file hashes.
It lists the changes for each copied file.
Original evidence hashes inside reports remain unchanged.
These hashes identify the local originals, not modified publication copies.

Model answers, task scores, and acceptance decisions have not been rewritten.
Some receipts refer to local artifacts outside this selected snapshot.
Those references do not establish that every runtime artifact is available here.

Live repetition requires the dependencies and provider setup described in [MODEL_SETUP.md](MODEL_SETUP.md).
Installing dependencies or preparing prompts does not create a new measured result.

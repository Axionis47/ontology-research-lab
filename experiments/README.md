# Experiment reports: what ran, what changed, and what worked afterward

Start with the [complete AppWorld repair-loop report](01-improvement-loop/README.md). It follows one recorded run from the original task through failure, diagnosis, the exact candidate change, validation, activation, and later task results.

The native result was a repair to one reusable artist-selection function: it originally applied a genre condition but omitted the follower-count threshold. A separate Gemini proposer call added the missing numeric-filter operation. The runtime tested and accepted the candidate. Three later episodes passed all five official AppWorld checks each.

The [ten ontology experiments](02-ontology-concepts/README.md) explain individual concepts using small supplied examples. Their report now shows the concrete input, ordered operations, actual answer, checker, and repair status for every lesson. They did not each run a repair cycle.

## Choose the report by the question you want answered

| Your question | Report | Kind of result |
| --- | --- | --- |
| What failed, what exactly was repaired, and what worked later? | [Full AppWorld harness loop](01-improvement-loop/README.md) | Native execution, Gemini-authored function change, measured later reuse |
| What happened in each of the ten small experiments? | [Ten experiments, step by step](02-ontology-concepts/README.md) | Ten model answers and deterministic checks; no automatic repair |
| How did text, definitions, queries, and functions reach the model? | [Model-consumption comparisons](04-model-consumption/README.md) | Interface-use, answer, evidence, and token measurements |
| How did source observations become graph facts, and what happened after a fact changed? | [Graph ingestion and recovery](03-runtime-graph/README.md) | Native observation flow plus a separate synthetic recovery run |
| Where are earlier failures and retained experiments? | [Evidence inventory](INVENTORY.md) | Historical records, including failed and unavailable runs |

The native tasks ran in AppWorld's simulated applications through its APIs and official evaluator. The teaching examples used fictional people and services. Neither category is a claim that a real Spotify account or production deployment was changed.

## How to read a run

A **harness** is the program around the model: it supplies inputs, invokes the model, runs allowed operations, records evidence, and checks outcomes. The harness may implement an improvement loop, but a model call followed by a checker is not by itself an improvement loop.

For a repair claim, follow all of these links in the evidence:

~~~text
Original task and initial state
  → original program or actor attempt
  → recorded failure
  → diagnosis tied to original evidence
  → separately authored candidate
  → parent/candidate comparison and preservation checks
  → fresh execution result
  → acceptance or rejection
  → later task outcome using the accepted version
~~~

For a component test, the report ends at its actual stopping point. If the model only proposed a read, it does not say that the read executed. If a local boolean changed, it does not say that a real service deployed. If no candidate was authored, it says that no repair occurred.

A passing answer, a passing evidence check, a valid tool call, a successful application action, and an accepted repair are separate results. The reports identify which one was measured.

## Where the building blocks sit

| Building block | Role in the recorded system | Boundary |
| --- | --- | --- |
| Ontology and contracts | Define types, properties, relation meanings, and permitted operation shapes. | A stored role definition does not grant database access. |
| Task binding | Supplies this task's genre, threshold, scope, and required effect. | The actor cannot relax the goal. |
| Knowledge graph | Holds observations from the current world, with provenance and revisions. | New tasks need fresh instance facts. |
| Reusable functions | Compute selections from the graph and task parameters. | The native repair changed one such function. |
| Executor and readback | Dispatch operations and observe resulting state. | A model proposal alone produces no effect. |
| Storage | Local SQLite indexes and saved JSON artifacts retain traces, packages, and results. | The current implementation does not provide full storage-layer RBAC. |
| Evaluation and release control | Check outcomes, preserve required behavior, and activate a measured improvement. | Gemini cannot accept its own candidate. |

Qwen is the native task actor. Gemini has separate diagnostic and proposer calls. In the ten teaching experiments, Gemini was explicitly the experimental participant; those trials did not replace Qwen's assigned native role.

The [project agreement](../AGENTS.md) defines these responsibilities. The [implementation notes](../docs/system/19-connected-inference.md) and [native result history](../docs/system/20-live-acceptance.md) describe the current narrow adapter and its limits.

The reports reconstruct saved runs. Documentation edits do not create new model calls, native task outcomes, or repaired capabilities. Original responses, failed attempts, and acceptance records remain the evidence.

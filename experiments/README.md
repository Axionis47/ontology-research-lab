# Experiment demonstrations

These pages explain recorded experiments.
The format uses short sentences and fixed technical terms.
The format follows principles from [ASD-STE100](https://www.asd-ste100.org/STE_faq.html).
A full STE dictionary review has not been completed.

## Main result

The AppWorld loop improved one reusable function.
Before the change, none of the three tasks passed.
After the change, all three tasks passed.
A separate run repeated the automatic loop.

The result applies to one Spotify task family.
It does not establish automatic construction of new ontologies.

## Read the demonstrations in this order

| Part | Demonstration | What it explains |
| --- | --- | --- |
| 1 | [Ten ontology concepts](02-ontology-concepts/README.md) | Types, facts, evidence, rules, actions, and versions |
| 2 | [Model access to definitions and facts](04-model-consumption/README.md) | What each model received and how the test evaluated its answer |
| 2 | [Graph observations and changes](03-runtime-graph/README.md) | How observations entered the graph and how a changed fact affected an action |
| 3 | [AppWorld improvement loop](01-improvement-loop/README.md) | How a failed task led to a tested function change |

These parts organize existing work.
They do not represent new experiments.

## Format for each demonstration

1. State the purpose.
2. State the starting conditions.
3. Show the actions in order.
4. State the result of each action.
5. State the rule that explains each decision.
6. State the final result.
7. State the limits.
8. Link the original evidence.

The action column describes recorded behavior.
The logic column explains the applicable rule.
It does not claim access to a model's internal reasoning.

## Technical terms

| Term | Meaning in these reports |
| --- | --- |
| Ontology | Definitions of types, properties, relations, and applicable rules |
| Graph | Concrete records and relations expressed with those definitions |
| Observation | Data returned by a source operation |
| Evidence | A stored record that supports a stated result |
| Runtime | Software that controls execution, records results, and applies required checks |
| Adapter | Software that connects the runtime to an application's APIs |
| Function | A reusable computation with defined inputs and outputs |
| Candidate | A proposed change that has not yet passed the acceptance checks |
| Revision | An identifier for a recorded graph state |
| Pinned version | The version that an episode must continue to use |
| Episode | One task execution with its own recorded state and actions |
| Synthetic case | A constructed test example |
| Native AppWorld task | A task executed in AppWorld and evaluated by its official evaluator |

## Read the scores correctly

A correct model answer is one result.
A complete evidence citation is a separate result.
Correct interface use is another result.
A blocked action can show correct control while the task remains unfinished.

Synthetic cases do not count as native AppWorld tasks.
Repeated runs do not create new independent task families.

## Other recorded experiments

The [full inventory](INVENTORY.md) includes earlier successes, failures, and component tests.
Each entry links to recorded evidence.
Original source reports and receipts remain unchanged.

The [project agreement](../AGENTS.md) defines the model roles.
Qwen executes tasks.
Gemini diagnoses failures and proposes changes through separate calls.
The runtime decides whether a candidate can become active.

# Ten ontology micro-experiments

**Read the [ten experiments step by step](../experiments/02-ontology-concepts/README.md), then the [complete native repair loop](../experiments/01-improvement-loop/README.md).** The first explains component checks; the second shows a failed task, a measured function repair, and successful later executions.

[All project experiments](../experiments/README.md) collects these ten lessons, the AppWorld improvement loop, the later consumption comparisons, and graph population/runtime work.

**Latest: [ten Gemini CLI experiments](GEMINI-START-HERE.md).** Each lesson now has a Gemini prompt, input, held-out reference answer and independent checker. Use `python3 learning-labs/gemini_experiments.py --live` to run them with the CLI's configured model and login. The commands below retain the original deterministic companion demonstrations.

**All ten Gemini lessons ran and passed. [Exact answers and receipts](GEMINI-RESULTS.md).**

These are parallel, independently runnable learning projects. Read them in numerical order; no lesson needs the previous lesson's mutable state. They teach mechanisms, not a replacement benchmark. All default worlds are synthetic. No successful fixture counts as an AppWorld outcome or a Gemini-authored improvement.

**Built and run:** [measured results](RESULTS.md) include 48 default checks and six actual configured-Qwen trials, with original receipts. All three model interfaces answered these small cases correctly; this is not evidence that ontology improved accuracy.

## Start here

From the repository root:

```sh
python3 learning-labs/run_all.py
```

The runner saves an original JSON result for each project, source hashes, and a summary in a new timestamped `learning-labs/results/` directory. Nonzero exits and missing results remain failures. Default execution needs no model, credentials, installation, or external writes. Experiment 6 separately offers a live configured-Qwen run; preparation alone is not a model result.

| Project | Question to settle | New terms |
| --- | --- | --- |
| [01](01-triples/README.md) | How does a sentence become queryable? | Entity, predicate, triple |
| [02](02-ontology-vs-facts/README.md) | Is a new person a new ontology? | Class, instance, ontology, graph |
| [03](03-constraints-provenance/README.md) | Does valid structure mean true? | Constraint, provenance, admission |
| [04](04-relationship-entities/README.md) | Where do role, scope and expiry belong? | Relationship entity, literal |
| [05](05-traversal-inference/README.md) | Does a path establish authority? | Traversal, inference, open world |
| [06](06-model-consumption/README.md) | What exactly does the model receive? | Context, interface, query result |
| [07](07-runtime-enforcement/README.md) | Can a model bypass a missing prerequisite? | Precondition, dispatch gate |
| [08](08-fact-invalidation/README.md) | What happens when evidence changes? | Revision, dependency, invalidation |
| [09](09-ontology-extension/README.md) | How do we add a missing concept? | Extension, migration, unknown |
| [10](10-semantic-version-change/README.md) | What if a definition changes meaning? | Breaking change, pinning, regression |

Each project contains its input, executable demonstration, explicit expectations, counterexamples, and interpretation limits. Read its README before its code. Inspect the result JSON alongside the input, rather than accepting a green pass without examining what was tested.

## One distinction to keep visible

```text
Sentence: Maya maintains LoginService.
Triple:   (Maya, maintains, LoginService)
Meaning:  maintains relates a Person to a Service.
Evidence: source receipt says this relationship currently holds.
Rule:     a maintainer may deploy only with the required approval.
Runtime:  checks the rule before dispatching deployment.
```

A triple can be wrong. A schema can be wrong. An LLM can misread a correct schema. Evidence can be stale. These experiments isolate those failure modes.

## Standards and execution boundaries

Read [STANDARDS.md](STANDARDS.md). Companion Turtle, SPARQL and SHACL files illustrate established formats. The dependency-free Python lessons are explicit small computations, not complete RDF/OWL reasoners or SHACL implementations. Do not describe their passes as standards conformance certification.

Facts changing is different from definitions changing. In lesson 8, update graph revisions and recheck dependent conclusions. In lesson 9, propose a new representation and migrate only supported values. In lesson 10, evaluate changed meaning and keep active episodes pinned. Automatic invalidation and package promotion are application policies, not magic supplied by RDF.

## Connection to the real project

The actual runtime and AppWorld evidence remain authoritative: [connected inference](../docs/system/19-connected-inference.md) and [measured native results](../docs/system/20-live-acceptance.md). The November 16 native run demonstrated separate Gemini diagnosis and proposal, a tested function improvement, and successful subsequent tasks. Older unavailable-judge and search-retention results remain historical records. The lesson suite did not execute or establish those native outcomes.

Qwen is the assigned actor. Gemini CLI has separate diagnostic and proposer roles. A fixture written for teaching is not a model proposal. There is no substitution when either configured provider is unavailable. The full native improvement experiment requires fresh AppWorld executions and the official evaluator; these labs do not manufacture that result.

# Same task, five ways to consume the domain model

**[Actual Gemini results, contexts, token counts and stale-action outcomes](RESULTS.md).**

Task: choose an eligible approver for LoginService's production deployment on November 16, 2026. The deployment author is Maya.

| Person | Observed assignment | Why it matters |
| --- | --- | --- |
| Maya | Current production approver | Cannot approve her own deployment |
| Noah | Current production approver | Eligible at graph revision 1 |
| Rin | Current staging approver | Wrong environment |
| Tao | Production approver whose assignment expired | Wrong validity interval |

Forty other-service assignments are also present in the same source world. Every interface uses the same definitions and requirements. The source graph is represented as assignment entities with relationship fields in JSON, not a complete RDF store.

## Interfaces under comparison

| Interface | What enters the model's submitted context | What software does |
| --- | --- | --- |
| Full text | Rules, task, deployment and all 44 assignments rendered as sentences | Only serialization |
| Full structured | The same information as JSON | Only serialization |
| Retrieved fragment | Rules, deployment and four target-service assignments | Deterministically filters by service; does not choose the approver |
| Graph queries | Rules and two documented read interfaces; requested observations arrive on later turns | Executes validated read requests, with coverage and revision |
| Typed function | Rules and one eligibility-function interface; computed candidates and exclusions arrive on later turns | Evaluates all eligibility predicates against the graph |

These are application protocols, not five industry standards. The model sees textual tool interfaces and emits JSON requests. The Python runtime validates and executes those requests locally, then submits the observation in the next CLI call. This is a bounded propose/execute/observe loop, not native Gemini CLI function calling. All built-in CLI tools are disabled.

Every continuation includes the same base payload and complete bounded application history. Each CLI invocation is fresh, so system/routing overhead is incurred again. This setup measures this implementation, not an optimized cached production session. The returned statistics, rather than character estimates, supply token totals.

## The stale-action test is separate

After each protocol returns its selection, the test revokes Noah's assignment and increments the graph to revision 2. The model did not observe this later change. Apply the exact same proposal to two local execution fixtures:

1. An unguarded dispatcher accepts a structurally valid selection.
2. A gate checks current revision and recomputed eligibility before changing the local state.

The second lane can block a stale action for **any** input protocol. It would be misleading to credit the typed function alone for that protection. No actual deployment or company system is modified. In this single-process fixture, the check and state transition are immediate; a real remote backend would need appropriate concurrency controls.

## Limits to discuss

- Full context has irrelevant records and more reading work. A pass does not prove it will fail when context grows further.
- Structured context still leaves constraint composition to the model.
- Retrieved context is small only because this fixture's trusted retriever knows the correct service boundary. Missing relations or poor coverage would undermine the answer.
- Graph queries require correct tool selection and arguments; extra calls can cost more than a larger single prompt.
- Typed functions make supported rules deterministic, but are only as correct as their implementation and scope. This function explicitly refuses a different task binding.
- A gate enforces checked conditions; it does not invent missing information, guarantee an alternative candidate, or prove a source is truthful.
- The forty irrelevant assignments are a modest distractor condition, not a context-window stress benchmark. No strong reliability or superiority claim follows from one example.

## Run

```sh
python3 learning-labs/protocol-comparison/run.py
python3 learning-labs/protocol-comparison/run.py --live
```

Preparation makes no model calls. The live runner uses the configured Gemini CLI and login, at most 14 invocations, with the existing per-call timeout and no model override. Original prompts, responses, local tool observations and action-probe outcomes are saved under a fresh `results/` directory. AppWorld and Gemini diagnosis/proposal are not exercised.

The exact submitted user prompts are captured. Gemini CLI's internal system context is not fully observable in this runner; provider token totals include that overhead and its internal router. No claim is made that the captured user prompt is the entire model context.

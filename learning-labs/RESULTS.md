# Actual lesson results, November 16, 2026

## What changed

Added ten independent projects, their input artifacts and READMEs, a shared standards map, and a suite runner. Production runtime code, task packages, provider configuration, AppWorld worlds, and prior evidence were not edited. These lessons introduce mechanisms without claiming a new native improvement.

## Default checks

All ten default programs exited successfully. There are 48 named checks: 46 deterministic component checks plus two interface-preparation checks. Experiment 6's default status is explicitly `PREPARED_NOT_RUN`. [Original suite summary](results/20261116T181747.466229Z/summary.json) and its sibling files retain stdout, stderr, exit codes, and source hashes. The existing query slice also passed its four unit tests before the lessons were built.

The tests include reversed relationships, ungrounded assertions, wrong environments, expired assignments, missing approvals, stale dependencies, unsupported migration defaults, and a regressing change candidate. These intentionally bad inputs must be rejected for the corresponding checks to pass.

## Actual model experiment

The unchanged configured actor `qwen3:8b-q4_K_M` answered two cases through three interfaces. It made eight actual model calls. [Original live receipt](06-model-consumption/results/20261116T181817940419Z.json) records complete requests, tool results, responses, returned model identities, and usage.

| Interface | Valid production approval | Only staging approval | Input tokens, both cases | Output tokens, both cases |
| --- | --- | --- | ---: | ---: |
| Text observations | Noah, e2 | unknown, e1/e2 | 455 | 45 |
| Structured observations | Noah, e2 | unknown, e1/e2 | 473 | 45 |
| Tool-mediated records | Noah, e2 | unknown, e2 | 1,147 | 69 |

Token totals are summed provider-reported prompt/evaluation counts, including both turns for each retrieval trial. They are not monetary costs or hidden-reasoning estimates. All six answers passed the bounded answer-and-citation scorer.

**Interpretation:** this model successfully used every interface on these tiny cases. Structured records did not improve accuracy over text here, and tool-mediated retrieval required more calls and tokens. All modes received the same definitions and available facts, so this compares serialization/access mechanics, not ontology versus no ontology. The retrieval tool returns raw records; it is not a SPARQL engine or a learned graph traversal function.

The [first live attempt](06-model-consumption/results/20261116T181700510581Z.json) was blocked by sandbox localhost access before any model response. It remains `MODEL_UNAVAILABLE`, with unattempted trials marked `NOT_RUN`. A subsequent authorized localhost execution produced the results above; the failure was not overwritten or counted as a reasoning error.

## What these runs do not establish

- No native AppWorld task ran in this lesson suite. Existing native outcomes remain in the project's measured-results document.
- Gemini diagnosis and proposal were not invoked. The candidate in lesson 10 is an assistant-authored teaching fixture, not an automated improvement.
- Turtle, SPARQL and SHACL companion files show standards syntax. No RDFLib, OWL reasoner, or SHACL engine was installed or executed.
- Pinning, migrations and admission algorithms are small explicit application policies, not a general compatibility checker or a production security guarantee.
- Two exposed synthetic cases do not establish model superiority, transfer, or reliability rates.

## Suggested first reading

Open [lesson 1](01-triples/README.md) beside its input and output. Then inspect [lesson 6](06-model-consumption/README.md) and its actual request/response receipt to see what the model consumes. Finally compare [fact invalidation](08-fact-invalidation/README.md), [representation extension](09-ontology-extension/README.md), and [changed meaning](10-semantic-version-change/README.md). Those are three different update mechanisms.

# Gemini CLI: measured results

Run: November 16, 2026. **10/10 lessons passed** the deterministic reference checks. These are small, exposed synthetic teaching cases, not native AppWorld tasks or a reliability benchmark.

- Installed CLI version: 0.68.0.
- Main model reported: gemini-3.8-flash.
- Internal utility router reported: gemini-3.5-flash-lite.
- CLI lesson invocations: 10. API requests reported across roles: 20.
- CLI tools called: 0. No model-generated code was executed.
- Six scorer unit tests passed, covering all ten reference answers, empty answers, reversed edges, wrong JSON types, duplicate values, extra fields, answer ordering, and an attempted actor authority flag.

The installed configuration and login were used, with no model override or substitute. The previous historical Gemini availability error is preserved in older project records; it does not describe this successful run. Successful lesson inference does not establish that the project's Gemini diagnosis/proposer coordinator is implemented.

[Run manifest](gemini-results/20261116T183611.251922Z/manifest.json) includes input, reference, prompt, policy, configuration and runner hashes. [Machine-readable summary](gemini-results/20261116T183611.251922Z/summary.json) records all outcomes. Every original receipt retains the submitted user prompt, reference answer withheld from that prompt, returned CLI envelope, reported models, parsed answer and field-level checks.

## Exact answers

| Lesson | Result | Gemini answer | Original evidence |
| --- | --- | --- | --- |
| [01](01-triples/GEMINI.md) | PASS | `{"positive_triples": [["Maya", "maintains", "LoginService"]], "negative_sentence_positive_triples": []}` | [Receipt](gemini-results/20261116T183611.251922Z/01-receipt.json) |
| [02](02-ontology-vs-facts/GEMINI.md) | PASS | `{"A": "graph", "B": "ontology"}` | [Receipt](gemini-results/20261116T183611.251922Z/02-receipt.json) |
| [03](03-constraints-provenance/GEMINI.md) | PASS | `{"A": {"structure_valid": true, "admitted": false}, "B": {"structure_valid": false, "admitted": false}, "C": {"structure_valid": true, "admitted": true}}` | [Receipt](gemini-results/20261116T183611.251922Z/03-receipt.json) |
| [04](04-relationship-entities/GEMINI.md) | PASS | `{"A": ["Maya"], "B": [], "C": []}` | [Receipt](gemini-results/20261116T183611.251922Z/04-receipt.json) |
| [05](05-traversal-inference/GEMINI.md) | PASS | `{"A": "UNKNOWN", "B": "SUPPORTED"}` | [Receipt](gemini-results/20261116T183611.251922Z/05-receipt.json) |
| [06](06-model-consumption/GEMINI.md) | PASS | `{"name": "get_service", "arguments": {"service_id": "LoginService"}}` | [Receipt](gemini-results/20261116T183611.251922Z/06-receipt.json) |
| [07](07-runtime-enforcement/GEMINI.md) | PASS | `{"A": {"name": "deploy", "arguments": {"service": "LoginService", "environment": "Production"}}, "B": {"name": "deploy", "arguments": {"service": "LoginService", "environment": "Production"}}}` | [Receipt](gemini-results/20261116T183611.251922Z/07-receipt.json) |
| [08](08-fact-invalidation/GEMINI.md) | PASS | `{"stale_nodes": ["decision8", "plan3"], "execute_plan3": false}` | [Receipt](gemini-results/20261116T183611.251922Z/08-receipt.json) |
| [09](09-ontology-extension/GEMINI.md) | PASS | `{"person": "Maya", "service": "LoginService", "environment": null, "validUntil": null, "source": "receipt1"}` | [Receipt](gemini-results/20261116T183611.251922Z/09-receipt.json) |
| [10](10-semantic-version-change/GEMINI.md) | PASS | `{"v1_permits": true, "v2_permits": false, "active_episode_version": "v1", "new_episode_version": "v2"}` | [Receipt](gemini-results/20261116T183611.251922Z/10-receipt.json) |

## What the runtime did in lesson 7

Gemini produced a deploy request for both cases. The trusted Python gate separately checked the supplied evidence. Case A had no approval, so its local `deployed` state stayed false. Case B had matching current approval and a source receipt, so its local state became true. This illustrates execution control independently of model compliance. It did not deploy a real service.

## What changes mean in lessons 8 through 10

- **Fact change:** Gemini identified decision8 and plan3 as stale, while leaving unrelated display state alone.
- **Representation extension:** Gemini preserved Maya, LoginService and the source, while leaving unsupported environment and expiry null.
- **Meaning change:** The same project-only approval was permitted under v1 and denied under v2. The active episode remained pinned to v1 and the new episode selected the externally accepted v2. No actual package was promoted.

These outcomes demonstrate correct interpretations on these inputs. They do not prove an ontology advantage over unstructured text, arbitrary-task support, or secure execution in a production environment.

## Reproduce

```sh
python3 -m unittest discover -s learning-labs -p test_gemini_experiments.py
python3 learning-labs/gemini_experiments.py --live
```

A rerun creates a separate evidence directory. Model routing and availability may change with the CLI's configured service; the new receipts must be inspected rather than assumed to match this run.

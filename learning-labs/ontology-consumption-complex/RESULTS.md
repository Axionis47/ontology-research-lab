# Complex ontology: actual Gemini results

Source run: `20261117T001326.948128Z`. Main models reported: gemini-3.8-flash. Router models: gemini-3.5-flash-lite.

All strategies received the same task and 53 facts, used one ontology version and ten business rules, and shared the same proof rubric and gate. Initial task/fact hashes match. [Frozen manifest](results/20261117T001326.948128Z/manifest.json). [Study design and candidate traps](README.md).

The expected pair is **Vera (Ops), Tao (Security)**. Uma is individually eligible for Ops but shares Tao's home team. Vera's authority is delegated from Iris's direct grant; Iris's expired certificate blocks Iris's own approval, not a valid delegation under this explicitly stated policy.

## Side-by-side measurements

| Strategy | CLI calls | Main input | Main generated | Router tokens | All-model total | Actual panel | Panel correct | Proof complete | Overall |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| All definitions injected | 1 | 9,562 | 5,396 | 5,207 | 20,165 | {"ops": "Vera", "security": "Tao"} | True | True | PASS |
| Relevant definitions retrieved | 1 | 9,391 | 7,274 | 10,895 | 27,560 | {"ops": "Vera", "security": "Tao"} | True | True | PASS |
| Model inspects definitions | 2 | 18,336 | 7,700 | 9,792 | 35,828 | {"ops": "Vera", "security": "Tao"} | True | True | PASS |
| Ontology-guided graph query | 1 | 9,533 | 16,137 | 5,565 | 31,235 | {"ops": "Vera", "security": "Tao"} | True | True | FAIL |
| Typed domain function | 2 | 19,327 | 9,385 | 11,338 | 40,050 | {"ops": "Vera", "security": "Tao"} | True | True | PASS |
| Candidate constraint service | 2 | 19,518 | 13,052 | 11,078 | 43,648 | {"ops": "Vera", "security": "Tao"} | True | True | PASS |

Main generated includes reported visible output and thinking tokens. Totals include reported router usage and all calls in this attempt. Unknown usage is not counted as zero; partial usage excludes calls without returned statistics. The model selection and thinking settings were inherited from the configured CLI, not optimized per method.

## Observed behavior

- Ontology-guided graph query produced a correct answer but failed the required interface-use protocol. Its answer does not demonstrate successful consumption through that interface.
- Constraint service checked Gemini's proposed panel `{"ops": "Uma", "security": "Tao"}` and rejected it for R9. Individual eligibility does not imply a valid pair.

The business-action gate below checks current eligibility and version binding. It does not enforce prior interface use. Protocol adherence is a separate experiment score; enforcing it before action would require an additional runtime precondition.

## Same execution gate for every strategy

| Strategy | Admitted at revision 7 | Admitted after delegation revoked | Admitted if proposal merely claims revision 8 | Successful interface calls |
| --- | --- | --- | --- | ---: |
| All definitions injected | True | False | False | 0 |
| Relevant definitions retrieved | True | False | False | 0 |
| Model inspects definitions | True | False | False | 1 |
| Ontology-guided graph query | True | False | False | 0 |
| Typed domain function | True | False | False | 1 |
| Candidate constraint service | True | False | False | 1 |

False after revocation means the gate blocked the proposal. This is deterministic local enforcement using the actual submitted panel, not evidence that the model noticed an unseen change. No external deployment or post-rejection model recovery ran. None means no final proposal was available to test.

## Exact submitted contexts

- 01-full-definitions, call 1: [exact submitted prompt](results/20261117T001326.948128Z/contexts/01-full-definitions-01.txt), 12,993 characters.
- 02-retrieved-definitions, call 1: [exact submitted prompt](results/20261117T001326.948128Z/contexts/02-retrieved-definitions-01.txt), 12,146 characters.
- 03-schema-inspection, call 1: [exact submitted prompt](results/20261117T001326.948128Z/contexts/03-schema-inspection-01.txt), 8,932 characters.
- 03-schema-inspection, call 2: [exact submitted prompt](results/20261117T001326.948128Z/contexts/03-schema-inspection-02.txt), 13,249 characters.
- 04-graph-queries, call 1: [exact submitted prompt](results/20261117T001326.948128Z/contexts/04-graph-queries-01.txt), 12,850 characters.
- 05-typed-function, call 1: [exact submitted prompt](results/20261117T001326.948128Z/contexts/05-typed-function-01.txt), 12,640 characters.
- 05-typed-function, call 2: [exact submitted prompt](results/20261117T001326.948128Z/contexts/05-typed-function-02.txt), 13,651 characters.
- 06-constraint-service, call 1: [exact submitted prompt](results/20261117T001326.948128Z/contexts/06-constraint-service-01.txt), 12,685 characters.
- 06-constraint-service, call 2: [exact submitted prompt](results/20261117T001326.948128Z/contexts/06-constraint-service-02.txt), 14,326 characters.

Original responses, application requests, returned graph/computation results, component scores and gate checks are in the per-strategy JSON files beside [the summary](results/20261117T001326.948128Z/summary.json). The captured prompts are user payloads, not the CLI's hidden system/global messages.

## Interpretation limits

Fourteen local test methods passed before inference against an independently written expected panel and counterexamples. These tests check scope hierarchy, validity boundaries, risk caps, delegation, certificates, denials, authorship, pair independence, evidence and stale gates. They do not establish arbitrary ontology correctness.

This is a harder single-case pilot, not a statistically reliable ranking. One attempt per strategy was scheduled in the frozen seeded order; failures and timeouts remain in the table. Typed functions and constraint services perform hand-coded computation, while prompt-based strategies ask the model to combine rules. The comparison is architectural, not a pure test of model intelligence or ontology versus no ontology. Retrieval assumes correct definition dependencies. All initial facts are deliberately present in every strategy. No AppWorld outcomes or learned ontology improvements are claimed.

[Machine-readable metrics](results/20261117T001326.948128Z/metrics.json).

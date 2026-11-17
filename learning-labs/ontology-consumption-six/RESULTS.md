# Six methods: actual same-task Gemini results

Run: `comparison-20261116T211322.549955Z`. Main models reported: gemini-3.8-flash. Utility-router models: gemini-3.5-flash-lite.

**Same task:** choose an eligible approver for LoginService's production deployment on November 16, 2026. The four shared assignments make Maya ineligible as the author, Rin ineligible for the environment, Tao ineligible by expiry, and Noah eligible at revision 1.

**Identity checks passed for the records in this report:** initial task hashes match, initial fact hashes match, and the source ontology and six business rules are fixed. Definition retrieval never selects facts. The same local gate is used whenever a final proposal is obtained. [Manifest](results/comparison-20261116T211322.549955Z/manifest.json).

## Results and tokens

| Method | CLI calls | Main input | Main generated | Router tokens | Total tokens | Answer | Complete evidence citations | Answer + citation rubric |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| All definitions injected | 1 | 6,857 | 6,520 | 2,934 | 16,311 | Noah | True | PASS |
| Relevant definitions retrieved | 1 | 6,682 | 18,756 | 2,395 | 27,833 | Noah | False | FAIL |
| Model inspects definitions | 2 | 13,455 | 4,045 | 5,633 | 23,133 | Noah | True | PASS |
| Ontology-guided graph query | 2 | 13,866 | 22,569 | 5,174 | 41,609 | Noah | False | FAIL |
| Typed domain function | 2 | 13,834 | 2,124 | 5,643 | 21,601 | Noah | True | PASS |
| Candidate constraint service | 2 | 13,804 | 1,985 | 5,802 | 21,591 | Noah | True | PASS |
## Attempt history

This is a collection of the latest completed attempted normal-JSON run for each method, not one uninterrupted suite run. There were 2 earlier operational failures, retained here: [01-full-definitions TIMEOUT](results/20261116T205826.471365Z/01-full-definitions.json), [01-full-definitions TIMEOUT](results/20261116T210153.652607Z/01-full-definitions.json). [All attempted runs](results/comparison-20261116T211322.549955Z/attempts.json) remain visible, including the two citation failures in the selected measurements. The token table covers the selected completed responses only. Timed-out requests did not report usage, so these numbers are not the total cost of all attempts. A separate short readiness probe and full-prompt streaming diagnostic were used to diagnose the timeouts; neither substitutes for a row in this normal-JSON comparison.


Main generated includes reported visible and thinking tokens. Router tokens include that model's input and output. Total is the sum of provider-reported model totals across all calls, not a cost estimate. Each CLI call also incurs system/context overhead. More calls can outweigh savings from a smaller definition set. Only successful reported usage is counted; a missing response is not evidence of zero provider spending.

Correct candidate selection and evidence completeness are different checks. The evidence contract requires both the assignment record and the deployment record that establishes authorship. A correct name with an omitted citation is an evidence-contract failure, not a wrong candidate. The independent gate recomputes eligibility from the trusted fixture and can still admit a correctly selected person.

Rubric limitation: the prompt asks for supporting record IDs but does not explicitly name the two IDs the checker requires. An omitted citation therefore cannot establish that the model ignored the corresponding business rule. Typed-function and checker results package complete evidence IDs explicitly; the generic query does not construct that proof bundle. Differences reflect interface/output design as well as ontology access.

## Consumption, gate outcomes, and limitations

| Method | Definitions exposed | Successful interface calls | Gate admitted at revision 1 | Gate admitted after revocation | Main limitation |
| --- | ---: | ---: | --- | --- | --- |
| All definitions injected | 19 | 0 | True | False | Large vocabularies consume context; definitions in a prompt are not enforcement. |
| Relevant definitions retrieved | 7 | 0 | True | False | A faulty dependency map can omit a decisive definition. This fixture uses exact closure, not uncertain semantic search. |
| Model inspects definitions | 7 | 1 | True | False | The model can request too little, misunderstand definitions, or spend extra calls inspecting. |
| Ontology-guided graph query | 7 | 1 | True | False | A syntactically valid query may implement the wrong rule. Query runtime checks structure, not intended semantics. |
| Typed domain function | 7 | 1 | True | False | A function only supports its implemented semantics. Smaller reasoning burden transfers trust to domain code. |
| Candidate constraint service | 7 | 1 | True | False | Checking proposed candidates does not guarantee all candidates were considered; rules and source completeness must be correct. |

`False` in the last gate column means the unchanged old proposal was blocked after the graph changed. This protection comes from the shared runtime gate. It does not distinguish the reasoning quality of the six interfaces, and no post-rejection recovery model call ran. All effects were local checks, not production writes.

## What actually entered context

Every method is configured with the identical task and complete four-assignment/deployment facts. The full method adds all 19 ontology definitions. Retrieved definitions supply the exact relevant closure. Inspection starts with a names/kinds catalog and returns definitions only after Gemini asks. Query, function and checker methods add the relevant definitions plus their respective interfaces. Only the call files below establish what was actually submitted; NOT_RUN and PREPARED_NOT_RUN rows are not model consumption.

- 01-full-definitions, call 1: [exact user prompt](results/comparison-20261116T211322.549955Z/contexts/01-full-definitions-01.txt), 3,885 characters.
- 02-retrieved-definitions, call 1: [exact user prompt](results/comparison-20261116T211322.549955Z/contexts/02-retrieved-definitions-01.txt), 3,094 characters.
- 03-schema-inspection, call 1: [exact user prompt](results/comparison-20261116T211322.549955Z/contexts/03-schema-inspection-01.txt), 2,450 characters.
- 03-schema-inspection, call 2: [exact user prompt](results/comparison-20261116T211322.549955Z/contexts/03-schema-inspection-02.txt), 4,171 characters.
- 04-graph-queries, call 1: [exact user prompt](results/comparison-20261116T211322.549955Z/contexts/04-graph-queries-01.txt), 3,646 characters.
- 04-graph-queries, call 2: [exact user prompt](results/comparison-20261116T211322.549955Z/contexts/04-graph-queries-02.txt), 4,583 characters.
- 05-typed-function, call 1: [exact user prompt](results/comparison-20261116T211322.549955Z/contexts/05-typed-function-01.txt), 3,629 characters.
- 05-typed-function, call 2: [exact user prompt](results/comparison-20261116T211322.549955Z/contexts/05-typed-function-02.txt), 4,460 characters.
- 06-constraint-service, call 1: [exact user prompt](results/comparison-20261116T211322.549955Z/contexts/06-constraint-service-01.txt), 3,619 characters.
- 06-constraint-service, call 2: [exact user prompt](results/comparison-20261116T211322.549955Z/contexts/06-constraint-service-02.txt), 4,372 characters.

The files capture exact user prompts, including every local observation used at each turn. They do not claim to expose the CLI's internal system messages. Original returned envelopes, model identities, answers, rule/source citations, protocol adherence and gates remain in these receipts:

- [All definitions injected](results/comparison-20261116T211322.549955Z/01-full-definitions.json): definitions exposed: Asset, Assignment, Deployment, Expense, Inventory, Invoice, Payment, Person, PurchaseOrder, Refund, Service, Shipment, Subscription, Supplier, TaxRate, Warehouse, eligibility, forService, heldBy.
- [Relevant definitions retrieved](results/comparison-20261116T211322.549955Z/02-retrieved-definitions.json): definitions exposed: Assignment, Deployment, Person, Service, eligibility, forService, heldBy.
- [Model inspects definitions](results/comparison-20261116T211322.549955Z/03-schema-inspection.json): definitions exposed: Assignment, Deployment, Person, Service, eligibility, forService, heldBy.
- [Ontology-guided graph query](results/comparison-20261116T211322.549955Z/04-graph-queries.json): definitions exposed: Assignment, Deployment, Person, Service, eligibility, forService, heldBy.
- [Typed domain function](results/comparison-20261116T211322.549955Z/05-typed-function.json): definitions exposed: Assignment, Deployment, Person, Service, eligibility, forService, heldBy.
- [Candidate constraint service](results/comparison-20261116T211322.549955Z/06-constraint-service.json): definitions exposed: Assignment, Deployment, Person, Service, eligibility, forService, heldBy.

## Limits on conclusions

This run tests six architectures on one exposed synthetic case. It cannot establish general superiority or reliability rates. The function/checker rely on implemented business rules, retrieval assumes correct definition dependencies, and graph queries depend on correct model-authored predicates. Small token differences can reflect stochastic thinking/routing effort, not only protocol design. No models or ontology definitions were trained or changed. AppWorld was not run.

Eight local test methods passed before inference, including task/fact equality, definition preservation, inspection equivalence, each business disqualification, generic query behavior, malformed requests, selector/checker scope, and stale/version gates.

[Experiment design and reproduction commands](README.md). [Machine-readable metrics](results/comparison-20261116T211322.549955Z/metrics.json).

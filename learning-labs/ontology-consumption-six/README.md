# Six ontology-consumption experiments, one unchanged task

**[Actual Gemini results, token counts, exact contexts and limitations](RESULTS.md).** All six chose Noah; four passed the complete citation rubric. Two earlier full-definition timeouts are retained separately.

**Question:** how does the interface for accessing definitions and computation change Gemini's behavior and token use?

**Task, identical in every experiment:** choose an eligible approver for LoginService's production deployment on November 16, 2026.

| Person | Shared observed fact | Constraint consequence |
| --- | --- | --- |
| Maya | Active production approval assignment; also the deployment author | Separation of duties disqualifies her |
| Noah | Active production approval assignment; not the author | Eligible at revision 1 |
| Rin | Active staging assignment | Wrong environment |
| Tao | Production assignment expired November 15 | Wrong validity interval |

The [facts](facts.json), [ontology](ontology.json), business rules, final answer contract, reference evaluation and gate are shared. The four task-relevant assignments from the previous comparison are given to **every model at the start**. Its 40 irrelevant other-service records are excluded from **all six**, not selectively. This isolates ontology consumption from fact retrieval. There is no hidden new task, regenerated world, or different threshold.

## Six separate projects

| Project | How definitions are consumed | External computation |
| --- | --- | --- |
| [1. Full definitions](01-full-definitions/README.md) | Whole ontology is in the initial prompt | None beyond checks after the answer |
| [2. Retrieved definitions](02-retrieved-definitions/README.md) | Eligibility definitions and their dependency closure are injected | Trusted exact definition retrieval |
| [3. Schema inspection](03-schema-inspection/README.md) | Names/kinds first; model requests definitions | Returns requested definitions and dependencies |
| [4. Graph queries](04-graph-queries/README.md) | Relevant definitions plus a generic query contract | Executes predicates composed by the model |
| [5. Typed function](05-typed-function/README.md) | Relevant definitions plus a domain function contract | Selects eligible candidates under implemented rules |
| [6. Constraint service](06-constraint-service/README.md) | Relevant definitions plus a candidate-checking contract | Checks only the candidates the model proposes |

The source ontology includes 7 relevant definitions and 12 unrelated definitions. They are not fabricated facts; they are irrelevant type definitions shared in the fixed source vocabulary. The full method sees all 19, retrieval sees the dependency closure, and inspection sees a catalog before choosing definitions to inspect. No retrieved definition is rewritten or summarized.

## Terms

- **Ontology:** versioned meanings of types, properties, relations and domain constraints.
- **Fact:** a concrete observed assignment or deployment record.
- **Definition retrieval:** selecting meanings, not selecting people or records.
- **Schema inspection:** the model actively asking what a concept means.
- **Graph query:** a computation over observed entities and their relationship fields. The lesson uses JSON records, not a SPARQL engine.
- **Typed function:** an operation with explicit arguments whose implementation performs domain computation.
- **Constraint service:** a checker returning whether proposed candidates satisfy explicit rules.
- **Gate:** a separate executor-side decision before an effect. It is the same code for every method.

## Common business rules

R1: service matches. R2: environment matches. R3: role is DeploymentApprover. R4: assignment is active. R5: validFrom <= task date < validUntil. R6: person differs from deployment author. All must hold. Unknown evidence cannot establish eligibility.

The source ontology expresses these meanings, while explicit Python implements their checks. This is not automatic compilation of natural language into a verified reasoner. The tests cover each disqualifying condition and distinguish generic querying, selection and candidate checking.

## Run together or separately

```sh
python3 -m unittest discover -s learning-labs/ontology-consumption-six -p test_protocols.py
python3 learning-labs/ontology-consumption-six/run.py
python3 learning-labs/ontology-consumption-six/run.py --live
python3 learning-labs/ontology-consumption-six/03-schema-inspection/run.py --live
```

The default prepares inputs only. Live mode uses the installed Gemini CLI's existing model routing and login. Maximum five CLI invocations per method, the same budget for all six. Each interaction is a fresh no-tools CLI call; a local dispatcher executes allowed JSON protocol requests and adds the result to bounded history. The current task and facts are resent unchanged. These are application-level tools, not built-in Gemini tool invocations.

The model must successfully use the declared interface in methods 3 through 6. Answer correctness and protocol adherence are recorded separately. Finishing without consuming the interface does not count as demonstrating that mechanism. Correctness checks exact result fields and cited source/rule IDs; citing a rule ID alone is not proof of deep understanding.

## Fixed execution test

Every final proposal passes through the identical gate at revision 1. Then the fixture revokes Noah's assignment, increments its graph revision to 2, and submits the same old proposal to the same gate. We record both outcomes. No model sees the revocation before selecting, and no real external write occurs. Blocking stale actions is a property of this common gate, not evidence that one consumption interface reasoned better.

## Fairness and limits

- Task and initial fact hashes must match across methods. Source definitions and rules are frozen. Every receipt identifies the definitions actually exposed.
- This deliberately changes where computation occurs as well as access to definitions. It is a comparison of six architectures, not a pure serialization ablation.
- Facts remain in every initial prompt to isolate definition consumption. Graph querying therefore does not get an artificial context advantage from withholding facts from the other methods.
- Exact retrieval assumes a correct dependency map. It is not a test of embedding retrieval quality or incomplete documentation.
- Generic queries can omit required filters. Typed functions can encode the wrong rule. Candidate checks can miss people never proposed.
- All methods still need an external freshness/authorization boundary. Prompt-only business rules cannot enforce side effects.
- One synthetic case per interface does not establish statistical reliability, arbitrary task transfer, or a context-pressure failure threshold. Thinking effort and CLI routing may vary even with unchanged configuration.
- Submitted user prompts are captured exactly; CLI-added system/global context is not fully exposed. Reported token usage includes that overhead and router requests.
- No AppWorld evaluation, Gemini diagnostic/proposer cycle, new ontology construction, or package promotion is performed here. Previous evidence is preserved.

See the shared [standards map](../STANDARDS.md). These six protocols are explicit application designs, not six standardized ontology languages.

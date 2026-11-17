# Model-consumption reports: what each interface exposed and what the model did

[All experiment reports](../README.md) · [Complete native repair loop](../01-improvement-loop/README.md)

These studies ask how a model receives definitions and facts, and how much computation an external function performs for it. They use synthetic approval tasks. They do not test storage-layer roles or deployment access.

A fictional service is called LoginService. Staging labels a testing environment; Production labels a live environment. Here both are strings in test records. A DeploymentApprover assignment describes a person's approval responsibility for a service and environment. The model must answer from the supplied records.

The studies below are separate runs. A later study's improved output is not evidence that an earlier model repaired itself. None of these interface comparisons activated a reusable program patch.

## A. Qwen used three interfaces

**Question:** Given the same definitions and available facts, does Qwen answer consistently when those facts arrive as sentences, structured records, or a local record-read result?

The task asked who had established authority to approve a Production deployment of LoginService. Both cases included Maya as a ProjectManager. That role alone did not satisfy the supplied DeploymentApprover rule.

The second record differed in exactly the relevant environment field:

| Input case | Person | Role | Service | Environment | Current | Required answer |
| --- | --- | --- | --- | --- | --- | --- |
| Valid | Noah | DeploymentApprover | LoginService | Production | true | Noah |
| Wrong environment | Noah | DeploymentApprover | LoginService | Staging | true | unknown |

The answer unknown meant that these records did not establish a Production approver. It did not mean the application denied a request or that no such approver could exist elsewhere.

**What happened:**

1. The runner prepared each case as text. Qwen returned Noah for the valid case and unknown for the wrong-environment case.
2. The runner prepared the same observations as structured records. Qwen returned the same two answers.
3. In the third interface, the initial context supplied definitions and a read_records operation. Qwen requested records; the local runner returned the supplied records without selecting an answer; Qwen then answered.
4. Python checked the returned answer and citations against that case's reference. A named approver had to cite the approval-assignment record e2.
5. The runner recorded six trials across eight model calls: four direct-input calls and two two-call retrieval trials.

| Interface | Valid-case answer | Wrong-environment answer | Model calls across both cases |
| --- | --- | --- | ---: |
| Text | Noah | unknown | 2 |
| Structured records | Noah | unknown | 2 |
| Tool-mediated records | Noah | unknown | 4 |

**Result and repair status:** All six answers passed the bounded scorer. The configured model was qwen3:8b-q4_K_M. No candidate change, deployment action, or storage authorization test followed. The study compared serialization and access mechanics on two small examples; it did not demonstrate an ontology accuracy advantage.

[Original inputs](../../learning-labs/06-model-consumption/inputs.json) · [Exact model requests, responses, and scores](../../learning-labs/06-model-consumption/results/20261116T181817940419Z.json) · [Token measurements](../../learning-labs/RESULTS.md)

## B. Gemini used five interfaces

**Question:** How do different ways of exposing one source world affect the answer, number of calls, and token usage?

The source world held four task-relevant assignments plus forty unrelated assignments. Maya was the deployment author, Rin had Staging scope, Tao's assignment had expired, and Noah was eligible.

The five interfaces were full text, structured records, a retrieved fragment, graph queries, and a typed function. They varied how much of the source world entered the prompt as well as how the model could request data.

**What happened:**

1. The runner constructed the initial context for each interface.
2. Full text, structured records, and the retrieved fragment each used one model call.
3. Graph queries used three calls, with local query results returned between calls. The typed function used two calls, with its computed result returned between calls.
4. Every method selected Noah from the original graph.
5. After selection, the fixture revoked Noah's assignment and advanced the graph from revision 1 to revision 2.
6. An unguarded local fixture reused each saved selection and violated the current eligibility rule.
7. The shared runtime gate instead recomputed current eligibility and rejected every stale proposal. The model was not called again after rejection in this study.

**Result and repair status:** Correct initial selections and correctly blocked stale proposals. The gate was already implemented. No learned repair or model recovery occurred. A smaller initial context did not automatically produce a cheaper full interaction because extra calls repeated context and CLI overhead.

[Results, exact contexts, calls, tokens, and gate outcomes](../../learning-labs/protocol-comparison/RESULTS.md)

## C. Gemini used six strategies on a simple task

This comparison separated definition access from initial fact retrieval. Every strategy received the same four assignments and deployment facts at the start. The ontology, task, and six rules stayed fixed.

**Concrete rules:** the assignment must match the service, Production environment, DeploymentApprover role, active flag, and date interval. The person must also differ from the deployment author. Applying those conditions leaves Noah.

The ontology had nineteen definitions. Seven were relevant to this task. Retrieval selected those definitions and their dependencies exactly; it did not perform uncertain semantic search.

| Strategy | What entered context or ran | Observed completed-attempt result |
| --- | --- | --- |
| Full definitions | All nineteen definitions, plus the shared facts. | Noah; complete citations. |
| Retrieved definitions | Seven definitions, plus the same facts. | Noah; required evidence citation omitted. |
| Schema inspection | A catalog, followed by definitions Gemini requested. | Noah; complete citations; interface used. |
| Graph queries | Relevant definitions and generic queries composed by Gemini. | Noah; required evidence citation omitted; interface used. |
| Typed function | Relevant definitions and a function computing eligible candidates. | Noah; complete citations; interface used. |
| Constraint service | Relevant definitions and checks of only candidates Gemini proposed. | Noah; complete citations; interface used. |

**What happened in the harness:**

1. It constructed each interface from the same task and facts, and recorded their hashes.
2. For the four interface-based methods, Gemini returned a JSON operation request.
3. Python dispatched only the method's supported operation, then added its result to the next model prompt.
4. Gemini returned a person, version/revision, source IDs, and rule IDs.
5. Python scored candidate selection and evidence completeness separately from interface use.
6. The common execution gate checked the final proposal. It then checked that same proposal after revoking Noah's assignment.

**Result and repair status:** All six selected Noah. Four met the complete citation rubric. The gate accepted each valid initial proposal and blocked each stale one. No new code or ontology was generated.

Two earlier full-definition timeouts remain recorded. The report collects completed attempts from several runs. The citation prompt also did not explicitly enumerate every ID the checker required, so a missing citation cannot establish that the corresponding rule was ignored.

[Actual results and attempt history](../../learning-labs/ontology-consumption-six/RESULTS.md) · [Definitions, rules, and reproduction](../../learning-labs/ontology-consumption-six/README.md)

## D. Gemini used six strategies on a complex task

**Question:** Can the same interfaces handle a decision that depends on several linked records and a rule about a pair of people?

The new task required one Ops approver and one Security approver for a Production deployment in the EU at risk level 4. Each of the six strategies received the same 53 facts and ten rules.

The function had to combine person, grant, delegation, certificate, service/project scope, denial, and team-membership records. The two selected people had to belong to different home teams and neither could be the deployment author.

The important candidates were:

| Person | Role eligibility | Pair consequence |
| --- | --- | --- |
| Vera | Eligible for Ops through a valid delegation; Platform team | Can pair with Tao. |
| Uma | Individually eligible for Ops; Identity team | Cannot pair with Tao because they share a home team. |
| Tao | Eligible for Security; Identity team | Can pair with Vera. |

Other supplied people were excluded for specific reasons such as expiry, region, risk limits, authorship, or an explicit denial. The [input and design report](../../learning-labs/ontology-consumption-complex/README.md) lists every candidate condition.

**What happened:**

1. The runner froze the task, facts, rules, scoring contract, and seeded method order.
2. It scheduled one attempt per method, retaining failures rather than automatically rerunning bad answers.
3. In the constraint-service method, Gemini proposed Uma and Tao. The checker returned a violation of R9, the different-team rule. Gemini's final answer selected Vera and Tao.
4. All six final answers selected Vera and Tao with complete evidence.
5. The graph-query method never requested a query. It answered from the facts already present in its prompt, so the experiment marked its interface-use protocol as failed.
6. The runtime revoked Vera's delegation after final selection. Every old proposal was blocked. A copy claiming the new revision was also blocked because current eligibility was recomputed.

**Result and repair status:** Six correct final pairs; five complete protocol passes. The constraint-service interaction corrected a proposal within that task. It did not rewrite the checker or install a reusable repair. The skipped graph-query call remains a failed demonstration of that interface.

[Answers, tokens, interface receipts, and gate results](../../learning-labs/ontology-consumption-complex/RESULTS.md)

## E. What actually happened after a rejection was returned to the model

The earlier studies tested old proposals after changing the fixture, but did not let the model respond to that change. A separate combined-interface study did.

Its five model calls were: inspect definitions, compute valid pairs, propose Vera and Tao, recompute after the runtime's revocation rejection, and return no valid pair.

The final result was RECOVERED_BLOCKED. The model correctly recognized that the changed graph no longer supported approval. No package changed and no deployment occurred.

[Full recovery sequence and current-state computation](../03-runtime-graph/README.md#b-a-graph-change-invalidated-an-action)

## What these comparisons do and do not measure

The reports distinguish answer correctness, evidence completeness, actual interface use, runtime rejection, and post-rejection behavior. The functions and constraint services contain implemented business rules, so the comparisons also change where computation happens.

The six-method studies gave all initial facts to every method. They did not demonstrate large-graph retrieval, storage permissions, a general cost ranking, or reliable performance across unseen tasks. None of these comparisons is the AppWorld improvement experiment.

For a recorded reusable repair followed by successful later tasks, read the [full native harness loop](../01-improvement-loop/README.md).

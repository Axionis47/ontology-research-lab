# Demonstrations: model access to definitions and facts

[Presentation](../README.md)

These demonstrations explain existing model experiments.
They do not add new test runs.
All cases in this page are synthetic.

## Technical terms

| Term | Meaning |
| --- | --- |
| Interface | A defined way to supply information or request an operation |
| Citation | A reference to a source record that supports an answer |
| Typed function | A function with defined input and output types |
| Constraint service | An operation that evaluates a proposed answer against stated rules |
| Rubric | The criteria that determine the test result |

## A. Qwen used three interfaces

**Purpose:** Compare three ways to give Qwen the same available facts.

**Starting conditions:** One case had a valid Production approval.
Another case had only a Staging approval.
The model was the configured `qwen3:8b-q4_K_M`.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The runner supplied the cases as text. | Qwen selected Noah in the valid case and returned unknown in the other case. | Staging approval did not satisfy the Production requirement. |
| 2 | The runner supplied the cases as structured records. | Qwen returned the same correct decisions. | The format changed. The available facts and definitions did not change. |
| 3 | The runner supplied a record-read interface. | Qwen requested records and then returned the correct decisions. | The interface added a read step before the answer. |
| 4 | The checker evaluated the six answers. | All six passed. The run used eight model calls. | The checker required a correct answer and supporting references. |

**Result:** All three interfaces worked on both cases.
The read interface required more calls and tokens.

**Limit:** Two small cases do not establish a general accuracy advantage.
This experiment compared access methods, not the presence or absence of an ontology.

**Evidence:** [Original results](../../learning-labs/RESULTS.md). [Model requests and responses](../../learning-labs/06-model-consumption/results/20261116T181817940419Z.json).

## B. Gemini used five interfaces

**Purpose:** Compare information access and token use on one approval task.

**Starting conditions:** Maya was the author.
Rin had Staging scope.
Tao's assignment had expired.
Noah was eligible at graph revision 1.
The source also contained 40 unrelated assignments.

The five interfaces were full text, structured records, a retrieved fragment, graph queries, and a typed function.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The runner supplied each interface with its defined view or access operations. | Gemini used one to three CLI calls per interface. | Different access methods required different numbers of exchanges. |
| 2 | Gemini returned the selected approver. | All five methods selected Noah. | Noah satisfied the supplied approval conditions at revision 1. |
| 3 | The fixture revoked Noah's assignment. | Revision 2 had no eligible candidate. | The original evidence no longer supported the proposed action. |
| 4 | The test applied each saved proposal through an unguarded fixture. | Each unguarded fixture selected Noah and violated the current rule. | A saved answer does not update itself when its source changes. |
| 5 | The test applied each saved proposal through the runtime gate. | The gate rejected every stale proposal. | The gate evaluated current eligibility before action. |

**Result:** Each method selected correctly from revision 1.
The runtime gate blocked the later stale action.
Token use differed across methods.

**Limit:** Gemini did not receive the revocation in another model call.
This study did not measure model recovery after rejection.
All effects occurred in local fixtures.

**Evidence:** [Results, prompts, and token counts](../../learning-labs/protocol-comparison/RESULTS.md).

## C. Gemini used six strategies on a simple task

**Purpose:** Compare access to ontology definitions and domain computations.

**Starting conditions:** Every strategy received the same task and initial facts.
Those facts included four assignments and the deployment record.
The source ontology and six business rules were fixed.
Noah was the valid selection.

| Strategy | Access provided |
| --- | --- |
| Full definitions | All 19 definitions entered the prompt. |
| Retrieved definitions | Seven relevant definitions entered the prompt. |
| Schema inspection | A catalog allowed the model to request definitions. |
| Graph queries | The model could request graph results. |
| Typed function | The model could request a domain computation. |
| Constraint service | The model could submit a candidate for evaluation. |

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The runner varied the interface while retaining the task and initial facts. | Each method had the same business problem. | A format comparison requires a stable task and source data. |
| 2 | Gemini returned its selection. | Every selected completed attempt returned Noah. | Noah satisfied the supplied rules. |
| 3 | The checker evaluated the cited evidence. | Four methods passed. Retrieval and graph-query methods omitted required evidence. | A correct name and a complete explanation are different test results. |
| 4 | The fixture revoked the approval. | The common gate blocked the old proposals. | The action required current support. |

**Result:** Candidate selection passed for all six methods.
The complete answer-and-citation rubric passed for four methods.

**Limit:** The report selected completed attempts from several runs.
Two earlier timeouts remain recorded.
The prompt did not explicitly name every citation identifier required by the checker.
An omitted citation does not prove that Gemini ignored the related rule.
The function and service interfaces also supplied computed evidence.

**Evidence:** [Results and attempt history](../../learning-labs/ontology-consumption-six/RESULTS.md).

## D. Gemini used six strategies on a complex task

**Purpose:** Determine how the same six strategies handle rules about both individual people and pairs of people.

**Starting conditions:** Each method received the same 53 facts and ten rules.
The task required an Operations approver and a Security approver.
The valid pair was Vera and Tao.
Vera's authority depended on a delegation.
Uma was individually eligible but shared Tao's home team.
The pair rule prohibited that combination.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The runner supplied the same task, facts, and ontology version to each strategy. | The methods differed in definition access and available operations. | The comparison retained the business requirements. |
| 2 | In the constraint-service method, Gemini proposed Uma with Tao. | The service rejected that pair under rule R9. | Individual eligibility did not satisfy pair independence. |
| 3 | Each method returned its final pair. | All six selected Vera for Operations and Tao for Security. | The final pair satisfied the supplied individual and pair rules. |
| 4 | The checker evaluated evidence and required interface use. | Five methods passed overall. Graph-query mode failed its interface-use criterion. | That method returned an answer without using its required query interface. |
| 5 | The fixture revoked Vera's delegation. | The common gate rejected the old proposals. | The original authority evidence no longer supported the action. |

**Result:** All final pairs were correct.
Five methods satisfied the full experiment protocol.

**Limit:** This was one exposed synthetic case.
Definitions and domain functions were hand-authored.
The test did not establish a general ranking of methods.
The business gate and interface-use rubric applied different criteria.

**Evidence:** [Complex task results](../../learning-labs/ontology-consumption-complex/RESULTS.md).

## E. Recovery after a graph change

The combined study gave the rejection back to Gemini.
Gemini then requested a new computation and returned no valid pair.

The [graph-change demonstration](../03-runtime-graph/README.md#b-a-graph-change-invalidated-an-action) shows the five model calls in order.
It also explains why a correct blocked result was not a completed approval.

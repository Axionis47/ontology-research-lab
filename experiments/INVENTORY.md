# Experiments with recorded evidence

Reviewed November 17, 2026. Every entry below has saved execution results, model responses or a result receipt. Failed and withdrawn experiments are retained and labelled. Plans, prepared prompts without responses, setup-only folders and unrun comparisons are excluded. Related retries are grouped instead of counted as new independent experiments.

[Experiment hub](README.md)

## 1. Current AppWorld improvement experiment

| Experiment | Recorded result | Limitation | Evidence |
| --- | --- | --- | --- |
| Qwen execution, Gemini diagnosis, separate Gemini proposal, runtime acceptance and reuse | Three native baselines failed; after an accepted numeric-filter correction, three subsequent tasks passed all five official checks each. A fresh automatic run repeated learning from the original seed without manual resume, then passed three subsequent episodes. | One Spotify task family, previously exposed training variants. The improvement changed a function, not ontology definitions or model weights. Qwen's argument errors remain. | [Full result](../runs/protocol/appworld-gemini-20261116/protocol-result.json), [automatic repeat](../runs/protocol/appworld-gemini-20261116/clean-replay/result.json), [wins and losses](../docs/system/20-live-acceptance.md#gemini-loop-verified-november-16-2026) |

## 2. Ten ontology concept experiments

All ten have actual Gemini responses that passed the deterministic reference checks. These are synthetic teaching cases, not ten complete domain ontologies. Their Python companion programs also have recorded results, with 48 named checks across the suite; the companion interface-preparation checks are not themselves model runs.

| Experiment | What was checked | Limitation | Original Gemini receipt |
| --- | --- | --- | --- |
| 01. Triples | Positive relationship extraction and rejection of a negated positive edge | Small constructed sentences; no general extraction benchmark | [01](../learning-labs/gemini-results/20261116T183611.251922Z/01-receipt.json) |
| 02. Ontology versus facts | New instance versus new definition | Classification of supplied examples; no autonomous ontology construction | [02](../learning-labs/gemini-results/20261116T183611.251922Z/02-receipt.json) |
| 03. Constraints and provenance | Structural validity versus evidence-backed admission | Synthetic source receipts; no independent verification of real-world truth | [03](../learning-labs/gemini-results/20261116T183611.251922Z/03-receipt.json) |
| 04. Relationship entities | Assignment role, environment and validity interval | Fixed representation and supplied facts | [04](../learning-labs/gemini-results/20261116T183611.251922Z/04-receipt.json) |
| 05. Traversal and inference | Graph connectivity versus approval authority | Explicit rules on a small fixture; no general reasoning engine | [05](../learning-labs/gemini-results/20261116T183611.251922Z/05-receipt.json) |
| 06. Model consumption | Generate the documented read request for missing information | This Gemini lesson proposes the request; it does not execute an external read | [06](../learning-labs/gemini-results/20261116T183611.251922Z/06-receipt.json) |
| 07. Runtime enforcement | Two proposed actions, admitted only with matching evidence | A real local Python gate changes a fixture boolean, not a production service | [07](../learning-labs/gemini-results/20261116T183611.251922Z/07-receipt.json) |
| 08. Fact invalidation | Identify dependent decisions and plans made stale by a changed fact | Dependencies are supplied; hidden or missing dependencies are not discovered | [08](../learning-labs/gemini-results/20261116T183611.251922Z/08-receipt.json) |
| 09. Ontology extension | Preserve known fields and leave unsupported scope/expiry unknown | A proposed migration on an example, not a promoted ontology extension | [09](../learning-labs/gemini-results/20261116T183611.251922Z/09-receipt.json) |
| 10. Semantic version change | Different outcomes under two meanings; active episode stays pinned | Supplied versions and rules; no live package promotion | [10](../learning-labs/gemini-results/20261116T183611.251922Z/10-receipt.json) |

[Exact answers and model identities](../learning-labs/GEMINI-RESULTS.md), [all ten measured outcomes](../learning-labs/gemini-results/20261116T183611.251922Z/summary.json), [companion-program results](../learning-labs/results/20261116T181747.466229Z/summary.json).

## 3. Model-consumption and graph-change experiments

| Experiment | Recorded result | Limitation | Evidence |
| --- | --- | --- | --- |
| Qwen: text, structured facts and tool-mediated records | Two cases through three interfaces: all six answers passed; eight actual model calls | Tiny synthetic cases. No measured accuracy advantage for structured input; retrieval used more calls/tokens | [Results](../learning-labs/RESULTS.md), [model receipt](../learning-labs/06-model-consumption/results/20261116T181817940419Z.json) |
| Gemini: five interfaces on one task | Full text, full structured records, retrieved fragment, graph queries and typed function all selected Noah. The common gate blocked their stale proposals after revocation | One synthetic task. No post-rejection model recovery in this study; protection came from the gate | [Results and contexts](../learning-labs/protocol-comparison/RESULTS.md) |
| Gemini: six ontology-consumption strategies, simple task | Full definitions, retrieved definitions, schema inspection, graph queries, typed function and constraint service all chose Noah. Four passed the complete rubric; retrieval and graph-query modes omitted required citations | Citation-rubric and interface-design limitations; selected completed attempts were assembled across runs. Earlier timeouts remain | [Results and attempt history](../learning-labs/ontology-consumption-six/RESULTS.md) |
| Gemini: the same six strategies, complex task | All chose the correct pair from 53 facts and ten rules. Five passed overall; graph-query mode skipped its required interface | One exposed synthetic case with hand-authored definitions and computation. Correct answer does not establish interface adherence | [Results](../learning-labs/ontology-consumption-complex/RESULTS.md) |
| Combined ontology consumption and recovery after graph change | Valid initial panel at revision 7; revoked delegation caused rejection; Gemini recomputed at revision 8 and returned no valid panel | Correctly blocked task, not completed approval. Synthetic mutation and supplied rejection feedback; zero external writes | [Results](../learning-labs/ontology-consumption-complex/combined-recovery/RESULTS.md), [original receipt](../learning-labs/ontology-consumption-complex/combined-recovery/results/20261117T003010.669432Z/receipt.json) |

The [runtime graph evidence page](03-runtime-graph/README.md) also collects native API-to-graph observations, queries and action readback from the AppWorld loop. This is another view of the same evidence, not an additional independent experiment. No incremental-population versus prepopulated-graph comparison has been executed.

## 4. Earlier component and loop experiments with results

| Experiment | Recorded result | Limitation | Evidence |
| --- | --- | --- | --- |
| Cardinality-gap detection | Saved `GAP_DETECTED` receipt for a max-count violation; cause explicitly undetermined | Synthetic example. No LLM diagnosis, live-source verification or authorized ontology change | [Receipt](../examples/gap-report.json) |
| ReAct execution and context compaction | Live short fixture succeeded; scripted compaction fixture succeeded; live compaction fixture reached its step limit | Local fixtures and different engineering revisions/budgets; not a paired benchmark | [Results and run index](../outputs/react-component/README.md) |
| Native MCP integration and write/readback probe | Write/readback, saved state, application restriction and official evaluator availability verified; native task success was false | Integration probe, not an agent success score | [Result](../runs/appworld-smoke/write-probe/result.json) |
| Initial AppWorld baseline | 0/3 evaluated native tasks passed; batch marked incomplete | Early tool-routing baseline; no learned kernel or completed improvement cycle | [Summary](../runs/appworld/baseline-v1/summary.json) |
| Selective-update completion checks | Correct update was TRUE; missing target and extra update were FALSE; incomplete coverage was UNKNOWN | Four synthetic scripted cases; cannot infer arbitrary task meaning | [Four recorded cases](../runs/completion/first-demo/summary.json) |
| Repair scoring and regression rejection | Parent 2/4; repaired candidate 4/4 accepted for development. Another candidate reached 3/4 but was rejected for a regression | Engineer-authored selectors, synthetic cases, no automatic proposal or native promotion | [Accepted comparison](../runs/repair-scoring/first-comparison/comparison.json), [rejected comparison](../runs/repair-scoring/regression-check/comparison.json) |
| Bounded program-search repair and local controller | Verified search demonstration retained a repair and passed four subsequent episodes. Later local controller record passed 7/7 episodes with two promotions | Scripted recovery and bounded structural search, not Gemini-authored improvement | [Search demonstration](../runs/learning/verified-loop/demo.json), [controller results](../runs/learning/closed-loop-verified/inference-result.json), [validation summary](../runs/learning/closed-loop-validation.json) |
| Native controller with reference recovery and search repair | Six native episodes passed; one repair retained | Actual AppWorld worlds, but scripted reference recovery and search proposals; not the assigned live-model loop | [Native results](../runs/learning/native-closed-loop/inference-result.json), [role-labelled validation](../runs/learning/closed-loop-validation.json) |
| Live native development probes | First seven saved probe outcomes were FALSE or UNKNOWN; eighth was TRUE | Engineering attempts used changing revisions; not eight independent comparable benchmark trials | [Recorded probe outcomes](#recorded-development-probes) |
| Earlier live acceptance test | Full acceptance failed. Raw and recovery native phases each passed 0/3; post-search-repair native inference passed 9/9. Two repairs accepted; broken candidate rejected | Search proposer, exposed native tasks and a local relationship fixture. Successful retained execution did not establish reliable Qwen recovery | [Full results](../runs/learning/live-acceptance-v2/RESULTS.md), [verdict](../runs/learning/live-acceptance-v2/proof-report.json), [previous failed/interrupted attempt](../runs/learning/live-acceptance/proof-report.json) |
| Registered-strategy policy repair | Latest completed report failed overall; discovery and binding edits were accepted within its component gates | Finite engineering mechanisms; failed overall acceptance is not a working Gemini protocol | [Report](../runs/learning/policy-acceptance-v4/proof-report.json) |
| Model-proposed policy repair attempts | Completed v2, v3, v4 and v6 reports failed overall; v6 retained no learned change | Historical policy-repair experiments, not evidence of the current separate Gemini judge/proposer cycle | [v2](../runs/learning/model-policy-loop-v2/proof-report.json), [v3](../runs/learning/model-policy-loop-v3/proof-report.json), [v4](../runs/learning/model-policy-loop-v4/proof-report.json), [v6](../runs/learning/model-policy-loop-v6/proof-report.json) |
| Qwen proposals under increasing synthetic work | Six recorded attempts; the requested LLM-authored retained improvement was not demonstrated | Synthetic ticket tasks; historical proposer assignment, not the current assigned Gemini role | [Attempt summary](../runs/learning/llm-new-work-20261115-v6/demonstration-summary.json) |
| Synthetic increasing-work control and Gemini-availability review | Scripted/search control reached 10/10 after per-request adjustments; three repairs retained; generated checks rose from 42/96 to 96/96. Gemini judgment unavailable | Control success was synthetic and search-authored. It did not complete the requested Gemini loop | [Review result](../runs/learning/gemini-judge-review-20261115/review-result.json) |
| Earlier native Gemini review and retained-program replay | Qwen raw 0/3; recovery 0/3; old retained program 3/3. Gemini unavailable. Extra Qwen schema-proposer experiment withdrawn | Retention of an older search-produced program, not a new Gemini improvement. Withdrawn result cannot support the intended protocol | [Native results and withdrawal](../runs/learning/appworld-gemini-review-20261115/appworld-results.json), [role correction](../runs/learning/appworld-gemini-review-20261115/role-correction.json) |
| Fresh diagnostic restart before CLI repair | Real Qwen task failed; Gemini rejected evidence before inference; no proposal or activation | One native diagnostic attempt, explicitly BLOCKED; superseded operationally by the working experiment in section 1 | [Protocol result](../runs/protocol/appworld-reset-20261116/protocol-result.json) |

### Recorded development probes

These are saved outcomes supporting the development-probes row, not additional claims of improvement:

| Probe | Recorded task state | Result |
| --- | --- | --- |
| 1 | UNKNOWN | [Receipt](../runs/learning/live-proof-probe/inference-result.json) |
| 2 | UNKNOWN | [Receipt](../runs/learning/live-proof-probe-2/inference-result.json) |
| 3 | UNKNOWN | [Receipt](../runs/learning/live-proof-probe-3/inference-result.json) |
| 4 | FALSE | [Receipt](../runs/learning/live-proof-probe-4/inference-result.json) |
| 5 | UNKNOWN | [Receipt](../runs/learning/live-proof-probe-5/inference-result.json) |
| 6 | FALSE | [Receipt](../runs/learning/live-proof-probe-6/inference-result.json) |
| 7 | FALSE | [Receipt](../runs/learning/live-proof-probe-7/inference-result.json) |
| 8 | TRUE | [Receipt](../runs/learning/live-proof-probe-8/inference-result.json) |

Earlier [first search-loop output](../runs/learning/first-complete-loop/demo.json), [local controller probe](../runs/learning/controller-probe/inference-result.json), [native execution-error probe](../runs/learning/native-controller-probe/probe.json), and [native successful probe](../runs/learning/native-controller-probe-open/probe.json) are also retained as development evidence for their corresponding families above. Their folder names do not establish any stronger result.

## Shared limitations

- Native results cover one Spotify task family on previously exposed training variants. Synthetic approval and ticket cases do not expand native benchmark coverage.
- The ten lessons and interface studies use supplied, hand-authored definitions and facts. They do not establish general task-conditioned ontology construction.
- Functions, graph facts, ontology definitions and model weights are distinct. The successful current loop improved a reusable function.
- Good final answers, complete citations, correct interface use, a successful guard and successful task completion are separate outcomes.
- Repeated attempts, development reruns and shared underlying evidence are not independent samples. No combined pass rate is computed across this inventory.
- CLI readiness checks, unit tests and specification validation are supporting checks, not additional ontology experiments. Architecture documents and unrun plans are excluded.

This document organizes existing evidence only. No model calls, new experiments, runtime changes or result rewrites were performed for the inventory.

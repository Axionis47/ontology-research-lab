# OaK paper: implementation specification

Status: source-derived specification, not an implemented or experimentally reproduced system.

Source: Xiaohui Zhang, Zequn Sun, Chengyuan Yang, Yuanning Cui, Lingbing Guo, and Wei Hu, *Toward Effective and Reliable LLM Agents via Dynamic Ontology*, [arXiv:2608.22974v1](https://arxiv.org/pdf/2608.22974v1), submitted 24 August 2026. The source declares CC BY 4.0.

Preserved evidence:

- [Original PDF](source/oak-2608.22974v1.pdf), 11 pages.
- [Complete extracted text with preserved HTML math](extracted/paper-text.md).
- [Embedded PDF text with page markers](extracted/paper-pdf.txt).
- [Extraction report](extracted/extraction-report.json) and [source manifest](source/manifest.json).

This document refines the paper into requirements. It does not replace the complete text or the numerical tables and figures. The user's visibility, revision, suggestion, compatibility-adapter, and selective-regression additions belong in [the project design](../design.md). They are extensions, not claims about the paper.

## 1. Interpretation rules

1. A requirement marked **Paper** is directly specified in the cited section.
2. An **Implication** follows from that requirement but is an implementation interpretation.
3. An **Open detail** is missing, underspecified, or ambiguous in the reviewed paper. It must not silently become a claimed paper fact.
4. Related work identifies context and baselines. It is not an instruction to include every cited technique inside OaK.
5. Construction uses task examples and LLM-generated artifacts. The described method does not specify gradient updates or fine-tuning of model weights.
6. An ontology consistency result is not by itself proof of extraction accuracy, function correctness, or task success.

## 2. Objects and boundaries

**Paper, Introduction and Sections 3.1 to 3.3, PDF pages 1 to 4.**

The ontology kernel is

$$\mathcal K=(\mathcal S,\mathcal F).$$

| Symbol | Meaning | Required role |
|---|---|---|
| T | Task description | Input to requirement analysis |
| D^{tr} | Training examples | Only construction/refinement examples |
| D_t | Fresh sample for round t | Contains complete pairs (q, C_q) |
| Q_t | Queries in D_t | Drive composition, execution, and scoring |
| C_t | Reference corpora accompanying D_t | Evidence for constructing G_t |
| R | Requirement specification | Task scope, entities, relations, constraints |
| S_t | Current lightweight schema | Named entity types, properties, identity fields, typed relations |
| G_t | Graph instantiated under S_t | Evidence operated on by the functions |
| O | Generic operator library | The nine public operators in Appendix B |
| F_t | Current domain function catalog | Typed executable functions grounded in O |
| A_t | Execution trajectories | Operator traces, function outputs, final answers |
| s_t | Official dataset scores | Inputs to the ontology judge |
| psi_t | Judge repair report | Changes to entity types, relation types, and functions |
| S*, F* | Final frozen schema and functions | Immutable during paper-style inference |
| G_q | Query-specific inference graph | Built from C_q under S* |

**Paper:** S bounds what the agent can express; F bounds what it can compute. After freezing, the kernel is the agent's channel to the data. The agent cannot invoke concepts or computations that the kernel does not declare.

**Implication:** Arbitrary access to the raw corpus or arbitrary generated execution at inference would need to be identified as a departure from this boundary. Runtime enforcement details are not fully supplied.

## 3. Construction lifecycle

**Paper, Section 3.2, PDF pages 3 to 4; Figure 1.**

At the start of round t, sample fresh examples:

$$D_t\subseteq D^{tr},\qquad D_t=\{(q,C_q)\},\qquad Q_t=\{q\},\qquad C_t=\{C_q\}.$$

Each round has four steps. Schema and function feedback from the previous round are empty in the first round.

### 3.1 Requirement analysis, drafting, and verification

**Paper, Section 3.2 Step 1, PDF page 3.**

Analyze the task description and round sample:

$$R=\mathrm{Analyze}(T,D_t).$$

R records scope, key entities and relations, and task constraints. Draft from R and previous schema feedback:

$$\mathcal S_t=\mathrm{Draft}(R,\psi^{\mathcal S}_{t-1}).$$

The draft:

- Enumerates entity types and their properties.
- Assigns each entity type an identity field used as its primary key.
- Declares relations with source and target entity types.
- Uses lightweight YAML or JSON, rather than presenting the full OWL axiomatic representation to the agent.

Encode the draft in OWL, then run the actual HermiT reasoner:

$$\mathrm{HermiT}(\mathrm{OWL}(\mathcal S_t))
  \rightarrow \{\text{consistent},\ \text{unsatisfiable classes}\}.$$

A failed check returns the draft for repair with reasoner counterexamples, followed by retry.

#### The five consistency checks

**Paper, Appendix A, PDF page 10.**

| Check | Paper requirement |
|---|---|
| Disjointness consistency | Check that categories intended to be mutually exclusive are not forced to overlap. |
| Restriction consistency | Check existential, universal, and cardinality restrictions for contradictions. |
| Property-level consistency | Check compatibility of functional, inverse-functional, transitive, symmetric, asymmetric, reflexive, irreflexive, and inverse-property declarations with other axioms. |
| Global consistency | Check satisfiability of the ontology as a whole. |
| Unsatisfiable classes | Detect classes that cannot have instances under the combined definitions and constraints. |

**Open detail:** The lightweight schema grammar and its exact translation to OWL axioms are not supplied. HermiT can only evaluate the axioms actually encoded. Domain mistakes must not be assumed to become logical contradictions automatically. The retry limit for the inner drafting/reasoner repair loop is also not specified.

### 3.2 Knowledge graph instantiation

**Paper, Section 3.2 Step 2, PDF pages 3 to 4.**

Partition C_t into token-bounded chunks c_1 through c_n, each fitting the extractor input budget. The LLM extractor emits schema-typed candidate entities and relations for each chunk:

$$\mathcal G_t=\mathrm{Build}(\mathcal S_t,C_t)
  =\bigsqcup_{i=1}^{n}\Phi_{\mathcal S_t}(c_i).$$

For candidate entity e, define its key signature:

$$\kappa(e)=(\tau(e),\pi_{\mathrm{pk}}(e)).$$

Here tau is entity type and pi_pk is its schema-declared primary-key value. The paper defines identity equivalence as:

$$e_i\sim e_j\iff \kappa(e_i)=\kappa(e_j).$$

Collapse each equivalence class into one canonical node with a deterministic identifier. Reattach relations to canonical endpoints, then collapse duplicate relations.

**Open details:** Chunk token budget and overlap, extraction prompts, output schema, primary-key normalization, missing keys, conflicting non-key property values, relation deduplication identity, and deterministic identifier encoding are not provided. These choices can affect downstream function behavior.

### 3.3 Function composition and task execution

**Paper, Section 3.2 Step 3, PDF page 4.**

An LLM composer identifies recurring reasoning patterns from the round queries and graph:

$$\mathcal F_t=\mathrm{Compose}
  (\mathcal O,\mathcal S_t,\mathcal G_t,Q_t,\psi^{\mathcal F}_{t-1}).$$

Each function f in F_t has typed inputs, typed outputs, and a realization r_f over O. The paper allows three forms:

1. Compose multiple operators into a pipeline.
2. Specialize an operator by fixing or reinterpreting parameters.
3. Adapt an operator with lightweight pre-processing or post-processing.

Test each function on G_t for executability. Expose the validated catalog as callable tools. A ReAct agent then executes:

$$A_t=\mathrm{Agent}(Q_t,\mathcal S_t,\mathcal G_t,\mathcal F_t).$$

The agent selects functions, binds typed arguments under S_t, and executes against G_t. A_t includes operator traces, function outputs, and final answers.

**Open details:** Composition prompts, function realization language or code grammar, allowed pre/post-processing, signature representation, executability acceptance tests, tool serialization, and execution isolation are not defined. Figure 7 is illustrative code, not a complete runtime.

### 3.4 Official scoring, judge diagnosis, and repair

**Paper, Section 3.2 Step 4, PDF page 4.**

First score final answers using the dataset evaluation protocol:

$$\mathbf s_t=\mathrm{Eval}(A_t).$$

The judge receives the kernel, graph, trajectory, and scores:

$$\psi_t=\mathrm{Judge}
  (\mathcal S_t,\mathcal G_t,\mathcal F_t,A_t,\mathbf s_t).$$

Let U_t = E_t union R_t union F_t denote entity types, relation types, and functions. A repair suggestion is:

$$\sigma=(u,a,\delta,\rho),\quad
  u\in U_t,\quad a\in\{\mathrm{add},\mathrm{delete},\mathrm{modify}\}.$$

u identifies the artifact, a the action, delta the proposed definition or patch, and rho the diagnosed reason. Collect suggestions as psi_t = {sigma_1, ..., sigma_k}. Partition by target:

$$\psi_t=\psi_t^E\cup\psi_t^R\cup\psi_t^{\mathcal F},
\qquad
\psi_t^{\mathcal S}=\psi_t^E\cup\psi_t^R.$$

Schema feedback feeds Step 1 of round t+1. Function feedback feeds Step 3. Apply repairs and start the next round. Stop when the judge finds no blocking fault or the iteration budget is exhausted.

**Open details:** Judge prompt, machine-readable report grammar, severity definitions, exact meaning of "blocking," handling contradictory or invalid repairs, ordering of dependent repairs, and acceptance/rollback rules are absent.

## 4. Frozen-kernel inference

**Paper, Section 3.3, PDF page 4.**

Freeze the final round's S* and F*. For each previously unseen test query q:

$$\mathcal G_q=\mathrm{Build}(\mathcal S^*,C_q),$$

$$a=\mathrm{Agent}(q,\mathcal S^*,\mathcal G_q,\mathcal F^*).$$

The graph is built from that query's accompanying corpus. S* and F* are not edited during inference. The agent uses the frozen functions and typed arguments to obtain graph evidence and produce an answer.

**Implications to verify in implementation:**

- Freezing the kernel does not mean freezing one training graph for all inference queries.
- Test results cannot feed repairs into the same frozen evaluation run without changing the paper's protocol.
- Historical successes cover observed cases. They do not certify all future agent decisions.
- User edits and compatibility adapters require a distinct new kernel revision under the project's extension design.

## 5. Appendix B operator inventory

**Paper, Appendix B, PDF pages 10 to 11.** The following reproduces the nine signatures with formatting cleaned up, retaining parameter names and defaults. Type declarations themselves are not supplied by the paper. These declarations are reference material, not executable project code.

### 5.1 Runtime-slot extraction

Maps a natural-language query to declared typed slots using an LLM. Retains explicit or strongly implied constraints and their evidence.

~~~python
def extract_runtime_slots(
    *,
    query: str,
    slot_specs: Sequence[RuntimeSlotSpec],
    env_path: str | Path = "/ontology_research/.env",
    log_dir: str | Path = "ontology_llm_logs",
    task_context: str = "",
    max_attempts: int = 3,
    max_tokens: int = 2000,
) -> RuntimeSlotExtractionResult:
~~~

The absolute environment path is an upstream example/default, not an instruction to access that path locally. Portable configuration must be recorded as an engineering adaptation.

### 5.2 Entity lookup

Retrieves by entity type, ID, primary key, exact property filters, or fuzzy name/text matching, with optional ranking and truncation.

~~~python
def lookup_entities(
    graph: str | Path | dict[str, Any] | InstantiatedGraph,
    *,
    entity_types: Sequence[str] | None = None,
    entity_ids: Sequence[str] | None = None,
    primary_key: dict[str, Any] | None = None,
    property_filters: dict[str, Any] | None = None,
    name_query: str | None = None,
    text_query: str | None = None,
    fuzzy: bool = True,
    top_k: int | None = None,
    min_score: float = 0.0,
) -> EntityLookupResult:
~~~

### 5.3 Relation traversal

Expands bounded neighborhoods from seed entities by selected relation types and directions; returns visited entities and relations.

~~~python
def traverse_relations(
    graph: str | Path | dict[str, Any] | InstantiatedGraph,
    *,
    start_entity_ids: Sequence[str],
    relation_types: Sequence[str] | None = None,
    direction: TraversalDirection = "outgoing",
    max_hops: int = 1,
    include_starting_entities: bool = True,
) -> TraversalResult:
~~~

### 5.4 Property projection

Projects properties into flat rows while preserving entity IDs, types, and primary keys.

~~~python
def project_properties(
    entities: Sequence[GraphEntity]
        | EntityLookupResult | EntityFilterResult | TraversalResult,
    *,
    property_names: Sequence[str],
    missing_value: Any = None,
) -> list[ProjectedRow]:
~~~

### 5.5 Categorical filtering

Applies exact categorical inclusion or exclusion conditions. O exposes this function through the alias filter_categorical.

~~~python
def filter_property_categorical(
    entities: Sequence[GraphEntity]
        | EntityLookupResult | EntityFilterResult | TraversalResult,
    *,
    conditions: Sequence[PropertyCategoricalFilterCondition],
) -> EntityFilterResult:
~~~

### 5.6 Relation-connectivity filtering

Keeps entities connected to specified anchors through required relation types.

~~~python
def filter_relation_connected(
    graph: str | Path | dict[str, Any] | InstantiatedGraph,
    entities: Sequence[GraphEntity]
        | EntityLookupResult | EntityFilterResult | TraversalResult,
    *,
    conditions: Sequence[RelationFilterCondition],
) -> EntityFilterResult:
~~~

### 5.7 Numeric filtering

Applies equality, inequality, threshold, or interval conditions to numeric properties.

~~~python
def filter_numeric(
    entities: Sequence[GraphEntity]
        | EntityLookupResult | EntityFilterResult | TraversalResult,
    *,
    conditions: Sequence[NumericFilterCondition],
) -> EntityFilterResult:
~~~

### 5.8 Set-overlap filtering

Applies any-match, all-match, or minimum-overlap requirements to multivalued properties.

~~~python
def filter_set_overlap(
    entities: Sequence[GraphEntity]
        | EntityLookupResult | EntityFilterResult | TraversalResult,
    *,
    conditions: Sequence[SetOverlapFilterCondition],
) -> EntityFilterResult:
~~~

### 5.9 Aggregation

Computes count, sum, minimum, maximum, or average, optionally grouped by a field.

~~~python
def aggregate_values(
    items: Sequence[GraphEntity | ProjectedRow | dict[str, Any]]
        | Iterable[GraphEntity | ProjectedRow | dict[str, Any]],
    *,
    request: AggregateRequest,
) -> AggregateResult:
~~~

**Open details common to operators:** condition/result dataclass fields, null and invalid-value handling, numeric precision, stable ordering, fuzzy match implementation and score meaning, traversal enum values, duplicate counting, aggregation empty-set semantics, and slot-evidence format are not fully defined. Figure 7 uses simplified positional filter calls, whereas Appendix B specifies keyword-only conditions. That mismatch needs an explicit implementation decision.

## 6. Exact published settings

**Paper, Section 4.2, PDF page 5; Appendix B, PDF pages 10 to 11.**

| Setting | Published value | Scope |
|---|---|---|
| Backbone models | DeepSeek-v4-flash; gpt-4o-mini | Requirement analysis, schema drafting, graph extraction, function composition, agent reasoning |
| Ontology judge | claude-sonnet-4.6 | Held fixed across experimental settings |
| Round sample | Fresh random 20% of training split | Each construction round |
| Maximum construction rounds | 5 | Outer construction/refinement loop |
| Maximum ReAct steps | 20 per query | Agent execution |
| Runtime-slot attempts | 3 | extract_runtime_slots default |
| Runtime-slot output token budget | 2000 | extract_runtime_slots default |
| Lookup fuzzy matching | True | lookup_entities default |
| Lookup minimum score | 0.0 | lookup_entities default |
| Traversal depth | 1 hop | traverse_relations default |
| Include traversal seeds | True | traverse_relations default |
| Projection missing value | None | project_properties default |

These are source values, not a declaration that providers or exact model versions are available locally. Model substitutions must be reported. The paper does not specify general temperature, decoding seed, maximum tokens, tokenization, chunk size, concurrency, retry/backoff settings, timeout limits, or inner HermiT repair budget.

## 7. Benchmark and evaluation requirements

**Paper, Sections 4.1 to 4.3, PDF pages 4 to 6; Tables 1 to 3.**

| Benchmark | Task surface | Metric definitions |
|---|---|---|
| TravelPlanner | Multi-day transportation, meals, attractions, accommodations, and constraints | CS for commonsense feasibility; HC for explicit hard constraints. Micro is fraction of individual constraints met; macro is fraction of plans meeting all applicable constraints in a family; final requires both families fully satisfied. |
| CRMArenaPro | Synthetic B2B and B2C CRM environments, with Workflow, Policy, Text, Database categories | Workflow/Policy/Database use exact match. Text uses exact match for discrete outputs or token-level F1 for free-form answers. Average is equal-weight mean of the four category scores. |
| ToolQA | Flight, Coffee, Airbnb, DBLP, Yelp subsets over external corpora | Normalized exact match. Table 3 aggregate is weighted across subsets. |

Baseline comparison methods are ReAct, AFlow, MemP, ReCode, and AgentSquare. Their implementation is needed for a full comparative reproduction, not for establishing that the first OaK implementation executes the method correctly.

Selected published OaK results, all percentages:

| Backbone | TravelPlanner final | CRM B2B average | CRM B2C average | ToolQA weighted average |
|---|---:|---:|---:|---:|
| DeepSeek-v4-flash | 55.90 | 78.38 | 75.20 | 64.58 |
| gpt-4o-mini | 19.70 | 63.93 | 67.62 | 59.32 |

The complete per-category, per-subset, and baseline numbers remain in Tables 1 to 3 of [the extracted text](extracted/paper-text.md) and original PDF. Do not infer exact benchmark splits, instance counts, or aggregate weights from percentages.

**Open detail:** Exact dataset revisions, task IDs, construction/evaluation partitions, sampling seeds, and the ToolQA subset weighting counts are not supplied. A local small-task pilot must publish its own task manifest and split protocol, and must not claim to reproduce Table 3.

## 8. Ablations, analyses, and case-study behavior

### 8.1 Three ablations

**Paper, Section 4.4 and Appendix D, PDF pages 5 to 6 and 11; Figures 2 to 4 and 9 to 11.**

| Variant | Required change from full OaK |
|---|---|
| Without function composition | Expose generic O directly instead of domain-composed functions. |
| Without function module | Remove F; let the LLM reason over the full graph, retaining minimal retrieval if the graph does not fit context. |
| Without iterative refinement | Execute only the first construction round, with no later schema/function updates. |

The paper reports lower performance after removal of these components. The strongest degradation varies by task. Preserve per-metric results rather than treating one aggregate as proof of all mechanisms.

For gpt-4o-mini, Appendix D states TravelPlanner final drops from 19.70 to 9.90 without the function module. It reports 65.78 as an overall CRM average and 59.32 for ToolQA's weighted average. Chart-only values must be read from the original figures or an author artifact, not manufactured from prose.

### 8.2 Construction-loop analysis

**Paper, Section 4.5, PDF page 7; Figure 5.**

Record each benchmark's primary aggregate score after each construction round under a fixed inference protocol. The prose reports rapid early improvement and a plateau around rounds 4 to 5, with later fluctuations related to fresh round samples and artifact refinements.

**Confirmed source ambiguity:** Visual inspection of PDF page 7 confirms that Figure 5 has iteration labels 1 through 7, while Section 4.2 specifies a maximum of 5 construction iterations. The figure's accompanying prose says the five-round budget captures most of the benefit. Preserve the explicit five-round default for the main protocol and do not silently treat the seven-round analysis as the same setting. Whether this analysis used an extended budget remains unresolved.

### 8.3 Coupled schema and function repair

**Paper, Section 4.6, PDF page 7; Figures 6 to 7.**

The TravelPlanner example initially omits Hotel.minimum_nights and Hotel.maximum_occupancy. The judge adds those schema fields. A schema update alone is insufficient: get_accommodation_candidates must also enforce maximum_occupancy >= people_count and minimum_nights <= stay_nights, alongside price and room-type filtering.

Visual inspection of the green additions in Figures 6 and 7 confirms both the added fields and their corresponding function filters. This example is direct evidence that schema repair can require downstream function repair. The example's rank_and_select helper is not one of the nine public Appendix B operators, and its implementation is not supplied. Figure 7's positional filter arguments also differ from the keyword-only condition objects printed in Appendix B; the visual check confirms this is a source mismatch, not a text-extraction artifact.

### 8.4 Resource costs and limitations

**Paper, Sections 4.7 and 5, PDF pages 7 to 8; Figure 8.**

Runtime and input/output token counts are resource proxies, paired with TravelPlanner final pass rate. The paper reports fewer input tokens than ReAct and MemP but higher runtime and output-token usage than several baselines, principally due to query-specific graph instantiation.

The conclusion identifies graph-instantiation cost, dependence on extractor/judge quality, and the need for a reliable task evaluator. Reusable or incrementally updated graphs, stronger verification/human feedback for open-ended tasks, and richer representations/operators are future-work directions. They are not already evaluated mechanisms of the published method.

### 8.5 Multi-seed robustness

**Paper, Appendix C, PDF page 11; Table 4.**

Three TravelPlanner runs use DeepSeek-v4-flash and seeds labeled 1, 2, 3. Reported final rates are 54.00, 58.20, and 55.50; mean and standard deviation are 55.90 +/- 2.13. CS macro is 58.60 +/- 2.38 and HC macro is 61.57 +/- 1.04. The complete five-metric table is preserved in the extracted text. Its grouped headers, seed rows, and reported summary row were checked against the rendered PDF page 11.

**Open detail:** The paper does not explain exactly which randomness those seed labels control, including provider nondeterminism.

## 9. Open-detail register for implementation planning

| ID | Missing or ambiguous detail | Why it matters | Required treatment |
|---|---|---|---|
| GAP-01 | Exact lightweight schema grammar and OWL mapping | Defines which logical constraints HermiT actually checks | Specify a supported grammar and axiom mapping; validate with real HermiT; label as engineering decisions. |
| GAP-02 | Prompts and structured response schemas for Analyze, Draft, Extract, Compose, Judge, ReAct | Affects every LLM-produced artifact | Version actual prompts and schemas; record source basis and assumptions. |
| GAP-03 | Function realization grammar and execution permissions | Determines computability boundary and tool behavior | Define a typed executable contract grounded in O; do not assume arbitrary code is the published grammar. |
| GAP-04 | Conflicting attributes, missing/normalized primary keys, relation identity | Affects canonical graph contents and answers | Declare merge policy; examine effects on extraction, traversal, and aggregation. |
| GAP-05 | Corpus chunking and extraction budget | Changes evidence coverage, costs, and duplicate rate | Declare chunking/tokenization settings and retained provenance. |
| GAP-06 | Exact dataset versions, splits, sample IDs, and aggregate weights | Required for reproducibility and avoiding evaluation leakage | Record real corpus/task manifests; distinguish pilot protocol from paper reproduction. |
| GAP-07 | Inner schema retries and repair acceptance/rollback | Can create unbounded loops or inconsistent artifacts | Specify bounded behavior and failure status; preserve failures in logs. |
| GAP-08 | Operator types and edge-case semantics | Determines deterministic behavior and compatibility | Define result/condition types, null/order/unit/precision policies, and executable checks. |
| GAP-09 | Prompts/model parameters and model availability | Alters experimental comparability | Record exact actual model/configuration; disclose substitutions. |
| GAP-10 | Evaluation adapters and answer normalization | Can change reported success without changing task behavior | Use benchmark-owned semantics; preserve evaluator version and real outputs. |
| GAP-11 | Kernel serialization, revision IDs, resumption | Necessary engineering features not defined by the method | Keep separate from paper requirements; version dependency relationships. |
| GAP-12 | Figure 5 round count and illustrative/API signature mismatch | Visually confirmed internal source ambiguity | Retain five-round main setting; document the distinct illustrative signatures and seek author artifacts before claiming a reconciliation. |

## 10. Section and evidence coverage map

| Paper section | PDF pages | Refined coverage | Complete evidence retained |
|---|---|---|---|
| Abstract and Introduction | 1 to 2 | Problem, executable interface, K=(S,F), construction/inference boundary | paper-text.md: Abstract and 1 Introduction |
| Related Work | 2 | Context and baseline distinction | paper-text.md: 2 Related Work; original references retained |
| 3.1 Overview / Figure 1 | 2 to 3 | Objects, kernel boundary, two stages | paper-text.md: 3.1; PDF Figure 1 visually checked |
| 3.2 Construction | 3 to 4 | All four steps, formulas, merge identity, repairs, stopping | paper-text.md: 3.2; page-marked PDF text; page 3 formulas visually checked |
| 3.3 Inference | 4 | Frozen S/F and query-specific graph | paper-text.md: 3.3 |
| 4.1 Tasks | 4 to 5 | Dataset surfaces and metric semantics | paper-text.md: 4.1 |
| 4.2 Details | 5 | Models, 20% sampling, 5 rounds, 20 agent steps | paper-text.md: 4.2 |
| 4.3 Main results / Tables 1 to 3 | 5 to 6 | Selected OaK results and aggregate definitions | All rows retained in paper-text.md; PDF for header layout |
| 4.4 Ablations / Figures 2 to 4 | 5 to 6 | Three interventions and qualitative findings | paper-text.md: 4.4; PDF for plotted values |
| 4.5 Loop analysis / Figure 5 | 7 | Per-round evaluation and plateau claim | paper-text.md: 4.5; visual check confirms labels 1 through 7; plotted values not digitized |
| 4.6 Case study / Figures 6 to 7 | 7 | Hotel schema and function changes | paper-text.md: 4.6; schema/function additions visually checked |
| 4.7 Cost / Figure 8 | 7 | Runtime/token tradeoffs | paper-text.md: 4.7; PDF for plotted values |
| 5 Conclusion | 7 to 8 | Limitations and future work | paper-text.md: 5 |
| References | 8 to 9 | Retained as evidence, not additional implementation requirements | Complete reference section in paper-text.md and PDF |
| Appendix A | 10 | All five consistency categories | paper-text.md: Appendix A; rendered page checked |
| Appendix B | 10 to 11 | All nine signatures and published defaults | paper-text.md: Appendix B; page-marked PDF text; rendered signatures checked |
| Appendix C / Table 4 | 11 | Three runs and reported variability | Full numerical table retained in paper-text.md; grouped headers and values visually checked |
| Appendix D / Figures 9 to 11 | 11 | Same ablations on gpt-4o-mini and stated values | paper-text.md: Appendix D; PDF for plotted values |

## 11. Verification status

- Read the complete extracted text, including appendices and references.
- Cross-checked the nine operator signatures against the page-marked PDF extraction and rendered PDF pages 10 and 11.
- Visually checked Figure 1 and the construction formulas on PDF page 3, the round labels and schema/function diffs on page 7, Appendix A on page 10, and Table 4 on page 11.
- Confirmed the Figure 5 round-count ambiguity and Figure 7 versus Appendix B signature mismatch in the rendered source.
- Preserved all available source text and numerical tables separately from this refinement.
- Recorded unresolved author choices and source inconsistencies without supplying invented answers.
- No model calls, HermiT execution, graph construction, benchmark runs, or scientific result reproduction have been completed by creating this document.
- Targeted visual QA is complete for pages 3, 7, 10, and 11. This is not an exhaustive layout check of every page or digitization of chart-only numerical values. Exact values for Figures 2 to 5 and 8 to 11 require explicit source labels or author data; any later plot digitization must be labeled approximate. The raw PDF remains the authority for layout-sensitive details.

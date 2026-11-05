# Kernel preservation through verified language translation

Status: deferred reference methodology as of 2026-11-04. [Historical execution replay](historical-execution-replay-plan.md) is the sole active execution plan. The proposed milestones below are not a parallel execution track, and this methodology does not replace that plan's required historical replay. No preservation checker, formal proof, benchmark result, or runtime improvement is established by writing this document. Documentation remains local.

## 1. Decision and scope

Treat a kernel revision as a translation between two versions of an executable language. A candidate must provide an implementation of every inherited protected capability and evidence that the translation preserves its specified observations. Verify each child against its immediate parent, then compose valid certificates to inherit guarantees from earlier ancestors.

The intended saving is to replace previous-case execution with reusable preservation proofs for the certified portion of the kernel. This does not establish the completeness of a task family, the correctness of an initially wrong function, or the choices of a fresh LLM planner.

The curator continues to own required task scope. The engine owns translation checking, inheritance accounting, invalidation, and truthful evidence presentation. There is no fixed one-or-two-function requirement. More capabilities can be introduced as scope grows; inherited capabilities cannot silently disappear from the protected contract.

### Source and decision boundary

| Classification | Basis |
| --- | --- |
| Paper-specified | OaK constructs S/F, validates the encoded ontology with HermiT, evaluates executions, and refines S/F. Frozen inference uses declared functions over query-dependent G. See [the paper specification](paper/method-spec.md), Sections 2 to 3 and 8.3. |
| Paper does not establish | Transitive preservation certificates, a verified compatibility compiler, complete dependency tracking, or a guarantee that each refinement preserves all previous task success. |
| User-requested extension | Preserve required behavior after schema changes without rerunning all previous questions; reuse existing reasoning through adapters; carry guarantees across successive revisions. |
| Engineering choice | A restricted executable language, explicit graph relations, translation validation, immutable capability contracts, and incremental certificate checking. |
| Unresolved implementation work | Formalize actual operator semantics, establish rule soundness and interpreter correspondence, implement the checker, then measure its coverage and cost on real artifacts. |

This plan extends the adapter and selective-regression design in [design.md](design.md). It does not activate additional construction rounds, automatic promotion, or new UI controls. Uncertified behavior continues to require the existing broader checks before any task-success claim.

## 2. The language being translated

The language here is the executable function/plan language, not English and not a model's private reasoning. Preserve typed calls, bindings, selections, projections, traversals, aggregations, results, and observable failures. Natural-language requirement interpretation remains a separate evidential boundary.

The existing finite compositions in `oak.functions`, registered primitives in `oak.operators`, and exact schema definitions are the implementation starting point. See the [function-language documentation](functions.md) and [generated runtime reference](reference/runtime.md). The adapter in `oak.regression` currently checks interface renames and supports actual recorded-call replay, as described in the [regression documentation](regression.md). Its interface validator explicitly does not establish semantic preservation. Existing artifacts must not be relabeled as certified.

Define these objects for the planned verifier:

| Object | Meaning |
| --- | --- |
| K_i = (S_i, F_i) | An immutable kernel revision. Operator implementations and other execution dependencies are pinned separately. |
| B_i | Versioned, protected capability contracts inherited or introduced at revision i. |
| L_i | The supported typed executable language over those contracts, with explicit observable semantics. |
| T_ij | A total translation on the protected fragment of L_i into realizations available in revision j. |
| R_ij | The relation between old and new graphs, inputs, and any other relevant execution state representing corresponding evidence. |
| Obs_i | The declared observation contract, including values, identity/provenance references where observable, ordering, and typed failures. |
| C_ij | Checked evidence binding the exact revisions, translation, relation, assumptions, rule set, and supported fragment. |

Each protected capability needs stable identity, version, accepted inputs, meaning of outputs, required graph invariants, failure behavior, and source requirement attribution. The new construction obligation-to-function accounting can supply links, but a model-written mapping is not a semantic specification or proof. Bootstrap contracts must explicitly separate reviewed requirements from observed implementation behavior.

Keep semantic contracts separate from presentation names and descriptions. Stable IDs make mapping tractable but do not prove unchanged meaning. A translated entry point must remain executable through the frozen catalog and authorized operator boundary, without arbitrary code or access to benchmark answers.

## 3. Preservation obligation

For every protected program p, valid old input x, and related state pair (G_i, G_j), require:

```text
R_ij(G_i, G_j) and Pre_i(p, G_i, x)
    imply
Pre_j(T_ij(p), G_j, a_ij(x))
    and
Obs_i(run_i(p, G_i, x))
    = b_ji(Obs_j(run_j(T_ij(p), G_j, a_ij(x))))
```

a_ij and b_ji are the checked input and output mappings. The equation compares corresponding evidence, not old and new live-world facts gathered at different times.

```text
old graph + old input  ---- old program ----> old observation
         |                                      ^
     state/input mapping                    output mapping
         |                                      |
new graph + new input  -- translated program --> new observation
```

The result is a conditional semantic theorem over all inputs satisfying its explicit assumptions. It is not a list of matching recorded outputs.

### Non-vacuity and substitutability

It is insufficient to prove equality only for the few old inputs the candidate still accepts. The checker must also establish that the mapping is defined for every state/input admitted by the protected old contract, or explicitly report a narrower conditional scope. New preconditions must not exclude formerly supported inputs. New invariants must follow from old invariants and the transformation, rather than being assumed because they make the proof convenient.

A graph migration needs a totality argument on that domain. A compatibility view needs a source-preservation argument. A runtime guard can verify a condition for a particular graph; that is instance-specific evidence and cannot be promoted to an unconditional guarantee over all old graphs. Inconsistent assumptions must never produce a vacuous preservation certificate.

### Observations and exactness

Define semantic observations before accepting rewrites. Cover empty results, null versus absent values, booleans versus numbers, multiplicity, group order, sorting/tie behavior, errors, canonical identities, and provenance links used by later operations. Timing and diagnostic wording may be excluded from semantic equality only when callers cannot depend on them. Execution limits and operational cost remain explicit acceptance constraints.

Initial certificates use exact equality after checked canonical mappings. Do not treat pairwise numeric tolerance as a transitive equivalence: an allowed error at each revision can accumulate across a chain. Approximate preservation requires a separate error-composition calculus and an ancestor-relative error budget, and is deferred.

The current numeric implementation uses Decimal operations followed by JSON number conversion. A proof over ideal real numbers does not automatically cover rounding, precision context, serialization, or changed aggregation order. Likewise, a rename can alter identity-derived ordering and top-k results. These are obligations, not harmless syntactic details.

## 4. Why checking the parent can cover the ancestors

Suppose C_01 establishes preservation from K_0 to K_1, and C_12 establishes preservation from K_1 to K_2. Compose:

```text
T_02 = T_12 composed with T_01
R_02(G_0, G_2) iff some G_1 satisfies R_01(G_0, G_1) and R_12(G_1, G_2)
a_02 = a_12 composed with a_01
b_20 = b_10 composed with b_21
```

The checker must establish that the intermediate contracts and assumptions match and that the totality obligations remain satisfied. Applying the first preservation result and then the second gives equality of the oldest and newest observations. Repeat by induction along the revision chain.

This argument requires all of the following:

1. B_(i+1) retains every inherited protected contract from B_i, including contracts implemented through earlier adapters. New capabilities extend that set. Checking only newly authored functions is insufficient.
2. Every adjacent certificate covers the relevant language fragment, data relation, observations, and execution semantics. Missing or unknown links cannot be crossed as if proved.
3. Translations preserve well-typed composition. Any control flow claimed to be supported must also preserve its conditions, termination, and relevant intermediate observations.
4. The composed translator and intermediate witnesses remain available or have a separately checked equivalent replacement.
5. All inherited preconditions and provenance mappings are discharged, rather than silently tightened or dropped.

A certificate for each primitive plus a sound composition rule can cover all well-typed plans in the defined fragment. A certificate for one function covers only that function and the compositions justified by its contract. A saved sequence of calls does not contain all hypothetical branches or the semantics of an intervening LLM decision.

An empirical pass at K_0 remains empirical evidence. A complete computational preservation chain can carry forward its deterministic computation on corresponding inputs; it cannot convert that initial pass into universal task correctness. Intentional fixes to incorrect behavior create explicitly revised contracts instead of claiming equivalence to the error.

Branching histories require an actual ancestry path. A merge must discharge obligations for every inherited contract it claims to retain. Chronological adjacency is not lineage. If a chain is incomplete, retain the last certified implementation, obtain a direct proof covering the gap, or report the new revision as uncertified for that scope.

## 5. Research mechanisms and their roles

### Information preservation and query rewriting

For a representation mapping M and protected query q, query determinacy requires:

```text
M(G_a) = M(G_b) implies q(G_a) = q(G_b)
```

If the new representation merges states whose required answers differ, no adapter using only that representation can recover those answers. Retaining enough information still does not establish that our executable language can express the required rewriting. Require an actual executable translation and its preservation derivation. This follows the distinction in [Views and Queries: Determinacy and Rewriting](https://lsv.ens-paris-saclay.fr/Publis/PAPERS/PDF/NSV-tods10.pdf).

The goal is to retain distinctions required by B_i, not a percentage of old declarations. Removing irrelevant internal detail can be legitimate. New capabilities require additional information and new correctness evidence; preservation does not establish their usefulness.

### Ontology conservativity and query inseparability

HermiT consistency remains mandatory where applicable but does not establish equivalence of old and new ontologies. Protect the meaning of an explicitly selected vocabulary/module. Query inseparability concerns unchanged relevant query answers; concept-level preservation alone may be too weak. General checks can be undecidable or costly. Start with sufficient conditions and supported fragments rather than a universal decision procedure. See [the inseparability survey](https://arxiv.org/abs/1804.07805) and [locality-based ontology modules](https://www.cs.ox.ac.uk/publications/publication898-abstract.html).

Logical open-world semantics and finite graph execution must remain distinct. OWL existential/cardinality axioms do not by themselves prove that concrete extracted records contain the total unique joins required by an executable function. Adding axioms is not automatically conservative, and adding records can change counts or no-match results.

### Behavioral refinement and translation validation

Use [behavioral subtyping](https://www.cs.cmu.edu/~wing/publications/LiskovWing94.pdf) to preserve old accepted inputs and promised outcomes. Use [translation validation](https://finkbeiner.groups.cispa.de/publications/2007-translation-validation-for-optimizing-compilers/) to check each actual old/new pair independently of the proposal generator. The LLM may suggest a patch, mapping, or proof derivation; it cannot certify its own output by explanation or score.

Proof search may be expensive or heuristic. Certificate checking should be small, deterministic, bounded, and separate. The [proof-carrying-code model](https://www.usenix.org/legacy/publications/library/proceedings/osdi96/full_papers/necula/html/node2.html) motivates this producer/checker split. Hash matching establishes identity, not theorem truth.

### Compositional proofs and efficient implementations

[HoTTSQL](https://homes.cs.washington.edu/~suciu/hottsql.pdf) demonstrates machine-checked query-rewrite reasoning. OaK needs a semantics matching its actual operators, not an assumption that SQL results transfer unchanged to NetworkX records, Python lists, or its numeric behavior.

Later, [equality saturation](https://arxiv.org/html/2004.03082v3) can explore equivalent implementations and select one using a cost model. Every rewrite must have valid side conditions. Flattening an adapter chain is itself a transformation requiring a certificate. This is optional optimization after a working preservation checker, not an initial dependency.

## 6. Initial certification fragment

Begin with pure, finite, deterministic computations. Preserve the existing typed DSL and executor instead of adding a second application workflow. Lower supported constructs to a small intermediate representation whose semantics is explicit and attributable to the actual runtime.

| Candidate change | Initial treatment and obligation |
| --- | --- |
| Identical protected implementation and dependencies | Reuse a valid prior certificate after checking its complete dependency identity and scope. An old test receipt is not a certificate. |
| Function/argument/result field renaming | Require capture-free bijections, preserved validation and value semantics, and corresponding executable bodies. Equal JSON schemas alone are insufficient. |
| Schema symbol renaming | Prove state mapping, identity/provenance mapping, constraints, ordering, and all affected operator references correspond. Start by rejecting unsupported identity changes. |
| Add internal fields or an isolated module | Keep an exact old view and prove additions cannot affect protected queries, wildcard access, inferred memberships, identities, or result populations. |
| Equivalent select/project compositions | Admit only with established rules for actual missing-value, multiplicity, ordering, and error semantics. |
| Split/merge entities or substitute relation paths | Later rule family: require executable lossless views, total unique keys where needed, preserved duplicates/order, and checked concrete data invariants. |
| Unit conversion or arithmetic rewrites | Defer until numeric representation, rounding, comparison, overflow/error, and serialization preservation are supported. |
| Arbitrary new ontology axioms, unsupported traversal, or opaque functions | Unknown unless covered by a checked rule or separately certified proof procedure. |
| Model slot extraction, graph extraction, live MCP acquisition | Outside unconditional pure-computation certification. Use explicit input/effect boundaries; do not simulate these operations. |

Begin the operator audit with exact lookup, projection, categorical/numeric filtering, and count over finite collections. A rule may be rejected even for these operators if its required semantics is not formalized. Expand to aggregates, set operations, and bounded traversal only as their proof obligations are established. Resource limits are executor bounds, not arbitrary restrictions on task scope.

An output-preserving old view can initially run the old implementation over the new representation. It still needs a proof that the view preserves required information, and it must comply with the frozen execution boundary. This provides a practical compatibility path before proving optimized new implementations equivalent.

## 7. Trust, data, and effect boundaries

The trusted base includes operator semantics, the correspondence between that semantics and the executed implementation, accepted rule soundness, the certificate checker, artifact identity, and invariant enforcement. Pin their versions. A correct theorem about an incorrect lowering does not prove the Python execution correct.

Milestone 1 must choose and document how rule soundness and lowering correspondence are established. A small rule checker is the initial architectural choice. Machine-checked lemmas through a suitable proof assistant are the preferred assurance path; backend selection is a bounded implementation investigation, not a new pinned dependency in this plan. Reviewed mathematical arguments, tested correspondence, and machine-checked proofs must remain separately labeled. Tests alone cannot authorize a universal formal-preservation claim. Optional solvers may help discover proofs or counterexamples; unsupported theories, bounded searches, and timeouts cannot become universal success.

For graph data, bind preservation to source receipts/snapshots and an explicit migration or compatibility view. A theorem over related graphs does not prove that a newly run LLM extractor produces related graphs. Preserve a valid existing extraction path for protected facts, use a justified deterministic source mapping, or leave that boundary uncertified. Retained receipts used to check a mapping are historical evidence, not newly acquired forecasts or simulated MCP responses.

Acquisition and extraction inside a function prevent treating the entire function as pure. Certify a deterministic suffix conditional on a validated acquired graph, and show that limited scope. A future effect-preserving translation would additionally need matching requests, ordering, permissions, failure semantics, state updates, and graph bindings. Live-source equality and fresh model output are not consequences of equal tool schemas.

Fresh LLM planning stays outside the proof. Catalog text, schema context, prompts, models, extraction, or routing changes can alter decisions even if every pure function is equivalent. A versioned compatibility interface can keep an old execution route stable, but selecting that route from a new natural-language question is a separate problem. Do not certify a recorded LLM trace as a general decision policy.

## 8. Candidate workflow and deterministic outcomes

1. Load the immutable parent, its inherited capability set, and the valid certificate dependency closure. Establish the exact public contracts the candidate must retain.
2. Generate or receive the candidate patch and mappings. Proposal inputs include contracts, schema/function differences, and public requirements. Exclude reference answers, task-ID special cases, and prior answer caches.
3. Run actual ontology and graph/function validation as applicable. Establish the concrete mapping obligations separately from logical satisfiability.
4. Lower protected realizations to the supported language. Record unsupported constructs and effects explicitly.
5. Compute semantic impact and reuse only valid unaffected certificates. Recheck changed obligations using established rules and bounded proof search.
6. Check preservation, non-vacuity, inherited coverage, assumptions, totality, and actual translation executability. Emit a receipt for every attempted obligation.
7. Compose successfully checked adjacent certificates. Persist their scope and actual lineage. No certification job changes an active kernel by itself.
8. Evaluate new capabilities and uncertified whole-agent behavior through the existing real checks under their original split and budget constraints. Keep that evidence separate from preservation.

| Result | Meaning | Consequence |
| --- | --- | --- |
| Certified within declared scope | The derivation checks against supported sound rules and all required assumptions have the recorded status. | Previous-case reruns are unnecessary for the covered computational preservation claim. |
| Counterexample | A validated witness violates an obligation. | Reject the preservation claim and expose the failed condition. |
| Unknown | Unsupported rule, incomplete dependencies, timeout, unproved assumption, or incomplete scope. | Retain the old certified route or perform the broader real checks needed for an empirical claim. Do not extend the certificate chain. |
| Invalid evidence | Hash, revision, lineage, parser, or proof-artifact validation failed. | Do not consume the evidence; retain failure attribution. This is not a semantic counterexample. |

These are conceptual outcomes, not a second hand-maintained API schema. The first implementation must define authoritative Pydantic models and generate API/frontend types from them. Partial results identify the exact certified and uncertified capabilities; they never display a whole-kernel success badge.

Formal counterexamples are mathematical witnesses, not fabricated benchmark observations. Label them as such and never merge them into retained source graphs or report them as real model/service executions. Formal small-model witnesses may be used for checker analysis; benchmark demonstrations still require genuine data and real components.

## 9. Incremental checking and durable evidence

Organize proof obligations by capability and semantic module, with shared premises. Record dependencies on schema axioms, function/operator bodies, graph-view definitions, identity/merge rules, result ordering, numeric semantics, and all relevant source/assumption contracts. Include negative dependencies, whole-set aggregates, and ontology entailment closure. Dynamic traces alone do not establish a complete dependency set.

Content-addressed certificates bind the old/new revisions, protected contract versions, language/semantics versions, translation, state relation, proof derivation, checker/rule versions, assumptions, and supporting evidence. The artifact store preserves immutable proof inputs and outputs; existing events expose their references. API readers and UI playback only inspect these artifacts.

An inherited coverage manifest must identify every contract and its certified realization. Reuse its digest and checked ancestry where possible, but validate new inheritance and dependency edges. There is no promise of constant-time checking: global axioms, wildcard behavior, or changed semantics can invalidate many obligations. The benefit is avoiding repeated model inference and deduplicating shared proof work, not eliminating all verification cost.

Changing the checker, rules, or semantic implementation invalidates affected trust assumptions until compatibility is established or certificates are rechecked. Historical certificates remain unchanged with their original trust basis. A certificate does not authorize reuse of an old answer when input facts changed.

The observation interface should show protected capabilities, exact lineage, certified scope, conditional assumptions, failed/unknown obligations, proof dependencies, and the reason old executions were unnecessary. Preserve the independent ontology, graph/function, replay, and fresh-task assessment dimensions. Unknown historical evidence stays unknown. This requires no manual editing, repair, or promotion controls.

## 10. Efficiency and candidate selection

Treat inherited preservation as a constraint for any claim of backward-compatible acceptance. Among eligible candidates, assess newly supported behavior and construction, migration, proof-checking, storage, and expected execution costs separately. Reward useful verified capability growth and cheaper implementations; unchanged or cosmetically small schemas are not automatically better.

Use actual measurements where available and label workload-dependent cost estimates. Report the amount of protected functionality certified, proof-checking time, translation overhead, and the number of previous executions avoided by a valid certificate. Never count unknown obligations as savings or claim unmeasured model cost reductions.

Compare a composed compatibility path with a flattened implementation only after equivalent observations are established. Bound proof search and translation expansion so a theoretically preserved computation does not become unusable under executor limits. Candidate proposal count is a configurable search budget, not a fixed five-candidate requirement.

## 11. Reviewable implementation milestones

| Milestone | Deliverable | Exit evidence |
| --- | --- | --- |
| 0. Formal scope and baseline | Audit actual operator semantics and existing real artifacts. Define protected contracts, observations, state relations, pure/effect boundaries, and a small typed intermediate language. Map paper gaps GAP-03, GAP-04, and GAP-08 explicitly. | A reviewed contract/semantics specification with unsupported constructs identified; no existing replay receipt relabeled as a proof. |
| 1. Sound rule/checker foundation | Establish identity, capture-free rename, sequencing, and isolated-view rules. Select and pin any necessary proof backend after a bounded feasibility check. Define the trusted base and implementation correspondence. | Actual checked derivations and soundness evidence, plus explicit assurance status for any unproved correspondence. Invalid derivations fail with evidence. |
| 2. One real parent-to-child translation | Apply one supported deterministic patch to a genuine retained kernel and graph. Derive candidates visibly from the real artifacts; do not invent benchmark observations. Execute the translation through the actual interpreter. | Correct input/output/provenance mapping, actual HermiT where relevant, and a certificate covering a named capability. Real differential execution validates integration separately from the universal proof. |
| 3. Transitive inheritance | Extend that genuine lineage to three revisions and compose adjacent proofs. Verify inherited capabilities are present even when no longer named directly in the newest catalog. | Ancestor guarantee derived from checked edges, no previous-case executions during the certification operation, and rejection of incomplete lineage, narrower domains, or missing inherited coverage. |
| 4. Incremental storage and inspection | Persist dependency graphs, proof/check receipts, invalidation, and coverage. Add authoritative typed contracts and evidence rendering through the existing API/events. | Reads/replay/reset make no calls; stale/corrupt/partial certificates do not imply success; only affected obligations are rechecked when independence is established. |
| 5. Broader transformations and evaluation | Add selected query rewrites and lossless graph views. Measure cost and coverage using genuine Coffee/USGS and retained weather evidence, with fresh inference only for claims that need it. | Measured preservation coverage and limits across materially different surfaces; separate agent-task outcomes and actual usage receipts. |

The next bounded milestone is 0, followed by the smallest viable identity/rename checker in milestone 1. No runtime milestone is authorized or started by this documentation request. Later paid checks require their own bounded execution plan inside the existing global $40 ledger, including unknown reservations. Historical held-out answers remain outside proposal and refinement inputs.

Formal-checker development may use real interpreter executions on genuine retained artifacts to validate implementation correspondence. The operational guarantee is that an already supported transformation can be certified without rerunning previous cases. Development validation is not a substitute for proof and is not a requirement to repeat those cases on every future revision.

## 12. Acceptance and failure checks

- Two adjacent valid translations compose to preserve every inherited protected capability on their declared domain. Proof composition checks assumptions and intermediate contracts, not merely parent IDs.
- Newly introduced preconditions, inconsistent assumptions, or partial migrations cannot remove old supported inputs while receiving a full preservation result.
- Missing function mappings cannot be hidden by a high aggregate coverage score. Candidate-added capabilities cannot replace inherited obligations.
- Same names or JSON types with different computation fail certification unless their required behavior is independently proved.
- Rename collisions, identity/order changes affecting top-k, duplicate-producing joins, null/absent conflation, numeric rounding, and lost provenance receive explicit unsupported or failing results.
- Added rows, inferred memberships, and changes affecting no-match or aggregate queries invalidate the correct obligations even when all previously returned entities remain unchanged.
- A timeout, bounded counterexample search, or unproved runtime assumption never becomes a universal certificate. Any conditional certificate displays its conditions and requires their discharge before use.
- Tampered artifacts, missing certificates, semantics-version changes, and a break in lineage prevent unjustified ancestor guarantees. Existing historical evidence remains inspectable.
- Changing extraction, MCP contracts, or LLM planning does not inherit a whole-task success claim from a pure-function certificate.
- Explicitly revised requirements are recorded as semantic changes. The system does not preserve a known bug merely to match an obsolete answer.
- Current numeric error tolerances are not composed as exact equivalence. Approximate translation remains unsupported until its separate calculus exists.
- Certification and inspection make no model, MCP, or paid evaluator calls. The first implementation demonstrates this with actual call/ledger evidence, without mocked providers.

## 13. Planning verification and remaining limits

This plan was grounded in the local paper specification, design/work plan, existing finite function DSL, operator implementations, rename adapter, and primary research linked above. It preserves the distinction between structural checks, semantic preservation, recorded execution, and fresh task success.

Only documentation is delivered in this milestone. No new proof backend has been selected or installed, no rule soundness or interpreter correspondence has been established, and no claimed speedup has been measured. The formalization effort and attainable certified coverage remain implementation questions. Arbitrary schema changes and fresh agent decisions are outside the guarantee unless their own obligations are established.

# Independent specification review

Review the supplied OaK paper text, refined method specification, and project design. This is read-only analysis. Do not modify files, install packages, run benchmarks, or invent experimental results.

The authoritative paper is arXiv:2608.22974v1. The project adds observable, versioned schema S, graph G, functions F, text suggestions validated through OWL/HermiT, and constrained schema/function adapters for earlier tasks. No mocks are permitted.

Return a concise review with these sections:

1. Paper fidelity: missing or incorrect requirements, with section/page evidence.
2. Missing details: distinguish author omissions from our explicit engineering choices.
3. Cross-component consequences: schema changes, extraction, identity, graph invariants, function behavior, and freeze boundaries.
4. Adapter soundness: allowed transformations, preconditions, loss of information, cardinality, units, query/negative dependencies, and potential answer leakage.
5. Evaluation validity: separate HermiT consistency, real function replay, and fresh agent behavior. Inspect split leakage and unsupported claims of reproduction.
6. Minimal real milestone: what can be built and checked on the official Coffee benchmark first.
7. Priority issues: only actionable findings, with evidence and a proposed resolution or explicit uncertainty.

Do not equate passing historical training cases with a universal certificate. Do not allow adapters to return archived answers instead of executing new real artifacts. Do not substitute generic framework preferences for the paper's ontology kernel.

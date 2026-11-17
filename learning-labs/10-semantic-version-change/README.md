# 10: A changed meaning changes answers, so adoption needs a gate

## Question

What happens when an ontology-backed action rule changes from project-wide approval to service-specific approval?

## Terms introduced

| Term | Meaning in this lesson |
| --- | --- |
| Semantic change | A change in what a definition or attached rule means |
| Breaking change | Existing inputs or conclusions can now produce different outcomes |
| Pinned package | An episode's fixed bundle of definitions and executable rules |
| Candidate | A proposed new version, not yet governing new episodes |
| Regression | Previously required behavior becomes incorrect |
| Acceptance gate | Deterministic conditions governing adoption |

## Input and prediction

Read `input.json`. A synthetic policy-owner receipt establishes the new service-specific requirement. Without that authority, changing the policy merely to improve a score would not be justified. These rules are part of a domain package, not OWL axioms executed by an OWL reasoner.

| Case | v1 prediction | v2 prediction | Required result |
| --- | --- | --- | --- |
| Project-only approval | Permit | Deny | Deny |
| Service approval | Permit | Permit | Permit |
| No approval | Deny | Deny | Deny |

The negative candidate denies everything. It fixes the target example but breaks service-approved deployments. It must be rejected.

## Run

```sh
python3 learning-labs/10-semantic-version-change/run.py
```

The script reports every case for every package, candidate decisions, the old episode's pin, the new episode's pin, and seven checks. It exits 0 only if all checks pass. It writes no production package or world state. All candidates are assistant-authored teaching fixtures, not outputs from Gemini.

## Exact execution

1. Pin an existing episode to v1.
2. Compute parent and candidate outcomes over independent fixture cases without mutable shared world state.
3. Require agreement with the source policy, improvement over the parent, and all required preservation checks.
4. Retain v2 only in this process's simulated release variable.
5. Verify that the active episode still references v1 and a new episode references v2.

Pinning gives reproducible interpretation. It is not a guarantee that an old authorization remains safe forever. An actual urgent policy revocation requires an explicit stop or revalidation policy; never silently rewrite the active episode or let a stale permission override current authorization.

## Industry standards versus our choices

[OWL 2 versioning](https://www.w3.org/TR/owl2-syntax/#Versioning_of_OWL_2_Ontologies) provides ontology and version identifiers plus version annotations. It does not implement our acceptance gate or hot-migration policy.

[Semantic Versioning](https://semver.org/) is a published software-versioning convention for a declared public API. A version number alone cannot detect a changed meaning. This lesson uses v1/v2 labels and makes no claim of SemVer conformance.

[SHACL](https://www.w3.org/TR/shacl/) validates RDF graphs against shapes. Passing graph-shape validation would not by itself prove that this new approval policy is correct or authorized. Behavior checks and authoritative requirements remain separate.

## Bridge to the real project and AppWorld

This executable teaches change control. It does **not** complete the native improvement experiment. The actual project assigns Qwen task execution, Gemini diagnosis, a separate Gemini proposer call, and deterministic acceptance based on fresh AppWorld worlds and its official evaluator.

The current [connected inference notes](../../docs/system/19-connected-inference.md) describe a missing Gemini coordinator and default `GEMINI_DIAGNOSIS_REQUIRED` guard. The [measured results](../../docs/system/20-live-acceptance.md) retain a prior `UNSUPPORTED_CLIENT` Gemini failure. That is historical evidence, not a fresh availability probe by this lab. No alternate model is substituted here.

To complete the native bridge, obtain a recorded real Qwen episode, give Gemini bounded original evidence for diagnosis, call Gemini separately for one candidate, and compare parent/candidate in fresh AppWorld worlds with the official evaluator and preservation gates. Retain missing results and rejected candidates. A fixture passing here cannot count as native task success, Gemini diagnosis success, or candidate promotion.

The current native adapter is narrow. This deployment example is not claimed to be supported by that adapter. The domain package for an actual Spotify task must use its documented entities and actions instead.

# 09: Extend the ontology without inventing observations

## Question

When we add environment-specific, time-bounded assignments, what happens to old maintenance records?

## Terms introduced

| Term | Meaning |
| --- | --- |
| Ontology extension | Adding definitions needed to express another supported concept |
| Compatibility | Preserving existing meanings and required behavior |
| Migration | Transforming records into a new representation |
| Unknown | Evidence does not establish a value or conclusion |
| Observation gap | A needed value is missing from evidence |
| Definition gap | The representation cannot express a needed concept |

## Inputs and prediction

Read `input.json`. Version 1 says Maya maintains LoginService but says nothing about environment or expiry. Version 2 adds Assignment while keeping the old relationship meaning unchanged. A separate source record says Noah has a staging assignment expiring November 20.

Predict: the old query still finds Maya. A new staging-and-date query returns UNKNOWN for Maya and TRUE for Noah. Adding fields cannot reveal Maya's missing environment or expiry.

## Run

```sh
python3 learning-labs/09-ontology-extension/run.py
```

The JSON output contains the original assertion, an incomplete migration record, the scoped query results, the source hash, and eight checks. Exit 0 means those checks passed. `null` represents an absent known value in this custom JSON format, not a literal RDF null.

## Exact computation

1. Compare the retained definitions and reject changed meanings in the small fixture dictionary.
2. Preserve the original maintenance assertion.
3. Create a migration record with a provenance link and unknown scope fields. This is an incomplete record, not proof of a newly discovered assignment.
4. Evaluate the scoped query. Unknown fields cannot satisfy an action prerequisite.
5. Try a negative candidate that silently changes maintenance into production-deployment authority. Reject it.

## Industry standards and their limits

[OWL 2 ontology versioning](https://www.w3.org/TR/owl2-syntax/#Versioning_of_OWL_2_Ontologies) provides ontology/version identifiers and version annotations. Version identifiers do not themselves establish compatibility. Our dictionary comparison only checks exact retained definitions in this fixture; it is not a general logical compatibility algorithm or OWL reasoner.

[SHACL](https://www.w3.org/TR/shacl/) supplies a standard language for validating RDF data graphs. A real migration can validate the resulting graph with shapes. This script uses explicit Python checks, not SHACL. Adding a class or axiom is not automatically logically conservative.

[PROV-O](https://www.w3.org/TR/prov-o/) provides a shared vocabulary for derivation provenance. Our `derivedFrom` field illustrates that idea but is a custom JSON field.

## What changes, and what does not?

The ontology version changes because expressible definitions changed. Adding Noah's observed assignment is a graph update. The assistant authored both teaching versions; neither is a Gemini-proposed or accepted production change. No live model, AppWorld world, or native evaluator runs here.

Our TRUE/FALSE/UNKNOWN convention is a runtime policy for this lesson. It is not SHACL's result model and not a complete account of OWL's open-world semantics.

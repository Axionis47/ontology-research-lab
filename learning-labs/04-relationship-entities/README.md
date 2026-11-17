# 04: A relationship can have its own identity

**Claim:** an assignment entity preserves scope and time that a bare maintains edge omits.

## Terms

- **Relationship entity:** an entity representing an association with several participants or attributes.
- **Scope:** where a responsibility applies, here service plus environment.
- **Validity interval:** when the assignment applies.
- **Literal:** a value such as an ISO date.

## Input and prediction

`input.json` gives Assignment17 to Maya for LoginService staging, valid from November 1 up to but excluding November 20, 2026. The clock is fixed at November 16 for reproducibility. Predict staging and production lookup results, then the result exactly at expiry.

## Mechanism and expected output

Filter assignments by service, role, environment, and the interval `validFrom <= at < validUntil`. Staging returns Maya; production and expired staging return no supported assignment. Missing required fields fail to qualify. Empty results mean unknown coverage, not proof nobody is responsible.

**Limit:** the interval convention and qualification rule are explicit local policy. A relationship entity does not evaluate time by itself.

## Standard versus local choice

The [W3C n-ary relations note](https://www.w3.org/TR/swbp-n-aryRelations/) describes introducing an entity for relations with additional participants or details. It is an informative Working Group Note, not a normative Recommendation. `graph.ttl` expresses our chosen assignment pattern in RDF.

## Execution boundary

This is a synthetic teaching fixture, not an AppWorld result or a model experiment. The runnable code uses Python standard-library data structures. It is a small explicit algorithm, not an RDF reasoner, SPARQL engine, or SHACL implementation. Companion `.ttl` and `.rq` files show standards syntax; this runner does not parse or execute them. No model is called.

Run from the repository root using the command below. The JSON output contains inputs, computed observations, named checks, and `passed`. A failed expectation exits with status 1. Editing inputs can intentionally make those checks fail.

```sh
python3 learning-labs/04-relationship-entities/run.py
```

# 03: Well typed does not mean supported

**Claim:** structural validation and evidence admission answer different questions.

## Terms

- **Constraint:** an executable acceptance condition.
- **Shape:** in SHACL, a description of conditions to validate against graph data.
- **Provenance:** where a claim originated and how it was produced.
- **Admission:** a runtime decision to retain a claim for a declared use.

## Input and prediction

`input.json` holds known types, three candidate maintenance assertions, and a synthetic source receipt. A is correctly typed but uncited. B reverses Person and Service. C is correctly typed and exactly matches the recorded receipt.

## Mechanism and expected output

Check the candidate's subject and object types. Independently resolve its source ID and require the original receipt's triple to match. A: structure passes, evidence fails. B: structure fails. C: both pass.

**Limit:** receipt linkage proves traceability in this fixture, not that the external source is honest or complete. Production acceptance additionally needs appropriate source authority and freshness. Nothing is sent to a real service.

## Standard versus local choice

[SHACL](https://www.w3.org/TR/shacl/) defines graph validation. The companion shapes require a Person subject and Service object. [PROV-O](https://www.w3.org/TR/prov-o/) supplies provenance vocabulary; `provenance.ttl` associates a claim record with a source entity. Neither standard guarantees truth. The Python checks and receipt-matching admission rule are our small illustration, not a SHACL execution.

## Execution boundary

This is a synthetic teaching fixture, not an AppWorld result or a model experiment. The runnable code uses Python standard-library data structures. It is a small explicit algorithm, not an RDF reasoner, SPARQL engine, or SHACL implementation. Companion `.ttl` and `.rq` files show standards syntax; this runner does not parse or execute them. No model is called.

Run from the repository root using the command below. The JSON output contains inputs, computed observations, named checks, and `passed`. A failed expectation exits with status 1. Editing inputs can intentionally make those checks fail.

```sh
python3 learning-labs/03-constraints-provenance/run.py
```

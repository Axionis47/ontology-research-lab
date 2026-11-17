# 02: Definitions are different from facts

**Claim:** observing another instance changes the graph without requiring a new ontology.

## Terms

- **Class/type:** a category such as Person.
- **Instance:** a particular member, such as Maya.
- **Ontology:** reusable vocabulary and meanings.
- **Instance graph:** particular assertions about the current world.
- **Revision:** an identifier for a particular stored version.

## Input and prediction

`ontology.json` defines Person, Service, Project and two relationship meanings. `facts.json` describes Maya, LoginService, and Atlas. `new-observation.json` adds Noah as a Person. Predict which hash changes.

## Mechanism and expected output

Hash the definitions and graph independently, add the observation to a copy of the graph, then hash both again. The ontology hash remains equal; the graph hash differs. Noah is recognized through an existing type. A proposed `Robot` instance exposes an unknown type under this local admission rule, not an automatic ontology repair.

**Limit:** hashing detects representation changes, not semantic equivalence. Unknown type handling is our policy.

## Standard versus local choice

[RDF Schema](https://www.w3.org/TR/rdf-schema/) provides classes, properties, domain and range vocabulary. RDFS domain/range declarations support type inference; they are not closed-world rejection checks. JSON revision hashes and explicit admission rules here are local mechanisms.

## Execution boundary

This is a synthetic teaching fixture, not an AppWorld result or a model experiment. The runnable code uses Python standard-library data structures. It is a small explicit algorithm, not an RDF reasoner, SPARQL engine, or SHACL implementation. Companion `.ttl` and `.rq` files show standards syntax; this runner does not parse or execute them. No model is called.

Run from the repository root using the command below. The JSON output contains inputs, computed observations, named checks, and `passed`. A failed expectation exits with status 1. Editing inputs can intentionally make those checks fail.

```sh
python3 learning-labs/02-ontology-vs-facts/run.py
```

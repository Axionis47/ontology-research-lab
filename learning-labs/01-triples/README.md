# 01: A sentence becomes a triple

**Claim:** explicit subject/predicate/object structure permits exact lookup without asking a language model.

## Terms

- **Entity:** an identifiable thing, such as Maya.
- **Predicate:** the named relationship, such as `maintains`.
- **Triple:** a subject, predicate, and object together.
- **IRI:** a globally scoped identifier; `ex:Maya` abbreviates one in the Turtle file.
- **Literal:** a value such as a string or date, rather than an entity identifier.

## Input and prediction

`input.json` manually encodes two sentences: Maya maintains LoginService; LoginService belongs to Atlas. This is human-authored translation, not automatic extraction. Predict Maya's maintained services, LoginService's project, and the reverse lookup.

## Mechanism and expected output

`objects(subject, predicate)` scans triples whose first two fields match, then returns their third fields. Expected: `["LoginService"]`, `["Atlas"]`, and `[]` for LoginService maintaining Maya. Direction matters. Duplicating an assertion does not create a new fact in the set representation.

**Limit:** exact lookup does not establish truth or understand arbitrary English. An empty answer is absence in this fixture, not proof that no real-world relation exists.

## Standard versus local choice

[RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/) specifies a graph of triples. `graph.ttl` shows RDF Turtle identifiers. The simplified JSON tuple representation and lookup function are local teaching choices.

## Execution boundary

This is a synthetic teaching fixture, not an AppWorld result or a model experiment. The runnable code uses Python standard-library data structures. It is a small explicit algorithm, not an RDF reasoner, SPARQL engine, or SHACL implementation. Companion `.ttl` and `.rq` files show standards syntax; this runner does not parse or execute them. No model is called.

Run from the repository root using the command below. The JSON output contains inputs, computed observations, named checks, and `passed`. A failed expectation exits with status 1. Editing inputs can intentionally make those checks fail.

```sh
python3 learning-labs/01-triples/run.py
```

# 05: Connected does not mean authorized

**Recorded Gemini experiment:** [Read the input, ordered steps, actual response, checker, and repair status](../../experiments/02-ontology-concepts/README.md#05-separate-graph-connectivity-from-authority). The deterministic companion below is a separate execution.

**Claim:** traversal discovers paths; a supported decision needs the right predicates and a rule.

## Terms

- **Traversal:** following existing graph edges.
- **Join:** matching intermediate values across relationships.
- **Inference:** deriving a conclusion under a declared rule.
- **Open-world caution:** missing evidence does not automatically establish the opposite.

## Input and prediction

`input.json` says Maya belongs to Atlas and LoginService belongs to Atlas. A second scenario adds a current production DeploymentApprover assignment. A third uses the wrong environment.

## Mechanism and expected output

First join Maya's projects to services in those projects, printing intermediate project values. LoginService is connected. Then evaluate a separate approval rule requiring matching person, service, role, environment, and validity. Membership alone produces UNKNOWN; the matching assignment produces SUPPORTED; the staging assignment still produces UNKNOWN for production.

**Limit:** this is an application rule over supplied evidence, not an OWL reasoner or real authorization service. Production action permission must also consider the executor's authority.

## Standard versus local choice

[SPARQL 1.1](https://www.w3.org/TR/sparql11-query/) supports matching graph patterns and joins. `query.rq` shows the membership join in standard syntax. That query makes no approval claim. Our separate rule is explicitly implemented Python.

## Execution boundary

This is a synthetic teaching fixture, not an AppWorld result or a model experiment. The runnable code uses Python standard-library data structures. It is a small explicit algorithm, not an RDF reasoner, SPARQL engine, or SHACL implementation. Companion `.ttl` and `.rq` files show standards syntax; this runner does not parse or execute them. No model is called.

Run from the repository root using the command below. The JSON output contains inputs, computed observations, named checks, and `passed`. A failed expectation exits with status 1. Editing inputs can intentionally make those checks fail.

```sh
python3 learning-labs/05-traversal-inference/run.py
```

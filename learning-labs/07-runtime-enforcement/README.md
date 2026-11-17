# 07: A proposed action is not an admitted action

## Point and terms

A **precondition** is a condition required before execution. **Admission** decides whether the proposed call can proceed. A **postcondition** describes an expected result. An **effect** is a change to the environment.

This fixture supplies proposed requests directly, without a model. It tests whether a dispatcher blocks unsafe requests, not whether prompts cause a model to make them.

## Inputs

`inputs.json` contains an action contract, one request and a synthetic attributed approval. The request is structurally well formed. Its arguments alone do not establish authority.

```text
request: deploy LoginService to Production
    -> check exact arguments
    -> check approval evidence identity and source
    -> check current validity
    -> check service and environment scope
    -> only then mutate the local deployment state
```

## Prediction and run

Missing evidence, wrong environment, stale approval and missing attribution must produce no state change. Valid approval permits the change. An extra argument must be rejected.

```sh
python3 learning-labs/07-runtime-enforcement/run.py
```

The JSON output shows every request, approval, decision, dispatch flag and before/after state. `checks` must all be true; otherwise the script exits nonzero. A deliberately unguarded dispatcher is a negative control. It executes the same kind of supplied unsafe proposal. No empirical model failure is claimed.

## What this establishes and omits

The fixture establishes enforcement for these cases at this one dispatch path. The ontology supplies meanings such as service and scope. Python predicates enforce the actual conditions. A valid source identifier here is only fixture provenance; a production system must verify receipts and source authority. Concurrent writes, atomic backend checks, external authorization, irreversible deployment effects, idempotency and network failure are outside this demonstration. It is not an AppWorld result.

## Standards versus policy

The input document includes a [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation) contract. The runnable script deliberately uses a tiny handwritten checker for this exact contract, not a general JSON Schema implementation. JSON Schema describes structure; it does not independently establish current domain approval. Our freshness, attribution and scope predicates are application policy. An MCP-compatible schema would still need these checks at the executor.

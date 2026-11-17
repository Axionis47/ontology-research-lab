# 08: A fact changes, its dependent conclusions become stale

## Question

If an assignment is revoked after an agent prepares a plan, which conclusions must it recheck?

## Terms introduced

| Term | Exact meaning here |
| --- | --- |
| Observation | A source-attributed record from this fixture's world |
| Revision | An integer identifying the observed version of one record |
| Dependency | An explicit statement that one result used another result |
| Invalidation | Marking a result stale so execution cannot reuse it without checking |
| Recompute | Evaluate the rule again using the current observation |

## Inspect the input

Read `input.json`. Assignment17 is active at revision 1. Decision8 uses Assignment17; Plan3 uses Decision8. A display label uses an unrelated service record. The fixture then supplies revision 2, where Assignment17 is inactive. These are manufactured observations, not live API receipts.

```text
assignment17 → decision8 → plan3
service → display_name
```

## Predict before running

The original plan is permitted. Revocation makes Decision8 and Plan3 stale. The display label remains usable. Reading the fresh assignment does not restore authority because it is now inactive. The ontology stays at version 1 because the meanings did not change.

## Run

From the repository root:

```sh
python3 learning-labs/08-fact-invalidation/run.py
```

The script prints the original and updated record, transitive invalidation set, input hash, and seven named checks. It exits 0 only if all checks pass. The negative control is attempting to reuse the revision-1 plan after revision 2 arrives. This is denied.

## What computation ran?

`affected_by` repeatedly follows dependencies until no new dependent result is found. The execution check compares the recorded revision to the current revision. The fresh rule checks whether the assignment is still active. No language model reasons inside this fixture.

## Standard versus project policy

[W3C PROV-O](https://www.w3.org/TR/prov-o/) defines provenance vocabulary including derivation and invalidation. Our JSON names and transitive invalidation algorithm are a custom teaching implementation, not a PROV-O conformance implementation. Source attribution does not itself prove a source is truthful.

[HTTP If-Match](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.1) is a standard mechanism for conditional requests. Our integer check illustrates a similar precondition but is not an HTTP implementation. In a real system, a check outside an atomic backend write cannot eliminate the race between checking and acting.

## What this does not prove

It does not undo completed actions, invalidate hidden model reasoning, establish freshness through timestamps alone, or count as an AppWorld result. Only recorded dependencies are tracked. Missing dependencies would make this invalidation incomplete.

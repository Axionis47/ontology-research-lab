# Demonstrations: graph observations and changes

[Presentation](../README.md)

This page explains two existing evidence sets.
The first uses native AppWorld observations.
The second uses a synthetic approval task.
Their results remain separate.

## A. AppWorld observations populated the task graph

**Purpose:** Explain how observed application state became input to the accepted function.

**Starting conditions:** The task specified a genre and a minimum follower count.
The accepted function already contained the numeric filter.
Each episode used a fresh AppWorld world.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The adapter read artists through the AppWorld API. | The adapter collected pages of artist records. | The graph needed actual source records. |
| 2 | The adapter read the account's following relations. | The adapter identified artists that the account already followed. | The runtime needed the existing state before action. |
| 3 | The adapter built a scoped snapshot. | Each starting graph contained one account and 36 artists. | Records and relations belonged to that task's observations. |
| 4 | The accepted function applied the genre and numeric conditions. | The function selected the required artists. | Both conditions had to hold for each target. |
| 5 | The runtime dispatched the required follow actions. | AppWorld changed the corresponding following relations. | Selection alone did not change application state. |
| 6 | The adapter read the state again. | The runtime obtained the resulting snapshot and revision. | A successful API response alone did not establish the final task result. |
| 7 | Completion checks evaluated the new state. | The required relations existed and unrelated state passed preservation checks. | Success required both the target effect and preservation. |
| 8 | AppWorld's official evaluator evaluated the task. | All three subsequent tasks passed all five official checks. | Native success required the official result as well. |

### Logic of the follower-count value

A follow action also changes an artist's follower count.
The adapter stored a baseline-adjusted count.
The adjustment removed this account's own follow-count change from the selection value.
The raw API responses remained in the original records.

### Result

The accepted function used facts from fresh worlds.
The runtime obtained new observations after actions.
The successful episodes made no Qwen calls.

### Limits

The adapter obtained a complete initial snapshot.
The evidence does not compare this method with gradual graph population during execution.
The accepted function operated on observations supplied by trusted adapter code.
The result does not show Qwen independently building or maintaining a graph.
The graph records are part of the loop experiment.
They do not count as a separate set of native tasks.

### Evidence

- [Task bindings and starting graphs](../../runs/protocol/appworld-gemini-20261116/representation.json).
- [Subsequent native episode records](../../runs/protocol/appworld-gemini-20261116/clean-replay/episodes.json).
- [Native adapter implementation](../../appworld_runtime/inference.py).
- [Completion checks](../../react_runtime/completion.py).

## B. A graph change invalidated an action

**Purpose:** Determine whether the system blocks a stale proposal and obtains a new model response.

**Starting conditions:** The synthetic graph contained 53 facts at revision 7.
The task required a valid pair of approvers.
Vera qualified for Operations through a delegation.
Tao qualified for Security.
The ontology version remained `approval-complex-v1`.

The runtime required definition inspection and a current valid-panel computation.
A panel is a pair of people selected for the two approval roles.

### What happened

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | Gemini requested the eligibility definitions through `inspect_schema`. | The runtime returned the requested definitions. | The required rules had to be available before completion. |
| 2 | Gemini called `find_valid_panels`. | The computation returned a valid pair at revision 7. | The function evaluated the supplied rules against the current graph. |
| 3 | Gemini proposed Vera and Tao. | The initial eligibility check accepted the pair. No external action occurred. | The pair was valid under revision 7. |
| 4 | The fixture revoked Vera's delegation. | The graph advanced to revision 8. | A fact supporting Vera's authority had changed. |
| 5 | The runtime evaluated the old proposal before action. | The runtime rejected it with `VERSION_MISMATCH`. | The proposal referred to revision 7. |
| 6 | The runtime supplied the rejection and new state information to Gemini. | Gemini received evidence that the old result was no longer current. | Recovery required new evidence rather than reuse of the old answer. |
| 7 | Gemini called `find_valid_panels` again. | The computation found no valid pair at revision 8. | The changed graph no longer satisfied the panel requirements. |
| 8 | Gemini returned a null panel with revision 8. | The recovery checker accepted the answer. The task remained blocked. | No valid pair meant that approval could not proceed. |

The sequence used five Gemini calls.
Steps 4, 5, and 6 describe runtime operations between model calls.
The runtime made no external writes.

### Decision logic

1. A proposal uses a specific graph revision.
2. A source change can invalidate that proposal.
3. A proposal from an old revision cannot authorize the action.
4. A new computation must use the current revision.
5. If the computation finds no valid pair, the task must remain blocked.

The final null answer did not grant permission.
It correctly reported the absence of a valid pair in this complete fixture.

### Result

The runtime blocked the stale proposal.
Gemini used the rejection feedback to request a current computation.
The recovery result was correct.
The approval task did not complete.

### Limits

The fixture supplied the revocation.
Gemini did not discover an unseen source change.
The computation used hand-authored rules and functions.
One synthetic recovery does not establish general graph-change handling.
This experiment did not execute an AppWorld task.

### Evidence

- [Original five-call sequence](../../learning-labs/ontology-consumption-complex/combined-recovery/RESULTS.md).
- [Requests, responses, and runtime decisions](../../learning-labs/ontology-consumption-complex/combined-recovery/results/20261117T003010.669432Z/receipt.json).
- [Recorded starting conditions](../../learning-labs/ontology-consumption-complex/combined-recovery/results/20261117T003010.669432Z/manifest.json).

## What remains unproven

The current evidence does not establish a general graph writer.
It does not establish automatic resolution of conflicting sources.
It does not establish complete detection of every stale derived result.
It does not compare gradual population with an already populated graph.

The [model-access demonstrations](../04-model-consumption/README.md) explain how models used supplied graphs.
The [ten concept demonstrations](../02-ontology-concepts/README.md) isolate provenance and dependency rules.

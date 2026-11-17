# Graph reports: observation, execution, stale results, and recovery

[All experiment reports](../README.md) · [Full AppWorld repair loop](../01-improvement-loop/README.md)

This page follows two different runs. Part A explains the graph and action path inside the native Spotify experiment. Part B follows a synthetic approval task through a source change and five model calls.

A graph revision identifies one observed state. It changes when the facts change. An ontology version identifies the definitions used to interpret those facts. A revoked assignment changes a fact; it does not automatically change the meaning of Assignment.

## A. AppWorld observations populated the task graph

**Starting point:** The runtime already had the accepted artist-selection function with genre and numeric filters. A fresh AppWorld task specified the requested genre and follower threshold. This report describes those subsequent episodes, not an additional improvement experiment.

**1. The adapter read actual records.** It paginated spotify__search_artists and spotify__show_following_artists. The former supplied artist records; the latter supplied this account's existing following relationships. Repeated IDs, an invalid page shape, or exhausting the page budget could not count as complete observation.

**2. The adapter converted the responses into a scoped graph.** It created Account self, Artist records such as artist:14, and follows edges for observed memberships. Each starting graph in the recorded tasks had one account and 36 artists. A source snapshot hash identified its revision.

**3. It normalized fields used by the task.** Genre values were case-folded. It computed baseline_adjusted_follower_count because this account's own follow action increases the API's follower count:

~~~text
selection value =
  current API count
  - 1 if this account currently follows the artist
  + 1 if this account followed the artist at episode start
~~~

For example, an initially unfollowed artist with count 22 becomes count 23 after this account follows. The adjusted value remains 22. This preserves the original selection condition while retaining the raw source response.

**4. The accepted function selected IDs.** It looked up Artist records, applied the task's genre condition, and then applied its numeric predicates. Returning an ID did not itself follow the artist.

**5. The executor performed the effect.** For selected artists not already followed, the adapter prepared spotify__follow_artist calls with the artist_id. The runtime dispatched them through the AppWorld adapter.

**6. The adapter observed the result again.** New source records produced the after-state graph. The completion checker compared that state with the requested effect and preservation requirements.

**7. AppWorld evaluated the task.** The three subsequent episodes in the automatic run passed all five official checks each. They made zero Qwen calls because the accepted function handled them directly.

**What changed and what worked later:** The reusable function had been repaired in the [native improvement loop](../01-improvement-loop/README.md). This graph path supplied fresh facts to that function on each later task. It was not a new repair of graph-ingestion code.

**Limit:** The trusted adapter constructed a complete initial snapshot for one narrow Spotify task grammar. The run did not show a model inventing an ontology, resolving conflicting sources, or gradually building an arbitrary graph. These episodes are the same native episodes counted in the improvement report.

[Graph/task summaries](../../runs/protocol/appworld-gemini-20261116/representation.json) · [Subsequent episode outcomes](../../runs/protocol/appworld-gemini-20261116/clean-replay/episodes.json) · [Adapter implementation](../../appworld_runtime/inference.py) · [Completion checker](../../react_runtime/completion.py)

## B. A graph change invalidated an action

**Question:** What does the model do after the runtime tells it that a previously valid answer is stale?

This synthetic task required two different approvers for deployment d2: one Ops approver and one Security approver. The pair also had to belong to different home teams.

The starting graph had 53 records at revision 7. The ontology stayed at approval-complex-v1 throughout the run. Staging and Production are environment labels in these example records; no real deployment was connected.

**The starting authority paths were:**

~~~text
Iris's direct grant → delegation del-Vera → Vera, Ops, Platform team
Tao's direct grant → Tao, Security, Identity team
~~~

Both selected people had the required supporting records. Vera and Tao formed the only valid pair. Uma was another individually eligible Ops candidate, but belonged to Tao's team, so Uma and Tao could not form a valid pair.

The runtime exposed schema inspection, generic queries, traversal, a valid-pair function, and a pair checker. It required the model to inspect eligibility definitions and obtain a valid-pair computation at the current graph revision before finishing. Merely having an interface available did not mean the model used it.

### Call 1: request the definitions

Gemini returned:

~~~json
{"type":"call","name":"inspect_schema","arguments":{"names":["eligibility"]}}
~~~

Python looked up the requested definition and its dependencies, then returned the rules and their ontology version. No external service was called.

### Call 2: compute valid pairs from revision 7

Gemini returned:

~~~json
{"type":"call","name":"find_valid_panels","arguments":{"deployment_id":"d2","at":"2026-11-16"}}
~~~

The hand-written function checked each person's grants, delegations, dates, risk limits, certificates, denials, and team membership. It combined eligible people into pairs and checked the different-team rule.

It returned Vera and Tao, along with the supporting record IDs and graph_revision=7.

### Call 3: propose the valid pair

Gemini returned a finish proposal selecting Vera for Ops and Tao for Security. Its answer cited the rule IDs, supporting records, ontology version, and revision 7.

The initial gate confirmed that the pair was valid at revision 7. That check did not execute an approval.

### Runtime step: revoke the support before execution

The fixture then changed one fact: del-Vera became inactive. It advanced the graph to revision 8 while leaving the ontology unchanged.

The old proposal still claimed revision 7. The runtime rejected it with VERSION_MISMATCH. It returned the new revision, the changed record ID, and an explanation that Vera's delegation had been revoked before execution.

The original revision-7 snapshot remained in the accumulated context, but the new observation explicitly superseded it. The harness required a new computation against revision 8.

### Call 4: recompute from revision 8

Gemini requested find_valid_panels again with the same task arguments.

The function now returned an empty panels list at revision 8. Vera no longer had a valid delegation. Uma's shared-team conflict with Tao still applied. The runtime did not add a replacement candidate or relax the rule.

This is the step that establishes the new result over the complete fixture. Merely changing the version number on the old answer would not restore eligibility.

### Call 5: finish with no valid pair

Gemini returned panel=null and graph_revision=8, with the unchanged ontology version and required rule IDs.

The deterministic recovery checker confirmed that no valid pair remained and the previous proposal had been blocked. It recorded:

~~~text
status: RECOVERED_BLOCKED
task_status: BLOCKED_NO_VALID_PANEL
admitted: false
external_writes: 0
~~~

### What was recovered, and what was not repaired

The runtime blocked the stale proposal. The model used explicit rejection feedback to request a current computation and then reported the blocked task accurately.

No ontology, function, tool schema, or policy was patched. This was task-level recovery from changed evidence. The approval task did not complete, and no later successful deployment was measured in this experiment.

The five model calls are actual requests in the receipt. The mutation and rejection were runtime operations between calls 3 and 4. Gemini did not independently discover an unseen source change.

The rule implementations, dependency information, and revocation were supplied by the fixture. This one recovery does not establish complete stale-result detection or general recovery reliability.

[Full five-call report](../../learning-labs/ontology-consumption-complex/combined-recovery/RESULTS.md) · [Original requests, function results, and feedback](../../learning-labs/ontology-consumption-complex/combined-recovery/results/20261117T003010.669432Z/receipt.json) · [Frozen inputs and execution plan](../../learning-labs/ontology-consumption-complex/combined-recovery/results/20261117T003010.669432Z/manifest.json)

For a reusable function change followed by successful later native tasks, continue to the [AppWorld repair-loop report](../01-improvement-loop/README.md).

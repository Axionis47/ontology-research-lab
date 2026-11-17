# AppWorld report: failure, function repair, and successful later tasks

[All experiment reports](../README.md) · [Ten component experiments](../02-ontology-concepts/README.md)

**Recorded outcome:** The system repaired one reusable artist-selection function. A fresh automatic run began with a failed AppWorld task, obtained a Gemini diagnosis and a separate Gemini proposal, accepted the candidate after checks, and then completed three subsequent episodes successfully.

This report follows that automatic run first. The earlier run, including failed proposer calls and a manual validation retry, is documented afterward. Neither run changed model weights or added an ontology definition.

## What the task meant

The first task was AppWorld task **07b42fd_1**:

> Follow all the classical artists on Spotify that have at least 22 followers.

The environment was AppWorld's simulated Spotify application. A fresh world restores the task's starting application state, so a later execution cannot pass merely because an earlier execution already followed the artists.

The requirement has two conditions: the artist must have genre classical, and the follower count must be at least 22. The account must follow qualifying artists while preserving unrelated state.

The trusted adapter read the public task and actual API observations. It created a graph with one Account and 36 Artist records, plus the observed following relationships. The initial account followed no artists in these cases. Each task had its own scope and graph revision.

The task binding separated what to select from what to do:

~~~text
Select:
  entity type = Artist
  genre = classical
  baseline-adjusted follower count >= 22

Effect:
  ensure the current Account follows each selected Artist
~~~

A follow itself increments the follower count. The adapter's baseline-adjusted property removes this account's own change from the selection value, preserving the original threshold meaning. Raw API observations remain recorded.

[Task bindings and graph summary](../../runs/protocol/appworld-gemini-20261116/representation.json)

## What the harness actually ran

The harness is the controller around the models and application. It binds a task, records observations, executes a pinned program, handles failure, requests diagnosis and a proposal, evaluates that proposal, and controls activation.

| Component | Actual responsibility in this run |
| --- | --- |
| Trusted AppWorld adapter | Read the task and APIs, build the task graph, perform allowed effects, and read back state. |
| Existing program | Select artist IDs by running a composition of implemented operators. |
| Qwen actor | Attempt task recovery when the existing program could not safely complete the task. |
| Gemini diagnostic call | Examine the failed episode and identify supported defects. |
| Separate Gemini proposer call | Return one bounded candidate program change. |
| Deterministic comparison and release controller | Test the candidate and decide whether it could become active. |
| AppWorld official evaluator | Evaluate the final native task state. |

Qwen used the configured **qwen3:8b-q4_K_M** model. Both Gemini calls reported **gemini-3.8-flash** as the main model and **gemini-3.5-flash-lite** as the utility router.

The observed automatic sequence was:

~~~text
Bind first task and observe a fresh world
  → run the original selection program
  → reject its incorrect plan before dispatch
  → let Qwen attempt recovery
  → record failure
  → Gemini diagnoses the evidence
  → separate Gemini call proposes a function patch
  → compare parent and candidate
  → run structural checks and a fresh native validation
  → activate the accepted candidate
  → execute later tasks using the accepted program
  → read back state and run official evaluation
~~~

The program runs first in this implementation. Qwen is invoked on handoff; the successful later episodes did not require Qwen.

## 1. The original program dropped one task condition

The original direct function had two operations:

~~~text
0. lookup_entities: obtain Artist records
1. filter_property_categorical: keep genre=classical
return result 1
~~~

The numeric condition was present in the task binding, but the function never evaluated it. This is a missing computation, not a missing follower-count observation.

The seven classical artist records in the stored initial observation make the defect concrete:

| Artist | Initial follower-count selection value | Should be selected for at least 22? |
| --- | ---: | --- |
| Zoe Mitchell | 16 | No |
| Mia Sullivan | 16 | No |
| Grace Harrison | 22 | Yes |
| Oceanic Odyssey | 18 | No |
| Carter Knight | 18 | No |
| Evelyn Rose | 15 | No |
| Felix Blackwood | 18 | No |

The original function selected all seven because each matched the genre. Only Grace Harrison also matched the threshold. The source case is identified by hash **3858738db4833e6ac75b67e73a931e6cec8ecd9b47f1baf45fb8ee117ea28471** in the [representation record](../../runs/protocol/appworld-gemini-20261116/representation.json). The [diagnosis](../../runs/protocol/appworld-gemini-20261116/clean-replay/diagnosis.json) records the seven-versus-one defect and its evidence references.

## 2. The runtime rejected the plan, and Qwen recovery failed

Before dispatching follows, deterministic preflight evaluated the proposed change against the original task contract. Following six below-threshold artists would violate preservation of unrelated state, so the runtime rejected the plan before those effects occurred.

It then handed the task to Qwen with the current evidence and original conditions. Qwen made three model calls but failed to produce valid tool-discovery arguments. The recorded errors included an empty strategy object and a limit of 100 where the schema maximum was 10.

The episode ended with **NO_PROGRESS**, native success=false, and zero dispatched actor tool attempts. Observations had already been obtained by the trusted adapter; zero actor tool attempts does not mean zero API activity in task setup.

**This task stayed failed.** Learning afterward did not retroactively turn the baseline episode into a success.

[Baseline episode, trace audit, and learning result](../../runs/protocol/appworld-gemini-20261116/clean-replay/episodes.json)

## 3. Gemini diagnosed two separate problems

The diagnostic call received the original requirements, parent program, relevant observations, original model/tool evidence, and permitted evaluation feedback.

It returned two supported findings:

| Finding | Why it mattered | What happened to it |
| --- | --- | --- |
| The direct function omitted numeric filtering. | It selected artists outside the requested threshold. | Routed to the separate proposer. |
| Qwen supplied invalid discovery arguments. | Recovery stalled after validation errors. | Recorded as unresolved. |

The diagnosis was checked for valid evidence references. Gemini's opinion did not establish native success or authorize activation.

[Original diagnostic assessment](../../runs/protocol/appworld-gemini-20261116/clean-replay/diagnosis.json)

## 4. A separate Gemini call authored the exact function repair

The proposer received the validated function finding and a bounded editable surface. It added one existing operator to the direct function and changed the return index to use that operator's result.

**Before:**

~~~json
{
  "nodes": [
    {"op":"lookup_entities","type":"selector.entity_type"},
    {"input":0,"op":"filter_property_categorical","where":"selector.where"}
  ],
  "return":1
}
~~~

**After:**

~~~json
{
  "nodes": [
    {"op":"lookup_entities","type":"selector.entity_type"},
    {"input":0,"op":"filter_property_categorical","where":"selector.where"},
    {"input":1,"op":"filter_numeric","predicates":"selector.numeric"}
  ],
  "return":2
}
~~~

The numeric-filter implementation already existed. The repair connected it into the function. Its predicates come from each task's selector, so the program can apply 22, 23, or 21 without hardcoding a task or artist.

The related function stayed unchanged. No new class, property, API, evaluator rule, or model weight was introduced.

The program format's version field remained 1. The content-addressed package identity changed from **995d9f3c…** to **292f3a14…**, allowing episodes to record exactly which program they used.

[Original proposer response](../../runs/protocol/appworld-gemini-20261116/clean-replay/proposer-calls.json) · [Full parent and candidate programs](../../runs/protocol/appworld-gemini-20261116/accepted-program.json)

## 5. The runtime tested the candidate before activating it

At this point the fresh archive contained only the first task. The system had not yet run tasks _2 or _3 in this archive.

| Check | Observed result | What it established |
| --- | --- | --- |
| Parent versus candidate on the retained case | Parent FALSE; candidate TRUE | The candidate fixed the reproduced selection failure. |
| Preservation comparison | No recorded regression or lost requirement | Previously true checks on the retained case remained true. |
| Generated structural challenges | 16/16 TRUE | The candidate handled the frozen variations tested by the local evaluator. These were synthetic checks. |
| Fresh native execution of the retained case | TRUE, fallback disabled | The candidate completed the native task without Qwen rescuing it. |
| Activation | Candidate became active | Subsequent episodes could use the accepted package. |

The local comparison and the fresh native execution are separate checks. A passing simulation alone was insufficient for activation. The structural tests also do not count as sixteen AppWorld tasks.

[Complete acceptance receipt](../../runs/protocol/appworld-gemini-20261116/clean-replay/acceptance.json)

## 6. Later tasks used the repaired function and passed

Each subsequent episode started in a fresh AppWorld world, rebuilt its graph from actual observations, and pinned the accepted program. The reusable function persisted; instance facts were obtained again.

The program selected artist IDs, the executor issued the follow calls, the adapter read back the resulting state, and the official evaluator checked the native outcome.

| Subsequent order | Task and requirement | Official outcome | Qwen calls | Further repair |
| --- | --- | --- | ---: | --- |
| 1 | 07b42fd_2: EDM, at least 23 followers | Passed, 5/5 checks | 0 | None; IDLE |
| 2 | 07b42fd_3: Reggae, at least 21 followers | Passed, 5/5 checks | 0 | None; IDLE |
| 3 | 07b42fd_1: Classical, at least 22 followers | Passed, 5/5 checks | 0 | None; IDLE |

IDLE means the learning controller found no reproduced program failure requiring another proposal. It does not mean the unresolved Qwen error was repaired.

The [final automatic-run record](../../runs/protocol/appworld-gemini-20261116/clean-replay/result.json) records one proposer call, three subsequent task passes, no manual resume, unchanged protected source hashes, and a passing archive-integrity check. [Episode-by-episode evidence](../../runs/protocol/appworld-gemini-20261116/clean-replay/episodes.json) retains the failed starting episode as well.

## 7. What happened in the earlier run

The automatic run above followed an earlier experiment with operational failures and an explicit validation retry. These histories must remain distinguishable.

1. The earlier experiment collected three native baselines before learning. All failed, with ten total Qwen calls.
2. Gemini diagnosed the function failure and the separate actor argument errors.
3. Seven proposer calls failed with INVALID_STREAM while the CLI integration was being corrected. These were failed calls, not useful candidate proposals.
4. A later candidate reached native validation. Two cases passed, but one result was UNKNOWN because an AppWorld session could not start. Activation was withheld.
5. A duplicate proposal was rejected.
6. An explicit validation-only retry tested the stored candidate in three fresh worlds. All passed, and the runtime activated it. Proposal spending was not reset.
7. Three fresh follow-up episodes then passed all five official checks per task. The next learning check returned IDLE.

| Task | Earlier baseline | Follow-up after validated repair |
| --- | --- | --- |
| 07b42fd_1 | Failed | Passed, 5/5 official checks |
| 07b42fd_2 | Failed | Passed, 5/5 official checks |
| 07b42fd_3 | Failed | Passed, 5/5 official checks |

The later automatic run started with a new archive and the original seed, with no accepted program imported. It reproduced the diagnosis/proposal/acceptance sequence without the manual validation retry.

[Earlier final result](../../runs/protocol/appworld-gemini-20261116/protocol-result.json) · [Earlier episode records](../../runs/protocol/appworld-gemini-20261116/episodes.json) · [Validation-only retry](../../runs/protocol/appworld-gemini-20261116/validation-retry.json) · [Automatic-run starting manifest](../../runs/protocol/appworld-gemini-20261116/clean-replay/manifest.json)

## What was repaired, and what remains open

| Item | Status and author |
| --- | --- |
| Missing numeric filter in the reusable direct function | Repaired by a separate Gemini proposer call, then accepted by deterministic and native checks. |
| CLI authentication/request handling | Operational corrections documented in the setup record. These were not learned ontology repairs. |
| Qwen's invalid discovery arguments | Unresolved. Later successful tasks avoided this recovery path. |
| Ontology definitions | No definition change in this experiment. |
| Storage-layer role-based access control | Not implemented or tested by this experiment. |
| General task-conditioned ontology construction | Not demonstrated by the narrow adapter. |

All three native tasks were previously exposed training variants of one Spotify family. Later-task success demonstrates reuse within that scope; it is not a held-out benchmark or a general transfer claim.

This is not evidence that Gemini improved Qwen's reasoning. It improved an executable function that the runtime could use without invoking Qwen on these later tasks. The accepted composition also matched an older search-produced composition, but the current run retained a new Gemini-authored proposal and started without importing that prior program.

The full native source data and runtime databases are local. The publication includes selected reports and receipts; some hashes in those receipts identify artifacts outside the published subset.

[CLI correction history](../../MODEL_SETUP.md#working-cli-repair-november-16-2026) · [Measured-results history](../../docs/system/20-live-acceptance.md) · [Final audit of the earlier experiment](../../runs/protocol/appworld-gemini-20261116/final-audit.json)

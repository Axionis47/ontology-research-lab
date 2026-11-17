# Demonstration: the AppWorld improvement loop

[Presentation](../README.md)

## Purpose

Determine whether a failed task can produce a reusable function change.
Determine whether that change helps later tasks.

**Evidence type:** Native AppWorld.
**Result:** Three tasks failed before the change.
All three passed after the change.

## Starting conditions

The task required the account to follow artists with a specified genre and minimum follower count.

| Task | Genre | Minimum followers |
| --- | --- | ---: |
| `07b42fd_1` | Classical | 22 |
| `07b42fd_2` | EDM | 23 |
| `07b42fd_3` | Reggae | 21 |

The adapter obtained observations from each fresh AppWorld world.
Each starting graph contained one account and 36 artists.

The original function applied the genre condition.
It did not apply the follower-count condition.

Qwen was the task actor.
Gemini was the diagnostic judge.
A separate Gemini call was the improvement proposer.
The runtime controlled actions and candidate acceptance.

## Run 1: what happened

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The adapter read the task's artists and following relations. | The runtime obtained a graph for that task's world. | Selection requires observations from the current world. |
| 2 | The runtime applied the original function. | The proposed selection included artists below the required threshold. | The function applied only the genre condition. |
| 3 | The runtime evaluated the proposed effects before dispatch. | The runtime rejected the plan and passed control to Qwen. | The plan would change records outside the permitted target set. |
| 4 | Qwen attempted recovery. | Invalid discovery arguments prevented progress. All three baseline tasks failed. | A rejected tool request cannot produce the required action. |
| 5 | Gemini received the recorded evidence. | Gemini identified a missing numeric filter and separate actor argument errors. | A function defect and an actor error require separate findings. |
| 6 | A separate Gemini call proposed a candidate. | The candidate added the existing numeric-filter operator. | The selection must satisfy both task conditions. |
| 7 | The runtime compared the parent and candidate. | The candidate passed the structural checks. Native validation produced two passes and one unknown result. | An incomplete native result cannot support activation. |
| 8 | The runtime withheld activation. | The original program remained active. A later duplicate proposal was rejected. | A candidate needs complete passing evidence. |
| 9 | A validation-only retry evaluated the stored candidate in fresh worlds. | All three native cases passed. The runtime activated the candidate. | The retry supplied the missing validation evidence. |
| 10 | The runtime used the accepted function for subsequent tasks. | All three tasks passed all five official checks. | The function applied each task's own genre and threshold. |
| 11 | The controller evaluated whether another function change was needed. | The controller returned `IDLE`. | The accepted function already handled the recorded cases. |

The retry did not reset proposal spending.
The original unknown result remains in the records.
The [validation receipt](../../runs/protocol/appworld-gemini-20261116/validation-retry.json) links the stored candidate to the retry.

## The function logic

**Before the change:** Find artists. Apply the genre condition. Return the selected artists.

**After the change:** Find artists. Apply the genre condition. Apply the numeric condition. Return the selected artists.

An artist must satisfy both conditions.
The function obtains their values from the task binding.
The candidate contains no fixed artist identifiers or task answers.
The candidate does not change an ontology definition.

The runtime performs the follow action.
The adapter reads the resulting state.
The completion checks compare that state with the original requirements.

[Original and accepted functions](../../runs/protocol/appworld-gemini-20261116/accepted-program.json).

## Run 2: automatic repeat from the original program

This run used a new archive.
It did not import the previously accepted program.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The controller ran task `_1` with the original function and Qwen recovery. | The task failed after three Qwen calls. | The original defects remained reproducible. |
| 2 | Gemini diagnosed the saved evidence. | The diagnosis identified a supported function defect. | A proposal required a valid diagnosis. |
| 3 | A separate Gemini call proposed the function change. | One proposer call returned the candidate. | The proposer had a bounded edit target. |
| 4 | The runtime tested the candidate. | The retained native case and 16 structural challenges passed. | At this point, only task `_1` was in this archive's retained suite. |
| 5 | The runtime activated the candidate. | Later episodes used the accepted version. | Activation applied only after the checks passed. |
| 6 | The controller ran tasks `_2`, `_3`, and `_1`. | All three passed. Each passed all five official checks. | The same function used different task bindings. |
| 7 | The controller evaluated further work. | Each subsequent episode needed no new patch. | The accepted function met the recorded requirements. |

The repeat required no manual resume or validation retry.
The successful subsequent episodes made no Qwen calls.

## Result and limits

| What the evidence supports | Limit |
| --- | --- |
| A separate Gemini proposal produced a useful function change. | The model did not learn new weights. |
| The runtime accepted the change after required checks. | Those checks cover the recorded cases and structural challenges. |
| Later tasks reused the function successfully. | All tasks came from one previously exposed Spotify family. |
| The fresh repeat completed automatically. | One repeat does not establish a general reliability rate. |
| The corrected function avoided Qwen recovery on these tasks. | Qwen's argument errors remain unresolved. |

Seven earlier proposer calls failed with `INVALID_STREAM`.
Those calls remain recorded.
The CLI required operational corrections before the clean repeat.

## Original evidence

- [Run 1 task outcomes](../../runs/protocol/appworld-gemini-20261116/protocol-result.json).
- [Run 1 episode records](../../runs/protocol/appworld-gemini-20261116/episodes.json).
- [Run 2 starting conditions](../../runs/protocol/appworld-gemini-20261116/clean-replay/manifest.json).
- [Run 2 diagnosis](../../runs/protocol/appworld-gemini-20261116/clean-replay/diagnosis.json).
- [Run 2 proposer response](../../runs/protocol/appworld-gemini-20261116/clean-replay/proposer-calls.json).
- [Run 2 acceptance checks](../../runs/protocol/appworld-gemini-20261116/clean-replay/acceptance.json).
- [Run 2 final result](../../runs/protocol/appworld-gemini-20261116/clean-replay/result.json).
- [Archive integrity and source checks](../../runs/protocol/appworld-gemini-20261116/final-audit.json).
- [CLI corrections](../../MODEL_SETUP.md#working-cli-repair-november-16-2026).

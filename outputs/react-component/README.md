# ReAct component evidence

Saved November 13, 2026. These files and the original run directories persist independently of chat and model-context compaction.

- Component checks: **18 passed, zero failures or errors**. [Validation record](validation.json), [test output](tests.txt).
- Live configured Ollama CLI, short fixture: **verified success**, 4 steps and 2 tool attempts. [Judge packet](../../runs/react/246510a6-0f3a-4ed6-bfd1-6c5ae5cb2ba1/exports/717a9e2b-d1cc-412c-baa6-b0ac19542139/judge_packet.json).
- Deterministic compaction fixture using the final verifier: **verified success**, 7 steps and 4 compactions. [Judge packet](../../runs/react/9f04939c-8901-46c9-b269-c97f61c3fb60/exports/621bca0c-68c6-40d1-b927-9016ab59cb07/judge_packet.json).
- Live Ollama compaction fixture: **task failed at its step limit**, 3 compactions; original evidence remained available and the trace audit passed. [Failure case with original receipts](live-compaction-case.md).
- All development runs, including earlier format failures: [run index](run-index.json). Each run has its own source/config snapshots. Attempts used different engineering revisions and sometimes different budgets, so these are not paired comparative results.

The early live runs exposed wrapped actions, omitted required fields and incorrectly typed finish references. Engineering changes clarified the actor's protocol and made validation feedback specific. These changes did not update model weights, implement automatic repair or establish a benchmark improvement.

The failed long fixture is retained for the next judge component. The complete trace records what was sent, returned, admitted, executed, compacted, verified and rejected. A complete trace is not a successful task.

Implemented boundaries and commands: [first component](../../docs/system/13-react-component.md). Audit and bounded original-evidence reads: [judge evidence contract](../../docs/system/14-judge-evidence.md). Full kernel, automated judge, repair and benchmark adapter remain later components. No benchmark score is reported.

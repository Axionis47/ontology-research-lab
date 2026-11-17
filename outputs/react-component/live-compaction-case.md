# Recorded live compaction failure

Engineering inspection of saved execution, not an automated judge verdict. Provider: the existing Ollama CLI and configured `qwen3:8b-q4_K_M`. [Complete judge packet](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/exports/0b94db92-2da4-4fbc-860e-6dd5607a9c0a/judge_packet.json).

The task required reading r1 through r5, then rereading the original r1 proof and returning it. The episode ended `BUDGET_EXHAUSTED` after 12 steps and 9 tool attempts. Its trace audit passes. Context compaction occurred before steps 5, 9, 11; original r1 evidence remained readable afterwards.

Observed record IDs: r1, r2, r3. Unread required IDs: r4, r5.

| Step | Proposed action | Evidence |
| --- | --- | --- |
| 1 | `get_record({"record_id": "r1"})` | [original proposal](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0001-0b47b668-1fa9-4942-99b9-9a6dbd811c4c.txt) |
| 2 | `read_output({"json_pointer": "/proof", "output_id": "1afa4816-50fa-4347-b7eb-097c58f20d6f"})` | [original proposal](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0002-8fb470fe-cead-43fc-a209-87fa926c949a.txt) |
| 3 | `finish(proof-for-r1)` | [original proposal](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0003-a49ba7c2-76bb-4038-83aa-c4f2eeabb2d3.txt) |
| 4 | `get_record({"record_id": "r2"})` | [original proposal](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0004-fe820a14-b311-413c-a10c-4b8119343aa1.txt) |
| 5 | `read_output({"json_pointer": "/proof", "output_id": "1afa4816-50fa-4347-b7eb-097c58f20d6f"})` | [original proposal](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0005-6e68ddef-a47c-485d-9dac-72bd619575f0.txt) |
| 6 | `read_output({"json_pointer": "/proof", "output_id": "1afa4816-50fa-4347-b7eb-097c58f20d6f"})` | [original proposal](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0006-41edc756-6274-4580-95a9-ef2ea7730e80.txt) |
| 7 | `finish(proof-for-r1)` | [original proposal](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0007-570fe306-f3f0-4e0c-b455-88a8a6a3249f.txt) |
| 8 | `get_record({"record_id": "r3"})` | [original proposal](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0008-df2313dc-be7e-425c-8e6b-e5ad73027b01.txt) |
| 9 | `read_output({"json_pointer": "/proof", "output_id": "1afa4816-50fa-4347-b7eb-097c58f20d6f"})` | [original proposal](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0009-ba641b82-4173-4c59-86ef-1ee7d2086cf8.txt) |
| 10 | `read_output({"json_pointer": "/proof", "output_id": "1afa4816-50fa-4347-b7eb-097c58f20d6f"})` | [original proposal](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0010-f735bc16-658e-4b63-98fd-fad008cd3739.txt) |
| 11 | `finish(proof-for-r1)` | [original proposal](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0011-e6c48ecd-11ce-45b3-a798-3fb6848abec0.txt) |
| 12 | `read_output({"json_pointer": "/proof", "output_id": "1afa4816-50fa-4347-b7eb-097c58f20d6f"})` | [original proposal](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0012-d83a058e-5d3d-4caf-96f1-d227b8bed318.txt) |

Rejected completion claims:

- Step 3: Still need records: ['r2', 'r3', 'r4', 'r5'] ([verification receipt](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0003-cb3e2111-77ff-4c14-a1c6-389a1f50f771.txt)).
- Step 7: Still need records: ['r3', 'r4', 'r5'] ([verification receipt](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0007-0f135411-996b-403d-8189-e4f3002db9cd.txt)).
- Step 11: Still need records: ['r4', 'r5'] ([verification receipt](../../runs/react/feda649c-b3a3-4072-9601-b80da489287f/observations/step-0011-111cca55-bd38-42cf-9f44-d44a06c3024f.txt)).

The first premature finish happened at step 3, before the first compaction. This rules out compaction as the sole cause of all premature finishes in this episode. Later original-output reads succeeded, so the trace does not support an explanation that the original r1 output was deleted.

The mechanism behind the model's repeated focus on the proof remains a hypothesis. A later judge should inspect the actual inputs before steps 3, 7 and 11, the verifier feedback, and both sides of each compaction. It must distinguish goal-following failure, insufficiently persistent progress feedback and context-packing effects. A proposed progress-feedback change would need a distinguishing test and preserving checks before any benchmark comparison. No improvement claim follows from this single development fixture.

Use the indexed evidence commands in [the judge evidence contract](../../docs/system/14-judge-evidence.md). Each read records exact source hashes, coverage and returned content separately from this episode.

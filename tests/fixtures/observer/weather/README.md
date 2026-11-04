# Genuine weather replay fixture

This portable subset contains 16 actual historical runs and 223 recorded events
from weather task `064d950af7a04b3e823a103a6ce8c6b2`. It includes the failed first
construction attempt, two candidate kernels with their recorded parent link,
and the Helsinki inference with a separate saved evaluator result. It contains
no fabricated responses and makes no model or MCP requests during replay.

`manifest.json` records original source hashes, exported artifact hashes,
redacted fields, rewritten references, omitted provider diagnostics, and exact
fixture file checksums. Sixty-eight artifacts retain their original bytes and
hashes. Other artifacts are explicit sanitized derivatives. Their new IDs must
not be presented as the original artifact IDs. The failed attempt's actual
reasoner schema is wrapped in a portable artifact with its source hash recorded.
Provider request bodies, raw stdout/stderr, credential values, and machine paths
are excluded or redacted. Private project documents are not included.

The checkpoint subset preserves actual primitive initial graph states for
inspection. It is replay evidence, not a resumable worker checkpoint export.
Only the original empty and populated graph snapshots are available; selection
highlights do not represent additional graph mutations.

Use `Observer` directly for read-only projection tests. Before starting the API,
copy this directory into a temporary workspace because application startup may
migrate the database. Never run the application against this checked-in folder.
The copied campaign remains historical evidence and must not be resumed for
live execution. New tasks use fresh connector configuration and runs.

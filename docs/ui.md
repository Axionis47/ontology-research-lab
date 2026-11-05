# Local observation workspace

Build the separate frontend package and launch the loopback application:

```sh
npm --prefix frontend ci --ignore-scripts
npm --prefix frontend run build
uv run --locked oak serve
```

The server uses `.local` by default; `oak serve --root PATH --port 8501` selects another server-owned workspace. It serves React and `/api/v1` from one origin. Vite development uses `npm --prefix frontend run dev` with its API proxy. The root Gemini CLI package and pin remain separate.

## Screens

Setup freezes task scope, starting ReAct instructions, representative cases and their partitions, selected MCP tools, and supported execution limits. Discovery only initializes a connection and lists actual tool contracts. Tool selection authorizes the read-only surface. Public Streamable HTTP and local stdio are supported; HTTP authentication is deferred. Start construction submits one current backend construction round with its existing bounded repairs.

Construction displays sampled cases, actual stages, failed attempts, schema and function definitions, exact declaration differences, and recorded parent relationships. Logical ontology checks, function probes, task assessments, and regressions stay separate. It does not claim automatic outer refinement or task correctness from HermiT alone.

Inference pins an exact eligible immutable kernel. New questions remain run-local and do not enter curated pools. The trajectory and graph share a selection, with public decision summaries and actual operator evidence. The answer is separate from independent assessment. Unknown checks remain Not checked. Existing corpus runs remain inspectable while corpus creation and execution stay in the backend and CLI.

Replay and Reset are viewer operations. Playback uses a labeled viewing pace, not claimed execution timing. The replay event list is fixed when opened. Reset returns to its first event and clears inspection selection. Graph projections default to 80 nodes and 240 edges and display omitted totals. Filtering highlights records rather than deleting them from a snapshot. Missing evidence stays missing.

## Contracts and execution ownership

The authoritative response and request models are `oak.api_contracts`. OpenAPI is exposed at `/api/v1/openapi.json`; `npm --prefix frontend run types:generate` derives TypeScript and `types:check` checks drift. See the [generated code reference](reference/runtime.md), rather than a second hand-maintained contract definition.

Read routes and SSE use `oak.observer` over saved evidence. They do not call models or MCP services, start workers, or reconcile jobs. The server lifecycle owns periodic worker reconciliation. Mutations require a local session token, trusted Host/Origin, and execution submissions require an idempotency key. Detached workers own paid execution, independent of HTTP connections. Interrupted workers are never automatically retried across uncertain external dispatches.

SQLite migration is additive and first backs up an existing catalog. Original artifacts and hashes are unchanged. Redacted presentations identify both their original artifact and a distinct projection digest. The budget includes outstanding unknown reservations and is an estimate, not an invoice.

## Verification

API tests use actual storage and retained artifacts. Browser tests run against the actual API without route mocks. Portable weather fixtures include reviewed provenance; richer Coffee/USGS checks use local retained runs when available. Live verification and residual limitations are recorded in the work plan and local receipts. Neither viewing history nor running the ordinary browser inspection suite dispatches paid work.

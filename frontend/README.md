# OaK observation interface

React consumes the versioned local API. Python remains authoritative for tasks,
workers, immutable kernels, ontology checks, artifacts, and spending.

From this directory:

```sh
npm ci
npm run types:generate
npm run build
```

From the project root, `oak serve` serves the built interface and API at
`http://127.0.0.1:8501`. During development, run `oak serve` and `npm run dev` in
separate terminals. Vite proxies `/api`; set `OAK_API_URL` when using another port.

API types are generated from `oak.api.create_app().openapi()` without opening the
workspace or launching a worker. `npm run types:check` detects contract drift.
Use `OAK_OPENAPI_URL` to generate against an already running API if necessary.

`npm run test:browser` starts the actual API on loopback port 8502 using a temporary
copy of the reviewed public weather evidence in `tests/fixtures/observer/weather`.
The fixture source remains unchanged. The server stops and the temporary copy is
removed after testing. Build the frontend first. The browser suite never intercepts
API requests or starts paid execution.

To check a running full local workspace, use:

```sh
OAK_TEST_URL=http://127.0.0.1:8501 npm run test:browser
```

`OAK_BASE_URL` is accepted as an alias. Evidence checks skip explicitly when their
genuine retained run is unavailable. Rich Coffee and USGS checks use local retained
artifacts and are skipped by the portable weather suite.

`node scripts/capture-preview.mjs` captures the actual setup, construction, and
Helsinki inference screens at three viewport sizes, plus dark appearance, under
`/tmp`. It requires the genuine retained weather history.

Replay freezes the currently loaded event sequence. Playback advances at a
labeled viewer pace, independent of execution timing. Reset clears viewer state.
Neither control sends a mutation or calls a service. Unknown event categories
render as generic evidence. New questions pin the selected eligible kernel and
do not enter curated construction or evaluation pools.

The `components/ui` source uses the shadcn/ui composition pattern with Radix
primitives and local design tokens. No schema or graph editing is exposed.

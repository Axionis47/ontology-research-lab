# MCP onboarding and task evidence

This user-requested extension starts with real configured MCP servers, a starter prompt, and a declared request pool. It does not require a corpus containing the answers. The shared engine obtains evidence through actual tool calls. The current focused slice is read-only and exposed through the CLI.

## Run the small weather surface

Run commands from the repository root. The upstream package and source integrity pins are recorded in `data/sources/weather-source.lock.json`. Install the reviewed server locally, then run the free server preflight. The script establishes nonsecret weather settings, verifies installed upstream source, and records real discovery and forecast receipts.

```sh
npm install --prefix .local/weather-mcp --ignore-scripts --no-audit --no-fund @dangahagan/weather-mcp@1.35.7
uv run --locked python scripts/verify_mcp_slice.py preflight
```

For separate CLI processes, supply the same environment configuration used at onboarding:

```sh
export OAK_WEATHER_ENABLED_TOOLS=get_forecast,search_location
export OAK_WEATHER_UNITS=metric
export OAK_WEATHER_ANALYTICS=false
export OAK_WEATHER_LIGHTNING_PREWARM=false
export OAK_WEATHER_DOTENV_PATH="$PWD/.local/weather-mcp/no-env-file"
uv run --locked oak mcp-onboard config/weather-surface.json
uv run --locked oak mcp-run SURFACE_ID construction-01
uv run --locked oak mcp-construct SURFACE_ID
uv run --locked oak mcp-run SURFACE_ID development-01 --kernel-id KERNEL_ID
uv run --locked python scripts/verify_mcp_slice.py evaluate --episode-id EPISODE_ID
uv run --locked oak artifact EPISODE_ID
```

Use `UV_CACHE_DIR=.local/uv-cache` and `UV_PYTHON_INSTALL_DIR=.tools/python` in a restricted workspace, as documented in stack setup. IDs are returned by the commands, not handwritten configuration constants. Do not run final held-out requests while refining artifacts or prompts.

## Inspect what happened

Onboarding records the actual server identities, capability schemas, configuration fingerprints, and failures. An episode records its initial context, base/runtime prompts, selected history, model decisions, actual MCP receipts, graph versions, function execution, and completion claim. Artifacts are immutable and hash-verified; `oak artifact` reads them. Model costs and pending reservations remain in the existing global ledger.

Construction records the seeded sample before collecting its episodes. It uses their actual decisions, calls, and failure evidence, drafts S, runs real HermiT, extracts acquired evidence, composes F, and probes those functions through actual calls. Acquisition results include typed entity groups from that response so functions can compute without mixing unrelated graph records. A candidate is not an independently scored success. Run the adapter evaluator against each episode's genuine receipts to establish that separate result.

History begins empty. The first slice ranks verified construction histories by lexical overlap and omits their answer values. It exposes the complete small authorized catalog; it does not use a per-query reference tool sequence. Missing semantics, unsupported operations, incomplete results, and source changes remain visible.

## Current limits

The live weather adapter tests three-day daily forecast questions. Its inputs are authored; observations are real. It evaluates displayed service values, not meteorological forecast accuracy. Existing pure-function replay remains supported. A live rerun obtains new observations and may legitimately return a different value.

The focused slice does not implement semantic history ranking, a workflow compiler, mutating MCP calls, automatic task-score-driven refinement or kernel promotion, or robust resumable MCP dispatch. Checkpoints preserve stage evidence, but a failed new episode should be restarted explicitly; saved outputs must not be passed off as fresh execution. Streamable HTTP support requires a separate real-server verification. Source drift with unchanged interface bytes cannot be ruled out by a contract hash. The function language also rejects unsupported JSON Schema constructs explicitly rather than promising compatibility with every possible MCP schema.

Each acquired response is extracted and validated before merging into G. Schemas must therefore permit independently observed fragments. Required cross-response fields or edges are not yet supported as deferred obligations. Logical validity and function execution do not establish that the agent satisfied all public task requirements.

See the generated API reference for the authoritative `TaskSurface`, `ServerConfig`, function, and runtime contracts.

The [verification report](verification/mcp-slice.md) records the real pilot, including a candidate that passed logical/probe checks but failed its new task, and the subsequent frozen candidate's development and held-out results.

# OaK

A task-conditioned ontology engine implementing construction and frozen execution from [Toward Effective and Reliable LLM Agents via Dynamic Ontology](https://arxiv.org/abs/2608.22974v1), with a live MCP extension.

Start with task requests, a starter prompt, and real MCP capabilities. Collect actual episodes, construct a schema and executable functions, validate through OWL/HermiT, and acquire fresh evidence during frozen inference. Corpus tasks and the local schema/graph/function inspector are also supported. The project refines external artifacts, not model weights.

## Run locally

Use uv 0.12.0 and Node.js. The current Java installer is pinned for macOS ARM64.

```sh
npm ci --ignore-scripts
uv sync --locked
uv run --locked python scripts/setup_java.py
uv run --locked python scripts/verify_environment.py
npm --prefix frontend ci --ignore-scripts
npm --prefix frontend run build
uv run --locked oak serve
```

Open [the local auditor](http://127.0.0.1:8501). Model execution requires a configured GCP project and application-default credentials. Gemini CLI runs with native tool execution disabled. Model configuration and spending limits are in `config/runtime.json`; credentials and run artifacts stay local.

The three screens are **Setup**, **Construction**, and **Inference**. Setup connects public Streamable HTTP MCP servers or local stdio servers, lets you inspect actual tool contracts and choose read-only capabilities, and saves immutable task inputs. Construction shows the current single construction round, sampled cases, schema/functions, and separate checks. Inference pins an exact eligible kernel and displays its saved trajectory beside the graph. Replay and Reset change only the viewer. A completed run and an independent task assessment are separate outcomes.

Existing Coffee and USGS runs remain inspectable. Corpus execution, revision operations, and the MCP commands remain available through the backend and CLI. HTTP authentication, automatic outer refinement, and manual schema editing are outside this release.

MCP construction uses separate requirement-analysis, schema, extraction, and function-composition prompts. Each run saves their exact text and hashes. Literal sampled requests and public requirements receive stable identifiers; the backend rejects omitted requirements, unknown references, and missing or explicitly unsupported function mappings before probing a candidate. These are declaration checks, not proof of semantic coverage or task success. Function probes and independent task assessments remain separate evidence. Task scope and representative cases still define what construction is expected to cover.

For frontend development, run `oak serve` and `npm --prefix frontend run dev` in separate terminals. Vite proxies `/api` to the loopback backend. The production server serves `frontend/dist` and `/api/v1` from the same origin. Keep the server bound to loopback.

MCP onboarding, construction, and inference also use the CLI:

```sh
uv run --locked oak --help
npm install --prefix .local/weather-mcp --ignore-scripts --no-audit --no-fund @dangahagan/weather-mcp@1.35.7
uv run --locked python scripts/verify_mcp_slice.py preflight
```

The preflight performs real discovery and acquisition without a model call. `config/weather-surface.json` defines the small authored pilot; weather-specific evaluation stays in its task adapter. Generic runtime code lives in `src/oak/bootstrap.py`, `src/oak/mcp_bridge.py`, and `src/oak/task_context.py`.

## Verification

```sh
uv run --locked python -c "from oak.tasks.coffee import ensure_coffee_data; ensure_coffee_data()"
uv run --locked pytest
uv run --locked ruff check src scripts tests
npm --prefix frontend run types:check
npm --prefix frontend run build
```

The first command downloads the checksum-pinned public Coffee dataset without a model call. Tests use real libraries, retained source fixtures, actual HermiT, and saved real trajectories when available. Live USGS checks require `OAK_LIVE_TESTS=1`; live weather MCP checks require `OAK_LIVE_MCP_TESTS=1`. Checks requiring prior local agent runs are explicitly skipped in a fresh checkout.

The MCP pilot passed two development checks and one untouched held-out request with a frozen candidate. An earlier candidate's wrong-location answer was independently rejected. These small results do not establish broad workflow correctness. Semantic retrieval, automatic task-score refinement, canonical graph identities, and complete task-obligation enforcement remain unfinished. LangSmith cloud tracing has not been verified.

Detailed research notes, documentation, agent configuration, and runtime artifacts are maintained locally and excluded from the repository. Required test fixtures and source integrity pins remain versioned.

The authoritative public contracts are Pydantic models in `src/oak/api_contracts.py`. Generate frontend types with `npm --prefix frontend run types:generate` after intentional contract changes. CI checks drift against OpenAPI. `npm --prefix frontend run test:browser` starts the actual API over a disposable copy of reviewed weather fixtures. To also inspect retained local Coffee/USGS runs, start `oak serve` and use `OAK_TEST_URL=http://127.0.0.1:8501 npm --prefix frontend run test:browser`. Browser checks never substitute server responses or invoke paid work merely to inspect evidence.

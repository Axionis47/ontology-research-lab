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
uv run --locked oak serve
```

Open [the local auditor](http://127.0.0.1:8501). Model execution requires a configured GCP project and application-default credentials. Gemini CLI runs with native tool execution disabled. Model configuration and spending limits are in `config/runtime.json`; credentials and run artifacts stay local.

The four views are Ask, Audit, Revise, and History. Suggestions create candidates with actual validation and replay evidence. MCP onboarding, construction, and inference use the CLI:

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
```

The first command downloads the checksum-pinned public Coffee dataset without a model call. Tests use real libraries, retained source fixtures, actual HermiT, and saved real trajectories when available. Live USGS checks require `OAK_LIVE_TESTS=1`; live weather MCP checks require `OAK_LIVE_MCP_TESTS=1`. Checks requiring prior local agent runs are explicitly skipped in a fresh checkout.

The MCP pilot passed two development checks and one untouched held-out request with a frozen candidate. An earlier candidate's wrong-location answer was independently rejected. These small results do not establish broad workflow correctness. Semantic retrieval, automatic task-score refinement, canonical graph identities, and complete task-obligation enforcement remain unfinished. LangSmith cloud tracing has not been verified.

Detailed research notes, documentation, agent configuration, and runtime artifacts are maintained locally and excluded from the repository. Required test fixtures and source integrity pins remain versioned.

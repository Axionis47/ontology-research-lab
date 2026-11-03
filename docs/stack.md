# Pinned technology stack

Decision: one local Python application, using the LangChain ecosystem for workflow, model integrations, tracing, and evaluation. This is an engineering decision for implementing OaK, not a stack specified by its authors.

Exact direct dependencies live in `pyproject.toml`. `uv.lock` locks transitive versions and distribution hashes. `.python-version` pins Python 3.12.13; `toolchain-java.lock.json` pins the Java archive and checksum. Change these deliberately in a dependency commit, then rerun the setup checks.

## Responsibilities

| Area | Library | Responsibility |
| --- | --- | --- |
| Workflow | LangGraph | Explicit construction, repair, freeze, inference, revision, and resume transitions |
| Agent and model interfaces | LangChain, langchain-core, OpenAI and Anthropic integrations | Messages, typed tool calls, structured outputs, provider usage metadata, bounded ReAct execution |
| Execution persistence | langgraph-checkpoint-sqlite | Local checkpoints keyed by workflow thread and checkpoint IDs |
| Traces and evaluations | LangSmith | Nested model/tool traces and experiment results, with benchmark-owned scoring functions |
| Contracts | Pydantic and pydantic-settings | Validated schemas, function definitions, patches, manifests, and configuration |
| Ontology | Owlready2 with its bundled HermiT, Temurin Java 21 | OWL construction and actual logical consistency/unsatisfiability checks |
| Knowledge graph | NetworkX MultiDiGraph | Typed entities and relations, explicit edge identities, deterministic graph operators |
| Artifact index | SQLite through SQLModel | Run, revision, dependency, and evidence metadata |
| Artifact storage | Immutable JSON/JSONL, OWL, and source files | Inspectable S/G/F versions and actual intermediate outputs, indexed by content hashes |
| Local interface | Streamlit | Schema, KG, function and revision inspection, text questions, and suggestions |
| Execution interface and logs | Typer and structlog | Explicit commands and structured local events |
| Code documentation | MkDocs with its bundled Read the Docs theme and mkdocstrings | A browsable method/design reference and API pages generated from docstrings |
| Development | uv, pytest, Ruff | Reproducible installation, real component checks, formatting and linting |
| Source extraction | pypdfium2 and BeautifulSoup | PDF text and arXiv HTML/math extraction |

LangGraph controls the paper's outer loop. LangChain supplies the inner agent/model interfaces. The paper's schema-to-OWL mapping, nine operators, function composition, freeze rules, and regression rules remain explicit project code. Generic memory integrations do not define these semantics.

The initial target is a local, single-user pilot. SQLite is appropriate for that scope. A multi-user deployment requires a separate concurrency/storage decision. Streamlit submits explicit work and displays stored state; ordinary page reruns must not launch model calls or repeat a job.

## Three kinds of persistence

1. **LangGraph checkpoints** restore execution. Graph state contains artifact IDs and hashes, plus small control state. Large KGs do not get copied into every checkpoint.
2. **LangSmith traces** explain model/tool execution and correlate experiments. Trace metadata links to the same run, kernel, graph, function, and evaluator versions.
3. **Local immutable artifacts and manifests** preserve the authoritative revision and validation history. Checkpoint retention or cloud trace retention cannot erase this evidence.

These use separate stores: `.local/checkpoints.sqlite`, `.local/catalog.sqlite`, and `.local/artifacts/`. Reviewed evidence can be copied into `docs/verification/` for a capability commit. A Git commit identifies code; a kernel revision identifies generated runtime state.

LangSmith's Python SDK supports `evaluate()` and `aevaluate()` with `upload_results=False`. Supply local examples and save returned results locally. Hosted tracing uses explicit credentials and `LANGSMITH_TRACING=true`. A self-hosted LangSmith server requires its Enterprise offering and is outside this pilot's setup. See [local evaluation](https://docs.langchain.com/langsmith/local), [observability setup](https://docs.langchain.com/langsmith/observability), and [self-hosting](https://docs.langchain.com/langsmith/self-hosted).

## Intermediate outputs are documentation

The following is the required implementation contract, not a claim that runtime stages already exist. Each completed stage saves its actual outputs and a validated manifest. Failed attempts save errors and partial-output status. A successful stage cannot advance without its evidence being durably written.

| Stage | Required inspectable output |
| --- | --- |
| Analyze | Requirements and links to source tasks/corpus |
| Draft and validate | Schema JSON, OWL translation, HermiT input/output, repair diff |
| Extract and merge | Extraction records with document/row provenance, merged KG, merge decisions |
| Compose | Typed function contracts, executable composition, operator dependencies |
| Execute and score | Actual calls/results, final answer, official metric, limits and usage |
| Judge and revise | Structured feedback, candidate patch, parent/candidate diff, acceptance evidence |
| Freeze and resume | Immutable kernel manifest and exact execution checkpoint reference |
| Adapt and regress | Adapter contract, impacted dependencies, actual replay results, fresh-inference coverage |

Every manifest must include:

- Format version, run/stage/attempt IDs, timestamps, status, parent revision, source-code commit, dependency-lock hash.
- Input/output artifact IDs, SHA-256 hashes, media types, and paths.
- Prompt, model, generation settings, evaluator and benchmark split versions, when applicable.
- Validation results with evidence type and coverage, errors, duration, reported usage, and separately labeled cost estimates.
- LangGraph thread/checkpoint and LangSmith trace IDs when available. Missing optional values are explicit nulls, never invented measurements.

Generate a short stage report from this manifest, link it from the inspector, and render the workflow diagram from the actual LangGraph topology. API documentation comes from docstrings. Keep paper facts in the method specification, engineering decisions here or in the design, and current status in the work plan. This avoids maintaining parallel prose accounts of the same code and run.

Pydantic validates record shapes. HermiT checks the encoded OWL semantics. Real function execution and benchmark scoring establish different evidence. All four results stay visible independently.

## Install and verify

The pinned Java installer currently supports this project's macOS ARM64 host. Another platform needs its own verified archive pin. Use uv 0.12.0, whose exact required version is enforced by `pyproject.toml`.

From the project root:

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.tools/python"
export UV_CACHE_DIR="$PWD/.local/uv-cache"
uv python install 3.12.13 --no-bin
uv sync --locked
uv run --locked python scripts/setup_java.py
uv run --locked python scripts/verify_environment.py --output .local/verification/environment.json
uv pip check
uv run --locked ruff check scripts
uv run --locked mkdocs build --strict
```

Use `uv run --locked mkdocs serve` to browse documentation. The generated API pages currently cover setup tooling. Runtime API pages will be added with the real implementation.

`.env.example` names configuration variables without credentials. Pin actual provider/model IDs, endpoint, prompt versions, sampling settings, and spending limits in each run's configuration before paid execution. Gemini CLI 0.66.0 is a development review tool, separate from runtime provider integrations; its authentication is still absent.

## Verification boundary

The setup verifier checks pinned package installation/imports, real SQLite checkpointer initialization and reopen, Java/HermiT startup, and the retained paper's hashes. Its machine-readable report records the evidence and failures. It makes no model calls and does not substitute synthetic ontology or benchmark results for the missing application. A successful setup report is not an OaK benchmark pass.

See [work plan](work-plan.md) for the current milestone and [setup API](reference/setup.md) for the actual verification implementation.

Primary implementation references: [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [LangChain overview](https://docs.langchain.com/oss/python/langchain/overview), [Owlready2 reasoning](https://owlready2.readthedocs.io/en/latest/reasoning.html), [Streamlit execution architecture](https://docs.streamlit.io/develop/concepts/architecture).

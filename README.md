# OaK

A local ontology auditor implementing the construction and frozen execution loop from [Toward Effective and Reliable LLM Agents via Dynamic Ontology](https://arxiv.org/abs/2608.22974v1).

Create a task from genuine evidence, inspect its schema, knowledge graph and functions, ask questions, and propose a revision in plain text. The app retains intermediate artifacts, actual HermiT results, model receipts, tool calls, candidate differences, and old-task replay evidence.

## Run locally

After the pinned setup in [docs/stack.md](docs/stack.md):

```sh
npm ci --ignore-scripts
uv sync --locked
uv run oak serve
```

Open [the local auditor](http://127.0.0.1:8501). Gemini CLI uses the configured GCP project and application-default credentials. It runs with native tool execution disabled. The model, prices, limits, and $40 shared application budget are pinned in `config/runtime.json`. See [Gemini setup and usage accounting](docs/gemini.md).

The four views are Ask, Audit, Revise, and History. New evidence is acquired explicitly. A suggestion creates a candidate; promotion checks construction evidence and actual replay of previous calls. Failed and interrupted runs retain their evidence and can resume.

## Verification status

The real seven-event USGS pilot completed construction, frozen answering, a depth/minimum-magnitude revision, old-call replay, and promotion. Its initial function gap is retained as an insufficient-evidence result. The revised maximum-depth answer matched the real source value of 70 km.

The official ToolQA Coffee pilot uses all 5,746 corpus rows and separate construction, development, and held-out queries. Its model-backed evaluation is in progress, not yet a reported benchmark result. Small pilot outcomes do not establish broad accuracy or reproduce the paper's reported scores.

```sh
uv run pytest
uv run mkdocs serve
```

Tests exercise real libraries, genuine public records, actual HermiT, and saved real model trajectories. Live network checks are opt-in with `OAK_LIVE_TESTS=1`; no mock services or fabricated model responses are used. LangSmith cloud tracing is optional and has not been verified here.

## Documentation

- [Runtime method, deviations, and limits](docs/runtime-method.md)
- [Corpus acquisition and provenance](docs/corpus.md)
- [Ontology semantics](docs/ontology-semantics.md)
- [Generated functions](docs/functions.md)
- [Constrained adapters and regression coverage](docs/regression.md)
- [Frontend workflow](docs/ui.md)
- [Official Coffee protocol](docs/coffee-protocol.md)
- [Generated runtime API reference](docs/reference/runtime.md)
- [Paper extraction](docs/paper/extracted/paper-text.md) and [refined specification](docs/paper/method-spec.md)
- [Progress and next actions](docs/work-plan.md)

The 18 Agent Skills for Context Engineering are installed project-locally under `.agents/skills`, with their pinned revision and license retained. The project builds task schemas and functions; it does not train model weights.

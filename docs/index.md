# OaK ontology auditor

The local application constructs task-specific schema S, knowledge graph G, and functions F from real evidence, then supports questions and versioned text suggestions. Its LangGraph workflow uses actual Gemini CLI calls through GCP and actual OWL/HermiT validation.

Run `uv run oak serve` and open [the local auditor](http://127.0.0.1:8501). Ask, Audit, Revise, and History expose answers, evidence, differences, validation, and resumable runs.

The real acceptance checks cover USGS corpus expansion, a model-proposed compatibility adapter, and the official Coffee pilot. See [results and limits](verification/acceptance.md).

- [Runtime method](runtime-method.md)
- [Pinned stack and setup](stack.md)
- [Paper specification](paper/method-spec.md)
- [Interface guide](ui.md)
- [Generated runtime API](reference/runtime.md)
- [Progress and continuation](work-plan.md)

All reports derive from saved real artifacts. No mocked provider, fabricated benchmark record, or simulated reasoner is used.

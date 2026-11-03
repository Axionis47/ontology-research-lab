# OaK

Implementation workspace for [Toward Effective and Reliable LLM Agents via Dynamic Ontology](https://arxiv.org/abs/2608.22974v1), with observable artifacts, versioned user suggestions, and constrained compatibility adapters.

Current status: pinned LangGraph/LangChain/LangSmith environment, source capture, and design. The OaK runtime has not been implemented or benchmarked yet.

- [Pinned stack, installation, and intermediate-output contract](docs/stack.md)
- [Actual setup verification report](docs/verification/setup.json)

- [Readable source extraction](docs/paper/extracted/paper-text.md)
- [PDF text with page boundaries](docs/paper/extracted/paper-pdf.txt)
- [Refined paper specification](docs/paper/method-spec.md)
- [System design and acceptance criteria](docs/design.md)
- [Progress, blockers, and commit milestones](docs/work-plan.md)
- [Independent Gemini review prompt](docs/review/gemini-prompt.md)

The 18 published Agent Skills for Context Engineering are installed project-locally in `.agents/skills`. Their source revision and license are recorded in `.agents/context-engineering-source.json` and `.agents/CONTEXT_ENGINEERING_LICENSE`.

No model training, benchmark execution, mocked implementation, or deployment has been performed.

After the setup commands in the stack document, run `uv run --locked mkdocs serve` to browse the documentation. API pages are generated from the actual setup code; runtime API pages will be added with their implementation.

# OaK implementation workspace

Implement [OaK](https://arxiv.org/abs/2608.22974v1) with inspectable schema, knowledge graph, and functions; versioned text suggestions; real OWL/HermiT validation; and explicit regression evidence.

The technology stack is pinned around LangGraph, LangChain, and LangSmith. Source extraction and design are preserved. The OaK runtime and benchmark pilot are the next implementation milestones.

- [Pinned stack and setup](stack.md)
- [Paper specification](paper/method-spec.md)
- [System design and acceptance criteria](design.md)
- [Progress and next milestone](work-plan.md)
- [Setup API generated from code](reference/setup.md)
- [Independent review prompt](review/gemini-prompt.md)

The intermediate-output contract lives in the stack decision. Actual runtime artifacts will appear only after the corresponding real stages execute.

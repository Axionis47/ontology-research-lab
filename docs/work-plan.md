# Current work and continuation

## Objective

Implement OaK from its paper with real components, visible S/G/F artifacts, text suggestions, versioned validation, and efficient compatibility checks after changes. The user wants autonomous progress within stated restrictions, durable context, and meaningful commits.

The engine must work across task domains. Coffee is a first validation surface; its schema and reasoning must not be hardcoded into core code. Frozen S/F are reused across queries, while paper-style inference builds the corpus-dependent G. See docs/design.md for the shared-engine/task-adapter boundary and the evidence required to claim reuse.

## Completed preparation

- Installed all 18 published context-engineering skills under .agents/skills at upstream commit 9ff0c99108b36d3b886defd825d8ac1f47dba374.
- Verified 18 unique skill names, required metadata, and every skill-local Markdown reference in SKILL.md.
- Saved the paper's PDF and HTML with source URLs and SHA-256 hashes.
- Extracted embedded text from all 11 PDF pages and a readable HTML-derived text with 111 MathML expressions preserved as LaTeX.
- Recorded the native Docling failures accurately in the extraction report. The fallback uses pypdfium2 plus arXiv HTML, not a simulated extraction.
- Investigated the official benchmark surfaces and selected ToolQA Coffee Easy as the proposed first pilot.
- Wrote the user extension, adapter idea, validation boundaries, and acceptance criteria in docs/design.md.
- Completed the source-derived method specification, including the nine operators and an explicit register of missing paper details.
- Visually checked PDF pages 3, 7, 10, and 11. Confirmed the Figure 5 round-count conflict and illustrative function/API mismatch. Chart-only values have not been exhaustively digitized.
- Prepared Gemini CLI 0.66.0 through temporary npm storage. Its headless availability check failed because authentication is absent; no Gemini review completed.
- Fixed the stack around LangGraph, LangChain, and LangSmith, with Pydantic, NetworkX, Owlready2/HermiT, SQLModel/SQLite, Streamlit, and MkDocs/mkdocstrings. Responsibilities and intermediate-output contracts are in docs/stack.md.
- Pinned Python 3.12.13, uv 0.12.0, exact direct dependencies and a transitive uv.lock. Installed and checksum-verified local Temurin JRE 21.0.13+9.
- Added reproducible Java setup and environment-verification scripts. The verifier records actual library versions/imports, reopened SQLite checkpoint tables, JVM/HermiT startup, and source hashes in docs/verification/setup.json.
- Added a documentation site and API pages generated from actual setup code. Runtime stages and their reports remain to be implemented.
- Checked the user's reusable-kernel interpretation against raw paper Sections 3.1 to 3.3. Recorded the fixed O versus generated S/F distinction, dynamic ReAct calls, per-query G, task-adapter boundary, and decision/evaluation policy in docs/design.md.

## Meaningful implementation milestones

1. **Project skills and provenance:** installed collection, license, pinned source, verified local references.
2. **Paper and design specification:** raw source, refined method, decisions, gaps, benchmark pilot, acceptance criteria.
3. **Pinned stack and setup:** LangGraph family, real installed dependencies, Java, setup receipts, generated code documentation.
4. **Real benchmark loading and scoring:** pinned official Coffee corpus/questions, documented split, real metric, no agent yet.
5. **Observable kernel construction:** real schema drafting, OWL/HermiT, graph extraction/merge, functions, traces, and artifact versions.
6. **Frozen-kernel execution:** real ReAct calls and benchmark score on the pilot, with S/G/F visible.
7. **User questions and revision candidates:** read-only questions, text patches, actual validation, history, and disposition.
8. **Constrained adapters and selective regression:** real old inputs against revised artifacts, explicit compatibility coverage, fresh inference fallback.
9. **Demonstrated reuse:** run the shared engine on a second materially different genuine task surface, constructing its own kernel and measuring held-out task outcomes. A second loader or copied domain implementation does not satisfy this milestone.

Each milestone should end in a reviewable commit with actual verification evidence. A documentation milestone must not be reported as a working runtime.

## Current implementation milestone

The real corpus connectors, official Coffee loader/scorer, ontology grammar and OWL/HermiT validation, generic operators, bounded function language, artifact store, LangGraph construction loop, frozen ReAct runner, and minimal Streamlit interface are implemented. Runtime acceptance checks are in progress. The interface has Ask, Audit, Revise, and History views.

Gemini CLI 0.66.0 successfully reached Vertex AI through the user's existing gcloud project and application-default credentials. A real tiny generation completed with 5,435 input and 6 output tokens and zero native tool calls. No API key is needed. The user authorized a total $40 limit, with careful small checks before longer runs. The CLI runs in an isolated empty directory with hooks and extensions disabled and native tool execution denied. See the model adapter and actual saved preflight evidence.

Actual component checks: 26 passed, two live API tests excluded from the default invocation. Earlier live USGS acquisition and truncation checks passed. Genuine Coffee data and scorer checks passed. Real HermiT accepted the consistent W3C ontology and detected the contradictory cases. Three genuine Service/Streamlit AppTest cases passed without mocks. The first real USGS loop subsequently completed: initial count/max construction scored 2/2, a fresh minimum query exposed a missing function with an honest insufficient-evidence response, a revision added minimum/depth, old construction calls replayed, and promotion passed. A fresh depth answer independently matched 70 km. The failed query remains evidence, not a success.

Current bounded work: test appending a second actual USGS corpus and replay original task corpora, then independently score fresh expanded-corpus answers. The Coffee construction is running with all 5,746 corpus records, preserving construction/development/held-out boundaries. Its first extracted chunks are under grounding review before concurrent exact-request prefetch. Record actual token costs and failures. Verify the interface against those populated artifacts, generate documentation, and commit reviewable capability groups.

## Known boundaries

- Initial pilot limits are three construction rounds and eight ReAct steps; these differ from paper defaults and are documented in runtime-method.md.
- Replay is evidence for recorded calls, not proof of fresh agent success. Changed corpora must preserve original task evidence for regression comparisons.
- The adapter supports bounded equivalent interface renaming, not arbitrary semantic migrations.
- LangSmith cloud tracing is not configured or tested. Local traces and artifacts are authoritative for this pilot.
- Do not report a benchmark score, completed revision loop, or working model-backed UI until its real acceptance checks finish.

## How to resume

Read AGENTS.md, this file, docs/runtime-method.md, docs/design.md, and docs/paper/method-spec.md. Check git status and saved .local/pilots receipts before restarting any paid work. The current goal is a final working, minimally built ontology audit application. Continue the original implementation objective rather than repeating conceptual setup. Preserve all failed-run evidence and keep reference labels outside agent prompts.

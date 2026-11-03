# From paper to an inspectable run

The source extraction and [method specification](paper/method-spec.md) distinguish the paper's claims from implementation decisions. This application implements ontology and function construction, not neural weight training.

The fixed operators O are ordinary tested Python functions. Gemini proposes task-specific schema S and a bounded function catalog F. Each function is data describing calls to those operators, with typed inputs and outputs. The executor does not execute arbitrary generated Python. The corpus C contains actual supplied or fetched evidence. Extraction produces G under S, retaining source identities. A frozen kernel contains S and F; the answering model chooses calls dynamically and sees their actual observations.

The saved LangGraph workflow is Analyze → Draft → HermiT → Extract → Compose → Execute → Judge → Repair or Freeze. Schema validation and function probes use real components. The judge receives execution evidence and construction scores. A favorable model judgment cannot override a wrong measured answer or a failed execution. Answers without independent reference labels remain unmeasured, even when the judge accepts the candidate.

## Visibility and persistence

Every run pins its request, parent revision, corpus, model configuration, and validation queries. JSON artifacts use SHA-256 identities and are verified on read. The SQLite index connects tasks, revisions, requests, events, and usage receipts. LangGraph checkpoints persist completed stages. Exact successful model calls can be reused during resume; they remain linked to the original request and response. A timeout with missing usage retains its cost reservation.

The Audit view shows S, G, F, original evidence, OWL, validation, and candidate differences. History shows actual intermediate events, tool calls, errors, and answer evidence. A failed run is inspectable and resumable. Artifact integrity, logical consistency, graph data integrity, function execution, recorded-call compatibility, and fresh task accuracy are separate evidence types.

A suggestion is a recorded input to task analysis and schema drafting. It creates an immutable candidate with a parent ID. Promotion requires construction checks and successful recorded-call replay. A later parent answer invalidates an older regression receipt until it is checked. Existing kernels and their original artifacts remain available.

## What the pilot changes or leaves open

These are explicit engineering choices, not claims of exact paper reproduction:

- The default pilot uses at most three construction rounds and eight ReAct steps. The paper describes five rounds and twenty steps. The small construction query set stays fixed across rounds, rather than fresh 20% sampling from a larger training pool.
- The schema grammar, OWL mapping, extraction format, function language, prompts, and repair diagnostics resolve details omitted by the paper. Their executable contracts and constraints are documented with the code.
- Extraction uses at most 80 evidence documents per chunk, additionally limited by bytes. Local citation aliases reduce repeated identifiers. Repeated entities may be returned as typed tables; expanding a model-produced values array into a record is structural serialization, not a handwritten domain extractor. All evidence values still come from the actual model response. Omitted documents require an explicit reason.
- Exact reuse of an already extracted graph for unchanged corpus and schema is a cache extension. New corpus evidence triggers extraction. Saved artifacts distinguish cached graph reuse from a fresh model extraction.
- Scalar arithmetic complements the paper's nine operators for derived quantities such as a price range. It is a bounded utility, not a claimed tenth paper primitive.
- The initial local application uses SQLite directly for its catalog and the official SQLite LangGraph checkpointer. SQLModel remains pinned but is not needed for this small local schema.
- Gemini CLI uses Vertex AI with application-default credentials. Local artifact tracing works without LangSmith credentials. LangSmith cloud tracing remains optional and unverified until configured.
- The same model performs construction and qualitative review. That review is not an independent quality guarantee. Actual reference scoring and deterministic gates carry separate labels.

## Corpus acquisition and old-task compatibility

A connector calls a read-only external API before inference. It saves request parameters, timestamps, the exact response, hashes, and completeness evidence. The agent does not fabricate a live result or decide arbitrary network calls. Refreshing a source is an explicit action. The UI explains whether evidence replaces an identical source request or adds a source.

A recorded task is the pair of its question and its supplied corpus. After a schema change, old calls run against a real graph built under the new schema from that original corpus. This may require fresh extraction, but does not rerun the ReAct loop. Adding new records therefore does not turn an old event-count comparison into a false regression. A new question over the expanded corpus is a separate fresh inference test.

A compatibility adapter may rename equivalent interfaces. It cannot insert answers, add constants, change computations, or use task IDs. Its proposer sees old and new schemas and functions, not benchmark reference answers. Successful replay establishes only the recorded calls on recorded corpora. It does not prove that a new planner will choose correctly, or that arbitrary unseen tasks are preserved.

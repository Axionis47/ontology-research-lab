# Queries, accompanying corpora, and live information

OaK's query `q` is the question or task request. Its accompanying corpus `C_q` is the evidence available to answer that request. A corpus can contain documents, table rows, or records obtained from an external service. It is separate from the ontology schema, from the instantiated knowledge graph, and from the evaluator's expected answer.

The paper specifies `G_q = Build(S*, C_q)` and then runs the agent with the frozen schema/functions over that graph. It does not fully specify a production API acquisition layer. The connector boundary described here is an engineering extension. [Paper, Section 3.3](https://arxiv.org/html/2608.22974v1#S3.SS3)

## The initial acquisition contract

An explicit source request produces an immutable snapshot:

`query + selected task + source request -> fetch supplied/live evidence -> preserve snapshot C_q -> build G_q -> ReAct through frozen functions -> cited answer`

`oak.corpus.fetch_usgs()` calls the actual, fixed USGS public earthquake endpoint. It accepts an explicit interval and minimum magnitude, limits usable records, and requests one extra record to detect truncation. A failed or incomplete fetch is visible and cannot be normalized as a complete corpus for reasoning. It makes no model call and supplies no ready-made ontology or answer.

`oak.corpus.load_local_corpus()` captures explicitly supplied UTF-8 JSON, JSONL, CSV, Markdown, or text files. Normalization preserves original values and source locations. CSV values remain strings until a later schema-directed conversion is validated. File completeness means that the whole supplied file was read; it does not prove that the file contains everything necessary for the task.

Every snapshot records:

- Connector/source identity, request parameters, and a safe request URL or supplied filename.
- Fetch/completion time, response status, selected response headers, and media type.
- Exact payload bytes encoded in base64, byte count, and SHA-256 hash.
- Request coverage, truncation/failure state, and freshness information.
- A snapshot ID covering the acquisition record and explicit errors with retryability.

`normalize_snapshot()` emits documents with source ID, record locator, snapshot ID, content hash, text, and original structured record. For USGS, source IDs use the real event ID. The API format explanation preserves units: coordinates are longitude, latitude, and depth in kilometres; event/update times are Unix milliseconds. Nulls stay null. This is source-format interpretation, not a generated domain ontology. [USGS API](https://earthquake.usgs.gov/fdsnws/event/1/), [USGS GeoJSON format](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php)

The default maximum is 100 usable records and 5 MB per response/file. Request timestamps are explicit UTC boundaries, inclusive as documented by USGS. Fixed dates make the request scope reproducible, but USGS may revise historical events. Exact reproducibility therefore binds the saved response hash and fetch time. A new acquisition is a new snapshot even when requested dates are unchanged.

## Fresh information during inference

The first implementation acquires needed external data before the frozen ReAct run. It binds the run to an explicit corpus snapshot and does not expose arbitrary HTTP URLs or raw API access as a shortcut around schema-bound functions.

If new evidence is needed, the UI must make the missing coverage visible, execute a declared connector request, preserve the new response, and construct a new graph snapshot. A fresh run can then reuse the same kernel when its schema/functions cover the request. Updating the graph must not mutate the evidence underneath an already recorded function call.

If the new task requires concepts or operations absent from the kernel, it needs a candidate kernel revision. A more autonomous mid-run acquisition tool would require explicit graph refresh/checkpoint semantics and evaluation; it is not silently included in this initial connector.

## A small scope-expansion use case

Use a simple earthquake information agent with a fixed historical period. The first task asks for event counts and magnitude comparisons. The actual API payload contains event identities, times, magnitudes, locations, and coordinates with depth.

A user can expand the task to ask about depth and request another interval of evidence. That creates an explicit scope change and additional corpus snapshot. The construction loop must determine whether the schema/functions need a depth property and filtering procedure, show their candidate diff, and validate real operations over the new graph. It must not merely return a canned response or silently inject a handwritten schema.

This use case is proposed validation for acquisition and revision behavior, not a benchmark result. The current connector tests validate real source acquisition, provenance, normalization, and incomplete-coverage rejection. They do not validate ontology discovery, an agent answer, or successful kernel revision.

## Executable checks

Run the parser/provenance checks:

```bash
uv run --locked pytest tests/test_corpus.py
```

Run the real public API checks and retain their snapshots:

```bash
OAK_LIVE_TESTS=1 uv run --locked pytest tests/test_corpus.py
```

Live checks use 2025-01-01 through 2025-01-02 UTC, minimum magnitude 5. The normal request must produce a complete bounded result. A separate one-record request must be explicitly incomplete when more events exist. No HTTP responses are mocked. Actual receipts are saved in `.local/verification/corpus/`.

::: oak.corpus

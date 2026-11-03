# Genuine ToolQA Coffee pilot

Status: real data adapter, metric validation, and full-corpus extraction transcription audit. This is not an OaK agent score.

The adapter imports no ontology or domain reasoning implementation. It supplies a task description, queries, the genuine accompanying corpus, split metadata, and official scoring. The shared engine must construct its own S/F and build G from these records.

## Sources and reproducibility

The repository revision is `acf55534d6dcd81df84df7b5d01ebdd14508367a`. Exact URLs, sizes, and SHA-256 values are committed in `data/sources/coffee-source.lock.json`.

- [Official Coffee Easy questions](https://github.com/night-chen/ToolQA/blob/acf55534d6dcd81df84df7b5d01ebdd14508367a/data/questions/easy/coffee-easy.jsonl): 100 questions with original qids.
- [Official preprocessed external corpus](https://drive.google.com/file/d/1zRbHzPW2x4dDcfmphBWlan8cxUCRNmqk/view): `external_corpus/coffee/coffee_price.csv` inside the author-provided archive.
- [Official scoring code](https://github.com/night-chen/ToolQA/blob/acf55534d6dcd81df84df7b5d01ebdd14508367a/benchmark/ReAct/code/agents.py): `normalize_answer` and `EM`.
- [Repository source guidance](https://github.com/night-chen/ToolQA/blob/acf55534d6dcd81df84df7b5d01ebdd14508367a/README.md): distinguishes preprocessed corpus from raw Kaggle data, which must not replace the benchmark corpus.

The public ZIP archive is 592,248,116 bytes. The adapter requests only its pinned directory, the Coffee local header, and the 74,041-byte compressed Coffee entry. It verifies the directory hash, member name, compressed hash, CRC, decompressed size, and corpus hash. It fails if the server ignores Range, so it does not silently download the complete archive. The whole archive's hash is not claimed.

The CSV is 254,031 bytes and contains 5,746 rows with columns `Date`, `Open`, `High`, `Low`, `Close`, `Volume`, and `Currency`. Its date range is 2000-01-03 through 2022-09-02. Each document preserves the original values as text and links to the original CSV line, counting the header as line 1. No inferred ontology is embedded in this normalization.

## Queries and accompanying corpus

An original query is: “What was the opening price of coffee on 2001-12-06?” Its qid is `easy-coffee-0000`. The model-facing query object contains only `id` and `query`.

For this benchmark adapter, C is the official Coffee table supplied as evidence documents. It is not the question's reference answer, the model's context window, or the KG. The graph is a later artifact extracted under the generated schema. All corpus rows remain available. Any later retrieval or corpus reduction must be recorded as a separate transformation with explicit selection and coverage evidence.

Each normalized document has `id`, `content`, `source_ref`, and `metadata`. `content` is the original row serialized as JSON. Metadata carries the CSV line, date, source URL, and source hash. Reference answers are exposed through a separate evaluator-facing `load_reference_answers()` function and are not returned by `load_coffee()`.

## Pilot partition

`oak-coffee-pilot-v1` is our protocol. OaK does not identify the exact Coffee training partition, so this is not represented as the authors' partition or a reproduction of Table 3.

Within each question template, replace only its date with `{date}` for sampling purposes, then order original qids by SHA-256 of `oak-coffee-pilot-v1:` followed by qid. Assign the first item to construction, the second to development, and the third to held-out evaluation. The split function never reads answer values to choose records.

| Pilot | Template coverage | Construction | Development | Held-out |
| --- | --- | --- | --- | --- |
| `small` | Opening price, volume, and high-low range | 3 | 3 | 3 |
| `expanded` | All eight original Easy templates | 8 | 8 | 8 |

The small surface includes direct lookup and a derived quantity. Expanded adds low/high/closing prices, percentage change, and bullish/bearish classification. All unused queries remain available but are explicitly outside the selected pilot. Expanded includes the small pilot's selected IDs, so it is not an independent untouched evaluation after the small pilot has been used.

The split manifest records exact selected qids. These are small functional demonstrations, not reliable estimates of broad task accuracy. Held-out queries and reference answers must not feed prompt tuning, schema repair, or adapter generation. Sharing the corpus across these task splits reflects this benchmark's evidence setting; it does not authorize exposing held-out question labels to construction.

## Scoring fidelity and limitations

The official score lowercases, removes all ASCII punctuation, removes standalone `a`, `an`, `the`, and `usd`, then collapses whitespace and compares strings. It consequently removes decimal points and negative signs. We preserve that published behavior and label it `ToolQA normalized exact match`. It is not a strict numeric-equivalence check and should not serve alone as a general schema-compatibility validator.

The tests compare our scoring function against the actual pinned upstream scoring definitions on all 10,000 pairs of the 100 genuine reference answers. Other tests parse the full corpus, check row provenance and query-date coverage, verify query inputs exclude labels, and validate disjoint template-stratified splits. No LLM response, fake external service, or fabricated benchmark row is used.

## Usage

```python
from oak.tasks.coffee import ensure_coffee_data, load_coffee, load_reference_answers, score_answer

paths = ensure_coffee_data()
task = load_coffee(pilot="small")
# Supply task inputs and corpus documents to the real engine.
# Keep the following mapping in the evaluator process/context only.
references = load_reference_answers()
```

Run the genuine-source checks with `uv run pytest tests/test_coffee.py`. Downloaded source files remain under `.local/benchmarks/toolqa-coffee/`; the lock and code are versioned. A missing corpus is an actionable setup failure, not a skipped test or a generated substitute.

## Running the real pipeline

Each phase is explicit so source preparation cannot silently start paid model calls:

```bash
uv run python scripts/run_coffee_pilot.py --phase prepare
uv run python scripts/run_coffee_pilot.py --phase construct
uv run python scripts/run_coffee_pilot.py --phase development
uv run python scripts/run_coffee_pilot.py --phase heldout
```

The default is the small pilot in `.local`, using the application's actual provider configuration and spending ledger. Preparation creates a real task from all 5,746 CSV rows and saves the exact split, source identifiers, corpus hash, and queries in `.local/evaluation/toolqa-coffee/small/protocol.json`. Reference labels are saved separately in `evaluator-references.json`. Only construction labels are attached to the construction evaluator. Development and held-out labels stay outside agent inputs.

Construction and evaluation execute the actual service worker synchronously, retaining its checkpoints, artifacts, events, failures, and costs. The script does not supply a schema, graph, function implementation, or model answer. Construction must pass before evaluation. Held-out evaluation requires a completed development report for the exact same frozen revision. Reports live under `reports/<revision-id>/` and are also immutable service artifacts.

Completed predictions are scored once using the official metric. An actual `insufficient_evidence` response retains that status and its exact answer string is scored; it is not replaced with a fabricated response or omitted from the denominator. Infrastructure failures leave the report incomplete. After inspecting a failed run, `--resume` resumes its saved workflow. Completed wrong predictions are never rerun by the script to improve the score.

Preparation was executed against the full authentic corpus and verified to create a 5,746-row task. This preparation evidence is not a model accuracy result. Paid-phase accuracy and cost must be reported from their saved run artifacts after completion.

## Full-corpus extraction evidence

Run `3e01ffff6cec418cb0548a68bdabab11` extracted all 5,746 source records through 111 real model requests. Every normalized record matched the original CSV, and all 40,222 directly comparable extracted field values matched the source. There were no missing or ignored documents. Every extracted entity used the model-generated `CoffeeMarketDay` type. This establishes transcription and citation coverage, separately from ontology consistency or downstream task accuracy.

The full audit is saved in `.local/prefetch/3e01ffff6cec418cb0548a68bdabab11/full-source-audit.json`, with immutable artifact ID `e2e1394eee846b17213f6f995579cf00f7c9d46e4956616910f16d741f8992db`. It records every chunk's receipt and comparisons. Extraction's recorded model-usage estimate was $1.82473425, excluding other construction and inference stages.

`scripts/prefetch_extraction.py` can warm exact model requests for an already running extraction. Its default dry run reconstructs saved requests from the actual checkpoint, verifies request hashes and runtime identity, and checks completed output against source records. Explicit `--run` uses the real Gemini adapter and its shared request locks; the original worker performs graph assembly and validation. The observed run had exactly one successful paid receipt per chunk. No replacement response, extracted program, reduced corpus, or manually authored entity was supplied.

## Completed model-backed pilot

The frozen kernel scored 3/3 construction, 3/3 development, and 3/3 untouched held-out questions using the official metric. Initial construction answers contained extra prose and scored 0/3 despite correct numeric tool results. A formatting repair reached 3/3 while retaining the unchanged validated graph and function catalog. No held-out question or reference was used for that repair. These nine selected questions establish a small functional pilot, not the paper’s aggregate results. Exact run, revision, metric, and report identities are retained in [acceptance evidence](verification/acceptance.json).

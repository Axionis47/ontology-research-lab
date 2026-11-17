# 06: What does the model actually consume?

## Point and new terms

An **interface** is the information and operations exposed to a model. A **tool call** is a structured proposal, not an executed action. **Grounding** connects an answer to observations. The model consumes tokens, including descriptions of ontology definitions. It does not automatically execute RDF inference.

## Input and prediction

Read `inputs.json`. Both cases contain Maya's project-management role. Only the first gives Noah current production approval. The second gives staging approval. The answers should be `Noah` and `unknown`, respectively. Unknown does not mean nobody has authority in the real world.

The script creates three interfaces per case, with the same definitions and evidence available:

1. `text`: observations as sentences.
2. `ontology`: the same observations as structured records, not a full OWL ontology.
3. `query`: definitions plus a tool. The model must request the observations; the runtime returns the same records without selecting an answer.

This isolates serialization and access method. It does not compare presence versus absence of domain rules. The query interface needs an extra model turn, so raw cost is not directly equivalent.

Here `query` means tool-mediated retrieval using `read_records`, not SPARQL traversal. A later extension can replace that tool with bounded graph queries while preserving the task and evidence.

## Run

From the repository root:

```sh
python3 learning-labs/06-model-consumption/run.py
python3 learning-labs/06-model-consumption/run.py --live
```

The first command prepares exact message payloads without contacting a model. It reports `PREPARED_NOT_RUN`, never model success. The second uses the unchanged model, endpoint, temperature, thinking setting, context and output limits in `config/models.toml`. It makes at most eight chat calls: one each for four direct-input cases and two each for two query cases. No model or provider is substituted. Connection failure records `MODEL_UNAVAILABLE`; unattempted trials remain unmeasured. The configured timeout applies per call.

Every run writes a timestamped JSON receipt under `results/`. Live receipts contain actual requests, raw responses, token counts reported by Ollama, tool results in the follow-up request, configured identity, returned identity and exact scoring outcomes. Expected answers are retained in the receipt but excluded from model requests. The stored request is the complete transcript, not a chain-of-thought claim.

## Recorded first attempt

On November 16, 2026, the preparation checks passed. The live attempt could not reach localhost because the execution environment returned `Operation not permitted`. Receipt `results/20261116T181700510581Z.json` preserves the attempted request and error. No model answered; the remaining trials are explicitly `NOT_RUN`. This is an operational restriction, not a model reasoning failure.

## Read the result

A subsequent authorized localhost run completed all six trials with the configured `qwen3:8b-q4_K_M`, using eight actual model calls. See `results/20261116T181817940419Z.json`. Both cases passed through all three interfaces. The initial sandbox failure remains retained. This shows successful consumption on these two fixtures, not an accuracy advantage for structured input. See [the suite results](../RESULTS.md) for the token comparison.

Compare `trials[].answer`, `passed`, and `events[].response` across interfaces. A correct answer must cite known evidence; a named approver must cite e2. This simple scorer does not validate every possible explanation. A failed JSON parse is retained as a failure. The default checks validate preparation only. One pass on two synthetic cases cannot demonstrate superior reasoning or general reliability. No AppWorld or Gemini outcome is claimed.

## Standards versus our choices

- [W3C RDF 1.1](https://www.w3.org/TR/rdf11-concepts/) defines graph triples. Our compact JSON records are an application representation, not RDF serialization or OWL reasoning.
- [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling) documents the vendor interface used by this optional live experiment. It is not a universal ontology-consumption standard.
- The approval rule, two-case evaluation, call budget and scoring are project choices.

# Ten small experiments with Gemini CLI

**Read the [ten experiments step by step](../experiments/02-ontology-concepts/README.md), then the [complete native repair loop](../experiments/01-improvement-loop/README.md).** The first explains component checks; the second shows a failed task, a measured function repair, and successful later executions.

**Executed: all ten passed. [Read the exact answers and original receipts](GEMINI-RESULTS.md).**

**Next comparison: [same task across five interfaces](protocol-comparison/RESULTS.md).** Actual context payloads, token counts and stale-action gate outcomes are shown side by side.

**Ontology consumption specifically: [six separate same-task experiments](ontology-consumption-six/README.md).** These hold all initial facts fixed and vary how definitions and domain computation are accessed.

**Harder task, same six strategies: [delegated authority and independent approval panels](ontology-consumption-complex/README.md).** This adds scope inheritance, time limits, explicit denials, and constraints on pairs of people.

These lessons use the installed **Gemini CLI with its configured model and login**, as requested on November 16. They do not change the AppWorld actor/judge/proposer configuration. Here Gemini is the participant whose answer is tested, not its own evaluator.

## What happens in every experiment

```text
Small definitions + concrete input + one question
                     |
                     v
            Gemini CLI, no tools
                     |
                     v
              JSON response
                     |
                     v
     Deterministic reference-answer checker
                     |
                     v
   Receipt: prompt, model, answer, checks, outcome
```

The reference answer is never included in the sent prompt. Inputs and reference answers are exposed teaching fixtures, not a held-out research benchmark. Every CLI call starts a fresh conversation in an empty working directory, retaining the CLI's global configuration and login. Tool calls are denied. We record models actually reported by CLI statistics rather than inventing a model identity. No alternative provider is used after an error.

The receipt captures the exact submitted user prompt and returned CLI envelope. Gemini CLI also supplies its own system context and may use an internal router. We do not claim to capture every internal message or control its configured routing. Provider-reported model roles and usage remain in the original statistics.

## Run

From the repository root:

```sh
# Prepare all ten exact prompts without calling Gemini.
python3 learning-labs/gemini_experiments.py

# Run just the first experiment through Gemini CLI.
python3 learning-labs/gemini_experiments.py --experiment 01 --live

# Run all ten sequentially, at most one CLI invocation each.
python3 learning-labs/gemini_experiments.py --live
```

Each invocation gets the configured timeout. The suite stops contacting the provider after an operational failure and explicitly marks remaining lessons NOT_RUN. Wrong model answers do not stop the remaining lessons. All receipts go into a new timestamped `gemini-results/` folder. Preparation is not success, and unavailable inference is not an incorrect answer.

## The ten questions

| Lesson | Gemini's job | What you inspect |
| --- | --- | --- |
| [01. Triples](01-triples/GEMINI.md) | Extract the asserted positive relationship without turning a denial into a positive edge | Subject, predicate, object order |
| [02. Definitions and facts](02-ontology-vs-facts/GEMINI.md) | Classify a new person versus a new type | Graph update versus ontology update |
| [03. Evidence](03-constraints-provenance/GEMINI.md) | Separate well-typed claims from supported claims | Valid structure alone is insufficient |
| [04. Scoped assignments](04-relationship-entities/GEMINI.md) | Select by role, environment and validity interval | Production and expiry near-misses |
| [05. Inference](05-traversal-inference/GEMINI.md) | Distinguish membership from approval authority | A graph path is not an approval rule |
| [06. Interfaces](06-model-consumption/GEMINI.md) | Propose a documented read call instead of guessing a value | The exact tool-call JSON |
| [07. Runtime control](07-runtime-enforcement/GEMINI.md) | Produce two identical requested deployment calls | Runtime allows only the case with evidence |
| [08. Changing facts](08-fact-invalidation/GEMINI.md) | Identify transitive stale conclusions | Unrelated state stays usable |
| [09. Extending definitions](09-ontology-extension/GEMINI.md) | Migrate a record without inventing scope or expiry | Unknown fields stay null |
| [10. Changing meaning](10-semantic-version-change/GEMINI.md) | Apply different versioned rules to the same evidence | Active package pin versus new episode version |

Each linked lesson introduces its terms. It includes `gemini-input.json`, `gemini-prompt.txt`, and a separate `gemini-expected.json`. Open those alongside the corresponding `NN-receipt.json` to follow every computational step.

## Boundaries

Lesson 6 generates an interface request; no external data tool runs. Lesson 7 uses a real Python gate against a local boolean fixture, not a production deployment. The other lessons check model interpretations and proposed records. These are not ten fully autonomous ReAct agents.

The [standards map](STANDARDS.md) explains RDF, RDFS, OWL, SPARQL, SHACL and PROV-O. Supplying a description of these concepts to Gemini is not executing an OWL reasoner. The old dependency-free `run.py` programs remain as deterministic companions, and the earlier Qwen measurement remains historical evidence rather than being relabeled Gemini.

No AppWorld task, Gemini diagnostic/proposer cycle, or reusable package promotion is claimed by this suite. Those have separate roles, source evidence and acceptance requirements.

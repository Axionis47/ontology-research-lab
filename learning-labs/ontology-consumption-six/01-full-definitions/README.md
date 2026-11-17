# All definitions injected

Full ontology in context; LLM interprets and combines the rules.

**Same task:** choose an eligible production approver for LoginService on November 16, 2026. All six experiments receive exactly the same four assignment facts and deployment fact. They use the same source ontology, rules, reference checker and execution gate. Only definition access and permitted computation differ.

**Limitation:** Large vocabularies consume context; definitions in a prompt are not enforcement.

Read the shared [experiment design](../README.md) and [source ontology](../ontology.json). The [facts](../facts.json) are shared, not regenerated per experiment. No definitions or business rules are learned or changed during a run.

```sh
python3 learning-labs/ontology-consumption-six/01-full-definitions/run.py
python3 learning-labs/ontology-consumption-six/01-full-definitions/run.py --live
```

Preparation does not call Gemini. A live run uses its configured CLI model and login, saves original prompts/results, and does not use an alternate provider. These are local synthetic teaching experiments, not AppWorld evaluations.

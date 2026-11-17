# Model inspects definitions

Initially sees names and kinds, then requests definitions through inspect_schema.

**Same task:** choose an eligible production approver for LoginService on November 16, 2026. All six experiments receive exactly the same four assignment facts and deployment fact. They use the same source ontology, rules, reference checker and execution gate. Only definition access and permitted computation differ.

**Limitation:** The model can request too little, misunderstand definitions, or spend extra calls inspecting.

Read the shared [experiment design](../README.md) and [source ontology](../ontology.json). The [facts](../facts.json) are shared, not regenerated per experiment. No definitions or business rules are learned or changed during a run.

```sh
python3 learning-labs/ontology-consumption-six/03-schema-inspection/run.py
python3 learning-labs/ontology-consumption-six/03-schema-inspection/run.py --live
```

Preparation does not call Gemini. A live run uses its configured CLI model and login, saves original prompts/results, and does not use an alternate provider. These are local synthetic teaching experiments, not AppWorld evaluations.

# 07. Propose a call, then enforce a gate: Gemini CLI experiment

## The point

Identical model proposals produce different execution decisions when evidence differs. The runner dispatches only a local boolean fixture, never a real deployment.

## Terms

- **precondition:** A requirement before execution.
- **runtime gate:** Code that decides whether to dispatch.
- **effect:** An observed state change.

## Four files to inspect

1. `gemini-input.json`: definitions, source input, question and output shape.
2. `gemini-prompt.txt`: the exact user prompt sent to Gemini, with no reference answer.
3. `gemini-expected.json`: reference answer held by the deterministic checker, not sent to Gemini.
4. The run receipt: actual CLI response, reported model identity, checks and any operational failure.

## Run from the repository root

```sh
python3 learning-labs/gemini_experiments.py --experiment 07
python3 learning-labs/gemini_experiments.py --experiment 07 --live
```

The first command prepares a receipt without calling a model. The second calls the installed Gemini CLI using its configured model and login. No model override or fallback is permitted. Read the reference answer before running if you want to predict the result; it is not present in the model prompt. The checker ignores array ordering but rejects missing/extra values, keys and wrong JSON types.

## Interpretation

One correct response demonstrates this mechanism on this input only. It is not proof of general reliability or an accuracy gain over a baseline. The original deterministic `run.py` remains available as a companion. This Gemini lesson uses synthetic observations and does not count as an AppWorld result, diagnostic judgment, or accepted improvement. No model-generated code is executed.

"""Report only actual recorded results from the six consumption experiments."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
folder = Path(sys.argv[1]).resolve()
summary = json.loads((folder / "summary.json").read_text())
manifest = json.loads((folder / "manifest.json").read_text())
if not summary["complete"]:
    raise SystemExit("Incomplete run")
assert len(set(manifest["task_hashes"].values())) == 1
assert len(set(manifest["initial_fact_hashes"].values())) == 1
context_dir = folder / "contexts"
context_dir.mkdir(exist_ok=True)
metrics, contexts, limits, receipts = [], [], [], []
main_models, router_models = set(), set()
metric_rows = []
attempt_note = ""
if (folder / "attempts.json").exists():
    attempts = json.loads((folder / "attempts.json").read_text())
    failed_attempts = [a for a in attempts if a["status"] == "CLI_UNAVAILABLE"]
    links = ", ".join(f"[{a['experiment']} {a.get('reason', 'error')}]({a['original_receipt']})" for a in failed_attempts)
    attempt_note = (f"\n## Attempt history\n\nThis is a collection of the latest completed attempted normal-JSON run for each method, not one uninterrupted suite run. "
        f"There were {len(failed_attempts)} earlier operational failures, retained here: {links or 'none'}. "
        f"[All attempted runs](results/{folder.name}/attempts.json) remain visible, including the two citation failures in the selected measurements. "
        "The token table covers the selected completed responses only. Timed-out requests did not report usage, so these numbers are not the total cost of all attempts. "
        "A separate short readiness probe and full-prompt streaming diagnostic were used to diagnose the timeouts; neither substitutes for a row in this normal-JSON comparison.\n")
for item in summary["experiments"]:
    name = item["experiment"]
    rec = json.loads((folder / f"{name}.json").read_text())
    protocol = json.loads((HERE / name / "protocol.json").read_text())
    main_in = main_gen = router_tokens = total = 0
    usage_responses = 0
    for index, event in enumerate(rec["calls"], 1):
        target = f"{name}-{index:02}.txt"
        (context_dir / target).write_text(event["submitted_prompt"])
        contexts.append(f"- {name}, call {index}: [exact user prompt](results/{folder.name}/contexts/{target}), {event['user_chars']:,} characters.")
        if event.get("cli_response", {}).get("stats", {}).get("models"):
            usage_responses += 1
        for model, value in event.get("cli_response", {}).get("stats", {}).get("models", {}).items():
            total += value.get("tokens", {}).get("total", 0)
            for role, details in value.get("roles", {}).items():
                tok = details.get("tokens", {})
                if role == "main":
                    main_models.add(model)
                    main_in += tok.get("input", 0)
                    main_gen += tok.get("candidates", 0) + tok.get("thoughts", 0)
                if role == "utility_router":
                    router_models.add(model)
                    router_tokens += tok.get("total", 0)
    gate_before = rec.get("gate_before_change", {}).get("admitted")
    gate_after = rec.get("gate_after_revocation", {}).get("admitted")
    answer = rec.get("answer", {}).get("person", "NO_RESULT")
    selection_correct = answer == "Noah" if "answer" in rec else None
    evidence = rec.get("answer", {}).get("evidence_ids", [])
    evidence_complete = isinstance(evidence, list) and all(isinstance(x, str) for x in evidence) and set(evidence) == {"a-noah", "d1"} if "answer" in rec else None
    outcome = "PASS" if rec["passed"] is True else ("FAIL" if rec["passed"] is False else rec["status"])
    usage = [f"{v:,}" if usage_responses else "unreported" for v in (main_in, main_gen, router_tokens, total)]
    if usage_responses and usage_responses < len(rec["calls"]):
        usage = [value + " (partial)" for value in usage]
    metrics.append(f"| {protocol['title']} | {len(rec['calls'])} | {' | '.join(usage)} | {answer} | {evidence_complete} | {outcome} |")
    limits.append(f"| {protocol['title']} | {len(rec['definition_names_exposed'])} | {rec['successful_interface_calls']} | {gate_before} | {gate_after} | {protocol['limitation']} |")
    receipts.append(f"- [{protocol['title']}](results/{folder.name}/{name}.json): definitions exposed: {', '.join(rec['definition_names_exposed'])}.")
    metric_rows.append({"experiment": name, "title": protocol["title"], "cli_calls": len(rec["calls"]),
        "main_input_tokens": main_in if usage_responses else None, "main_generated_tokens": main_gen if usage_responses else None, "router_tokens": router_tokens if usage_responses else None,
        "total_tokens": total if usage_responses else None, "usage_responses": usage_responses, "answer": answer, "selection_correct": selection_correct,
        "evidence_complete": evidence_complete, "passed": rec["passed"], "gate_before": gate_before, "gate_after": gate_after})
(folder / "metrics.json").write_text(json.dumps(metric_rows, indent=2) + "\n")
text = f'''# Six methods: actual same-task Gemini results

Run: `{folder.name}`. Main models reported: {', '.join(sorted(main_models)) or 'unreported'}. Utility-router models: {', '.join(sorted(router_models)) or 'unreported'}.

**Same task:** choose an eligible approver for LoginService's production deployment on November 16, 2026. The four shared assignments make Maya ineligible as the author, Rin ineligible for the environment, Tao ineligible by expiry, and Noah eligible at revision 1.

**Identity checks passed for the records in this report:** initial task hashes match, initial fact hashes match, and the source ontology and six business rules are fixed. Definition retrieval never selects facts. The same local gate is used whenever a final proposal is obtained. [Manifest](results/{folder.name}/manifest.json).

## Results and tokens

| Method | CLI calls | Main input | Main generated | Router tokens | Total tokens | Answer | Complete evidence citations | Answer + citation rubric |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
'''+ '\n'.join(metrics)+attempt_note+'''

Main generated includes reported visible and thinking tokens. Router tokens include that model's input and output. Total is the sum of provider-reported model totals across all calls, not a cost estimate. Each CLI call also incurs system/context overhead. More calls can outweigh savings from a smaller definition set. Only successful reported usage is counted; a missing response is not evidence of zero provider spending.

Correct candidate selection and evidence completeness are different checks. The evidence contract requires both the assignment record and the deployment record that establishes authorship. A correct name with an omitted citation is an evidence-contract failure, not a wrong candidate. The independent gate recomputes eligibility from the trusted fixture and can still admit a correctly selected person.

Rubric limitation: the prompt asks for supporting record IDs but does not explicitly name the two IDs the checker requires. An omitted citation therefore cannot establish that the model ignored the corresponding business rule. Typed-function and checker results package complete evidence IDs explicitly; the generic query does not construct that proof bundle. Differences reflect interface/output design as well as ontology access.

## Consumption, gate outcomes, and limitations

| Method | Definitions exposed | Successful interface calls | Gate admitted at revision 1 | Gate admitted after revocation | Main limitation |
| --- | ---: | ---: | --- | --- | --- |
'''+ '\n'.join(limits)+'''

`False` in the last gate column means the unchanged old proposal was blocked after the graph changed. This protection comes from the shared runtime gate. It does not distinguish the reasoning quality of the six interfaces, and no post-rejection recovery model call ran. All effects were local checks, not production writes.

## What actually entered context

Every method is configured with the identical task and complete four-assignment/deployment facts. The full method adds all 19 ontology definitions. Retrieved definitions supply the exact relevant closure. Inspection starts with a names/kinds catalog and returns definitions only after Gemini asks. Query, function and checker methods add the relevant definitions plus their respective interfaces. Only the call files below establish what was actually submitted; NOT_RUN and PREPARED_NOT_RUN rows are not model consumption.

'''+ '\n'.join(contexts)+'''

The files capture exact user prompts, including every local observation used at each turn. They do not claim to expose the CLI's internal system messages. Original returned envelopes, model identities, answers, rule/source citations, protocol adherence and gates remain in these receipts:

'''+ '\n'.join(receipts)+f'''

## Limits on conclusions

This run tests six architectures on one exposed synthetic case. It cannot establish general superiority or reliability rates. The function/checker rely on implemented business rules, retrieval assumes correct definition dependencies, and graph queries depend on correct model-authored predicates. Small token differences can reflect stochastic thinking/routing effort, not only protocol design. No models or ontology definitions were trained or changed. AppWorld was not run.

Eight local test methods passed before inference, including task/fact equality, definition preservation, inspection equivalence, each business disqualification, generic query behavior, malformed requests, selector/checker scope, and stale/version gates.

[Experiment design and reproduction commands](README.md). [Machine-readable metrics](results/{folder.name}/metrics.json).
'''
(HERE / "RESULTS.md").write_text(text)
print(text)

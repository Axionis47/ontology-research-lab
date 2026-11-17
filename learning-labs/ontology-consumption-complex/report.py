"""Render the frozen complex pilot's actual responses and reported usage."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
run = Path(sys.argv[1]).resolve()
summary = json.loads((run / "summary.json").read_text())
manifest = json.loads((run / "manifest.json").read_text())
if not summary["complete"]:
    raise SystemExit("Run incomplete")
assert len(set(manifest["task_hashes"].values())) == 1
assert len(set(manifest["initial_fact_hashes"].values())) == 1
context_dir = run / "contexts"
context_dir.mkdir(exist_ok=True)
rows, gates, contexts, metrics, findings = [], [], [], [], []
main_models, router_models = set(), set()
for item in sorted(summary["experiments"], key=lambda r: r["experiment"]):
    name = item["experiment"]
    receipt = json.loads((run / (name + ".json")).read_text())
    title = json.loads((HERE / name / "protocol.json").read_text())["title"]
    main_input = main_generated = router_total = all_total = usage_count = 0
    for i, event in enumerate(receipt["calls"], 1):
        target = f"{name}-{i:02}.txt"
        (context_dir / target).write_text(event["submitted_prompt"])
        contexts.append(f"- {name}, call {i}: [exact submitted prompt](results/{run.name}/contexts/{target}), {event['user_chars']:,} characters.")
        stats = event.get("cli_response", {}).get("stats", {}).get("models", {})
        if stats: usage_count += 1
        for model, value in stats.items():
            all_total += value.get("tokens", {}).get("total", 0)
            for role, v in value.get("roles", {}).items():
                tok = v.get("tokens", {})
                if role == "main":
                    main_models.add(model)
                    main_input += tok.get("input", 0)
                    main_generated += tok.get("candidates", 0) + tok.get("thoughts", 0)
                if role == "utility_router":
                    router_models.add(model)
                    router_total += tok.get("total", 0)
    details = receipt.get("score_details", {})
    if receipt.get("answer_correct") and not receipt.get("protocol_followed"):
        findings.append(f"- {title} produced a correct answer but failed the required interface-use protocol. Its answer does not demonstrate successful consumption through that interface.")
    if name == "06-constraint-service":
        for turn in receipt.get("history", []):
            checks = turn.get("runtime_result", {}).get("checks", [])
            for check in checks:
                if check.get("status") == "INVALID":
                    findings.append(f"- Constraint service checked Gemini's proposed panel `{json.dumps(check['panel'])}` and rejected it for {', '.join(check.get('violated_rules', []))}. Individual eligibility does not imply a valid pair.")
    values = [f"{n:,}" if usage_count else "unreported" for n in (main_input, main_generated, router_total, all_total)]
    if usage_count and usage_count < len(receipt["calls"]): values = [v + " (partial)" for v in values]
    panel = receipt.get("answer", {}).get("panel", "NO_RESULT")
    status = "PASS" if receipt["passed"] is True else ("FAIL" if receipt["passed"] is False else receipt["status"])
    rows.append(f"| {title} | {len(receipt['calls'])} | {' | '.join(values)} | {json.dumps(panel)} | {details.get('panel_correct')} | {details.get('proof_complete')} | {status} |")
    gate_fields = [receipt.get(key, {}).get("admitted") for key in ("gate_before_change", "gate_after_revocation", "gate_with_forged_current_revision")]
    gates.append(f"| {title} | {' | '.join(str(v) for v in gate_fields)} | {receipt['successful_interface_calls']} |")
    metrics.append({"experiment": name, "cli_calls": len(receipt["calls"]), "status": receipt["status"], "passed": receipt["passed"],
        "score_details": details, "panel": panel, "main_input": main_input if usage_count else None,
        "main_generated": main_generated if usage_count else None, "router_tokens": router_total if usage_count else None,
        "total_tokens": all_total if usage_count else None, "usage_responses": usage_count,
        "gate_before": gate_fields[0], "gate_stale": gate_fields[1], "gate_claimed_fresh": gate_fields[2]})
(run / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
text = f'''# Complex ontology: actual Gemini results

Source run: `{run.name}`. Main models reported: {', '.join(sorted(main_models)) or 'unreported'}. Router models: {', '.join(sorted(router_models)) or 'unreported'}.

All strategies received the same task and 53 facts, used one ontology version and ten business rules, and shared the same proof rubric and gate. Initial task/fact hashes match. [Frozen manifest](results/{run.name}/manifest.json). [Study design and candidate traps](README.md).

The expected pair is **Vera (Ops), Tao (Security)**. Uma is individually eligible for Ops but shares Tao's home team. Vera's authority is delegated from Iris's direct grant; Iris's expired certificate blocks Iris's own approval, not a valid delegation under this explicitly stated policy.

## Side-by-side measurements

| Strategy | CLI calls | Main input | Main generated | Router tokens | All-model total | Actual panel | Panel correct | Proof complete | Overall |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
'''+ '\n'.join(rows)+'''

Main generated includes reported visible output and thinking tokens. Totals include reported router usage and all calls in this attempt. Unknown usage is not counted as zero; partial usage excludes calls without returned statistics. The model selection and thinking settings were inherited from the configured CLI, not optimized per method.

## Observed behavior

'''+ '\n'.join(findings)+'''

The business-action gate below checks current eligibility and version binding. It does not enforce prior interface use. Protocol adherence is a separate experiment score; enforcing it before action would require an additional runtime precondition.

## Same execution gate for every strategy

| Strategy | Admitted at revision 7 | Admitted after delegation revoked | Admitted if proposal merely claims revision 8 | Successful interface calls |
| --- | --- | --- | --- | ---: |
'''+ '\n'.join(gates)+'''

False after revocation means the gate blocked the proposal. This is deterministic local enforcement using the actual submitted panel, not evidence that the model noticed an unseen change. No external deployment or post-rejection model recovery ran. None means no final proposal was available to test.

## Exact submitted contexts

'''+ '\n'.join(contexts)+f'''

Original responses, application requests, returned graph/computation results, component scores and gate checks are in the per-strategy JSON files beside [the summary](results/{run.name}/summary.json). The captured prompts are user payloads, not the CLI's hidden system/global messages.

## Interpretation limits

Fourteen local test methods passed before inference against an independently written expected panel and counterexamples. These tests check scope hierarchy, validity boundaries, risk caps, delegation, certificates, denials, authorship, pair independence, evidence and stale gates. They do not establish arbitrary ontology correctness.

This is a harder single-case pilot, not a statistically reliable ranking. One attempt per strategy was scheduled in the frozen seeded order; failures and timeouts remain in the table. Typed functions and constraint services perform hand-coded computation, while prompt-based strategies ask the model to combine rules. The comparison is architectural, not a pure test of model intelligence or ontology versus no ontology. Retrieval assumes correct definition dependencies. All initial facts are deliberately present in every strategy. No AppWorld outcomes or learned ontology improvements are claimed.

[Machine-readable metrics](results/{run.name}/metrics.json).
'''
(HERE / "RESULTS.md").write_text(text)
print(text)

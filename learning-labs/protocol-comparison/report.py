"""Render actual recorded context, usage and outcomes. Does not run models."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
folder = Path(sys.argv[1]).resolve()
summary = json.loads((folder / "summary.json").read_text())
if not summary["complete"]:
    raise SystemExit("Run is incomplete; do not render final results")
contexts = folder / "contexts"
contexts.mkdir(exist_ok=True)
table = []
effects = []
context_lines = []
models = set()
for result in summary["results"]:
    mode = result["mode"]
    row = json.loads((folder / f"{mode}.json").read_text())
    main_input = main_generated = all_total = router_total = 0
    for index, call in enumerate(row["calls"], 1):
        name = f"{mode}-{index:02}.txt"
        (contexts / name).write_text(call["submitted_prompt"])
        context_lines.append(f"- {mode}, call {index}: [exact submitted prompt](results/{folder.name}/contexts/{name}), {call['user_prompt_chars']:,} characters.")
        for model, stats in call.get("cli_response", {}).get("stats", {}).get("models", {}).items():
            models.add(model)
            all_total += stats.get("tokens", {}).get("total", 0)
            for role, details in stats.get("roles", {}).items():
                tokens = details.get("tokens", {})
                if role == "main":
                    main_input += tokens.get("input", 0)
                    main_generated += tokens.get("candidates", 0) + tokens.get("thoughts", 0)
                if role == "utility_router":
                    router_total += tokens.get("total", 0)
    answer = row.get("answer", {}).get("person", "NO_RESULT")
    table.append(f"| {mode} | {len(row['calls'])} | {main_input:,} | {main_generated:,} | {router_total:,} | {all_total:,} | {answer} | {row['status']} |")
    probe = row.get("action_probe")
    if probe:
        effects.append(f"| {mode} | {probe['unguarded_fixture']['selected_person']} | {probe['unguarded_fixture']['constraint_violation']} | {probe['gated_fixture']['admitted']} | {probe['gated_fixture']['reason']} |")
text = f'''# Actual Gemini comparison

Run directory: `{folder.name}`. Models reported: {', '.join(sorted(models))}.

Same task: choose the eligible production approver for LoginService. Maya is the author, Rin covers staging, Tao is expired, and Noah is eligible at revision 1. Forty unrelated assignments are present in the source world.

## Measured token use

| Interface | CLI calls | Main input tokens | Main generated tokens | Router total tokens | All-model total tokens | Answer | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
'''+ '\n'.join(table)+'''

Counts are summed from Gemini CLI's actual statistics across each interface's calls. Main generated includes visible candidate tokens and reported thinking tokens. Router total includes its own input and generated tokens. All-model totals are provider-reported totals, not monetary cost. Repeated calls resend application history and incur CLI system/routing overhead. Character counts below describe only submitted user prompts, not hidden CLI context.

## Which stopped the stale action?

After selection, Noah's assignment was revoked. Revision 2 has no eligible candidate. Each model's identical recorded proposal was tested through an unguarded and a gated local fixture.

| Interface | Unguarded selected person | Unguarded violation | Gate admitted action | Gate reason |
| --- | --- | --- | --- | --- |
'''+ '\n'.join(effects)+'''

The gate, not a particular context format, checks freshness before acting. This is a deterministic local effect test using actual model proposals. It does not mean the model saw the revocation or that it made an incorrect decision from revision 1. No external action ran, and no recovery model call was measured after rejection.

## Exact context at each call

'''+ '\n'.join(context_lines)+f'''

All responses and observations are in the [original summary](results/{folder.name}/summary.json) and sibling per-interface JSON files. [Manifest](results/{folder.name}/manifest.json) pins source hashes, policy, configuration and limits.

## Interpretation limits

This is one exposed synthetic task, not an accuracy benchmark. A smaller prompt is not automatically a cheaper overall interaction: extra calls and system context also cost tokens. Retrieval coverage is trusted here, and the typed function implements these specific rules. Results do not establish arbitrary ontology construction, full RDF reasoning, native AppWorld performance, or production safety. See [the protocol definitions and limitations](README.md).
'''
(HERE / "RESULTS.md").write_text(text)
print(text)

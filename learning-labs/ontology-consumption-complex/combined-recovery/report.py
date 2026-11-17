import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
run=Path(sys.argv[1]).resolve();rec=json.loads((run/'receipt.json').read_text())
if any(c['status']=='IN_FLIGHT' for c in rec['calls']):raise SystemExit('Run still active')
rows=[]; totals={};models=set();steps=[]
(run/'contexts').mkdir(exist_ok=True)
for c in rec['calls']:
 phase=c['phase']; t=totals.setdefault(phase,{'calls':0,'main_input':0,'main_generated':0,'router':0,'total':0,'reported_calls':0});t['calls']+=1
 stats=c.get('cli_response',{}).get('stats',{}).get('models',{})
 if stats:t['reported_calls']+=1
 for model,v in stats.items():
  models.add(model);t['total']+=v.get('tokens',{}).get('total',0)
  for role,item in v.get('roles',{}).items():
   tokens=item.get('tokens',{})
   if role=='main':t['main_input']+=tokens.get('input',0);t['main_generated']+=tokens.get('candidates',0)+tokens.get('thoughts',0)
   elif role=='utility_router':t['router']+=tokens.get('total',0)
 name=f"call-{c['step']:02}.txt";(run/'contexts'/name).write_text(c['submitted_prompt'])
 msg=c.get('parsed',{})
 steps.append(f"| {c['step']} | {phase} | `{msg.get('name',msg.get('type',c['status']))}` | {json.dumps(msg.get('arguments',msg.get('panel')))} | [context](results/{run.name}/contexts/{name}) |")
for phase,t in totals.items():
 vals=[f"{t[k]:,}" if t['reported_calls'] else 'unreported' for k in ('main_input','main_generated','router','total')]
 if t['reported_calls']<t['calls']:vals=[v+' (partial)' for v in vals]
 rows.append(f"| {phase} | {t['calls']} | {' | '.join(vals)} |")
(run/'metrics.json').write_text(json.dumps(totals,indent=2)+'\n')
text=f'''# Combined ontology consumption and recovery: actual Gemini run

Status: **{rec['status']}**. Deterministic recovery check: **{rec['passed']}**. Models reported: {', '.join(sorted(models))}.

The original task, all 53 initial facts, and ontology approval-complex-v1 are unchanged. This run combines a small catalog, on-demand definition retrieval, graph queries/traversal, a typed valid-panel function, candidate checks, and a mandatory runtime gate. Available interfaces are not necessarily all selected by the model.

Unlike the six independent runs, the runtime requires definition inspection and a current find_valid_panels receipt before accepting a finish. After the first correct initial proposal it revokes del-Vera before execution, advances the graph from 7 to 8, and gives the rejection back to Gemini. The original snapshot remains in context, explicitly superseded by new observations. A new current computation is required. We do not add a replacement candidate or relax constraints.

## Usage

| Phase | CLI calls | Main input | Output + thinking | Router | All-model total |
| --- | ---: | ---: | ---: | ---: | ---: |
'''+ '\n'.join(rows)+f'''

All reported totals across phases: **{sum(t['total'] for t in totals.values()):,} tokens**. These include fresh CLI routing and repeated context on every continuation. Unknown usage is not zero. Recovery includes every call after the revocation feedback, not the initial proposal call. [Machine-readable usage](results/{run.name}/metrics.json).

## Actual sequence

| Call | Phase | Model request | Arguments or proposed panel | Exact submitted prompt |
| --- | --- | --- | --- | --- |
'''+ '\n'.join(steps)+f'''

## Recorded outcomes

- Initial answer: `{json.dumps(rec.get('initial_answer'))}`.
- Initial eligibility gate before mutation: `{json.dumps(rec.get('prechange_gate'))}`.
- Gate after revocation, before execution: `{json.dumps(rec.get('revocation_gate'))}`.
- Recovery answer: `{json.dumps(rec.get('recovery_answer'))}`.
- Recovery component scores: `{json.dumps(rec.get('recovery_score'))}`.
- External writes: **{rec['external_writes']}**.

The unchanged fixture has no valid panel after revocation. A correct null result is safe recovery to a blocked task, not successful approval. An old proposal cannot execute. Null never grants execution permission. A current deterministic search returning no panels supports this conclusion over the complete fixture; a short citation list alone does not prove absence.

[Original model envelopes, prompts, interface responses and rejection feedback](results/{run.name}/receipt.json). [Frozen manifest and hashes](results/{run.name}/manifest.json).

## Limits

One synthetic teaching run, no AppWorld evaluation, external deployment, learned ontology change, or Gemini judge/proposer cycle. Gemini is the explicitly requested experimental participant; production roles are unchanged. Definitions and functions are hand-authored. This measures model recovery with a strong runtime protocol, not unaided model detection of stale facts. Both initial observations and recovery are stored in the same growing history. Costs are not directly comparable to single-phase runs. No automatic run retries are performed; failures remain in the evidence.
'''
(HERE/'RESULTS.md').write_text(text);print(text)

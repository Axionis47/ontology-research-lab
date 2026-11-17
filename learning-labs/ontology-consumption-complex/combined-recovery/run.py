"""Combined ontology access with an actual model recovery turn after revocation."""
import sys,json,hashlib,shutil,tomllib,subprocess
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
PARENT=HERE.parent
sys.path.insert(0,str(PARENT))
import engine as e
import run as helpers
h=helpers.h
ROOT=PARENT.parents[1]
MODES={name:mode for mode in ('inspect','query','function','check') for name in e.interfaces(mode)}

def prerequisites(history,revision):
    schema=any('eligibility' in t.get('runtime_result',{}).get('definitions',{}) for t in history)
    fresh=any(t.get('runtime_result',{}).get('graph_revision')==revision and t.get('model_request',{}).get('name')=='find_valid_panels' for t in history)
    return schema and fresh

def main():
    live='--live' in sys.argv
    world=json.loads((PARENT/'facts.json').read_text()); ontology=json.loads((PARENT/'ontology.json').read_text())
    base=e.payload('inspect',world,ontology)
    base['interfaces']={name:contract for mode in ('inspect','query','function','check') for name,contract in e.interfaces(mode).items()}
    base['consumption_protocol']='Inspect eligibility definitions before finishing. Use queries or traversal to inspect evidence, find_valid_panels to compute candidates, and check_panels to diagnose proposed combinations as useful. A finish requires an eligibility inspection and find_valid_panels result at the current revision. Return one JSON call or finish per turn. All interface results are scoped to their graph_revision. On rejection, acquire current evidence and recompute. Do not change the task or rules. If no valid panel exists, finish with panel=null, all rule IDs, current version/revision, and known evidence IDs. A null result is a blocked task, never permission to execute.'
    cfg_path=ROOT/'config/models.toml'; cfg=tomllib.loads(cfg_path.read_text())['gemini']; policy=ROOT/cfg['policy']
    executable=shutil.which(cfg['executable'])
    out=HERE/'results'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'); out.mkdir(parents=True)
    workspace=out/'empty-workspace'; workspace.mkdir()
    rec={'status':'PREPARED','initial_payload':base,'calls':[],'history':[],'phase':'initial','passed':False,'external_writes':0}
    manifest={'task_hash':e.sha(base['task']),'initial_facts_hash':e.sha(base['facts']),'sources':{str(p.relative_to(ROOT)):h.digest(p) for p in [Path(__file__),PARENT/'engine.py',PARENT/'facts.json',PARENT/'ontology.json',PARENT/'oracle.json',cfg_path,policy]},'max_calls':12,'timeout_seconds':cfg['timeout_seconds'],'model':'configured CLI, no override','retries':0,'appworld_runs':0,'mutation':'revoke del-Vera exactly once after first correct initial proposal, before execution','initial_facts_in_context':'unchanged revision 7 snapshot; newer observations supersede it','cli_version':subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=30).stdout.strip() if live and executable else None}
    h.save(out/'manifest.json',manifest); h.save(out/'receipt.json',rec)
    print('Evidence:',out,flush=True)
    if not live:return
    rec['status']='CALL_LIMIT'
    for step in range(12):
        prompt='Solve the approval task using only supplied facts, definitions and application interfaces. Return one JSON object without Markdown. Do not use CLI builtin tools, files, or external state.\n'+json.dumps({'context':base,'history':rec['history']},separators=(',',':'))
        ev={'step':step+1,'phase':rec['phase'],'submitted_prompt':prompt,'user_chars':len(prompt),'status':'IN_FLIGHT'}; rec['calls'].append(ev); h.save(out/'receipt.json',rec)
        if not executable:rec['status']='CLI_NOT_FOUND';break
        cmd=[executable,'--extensions','none','--allowed-mcp-server-names','model-check-no-servers','--policy',str(policy),'--output-format','json','--skip-trust','--prompt',prompt]
        code,stdout,stderr=h.invoke(cmd,workspace,cfg['timeout_seconds']); ev.update(exit_code=code,stderr_sha256=hashlib.sha256(stderr.encode()).hexdigest())
        if code:ev['status']=rec['status']=h.failure_category(code,stderr);break
        try:
            env=json.loads(stdout); ev['cli_response']=env
            if env.get('error') or not env.get('stats',{}).get('models') or env.get('stats',{}).get('tools',{}).get('totalCalls',0):raise ValueError('CLI error, missing identity or unexpected tool use')
            msg=json.loads(env['response']); ev.update(status='RECEIVED',parsed=msg)
            if not isinstance(msg,dict):raise ValueError('Expected object')
            if msg.get('type')=='finish':
                scored=e.score_details(msg,world,ontology)
                if not prerequisites(rec['history'],world['revision']):
                    result={'admitted':False,'reason':'PROTOCOL_PRECONDITION','required':'Inspect eligibility and obtain find_valid_panels at the current revision','graph_revision':world['revision']}
                elif not scored['passed']:
                    result={'admitted':False,'reason':'INVALID_FINISH','checks':scored,'graph_revision':world['revision']}
                elif rec['phase']=='initial':
                    rec['initial_answer']=msg; rec['initial_score']=scored; rec['prechange_gate']=e.gate(msg,world,ontology)
                    world=e.revoked(world); h.save(out/'revoked-world.json',world)
                    rec['revocation_gate']=e.gate(msg,world,ontology)
                    result={**rec['revocation_gate'],'graph_revision':world['revision'],'ontology_version':ontology['version'],'event':'Delegation del-Vera was revoked before execution. No approval was executed.','changed_ids':['del-Vera'],'invalidated':'Previously derived panels and eligibility depending on del-Vera; refresh affected evidence and recompute before finishing.'}
                    rec['phase']='recovery'
                else:
                    rec['recovery_answer']=msg;rec['recovery_score']=scored
                    rec['passed']=msg['panel'] is None and not e.valid_panels(world) and not rec['revocation_gate']['admitted']
                    rec['status']='RECOVERED_BLOCKED' if rec['passed'] else 'RECOVERY_FAILED'
                    rec['history'].append({'model_request':msg,'runtime_result':{'task_status':'BLOCKED_NO_VALID_PANEL','admitted':False,'graph_revision':world['revision']}})
                    print(step+1,rec['phase'],rec['status'],flush=True);break
            else:
                try:result=e.execute(msg,MODES.get(msg.get('name')),world,ontology)
                except ValueError as error:result={'error':str(error),'graph_revision':world['revision']}
            rec['history'].append({'model_request':msg,'runtime_result':result})
            print(step+1,ev['phase'],msg.get('name',msg.get('type')),result.get('reason',''),flush=True)
        except (ValueError,KeyError,TypeError) as error:
            ev.update(status='INVALID_RESPONSE',reason=str(error),raw_stdout=stdout);rec['status']='INVALID_RESPONSE';break
        h.save(out/'receipt.json',rec)
    h.save(out/'receipt.json',rec)
    print('Final:',rec['status'],flush=True)
    return 0 if rec['passed'] else 1
if __name__=='__main__':sys.exit(main())

import unittest,json,sys,importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('recovery_runner',HERE/'run.py'); r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
e=r.e
class RecoveryTests(unittest.TestCase):
 def setUp(self):
  self.w=json.loads((HERE.parent/'facts.json').read_text());self.o=json.loads((HERE.parent/'ontology.json').read_text())
 def test_revocation_removes_only_valid_pair_and_stale_proof(self):
  panels=e.valid_panels(self.w);self.assertEqual([p['panel'] for p in panels],[{'ops':'Vera','security':'Tao'}])
  a={'type':'finish','panel':panels[0]['panel'],'proof_ids':panels[0]['proof_ids'],'rule_ids':e.RULE_IDS,'graph_revision':7,'ontology_version':self.o['version']}
  changed=e.revoked(self.w)
  self.assertTrue(e.gate(a,self.w,self.o)['admitted']);self.assertFalse(e.gate(a,changed,self.o)['admitted']);self.assertFalse(e.gate({**a,'graph_revision':8},changed,self.o)['admitted']);self.assertEqual(e.valid_panels(changed),[])
  self.assertTrue(e.score({**a,'panel':None,'proof_ids':['del-Vera'],'graph_revision':8},changed,self.o))
  self.assertTrue(e.index(self.w)['del-Vera']['active'])
 def test_current_computation_required_after_rejection(self):
  history=[{'runtime_result':{'definitions':{'eligibility':{}}}},{'model_request':{'name':'find_valid_panels'},'runtime_result':{'graph_revision':7}}]
  self.assertTrue(r.prerequisites(history,7));self.assertFalse(r.prerequisites(history,8))
  history.append({'model_request':{'name':'find_valid_panels'},'runtime_result':{'graph_revision':8}})
  self.assertTrue(r.prerequisites(history,8))
if __name__=='__main__':unittest.main()

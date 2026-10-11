import json,sys,tempfile,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from workflow_engine import Engine,ContractError
results=[]
class Fixture:
 def __init__(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'state.sqlite';self.e=Engine(self.path);self.n=0
  self.call('create',dict(goal='independent synthetic audit',scope=['test data'],constraints=['no external calls'],owner='owner',acceptance=['report']),0)
 def call(self,action,payload,rev=None,op=None):
  self.n+=1
  return self.e.apply('j', self.e.job('j')['revision'] if rev is None else rev,op or 'op'+str(self.n),action,payload)
 def task(self,key,deps=[]):return self.call('add_task',dict(id=key,goal='test',owner='owner',acceptance=['pass'],deps=deps))
 def verify(self,key,cp):return self.call('verify',dict(task_id=key,id=cp,verifier='independent reviewer',evidence=['test:'+key],checks={'pass':True}))
 def close(self):self.e.close();self.tmp.cleanup()
def run(name,fn):
 f=Fixture()
 try: detail=fn(f);results.append(dict(item=name,status='VERIFIED',evidence=detail or 'assertions passed'))
 except Exception as e:results.append(dict(item=name,status='FAILED',evidence=type(e).__name__+': '+str(e)))
 finally:f.close()
def rejected(f,action,payload,pattern,**kw):
 rev=f.e.job('j')['revision'];count=f.e.db.execute('select count(*) from events').fetchone()[0]
 try:f.call(action,payload,**kw)
 except ContractError as e:
  assert pattern in str(e),(pattern,str(e))
 else:raise AssertionError('invalid request accepted')
 assert f.e.job('j')['revision']==rev
 assert f.e.db.execute('select count(*) from events').fetchone()[0]==count
def replay(f):
 p=dict(id='a',goal='test',owner='owner',acceptance=['pass'],deps=[]);a=f.call('add_task',p,rev=1,op='fixed');f.task('unrelated')
 assert a==f.call('add_task',p,rev=1,op='fixed')
 rejected(f,'add_task',dict(p,goal='conflict'),'operation payload conflict',rev=1,op='fixed')
 rejected(f,'update',dict(task_id='a'),'revision conflict',rev=1)
 return 'Same operation returns original revision after later write; changed retry and stale revision reject atomically.'
def restart(f):
 f.task('a');f.verify('a','cpa');before=f.e.recover('j');f.e.close();f.e=Engine(f.path);assert before==f.e.recover('j')
 script=ROOT/'tools/workflow_engine.py';p=subprocess.run([sys.executable,str(script),'--db',str(f.path),'recover','j'],capture_output=True,text=True,check=True)
 assert json.loads(p.stdout)==before
 return 'New Engine instance and separate CLI process recover identical state.'
def guards(f):
 f.task('a');f.task('b',['a'])
 base=dict(task_id='a',id='cp',verifier='reviewer',evidence=['proof'],checks={'pass':True})
 rejected(f,'verify',dict(base,verifier='owner'),'independent verifier')
 rejected(f,'verify',dict(base,evidence=[]),'evidence')
 rejected(f,'verify',dict(base,checks={'pass':False}),'acceptance')
 rejected(f,'verify',dict(base,checks={'pass':True,'extra':True}),'acceptance')
 rejected(f,'verify',dict(base,task_id='b'),'unmet dependencies')
 rejected(f,'update',dict(task_id='a',status='verified'),'completion')
 return 'Self verification, empty evidence, false/extra checks, unmet prerequisite and direct verified status rejected.'
def chain(f):
 f.task('a');f.task('b',['a']);f.task('c',['b']);f.task('other')
 f.call('update',dict(task_id='a',outputs=['original.txt'],attempt='first'))
 for k in ['a','b','c','other']:f.verify(k,'cp_'+k)
 old=[tuple(r) for r in f.e.db.execute('select id,payload from checkpoints order by id')]
 events=f.e.db.execute('select count(*) from events').fetchone()[0]
 f.call('correct',dict(task_id='a',id='corr',reason='source correction'))
 p=f.e.recover('j')
 for k in ['a','b','c']:assert p['tasks'][k]['status']=='needs_rechecking'
 assert p['tasks']['other']['status']=='verified'
 assert p['tasks']['a']['outputs']==['original.txt'] and len(p['tasks']['a']['attempts'])==1
 assert [tuple(r) for r in f.e.db.execute('select id,payload from checkpoints order by id')]==old
 assert [(r['id'],r['valid']) for r in f.e.db.execute('select id,valid from checkpoints order by id')]==[('cp_a',0),('cp_b',0),('cp_c',0),('cp_other',1)]
 assert f.e.db.execute('select count(*) from events').fetchone()[0]==events+1
 assert p['next_permitted_action']['task_id']=='a';assert p['pending_dependencies']['c']==['b']
 rejected(f,'update',dict(task_id='a',checkpoint_id='cp_a'),'stale checkpoint')
 f.verify('a','newa');f.verify('b','newb');assert len(f.e.recover('j')['active_corrections'])==1
 f.verify('c','newc');assert not f.e.recover('j')['active_corrections']
 return '3-hop invalidation; unrelated proof stays valid; historical proof payloads/attempts/output remain; correction clears only after all 3 reverify.'
def dag(f):
 f.task('a');f.task('b',['a'])
 rejected(f,'dependencies',dict(task_id='a',deps=['b']),'cycle')
 rejected(f,'add_task',dict(id='bad',goal='x',owner='owner',acceptance=['pass'],deps=['missing']),'unknown dependency')
 rejected(f,'dependencies',dict(task_id='a',deps=['a']),'cycle')
 return 'Cycle, self-cycle and missing dependency reject atomically.'
def reopen(f):
 f.task('a');f.task('b',['a']);f.verify('a','cpa');f.verify('b','cpb');f.call('update',dict(task_id='a',attempt='reopen'))
 p=f.e.recover('j');assert p['tasks']['b']['status']=='needs_rechecking' and p['last_valid_verified_checkpoint'] is None
 return 'Reopening verified ancestor invalidates descendant proof.'
def depchange(f):
 f.task('a');f.task('b',['a']);f.task('c',['b']);[f.verify(k,'cp'+k) for k in ['a','b','c']]
 f.call('dependencies',dict(task_id='b',deps=[]));p=f.e.recover('j');assert p['tasks']['a']['status']=='verified'
 assert p['tasks']['b']['status']=='needs_rechecking' and p['tasks']['c']['status']=='needs_rechecking'
 return 'Changed prerequisite invalidates target and descendants, preserves ancestor.'
def stale(f):
 f.task('a');f.verify('a','cpa');f.task('other');rejected(f,'update',dict(task_id='a',checkpoint_id='cpa'),'stale checkpoint')
 return 'Older valid checkpoint cannot drive update after unrelated revision.'
def malformed_evidence(f):
 f.task('a')
 p=dict(task_id='a',id='badcp',verifier={'arbitrary':'object'},evidence=True,checks={'pass':True})
 rejected(f,'verify',p,'')
 return 'Malformed named verifier/evidence rejected.'
def blankrefs(f):
 f.task('a');rejected(f,'verify',dict(task_id='a',id='badcp',verifier='   ',evidence=[''],checks={'pass':True}),'')
 return 'Blank verifier and blank evidence reference rejected.'
def malformed_acceptance(f):
 rejected(f,'add_task',dict(id='a',goal='x',owner='owner',acceptance='pass',deps=[]),'')
 return 'String acceptance rejected.'
def boolrev(f):
 f.task('a');rejected(f,'update',dict(task_id='a'),'revision',rev=True)
 return 'Boolean revision rejected.'
def correction_snapshot(f):
 f.task('a');f.task('b',['a']);f.verify('a','cpa');f.verify('b','cpb')
 f.call('correct',dict(task_id='a',id='corr',reason='source correction'))
 f.call('dependencies',dict(task_id='b',deps=[]));f.verify('a','newa')
 packet=f.e.recover('j')
 assert packet['tasks']['b']['status']=='needs_rechecking'
 assert len(packet['active_corrections'])==1, 'Correction cleared although originally affected b remains needs_rechecking with invalid old proof.'
 return 'Original correction affected set retained across later DAG edits.'
for name,fn in [('revision_idempotency_conflicting_retry',replay),('restart_new_process',restart),('proof_guards',guards),('transitive_correction_oldproof_preserved',chain),('dag_atomic_rollback',dag),('reopening_invalidation',reopen),('prerequisite_edit_invalidation',depchange),('stale_checkpoint',stale),('malformed_verifier_evidence_types',malformed_evidence),('blank_evidence_verifier',blankrefs),('malformed_acceptance_type',malformed_acceptance),('boolean_revision',boolrev),('correction_affected_set_survives_dag_edit',correction_snapshot)]:run(name,fn)
out=dict(scope='independent local synthetic workflow tests; no service/UI/app writes',engine_sha256=hashlib.sha256((ROOT/'tools/workflow_engine.py').read_bytes()).hexdigest(),results=results)
(ROOT/'reports/independent-foundation-workflow.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2));sys.exit(1 if any(r['status']=='FAILED' for r in results) else 0)

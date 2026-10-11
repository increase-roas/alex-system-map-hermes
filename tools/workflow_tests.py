"""Behavior tests for local synthetic workflow contract; stdlib only."""
import tempfile
import json
import subprocess
import sys
import unittest
from pathlib import Path
from workflow_engine import Engine, ContractError

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.path = str(Path(self.tmp.name) / 'state.sqlite')
        self.e = Engine(self.path); self.n = 0
        self.apply('create', dict(goal='Synthetic lamp audit', scope=['fixture sample'], constraints=['no services'], owner='maker', acceptance=['report']))
    def tearDown(self): self.e.close(); self.tmp.cleanup()
    def apply(self, action, payload, rev=None, op=None):
        self.n += 1
        return self.e.apply(
            'demo',
            rev if rev is not None else (0 if action == 'create' else self.e.job('demo')['revision']),
            op or f'op{self.n}',
            action,
            payload,
            actor_owner='maker',
        )
    def task(self, identity='a', deps=None):
        return self.apply('add_task', dict(id=identity, goal='Inspect synthetic sample', owner='maker', acceptance=['file:synthetic.txt non-empty'], deps=deps or []))
    def verify(self, identity='a', cp='cp1', verifier='reviewer', evidence=None):
        return self.apply('verify', dict(task_id=identity, id=cp, verifier=verifier, evidence=evidence if evidence is not None else ['synthetic test fixture'], checks={'file:synthetic.txt non-empty': True}))
    def test_cli_init_create_recover(self):
        script = str(Path(__file__).with_name('workflow_engine.py'))
        db = str(Path(self.tmp.name) / 'cli.sqlite')
        request = str(Path(__file__).parent.parent / 'examples' / 'workflow-create-request.json')
        def cli(*args):
            result = subprocess.run([sys.executable, script, '--db', db, *args], check=True, capture_output=True, text=True)
            return json.loads(result.stdout)
        self.assertTrue(cli('init')['initialized'])
        self.assertEqual(1, cli('apply', request)['revision'])
        self.assertTrue(cli('recover', 'cli-synthetic-job')['synthetic_only'])

    def test_malformed_requests_leave_database_unchanged(self):
        self.task()
        revision = self.e.job('demo')['revision']
        create = dict(goal='g',scope=['local'],constraints=[],owner='maker',acceptance=['check'])
        task = dict(id='new',goal='g',owner='maker',acceptance=['check'],deps=[])
        proof = dict(id='proof',task_id='a',verifier='reviewer',evidence=['ref'],checks={'file:synthetic.txt non-empty':True})
        requests = [
            ('create', dict(create,goal=''), 'newjob', 0),
            ('create', dict(create,owner=''), 'newjob', 0),
            ('create', dict(create,acceptance='check'), 'newjob', 0),
            ('create', dict(create,scope='local'), 'newjob', 0),
            ('create', dict(create,constraints={}), 'newjob', 0),
            ('create', dict(create,goal='REQUIRED'), 'newjob', 0),
            ('create', create, 'newjob', False),
            ('add_task', dict(task,id=[]), 'demo', revision),
            ('add_task', dict(task,deps=['a','a']), 'demo', revision),
            ('add_task', dict(task,acceptance=[]), 'demo', revision),
            ('add_task', dict(task,status='verified'), 'demo', revision),
            ('add_task', dict(task,id='build-TASK_ID'), 'demo', revision),
            ('verify', dict(proof,evidence='reference'), 'demo', revision),
            ('verify', dict(proof,checks={'file:synthetic.txt non-empty':1}), 'demo', revision),
            ('verify', dict(proof,verifier=123), 'demo', revision),
            ('update', ['bad'], 'demo', revision),
            ('update', dict(task_id='a'), [], revision),
        ]
        def snapshot():
            return {table:[tuple(row) for row in self.e.db.execute('SELECT * FROM '+table)] for table in ('jobs','tasks','checkpoints','corrections','events','operations')}
        before = snapshot()
        for action,payload,job,rev in requests:
            with self.subTest(action=action,payload=payload):
                with self.assertRaises(ContractError): self.e.apply(job,rev,'malformed-operation',action,payload)
                self.assertEqual(before,snapshot())
        for op in ('',None,[]):
            with self.assertRaises(ContractError): self.e.apply('demo',revision,op,'update',dict(task_id='a'))
            self.assertEqual(before,snapshot())

    def test_restart_and_recovery(self):
        self.task(); self.verify(); before = self.e.recover('demo'); self.e.close(); self.e = Engine(self.path)
        self.assertEqual(before, self.e.recover('demo')); self.assertEqual('cp1', before['last_valid_verified_checkpoint']['id'])
    def test_revision_and_idempotency(self):
        payload=dict(id='a',goal='g',owner='maker',acceptance=['check'],deps=[])
        first=self.apply('add_task',payload,rev=1,op='stable')
        self.assertEqual(first,self.apply('add_task',payload,rev=1,op='stable'))
        with self.assertRaisesRegex(ContractError,'operation payload conflict'): self.apply('add_task',dict(payload,goal='changed'),rev=1,op='stable')
        with self.assertRaisesRegex(ContractError,'revision conflict'): self.apply('update',dict(task_id='a'),rev=1)
        self.assertEqual(2,self.e.job('demo')['revision'])
    def test_verification_guardrails(self):
        self.task(); self.task('b',['a'])
        with self.assertRaisesRegex(ContractError,'unmet dependencies'): self.verify('b','cpb')
        with self.assertRaisesRegex(ContractError,'independent verifier'): self.verify(verifier='maker')
        with self.assertRaisesRegex(ContractError,'evidence'): self.verify(evidence=[])
        with self.assertRaisesRegex(ContractError,'acceptance'): self.apply('verify',dict(task_id='a',id='bad',verifier='reviewer',evidence=['e'],checks={}))
        with self.assertRaisesRegex(ContractError,'completion'): self.apply('update',dict(task_id='a',status='verified'))
        self.verify(); self.verify('b','cpb'); self.assertIsNone(self.e.recover('demo')['next_permitted_action'])
    def test_corrections_preserve_history_and_recheck_descendants(self):
        self.task(); self.task('b',['a']); self.apply('update',dict(task_id='a',attempt='first try',outputs=['artifact']))
        self.verify(); self.verify('b','cpb')
        self.apply('correct',dict(id='correction1',task_id='a',reason='Synthetic fixture changed'))
        packet=self.e.recover('demo')
        self.assertIsNone(packet['last_valid_verified_checkpoint']); self.assertEqual(['a'],packet['pending_dependencies']['b'])
        self.assertEqual('needs_rechecking',packet['tasks']['b']['status']); self.assertEqual(1,len(packet['tasks']['a']['attempts']))
        with self.assertRaisesRegex(ContractError,'stale checkpoint'): self.apply('update',dict(task_id='a',checkpoint_id='cp1'))
        self.verify(cp='cp2'); self.assertEqual(1,len(self.e.recover('demo')['active_corrections']))
        self.verify('b','cpb2'); self.assertEqual([],self.e.recover('demo')['active_corrections'])
        self.assertEqual(4,self.e.db.execute('SELECT count(*) FROM checkpoints').fetchone()[0])
    def test_cycles_and_atomic_rollback(self):
        self.task(); self.task('b',['a']); revision=self.e.job('demo')['revision']
        count=self.e.db.execute('SELECT count(*) FROM events').fetchone()[0]
        with self.assertRaisesRegex(ContractError,'cycle'): self.apply('dependencies',dict(task_id='a',deps=['b']))
        self.assertEqual([],self.e.tasks('demo')['a']['deps']); self.assertEqual(revision,self.e.job('demo')['revision'])
        self.assertEqual(count,self.e.db.execute('SELECT count(*) FROM events').fetchone()[0])
        with self.assertRaisesRegex(ContractError,'unknown dependency'): self.task('unknown',['missing'])
        self.assertNotIn('unknown',self.e.tasks('demo'))
    def test_stale_checkpoint_after_unrelated_revision(self):
        self.task(); self.verify(); self.task('b')
        with self.assertRaisesRegex(ContractError,'stale checkpoint'): self.apply('update',dict(task_id='a',checkpoint_id='cp1'))
    def test_reopened_task_invalidates_prior_proof(self):
        self.task(); self.verify()
        self.apply('update',dict(task_id='a',checkpoint_id='cp1',attempt='reopened'))
        self.assertIsNone(self.e.recover('demo')['last_valid_verified_checkpoint'])

    def test_correction_retains_original_affected_tasks_after_dependency_edit(self):
        self.task(); self.task('b', ['a']); self.verify(); self.verify('b', 'cpb')
        self.apply('correct', dict(id='correction1', task_id='a', reason='fixture changed'))
        self.apply('dependencies', dict(task_id='b', deps=[]))
        self.verify(cp='cp2')
        packet = self.e.recover('demo')
        self.assertEqual(['a', 'b'], packet['active_corrections'][0]['affected_task_ids'])
        self.assertEqual('needs_rechecking', packet['tasks']['b']['status'])
        self.verify('b', 'cpb2')
        self.assertEqual([], self.e.recover('demo')['active_corrections'])

    def test_active_correction_captures_new_descendants_before_edge_removal(self):
        self.task(); self.verify()
        self.apply('correct', dict(id='correction1', task_id='a', reason='fixture changed'))
        self.task('b', ['a'])
        self.apply('dependencies', dict(task_id='b', deps=[]))
        self.verify(cp='cp2')
        self.assertEqual(['a', 'b'], self.e.recover('demo')['active_corrections'][0]['affected_task_ids'])
        self.verify('b', 'cpb2')
        self.assertEqual([], self.e.recover('demo')['active_corrections'])

    def test_globally_unique_ids(self):
        self.task()
        with self.assertRaisesRegex(ContractError,'ID already exists'): self.task('a')
        with self.assertRaisesRegex(ContractError,'ID already exists'): self.verify(cp='a')

if __name__ == '__main__': unittest.main(verbosity=2)

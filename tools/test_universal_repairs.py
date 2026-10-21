"""Disposable native-boundary fixtures for the durable coordinator."""
import json
import subprocess
import tempfile
import sys
import time
import multiprocessing
import os
import fcntl
import unittest
from pathlib import Path
from repair_contracts import RepairError
from repair_registry import RepairRegistry
from universal_repairs import Coordinator


class Files:
    adapter_id = 'fixture'
    version = '1'

    def __init__(self, root):
        self.root = root
        self.fail_backup = None
        self.lose_response = None
        self.crash_after_effect = False
        self.crash_after_undo = False
        self.effects = []
        for name in ('alpha', 'beta'):
            if not (root / name).exists():
                (root / name).write_text('old')

    def discover(self):
        return [dict(id=n, adapter_id=self.adapter_id, category='fixture', owner='fixture', scope='local', identity={'object': n}, capabilities=['repair'], observed_at='now', evidence=[], limitations=[]) for n in ('alpha', 'beta')]

    def read(self, target):
        value = (self.root / target['id']).read_text()
        return {'fingerprint': value, 'version': '1', 'context_fingerprint': 'context', 'projection': {'text': value}}

    def prepare(self, target, snapshot, proposal):
        return dict(action='replace', candidate=proposal['text'], expected_fingerprint=snapshot['fingerprint'], expected_version='1', context_fingerprint='context', checks=[], public_diff='old -> new')

    def prepare_bundle(self, operations, targets):
        return operations

    def preflight(self, target, operation):
        return {'ok': self.read(target)['fingerprint'] == operation['expected_fingerprint']}

    def backup(self, target, operation, backup_dir):
        if target['id'] == self.fail_backup:
            raise RuntimeError('secret-provider-token-must-not-leak')
        return {'before': (self.root / target['id']).read_text()}

    def apply(self, target, operation, backup):
        if not self.preflight(target, operation)['ok']:
            raise RepairError('stale')
        (self.root / target['id']).write_text(operation['candidate'])
        self.effects.append(target['id'])
        if self.crash_after_effect:
            raise SystemExit('worker interrupted')
        if target['id'] == self.lose_response:
            raise RuntimeError('secret-provider-token-must-not-leak')
        return {'after': operation['candidate']}

    def verify(self, target, operation, result):
        ok = self.read(target)['fingerprint'] == operation['candidate']
        return {'ok': ok, 'state': 'byte_verified' if ok else 'blocked', 'evidence': ['fixture-readback'], 'checks': [], 'limitations': []}

    def reconcile(self, target, operation, backup):
        value = self.read(target)['fingerprint']
        undo = operation.get('recovery_phase') == 'undo'
        landed = backup['before'] if undo else operation['candidate']
        unchanged = operation['candidate'] if undo else backup['before']
        return {'outcome': 'applied' if value == landed else 'not_applied' if value == unchanged else 'unknown', 'result': {'after': operation['candidate']}, 'evidence': ['fixture-readback']}

    def undo(self, target, operation, backup, applied):
        ok = self.read(target)['fingerprint'] == applied['after']
        if ok:
            (self.root / target['id']).write_text(backup['before'])
            self.effects.append('undo:' + target['id'])
            if self.crash_after_undo:
                raise SystemExit('undo interrupted')
        return {'ok': ok, 'state': 'undone' if ok else 'blocked', 'evidence': [], 'checks': [], 'limitations': []}


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.adapter = Files(self.root)
        self.registry = RepairRegistry()
        self.registry.register(self.adapter)
        self.service = Coordinator(self.root / 'state', self.registry)

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self):
        return self.service.freeze('fix both', [{'target_id': n, 'proposal': {'text': 'new'}} for n in ('alpha', 'beta')])

    def job(self):
        plan = self.plan()
        return self.service.approve(plan['plan_id'], plan['digest'])

    def test_last_backup_failure_has_zero_effects_and_safe_error(self):
        job = self.job()
        self.adapter.fail_backup = 'beta'
        result = self.service.run_job(job['job_id'])
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(self.adapter.effects, [])
        self.assertNotIn('secret-provider', json.dumps(result))
        self.assertEqual((self.root / 'alpha').read_text(), 'old')

    def test_stale_last_target_zero_effects(self):
        job = self.job()
        (self.root / 'beta').write_text('external')
        result = self.service.run_job(job['job_id'])
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(self.adapter.effects, [])

    def test_lost_response_reopen_reconcile_and_resume_without_duplicate(self):
        job = self.job()
        self.adapter.lose_response = 'alpha'
        result = self.service.run_job(job['job_id'])
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(self.adapter.effects, ['alpha'])
        reopened = Coordinator(self.root / 'state', self.registry)
        self.assertEqual(reopened.get_job(job['job_id'])['unknown_effect'], result['unknown_effect'])
        reconciled = reopened.reconcile(job['job_id'])
        self.assertEqual(reconciled['status'], 'queued')
        self.adapter.lose_response = None
        result = reopened.run_job(job['job_id'])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.adapter.effects, ['alpha', 'beta'])
        self.assertEqual(self.service.approve(job['plan_id'], job['digest'])['job_id'], job['job_id'])

    def test_reverse_undo_and_preserve_later_changed_target(self):
        job = self.job()
        self.service.run_job(job['job_id'])
        (self.root / 'alpha').write_text('later')
        result = self.service.undo(job['job_id'])
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(self.adapter.effects, ['alpha', 'beta', 'undo:beta'])
        self.assertEqual((self.root / 'alpha').read_text(), 'later')
        self.assertEqual((self.root / 'beta').read_text(), 'old')

    def test_plan_tamper_and_exact_digest_rejected(self):
        plan = self.plan()
        with self.assertRaises(RepairError):
            self.service.approve(plan['plan_id'], '0' * 64)
        path = self.root / 'state' / 'plans' / (plan['plan_id'] + '.json')
        value = json.loads(path.read_text())
        value['operations'][0]['candidate'] = 'forged'
        path.write_text(json.dumps(value))
        with self.assertRaises(RepairError):
            self.service.approve(plan['plan_id'], plan['digest'])
        self.assertEqual(self.adapter.effects, [])

    def test_process_loss_after_intent_requires_readback(self):
        job = self.job()
        self.adapter.crash_after_effect = True
        with self.assertRaises(SystemExit):
            self.service.run_job(job['job_id'])
        self.adapter.crash_after_effect = False
        reopened = Coordinator(self.root / 'state', self.registry)
        result = reopened.run_job(job['job_id'])
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(self.adapter.effects, ['alpha'])
        reopened.reconcile(job['job_id'])
        self.assertEqual(reopened.run_job(job['job_id'])['status'], 'completed')
        self.assertEqual(self.adapter.effects, ['alpha', 'beta'])

    def test_interrupted_undo_reconciles_inverse_without_reapplying(self):
        job = self.job()
        self.service.run_job(job['job_id'])
        self.adapter.crash_after_undo = True
        with self.assertRaises(SystemExit):
            self.service.undo(job['job_id'])
        self.adapter.crash_after_undo = False
        reopened = Coordinator(self.root / 'state', self.registry)
        self.assertEqual(reopened.undo(job['job_id'])['status'], 'unknown')
        self.assertEqual(reopened.reconcile(job['job_id'])['status'], 'undoing')
        self.assertEqual(reopened.undo(job['job_id'])['status'], 'undone')
        self.assertEqual(self.adapter.effects, ['alpha', 'beta', 'undo:beta', 'undo:alpha'])
        self.assertEqual((self.root / 'alpha').read_text(), 'old')
        self.assertEqual((self.root / 'beta').read_text(), 'old')

    def test_projection_derived_metadata_changes_do_not_block_conditional_undo(self):
        original_discover = self.adapter.discover
        def dynamic_discover():
            rows = original_discover()
            for row in rows:
                state = (self.root / row['id']).read_text()
                row['allowed_patch_paths'] = ['before.enabled'] if state == 'old' else ['after.enabled']
                row['related_target_ids'] = ['before-copy'] if state == 'old' else ['after-copy']
            return rows
        self.adapter.discover = dynamic_discover
        job = self.job()
        self.assertEqual(self.service.run_job(job['job_id'])['status'], 'completed')
        self.assertEqual(self.service.undo(job['job_id'])['status'], 'undone')
        self.assertEqual((self.root / 'alpha').read_text(), 'old')
        self.assertEqual((self.root / 'beta').read_text(), 'old')

    def test_identity_account_and_adapter_version_changes_still_reject_undo(self):
        for changed in ('identity', 'account', 'adapter_version'):
            with self.subTest(changed=changed):
                original_discover = self.adapter.discover
                original_version = self.adapter.version
                job = self.job()
                self.assertEqual(self.service.run_job(job['job_id'])['status'], 'completed')
                def changed_discover():
                    rows = original_discover()
                    if changed == 'identity':
                        rows[0]['identity'] = {'object': 'different-owner-object'}
                    elif changed == 'account':
                        rows[0]['account'] = 'different-login'
                    return rows
                self.adapter.discover = changed_discover
                if changed == 'adapter_version':
                    self.adapter.version = 'changed-version'
                with self.assertRaises(RepairError):
                    self.service.undo(job['job_id'])
                self.assertEqual((self.root / 'alpha').read_text(), 'new')
                self.adapter.discover = original_discover
                self.adapter.version = original_version
                self.service.undo(job['job_id'])

    def test_ai_context_cannot_change_during_analysis(self):
        def proposer(intent, sources):
            (self.root / 'alpha').write_text('changed during analysis')
            return {'proposals': [{'target_id': 'alpha', 'proposal': {'text': 'new'}}], 'checks': [], 'limitations': []}
        service = Coordinator(self.root / 'state', self.registry, proposer)
        with self.assertRaises(RepairError):
            service.propose(['alpha'], 'fix alpha')
        self.assertEqual(self.adapter.effects, [])

    def test_only_continuation_ready_preflight_gets_forward_marker(self):
        self.service.proposer = lambda intent, sources: {
            'proposals': [{'target_id': source['target']['id'], 'proposal': {'text': 'new'}} for source in sources]}
        plan = self.service.propose(['alpha', 'beta'], 'fix both')
        frozen = self.service.checked_plan(plan['plan_id'])
        self.assertEqual(set(frozen['reviewed_context']), {'alpha', 'beta'})
        calls = []
        preflight = self.adapter.preflight
        def observed_preflight(target, operation):
            calls.append((target['id'], operation.get('recovery_phase')))
            return preflight(target, operation)
        self.adapter.preflight = observed_preflight
        verify = self.adapter.verify
        self.adapter.verify = lambda *_: {'ok': False}
        job = self.service.approve(plan['plan_id'], plan['digest'])
        self.assertEqual(self.service.run_job(job['job_id'])['status'], 'blocked')
        self.assertTrue(calls)
        self.assertTrue(all(phase is None for _, phase in calls))
        self.adapter.verify = verify
        calls.clear()
        self.service.resume(job['job_id'])
        self.assertEqual(self.service.run_job(job['job_id'])['status'], 'completed')
        self.assertEqual(calls, [('beta', 'forward'), ('beta', None)])
        self.assertEqual(self.service.checked_plan(plan['plan_id']), frozen)
        self.assertTrue(all('recovery_phase' not in operation for operation in frozen['operations']))

    def test_first_blocked_undo_reconcile_keeps_inverse_direction(self):
        plan = self.service.freeze('fix alpha', [{'target_id': 'alpha', 'proposal': {'text': 'new'}}])
        job = self.service.approve(plan['plan_id'], plan['digest'])
        self.service.run_job(job['job_id'])
        (self.root / 'alpha').write_text('external')
        self.assertEqual(self.service.undo(job['job_id'])['status'], 'blocked')
        (self.root / 'alpha').write_text('new')
        reopened = Coordinator(self.root / 'state', self.registry)
        self.assertEqual(reopened.reconcile(job['job_id'])['status'], 'undoing')
        self.assertEqual(reopened.undo(job['job_id'])['status'], 'undone')
        self.assertEqual((self.root / 'alpha').read_text(), 'old')
        self.assertEqual(self.adapter.effects, ['alpha', 'undo:alpha'])

    def test_unchanged_reviewed_context_cannot_change_during_analysis(self):
        def proposer(intent, sources):
            (self.root / 'beta').write_text('changed during analysis')
            return {'proposals': [{'target_id': 'alpha', 'proposal': {'text': 'new'}}]}
        service = Coordinator(self.root / 'state', self.registry, proposer)
        with self.assertRaisesRegex(RepairError, 'analysis_context_changed'):
            service.propose(['alpha', 'beta'], 'fix alpha using beta')
        self.assertEqual(self.adapter.effects, [])

    def test_unchanged_reviewed_context_bound_before_first_effect(self):
        service = Coordinator(self.root / 'state', self.registry, lambda *_: {
            'proposals': [{'target_id': 'alpha', 'proposal': {'text': 'new'}}]})
        plan = service.propose(['alpha', 'beta'], 'fix alpha using beta')
        private = service.checked_plan(plan['plan_id'])
        self.assertIn('beta', private['reviewed_context'])
        self.assertNotIn('reviewed_context', plan)
        self.assertNotIn('projection', private['reviewed_context']['beta'])
        job = service.approve(plan['plan_id'], plan['digest'])
        (self.root / 'beta').write_text('changed after approval')
        self.assertEqual(service.run_job(job['job_id'])['status'], 'blocked')
        self.assertEqual(self.adapter.effects, [])

    def test_empty_ai_result_has_safe_diagnostics_and_no_plan(self):
        service = Coordinator(self.root / 'state', self.registry, lambda *_: {
            'proposals': [], 'diagnostics': {'stage': 'scenario', 'reason': 'schema'},
            'checks': [{'status': 'unavailable'}], 'limitations': ['No approvable proposal was produced.']})
        with self.assertRaisesRegex(RepairError, 'ai_no_proposals') as caught:
            service.propose(['alpha'], 'fix alpha')
        self.assertEqual(caught.exception.details['diagnostics'], {'stage': 'scenario', 'reason': 'schema'})
        self.assertFalse(list((self.root / 'state' / 'plans').glob('*.json')))

    def test_registered_canonical_gates_are_readonly_bound_context(self):
        original = self.adapter.discover
        def discover():
            rows = original()
            for row in rows:
                row['category'] = 'hook'
                row['identity'] = {'path': str(self.root / row['id']), 'home': str(self.root)}
            for identifier, relative in [('shared', '.agents/instructions/shared.md'), ('gates', '.agents/skills/alex-director/references/gates.md')]:
                row = dict(rows[0], id=identifier, category='rule', identity={'path': str(self.root / relative), 'home': str(self.root)})
                if identifier == 'gates':
                    row.update(context_only=True, capabilities=['read'], missing_capability='context_only_policy')
                rows.append(row)
            return rows
        self.adapter.discover = discover
        (self.root / 'shared').write_text('shared standing permissions')
        (self.root / 'gates').write_text('canonical security and spending gates')
        seen = []
        def proposer(intent, sources):
            seen.extend(sources)
            return {'proposals': [{'target_id': 'alpha', 'proposal': {'text': 'new'}}]}
        service = Coordinator(self.root / 'state', self.registry, proposer)
        plan = service.propose(['alpha'], 'fix the hook')
        self.assertEqual([source['target']['id'] for source in seen], ['alpha', 'shared', 'gates'])
        self.assertTrue(all(source['context_only'] for source in seen[1:]))
        self.assertNotIn('context_only', seen[0]['target'])
        self.assertNotIn('context_only', seen[1]['target'])
        self.assertEqual(seen[2]['target']['missing_capability'], 'context_only_policy')
        with self.assertRaisesRegex(RepairError, 'target_unavailable'):
            service.source('gates')
        self.assertEqual(set(service.checked_plan(plan['plan_id'])['reviewed_context']), {'alpha', 'shared', 'gates'})
        job = service.approve(plan['plan_id'], plan['digest'])
        (self.root / 'gates').write_text('updated canonical gates')
        self.assertEqual(service.run_job(job['job_id'])['status'], 'blocked')
        self.assertEqual(self.adapter.effects, [])
        service.proposer = lambda *_: {'proposals': [{'target_id': 'gates', 'proposal': {'text': 'new'}}]}
        with self.assertRaisesRegex(RepairError, 'proposal_scope_changed'):
            service.propose(['alpha'], 'fix the hook')

    def test_cross_adapter_local_sources_include_exact_home_canonical_context(self):
        from repair_local_adapters import LocalAdapter
        home = self.root.resolve()
        shared = home / '.agents/instructions/shared.md'
        gates = home / '.agents/skills/alex-director/references/gates.md'
        shared.parent.mkdir(parents=True)
        gates.parent.mkdir(parents=True)
        shared.write_text('Fix safe reversible owned changes.\n')
        gates.write_text('Ask Alex before security changes and spending money.\n')
        (gates.parent.parent / 'SKILL.md').write_text('# Director\nRun canonical approval gates.\n')
        for category in ('skill', 'hook', 'executable', 'skill_reference'):
            with self.subTest(category=category):
                registry = RepairRegistry()
                local = LocalAdapter(home)
                registry.register(local)
                class OwnedPlugin(Files):
                    adapter_id = 'owned-plugin-fixture'
                    def discover(plugin):
                        row = super().discover()[0]
                        row.update(category=category, identity={'path': str(home / 'alpha'), 'home': str(home)})
                        return [row]
                plugin = OwnedPlugin(home)
                registry.register(plugin)
                seen = []
                def proposer(intent, sources):
                    seen.extend(sources)
                    return {'proposals': [{'target_id': 'alpha', 'proposal': {'text': 'new'}}]}
                service = Coordinator(home / ('state-' + category), registry, proposer)
                plan = service.propose(['alpha'], 'fix selected owned source')
                self.assertEqual([source['target']['identity']['path'] for source in seen], [str(home / 'alpha'), str(shared), str(gates)])
                self.assertEqual(seen[0]['target']['adapter_id'], 'owned-plugin-fixture')
                self.assertTrue(all(source['target']['adapter_id'] == local.adapter_id and source['context_only'] for source in seen[1:]))
                self.assertEqual([operation['target_id'] for operation in plan['operations']], ['alpha'])
                self.assertEqual(len(service.checked_plan(plan['plan_id'])['reviewed_context']), 3)
                job = service.approve(plan['plan_id'], plan['digest'])
                gates.write_text('Updated security gate requires approval.\n')
                self.assertEqual(service.run_job(job['job_id'])['status'], 'blocked')
                self.assertEqual(plugin.effects, [])
                service.proposer = lambda *_: {'proposals': [{'target_id': seen[-1]['target']['id'], 'proposal': {'text': 'new'}}]}
                with self.assertRaisesRegex(RepairError, 'proposal_scope_changed'):
                    service.propose(['alpha'], 'fix selected owned source')
                gates.write_text('Ask Alex before security changes and spending money.\n')

    def test_public_plan_and_job_exclude_private_operation_and_backup(self):
        plan = self.plan()
        self.assertNotIn('candidate', json.dumps(plan))
        job = self.service.approve(plan['plan_id'], plan['digest'])
        result = self.service.run_job(job['job_id'])
        self.assertNotIn('backup', json.dumps(result))
        self.assertNotIn('"after"', json.dumps(result))


class DiscoveryAndCliTests(unittest.TestCase):
    def test_discovery_is_bounded_parallel_ordered_and_failure_isolated(self):
        registry = RepairRegistry()
        context = multiprocessing.get_context('fork')
        barrier = context.Barrier(4, timeout=2)
        lock = context.Lock()
        active = context.Value('i', 0)
        peak = context.Value('i', 0)
        class Adapter:
            version = '1'
            def __init__(self, index):
                self.index = index
                self.adapter_id = 'parallel_' + str(index)
            def discover(self):
                with lock:
                    active.value += 1
                    peak.value = max(peak.value, active.value)
                try:
                    if self.index < 4:
                        barrier.wait()
                    if self.index == 2:
                        raise RuntimeError('private failed read')
                    return [{'id': str(self.index), 'adapter_id': self.adapter_id}]
                finally:
                    with lock:
                        active.value -= 1
        for index in range(6):
            registry.register(Adapter(index))
        targets = registry.discover()
        self.assertEqual(peak.value, 4)
        self.assertEqual([target['adapter_id'] for target in targets.values()], ['parallel_' + str(index) for index in range(6)])
        self.assertEqual(sum('missing_capability' in target for target in targets.values()), 1)
        self.assertEqual(registry.limitations, ['parallel_2: discovery_unavailable'])

    def test_hanging_discovery_returns_healthy_rows_and_reaps_process_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = RepairRegistry(discovery_timeout=.35)
            class Hanging:
                adapter_id = 'hanging'
                version = '1'
                def discover(self):
                    with (root / 'worker.lock').open('w') as handle:
                        fcntl.flock(handle, fcntl.LOCK_EX)
                        (root / 'pid').write_text(str(os.getpid()))
                        # The descendant shares the discovery process group and lock.
                        descendant = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], pass_fds=(handle.fileno(),))
                        time.sleep(60)
            registry.register(Hanging())
            registry.register(Files(root))
            started = time.monotonic()
            targets = registry.discover()
            self.assertLess(time.monotonic() - started, 1.5)
            self.assertTrue({'alpha', 'beta'}.issubset(targets))
            self.assertEqual(sum(row.get('missing_capability') == 'discovery_unavailable' for row in targets.values()), 1)
            pid = int((root / 'pid').read_text())
            self.assertNotIn(pid, [child.pid for child in multiprocessing.active_children()])
            with (root / 'worker.lock').open('w') as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(handle, fcntl.LOCK_UN)
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_two_target_proposal_discovers_once_before_analysis_then_once_for_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            class CountedRegistry(RepairRegistry):
                count = 0
                def discover(self):
                    self.count += 1
                    return super().discover()
            registry = CountedRegistry()
            registry.register(Files(root))
            def proposer(intent, sources):
                self.assertEqual(registry.count, 1)
                self.assertEqual([source['target']['id'] for source in sources], ['alpha', 'beta'])
                return {'proposals': [{'target_id': source['target']['id'], 'proposal': {'text': 'new'}} for source in sources], 'checks': [], 'limitations': []}
            service = Coordinator(root / 'state', registry, proposer)
            plan = service.propose(['alpha', 'beta'], 'fix both')
            self.assertEqual(len(plan['operations']), 2)
            self.assertEqual(registry.count, 2)

    def test_one_unavailable_adapter_preserves_working_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = RepairRegistry()
            registry.register(Files(root))
            class Unavailable:
                adapter_id = 'provider_fixture'
                version = '1'
                def discover(self):
                    raise RuntimeError('secret-provider-response')
            registry.register(Unavailable())
            inventory = Coordinator(root / 'state', registry).discover()
            self.assertTrue({'alpha', 'beta'}.issubset({row['id'] for row in inventory['targets']}))
            unavailable = [row for row in inventory['targets'] if row.get('missing_capability')]
            self.assertEqual(len(unavailable), 1)
            self.assertEqual(unavailable[0]['capabilities'], [])
            self.assertNotIn('secret-provider', json.dumps(inventory))
            self.assertTrue(inventory['limitations'])

    def test_cli_missing_job_404_and_empty_ai_422_are_controlled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = Path(__file__).resolve().parent
            driver = root / 'driver.py'
            driver.write_text("import sys\nfrom pathlib import Path\nsys.path.insert(0," + repr(str(tools)) + ")\nimport universal_repairs as engine\nfrom test_universal_repairs import Files\nfrom repair_registry import RepairRegistry\nr=RepairRegistry();r.register(Files(Path("+repr(str(root))+")))\ndef proposer(*args):return {'proposals':[],'diagnostics':{'stage':'scenario','reason':'schema'},'checks':[{'status':'unavailable'}],'limitations':['No approvable proposal was produced.']}\nengine.service=lambda state:engine.Coordinator(state,r,proposer)\nengine.main()\n")
            def call(payload):
                response = subprocess.run([sys.executable, '-B', str(driver), '--state', str(root / 'state')], input=json.dumps(payload), capture_output=True, text=True, timeout=10)
                self.assertEqual(response.returncode, 0, response.stderr)
                return json.loads(response.stdout)
            missing = call({'action': 'job', 'job_id': 'a' * 32})
            self.assertEqual((missing['status'], missing['code']), (404, 'record_unavailable'))
            empty = call({'action': 'propose', 'target_ids': ['alpha'], 'intent': 'fix alpha'})
            self.assertEqual(empty['status'], 422)
            self.assertEqual(empty['data']['diagnostics'], {'stage': 'scenario', 'reason': 'schema'})
            self.assertEqual(empty['data']['checks'], [{'status': 'unavailable'}])
            self.assertFalse(list((root / 'state' / 'plans').glob('*.json')))

    def test_cli_reconcile_and_resume_launch_recorded_worker_to_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = Files(root)
            registry = RepairRegistry()
            registry.register(adapter)
            coordinator = Coordinator(root / 'state', registry)
            tools = Path(__file__).resolve().parent
            driver = root / 'driver.py'
            driver.write_text("import sys\nfrom pathlib import Path\nsys.path.insert(0," + repr(str(tools)) + ")\nimport universal_repairs as engine\nfrom test_universal_repairs import Files\nfrom repair_registry import RepairRegistry\nroot=Path("+repr(str(root))+")\nadapter=Files(root)\nregistry=RepairRegistry()\nregistry.register(adapter)\nengine.service=lambda state:engine.Coordinator(state,registry)\nengine.__file__=__file__\nengine.main()\n")
            def call(action, job_id):
                response = subprocess.run([sys.executable, '-B', str(driver), '--state', str(root / 'state')], input=json.dumps({'action': action, 'job_id': job_id}), capture_output=True, text=True, timeout=10)
                self.assertEqual(response.returncode, 0, response.stderr)
                value = json.loads(response.stdout)
                self.assertEqual(value['status'], 200, value)
                return value['data']
            def wait(job_id, status):
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    result = coordinator.get_job(job_id)
                    if result['status'] == status:
                        return result
                    time.sleep(.02)
                self.fail('detached worker did not reach '+status+': '+json.dumps(result))
            def job():
                plan = coordinator.freeze('fixture', [{'target_id': name, 'proposal': {'text': 'new'}} for name in ('alpha', 'beta')])
                return coordinator.approve(plan['plan_id'], plan['digest'])['job_id']
            job_id = job()
            adapter.lose_response = 'alpha'
            self.assertEqual(coordinator.run_job(job_id)['status'], 'unknown')
            call('reconcile', job_id)
            wait(job_id, 'completed')
            self.assertEqual((root / 'beta').read_text(), 'new')
            coordinator.undo(job_id)
            adapter.lose_response = None
            job_id = job()
            adapter.fail_backup = 'beta'
            self.assertEqual(coordinator.run_job(job_id)['status'], 'blocked')
            call('resume', job_id)
            wait(job_id, 'completed')
            self.assertEqual((root / 'alpha').read_text(), 'new')
            coordinator.undo(job_id)
            adapter.fail_backup = None
            job_id = job()
            original_verify = adapter.verify
            adapter.verify = lambda *args: {'ok': False, 'state': 'blocked', 'checks': [], 'evidence': [], 'limitations': []}
            self.assertEqual(coordinator.run_job(job_id)['status'], 'blocked')
            adapter.verify = original_verify
            call('resume', job_id)
            result = wait(job_id, 'completed')
            self.assertEqual(sum(event['phase'] == 'intent' for event in result['events']), 2)
            adapter.crash_after_undo = True
            with self.assertRaises(SystemExit):
                coordinator.undo(job_id)
            adapter.crash_after_undo = False
            call('reconcile', job_id)
            result = wait(job_id, 'undone')
            self.assertEqual(sum(event['phase'] == 'undo_intent' for event in result['events']), 2)
            self.assertEqual((root / 'alpha').read_text(), 'old')
            self.assertEqual((root / 'beta').read_text(), 'old')
            job_id = job()
            adapter.lose_response = 'alpha'
            coordinator.run_job(job_id)
            (root / 'alpha').write_text('unrecognized external state')
            response = call('reconcile', job_id)
            self.assertEqual(response['status'], 'unknown')
            self.assertFalse(response['worker_started'])
            response = call('resume', job_id)
            self.assertEqual(response['status'], 'unknown')
            self.assertFalse(response['worker_started'])
            self.assertEqual((root / 'beta').read_text(), 'old')



class ApiBoundaryTests(unittest.TestCase):
    def test_bridge_preserves_missing_job_and_safe_ai_diagnostics(self):
        project = Path(__file__).resolve().parents[1]
        script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {EventEmitter}=require('node:events'),ts=require('./app/node_modules/typescript');
let result;
const exports={};
const text=ts.transpileModule(fs.readFileSync('app/src/lib/server/universal-repairs.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText;
function requireModule(name){
 if(name==='./paths')return {ensureLocalDataDir(){},foundationRoot:()=>process.cwd(),localDataDir:()=>'/tmp'};
 if(name==='node:child_process')return {spawn(){
  const child=new EventEmitter();child.stdout=new EventEmitter();child.stdin=new EventEmitter();child.kill=()=>{};
  child.stdin.end=()=>process.nextTick(()=>{child.stdout.emit('data',Buffer.from(JSON.stringify(result)));child.emit('close',0)});
  return child;
 }};
 return require(name);
}
vm.runInNewContext(text,{exports,require:requireModule,Buffer,setTimeout,clearTimeout,process,Response});
(async()=>{
 result={status:404,code:'record_unavailable',error:'Repair operation unavailable.'};
 let response=await exports.repairResponse({action:'job'});
 assert.equal(response.status,404);assert.equal((await response.json()).code,'record_unavailable');
 result={status:422,data:{code:'ai_no_proposals',diagnostics:{stage:'scenario',reason:'schema'},checks:[{status:'unavailable'}],limitations:['No approvable proposal was produced.']}};
 response=await exports.repairResponse({action:'propose'});
 assert.equal(response.status,422);assert.deepEqual((await response.json()).diagnostics,{stage:'scenario',reason:'schema'});
 console.log('bridge 404/422 contracts PASS');
})().catch(error=>{console.error(error);process.exitCode=1});
"""
        result = subprocess.run(['node', '-e', script], cwd=project, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS', result.stdout)

    def test_real_auth_on_all_reads_and_actions_and_reject_browser_checks(self):
        project = Path(__file__).resolve().parents[1]
        script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('./app/node_modules/typescript');
const os = require('node:os');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'repair-route-'));
const cache = new Map();
let bridgeCalls = 0;
function load(relative) {
  const absolute = path.resolve(relative);
  if (cache.has(absolute)) return cache.get(absolute);
  const exports = {};
  cache.set(absolute, exports);
  const text = ts.transpileModule(fs.readFileSync(absolute, 'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText;
  function requireModule(name) {
    if (name === './paths') return {ensureLocalDataDir(){},localDataDir:()=>temp,foundationRoot:()=>process.cwd()};
    if (name === '@/lib/server/universal-repairs') {
      return {...load('app/src/lib/server/universal-repairs.ts'),repairResponse: async input=>{bridgeCalls++;return Response.json(input)}};
    }
    if (name.startsWith('@/')) return load('app/src/'+name.slice(2)+'.ts');
    if (name.startsWith('.')) return load(path.join(path.dirname(absolute),name+'.ts'));
    return require(name);
  }
  vm.runInNewContext(text,{exports,require:requireModule,Request,Response,URL,Buffer,setTimeout,clearTimeout,process,console},{filename:absolute});
  return exports;
}
(async()=>{
 try {
  const route=load('app/src/app/api/repairs/route.ts');
  const job=load('app/src/app/api/repairs/jobs/[jobId]/route.ts');
  const auth=load('app/src/lib/server/local-auth.ts');
  const token=auth.getOrCreateLocalToken();
  const context={params:Promise.resolve({jobId:'a'.repeat(32)})};
  for (const [handler,url,method,body] of [
   [route.GET,'/api/repairs','GET'],[route.GET,'/api/repairs?target_id=alpha','GET'],[route.GET,'/api/repairs?plan_id='+'a'.repeat(32),'GET'],
   [route.POST,'/api/repairs','POST',{action:'apply',plan_id:'a'.repeat(32),digest:'b'.repeat(64)}],
   [job.GET,'/api/repairs/jobs/'+'a'.repeat(32),'GET'],[job.POST,'/api/repairs/jobs/'+'a'.repeat(32),'POST',{action:'undo'}]]) {
    const options={method,headers:{host:'127.0.0.1'},...(body?{body:JSON.stringify(body)}:{})};
    assert.equal((await handler(new Request('http://127.0.0.1'+url,options),context)).status,401);
    options.headers['x-local-token']=token;
    options.headers['tailscale-user-login']='remote';
    assert.equal((await handler(new Request('http://127.0.0.1'+url,options),context)).status,403);
  }
  assert.equal(bridgeCalls,0);
  const valid={action:'apply',plan_id:'a'.repeat(32),digest:'b'.repeat(64)};
  const options=body=>({method:'POST',headers:{host:'127.0.0.1','x-local-token':token},body:JSON.stringify(body)});
  assert.equal((await route.POST(new Request('http://127.0.0.1/api/repairs',options({...valid,checks:[]})))).status,400);
  assert.equal((await route.POST(new Request('http://127.0.0.1/api/repairs',options({...valid,account:'other'})))).status,400);
  assert.equal((await route.POST(new Request('http://127.0.0.1/api/repairs',options(valid)))).status,200);
  assert.equal(bridgeCalls,1);
  console.log('real route auth and exact browser approval PASS');
 } finally {fs.rmSync(temp,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1});
"""
        result = subprocess.run(['node', '-e', script], cwd=project, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()

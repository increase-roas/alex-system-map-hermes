"""Protocol fixtures and optional installed native CLI probes use TEMP homes only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from repair_contracts import RepairError
from repair_plugin_adapters import PluginAdapter, ClaudePluginClient
from repair_native_adapters import CodexClient
from repair_registry import RepairRegistry
from universal_repairs import Coordinator


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()


class NativeFixture:
    """Protocol-shaped installation fixture, not evidence about vendor runtime."""
    def __init__(self, home, market, system):
        self.home, self.market, self.system = home, market, system
        self.version = '1.0.0'
        self.calls = []
        self.install()

    def install(self):
        self.version = json.loads((self.market / 'toy/.claude-plugin/plugin.json').read_text())['version']
        self.cache = self.home / ('.codex' if self.system == 'codex' else '.claude') / 'plugins/cache/toy-market/toy' / self.version
        if self.system == 'codex' and self.cache.parent.exists():
            shutil.rmtree(self.cache.parent)
        elif self.cache.exists():
            shutil.rmtree(self.cache)
        shutil.copytree(self.market / 'toy', self.cache)
        if self.system == 'codex':
            path = self.home / '.codex/config.toml'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('[marketplaces.toy-market]\nsource_type = "local"\nsource = ' + json.dumps(str(self.market)) + '\n[plugins."toy@toy-market"]\nenabled = true\n')
        else:
            path = self.home / '.claude/plugins/installed_plugins.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'version': 2, 'plugins': {'toy@toy-market': [{
                'scope': 'user', 'version': self.version, 'installPath': str(self.cache),
                'installedAt': '2026-10-21T00:00:00.000Z', 'lastUpdated': '2026-10-21T00:00:00.000Z'}]}}))

    def request(self, method, params=None):
        self.calls.append((method, params))
        if method == 'plugin/list':
            return {'marketplaces': [{'name': 'toy-market', 'path': str(self.market / '.claude-plugin/marketplace.json'), 'plugins': [self.summary()]}]}
        if method == 'plugin/read':
            return {'plugin': {'summary': self.summary()}}
        if method == 'plugin/install':
            self.install(); return {'authPolicy': 'ON_INSTALL', 'appsNeedingAuth': []}
        if method == 'list':
            return [{'id': 'toy@toy-market', 'version': self.version, 'scope': 'user', 'installPath': str(self.cache)}]
        if method == 'update':
            candidate = json.loads((self.market / 'toy/.claude-plugin/plugin.json').read_text())['version']
            if candidate != self.version:
                self.install()
            return {'outcome': 'ok'}
        raise AssertionError(method)

    def summary(self):
        return {'name': 'toy', 'id': 'toy@toy-market', 'installed': True, 'localVersion': self.version,
                'source': {'type': 'local', 'path': str(self.market / 'toy')}}


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='owned-plugin-tests-')
        self.home = Path(self.tmp.name).resolve()
        (self.home / 'Backups').mkdir()
        self.market = self.home / 'source'
        (self.market / '.claude-plugin').mkdir(parents=True)
        (self.market / 'toy/.claude-plugin').mkdir(parents=True)
        self.skill = self.market / 'toy/skills/toy/SKILL.md'
        self.skill.parent.mkdir(parents=True)
        self.before = '---\nname: toy\ndescription: A fixture procedure.\n---\nALPHA\n'
        self.skill.write_text(self.before)
        (self.market / 'toy/.claude-plugin/plugin.json').write_text(json.dumps({'name': 'toy', 'version': '1.0.0', 'description': 'Fixture'}))
        (self.market / '.claude-plugin/marketplace.json').write_text(json.dumps({'name': 'toy-market', 'owner': {'name': 'Fixture'}, 'plugins': [{'name': 'toy', 'source': './toy', 'version': '1.0.0'}]}))
        registry = self.home / '.claude/plugins/known_marketplaces.json'
        registry.parent.mkdir(parents=True)
        registry.write_text(json.dumps({'toy-market': {'source': {'source': 'directory', 'path': str(self.market)}, 'installLocation': str(self.market), 'lastUpdated': '2026-10-21T00:00:00.000Z'}}))
        git(self.market, 'init', '-b', 'main')
        git(self.market, 'config', 'user.email', 'fixture@example.invalid')
        git(self.market, 'config', 'user.name', 'Fixture')
        git(self.market, 'add', '.')
        git(self.market, 'commit', '-m', 'Fixture')
        self.remote = self.home / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(self.remote)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        git(self.market, 'remote', 'add', 'origin', str(self.remote))
        git(self.market, 'push', '-u', 'origin', 'main')
        self.codex = NativeFixture(self.home, self.market, 'codex')
        self.claude = NativeFixture(self.home, self.market, 'claude')
        self.adapter = PluginAdapter(self.home, self.codex, self.claude)
        registry = RepairRegistry(); registry.register(self.adapter)
        self.service = Coordinator(self.home / 'state', registry)

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self):
        rows = self.adapter.discover()
        target = next(t for t in rows if t['identity']['path'] == str(self.skill))
        return self.service.freeze('Repair owned plugin', [{'target_id': target['id'], 'proposal': {'candidate': self.before.replace('ALPHA', 'BRAVO')}}])

    def test_coordinator_frozen_source_publication_both_caches_and_undo(self):
        plan = self.plan()
        self.assertEqual(['replace', 'replace', 'replace', 'publish', 'plugin_materialize'], [o['action'] for o in plan['operations']])
        self.assertIn('1.0.1', json.dumps(plan))
        self.assertEqual(self.before, self.skill.read_text())
        self.assertFalse(any(m == 'plugin/install' for m, _ in self.codex.calls))
        job = self.service.approve(plan['plan_id'], plan['digest'])
        result = self.service.run_job(job['job_id'])
        self.assertEqual('completed', result['status'], result)
        for client in (self.codex, self.claude):
            self.assertIn('BRAVO', (client.cache / 'skills/toy/SKILL.md').read_text())
        self.assertEqual(git(self.market, 'rev-parse', 'HEAD'), git(self.market, 'ls-remote', 'origin', 'refs/heads/main').split()[0])
        result = self.service.undo(job['job_id'])
        self.assertEqual('undone', result['status'], result)
        self.assertEqual(self.before, self.skill.read_text())
        for client in (self.codex, self.claude):
            self.assertEqual('1.0.0', client.version)
            self.assertEqual(self.before, (client.cache / 'skills/toy/SKILL.md').read_text())

    def test_stale_cache_preflight_no_source_effect(self):
        plan = self.plan()
        (self.codex.cache / 'skills/toy/SKILL.md').write_text('NEWER')
        job = self.service.approve(plan['plan_id'], plan['digest'])
        result = self.service.run_job(job['job_id'])
        self.assertEqual('blocked', result['status'])
        self.assertEqual(self.before, self.skill.read_text())

    def test_unselected_source_change_blocks_before_any_effect(self):
        reference = self.market / 'toy/skills/toy/references/unselected.md'
        reference.parent.mkdir(parents=True)
        reference.write_text('Frozen unselected source.\n')
        git(self.market, 'add', '.');git(self.market, 'commit', '-m', 'Unselected source fixture');git(self.market, 'push', 'origin', 'main')
        self.codex.install();self.claude.install()
        plan = self.plan()
        source_before = self.adapter.file_hashes(self.market / 'toy')
        caches_before = self.adapter.cache_state(next(iter(self.adapter.packages.values())))
        head_before = git(self.market, 'rev-parse', 'HEAD')
        remote_before = git(self.market, 'ls-remote', 'origin', 'refs/heads/main')
        reference.write_text('Newer external source.\n')
        stored = self.service.checked_plan(plan['plan_id'])
        operation = stored['operations'][-1]
        target = stored['targets'][operation['target_id']]
        with mock.patch.object(self.codex, 'request', side_effect=AssertionError('native preapproval call')) as codex_call, mock.patch.object(self.claude, 'request', side_effect=AssertionError('native preapproval call')) as claude_call:
            self.assertFalse(self.adapter.preflight(target, operation)['ok'])
            with self.assertRaisesRegex(RepairError, 'stale_plugin_backup_source'):
                self.adapter.backup(target, operation, self.home / 'rejected-backup')
            job = self.service.approve(plan['plan_id'], plan['digest'])
            result = self.service.run_job(job['job_id'])
            self.assertEqual('blocked', result['status'], result)
            codex_call.assert_not_called();claude_call.assert_not_called()
        self.assertEqual(self.before, self.skill.read_text())
        self.assertEqual('Newer external source.\n', reference.read_text())
        after = self.adapter.file_hashes(self.market / 'toy')
        unselected = reference.relative_to(self.market / 'toy').as_posix()
        self.assertEqual({k: v for k, v in source_before.items() if k != unselected}, {k: v for k, v in after.items() if k != unselected})
        self.assertEqual(caches_before, self.adapter.cache_state(next(iter(self.adapter.packages.values()))))
        self.assertEqual(head_before, git(self.market, 'rev-parse', 'HEAD'))
        self.assertEqual(remote_before, git(self.market, 'ls-remote', 'origin', 'refs/heads/main'))

    def test_external_cache_or_source_edit_preserved_by_undo(self):
        plan = self.plan(); job = self.service.approve(plan['plan_id'], plan['digest'])
        self.assertEqual('completed', self.service.run_job(job['job_id'])['status'])
        path = self.claude.cache / 'skills/toy/SKILL.md'; path.write_text('NEWER')
        result = self.service.undo(job['job_id'])
        self.assertEqual('blocked', result['status'], result)
        self.assertEqual('NEWER', path.read_text())
        self.assertIn('BRAVO', self.skill.read_text())

    def test_stale_initial_cache_converges_and_undo_uses_canonical_baseline(self):
        (self.claude.cache / 'skills/toy/SKILL.md').write_text('OLD STALE CACHE')
        plan = self.plan()
        self.assertIn('pre-existing stale copies are not recreated', json.dumps(plan))
        job = self.service.approve(plan['plan_id'], plan['digest'])
        self.assertEqual('completed', self.service.run_job(job['job_id'])['status'])
        saved = self.service.load('jobs', job['job_id'])['steps'][-1]['backup']['stale_cache_backups']
        self.assertEqual(1, len(saved))
        self.assertEqual('OLD STALE CACHE', Path(saved[0]['path']).read_text())
        result = self.service.undo(job['job_id'])
        self.assertEqual('undone', result['status'], result)
        self.assertEqual(self.before, (self.claude.cache / 'skills/toy/SKILL.md').read_text())

    def test_forward_refresh_zero_effect_failure_reconciles_and_resumes(self):
        plan = self.plan();job = self.service.approve(plan['plan_id'], plan['digest'])
        with mock.patch.object(self.adapter, 'refresh', side_effect=RuntimeError('Fixture native unavailable before first effect')):
            result = self.service.run_job(job['job_id'])
        self.assertEqual('unknown', result['status'])
        self.assertIn('BRAVO', self.skill.read_text())
        self.assertEqual('1.0.0', self.codex.version);self.assertEqual('1.0.0', self.claude.version)
        forward_head = git(self.market, 'rev-parse', 'HEAD')
        self.assertEqual('queued', self.service.reconcile(job['job_id'])['status'])
        result = self.service.run_job(job['job_id'])
        self.assertEqual('completed', result['status'], result)
        self.assertEqual(forward_head, git(self.market, 'rev-parse', 'HEAD'))
        self.assertEqual('1.0.1', self.codex.version);self.assertEqual('1.0.1', self.claude.version)

    def test_forward_partial_refresh_resumes_only_missing_copy(self):
        plan = self.plan();job = self.service.approve(plan['plan_id'], plan['digest'])
        original = self.claude.request
        def unavailable(method, params=None):
            if method == 'update':
                raise RuntimeError('Fixture second native unavailable')
            return original(method, params)
        with mock.patch.object(self.claude, 'request', side_effect=unavailable):
            result = self.service.run_job(job['job_id'])
        self.assertEqual('unknown', result['status'])
        self.assertEqual('1.0.1', self.codex.version);self.assertEqual('1.0.0', self.claude.version)
        forward_head = git(self.market, 'rev-parse', 'HEAD')
        self.assertEqual('queued', self.service.reconcile(job['job_id'])['status'])
        with mock.patch.object(self.codex, 'request', side_effect=AssertionError('Completed native copy replayed')) as completed:
            result = self.service.run_job(job['job_id'])
            self.assertEqual('completed', result['status'], result)
            completed.assert_not_called()
        self.assertEqual(forward_head, git(self.market, 'rev-parse', 'HEAD'))
        self.assertEqual('1.0.1', self.codex.version);self.assertEqual('1.0.1', self.claude.version)

    def interrupted_inverse_refresh(self):
        plan = self.plan();job = self.service.approve(plan['plan_id'], plan['digest'])
        self.assertEqual('completed', self.service.run_job(job['job_id'])['status'])
        def interrupted(package, copies):
            self.codex.install()
            raise RuntimeError('Fixture process loss after first native inverse refresh')
        with mock.patch.object(self.adapter, 'refresh', side_effect=interrupted):
            result = self.service.undo(job['job_id'])
        self.assertEqual('unknown', result['status'])
        self.assertEqual(self.before, self.skill.read_text())
        self.assertEqual('1.0.0', self.codex.version);self.assertEqual('1.0.1', self.claude.version)
        return job

    def test_lost_inverse_refresh_reconciles_remaining_copies_without_new_commit(self):
        job = self.interrupted_inverse_refresh()
        inverse_head = git(self.market, 'rev-parse', 'HEAD')
        self.assertEqual('undoing', self.service.reconcile(job['job_id'])['status'])
        with mock.patch.object(self.codex, 'request', side_effect=AssertionError('Completed inverse copy replayed')) as completed:
            result = self.service.run_job(job['job_id'])
            self.assertEqual('undone', result['status'], result)
            completed.assert_not_called()
        self.assertEqual(inverse_head, git(self.market, 'rev-parse', 'HEAD'))
        self.assertEqual(inverse_head, git(self.market, 'ls-remote', 'origin', 'refs/heads/main').split()[0])
        self.assertEqual('1.0.0', self.codex.version);self.assertEqual('1.0.0', self.claude.version)

    def test_lost_inverse_refresh_with_later_source_edit_stays_unknown(self):
        job = self.interrupted_inverse_refresh()
        inverse_head = git(self.market, 'rev-parse', 'HEAD')
        self.skill.write_text('NEWER SOURCE AFTER INVERSE')
        with mock.patch.object(self.codex, 'request', side_effect=AssertionError('Unexpected native recovery effect')) as codex_call, mock.patch.object(self.claude, 'request', side_effect=AssertionError('Unexpected native recovery effect')) as claude_call:
            self.assertEqual('unknown', self.service.reconcile(job['job_id'])['status'])
            codex_call.assert_not_called();claude_call.assert_not_called()
        self.assertEqual('NEWER SOURCE AFTER INVERSE', self.skill.read_text())
        self.assertEqual(inverse_head, git(self.market, 'rev-parse', 'HEAD'))
        self.assertEqual('1.0.0', self.codex.version);self.assertEqual('1.0.1', self.claude.version)

    def test_private_stale_cache_stays_unavailable_without_exposing_bytes(self):
        private = 'api_key = "opaque-private-value"'
        (self.claude.cache / 'skills/toy/SKILL.md').write_text(private)
        with self.assertRaisesRegex(RepairError, 'plugin_private_cache_preimage') as caught:
            self.plan()
        self.assertNotIn(private, str(caught.exception))
        self.assertEqual(self.before, self.skill.read_text())

    def test_source_edit_preserved_by_undo(self):
        plan = self.plan(); job = self.service.approve(plan['plan_id'], plan['digest'])
        self.assertEqual('completed', self.service.run_job(job['job_id'])['status'])
        self.skill.write_text('NEWER SOURCE')
        result = self.service.undo(job['job_id'])
        self.assertEqual('blocked', result['status'])
        self.assertEqual('NEWER SOURCE', self.skill.read_text())

    @unittest.skipUnless(shutil.which('codex') and shutil.which('claude'), 'Installed native CLIs unavailable')
    def test_actual_two_plugins_share_one_publication_and_one_inverse(self):
        other = self.market / 'toy-two'
        (other / '.claude-plugin').mkdir(parents=True)
        (other / '.claude-plugin/plugin.json').write_text(json.dumps({'name': 'toy-two', 'version': '1.0.0', 'description': 'Second fixture'}))
        second_skill = other / 'skills/toy-two/SKILL.md';second_skill.parent.mkdir(parents=True)
        second_before = self.before.replace('name: toy', 'name: toy-two')
        second_skill.write_text(second_before)
        market_path = self.market / '.claude-plugin/marketplace.json'
        value = json.loads(market_path.read_text());value['plugins'].append({'name': 'toy-two', 'source': './toy-two', 'version': '1.0.0'});market_path.write_text(json.dumps(value))
        git(self.market, 'add', '.');git(self.market, 'commit', '-m', 'Two plugin fixture');git(self.market, 'push', 'origin', 'main')
        initial_head = git(self.market, 'rev-parse', 'HEAD')
        codex = CodexClient(self.home / '.codex')
        claude = ClaudePluginClient(self.home / '.claude')
        for name in ('toy', 'toy-two'):
            codex.request('plugin/install', {'pluginName': name, 'marketplacePath': str(market_path)})
            result = subprocess.run([claude.binary, 'plugin', 'install', name + '@toy-market', '--scope', 'user', '--json'],
                                    cwd=self.home, env={**os.environ, 'CLAUDE_CONFIG_DIR': str(claude.home)}, capture_output=True, text=True, timeout=45)
            self.assertEqual(0, result.returncode, result.stdout)
        self.adapter = PluginAdapter(self.home, codex, claude)
        registry = RepairRegistry();registry.register(self.adapter)
        self.service = Coordinator(self.home / 'two-plugin-state', registry)
        targets = {t['identity']['path']: t for t in self.adapter.discover()}
        proposals = [{'target_id': targets[str(path)]['id'], 'proposal': {'candidate': original.replace('ALPHA', 'BRAVO')}}
                     for path, original in ((self.skill, self.before), (second_skill, second_before))]
        plan = self.service.freeze('Two selected plugins in one marketplace', proposals)
        self.assertEqual(1, sum(op['action'] == 'publish' for op in plan['operations']))
        self.assertEqual(2, sum(op['action'] == 'plugin_materialize' for op in plan['operations']))
        job = self.service.approve(plan['plan_id'], plan['digest'])
        self.assertEqual('completed', self.service.run_job(job['job_id'])['status'])
        result = self.service.undo(job['job_id'])
        self.assertEqual('undone', result['status'], result)
        self.assertEqual(self.before, self.skill.read_text());self.assertEqual(second_before, second_skill.read_text())
        self.assertEqual('2', git(self.market, 'rev-list', '--count', initial_head + '..HEAD'))
        head = git(self.market, 'rev-parse', 'HEAD')
        self.assertEqual(head, git(self.market, 'ls-remote', 'origin', 'refs/heads/main').split()[0])
        copies = {key: self.adapter.cache_state(package) for key, package in self.adapter.packages.items()}
        self.assertEqual(2, len(copies))
        for rows in copies.values():
            self.assertEqual({'codex', 'claude'}, {r['system'] for r in rows})
            self.assertTrue(all(r['version'] == '1.0.0' for r in rows))
        with mock.patch.object(codex, 'request', side_effect=AssertionError('Repeated Undo native effect')) as codex_call, mock.patch.object(claude, 'request', side_effect=AssertionError('Repeated Undo native effect')) as claude_call:
            self.assertEqual('undone', self.service.undo(job['job_id'])['status'])
            codex_call.assert_not_called();claude_call.assert_not_called()
        self.assertEqual(head, git(self.market, 'rev-parse', 'HEAD'))
        self.assertEqual(copies, {key: self.adapter.cache_state(package) for key, package in self.adapter.packages.items()})

    @unittest.skipUnless(shutil.which('codex') and shutil.which('claude'), 'Installed native CLIs unavailable')
    def test_actual_native_both_copies_through_coordinator_and_undo(self):
        host = self.market / 'toy/.codex-plugin/plugin.json';host.parent.mkdir()
        host.write_text(json.dumps({'name': 'toy', 'version': '1.0.0', 'description': 'Fixture', 'skills': './skills/'}))
        git(self.market, 'add', '.');git(self.market, 'commit', '-m', 'Dual native manifest fixture');git(self.market, 'push', 'origin', 'main')
        codex_home = self.home / '.codex';codex_home.mkdir(exist_ok=True)
        (codex_home / 'config.toml').write_text('[marketplaces.toy-market]\nsource_type = "local"\nsource = ' + json.dumps(str(self.market)) + '\n')
        codex = CodexClient(codex_home)
        listing = codex.request('plugin/list', {'marketplaceKinds': ['local'], 'forceRefetch': False})
        market = next(m for m in listing['marketplaces'] if m['name'] == 'toy-market')
        codex.request('plugin/install', {'pluginName': 'toy', 'marketplacePath': market['path']})
        claude = ClaudePluginClient(self.home / '.claude')
        result = subprocess.run([claude.binary, 'plugin', 'install', 'toy@toy-market', '--scope', 'user', '--json'],
                                cwd=self.home, env={**os.environ, 'CLAUDE_CONFIG_DIR': str(claude.home)}, capture_output=True, text=True, timeout=45)
        self.assertEqual(0, result.returncode, result.stdout)
        self.adapter = PluginAdapter(self.home, codex, claude)
        registry = RepairRegistry();registry.register(self.adapter)
        self.service = Coordinator(self.home / 'actual-state', registry)
        plan = self.plan()
        self.assertEqual(self.before, self.skill.read_text())
        job = self.service.approve(plan['plan_id'], plan['digest'])
        result = self.service.run_job(job['job_id'])
        self.assertEqual('completed', result['status'], result)
        sync = next(t for t in self.adapter.discover() if t['category'] == 'plugin_sync')
        copies = self.adapter.read(sync)['projection']['copies']
        self.assertEqual({'claude', 'codex'}, {c['system'] for c in copies})
        self.assertTrue(all(c['version'] == '1.0.1' for c in copies))
        result = self.service.undo(job['job_id'])
        self.assertEqual('undone', result['status'], result)
        self.assertEqual(self.before, self.skill.read_text())
        self.assertTrue(all(c['version'] == '1.0.0' for c in self.adapter.read(sync)['projection']['copies']))

    def test_every_preapproval_phase_uses_zero_native_calls(self):
        # Even when source version differs, inventory must not invoke native list.
        path = self.market / 'toy/.claude-plugin/plugin.json'
        value = json.loads(path.read_text());value['version'] = '2.0.0';path.write_text(json.dumps(value))
        git(self.market, 'add', '.');git(self.market, 'commit', '-m', 'Stale version fixture');git(self.market, 'push', 'origin', 'main')
        before = {system: self.adapter.file_hashes(client.cache) for system, client in [('codex', self.codex), ('claude', self.claude)]}
        with mock.patch.object(self.codex, 'request', side_effect=AssertionError('native preapproval call')) as codex_call, mock.patch.object(self.claude, 'request', side_effect=AssertionError('native preapproval call')) as claude_call:
            plan = self.plan()
            stored = self.service.checked_plan(plan['plan_id'])
            sync = next(t for t in self.adapter.discover() if t['category'] == 'plugin_sync')
            self.adapter.read(sync)
            for operation in stored['operations']:
                target = stored['targets'][operation['target_id']]
                self.assertTrue(self.adapter.preflight(target, operation)['ok'])
                self.adapter.backup(target, operation, self.home / 'preapproval-backup')
            self.service.approve(plan['plan_id'], plan['digest'])
            codex_call.assert_not_called();claude_call.assert_not_called()
        self.assertEqual(before, {system: self.adapter.file_hashes(client.cache) for system, client in [('codex', self.codex), ('claude', self.claude)]})

    @unittest.skipUnless(shutil.which('codex') and shutil.which('claude'), 'Installed native CLIs unavailable')
    def test_actual_stale_version_preproposal_leaves_cache_unchanged(self):
        codex = CodexClient(self.home / '.codex')
        listing = codex.request('plugin/list', {'marketplaceKinds': ['local'], 'forceRefetch': False})
        market = next(m for m in listing['marketplaces'] if m['name'] == 'toy-market')
        codex.request('plugin/install', {'pluginName': 'toy', 'marketplacePath': market['path']})
        claude = ClaudePluginClient(self.home / '.claude')
        # Existing fixture registry is the actual native v2 installed-file shape.
        self.adapter = PluginAdapter(self.home, codex, claude)
        registry = RepairRegistry();registry.register(self.adapter)
        self.service = Coordinator(self.home / 'actual-stale-state', registry)
        for relative in ('toy/.claude-plugin/plugin.json', '.claude-plugin/marketplace.json'):
            path = self.market / relative; value = json.loads(path.read_text())
            if 'plugins' in value:
                value['plugins'][0]['version'] = '2.0.0'
            else:
                value['version'] = '2.0.0'
            path.write_text(json.dumps(value))
        git(self.market, 'add', '.');git(self.market, 'commit', '-m', 'Stale native version fixture');git(self.market, 'push', 'origin', 'main')
        roots = [self.home / '.codex/plugins/cache', self.home / '.claude/plugins/cache']
        before = [self.adapter.file_hashes(root) for root in roots]
        with mock.patch.object(codex, 'request', side_effect=AssertionError('native preapproval call')) as codex_call, mock.patch.object(claude, 'request', side_effect=AssertionError('native preapproval call')) as claude_call:
            plan = self.plan()
            self.assertIn('2.0.1', json.dumps(plan))
            stored = self.service.checked_plan(plan['plan_id'])
            for operation in stored['operations']:
                self.assertTrue(self.adapter.preflight(stored['targets'][operation['target_id']], operation)['ok'])
            codex_call.assert_not_called();claude_call.assert_not_called()
        self.assertEqual(before, [self.adapter.file_hashes(root) for root in roots])
        self.assertFalse((self.home / '.codex/plugins/cache/toy-market/toy/2.0.0').exists())

    def test_provider_and_alias_never_owned(self):
        registry = self.home / '.claude/plugins/known_marketplaces.json'
        value = json.loads(registry.read_text()); value['toy-market']['source']['source'] = 'github';registry.write_text(json.dumps(value))
        self.assertEqual([], self.adapter.discover())

    def test_hook_and_script_source_categories(self):
        root = self.market / 'toy'
        for relative, content in [('hooks/hooks.json', '{"hooks": {}}'), ('scripts/tool.py', 'print("fixture")\n'), ('skills/toy/references/help.md', 'Help\n')]:
            path = root / relative;path.parent.mkdir(parents=True, exist_ok=True);path.write_text(content)
        rows = self.adapter.discover()
        self.assertTrue({'hook', 'executable', 'skill_reference', 'skill', 'plugin_sync', 'publication'} <= {t['category'] for t in rows})
        hook = next(t for t in rows if t['category'] == 'hook')
        self.adapter.prepare(hook, self.adapter.read(hook), {'candidate': '{"hooks": {}}\n'})

    @unittest.skipUnless(shutil.which('claude'), 'Installed Claude CLI unavailable')
    def test_installed_claude_isolated_version_bump_and_downgrade(self):
        client = ClaudePluginClient(self.home / 'native-claude')
        env = {**os.environ, 'CLAUDE_CONFIG_DIR': str(client.home)}
        for args in [('marketplace', 'add', str(self.market), '--json'), ('install', 'toy@toy-market', '--scope', 'user', '--json')]:
            result = subprocess.run([client.binary, 'plugin', *args], env=env, cwd=self.home, capture_output=True, text=True, timeout=45)
            self.assertEqual(0, result.returncode, result.stdout)
        self.skill.write_text(self.before.replace('ALPHA', 'BRAVO'))
        result = client.request('update', 'toy@toy-market')
        self.assertEqual('up_to_date', result['updateOutcome'])
        for version, token in [('1.0.1', 'BRAVO'), ('1.0.0', 'ALPHA')]:
            if version == '1.0.0':
                self.skill.write_text(self.before)
            path = self.market / 'toy/.claude-plugin/plugin.json'; value = json.loads(path.read_text());value['version'] = version;path.write_text(json.dumps(value))
            path = self.market / '.claude-plugin/marketplace.json';value = json.loads(path.read_text());value['plugins'][0]['version'] = version;path.write_text(json.dumps(value))
            client.request('update', 'toy@toy-market')
            row = next(r for r in client.request('list') if r['id'] == 'toy@toy-market')
            self.assertEqual(version, row['version'])
            self.assertIn(token, (Path(row['installPath']) / 'skills/toy/SKILL.md').read_text())

    @unittest.skipUnless(shutil.which('codex'), 'Installed Codex CLI unavailable')
    def test_installed_codex_isolated_same_version_install(self):
        home = self.home / 'native-codex'; home.mkdir()
        # Native local marketplace registration schema, scoped to this TEMP home.
        (home / 'config.toml').write_text('[marketplaces.toy-market]\nsource_type = "local"\nsource = ' + json.dumps(str(self.market)) + '\n')
        client = CodexClient(home)
        listing = client.request('plugin/list', {'marketplaceKinds': ['local'], 'forceRefetch': False})
        market = next((m for m in listing.get('marketplaces', []) if m.get('name') == 'toy-market'), None)
        self.assertIsNotNone(market, listing)
        params = {'pluginName': 'toy', 'marketplacePath': market['path']}
        for token in ('ALPHA', 'BRAVO', 'ALPHA'):
            self.skill.write_text(self.before.replace('ALPHA', token))
            client.request('plugin/install', params)
            row = client.request('plugin/read', params)['plugin']['summary']
            self.assertTrue(row['installed'])
            self.assertIn(token, (home / 'plugins/cache/toy-market/toy/1.0.0/skills/toy/SKILL.md').read_text())


if __name__ == '__main__':
    unittest.main()

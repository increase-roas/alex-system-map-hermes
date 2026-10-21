"""One approved bundle across real adapters, with disposable owner boundaries.

The HTTP provider and Codex protocol fixture own independent file-backed state.
Remote files use the real reviewed runner with explicitly injected temp roots.
Only the optional installed-Codex case launches a native owner process; its HOME
and CODEX_HOME are temporary. No fixture touches a real account or home.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import tomllib
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.request import Request, urlopen

from repair_contracts import RepairError
from repair_local_adapters import LocalAdapter
from repair_native_adapters import CodexAdapter
from repair_registry import RepairRegistry
from repair_remote_adapters import PROVIDERS, ProviderAdapter, RemoteFileAdapter
from repair_remote_runner import run_request
from universal_repairs import Coordinator


class FileConfigOwner:
    """Small independent versioned protocol owner, not an adapter stub."""

    def __init__(self, path):
        self.path = path
        self.writes = 0

    def request(self, method, params):
        raw = self.path.read_bytes()
        version = hashlib.sha256(raw).hexdigest()
        config = tomllib.loads(raw.decode())
        if method == 'config/read':
            return {'config': config, 'layers': [{'name': {'type': 'user', 'file': str(self.path)},
                                                   'config': copy.deepcopy(config), 'version': version}]}
        if method != 'config/batchWrite':
            raise AssertionError(method)
        if params['filePath'] != str(self.path) or params['expectedVersion'] != version:
            raise RepairError('fixture_config_conflict')
        if params['reloadUserConfig'] is not True:
            raise AssertionError('owner reload required')
        for edit in params['edits']:
            if edit['mergeStrategy'] != 'replace':
                raise AssertionError('unsupported fixture merge')
            if edit['value'] is None:
                config.pop(edit['keyPath'], None)
            else:
                config[edit['keyPath']] = edit['value']
        self.path.write_text(''.join(key + ' = ' + json.dumps(value) + '\n' for key, value in config.items()))
        self.writes += 1
        return {'status': 'ok', 'filePath': str(self.path),
                'version': hashlib.sha256(self.path.read_bytes()).hexdigest()}


class HttpProviderOwner:
    """Loopback native API fixture: disk persistence, version CAS, typed PATCH."""

    def __init__(self, path):
        self.path = path
        self.writes = 0
        self.lose_next_response = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def reply(self, status, value):
                self.send_response(status)
                self.end_headers()
                self.wfile.write(json.dumps(value).encode())

            def do_GET(self):
                if self.path != '/projects/fixture':
                    return self.reply(404, {})
                self.reply(200, json.loads(owner.path.read_text()))

            def do_PATCH(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                state = json.loads(owner.path.read_text())
                if self.path != '/projects/fixture' or body['expected_version'] != state['version']:
                    return self.reply(409, {'error': 'version_conflict'})
                changes = body['patch']
                if set(changes) != {'name'} or not isinstance(changes['name'], str):
                    return self.reply(422, {'error': 'invalid_project_name'})
                state['config'].update(changes)
                state['version'] = str(int(state['version']) + 1)
                owner.path.write_text(json.dumps(state))
                owner.writes += 1
                self.reply(200, {'version': state['version']})

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def exchange(self, action, target, payload=None):
        if action == 'dry_run':
            valid = set(payload['patch']) == {'name'} and isinstance(payload['patch']['name'], str)
            return {'ok': valid, 'schema_revision': PROVIDERS['neon_project']['revision']}
        if action not in ('read', 'write'):
            raise AssertionError(action)
        request = Request('http://127.0.0.1:' + str(self.server.server_port) + '/projects/fixture',
                          method='PATCH' if action == 'write' else 'GET',
                          data=json.dumps(payload).encode() if action == 'write' else None,
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=5) as response:
            result = json.load(response)
        if action == 'write':
            if self.lose_next_response:
                self.lose_next_response = False
                raise RepairError('remote_transport_uncertain')
            return result
        return {**result, 'identity': target['identity'], 'schema_revision': PROVIDERS['neon_project']['revision']}


class UniversalRepairIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='universal-bundle-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        (self.home / 'Backups').mkdir()
        self.local_path = self.put('.cursor/cli-config.json', '{"model":"before","apiKey":"PRIVATE_LOCAL","other":1}')
        self.hook_path = self.put('.cursor/hooks.json', '{"version":1,"hooks":{},"other":1}')
        self.native_path = self.put('.codex/config.toml', 'model = "fixture-model"\nmodel_verbosity = "low"\n')
        self.remote_path = self.put('remote-home/settings.json', '{"model":"before","apiKey":"PRIVATE_REMOTE","other":1}')
        self.provider_path = self.put('provider.json', json.dumps({'version': '1', 'config': {
            'name': 'before', 'apiKey': 'PRIVATE_PROVIDER', 'other': 1}}))
        self.native_owner = FileConfigOwner(self.native_path)
        self.provider_owner = HttpProviderOwner(self.provider_path)
        self.addCleanup(self.provider_owner.close)
        self.fail_remote_backup = False
        self.marker = self.home / 'HOOK_MUST_NOT_EXECUTE'
        self.registry = RepairRegistry()
        self.local = LocalAdapter(self.home)
        self.native = CodexAdapter(self.native_path.parent, client=self.native_owner)
        self.provider = ProviderAdapter('neon_project', exchange=self.provider_owner.exchange,
            registrations=[{'object_id': 'fixture', 'identity': {
                'object_id': 'fixture', 'project_id': 'fixture', 'account': PROVIDERS['neon_project']['account']}}])
        self.remote = RemoteFileAdapter('ssh', exchange=self.remote_exchange)
        for adapter in (self.local, self.native, self.provider, self.remote):
            self.registry.register(adapter)
        self.state = self.home / 'coordinator'
        self.service = Coordinator(self.state, self.registry)

    def put(self, relative, content):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o640)
        return path

    def remote_exchange(self, request):
        if self.fail_remote_backup and request['action'] == 'backup':
            raise RepairError('fixture_remote_backup_unavailable')
        return run_request(request, {'fixture': str(self.remote_path.parent)}, 'fixture-remote')

    def plan(self):
        targets = list(self.registry.discover().values())
        def local_id(path):
            return next(t['id'] for t in targets if t['identity'].get('path') == str(path))
        native_id = next(t['id'] for t in targets if t['adapter_id'] == self.native.adapter_id)
        provider_id = next(t['id'] for t in targets if t['adapter_id'] == self.provider.adapter_id)
        remote_id = next(t['id'] for t in targets if t['adapter_id'] == self.remote.adapter_id)
        return self.service.freeze('one reviewed repair across four owners', [
            {'target_id': local_id(self.local_path), 'proposal': {'patch': {'model': 'after'}}},
            {'target_id': local_id(self.hook_path), 'proposal': {'patch': {
                'hooks.beforeSubmitPrompt': [{'command': 'touch ' + str(self.marker)}]}}},
            {'target_id': native_id, 'proposal': {'patch': {'model_verbosity': 'high'}}},
            {'target_id': provider_id, 'proposal': {'patch': {'name': 'after'}}},
            {'target_id': remote_id, 'proposal': {'patch': {'model': 'after'}}},
        ])

    def approve(self):
        plan = self.plan()
        self.assertEqual(5, len(plan['operations']))
        self.assertEqual({'local-owner', 'codex-native', 'provider_neon_project', 'remote_file_ssh'},
                         {op['adapter_id'] for op in plan['operations']})
        with self.assertRaises(RepairError):
            self.service.approve(plan['plan_id'], '0' * 64)
        job = self.service.approve(plan['plan_id'], plan['digest'])
        self.assertEqual(job['job_id'], self.service.approve(plan['plan_id'], plan['digest'])['job_id'])
        self.assertEqual([self.state / 'jobs' / (job['job_id'] + '.json')], list((self.state / 'jobs').glob('*.json')))
        return plan, job

    def assert_after(self):
        self.assertEqual('after', json.loads(self.local_path.read_text())['model'])
        self.assertEqual('after', json.loads(self.remote_path.read_text())['model'])
        self.assertEqual('after', json.loads(self.provider_path.read_text())['config']['name'])
        self.assertEqual('high', tomllib.loads(self.native_path.read_text())['model_verbosity'])
        self.assertIn('beforeSubmitPrompt', json.loads(self.hook_path.read_text())['hooks'])
        self.assertFalse(self.marker.exists())

    def assert_public(self, value):
        raw = json.dumps(value)
        for forbidden in ('PRIVATE_LOCAL', 'PRIVATE_REMOTE', 'PRIVATE_PROVIDER'):
            self.assertNotIn(forbidden, raw)
        def check_keys(item):
            if isinstance(item, dict):
                self.assertTrue({'inverse', 'backup', 'candidate'}.isdisjoint(item))
                for child in item.values():
                    check_keys(child)
            elif isinstance(item, list):
                for child in item:
                    check_keys(child)
        check_keys(value)

    def test_one_digest_barrier_receipts_reopen_and_reverse_conditional_undo(self):
        plan, job = self.approve()
        result = self.service.run_job(job['job_id'])
        self.assertEqual('completed', result['status'], result)
        self.assert_after()
        phases = [event['phase'] for event in result['events']]
        self.assertEqual(5, phases[:phases.index('barrier_complete')].count('backed_up'))
        self.assertLess(phases.index('barrier_complete'), phases.index('intent'))
        for step in result['steps']:
            self.assertEqual('verified', step['phase'])
            self.assertTrue(step['receipt']['ok'])
            self.assertIn(step['receipt']['state'], ('byte_verified', 'effective'))
            self.assertTrue(step['receipt']['evidence'])
        self.assert_public(plan)
        self.assert_public(result)
        reopened = Coordinator(self.state, self.registry)
        self.assertEqual(result, reopened.get_job(job['job_id']))
        durable_plan = reopened.get_plan(plan['plan_id'])
        self.assertEqual({target['id']: target for target in plan['targets']},
                         {target['id']: target for target in durable_plan['targets']})
        self.assertEqual({key: value for key, value in plan.items() if key != 'targets'},
                         {key: value for key, value in durable_plan.items() if key != 'targets'})
        # A later owner edit must survive, including a conflicting repaired key.
        self.local_path.write_text('{"model":"later-owner-value","apiKey":"PRIVATE_LOCAL","other":2}')
        remote = json.loads(self.remote_path.read_text()); remote['other'] = 2
        self.remote_path.write_text(json.dumps(remote))
        provider = json.loads(self.provider_path.read_text()); provider['config']['other'] = 2
        provider['version'] = '3'; self.provider_path.write_text(json.dumps(provider))
        self.native_path.write_text(self.native_path.read_text() + 'personality = "friendly"\n')
        undone = reopened.undo(job['job_id'])
        self.assertEqual('blocked', undone['status'], undone)
        self.assertEqual('undo_conflict', undone['error'])
        self.assertEqual([op['step_id'] for op in reversed(plan['operations'])],
                         [e['step_id'] for e in undone['events'] if e['phase'] == 'undo_intent'])
        self.assertEqual('later-owner-value', json.loads(self.local_path.read_text())['model'])
        self.assertEqual({}, json.loads(self.hook_path.read_text())['hooks'])
        self.assertEqual({'model': 'before', 'apiKey': 'PRIVATE_REMOTE', 'other': 2}, json.loads(self.remote_path.read_text()))
        self.assertEqual({'name': 'before', 'apiKey': 'PRIVATE_PROVIDER', 'other': 2}, json.loads(self.provider_path.read_text())['config'])
        self.assertEqual({'model': 'fixture-model', 'model_verbosity': 'low', 'personality': 'friendly'}, tomllib.loads(self.native_path.read_text()))
        self.assertEqual(['applied', 'undone', 'undone', 'undone', 'undone'], [s['phase'] for s in undone['steps']])
        self.assertFalse(self.marker.exists())
        self.assert_public(undone)

    def test_last_owner_backup_failure_prevents_every_destination_write(self):
        _, job = self.approve()
        paths = (self.local_path, self.hook_path, self.native_path, self.provider_path, self.remote_path)
        before = {path: path.read_bytes() for path in paths}
        self.fail_remote_backup = True
        result = self.service.run_job(job['job_id'])
        self.assertEqual('blocked', result['status'])
        self.assertEqual('fixture_remote_backup_unavailable', result['error'])
        self.assertEqual(before, {path: path.read_bytes() for path in paths})
        self.assertEqual(0, self.native_owner.writes)
        self.assertEqual(0, self.provider_owner.writes)
        self.assertFalse(self.marker.exists())
        self.assertNotIn('intent', [e['phase'] for e in result['events']])
        self.assertEqual(4, sum(e['phase'] == 'backed_up' for e in result['events']))
        self.assert_public(result)

    def test_changed_provider_account_cannot_reuse_frozen_cross_owner_approval(self):
        _, job = self.approve()
        paths = (self.local_path, self.hook_path, self.native_path, self.provider_path, self.remote_path)
        before = {path: path.read_bytes() for path in paths}
        self.provider.registrations[0]['identity']['account'] = 'different-account'
        result = self.service.run_job(job['job_id'])
        self.assertEqual('blocked', result['status'])
        self.assertEqual('target_binding_changed', result['error'])
        self.assertEqual(before, {path: path.read_bytes() for path in paths})
        self.assertEqual(0, self.provider_owner.writes)
        self.assertEqual(0, self.native_owner.writes)
        self.assertNotIn('intent', [event['phase'] for event in result['events']])
        self.assert_public(result)

    def test_lost_provider_response_reopen_reconciles_without_duplicate_write(self):
        _, job = self.approve()
        self.provider_owner.lose_next_response = True
        result = self.service.run_job(job['job_id'])
        self.assertEqual('unknown', result['status'])
        self.assertEqual('before', json.loads(self.remote_path.read_text())['model'])
        self.assertEqual('after', json.loads(self.provider_path.read_text())['config']['name'])
        reopened = Coordinator(self.state, self.registry)
        self.assertEqual('queued', reopened.reconcile(job['job_id'])['status'])
        result = reopened.run_job(job['job_id'])
        self.assertEqual('completed', result['status'], result)
        self.assert_after()
        self.assertEqual(1, self.provider_owner.writes)
        self.assertEqual(1, self.native_owner.writes)
        self.assertEqual('undone', reopened.undo(job['job_id'])['status'])
        self.assertEqual('before', json.loads(self.local_path.read_text())['model'])
        self.assertEqual('before', json.loads(self.remote_path.read_text())['model'])
        self.assertEqual('before', json.loads(self.provider_path.read_text())['config']['name'])
        self.assertEqual('low', tomllib.loads(self.native_path.read_text())['model_verbosity'])
        self.assert_public(result)

    @unittest.skipUnless(shutil.which('codex'), 'installed Codex unavailable; fixture integration remains runnable offline')
    def test_same_bundle_with_installed_codex_owner_and_disposable_child_home(self):
        self.registry.adapters['codex-native'] = CodexAdapter(self.native_path.parent)
        with patch.dict(os.environ, {'HOME': str(self.home), 'CODEX_HOME': str(self.native_path.parent)}):
            plan, job = self.approve()
            result = self.service.run_job(job['job_id'])
            self.assertEqual('completed', result['status'], result)
            self.assert_after()
            reopened = Coordinator(self.state, self.registry)
            self.assertEqual(plan['digest'], reopened.get_job(job['job_id'])['digest'])
            self.assertEqual('undone', reopened.undo(job['job_id'])['status'])
        self.assertEqual('low', tomllib.loads(self.native_path.read_text())['model_verbosity'])
        self.assertEqual('before', json.loads(self.local_path.read_text())['model'])
        self.assertEqual('before', json.loads(self.remote_path.read_text())['model'])
        self.assertEqual('before', json.loads(self.provider_path.read_text())['config']['name'])
        self.assert_public(result)


if __name__ == '__main__':
    unittest.main()

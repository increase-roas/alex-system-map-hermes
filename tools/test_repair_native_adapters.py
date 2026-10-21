import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from repair_contracts import RepairError
from repair_native_adapters import CodexAdapter, CodexClient


class FixtureClient:
    def __init__(self, home):
        self.home = Path(home)
        self.user = {'model': 'fixture-model', 'model_verbosity': 'low', 'private_token': 'fixture-hidden'}
        self.version = 1
        self.writes = 0
        self.override = {}

    def request(self, method, params):
        if method == 'config/read':
            return {'config': {**self.user, **self.override}, 'layers': [{'name': {'type': 'user', 'file': str(self.home / 'config.toml')}, 'config': copy.deepcopy(self.user), 'version': str(self.version)}]}
        if method == 'config/batchWrite':
            if params['expectedVersion'] != str(self.version):
                raise RepairError('native_version_changed')
            assert params['filePath'] == str(self.home / 'config.toml')
            assert params['reloadUserConfig'] is True
            for edit in params['edits']:
                if edit['value'] is None:
                    self.user.pop(edit['keyPath'], None)
                else:
                    self.user[edit['keyPath']] = edit['value']
            self.version += 1
            self.writes += 1
            return {'status': 'okOverridden' if self.override else 'ok', 'version': str(self.version), 'filePath': str(self.home / 'config.toml')}
        raise AssertionError(method)


class NativeRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='native-repair-')
        self.addCleanup(self.tmp.cleanup)
        self.client = FixtureClient(self.tmp.name)
        self.adapter = CodexAdapter(codex_home=self.tmp.name, client=self.client)
        self.target = self.adapter.discover()[0]

    def prepared(self, patch=None):
        return self.adapter.prepare(self.target, self.adapter.read(self.target), {'patch': patch or {'model_verbosity': 'high'}})

    def test_projection_excludes_secret_fields_and_rejects_unknown_patch(self):
        self.assertNotIn('fixture-hidden', json.dumps(self.adapter.read(self.target)))
        with self.assertRaises(RepairError):
            self.prepared({'private_token': 'replacement'})

    def test_versioned_lifecycle_and_key_scoped_inverse(self):
        op = self.prepared()
        self.assertTrue(self.adapter.preflight(self.target, op)['ok'])
        backup = self.adapter.backup(self.target, op, self.tmp.name)
        result = self.adapter.apply(self.target, op, backup)
        self.assertEqual(self.adapter.verify(self.target, op, result)['state'], 'effective')
        self.client.user['model'] = 'new-unrelated-value'
        self.client.version += 1
        self.assertEqual(self.adapter.undo(self.target, op, backup, result)['state'], 'undone')
        self.assertEqual(self.client.user['model_verbosity'], 'low')
        self.assertEqual(self.client.user['model'], 'new-unrelated-value')
        self.assertNotIn('private_token', json.dumps(backup))

    def test_stale_preflight_has_zero_writes(self):
        op = self.prepared()
        self.client.version += 1
        with self.assertRaises(RepairError):
            self.adapter.preflight(self.target, op)
        self.assertEqual(self.client.writes, 0)

    def test_reconcile_after_lost_response_never_writes(self):
        op = self.prepared()
        backup = self.adapter.backup(self.target, op, self.tmp.name)
        self.assertEqual(self.adapter.reconcile(self.target, op, backup)['outcome'], 'not_applied')
        self.adapter.apply(self.target, op, backup)
        self.assertEqual(self.adapter.reconcile(self.target, op, backup)['outcome'], 'applied')
        self.assertEqual(self.client.writes, 1)

    def test_changed_repaired_key_blocks_undo(self):
        op = self.prepared()
        backup = self.adapter.backup(self.target, op, self.tmp.name)
        result = self.adapter.apply(self.target, op, backup)
        self.client.user['model_verbosity'] = 'medium'
        self.client.version += 1
        refused = self.adapter.undo(self.target, op, backup, result)
        self.assertFalse(refused['ok'])
        self.assertEqual(refused['state'], 'blocked')
        self.assertEqual(self.client.user['model_verbosity'], 'medium')

    def test_override_is_pending_and_static_default_has_scope_limitation(self):
        self.client.override = {'model_verbosity': 'medium'}
        op = self.prepared()
        backup = self.adapter.backup(self.target, op, self.tmp.name)
        result = self.adapter.apply(self.target, op, backup)
        self.assertEqual(self.adapter.verify(self.target, op, result)['state'], 'pending')
        self.client.override = {}
        op = self.prepared({'model': 'other-model'})
        result = self.adapter.apply(self.target, op, self.adapter.backup(self.target, op, self.tmp.name))
        receipt = self.adapter.verify(self.target, op, result)
        self.assertEqual(receipt['state'], 'effective')
        self.assertTrue(any('future' in text.lower() for text in receipt['limitations']))

    def test_interrupted_undo_reconciles_without_writing(self):
        op = self.prepared()
        backup = self.adapter.backup(self.target, op, self.tmp.name)
        result = self.adapter.apply(self.target, op, backup)
        inverse_op = {**op, 'recovery_phase': 'undo'}
        self.assertEqual(self.adapter.reconcile(self.target, inverse_op, backup)['outcome'], 'not_applied')
        self.adapter.undo(self.target, op, backup, result)
        self.assertEqual(self.adapter.reconcile(self.target, inverse_op, backup)['outcome'], 'applied')
        self.assertEqual(self.client.writes, 2)

    @unittest.skipUnless(shutil.which('codex'), 'Installed Codex protocol is verified locally; CLI absent on this runner.')
    def test_native_installed_protocol_roundtrip_in_disposable_home(self):
        home = Path(self.tmp.name)
        (home / 'config.toml').write_text('model = "fixture-model"\nmodel_verbosity = "low"\n')
        adapter = CodexAdapter(codex_home=home)
        target = adapter.discover()[0]
        op = adapter.prepare(target, adapter.read(target), {'patch': {'model_verbosity': 'high'}})
        backup = adapter.backup(target, op, self.tmp.name)
        result = adapter.apply(target, op, backup)
        self.assertEqual(adapter.verify(target, op, result)['state'], 'effective')
        with self.assertRaises(RepairError):
            adapter.apply(target, op, backup)
        self.assertEqual(adapter.undo(target, op, backup, result)['state'], 'undone')
        self.assertEqual(adapter.read(target)['projection']['model_verbosity'], 'low')
        # A newly added override must undo to absence, rather than pinning an
        # effective default that was never present in the user layer.
        op = adapter.prepare(target, adapter.read(target), {'patch': {'web_search': 'disabled'}})
        backup = adapter.backup(target, op, self.tmp.name)
        result = adapter.apply(target, op, backup)
        self.assertEqual(adapter.undo(target, op, backup, result)['state'], 'undone')
        self.assertNotIn('web_search', adapter.read(target)['user_values'])


if __name__ == '__main__':
    unittest.main()

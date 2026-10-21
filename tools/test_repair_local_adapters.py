"""All effects occur in disposable native-owner homes and Git repositories."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from repair_contracts import RepairError
from repair_local_adapters import LocalAdapter, register_adapters
from repair_local_checks import syntax_check


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()


class LocalAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='owner-adapters-')
        self.home = Path(self.tmp.name).resolve()
        (self.home / 'Backups').mkdir()
        self.adapter = LocalAdapter(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, path, value):
        path = self.home / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        path.chmod(0o640)
        return path

    def target(self, path):
        return next(t for t in self.adapter.discover() if t['identity'].get('path') == str(path))

    def operation(self, path, proposal):
        target = self.target(path)
        op = self.adapter.prepare(target, self.adapter.read(target), proposal)
        op.update(target_id=target['id'], adapter_id=self.adapter.adapter_id, adapter_version=self.adapter.version,
                  target_identity=target['identity'], step_id='step-' + target['id'])
        return target, op

    def lifecycle(self, target, op):
        self.assertTrue(self.adapter.preflight(target, op)['ok'])
        backup = self.adapter.backup(target, op, str(self.home / 'state'))
        applied = self.adapter.apply(target, op, backup)
        self.assertTrue(self.adapter.verify(target, op, applied)['ok'])
        self.assertEqual('applied', self.adapter.reconcile(target, op, backup)['outcome'])
        return backup, applied

    def test_registered_discovery_canonical_and_provider_ownership(self):
        local = self.put('.agents/skills/ours/SKILL.md', '---\nname: ours\ndescription: A local procedure.\n---\nDo the task.\n')
        provider = self.put('.agents/skills/vendor/SKILL.md', '---\nname: vendor\ndescription: Vendor.\n---\nBody\n')
        self.put('.agents/.skill-lock.json', json.dumps({'version': 3, 'skills': {'vendor': {'source': 'vendor/repo'}}}))
        self.put('.agents/tools/random.py', 'pass\n')
        self.put('.agents/tools/unify/check.py', 'pass\n')
        screened = self.put('.agents/tools/unify/validate_docs.py', 'API_KEY = \"fixture-private\"\n')
        self.assertEqual('safe_text_projection', self.target(screened)['missing_capability'])
        paths = {t['identity'].get('path') for t in self.adapter.discover()}
        self.assertIn(str(local), paths)
        self.assertNotIn(str(provider), paths)
        self.assertNotIn(str(self.home / '.agents/tools/random.py'), paths)
        self.assertIn(str(self.home / '.agents/tools/unify/check.py'), paths)
        class Registry:
            def register(self, adapter):
                self.adapter = adapter
        registry = Registry()
        register_adapters(registry, self.home)
        self.assertEqual(self.adapter.adapter_id, registry.adapter.adapter_id)

    def test_cli_patch_secret_preservation_conditional_inverse(self):
        path = self.put('.cursor/cli-config.json', json.dumps({'model': 'before', 'apiKey': 'opaque-secret', 'unknown': {'stay': 7}}))
        target, op = self.operation(path, {'patch': {'model': 'after'}})
        self.assertNotIn('opaque-secret', json.dumps(self.adapter.read(target)) + json.dumps(op))
        backup, applied = self.lifecycle(target, op)
        self.assertNotIn('opaque-secret', json.dumps(backup))
        value = json.loads(path.read_text())
        self.assertEqual('opaque-secret', value['apiKey'])
        value['newUnknown'] = True
        path.write_text(json.dumps(value))
        self.assertTrue(self.adapter.undo(target, op, backup, applied)['ok'])
        self.assertEqual({'model': 'before', 'apiKey': 'opaque-secret', 'unknown': {'stay': 7}, 'newUnknown': True}, json.loads(path.read_text()))
        self.assertEqual(0o640, path.stat().st_mode & 0o777)
        target, op = self.operation(path, {'patch': {'model': 'after'}})
        backup, applied = self.lifecycle(target, op)
        value = json.loads(path.read_text()); value['model'] = 'third'; path.write_text(json.dumps(value))
        self.assertFalse(self.adapter.undo(target, op, backup, applied)['ok'])
        self.assertEqual('third', json.loads(path.read_text())['model'])

    def test_hooks_and_app_settings_preserve_unknown_and_do_not_execute(self):
        marker = self.home / 'NEVER_EXECUTED'
        path = self.put('.cursor/hooks.json', json.dumps({'version': 1, 'hooks': {}, 'env': {'CUSTOM': 'opaque-secret'}, 'other': 8}))
        target, op = self.operation(path, {'patch': {'hooks.beforeSubmitPrompt': [{'command': 'touch ' + str(marker)}]}})
        self.assertFalse(marker.exists())
        self.assertNotIn('opaque-secret', json.dumps(self.adapter.read(target)))
        backup, applied = self.lifecycle(target, op)
        self.assertFalse(marker.exists())
        self.assertEqual(8, json.loads(path.read_text())['other'])
        self.assertTrue(self.adapter.undo(target, op, backup, applied)['ok'])
        app = self.put('.claude/settings.json', '{"model":"old","env":{"CUSTOM":"opaque-secret"}}')
        target, op = self.operation(app, {'patch': {'model': 'new'}})
        self.assertEqual('app_settings', target['category'])
        backup, applied = self.lifecycle(target, op)
        self.assertEqual('byte_verified', self.adapter.verify(target, op, applied)['state'])
        self.assertTrue(self.adapter.undo(target, op, backup, applied)['ok'])

    def test_nested_hook_leaf_keeps_secret_siblings_and_undo_recovery(self):
        path = self.put('.claude/settings.json', json.dumps({'hooks': {'PreToolUse': [{'hooks': [{'type': 'command', 'command': 'python3 canonical.py', 'timeout': 5, 'env': {'CUSTOM': 'opaque-secret'}}]}]}, 'env': {'EXTERNAL': 'also-private'}}))
        target = self.target(path)
        snapshot = self.adapter.read(target)
        self.assertNotIn('opaque-secret', json.dumps(snapshot))
        self.assertNotIn('also-private', json.dumps(snapshot))
        self.assertEqual('python3 canonical.py', snapshot['projection']['hooks']['PreToolUse'][0]['hooks'][0]['command'])
        key = 'hooks.PreToolUse.0.hooks.0.timeout'
        self.assertIn(key, target['allowed_patch_paths'])
        target, op = self.operation(path, {'patch': {key: 20}})
        backup, applied = self.lifecycle(target, op)
        self.assertEqual('not_applied', self.adapter.reconcile(target, dict(op, recovery_phase='undo'), backup)['outcome'])
        self.assertTrue(self.adapter.undo(target, op, backup, applied)['ok'])
        self.assertEqual('applied', self.adapter.reconcile(target, dict(op, recovery_phase='undo'), backup)['outcome'])
        self.assertEqual('opaque-secret', json.loads(path.read_text())['hooks']['PreToolUse'][0]['hooks'][0]['env']['CUSTOM'])
        with self.assertRaises(RepairError):
            self.operation(path, {'patch': {'hooks': {'PreToolUse': []}}})
        with self.assertRaises(RepairError):
            self.operation(path, {'patch': {'hooks.PreToolUse.0.hooks.0.command': '[REDACTED]'}})

    def test_registered_hook_script_relation_bound_to_candidate(self):
        script = self.put('.agents/tools/unify/check.py', 'value = 1\n')
        path = self.put('.cursor/hooks.json', json.dumps({'version': 1, 'hooks': {'beforeSubmitPrompt': [{'command': 'python3 ' + str(script), 'timeout': 5}]}}))
        target = self.target(path)
        self.assertIn(self.target(script)['id'], target['related_target_ids'])
        target, op = self.operation(path, {'patch': {'hooks.beforeSubmitPrompt.0.timeout': 10}})
        script.write_text('value = 2\n')
        self.assertFalse(self.adapter.preflight(target, op)['ok'])

    def test_hook_command_private_assignments_and_query_credentials_hidden(self):
        path = self.put('.cursor/hooks.json', json.dumps({'version': 1, 'hooks': {'beforeSubmitPrompt': [{'command': 'CUSTOM_ENV=opaque-private python3 canonical.py'}, {'command': 'curl https://example.invalid/check?key=opaque-query'}]}}))
        snapshot = self.adapter.read(self.target(path))
        self.assertNotIn('opaque-private', json.dumps(snapshot))
        self.assertNotIn('opaque-query', json.dumps(snapshot))

    def test_invalid_native_json_is_not_normalized_over_unknown_fields(self):
        for raw in ('{"model":"first","model":"second"}', '{"model":"before","unknown":NaN}'):
            path = self.put('.cursor/cli-config.json', raw)
            with self.assertRaises(RepairError):
                self.operation(path, {'patch': {'model': 'after'}})
            self.assertEqual(raw, path.read_text())

    def test_json_schema_rejects_invalid_native_key_type(self):
        path = self.put('.cursor/cli-config.json', '{"model":"before"}')
        with self.assertRaises(RepairError):
            self.operation(path, {'patch': {'model': {'invalid': 'object'}}})

    def test_repeated_apply_is_idempotent_and_backup_tampering_blocks_undo(self):
        path = self.put('.cursor/cli-config.json', '{"model":"before"}')
        target, op = self.operation(path, {'patch': {'model': 'after'}})
        backup, applied = self.lifecycle(target, op)
        again = self.adapter.apply(target, op, backup)
        self.assertEqual(applied, again)
        self.assertEqual(applied['after_state']['inode'], path.stat().st_ino)
        Path(backup['path']).write_text('tampered')
        self.assertFalse(self.adapter.undo(target, op, backup, applied)['ok'])
        self.assertEqual('after', json.loads(path.read_text())['model'])

    def test_skill_lifecycle_retains_canonical_links_and_checks(self):
        path = self.put('.agents/skills/ours/SKILL.md', '---\nname: ours\ndescription: Do a concrete job.\n---\nOriginal body.\n')
        for runtime in ('.claude', '.cursor'):
            link = self.home / runtime / 'skills/ours'; link.parent.mkdir(parents=True); link.symlink_to(path.parent)
        target, op = self.operation(path, {'candidate': path.read_text().replace('Original', 'Changed')})
        kinds = {c['kind'] for c in op['checks']}
        self.assertIn('structural', kinds)
        self.assertIn('lifecycle', kinds)
        backup, applied = self.lifecycle(target, op)
        self.assertTrue((self.home / '.claude/skills/ours').is_symlink())
        self.assertIn('runtime', ' '.join(self.adapter.verify(target, op, applied)['limitations']).lower())
        self.assertTrue(self.adapter.undo(target, op, backup, applied)['ok'])

    def test_skill_reference_and_discovery_context_bound_before_effect(self):
        path = self.put('.agents/skills/ours/SKILL.md', '---\nname: ours\ndescription: Do a concrete job.\n---\nRead [reference](references/guide.md).\n')
        reference = self.put('.agents/skills/ours/references/guide.md', 'original guide\n')
        link = self.home / '.claude/skills/ours'; link.parent.mkdir(parents=True); link.symlink_to(path.parent)
        target, op = self.operation(path, {'candidate': path.read_text().replace('Read ', 'Consult ')})
        reference.write_text('changed guide\n')
        self.assertFalse(self.adapter.preflight(target, op)['ok'])
        reference.write_text('original guide\n')
        target, op = self.operation(path, {'candidate': path.read_text().replace('Read ', 'Consult ')})
        link.unlink()
        self.assertFalse(self.adapter.preflight(target, op)['ok'])

    def test_real_adapter_coordinator_contract_and_private_inverse(self):
        from repair_registry import RepairRegistry
        from universal_repairs import Coordinator
        path = self.put('.cursor/cli-config.json', '{"model":"before","apiKey":"opaque-secret"}')
        registry = RepairRegistry(); registry.register(self.adapter)
        service = Coordinator(self.home / 'coordinator', registry)
        target = self.target(path)
        plan = service.freeze('fix native model', [{'target_id': target['id'], 'proposal': {'patch': {'model': 'after'}}}])
        self.assertNotIn('opaque-secret', json.dumps(plan))
        job = service.approve(plan['plan_id'], plan['digest'])
        result = service.run_job(job['job_id'])
        self.assertEqual('completed', result['status'])
        self.assertNotIn('opaque-secret', json.dumps(result))
        self.assertEqual('undone', service.undo(job['job_id'])['status'])
        self.assertEqual('opaque-secret', json.loads(path.read_text())['apiKey'])

    def test_hook_addition_remains_same_registered_owner_during_coordinator_undo(self):
        from repair_registry import RepairRegistry
        from universal_repairs import Coordinator
        path = self.put('.cursor/hooks.json', '{"version":1,"hooks":{},"other":7}')
        registry = RepairRegistry(); registry.register(self.adapter)
        service = Coordinator(self.home / 'coordinator', registry)
        target = self.target(path)
        plan = service.freeze('add native hook', [{'target_id': target['id'], 'proposal': {'patch': {'hooks.beforeSubmitPrompt': [{'command': 'python3 canonical.py'}]}}}])
        job = service.approve(plan['plan_id'], plan['digest'])
        self.assertEqual('completed', service.run_job(job['job_id'])['status'])
        self.assertEqual('undone', service.undo(job['job_id'])['status'])
        self.assertEqual({'version': 1, 'hooks': {}, 'other': 7}, json.loads(path.read_text()))

    def test_python_shell_js_syntax_and_executable_lifecycle(self):
        for suffix, good, bad in [('py', 'value = 3\n', 'def broken(:\n'), ('sh', '#!/bin/sh\necho good\n', 'if then\n'), ('js', 'const value = 3;\n', 'const = ;\n')]:
            self.assertEqual('passed', syntax_check(good, suffix)['status'])
            self.assertEqual('failed', syntax_check(bad, suffix)['status'])
        path = self.put('.agents/tools/unify/check.py', 'value = 1\n')
        target, op = self.operation(path, {'candidate': 'value = 2\n'})
        backup, applied = self.lifecycle(target, op)
        self.assertTrue(self.adapter.undo(target, op, backup, applied)['ok'])
        with self.assertRaises(RepairError):
            self.operation(path, {'candidate': 'def bad(:\n'})

    def test_cas_mode_inode_and_alias_rejected(self):
        path = self.put('.cursor/cli-config.json', '{"model":"before"}')
        target, op = self.operation(path, {'patch': {'model': 'after'}})
        path.chmod(0o600)
        self.assertFalse(self.adapter.preflight(target, op)['ok'])
        path.chmod(0o640)
        replacement = path.with_suffix('.new'); replacement.write_bytes(path.read_bytes()); replacement.chmod(0o640); replacement.replace(path)
        self.assertFalse(self.adapter.preflight(target, op)['ok'])
        path.unlink(); outside = self.put('outside.json', '{"model":"outside"}'); path.symlink_to(outside)
        self.assertFalse(self.adapter.preflight(target, op)['ok'])

    def test_noop_generated_copy_has_no_empty_publication_commit(self):
        repo = self.home / '.codex'; repo.mkdir()
        path = self.put('.codex/AGENTS.md', 'same generated bytes\n')
        self.put('.agents/instructions/shared.md', 'shared\n')
        git(repo, 'init', '-b', 'main'); git(repo, 'config', 'user.email', 'fixture@example.invalid'); git(repo, 'config', 'user.name', 'Fixture')
        git(repo, 'add', '.'); git(repo, 'commit', '-m', 'baseline')
        remote = self.home / 'remote.git'; subprocess.run(['git', 'init', '--bare', str(remote)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        git(repo, 'remote', 'add', 'origin', str(remote)); git(repo, 'push', '-u', 'origin', 'main')
        target = self.target(path); snap = self.adapter.read(target)
        op = {'target_id': target['id'], 'action': 'replace', 'selector': {'path': str(path)}, 'candidate': path.read_text(), 'before_state': self.adapter.state(path)[1], 'inverse': {'content': path.read_text()}, 'expected_fingerprint': snap['fingerprint'], 'expected_version': snap['version'], 'context_fingerprint': snap['context_fingerprint'], 'checks': [], 'public_diff': ''}
        ops = self.adapter.prepare_bundle([op], {t['id']: t for t in self.adapter.discover()})
        self.assertFalse(any(item['action'] == 'publish' for item in ops))

    def test_rule_union_and_one_exact_path_publication(self):
        repo = self.home / '.agents'
        for name in ('shared.md', 'codex.md', 'claude.md', 'shared-style.md', 'claude-style.md'):
            self.put('.agents/instructions/' + name, 'Original ' + name + '\n')
        self.put('.agents/instructions/codex-style.md', '## Voice\nPlain\n## Delegation and model routing\nRoute\n')
        builder = self.home / '.agents/tools/unify/build_instructions.py'; builder.parent.mkdir(parents=True)
        shutil.copyfile(Path.home() / '.agents/tools/unify/build_instructions.py', builder)
        self.put('.codex/config.toml', 'model = "fixture"\n')
        for directory in ('.claude/output-styles', '.cursor/rules'):
            (self.home / directory).mkdir(parents=True)
        git(repo, 'init', '-b', 'main'); git(repo, 'config', 'user.email', 'fixture@example.invalid'); git(repo, 'config', 'user.name', 'Fixture')
        self.put('.agents/unrelated.md', 'original unrelated\n')
        git(repo, 'add', '.'); git(repo, 'commit', '-m', 'baseline')
        remote = self.home / 'remote.git'; subprocess.run(['git', 'init', '--bare', str(remote)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        git(repo, 'remote', 'add', 'origin', str(remote)); git(repo, 'push', '-u', 'origin', 'main')
        self.put('.agents/unrelated.md', 'unrelated staged\n')
        git(repo, 'add', 'unrelated.md')
        staged = git(repo, 'show', ':unrelated.md')
        a, op1 = self.operation(repo / 'instructions/shared.md', {'candidate': 'Shared NEW\n'})
        b, op2 = self.operation(repo / 'instructions/codex.md', {'candidate': 'Codex NEW\n'})
        targets = {t['id']: t for t in self.adapter.discover()}
        ops = self.adapter.prepare_bundle([op1, op2], targets)
        publications = [o for o in ops if o['action'] == 'publish']
        self.assertEqual(1, len(publications))
        codex = next(o for o in ops if o.get('selector', {}).get('path') == str(self.home / '.codex/AGENTS.md'))
        self.assertIn('Shared NEW', codex['candidate']); self.assertIn('Codex NEW', codex['candidate'])
        self.assertEqual(len(ops), len({o['target_id'] for o in ops}))
        backups = [self.adapter.backup(targets[o['target_id']], o, str(self.home / 'state')) for o in ops]
        for o, backup in zip(ops, backups):
            t = targets[o['target_id']]
            result = self.adapter.apply(t, o, backup)
            self.assertTrue(self.adapter.verify(t, o, result)['ok'])
        self.assertEqual(['instructions/codex.md', 'instructions/shared.md'], git(repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines())
        self.assertEqual(git(repo, 'rev-parse', 'HEAD'), git(remote, 'rev-parse', 'main'))
        self.assertEqual(staged, git(repo, 'show', ':unrelated.md'))
        for o, backup in reversed(list(zip(ops, backups))):
            self.assertTrue(self.adapter.undo(targets[o['target_id']], o, backup, {})['ok'])
        self.assertEqual('Original shared.md\n', (repo / 'instructions/shared.md').read_text())

"""All effects occur in disposable native-owner homes and Git repositories."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

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

    def test_receipt_hook_is_a_registered_source_with_installed_hosts(self):
        guard = self.put('.agents/tools/approvals/receipt_store_guard.py', 'def reason(payload):\n    return None\n')
        wrapper = self.put('.agents/tools/guards/composio_guard.py', 'def local_receipt_reason(payload):\n    import receipt_store_guard\n    return receipt_store_guard.reason(payload)\n')
        config = self.put('.claude/settings.json', json.dumps({'hooks': {'PreToolUse': [{'hooks': [{'type': 'command', 'command': 'python3 ' + str(wrapper)}]}]}}))
        target = self.target(guard)
        self.assertEqual('receipt-store-v1', target['hook_behavior_profile'])
        self.assertEqual(['claude'], [host['runtime'] for host in target['hook_hosts']])
        self.assertIn(self.target(config)['id'], target['related_target_ids'])
        self.assertIn(target['id'], self.target(config)['related_target_ids'])
        before = target['hook_hosts']
        wrapper.write_text(wrapper.read_text() + '# changed registration code\n')
        self.assertNotEqual(before, self.target(guard)['hook_hosts'])
        wrapper.write_text('# receipt_store_guard.reason(payload)\n')
        self.assertEqual([], self.target(guard)['hook_hosts'])
        wrapper.write_text('def local_receipt_reason(payload):\n    import receipt_store_guard\n    receipt_store_guard=other\n    return receipt_store_guard.reason(payload)\n')
        self.assertEqual([], self.target(guard)['hook_hosts'])

    def test_python_parser_token_pattern_is_source_but_credential_values_are_withheld(self):
        from repair_local_checks import python_source_projection
        source = 'import re\nTOKEN = re.compile(r"[a-z]+")\n'
        self.assertEqual((source, False), python_source_projection(source))
        source = 'import re\ntokens = [value] + re.findall(r"[a-z]+", value)\n'
        self.assertEqual((source, False), python_source_projection(source))
        source = 'import re\nTOKEN = re.compile(r"[a-z]+", re.M)\n'
        self.assertEqual((source, False), python_source_projection(source))
        for source in ('TOKEN = "private-fixture-value"\n',
                       'import re\nTOKEN = re.compile("sk-proj-1234567890private")\n',
                       'import re\ntokens = re.findall("[a-z]+", "private-fixture-value")\n',
                       'import re\nre = arbitrary\nTOKEN = re.compile("private-fixture-value")\n'):
            self.assertTrue(python_source_projection(source)[1])

    def test_regex_projection_rejects_mutation_and_shadowed_imports(self):
        from repair_local_checks import python_source_projection
        for change in ('re.compile = lambda value: value', 'class re: pass',
                       'def re(): pass', 'from other import re', 'import other as re',
                       'setattr(re, "compile", arbitrary)', 'alias = re',
                       'import re as alias\nalias.compile = arbitrary',
                       're.__dict__["compile"] = lambda value: value',
                       're.__setattr__("compile", lambda value: value)',
                       're.__dict__.update(compile=lambda value: value)'):
            source = 'import re\n' + change + '\nTOKEN = re.compile("opaque-private-value")\n'
            with self.subTest(change=change):
                self.assertTrue(python_source_projection(source)[1])

    def test_script_and_hook_config_apply_in_source_order_for_either_selection(self):
        for script_first in (False, True):
            with self.subTest(script_first=script_first):
                script = self.put('.agents/tools/unify/check.py', 'value = 1\n')
                config = self.put('.cursor/hooks.json', json.dumps({'version': 1, 'hooks': {'beforeSubmitPrompt': [{'command': 'python3 ' + str(script), 'timeout': 5}]}}))
                st, so = self.operation(script, {'candidate': 'value = 2\n'})
                ct, co = self.operation(config, {'patch': {'hooks.beforeSubmitPrompt.0.timeout': 10}})
                targets = {target['id']: target for target in self.adapter.discover()}
                bundle = self.adapter.prepare_bundle([so, co] if script_first else [co, so], targets)
                self.assertEqual(str(script), bundle[0]['selector']['path'])
                backups = [self.adapter.backup(targets[op['target_id']], op, str(self.home / 'state')) for op in bundle]
                for op, backup in zip(bundle, backups):
                    result = self.adapter.apply(targets[op['target_id']], op, backup)
                    self.assertTrue(self.adapter.verify(targets[op['target_id']], op, result)['ok'])

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
        self.assertIn('syntax', kinds)
        self.assertIn('owner_lifecycle', kinds)
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

    def test_python_guard_runtime_values_stay_exact_and_repairable(self):
        before = ("import os\n"
                  "token = os.getenv('SERVICE_TOKEN')\n"
                  "command = os.getenv('COMMAND_NAME', 'python3 canonical.py')\n"
                  "request = {'token': token, 'command': command}\n"
                  "timeout = 30\n")
        path = self.put('.agents/tools/guards/pre_tool_guard.py', before)
        target = self.target(path)
        self.assertNotIn('missing_capability', target)
        self.assertEqual('py', target['source_language'])
        self.assertEqual(before, self.adapter.read(target)['projection']['content'])
        target, op = self.operation(path, {'candidate': before.replace('timeout = 30', 'timeout = 40')})
        self.assertEqual('syntax', op['checks'][0]['kind'])
        backup, applied = self.lifecycle(target, op)
        self.assertTrue(self.adapter.undo(target, op, backup, applied)['ok'])
        self.assertEqual(before, path.read_text())
        self.put('.agents/skills/ours/SKILL.md', '---\nname: ours\ndescription: Do a job.\n---\nUse the script.\n')
        skill_script = self.put('.agents/skills/ours/scripts/guard.py', before)
        self.assertEqual('py', self.target(skill_script)['source_language'])
        self.assertEqual(before, self.adapter.read(self.target(skill_script))['projection']['content'])

    def test_python_actual_credential_literal_withheld_and_no_secret_preimage(self):
        secret = 'opaque-private-literal-723'
        path = self.put('.agents/tools/guards/pre_tool_guard.py', "token = " + repr(secret) + "\n")
        target = self.target(path)
        self.assertEqual('safe_text_projection', target['missing_capability'])
        self.assertNotIn(secret, json.dumps(self.adapter.read(target)))
        with self.assertRaises(RepairError):
            self.operation(path, {'candidate': "token = None\n"})
        self.assertFalse((self.home / 'Backups/universal-repairs').exists())
        clean = self.put('.agents/tools/unify/check.py', "token = None\n")
        with self.assertRaises(RepairError):
            self.operation(clean, {'candidate': "token = " + repr(secret) + "\n"})
        self.assertEqual("token = None\n", clean.read_text())

    def test_python_owner_projection_inspects_literals_not_variable_names(self):
        from repair_local_checks import python_source_projection
        safe = ["token = os.getenv('TOKEN')\n", "data = {'Authorization': token, 'command': command}\n",
                "pattern = re.compile(r'api[_-]?key|token|password')\n", "error = 'token missing'\n",
                "headers = {'Authorization': 'Bearer ' + token}\n",
                "schema = {'token': {'type': 'string'}}\n", "token, command = os.getenv('TOKEN'), 'echo ready'\n"]
        unsafe = ["value = 'sk-proj-' + 'fixtureOnlyCredential723'\n",  # known complete literal below is checked separately
                  "api_key = 'opaque-private-value'\n", "data = {'apiKey': 'opaque-private-value'}\n",
                  "request(token='opaque-private-value')\n", "command = 'API_KEY=opaque-private-value python3 run.py'\n",
                  "value = 'sk-proj-fixtureOnlyCredential723'\n"]
        # Composite stored credentials are inspected structurally, without eval.
        for source in safe:
            self.assertEqual((source, False), python_source_projection(source))
        for source in unsafe:
            projected, withheld = python_source_projection(source)
            self.assertTrue(withheld)
            self.assertNotIn('opaque-private-value', projected)
            self.assertNotIn('sk-proj-fixtureOnlyCredential723', projected)
        self.assertTrue(python_source_projection('def broken(:\n')[1])

    def test_composite_credentials_never_reach_first_ai_prompt(self):
        import repair_ai
        secrets = ["password = 'synthetic-' + 'private-value'\n",
                   "password = f'synthetic-private-{value}'\n",
                   "password = os.getenv('PASSWORD', 'synthetic-private-value')\n",
                   "password = settings.get('password', default='synthetic-private-value')\n"]
        for source in secrets:
            path = self.put('.agents/tools/guards/pre_tool_guard.py', source)
            target = self.target(path)
            self.assertEqual('safe_text_projection', target.get('missing_capability'))
            snapshot = self.adapter.read(target)
            self.assertNotIn('synthetic-private', json.dumps(snapshot))
            with patch.object(repair_ai, 'invoke', side_effect=RuntimeError('stop before provider')) as invoke:
                repair_ai.propose_repair('Review registered source.', [{'target': target, 'snapshot': snapshot}])
            for call in invoke.call_args_list:
                self.assertNotIn('synthetic-private', call.args[0])
        path.write_text("password = os.getenv('PASSWORD')\n")
        target = self.target(path)
        with patch.object(repair_ai, 'invoke', side_effect=RuntimeError('stop before provider')) as invoke:
            repair_ai.propose_repair('Review registered source.', [{'target': target, 'snapshot': self.adapter.read(target)}])
        self.assertEqual(1, invoke.call_count)
        self.assertIn("os.getenv('PASSWORD')", invoke.call_args.args[0])

    def test_canonical_guard_and_owned_skill_reference_discovery(self):
        paths = [self.put('.agents/tools/guards/composio_guard.py', 'value = 1\n'),
                 self.put('.agents/tools/guards/context_watch.py', 'value = 1\n'),
                 self.put('.agents/tools/guards/own.go', 'package guard\nfunc Check() {}\n')]
        self.put('.agents/skills/ours/SKILL.md', '---\nname: ours\ndescription: Owned.\n---\nRead `references/guide.md`.\n')
        reference = self.put('.agents/skills/ours/references/guide.md', 'Read the source.\n')
        self.put('.agents/skills/alex-director/SKILL.md', '---\nname: alex-director\ndescription: Director.\n---\nRead gates.\n')
        gates = self.put('.agents/skills/alex-director/references/gates.md', 'Alex gate context.\n')
        self.put('.agents/tools/guards/generated/skip.py', 'value = 1\n')
        self.put('.agents/tools/guards/cache.py', '# GENERATED BY native owner\n')
        linked = self.home / '.agents/tools/guards/link.py'; linked.symlink_to(paths[0])
        rows = self.adapter.discover(); by_path = {r['identity']['path']: r for r in rows}
        for path in paths:
            self.assertEqual(path.suffix[1:], by_path[str(path)]['content_language'])
        self.assertIn(str(reference), by_path)
        self.assertEqual(['read'], by_path[str(gates)]['capabilities'])
        with self.assertRaises(RepairError):
            self.adapter.prepare(by_path[str(gates)], self.adapter.read(by_path[str(gates)]), {'candidate': 'Changed policy.\n'})
        self.assertNotIn(str(linked), by_path)
        self.assertFalse(any('/generated/' in p or p.endswith('/cache.py') for p in by_path))
        expected = 'passed' if shutil.which('gofmt') else 'unavailable'
        self.assertEqual(expected, syntax_check(paths[-1].read_text(), 'go')['status'])
        if shutil.which('gofmt'):
            self.assertEqual('failed', syntax_check('package broken\nfunc (', 'go')['status'])

    def test_canonical_gates_excerpt_is_readonly_screened_and_full_file_bound(self):
        import repair_ai
        from repair_local_adapters import sha
        skill = self.put('.agents/skills/alex-director/SKILL.md', '---\nname: alex-director\ndescription: Director.\n---\nRead gates.\n')
        source = ("# Policy context\npassword = 'synthetic-private-outside'\n"
                  "## Alex's gates (the one list)\nAsk Alex before spending money.\n"
                  "## Historical examples\ncommand = run-private-example\n")
        gates = self.put('.agents/skills/alex-director/references/gates.md', source)
        target = self.target(gates)
        self.assertEqual('context_only_policy', target['missing_capability'])
        snapshot = self.adapter.read(target)
        projected = snapshot['projection']['content']
        self.assertNotIn('synthetic-private-outside', json.dumps(snapshot))
        self.assertNotIn('run-private-example', json.dumps(snapshot))
        self.assertEqual(source.splitlines().index('Ask Alex before spending money.'), projected.splitlines().index('Ask Alex before spending money.'))
        self.assertEqual(len(source.splitlines()), len(projected.splitlines()))
        self.assertEqual(sha(gates.read_bytes()), snapshot['whole_file_sha256'])
        self.assertIn('other sections are not reviewed', ' '.join(target['limitations']))
        self.assertIn('blank-padded', ' '.join(target['limitations']))
        with patch.object(repair_ai, 'invoke', side_effect=RuntimeError('stop before provider')) as invoke:
            repair_ai.propose_repair('Review policy context.', [{'target': target, 'snapshot': snapshot}])
        self.assertEqual(1, invoke.call_count)
        self.assertNotIn('synthetic-private-outside', invoke.call_args.args[0])
        self.assertNotIn('run-private-example', invoke.call_args.args[0])
        with self.assertRaises(RepairError):
            self.adapter.prepare(target, snapshot, {'candidate': projected + 'Altered gates.\n'})
        original_fingerprint = snapshot['fingerprint']
        gates.write_text(source.replace('synthetic-private-outside', 'synthetic-private-changed'))
        changed = self.adapter.read(target)
        self.assertEqual(projected, changed['projection']['content'])
        self.assertNotEqual(original_fingerprint, changed['fingerprint'])
        self.assertNotEqual(snapshot['whole_file_sha256'], changed['whole_file_sha256'])
        other = self.put('.agents/skills/alex-director/references/other-policy.md', source)
        other_target = self.target(other)
        self.assertEqual('safe_text_projection', other_target['missing_capability'])
        self.assertNotIn('synthetic-private-outside', json.dumps(self.adapter.read(other_target)))
        gates.write_text(source.replace('Ask Alex before spending money.', 'password = "synthetic-private-inside"'))
        self.assertEqual('safe_text_projection', self.target(gates)['missing_capability'])
        self.assertNotIn('synthetic-private-inside', json.dumps(self.adapter.read(self.target(gates))))

    def publication_fixture(self):
        repo = self.home / '.cursor'; repo.mkdir()
        path = self.put('.cursor/cli-config.json', '{"model":"before"}\n')
        git(repo, 'init', '-b', 'main'); git(repo, 'config', 'user.email', 'fixture@example.invalid'); git(repo, 'config', 'user.name', 'Fixture')
        git(repo, 'add', '.'); git(repo, 'commit', '-m', 'baseline')
        remote = self.home / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(remote)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        git(repo, 'remote', 'add', 'origin', str(remote)); git(repo, 'push', '-u', 'origin', 'main')
        target, op = self.operation(path, {'patch': {'model': 'after'}})
        targets = {t['id']: t for t in self.adapter.discover()}
        ops = self.adapter.prepare_bundle([op], targets)
        backups = [self.adapter.backup(targets[o['target_id']], o, str(self.home / 'state')) for o in ops]
        self.adapter.apply(target, ops[0], backups[0])
        return repo, remote, path, targets[ops[-1]['target_id']], ops[-1], backups[-1]

    def test_existing_own_commit_push_retry_and_lost_response(self):
        repo, remote, path, target, op, backup = self.publication_fixture()
        native = self.adapter.git
        def fail_push(root, *args, **kwargs):
            if args[0] == 'push':
                raise RepairError('synthetic_push_failure')
            return native(root, *args, **kwargs)
        with patch.object(self.adapter, 'git', side_effect=fail_push):
            with self.assertRaises(RepairError):
                self.adapter.apply(target, op, backup)
        own = git(repo, 'rev-parse', 'HEAD')
        self.assertNotEqual(own, git(remote, 'rev-parse', 'main'))
        self.assertEqual('not_applied', self.adapter.reconcile(target, op, backup)['outcome'])
        result = self.adapter.apply(target, op, backup)
        self.assertEqual(own, result['commit'])
        self.assertEqual(own, git(remote, 'rev-parse', 'main'))
        def lost_push(root, *args, **kwargs):
            result = native(root, *args, **kwargs)
            if args[0] == 'push':
                raise RepairError('synthetic_lost_response')
            return result
        with patch.object(self.adapter, 'git', side_effect=lost_push):
            with self.assertRaises(RepairError):
                self.adapter.undo(target, op, backup, result)
        inverse = git(repo, 'rev-parse', 'HEAD')
        self.assertEqual('before', json.loads(path.read_text())['model'])
        self.assertEqual('applied', self.adapter.reconcile_undo(target, op, backup)['outcome'])
        self.assertTrue(self.adapter.undo(target, op, backup, result)['ok'])
        self.assertEqual(inverse, git(repo, 'rev-parse', 'HEAD'))

    def test_restore_readback_failure_propagates_for_inverse_reconcile(self):
        repo, remote, path, target, op, backup = self.publication_fixture()
        result = self.adapter.apply(target, op, backup)
        native = self.adapter.restore_one
        def restored_then_lost(*args, **kwargs):
            self.assertTrue(native(*args, **kwargs))
            raise RepairError('synthetic_restoration_response_lost')
        with patch.object(self.adapter, 'restore_one', side_effect=restored_then_lost):
            with self.assertRaises(RepairError):
                self.adapter.undo(target, op, backup, result)
        self.assertEqual('before', json.loads(path.read_text())['model'])
        self.assertEqual('not_applied', self.adapter.reconcile_undo(target, op, backup)['outcome'])
        self.assertTrue(self.adapter.undo(target, op, backup, result)['ok'])
        self.assertEqual(git(repo, 'rev-parse', 'HEAD'), git(remote, 'rev-parse', 'main'))

    def test_coordinator_recovers_interrupted_publication_inverse(self):
        from repair_registry import RepairRegistry
        from universal_repairs import Coordinator
        original_home = self.home
        for failure in ('first_member', 'all_members', 'inverse_push', 'unknown_member'):
            with self.subTest(failure=failure):
                self.home = original_home / failure; self.home.mkdir()
                (self.home / 'Backups').mkdir()
                self.adapter = LocalAdapter(self.home)
                repo = self.home / '.cursor'; repo.mkdir()
                model = self.put('.cursor/cli-config.json', '{"model":"before","unrelated":7}\n')
                hook = self.put('.cursor/hooks.json', '{"version":1,"hooks":{},"unrelated":8}\n')
                git(repo, 'init', '-b', 'main'); git(repo, 'config', 'user.email', 'fixture@example.invalid'); git(repo, 'config', 'user.name', 'Fixture')
                git(repo, 'add', '.'); git(repo, 'commit', '-m', 'baseline')
                remote = self.home / 'remote.git'
                subprocess.run(['git', 'init', '--bare', str(remote)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                git(repo, 'remote', 'add', 'origin', str(remote)); git(repo, 'push', '-u', 'origin', 'main')
                registry = RepairRegistry(); registry.register(self.adapter)
                service = Coordinator(self.home / 'coordinator', registry)
                plan = service.freeze('repair two native sources', [
                    {'target_id': self.target(model)['id'], 'proposal': {'patch': {'model': 'after'}}},
                    {'target_id': self.target(hook)['id'], 'proposal': {'patch': {'hooks.beforeSubmitPrompt': [{'command': 'python3 owned.py'}]}}}])
                job = service.approve(plan['plan_id'], plan['digest']); job_id = job['job_id']
                self.assertEqual('completed', service.run_job(job_id)['status'])
                forward_head = git(repo, 'rev-parse', 'HEAD')
                native_restore = self.adapter.restore_one; restored = []
                def restore_then_interrupt(*args, **kwargs):
                    outcome = native_restore(*args, **kwargs)
                    restored.append(args[1]['selector']['path'])
                    if len(restored) == (2 if failure == 'all_members' else 1):
                        raise RepairError('synthetic_member_restoration_response_lost')
                    return outcome
                native_git = self.adapter.git
                def fail_inverse_push(root, *args, **kwargs):
                    if args[0] == 'push':
                        raise RepairError('synthetic_inverse_push_failure')
                    return native_git(root, *args, **kwargs)
                with patch.object(self.adapter, 'git', side_effect=fail_inverse_push) if failure == 'inverse_push' else patch.object(self.adapter, 'restore_one', side_effect=restore_then_interrupt):
                    self.assertEqual('unknown', service.undo(job_id)['status'])
                interrupted_head = git(repo, 'rev-parse', 'HEAD')
                self.assertEqual(forward_head, git(remote, 'rev-parse', 'main'))
                if failure == 'unknown_member':
                    model.write_text('{"model":"newer-human-value","unrelated":77}\n')
                    before = {p: p.read_bytes() for p in (model, hook)}
                    self.assertEqual('unknown', service.reconcile(job_id)['status'])
                    self.assertEqual('unknown', service.resume(job_id)['status'])
                    self.assertEqual(before, {p: p.read_bytes() for p in (model, hook)})
                    self.assertEqual(interrupted_head, git(repo, 'rev-parse', 'HEAD'))
                    continue
                self.assertEqual('undoing', service.reconcile(job_id)['status'])
                self.assertEqual('undoing', service.resume(job_id)['status'])
                self.assertEqual('undone', service.run_job(job_id)['status'])
                self.assertEqual({'model': 'before', 'unrelated': 7}, json.loads(model.read_text()))
                self.assertEqual({'version': 1, 'hooks': {}, 'unrelated': 8}, json.loads(hook.read_text()))
                self.assertEqual(git(repo, 'rev-parse', 'HEAD'), git(remote, 'rev-parse', 'main'))
                if failure == 'inverse_push':
                    self.assertEqual(interrupted_head, git(repo, 'rev-parse', 'HEAD'))
                self.assertEqual('1', git(repo, 'rev-list', '--count', forward_head + '..HEAD'))

    def test_inverse_commit_pending_push_is_retried_without_new_commit(self):
        repo, remote, path, target, op, backup = self.publication_fixture()
        result = self.adapter.apply(target, op, backup)
        native = self.adapter.git
        def fail_push(root, *args, **kwargs):
            if args[0] == 'push':
                raise RepairError('synthetic_push_failure')
            return native(root, *args, **kwargs)
        with patch.object(self.adapter, 'git', side_effect=fail_push):
            with self.assertRaises(RepairError):
                self.adapter.undo(target, op, backup, result)
        inverse = git(repo, 'rev-parse', 'HEAD')
        self.assertEqual('not_applied', self.adapter.reconcile_undo(target, op, backup)['outcome'])
        self.assertTrue(self.adapter.undo(target, op, backup, result)['ok'])
        self.assertEqual(inverse, git(repo, 'rev-parse', 'HEAD'))
        self.assertEqual(inverse, git(remote, 'rev-parse', 'main'))

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
        shutil.copyfile(Path(__file__).parent / 'fixtures/native_instruction_builder.py', builder)
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

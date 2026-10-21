import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import test_local_file_repairs as fixtures
import local_file_ai as ai
import local_file_repairs as repairs


class AITests(unittest.TestCase):
    def setUp(self):
        fixtures.RepairTests.setUp(self)
        self.peer = self.rules / 'other.md'
        self.index['findings'] = [{'id': 'f' * 24, 'evidence': [{'file_id': self.row['id']}, {'file_id': next(r['id'] for r in self.index['files'] if r['path'] == str(self.peer))}]}]
        self.index_path.write_text(json.dumps(self.index))
        self.worker = ai.SuggestionService(self.service)

    def tearDown(self):
        fixtures.RepairTests.tearDown(self)

    def answer(self, status='proposed'):
        return {'status': status, 'summary': 'Preserve the evidence.', 'rationale': 'Clarify the existing instruction without changing authority.', 'conflicts': [{'explanation': 'The wording can be clearer.', 'evidence': [{'file_id': self.row['id'], 'line': 1, 'quote': self.before.strip()}]}], 'limitations': ['Only supplied files were reviewed.'], 'edits': [{'old_text': 'keep', 'new_text': 'preserve'}] if status == 'proposed' else []}

    def suggest(self, response=None):
        with patch.object(self.worker, 'infer', return_value=response or self.answer()):
            return self.worker.suggest(self.row['id'], self.row['sha256'], 'f' * 24)

    def test_context_exact_preview_without_source_write(self):
        result = self.suggest()
        self.assertEqual('proposed', result['status'])
        self.assertEqual(self.after, result['proposed_content'])
        self.assertIn('-Always keep', result['preview']['diff'])
        self.assertEqual({str(self.file), str(self.peer)}, {f['path'] for f in result['context_files']})
        self.assertEqual(self.before, self.file.read_text())

    def test_no_change_and_needs_decision_never_preview(self):
        for status in ['no_change', 'needs_decision']:
            with self.subTest(status=status):
                result = self.suggest(self.answer(status))
                self.assertIsNone(result['preview'])
                self.assertIsNone(result['proposed_content'])
        self.assertEqual([], list(self.service.state.glob('*.json')))
        self.assertEqual(self.before, self.file.read_text())

    def test_invalid_citations_and_edits_and_secrets_never_write(self):
        bad = []
        for field, val in [('line', 2), ('quote', 'invented'), ('file_id', 'a' * 24)]:
            value = self.answer(); value['conflicts'][0]['evidence'][0][field] = val; bad.append(value)
        value = self.answer(); value['edits'][0]['old_text'] = 'e'; bad.append(value)
        value = self.answer(); value['edits'].append(copy.copy(value['edits'][0])); bad.append(value)
        value = self.answer(); value['edits'][0]['new_text'] = 'api_key=fixture-opaque-secret'; bad.append(value)
        value = self.answer(); value['command'] = 'anything'; bad.append(value)
        value = self.answer('no_change'); value['edits'] = self.answer()['edits']; bad.append(value)
        for value in bad:
            with self.subTest(value=value), self.assertRaises(repairs.RepairError): self.suggest(value)
        self.assertEqual(self.before, self.file.read_text())
        self.assertEqual([], list(self.service.state.glob('*.json')))

    def test_stale_target_and_context_never_preview(self):
        for path in [self.file, self.peer]:
            before = path.read_bytes()
            def change(_context):
                path.write_text('Changed during inference\n')
                return self.answer()
            with patch.object(self.worker, 'infer', side_effect=change), self.assertRaises(repairs.RepairError) as caught:
                self.worker.suggest(self.row['id'], self.row['sha256'], 'f' * 24)
            self.assertEqual('stale_context', caught.exception.code)
            path.write_bytes(before)
        with self.assertRaises(repairs.RepairError): self.worker.suggest(self.row['id'], '0' * 64, None)
        self.assertEqual([], list(self.service.state.glob('*.json')))

    def test_provider_failure_is_static_and_never_writes(self):
        with patch('local_file_ai.proposal_model_catalog', return_value={'models': []}), patch('local_file_ai.subprocess.run', side_effect=OSError('sensitive raw failure')):
            with self.assertRaises(repairs.RepairError) as caught: self.worker.infer({'files': []})
        self.assertNotIn('sensitive', caught.exception.message)
        self.assertEqual(self.before, self.file.read_text())

    def test_unknown_or_unrelated_finding_rejected(self):
        with self.assertRaises(repairs.RepairError): self.worker.suggest(self.row['id'], self.row['sha256'], '0' * 24)

    def test_command_has_isolation_and_no_paid_fallback(self):
        command = ai.provider_command(Path('/tmp/schema'), Path('/tmp/output'), Path('/tmp/model-catalog.json'))
        for flag in ['--ignore-user-config', '--ignore-rules', '--ephemeral', '--skip-git-repo-check', 'read-only', '--output-schema']:
            self.assertIn(flag, command)
        self.assertIn('forced_login_method="chatgpt"', command)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', command)
        self.assertNotIn('--dangerously-bypass-hook-trust', command)

    def test_context_canonical_shared_rules_and_size_limit(self):
        shared = self.rules / 'shared.md'
        shared.write_text('Shared authority is explicit.\n')
        import local_files
        self.index = local_files.scan(self.home, roots=[(self.rules, 'fixture')])
        self.index_path.write_text(json.dumps(self.index))
        context = self.worker.context(self.row['id'], self.row['sha256'], None)
        self.assertIn(str(shared), [f['path'] for f in context['files']])
        with patch.object(ai, 'MAX_CONTEXT', len(self.before.encode())):
            context = self.worker.context(self.row['id'], self.row['sha256'], None)
        self.assertEqual([self.row['id']], [f['file_id'] for f in context['files']])
        self.assertTrue(any('exceeded' in value for value in context['limitations']))
        shared.write_text('api_key=fixture-opaque-secret\n')
        context = self.worker.context(self.row['id'], self.row['sha256'], None)
        self.assertTrue(any('unavailable or screened' in value for value in context['limitations']))

    def test_malformed_provider_result_and_overlapping_occurrences(self):
        for answer in [None, [], {}, {'status': 'proposed'}]:
            with self.subTest(answer=answer), self.assertRaises(repairs.RepairError):
                self.worker.validate(answer, self.worker.context(self.row['id'], self.row['sha256'], None))
        context = self.worker.context(self.row['id'], self.row['sha256'], None)
        context['files'][0]['content'] = 'aaa\n'
        answer = self.answer()
        answer['conflicts'][0]['evidence'][0]['quote'] = 'aaa'
        answer['edits'] = [{'old_text': 'aa', 'new_text': 'b'}]
        with self.assertRaises(repairs.RepairError): self.worker.validate(answer, context)

    def test_provider_timeout_sanitized(self):
        import subprocess
        with patch('local_file_ai.proposal_model_catalog', return_value={'models': []}), patch('local_file_ai.subprocess.run', side_effect=subprocess.TimeoutExpired('private command', 120)):
            with self.assertRaises(repairs.RepairError) as caught: self.worker.infer({'files': []})
        self.assertEqual('ai_provider_failed', caught.exception.code)
        self.assertNotIn('private command', caught.exception.message)

    def test_ai_preview_context_bound_until_apply(self):
        result = self.suggest()
        preview = result['preview']
        frozen = self.service.load(preview['repair_id'])['proposal']
        self.assertEqual(2, len(frozen['context_fingerprints']))
        self.peer.write_text('Changed after reviewed AI preview\n')
        with self.assertRaises(repairs.RepairError) as caught:
            self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual(('stale_context', 409), (caught.exception.code, caught.exception.status))
        self.assertEqual(self.before, self.file.read_text())
        self.assertFalse((self.home / 'Backups/local-file-repairs').exists())

    def test_ai_context_unchanged_apply_undo_and_applied_replay(self):
        preview = self.suggest()['preview']
        applied = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual('applied', applied['state'])
        self.assertTrue(applied['pushed'])
        self.peer.write_text('Context changed after successful apply\n')
        self.assertEqual(applied, self.service.apply(preview['repair_id'], preview['proposal_sha256']))
        restored = self.service.undo(preview['repair_id'])
        self.assertEqual('undone', restored['state'])
        self.assertTrue(restored['pushed'])
        self.assertEqual(self.before, self.file.read_text())

    def test_context_is_validated_at_freeze(self):
        context = self.worker.context(self.row['id'], self.row['sha256'], 'f' * 24)
        bindings = [{key: entry[key] for key in ['file_id', 'sha256', 'real_path']} for entry in context['files']]
        self.peer.write_text('Changed before freeze\n')
        with self.assertRaises(repairs.RepairError) as caught:
            self.service.preview(self.row['id'], self.row['sha256'], self.after, context_fingerprints=bindings)
        self.assertEqual('stale_context', caught.exception.code)
        self.assertEqual([], list(self.service.state.glob('*.json')))

    def test_failure_status_is_not_staleness(self):
        with patch('local_file_ai.proposal_model_catalog', return_value={'models': []}), patch('local_file_ai.subprocess.run', side_effect=OSError('private failure')):
            with self.assertRaises(repairs.RepairError) as caught: self.worker.infer({'files': []})
        self.assertEqual(503, caught.exception.status)
        with self.assertRaises(repairs.RepairError) as caught:
            self.worker.validate({}, self.worker.context(self.row['id'], self.row['sha256'], None))
        self.assertEqual(422, caught.exception.status)
        self.assertEqual(self.before, self.file.read_text())

    def test_canonical_evidence_precedes_optional_peers(self):
        shared = self.rules / 'shared.md'
        shared.write_text('Shared authority.\n')
        gates = self.repo / 'skills/alex-director/references/gates.md'
        gates.parent.mkdir(parents=True)
        gates.write_text('Explicit spending gate.\n')
        import local_files
        self.index = local_files.scan(self.home, roots=[(self.repo, 'fixture')])
        peer_id = next(row['id'] for row in self.index['files'] if row['path'] == str(self.peer))
        self.index['findings'] = [{'id': 'f' * 24, 'evidence': [{'file_id': self.row['id']}, {'file_id': peer_id}]}]
        self.index_path.write_text(json.dumps(self.index))
        with patch.object(ai, 'MAX_FILES', 3):
            context = self.worker.context(self.row['id'], self.row['sha256'], 'f' * 24)
        self.assertEqual([str(self.file), str(shared), str(gates)], [entry['path'] for entry in context['files']])
        self.assertTrue(any('exceeded' in value for value in context['limitations']))

    def test_canonical_gates_excerpt_preserves_lines_hash_and_screening(self):
        gates = self.repo / 'skills/alex-director/references/gates.md'
        gates.parent.mkdir(parents=True)
        policy = 'Ask Alex before spending money.'
        before = '# Gates\nIntroduction.\n\n'
        section = "## Alex's gates (the one list)\n" + policy + '\n### Detail\nKeep this policy detail.\n'
        outside = '## Examples\n{"authorization":"fixture-outside-value"}\n'
        gates.write_text(before + section + outside)
        import local_files
        self.index = local_files.scan(self.home, roots=[(self.repo, 'fixture')])
        self.index_path.write_text(json.dumps(self.index))
        context = self.worker.context(self.row['id'], self.row['sha256'], None)
        entry = next(f for f in context['files'] if f['path'] == str(gates))
        self.assertEqual('\n' * 3 + section + '\n' * 2, entry['content'])
        self.assertEqual(policy, entry['content'].splitlines()[4])
        self.assertEqual(repairs.sha(gates.read_bytes()), entry['sha256'])
        self.assertEqual(str(gates.resolve()), entry['real_path'])
        self.assertNotIn('fixture-outside-value', json.dumps(context))
        gates_row = next(row for row in self.index['files'] if row['path'] == str(gates))
        with self.assertRaises(repairs.RepairError):
            self.worker.context_file(self.index, gates_row)
        answer = self.answer()
        answer['conflicts'][0]['evidence'].append({'file_id': entry['file_id'], 'line': 5, 'quote': policy})
        with patch.object(self.worker, 'infer', return_value=answer):
            result = self.worker.suggest(self.row['id'], self.row['sha256'], None)
        self.assertTrue(any('Only the canonical gates section' in value for value in result['limitations']))
        gates.write_text(before + section + outside + 'Changed outside the excerpt.\n')
        preview = result['preview']
        with self.assertRaises(repairs.RepairError) as caught:
            self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual('stale_context', caught.exception.code)
        gates.write_text(before + section + 'api_key=fixture-inside-value\n' + outside)
        context = self.worker.context(self.row['id'], self.row['sha256'], None)
        self.assertNotIn(str(gates), [f['path'] for f in context['files']])
        self.assertTrue(any('unavailable or screened' in value for value in context['limitations']))
        self.assertNotIn('fixture-inside-value', json.dumps(context))
        binding = {'file_id': entry['file_id'], 'sha256': repairs.sha(gates.read_bytes()), 'real_path': entry['real_path']}
        with self.assertRaises(repairs.RepairError):
            self.service.validate_context_fingerprints([binding])
        gates.write_text('Policy without the exact heading.\napi_key=fixture-fallback-value\n')
        context = self.worker.context(self.row['id'], self.row['sha256'], None)
        self.assertNotIn(str(gates), [f['path'] for f in context['files']])
        binding['sha256'] = repairs.sha(gates.read_bytes())
        with self.assertRaises(repairs.RepairError):
            self.service.validate_context_fingerprints([binding])

    def test_noncanonical_peer_with_gates_heading_still_screens_whole_file(self):
        self.peer.write_text("## Alex's gates (the one list)\nSafe policy.\n## Examples\napi_key=fixture-peer-value\n")
        with self.assertRaises(repairs.RepairError) as caught:
            self.worker.context(self.row['id'], self.row['sha256'], 'f' * 24)
        self.assertEqual('context_unavailable', caught.exception.code)

    def test_all_tool_feature_defaults_explicitly_disabled(self):
        expected = {
            'shell_tool', 'apply_patch_freeform', 'hooks', 'apps', 'multi_agent', 'multi_agent_v2',
            'browser_use', 'browser_use_external', 'browser_use_full_cdp_access', 'computer_use',
            'image_generation', 'view_image', 'sleep_tool', 'goals', 'workspace_dependencies',
            'skill_search', 'plugins', 'remote_plugin', 'plugin_sharing', 'tool_suggest',
            'code_mode_host', 'in_app_browser', 'in_app_local_automation', 'realtime_conversation',
            'skill_mcp_dependency_install', 'tool_call_mcp_elicitation', 'unified_exec',
            'unified_exec_tty', 'shell_snapshot', 'artifact', 'agent_message_board', 'code_mode',
        }
        self.assertEqual(expected, set(ai.DISABLED_TOOL_FEATURES))
        command = ai.provider_command(Path('/tmp/schema'), Path('/tmp/output'), Path('/tmp/model-catalog.json'))
        overrides = [command[i + 1] for i, value in enumerate(command) if value == '-c']
        for feature in expected:
            self.assertEqual(1, overrides.count('features.' + feature + '=false'))
        for setting in ['agents.enabled=false', 'web_search="disabled"', 'features.skip_host_skill_discovery=true', 'project_doc_max_bytes=0', 'forced_login_method="chatgpt"']:
            self.assertIn(setting, overrides)

    def test_catalog_disables_model_tools_preserving_metadata_and_live_bytes(self):
        cache = self.home / 'codex-home'
        cache.mkdir()
        model = {'slug': ai.MODEL, 'display_name': 'Same subscribed model', 'shell_type': 'unified_exec', 'apply_patch_tool_type': 'freeform', 'experimental_supported_tools': ['clock', 'send_user_message_async'], 'include_skills_usage_instructions': True, 'include_apps_usage_instructions': True, 'include_plugin_usage_instructions': True, 'other_metadata': {'same': True}}
        source = cache / 'models_cache.json'
        source.write_text(json.dumps({'models': [model, {'slug': 'other'}]}))
        original = source.read_bytes()
        catalog = ai.proposal_model_catalog(cache)
        selected = catalog['models'][0]
        self.assertEqual('disabled', selected['shell_type'])
        self.assertIsNone(selected['apply_patch_tool_type'])
        self.assertEqual([], selected['experimental_supported_tools'])
        self.assertFalse(selected['include_skills_usage_instructions'])
        self.assertFalse(selected['include_apps_usage_instructions'])
        self.assertFalse(selected['include_plugin_usage_instructions'])
        self.assertEqual(model['other_metadata'], selected['other_metadata'])
        self.assertEqual(ai.MODEL, selected['slug'])
        self.assertEqual(original, source.read_bytes())
        self.assertEqual(['models_cache.json'], sorted(path.name for path in cache.iterdir()))

    def test_catalog_missing_model_static_failure_without_fallback(self):
        cache = self.home / 'codex-home'
        cache.mkdir()
        (cache / 'models_cache.json').write_text(json.dumps({'models': [{'slug': 'other'}]}))
        with self.assertRaises(repairs.RepairError) as caught:
            ai.proposal_model_catalog(cache)
        self.assertEqual(('ai_provider_failed', 503), (caught.exception.code, caught.exception.status))
        self.assertNotIn(str(cache), caught.exception.message)

    def test_command_disables_direct_nonfeature_tools_and_binds_temp_catalog(self):
        command = ai.provider_command(Path('/tmp/schema'), Path('/tmp/output'), Path('/tmp/model-catalog.json'))
        self.assertIn('tools.update_plan.enabled=false', command)
        self.assertIn('tools.experimental_request_user_input.enabled=false', command)
        self.assertIn('model_catalog_json="/tmp/model-catalog.json"', command)

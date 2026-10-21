import copy
import json
import unittest
from unittest.mock import patch

import repair_ai


def source(identifier, category='rule', content='Old behavior.\nKeep evidence.\n'):
    return {'target': {'id': identifier, 'adapter_id': 'fixture', 'category': category,
                       'owner': 'fixture', 'scope': 'local', 'identity': {},
                       'capabilities': ['candidate'], 'evidence': [], 'limitations': []},
            'snapshot': {'fingerprint': 'before', 'version': '1',
                         'context_fingerprint': 'context', 'projection': {'content': content}}}


class RepairAITests(unittest.TestCase):
    def fixture(self, sources=None, mutate=None, after='A', mutate_cases=None, before='B'):
        sources = sources or [source('one'), source('two')]
        proposals = [{'target_id': s['target']['id'], 'proposal': {'candidate': 'New behavior.\nKeep evidence.\n'},
                      'evidence': [{'file_id': s['target']['id'], 'line': 1, 'quote': 'Old behavior.'}]} for s in sources]
        if mutate:
            mutate(proposals)
        cases = [{'id': 'fix', 'purpose': 'fix', 'scenario': 'Both sources must permit new behavior.',
                  'choices': {'A': 'New behavior.', 'B': 'Old behavior.', 'C': 'Unknown behavior.'},
                  'expected': 'A', 'rationale': 'Requested repair.',
                  'evidence': [{'file_id': s['target']['id'], 'line': 1, 'quote': 'Old behavior.'} for s in sources]},
                 {'id': 'preserve', 'purpose': 'preserve', 'scenario': 'Evidence must remain.',
                  'choices': {'A': 'Discard evidence.', 'B': 'Keep evidence.', 'C': 'Invent evidence.'},
                  'expected': 'B', 'rationale': 'Preserve source requirement.',
                  'evidence': [{'file_id': s['target']['id'], 'line': 2, 'quote': 'Keep evidence.'} for s in sources]}]
        if mutate_cases:
            mutate_cases(cases)
        calls = []
        def invoke(prompt, schema):
            calls.append(prompt)
            if len(calls) == 1:
                return {'proposals': proposals, 'limitations': []}
            if len(calls) == 2:
                return {'cases': cases}
            payload = json.loads(prompt.split('EVIDENCE_JSON:\n')[1])
            self.assertEqual({'id', 'scenario', 'choices'}, set(payload['scenarios'][0]))
            changed = all('New behavior.' in f['content'] for f in payload['instructions']['files'])
            return {'choices': [{'id': 'fix', 'choice': after if changed else before}, {'id': 'preserve', 'choice': 'B'}]}
        with patch.object(repair_ai, 'invoke', side_effect=invoke):
            result = repair_ai.propose_repair('Use new behavior in both sources; preserve evidence.', sources)
        return result, calls

    def test_bundle_substitutes_all_candidates_and_binds_evidence(self):
        result, calls = self.fixture()
        self.assertEqual(2, len(result['proposals']))
        self.assertTrue(all(c['status'] == 'passed' for c in result['checks']))
        self.assertEqual(4, len(calls))
        self.assertTrue(all(c['input_digest'] and c['output_digest'] for c in result['checks']))
        candidate = json.loads(calls[-1].split('EVIDENCE_JSON:\n')[1])
        self.assertTrue(all(f['content'].startswith('New behavior.') for f in candidate['instructions']['files']))

    def test_categories_use_identical_citation_and_behavior_boundary(self):
        for category in ['rule', 'skill', 'hook', 'app_settings', 'cli_config', 'executable', 'remote_file', 'provider_api']:
            with self.subTest(category=category):
                result, _ = self.fixture([source('one', category)])
                self.assertEqual(1, len(result['proposals']))

    def test_bad_model_fields_ids_citations_and_oversize_reject_without_checks(self):
        mutations = [lambda p: p[0].update(target_id='unknown'),
                     lambda p: p[0]['proposal'].update(command='touch /tmp/no'),
                     lambda p: p[0].update(account='other'),
                     lambda p: p[0].update(checks=[{'status': 'passed'}]),
                     lambda p: p[0]['evidence'][0].update(file_id='unknown'),
                     lambda p: p[0]['evidence'][0].update(line=True),
                     lambda p: p[0]['evidence'][0].update(quote='1: Old behavior.'),
                     lambda p: p[0].update(evidence=[]),
                     lambda p: p[0]['proposal'].update(candidate='x' * 300000)]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                result, calls = self.fixture(mutate=mutation)
                self.assertEqual([], result['proposals'])
                self.assertEqual('unavailable', result['checks'][0]['status'])
                self.assertEqual(1, len(calls))

    def test_failed_or_unknown_candidate_has_no_approvable_proposal(self):
        for choice in ['B', 'unknown']:
            result, _ = self.fixture(after=choice)
            self.assertEqual([], result['proposals'])
            self.assertEqual('failed', result['checks'][0]['status'])

    def test_fix_case_must_distinguish_baseline_from_candidate(self):
        result, _ = self.fixture(before='A')
        self.assertEqual([], result['proposals'])
        self.assertEqual('failed', result['checks'][0]['status'])

    def test_each_changed_target_requires_fix_and_preserve_coverage(self):
        result, calls = self.fixture(mutate_cases=lambda cases: cases[1].update(evidence=cases[1]['evidence'][:1]))
        self.assertEqual([], result['proposals'])
        self.assertEqual('unavailable', result['checks'][0]['status'])
        self.assertEqual(2, len(calls))

    def test_screened_source_not_given_to_model(self):
        with patch.object(repair_ai, 'invoke') as invoke:
            result = repair_ai.propose_repair('repair', [source('one', content='api_key = "sk-proj-' + 'x' * 60 + '"')])
        self.assertFalse(invoke.called)
        self.assertEqual([], result['proposals'])

    def test_non_token_shaped_credentials_are_excluded_before_model(self):
        s = source('one', 'provider_api')
        s['target'].update(content_format='json', allowed_patch_paths=['enabled'])
        s['snapshot']['projection'] = {'enabled': False, 'token': 'private-real'}
        with patch.object(repair_ai, 'invoke') as invoke:
            result = repair_ai.propose_repair('repair', [s])
        self.assertFalse(invoke.called)
        self.assertEqual([], result['proposals'])

    def test_json_patch_keeps_unrelated_fields_and_never_inserts_placeholder(self):
        s = source('settings', 'app_settings')
        s['target'].update(content_format='json', allowed_patch_paths=['ui.enabled'])
        s['snapshot']['projection'] = {'ui': {'enabled': False, 'theme': 'dark'}, 'token': '[REDACTED]'}
        context, targets = repair_ai.source_context([s])
        candidate = json.loads(repair_ai.apply_proposal(targets['settings'], {'patch': {'ui.enabled': True}}))
        self.assertEqual({'ui': {'enabled': True, 'theme': 'dark'}, 'token': '[REDACTED]'}, candidate)
        self.assertNotIn('identity', context['files'][0]['target'])
        for bad in [{'patch': {'ui.theme': 'light'}}, {'patch': {'ui.enabled': 'true'}},
                    {'patch': {'ui.enabled': '[REDACTED]'}}, {'patch': {}, 'account': 'evil'}]:
            with self.assertRaises(ValueError):
                repair_ai.apply_proposal(targets['settings'], bad)

    def test_schema_omits_absent_null_and_unsupported_registered_fields(self):
        s = source('settings', 'app_settings')
        s['target'].update(content_format='json', allowed_patch_paths=['enabled', 'absent', 'optional', 'nested.missing'])
        s['snapshot']['projection'] = {'enabled': False, 'optional': None, 'nested': {}}
        _, targets = repair_ai.source_context([s])
        schema = repair_ai.proposal_schema(targets)
        patch_schema = schema['properties']['proposals']['items']['anyOf'][0]['properties']['proposal']['properties']['patch']
        self.assertEqual({'enabled': {'anyOf': [{'type': 'boolean'}, {'type': 'null'}]}}, patch_schema['properties'])
        self.assertEqual(['enabled'], patch_schema['required'])
        candidate = repair_ai.apply_proposal(targets['settings'], {'patch': {'enabled': True}})
        self.assertTrue(json.loads(candidate)['enabled'])

    def test_recursive_hooks_and_provider_values_keep_registered_structure(self):
        s = source('settings', 'hook')
        s['target'].update(content_format='json', allowed_patch_paths=['hooks'])
        hooks = {'Stop': [{'enabled': False, 'timeout': 10, 'labels': ['owned'], 'optional': None}]}
        s['snapshot']['projection'] = {'hooks': hooks, 'unrelated': 'keep'}
        _, targets = repair_ai.source_context([s])
        schema = repair_ai.proposal_schema(targets)
        structure = schema['properties']['proposals']['items']['anyOf'][0]['properties']['proposal']['properties']['patch']['properties']['hooks']['anyOf'][0]
        self.assertEqual('object', structure['type'])
        self.assertFalse(structure['additionalProperties'])
        changed = copy.deepcopy(hooks)
        changed['Stop'][0]['enabled'] = True
        result = json.loads(repair_ai.apply_proposal(targets['settings'], {'patch': {'hooks': changed}}))
        self.assertTrue(result['hooks']['Stop'][0]['enabled'])
        self.assertEqual('keep', result['unrelated'])
        for mutate in [lambda v: v['Stop'][0].update(unknown='bad'), lambda v: v['Stop'][0].update(timeout='ten'),
                       lambda v: v.update(NewEvent=[]), lambda v: v['Stop'][0].update(optional='invented')]:
            bad = copy.deepcopy(changed)
            mutate(bad)
            with self.assertRaises(ValueError):
                repair_ai.apply_proposal(targets['settings'], {'patch': {'hooks': bad}})

    def test_json_provider_patch_runs_production_entrypoint_to_checked_proposal(self):
        s = source('settings', 'provider_api')
        s['target'].update(content_format='json', allowed_patch_paths=['enabled'])
        s['snapshot']['projection'] = {'enabled': False, 'preserve': True, 'token': '[REDACTED]'}
        original = copy.deepcopy(s)
        context, _ = repair_ai.source_context([s])
        lines = context['files'][0]['content'].splitlines()
        evidence = [{'file_id': 'settings', 'line': 2, 'quote': lines[1]}]
        proposal = {'proposals': [{'target_id': 'settings', 'proposal': {'patch': {'enabled': True}}, 'evidence': evidence}], 'limitations': []}
        cases = [{'id': purpose, 'scenario': 'Check ' + purpose, 'purpose': purpose,
                  'choices': {'A': 'Enable.', 'B': 'Keep disabled.', 'C': 'Remove.'},
                  'expected': 'A' if purpose == 'fix' else 'B', 'rationale': 'Cited field.',
                  'evidence': evidence} for purpose in ['fix', 'preserve']]
        calls = []
        def invoke(prompt, schema):
            calls.append(prompt)
            if len(calls) == 1:
                return proposal
            if len(calls) == 2:
                return {'cases': cases}
            payload = json.loads(prompt.split('EVIDENCE_JSON:\n')[1])
            content = json.loads(payload['instructions']['files'][0]['content'])
            self.assertEqual('[REDACTED]', content['token'])
            return {'choices': [{'id': 'fix', 'choice': 'A' if content['enabled'] else 'B'}, {'id': 'preserve', 'choice': 'B'}]}
        with patch.object(repair_ai, 'invoke', side_effect=invoke):
            result = repair_ai.propose_repair('Enable the registered field and preserve others.', [s])
        self.assertEqual([{'target_id': 'settings', 'proposal': {'patch': {'enabled': True}}}], result['proposals'])
        self.assertEqual('passed', result['checks'][0]['status'])
        self.assertEqual(original, s)

    def test_native_strict_patch_schema_requires_all_keys_with_null_no_change(self):
        s = source('settings', 'app_settings')
        s['target'].update(content_format='json', allowed_patch_paths=['enabled', 'preserve'])
        s['snapshot']['projection'] = {'enabled': False, 'preserve': True}
        context, targets = repair_ai.source_context([s])
        schema = repair_ai.proposal_schema(targets)
        patch_schema = schema['properties']['proposals']['items']['anyOf'][0]['properties']['proposal']['properties']['patch']
        self.assertEqual(set(patch_schema['properties']), set(patch_schema['required']))
        answer = {'proposals': [{'target_id': 'settings', 'proposal': {'patch': {'enabled': True, 'preserve': None}},
                                 'evidence': [{'file_id': 'settings', 'line': 2, 'quote': '  "enabled": false,'}]}], 'limitations': []}
        repair_ai.validate_proposals(answer, targets, context)
        self.assertEqual({'patch': {'enabled': True}}, answer['proposals'][0]['proposal'])

    def test_owner_hook_commands_are_data_and_numeric_registered_paths_work(self):
        s = source('settings', 'hook')
        s['target'].update(content_format='json', allowed_patch_paths=['hooks.Stop.0.hooks.0.timeout'])
        s['snapshot']['projection'] = {'hooks': {'Stop': [{'hooks': [{'command': 'python3 owned.py', 'timeout': 10, 'args': ['--verbose']}]}]}}
        context, targets = repair_ai.source_context([s])
        self.assertIn('command', context['files'][0]['content'])
        result = json.loads(repair_ai.apply_proposal(targets['settings'], {'patch': {'hooks.Stop.0.hooks.0.timeout': 20}}))
        self.assertEqual(20, result['hooks']['Stop'][0]['hooks'][0]['timeout'])
        self.assertEqual('python3 owned.py', result['hooks']['Stop'][0]['hooks'][0]['command'])
        s['snapshot']['projection']['hooks']['Stop'][0]['hooks'][0]['env'] = {'TOKEN': 'private-real'}
        with self.assertRaises(ValueError):
            repair_ai.source_context([s])

    def test_hook_source_inline_credentials_stay_excluded(self):
        for command in ['python3 owned.py --token private-real', 'API_KEY=private-real python3 owned.py',
                        'curl https://user:private-real@example.test']:
            s = source('settings', 'hook')
            s['target'].update(content_format='json', allowed_patch_paths=['hooks'])
            s['snapshot']['projection'] = {'hooks': {'Stop': [{'command': command}]}}
            with patch.object(repair_ai, 'invoke') as invoke:
                result = repair_ai.propose_repair('repair hook', [s])
            self.assertFalse(invoke.called)
            self.assertEqual([], result['proposals'])

    def test_exact_per_line_endings_are_preserved_in_prompt(self):
        s = source('one', content='Old behavior.\r\nKeep evidence.\nLast line')
        result, calls = self.fixture([s])
        self.assertEqual(1, len(result['proposals']))
        payload = json.loads(calls[0].split('EVIDENCE_JSON:\n')[1])
        self.assertEqual(['\r\n', '\n', ''], [line['ending'] for line in payload['context']['files'][0]['source_lines']])

    def test_text_redaction_placeholder_never_becomes_complete_file(self):
        result, _ = self.fixture([source('one', content='Old behavior.\nKeep evidence.\n[REDACTED]')])
        self.assertEqual([], result['proposals'])

    def test_provider_errors_are_static_and_do_not_expose_private_output(self):
        with patch.object(repair_ai, 'invoke', side_effect=RuntimeError('PRIVATE-PROVIDER-VALUE')):
            result = repair_ai.propose_repair('repair', [source('one')])
        self.assertEqual([], result['proposals'])
        self.assertNotIn('PRIVATE-PROVIDER-VALUE', json.dumps(result))


if __name__ == '__main__':
    unittest.main()

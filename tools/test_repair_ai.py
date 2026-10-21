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

    def test_registered_python_guard_variables_survive_full_four_stage_entry(self):
        guard = ('import os\n'
                 'token = os.getenv("SERVICE_TOKEN")\n'
                 'command = os.getenv("NEXT_ACTION")\n'
                 'def allowed(action):\n'
                 '    return action == "read"\n')
        candidate = guard.replace('action == "read"', 'action in ("read", "inspect")')
        s = source('guard', 'executable', guard)
        s['target'].update(source_language='py')
        evidence = [{'file_id': 'guard', 'line': 2, 'quote': 'token = os.getenv("SERVICE_TOKEN")'}]
        cases = [{'id': purpose, 'scenario': 'Inspect action' if purpose == 'fix' else 'Read action',
                  'purpose': purpose, 'choices': {'A': 'Allowed.', 'B': 'Denied.', 'C': 'Unknown.'},
                  'expected': 'A', 'rationale': 'Guard decision from source.', 'evidence': evidence}
                 for purpose in ['fix', 'preserve']]
        calls = []
        def invoke(prompt, schema):
            calls.append(prompt)
            if len(calls) == 1:
                return {'proposals': [{'target_id': 'guard', 'proposal': {'candidate': candidate}, 'evidence': evidence}], 'limitations': []}
            if len(calls) == 2:
                return {'cases': cases}
            payload = json.loads(prompt.split('EVIDENCE_JSON:\n')[1])
            self.assertNotIn('expected', payload['scenarios'][0])
            raw = payload['instructions']['files'][0]['content']
            self.assertIn('token = os.getenv', raw)
            self.assertIn('command = os.getenv', raw)
            return {'choices': [{'id': 'fix', 'choice': 'A' if '"inspect"' in raw else 'B'}, {'id': 'preserve', 'choice': 'A'}]}
        with patch.object(repair_ai, 'invoke', side_effect=invoke):
            result = repair_ai.propose_repair('Permit inspect actions and keep read actions.', [s])
        self.assertEqual(4, len(calls))
        self.assertEqual(candidate, result['proposals'][0]['proposal']['candidate'])
        self.assertEqual('passed', result['checks'][0]['status'])

    def test_registered_python_literal_credentials_never_reach_model_or_candidate(self):
        for body in ['token = "private-real"\n', 'config = {"token": "private-real"}\n']:
            s = source('guard', 'executable', body)
            s['target'].update(source_language='py')
            with patch.object(repair_ai, 'invoke') as invoke:
                result = repair_ai.propose_repair('repair guard', [s])
            self.assertFalse(invoke.called)
            self.assertEqual([], result['proposals'])
        s = source('guard', 'executable', 'enabled = False\n')
        s['target'].update(source_language='py')
        _, targets = repair_ai.source_context([s])
        with self.assertRaises(ValueError):
            repair_ai.apply_proposal(targets['guard'], {'candidate': 'token = "private-real"\n'})

    def test_large_text_exact_edits_assemble_public_candidate_and_preserve_other_bytes(self):
        raw = 'Old behavior.\r\nKeep evidence.\n# ' + 'x' * 118000 + '\r\n'
        s = source('large', content=raw)
        result, calls = self.fixture([s], mutate=lambda proposals: proposals[0].update(proposal={'edits': [{'old_text': 'Old behavior.', 'new_text': 'New behavior.'}]}))
        self.assertEqual(4, len(calls))
        self.assertEqual({'candidate': raw.replace('Old behavior.', 'New behavior.', 1)}, result['proposals'][0]['proposal'])
        self.assertEqual('passed', result['checks'][0]['status'])

    def test_exact_text_edits_reject_ambiguous_overlapping_noop_and_bad_shapes(self):
        s = source('one', content='old old\nKeep evidence.\n')
        _, targets = repair_ai.source_context([s])
        edits = [[], [{'old_text': 'old', 'new_text': 'new'}],
                 [{'old_text': 'old old', 'new_text': 'new'}, {'old_text': 'old old\n', 'new_text': 'new\n'}],
                 [{'old_text': 'Keep evidence.', 'new_text': 'Keep evidence.'}],
                 [{'old_text': '', 'new_text': 'new'}],
                 [{'old_text': 'missing', 'new_text': 'new'}],
                 [{'old_text': 'Keep evidence.', 'new_text': 'Keep proof.', 'command': 'no'}]]
        for value in edits:
            with self.assertRaises(ValueError):
                repair_ai.apply_proposal(targets['one'], {'edits': value})
        repeated = source('repeat', content='aaa\nKeep evidence.\n')
        _, repeat_targets = repair_ai.source_context([repeated])
        with self.assertRaises(ValueError):
            repair_ai.apply_proposal(repeat_targets['repeat'], {'edits': [{'old_text': 'aa', 'new_text': 'b'}]})

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


    def test_diagnostics_identify_each_provider_stage_without_private_exception(self):
        for failure_call, stage in enumerate(['proposal', 'scenario', 'before', 'candidate'], 1):
            calls = 0
            # Capture the deterministic fixture's injected invocations; no model runs.
            real_patch = patch.object
            def inject(target, name, **kwargs):
                nonlocal calls
                wrapped = kwargs['side_effect']
                def fail_at_stage(*args):
                    nonlocal calls
                    calls += 1
                    if calls == failure_call:
                        raise RuntimeError('PRIVATE-SOURCE-PROVIDER-SECRET')
                    return wrapped(*args)
                return real_patch(target, name, side_effect=fail_at_stage)
            with patch('test_repair_ai.patch.object', side_effect=inject):
                result, _ = self.fixture()
            self.assertEqual({'stage': stage, 'reason': 'provider_unavailable'}, result['diagnostics'])
            self.assertEqual([], result['proposals'])
            self.assertNotIn('PRIVATE-SOURCE-PROVIDER-SECRET', json.dumps(result))

    def test_diagnostics_classify_source_citation_coverage_schema_and_simulation(self):
        with patch.object(repair_ai, 'invoke') as model:
            result = repair_ai.propose_repair('repair', [source('one', content='api_key = "private-real"')])
        self.assertFalse(model.called)
        self.assertEqual({'stage': 'source', 'reason': 'source_boundary'}, result['diagnostics'])
        result, _ = self.fixture(mutate=lambda p: p[0]['evidence'][0].update(quote='wrong'))
        self.assertEqual({'stage': 'proposal', 'reason': 'citation'}, result['diagnostics'])
        result, _ = self.fixture(mutate_cases=lambda c: c[1].update(evidence=c[1]['evidence'][:1]))
        self.assertEqual({'stage': 'scenario', 'reason': 'coverage'}, result['diagnostics'])
        result, _ = self.fixture(mutate_cases=lambda c: c[0].update(unregistered='PRIVATE-SENTINEL'))
        self.assertEqual({'stage': 'scenario', 'reason': 'schema'}, result['diagnostics'])
        result, _ = self.fixture(after='B')
        self.assertEqual({'stage': 'validation', 'reason': 'simulation'}, result['diagnostics'])
        self.assertEqual('failed', result['checks'][0]['status'])
        self.assertNotIn('PRIVATE-SENTINEL', json.dumps(result))

    def test_malformed_decision_response_is_safe_schema_failure_at_exact_run(self):
        for failure_call, stage in [(3, 'before'), (4, 'candidate')]:
            calls = 0
            real_patch = patch.object
            def inject(target, name, **kwargs):
                wrapped = kwargs['side_effect']
                def malformed(*args):
                    nonlocal calls
                    calls += 1
                    return {'PRIVATE-PROVIDER-SENTINEL': 'PRIVATE-SOURCE'} if calls == failure_call else wrapped(*args)
                return real_patch(target, name, side_effect=malformed)
            with patch('test_repair_ai.patch.object', side_effect=inject):
                result, _ = self.fixture()
            self.assertEqual({'stage': stage, 'reason': 'schema'}, result['diagnostics'])
            self.assertEqual([], result['proposals'])
            self.assertNotIn('PRIVATE-', json.dumps(result))

    def test_unexpected_validation_exception_cannot_escape_safe_metadata(self):
        for validator, stage, reason in [('source_context', 'source', 'source_boundary'),
                                         ('validate_proposals', 'proposal', 'schema'),
                                         ('validate_cases', 'proposal', 'schema'),
                                         ('choices', 'before', 'schema')]:
            with self.subTest(validator=validator):
                with patch.object(repair_ai, validator, side_effect=ValueError('PRIVATE-EXCEPTION-SOURCE')):
                    result, _ = self.fixture()
                self.assertEqual({'stage': stage, 'reason': reason}, result['diagnostics'])
                self.assertEqual([], result['proposals'])
                self.assertNotIn('PRIVATE-EXCEPTION-SOURCE', json.dumps(result))

    def test_owned_receipt_guard_narrows_harmless_actions_and_preserves_real_gates(self):
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        blocked = ('spend', 'contact', 'production', 'unbacked_delete', 'security', 'fake_approval')
        harmless = ('repair', 'commit', 'handoff')
        old = repr(harmless + blocked)
        new = repr(blocked)
        rule = 'Require approval for action names in ' + old + '.\nKeep exact approval requirements for real gates.\n'
        guard = 'import sys\nBLOCKED = ' + old + '\nprint("approval" if sys.argv[1] in BLOCKED else "allowed")\n'
        sources = [source('rule', content=rule), source('guard', 'executable', guard)]
        sources[1]['target']['source_language'] = 'py'
        evidence = [{'file_id': 'rule', 'line': 1, 'quote': rule.splitlines()[0]},
                    {'file_id': 'guard', 'line': 2, 'quote': guard.splitlines()[1]}]
        cases = [{'id': purpose, 'purpose': purpose,
                  'scenario': 'Harmless owned repair, commit and handoff.' if purpose == 'fix' else 'Spending, contact, client production, unbacked deletion, security and fake approval.',
                  'choices': {'A': 'Allowed.', 'B': 'Approval required.', 'C': 'Unknown.'},
                  'expected': 'A' if purpose == 'fix' else 'B', 'rationale': 'Exact scoped rule and guard.', 'evidence': evidence}
                 for purpose in ['fix', 'preserve']]
        calls = []
        def model(prompt, schema):
            calls.append(prompt)
            if len(calls) == 1:
                return {'proposals': [{'target_id': item['target']['id'],
                         'proposal': {'edits': [{'old_text': old, 'new_text': new}]},
                         'evidence': [e for e in evidence if e['file_id'] == item['target']['id']]}
                         for item in sources], 'limitations': []}
            if len(calls) == 2:
                return {'cases': cases}
            payload = json.loads(prompt.split('EVIDENCE_JSON:\n')[1])
            texts = [item['content'] for item in payload['instructions']['files']]
            self.assertNotIn('expected', payload['scenarios'][0])
            return {'choices': [{'id': 'fix', 'choice': 'A' if all(new in text for text in texts) else 'B'},
                                {'id': 'preserve', 'choice': 'B'}]}
        with patch.object(repair_ai, 'invoke', side_effect=model):
            result = repair_ai.propose_repair('Narrow the owned receipt rule and guard for harmless repair, commit and handoff; preserve every actual approval gate.', sources)
        self.assertEqual(4, len(calls))
        self.assertEqual(2, len(result['proposals']))
        self.assertEqual('passed', result['checks'][0]['status'])
        self.assertNotIn('diagnostics', result)
        candidates = {item['target_id']: item['proposal']['candidate'] for item in result['proposals']}
        self.assertEqual(rule.replace(old, new), candidates['rule'])
        self.assertEqual(guard.replace(old, new), candidates['guard'])
        with tempfile.TemporaryDirectory(prefix='owned-receipt-fixture-') as temp:
            path = Path(temp) / 'guard.py'
            for body, changed in [(guard, False), (candidates['guard'], True)]:
                path.write_text(body)
                for action in harmless + blocked:
                    run = subprocess.run([sys.executable, '-B', str(path), action], capture_output=True, text=True, check=True)
                    self.assertEqual('allowed' if changed and action in harmless else 'approval', run.stdout.strip())


    def test_context_only_sources_are_citable_but_not_mutable_or_schema_targets(self):
        mutable = source('guard', content='Approval required for harmless repair.\nPreserve real gates.\n')
        policy = source('canonical-gates', content='Harmless owned repair is allowed.\nSpending and client production require approval.\n')
        policy['context_only'] = True
        original = copy.deepcopy([mutable, policy])
        context, targets = repair_ai.source_context([mutable, policy])
        self.assertEqual(original, [mutable, policy])
        self.assertFalse(context['files'][0]['context_only'])
        self.assertTrue(context['files'][1]['context_only'])
        self.assertTrue(targets['canonical-gates']['context_only'])
        schema = repair_ai.proposal_schema(targets)
        variants = schema['properties']['proposals']['items']['anyOf']
        self.assertEqual([['guard']], [variant['properties']['target_id']['enum'] for variant in variants])
        answer = {'proposals': [{'target_id': 'canonical-gates', 'proposal': {'candidate': 'Never ask.'},
                  'evidence': [{'file_id': 'canonical-gates', 'line': 1, 'quote': 'Harmless owned repair is allowed.'}]}], 'limitations': []}
        with self.assertRaises(ValueError):
            repair_ai.validate_proposals(answer, targets, context)
        with self.assertRaises(ValueError):
            repair_ai.apply_proposal(targets['canonical-gates'], {'candidate': 'Never ask.'})

    def test_context_only_gates_survive_four_stages_and_only_baseline_quotes_validate(self):
        guard = source('guard', content='Approval required for harmless repair.\nPreserve real gates.\n')
        gates = source('canonical-gates', content='Harmless owned repair is allowed.\nSpending and client production require approval.\n')
        gates['context_only'] = True
        old = 'Approval required for harmless repair.'
        new = 'Harmless owned repair is allowed.'
        baseline = [{'file_id': 'guard', 'line': 1, 'quote': old},
                    {'file_id': 'canonical-gates', 'line': 1, 'quote': new}]
        for bad_quote in [False, True]:
            calls = []
            def model(prompt, schema):
                calls.append(prompt)
                data = json.loads(prompt.split('EVIDENCE_JSON:\n')[1])
                if len(calls) == 1:
                    self.assertEqual(2, len(data['context']['files']))
                    return {'proposals': [{'target_id': 'guard', 'proposal': {'edits': [{'old_text': old, 'new_text': new}]},
                                          'evidence': baseline}], 'limitations': []}
                if len(calls) == 2:
                    self.assertIn('baseline', prompt)
                    self.assertIn('never cite candidate', prompt)
                    evidence = copy.deepcopy(baseline)
                    if bad_quote:
                        evidence[0]['quote'] = new
                    return {'cases': [{'id': purpose, 'purpose': purpose, 'scenario': 'Owned repair' if purpose == 'fix' else 'Real gates',
                             'choices': {'A': 'Allowed.', 'B': 'Approval required.', 'C': 'Unknown.'},
                             'expected': 'A' if purpose == 'fix' else 'B', 'rationale': 'Registered policy context.',
                             'evidence': evidence} for purpose in ['fix', 'preserve']]}
                files = {item['file_id']: item for item in data['instructions']['files']}
                self.assertTrue(files['canonical-gates']['context_only'])
                self.assertEqual(gates['snapshot']['projection']['content'], files['canonical-gates']['content'])
                return {'choices': [{'id': 'fix', 'choice': 'A' if files['guard']['content'].startswith(new) else 'B'},
                                    {'id': 'preserve', 'choice': 'B'}]}
            with patch.object(repair_ai, 'invoke', side_effect=model):
                result = repair_ai.propose_repair('Allow harmless owned repair; preserve real gates.', [guard, gates])
            if bad_quote:
                self.assertEqual(2, len(calls))
                self.assertEqual([], result['proposals'])
                self.assertEqual({'stage': 'scenario', 'reason': 'citation'}, result['diagnostics'])
            else:
                self.assertEqual(4, len(calls))
                self.assertEqual(['guard'], [item['target_id'] for item in result['proposals']])
                self.assertEqual('passed', result['checks'][0]['status'])

    def test_mutable_and_readonly_source_counts_have_separate_explicit_bounds(self):
        mutable = [source('mutable-' + str(i)) for i in range(16)]
        readonly = [dict(source('context-' + str(i)), context_only=True) for i in range(4)]
        context, _ = repair_ai.source_context(mutable + readonly)
        self.assertEqual(20, len(context['files']))
        for invalid in [mutable + [source('extra-mutable')], mutable + readonly + [dict(source('extra-context'), context_only=True)], readonly,
                        [dict(source('invalid-flag'), context_only='true')]]:
            with self.assertRaises(ValueError):
                repair_ai.source_context(invalid)

    def test_bounded_context_accepts_large_guard_plus_policy_without_truncation(self):
        guard = source('guard', content='Old behavior.\n# ' + 'x' * 118000 + '\n')
        policy = dict(source('policy', content='Real gates.\n' + 'y' * 45000 + '\n'), context_only=True)
        context, _ = repair_ai.source_context([guard, policy])
        self.assertEqual(guard['snapshot']['projection']['content'], context['files'][0]['content'])
        self.assertEqual(policy['snapshot']['projection']['content'], context['files'][1]['content'])
        self.assertGreater(len(json.dumps(context)), 128 * 1024)
        self.assertEqual(256 * 1024, repair_ai.MAX_CONTEXT)
        with self.assertRaises(ValueError):
            repair_ai.source_context([source('too-large', content='x' * (256 * 1024))])


    def test_explicit_clarify_resolves_cited_contradiction_without_changing_legacy_schema(self):
        import local_file_checks
        self.assertEqual(['fix', 'preserve'], local_file_checks.CASE['properties']['purpose']['enum'])
        self.assertIn('clarify', repair_ai.PLAN['properties']['cases']['items']['properties']['purpose']['enum'])
        sources = [source('one', content='Never change tools to bypass the owned receipt rule.\nChange the tool when the receipt rule blocks harmless work.\nKeep real gates.\n')]
        evidence = [{'file_id': 'one', 'line': 1, 'quote': 'Never change tools to bypass the owned receipt rule.'},
                    {'file_id': 'one', 'line': 2, 'quote': 'Change the tool when the receipt rule blocks harmless work.'}]
        def clarify(cases):
            cases[0].update(purpose='clarify', scenario='The owned receipt rule blocks harmless work. What action is directed?',
                            rationale='Opposing directives require never changing tools versus changing tools for the same block.', evidence=evidence)
            cases[1].update(evidence=[{'file_id': 'one', 'line': 3, 'quote': 'Keep real gates.'}])
        # The existing fixture supplies a deterministic candidate and unknown
        # baseline; explicit clarify alone accepts this ambiguity resolution.
        result, calls = self.fixture(sources, mutate=lambda p: p[0].update(evidence=[evidence[0]], proposal={'candidate': 'New behavior.\nRepair the owned receipt rule at its cause; never change tools to bypass it.\nKeep real gates.\n'}), mutate_cases=clarify, before='unknown')
        self.assertEqual(4, len(calls))
        self.assertEqual('passed', result['checks'][0]['status'])
        outcomes = [json.loads(item) for item in result['checks'][0]['evidence'] if '"purpose"' in item]
        clarification = next(item for item in outcomes if item['purpose'] == 'clarify')
        self.assertTrue(clarification['baseline_ambiguous'])
        self.assertEqual('unknown', clarification['before'])
        self.assertEqual('A', clarification['after'])
        self.assertIn('opposing directives', calls[1])

    def test_clarify_requires_distinct_baseline_citations_and_unknown_before(self):
        def clarify(cases):
            cases[0]['purpose'] = 'clarify'
        for duplicate in [False, True]:
            def insufficient(cases):
                clarify(cases)
                cases[0]['evidence'] = cases[0]['evidence'][:1] * (2 if duplicate else 1)
            result, calls = self.fixture(mutate_cases=insufficient, before='unknown')
            self.assertEqual([], result['proposals'])
            self.assertEqual('unavailable', result['checks'][0]['status'])
            self.assertEqual(2, len(calls))
        for before, after in [('B', 'A'), ('unknown', 'unknown'), ('unknown', 'B')]:
            result, _ = self.fixture(mutate_cases=clarify, before=before, after=after)
            self.assertEqual([], result['proposals'])
            self.assertEqual('failed', result['checks'][0]['status'])

    def test_ordinary_fix_still_rejects_unknown_and_clarify_needs_preservation(self):
        result, _ = self.fixture(before='unknown')
        self.assertEqual([], result['proposals'])
        self.assertEqual('failed', result['checks'][0]['status'])
        result, _ = self.fixture(mutate_cases=lambda cases: cases[1].update(purpose='clarify'), before='unknown')
        self.assertEqual([], result['proposals'])
        self.assertEqual('unavailable', result['checks'][0]['status'])


    def test_clarify_does_not_accept_unknown_preservation_or_provider_failure(self):
        def clarify(cases):
            cases[0]['purpose'] = 'clarify'
        parse = repair_ai.choices
        def unknown_preserve(answer, cases):
            parsed = parse(answer, cases)
            parsed['preserve'] = 'unknown'
            return parsed
        with patch.object(repair_ai, 'choices', side_effect=unknown_preserve):
            result, _ = self.fixture(mutate_cases=clarify, before='unknown')
        self.assertEqual([], result['proposals'])
        self.assertEqual('failed', result['checks'][0]['status'])
        calls = 0
        def fail_before(answer, cases):
            nonlocal calls
            calls += 1
            raise RuntimeError('PRIVATE-PROVIDER-FAILURE')
        with patch.object(repair_ai, 'choices', side_effect=fail_before):
            result, _ = self.fixture(mutate_cases=clarify, before='unknown')
        self.assertEqual(1, calls)
        self.assertEqual([], result['proposals'])
        self.assertEqual('unavailable', result['checks'][0]['status'])
        self.assertNotIn('PRIVATE-PROVIDER-FAILURE', json.dumps(result))


    def test_ai_schema_matches_case_and_citation_bounds_without_legacy_mutation(self):
        import local_file_checks
        evidence = repair_ai.CASE['properties']['evidence']
        self.assertEqual((1, 12), (evidence['minItems'], evidence['maxItems']))
        cases = repair_ai.PLAN['properties']['cases']
        self.assertEqual((2, 4), (cases['minItems'], cases['maxItems']))
        self.assertEqual(evidence, cases['items']['properties']['evidence'])
        self.assertNotIn('minItems', local_file_checks.CASE['properties']['evidence'])
        self.assertNotIn('maxItems', local_file_checks.CASE['properties']['evidence'])
        result, calls = self.fixture()
        self.assertEqual(2, len(result['proposals']))
        self.assertIn('1-12 exact baseline citations per case', calls[1])
        self.assertIn('1-12 exact baseline citations per proposal', calls[0])
        _, targets = repair_ai.source_context([source('one')])
        variants = repair_ai.proposal_schema(targets)['properties']['proposals']['items']['anyOf']
        for variant in variants:
            evidence = variant['properties']['evidence']
            self.assertEqual((1, 12), (evidence['minItems'], evidence['maxItems']))

    def test_fourteen_exact_citations_remain_rejected_without_truncation(self):
        lines = ['Directive ' + str(i) for i in range(1, 15)]
        context = {'files': [{'file_id': 'one', 'content': '\n'.join(lines)}]}
        citations = [{'file_id': 'one', 'line': i, 'quote': text} for i, text in enumerate(lines, 1)]
        def case(purpose, evidence):
            return {'id': purpose, 'purpose': purpose, 'scenario': 'Behavior of cited directives.',
                    'choices': {'A': 'Allow.', 'B': 'Require approval.', 'C': 'Unknown.'},
                    'expected': 'A', 'rationale': 'Exact baseline evidence.', 'evidence': evidence}
        plan = {'cases': [case('fix', citations[:2]), case('preserve', citations)]}
        with self.assertRaisesRegex(ValueError, '^case evidence$'):
            repair_ai.validate_cases(plan, context)
        self.assertEqual(14, len(plan['cases'][1]['evidence']))
        valid = copy.deepcopy(plan)
        valid['cases'][1]['evidence'] = valid['cases'][1]['evidence'][:12]
        self.assertEqual(2, len(repair_ai.validate_cases(valid, context)))


if __name__ == '__main__':
    unittest.main()

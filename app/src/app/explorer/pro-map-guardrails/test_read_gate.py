"""Real subprocess hook tests. Every temporary write stays in read-fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / 'read_gate.py'
FIXTURES = HERE / 'read-fixtures'


class ReadGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=FIXTURES)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        self.state = self.root / 'runtime-state'
        self.state.mkdir(mode=0o700)
        self.a = self.root / 'alpha.md'
        self.b = self.root / 'beta.md'
        self.a.write_text('Alpha card\nRead before use.\n')
        self.b.write_text('Beta card\nDifferent service.\n')
        self.policy = self.root / 'policy.json'
        self.config = {'version': 1, 'project_root': str(self.project),
                       'servers': {'alpha': [str(self.a)], 'beta': [str(self.b)],
                                   'composio': [str(self.a)]},
                       'direct_tools': ['mcp__alpha__get', 'mcp__beta__get'],
                       'batches': {'mcp__composio__COMPOSIO_MULTI_EXECUTE_TOOL': {
                           'actions_key': 'tools', 'action_name_key': 'tool_slug',
                           'arguments_key': 'arguments',
                           'optional_fields': {'session_id': 'string'},
                           'actions': {'ALPHA_GET': [str(self.a)],
                                       'BETA_GET': [str(self.b)]}}}}
        self.save_policy()
        self.command = [sys.executable, '-B', str(SCRIPT), '--policy', str(self.policy),
                        '--state-dir', str(self.state), '--project', str(self.project)]

    def save_policy(self):
        self.policy.write_text(json.dumps(self.config))

    def event(self, name='PreToolUse', tool='mcp__alpha__get', inp=None, uid='call-1', **extra):
        result = {'hook_event_name': name, 'session_id': 'session-a',
                  'cwd': str(self.project), 'tool_use_id': uid, 'tool_name': tool,
                  'tool_input': {} if inp is None else inp}
        result.update(extra)
        return result

    def invoke(self, event, command=None):
        result = subprocess.run(command or self.command, input=json.dumps(event),
                                capture_output=True, text=True, cwd=HERE, timeout=10)
        self.assertIn(result.returncode, (0, 2), result.stderr)
        return result

    def deny(self, event, command=None):
        result = self.invoke(event, command)
        if result.returncode == 2:
            self.assertTrue(result.stderr.strip())
        else:
            out = json.loads(result.stdout)
            self.assertEqual(out['hookSpecificOutput']['hookEventName'], 'PreToolUse')
            self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')
        return result

    def allow(self, event, command=None):
        result = self.invoke(event, command)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '{}', result.stdout)

    def response(self, card=None):
        card = card or self.a
        content = card.read_text()
        return {'type': 'text', 'file': {'filePath': str(card), 'content': content,
                'numLines': len(content.split('\n')), 'startLine': 1,
                'totalLines': len(content.split('\n'))}}

    def read_events(self, card=None, uid='read-1', **extra):
        card = card or self.a
        pre = self.event(tool='Read', inp={'file_path': str(card)}, uid=uid, **extra)
        post = dict(pre, hook_event_name='PostToolUse', tool_response=self.response(card))
        return pre, post

    def mark(self, card=None, uid='read-1', **extra):
        pre, post = self.read_events(card, uid, **extra)
        self.allow(pre)
        self.allow(post)

    def state_data(self):
        path = self.state / 'state.json'
        return json.loads(path.read_text()) if path.exists() else {'markers': {}, 'reads': {}}

    def test_success_requires_actual_pre_and_successful_post(self):
        self.deny(self.event())
        pre, post = self.read_events()
        self.allow(pre)
        self.assertFalse(self.state_data()['markers'])
        self.deny(self.event())
        self.allow(post)
        self.allow(self.event())
        self.assertTrue(self.state_data()['markers'])

    def test_repeated_denials_never_mark_or_mutate_existing_state(self):
        self.allow(self.read_events()[0])
        before = (self.state / 'state.json').read_bytes()
        for _ in range(4):
            self.deny(self.event())
        self.assertEqual(before, (self.state / 'state.json').read_bytes())
        self.assertFalse(self.state_data()['markers'])

    def test_missing_and_empty_cards_block(self):
        self.mark()
        self.a.unlink()
        self.deny(self.event())
        self.a.write_text('  \n')
        self.deny(self.event())
        self.allow(self.read_events()[0])
        self.assertFalse(any(r['status'] == 'pending' for r in self.state_data()['reads'].values()))

    def test_different_session_and_project_and_agent(self):
        self.mark()
        self.deny(self.event(session_id='session-b'))
        self.deny(self.event(agent_id='child'))
        other = self.root / 'other-project'
        other.mkdir()
        self.deny(self.event(cwd=str(other)))
        child = self.project / 'nested'
        child.mkdir()
        self.allow(self.event(cwd=str(child)))
        command = self.command[:-1] + [str(other)]
        self.deny(self.event(cwd=str(other)), command)

    def test_edited_card_invalidates_marker(self):
        self.mark()
        self.a.write_text('New policy\n')
        self.deny(self.event())
        self.mark(uid='read-2')
        self.allow(self.event())

    def test_changed_policy_invalidates_marker(self):
        self.mark()
        self.config['servers']['gamma'] = [str(self.a)]
        self.save_policy()
        self.deny(self.event())

    def test_race_changed_between_pre_and_post(self):
        pre, post = self.read_events()
        self.allow(pre)
        self.a.write_text('Changed while reading\n')
        post['tool_response'] = self.response()
        self.allow(post)
        self.deny(self.event())
        self.assertFalse(self.state_data()['markers'])

    def test_aba_edit_restore_during_read_does_not_mark(self):
        pre, post = self.read_events()
        self.allow(pre)
        original = self.a.read_bytes()
        self.a.write_text('Intermediate edit\n')
        self.a.write_bytes(original)
        self.allow(post)
        self.deny(self.event())

    def test_post_without_pending_or_wrong_id_does_not_mark(self):
        pre, post = self.read_events()
        self.allow(post)
        self.deny(self.event())
        self.allow(pre)
        self.allow(dict(post, tool_use_id='different-id'))
        self.deny(self.event())

    def test_duplicate_pre_retry_and_replayed_post_do_not_mark(self):
        pre, post = self.read_events()
        self.allow(pre)
        self.allow(pre)
        self.allow(post)
        self.deny(self.event())
        self.mark(uid='fresh-id')
        self.a.write_text('Changed\n')
        self.allow(post)
        self.deny(self.event())

    def test_failed_or_denied_read_consumes_pending(self):
        for event_name in ['PostToolUseFailure', 'PermissionDenied']:
            with self.subTest(event_name=event_name):
                pre, post = self.read_events(uid=event_name)
                self.allow(pre)
                self.allow(dict(post, hook_event_name=event_name, error='denied'))
                self.allow(post)
                self.deny(self.event())
                self.assertFalse(self.state_data()['markers'])

    def test_partial_truncated_errors_wrong_path_and_content_rejected(self):
        variants = [
            {'type': 'file_unchanged', 'file': {'filePath': str(self.a)}},
            {'type': 'text', 'file': {}}, 'plain text is not evidence',
            dict(self.response(), is_error=True), dict(self.response(), error='failure'),
        ]
        for field, value in [('startLine', 2), ('numLines', 1), ('totalLines', 99),
                             ('truncatedByTokenCap', True), ('content', 'Alpha card'),
                             ('filePath', str(self.b)), ('numLines', True)]:
            response = self.response()
            response['file'][field] = value
            variants.append(response)
        for index, response in enumerate(variants):
            with self.subTest(index=index):
                pre, post = self.read_events(uid=f'invalid-{index}')
                self.allow(pre)
                self.allow(dict(post, tool_response=response))
                self.deny(self.event())
                # A later correct response on the same ID cannot rescue a failed Read.
                self.allow(post)
                self.deny(self.event())

    def test_partial_input_and_modified_post_input(self):
        for index, patch in enumerate([{'offset': 2}, {'limit': 1}, {'pages': '1'},
                                       {'offset': True}, {'limit': -1}]):
            pre, post = self.read_events(uid=f'partial-{index}')
            pre['tool_input'].update(patch)
            post['tool_input'] = dict(pre['tool_input'])
            self.allow(pre)
            self.allow(post)
            self.deny(self.event())
        pre, post = self.read_events(uid='input-change')
        self.allow(pre)
        post['tool_input']['offset'] = 1
        self.allow(post)
        self.deny(self.event())

    def test_full_explicit_limit_is_accepted(self):
        pre, post = self.read_events()
        pre['tool_input'].update(offset=1, limit=100)
        post['tool_input'] = dict(pre['tool_input'])
        self.allow(pre)
        self.allow(post)
        self.allow(self.event())

    def batch(self, tools):
        return self.event(tool='mcp__composio__COMPOSIO_MULTI_EXECUTE_TOOL', inp={'tools': tools})

    def test_batch_checks_every_action_second_unread_then_success(self):
        self.mark()
        batch = self.batch([{'tool_slug': 'ALPHA_GET', 'arguments': {}},
                            {'tool_slug': 'BETA_GET', 'arguments': {}}])
        self.deny(batch)
        self.mark(self.b, uid='read-beta')
        self.allow(batch)

    def test_unknown_and_malformed_batches_fail_closed(self):
        self.mark()
        self.mark(self.b, uid='read-beta')
        for tools in [[], None, {}, 'ALPHA_GET', [None],
                      [{'tool_slug': 'UNKNOWN', 'arguments': {}}],
                      [{'tool_slug': 'ALPHA_GET'}],
                      [{'tool_slug': 'ALPHA_GET', 'arguments': []}],
                      [{'tool_slug': 'ALPHA_GET', 'arguments': {}, 'extra': True}],
                      [{'tool_slug': 'ALPHA_GET', 'arguments': {}}, {'tool_slug': 'UNKNOWN', 'arguments': {}}]]:
            with self.subTest(tools=tools):
                self.deny(self.batch(tools))
        self.deny(self.event(tool='mcp__composio__COMPOSIO_MULTI_EXECUTE_TOOL', inp={'actions': []}))
        good = self.batch([{'tool_slug': 'ALPHA_GET', 'arguments': {}}])
        good['tool_input']['session_id'] = False
        self.deny(good)
        good['tool_input']['session_id'] = 'external-session'
        self.allow(good)
        good['tool_input']['unknown'] = True
        self.deny(good)

    def test_known_server_unregistered_direct_tool_blocks(self):
        self.mark()
        self.deny(self.event(tool='mcp__alpha__unknown'))
        self.deny(self.event(tool='mcp__composio__DIRECT_UNKNOWN'))
        self.allow(self.event(tool='mcp__alpha__get'))

    def test_known_server_unregistered_batch_and_remoteexec_block(self):
        self.mark()
        self.mark(self.b, uid='read-beta')
        for name in ['mcp__composio__ALTERNATE_BATCH',
                     'mcp__composio__COMPOSIO_REMOTE_EXECUTE_TOOL',
                     'mcp__composio__COMPOSIO_REMOTE_WORKBENCH']:
            self.deny(self.event(tool=name, inp={'tools': [
                {'tool_slug': 'ALPHA_GET', 'arguments': {}}]}))
        self.allow(self.batch([{'tool_slug': 'ALPHA_GET', 'arguments': {}}]))

    def test_unknown_mcp_server_and_malformed_names_block(self):
        self.mark()
        for tool in ['mcp__unknown__get', 'mcp__alpha', 'mcp__alpha__', 'mcp__alpha__get__extra']:
            self.deny(self.event(tool=tool))

    def test_exact_server_mapping_not_prefix_guess(self):
        self.mark()
        self.deny(self.event(tool='mcp__alphabet__get'))
        self.deny(self.event(tool='mcp__beta__get'))

    def test_damaged_state_blocks_without_reset(self):
        self.mark()
        path = self.state / 'state.json'
        for value in ['{', 'null', '{}', '{"version":1,"markers":[],"reads":{}}',
                      '{"version":1,"markers":{"fake":true},"reads":{}}']:
            path.write_text(value)
            self.deny(self.event())
            self.assertEqual(path.read_text(), value)

    def test_insecure_state_directory_and_symlink_block(self):
        self.state.chmod(0o777)
        self.deny(self.event())
        self.state.chmod(0o700)
        link = self.root / 'state-link'
        link.symlink_to(self.state, target_is_directory=True)
        command = self.command.copy()
        command[command.index('--state-dir') + 1] = str(link)
        self.deny(self.event(), command)
        project_state = self.project / 'state'
        project_state.mkdir(mode=0o700)
        command[command.index('--state-dir') + 1] = str(project_state)
        self.deny(self.event(), command)

    def test_state_file_symlink_and_hardlink_block(self):
        target = self.root / 'target'
        target.write_text('{}')
        target.chmod(0o600)
        state_file = self.state / 'state.json'
        state_file.symlink_to(target)
        self.deny(self.event())
        state_file.unlink()
        os.link(target, state_file)
        self.deny(self.event())
        self.assertEqual(target.read_text(), '{}')

    def test_missing_config_and_invalid_input_exit_two(self):
        self.policy.unlink()
        self.deny(self.event())
        result = subprocess.run(self.command, input='not json', text=True,
                                capture_output=True, cwd=HERE, timeout=10)
        self.assertEqual(result.returncode, 2)

    def test_deeply_nested_or_duplicate_json_is_blocking(self):
        for raw in ['[' * 1500 + ']' * 1500,
                    '{"hook_event_name":"PreToolUse","hook_event_name":"PostToolUse"}']:
            result = subprocess.run(self.command, input=raw, capture_output=True,
                                    text=True, cwd=HERE, timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn('Traceback', result.stderr)
        self.mark()
        path = self.state / 'state.json'
        path.write_text('[' * 1500 + ']' * 1500)
        self.deny(self.event())
        self.assertEqual(path.read_text(), '[' * 1500 + ']' * 1500)

    def test_policy_relative_paths_and_invalid_adapter_block(self):
        for patch in [{'project_root': 'project'}, {'servers': {'alpha': ['alpha.md']}},
                      {'direct_tools': ['mcp__alpha__get', 'mcp__beta__get'],
                       'batches': {'mcp__composio__COMPOSIO_MULTI_EXECUTE_TOOL': {}}}]:
            original = dict(self.config)
            self.config.update(patch)
            self.save_policy()
            self.deny(self.event())
            self.config = original

    def test_trusted_environment_contract(self):
        env = dict(os.environ, READ_GATE_POLICY=str(self.policy),
                   READ_GATE_STATE_DIR=str(self.state), READ_GATE_PROJECT=str(self.project))
        result = subprocess.run([sys.executable, '-B', str(SCRIPT)],
                                input=json.dumps(self.event()), text=True,
                                capture_output=True, cwd=HERE, env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_permission_denial_without_id_invalidates_pending(self):
        pre, post = self.read_events()
        self.allow(pre)
        denied = self.event(name='PermissionDenied', tool='Read', inp=pre['tool_input'])
        denied.pop('tool_use_id')
        self.allow(denied)
        self.allow(post)
        self.deny(self.event())

    def test_claude_project_dir_policy_token_and_environment(self):
        self.config['project_root'] = '${CLAUDE_PROJECT_DIR}'
        self.save_policy()
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.project))
        env.pop('READ_GATE_PROJECT', None)
        command = self.command[:-2]
        for event in self.read_events():
            result = subprocess.run(command, input=json.dumps(event), text=True,
                                    capture_output=True, cwd=HERE, env=env, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), '{}')
        result = subprocess.run(command, input=json.dumps(self.event()), text=True,
                                capture_output=True, cwd=HERE, env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '{}')
        env['CLAUDE_PROJECT_DIR'] = str(self.root)
        result = subprocess.run(self.command, input=json.dumps(self.event()), text=True,
                                capture_output=True, cwd=HERE, env=env, timeout=10)
        self.assertEqual(result.returncode, 2)

    def test_non_mcp_bash_is_not_covered_or_marked(self):
        self.allow(self.event(tool='Bash', inp={'command': 'connector-wrapper'}))
        self.assertFalse(self.state_data()['markers'])

    def test_concurrent_reads_preserve_both_markers(self):
        pairs = [self.read_events(self.a, 'parallel-alpha'), self.read_events(self.b, 'parallel-beta')]
        for phase in [0, 1]:
            workers = [subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, cwd=HERE) for _ in pairs]
            for worker, pair in zip(workers, pairs):
                out, err = worker.communicate(json.dumps(pair[phase]), timeout=10)
                self.assertEqual(worker.returncode, 0, err)
                self.assertEqual(out.strip(), '{}')
        self.allow(self.event())
        self.allow(self.event(tool='mcp__beta__get'))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReadGateTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    receipt = {'tests_run': result.testsRun, 'failures': len(result.failures),
               'errors': len(result.errors), 'successful': result.wasSuccessful(),
               'test_command': 'python3 -B test_read_gate.py',
               'scope': str(HERE), 'subprocess_contract': True}
    (FIXTURES / 'test-results.json').write_text(json.dumps(receipt, indent=2) + '\n')
    sys.exit(0 if result.wasSuccessful() else 1)

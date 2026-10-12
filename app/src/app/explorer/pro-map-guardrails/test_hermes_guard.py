"""Real subprocess tests using Hermes shell-hook stdin, not Claude envelopes.
Run: python3 -B test_hermes_guard.py -v
All scratch data stays under hermes-fixtures; no runtime installation.
"""
import ast
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parent
SCRIPT = BASE / 'hermes_guard.py'
FIXTURES = BASE / 'hermes-fixtures'


def skill(name='demo'):
    return '---\n' + json.dumps({'name': name, 'description': 'Use when testing a bounded fixture skill.'}) + '\n---\n# Steps\nRead the source.\n'


def numbered(text):
    return '\n'.join(f'{n}|{line}' for n, line in enumerate(text.removesuffix('\n').split('\n'), 1))


class HermesGuardTests(unittest.TestCase):
    def setUp(self):
        FIXTURES.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=FIXTURES)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'profile'
        self.cards = self.root / 'cards'
        self.state = self.root / 'state'
        self.home.mkdir(); self.cards.mkdir()
        self.card = self.cards / 'github.md'
        self.card.write_text('# GitHub card\nRead only, fixture account.\n')
        self.config = self.home / 'config.yaml'
        self.cfg = {'mcp_servers': {'github': {'url': 'https://example.invalid/mcp'}}, 'skills': {'write_approval': True}}
        self.config.write_text(json.dumps(self.cfg))
        self.skill = self.home / 'skills' / 'demo' / 'SKILL.md'
        self.skill.parent.mkdir(parents=True); self.skill.write_text(skill())
        self.policy = self.root / 'policy.json'
        self.policy.write_text(json.dumps({'home': str(self.home), 'profile': 'fixture', 'cards_dir': str(self.cards), 'state_dir': str(self.state), 'routes': {'mcp__github__get_issue': {'server': 'github', 'card': 'github.md'}}}))

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self, event='pre_tool_call', tool='mcp__github__get_issue', args=None, session='s1', call_id='call1', **extra):
        # Exact agent/shell_hooks.py::_serialize_payload shape at pinned commit.
        if call_id is not None: extra['tool_call_id'] = call_id
        return {'hook_event_name': event, 'tool_name': tool, 'tool_input': args if args is not None else {}, 'session_id': session, 'cwd': str(self.home), 'profile': 'fixture', 'extra': extra}

    def run_hook(self, payload, expected=0):
        proc = subprocess.run([sys.executable, '-B', str(SCRIPT), '--policy', str(self.policy)], input=json.dumps(payload), text=True, capture_output=True, env={**os.environ, 'HERMES_HOME': str(self.home), 'PYTHONDONTWRITEBYTECODE': '1'}, timeout=10)
        self.assertEqual(proc.returncode, expected, proc.stderr + proc.stdout)
        self.assertEqual(proc.stderr, '')
        return json.loads(proc.stdout)

    def blocked(self, payload, reason=None):
        result = self.run_hook(payload, 2)
        self.assertEqual(result['action'], 'block')
        if reason: self.assertIn(reason, result['message'])
        return result

    def read(self, session='s1', call_id='read1', result=None, **args):
        arguments = {'path': str(self.card), **args}
        self.run_hook(self.payload(tool='read_file', args=arguments, session=session, call_id=call_id))
        if result is None:
            text = self.card.read_text()
            result = {'content': numbered(text), 'total_lines': len(text.splitlines()), 'file_size': len(text.encode()), 'truncated': False}
        return self.run_hook(self.payload(event='post_tool_call', tool='read_file', args=arguments, session=session, call_id=call_id, result=json.dumps(result), status='success'))

    def test_script_exists(self):
        self.assertTrue(SCRIPT.is_file(), 'Hermes adapter is missing')

    def test_missing_card_blocks(self):
        self.card.unlink(); self.blocked(self.payload(), 'missing card')

    def test_unread_card_blocks(self):
        self.blocked(self.payload(), 'successful full read_file')

    def test_pre_read_alone_never_marks(self):
        self.run_hook(self.payload(tool='read_file', args={'path': str(self.card)}))
        self.blocked(self.payload())

    def test_full_read_allows_exact_route(self):
        self.read(); self.assertEqual(self.run_hook(self.payload()), {})

    def test_read_without_ids_uses_pending_session_file(self):
        self.read(call_id=None); self.assertEqual(self.run_hook(self.payload(call_id=None)), {})

    def test_post_without_pre_never_marks(self):
        text = self.card.read_text()
        self.run_hook(self.payload(event='post_tool_call', tool='read_file', args={'path': str(self.card)}, result=json.dumps({'content': numbered(text), 'total_lines': 2, 'truncated': False}), status='success'))
        self.blocked(self.payload())

    def test_failed_read_never_marks(self):
        self.read(result={'error': 'permission denied'}); self.blocked(self.payload())

    def test_status_error_never_marks(self):
        args = {'path': str(self.card)}
        self.run_hook(self.payload(tool='read_file', args=args))
        self.run_hook(self.payload(event='post_tool_call', tool='read_file', args=args, result=json.dumps({'content': numbered(self.card.read_text()), 'total_lines': 2, 'truncated': False}), status='error'))
        self.blocked(self.payload())

    def test_truncated_read_never_marks(self):
        self.read(result={'content': numbered(self.card.read_text()), 'total_lines': 2, 'truncated': True}); self.blocked(self.payload())

    def test_partial_offset_never_marks(self):
        self.read(offset=2); self.blocked(self.payload())

    def test_false_full_content_never_marks(self):
        self.read(result={'content': '1|Wrong text', 'total_lines': 2, 'truncated': False}); self.blocked(self.payload())

    def test_redacted_result_never_marks(self):
        self.read(result={'content': '1|<redacted>\n2|Read only, fixture account.', 'total_lines': 2, 'truncated': False}); self.blocked(self.payload())

    def test_changed_card_invalidates_read(self):
        self.read(); self.card.write_text('Changed card\n'); self.blocked(self.payload())

    def test_change_between_pre_and_post_invalidates_read(self):
        args = {'path': str(self.card)}; old = self.card.read_text()
        self.run_hook(self.payload(tool='read_file', args=args))
        self.card.write_text('Changed card\n')
        self.run_hook(self.payload(event='post_tool_call', tool='read_file', args=args, result=json.dumps({'content': numbered(old), 'total_lines': 2, 'truncated': False}), status='success'))
        self.blocked(self.payload())

    def test_other_session_cannot_reuse_read(self):
        self.read(); self.blocked(self.payload(session='s2'))

    def test_wrong_call_id_cannot_mark(self):
        args = {'path': str(self.card)}
        self.run_hook(self.payload(tool='read_file', args=args, call_id='a'))
        self.run_hook(self.payload(event='post_tool_call', tool='read_file', args=args, call_id='b', result=json.dumps({'content': numbered(self.card.read_text()), 'total_lines': 2, 'truncated': False}), status='success'))
        self.blocked(self.payload())

    def test_overlapping_no_id_reads_are_denied(self):
        args = {'path': str(self.card)}
        self.run_hook(self.payload(tool='read_file', args=args, call_id=None))
        self.blocked(self.payload(tool='read_file', args=args, call_id=None), 'pending')

    def test_invalid_skill_blocks_write(self):
        self.blocked(self.payload(tool='write_file', args={'path': str(self.skill), 'content': '# Missing frontmatter\n'}), 'skill')

    def test_valid_skill_full_write_allowed(self):
        self.assertEqual(self.run_hook(self.payload(tool='write_file', args={'path': str(self.skill), 'content': skill()})), {})

    def test_mcp_plaintext_secret_blocks_write(self):
        cfg = {'mcp_servers': {'github': {'url': 'https://example.invalid/mcp', 'headers': {'Authorization': 'Bearer fixture-plaintext-not-secret'}}}}
        self.blocked(self.payload(tool='write_file', args={'path': str(self.config), 'content': json.dumps(cfg)}), 'plaintext')

    def test_mcp_command_argument_secret_blocks(self):
        cfg = {'mcp_servers': {'github': {'command': 'server', 'args': ['--api-key', 'fixture-value']}}}
        self.blocked(self.payload(tool='write_file', args={'path': str(self.config), 'content': json.dumps(cfg)}), 'credential')

    @unittest.skipIf(importlib.util.find_spec("yaml"), "JSON-only fallback checked only without PyYAML")
    def test_general_yaml_missing_dependency_blocks(self):
        self.config.write_text('mcp_servers:\n  github:\n    url: https://example.invalid/mcp\n')
        self.blocked(self.payload(), 'general YAML parser')

    def test_skill_batch_explicitly_denied(self):
        self.blocked(self.payload(tool='skill_manage', args={'operations': [{'action': 'create', 'name': 'demo', 'content': skill()}, {'action': 'create', 'name': 'broken', 'content': 'bad'}]}), 'aggregate')

    def test_connector_batch_explicitly_denied_even_after_read(self):
        self.read()
        self.blocked(self.payload(tool='COMPOSIO_MULTI_EXECUTE_TOOL', args={'tools': [{'tool_slug': 'read'}, {'tool_slug': 'send'}]}), 'unsupported')

    def test_mapped_tool_cannot_hide_batch(self):
        self.read(); self.blocked(self.payload(args={'actions': [{'action': 'read'}, {'action': 'send'}]}), 'aggregate')

    def test_unknown_mcp_route_denied(self):
        self.read(); self.blocked(self.payload(tool='mcp__github__delete_issue'), 'unsupported')

    def test_terminal_denied_no_simulated_prewrite_claim(self):
        self.blocked(self.payload(tool='terminal', args={'command': 'echo bad > config.yaml'}), 'unsupported')

    def test_patch_denied(self):
        self.blocked(self.payload(tool='patch', args={'path': str(self.skill), 'new_string': 'bad'}), 'unsupported')

    def test_pre_verify_catches_actual_invalid_edit(self):
        self.skill.write_text('bad actual edit')
        result = self.run_hook(self.payload(event='pre_verify', tool=None, args=None, coding=True, attempt=0, changed_paths=[str(self.skill)]))
        self.assertEqual(result['action'], 'continue'); self.assertIn('skill', result['message'])

    def test_post_detects_actual_invalid_edit_observer_only(self):
        self.config.write_text('{"mcp_servers":{"github":{"env":{"TOKEN":"fixture-plaintext"},"command":"server"}}}')
        result = self.run_hook(self.payload(event='post_tool_call', tool='terminal', result='{}', status='success'))
        self.assertEqual(result, {})
        findings = json.loads((self.state / 'findings.json').read_text())
        self.assertTrue(findings['violations']); self.assertTrue(findings['observer_only'])
        self.assertEqual(self.run_hook(self.payload(event='pre_verify', tool=None, coding=True, attempt=1))['action'], 'continue')

    def test_pre_verify_valid_is_noop(self):
        self.assertEqual(self.run_hook(self.payload(event='pre_verify', tool=None, coding=True, attempt=0)), {})

    def test_missing_session_blocks(self):
        self.blocked(self.payload(session=''), 'session')

    def test_profile_home_mismatch_blocks(self):
        p=self.payload(); p['profile']='wrong'; self.blocked(p, 'profile')

    def test_claude_payload_not_accepted(self):
        self.blocked({'hook_event_name':'PreToolUse','tool_name':'Read','tool_input':{'file_path':str(self.card)},'session_id':'s1'}, 'unsupported')

    def test_no_claude_mcp_config_substitution(self):
        self.config.unlink()
        (self.home / '.mcp.json').write_text(json.dumps({'mcpServers': {'github': {'url': 'https://example.invalid'}}}))
        self.blocked(self.payload(), 'config.yaml')

    def test_write_outside_native_assets_denied(self):
        self.blocked(self.payload(tool='write_file', args={'path': str(self.root/'unowned.py'), 'content':'bad'}), 'unsupported')

    def test_append_denied(self):
        self.blocked(self.payload(tool='write_file', args={'path': str(self.skill), 'content': skill(), 'append':True}), 'append')

    def test_disabled_mcp_server_denied(self):
        self.cfg['mcp_servers']['github']['enabled']=False; self.config.write_text(json.dumps(self.cfg))
        self.read(); self.blocked(self.payload(), 'disabled')

    def test_symlink_card_escape_denied(self):
        self.card.unlink(); self.card.symlink_to(self.skill)
        self.blocked(self.payload(), 'symlink')

    def test_description_requires_use_when_custom_policy(self):
        bad = skill().replace('Use when testing a bounded fixture skill.', 'A bounded fixture skill.')
        self.blocked(self.payload(tool='write_file', args={'path': str(self.skill), 'content': bad}), 'Use when')

    def test_501_body_lines_denied(self):
        bad = skill().split('\n---\n', 1)[0] + '\n---\n' + '\n'.join(['step'] * 501)
        self.blocked(self.payload(tool='write_file', args={'path': str(self.skill), 'content': bad}), '500')

    def test_500_body_lines_allowed(self):
        good = skill().split('\n---\n', 1)[0] + '\n---\n' + '\n'.join(['step'] * 500)
        self.assertEqual(self.run_hook(self.payload(tool='write_file', args={'path': str(self.skill), 'content': good})), {})

    def test_one_level_existing_reference_allowed(self):
        ref = self.skill.parent / 'references' / 'guide.md'
        ref.parent.mkdir(); ref.write_text('# Direct guide\n')
        good = skill() + '[guide](references/guide.md)\n'
        self.assertEqual(self.run_hook(self.payload(tool='write_file', args={'path': str(self.skill), 'content': good})), {})

    def test_chained_reference_denied(self):
        ref = self.skill.parent / 'guide.md'
        ref.write_text('[chain](other.md)\n')
        bad = skill() + '[guide](guide.md)\n'
        self.blocked(self.payload(tool='write_file', args={'path': str(self.skill), 'content': bad}), 'chained')

    def test_deep_reference_denied(self):
        bad = skill() + '[guide](references/deep/guide.md)\n'
        self.blocked(self.payload(tool='write_file', args={'path': str(self.skill), 'content': bad}), 'one subdirectory')

    def test_missing_reference_denied(self):
        bad = skill() + '[guide](missing.md)\n'
        self.blocked(self.payload(tool='write_file', args={'path': str(self.skill), 'content': bad}), 'missing skill reference')

    def test_reference_definition_escape_denied(self):
        bad = skill() + '[guide][source]\n[source]: ../outside.md\n'
        self.blocked(self.payload(tool='write_file', args={'path': str(self.skill), 'content': bad}), 'one subdirectory')

    def test_env_placeholders_supported(self):
        cfg = {'mcp_servers': {'github': {'command': 'server', 'env': {'GITHUB_TOKEN': '${GITHUB_TOKEN}'}}}}
        self.assertEqual(self.run_hook(self.payload(tool='write_file', args={'path': str(self.config), 'content': json.dumps(cfg)})), {})

    def test_header_placeholders_supported(self):
        cfg = {'mcp_servers': {'github': {'url': 'https://example.invalid/mcp', 'headers': {'Authorization': 'Bearer ${env:GITHUB_TOKEN}', 'X-Api-Key': '${API_KEY}'}}}}
        self.assertEqual(self.run_hook(self.payload(tool='write_file', args={'path': str(self.config), 'content': json.dumps(cfg)})), {})

    def test_embedded_plaintext_with_placeholder_denied(self):
        cfg = {'mcp_servers': {'github': {'url': 'https://example.invalid/mcp', 'headers': {'Authorization': 'Bearer fixture-plaintext${TOKEN}'}}}}
        self.blocked(self.payload(tool='write_file', args={'path': str(self.config), 'content': json.dumps(cfg)}), 'plaintext')

    def test_print_exact_hook_config(self):
        proc = subprocess.run([sys.executable, '-B', str(SCRIPT), '--policy', str(self.policy), '--print-hook-config'], text=True, capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0)
        cfg = json.loads(proc.stdout)
        self.assertEqual(set(cfg['hooks']), {'pre_tool_call', 'post_tool_call', 'pre_verify'})
        self.assertTrue(cfg['hooks']['pre_tool_call'][0]['fail_closed'])
        self.assertNotIn('fail_closed', cfg['hooks']['pre_verify'][0])
        self.assertNotIn('matcher', cfg['hooks']['pre_tool_call'][0])

    def test_copied_adapter_uses_operator_state_location(self):
        # Script copied under an installation dir; state stays OUTSIDE that dir
        # but still within our authorized fixture sandbox for this execution.
        installation = self.root / 'installed'; installation.mkdir()
        copied = installation / 'hermes_guard.py'; copied.write_bytes(SCRIPT.read_bytes())
        proc = subprocess.run([sys.executable, '-B', str(copied), '--policy', str(self.policy)], input=json.dumps(self.payload(event='pre_verify', tool=None, coding=True, attempt=0)), text=True, capture_output=True, env={**os.environ, 'HERMES_HOME': str(self.home)}, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stdout+proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {})
        self.assertTrue((self.state/'state.json').is_file())
        self.assertFalse((installation/'hermes-fixtures').exists())

    @unittest.skipUnless(importlib.util.find_spec('yaml'), 'PyYAML prerequisite missing; no install authorized')
    def test_general_yaml_with_actual_pyyaml(self):
        self.config.write_text('mcp_servers:\n  github:\n    url: https://example.invalid/mcp\n')
        self.skill.write_text('---\nname: demo\ndescription: Use when checking general YAML fixtures.\n---\n# Steps\nRead source.\n')
        self.assertEqual(self.run_hook(self.payload(event='pre_verify', tool=None, coding=True, attempt=0)), {})

    def test_native_name_from_pinned_runtime_function(self):
        import re
        import hashlib
        import logging
        source = FIXTURES/'sources'/'tools__mcp_tool_schema.py'
        tree = ast.parse(source.read_text())
        names = {'sanitize_mcp_name_component', 'mcp_prefixed_tool_name'}
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        env = {'re': re, 'hashlib': hashlib, 'logger': logging.getLogger('fixture'), 'MCP_TOOL_NAME_PREFIX':'mcp__', '_MCP_TOOL_NAME_MAX_LENGTH':64, '_MCP_TOOL_NAME_HASH_LENGTH':8, '_clamped_names_warned':set()}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), env)
        self.assertEqual(env['mcp_prefixed_tool_name']('github', 'get_issue'), 'mcp__github__get_issue')
        self.assertEqual(env['mcp_prefixed_tool_name']('my-server', 'read-item'), 'mcp__my_server__read_item')

    def test_actual_pinned_serializer_envelope(self):
        import builtins
        import types
        source = FIXTURES/'sources'/'agent__shell_hooks.py'
        tree=ast.parse(source.read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'_payload_fields','_serialize_payload'}]
        def scoped_import(name, *args, **kwargs):
            if name == 'hermes_cli.profiles':
                return types.SimpleNamespace(get_active_profile_name=lambda:'fixture')
            return builtins.__import__(name,*args,**kwargs)
        env={'json':json,'Path':Path,'Any':object,'_TOP_LEVEL_PAYLOAD_KEYS':{'tool_name','args','session_id','parent_session_id'},'__builtins__':{**vars(builtins),'__import__':scoped_import}}
        exec(compile(ast.Module(body=functions,type_ignores=[]),str(source),'exec'),env)
        wire=json.loads(env['_serialize_payload']('post_tool_call',{'tool_name':'read_file','args':{'path':str(self.card)},'session_id':'s1','tool_call_id':'read1','result':'{}','status':'success'}))
        self.assertEqual(wire['tool_input'],{'path':str(self.card)})
        self.assertEqual(wire['extra'],{'tool_call_id':'read1','result':'{}','status':'success'})
        self.assertEqual(wire['profile'],'fixture')
        self.assertNotIn('tool_use_id',wire)

    def test_policy_revision_invalidates_completed_read(self):
        self.read()
        self.assertEqual(self.run_hook(self.payload()), {})
        self.policy.write_text(self.policy.read_text() + "\n")
        self.blocked(self.payload(), 'successful full read_file')
        self.read(call_id='new-policy-read')
        self.assertEqual(self.run_hook(self.payload()), {})

    def test_policy_revision_invalidates_pending_read(self):
        args = {'path': str(self.card)}
        self.run_hook(self.payload(tool='read_file', args=args, call_id='pending'))
        self.policy.write_text(self.policy.read_text() + "\n")
        text = self.card.read_text()
        result = {'content': numbered(text), 'total_lines': len(text.splitlines()), 'file_size': len(text.encode()), 'truncated': False}
        self.run_hook(self.payload(event='post_tool_call', tool='read_file', args=args, call_id='pending', result=json.dumps(result), status='success'))
        self.blocked(self.payload(), 'successful full read_file')

    def test_first_call_receipt_reusable_without_state_rewrite(self):
        self.read()
        state = self.state / 'state.json'
        original = state.stat().st_mtime_ns
        self.assertEqual(self.run_hook(self.payload(call_id='first')), {})
        self.assertEqual(self.run_hook(self.payload(call_id='second')), {})
        self.assertEqual(state.stat().st_mtime_ns, original)

    def test_json_core_imports_stdlib_only(self):
        tree=ast.parse(SCRIPT.read_text())
        roots={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import)} | {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module}
        self.assertFalse(roots - sys.stdlib_module_names, roots - sys.stdlib_module_names)


if __name__ == '__main__':
    unittest.main()

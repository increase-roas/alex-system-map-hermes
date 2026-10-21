import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import local_files as lf


class LocalFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.root = self.home / '.agents'
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def scan(self, **kw):
        return lf.scan(self.home, roots=[(self.root, 'fixture')], **kw)

    def test_exact_copies_links_generated_and_evidence(self):
        a = self.put('instructions/a.md', 'Always use Hindsight as the only memory layer.\nNever send customer emails.\n')
        self.put('instructions/b.md', a.read_text())
        (self.root / 'linked.md').symlink_to(a)
        self.put('generated.md', '<!-- GENERATED\nSources: instructions/a.md\n-->\nAlways use local files as the only memory layer.\nAlways send customer emails.\n')
        idx = self.scan()
        self.assertEqual({'same_file', 'identical_copy'}, {g['kind'] for g in idx['duplicates']})
        self.assertTrue(any(r['kind'] == 'generated_from' for r in idx['references']))
        self.assertTrue(any(f['kind'] == 'repeated_rule' for f in idx['findings']))
        candidates = [f for f in idx['findings'] if f['kind'] == 'conflict_candidate']
        self.assertTrue(candidates)
        self.assertTrue(all(f['confidence'] == 'candidate' and len(f['evidence']) >= 2 and all(e['line'] > 0 for e in f['evidence']) for f in candidates))

    def test_content_changed_missing_and_unknown_id(self):
        p = self.put('rule.md', 'Always keep the original.\n')
        idx = self.scan()
        row = idx['files'][0]
        p.write_text('Changed contents\n')
        self.assertTrue(lf.content(idx, row['id'])['changed_since_scan'])
        p.unlink()
        self.assertIn('error', lf.content(idx, row['id']))
        with self.assertRaises(KeyError):
            lf.content(idx, '../../etc/passwd')

    def test_secret_screening_recursive_config_and_evidence(self):
        raw = '{"apiKey":"arbitrary-value-should-not-leak","nested":{"password":"odd credential"},"commands":["curl -H Authorization: Bearer myprivatevalue https://example.com"],"safe":"visible"}'
        self.put('settings.json', raw)
        self.put('rules.md', 'export API_KEY=hidden-value\n-----BEGIN PRIVATE KEY-----\nprivatebody\n-----END PRIVATE KEY-----\nNever send token=abc123 customer emails.\n')
        idx = self.scan()
        combined = json.dumps(idx) + ''.join(lf.content(idx, f['id'])['content'] for f in idx['files'])
        for secret in ['arbitrary-value-should-not-leak', 'odd credential', 'myprivatevalue', 'hidden-value', 'privatebody', 'abc123']:
            self.assertNotIn(secret, combined)
        self.assertIn('visible', combined)
        self.assertTrue(all(lf.content(idx, f['id'])['redacted'] for f in idx['files']))
        self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(), next(f['sha256'] for f in idx['files'] if f['path'].endswith('settings.json')))

    def test_boundary_alias_cycle_broken_exclusions_and_limits(self):
        self.put('rules/one.md', 'one')
        (self.root / 'alias').symlink_to(self.root / 'rules', target_is_directory=True)
        (self.root / 'rules' / 'cycle').symlink_to(self.root, target_is_directory=True)
        outside = self.home / 'outside.md'
        outside.write_text('outside private')
        (self.root / 'escape.md').symlink_to(outside)
        (self.root / 'broken.md').symlink_to(self.root / 'absent.md')
        self.put('.env', 'TOP_SECRET=value')
        self.put('auth.json', '{"secret":"private"}')
        self.put('node_modules/no.md', 'dependency')
        self.put('big.md', 'x' * 300)
        idx = self.scan(max_bytes=100)
        self.assertFalse(any(f['path'].endswith(('escape.md', '.env', 'auth.json', 'no.md')) for f in idx['files']))
        self.assertTrue(any(f['path'].endswith('alias/one.md') for f in idx['files']))
        self.assertTrue(any(f['state'] == 'missing' for f in idx['files']))
        self.assertTrue(any(f['state'] == 'too_large' for f in idx['files']))
        self.assertTrue(idx['coverage']['truncated'])
        one = self.scan(max_files=1)
        self.assertEqual(1, len(one['files']))
        self.assertTrue(one['coverage']['truncated'])

    def test_multiline_secret_sections_and_line_proof(self):
        text = '[env]\nUNUSUAL_NAME = "arbitrary-hidden"\n[normal]\nmode = "visible"\n'
        screened, redacted = lf.screen(text)
        self.assertNotIn('arbitrary-hidden', screened)
        self.assertIn('visible', screened)
        self.assertEqual(text.count('\n'), screened.count('\n'))
        text = 'env:\n  ODD_NAME: hidden-yaml-value\nsafe: visible\n'
        screened, _ = lf.screen(text)
        self.assertNotIn('hidden-yaml-value', screened)
        self.assertIn('visible', screened)

    def test_command_argument_containers_withhold_arbitrary_credentials(self):
        secret = 'fixture-opaque-value-723'
        fixtures = [
            '{"command":"bridge","args":["--api-key","' + secret + '"]}',
            'command = "bridge"\nargs = ["--api-key", "' + secret + '"]\n',
            'command = "bridge"\nargs = [\n "--api-key",\n "' + secret + '",\n]\nsafe = "visible"\n',
            'command: bridge\nargs:\n  - --api-key\n  - ' + secret + '\nsafe: visible\n',
            'args:\n- --api-key\n- ' + secret + '\nsafe: visible\n',
            'command: bridge\nargs: ["--api-key", "' + secret + '"]\n',
        ]
        for text in fixtures:
            with self.subTest(format=text.splitlines()[0][:15]):
                screened, redacted = lf.screen(text)
                self.assertNotIn(secret, screened)
                self.assertTrue(redacted)
                self.assertEqual(text.count('\n'), screened.count('\n'))
        self.put('settings.json', fixtures[0])
        idx = self.scan()
        self.assertNotIn(secret, json.dumps(idx) + lf.content(idx, idx['files'][0]['id'])['content'])

    def test_alias_to_excluded_target_is_never_read(self):
        target = self.put('auth.json', '{"safe":"fixture-private-auth"}')
        (self.root / 'harmless.md').symlink_to(target)
        idx = self.scan()
        self.assertEqual([], idx['files'])
        self.assertNotIn('fixture-private-auth', json.dumps(idx))
        # A stale stored row must also be refused by the content boundary.
        forged = {'files': [{'id': 'old-id', 'path': str(self.root / 'harmless.md'), 'real_path': str(target), 'sha256': None}], 'coverage': idx['coverage']}
        self.assertIn('error', lf.content(forged, 'old-id'))

    def test_fair_roots_prioritize_harness_rules_with_hard_aggregate_budget(self):
        skills = self.root / 'skills'
        skills.mkdir()
        for i in range(100):
            (skills / ('skill-%03d.md' % i)).write_text('x' * 262144)
        codex = self.home / '.codex'
        codex.mkdir()
        (codex / 'AGENTS.md').write_text('Always keep Codex rules visible.\n')
        (codex / 'config.toml').write_text('mode = "fixture"\n')
        claude = self.home / '.claude'
        claude.mkdir()
        (claude / 'CLAUDE.md').write_text('Always keep Claude rules visible.\n')
        alias = self.home / '.cursor'
        alias.symlink_to(claude, target_is_directory=True)
        roots = [(skills, 'large skills'), (codex, 'Codex'), (claude, 'Claude'), (alias, 'Cursor alias')]
        actual_bytes = 0
        original = lf.read_source
        def measured(*args, **kwargs):
            nonlocal actual_bytes
            result = original(*args, **kwargs)
            actual_bytes += len(result[0])
            return result
        with patch.object(lf, 'read_source', side_effect=measured):
            idx = lf.scan(self.home, roots=roots)
        paths = {f['path'] for f in idx['files'] if f['state'] == 'readable'}
        for p in [codex / 'AGENTS.md', codex / 'config.toml', claude / 'CLAUDE.md', alias / 'CLAUDE.md']:
            self.assertIn(str(p), paths)
        self.assertLessEqual(actual_bytes, 24 * 1024 * 1024)
        self.assertEqual('partial', idx['coverage']['roots'][0]['state'])
        self.assertTrue(idx['coverage']['truncated'])
        with patch.object(lf, 'read_source', side_effect=PermissionError('fixture')):
            failed = lf.scan(self.home, roots=[(codex, 'Codex')])
        self.assertEqual('partial', failed['coverage']['roots'][0]['state'])
        limited = lf.scan(self.home, roots=roots, max_files=1)
        self.assertTrue(all(r['state'] == 'partial' for r in limited['coverage']['roots']))

    def test_ordinary_prose_has_no_findings_and_mixed_case_memory_declarations_remain(self):
        self.put('ordinary.md', ('ordinary prose without a declaration ' * 20 + '\n') * 100)
        ordinary = self.scan()
        self.assertEqual([], ordinary['findings'])
        self.put('a.md', 'Always use Hindsight as the ONLY memory layer.\n')
        self.put('b.md', 'Always use local files as the ONE MEMORY LAYER.\n')
        idx = self.scan()
        self.assertTrue(any(f['kind'] == 'conflict_candidate' and f['topic'].startswith('exclusive memory declarations') for f in idx['findings']))

    def test_read_failure_and_retargeted_alias(self):
        p = self.put('rules.md', 'source')
        idx = self.scan()
        with patch.object(lf, 'read_source', side_effect=PermissionError('private filename or credential')):
            result = lf.content(idx, idx['files'][0]['id'])
            self.assertEqual('Unable to read source (PermissionError)', result['error'])
        p.unlink()
        outside = self.home / 'outside.md'
        outside.write_text('must not leak')
        p.symlink_to(outside)
        self.assertIn('error', lf.content(idx, idx['files'][0]['id']))


if __name__ == '__main__':
    unittest.main(verbosity=2)

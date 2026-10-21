import json
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import local_files
import local_file_repairs as repairs


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL).decode().strip()


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='local-file-repairs-')
        self.home = Path(self.tmp.name).resolve()
        self.repo = self.home / '.agents'
        self.repo.mkdir()
        self.rules = self.repo / 'instructions'
        self.rules.mkdir()
        self.file = self.rules / 'alpha.md'
        self.before = 'Always keep reviewed source evidence.\n'
        self.after = 'Always preserve reviewed source evidence.\n'
        self.file.write_text(self.before)
        self.file.chmod(0o640)
        (self.rules / 'other.md').write_text('Other original\n')
        (self.rules / 'dirty.md').write_text('Dirty original\n')
        git(self.repo, 'init', '-b', 'main')
        git(self.repo, 'config', 'user.email', 'fixture@example.invalid')
        git(self.repo, 'config', 'user.name', 'Fixture')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-m', 'Fixture baseline')
        self.remote = self.home / 'origin.git'
        subprocess.run(['git', 'init', '--bare', str(self.remote)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        git(self.repo, 'remote', 'add', 'origin', str(self.remote))
        git(self.repo, 'push', '-u', 'origin', 'main')
        (self.home / 'Backups').mkdir()
        self.state = self.home / 'state'
        self.state.mkdir()
        self.index = local_files.scan(self.home, roots=[(self.rules, 'fixture')])
        self.index_path = self.state / 'local-files.json'
        self.index_path.write_text(json.dumps(self.index))
        self.row = next(r for r in self.index['files'] if r['path'] == str(self.file))
        self.env = patch.dict(os.environ, {'LOCAL_FILE_REPAIR_FIXTURE_HOME': str(self.home)})
        self.env.start()
        self.service = repairs.RepairService(self.home, self.index_path, self.state)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def preview(self):
        return self.service.preview(self.row['id'], self.row['sha256'], self.after)

    def test_apply_undo_exact_backup_remote_and_other_changes(self):
        (self.rules / 'other.md').write_text('Other staged\n')
        git(self.repo, 'add', 'instructions/other.md')
        (self.rules / 'dirty.md').write_text('Other dirty\n')
        staged = git(self.repo, 'show', ':instructions/other.md')
        preview = self.preview()
        self.assertIn('-Always keep', preview['diff'])
        self.assertEqual(self.before, self.file.read_text())
        applied = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual('applied', applied['state'])
        self.assertTrue(applied['pushed'])
        self.assertEqual(self.after, self.file.read_text())
        self.assertEqual(0o640, self.file.stat().st_mode & 0o777)
        self.assertEqual(self.before.encode(), Path(applied['backup_path']).read_bytes())
        self.assertEqual('Always preserve reviewed source evidence.', git(self.remote, 'show', 'main:instructions/alpha.md'))
        head = git(self.repo, 'rev-parse', 'HEAD')
        self.assertEqual(applied, self.service.apply(preview['repair_id'], preview['proposal_sha256']))
        self.assertEqual(head, git(self.repo, 'rev-parse', 'HEAD'))
        undone = self.service.undo(preview['repair_id'])
        self.assertEqual('undone', undone['state'])
        self.assertEqual(self.before, self.file.read_text())
        self.assertEqual('Always keep reviewed source evidence.', git(self.remote, 'show', 'main:instructions/alpha.md'))
        self.assertEqual(staged, git(self.repo, 'show', ':instructions/other.md'))
        self.assertEqual('Other dirty\n', (self.rules / 'dirty.md').read_text())
        self.assertEqual(undone, self.service.undo(preview['repair_id']))

    def test_stale_and_secret_proposals_never_write(self):
        preview = self.preview()
        self.file.write_text('Third party edit\n')
        with self.assertRaises(repairs.RepairError) as ctx:
            self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual(409, ctx.exception.status)
        self.assertEqual('Third party edit\n', self.file.read_text())
        self.file.write_text(self.before)
        with self.assertRaises(repairs.RepairError):
            self.service.preview(self.row['id'], self.row['sha256'], 'api_key=fixture-opaque-secret\n')
        self.assertEqual(self.before, self.file.read_text())

    def test_unbacked_git_and_untracked_and_path_ownership_refused(self):
        git(self.repo, 'remote', 'remove', 'origin')
        with self.assertRaises(repairs.RepairError):
            self.preview()
        self.assertEqual(self.before, self.file.read_text())
        self.assertFalse(self.service.source('../../etc/passwd')['editable'])
        alias = self.rules / 'alias.md'
        alias.symlink_to(self.file)
        self.index = local_files.scan(self.home, roots=[(self.rules, 'fixture')])
        self.index_path.write_text(json.dumps(self.index))
        row = next(r for r in self.index['files'] if r['path'] == str(alias))
        self.assertFalse(self.service.source(row['id'])['editable'])
        self.file.write_text('<!-- GENERATED by fixture; DO NOT EDIT -->\n')
        self.assertFalse(self.service.source(self.row['id'])['editable'])

    def test_conditional_undo_and_publish_pending_do_not_retry_effects(self):
        preview = self.preview()
        original = self.service.publish
        calls = []
        def failed_publish(*args):
            calls.append(1)
            raise repairs.RepairError('fixture_push_failure', 'Fixture remote unavailable', 409)
        with patch.object(self.service, 'publish', side_effect=failed_publish):
            result = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
            self.assertEqual('applied_publish_pending', result['state'])
            self.assertEqual(result, self.service.apply(preview['repair_id'], preview['proposal_sha256']))
        self.assertEqual(1, len(calls))
        self.file.write_text('Newer edit\n')
        with self.assertRaises(repairs.RepairError):
            self.service.undo(preview['repair_id'])
        self.assertEqual('Newer edit\n', self.file.read_text())

    def test_frozen_fingerprint_untracked_and_generated_owners(self):
        preview = self.preview()
        with self.assertRaises(repairs.RepairError):
            self.service.apply(preview['repair_id'], '0' * 64)
        untracked = self.rules / 'untracked.md'
        untracked.write_text('Untracked rule source\n')
        generated = self.repo / 'AGENTS.md'
        generated.write_text('<!-- GENERATED by fixture\nSources: instructions/alpha.md\n-->\n')
        config = self.rules / 'settings.json'
        config.write_text('{"mode":"fixture"}')
        self.index = local_files.scan(self.home, roots=[(self.repo, 'fixture')])
        self.index_path.write_text(json.dumps(self.index))
        rows = {Path(r['path']).name: r for r in self.index['files']}
        with self.assertRaises(repairs.RepairError):
            self.service.preview(rows['untracked.md']['id'], rows['untracked.md']['sha256'], 'Proposed untracked rule\n')
        source = self.service.source(rows['AGENTS.md']['id'])
        self.assertFalse(source['editable'])
        self.assertIn(self.row['id'], source['source_file_ids'])
        self.assertFalse(self.service.source(rows['settings.json']['id'])['editable'])
        self.assertEqual(self.before, self.file.read_text())

    def test_native_generated_header_maps_to_indexed_agents_owner(self):
        codex = self.home / '.codex'
        codex.mkdir()
        generated = codex / 'AGENTS.md'
        generated.write_text('<!-- GENERATED by tools/unify/build_instructions.py; DO NOT EDIT.\nSources: instructions/alpha.md (Voice; Delegation and model routing)\n-->\n')
        idx = local_files.scan(self.home, roots=[(self.rules, 'instructions'), (generated, 'Codex distribution')])
        idx['references'] = []  # Generic cross-harness resolution need not work.
        self.index_path.write_text(json.dumps(idx))
        row = next(r for r in idx['files'] if r['path'] == str(generated))
        owner = self.service.source(row['id'])
        self.assertFalse(owner['editable'])
        self.assertEqual([self.row['id']], owner['source_file_ids'])
        self.assertTrue(self.preview()['generated_follow_up'])

    def test_replayed_receipts_refuse_newer_source_and_index(self):
        preview = self.preview()
        self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.file.write_text('Newer source contents\n')
        with self.assertRaises(repairs.RepairError):
            self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.file.write_text(self.after)
        self.file.write_text('New staged target\n')
        git(self.repo, 'add', 'instructions/alpha.md')
        self.file.write_text(self.after)
        with self.assertRaises(repairs.RepairError):
            self.service.undo(preview['repair_id'])
        self.assertEqual(self.after, self.file.read_text())
        self.assertEqual('New staged target', git(self.repo, 'show', ':instructions/alpha.md'))

    def test_publication_does_not_commit_intervening_target_edit(self):
        preview = self.preview()
        original = self.service.replace
        def changed_after_replacement(*args):
            original(*args)
            self.file.write_text('Intervening source edit\n')
        with patch.object(self.service, 'replace', side_effect=changed_after_replacement):
            result = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual('applied_publish_pending', result['state'])
        self.assertEqual('Intervening source edit\n', self.file.read_text())
        self.assertEqual(hashlib.sha256(self.file.read_bytes()).hexdigest(), result['current_sha256'])
        self.assertEqual(self.before.strip(), git(self.repo, 'show', 'HEAD:instructions/alpha.md'))

    def test_loopback_origins_refused_before_network(self):
        for origin in ['https://localhost/repo.git', 'ssh://git@127.0.0.1/repo.git', 'git://[::1]/repo.git', 'git@localhost:repo.git']:
            git(self.repo, 'remote', 'set-url', 'origin', origin)
            with self.assertRaises(repairs.RepairError) as ctx:
                self.preview()
            self.assertEqual('remote_not_durable', ctx.exception.code)
        self.assertEqual(self.before, self.file.read_text())

    def test_fixture_boundary_and_default_local_origin_refused(self):
        with patch.dict(os.environ, {'LOCAL_FILE_REPAIR_FIXTURE_HOME': ''}):
            unconfigured = repairs.RepairService(self.home, self.index_path, self.state)
            with self.assertRaises(repairs.RepairError):
                unconfigured.preview(self.row['id'], self.row['sha256'], self.after)
        outside = Path(tempfile.gettempdir()) / 'outside-repair-state'
        with self.assertRaises(repairs.RepairError):
            repairs.RepairService(self.home, self.index_path, outside)


if __name__ == '__main__':
    unittest.main(verbosity=2)

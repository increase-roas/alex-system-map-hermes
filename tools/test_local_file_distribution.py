"""Native builder integration: all writes are private disposable fixture homes."""
import importlib.util
import shutil
from unittest.mock import patch
import json
from pathlib import Path
import unittest

import test_local_file_repairs as repair_tests
from test_local_file_repairs import git
import local_files
import local_file_repairs as repairs


class DistributionTests(unittest.TestCase):
    tearDown = repair_tests.RepairTests.tearDown
    preview = repair_tests.RepairTests.preview
    def setUp(self):
        repair_tests.RepairTests.setUp(self)
        builder = self.repo / 'tools/unify/build_instructions.py'
        builder.parent.mkdir(parents=True)
        shutil.copyfile(Path(__file__).parent / 'fixtures/native_instruction_builder.py', builder)
        self.file = self.rules / 'shared.md'
        self.file.write_text(self.before)
        self.file.chmod(0o640)
        for name, text in {'codex.md': 'Codex fixture rules.\n', 'claude.md': 'Claude fixture rules.\n',
                           'codex-style.md': '## Voice\nPlain fixture voice.\n## Delegation and model routing\nFixture routing.\n',
                           'shared-style.md': 'Shared fixture style.\n', 'claude-style.md': 'Claude fixture style.\n'}.items():
            (self.rules / name).write_text(text)
        for folder in ['.codex', '.claude/output-styles', '.cursor/rules']:
            (self.home / folder).mkdir(parents=True, exist_ok=True)
        self.config = self.home / '.codex/config.toml'
        self.config.write_text('model = "fixture-owned-by-app"\n')
        spec = importlib.util.spec_from_file_location('fixture_native_builder', builder)
        self.native = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.native)
        self.native.H = str(self.home)
        self.native.SRC = str(self.rules)
        self.native.OUT = {key: str(self.home / Path(value).relative_to(Path.home())) for key, value in self.native.OUT.items()}
        for key, text in self.native.build(rules_only=True).items():
            Path(self.native.OUT[key]).write_text(text)
            Path(self.native.OUT[key]).chmod(0o640)
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-m', 'Native fixture baseline')
        git(self.repo, 'push', 'origin', 'main')
        self.index = local_files.scan(self.home, roots=[(self.rules, 'fixture')])
        self.index_path.write_text(json.dumps(self.index))
        self.row = next(r for r in self.index['files'] if r['path'] == str(self.file))

    def test_native_preview_apply_undo_exact_scoped_copies(self):
        before = {key: Path(self.native.OUT[key]).read_bytes() for key in self.native.build(rules_only=True)}
        cfg = self.config.read_bytes()
        preview = self.preview()
        self.assertEqual('ready', preview['distribution']['status'])
        self.assertEqual({str(self.home / p) for p in ['.codex/AGENTS.md', 'AGENTS.md', '.cursor/rules/agent-routing.mdc', '.claude/CLAUDE.md']}, {r['path'] for r in preview['distribution']['targets']})
        self.assertTrue(any(r['kind'] == 'import' and r['diff'] == '' for r in preview['distribution']['targets']))
        self.assertEqual(self.before, self.file.read_text())
        result = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual('verified', result['distribution']['status'])
        self.assertFalse(result['generated_follow_up'])
        for key in ['codex', 'home_agents', 'cursor']:
            self.assertIn(self.after.encode().strip(), Path(self.native.OUT[key]).read_bytes())
        self.assertEqual(cfg, self.config.read_bytes())
        self.assertTrue(result['pushed'])
        undone = self.service.undo(preview['repair_id'])
        self.assertEqual('verified', undone['distribution']['status'])
        for key, raw in before.items():
            self.assertEqual(raw, Path(self.native.OUT[key]).read_bytes())
        self.assertEqual(cfg, self.config.read_bytes())

    def test_stale_native_input_or_destination_refused_before_source(self):
        preview = self.preview()
        output = self.home / '.codex/AGENTS.md'
        output.write_text('Newer destination\n')
        with self.assertRaises(repairs.RepairError):
            self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual(self.before, self.file.read_text())
        preview = self.preview()
        (self.rules / 'codex.md').write_text('New native input\n')
        with self.assertRaises(repairs.RepairError):
            self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual(self.before, self.file.read_text())

    def test_partial_copy_failure_retains_recovery_without_retry(self):
        import local_file_distribution as distribution
        preview = self.preview()
        with patch.object(distribution.Distribution, 'install', side_effect=OSError('fixture failure')):
            result = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual(self.after, self.file.read_text())
        self.assertEqual('pending', result['distribution']['status'])
        self.assertTrue(result['generated_follow_up'])
        self.assertEqual(result, self.service.apply(preview['repair_id'], preview['proposal_sha256']))
        self.assertTrue(Path(result['backup_path']).is_file())
        self.service.undo(preview['repair_id'])
        self.assertEqual(self.before, self.file.read_text())

    def test_undo_refuses_newer_output_or_canonical_input(self):
        preview = self.preview()
        self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        output = self.home / '.codex/AGENTS.md'
        output.write_text('Newer generated edit\n')
        with self.assertRaises(repairs.RepairError):
            self.service.undo(preview['repair_id'])
        self.assertEqual(self.after, self.file.read_text())
        self.assertEqual('Newer generated edit\n', output.read_text())

    def test_created_output_undo_keeps_backed_recovery(self):
        output = self.home / '.cursor/rules/agent-routing.mdc'
        output.unlink()
        preview = self.preview()
        result = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertTrue(output.exists())
        undone = self.service.undo(preview['repair_id'])
        self.assertFalse(output.exists())
        self.assertEqual('verified', undone['distribution']['status'])
        self.assertTrue(list(Path(result['backup_path']).parent.glob('*.created-recovery')))

    def test_checks_bound_and_style_settings_disclosed(self):
        report = {'status': 'passed', 'cases': [], 'limitations': []}
        preview = self.service.preview(self.row['id'], self.row['sha256'], self.after, checks=report)
        self.assertEqual(report, preview['checks'])
        frozen = self.service.load(preview['repair_id'])
        self.assertEqual(report, frozen['proposal']['checks'])

    def test_normal_failing_commit_hook_keeps_direct_copy_generation(self):
        hook = self.repo / '.git/hooks/pre-commit'
        marker = self.home / 'hook-ran'
        hook.write_text('#!/bin/sh\nprintf ran > "' + str(marker) + '"\nexit 1\n')
        hook.chmod(0o700)
        preview = self.preview()
        result = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual('ran', marker.read_text())
        self.assertFalse(result['pushed'])
        self.assertTrue(result['source_verified'])
        self.assertEqual('verified', result['distribution']['status'])
        self.assertFalse(result['generated_follow_up'])
        self.assertIn(self.after.encode().strip(), (self.home / '.codex/AGENTS.md').read_bytes())
        self.assertEqual(self.before.strip(), git(self.remote, 'show', 'main:instructions/shared.md'))

    def test_result_reconciles_exact_hook_output_and_detects_input_drift(self):
        preview = self.preview()
        original = self.service.publish
        def publish_with_native_hook(*args, **kwargs):
            # An existing hook may rewrite the same expected bytes/mode.
            for key in ['codex', 'home_agents', 'cursor']:
                path = Path(self.native.OUT[key])
                path.write_text(self.native.build(rules_only=True)[key])
            return original(*args, **kwargs)
        with patch.object(self.service, 'publish', side_effect=publish_with_native_hook):
            result = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual('verified', result['distribution']['status'])
        self.assertTrue(result['source_verified'])
        self.config.write_text('model = "newer-app-setting"\n')
        replay = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual('pending', replay['distribution']['status'])
        self.assertTrue(replay['generated_follow_up'])
        with self.assertRaises(repairs.RepairError):
            self.service.undo(preview['repair_id'])
        self.assertEqual(self.after, self.file.read_text())

    def test_builder_change_refused_without_executing_new_code(self):
        preview = self.preview()
        marker = self.home / 'must-not-execute'
        builder = self.repo / 'tools/unify/build_instructions.py'
        builder.write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
        with self.assertRaises(repairs.RepairError):
            self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertFalse(marker.exists())
        self.assertEqual(self.before, self.file.read_text())

    def test_legacy_receipt_has_pending_distribution_and_can_undo_source(self):
        preview = self.preview()
        applied = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        value = self.service.load(preview['repair_id'])
        value['proposal'].pop('distribution')
        value.pop('distribution_state')
        value['proposal_sha256'] = repairs.sha(repairs.canonical(value['proposal']))
        value['result'].pop('distribution')
        self.service.save(preview['repair_id'], value)
        replay = self.service.apply(preview['repair_id'], value['proposal_sha256'])
        self.assertEqual('pending', replay['distribution']['status'])
        undone = self.service.undo(preview['repair_id'])
        self.assertEqual('pending', undone['distribution']['status'])
        self.assertTrue(undone['pushed'])
        self.assertEqual(self.before, self.file.read_text())

    def test_style_source_exposes_unsupported_settings_dependency(self):
        path = self.rules / 'shared-style.md'
        row = next(r for r in self.index['files'] if r['path'] == str(path))
        preview = self.service.preview(row['id'], row['sha256'], 'New shared fixture style.\n')
        self.assertEqual([str(self.home / '.claude/output-styles/alex-big-brother.md')], [r['path'] for r in preview['distribution']['targets']])
        self.assertIn('App-owned config', ' '.join(preview['distribution']['limitations']))
        cfg = self.config.read_bytes()
        result = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertEqual('pending', result['distribution']['status'])
        self.assertEqual(cfg, self.config.read_bytes())

    def test_source_readback_after_publication_does_not_claim_verified(self):
        preview = self.preview()
        original = self.service.publish
        def changed_after_publish(*args, **kwargs):
            commit = original(*args, **kwargs)
            self.file.write_text('Newer source after publication\n')
            return commit
        with patch.object(self.service, 'publish', side_effect=changed_after_publish):
            result = self.service.apply(preview['repair_id'], preview['proposal_sha256'])
        self.assertTrue(result['pushed'])
        self.assertFalse(result['source_verified'])
        self.assertEqual('pending', result['distribution']['status'])
        self.assertIn('changed after confirmed publication', result['message'])
        self.assertNotIn('publication stopped', result['message'])
        self.assertNotIn('exact readback verified', result['message'])

    def test_native_constraints_reserve_shared_double_projection_budget(self):
        projected = self.native.build(rules_only=True)
        used = len(projected['codex'].encode()) + len(projected['home_agents'].encode())
        self.config.write_text('project_doc_max_bytes = ' + str(used + 534) + '\n')
        cfg = self.config.read_bytes()
        before_outputs = {key: Path(self.native.OUT[key]).read_bytes() for key in projected}
        constraint = self.service.distributor.constraints(self.file, self.before.encode())
        self.assertEqual(267, constraint['growth_budget_bytes'])
        self.assertEqual(len(self.before.encode()) + 267, constraint['max_candidate_bytes'])
        self.assertIn('native', constraint['reason'].lower())
        for name in ['codex.md', 'codex-style.md']:
            source = self.rules / name
            constraint = self.service.distributor.constraints(source, source.read_bytes())
            self.assertEqual(534, constraint['growth_budget_bytes'])
            self.assertEqual(len(source.read_bytes()) + 534, constraint['max_candidate_bytes'])
        self.assertIsNone(self.service.distributor.constraints(self.rules / 'claude.md', (self.rules / 'claude.md').read_bytes()))
        self.assertEqual(cfg, self.config.read_bytes())
        self.assertEqual(self.before, self.file.read_text())
        self.assertEqual(before_outputs, {key: Path(self.native.OUT[key]).read_bytes() for key in projected})

    def test_native_oversize_is_actionable_422_without_source_change(self):
        projected = self.native.build(rules_only=True)
        used = len(projected['codex'].encode()) + len(projected['home_agents'].encode())
        self.config.write_text('project_doc_max_bytes = ' + str(used + 534) + '\n')
        with self.assertRaises(repairs.RepairError) as ctx:
            self.service.preview(self.row['id'], self.row['sha256'], self.before + 'x' * 268 + '\n')
        self.assertEqual('native_projection_failed', ctx.exception.code)
        self.assertEqual(422, ctx.exception.status)
        self.assertIn('bytes', ctx.exception.message)
        self.assertIn('shorter', ctx.exception.message)
        self.assertEqual(self.before, self.file.read_text())

    def test_shrinking_preview_from_oversized_native_before_is_allowed(self):
        before = 'Keep the evidence. ' * 150 + '\n'
        self.file.write_text(before)
        git(self.repo, 'add', 'instructions/shared.md')
        git(self.repo, 'commit', '-m', 'Oversized source fixture')
        git(self.repo, 'push', 'origin', 'main')
        self.index = local_files.scan(self.home, roots=[(self.rules, 'fixture')])
        self.index_path.write_text(json.dumps(self.index))
        self.row = next(r for r in self.index['files'] if r['path'] == str(self.file))
        self.config.write_text('project_doc_max_bytes = 1024\n')
        cfg = self.config.read_bytes()
        candidate = 'Keep reviewed evidence.\n'
        constraints = self.service.distributor.constraints(self.file, before.encode())
        self.assertLess(constraints['max_candidate_bytes'], len(before.encode()))
        self.assertGreaterEqual(constraints['max_candidate_bytes'], len(candidate.encode()))
        preview = self.service.preview(self.row['id'], self.row['sha256'], candidate)
        self.assertEqual('ready', preview['distribution']['status'])
        self.assertEqual(before, self.file.read_text())
        self.assertEqual(cfg, self.config.read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)

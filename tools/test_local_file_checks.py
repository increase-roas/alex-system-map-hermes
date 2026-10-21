import copy
import json
import unittest
from local_file_checks import run_checks
from local_file_repairs import RepairError


class ChecksTests(unittest.TestCase):
    def setUp(self):
        self.context = {'target_file_id': 'target', 'canonical_gate_file_id': 'policy', 'files': [
            {'file_id': 'target', 'content': 'Ask before any work.\nKeep source evidence.\n'},
            {'file_id': 'policy', 'content': 'Own-stack reversible work proceeds.\nAsk before spending.\n'}]}
        self.candidate = 'Own-stack reversible work proceeds.\nAsk before spending.\nKeep source evidence.\n'
        self.cases = [
            {'id': 'own', 'scenario': 'Own-stack reversible repair, standing authorization applies.', 'purpose': 'fix', 'choices': {'A': 'Proceed with repair.', 'B': 'Ask before any work.', 'C': 'Spend money.'}, 'expected': 'A', 'rationale': 'Exact standing policy permits own-stack work.', 'evidence': [{'file_id': 'policy', 'line': 1, 'quote': 'Own-stack reversible work proceeds.'}]},
            {'id': 'spend', 'scenario': 'Repair requires spending money without approval.', 'purpose': 'preserve', 'choices': {'A': 'Spend immediately.', 'B': 'Ask for spending approval.', 'C': 'Ignore the task.'}, 'expected': 'B', 'rationale': 'Spending gate remains.', 'evidence': [{'file_id': 'policy', 'line': 2, 'quote': 'Ask before spending.'}]}]
        self.before = {'choices': [{'id': 'own', 'choice': 'B'}, {'id': 'spend', 'choice': 'B'}]}
        self.after = {'choices': [{'id': 'spend', 'choice': 'B'}, {'id': 'own', 'choice': 'A'}]}

    def run_fixture(self, plan=None, before=None, after=None):
        calls = []
        results = iter([{'cases': copy.deepcopy(self.cases)} if plan is None else plan, self.before if before is None else before, self.after if after is None else after])
        def invoke(prompt, schema):
            calls.append((prompt, schema))
            value = next(results)
            if isinstance(value, Exception): raise value
            return value
        return run_checks(self.context, self.candidate, invoke, 'fixture-model'), calls

    def test_passed_comparison_and_unlabelled_independent_runs(self):
        report, calls = self.run_fixture()
        self.assertEqual('passed', report['status'])
        self.assertEqual([('B', 'A'), ('B', 'B')], [(c['before'], c['after']) for c in report['cases']])
        self.assertEqual(3, len(calls))
        for prompt, _ in calls[1:]:
            payload = json.loads(prompt.split('EVIDENCE_JSON:\n', 1)[1])
            self.assertEqual({'id', 'scenario', 'choices'}, set(payload['scenarios'][0]))
            self.assertNotIn('expected', payload['scenarios'][0])
        baseline = json.loads(calls[1][0].split('EVIDENCE_JSON:\n', 1)[1])
        candidate = json.loads(calls[2][0].split('EVIDENCE_JSON:\n', 1)[1])
        self.assertEqual(self.context, baseline['instructions'])
        self.assertEqual(self.candidate, candidate['instructions']['files'][0]['content'])
        self.assertEqual(baseline['scenarios'], candidate['scenarios'])
        self.assertEqual('Ask before any work.\nKeep source evidence.\n', self.context['files'][0]['content'])
        self.assertIn('simulated', report['limitations'][0])

    def test_planner_numbered_sources_preserve_blank_unicode_and_decision_raw(self):
        self.context['files'][0]['content'] += '\nUnicode café α.\n'
        original = copy.deepcopy(self.context)
        report, calls = self.run_fixture()
        self.assertEqual('passed', report['status'])
        payload = json.loads(calls[0][0].split('EVIDENCE_JSON:\n', 1)[1])
        source = payload['context']['files'][0]
        self.assertNotIn('content', source)
        self.assertEqual([{'line': 1, 'text': 'Ask before any work.', 'ending': '\n'}, {'line': 2, 'text': 'Keep source evidence.', 'ending': '\n'}, {'line': 3, 'text': '', 'ending': '\n'}, {'line': 4, 'text': 'Unicode café α.', 'ending': '\n'}], source['source_lines'])
        self.assertIn('unprefixed text', calls[0][0])
        self.assertEqual(original, self.context)
        baseline = json.loads(calls[1][0].split('EVIDENCE_JSON:\n', 1)[1])
        self.assertEqual(original, baseline['instructions'])
        self.assertNotIn('source_lines', baseline['instructions']['files'][0])

    def test_check_failures_report_stage_and_exact_citation_problem(self):
        wrong_line = copy.deepcopy(self.cases)
        wrong_line[0]['evidence'][0]['line'] = 2
        report, calls = self.run_fixture(plan={'cases': wrong_line})
        self.assertEqual('unavailable', report['status'])
        self.assertIn('Planning failed: case 1 citation 1 does not match its exact one-based source line.', report['limitations'][-1])
        self.assertEqual(1, len(calls))
        for stage, kwargs in [('Planning', {'plan': RepairError('ai_provider_failed', 'PRIVATE_PROVIDER_DETAIL', 503)}), ('Before', {'before': {}}), ('Candidate', {'after': {}})]:
            report, _ = self.run_fixture(**kwargs)
            self.assertEqual('unavailable', report['status'])
            self.assertTrue(report['limitations'][-1].startswith(stage + ' '))
            self.assertNotIn('PRIVATE_PROVIDER_DETAIL', str(report))

    def test_unknown_is_recorded_and_fails_in_either_run(self):
        unknown = {'choices': [{'id': 'own', 'choice': 'unknown'}, {'id': 'spend', 'choice': 'B'}]}
        for before, after in [(unknown, None), (None, unknown)]:
            report, calls = self.run_fixture(before=before, after=after)
            self.assertEqual('failed', report['status'])
            self.assertEqual('failed', report['cases'][0]['status'])
            self.assertEqual('unknown', report['cases'][0]['before' if before else 'after'])
            self.assertEqual(3, len(calls))
            for prompt, schema in calls[1:]:
                self.assertIn('unknown', schema['properties']['choices']['items']['properties']['choice']['enum'])
                self.assertIn('choose unknown', prompt)

    def test_generated_relationship_is_supplied_without_discarding_peers(self):
        self.context['relationships'] = [{'source_id': 'mirror', 'target_id': 'target', 'kind': 'generated_from'}]
        self.context['files'].append({'file_id': 'mirror', 'content': 'Ask before any work.\n'})
        report, calls = self.run_fixture()
        self.assertEqual('passed', report['status'])
        for prompt, _ in calls[1:]:
            self.assertIn('source_id is derived from target_id', prompt)
            payload = json.loads(prompt.split('EVIDENCE_JSON:\n', 1)[1])
            self.assertEqual(self.context['relationships'], payload['instructions']['relationships'])
            self.assertEqual(['target', 'policy', 'mirror'], [f['file_id'] for f in payload['instructions']['files']])

    def test_candidate_failure_and_preservation_baseline_failure_are_failed(self):
        for before, after in [(None, self.before), ({'choices': [{'id': 'own', 'choice': 'B'}, {'id': 'spend', 'choice': 'A'}]}, None)]:
            with self.subTest(before=before, after=after):
                report, _ = self.run_fixture(before=before, after=after)
                self.assertEqual('failed', report['status'])
                self.assertTrue(any(c['status'] == 'failed' for c in report['cases']))

    def test_invalid_plans_stop_before_decision_runs(self):
        plans = [{'cases': []}, {'cases': self.cases * 3}]
        for mutation in ['quote', 'purpose', 'duplicate', 'choices']:
            cases = copy.deepcopy(self.cases)
            if mutation == 'quote': cases[0]['evidence'][0]['quote'] = 'invented authority'
            if mutation == 'purpose': cases[1]['purpose'] = 'fix'
            if mutation == 'duplicate': cases[1]['id'] = cases[0]['id']
            if mutation == 'choices': cases[0]['choices']['A'] = cases[0]['choices']['B']
            plans.append({'cases': cases})
        for plan in plans:
            with self.subTest(plan=plan):
                report, calls = self.run_fixture(plan=plan)
                self.assertEqual('unavailable', report['status'])
                self.assertEqual(1, len(calls))
                self.assertEqual([], report['cases'])

    def test_malformed_runs_or_provider_failure_never_pass_or_retry(self):
        for response in [{}, {'choices': []}, {'choices': [{'id': 'own', 'choice': 'A'}, {'id': 'own', 'choice': 'B'}]}, RepairError('ai_provider_failed', 'Static unavailable', 503)]:
            report, calls = self.run_fixture(before=response)
            self.assertEqual('unavailable', report['status'])
            self.assertEqual(2, len(calls))
            self.assertTrue(all(c['status'] == 'unknown' for c in report['cases']))
        report, calls = self.run_fixture(after={})
        self.assertEqual('unavailable', report['status'])
        self.assertEqual('B', report['cases'][0]['before'])
        self.assertEqual('unknown', report['cases'][0]['after'])
        self.assertEqual(3, len(calls))


if __name__ == '__main__': unittest.main()

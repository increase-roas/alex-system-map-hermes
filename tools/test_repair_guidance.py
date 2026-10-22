import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import repair_guidance as g


def selected(owner='claude', category='hook', **extra):
    return [{'target': dict(id='target-one', owner=owner, category=category, **extra),
             'snapshot': {'projection': 'PRIVATE source /secret/path user-intent'}}]


def response(urls):
    return {'successful': True, 'data': {'results': [
        {'id': u, 'url': u, 'title': 'Official documentation',
         'text': 'Hooks receive JSON input. Validate configuration before using hooks.\n\n' + 'Official instructions AGENTS.md rules skill SKILL.md settings configuration model plugin manifest agent adapter project history branch protected bank mission alert threshold evaluation dashboard panel computer environment machine. ' * 4}
        for u in urls], 'statuses': [{'id': u, 'status': 'success', 'source': 'crawled'} for u in urls]}}


class GuidanceTests(unittest.TestCase):
    def collect(self, sources=None, transform=None):
        def retrieve(urls):
            self.urls = urls
            value = response(urls)
            return transform(value) if transform else value
        with patch.object(g, '_retrieve', retrieve):
            return g.collect_guidance(sources or selected())

    def test_private_request_and_exact_passages(self):
        packet = self.collect()
        self.assertTrue(g.validate_guidance(packet, ['target-one']))
        self.assertNotIn('PRIVATE', json.dumps(self.urls))
        self.assertNotIn('/secret', json.dumps(self.urls))
        for source in packet['sources']:
            self.assertIsNone(source['version'])
            self.assertIsNone(source['publication_date'])
            self.assertEqual(source['crawl_status'], 'crawled')
            for passage in source['passages']:
                self.assertIn(passage['text'], response([source['url']])['data']['results'][0]['text'])
                self.assertEqual(passage['id'], 'p-' + hashlib.sha256(passage['text'].encode()).hexdigest())
        public = g.public_guidance(packet)
        for source in public['sources']:
            self.assertLessEqual(sum(len(p['text'].split()) for p in source['passages']), 24)
        bad = copy.deepcopy(packet)
        bad['sources'][0]['passages'][0]['text'] += ' fabricated'
        with self.assertRaises(ValueError): g.validate_guidance(bad, ['target-one'])

    def test_forged_redirect_partial_and_oversized(self):
        for kind in ['forged', 'partial', 'oversized', 'empty', 'duplicate']:
            def tamper(value):
                body = value['data']
                if kind == 'forged': body['results'][0]['url'] += '?redirect=evil'
                if kind == 'partial': body['statuses'] = []
                if kind == 'oversized': body['results'][0]['text'] = 'x' * (g.MAX_PAGE_BYTES + 1)
                if kind == 'empty': body['results'][0]['text'] = ''
                if kind == 'duplicate': body['results'].append(body['results'][0])
                return value
            packet = self.collect(transform=tamper)
            self.assertEqual(packet['coverage'][0]['status'], 'unavailable', kind)
            self.assertEqual(packet['sources'], [], kind)

    def test_unknown_owner_coverage_freshness_and_source_identity(self):
        packet = self.collect(selected('unmapped-owner'))
        self.assertEqual(packet['coverage'][0]['status'], 'unavailable')
        self.assertTrue(g.validate_guidance(packet, ['target-one']))
        packet = self.collect()
        for mutate in [lambda p: p['sources'][0].update(url='https://evil.example/docs'),
                       lambda p: p['sources'][0].update(publisher='spoof'),
                       lambda p: p['coverage'][0].update(source_ids=[]),
                       lambda p: p.update(expires_at=p['retrieved_at'])]:
            bad = copy.deepcopy(packet); mutate(bad)
            with self.assertRaises(ValueError): g.validate_guidance(bad, ['target-one'])
        with self.assertRaises(ValueError): g.validate_guidance(packet, ['another-target'])
        with self.assertRaises(ValueError): g.validate_guidance(packet, ['target-one'], at='2099-01-01T00:00:00+00:00')
        historical=copy.deepcopy(packet)
        historical['retrieved_at']='2020-01-01T00:00:00+00:00'
        historical['expires_at']='2020-01-01T01:00:00+00:00'
        for source in historical['sources']:source['retrieved_at']=historical['retrieved_at']
        self.assertTrue(g.public_guidance(historical)['sources'])
        with self.assertRaises(ValueError):g.validate_guidance(historical,['target-one'])

    def test_pointer_envelope(self):
        root = Path(tempfile.gettempdir()) / 'composio'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            path = Path(folder) / 'output.json'
            path.write_text(json.dumps(response(['https://code.claude.com/docs/en/hooks'])))
            envelope = {'successful': True, 'storedInFile': True, 'outputFilePath': str(path)}
            self.assertIn('results', g._unwrap(envelope))
            link = Path(folder) / 'link.json'; link.symlink_to(path)
            for candidate in [str(link), '/etc/passwd', str(path.parent / '..' / path.parent.name / path.name)]:
                with self.assertRaises(ValueError): g._unwrap(dict(envelope, outputFilePath=candidate))
            path.write_text('x' * (g.MAX_RESPONSE_BYTES + 1))
            with self.assertRaises(ValueError): g._unwrap(envelope)
        with self.assertRaises(ValueError): g._unwrap({'successful': False, 'data': {}})

    def test_late_contract_and_applicability_notice_are_captured(self):
        navigation = '\n\n'.join('# Hooks navigation '+str(i) for i in range(30))
        contract = 'A PreToolUse hook returns permissionDecision deny to block the action. Exit code 2 blocks execution and reports the error.'
        notice = 'The available tooling has changed since this article was written; Managed Agents now provides native orchestration.'
        text = navigation+'\n\n'+contract+'\n\n'+notice
        passages = g._passages(text, ['permissionDecision','exit code','hooks'])
        self.assertIn(contract, [p['text'] for p in passages])
        self.assertIn(notice, [p['text'] for p in passages])
        self.assertTrue(all(p['text'] in text for p in passages))

    def test_error_page_and_explicit_per_url_failure(self):
        def error_page(value):
            value['data']['results'][0]['title'] = '404 Page not found'
            return value
        self.assertEqual(self.collect(transform=error_page)['coverage'][0]['status'], 'unavailable')
        def failure(value):
            row = value['data']['statuses'][0]
            row.update(status='error', error={'tag':'CRAWL_NOT_FOUND'})
            value['data']['results'] = [r for r in value['data']['results'] if r['url'] != row['id']]
            return value
        packet = self.collect(transform=failure)
        self.assertEqual(packet['coverage'][0]['status'],'unavailable')
        self.assertTrue(g.validate_guidance(packet,['target-one']))

    def test_failed_document_preserves_independent_healthy_target(self):
        sources = selected('claude', 'hook') + selected('codex', 'hook')
        sources[1]['target']['id'] = 'target-two'
        failed_url = g.DOCS['codex-hooks']['url']
        def mixed(value):
            body = value['data']
            body['results'] = [row for row in body['results'] if row['url'] != failed_url]
            for row in body['statuses']:
                if row['id'] == failed_url:
                    row.update(status='error', error={'tag': 'CRAWL_NOT_FOUND'})
            return value
        packet = self.collect(sources, mixed)
        coverage = {row['target_id']: row for row in packet['coverage']}
        self.assertEqual('available', coverage['target-one']['status'])
        self.assertIn('claude-hooks', coverage['target-one']['source_ids'])
        self.assertEqual('unavailable', coverage['target-two']['status'])
        self.assertNotIn('codex-hooks', coverage['target-two']['source_ids'])
        self.assertTrue(g.validate_guidance(packet, ['target-one', 'target-two']))

    def test_cli_request_contains_only_fixed_public_fields(self):
        seen = {}
        def run(argv, **kwargs):
            seen['argv'] = argv
            seen['payload'] = json.loads(Path(argv[-1][1:]).read_text())
            class Result:
                returncode=0
                stdout=json.dumps(response(seen['payload']['urls']))
            return Result()
        with patch.object(g.subprocess,'run',run):
            packet=g.collect_guidance(selected())
        self.assertEqual(seen['argv'][:6], ['composio','execute','EXA_GET_CONTENTS_ACTION','--account','exa_mars-saite','-d'])
        self.assertEqual(set(seen['payload']),{'urls','text','maxAgeHours','livecrawlTimeout'})
        self.assertEqual(seen['payload']['maxAgeHours'],0)
        self.assertNotIn('PRIVATE',json.dumps(seen))
        self.assertEqual(packet['coverage'][0]['status'],'available')
        with self.assertRaises(ValueError): g._retrieve(['https://evil.example/private'])

    def test_remote_root_routing_and_unmapped_root(self):
        for root,expected in [('hermes','hermes'),('claude','claude-hooks'),('codex','codex-hooks'),('instructions','codex-instructions')]:
            packet=self.collect(selected('opaque-host','remote_files',adapter_id='remote_file_ssh',identity={'root':root}))
            self.assertIn(expected,packet['coverage'][0]['source_ids'])
            if root != 'hermes': self.assertNotIn('hermes',packet['coverage'][0]['source_ids'])
        packet=self.collect(selected('opaque-host','remote_files',adapter_id='remote_file_ssh',identity={'root':'openclaw'}))
        self.assertEqual(packet['coverage'][0]['status'],'unavailable')
        self.assertEqual(packet['sources'],[])

    def test_owner_profiles(self):
        for owner, category, extra in [
            ('native-instruction-builder','rule',{}), ('shared-skill-lifecycle','skill',{}),
            ('registered-agent-tools','executable',{}), ('claude','app_settings',{}),
            ('cursor','hook',{}), ('Codex native app-server','app_settings',{}),
            ('owned-plugin-source','plugin_metadata',{}), ('native-plugin-install','plugin_sync',{}),
            ('opaque-company','paperclip_agent',{'adapter_id':'provider_paperclip_agent'}),
            ('opaque-project','neon_project',{'adapter_id':'provider_neon_project'}),
            ('opaque-bank','hindsight_bank',{'adapter_id':'provider_hindsight_bank'}),
            ('opaque-dashboard','signoz_dashboard',{'adapter_id':'provider_signoz_dashboard'}),
            ('opaque-host','remote_files',{'adapter_id':'remote_file_orgo_host','identity':{'root':'hermes'}}),
            ('opaque-host','remote_files',{'adapter_id':'remote_file_ssh','identity':{'root':'hermes'}})]:
            packet = self.collect(selected(owner, category, **extra))
            self.assertEqual(packet['coverage'][0]['status'], 'available', (owner,category))
            self.assertTrue(g.validate_guidance(packet, ['target-one']))

if __name__ == '__main__': unittest.main()

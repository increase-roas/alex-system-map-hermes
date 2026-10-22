"""Native execution tests use authored fake hooks and disposable canaries only."""
import json
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from repair_hook_checks import NATIVE_AVAILABLE, run_receipt_checks, _run, _decision, _cases

FAKE = '''import json,sys
try:
    p=json.load(sys.stdin)
    c=p.get('tool_input',{}).get('command','')
    path=p.get('tool_input',{}).get('file_path','')
    deny=bool(path or any(x in c for x in (' > ', ' | python3', 'import human_receipts', 'cp ', 'rm ')))
except Exception:
    deny=True
if deny: print(json.dumps({'hookSpecificOutput':{'hookEventName':'PreToolUse','permissionDecision':'deny'}}))
'''

class NativeChecks(unittest.TestCase):
    def test_missing_native_is_unavailable(self):
        with patch('repair_hook_checks.NATIVE_AVAILABLE', False):
            self.assertEqual(run_receipt_checks(FAKE, FAKE)['status'], 'unavailable')

    @unittest.skipUnless(NATIVE_AVAILABLE, 'native macOS confinement unavailable')
    def test_fixed_cases_and_disabled_guard(self):
        result=run_receipt_checks(FAKE, FAKE)
        self.assertEqual(result['status'], 'passed', result)
        self.assertEqual(run_receipt_checks(FAKE, 'pass\n')['status'], 'failed')

    def test_contract(self):
        self.assertEqual(_decision(0,b''), 'allow')
        self.assertEqual(_decision(0,b'{"permission":"deny"}'), 'deny')
        for rc,raw in ((1,b''),(0,b'garbage'),(0,b'{}'),(0,b'{"permission":"allow"}')):
            self.assertEqual(_decision(rc,raw), 'invalid')

    @unittest.skipUnless(NATIVE_AVAILABLE, 'native macOS confinement unavailable')
    def test_malformed_and_timeout(self):
        self.assertEqual(_run('print("not json")', '{}')['status'], 'invalid')
        self.assertEqual(_run('while True: pass', '{}')['status'], 'timeout')
        self.assertEqual(_run('print("x" * 1000000)', '{}')['status'], 'output_limit')

    @unittest.skipUnless(NATIVE_AVAILABLE, 'native macOS confinement unavailable')
    def test_hostile_read_write_network_spawn_are_blocked(self):
        source='''import os,socket,sys
blocked=0
for operation in (
    lambda: open('/etc/passwd').read(),
    lambda: open('/private/tmp/receipt-native-hostile-escape','w').write('x'),
    lambda: socket.create_connection(('127.0.0.1',9),timeout=.1),
    lambda: os.fork(),
    lambda: os.execv('/usr/bin/true',['true']),
):
    try: operation()
    except (OSError,PermissionError): blocked+=1
sys.exit(0 if blocked==5 else 4)
'''
        self.assertEqual(_run(source, '{}'), {'decision':'allow','status':'ok'})

    @unittest.skipUnless(NATIVE_AVAILABLE, 'native macOS confinement unavailable')
    def test_regressions_require_completion_count_and_no_skips(self):
        suite = 'import unittest\nimport receipt_store_guard\nclass Checks(unittest.TestCase):\n    def test_run(self):\n        self.assertTrue(receipt_store_guard.reason({"tool_input":{"file_path":"/fixture/guard.py"}}))\n'
        regressions = {'test_receipt_store_guard_narrow.py': suite, 'approval_check.py': ''}
        self.assertEqual(_run(FAKE, '{}', regressions), {'decision':'allow','status':'ok'})
        for candidate in ('import sys;sys.exit(0)\n', 'import os;os._exit(0)\n',
                          'import os\nprint(\'{"completed":true,"tests_run":1,"failures":0,"errors":0,"skips":0}\',flush=True)\nos._exit(0)\n'):
            with self.subTest(candidate=candidate):
                self.assertNotEqual(_run(candidate, '{}', regressions), {'decision':'allow','status':'ok'})
        regressions['test_receipt_store_guard_narrow.py'] = suite.replace('    def test_run', '    @unittest.skip("skipped")\n    def test_run')
        self.assertNotEqual(_run(FAKE, '{}', regressions), {'decision':'allow','status':'ok'})

    @unittest.skipUnless(NATIVE_AVAILABLE, 'native macOS confinement unavailable')
    def test_real_coordinator_preview_tests_hook_and_never_applies_failed_candidate(self):
        from repair_contracts import RepairError
        from repair_local_adapters import LocalAdapter
        from repair_registry import RepairRegistry
        from universal_repairs import Coordinator
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary).resolve()
            source=home/'.agents/tools/approvals/receipt_store_guard.py'
            source.parent.mkdir(parents=True); source.write_text(FAKE)
            registry=RepairRegistry(); registry.register(LocalAdapter(home))
            seen=[]
            def proposer(intent,sources):
                seen.extend(sources)
                return {'proposals':[{'target_id':sources[0]['target']['id'],'proposal':{'candidate':'pass\n'}}]}
            service=Coordinator(home/'state',registry,proposer=proposer)
            target=next(t for t in service.discover()['targets'] if t['identity'].get('path')==str(source))
            plan=service.propose([target['id']],'Fix the false stop and preserve receipt protection.')
            self.assertEqual('passed',seen[0]['native_baseline']['status'])
            behavior=next(c for c in plan['operations'][0]['checks'] if c['kind']=='native_behavior')
            self.assertEqual('failed',behavior['status'])
            self.assertEqual(13,len(behavior['native_cases']))
            with self.assertRaises(RepairError): service.approve(plan['plan_id'],plan['digest'])
            self.assertEqual(FAKE,source.read_text())
            self.assertEqual([],list((home/'state/jobs').glob('*.json')))

if __name__ == '__main__': unittest.main()

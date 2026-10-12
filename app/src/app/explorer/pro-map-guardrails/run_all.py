#!/usr/bin/env python3
"""Run offline hook fixtures and retain a hash-bound receipt inside this folder."""
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parent
results = []
for name in ('asset_guard', 'read_gate', 'hermes_guard'):
    test = root / ('test_' + name + '.py')
    run = subprocess.run([sys.executable, '-B', str(test)], cwd=root,
                         text=True, capture_output=True, timeout=120)
    output = run.stdout + run.stderr
    match = re.search(r'Ran (\d+) tests?', output)
    skipped_match = re.search(r'skipped=(\d+)', output)
    skipped = int(skipped_match.group(1)) if skipped_match else 0
    item = {'skipped': skipped, 'script': name + '.py', 'test': test.name, 'exit_code': run.returncode,
            'tests': int(match.group(1)) if match else None,
            'script_sha256': hashlib.sha256((root / (name + '.py')).read_bytes()).hexdigest(),
            'test_sha256': hashlib.sha256(test.read_bytes()).hexdigest(),
            'output': output.strip()}
    results.append(item)
    print(name + ': ' + ('PASS' if run.returncode == 0 and match else 'FAIL') +
          ' (' + str(item['tests']) + ' tests)', flush=True)
    if run.returncode:
        print(output, flush=True)
passed = all(r['exit_code'] == 0 and r['tests'] for r in results)
receipt = {'checked_at': datetime.now(timezone.utc).isoformat(),
           'status': 'PASS' if passed else 'FAIL',
           'scope': 'Offline subprocess fixture tests, not installed/runtime hook proof',
           'tests': sum(r['tests'] or 0 for r in results),
           'skipped': sum(r['skipped'] for r in results),
           'passed': sum((r['tests'] or 0) - r['skipped'] for r in results) if passed else None,
           'results': results}
(root / 'test-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
raise SystemExit(0 if passed else 1)

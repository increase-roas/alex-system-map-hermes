#!/usr/bin/env python3
"""Pre-flight for the p4 package: compiles, plist renders and lints, arguments are right.

Run: python3 -B work/signoz-relay/validate_p4.py
"""
from __future__ import annotations

import os
import plistlib
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
HOME = Path.home()

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = '') -> None:
    results.append((name, bool(ok), detail))


# 1. every script compiles, on both interpreters the job might meet
for script in ('verify_durable.py', 'canary_through_relay.py', 'make_patch.py',
               'make_patch_codex_traced.py', 'test_relay_collector.py'):
    path = HERE / script
    if not path.exists():
        record(f'{script} exists', False, 'missing')
        continue
    # Compile to a throwaway file, not /dev/null: py_compile refuses a non-regular cfile.
    with tempfile.NamedTemporaryFile(suffix='.pyc', delete=False) as cache:
        cache_path = cache.name
    try:
        py_compile.compile(str(path), cfile=cache_path, doraise=True)
        record(f'{script} compiles here', True)
    except py_compile.PyCompileError as err:
        record(f'{script} compiles here', False, str(err)[:120])
    finally:
        try:
            os.unlink(cache_path)
        except OSError:
            pass

for interpreter in ('/usr/bin/python3', sys.executable):
    target = REPO / 'tools' / 'otel_collector.py'
    proc = subprocess.run([interpreter, '-B', str(target), '--self-test'],
                          capture_output=True, text=True, timeout=120)
    version = subprocess.run([interpreter, '-V'], capture_output=True, text=True).stdout.strip()
    record(f'collector self-test on {version}', proc.returncode == 0,
           proc.stdout.strip().splitlines()[-1] if proc.stdout else proc.stderr[:120])

# 2. the plist renders, lints, and says what it should
template = HERE / 'com.alex.signoz-collector.plist.template'
rendered = template.read_text().replace('<HOME>', str(HOME))
with tempfile.NamedTemporaryFile('w', suffix='.plist', delete=False) as handle:
    handle.write(rendered)
    temp_path = handle.name
lint = subprocess.run(['plutil', '-lint', temp_path], capture_output=True, text=True)
record('rendered plist lints', lint.returncode == 0, lint.stdout.strip() or lint.stderr.strip())

try:
    with open(temp_path, 'rb') as handle:
        plist = plistlib.load(handle)
except Exception as err:  # noqa: BLE001
    record('rendered plist parses', False, str(err)[:120])
    plist = {}
else:
    record('rendered plist parses', True)

args = plist.get('ProgramArguments', [])
record('label is com.alex.signoz-collector',
       plist.get('Label') == 'com.alex.signoz-collector', str(plist.get('Label')))
record('KeepAlive and RunAtLoad are both on',
       plist.get('KeepAlive') is True and plist.get('RunAtLoad') is True)
record('uses /usr/bin/python3, not a Homebrew path',
       args[:1] == ['/usr/bin/python3'], str(args[:1]))
record('points at the collector in this repo',
       str(REPO / 'tools' / 'otel_collector.py') in args)
record('port 4320', '4320' in args)
record('both upstreams for the side-by-side day',
       args.count('--upstream') == 2 and 'signoz' in args and 'langfuse' in args,
       f'upstream count={args.count("--upstream")}')
record('no <HOME> placeholder left unresolved', '<HOME>' not in rendered)
record('every path in the plist is absolute',
       all(not value.startswith('~') for value in args if isinstance(value, str)))
os.unlink(temp_path)

# 3. the collector the plist points at really exists and takes those flags
collector = REPO / 'tools' / 'otel_collector.py'
record('the collector file exists', collector.exists(), str(collector))
helptext = subprocess.run([sys.executable, '-B', str(collector), '--help'],
                          capture_output=True, text=True, timeout=60).stdout
for flag in ('--port', '--upstream', '--log', '--dry-run', '--self-test'):
    record(f'collector accepts {flag}', flag in helptext)

# 4. no key value anywhere in anything this package ships
SECRET_SHAPES = ('sk' '-lf-', 'pk' '-lf-', 'OP_SERVICE_ACCOUNT' '_TOKEN=')
leaks = []
for path in list(HERE.glob('*.md')) + list(HERE.glob('*.py')) + [template]:
    if path.name == Path(__file__).name:
        continue  # this file necessarily contains the shapes it searches for
    text = path.read_text(errors='replace')
    for shape in SECRET_SHAPES:
        index = text.find(shape)
        if index == -1:
            continue
        # A shape check in source ("if not public.startswith(...)") is not a leak.
        context = text[max(0, index - 80):index]
        if 'startswith' in context or 'SHAPES' in context:
            continue
        leaks.append(f'{path.name}:{shape}')
record('no key-shaped literal in the package', not leaks, '; '.join(leaks))

width = max(len(name) for name, _ok, _d in results)
for name, ok, detail in results:
    line = f'  {"pass" if ok else "FAIL"}  {name:{width}}'
    print(line if ok else line + f'   <- {detail}')
failed = [name for name, ok, _d in results if not ok]
print()
print(f'{len(results) - len(failed)}/{len(results)} checks passed')
if failed:
    print('FAILED: ' + '; '.join(failed))
sys.exit(1 if failed else 0)

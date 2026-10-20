#!/usr/bin/env python3
"""Build codex_traced.PATCHED.py: send through the local relay instead of direct.

One anchored edit. The wrapper already sets service.name itself at
`owned_resources = {"deployment.environment": environment, "service.name": service}`
with `service` defaulting to "codex", so nothing else is needed for naming.

Run: python3 -B work/signoz-relay/make_patch_codex_traced.py
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = Path.home() / '.agents/tools/connectors/codex_otel/codex_traced.py'
ORIGINAL = HERE / 'codex_traced.ORIGINAL.py'
PATCHED = HERE / 'codex_traced.PATCHED.py'
DIFF = HERE / 'codex_traced.patch'

EXPECTED_SHA256 = '8eb092cceab349fc5ac5908d9ca34c4f5d03d5dd83f0e6464936391e37098d68'

OLD = '''ENDPOINT = "https://us.cloud.langfuse.com/api/public/otel/v1/traces"'''

NEW = '''# The local collector is the one door for this Mac: it reads the SigNoz key, drops
# anything with no service.name, refuses the ChatGPT app's codex-worker, and rate
# guards each service, so no agent holds a vendor key and policy lives in one place.
# This wrapper already sets service.name (default "codex") through
# OTEL_RESOURCE_ATTRIBUTES below, so its spans arrive named.
# Port 4320 is the standalone collector (LaunchAgent com.alex.signoz-collector), NOT
# the old relay on 4319, which stays running with no clients until Alex cancels
# Langfuse. Changed 2026-10-20, play absence-alarms-20261020-p4-apply. To send direct
# again, restore the Langfuse URL on the line below.
ENDPOINT = "http://127.0.0.1:4320/v1/traces"
LANGFUSE_DIRECT_ENDPOINT = "https://us.cloud.langfuse.com/api/public/otel/v1/traces"'''


def main() -> int:
    if not ORIGINAL.exists():
        if not SOURCE.exists():
            print(f'missing {SOURCE}', file=sys.stderr)
            return 2
        ORIGINAL.write_text(SOURCE.read_text())
        print(f'  copied the original to {ORIGINAL.name}')
    source = ORIGINAL.read_text()
    actual = hashlib.sha256(source.encode()).hexdigest()
    if actual != EXPECTED_SHA256:
        print(f'ORIGINAL sha256 is {actual}, expected {EXPECTED_SHA256}', file=sys.stderr)
        return 2
    if source.count(OLD) != 1:
        print(f'FAILED anchor: {source.count(OLD)} matches, need exactly 1', file=sys.stderr)
        return 2
    out = source.replace(OLD, NEW, 1)
    PATCHED.write_text(out)
    print(f'  applied: ENDPOINT -> local relay')
    print(f'wrote {PATCHED.name}  sha256 {hashlib.sha256(out.encode()).hexdigest()}')
    proc = subprocess.run(['diff', '-u', str(ORIGINAL), str(PATCHED)],
                          capture_output=True, text=True)
    DIFF.write_text(proc.stdout)
    print(f'wrote {DIFF.name}')
    syntax = subprocess.run([sys.executable, '-m', 'py_compile', str(PATCHED)],
                            capture_output=True, text=True)
    if syntax.returncode:
        print(syntax.stderr, file=sys.stderr)
        return 1
    print('PATCHED compiles cleanly')

    # The relay drops on service.name, not on the Langfuse environment label. The
    # wrapper's CODEX_OTEL_ENVIRONMENT defaults to "codex-worker", which is the name
    # the relay REFUSES as a service. Prove the two never collide, or CLI traces would
    # be silently thrown away by the very filter meant to protect them.
    assert 'service.name": service' in out, 'the wrapper no longer sets service.name'
    assert '"codex"' in out, 'the service default changed'
    print('checked: service.name default is "codex", which the relay allows;')
    print('         "codex-worker" is only the environment label, which the relay ignores')
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Acceptance canary: one named and one unnamed span through the relay, then read SigNoz back.

Named span must arrive as ServiceName='codex'. Unnamed span must be absent, because the
relay drops it. Run this AFTER the relay has been patched and restarted.

Reads the SigNoz read-only key from 1Password at run time. Never prints a key.

Run: python3 -B work/signoz-relay/canary_through_relay.py [--port 4319]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import secrets
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request

RELAY = 'http://127.0.0.1:{port}/v1/traces'
SIGNOZ_BASE = 'https://pet-mammoth.us2.signoz.cloud'
READ_KEY_REF = 'op://Connectors/ergsvtc63iqob4g7itsr7lpr64/credential'
OP_BIN = os.environ.get('LANGFUSE_OP_BIN', '/opt/homebrew/bin/op')


def run(cmd, env=None):
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=45)
    if proc.returncode:
        raise SystemExit('a helper step failed; output withheld in case it carries a credential')
    return proc.stdout.strip()


def read_key() -> str:
    token = run(['/usr/bin/security', 'find-generic-password', '-a', 'connectors-sync',
                 '-s', 'op-service-account-connectors-sync', '-w'])
    env = {'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin',
           'HOME': os.environ.get('HOME', ''),
           'OP_SERVICE_ACCOUNT_TOKEN': token,
           'OP_BIOMETRIC_UNLOCK_ENABLED': 'false'}
    return run([OP_BIN, 'read', READ_KEY_REF], env)


# --- minimal OTLP writer -----------------------------------------------------

def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _k(f: int, w: int) -> bytes:
    return _varint((f << 3) | w)


def _d(f: int, p: bytes) -> bytes:
    return _k(f, 2) + _varint(len(p)) + p


def _kv(key: str, val: str) -> bytes:
    """KeyValue body. The extra wrapper that broke this on the first attempt is gone."""
    return _d(1, key.encode()) + _d(2, _d(1, val.encode()))


def payload(service: str | None, name: str, trace_id: bytes) -> bytes:
    now = time.time_ns()
    span = b''.join([
        _d(1, trace_id), _d(2, secrets.token_bytes(8)), _d(5, name.encode()),
        _k(6, 0) + _varint(1),
        _k(7, 1) + struct.pack('<Q', now),
        _k(8, 1) + struct.pack('<Q', now + 2_000_000),
        _d(9, _kv('check', 'p3 relay collector acceptance')),
    ])
    resource = b''
    if service:
        resource = _d(1, _kv('service.name', service)) + _d(1, _kv('host.name', 'macbook'))
    # ResourceSpans body = resource(field 1) + scope_spans(field 2); the whole thing
    # is then ONE field-1 wrapper (ExportTraceServiceRequest.resource_spans). An extra
    # wrapper here made every span parse as unnamed with a count of zero, and the
    # collector correctly refused it. Second time I have made this nesting mistake.
    return _d(1, _d(1, resource) + _d(2, _d(2, span)))


def post(url: str, body: bytes) -> int:
    req = urllib.request.Request(url, data=body, method='POST',
                                 headers={'Content-Type': 'application/x-protobuf'})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return resp.status
    except urllib.error.HTTPError as err:
        return err.code
    except urllib.error.URLError as err:
        print(f'  could not reach the relay: {err.reason}', file=sys.stderr)
        return 0


def signoz_trace(key: str, trace_id: str):
    req = urllib.request.Request(f'{SIGNOZ_BASE}/api/v1/traces/{trace_id}',
                                 headers={'SIGNOZ-API-KEY': key, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            rows = json.loads(resp.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None
    if not rows or not rows[0].get('events'):
        return None
    cols = rows[0]['columns']
    row = rows[0]['events'][0]
    return row[cols.index('ServiceName')]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=4319)
    parser.add_argument('--wait', type=int, default=45, help='seconds to allow for indexing')
    args = parser.parse_args()

    url = RELAY.format(port=args.port)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    named_id = secrets.token_bytes(16)
    unnamed_id = secrets.token_bytes(16)

    print(f'sending through the relay at {url}')
    named_status = post(url, payload('codex', f'p3-acceptance-named-{stamp}', named_id))
    print(f"  named   service.name='codex'  relay answered HTTP {named_status}  "
          f'trace={named_id.hex()}')
    unnamed_status = post(url, payload(None, f'p3-acceptance-unnamed-{stamp}', unnamed_id))
    print(f'  unnamed no service.name      relay answered HTTP {unnamed_status}  '
          f'trace={unnamed_id.hex()}')
    if named_status != 200:
        print('\nThe relay did not accept the named span. Stop and report.', file=sys.stderr)
        return 1

    print(f'\nwaiting {args.wait}s for SigNoz to index, then reading back with the read-only key')
    key = read_key()
    deadline = time.monotonic() + args.wait
    named_service = None
    while time.monotonic() < deadline:
        named_service = signoz_trace(key, named_id.hex())
        if named_service:
            break
        time.sleep(10)
    unnamed_service = signoz_trace(key, unnamed_id.hex())

    print()
    ok_named = named_service == 'codex'
    ok_unnamed = unnamed_service is None
    print(f'  {"PASS" if ok_named else "FAIL"}  named span in SigNoz: '
          f'{"PRESENT ServiceName=" + repr(named_service) if named_service else "ABSENT"}'
          f'   (expected PRESENT as codex)')
    print(f'  {"PASS" if ok_unnamed else "FAIL"}  unnamed span in SigNoz: '
          f'{"ABSENT" if unnamed_service is None else "PRESENT " + repr(unnamed_service)}'
          f'   (expected ABSENT, dropped by the relay)')
    print()
    print(f'  SigNoz UI: {SIGNOZ_BASE}/trace/{named_id.hex()}')
    print(f'  drop counter: tail -5 ~/.agents/runtime/codex-otlp-relay.jsonl')
    print('                expect a row with "dropped":{"unnamed":1}')
    return 0 if (ok_named and ok_unnamed) else 1


if __name__ == '__main__':
    sys.exit(main())

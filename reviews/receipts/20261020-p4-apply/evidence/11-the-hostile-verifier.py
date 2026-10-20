#!/usr/bin/env python3
"""Prove the collector LaunchAgent is real: loaded, answering, surviving, and delivering.

Run this AFTER the job is bootstrapped. It is the acceptance test for
absence-alarms-20261020-p4-collector-durable, and it is deliberately hostile: a
"loaded" line from launchctl is a claim, not proof, so every check here either reads
live state or makes something happen.

Checks, in order:
  1. launchctl reports the job with a real PID (not just present, running)
  2. the PID is the one actually holding port 4320
  3. GET /stats answers from a FRESH process, so nothing depends on this shell
  4. the 1Password read happened inside launchd, proven by a successful SigNoz send
     rather than by reading a key
  5. a named canary through the collector arrives in SigNoz as the right service
  6. an unnamed canary is dropped, with the drop visible in the collector's counts
  7. the job comes back by itself after being killed (KeepAlive really works)

Run: python3 -B work/signoz-relay/verify_durable.py
     python3 -B work/signoz-relay/verify_durable.py --skip-restart   (leave step 7 out)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import secrets
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request

LABEL = 'com.alex.signoz-collector'
PORT = 4320
SIGNOZ_BASE = 'https://pet-mammoth.us2.signoz.cloud'
READ_KEY_REF = 'op://Connectors/ergsvtc63iqob4g7itsr7lpr64/credential'
OP_BIN = '/opt/homebrew/bin/op'

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = '') -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f'  {"pass" if ok else "FAIL"}  {name}' + (f'   <- {detail}' if detail else ''))


def sh(cmd: list[str], timeout: int = 45) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stdout or '') + (proc.stderr or '')


def launchctl_pid() -> int | None:
    code, out = sh(['launchctl', 'print', f'gui/{os.getuid()}/{LABEL}'])
    if code:
        return None
    match = re.search(r'^\s*pid\s*=\s*(\d+)', out, re.M)
    return int(match.group(1)) if match else None


def port_holder() -> int | None:
    code, out = sh(['lsof', '-nP', f'-iTCP:{PORT}'])
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) > 1 and 'LISTEN' in line:
            try:
                return int(parts[1])
            except ValueError:
                continue
    return None


def stats_from_fresh_process() -> dict | None:
    """Deliberately a separate interpreter: proves nothing is held open by this shell."""
    code, out = sh([sys.executable, '-c',
                    f'import urllib.request,sys;'
                    f'sys.stdout.write(urllib.request.urlopen('
                    f'"http://127.0.0.1:{PORT}/stats", timeout=15).read().decode())'])
    if code:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


# --- OTLP ---------------------------------------------------------------------

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
    return _d(1, key.encode()) + _d(2, _d(1, val.encode()))


def payload(service, name: str, trace_id: bytes, host: str = 'macbook') -> bytes:
    now = time.time_ns()
    span = b''.join([
        _d(1, trace_id), _d(2, secrets.token_bytes(8)), _d(5, name.encode()),
        _k(6, 0) + _varint(1),
        _k(7, 1) + struct.pack('<Q', now),
        _k(8, 1) + struct.pack('<Q', now + 2_000_000),
        _d(9, _kv('check', 'p4 durability acceptance')),
    ])
    resource = b''
    if service:
        resource = _d(1, _kv('service.name', service)) + _d(1, _kv('host.name', host))
    # ResourceSpans body = resource(field 1) + scope_spans(field 2); the whole thing
    # is then ONE field-1 wrapper (ExportTraceServiceRequest.resource_spans). An extra
    # wrapper here made every span parse as unnamed with a count of zero, and the
    # collector correctly refused it. Second time I have made this nesting mistake.
    return _d(1, _d(1, resource) + _d(2, _d(2, span)))


def post(body: bytes) -> int:
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/traces', data=body,
                                 method='POST',
                                 headers={'Content-Type': 'application/x-protobuf'})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return resp.status
    except urllib.error.HTTPError as err:
        return err.code
    except urllib.error.URLError:
        return 0


def read_key() -> str:
    code, token = sh(['/usr/bin/security', 'find-generic-password', '-a', 'connectors-sync',
                      '-s', 'op-service-account-connectors-sync', '-w'])
    if code:
        raise SystemExit('could not read the service account token')
    # Through op_items.robot_env, not the real HOME. Under the real HOME op stalls for
    # minutes before any network step and makes macOS prompt for app data access; this
    # script hit that itself after the collector had already been fixed for it.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'op_items', os.path.expanduser('~/.agents/tools/connectors/op_items.py'))
    op_items = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(op_items)
    with op_items.robot_env(token.strip()) as env:
        proc = subprocess.run([OP_BIN, 'read', READ_KEY_REF], capture_output=True, text=True,
                              env=env, stdin=subprocess.DEVNULL, timeout=15)
    if proc.returncode:
        raise SystemExit('could not read the SigNoz read key')
    return proc.stdout.strip()


def signoz_service(key: str, trace_id: str):
    req = urllib.request.Request(f'{SIGNOZ_BASE}/api/v1/traces/{trace_id}',
                                 headers={'SIGNOZ-API-KEY': key, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            rows = json.loads(resp.read())
    except Exception:
        return None
    if not rows or not rows[0].get('events'):
        return None
    cols = rows[0]['columns']
    return rows[0]['events'][0][cols.index('ServiceName')]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-restart', action='store_true')
    parser.add_argument('--wait', type=int, default=60)
    args = parser.parse_args()

    print(f'verifying {LABEL} at {dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ}\n')

    pid = launchctl_pid()
    check('launchctl reports the job with a live PID', pid is not None, f'pid={pid}')
    holder = port_holder()
    check(f'that same PID holds port {PORT}', pid is not None and holder == pid,
          f'launchctl pid={pid}, port holder={holder}')

    stats = stats_from_fresh_process()
    check('/stats answers from a separate process', stats is not None,
          'nothing answered' if stats is None else f'uptime {stats.get("uptime_hours")}h')
    if stats is None:
        print('\nThe collector is not answering. Everything below would be meaningless.')
        return 1
    before_kept = sum(stats.get('kept_spans', {}).values())

    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    named_id = secrets.token_bytes(16)
    unnamed_id = secrets.token_bytes(16)
    named_status = post(payload('alex-system-map', f'p4-durable-named-{stamp}', named_id))
    unnamed_status = post(payload(None, f'p4-durable-unnamed-{stamp}', unnamed_id))
    check('collector accepts a named span', named_status == 200, f'HTTP {named_status}')
    check('collector accepts and swallows an unnamed span', unnamed_status == 200,
          f'HTTP {unnamed_status}')
    time.sleep(2)

    after = stats_from_fresh_process() or {}
    kept_now = sum(after.get('kept_spans', {}).values())
    dropped_now = after.get('dropped_spans', {})
    check('the kept counter moved', kept_now > before_kept, f'{before_kept} -> {kept_now}')
    check('the drop counter shows the unnamed span',
          dropped_now.get('(unnamed)', 0) >= 1, f'dropped={dropped_now}')
    upstream = after.get('upstream_responses', {})
    check('SigNoz accepted it, so the key WAS read inside launchd',
          any(k.startswith('signoz:200') for k in upstream), f'upstream={upstream}')

    print(f'\n  waiting up to {args.wait}s for SigNoz to index')
    key = read_key()
    deadline = time.monotonic() + args.wait
    service = None
    while time.monotonic() < deadline:
        service = signoz_service(key, named_id.hex())
        if service:
            break
        time.sleep(10)
    check("named canary in SigNoz as 'alex-system-map'", service == 'alex-system-map',
          f'got {service!r}')
    check('unnamed canary absent from SigNoz',
          signoz_service(key, unnamed_id.hex()) is None)
    print(f'    trace: {SIGNOZ_BASE}/trace/{named_id.hex()}')

    if not args.skip_restart:
        print('\n  killing the process to prove KeepAlive brings it back')
        old = launchctl_pid()
        if old:
            sh(['kill', '-9', str(old)])
        new = None
        for _ in range(12):
            time.sleep(5)
            new = launchctl_pid()
            if new and new != old:
                break
        check('KeepAlive restarted it with a new PID', bool(new) and new != old,
              f'{old} -> {new}')
        check('/stats answers again after the restart',
              stats_from_fresh_process() is not None)

    failed = [n for n, ok, _d in CHECKS if not ok]
    print(f'\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed')
    if failed:
        print('FAILED: ' + '; '.join(failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())

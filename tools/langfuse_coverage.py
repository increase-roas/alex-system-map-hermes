#!/usr/bin/env python3
"""Who is reporting into Langfuse, and when did each one last say anything.

Read-only against Langfuse Cloud US. Credentials are read at run time from
1Password through the same path the dashboard uses
(app/src/lib/server/langfuse.ts): the op service account token lives in the
login Keychain under account "connectors-sync", service
"op-service-account-connectors-sync". No key, token or header value is ever
printed, written or logged by this file.

Two modes:

  python3 -B tools/langfuse_coverage.py
      Prints one line per known sender: its Langfuse environment, how many
      observations it sent in the window, and when it was last heard from.
      This is the measurement a silence alarm would read.

  python3 -B tools/langfuse_coverage.py --canary
      Sends one span of its own to environment "system-map-canary", then reads
      it back by trace id. This proves the whole path end to end: credentials,
      network, ingestion and query. A config file that looks right is not
      evidence; this is.

Writes nothing outside app/.data/ (and only with --save).
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import secrets
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Allowlist. The only host this file may reach, named here as tools/** requires.
# It is the same host app/src/lib/server/langfuse.ts already calls for the
# Tracing tab, and the same one ~/.claude/settings.json already exports to. It
# is a new outbound host for tools/, so it is called out for Alex in
# docs/trace-coverage-20261019.md.
ALLOWED_HOSTS = ('us.cloud.langfuse.com',)
HOST = 'https://us.cloud.langfuse.com'
OTLP_PATH = '/api/public/otel/v1/traces'
METRICS_PATH = '/api/public/v2/metrics'
OBSERVATIONS_PATH = '/api/public/v2/observations'

# 1Password locations. Item ids and field labels copied from
# app/src/lib/server/langfuse.ts so both readers stay in step.
VAULT = 'r6z62bjyy3c5ipilbgs4lyakwi'
PROJECTS = {
    'agents': {'item': 'xvpwk4vkwbmogmld2hxcq4pply', 'public': 'public_key', 'secret': 'secret_key',
               'project_id': 'cmv733aoq01e7ad0mfeqexnrx', 'label': 'Agents'},
    'langflow': {'item': 'rxoo6lpuxbca67oj4yofie45sm', 'public': 'public key', 'secret': 'credential',
                 'project_id': 'cmv7mth3h01tjad0j3q7b0okl', 'label': 'Langflow'},
}
OP_BIN = os.environ.get('LANGFUSE_OP_BIN', '/opt/homebrew/bin/op')
TIMEOUT = 45
CANARY_ENV = 'system-map-canary'

# The things that actually run, and the Langfuse environment each one reports
# into. "env: None" means nothing sends for it today. Sources for each claim
# are in docs/trace-coverage-20261019.md.
SENDERS = [
    ('Claude Code', 'app', 'default'),
    ('Codex app', 'app', 'codex-worker'),
    ('Claude desktop', 'app', None),
    ('Cursor', 'app', None),
    ('ChatGPT', 'app', None),
    ('Manus', 'app', None),
    ('Javar', 'agent', 'javar'),
    ('JAVAR-LAB', 'agent', 'javar-lab'),
    ('Javante', 'agent', None),
    ('Setter', 'agent', None),
    ('Hunter', 'agent', None),
    ('CSM', 'agent', None),
    ('Finance', 'agent', None),
    ('Director', 'role', None),
    ('Conductor', 'role', None),
    ('Reviewer', 'role', None),
]


class Blocked(Exception):
    """A step could not run. The message never carries credential text."""


def _run(cmd: list[str], env: dict | None = None) -> str:
    """Run a command, returning stdout. stderr is dropped: it could hold a key."""
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=TIMEOUT)
    if proc.returncode:
        raise Blocked(f'{Path(cmd[0]).name} failed (exit {proc.returncode}); output withheld')
    return proc.stdout.strip()


def auth_header(project: str) -> str:
    """Basic auth value for one Langfuse project. Never print the return value."""
    cfg = PROJECTS[project]
    env_public = os.environ.get(f'LANGFUSE_{project.upper()}_PUBLIC_KEY')
    env_secret = os.environ.get(f'LANGFUSE_{project.upper()}_SECRET_KEY')
    if env_public and env_secret:
        pair = f'{env_public}:{env_secret}'
    else:
        token = _run(['/usr/bin/security', 'find-generic-password', '-a', 'connectors-sync',
                      '-s', 'op-service-account-connectors-sync', '-w'])
        op_env = {
            'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin',
            'HOME': os.environ.get('HOME', ''),
            'OP_SERVICE_ACCOUNT_TOKEN': token,
            'OP_BIOMETRIC_UNLOCK_ENABLED': 'false',
        }
        public = _run([OP_BIN, 'read', f"op://{VAULT}/{cfg['item']}/{cfg['public']}"], op_env)
        secret = _run([OP_BIN, 'read', f"op://{VAULT}/{cfg['item']}/{cfg['secret']}"], op_env)
        if not public.startswith('pk-lf-') or not secret.startswith('sk-lf-'):
            raise Blocked('the Langfuse keys in 1Password do not have the expected shape')
        pair = f'{public}:{secret}'
    return 'Basic ' + base64.b64encode(pair.encode()).decode()


def _request(auth: str, path: str, body: bytes | None = None, content_type: str | None = None) -> dict:
    headers = {'Authorization': auth, 'Accept': 'application/json'}
    if content_type:
        headers['Content-Type'] = content_type
    url = HOST + path
    if urllib.parse.urlsplit(url).hostname not in ALLOWED_HOSTS:
        raise Blocked('refused: host is not in ALLOWED_HOSTS')
    req = urllib.request.Request(url, data=body, headers=headers,
                                 method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            if not raw:
                return {'status': resp.status}
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {'status': resp.status}
    except urllib.error.HTTPError as err:
        # The response body is Langfuse's, not ours, and holds no credential.
        detail = err.read()[:200].decode('utf8', 'replace')
        raise Blocked(f'Langfuse answered HTTP {err.code}: {detail}') from None
    except urllib.error.URLError as err:
        raise Blocked(f'could not reach {HOST}: {err.reason}') from None


def _iso(moment: dt.datetime) -> str:
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ')


def last_seen(auth: str, environment: str, days: int) -> dict:
    """Observation count and the newest day with data, for one environment."""
    now = dt.datetime.now(dt.timezone.utc)
    query = {
        'view': 'observations',
        'dimensions': [],
        'metrics': [{'measure': 'count', 'aggregation': 'count'},
                    {'measure': 'totalCost', 'aggregation': 'sum'}],
        'filters': [{'column': 'environment', 'operator': '=', 'value': environment, 'type': 'string'}],
        'timeDimension': {'granularity': 'day'},
        'fromTimestamp': _iso(now - dt.timedelta(days=days)),
        'toTimestamp': _iso(now),
    }
    payload = _request(auth, f'{METRICS_PATH}?query=' + urllib.parse.quote(json.dumps(query)))
    rows = [r for r in payload.get('data', []) if (r.get('count_count') or 0) > 0]
    total = sum(r.get('count_count') or 0 for r in rows)
    cost = sum(r.get('sum_totalCost') or 0 for r in rows)
    newest = max((str(r.get('time_dimension') or '') for r in rows), default='')
    return {'observations': total, 'cost': round(cost, 6), 'days_active': len(rows), 'last_day': newest}


# --- canary: prove a trace really lands ------------------------------------

def _otlp_span(trace_id: bytes, span_id: bytes, name: str, environment: str) -> bytes:
    """One minimal OTLP/protobuf ExportTraceServiceRequest, hand-encoded.

    Hand-encoded on purpose: this repo has no OpenTelemetry dependency and a
    proof tool should not need one. Field numbers come from the OTLP v1 proto
    (trace.proto and common.proto).
    """
    def key(field: int, wire: int) -> bytes:
        return _varint((field << 3) | wire)

    def _varint(value: int) -> bytes:
        out = bytearray()
        while True:
            byte = value & 0x7F
            value >>= 7
            out.append(byte | (0x80 if value else 0))
            if not value:
                return bytes(out)

    def delimited(field: int, payload: bytes) -> bytes:
        return key(field, 2) + _varint(len(payload)) + payload

    def str_kv(k: str, v: str) -> bytes:
        any_value = delimited(1, v.encode())          # AnyValue.string_value
        return delimited(1, k.encode()) + delimited(2, any_value)  # KeyValue

    now_ns = time.time_ns()
    span = b''.join([
        delimited(1, trace_id),                       # trace_id
        delimited(2, span_id),                        # span_id
        delimited(5, name.encode()),                  # name
        key(6, 0) + _varint(1),                       # kind = INTERNAL
        key(7, 1) + struct.pack('<Q', now_ns),        # start_time_unix_nano
        key(8, 1) + struct.pack('<Q', now_ns + 1_000_000),  # end_time_unix_nano
        delimited(9, str_kv('langfuse.environment', environment)),
        delimited(9, str_kv('check', 'alex-system-map trace coverage canary')),
    ])
    scope_spans = delimited(2, span)
    resource = delimited(1, str_kv('service.name', 'alex-system-map'))
    resource_spans = delimited(1, resource) + delimited(2, scope_spans)
    return delimited(1, resource_spans)               # ExportTraceServiceRequest.resource_spans


def canary(auth: str, environment: str = CANARY_ENV, wait_s: int = 150) -> dict:
    """Send one span, then read it back by trace id. Returns the proof."""
    trace_id = secrets.token_bytes(16)
    span_id = secrets.token_bytes(8)
    hex_trace = trace_id.hex()
    name = f'system-map-canary-{dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")}'
    body = _otlp_span(trace_id, span_id, name, environment)

    sent_at = dt.datetime.now(dt.timezone.utc)
    _request(auth, OTLP_PATH, body=body, content_type='application/x-protobuf')
    print(f'  sent span {name}')
    print(f'  trace id  {hex_trace}')
    print(f'  trace url {HOST}/project/{PROJECTS["agents"]["project_id"]}/traces/{hex_trace}')

    # Langfuse ingests asynchronously, so poll instead of assuming.
    deadline = time.monotonic() + wait_s
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        found = _request(auth, f'{OBSERVATIONS_PATH}?limit=50&traceId={hex_trace}')
        rows = found.get('data', [])
        if rows:
            row = rows[0]
            return {'found': True, 'trace_id': hex_trace, 'name': row.get('name'),
                    'environment': row.get('environment'), 'start_time': row.get('startTime'),
                    'attempts': attempt,
                    'seconds_to_appear': round((dt.datetime.now(dt.timezone.utc) - sent_at).total_seconds(), 1),
                    'url': f'{HOST}/project/{PROJECTS["agents"]["project_id"]}/traces/{hex_trace}'}
        time.sleep(10)
    return {'found': False, 'trace_id': hex_trace, 'waited_seconds': wait_s,
            'url': f'{HOST}/project/{PROJECTS["agents"]["project_id"]}/traces/{hex_trace}'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--days', type=int, default=7, help='window to look back over (default 7)')
    parser.add_argument('--canary', action='store_true', help='send one span and read it back')
    parser.add_argument('--project', default='agents', choices=sorted(PROJECTS))
    parser.add_argument('--save', metavar='PATH',
                        help='also write the result as JSON (must be inside app/.data/)')
    args = parser.parse_args(argv)

    try:
        auth = auth_header(args.project)
    except Blocked as err:
        print(f'BLOCKED: {err}', file=sys.stderr)
        return 2

    result: dict = {'checked_at': _iso(dt.datetime.now(dt.timezone.utc)),
                    'project': args.project, 'window_days': args.days}

    if args.canary:
        print(f'Canary into environment "{CANARY_ENV}":')
        try:
            proof = canary(auth)
        except Blocked as err:
            print(f'BLOCKED: {err}', file=sys.stderr)
            return 2
        result['canary'] = proof
        if proof['found']:
            print(f'  READ BACK after {proof["seconds_to_appear"]}s '
                  f'(environment {proof["environment"]}, name {proof["name"]})')
            print('  PROVEN: a span sent from this repo arrived in Langfuse and was queried back.')
        else:
            print(f'  NOT FOUND after {proof["waited_seconds"]}s. The send was accepted but the '
                  'read did not return it yet; check the url above by hand.')
        print()

    print(f'Reporting into Langfuse, project "{PROJECTS[args.project]["label"]}", '
          f'last {args.days} days (checked {result["checked_at"]}):')
    print()
    print(f'  {"what":16} {"kind":7} {"environment":26} {"observations":>12}  {"cost":>9}  last day')
    rows = []
    reporting = 0
    for name, kind, environment in SENDERS:
        if not environment:
            rows.append({'name': name, 'kind': kind, 'environment': None, 'reporting': False})
            print(f'  {name:16} {kind:7} {"(nothing sends)":26} {"-":>12}  {"-":>9}  never')
            continue
        try:
            seen = last_seen(auth, environment, args.days)
        except Blocked as err:
            print(f'  {name:16} {kind:7} {environment:26} BLOCKED: {err}')
            rows.append({'name': name, 'kind': kind, 'environment': environment, 'blocked': str(err)})
            continue
        live = seen['observations'] > 0
        reporting += 1 if live else 0
        cost = f'{seen["cost"]:.4f}' if seen['cost'] else 'none'
        print(f'  {name:16} {kind:7} {environment:26} {seen["observations"]:>12}  {cost:>9}  '
              f'{seen["last_day"] or "never"}')
        rows.append({'name': name, 'kind': kind, 'environment': environment, 'reporting': live, **seen})

    result['senders'] = rows
    result['reporting'] = reporting
    result['total'] = len(SENDERS)
    print()
    print(f'  {reporting} of {len(SENDERS)} running things reported in the last {args.days} days.')
    quiet = [r['name'] for r in rows if r.get('environment') and not r.get('reporting')]
    if quiet:
        print(f'  Has an environment but said nothing in the window: {", ".join(quiet)}')

    if args.save:
        target = Path(args.save).resolve()
        allowed = (Path(__file__).resolve().parent.parent / 'app' / '.data').resolve()
        if allowed not in target.parents:
            print(f'BLOCKED: --save must point inside {allowed}', file=sys.stderr)
            return 2
        target.write_text(json.dumps(result, indent=2) + '\n')
        print(f'  saved {target}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

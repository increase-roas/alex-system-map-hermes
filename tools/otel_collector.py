#!/usr/bin/env python3
"""A loopback OTLP collector that names, caps and fans out agent traces.

WHY THIS EXISTS AND NOT A PATCH TO THE EXISTING RELAY
-----------------------------------------------------
`~/.agents/tools/connectors/codex_otel/otlp_relay.py` is a security-reviewed
component whose documented contract is that it forwards OTLP bytes unchanged and
"does not inspect or change span bodies". Dropping spans by name and rate-limiting
per service both require parsing the payload, which is exactly the property that
file was reviewed for not having. It is also under ~/.agents, which this project
may not edit.

So this is a separate collector, in this repo, where it can be read, tested and
reverted. The existing relay keeps its contract and, since the ChatGPT app's Codex
tracing was switched off on 2026-10-19, currently has no clients at all.

WHAT IT DOES
------------
1. Accepts OTLP/HTTP protobuf on POST /v1/traces, loopback only.
2. Drops any ResourceSpans whose resource has no non-empty `service.name`.
   SigNoz does NOT do this for you: a span with no resource attributes at all was
   accepted with HTTP 200 on 2026-10-20 (trace 271bb7f1cea12b2b365fc23aee6a034c).
3. Refuses service names on a block list outright.
4. Rate-guards EVERY service with its own token bucket, so one sender cannot flood
   the account. This is the lesson from 2026-10-19: the Langfuse flood came from
   spans that WERE labelled (Langfuse environment "codex-worker", ~0.9M-1.4M
   observations an hour), so a name-based drop alone would not have stopped it.
   Naming and capping are two different jobs and both are needed.
5. Fans out what survives to one or more upstreams, each with its own auth header
   read from 1Password at run time. Never logs a key, a span body or a header.
6. Counts kept, unnamed, blocked and throttled spans per service, so the per-service
   hourly rate can be reported without reading anything back from a vendor.

NOT DURABLE BY ITSELF. It runs in the foreground. Keeping it alive across reboots
needs a LaunchAgent, which this project cannot write; see the handover note in
docs/ for the one-line change and who has to make it.

Run:
    python3 -B tools/otel_collector.py --port 4320 --upstream signoz
    python3 -B tools/otel_collector.py --dry-run --port 4320    # accept, count, forward nothing
    python3 -B tools/otel_collector.py --self-test              # no network, no listener
"""
from __future__ import annotations

import argparse
import collections
import ipaddress
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Allowlist. The only hosts this file may reach, named here as tools/** requires.
ALLOWED_HOSTS = ('ingest.us2.signoz.cloud', 'us.cloud.langfuse.com')

UPSTREAMS = {
    # name: (url, header name, 1Password vault, item id, field)
    'signoz': ('https://ingest.us2.signoz.cloud/v1/traces', 'signoz-ingestion-key',
               'Connectors', 'hfy4llw7gassge2w5xuz64kgyu', 'credential'),
    # Langfuse uses Basic auth built from a public/secret pair, handled separately.
    'langfuse': ('https://us.cloud.langfuse.com/api/public/otel/v1/traces', 'Authorization',
                 'r6z62bjyy3c5ipilbgs4lyakwi', 'xvpwk4vkwbmogmld2hxcq4pply', None),
}

# Names that are allowed through at all. Anything else is counted and dropped, so a
# typo in an agent's config shows up as a number instead of silently becoming "other".
KNOWN_SERVICES = (
    'claude-code', 'codex', 'cursor', 'javar', 'javante', 'auditor',
    'task-codex', 'task-claude', 'paperclip-worker', 'paperclip-reviewer',
    'dynamite-chatbot', 'alex-system-map',
)

# Never forwarded. The ChatGPT app's built-in Codex sent roughly 4.7M events a week
# into Langfuse with no per-run session id; Alex switched it off on 2026-10-19 and the
# Director's instruction is that it is not to be forwarded here either unless it is
# sampled hard and Alex agrees.
BLOCKED_SERVICES = ('codex-worker',)

# Spans per minute per service, and the burst each may hold. Set from the measured
# 7-day behaviour on 2026-10-19: Claude Code ran about 110,000 units a week, which is
# roughly 11 spans a minute, so 600 leaves two orders of magnitude of headroom while
# still stopping a runaway. A service that legitimately needs more should be raised
# here deliberately, with the reason, rather than the cap being removed.
DEFAULT_RATE_PER_MIN = 600
RATE_OVERRIDES: dict[str, int] = {}

MAX_BODY = 16 * 1024 * 1024
IO_TIMEOUT = 30
# `op read` needs considerably longer than a local helper script, especially on a
# cold start under launchd where the service account has to authenticate before the
# first read. Measured 2026-10-20: at 15 seconds the job died twice with
# subprocess.TimeoutExpired and only survived its third launch, while KeepAlive kept
# reporting "state = running" the whole time. That is the exact silent-success shape
# this project exists to remove, so the timeout is generous and the retry is explicit.
HELPER_TIMEOUT = 90
KEY_RETRIES = 3
KEY_RETRY_WAIT = 5
KEY_TTL = 3600


class Blocked(Exception):
    """A step could not run. The message never carries credential text."""


# --------------------------------------------------------------------------- protobuf

def read_varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = 0
    value = 0
    while True:
        if i >= len(buf):
            raise ValueError('truncated varint')
        byte = buf[i]
        i += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, i
        shift += 7
        if shift > 63:
            raise ValueError('varint too long')


def iter_fields(buf: bytes):
    """Yield (field_number, wire_type, payload_bytes_or_int, start, end) over one message."""
    i = 0
    while i < len(buf):
        start = i
        key, i = read_varint(buf, i)
        field, wire = key >> 3, key & 0x7
        if wire == 0:
            val, i = read_varint(buf, i)
            yield field, wire, val, start, i
        elif wire == 1:
            yield field, wire, buf[i:i + 8], start, i + 8
            i += 8
        elif wire == 2:
            length, i = read_varint(buf, i)
            if i + length > len(buf):
                raise ValueError('truncated length-delimited field')
            yield field, wire, buf[i:i + length], start, i + length
            i += length
        elif wire == 5:
            yield field, wire, buf[i:i + 4], start, i + 4
            i += 4
        else:
            raise ValueError(f'unsupported wire type {wire}')


def varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def delimited(field: int, payload: bytes) -> bytes:
    return varint((field << 3) | 2) + varint(len(payload)) + payload


def service_name_of(resource: bytes) -> str:
    """Read service.name out of a Resource message. '' when absent or empty.

    Resource.attributes = field 1, repeated KeyValue.
    KeyValue.key = field 1 (string), KeyValue.value = field 2 (AnyValue).
    AnyValue.string_value = field 1.
    """
    for field, wire, payload, _s, _e in iter_fields(resource):
        if field != 1 or wire != 2:
            continue
        key = value = None
        for kf, kw, kp, _ks, _ke in iter_fields(payload):
            if kf == 1 and kw == 2:
                key = kp
            elif kf == 2 and kw == 2:
                for af, aw, ap, _as, _ae in iter_fields(kp):
                    if af == 1 and aw == 2:
                        value = ap
                        break
        if key == b'service.name' and value:
            try:
                return value.decode('utf8').strip()
            except UnicodeDecodeError:
                return ''
    return ''


def count_spans(resource_spans: bytes) -> int:
    """ResourceSpans.scope_spans = field 2; ScopeSpans.spans = field 2."""
    total = 0
    for field, wire, payload, _s, _e in iter_fields(resource_spans):
        if field == 2 and wire == 2:
            for sf, sw, _sp, _ss, _se in iter_fields(payload):
                if sf == 2 and sw == 2:
                    total += 1
    return total


# --------------------------------------------------------------------------- limiter

class RateGuard:
    """One token bucket per service. Refills continuously; never blocks a thread."""

    def __init__(self, per_min: int, overrides: dict[str, int], clock=time.monotonic):
        self.per_min = per_min
        self.overrides = overrides
        self.clock = clock
        self.lock = threading.Lock()
        self.state: dict[str, tuple[float, float]] = {}

    def limit_for(self, service: str) -> int:
        return self.overrides.get(service, self.per_min)

    def allow(self, service: str, spans: int) -> bool:
        limit = self.limit_for(service)
        if limit <= 0:
            return False
        now = self.clock()
        with self.lock:
            tokens, last = self.state.get(service, (float(limit), now))
            tokens = min(float(limit), tokens + (now - last) * (limit / 60.0))
            if tokens >= spans:
                self.state[service] = (tokens - spans, now)
                return True
            self.state[service] = (tokens, now)
            return False


# --------------------------------------------------------------------------- filtering

class Decision:
    __slots__ = ('body', 'kept', 'dropped')

    def __init__(self, body: bytes, kept: dict, dropped: dict):
        self.body = body
        self.kept = kept
        self.dropped = dropped


def filter_payload(body: bytes, guard: RateGuard, known=KNOWN_SERVICES,
                   blocked=BLOCKED_SERVICES) -> Decision:
    """Keep only named, allowed, in-budget ResourceSpans. Re-emit valid OTLP."""
    kept_counts: dict[str, int] = collections.Counter()
    dropped: dict[str, int] = collections.Counter()
    out = bytearray()
    for field, wire, payload, _s, _e in iter_fields(body):
        if field != 1 or wire != 2:
            continue  # ExportTraceServiceRequest.resource_spans only
        resource = b''
        for rf, rw, rp, _rs, _re in iter_fields(payload):
            if rf == 1 and rw == 2:
                resource = rp
                break
        service = service_name_of(resource)
        spans = count_spans(payload)
        if not service:
            dropped['(unnamed)'] += spans
            continue
        if service in blocked:
            dropped[f'blocked:{service}'] += spans
            continue
        if known and service not in known:
            dropped[f'unknown:{service}'] += spans
            continue
        if not guard.allow(service, spans):
            dropped[f'throttled:{service}'] += spans
            continue
        kept_counts[service] += spans
        out += delimited(1, payload)
    return Decision(bytes(out), dict(kept_counts), dict(dropped))


# --------------------------------------------------------------------------- upstreams

def _run(cmd: list[str], env: dict | None = None) -> str:
    """Run a command, returning stdout. stderr is dropped: it could hold a key.

    Every subprocess failure, a timeout included, becomes a Blocked carrying no
    payload. Before this, a TimeoutExpired escaped as an unhandled traceback: it
    killed the process and printed the command line into the job log, and KeepAlive
    then relaunched it while still reporting "state = running".
    """
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                              timeout=HELPER_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Blocked(f'{Path(cmd[0]).name} did not answer within {HELPER_TIMEOUT}s') from None
    except subprocess.SubprocessError:
        raise Blocked(f'{Path(cmd[0]).name} could not be run') from None
    if proc.returncode:
        raise Blocked(f'{Path(cmd[0]).name} failed (exit {proc.returncode}); output withheld')
    return proc.stdout.strip()


def _op_env() -> dict:
    token = _run(['/usr/bin/security', 'find-generic-password', '-a', 'connectors-sync',
                  '-s', 'op-service-account-connectors-sync', '-w'])
    return {'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin',
            'HOME': os.environ.get('HOME', ''),
            'OP_SERVICE_ACCOUNT_TOKEN': token,
            'OP_BIOMETRIC_UNLOCK_ENABLED': 'false'}


def auth_for(name: str) -> str:
    """Header VALUE for one upstream. Never print or log the return value."""
    url, header, vault, item, field = UPSTREAMS[name]
    env = _op_env()
    op = os.environ.get('LANGFUSE_OP_BIN', '/opt/homebrew/bin/op')
    if name == 'langfuse':
        import base64
        public = _run([op, 'read', f'op://{vault}/{item}/public_key'], env)
        secret = _run([op, 'read', f'op://{vault}/{item}/secret_key'], env)
        if not public.startswith('pk-lf-') or not secret.startswith('sk-lf-'):
            raise Blocked('the Langfuse keys do not have the expected shape')
        return 'Basic ' + base64.b64encode(f'{public}:{secret}'.encode()).decode()
    value = _run([op, 'read', f'op://{vault}/{item}/{field}'], env)
    if not value or '\n' in value:
        raise Blocked(f'the {name} key does not have the expected shape')
    return value


class KeyCache:
    def __init__(self, names: list[str], ttl: int = KEY_TTL):
        self.names = names
        self.ttl = ttl
        self.lock = threading.Lock()
        self.cache: dict[str, tuple[str, float]] = {}

    def get(self, name: str) -> str:
        with self.lock:
            hit = self.cache.get(name)
            if hit and time.monotonic() - hit[1] < self.ttl:
                return hit[0]
        value = auth_for(name)
        with self.lock:
            self.cache[name] = (value, time.monotonic())
        return value

    def drop(self, name: str) -> None:
        with self.lock:
            self.cache.pop(name, None)


def forward(name: str, body: bytes, keys: KeyCache) -> int:
    url, header, *_ = UPSTREAMS[name]
    from urllib.parse import urlsplit
    if urlsplit(url).hostname not in ALLOWED_HOSTS:
        raise Blocked('refused: upstream host is not in ALLOWED_HOSTS')
    headers = {'Content-Type': 'application/x-protobuf', header: keys.get(name)}
    if name == 'langfuse':
        headers['x-langfuse-ingestion-version'] = '4'
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=IO_TIMEOUT) as resp:
            resp.read(64 * 1024)
            return resp.status
    except urllib.error.HTTPError as err:
        err.read(4096)
        if err.code in (401, 403):
            keys.drop(name)  # a rotated key should not stay rejected until the TTL
        return err.code
    except urllib.error.URLError:
        return 0  # network failure; never surface the reason, it can carry a URL with auth


# --------------------------------------------------------------------------- server

class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.kept = collections.Counter()
        self.dropped = collections.Counter()
        self.upstream = collections.Counter()
        self.started = time.time()

    def add(self, decision: Decision, statuses: dict[str, int]):
        with self.lock:
            self.kept.update(decision.kept)
            self.dropped.update(decision.dropped)
            for name, status in statuses.items():
                self.upstream[f'{name}:{status}'] += 1

    def snapshot(self) -> dict:
        with self.lock:
            hours = max((time.time() - self.started) / 3600, 1 / 3600)
            return {
                'uptime_hours': round(hours, 3),
                'kept_spans': dict(self.kept),
                'kept_spans_per_hour': {k: round(v / hours) for k, v in self.kept.items()},
                'dropped_spans': dict(self.dropped),
                'upstream_responses': dict(self.upstream),
            }


def is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class Collector(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, *, upstreams: list[str], guard: RateGuard,
                 keys: KeyCache, dry_run: bool, log_path: Path | None):
        super().__init__(address, Handler)
        self.upstreams = upstreams
        self.guard = guard
        self.keys = keys
        self.dry_run = dry_run
        self.log_path = log_path
        self.stats = Stats()

    def log_row(self, row: dict) -> None:
        if not self.log_path:
            return
        try:
            with open(self.log_path, 'a') as handle:
                handle.write(json.dumps(row) + '\n')
        except OSError:
            pass  # best effort: never fail a request because the log is unwritable


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass  # the request line could carry a query string; never log it

    def _reply(self, status: int, body: bytes = b'') -> None:
        self.send_response(status)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        if self.path == '/stats':
            body = json.dumps(self.server.stats.snapshot(), indent=2).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._reply(404)

    def do_POST(self):
        if not is_loopback(self.client_address[0]):
            self._reply(403)
            return
        if self.path != '/v1/traces':
            self._reply(404)
            return
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            self._reply(400)
            return
        if length <= 0 or length > MAX_BODY:
            self._reply(413 if length > MAX_BODY else 400)
            return
        body = self.rfile.read(length)
        try:
            decision = filter_payload(body, self.server.guard)
        except ValueError:
            self._reply(400)
            return

        statuses: dict[str, int] = {}
        if decision.body and not self.server.dry_run:
            for name in self.server.upstreams:
                try:
                    statuses[name] = forward(name, decision.body, self.server.keys)
                except Blocked:
                    statuses[name] = -1
        self.server.stats.add(decision, statuses)
        self.server.log_row({
            'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'bytes_in': length, 'kept': decision.kept, 'dropped': decision.dropped,
            'upstream': statuses, 'dry_run': self.server.dry_run,
        })
        self._reply(200 if (not statuses or any(s == 200 for s in statuses.values())) else 502)


# --------------------------------------------------------------------------- self test

def self_test() -> int:
    """No network, no listener. Proves the filter does what the docstring claims."""
    import struct

    def kvbody(key: str, val: str) -> bytes:
        return delimited(1, key.encode()) + delimited(2, delimited(1, val.encode()))

    def span(name: str) -> bytes:
        now = time.time_ns()
        return b''.join([
            delimited(1, b'\x11' * 16), delimited(2, b'\x22' * 8), delimited(5, name.encode()),
            varint((6 << 3) | 0) + varint(1),
            varint((7 << 3) | 1) + struct.pack('<Q', now),
            varint((8 << 3) | 1) + struct.pack('<Q', now + 1000),
        ])

    def resource_spans(service: str | None, n: int) -> bytes:
        resource = delimited(1, kvbody('service.name', service)) if service is not None else b''
        scope = delimited(2, b''.join(delimited(2, span(f's{i}')) for i in range(n)))
        return delimited(1, delimited(1, resource) + scope)

    checks: list[tuple[str, bool]] = []

    def check(name: str, ok: bool):
        checks.append((name, bool(ok)))

    guard = RateGuard(DEFAULT_RATE_PER_MIN, {})
    d = filter_payload(resource_spans('claude-code', 3), guard)
    check('named service kept', d.kept == {'claude-code': 3} and len(d.body) > 0)

    d = filter_payload(resource_spans(None, 2), RateGuard(600, {}))
    check('resource with no attributes dropped', d.dropped == {'(unnamed)': 2} and d.body == b'')

    d = filter_payload(resource_spans('', 2), RateGuard(600, {}))
    check('empty service.name dropped', d.dropped == {'(unnamed)': 2} and d.body == b'')

    d = filter_payload(resource_spans('codex-worker', 5), RateGuard(600, {}))
    check('blocked service refused', d.dropped == {'blocked:codex-worker': 5} and d.body == b'')

    d = filter_payload(resource_spans('typo-agent', 1), RateGuard(600, {}))
    check('unknown name counted, not silently kept', d.dropped == {'unknown:typo-agent': 1})

    # The flood case: labelled, known, but far over budget.
    tiny = RateGuard(10, {})
    first = filter_payload(resource_spans('claude-code', 10), tiny)
    second = filter_payload(resource_spans('claude-code', 10), tiny)
    check('rate guard passes the first burst', first.kept == {'claude-code': 10})
    check('rate guard throttles the flood', second.dropped == {'throttled:claude-code': 10})

    # One over-budget service must not starve another.
    shared = RateGuard(10, {})
    filter_payload(resource_spans('claude-code', 10), shared)
    other = filter_payload(resource_spans('codex', 5), shared)
    check('one sender cannot starve another', other.kept == {'codex': 5})

    mixed = filter_payload(
        resource_spans('claude-code', 1) + resource_spans(None, 4) + resource_spans('codex', 2),
        RateGuard(600, {}))
    check('mixed batch keeps the named and drops the rest',
          mixed.kept == {'claude-code': 1, 'codex': 2} and mixed.dropped == {'(unnamed)': 4})
    check('re-emitted body is parseable OTLP',
          filter_payload(mixed.body, RateGuard(600, {})).kept == {'claude-code': 1, 'codex': 2})

    check('loopback check rejects a public address', not is_loopback('8.8.8.8'))
    check('loopback check accepts 127.0.0.1', is_loopback('127.0.0.1'))

    width = max(len(n) for n, _ in checks)
    for name, ok in checks:
        print(f'  {"pass" if ok else "FAIL"}  {name:{width}}')
    failed = [n for n, ok in checks if not ok]
    print()
    print(f'{len(checks) - len(failed)}/{len(checks)} checks passed')
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', type=int, default=4320)
    parser.add_argument('--upstream', action='append', choices=sorted(UPSTREAMS),
                        help='repeatable; omit with --dry-run to forward nowhere')
    parser.add_argument('--dry-run', action='store_true',
                        help='accept, filter and count, but forward nothing')
    parser.add_argument('--rate-per-min', type=int, default=DEFAULT_RATE_PER_MIN)
    parser.add_argument('--log', default=None, help='JSONL path for per-request counts')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    upstreams = args.upstream or []
    if not upstreams and not args.dry_run:
        print('Refusing to start: pass --upstream, or --dry-run to forward nothing.',
              file=sys.stderr)
        return 2

    guard = RateGuard(args.rate_per_min, RATE_OVERRIDES)
    keys = KeyCache(upstreams)
    if upstreams and not args.dry_run:
        for name in upstreams:
            # Read each key before serving, so a credential problem is loud here rather
            # than silent at the first span. Retried, because a cold `op read` under
            # launchd is slow rather than broken: on 2026-10-20 a single attempt killed
            # the job twice while KeepAlive kept reporting it as running.
            last: Blocked | None = None
            for attempt in range(1, KEY_RETRIES + 1):
                try:
                    keys.get(name)
                    last = None
                    break
                except Blocked as err:
                    last = err
                    if attempt < KEY_RETRIES:
                        print(f'  {name} key not read on attempt {attempt} ({err}); '
                              f'retrying in {KEY_RETRY_WAIT}s', file=sys.stderr)
                        sys.stderr.flush()
                        time.sleep(KEY_RETRY_WAIT)
            if last is not None:
                print(f'BLOCKED: cannot read the {name} key after {KEY_RETRIES} attempts: '
                      f'{last}', file=sys.stderr)
                return 2
        print(f'  keys for {", ".join(upstreams)} read from 1Password (values not shown)')

    server = Collector(('127.0.0.1', args.port), upstreams=upstreams, guard=guard, keys=keys,
                       dry_run=args.dry_run, log_path=Path(args.log) if args.log else None)
    print(f'  listening on 127.0.0.1:{server.server_address[1]}/v1/traces')
    print(f'  upstreams: {", ".join(upstreams) or "(none, dry run)"}')
    print(f'  rate guard: {args.rate_per_min} spans/min per service')
    print(f'  blocked: {", ".join(BLOCKED_SERVICES)}')
    print(f'  counts: GET http://127.0.0.1:{server.server_address[1]}/stats')
    sys.stdout.flush()

    # Under launchd a stop arrives as SIGTERM, not KeyboardInterrupt. shutdown()
    # cannot be called from the serving thread, so the handler only sets a flag and
    # the main thread closes the listener and lets in-flight requests finish.
    stop = threading.Event()
    previous = {}
    worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.5})
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, lambda *_: stop.set())
        worker.start()
        stop.wait()
    finally:
        if worker.is_alive():
            server.shutdown()
            worker.join(timeout=10)
        server.server_close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    # The final counts go to stdout, which launchd captures in the job's log.
    print(json.dumps(server.stats.snapshot(), indent=2))
    sys.stdout.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())

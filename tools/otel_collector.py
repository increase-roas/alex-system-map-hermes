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

SIGNOZ_HEADER = 'signoz-ingestion-key'
# 1Password vault Connectors, item "SigNoz ingestion key", field credential.
SIGNOZ_OP_REF = 'op://Connectors/hfy4llw7gassge2w5xuz64kgyu/credential'

UPSTREAMS = {
    # name: (url, header name). The credential route per upstream lives in auth_for():
    # SigNoz through robot_env plus a Keychain cache, Langfuse through the existing
    # langfuse_otel_headers.py helper, which already owns its own cache.
    'signoz': ('https://ingest.us2.signoz.cloud/v1/traces', SIGNOZ_HEADER),
    'langfuse': ('https://us.cloud.langfuse.com/api/public/otel/v1/traces', 'Authorization'),
}

# Names that are allowed through at all. Anything else is counted and dropped, so a
# typo in an agent's config shows up as a number instead of silently becoming "other".
KNOWN_SERVICES = (
    'claude-code', 'codex', 'cursor', 'javar', 'javante', 'auditor',
    'task-codex', 'task-claude', 'paperclip-worker', 'paperclip-reviewer',
    'dynamite-chatbot', 'alex-system-map',
    # Added 2026-10-20 (Alex: "switch everything to signoz"). paperclip = the Paperclip
    # server's own default service.name; hermes-agent = the Hermes Langfuse plugin's default.
    'paperclip', 'hermes-agent',
    # Claude Code sessions run from the Claude desktop app (Code tab, Cowork on this computer)
    # report as claude-code-desktop; found dropped as unknown 2026-10-20.
    'claude-code-desktop',
)

# Paths accepted. /api/public/otel/v1/traces is where Langfuse SDK v3 based senders (the
# Hermes Langfuse plugin) post when their base URL points here; the body is plain OTLP.
TRACE_PATHS = ('/v1/traces', '/api/public/otel/v1/traces')
# Logs and metrics too (2026-10-20): per SigNoz's own guides, Claude Code's main data is metrics and
# event logs (traces are beta), Codex sends logs, Hermes sends all three. OTLP logs and metrics have
# the same Resource -> scope -> records shape as traces, so the same filter, allowlist and per-service
# rate guard apply; each signal gets its own guard so a chatty log stream cannot starve traces.
SIGNAL_PATHS = {p: 'traces' for p in TRACE_PATHS}
SIGNAL_PATHS.update({'/v1/logs': 'logs', '/v1/metrics': 'metrics'})

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
KEY_TTL = 3600
# The warmer re-reads every key at half the TTL, so a cached header is replaced well
# before peek() would refuse it, and one failed refresh still leaves a second attempt
# (after the backoff) inside the old header's lifetime. Without this the warmer exited
# after the first success and an hour later every span was dropped with no error.
KEY_REFRESH_INTERVAL = KEY_TTL // 2
# Backoff after a failed key read, doubling each time, so a credential problem costs
# 1Password a handful of calls rather than one every few seconds forever.
KEY_BACKOFF_BASE = 30
KEY_BACKOFF_MAX = 900


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


# --------------------------------------------------------------------------- PII scrubbing
# Alex 2026-10-20: keep full content for debugging, but customer emails and phone numbers never
# leave this machine. SigNoz's PII guide scrubs in the collector, before export, so it happens
# here. Strings are rewritten inside the OTLP protobuf on the paths where text lives: span names,
# event names, status messages, log bodies, and every attribute value (nested arrays and maps too).
# Emails keep their domain (debuggable, not identifying); phone numbers need a separator, a "+1"
# or brackets, so bare digit runs (IDs, epoch seconds) are never touched.
EMAIL_RE_PII = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
PHONE_RE_PII = re.compile(r"(?<![\w+])(?:\+1[\s.-]?\d{3}[\s.-]?\d{3}[\s.-]?\d{4}|\(\d{3}\)\s?\d{3}[\s.-]?\d{4}|"
                          r"\d{3}[.-]\d{3}[.-]\d{4}|\d{3} \d{3} \d{4})(?![\w])")
SCRUB_STATS = collections.Counter()


def scrub_text(raw: bytes) -> bytes:
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw
    text, n1 = EMAIL_RE_PII.subn(r'[email]@\1', text)
    text, n2 = PHONE_RE_PII.subn('[phone]', text)
    if n1 or n2:
        SCRUB_STATS['email'] += n1
        SCRUB_STATS['phone'] += n2
        return text.encode('utf-8')
    return raw


def _rewrite(msg: bytes, plan: dict) -> bytes:
    """Copy a message, passing listed length-delimited fields through their handler."""
    out = bytearray()
    changed = False
    for field, wire, payload, start, end in iter_fields(msg):
        handler = plan.get(field) if wire == 2 else None
        if handler is None:
            out += msg[start:end]
            continue
        new = handler(payload)
        if new is payload or new == payload:
            out += msg[start:end]
        else:
            changed = True
            out += delimited(field, new)
    return bytes(out) if changed else msg


def _any_value(b):    # AnyValue: 1 string, 5 ArrayValue, 6 KeyValueList
    return _rewrite(b, {1: scrub_text, 5: lambda x: _rewrite(x, {1: _any_value}),
                        6: lambda x: _rewrite(x, {1: _key_value})})


def _key_value(b):    # KeyValue: 2 value
    return _rewrite(b, {2: _any_value})


def _attrs_at(n):
    return {n: _key_value}


def _span(b):         # Span: 5 name, 9 attributes, 11 events, 13 links, 15 status
    return _rewrite(b, {5: scrub_text, 9: _key_value,
                        11: lambda x: _rewrite(x, {2: scrub_text, 3: _key_value}),
                        13: lambda x: _rewrite(x, _attrs_at(4)),
                        15: lambda x: _rewrite(x, {2: scrub_text})})


def _log_record(b):   # LogRecord: 5 body, 6 attributes
    return _rewrite(b, {5: _any_value, 6: _key_value})


def _resource_block(record):
    # Resource{1: attributes}; Scope{1: InstrumentationScope, 2: records}
    return lambda b: _rewrite(b, {1: lambda r: _rewrite(r, _attrs_at(1)),
                                  2: lambda s: _rewrite(s, {2: record})})


SCRUBBERS = {'traces': _resource_block(_span), 'logs': _resource_block(_log_record)}


def scrub_payload(body: bytes, signal: str) -> bytes:
    """Mask emails and phone numbers in an OTLP export request. Metrics pass through."""
    block = SCRUBBERS.get(signal)
    return _rewrite(body, {1: block}) if block else body


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


# The proven credential path, reused rather than reimplemented.
#
# The hang I spent hours on is documented in op_items.robot_env: "Under the real HOME,
# op 2.39.0 on Alex's MacBook stalls for minutes before any network step; with a private
# HOME it answers in about a second". It also records that OP_BIOMETRIC_UNLOCK_ENABLED
# and OP_CACHE alone do NOT stop it. I had set exactly those two and passed the real
# HOME, which is why every launchd read timed out and why macOS kept asking Alex to let
# "op" reach other apps: with the real HOME, op goes near the 1Password app's data.
#
# robot_env gives op a private HOME, OP_CONFIG_DIR and TMPDIR under
# ~/.agents/runtime/op-robot, drops XDG_RUNTIME_DIR, and lets one `op daemon` serve every
# robot call. Nothing here is hand-rolled any more.
#
# On top of that, finished headers are cached in the login Keychain, the same pattern
# langfuse_otel_headers.py added on 2026-10-15 after 7,200 op calls a day starved every
# other op tool. `security` works fine under launchd and never prompts, so the common
# path touches 1Password not at all.
CONNECTORS = Path.home() / '.agents/tools/connectors'
LANGFUSE_HELPER = CONNECTORS / 'langfuse_otel_headers.py'
SECURITY = '/usr/bin/security'
CACHE_ACCOUNT = 'connectors-sync'
CACHE_TTL_SECONDS = 12 * 3600
SIGNOZ_CACHE_SERVICE = 'signoz-ingestion-header-cache'
ROBOT_TOKEN_SERVICE = 'op-service-account-connectors-sync'
# A single read gets a SHORT ceiling on purpose. A long one is worse than useless when
# the failure mode is a modal dialog waiting on a human: it holds the prompt on screen.
# A healthy robot call answers in about a second.
OP_READ_TIMEOUT = 10


def _load_op_items():
    """Import the shared op_items module from ~/.agents. Read-only use of their code."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('op_items', CONNECTORS / 'op_items.py')
    if spec is None or spec.loader is None:
        raise Blocked('op_items.py not found; cannot read credentials the proven way')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _keychain_get(service: str) -> dict | None:
    try:
        proc = subprocess.run([SECURITY, 'find-generic-password', '-a', CACHE_ACCOUNT,
                               '-s', service, '-w'], capture_output=True, text=True,
                              timeout=OP_READ_TIMEOUT)
    except subprocess.SubprocessError:
        # Blocked, not a miss: a hung Keychain must not fall through to a 1Password read.
        raise Blocked('the Keychain cache did not answer') from None
    if proc.returncode:
        return None
    try:
        held = json.loads(proc.stdout.strip())
    except ValueError:
        return None
    if not isinstance(held, dict) or time.time() - float(held.get('ts', 0)) >= CACHE_TTL_SECONDS:
        return None
    headers = held.get('headers')
    return headers if isinstance(headers, dict) and headers else None


def _keychain_put(service: str, headers: dict) -> None:
    # security(1) -i reads its command from stdin, so no credential rides in argv.
    import shlex
    command = ['add-generic-password', '-U', '-a', CACHE_ACCOUNT, '-s', service, '-w',
               json.dumps({'ts': time.time(), 'headers': headers})]
    try:
        subprocess.run([SECURITY, '-i'], input=shlex.join(command) + '\n',
                       capture_output=True, text=True, timeout=OP_READ_TIMEOUT)
    except subprocess.SubprocessError:
        pass  # best effort: the key is already read, a missed cache write only costs a re-read


def _robot_token() -> str:
    try:
        proc = subprocess.run([SECURITY, 'find-generic-password', '-a', CACHE_ACCOUNT,
                               '-s', ROBOT_TOKEN_SERVICE, '-w'], capture_output=True, text=True,
                              timeout=OP_READ_TIMEOUT)
    except subprocess.SubprocessError:
        raise Blocked('the robot service-account token could not be read') from None
    if proc.returncode or not proc.stdout.strip():
        raise Blocked('the robot service-account token is not readable')
    return proc.stdout.strip()


# Keychain-only mode, for a machine with no 1Password robot (the Mac mini, 2026-10-20).
# Set by --key-keychain SERVICE: the raw ingestion key sits in the login Keychain under
# account CACHE_ACCOUNT and that service, and 1Password is never called.
STATIC_KEY_SERVICE: str | None = None


def _keychain_raw(service: str) -> str:
    try:
        proc = subprocess.run([SECURITY, 'find-generic-password', '-a', CACHE_ACCOUNT, '-s', service, '-w'],
                              capture_output=True, text=True, timeout=OP_READ_TIMEOUT)
    except subprocess.SubprocessError:
        raise Blocked('the Keychain did not answer') from None
    key = proc.stdout.strip()
    if proc.returncode or not key or '\n' in key:
        raise Blocked(f'no usable SigNoz key in Keychain service {service}')
    return key


def signoz_headers() -> dict:
    """SigNoz ingestion header, Keychain-cached, read through robot_env on a miss."""
    if STATIC_KEY_SERVICE:
        return {SIGNOZ_HEADER: _keychain_raw(STATIC_KEY_SERVICE)}
    cached = _keychain_get(SIGNOZ_CACHE_SERVICE)
    if cached:
        return cached
    op_items = _load_op_items()
    token = _robot_token()
    with op_items.robot_env(token) as env:
        try:
            proc = subprocess.run(['op', 'read', SIGNOZ_OP_REF], capture_output=True, text=True,
                                  env=env, stdin=subprocess.DEVNULL, timeout=OP_READ_TIMEOUT)
        except subprocess.SubprocessError:
            raise Blocked('op did not answer for the SigNoz key') from None
    if proc.returncode or not proc.stdout.strip():
        raise Blocked('the SigNoz key could not be read from 1Password')
    key = proc.stdout.strip()
    if '\n' in key or '\r' in key:
        raise Blocked('the SigNoz key does not have the expected shape')
    headers = {SIGNOZ_HEADER: key}
    _keychain_put(SIGNOZ_CACHE_SERVICE, headers)
    return headers


def langfuse_headers() -> dict:
    """Langfuse headers from the EXISTING helper, which already owns its own 12h cache."""
    if not LANGFUSE_HELPER.exists():
        raise Blocked('the Langfuse header helper is missing')
    try:
        proc = subprocess.run([sys.executable, '-B', str(LANGFUSE_HELPER)], capture_output=True,
                              text=True, stdin=subprocess.DEVNULL, timeout=OP_READ_TIMEOUT)
    except subprocess.SubprocessError:
        raise Blocked('the Langfuse header helper did not answer') from None
    if proc.returncode:
        raise Blocked('the Langfuse header helper would not answer')
    try:
        headers = json.loads(proc.stdout.strip())
    except ValueError:
        raise Blocked('the Langfuse header helper returned nothing usable') from None
    if not isinstance(headers, dict) or 'Authorization' not in headers:
        raise Blocked('the Langfuse header helper returned no Authorization')
    return headers


def auth_for(name: str) -> str:
    """Header VALUE for one upstream. Never print or log the return value."""
    if name == 'signoz':
        return signoz_headers()[SIGNOZ_HEADER]
    if name == 'langfuse':
        return langfuse_headers()['Authorization']
    raise Blocked(f'no credential route for upstream {name}')


class KeyCache:
    """Holds each upstream's auth header, and refuses to hammer 1Password for it.

    The backoff is the important part. The 1Password service account is shared by
    every agent on this Mac and has a daily read cap. On 2026-10-20 this collector
    read three secrets per launch, crashed on a slow read, and launchd's KeepAlive
    relaunched it: the loop exhausted the account's authenticated path for everyone
    until the reads stopped. So a failed read now blocks further attempts for an
    exponentially growing interval, and a caller gets an immediate refusal instead
    of a new subprocess.
    """

    def __init__(self, names: list[str], ttl: int = KEY_TTL, clock=time.monotonic):
        self.names = names
        self.ttl = ttl
        self.clock = clock
        self.lock = threading.Lock()
        self.cache: dict[str, tuple[str, float]] = {}
        self.failures: dict[str, int] = {}
        self.blocked_until: dict[str, float] = {}

    def backoff_for(self, failures: int) -> float:
        return min(KEY_BACKOFF_BASE * (2 ** max(failures - 1, 0)), KEY_BACKOFF_MAX)

    def get(self, name: str, force: bool = False) -> str:
        """Cached value, or a read. force=True skips the cache hit (the refresh path)
        but still honours the failure backoff."""
        now = self.clock()
        with self.lock:
            hit = self.cache.get(name)
            if hit and not force and now - hit[1] < self.ttl:
                return hit[0]
            wait = self.blocked_until.get(name, 0.0) - now
            if wait > 0:
                raise Blocked(f'{name} key unavailable; not retrying for {wait:.0f}s')
        try:
            value = auth_for(name)
        except Exception as err:
            # Any failure counts, not just Blocked: a raw TimeoutExpired once skipped
            # this bookkeeping and the warmer retried at a fixed interval forever.
            with self.lock:
                self.failures[name] = self.failures.get(name, 0) + 1
                delay = self.backoff_for(self.failures[name])
                self.blocked_until[name] = self.clock() + delay
                count = self.failures[name]
            print(f'  {name} key read failed ({count} in a row); holding off {delay:.0f}s '
                  f'so 1Password is not hammered', file=sys.stderr)
            sys.stderr.flush()
            if isinstance(err, Blocked):
                raise
            raise Blocked(f'{name} key read failed ({type(err).__name__})') from None
        with self.lock:
            self.cache[name] = (value, self.clock())
            self.failures.pop(name, None)
            self.blocked_until.pop(name, None)
        return value

    def peek(self, name: str) -> str:
        """Cached value only. NEVER calls 1Password, so it cannot block a request.

        The request path must not wait on a credential: on 2026-10-20 a span arriving
        while the keys were cold held the HTTP handler for 90 seconds and the sender
        timed out. A span that cannot be forwarded right now is counted and dropped,
        which is visible in /stats, instead of stalling whoever sent it. The
        background warmer is the only thing that calls out to 1Password.
        """
        with self.lock:
            hit = self.cache.get(name)
            if hit and self.clock() - hit[1] < self.ttl:
                return hit[0]
        raise Blocked(f'{name} key not cached yet')

    def drop(self, name: str) -> None:
        with self.lock:
            self.cache.pop(name, None)


def warm_loop(keys: KeyCache, names: list[str], stop, interval: float = KEY_REFRESH_INTERVAL) -> None:
    """Keep every key fresh for the life of the process. Never raises, never exits
    on a failed read: a failure waits KEY_BACKOFF_BASE (KeyCache's own backoff stops
    the actual 1Password calls), a success waits `interval`. Uses stop.wait, so a
    SIGTERM ends it promptly."""
    # Reported once so the thread can be identified from outside, in the job log.
    print(f'  key warmer started: thread={threading.current_thread().name}')
    sys.stdout.flush()
    while not stop.is_set():
        failed = False
        for name in names:
            if stop.is_set():
                return
            try:
                keys.get(name, force=True)
                print(f'  {name} key read from 1Password (value not shown)')
                sys.stdout.flush()
            except Exception as err:  # a bad read must never end the warmer
                failed = True
                print(f'  {name} key still unavailable: {err if isinstance(err, Blocked) else type(err).__name__}',
                      file=sys.stderr)
                sys.stderr.flush()
        if stop.wait(KEY_BACKOFF_BASE if failed else interval):
            return


def forward(name: str, body: bytes, keys: KeyCache, signal: str = 'traces') -> int:
    url, header = UPSTREAMS[name]
    if signal != 'traces':
        url = url.rsplit('/v1/traces', 1)[0] + f'/v1/{signal}'
    from urllib.parse import urlsplit
    if urlsplit(url).hostname not in ALLOWED_HOSTS:
        raise Blocked('refused: upstream host is not in ALLOWED_HOSTS')
    headers = {'Content-Type': 'application/x-protobuf', header: keys.peek(name)}
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
        self.guards = {'traces': guard,
                       'logs': RateGuard(guard.per_min, guard.overrides),
                       'metrics': RateGuard(guard.per_min, guard.overrides)}
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
        signal = SIGNAL_PATHS.get(self.path.split('?', 1)[0])
        if not signal:
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
            decision = filter_payload(body, self.server.guards[signal])
        except ValueError:
            self._reply(400)
            return
        if signal != 'traces':  # counts in /stats read "logs:claude-code", "metrics:codex"
            decision = Decision(decision.body, {f'{signal}:{k}': v for k, v in decision.kept.items()},
                                {f'{signal}:{k}': v for k, v in decision.dropped.items()})

        if decision.body:
            try:
                decision.body = scrub_payload(decision.body, signal)
            except Exception:
                # Never forward unscrubbed content: an unreadable payload is dropped, and counted.
                self.server.stats.add(Decision(b'', {}, {f'scrub-failed:{signal}': 1}), {})
                self._reply(400)
                return

        statuses: dict[str, int] = {}
        if decision.body and not self.server.dry_run:
            for name in self.server.upstreams:
                if name != 'signoz' and signal != 'traces':
                    continue  # only SigNoz takes logs and metrics
                try:
                    statuses[name] = forward(name, decision.body, self.server.keys, signal)
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

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = ''):
        checks.append((name, bool(ok), detail))

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

    # The amplifier fix. These exist because on 2026-10-20 this collector exhausted the
    # shared 1Password service account by reading keys inside a KeepAlive restart loop.
    calls = {'n': 0}
    real_auth = globals()['auth_for']

    def counting_auth(name):
        calls['n'] += 1
        raise Blocked('simulated 1Password failure')

    globals()['auth_for'] = counting_auth
    try:
        cache = KeyCache(['signoz'])
        refusals = []
        for _ in range(5):
            try:
                cache.get('signoz')
            except Blocked as err:
                refusals.append(str(err))
        check('five requests cause ONE call to 1Password, not five',
              calls['n'] == 1, f'calls made: {calls["n"]}')
        check('later requests are refused without calling out',
              len(refusals) == 5 and any('not retrying' in r for r in refusals[1:]),
              f'refusals: {refusals[1:2]}')
        check('backoff grows with consecutive failures',
              cache.backoff_for(1) < cache.backoff_for(3) < cache.backoff_for(9))
        check('backoff is capped', cache.backoff_for(99) == KEY_BACKOFF_MAX,
              f'{cache.backoff_for(99)} vs {KEY_BACKOFF_MAX}')

        # A key that starts working must clear the hold immediately.
        cache2 = KeyCache(['signoz'])
        try:
            cache2.get('signoz')
        except Blocked:
            pass
        globals()['auth_for'] = lambda name: 'test-header-value'
        cache2.blocked_until['signoz'] = 0.0  # as if the hold had elapsed
        check('a recovered key is cached and the failure count resets',
              cache2.get('signoz') == 'test-header-value'
              and 'signoz' not in cache2.failures)

        # The request path must never wait on 1Password.
        before = calls['n']
        globals()['auth_for'] = counting_auth
        cold = KeyCache(['signoz'])
        try:
            cold.peek('signoz')
            peeked = 'returned a value it should not have'
        except Blocked:
            peeked = 'refused'
        check('peek on a cold cache refuses instead of blocking', peeked == 'refused', peeked)
        check('peek makes NO call to 1Password', calls['n'] == before,
              f'calls before {before}, after {calls["n"]}')

        # The one-hour failure: the warmer used to exit after its first success, so the
        # header expired and every span was dropped. Fake clock, tiny TTL, no network.
        now = {'t': 0.0}
        reads = {'n': 0}

        def good_auth(name):
            reads['n'] += 1
            return f'hdr-{reads["n"]}'

        globals()['auth_for'] = good_auth
        ttl = 100
        live = KeyCache(['signoz'], ttl=ttl, clock=lambda: now['t'])

        class FakeStop:
            """Each wait() advances the clock by the requested time; ends after 6 waits."""
            def __init__(self):
                self.waits = []
            def is_set(self):
                return len(self.waits) >= 6
            def wait(self, t):
                self.waits.append(t)
                now['t'] += t
                return self.is_set()

        fs = FakeStop()
        warm_loop(live, ['signoz'], fs, interval=ttl // 2)
        check('warmer outlives the TTL and keeps a header available',
              now['t'] >= 3 * ttl and live.peek('signoz') == f'hdr-{reads["n"]}',
              f'clock {now["t"]}, reads {reads["n"]}')
        check('refresh is scheduled, not a storm', 5 <= reads['n'] <= 7 and set(fs.waits) == {ttl // 2},
              f'reads {reads["n"]}, waits {sorted(set(fs.waits))}')
        # Without any refresh, the same cache must have expired (proves the clock works).
        stale = KeyCache(['signoz'], ttl=ttl, clock=lambda: now['t'])
        stale.get('signoz')
        now['t'] += ttl + 1
        try:
            stale.peek('signoz')
            expired = 'still served'
        except Blocked:
            expired = 'refused'
        check('an unrefreshed header is refused after the TTL', expired == 'refused', expired)

        # A failing read must not end the warmer or hammer 1Password.
        globals()['auth_for'] = counting_auth
        calls['n'] = 0
        now['t'] = 0.0
        down = KeyCache(['signoz'], ttl=ttl, clock=lambda: now['t'])
        fs2 = FakeStop()
        warm_loop(down, ['signoz'], fs2, interval=ttl // 2)
        check('failed reads keep the warmer alive and are backed off',
              len(fs2.waits) == 6 and calls['n'] < 6, f'waits {len(fs2.waits)}, calls {calls["n"]}')

        # The backoff bypass: a reader that raised anything but Blocked skipped the
        # bookkeeping, so the warmer retried at a fixed interval forever. Each failure
        # type must produce the same attempt count and the same growing hold as Blocked.
        def run_failing(make_exc):
            attempts = {'n': 0}

            def failing_auth(name):
                attempts['n'] += 1
                raise make_exc()

            globals()['auth_for'] = failing_auth
            clock = {'t': 0.0}
            kc = KeyCache(['signoz'], ttl=100, clock=lambda: clock['t'])

            class Stop:
                def __init__(self):
                    self.waits = []
                def is_set(self):
                    return len(self.waits) >= 12
                def wait(self, t):
                    self.waits.append(t)
                    clock['t'] += t
                    return self.is_set()

            st = Stop()
            try:
                warm_loop(kc, ['signoz'], st, interval=50)
                survived = True
            except BaseException:
                survived = False
            hold = kc.blocked_until.get('signoz', 0.0) - clock['t']
            return attempts['n'], kc.failures.get('signoz', 0), survived, len(st.waits), hold, kc

        ref = run_failing(lambda: Blocked('simulated'))
        for label, make_exc in (
                ('subprocess.TimeoutExpired', lambda: subprocess.TimeoutExpired(['op', 'read'], 10)),
                ('an arbitrary RuntimeError', lambda: RuntimeError('boom'))):
            got = run_failing(make_exc)
            check(f'{label} from the reader is counted as a failure',
                  got[1] >= 1, f'failure_count {got[1]}')
            check(f'{label} gets the same attempt count as Blocked (not a fixed-interval retry)',
                  got[0] == ref[0] and got[1] == ref[1],
                  f'attempts {got[0]} vs {ref[0]}, failure_count {got[1]} vs {ref[1]}')
            check(f'{label} sets a hold, and the warmer stays alive',
                  got[2] and got[3] == 12 and got[4] > 0 and ref[0] < 12,
                  f'survived {got[2]}, waits {got[3]}, hold {got[4]:.0f}s')
            try:
                run_failing(make_exc)[5].get('signoz')
                shape = 'no exception'
            except Blocked:
                shape = 'Blocked'
            except BaseException as err:
                shape = type(err).__name__
            check(f'{label} reaches callers as Blocked', shape == 'Blocked', shape)
        globals()['auth_for'] = real_auth

        # Half one: each credential function turns a subprocess failure into Blocked.
        real_run = subprocess.run
        real_helper = globals()['LANGFUSE_HELPER']
        real_get, real_put = globals()['_keychain_get'], globals()['_keychain_put']
        real_tok, real_load = globals()['_robot_token'], globals()['_load_op_items']

        def raiser(exc):
            def fake(*a, **k):
                raise exc
            return fake

        def outcome(fn, *args):
            try:
                fn(*args)
                return 'returned'
            except Blocked:
                return 'Blocked'
            except BaseException as err:
                return type(err).__name__

        class FakeOps:
            @staticmethod
            def robot_env(token):
                import contextlib
                return contextlib.nullcontext({})

        try:
            globals()['LANGFUSE_HELPER'] = Path(__file__)
            for label, exc in (('timeout', subprocess.TimeoutExpired(['x'], 10)),
                               ('subprocess error', subprocess.SubprocessError('x'))):
                subprocess.run = raiser(exc)
                check(f'_keychain_get: {label} becomes Blocked', outcome(real_get, 'svc') == 'Blocked',
                      outcome(real_get, 'svc'))
                check(f'_keychain_put: {label} does not escape', outcome(real_put, 'svc', {'h': 'v'}) == 'returned',
                      outcome(real_put, 'svc', {'h': 'v'}))
                check(f'_robot_token: {label} becomes Blocked', outcome(real_tok) == 'Blocked', outcome(real_tok))
                check(f'langfuse_headers: {label} becomes Blocked',
                      outcome(langfuse_headers) == 'Blocked', outcome(langfuse_headers))
                globals()['_keychain_get'] = lambda service: None
                globals()['_keychain_put'] = lambda service, headers: None
                globals()['_robot_token'] = lambda: 'tok'
                globals()['_load_op_items'] = lambda: FakeOps
                check(f'signoz_headers op read: {label} becomes Blocked',
                      outcome(signoz_headers) == 'Blocked', outcome(signoz_headers))
                globals()['_keychain_get'], globals()['_keychain_put'] = real_get, real_put
                globals()['_robot_token'], globals()['_load_op_items'] = real_tok, real_load
        finally:
            subprocess.run = real_run
            globals()['LANGFUSE_HELPER'] = real_helper
            globals()['_keychain_get'], globals()['_keychain_put'] = real_get, real_put
            globals()['_robot_token'], globals()['_load_op_items'] = real_tok, real_load
    finally:
        globals()['auth_for'] = real_auth

    # PII scrubbing (2026-10-20): emails and phones masked in log bodies, attributes and span names;
    # IDs and bare digit runs untouched; the scrubbed payload still parses and keeps its service.
    def _kv(k, v):
        return delimited(1, k.encode()) + delimited(2, delimited(1, v.encode()))
    _res = delimited(1, delimited(1, _kv('service.name', 'javante')))
    _txt = 'jane.doe@gmail.com (555) 123-4567 +1 555 987 6543 id 1792487516'
    _rec = delimited(5, delimited(1, _txt.encode())) + delimited(6, _kv('lead.phone', '555-222-3333'))
    _out = scrub_payload(delimited(1, _res + delimited(2, delimited(2, _rec))), 'logs')
    check('scrub: email masked, domain kept', b'[email]@gmail.com' in _out and b'jane.doe' not in _out, _out[:80])
    check('scrub: phone formats masked', _out.count(b'[phone]') == 3 and b'123-4567' not in _out, _out[:80])
    check('scrub: bare digit ids untouched', b'1792487516' in _out, _out[:80])
    _span = scrub_payload(delimited(1, _res + delimited(2, delimited(2, delimited(5, b'call bob@acme.io')))), 'traces')
    check('scrub: span names masked', b'[email]@acme.io' in _span and b'bob@' not in _span, _span)
    check('scrub: output still parses with its service',
          filter_payload(_out, RateGuard(600, {})).kept == {'javante': 1}, '')

    width = max(len(n) for n, _ok, _d in checks)
    for name, ok, detail in checks:
        line = f'  {"pass" if ok else "FAIL"}  {name:{width}}'
        print(line if ok else line + f'   <- {detail}')
    failed = [n for n, ok, _d in checks if not ok]
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
    parser.add_argument('--key-keychain', default=None, metavar='SERVICE',
                        help='read the SigNoz key from this login Keychain service only (no 1Password)')
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if args.key_keychain:
        globals()['STATIC_KEY_SERVICE'] = args.key_keychain

    upstreams = args.upstream or []
    if not upstreams and not args.dry_run:
        print('Refusing to start: pass --upstream, or --dry-run to forward nothing.',
              file=sys.stderr)
        return 2

    guard = RateGuard(args.rate_per_min, RATE_OVERRIDES)
    keys = KeyCache(upstreams)

    # Under launchd a stop arrives as SIGTERM, not KeyboardInterrupt. shutdown() cannot
    # be called from the serving thread, so the handler only sets this flag and the main
    # thread closes the listener and lets in-flight requests finish. Declared here
    # because the key-warming thread waits on it too.
    stop = threading.Event()

    server = Collector(('127.0.0.1', args.port), upstreams=upstreams, guard=guard, keys=keys,
                       dry_run=args.dry_run, log_path=Path(args.log) if args.log else None)
    print(f'  listening on 127.0.0.1:{server.server_address[1]}/v1/traces')
    print(f'  upstreams: {", ".join(upstreams) or "(none, dry run)"}')
    print(f'  rate guard: {args.rate_per_min} spans/min per service')
    print(f'  blocked: {", ".join(BLOCKED_SERVICES)}')
    print(f'  counts: GET http://127.0.0.1:{server.server_address[1]}/stats')
    sys.stdout.flush()

    # Keys are warmed in the BACKGROUND, after the listener is already bound. Reading
    # them first was a design bug: on 2026-10-20 a slow `op read` under launchd held the
    # startup path for minutes, so the port never opened and the service looked dead
    # while the process was perfectly healthy. Binding first means /stats answers at
    # once, a span that cannot be forwarded is counted rather than lost, and the thing
    # is diagnosable from outside. KeyCache's backoff keeps the retries cheap.
    if upstreams and not args.dry_run:
        threading.Thread(target=warm_loop, args=(keys, upstreams, stop), daemon=True, name='warm-keys').start()

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

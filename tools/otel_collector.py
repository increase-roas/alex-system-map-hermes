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
7. Says when it is failing, and keeps what it could not send (2026-10-21, after a 12-hour
   silent key outage): GET /health is 503 with the reason when SigNoz is not getting data,
   a heartbeat log (service signoz-collector) goes out every 5 minutes for SigNoz to alert
   on, and batches SigNoz could not take wait in a capped on-disk spool and are replayed.

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
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Allowlist. The only hosts this file may reach, named here as tools/** requires.
# Langfuse removed 2026-10-20 (Alex approved: SigNoz is the only upstream).
ALLOWED_HOSTS = ('ingest.us2.signoz.cloud',)

SIGNOZ_HEADER = 'signoz-ingestion-key'
# 1Password vault Connectors, item "SigNoz ingestion key", field credential.
SIGNOZ_OP_REF = 'op://Connectors/hfy4llw7gassge2w5xuz64kgyu/credential'

UPSTREAMS = {
    # name: (url, header name). The credential route per upstream lives in auth_for():
    # SigNoz through robot_env plus a Keychain cache. The Langfuse upstream was removed
    # on 2026-10-20 (Alex approved); SigNoz is the only destination.
    'signoz': ('https://ingest.us2.signoz.cloud/v1/traces', SIGNOZ_HEADER),
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
    # OpenClaw gateway on the Orgo openclaw-hub computer (diagnostics-otel plugin, serviceName
    # openclaw, which is also the plugin's own default). Added 2026-10-20, Alex approved the switch.
    'openclaw',
    # The collector's own 5-minute heartbeat (2026-10-21), so SigNoz can alert when a collector goes dark.
    'signoz-collector',
    # Paperclip's agent-observability connection test (service.name paperclip-observability-test, set in
    # @paperclipai/server/dist/services/agent-observability-test.js:54). Added 2026-10-21 on the Mac mini copy: the
    # export arrives through otel.increaseroas.com behind Access, and without this the test span was accepted at the
    # door and dropped here, so nothing proved the last hop. Real agent runs send as claude-code or codex/task-claude.
    'paperclip-observability-test',
)

# Paths accepted. /api/public/otel/v1/traces is where Langfuse SDK v3 based senders (the
# Hermes Langfuse plugin) post when their base URL points here; the body is plain OTLP and
# it is forwarded to SigNoz like any other trace. Kept after the Langfuse upstream went.
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
# paperclip: agent runs burst past 600/min (Mac mini, 2026-10-20); SigNoz's 1 GiB/day cap still applies.
RATE_OVERRIDES: dict[str, int] = {'paperclip': 3000}

# Per-signal caps that apply on top of RATE_OVERRIDES for one signal only.
# task-claude logs (the Codex desktop app, below): measured 2026-10-20 on a count-only listener
# at about 630 bytes a record, 16 records at app start and 19 for a minimal turn. 200 a minute
# is roughly 10 busy turns a minute of headroom, and caps a runaway at about 288k records
# (~180 MB on the wire) a day, inside the 1 GiB/day SigNoz logs cap with the other senders.
# Claude Code traces run from Codex shells also report as task-claude; they keep the default.
SIGNAL_RATE_OVERRIDES: dict[str, dict[str, int]] = {
    'logs': {'task-claude': 200},
}

# Exact incoming service.name -> stored name, per signal, for a sender that cannot set its own.
# Codex's [otel] config has no service-name setting (the reference lists environment, exporter,
# trace_exporter, metrics_exporter, log_user_prompt); it stamps service.name with its originator.
# The Codex desktop app (ChatGPT.app's `codex app-server`) reports `codex-app-server`, measured
# 2026-10-20. Alex: "Send its OTel logs to 127.0.0.1:4320 as task-claude". Exact names only; the
# original is kept on the resource as collector.renamed_from. Blocked names are refused BEFORE
# any rename, so a rename can never let codex-worker through.
SERVICE_RENAMES: dict[str, dict[str, str]] = {
    'logs': {'codex-app-server': 'task-claude'},
}
RENAMED_FROM_KEY = 'collector.renamed_from'

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


class BodyError(Exception):
    """A request body that cannot be read; carries the HTTP status to answer with."""

    def __init__(self, status: int):
        super().__init__(status)
        self.status = status


def read_request_body(headers, rfile, limit: int = MAX_BODY) -> bytes:
    """The request body, de-chunked and gunzipped, never more than `limit` bytes.

    OTel JS 0.2xx (OpenClaw's diagnostics-otel, 2026-10-20) streams every export with
    Transfer-Encoding: chunked and no Content-Length, and gzips when compression is set;
    before this the collector answered 400 without reading the body, and the unread bytes
    then broke the next response on the kept-alive connection ("Parse Error: Expected
    HTTP/"). HTTP/1.1 servers must accept chunked bodies (RFC 9112 section 7.1) and the
    OpenTelemetry Collector's OTLP receiver accepts gzip, so both are handled here.
    """
    if 'chunked' in (headers.get('Transfer-Encoding') or '').lower():
        parts, total = [], 0
        while True:
            line = rfile.readline(1024)
            try:
                size = int(line.split(b';', 1)[0].strip(), 16)
            except ValueError:
                raise BodyError(400) from None
            if size == 0:
                while rfile.readline(1024) not in (b'\r\n', b'\n', b''):
                    pass  # trailer fields, never used
                break
            total += size
            if total > limit:
                raise BodyError(413)
            parts.append(rfile.read(size))
            rfile.readline(1024)  # CRLF after each chunk
        body = b''.join(parts)
    else:
        try:
            length = int(headers.get('Content-Length') or 0)
        except ValueError:
            raise BodyError(400) from None
        if length > limit:
            raise BodyError(413)
        body = rfile.read(length) if length > 0 else b''
    if not body:
        raise BodyError(400)
    encoding = (headers.get('Content-Encoding') or '').strip().lower()
    if encoding == 'gzip':
        import zlib
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            body = inflater.decompress(body, limit + 1)
        except zlib.error:
            raise BodyError(400) from None
        if len(body) > limit or inflater.unconsumed_tail:
            raise BodyError(413)
    elif encoding not in ('', 'identity'):
        raise BodyError(415)
    return body


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


def _string_kv(key: str, value: str) -> bytes:
    return delimited(1, key.encode()) + delimited(2, delimited(1, value.encode()))


def _renamed_resource(resource: bytes, new: str, old: str) -> bytes:
    """Resource with service.name replaced and the old name kept as collector.renamed_from."""
    out = bytearray()
    for field, wire, payload, start, end in iter_fields(resource):
        if field == 1 and wire == 2:
            key = next((kp for kf, kw, kp, _s, _e in iter_fields(payload) if kf == 1 and kw == 2), None)
            if key == b'service.name':
                out += delimited(1, _string_kv('service.name', new))
                out += delimited(1, _string_kv(RENAMED_FROM_KEY, old))
                continue
        out += resource[start:end]
    return bytes(out)


def rename_block(block: bytes, new: str, old: str) -> bytes:
    """ResourceSpans / ResourceLogs / ResourceMetrics: field 1 is the Resource."""
    return _rewrite(block, {1: lambda r: _renamed_resource(r, new, old)})


def filter_payload(body: bytes, guard: RateGuard, known=KNOWN_SERVICES,
                   blocked=BLOCKED_SERVICES, renames: dict[str, str] | None = None) -> Decision:
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
        new_name = (renames or {}).get(service)
        if new_name:
            payload = rename_block(payload, new_name, service)
            service = new_name
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
SECURITY = '/usr/bin/security'
CACHE_ACCOUNT = 'connectors-sync'
CACHE_TTL_SECONDS = 12 * 3600
SIGNOZ_CACHE_SERVICE = 'signoz-ingestion-header-cache'
ROBOT_TOKEN_SERVICE = 'op-service-account-connectors-sync'
# The LaunchAgent names the Keychain item that holds the robot token in its EnvironmentVariables (a
# reference, never the token), so the job's own plist says where its credential comes from (2026-10-21).
ROBOT_TOKEN_ENV = 'SIGNOZ_ROBOT_TOKEN_SERVICE'
# A single read gets a SHORT ceiling on purpose. A long one is worse than useless when
# the failure mode is a modal dialog waiting on a human: it holds the prompt on screen.
# A healthy robot call answers in about a second.
OP_READ_TIMEOUT = 10
# launchd gives this job PATH=/usr/bin:/bin:/usr/sbin:/sbin, and Homebrew keeps op in /opt/homebrew/bin.
# A bare 'op' raised FileNotFoundError on every refresh once the Keychain cache expired on 2026-10-20 at
# 15:31Z, and every batch after 16:03Z was dropped. So op is found by absolute path, PATH first.
OP_FALLBACK_DIRS = ('/opt/homebrew/bin', '/usr/local/bin')


def _op_bin() -> str:
    found = shutil.which('op')
    if found:
        return found
    for folder in OP_FALLBACK_DIRS:
        candidate = os.path.join(folder, 'op')
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise Blocked('the 1Password CLI (op) is not on PATH or in ' + ', '.join(OP_FALLBACK_DIRS))


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


def robot_token_service() -> str:
    return os.environ.get(ROBOT_TOKEN_ENV) or ROBOT_TOKEN_SERVICE


def robot_token_present() -> bool:
    """Is the referenced Keychain item there? Attributes only; the token is never read here."""
    try:
        return subprocess.run([SECURITY, 'find-generic-password', '-a', CACHE_ACCOUNT, '-s', robot_token_service()],
                              capture_output=True, timeout=OP_READ_TIMEOUT).returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _robot_token() -> str:
    try:
        proc = subprocess.run([SECURITY, 'find-generic-password', '-a', CACHE_ACCOUNT,
                               '-s', robot_token_service(), '-w'], capture_output=True, text=True,
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


# Key-file mode, for a Linux machine with no Keychain and no robot that can see vault Connectors
# (the Orgo computers, 2026-10-20). Set by --key-file PATH: the raw ingestion key is the whole
# file. The file must be a regular file (no symlink), owned by the user this collector runs as,
# with no group or other permission bits, so a key left readable by the agent is refused.
STATIC_KEY_FILE: str | None = None


def _key_file_raw(path: str) -> str:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    except OSError:
        raise Blocked('the SigNoz key file could not be opened') from None
    with os.fdopen(fd, 'r') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise Blocked('the SigNoz key file must be a regular file, owned by this user, mode 0600 or 0400')
        key = stream.read().strip()
    if not key or '\n' in key or '\r' in key:
        raise Blocked('the SigNoz key file does not hold one key')
    return key


def signoz_headers() -> dict:
    """SigNoz ingestion header, Keychain-cached, read through robot_env on a miss."""
    if STATIC_KEY_FILE:
        return {SIGNOZ_HEADER: _key_file_raw(STATIC_KEY_FILE)}
    if STATIC_KEY_SERVICE:
        return {SIGNOZ_HEADER: _keychain_raw(STATIC_KEY_SERVICE)}
    cached = _keychain_get(SIGNOZ_CACHE_SERVICE)
    if cached:
        return cached
    op_items = _load_op_items()
    op = _op_bin()
    token = _robot_token()
    with op_items.robot_env(token) as env:
        try:
            proc = subprocess.run([op, 'read', SIGNOZ_OP_REF], capture_output=True, text=True,
                                  env=env, stdin=subprocess.DEVNULL, timeout=OP_READ_TIMEOUT)
        except (subprocess.SubprocessError, OSError):
            raise Blocked('op did not answer for the SigNoz key') from None
    if proc.returncode or not proc.stdout.strip():
        raise Blocked('the SigNoz key could not be read from 1Password')
    key = proc.stdout.strip()
    if '\n' in key or '\r' in key:
        raise Blocked('the SigNoz key does not have the expected shape')
    headers = {SIGNOZ_HEADER: key}
    _keychain_put(SIGNOZ_CACHE_SERVICE, headers)
    return headers


def auth_for(name: str) -> str:
    """Header VALUE for one upstream. Never print or log the return value."""
    if name == 'signoz':
        return signoz_headers()[SIGNOZ_HEADER]
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


# --------------------------------------------------------------------------- spool, heartbeat, health

# 2026-10-20/21: the key failed for 12 hours and 25,267 batches were dropped, because nothing kept them
# and nothing said so. A batch SigNoz did not take for a reason that can clear (no key, network, auth,
# rate limit, server error) is now written here and replayed; the folder is capped, oldest out first.
# Bodies are already PII-scrubbed when they get here. ~/.agents/runtime is git-ignored.
SPOOL_DIR = Path.home() / '.agents/runtime/otel-spool'
SPOOL_MAX_BYTES = 256 * 1024 * 1024
SPOOL_REPLAY_SECONDS = 60
SPOOL_REPLAY_BATCH = 500
# A heartbeat log every 5 minutes, sent the same way as everything else, so SigNoz can alert on its
# absence. Silence from claude-code-desktop is normal when Alex is away; silence from this is not.
HEARTBEAT_SERVICE = 'signoz-collector'
HEARTBEAT_SECONDS = 300
# /health turns 503 when the key is missing, or sends have failed 3 times in a row with no success
# for this long. The first HEALTH_GRACE_SECONDS after a start are spent warming the key.
HEALTH_STALE_SECONDS = 900
HEALTH_GRACE_SECONDS = 120


def retryable(status: int) -> bool:
    """-1 no key, 0 network, auth (a refreshed key fixes it), timeout, rate limit, server error."""
    return status in (-1, 0, 401, 403, 408, 429) or status >= 500


class Spool:
    """Batches waiting for SigNoz, one file each: <ns>-<seq>.<upstream>.<signal>.pb."""

    def __init__(self, folder: Path | None, max_bytes: int = SPOOL_MAX_BYTES):
        self.folder = folder
        self.max_bytes = max_bytes
        self.lock = threading.Lock()
        self.seq = 0
        self.counts = collections.Counter()
        if folder:
            # A folder that can't be made (an Orgo service user has HOME=/nonexistent) turns the spool off
            # instead of stopping the collector; /stats shows spool dir-failed.
            try:
                folder.mkdir(parents=True, exist_ok=True)
                os.chmod(folder, 0o700)
            except OSError:
                self.folder = None
                self.counts['dir-failed'] += 1
                print(f'  spool folder {folder} could not be made; spool off', file=sys.stderr)

    def put(self, upstream: str, signal: str, body: bytes) -> bool:
        if not self.folder:
            return False
        with self.lock:
            self.seq += 1
            name = f'{time.time_ns():020d}-{self.seq:06d}.{upstream}.{signal}.pb'
        tmp = self.folder / f'.{name}.tmp'
        try:
            tmp.write_bytes(body)
            os.replace(tmp, self.folder / name)
        except OSError:
            with self.lock:
                self.counts['write-failed'] += 1
            return False
        with self.lock:
            self.counts['spooled'] += 1
        self.trim()
        return True

    def pending(self) -> list[Path]:
        return sorted(self.folder.glob('*.pb')) if self.folder else []

    def size(self) -> tuple[int, int]:
        files = self.pending()
        total = 0
        for path in files:
            try:
                total += path.stat().st_size
            except OSError:
                pass
        return len(files), total

    def trim(self) -> None:
        files = self.pending()
        sizes = []
        for path in files:
            try:
                sizes.append(path.stat().st_size)
            except OSError:
                sizes.append(0)
        total = sum(sizes)
        for path, size in zip(files, sizes):
            if total <= self.max_bytes:
                return
            try:
                path.unlink()
            except OSError:
                continue
            total -= size
            with self.lock:
                self.counts['evicted'] += 1

    def replay(self, send) -> None:
        """Oldest first. send(upstream, signal, body) -> status. Stops at the first batch that still
        can't go (the outage isn't over); drops one SigNoz refused for good (a bad payload)."""
        for path in self.pending()[:SPOOL_REPLAY_BATCH]:
            try:
                _stamp, upstream, signal, _ext = path.name.split('.')
                body = path.read_bytes()
            except (ValueError, OSError):
                continue
            status = send(upstream, signal, body)
            if retryable(status):
                return
            try:
                path.unlink()
            except OSError:
                pass
            with self.lock:
                self.counts['replayed' if 200 <= status < 300 else f'rejected:{status}'] += 1


def heartbeat_body(host: str, extra: dict) -> bytes:
    """One OTLP log record from service signoz-collector (ExportLogsServiceRequest, protobuf)."""
    now = struct.pack('<Q', time.time_ns())
    record = b''.join([
        varint((1 << 3) | 1) + now,                       # time_unix_nano
        varint((11 << 3) | 1) + now,                      # observed_time_unix_nano
        varint((2 << 3) | 0) + varint(9),                 # severity_number INFO
        delimited(3, b'INFO'),
        delimited(5, delimited(1, b'collector heartbeat')),
        *(delimited(6, _string_kv(k, str(v))) for k, v in extra.items()),
    ])
    resource = delimited(1, _string_kv('service.name', HEARTBEAT_SERVICE)) + delimited(1, _string_kv('host.name', host))
    return delimited(1, delimited(1, resource) + delimited(2, delimited(2, record)))


def health(server) -> dict:
    """What /health reports. ok is false when SigNoz is not getting the data."""
    if server.dry_run or not server.upstreams:
        return {'ok': True, 'problems': [], 'mode': 'dry run'}
    problems = []
    state = server.stats.upstream_state()
    for name in server.upstreams:
        st = state.get(name, {})
        warming = time.time() - server.stats.started < HEALTH_GRACE_SECONDS and not st.get('fail_streak')
        try:
            server.keys.peek(name)
        except Blocked as err:
            if not warming:
                problems.append(f'{name}: no key ({err})')
        last_ok = st.get('last_ok_at')
        if st.get('fail_streak', 0) >= 3 and (not last_ok or time.time() - last_ok > HEALTH_STALE_SECONDS):
            problems.append(f'{name}: {st["fail_streak"]} sends failed in a row, last status '
                            f'{st.get("last_fail_status")}, last ok {st.get("last_ok") or "never"}')
    files, size = server.spool.size()
    route = 'key file' if STATIC_KEY_FILE else 'keychain key' if STATIC_KEY_SERVICE else '1Password robot'
    key_route = {'route': route}
    if route == '1Password robot':
        key_route.update({'robot_token_service': robot_token_service(),
                          'robot_token_from': 'plist' if os.environ.get(ROBOT_TOKEN_ENV) else 'code default',
                          'robot_token_present': robot_token_present()})
    return {'ok': not problems, 'problems': problems, 'spool_files': files, 'spool_bytes': size,
            'key_route': key_route, 'upstream_state': state}


def default_host_name() -> str:
    """A name that stays put. gethostname() on a Mac follows the network (Mac.attwifi.manager on one
    Wi-Fi, Alexs-MacBook-Pro.local on another), which would trip a per-host alert; LocalHostName doesn't.
    Under launchd this lookup came back empty (2026-10-21), so the LaunchAgent passes --host-name itself."""
    if sys.platform == 'darwin':
        try:
            name = subprocess.run(['/usr/sbin/scutil', '--get', 'LocalHostName'], capture_output=True,
                                  text=True, timeout=5).stdout.strip()
            if name:
                return name
        except (subprocess.SubprocessError, OSError):
            pass
    return socket.gethostname().split('.')[0]


def background_loop(server, stop, host: str) -> None:
    """Heartbeat every HEARTBEAT_SECONDS, spool replay every SPOOL_REPLAY_SECONDS. Never raises."""
    next_beat = time.monotonic()
    while not stop.is_set():
        try:
            if time.monotonic() >= next_beat:
                next_beat = time.monotonic() + HEARTBEAT_SECONDS
                files, size = server.spool.size()
                streak = server.stats.upstream_state().get('signoz', {}).get('fail_streak', 0)
                body = heartbeat_body(host, {'spool.files': files, 'spool.bytes': size, 'fail_streak': streak})
                server.deliver('logs', Decision(body, {f'logs:{HEARTBEAT_SERVICE}': 1}, {}), len(body))
            server.replay_spool()
        except Exception as err:  # the loop must outlive any one bad round
            print(f'  background loop error: {type(err).__name__}', file=sys.stderr)
            sys.stderr.flush()
        if stop.wait(SPOOL_REPLAY_SECONDS):
            return


# --------------------------------------------------------------------------- server

class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.kept = collections.Counter()
        self.dropped = collections.Counter()
        self.upstream = collections.Counter()
        self.started = time.time()
        # Per upstream: last success, last failure, failures in a row. /health reads these, so a dead
        # upstream shows as a 503 instead of a process that merely looks alive.
        self.state: dict[str, dict] = {}

    def add(self, decision: Decision, statuses: dict[str, int]):
        with self.lock:
            self.kept.update(decision.kept)
            self.dropped.update(decision.dropped)
            for name, status in statuses.items():
                self.upstream[f'{name}:{status}'] += 1
                st = self.state.setdefault(name, {'fail_streak': 0})
                if 200 <= status < 300:
                    st['last_ok_at'], st['fail_streak'] = time.time(), 0
                else:
                    st['last_fail_at'], st['last_fail_status'] = time.time(), status
                    st['fail_streak'] += 1

    def upstream_state(self) -> dict:
        def stamp(t):
            return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t)) if t else None
        with self.lock:
            return {name: {**st, 'last_ok': stamp(st.get('last_ok_at')), 'last_fail': stamp(st.get('last_fail_at'))}
                    for name, st in self.state.items()}

    def snapshot(self) -> dict:
        state = self.upstream_state()
        with self.lock:
            hours = max((time.time() - self.started) / 3600, 1 / 3600)
            return {
                'uptime_hours': round(hours, 3),
                'kept_spans': dict(self.kept),
                'kept_spans_per_hour': {k: round(v / hours) for k, v in self.kept.items()},
                'dropped_spans': dict(self.dropped),
                'upstream_responses': dict(self.upstream),
                'upstream_state': state,
            }


def is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def signal_guards(guard: RateGuard) -> dict[str, RateGuard]:
    """One rate guard per signal; logs and metrics add their SIGNAL_RATE_OVERRIDES."""
    return {'traces': guard,
            **{sig: RateGuard(guard.per_min, {**guard.overrides, **SIGNAL_RATE_OVERRIDES.get(sig, {})})
               for sig in ('logs', 'metrics')}}


class Collector(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, *, upstreams: list[str], guard: RateGuard,
                 keys: KeyCache, dry_run: bool, log_path: Path | None, spool: Spool | None = None):
        super().__init__(address, Handler)
        self.upstreams = upstreams
        self.guard = guard
        self.guards = signal_guards(guard)
        self.keys = keys
        self.dry_run = dry_run
        self.log_path = log_path
        self.stats = Stats()
        self.spool = spool or Spool(None)

    def deliver(self, signal: str, decision: Decision, length: int) -> tuple[dict[str, int], bool]:
        """Forward a filtered, scrubbed batch; spool it for each upstream that could not take it now."""
        statuses: dict[str, int] = {}
        spooled = False
        if decision.body and not self.dry_run:
            for name in self.upstreams:
                if name != 'signoz' and signal != 'traces':
                    continue  # only SigNoz takes logs and metrics
                try:
                    statuses[name] = forward(name, decision.body, self.keys, signal)
                except Blocked:
                    statuses[name] = -1
                if retryable(statuses[name]) and self.spool.put(name, signal, decision.body):
                    spooled = True
        self.stats.add(decision, statuses)
        row = {'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'bytes_in': length, 'kept': decision.kept, 'dropped': decision.dropped,
               'upstream': statuses, 'dry_run': self.dry_run}
        if spooled:
            row['spooled'] = True
        self.log_row(row)
        return statuses, spooled

    def replay_spool(self) -> None:
        def send(name: str, signal: str, body: bytes) -> int:
            try:
                status = forward(name, body, self.keys, signal)
            except Blocked:
                status = -1
            self.stats.add(Decision(b'', {}, {}), {name: status})
            return status
        self.spool.replay(send)

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
        if self.path in ('/stats', '/health'):
            if self.path == '/stats':
                status, data = 200, {**self.server.stats.snapshot(),
                                     'spool': dict(self.server.spool.counts)}
            else:
                data = health(self.server)
                status = 200 if data['ok'] else 503
            body = json.dumps(data, indent=2).encode()
            self.send_response(status)
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
            body = read_request_body(self.headers, self.rfile)
        except BodyError as err:
            self.close_connection = True  # whatever was not read must not be parsed as the next request
            self._reply(err.status)
            return
        length = len(body)
        try:
            decision = filter_payload(body, self.server.guards[signal], renames=SERVICE_RENAMES.get(signal))
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

        statuses, spooled = self.server.deliver(signal, decision, length)
        # A spooled batch is safe and will be replayed, so the sender is told 200 and does not resend it.
        self._reply(200 if (not statuses or spooled or any(s == 200 for s in statuses.values())) else 502)


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
            for label, exc in (('timeout', subprocess.TimeoutExpired(['x'], 10)),
                               ('subprocess error', subprocess.SubprocessError('x'))):
                subprocess.run = raiser(exc)
                check(f'_keychain_get: {label} becomes Blocked', outcome(real_get, 'svc') == 'Blocked',
                      outcome(real_get, 'svc'))
                check(f'_keychain_put: {label} does not escape', outcome(real_put, 'svc', {'h': 'v'}) == 'returned',
                      outcome(real_put, 'svc', {'h': 'v'}))
                check(f'_robot_token: {label} becomes Blocked', outcome(real_tok) == 'Blocked', outcome(real_tok))
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
            globals()['_keychain_get'], globals()['_keychain_put'] = real_get, real_put
            globals()['_robot_token'], globals()['_load_op_items'] = real_tok, real_load
    finally:
        globals()['auth_for'] = real_auth

    # launchd PATH (2026-10-21): the LaunchAgent runs with PATH=/usr/bin:/bin:/usr/sbin:/sbin and Homebrew
    # keeps op in /opt/homebrew/bin. A bare 'op' raised FileNotFoundError on every key refresh once the
    # Keychain cache expired (2026-10-20 15:31Z), so 25,267 batches were dropped. op is found by absolute path.
    import tempfile
    real_get, real_put = globals()['_keychain_get'], globals()['_keychain_put']
    real_tok, real_load = globals()['_robot_token'], globals()['_load_op_items']
    real_dirs, real_path = globals().get('OP_FALLBACK_DIRS', ()), os.environ.get('PATH', '')

    class PathOps:
        @staticmethod
        def robot_env(token):
            import contextlib
            return contextlib.nullcontext(dict(os.environ))

    def headers_outcome():
        try:
            return signoz_headers().get(SIGNOZ_HEADER)
        except Blocked:
            return 'Blocked'
        except BaseException as err:
            return type(err).__name__

    with tempfile.TemporaryDirectory() as bindir:
        fake_op = os.path.join(bindir, 'op')
        with open(fake_op, 'w') as handle:
            handle.write('#!/bin/sh\necho fake-test-key\n')
        os.chmod(fake_op, 0o700)
        try:
            os.environ['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'
            globals()['OP_FALLBACK_DIRS'] = (bindir,)
            globals()['_keychain_get'] = lambda service: None
            globals()['_keychain_put'] = lambda service, headers: None
            globals()['_robot_token'] = lambda: 'tok'
            globals()['_load_op_items'] = lambda: PathOps
            got = headers_outcome()
            check('launchd PATH: op outside PATH is found and the key is read', got == 'fake-test-key', got)
            globals()['OP_FALLBACK_DIRS'] = (os.path.join(bindir, 'missing'),)
            got = headers_outcome()
            check('launchd PATH: op missing everywhere is Blocked, not FileNotFoundError', got == 'Blocked', got)
        finally:
            os.environ['PATH'] = real_path
            globals()['OP_FALLBACK_DIRS'] = real_dirs
            globals()['_keychain_get'], globals()['_keychain_put'] = real_get, real_put
            globals()['_robot_token'], globals()['_load_op_items'] = real_tok, real_load

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

    # Key-file mode (Orgo, 2026-10-20): an owner-only file is read; a group-readable file, a
    # symlink, a missing file and a file with two lines are refused as Blocked; openclaw is allowed.
    import tempfile
    def _kf(fn, *a):
        try:
            return fn(*a)
        except Blocked:
            return 'Blocked'
    with tempfile.TemporaryDirectory() as _d:
        _good, _open, _two, _link = (os.path.join(_d, n) for n in ('good', 'open', 'two', 'link'))
        for _p, _body, _mode in ((_good, 'fake-test-key\n', 0o600), (_open, 'fake-test-key', 0o640),
                                 (_two, 'a\nb', 0o600)):
            with open(_p, 'w') as _f:
                _f.write(_body)
            os.chmod(_p, _mode)
        os.symlink(_good, _link)
        check('key file: owner-only file read', _kf(_key_file_raw, _good) == 'fake-test-key', '')
        check('key file: group-readable refused', _kf(_key_file_raw, _open) == 'Blocked', '')
        check('key file: symlink refused', _kf(_key_file_raw, _link) == 'Blocked', '')
        check('key file: missing refused', _kf(_key_file_raw, os.path.join(_d, 'none')) == 'Blocked', '')
        check('key file: two lines refused', _kf(_key_file_raw, _two) == 'Blocked', '')
        _saved = globals()['STATIC_KEY_FILE']
        globals()['STATIC_KEY_FILE'] = _good
        try:
            check('key file: signoz_headers uses it', signoz_headers() == {SIGNOZ_HEADER: 'fake-test-key'}, '')
        finally:
            globals()['STATIC_KEY_FILE'] = _saved
    _oc_res = delimited(1, delimited(1, _kv('service.name', 'openclaw')))
    _oc = delimited(1, _oc_res + delimited(2, delimited(2, delimited(5, b'openclaw.model.usage'))))
    check('openclaw is an allowed service', filter_payload(_oc, RateGuard(600, {})).kept == {'openclaw': 1}, '')

    # Renames (2026-10-20): the Codex desktop app reports codex-app-server and cannot set its own name.
    def _logs_block(service: str, n: int) -> bytes:
        res = delimited(1, delimited(1, _kv('service.name', service)))
        recs = b''.join(delimited(2, delimited(5, delimited(1, f'r{i}'.encode()))) for i in range(n))
        return delimited(1, res + delimited(2, recs))
    _ren = SERVICE_RENAMES['logs']
    d = filter_payload(_logs_block('codex-app-server', 3), RateGuard(600, {}), renames=_ren)
    check('rename: codex-app-server logs kept as task-claude', d.kept == {'task-claude': 3}, d.kept)
    _again = filter_payload(d.body, RateGuard(600, {}))
    check('rename: re-emitted body parses as task-claude and keeps the old name',
          _again.kept == {'task-claude': 3} and b'collector.renamed_from' in d.body
          and b'codex-app-server' in d.body, _again.kept)
    d = filter_payload(_logs_block('codex-worker', 2), RateGuard(600, {}),
                       renames={**_ren, 'codex-worker': 'task-claude'})
    check('rename: a blocked name stays blocked even if a rename names it',
          d.dropped == {'blocked:codex-worker': 2} and d.body == b'', d.dropped)
    d = filter_payload(_logs_block('codex_exec', 2), RateGuard(600, {}), renames=_ren)
    check('rename: other names are not renamed', d.dropped == {'unknown:codex_exec': 2}, d.dropped)
    d = filter_payload(_logs_block('codex-app-server', 2), RateGuard(600, {}))
    check('rename: traces/metrics without a rename table leave the name alone',
          d.dropped == {'unknown:codex-app-server': 2}, d.dropped)
    _g = signal_guards(RateGuard(DEFAULT_RATE_PER_MIN, RATE_OVERRIDES))
    check('logs cap for task-claude is 200/min, its traces keep the default',
          _g['logs'].limit_for('task-claude') == 200
          and _g['traces'].limit_for('task-claude') == DEFAULT_RATE_PER_MIN
          and _g['logs'].limit_for('claude-code') == DEFAULT_RATE_PER_MIN,
          {k: v.limit_for('task-claude') for k, v in _g.items()})

    # Request bodies (2026-10-20): OTel JS 0.2xx streams chunked and may gzip; both must be read in full.
    import gzip as _gzip
    import io as _io

    def _body(headers, raw):
        try:
            return read_request_body(headers, _io.BytesIO(raw))
        except BodyError as err:
            return err.status
    _pb = _oc  # a valid ExportTraceServiceRequest from the openclaw check above
    _chunked = b''.join(b'%x\r\n%s\r\n' % (len(p), p) for p in (_pb[:7], _pb[7:])) + b'0\r\n\r\nNEXT'
    check('body: Content-Length read as before', _body({'Content-Length': str(len(_pb))}, _pb) == _pb, '')
    _rf = _io.BytesIO(_chunked)
    check('body: chunked read in full, and no further',
          read_request_body({'Transfer-Encoding': 'chunked'}, _rf) == _pb and _rf.read() == b'NEXT', '')
    _gz = _gzip.compress(_pb)
    check('body: gzip inflated', _body({'Content-Length': str(len(_gz)), 'Content-Encoding': 'gzip'}, _gz) == _pb, '')
    _gzc = b'%x\r\n%s\r\n0\r\n\r\n' % (len(_gz), _gz)
    check('body: chunked + gzip', _body({'Transfer-Encoding': 'chunked', 'Content-Encoding': 'gzip'}, _gzc) == _pb, '')
    check('body: empty is 400', _body({}, b'') == 400, '')
    check('body: oversized is 413', _body({'Content-Length': str(MAX_BODY + 1)}, b'') == 413, '')
    _bomb = _gzip.compress(b'\0' * (MAX_BODY + 10))
    check('body: gzip that inflates past the cap is 413',
          _body({'Content-Length': str(len(_bomb)), 'Content-Encoding': 'gzip'}, _bomb) == 413, '')
    check('body: unknown encoding is 415', _body({'Content-Length': '3', 'Content-Encoding': 'br'}, b'abc') == 415, '')
    check('body: bad chunk size is 400', _body({'Transfer-Encoding': 'chunked'}, b'zz\r\n') == 400, '')

    # Spool, heartbeat and health (2026-10-21): nothing SigNoz could not take is lost, a dead upstream
    # turns /health red, and the heartbeat is a log the filter keeps under its own service.
    import types
    hb = heartbeat_body('test-host', {'spool.files': 0})
    check('heartbeat: parses as a log from signoz-collector',
          filter_payload(hb, RateGuard(600, {})).kept == {HEARTBEAT_SERVICE: 1}, '')
    with tempfile.TemporaryDirectory() as _sd:
        sp = Spool(Path(_sd))
        for i in range(3):
            sp.put('signoz', 'logs', b'batch%d' % i)
        calls = []
        sp.replay(lambda u, s, b: calls.append(b) or -1)
        check('spool: an outage stops replay at the first batch and keeps all', len(calls) == 1 and sp.size()[0] == 3,
              f'calls {len(calls)}, files {sp.size()[0]}')
        sent = []
        sp.replay(lambda u, s, b: sent.append((u, s, b)) or 200)
        check('spool: replays oldest first, deletes on 200',
              [b for _u, _s, b in sent] == [b'batch0', b'batch1', b'batch2'] and sent[0][:2] == ('signoz', 'logs')
              and sp.size()[0] == 0 and sp.counts['replayed'] == 3, str(sent))
        sp.put('signoz', 'traces', b'bad')
        sp.replay(lambda u, s, b: 400)
        check('spool: a batch SigNoz refuses for good (400) is dropped and counted',
              sp.size()[0] == 0 and sp.counts['rejected:400'] == 1, dict(sp.counts))
    with tempfile.TemporaryDirectory() as _sd:
        sp = Spool(Path(_sd), max_bytes=10)
        for body in (b'aaaaaa', b'bbbbbb', b'cccccc'):
            sp.put('signoz', 'logs', body)
        left = [p.read_bytes() for p in sp.pending()]
        check('spool: over the cap the oldest go first', left == [b'cccccc'] and sp.counts['evicted'] == 2, str(left))
    with tempfile.TemporaryDirectory() as _sd:
        blocked = Path(_sd) / 'file'
        blocked.write_text('x')
        sp = Spool(blocked / 'spool')  # a path under a regular file can't be made
        check('spool: a folder that cannot be made turns the spool off, the collector keeps running',
              sp.folder is None and sp.counts['dir-failed'] == 1 and sp.put('signoz', 'logs', b'x') is False,
              dict(sp.counts))
    check('paperclip-observability-test is an allowed service; paperclip has its 3000/min cap',
          'paperclip-observability-test' in KNOWN_SERVICES and RATE_OVERRIDES.get('paperclip') == 3000, '')
    real_forward = globals()['forward']
    try:
        with tempfile.TemporaryDirectory() as _sd:
            fake = types.SimpleNamespace(upstreams=['signoz'], dry_run=False, keys=KeyCache(['signoz']),
                                         spool=Spool(Path(_sd)), stats=Stats(), log_row=lambda row: None)

            def no_key(*a, **k):
                raise Blocked('signoz key not cached yet')
            globals()['forward'] = no_key
            statuses, spooled = Collector.deliver(fake, 'logs', Decision(b'body', {'logs:claude-code': 1}, {}), 4)
            check('deliver: no key is -1, spooled, and the sender gets 200',
                  statuses == {'signoz': -1} and spooled and fake.spool.size()[0] == 1, str(statuses))
            fake.stats.started -= 3600
            for _ in range(3):
                fake.stats.add(Decision(b'', {}, {}), {'signoz': -1})
            got = health(fake)
            check('health: no key and 3 failed sends is not ok, and says why',
                  not got['ok'] and any('no key' in p for p in got['problems'])
                  and any('4 sends failed in a row' in p for p in got['problems']) and got['spool_files'] == 1, str(got))
            globals()['forward'] = lambda *a, **k: 200
            fake.keys.cache['signoz'] = ('v', fake.keys.clock())
            Collector.replay_spool(fake)
            got = health(fake)
            check('health: key back and a 200 is ok, spool drained', got['ok'] and got['spool_files'] == 0, str(got))
    finally:
        globals()['forward'] = real_forward

    # The plist names the robot token's Keychain item (2026-10-21); the reader asks security(1) for that item.
    real_run, real_env = subprocess.run, os.environ.get(ROBOT_TOKEN_ENV)
    seen_args = []

    def fake_security(args, **kwargs):
        seen_args.append(args)
        return types.SimpleNamespace(returncode=0, stdout='fake-token\n')
    try:
        subprocess.run = fake_security
        os.environ[ROBOT_TOKEN_ENV] = 'plist-named-item'
        got = _robot_token()
        check('robot token: the Keychain item named in the plist is the one read',
              got == 'fake-token' and seen_args and seen_args[-1][seen_args[-1].index('-s') + 1] == 'plist-named-item',
              str(seen_args[-1:]))
        os.environ.pop(ROBOT_TOKEN_ENV)
        _robot_token()
        check('robot token: no plist entry falls back to the code default',
              seen_args[-1][seen_args[-1].index('-s') + 1] == ROBOT_TOKEN_SERVICE, str(seen_args[-1:]))
    finally:
        subprocess.run = real_run
        if real_env is None:
            os.environ.pop(ROBOT_TOKEN_ENV, None)
        else:
            os.environ[ROBOT_TOKEN_ENV] = real_env

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
    parser.add_argument('--key-file', default=None, metavar='PATH',
                        help='read the SigNoz key from this owner-only file (Linux; no Keychain, no 1Password)')
    parser.add_argument('--spool-dir', default=str(SPOOL_DIR),
                        help='where batches SigNoz could not take wait for replay; "" turns the spool off')
    parser.add_argument('--host-name', default=None,
                        help='host.name on the heartbeat (default: the Mac\'s LocalHostName, else the short hostname)')
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if args.key_keychain:
        globals()['STATIC_KEY_SERVICE'] = args.key_keychain
    if args.key_file:
        globals()['STATIC_KEY_FILE'] = args.key_file

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

    args.host_name = args.host_name or default_host_name()
    spool = Spool(Path(args.spool_dir) if args.spool_dir and upstreams and not args.dry_run else None)
    server = Collector(('127.0.0.1', args.port), upstreams=upstreams, guard=guard, keys=keys,
                       dry_run=args.dry_run, log_path=Path(args.log) if args.log else None, spool=spool)
    print(f'  listening on 127.0.0.1:{server.server_address[1]}/v1/traces')
    print(f'  spool: {spool.folder or "(off)"}, max {SPOOL_MAX_BYTES // (1024 * 1024)} MB; '
          f'heartbeat every {HEARTBEAT_SECONDS}s as {HEARTBEAT_SERVICE} host {args.host_name}')
    print(f'  health: GET http://127.0.0.1:{server.server_address[1]}/health (503 when SigNoz is not getting data)')
    print(f'  upstreams: {", ".join(upstreams) or "(none, dry run)"}')
    print(f'  rate guard: {args.rate_per_min} spans/min per service')
    print(f'  blocked: {", ".join(BLOCKED_SERVICES)}')
    print(f'  renames: {SERVICE_RENAMES}')
    print(f'  per-signal caps: {SIGNAL_RATE_OVERRIDES}')
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
        threading.Thread(target=background_loop, args=(server, stop, args.host_name), daemon=True,
                         name='heartbeat-spool').start()

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

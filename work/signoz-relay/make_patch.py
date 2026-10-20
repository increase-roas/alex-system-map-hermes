#!/usr/bin/env python3
"""Build otlp_relay.PATCHED.py from otlp_relay.ORIGINAL.py by explicit anchored edits.

Generated rather than hand-written so every change is a named, reviewable edit against
an exact anchor. If an anchor is missing the build fails loudly instead of producing a
half-patched file: that is the whole point.

Run: python3 -B work/signoz-relay/make_patch.py
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE / 'otlp_relay.ORIGINAL.py'
PATCHED = HERE / 'otlp_relay.PATCHED.py'
DIFF = HERE / 'otlp_relay.patch'

# The relay this patch was built against. The apply worker must confirm this hash
# before applying, or the anchors may no longer mean what they meant here.
EXPECTED_SHA256 = '90e6dd0a0944003cf05f47ad2c6bd09627fa47eab4548d043d02644723768417'

EDITS: list[tuple[str, str, str]] = []


def edit(name: str, old: str, new: str) -> None:
    EDITS.append((name, old, new))


# --------------------------------------------------------------------- 1. constants
edit(
    'constants: SigNoz upstream, policy lists, rate ceiling',
    '''UPSTREAM = "https://us.cloud.langfuse.com/api/public/otel/v1/traces"
MAX_BODY = 16 * 1024 * 1024''',
    '''UPSTREAM = "https://us.cloud.langfuse.com/api/public/otel/v1/traces"
# SigNoz is now the tracing home; this relay is the one local collector for this Mac.
# Agents never hold the SigNoz key: they post to loopback and the key is read here.
SIGNOZ_UPSTREAM = "https://ingest.us2.signoz.cloud/v1/traces"
SIGNOZ_HEADER = "signoz-ingestion-key"
# 1Password: vault Connectors, item "SigNoz ingestion key", field credential.
SIGNOZ_OP_REF = "op://Connectors/hfy4llw7gassge2w5xuz64kgyu/credential"
OP_BIN = "/opt/homebrew/bin/op"

# Policy. Spans are grouped per resource; a group is kept only if it is named, allowed
# and inside its budget. Nothing unnamed is forwarded: SigNoz accepts a span with no
# resource attributes at all (HTTP 200, 2026-10-20), so the drop has to happen here.
KNOWN_SERVICES = (
    "claude-code", "codex", "cursor", "javar", "javante", "auditor",
    "task-codex", "task-claude", "paperclip-worker", "paperclip-reviewer",
    "dynamite-chatbot", "alex-system-map",
)
# The ChatGPT app's built-in Codex. It sent ~4.7M labelled events a week into Langfuse
# with no per-run session id; Alex switched it off on 2026-10-19. Refused here too, so
# re-enabling it upstream cannot quietly restart the flood.
BLOCKED_SERVICES = ("codex-worker",)

# Spans per minute per service, with its own bucket each, so one sender cannot flood
# the account and cannot starve another. The ceiling is set from measured rates: the
# 2026-10-19 flood ran at 0.9M-1.4M observations an hour (about 15,000-23,000 a minute)
# from spans that WERE labelled, while Claude Code's honest rate over the same week was
# roughly 11 a minute. 600 leaves nearly two orders of magnitude of headroom above
# normal use and still stops a runaway inside a minute. Raise a single service in
# RATE_OVERRIDES deliberately, with its reason, rather than lifting the ceiling.
RATE_PER_MIN = 600
RATE_OVERRIDES = {}

MAX_BODY = 16 * 1024 * 1024''',
)

# --------------------------------------------------------------------- 2. protobuf + policy
edit(
    'policy: minimal OTLP reader, rate guard, payload filter',
    '''def is_loopback(host):''',
    '''def read_varint(buf, index):
    shift = 0
    value = 0
    while True:
        if index >= len(buf):
            raise ValueError("truncated varint")
        byte = buf[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, index
        shift += 7
        if shift > 63:
            raise ValueError("varint too long")


def iter_fields(buf):
    """Yield (field_number, wire_type, payload) over one protobuf message."""
    index = 0
    while index < len(buf):
        key, index = read_varint(buf, index)
        field, wire = key >> 3, key & 0x7
        if wire == 0:
            value, index = read_varint(buf, index)
            yield field, wire, value
        elif wire == 1:
            yield field, wire, buf[index:index + 8]
            index += 8
        elif wire == 2:
            length, index = read_varint(buf, index)
            if index + length > len(buf):
                raise ValueError("truncated length-delimited field")
            yield field, wire, buf[index:index + length]
            index += length
        elif wire == 5:
            yield field, wire, buf[index:index + 4]
            index += 4
        else:
            raise ValueError("unsupported wire type")


def encode_varint(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def delimited(field, payload):
    return encode_varint((field << 3) | 2) + encode_varint(len(payload)) + payload


def service_name_of(resource):
    """service.name from a Resource message, or '' when absent or empty.

    Resource.attributes = field 1 (repeated KeyValue); KeyValue.key = field 1,
    KeyValue.value = field 2 (AnyValue); AnyValue.string_value = field 1.
    """
    for field, wire, payload in iter_fields(resource):
        if field != 1 or wire != 2:
            continue
        key = value = None
        for key_field, key_wire, key_payload in iter_fields(payload):
            if key_field == 1 and key_wire == 2:
                key = key_payload
            elif key_field == 2 and key_wire == 2:
                for any_field, any_wire, any_payload in iter_fields(key_payload):
                    if any_field == 1 and any_wire == 2:
                        value = any_payload
                        break
        if key == b"service.name" and value:
            try:
                return value.decode("utf-8").strip()
            except UnicodeDecodeError:
                return ""
    return ""


def count_spans(resource_spans):
    """ResourceSpans.scope_spans = field 2; ScopeSpans.spans = field 2."""
    total = 0
    for field, wire, payload in iter_fields(resource_spans):
        if field == 2 and wire == 2:
            for scope_field, scope_wire, _ in iter_fields(payload):
                if scope_field == 2 and scope_wire == 2:
                    total += 1
    return total


class RateGuard:
    """One token bucket per service. Refills continuously; never blocks a thread."""

    def __init__(self, per_min=RATE_PER_MIN, overrides=None, clock=time.monotonic):
        self.per_min = per_min
        self.overrides = dict(overrides or RATE_OVERRIDES)
        self.clock = clock
        self.lock = threading.Lock()
        self.state = {}

    def limit_for(self, service):
        return self.overrides.get(service, self.per_min)

    def allow(self, service, spans):
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


def filter_payload(body, guard, known=KNOWN_SERVICES, blocked=BLOCKED_SERVICES):
    """Return (kept_body, kept_counts, dropped_counts).

    Counts only. No span name, attribute or body text is ever recorded or logged.
    """
    kept_counts = {}
    dropped = {}

    def bump(table, key, spans):
        table[key] = table.get(key, 0) + spans

    out = bytearray()
    for field, wire, payload in iter_fields(body):
        if field != 1 or wire != 2:
            continue  # ExportTraceServiceRequest.resource_spans only
        resource = b""
        for res_field, res_wire, res_payload in iter_fields(payload):
            if res_field == 1 and res_wire == 2:
                resource = res_payload
                break
        service = service_name_of(resource)
        spans = count_spans(payload)
        if not service:
            bump(dropped, "unnamed", spans)
            continue
        if service in blocked:
            bump(dropped, "blocked:" + service, spans)
            continue
        if known and service not in known:
            bump(dropped, "unknown:" + service, spans)
            continue
        if not guard.allow(service, spans):
            bump(dropped, "throttled:" + service, spans)
            continue
        bump(kept_counts, service, spans)
        out += delimited(1, payload)
    return bytes(out), kept_counts, dropped


def validate_signoz_headers(headers):
    """SigNoz authenticates with its own header, not Authorization.

    HeaderCache's default validator is validate_headers, which REQUIRES an
    authorization header and injects the Langfuse ingestion version. Neither is
    correct here, so the SigNoz cache gets this validator instead. Found by the
    acceptance test: reusing the Langfuse validator made every SigNoz send fail
    with "missing auth header" while the relay still answered 200.
    """
    if not isinstance(headers, dict) or not headers:
        raise ValueError("empty headers")
    for key, value in headers.items():
        if not isinstance(key, str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key):
            raise ValueError("invalid header name")
        if not isinstance(value, str) or not value.strip() or any(c in value for c in "\\r\\n\\0"):
            raise ValueError("invalid header value")
    if not any(key.lower() == SIGNOZ_HEADER for key in headers):
        raise ValueError("missing signoz ingestion key")
    return {key.lower(): value for key, value in headers.items()}


def fetch_signoz_key(op_bin=None):
    """SigNoz ingestion key, read from 1Password at run time. Never logged or printed."""
    token_helper = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-a", "connectors-sync",
         "-s", "op-service-account-connectors-sync", "-w"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=HELPER_TIMEOUT)
    if token_helper.returncode:
        raise ValueError("signoz key helper unavailable")
    env = {
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        "HOME": os.environ.get("HOME", ""),
        "OP_SERVICE_ACCOUNT_TOKEN": token_helper.stdout.decode("utf-8").strip(),
        "OP_BIOMETRIC_UNLOCK_ENABLED": "false",
    }
    read = subprocess.run([op_bin or OP_BIN, "read", SIGNOZ_OP_REF],
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, timeout=HELPER_TIMEOUT, env=env)
    if read.returncode:
        raise ValueError("signoz key helper unavailable")
    key = read.stdout.decode("utf-8").strip()
    if not key or any(char in key for char in "\\r\\n\\0"):
        raise ValueError("invalid signoz key")
    return {SIGNOZ_HEADER: key}


def is_loopback(host):''',
)

# --------------------------------------------------------------------- 3. server wiring
edit(
    'server: accept the SigNoz destination and hold both key caches',
    '''        if upstream_url != UPSTREAM and not (''',
    '''        if upstream_url not in (UPSTREAM, SIGNOZ_UPSTREAM) and not (''',
)

edit(
    'HeaderCache: allow a per-destination validator',
    '''class HeaderCache:
    def __init__(self, loader, clock=time.monotonic, stopping=None):
        self.loader = loader
        self.clock = clock
        self.lock = threading.Lock()
        self.headers = None
        self.expires = 0.0
        self.stopping = stopping''',
    '''class HeaderCache:
    def __init__(self, loader, clock=time.monotonic, stopping=None, validator=None):
        self.loader = loader
        self.clock = clock
        self.lock = threading.Lock()
        self.headers = None
        self.expires = 0.0
        self.stopping = stopping
        # Langfuse and SigNoz authenticate differently, so each cache validates with
        # its own rule. Default stays validate_headers so the Langfuse path is unchanged.
        self.validator = validator or validate_headers''',
)

edit(
    'HeaderCache: validate with the cache\'s own validator',
    '''        self.headers = None
        headers = validate_headers(self.loader())''',
    '''        self.headers = None
        headers = self.validator(self.loader())''',
)

edit(
    'server: SigNoz sender, rate guard, mirror switch',
    '''        self.header_cache = HeaderCache(header_loader or fetch_headers, stopping=self.stopping)''',
    '''        self.header_cache = HeaderCache(header_loader or fetch_headers, stopping=self.stopping)
        # SigNoz is the primary destination; Langfuse is a mirror during the
        # side-by-side day and takes NAMED services only, never the dropped ones.
        # Validated exactly as strictly as the Langfuse upstream above: the only
        # alternate destination is an explicitly injected loopback test server.
        if signoz_url is not None:
            signoz_parsed = urlsplit(signoz_url)
            if signoz_url != SIGNOZ_UPSTREAM and not (
                signoz_parsed.scheme == "http" and signoz_parsed.hostname
                and is_loopback(signoz_parsed.hostname) and not signoz_parsed.username
                and not signoz_parsed.password and not signoz_parsed.fragment
            ):
                raise ValueError("invalid signoz upstream")
            self.signoz_target = signoz_parsed
        else:
            self.signoz_target = None
        self.signoz_cache = HeaderCache(signoz_loader or fetch_signoz_key,
                                        stopping=self.stopping,
                                        validator=validate_signoz_headers)
        self.mirror_langfuse = mirror_langfuse
        self.guard = guard or RateGuard()''',
)

edit(
    'server: signature',
    '''    def __init__(self, address, *, log_path=None, header_loader=None, upstream_url=UPSTREAM):''',
    '''    def __init__(self, address, *, log_path=None, header_loader=None, upstream_url=UPSTREAM,
                 signoz_url=SIGNOZ_UPSTREAM, signoz_loader=None, mirror_langfuse=True,
                 guard=None):''',
)

# --------------------------------------------------------------------- 4. log row
edit(
    'log: carry kept and dropped counts, never content',
    '''    def log_request_row(self, status, bytes_in, upstream_ms):
        row = {"ts": datetime.now(timezone.utc).isoformat(), "status": status,
               "bytes_in": bytes_in, "upstream_ms": upstream_ms}''',
    '''    def log_request_row(self, status, bytes_in, upstream_ms, kept=None, dropped=None):
        row = {"ts": datetime.now(timezone.utc).isoformat(), "status": status,
               "bytes_in": bytes_in, "upstream_ms": upstream_ms}
        # Counts only. A service name is a configured label, never request content.
        if kept:
            row["kept"] = kept
        if dropped:
            row["dropped"] = dropped''',
)

# --------------------------------------------------------------------- 5. sending
edit(
    'send: let _send_upstream target either destination',
    '''    def _send_upstream(self, body, headers):
        factory = http.client.HTTPSConnection if self.target.scheme == "https" else http.client.HTTPConnection
        connection = factory(self.target.hostname, self.target.port, timeout=IO_TIMEOUT)''',
    '''    def _send_upstream(self, body, headers, target=None):
        target = target or self.target
        factory = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
        connection = factory(target.hostname, target.port, timeout=IO_TIMEOUT)''',
)

edit(
    'send: use the chosen target for path and query',
    '''            path = self.target.path or "/"
            if self.target.query:
                path += "?" + self.target.query''',
    '''            path = target.path or "/"
            if target.query:
                path += "?" + target.query''',
)

edit(
    'forward: filter first, send to SigNoz, mirror named spans to Langfuse',
    '''    def forward(self, body, content_headers):
        upstream_ms = 0.0
        if self.stopping.is_set():
            return 503, b"upstream unavailable\\n", upstream_ms''',
    '''    def forward_filtered(self, body, content_headers):
        """Apply policy, then fan out. Returns (status, response, ms, kept, dropped)."""
        try:
            kept_body, kept, dropped = filter_payload(body, self.guard)
        except ValueError:
            return 400, b"invalid payload\\n", 0.0, {}, {"malformed": 1}
        if not kept_body:
            # Everything was dropped on purpose. Accept so the sender does not retry
            # forever, and record why in counts.
            return 200, b"", 0.0, kept, dropped
        status, response, upstream_ms = self._forward_to(
            self.signoz_target, self.signoz_cache, kept_body, content_headers)
        if self.mirror_langfuse:
            try:
                mirror_status, _mirror_body, mirror_ms = self._forward_to(
                    self.target, self.header_cache, kept_body, content_headers)
                upstream_ms = round(upstream_ms + mirror_ms, 3)
                dropped = dict(dropped)
                if mirror_status != 200:
                    dropped["mirror_status:" + str(mirror_status)] = 1
            except Exception:
                dropped = dict(dropped)
                dropped["mirror_failed"] = 1
        return status, response, upstream_ms, kept, dropped

    def forward(self, body, content_headers):
        return self._forward_to(self.target, self.header_cache, body, content_headers)

    def _forward_to(self, target, cache, body, content_headers):
        upstream_ms = 0.0
        if self.stopping.is_set():
            return 503, b"upstream unavailable\\n", upstream_ms''',
)

edit(
    'forward: read headers from the chosen cache',
    '''        try:
            headers = self.header_cache.get()
        except Exception:
            return 502, b"header helper unavailable\\n", upstream_ms''',
    '''        if target is None:
            return 503, b"upstream unavailable\\n", upstream_ms
        try:
            headers = cache.get()
        except Exception:
            return 502, b"header helper unavailable\\n", upstream_ms''',
)

edit(
    'forward: send and refresh against the chosen target and cache',
    '''            start = time.monotonic()
            try:
                status, response = self._send_upstream(body, dict(headers, **content_headers))
            except Exception:''',
    '''            start = time.monotonic()
            try:
                status, response = self._send_upstream(
                    body, dict(headers, **content_headers), target=target)
            except Exception:''',
)

edit(
    'forward: refresh the chosen cache on 401/403',
    '''            try:
                headers = self.header_cache.refresh(headers)
            except Exception:
                return 502, b"header helper unavailable\\n", round(upstream_ms, 3)''',
    '''            try:
                headers = cache.refresh(headers)
            except Exception:
                return 502, b"header helper unavailable\\n", round(upstream_ms, 3)''',
)

# --------------------------------------------------------------------- 6. handler
edit(
    'handler: carry counts into the log row',
    '''    def setup(self):
        self.request.settimeout(IO_TIMEOUT)
        self.bytes_in = 0
        self.upstream_ms = 0.0
        super().setup()''',
    '''    def setup(self):
        self.request.settimeout(IO_TIMEOUT)
        self.bytes_in = 0
        self.upstream_ms = 0.0
        self.kept = None
        self.dropped = None
        super().setup()''',
)

edit(
    'handler: log the counts',
    '''        self.server.log_request_row(status, self.bytes_in, self.upstream_ms)''',
    '''        self.server.log_request_row(status, self.bytes_in, self.upstream_ms,
                                    getattr(self, "kept", None), getattr(self, "dropped", None))''',
)

edit(
    'handler: route POST through the filter',
    '''        status, response, self.upstream_ms = self.server.forward(body, content_headers)
        self.respond(status, response)''',
    '''        (status, response, self.upstream_ms,
         self.kept, self.dropped) = self.server.forward_filtered(body, content_headers)
        self.respond(status, response)''',
)

# --------------------------------------------------------------------- 7. imports + cli
edit(
    'imports: subprocess is already imported; add nothing. CLI: a no-mirror switch',
    '''    parser.add_argument("--check", action="store_true", help="Check headers without starting a server")''',
    '''    parser.add_argument("--check", action="store_true", help="Check headers without starting a server")
    parser.add_argument("--no-langfuse-mirror", action="store_true",
                        help="stop mirroring to Langfuse (use after the side-by-side day)")''',
)

edit(
    'cli: pass the mirror switch through',
    '''        server = RelayServer(("127.0.0.1", port))''',
    '''        server = RelayServer(("127.0.0.1", port),
                             mirror_langfuse=not args.no_langfuse_mirror)''',
)


def main() -> int:
    if not ORIGINAL.exists():
        print(f'missing {ORIGINAL}', file=sys.stderr)
        return 2
    source = ORIGINAL.read_text()
    actual = hashlib.sha256(source.encode()).hexdigest()
    if actual != EXPECTED_SHA256:
        print(f'ORIGINAL sha256 is {actual}, expected {EXPECTED_SHA256}', file=sys.stderr)
        print('The relay changed since this patch was built. Rebuild the anchors.', file=sys.stderr)
        return 2

    out = source
    for name, old, new in EDITS:
        count = out.count(old)
        if count != 1:
            print(f'FAILED anchor ({count} matches, need exactly 1): {name}', file=sys.stderr)
            return 2
        out = out.replace(old, new, 1)
        print(f'  applied: {name}')

    PATCHED.write_text(out)
    print(f'\nwrote {PATCHED.name}  ({len(out.splitlines())} lines, was {len(source.splitlines())})')
    print(f'  sha256 {hashlib.sha256(out.encode()).hexdigest()}')

    proc = subprocess.run(['diff', '-u', str(ORIGINAL), str(PATCHED)],
                          capture_output=True, text=True)
    DIFF.write_text(proc.stdout)
    print(f'wrote {DIFF.name}  ({len(proc.stdout.splitlines())} diff lines)')

    syntax = subprocess.run([sys.executable, '-m', 'py_compile', str(PATCHED)],
                            capture_output=True, text=True)
    if syntax.returncode:
        print('PATCHED does not compile:', file=sys.stderr)
        print(syntax.stderr, file=sys.stderr)
        return 1
    print('PATCHED compiles cleanly')
    return 0


if __name__ == '__main__':
    sys.exit(main())

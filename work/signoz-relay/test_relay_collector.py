#!/usr/bin/env python3
"""Acceptance tests for the patched relay, against a disposable copy. No network.

Runs the real patched relay on a loopback port, with two fake loopback upstreams
standing in for SigNoz and Langfuse, and real OTLP protobuf bodies on the wire. The
patched relay's own validation permits a loopback http destination for exactly this.

Nothing here reaches SigNoz, Langfuse, 1Password or the login Keychain: both key
loaders are injected.

Run: python3 -B work/signoz-relay/test_relay_collector.py
"""
from __future__ import annotations

import importlib.util
import json
import secrets
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCHED = HERE / 'otlp_relay.PATCHED.py'

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = '') -> None:
    CHECKS.append((name, bool(ok), detail))


def load_relay():
    """Import the disposable patched copy under its own module name."""
    spec = importlib.util.spec_from_file_location('relay_patched', PATCHED)
    module = importlib.util.module_from_spec(spec)
    sys.modules['relay_patched'] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------- OTLP builders

def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _key(field: int, wire: int) -> bytes:
    return _varint((field << 3) | wire)


def _d(field: int, payload: bytes) -> bytes:
    return _key(field, 2) + _varint(len(payload)) + payload


def _kv(key: str, val: str) -> bytes:
    return _d(1, key.encode()) + _d(2, _d(1, val.encode()))


def _span(name: str) -> bytes:
    now = time.time_ns()
    return b''.join([
        _d(1, secrets.token_bytes(16)), _d(2, secrets.token_bytes(8)),
        _d(5, name.encode()), _key(6, 0) + _varint(1),
        _key(7, 1) + struct.pack('<Q', now),
        _key(8, 1) + struct.pack('<Q', now + 1_000_000),
    ])


def resource_spans(service, n=1, attrs=True):
    """One ResourceSpans. service=None means no resource attributes at all."""
    if service is None:
        resource = b''
    else:
        resource = _d(1, _kv('service.name', service))
        if attrs:
            resource += _d(1, _kv('host.name', 'macbook'))
    scope = _d(2, b''.join(_d(2, _span(f'sp{i}')) for i in range(n)))
    return _d(1, _d(1, resource) + scope)


# --------------------------------------------------------------------- fake upstreams

class Sink(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, status=200):
        super().__init__(('127.0.0.1', 0), SinkHandler)
        self.status_to_return = status
        self.lock = threading.Lock()
        self.bodies: list[bytes] = []
        self.headers_seen: list[dict] = []

    @property
    def url(self) -> str:
        return f'http://127.0.0.1:{self.server_address[1]}/v1/traces'

    def record(self, body: bytes, headers: dict) -> None:
        with self.lock:
            self.bodies.append(body)
            self.headers_seen.append(headers)

    def count(self) -> int:
        with self.lock:
            return len(self.bodies)


class SinkHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length) if length else b''
        self.server.record(body, dict(self.headers))
        self.send_response(self.server.status_to_return)
        self.send_header('Content-Length', '0')
        self.end_headers()


def post(port: int, body: bytes, path: str = '/v1/traces', headers=None):
    req = urllib.request.Request(
        f'http://127.0.0.1:{port}{path}', data=body, method='POST',
        headers=headers or {'Content-Type': 'application/x-protobuf'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


# --------------------------------------------------------------------- harness

class Harness:
    def __init__(self, relay, *, mirror=True, rate=600, log_path=None, signoz_status=200):
        self.signoz = Sink(signoz_status)
        self.langfuse = Sink()
        for sink in (self.signoz, self.langfuse):
            threading.Thread(target=sink.serve_forever, daemon=True).start()
        self.log_path = log_path
        self.server = relay.RelayServer(
            ('127.0.0.1', 0),
            log_path=str(log_path) if log_path else None,
            header_loader=lambda: {'Authorization': 'Basic test-langfuse-not-a-real-key'},
            upstream_url=self.langfuse.url,
            signoz_url=self.signoz.url,
            signoz_loader=lambda: {relay.SIGNOZ_HEADER: 'test-signoz-not-a-real-key'},
            mirror_langfuse=mirror,
            guard=relay.RateGuard(per_min=rate),
        )
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
        self.thread.start()
        time.sleep(0.25)

    def close(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        for sink in (self.signoz, self.langfuse):
            sink.shutdown()
            sink.server_close()

    def log_rows(self):
        if not self.log_path or not Path(self.log_path).exists():
            return []
        return [json.loads(line) for line in Path(self.log_path).read_text().splitlines() if line]


def main() -> int:
    if not PATCHED.exists():
        print(f'missing {PATCHED}; run make_patch.py first', file=sys.stderr)
        return 2
    relay = load_relay()

    # ---------------------------------------------------------------- unit: filter
    guard = relay.RateGuard(per_min=600)
    body, kept, dropped = relay.filter_payload(resource_spans('claude-code', 3), guard)
    check('named service kept', kept == {'claude-code': 3} and body, f'kept={kept}')

    body, kept, dropped = relay.filter_payload(resource_spans(None, 2), relay.RateGuard(600))
    check('no resource attributes at all -> dropped unnamed',
          dropped == {'unnamed': 2} and body == b'', f'dropped={dropped}')

    body, kept, dropped = relay.filter_payload(resource_spans('', 2), relay.RateGuard(600))
    check('empty service.name -> dropped unnamed',
          dropped == {'unnamed': 2} and body == b'', f'dropped={dropped}')

    body, kept, dropped = relay.filter_payload(resource_spans('codex-worker', 5), relay.RateGuard(600))
    check('codex-worker refused outright',
          dropped == {'blocked:codex-worker': 5} and body == b'', f'dropped={dropped}')

    body, kept, dropped = relay.filter_payload(resource_spans('typo-agent', 1), relay.RateGuard(600))
    check('unknown name counted, never silently kept',
          dropped == {'unknown:typo-agent': 1}, f'dropped={dropped}')

    tiny = relay.RateGuard(per_min=10)
    _b1, k1, _d1 = relay.filter_payload(resource_spans('claude-code', 10), tiny)
    _b2, _k2, d2 = relay.filter_payload(resource_spans('claude-code', 10), tiny)
    check('rate guard passes the first burst', k1 == {'claude-code': 10}, f'kept={k1}')
    check('rate guard trips on the flood', d2 == {'throttled:claude-code': 10}, f'dropped={d2}')

    shared = relay.RateGuard(per_min=10)
    relay.filter_payload(resource_spans('claude-code', 10), shared)
    _b, k3, _d = relay.filter_payload(resource_spans('codex', 5), shared)
    check('a throttled sender cannot starve another', k3 == {'codex': 5}, f'kept={k3}')

    mixed = resource_spans('claude-code', 1) + resource_spans(None, 4) + resource_spans('codex', 2)
    body, kept, dropped = relay.filter_payload(mixed, relay.RateGuard(600))
    check('mixed batch: named kept, unnamed dropped',
          kept == {'claude-code': 1, 'codex': 2} and dropped == {'unnamed': 4},
          f'kept={kept} dropped={dropped}')
    _b, rekept, _d = relay.filter_payload(body, relay.RateGuard(600))
    check('re-emitted body is still parseable OTLP',
          rekept == {'claude-code': 1, 'codex': 2}, f'kept={rekept}')

    try:
        relay.filter_payload(b'\xff\xff\xff\xff', relay.RateGuard(600))
        malformed_raised = False
    except ValueError:
        malformed_raised = True
    check('malformed protobuf raises rather than forwarding', malformed_raised)

    # ---------------------------------------------------------------- destination guard
    try:
        relay.RelayServer(('127.0.0.1', 0), signoz_url='https://evil.example.com/v1/traces')
        refused = False
    except ValueError:
        refused = True
    check('a non-loopback, non-SigNoz destination is refused', refused)

    # ---------------------------------------------------------------- end to end
    log = HERE / 'test-relay.jsonl'
    if log.exists():
        log.unlink()
    harness = Harness(relay, mirror=True, rate=600, log_path=log)
    try:
        status, _ = post(harness.port, resource_spans('codex', 2))
        time.sleep(0.4)
        check('named span: relay answers 200', status == 200, f'status={status}')
        check('named span reaches SigNoz', harness.signoz.count() == 1,
              f'signoz bodies={harness.signoz.count()}')
        check('named span is mirrored to Langfuse', harness.langfuse.count() == 1,
              f'langfuse bodies={harness.langfuse.count()}')
        sent = harness.signoz.bodies[0] if harness.signoz.bodies else b""
        _b, arrived, _d = relay.filter_payload(sent, relay.RateGuard(600))
        check('what SigNoz received is the named span', arrived == {'codex': 2}, f'{arrived}')
        check('SigNoz got the ingestion-key header',
              any(relay.SIGNOZ_HEADER in {k.lower(): v for k, v in h.items()}
                  for h in harness.signoz.headers_seen))
        check('Langfuse got Authorization, not the SigNoz header',
              any('authorization' in {k.lower() for k in h} for h in harness.langfuse.headers_seen)
              and not any(relay.SIGNOZ_HEADER in {k.lower() for k in h}
                          for h in harness.langfuse.headers_seen))

        before_signoz, before_langfuse = harness.signoz.count(), harness.langfuse.count()
        status, _ = post(harness.port, resource_spans(None, 3))
        time.sleep(0.4)
        check('unnamed span: relay still answers 200 (no retry storm)', status == 200,
              f'status={status}')
        check('unnamed span never reaches SigNoz', harness.signoz.count() == before_signoz,
              f'{harness.signoz.count()} vs {before_signoz}')
        check('unnamed span never reaches Langfuse', harness.langfuse.count() == before_langfuse)

        status, _ = post(harness.port, resource_spans('codex-worker', 4))
        time.sleep(0.4)
        check('codex-worker never leaves the machine',
              harness.signoz.count() == before_signoz and harness.langfuse.count() == before_langfuse)

        # contract the original relay had, which must survive the patch
        status, _ = post(harness.port, b'x', path='/not-traces')
        check('wrong path still 404', status == 404, f'status={status}')
        status, _ = post(harness.port, resource_spans('codex', 1),
                         headers={'Content-Type': 'application/x-protobuf',
                                  'Transfer-Encoding': 'chunked'})
        check('chunked framing still refused', status == 400, f'status={status}')

        rows = harness.log_rows()
        kept_rows = [r for r in rows if r.get('kept')]
        dropped_rows = [r for r in rows if r.get('dropped')]
        check('log row carries kept counts', bool(kept_rows), f'rows={len(rows)}')
        check('log row carries dropped counts', bool(dropped_rows))
        check('drop counter shows the unnamed drop',
              any(r['dropped'].get('unnamed') == 3 for r in dropped_rows),
              f'{[r.get("dropped") for r in dropped_rows]}')
        check('drop counter shows codex-worker blocked',
              any(r['dropped'].get('blocked:codex-worker') == 4 for r in dropped_rows))
        raw = log.read_text()
        check('no key value anywhere in the log',
              'test-signoz-not-a-real-key' not in raw and 'test-langfuse-not-a-real-key' not in raw)
        check('no span name in the log', 'sp0' not in raw and 'signoz-hookup' not in raw)
    finally:
        harness.close()

    # ---------------------------------------------------------------- mirror off
    harness = Harness(relay, mirror=False, rate=600)
    try:
        post(harness.port, resource_spans('codex', 1))
        time.sleep(0.4)
        check('--no-langfuse-mirror: SigNoz still gets it', harness.signoz.count() == 1)
        check('--no-langfuse-mirror: Langfuse gets nothing', harness.langfuse.count() == 0)
    finally:
        harness.close()

    # ---------------------------------------------------------------- SigNoz failing
    harness = Harness(relay, mirror=False, rate=600, signoz_status=500)
    try:
        status, _ = post(harness.port, resource_spans('codex', 1))
        time.sleep(0.4)
        check('a failing SigNoz is reported upstream, not hidden', status == 500, f'status={status}')
    finally:
        harness.close()

    width = max(len(n) for n, _ok, _d in CHECKS)
    for name, ok, detail in CHECKS:
        line = f'  {"pass" if ok else "FAIL"}  {name:{width}}'
        print(line if ok else line + f'   <- {detail}')
    failed = [n for n, ok, _d in CHECKS if not ok]
    print()
    print(f'{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed')
    if failed:
        print('FAILED: ' + '; '.join(failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())

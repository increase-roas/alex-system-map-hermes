#!/usr/bin/env python3
"""Loopback-only OTLP/HTTP trace relay. Credentials exist only in captured pipes/memory.

The existing helper owns its login-Keychain cache; do not pass --no-cache here.
No request/exception/header/body text is ever logged. Python 3.9+, stdlib only.
"""
from datetime import datetime, timezone
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

UPSTREAM = "https://us.cloud.langfuse.com/api/public/otel/v1/traces"
MAX_BODY = 16 * 1024 * 1024
MAX_RESPONSE = 64 * 1024
HEADER_TTL = 3600
HELPER_TIMEOUT = 10
IO_TIMEOUT = 30


def is_loopback(host):
    # Numeric addresses only: no DNS rebinding or hostname-dependent validation.
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_headers(headers):
    """Same checks as codex_traced.fetch_headers, without its --no-cache policy."""
    if not isinstance(headers, dict) or not headers:
        raise ValueError("empty headers")
    for key, value in headers.items():
        if not isinstance(key, str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key):
            raise ValueError("invalid header name")
        if not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n\0"):
            raise ValueError("invalid header value")
    if not any(key.lower() == "authorization" for key in headers):
        raise ValueError("missing auth header")
    normalized = {key.lower(): value for key, value in headers.items()}
    normalized["x-langfuse-ingestion-version"] = "4"
    return normalized


def fetch_headers():
    helper = Path.home() / ".agents/tools/connectors/langfuse_otel_headers.py"
    # Suppress helper stderr, capture stdout, and reap its whole process group on
    # timeout. Never print subprocess/JSON exceptions: they may contain credentials.
    with subprocess.Popen([sys.executable, "-B", str(helper)], stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          start_new_session=True) as process:
        try:
            output, _ = process.communicate(timeout=HELPER_TIMEOUT)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise ValueError("header helper unavailable") from None
        if process.returncode:
            raise ValueError("header helper unavailable")
    return validate_headers(json.loads(output))


class HeaderCache:
    def __init__(self, loader, clock=time.monotonic, stopping=None):
        self.loader = loader
        self.clock = clock
        self.lock = threading.Lock()
        self.headers = None
        self.expires = 0.0
        self.stopping = stopping

    def _load(self):
        if self.stopping is not None and self.stopping.is_set():
            raise ValueError("relay stopping")
        # A failed refresh must never leave rejected/expired headers usable.
        self.headers = None
        headers = validate_headers(self.loader())
        self.headers = headers
        self.expires = self.clock() + HEADER_TTL
        return headers

    def get(self):
        with self.lock:
            if self.headers is None or self.clock() >= self.expires:
                return self._load()
            return self.headers

    def refresh(self, rejected):
        with self.lock:
            # Another request may already have refreshed this generation.
            if self.headers is rejected or self.headers is None or self.clock() >= self.expires:
                return self._load()
            return self.headers


class RelayServer(ThreadingHTTPServer):
    # Wait for bounded in-flight requests during graceful shutdown.
    daemon_threads = False
    block_on_close = True

    def __init__(self, address, *, log_path=None, header_loader=None, upstream_url=UPSTREAM):
        if not is_loopback(address[0]) or address[0] != "127.0.0.1":
            raise ValueError("bind host must be 127.0.0.1")
        target = urlsplit(upstream_url)
        # The only alternate destination is an explicitly injected loopback test
        # server. No environment/CLI destination override, proxies or redirects.
        if upstream_url != UPSTREAM and not (
            target.scheme == "http" and target.hostname and is_loopback(target.hostname)
            and not target.username and not target.password and not target.fragment
        ):
            raise ValueError("invalid upstream")
        self.target = target
        self.stopping = threading.Event()
        self.socket_lock = threading.Lock()
        self.sockets = set()
        self.header_cache = HeaderCache(header_loader or fetch_headers, stopping=self.stopping)
        self.log_path = Path(log_path) if log_path is not None else (
            Path.home() / ".agents/runtime/codex-otlp-relay.jsonl"
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_lock = threading.Lock()
        super().__init__(address, RelayHandler)

    @staticmethod
    def cancel_socket(connection):
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        connection.close()

    def track_socket(self, connection):
        with self.socket_lock:
            if self.stopping.is_set():
                self.cancel_socket(connection)
                raise OSError("relay stopping")
            self.sockets.add(connection)

    def get_request(self):
        connection, address = super().get_request()
        self.track_socket(connection)
        return connection, address

    def shutdown_request(self, request):
        with self.socket_lock:
            self.sockets.discard(request)
        super().shutdown_request(request)

    def server_close(self):
        # Wake blocked reads before ThreadingMixIn joins request threads. A
        # trickling client must not keep SIGTERM/SIGINT shutdown alive forever.
        with self.socket_lock:
            self.stopping.set()
            active = list(self.sockets)
        for connection in active:
            self.cancel_socket(connection)
        super().server_close()

    def handle_error(self, request, client_address):
        # SocketServer's default traceback can expose header-bearing exceptions.
        pass

    def log_request_row(self, status, bytes_in, upstream_ms):
        row = {"ts": datetime.now(timezone.utc).isoformat(), "status": status,
               "bytes_in": bytes_in, "upstream_ms": upstream_ms}
        try:
            with self.log_lock, self.log_path.open("a", encoding="utf-8") as log:
                log.write(json.dumps(row, separators=(",", ":")) + "\n")
        except OSError:
            print("otlp_relay: request log unavailable", file=sys.stderr)

    def _send_upstream(self, body, headers):
        factory = http.client.HTTPSConnection if self.target.scheme == "https" else http.client.HTTPConnection
        connection = factory(self.target.hostname, self.target.port, timeout=IO_TIMEOUT)
        upstream_socket = None
        try:
            connection.connect()
            upstream_socket = connection.sock
            self.track_socket(upstream_socket)
            path = self.target.path or "/"
            if self.target.query:
                path += "?" + self.target.query
            connection.request("POST", path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, response.read(MAX_RESPONSE)
        finally:
            connection.close()
            if upstream_socket is not None:
                with self.socket_lock:
                    self.sockets.discard(upstream_socket)

    def forward(self, body, content_headers):
        upstream_ms = 0.0
        if self.stopping.is_set():
            return 503, b"upstream unavailable\n", upstream_ms
        try:
            headers = self.header_cache.get()
        except Exception:
            return 502, b"header helper unavailable\n", upstream_ms
        for attempt in range(2):
            if self.stopping.is_set():
                return 503, b"upstream unavailable\n", round(upstream_ms, 3)
            start = time.monotonic()
            try:
                status, response = self._send_upstream(body, dict(headers, **content_headers))
            except Exception:
                upstream_ms += (time.monotonic() - start) * 1000
                return 503, b"upstream unavailable\n", round(upstream_ms, 3)
            upstream_ms += (time.monotonic() - start) * 1000
            if status not in (401, 403) or attempt:
                return status, response, round(upstream_ms, 3)
            try:
                headers = self.header_cache.refresh(headers)
            except Exception:
                return 502, b"header helper unavailable\n", round(upstream_ms, 3)


class RelayHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(IO_TIMEOUT)
        self.bytes_in = 0
        self.upstream_ms = 0.0
        super().setup()

    def log_message(self, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        # Parsing errors must not reflect request text in HTML or access logs.
        self.respond(code, b"invalid request\n")

    def parse_request(self):
        if not super().parse_request():
            return False
        if not is_loopback(self.client_address[0]):
            self.respond(403, b"loopback clients only\n")
            return False
        return True

    def __getattr__(self, name):
        if name.startswith("do_"):
            return self.not_found
        raise AttributeError(name)

    def not_found(self):
        self.respond(404, b"not found\n")

    def respond(self, status, body):
        self.close_connection = True
        # Commit the single safe row before the client can observe completion.
        self.server.log_request_row(status, self.bytes_in, self.upstream_ms)
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except OSError:
            pass

    def do_POST(self):
        if self.path != "/v1/traces":
            self.not_found()
            return
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") is not None:
            self.respond(400, b"invalid request framing\n")
            return
        if not lengths:
            self.respond(411, b"content length required\n")
            return
        if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,20}", lengths[0]):
            self.respond(400, b"invalid content length\n")
            return
        length = int(lengths[0])
        if length > MAX_BODY:
            self.respond(413, b"request too large\n")
            return
        try:
            body = self.rfile.read(length)
        except OSError:
            self.respond(400, b"incomplete request body\n")
            return
        self.bytes_in = len(body)
        if self.bytes_in != length:
            self.respond(400, b"incomplete request body\n")
            return
        content_headers = {key: self.headers[key] for key in ("content-type", "content-encoding")
                           if key in self.headers}
        status, response, self.upstream_ms = self.server.forward(body, content_headers)
        self.respond(status, response)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Loopback Codex OTLP trace relay")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--check", action="store_true", help="Check headers without starting a server")
    args = parser.parse_args(argv)
    if args.check:
        try:
            validate_headers(fetch_headers())
            ok = True
        except Exception:
            ok = False
        print(json.dumps({"headers_ok": ok}))
        return 0 if ok else 1
    try:
        port = args.port if args.port is not None else int(os.environ.get("CODEX_OTLP_RELAY_PORT", "4319"))
        if not 0 <= port <= 65535:
            raise ValueError("invalid port")
        server = RelayServer(("127.0.0.1", port))
    except Exception:
        print("otlp_relay: could not start", file=sys.stderr)
        return 1
    # shutdown() cannot run in the serve_forever thread. The signal handler only
    # requests a stop; the main thread closes the listener and joins workers.
    stop = threading.Event()
    previous = {}
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1})
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, lambda *_: stop.set())
        worker.start()
        stop.wait()
    finally:
        if worker.is_alive():
            server.shutdown()
            worker.join()
        server.server_close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return 0


if __name__ == "__main__":
    sys.exit(main())

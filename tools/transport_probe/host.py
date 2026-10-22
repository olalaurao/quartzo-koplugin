"""Ephemeral synthetic-only TLS fixture. Never canonical ingestion or ACK."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import pathlib
import secrets
import socket
import ssl
import subprocess
import threading
import time
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer

RECEIPT = b'{"probe_version":1,"transport_only":true,"canonical_ack":false,"persisted_canonical":false}'
PAYLOAD = b'{"probe_version":1,"source_data":"synthetic","event_count":1,"diagnostic_only":true}'


def private_address(value: str) -> str:
    address = ipaddress.IPv4Address(value)
    networks = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.1/32")
    if not any(address in ipaddress.IPv4Network(network) for network in networks):
        raise ValueError("Explicit private IPv4 binding required")
    return str(address)


class DiagnosticHost:
    """Caller owns a fresh private runtime directory outside every Git repo."""
    def __init__(self, directory: pathlib.Path, bind: str, openssl: pathlib.Path, ttl: int = 900):
        self.directory = directory.resolve()
        self.bind = private_address(bind)
        if not self.directory.is_relative_to(pathlib.Path(tempfile.gettempdir()).resolve()):
            raise ValueError("Runtime credentials must stay in the OS temporary directory")
        if not 10 <= ttl <= 1800:
            raise ValueError("Diagnostic lifetime must be 10..1800 seconds")
        if any((parent / ".git").exists() for parent in (self.directory, *self.directory.parents)):
            raise ValueError("Runtime credentials must be outside every Git repository")
        self.directory.mkdir(mode=0o700, exist_ok=False)
        self.run_id = secrets.token_hex(16)
        self.token = secrets.token_hex(32)
        self.expired_token = secrets.token_hex(32)
        self.expires_at = int(time.time()) + ttl
        self.deadline = time.monotonic() + ttl
        self.counts = {"unauthorized": 0, "expired": 0, "rate": 0, "server": 0, "ok": 0}
        self.unique_payloads: set[str] = set()
        self.tls_versions: set[str] = set()
        self.errors = 0
        self._thread = None
        self._stop = threading.Event()
        for prefix in ("server", "untrusted"):
            command = [str(openssl), "req", "-x509", "-newkey", "rsa:2048", "-sha256",
                "-days", "1", "-nodes", "-subj", "/CN=quartzo-synthetic-transport",
                "-addext", f"subjectAltName=IP:{self.bind}",
                "-keyout", str(self.directory / f"{prefix}.key"),
                "-out", str(self.directory / f"{prefix}.pem")]
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.context.maximum_version = ssl.TLSVersion.TLSv1_2
        self.context.load_cert_chain(self.directory / "server.pem", self.directory / "server.key")
        self.server = self._server_class()((self.bind, 0), self._handler_class())
        self.server.timeout = 0.5
        self.endpoint = f"https://{self.bind}:{self.server.server_address[1]}"
        # This file is private runtime input, never diagnostics/public evidence.
        config = dict(endpoint=self.endpoint, token=self.token, expired_token=self.expired_token,
            run_id=self.run_id, expires_at=self.expires_at,
            ca_file="server.pem", bad_ca_file="untrusted.pem")
        (self.directory / "private-session.json").write_text(json.dumps(config), encoding="utf-8")
        (self.directory / "synthetic-payload.json").write_bytes(PAYLOAD)

    def _server_class(self):
        owner = self
        class Server(HTTPServer):
            allow_reuse_address = False
            def get_request(self):
                connection, address = self.socket.accept()
                connection.settimeout(5)
                try:
                    secure = owner.context.wrap_socket(connection, server_side=True)
                except Exception:
                    connection.close()
                    raise
                owner.tls_versions.add(secure.version())
                return secure, address
            def finish_request(self, request, address):
                def expire_connection():
                    try: request.shutdown(socket.SHUT_RDWR)
                    except OSError: pass
                    request.close()
                timer = threading.Timer(10, expire_connection)
                timer.daemon = True
                timer.start()
                try: super().finish_request(request, address)
                finally: timer.cancel()
            def handle_error(self, request, address):
                # No peer IP, headers, credentials, body or traceback logging.
                owner.errors += 1
        return Server

    def _handler_class(self):
        owner = self
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *args): pass
            def reply(self, status, body=b'{"transport_only":true,"canonical_ack":false}', retry=False):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                if retry: self.send_header("Retry-After", "1")
                self.end_headers()
                self.wfile.write(body)
                self.close_connection = True
            def do_GET(self): self.reply(405)
            def do_POST(self):
                try:
                    try: length = int(self.headers.get("Content-Length", "0"))
                    except ValueError: length = 0
                    # Consume a bounded body before early replies. Leaving a
                    # small TLS request unread can reset the connection before
                    # Windows clients receive the 401/403/404 response.
                    if length < 1:
                        self.reply(413); return
                    body = self.rfile.read(min(length, 8193))
                    if length > 8192:
                        self.reply(413); return
                    if time.time() >= owner.expires_at:
                        self.reply(401); return
                    authorization = self.headers.get("Authorization", "")
                    value = authorization[7:] if authorization.startswith("Bearer ") else ""
                    if len(value) != 64 or any(character not in "abcdef0123456789" for character in value):
                        owner.counts["unauthorized"] += 1
                        self.reply(401); return
                    if hmac.compare_digest(value, owner.expired_token):
                        owner.counts["expired"] += 1
                        self.reply(401); return
                    if len(self.headers.get_all("Authorization", [])) != 1 or not hmac.compare_digest(value, owner.token):
                        owner.counts["unauthorized"] += 1
                        self.reply(401); return
                    if self.headers.get("X-Quartzo-Probe-Run") != owner.run_id:
                        self.reply(403); return
                    if self.path not in ("/probe/ok", "/probe/rate", "/probe/server"):
                        self.reply(404); return
                    if body != PAYLOAD:
                        self.reply(400); return
                    scenario = self.path.rsplit("/", 1)[-1]
                    if scenario in ("rate", "server") and owner.counts[scenario] == 0:
                        owner.counts[scenario] += 1
                        self.reply(429 if scenario == "rate" else 503, retry=scenario == "rate")
                        return
                    owner.unique_payloads.add(hashlib.sha256(PAYLOAD).hexdigest())
                    owner.counts["ok"] += 1
                    self.reply(200, RECEIPT)
                except (OSError, ValueError):
                    owner.errors += 1
                    self.close_connection = True
        return Handler

    def start(self):
        if self._thread is not None: raise RuntimeError("Diagnostic already started")
        def serve():
            while not self._stop.is_set() and time.monotonic() < self.deadline:
                self.server.handle_request()
        self._thread = threading.Thread(target=serve, daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread is not None: self._thread.join(timeout=16)
        self.server.server_close()
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("Diagnostic listener did not stop")

    def report(self):
        return dict(probe_version=1, proof="host_tls_fixture_only", source_data="synthetic",
            run_id=self.run_id, counts=dict(self.counts), unique_payloads=len(self.unique_payloads),
            tls_versions=sorted(self.tls_versions), server_errors=self.errors,
            canonical_ack_claimed=False, canonical_persistence_proven=False,
            kindle_runtime_proven=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-directory", required=True, type=pathlib.Path)
    parser.add_argument("--bind", required=True)
    parser.add_argument("--openssl", required=True, type=pathlib.Path)
    parser.add_argument("--lifetime-seconds", default=900, type=int)
    args = parser.parse_args()
    host = None
    try:
        host = DiagnosticHost(args.runtime_directory, args.bind, args.openssl, args.lifetime_seconds)
        host.start()
        print("Ephemeral synthetic TLS fixture ready; credentials remain in private runtime files", flush=True)
        while host._thread.is_alive():
            if (host.directory / "stop-requested").is_file() or (
                host.counts == dict(unauthorized=1, expired=1, rate=1, server=1, ok=4)):
                break
            host._thread.join(timeout=1)
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print(f"Synthetic TLS fixture failed: {type(error).__name__}", flush=True)
        return 1
    finally:
        if host is not None:
            host.close()
            (host.directory / "host-observation.json").write_text(json.dumps(host.report(), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

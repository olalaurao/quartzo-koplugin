"""Real Linux LuaSec/LuaSocket loopback acceptance, never device/ACK proof."""
import hashlib
import importlib.util
import os
import pathlib
import shutil
import ssl
import subprocess
import tempfile
import time
import unittest
from http.server import BaseHTTPRequestHandler


ROOT = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "reading_pinned_native_host", ROOT.parent / "transport_probe/host.py")
host_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host_module)

# Trusted fixed test source. All network operations use the actual shared
# carrier, LuaSec native factory and LuaSocket HTTP implementation.
DRIVER = r'''
assert(_VERSION == 'Lua 5.1', 'native_Lua51_required')
local https, http = require('ssl.https'), require('socket.http')
assert(require('ssl')._VERSION == '1.3.2' and https._VERSION == '1.3.2', 'native_LuaSec132_required')
local carrier = dofile(arg[1])
local config = {endpoint=arg[2],ca_file=arg[3],peer_certificate_sha256=arg[4],
    binding_id=string.rep('b',64)}
local token, payload = string.rep('t',43), 'synthetic-pinned-native'
local send = carrier.pinned_wire_transport(config,https,require('ltn12'),http)
local status, body, headers, delivery = send(payload,token,'good')
if arg[5] == 'ok' then
    assert(status == 200 and delivery, 'native_delivery_missing')
    assert(body == '{"transport_only":true,"canonical_ack":false}', 'native_body_mismatch')
    local checked, original = carrier.read_pinned_delivery(delivery,payload,token,config)
    assert(checked == 200 and original == body, 'native_delivery_binding_failed')
    assert(delivery.canonical_ack == nil and delivery.accepted_events == nil, 'ACK_authority_forbidden')
    assert(not carrier.read_pinned_delivery({},payload,token,config), 'forged_delivery_accepted')
    print('native_delivery_checked_no_ACK')
else
    assert(status == nil and delivery == nil, 'untrusted_delivery_accepted')
    assert(body == arg[5], 'native_rejection_reason_mismatch')
    print('native_rejected_no_delivery')
end
'''


class WireHost(host_module.DiagnosticHost):
    """Reuse existing ephemeral cert/listener lifecycle, no canonical storage."""
    def _handler_class(self):
        self.requests = []
        self.application_bytes_observed = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def handle_one_request(self):
                # Observe even incomplete HTTP bytes, not just completed POSTs.
                if self.rfile.peek(1):
                    owner.application_bytes_observed = True
                super().handle_one_request()

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(min(length, 1024))
                owner.requests.append((self.path, self.headers.get("Authorization"), body))
                if getattr(owner, "delay_response", False):
                    # The owner stop event interrupts this finite test delay.
                    if owner._stop.wait(8):
                        return
                response = b'{"transport_only":true,"canonical_ack":false}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(response)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(response)

        return Handler


@unittest.skipUnless(os.environ.get("READING_NATIVE_LUA51"),
                     "native LuaSec fixture requires explicit READING_NATIVE_LUA51")
class NativePinnedTlsTest(unittest.TestCase):
    def setUp(self):
        # An explicitly configured missing/wrong runtime fails, never skips.
        self.runtime = os.environ["READING_NATIVE_LUA51"]
        self.temporary = tempfile.TemporaryDirectory(prefix="quartzo-native-pin-")
        self.addCleanup(self.temporary.cleanup)
        directory = pathlib.Path(self.temporary.name)
        executable = shutil.which("openssl")
        self.assertIsNotNone(executable, "native TLS fixture requires OpenSSL")
        self.host = WireHost(directory / "session", "127.0.0.1", pathlib.Path(executable))
        self.addCleanup(self.host.close)
        self.host.start()
        self.driver = directory / "driver.lua"
        self.driver.write_text(DRIVER, encoding="utf-8")
        der = ssl.PEM_cert_to_DER_cert((self.host.directory / "server.pem").read_text())
        self.pin = hashlib.sha256(der).hexdigest()

    def run_client(self, reason="ok", pin=None, ca="server.pem"):
        result = subprocess.run([
            self.runtime, str(self.driver), str(ROOT.parents[1] / "quartzo.koplugin/quartzo/transport.lua"),
            self.host.endpoint, str(self.host.directory / ca), pin or self.pin, reason,
        ], capture_output=True, timeout=20)
        # Never print stderr, which can contain temporary private input paths.
        self.assertEqual(result.returncode, 0, "native Lua carrier assertion failed")
        expected = (b"native_delivery_checked_no_ACK\n" if reason == "ok"
                    else b"native_rejected_no_delivery\n")
        self.assertEqual(result.stdout, expected)

    def test_real_tls12_exact_leaf_pin_delivers_bound_bytes_without_ack(self):
        self.run_client()
        self.assertEqual(self.host.tls_versions, {"TLSv1.2"})
        self.assertTrue(self.host.application_bytes_observed)
        self.assertEqual(self.host.requests, [
            ("/reading/activity/v1", "Bearer " + "t" * 43, b"synthetic-pinned-native")])

    def test_trusted_ca_wrong_leaf_pin_sends_no_http_credentials(self):
        wrong = "0" * 64 if self.pin != "0" * 64 else "1" * 64
        self.run_client("reading_peer_pin_mismatch", pin=wrong)
        self.assertEqual(self.host.tls_versions, {"TLSv1.2"})
        self.assertEqual(self.host.requests, [])
        self.assertFalse(self.host.application_bytes_observed)

    def test_wrong_ca_sends_no_http_credentials(self):
        self.run_client("certificate verify failed", ca="untrusted.pem")
        self.assertEqual(self.host.requests, [])
        self.assertFalse(self.host.application_bytes_observed)

    def test_native_receive_timeout_grants_no_delivery(self):
        self.host.delay_response = True
        started = time.monotonic()
        self.run_client("reading_transport_failed")
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, 4)
        self.assertLess(elapsed, 10)
        self.assertEqual(len(self.host.requests), 1)
        self.assertTrue(self.host.application_bytes_observed)


if __name__ == "__main__":
    unittest.main()

"""Actual loopback TLS/HTTP fixture tests; no Kindle or canonical persistence."""
import http.client
import pathlib
import shutil
import ssl
import tempfile
import unittest
from lupa.lua51 import LuaRuntime

from host import DiagnosticHost, PAYLOAD, RECEIPT


class HostTlsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = pathlib.Path(tempfile.mkdtemp(prefix="quartzo-tls-host-tests-")).resolve()
        executable = shutil.which("openssl") or r"C:\Program Files\Git\usr\bin\openssl.exe"
        self.host = DiagnosticHost(self.temporary / "session", "127.0.0.1", pathlib.Path(executable))
        self.host.start()

    def tearDown(self):
        self.host.close()
        self.assertTrue(self.temporary.is_relative_to(pathlib.Path(tempfile.gettempdir()).resolve()))
        self.assertTrue(self.temporary.name.startswith("quartzo-tls-host-tests-"))
        shutil.rmtree(self.temporary)

    def request(self, scenario="ok", token=None, body=PAYLOAD, ca="server.pem", run_id=None):
        context = ssl.create_default_context(cafile=str(self.host.directory / ca))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_2
        connection = http.client.HTTPSConnection("127.0.0.1", self.host.server.server_address[1], context=context, timeout=5)
        try:
            connection.request("POST", "/probe/" + scenario, body=body, headers={
                "Authorization": "Bearer " + (token if token is not None else self.host.token),
                "X-Quartzo-Probe-Run": run_id or self.host.run_id,
                "Content-Type": "application/json"})
            response = connection.getresponse()
            return response.status, response.read(), response.getheader("Retry-After")
        finally:
            connection.close()

    def test_actual_tls_trust_rejects_wrong_ca_and_accepts_explicit_certificate(self):
        with self.assertRaises(ssl.SSLCertVerificationError): self.request(ca="untrusted.pem")
        self.assertEqual(self.request()[:2], (200, RECEIPT))
        self.assertEqual(self.host.report()["tls_versions"], ["TLSv1.2"])

    def test_invalid_expired_and_wrong_scope_credentials_never_accept_payload(self):
        self.assertEqual(self.request(token="0" * 64)[0], 401)
        self.assertEqual(self.request(token=self.host.expired_token)[0], 401)
        self.assertEqual(self.request(run_id="d" * 32)[0], 403)
        self.assertEqual(self.host.report()["unique_payloads"], 0)

    def test_retry_faults_and_replay_never_create_canonical_ack(self):
        self.assertEqual(self.request("rate")[::2], (429, "1"))
        self.assertEqual(self.request("rate")[:2], (200, RECEIPT))
        self.assertEqual(self.request("server")[0], 503)
        self.assertEqual(self.request("server")[:2], (200, RECEIPT))
        self.assertEqual(self.request()[:2], (200, RECEIPT))
        self.assertEqual(self.request()[:2], (200, RECEIPT))
        self.assertEqual(self.host.report()["unique_payloads"], 1)
        self.assertFalse(self.host.report()["canonical_ack_claimed"])
        self.assertFalse(self.host.report()["kindle_runtime_proven"])

    def test_unexpected_or_oversized_content_is_not_an_ingestion_endpoint(self):
        self.assertEqual(self.request(body=b"unexpected")[0], 400)
        self.assertEqual(self.request(body=b"x" * 8193)[0], 413)
        self.assertEqual(self.request(scenario="unknown")[0], 404)
        self.assertEqual(self.host.report()["unique_payloads"], 0)

    def test_public_report_omits_credentials_endpoints_and_runtime_paths(self):
        report = str(self.host.report())
        for private in (self.host.token, self.host.expired_token, self.host.endpoint, str(self.host.directory)):
            self.assertNotIn(private, report)

    def test_current_credential_rejects_after_its_actual_session_expiry(self):
        self.host.expires_at = 0
        self.assertEqual(self.request()[0], 401)
        self.assertEqual(self.host.report()["unique_payloads"], 0)

    def test_malformed_credentials_return_401_without_unhandled_server_error(self):
        for token in ("", "a" * 1000, "é" * 64):
            self.assertEqual(self.request(token=token)[0], 401)
        self.assertEqual(self.host.report()["server_errors"], 0)
        self.assertEqual(self.host.report()["unique_payloads"], 0)

    def test_host_receipt_bytes_match_the_lua_diagnostic_contract(self):
        module = LuaRuntime(unpack_returned_tuples=True).execute(
            (pathlib.Path(__file__).resolve().parents[2] / "quartzo.koplugin/quartzo/transport.lua").read_text(encoding="utf-8"))
        self.assertEqual(module.RECEIPT.encode("ascii"), RECEIPT)

    def test_runtime_directory_and_binding_are_explicit_and_confined(self):
        with self.assertRaises(ValueError):
            DiagnosticHost(self.temporary / "other", "0.0.0.0", pathlib.Path("unused"))
        with self.assertRaises(FileExistsError):
            DiagnosticHost(self.host.directory, "127.0.0.1", pathlib.Path("unused"))
        repository = pathlib.Path(__file__).resolve().parents[2]
        with self.assertRaises(ValueError):
            DiagnosticHost(repository / "must-not-create-credentials", "127.0.0.1", pathlib.Path("unused"))
        self.assertFalse((repository / "must-not-create-credentials").exists())


if __name__ == "__main__":
    unittest.main()

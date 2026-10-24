"""Real Lua 5.1 execution with injected HTTP only; never physical/TLS proof."""
import pathlib
import unittest

from lupa.lua51 import LuaRuntime


class ClientContractTest(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.assertEqual(self.lua.eval("_VERSION"), "Lua 5.1")
        self.module = self.lua.execute((pathlib.Path(__file__).resolve().parents[2] / "quartzo.koplugin/quartzo/transport.lua").read_text())
        self.config = self.lua.table_from(dict(endpoint="https://127.0.0.1:8443", token="a" * 64,
            expired_token="b" * 64, run_id="c" * 32, expires_at=2000,
            ca_file="/fixture/ca.pem", bad_ca_file="/fixture/bad-ca.pem"))
        self.lua.globals().fixture = self.config
        self.lua.globals().receipt = self.module.RECEIPT

    def dependencies(self, expression="return nil, 'certificate verify failed'", remainder=None):
        # All scripts here are fixed test source, never user/document content.
        script = """
        local calls, sleeps, scenarios = 0, {}, {}
        local deps = {now=function() return 1000 end, sleep=function(n) sleeps[#sleeps+1]=n end}
        deps.request=function(path, token, trust)
          calls=calls+1
          if trust=='bad' then BAD end
          REMAINDER
          if token~=fixture.token then return 401, '' end
          scenarios[path]=(scenarios[path] or 0)+1
          if path=='rate' and scenarios[path]==1 then return 429, '', {['retry-after']='1'} end
          if path=='server' and scenarios[path]==1 then return 503, '' end
          return 200, receipt
        end
        return deps, function() return calls, #sleeps end
        """.replace("BAD", expression).replace("REMAINDER", remainder or "")
        return self.lua.execute(script)

    def test_full_diagnostic_sequence_is_bounded_and_never_acks(self):
        for expression in ("return nil, 'certificate verify failed'",
                           "return nil, {'TLSV1_ALERT_UNKNOWN CA'}"):
            with self.subTest(expression=expression):
                deps, counts = self.dependencies(expression)
                result = self.module.run(self.config, deps)
                self.assertEqual(result.phase, "passed")
                self.assertEqual(result.request_attempts, 9)
                self.assertEqual(counts(), (9, 2))
                self.assertFalse(result.canonical_ack_claimed)
                self.assertFalse(result.statistics_accessed)
                self.assertFalse(result.wifi_changed)

    def test_bad_ca_must_fail_for_certificate_reason_not_offline(self):
        for expression in ("return 401, ''", "return nil, 'timeout'",
                           "return nil, 'connection refused'", "return nil, 'tls_failed'",
                           "return nil, 'error loading certificate file'",
                           "return nil, 'error loading CA file'"):
            deps, counts = self.dependencies(expression)
            result, error = self.module.run(self.config, deps)
            self.assertIsNone(result)
            self.assertEqual(error, "bad_ca_not_rejected_by_certificate_validation")
            self.assertEqual(counts()[0], 1)

    def test_invalid_and_expired_auth_are_not_retried(self):
        deps, counts = self.dependencies(remainder="if token~=fixture.token then return 200, receipt end")
        result, error = self.module.run(self.config, deps)
        self.assertIsNone(result)
        self.assertEqual(error, "unauthorized_not_rejected")
        self.assertEqual(counts()[0], 2)

    def test_canonical_ack_or_unknown_receipt_is_rejected(self):
        deps, _ = self.dependencies(remainder="if token==fixture.token then return 200, '{\"canonical_ack\":true}' end")
        result, error = self.module.run(self.config, deps)
        self.assertIsNone(result)
        self.assertEqual(error, "noncanonical_receipt_required")

    def test_public_plaintext_redirect_and_ambiguous_ipv4_are_refused_before_io(self):
        for endpoint in ("http://127.0.0.1:8443", "https://8.8.8.8:8443", "https://010.0.0.1:8443",
            "https://127.0.0.1:8443/path", "https://localhost:8443", "https://127.0.0.1:8443?token=x"):
            self.config.endpoint = endpoint
            deps, counts = self.dependencies()
            result, _ = self.module.run(self.config, deps)
            self.assertIsNone(result)
            self.assertEqual(counts()[0], 0)

    def test_untrusted_or_expired_clock_refuses_all_requests(self):
        for expiry in (1000, 999, 2801):
            self.config.expires_at = expiry
            deps, counts = self.dependencies()
            result, error = self.module.run(self.config, deps)
            self.assertIsNone(result)
            self.assertEqual(error, "expired_or_untrusted_clock")
            self.assertEqual(counts()[0], 0)

    def test_explicit_distinct_trust_files_are_required(self):
        for bad in ("", self.config.ca_file):
            self.config.bad_ca_file = bad
            deps, counts = self.dependencies()
            result, _ = self.module.run(self.config, deps)
            self.assertIsNone(result)
            self.assertEqual(counts()[0], 0)

    def test_retry_is_limited_and_bounded_retry_after_required(self):
        deps, counts = self.dependencies(remainder="if path=='rate' then return 429, '', {['retry-after']='1'} end")
        result, error = self.module.run(self.config, deps)
        self.assertIsNone(result)
        self.assertEqual(error, "bounded_retry_failed")
        self.assertEqual(counts()[0], 6)
        deps, counts = self.dependencies(remainder="if path=='rate' then return 429, '', {['retry-after']='999'} end")
        result, error = self.module.run(self.config, deps)
        self.assertIsNone(result)
        self.assertEqual(error, "retry_delay_rejected")
        self.assertEqual(counts()[0], 5)
        deps, _ = self.dependencies(remainder="if path=='rate' then return 429, '', {['retry-after']='invalid'} end")
        result, error = self.module.run(self.config, deps)
        self.assertIsNone(result)
        self.assertEqual(error, "retry_delay_rejected")

    def test_native_luasec_adapter_sets_trust_protocol_redirect_and_body_bounds(self):
        self.lua.globals().client = self.module
        self.assertTrue(self.lua.execute("""
          local captured
          local https={request=function(r) captured=r; r.sink(receipt); return 1,200,{} end}
          local ltn12={source={string=function(p) return function() return p end end}}
          local send=client.transport(fixture,https,ltn12,'synthetic')
          local code,body=send('ok',fixture.token,'good')
          assert(code==200 and body==receipt and https.TIMEOUT==5)
          assert(captured.verify=='peer' and captured.protocol=='tlsv1_2' and captured.redirect==false)
          assert(captured.cafile==fixture.ca_file and captured.headers.authorization=='Bearer '..fixture.token)
          assert(captured.headers['content-length']=='9')
          https.request=function(r) r.sink(string.rep('x',2049)); return 1,200,{} end
          local failed,reason=send('ok',fixture.token,'good')
          assert(failed==nil and reason=='response_bound')
          https.request=function() error('invalid request reached network') end
          local refused,invalid=send('../elsewhere',fixture.token,'good')
          assert(refused==nil and invalid=='invalid_diagnostic_request')
          refused,invalid=send('ok','invalid'..string.char(13,10)..'header','good')
          assert(refused==nil and invalid=='invalid_diagnostic_request')
          return true
        """))


if __name__ == "__main__":
    unittest.main()

"""Real Lua 5.1 harness control flow; native dependencies are injected."""
import pathlib
import unittest

from lupa.lua51 import LuaRuntime


class DeviceHarnessTest(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        directory = pathlib.Path(__file__).parent
        self.lua.globals().client = self.lua.execute((directory.parents[1] / "quartzo.koplugin/quartzo/transport.lua").read_text())
        self.harness = self.lua.execute((directory / "device.lua").read_text())
        self.deps, self.config, self.files, self.calls = self.lua.execute("""
          local config={endpoint='https://127.0.0.1:8443', token=string.rep('a',64),
            expired_token=string.rep('b',64),run_id=string.rep('c',32),expires_at=1900,
            ca_file='server.pem',bad_ca_file='untrusted.pem'}
          local files={['private-session.json']='fixture',
            ['server.pem']='-----BEGIN CERTIFICATE-----synthetic',
            ['untrusted.pem']='-----BEGIN CERTIFICATE-----other',
            ['synthetic-payload.json']='PAYLOAD'}
          local calls, scenarios=0,{}
          local deps={client=client,now=function() return 1000 end,sleep=function() end,
            decode=function() return config end,read=function(path,limit)
              local name=path:match('/([^/]+)$');local value=assert(files[name]);
              assert(#value<=limit);return value end,
            ltn12={source={string=function(p) return function() return p end end}}}
          deps.https={request=function(r)
            calls=calls+1
            if r.cafile:find('untrusted.pem',1,true) then return nil,'certificate verify failed' end
            if r.headers.authorization~='Bearer '..config.token then return 1,401,{} end
            local path=r.url:match('/([^/]+)$');scenarios[path]=(scenarios[path] or 0)+1
            if path=='rate' and scenarios[path]==1 then return 1,429,{['retry-after']='1'} end
            if path=='server' and scenarios[path]==1 then return 1,503,{} end
            r.sink(client.RECEIPT);return 1,200,{}
          end}
          return deps,config,files,function() return calls end
        """.replace("PAYLOAD", self.harness.PAYLOAD))
        self.directory = "/mnt/us/extensions/quartzo-transport-probe"

    def test_exact_synthetic_sequence_returns_sanitized_diagnostic_only(self):
        report = self.harness.run(self.directory, self.deps)
        self.assertEqual(report.phase, "passed")
        self.assertEqual(report.request_attempts, 9)
        self.assertEqual(self.calls(), 9)
        for field in ("statistics_accessed", "wifi_changed", "canonical_ack_claimed", "canonical_persistence_proven"):
            self.assertFalse(report[field])
        self.assertNotIn("token", dict(report))
        self.assertNotIn("endpoint", dict(report))

    def test_unowned_directory_and_traversal_do_not_read_or_send(self):
        for path in ("/tmp/elsewhere", self.directory + "/../reader", self.directory + "/"):
            self.assertEqual(self.harness.run(path, self.deps).error_code, "invalid_owned_directory")
        self.assertEqual(self.calls(), 0)

    def test_unknown_session_field_and_trust_path_fail_before_io(self):
        self.config.extra = "private"
        self.assertEqual(self.harness.run(self.directory, self.deps).error_code, "unexpected_session_field")
        self.config.extra = None
        self.config.ca_file = "../../reader/config.lua"
        self.assertEqual(self.harness.run(self.directory, self.deps).error_code, "invalid_trust_path")
        self.assertEqual(self.calls(), 0)

    def test_modified_payload_or_private_key_is_never_transmitted(self):
        self.files["synthetic-payload.json"] = "real content is forbidden"
        self.assertEqual(self.harness.run(self.directory, self.deps).phase, "failed")
        self.files["synthetic-payload.json"] = self.harness.PAYLOAD
        self.files["server.pem"] = "-----BEGIN CERTIFICATE-----PRIVATE KEY"
        self.assertEqual(self.harness.run(self.directory, self.deps).phase, "failed")
        self.assertEqual(self.calls(), 0)

    def test_expired_clock_fails_before_any_network_request(self):
        self.config.expires_at = 999
        self.assertEqual(self.harness.run(self.directory, self.deps).error_code, "expired_or_untrusted_clock")
        self.assertEqual(self.calls(), 0)

    def test_native_exception_is_redacted(self):
        self.deps.https.request = self.lua.eval("function() error('private endpoint/token must not escape') end")
        report = self.harness.run(self.directory, self.deps)
        self.assertEqual(report.phase, "failed")
        self.assertEqual(report.error_code, "bad_ca_not_rejected_by_certificate_validation")
        self.assertNotIn("private endpoint", str(dict(report)))

    def test_native_bootstrap_compiles_as_lua51_without_executing(self):
        source = pathlib.Path(__file__).with_name("kindle.lua").read_text()
        self.assertIsNotNone(self.lua.eval("loadstring")(source))


if __name__ == "__main__": unittest.main()

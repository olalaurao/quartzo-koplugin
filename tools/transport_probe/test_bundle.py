"""Owned host fixtures test provisioning/collection, never a real USB deployment."""
import json
import pathlib
import shutil
import tempfile
import unittest

from bundle import BASELINE, NAME, SOURCES, collect, install, prepare, read_json, verify_bundle
from host import DiagnosticHost


class BundleTest(unittest.TestCase):
    def setUp(self):
        self.temporary = pathlib.Path(tempfile.mkdtemp(prefix="quartzo-bundle-tests-")).resolve()
        executable = shutil.which("openssl") or r"C:\Program Files\Git\usr\bin\openssl.exe"
        self.host = DiagnosticHost(self.temporary / "session", "127.0.0.1", pathlib.Path(executable))
        self.bundle = self.temporary / "bundle"
        self.root = self.temporary / "mock-mounted-kindle"
        (self.root / "koreader").mkdir(parents=True)
        (self.root / "extensions").mkdir()
        (self.root / "koreader" / "git-rev").write_text(BASELINE + "\n")
        (self.root / "koreader" / "luajit").write_bytes(b"synthetic runtime placeholder")
        self.sentinel = self.root / "koreader" / "settings.reader.lua"
        self.sentinel.write_bytes(b"owned production settings sentinel")

    def tearDown(self):
        self.host.close()
        self.assertEqual(self.sentinel.read_bytes(), b"owned production settings sentinel")
        self.assertTrue(self.temporary.is_relative_to(pathlib.Path(tempfile.gettempdir()).resolve()))
        self.assertTrue(self.temporary.name.startswith("quartzo-bundle-tests-"))
        shutil.rmtree(self.temporary)

    def prepared(self):
        return prepare(self.host.directory, self.bundle)

    def observation_fixtures(self):
        self.prepared()
        target = install(self.bundle, self.root)
        device = dict(probe_version=1, phase="passed", run_id=self.host.run_id, request_attempts=9,
            lua_version="Lua 5.1", luasec_version="1.3.2", koreader_version=BASELINE,
            canonical_ack_claimed=False, canonical_persistence_proven=False,
            statistics_accessed=False, wifi_changed=False)
        for key in ("bad_ca_rejected", "unauthorized_rejected", "expired_token_rejected",
            "rate_limit_retried", "server_error_retried", "replay_receipt_received"): device[key] = True
        (target / "device-observation.json").write_text(json.dumps(device))
        (target / "launcher-status.txt").write_text("completed\n")
        self.host.counts = dict(unauthorized=1, expired=1, rate=1, server=1, ok=4)
        self.host.unique_payloads.add("synthetic digest")
        self.host.tls_versions.add("TLSv1.2")
        report = self.temporary / "host-observation.json"
        report.write_text(json.dumps(self.host.report()))
        return target, device, report

    def test_prepare_copies_exact_allowlist_no_keys_and_normalizes_shell(self):
        manifest = self.prepared()
        self.assertEqual(manifest, verify_bundle(self.bundle))
        self.assertEqual(set(path.name for path in self.bundle.iterdir()),
            set(SOURCES) | {"server.pem", "untrusted.pem", "synthetic-payload.json", "private-session.json", "bundle-manifest.json"})
        self.assertNotIn(b"\r", (self.bundle / "run.sh").read_bytes())
        self.assertFalse(any(path.suffix == ".key" for path in self.bundle.iterdir()))

    def test_prepare_refuses_existing_output_expiry_extra_fields_and_private_keys(self):
        config_path = self.host.directory / "private-session.json"
        original = read_json(config_path)
        for change in ({"expires_at": 0}, {"unknown": "field"}, {"ca_file": "../private.key"}):
            config_path.write_text(json.dumps(original | change))
            with self.assertRaises(ValueError): self.prepared()
            self.assertFalse(self.bundle.exists())
        config_path.write_text(json.dumps(original))
        (self.host.directory / "server.pem").write_bytes(b"-----BEGIN CERTIFICATE-----PRIVATE KEY")
        with self.assertRaises(ValueError): self.prepared()

    def test_install_only_creates_fresh_extension_and_never_overwrites(self):
        self.prepared()
        target = install(self.bundle, self.root)
        self.assertEqual(target, self.root / "extensions" / NAME)
        with self.assertRaises(ValueError): install(self.bundle, self.root)
        with self.assertRaises(ValueError): self.prepared()

    def test_mismatched_baseline_or_changed_bundle_refuses_device_copy(self):
        self.prepared()
        revision = self.root / "koreader" / "git-rev"
        revision.write_text("v2025.04")
        with self.assertRaises(ValueError): install(self.bundle, self.root)
        revision.write_text(BASELINE)
        (self.bundle / "client.lua").write_bytes(b"modified")
        with self.assertRaises(ValueError): install(self.bundle, self.root)
        self.assertFalse((self.root / "extensions" / NAME).exists())

    def test_matching_synthetic_observations_cannot_self_attest_physical_proof(self):
        _, _, report = self.observation_fixtures()
        result = collect(self.bundle, self.root, report)
        self.assertTrue(result["observations_match"])
        self.assertFalse(result["physical_execution_attested"])
        self.assertFalse(result["canonical_ack_claimed"])
        for secret in (self.host.token, self.host.expired_token, self.host.endpoint, str(self.host.directory)):
            self.assertNotIn(secret, json.dumps(result))

    def test_collection_rejects_mismatched_run_ack_missing_scenario_and_changed_deployment(self):
        target, device, report = self.observation_fixtures()
        for change in ({"run_id": "d" * 32}, {"canonical_ack_claimed": True}, {"server_error_retried": False}):
            (target / "device-observation.json").write_text(json.dumps(device | change))
            with self.assertRaises(ValueError): collect(self.bundle, self.root, report)
        (target / "device-observation.json").write_text(json.dumps(device))
        altered = self.host.report()
        altered["counts"]["ok"] = 3
        report.write_text(json.dumps(altered))
        with self.assertRaises(ValueError): collect(self.bundle, self.root, report)
        report.write_text(json.dumps(self.host.report()))
        (target / "client.lua").write_bytes(b"modified deployment")
        with self.assertRaises(ValueError): collect(self.bundle, self.root, report)

    def test_duplicate_or_oversized_json_is_rejected(self):
        source = self.temporary / "input.json"
        source.write_text('{"key":1,"key":2}')
        with self.assertRaises(ValueError): read_json(source)
        source.write_bytes(b"x" * 8193)
        with self.assertRaises(ValueError): read_json(source)


if __name__ == "__main__": unittest.main()

"""Owned fake mount/export safety tests, never physical or canonical ACK proof."""
import base64
import json
import pathlib
import shutil
import tempfile
import time
import unittest
from unittest import mock

import sequence_bundle as bundle
import test_sequence_driver as driver_reference


class SequenceBundleTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix='quartzo-wire-tls-test-')).resolve()
        self.values = {name: (bundle.ROOT / source).read_bytes().replace(b'\r\n', b'\n')
                       for name, source in bundle.SOURCE_MAP.items()}
        self.values['run.sh'] = self.values['run.sh'].replace(b'quartzo-transport-probe', bundle.NAME.encode())
        self.patch = mock.patch.object(bundle, 'read_sources', return_value=self.values)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.session = self.root / 'private-session'
        self.session.mkdir()
        now = int(time.time())
        self.fixture,pairing=driver_reference.paired_reference.fixture_and_pairing(now)
        for name, value in {'private-pairing.json': bundle.encoded(pairing),
            'server.pem': pairing['certificate_pem'].encode('ascii'),
            'synthetic-fixture.json': bundle.encoded(self.fixture),
            'phone-input.json': b'PRIVATE_KEY_SENTINEL_MUST_NOT_LEAVE_HOST'}.items():
            (self.session / name).write_bytes(value)
        self.output = self.root / 'bundle'
        self.manifest = bundle.prepare(self.session, self.output, 'a'*40)
        self.mount = self.root / 'synthetic-mount'
        (self.mount / 'koreader/common').mkdir(parents=True)
        (self.mount / 'koreader/ffi').mkdir()
        (self.mount / 'extensions').mkdir()
        for name, value in {'git-rev': b'v2026.07.1\n', 'luajit': b'synthetic placeholder',
            'common/dkjson.lua': b'synthetic JSON source identity',
            'ffi/sha2.lua': b'synthetic SHA source identity',
            'statistics.sqlite3': b'owned Statistics preservation sentinel'}.items():
            (self.mount / 'koreader' / name).write_bytes(value)
        self.android = self.root / 'synthetic-android-export'
        (self.android / 'vault').mkdir(parents=True)
        self.observation = self.root / 'installation.json'
        self.target = self.mount / 'extensions' / bundle.NAME

    def tearDown(self):
        self.assertFalse(self.root.is_symlink() or self.root.is_junction())
        self.assertEqual(self.root.resolve(), self.root)
        self.assertTrue(self.root.is_relative_to(pathlib.Path(tempfile.gettempdir()).resolve()))
        self.assertTrue(self.root.name.startswith('quartzo-wire-tls-test-'))
        shutil.rmtree(self.root)

    def installed(self):
        observation = bundle.install(self.output, self.mount)
        self.observation.write_bytes(bundle.encoded(observation))
        return observation

    def completed(self):
        observation = self.installed()
        driver = driver_reference.WireSequenceDriverTest()
        driver.setUp()
        report, _, _ = driver.driver(document=json.loads((self.session/'private-pairing.json').read_bytes()))
        # Deliberately synthetic ARM-looking data must STILL never attest hardware.
        report.update(jit_arch='arm', source_commit='a'*40,
                      manifest_digest=observation['manifest_digest'])
        (self.target / 'run.lock').mkdir()
        (self.target / 'launcher-status.txt').write_bytes(b'completed\n')
        (self.target / 'device-observation.json').write_bytes(bundle.encoded(report))
        fixture = self.fixture
        phone = dict(probe_revision='canonical-paired-wire-v1', phase='completed', run_id=fixture['run_id'],
            source_data='synthetic',synthetic_account=True,credential_cleanup_failed=False,unique_events=3,native_seconds=120,
            pending_queue_actions=6, canonical_ack=False, source_cursor_changed=False,
            statistics_accessed=False, wifi_changed=False, physical_execution_attested=False,
            credential_revoked=True, control_failed=False, production_registered=False, cloud_delivery_proven=False,
            canonical_paths=[shard['path'] for shard in fixture['expected_shards']])
        (self.android / 'completed.json').write_bytes(bundle.encoded(phone))
        for shard in fixture['expected_shards']:
            path = self.android / 'vault' / shard['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(shard['bytes_base64'], validate=True))
        return report, phone

    def collect(self):
        return bundle.collect(self.output, self.mount, self.observation, self.android)

    def test_prepare_never_packages_phone_private_key_or_overwrites_previous_bundle(self):
        self.assertEqual({path.name for path in self.output.iterdir()},
                         set(bundle.SOURCE_MAP) | bundle.INPUTS | {'bundle-manifest.json'})
        self.assertNotIn('phone-input.json', self.manifest['files'])
        before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        with self.assertRaises(ValueError):
            bundle.prepare(self.session, self.output, 'a'*40)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.output.iterdir()})
        with self.assertRaises(ValueError):
            bundle.private_directory(bundle.ROOT / 'never-create-this-test-bundle', fresh=True)

    def test_invalid_or_duplicate_private_session_and_private_key_certificate_reject_before_output(self):
        original = (self.session / 'private-pairing.json').read_bytes()
        invalid = original.replace(b'"pairing_version":', b'"pairing_version":1,"pairing_version":')
        (self.session / 'private-pairing.json').write_bytes(invalid)
        with self.assertRaises(ValueError):
            bundle.prepare(self.session, self.root / 'fresh-1', 'a'*40)
        self.assertFalse((self.root / 'fresh-1').exists())
        (self.session / 'private-pairing.json').write_bytes(original)
        with (self.session / 'server.pem').open('ab') as stream:
            stream.write(b'PRIVATE KEY')
        with self.assertRaises(ValueError):
            bundle.prepare(self.session, self.root / 'fresh-2', 'a'*40)
        self.assertFalse((self.root / 'fresh-2').exists())

    def test_install_preserves_native_and_statistics_and_refuses_existing_target(self):
        before = {path.relative_to(self.mount):path.read_bytes() for path in
                  (self.mount / 'koreader').rglob('*') if path.is_file()}
        observation = self.installed()
        self.assertFalse(observation['physical_execution_attested'])
        with self.assertRaises(ValueError):
            bundle.install(self.output, self.mount)
        self.assertEqual(before, {path.relative_to(self.mount):path.read_bytes() for path in
                  (self.mount / 'koreader').rglob('*') if path.is_file()})

    def test_correlated_host_forged_observations_cannot_attest_physical_or_issue_ack(self):
        self.completed()
        report = self.collect()
        self.assertTrue(report['observations_match'])
        self.assertFalse(report['physical_execution_attested'])
        self.assertFalse(report['canonical_ack'])
        self.assertFalse(report['cloud_delivery_proven'])
        self.assertEqual(report['native_seconds'],120)
        self.assertNotIn('t'*43, json.dumps(report))

    def test_changed_canonical_bytes_and_unexpected_files_are_not_hidden_by_report_counts(self):
        self.completed()
        path = self.android / 'vault' / driver_reference.FIXTURE['expected_shards'][0]['path']
        original = path.read_bytes()
        path.write_bytes(b'changed canonical bytes')
        with self.assertRaises(ValueError): self.collect()
        path.write_bytes(original)
        extra = self.android / 'vault' / 'unobserved.jsonl'
        extra.write_bytes(b'preserve me')
        with self.assertRaises(ValueError): self.collect()
        self.assertEqual(extra.read_bytes(), b'preserve me')

    def test_ack_claim_revocation_failure_wrong_counter_types_and_nonce_reuse_reject(self):
        device, phone = self.completed()
        for key, value in [('canonical_ack',True),('credential_revoked',False),
                           ('pending_queue_actions',True)]:
            changed = {**phone, key:value}
            (self.android / 'completed.json').write_bytes(bundle.encoded(changed))
            with self.assertRaises(ValueError): self.collect()
        (self.android / 'completed.json').write_bytes(bundle.encoded(phone))
        device['steps'][5]['request_id'] = device['steps'][4]['request_id']
        (self.target / 'device-observation.json').write_bytes(bundle.encoded(device))
        with self.assertRaises(ValueError): self.collect()

    def test_request_bytes_and_receipt_native_bindings_are_independently_recomputed(self):
        device,_=self.completed()
        target=self.target/'device-observation.json'
        for field,value in [('request_sha256','0'*64),('event_id','qre_'+'0'*64),
                            ('native_digest','0'*64),('canonical_commit','qrc_'+'0'*64)]:
            changed=json.loads(json.dumps(device))
            if field=='request_sha256':changed['steps'][1][field]=value
            else:changed['steps'][1]['receipt_event'][field]=value
            target.write_bytes(bundle.encoded(changed))
            with self.assertRaises(ValueError):self.collect()
        target.write_bytes(bundle.encoded(device))
        self.assertTrue(self.collect()['observations_match'])

    def test_changed_source_unknown_entries_and_unfinished_report_preserve_evidence(self):
        self.completed()
        source = self.target / 'sequence.lua'
        original = source.read_bytes()
        source.write_bytes(b'changed source')
        with self.assertRaises(ValueError): self.collect()
        source.write_bytes(original)
        unfinished = self.target / 'device-observation.json.tmp'
        unfinished.write_bytes(b'partial evidence')
        with self.assertRaises(ValueError): self.collect()
        self.assertEqual(unfinished.read_bytes(), b'partial evidence')

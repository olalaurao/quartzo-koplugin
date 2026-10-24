"""Owned fake mount/export safety tests, never physical or canonical ACK proof."""
import base64
import datetime
import json
import pathlib
import os
import shutil
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import time
import unittest
from http.server import BaseHTTPRequestHandler
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


@unittest.skipUnless(sys.platform=='linux','Actual standalone KOReader native SDK requires Linux')
class NativeOutboxBundleTest(unittest.TestCase):
    installed=SequenceBundleTest.installed
    collect=SequenceBundleTest.collect

    def setUp(self):
        SequenceBundleTest.setUp(self)
        import test_pinned_tls_native as tls
        self.model=driver_reference.paired_reference.NativeOutboxPairedSequenceTest()
        self.model.setUp()
        self.addCleanup(self.model.doCleanups)
        model=self.model

        class PairedHost(tls.WireHost):
            def _handler_class(owner):
                class Handler(BaseHTTPRequestHandler):
                    def log_message(self,*args):pass
                    def do_POST(self):
                        length=int(self.headers.get('Content-Length','0'))
                        if self.path!='/reading/activity/v1' or not 0<length<=16384:
                            self.send_error(400);return
                        raw=self.rfile.read(length)
                        model.case.current_time=datetime.datetime.now(datetime.timezone.utc).isoformat(
                            timespec='milliseconds').replace('+00:00','Z').encode()
                        status,response=model.case.transport(raw,
                            self.headers.get('Authorization','').removeprefix('Bearer ').encode(),b'good')
                        self.send_response(status)
                        self.send_header('Content-Length',str(len(response)))
                        self.send_header('Connection','close')
                        self.end_headers()
                        self.wfile.write(response)
                return Handler

        openssl=shutil.which('openssl')
        self.assertIsNotNone(openssl)
        self.host=PairedHost(self.root/'tls-session','127.0.0.1',pathlib.Path(openssl))
        self.host.start()
        self.host_closed=False
        self.addCleanup(self.close_host)
        self.fixture=json.loads(json.dumps(model.native_fixture))
        self.fixture['binding']=dict(model.document['binding'])
        now=int(time.time())
        _,pairing=driver_reference.paired_reference.fixture_and_pairing(now)
        pairing.update(endpoint=self.host.endpoint,binding=self.fixture['binding'],
            certificate_pem=(self.host.directory/'server.pem').read_text())
        pairing['peer_certificate_sha256']=bundle.sha(ssl.PEM_cert_to_DER_cert(pairing['certificate_pem']))
        for name,value in {'private-pairing.json':bundle.encoded(pairing),
                'server.pem':pairing['certificate_pem'].encode(),
                'synthetic-fixture.json':bundle.encoded(self.fixture)}.items():
            (self.session/name).write_bytes(value)
        # Remap only the fixed diagnostic I/O root. Runtime architecture stays
        # genuinely x64; no ARM run is attested by this loopback response model.
        self.values['kindle.lua']=self.values['kindle.lua'].replace(
            b'/mnt/us/extensions/quartzo-wire-tls-probe',str(self.target).encode())
        self.output=self.root/'native-bundle'
        self.manifest=bundle.prepare(self.session,self.output,'a'*40,outbox_seed=model.source)
        reference=pathlib.Path(os.environ['READING_SQLITE_REFERENCE_DIR'])
        wire=pathlib.Path(os.environ['READING_WIRE_REFERENCE_DIR'])
        for key,relative in bundle.OUTBOX_NATIVE.items():
            source=wire/('dkjson.lua' if key=='dkjson' else 'sha2.lua') if key in ('dkjson','sha2') else reference/relative
            destination=self.mount/'koreader'/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,destination)
        self.bootstrap=self.root/'native-bootstrap.lua'
        self.bootstrap.write_text('''
local ref,wire,driver=unpack(arg)
package.path=ref..'/?.lua;'..ref..'/common/?.lua;/usr/share/lua/5.1/?.lua;/usr/share/lua/5.1/?/init.lua;'..package.path
package.cpath='/usr/lib/x86_64-linux-gnu/lua/5.1/?.so;'..package.cpath
bit=require('bit')
local ffi=require('ffi')
ffi.loadlib=function(name,version)
  assert(name=='sqlite3' and version=='0')
  return ffi.load(ref..'/libs/libsqlite3.so.0')
end
package.preload['setupkoenv']=function() return true end
package.preload['libs/libkoreader-lfs']=function()
  return assert(package.loadlib(ref..'/libs/libkoreader-lfs.so','luaopen_lfs'))()
end
package.preload.dkjson=function() return dofile(wire..'/dkjson.lua') end
package.preload['ffi/sha2']=function() return dofile(wire..'/sha2.lua') end
dofile(driver)
''',encoding='utf-8')
        self.reference,self.wire=reference,wire

    def close_host(self):
        if not self.host_closed:
            self.host.close()
            self.host_closed=True

    def tearDown(self):
        self.close_host()
        SequenceBundleTest.tearDown(self)

    def completed(self):
        self.installed()
        with mock.patch.object(driver_reference.paired_reference.legacy,'FIXTURE',self.fixture):
            result=subprocess.run([str(self.mount/'koreader/luajit'),str(self.bootstrap),str(self.reference),
                str(self.wire),str(self.target/'kindle.lua')],cwd=self.mount/'koreader',
                capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,'Actual native two-process driver failed')
        report=bundle.parse((self.target/'device-observation.json').read_bytes())
        seed=bundle.parse((self.target/'seed-observation.json').read_bytes())
        self.assertEqual(report['jit_arch'],'x64')
        self.assertNotEqual(report['source_process_id'],report['seed_process_id'])
        self.assertEqual(seed['source_process_id'],report['seed_process_id'])
        self.assertEqual(report['outbox_pruned'],3)
        self.assertEqual(len(self.model.case.sent),7)
        nonces=[json.loads(item[0])['request_id'] for item in self.model.case.sent]
        self.assertEqual(len(set(nonces)),7)
        self.assertTrue(nonces[0].endswith('0000000000000007'))
        self.assertEqual(self.host.tls_versions,{'TLSv1.2'})
        (self.target/'run.lock').mkdir()
        (self.target/'launcher-status.txt').write_bytes(b'completed\n')
        # A forged ARM label is used ONLY to test the correlation collector:
        # it must still return physical_execution_attested=False and no ACK.
        report['jit_arch']='arm'
        (self.target/'device-observation.json').write_bytes(bundle.encoded(report))
        phone=dict(probe_revision='canonical-paired-wire-v1',phase='completed',run_id=self.fixture['run_id'],
            source_data='synthetic',synthetic_account=True,credential_cleanup_failed=False,unique_events=3,native_seconds=120,
            pending_queue_actions=7,canonical_ack=False,source_cursor_changed=False,statistics_accessed=False,
            wifi_changed=False,physical_execution_attested=False,credential_revoked=True,control_failed=False,
            production_registered=False,cloud_delivery_proven=False,
            canonical_paths=[item['path'] for item in self.fixture['expected_shards']])
        (self.android/'completed.json').write_bytes(bundle.encoded(phone))
        for shard in self.fixture['expected_shards']:
            path=self.android/'vault'/shard['path']
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(base64.b64decode(shard['bytes_base64'],validate=True))
        return report,seed

    def test_actual_two_process_native_sqlite_tls_replay_and_bounded_collection(self):
        self.completed()
        report=self.collect()
        self.assertTrue(report['paired_outbox_observations_match'])
        self.assertEqual(report['outbox_pending'],0)
        self.assertEqual(report['outbox_review_retained'],1)
        self.assertFalse(report['physical_execution_attested'])
        self.assertFalse(report['canonical_ack'])
        self.assertFalse(report['gate4_passed'])

    def test_bad_process_seed_or_retained_review_preserves_and_rejects_evidence(self):
        report,seed=self.completed()
        path=self.target/'device-observation.json'
        bad=dict(report,source_process_id=report['seed_process_id'])
        path.write_bytes(bundle.encoded(bad))
        with self.assertRaises(ValueError):self.collect()
        path.write_bytes(bundle.encoded(report))
        seed_path=self.target/'seed-observation.json'
        bad_seed=json.loads(json.dumps(seed))
        bad_seed['steps'][0]['request_sha256']='0'*64
        seed_path.write_bytes(bundle.encoded(bad_seed))
        with self.assertRaises(ValueError):self.collect()
        seed_path.write_bytes(bundle.encoded(seed))
        state=self.target/'outbox-state/quartzo_sync_state.sqlite3'
        conn=sqlite3.connect(state)
        try:
            conn.execute("UPDATE review SET duration='11'")
            conn.commit()
        finally:conn.close()
        altered=state.read_bytes()
        with self.assertRaises(ValueError):self.collect()
        self.assertEqual(state.read_bytes(),altered)

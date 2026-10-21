"""Bounded actual Lua driver with explicit fake I/O and TLS; no device proof."""
import datetime
import hashlib
import json
import pathlib
import time
import unittest

import test_paired_sequence as paired_reference
from sequence_bundle import SOURCE_MAP

ROOT=pathlib.Path(__file__).resolve().parent
PREFIX=b'/mnt/us/extensions/quartzo-wire-tls-probe/'
FIXTURE=paired_reference.fixture_and_pairing()[0]
FIXTURE_BYTES=json.dumps(FIXTURE,separators=(',',':')).encode()


class WireSequenceDriverTest(unittest.TestCase):
    def setUp(self):
        self.case=paired_reference.legacy.WireSequenceTest();self.case.setUp()
        self.case.authenticated=2
        self.lua=self.case.lua

    def driver(self,mutate=None,changed_config=None,document=None):
        values={name:(ROOT.parents[1]/source).read_bytes().replace(b'\r\n',b'\n') for name,source in SOURCE_MAP.items()}
        values['run.sh']=values['run.sh'].replace(b'quartzo-transport-probe',b'quartzo-wire-tls-probe')
        now=int(time.time())
        fixture,default=paired_reference.fixture_and_pairing(now)
        pairing=json.loads(json.dumps(default if document is None else document))
        actual_pin=pairing['peer_certificate_sha256']
        if changed_config:changed_config(pairing)
        encoded=lambda value:json.dumps(value,separators=(',',':')).encode()
        self.case.fixture=self.case.deps[b'decode_json'](encoded(fixture))
        self.case.binding=self.case.fixture[b'binding']
        self.case.current_time=datetime.datetime.fromtimestamp(now,datetime.timezone.utc).isoformat(
            timespec='milliseconds').replace('+00:00','Z').encode()
        values.update({'private-pairing.json':encoded(pairing),'synthetic-fixture.json':encoded(fixture),
            'server.pem':pairing['certificate_pem'].encode()})
        manifest=dict(probe_revision='canonical-paired-sequence-v1',run_id=fixture['run_id'],
            koreader_baseline='v2026.07.1',source_commit='a'*40,
            files={name:hashlib.sha256(value).hexdigest() for name,value in values.items()})
        fs=self.lua.table_from({PREFIX+name.encode():value for name,value in values.items()})
        fs[PREFIX+b'bundle-manifest.json']=encoded(manifest)
        fs[b'git-rev']=b'v2026.07.1\n'
        fs[b'common/dkjson.lua']=b'synthetic JSON source identity'
        fs[b'ffi/sha2.lua']=b'synthetic SHA source identity'
        if mutate:mutate(fs)
        callback=self.lua.eval('function(fn) return function(...) return fn(...) end end')(self.case.transport)
        https,http,ltn12,counts=paired_reference.native_sdk(self.lua,callback,actual_pin)
        from test_native_provider import libraries
        sha=self.lua.execute(libraries()[1])
        io_stub,os_stub,loader,dofile,reads,output=self.lua.execute('''
          local fs,json,sha,https,http,ltn12,now,prefix=...
          local reads,output={},{}
          local io={open=function(path,mode)
            if mode=='rb' then
              reads[#reads+1]=path
              if fs[path]==nil then return nil end
              return {read=function(_,bound) return fs[path]:sub(1,bound) end,close=function() return true end}
            end
            assert(mode=='wb' and path==prefix..'device-observation.json.tmp' and fs[path]==nil)
            local bytes=''
            return {write=function(_,value) bytes=bytes..value;return true end,
              close=function() fs[path]=bytes;return true end}
          end}
          local os={date=os.date,exit=function(code) output.exit_code=code end,
            rename=function(source,target)
              assert(source==prefix..'device-observation.json.tmp' and target==prefix..'device-observation.json')
              assert(fs[target]==nil);fs[target]=fs[source];fs[source]=nil;return true
            end}
          local function loader(name)
            if name=='setupkoenv' then return true end
            if name=='dkjson' then return json end
            if name=='ffi/sha2' then return sha end
            if name=='socket' then return {gettime=function() return now end} end
            if name=='ssl.https' then return https end
            if name=='socket.http' then return http end
            if name=='ltn12' then return ltn12 end
            error('unexpected_native_module')
          end
          local function dofile(path)
            assert(path:sub(1,#prefix)==prefix and fs[path]);return assert(loadstring(fs[path]))()
          end
          return io,os,loader,dofile,reads,output
        ''',fs,self.case.json,sha,https,http,ltn12,now,PREFIX)
        self.lua.globals()[b'io']=io_stub
        self.lua.globals()[b'os']=os_stub
        self.lua.globals()[b'require']=loader
        self.lua.globals()[b'dofile']=dofile
        self.lua.execute(values['kindle.lua'])
        return json.loads(fs[PREFIX+b'device-observation.json']),list(reads.values()),output

    def test_actual_driver_composes_native_codec_shared_carrier_and_finite_sequence(self):
        report,reads,output=self.driver()
        self.assertEqual(report['phase'],'paired_receipts_checked')
        self.assertEqual(output[b'exit_code'],0)
        self.assertEqual(report['jit_arch'],'x64')
        self.assertEqual(report['attempts'],6)
        self.assertEqual(report['checked_receipts'],5)
        self.assertFalse(report['canonical_ack'])
        self.assertFalse(report['physical_execution_attested'])
        self.assertLess(len(json.dumps(report)),12288)
        self.assertNotIn('t'*43,json.dumps(report))
        allowed={b'git-rev',b'common/dkjson.lua',b'ffi/sha2.lua'}
        allowed.update(PREFIX+name.encode() for name in (*SOURCE_MAP,
            'private-pairing.json','synthetic-fixture.json','server.pem','bundle-manifest.json'))
        self.assertTrue(set(reads)<=allowed)
        self.assertFalse(any(b'statistics' in path or b'sidecar' in path for path in reads))

    def test_changed_source_and_missing_baseline_fail_before_network(self):
        for mutate in (lambda fs:fs.__setitem__(PREFIX+b'client.lua',b'changed'),
                       lambda fs:fs.__setitem__(b'git-rev',b'v2025.04'),
                       lambda fs:fs.__setitem__(PREFIX+b'synthetic-fixture.json',b'x'*65537)):
            self.setUp();report,_,output=self.driver(mutate=mutate)
            self.assertEqual(report['phase'],'failed');self.assertEqual(output[b'exit_code'],1)
            self.assertEqual(self.case.sent,[])

    def test_driver_transport_or_bound_receipt_failure_never_claims_success(self):
        for mutation in ('provider_error','wrong_nonce','wrong_revision','wrong_outcome'):
            self.setUp();self.case.mutation=mutation
            report,_,output=self.driver()
            self.assertEqual(report['phase'],'failed');self.assertEqual(output[b'exit_code'],1)
            self.assertLessEqual(len(self.case.sent),2)
            self.assertNotIn('PRIVATE',json.dumps(report))

    def test_private_input_expiry_bad_scope_and_unknown_fields_cannot_start_a_sequence(self):
        for change in (lambda c:c.__setitem__('expires_at_utc',c['not_before_utc']),
                       lambda c:c['binding'].__setitem__('vault_scope','f'*64),
                       lambda c:c.__setitem__('extra','PRIVATE_SENTINEL'),
                       lambda c:c.__setitem__('token','PRIVATE_SENTINEL')):
            self.setUp();report,_,output=self.driver(changed_config=change)
            self.assertEqual(report['phase'],'failed');self.assertEqual(output[b'exit_code'],1)
            self.assertNotIn('PRIVATE_SENTINEL',json.dumps(report));self.assertEqual(self.case.sent,[])

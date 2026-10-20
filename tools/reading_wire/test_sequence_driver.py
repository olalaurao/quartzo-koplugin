"""Bounded native driver with explicit fake I/O/HTTPS; no physical evidence."""
import datetime
import hashlib
import json
import pathlib
import unittest

import test_sequence as sequence_reference
from sequence_bundle import SOURCE_MAP

ROOT = pathlib.Path(__file__).resolve().parent
PREFIX = b'/mnt/us/extensions/quartzo-wire-tls-probe/'
FIXTURE_BYTES, FIXTURE = sequence_reference.FIXTURE_BYTES, sequence_reference.FIXTURE


class WireSequenceDriverTest(unittest.TestCase):
    def setUp(self):
        self.case = sequence_reference.WireSequenceTest()
        self.case.setUp()
        self.lua = self.case.lua

    def driver(self, mutate=None, changed_config=None):
        values = {name: (ROOT.parents[1] / source).read_bytes().replace(b'\r\n', b'\n')
                  for name, source in SOURCE_MAP.items()}
        values['run.sh'] = values['run.sh'].replace(b'quartzo-transport-probe', b'quartzo-wire-tls-probe')
        now = int(datetime.datetime(2026, 10, 20, 10, 1, tzinfo=datetime.timezone.utc).timestamp())
        config = dict(endpoint='https://127.0.0.1:8443', token='t' * 43, run_id=FIXTURE['run_id'],
                      not_before_epoch=now-1, expires_at_epoch=now+120)
        if changed_config:
            changed_config(config)
        values.update({'private-session.json': json.dumps(config, separators=(',', ':')).encode(),
            'synthetic-fixture.json': FIXTURE_BYTES, 'server.pem': b'synthetic-public-certificate',
            'untrusted.pem': b'synthetic-untrusted-certificate'})
        manifest = dict(probe_revision='canonical-wire-sequence-v1', run_id=FIXTURE['run_id'],
            koreader_baseline='v2026.07.1', source_commit='a' * 40,
            files={name: hashlib.sha256(value).hexdigest() for name, value in values.items()})
        fs = self.lua.table_from({PREFIX + name.encode(): value for name, value in values.items()})
        fs[PREFIX + b'bundle-manifest.json'] = json.dumps(manifest, separators=(',', ':')).encode()
        fs[b'git-rev'] = b'v2026.07.1\n'
        fs[b'common/dkjson.lua'] = b'synthetic JSON source identity'
        fs[b'ffi/sha2.lua'] = b'synthetic SHA source identity'
        if mutate:
            mutate(fs)
        wrap = self.lua.eval('function(fn) return function(...) return fn(...) end end')
        # Each read/write/rename/module path is checked in the actual Lua driver.
        # All real host filesystem/process/network access is excluded from it.
        io_stub, os_stub, loader, dofile, reads, output = self.lua.execute('''
          local fs,json,sha,send,now,prefix = ...
          local reads,output = {},{}
          local io = {open=function(path,mode)
            if mode=='rb' then
              reads[#reads+1]=path
              if fs[path]==nil then return nil end
              return {read=function(_,bound) return fs[path]:sub(1,bound) end,close=function() return true end}
            end
            assert(mode=='wb' and path==prefix..'device-observation.json.tmp' and fs[path]==nil)
            local data=''
            return {write=function(_,bytes) data=data..bytes; return true end,
              close=function() fs[path]=data; return true end}
          end}
          local os = {date=os.date,exit=function(code) output.exit_code=code end,
            rename=function(source,target)
              assert(source==prefix..'device-observation.json.tmp' and target==prefix..'device-observation.json')
              assert(fs[target]==nil); fs[target]=fs[source]; fs[source]=nil; return true
            end}
          local https = {_VERSION='synthetic-http-api',request=function(r)
            assert(r.protocol=='tlsv1_2' and r.verify=='peer' and r.redirect==false)
            assert(r.url=='https://127.0.0.1:8443/reading/activity/v1')
            assert(r.headers['x-quartzo-reading-binding']=='synthetic-wire-0123456789abcdef0123456789abcdef')
            local body=r.source()
            assert(tonumber(r.headers['content-length'])==#body)
            local status,response=send(body,r.headers.authorization:sub(8),r.cafile==prefix..'untrusted.pem' and 'bad' or 'good')
            if not status then return nil,'certificate_failed' end
            assert(r.sink(response)); return 1,status,{}
          end}
          local ltn12 = {source={string=function(value)
            return function() local current=value; value=nil; return current end
          end}}
          local function loader(name)
            if name=='setupkoenv' then return true end
            if name=='dkjson' then return json end
            if name=='ffi/sha2' then return sha end
            if name=='socket' then return {gettime=function() return now end,sleep=function(n) assert(n==1); output.paused=true end} end
            if name=='ssl.https' then return https end
            if name=='ltn12' then return ltn12 end
            error('unexpected_native_module')
          end
          local function dofile(path)
            assert(path:sub(1,#prefix)==prefix and fs[path]); return assert(loadstring(fs[path]))()
          end
          return io,os,loader,dofile,reads,output
        ''', fs, self.case.json, self.case.lua.execute(self._sha_bytes()),
            wrap(self.case.transport), now, PREFIX)
        self.lua.globals()[b'io'] = io_stub
        self.lua.globals()[b'os'] = os_stub
        self.lua.globals()[b'require'] = loader
        self.lua.globals()[b'dofile'] = dofile
        self.lua.execute(values['kindle.lua'])
        return json.loads(fs[PREFIX + b'device-observation.json']), list(reads.values()), output

    def _sha_bytes(self):
        from test_native_provider import libraries
        return libraries()[1]

    def test_actual_driver_composes_native_codec_shared_carrier_and_finite_sequence(self):
        report, reads, output = self.driver()
        self.assertEqual(report['phase'], 'wire_claims_checked')
        self.assertEqual(output[b'exit_code'], 0)
        self.assertTrue(output[b'paused'])
        self.assertEqual(report['jit_arch'], 'x64')
        self.assertEqual(report['attempts'], 10)
        self.assertFalse(report['canonical_ack'])
        self.assertFalse(report['physical_execution_attested'])
        self.assertLess(len(json.dumps(report)), 12288)
        self.assertNotIn('t' * 43, json.dumps(report))
        allowed = {b'git-rev', b'common/dkjson.lua', b'ffi/sha2.lua'}
        allowed.update(PREFIX + name.encode() for name in (*SOURCE_MAP,
            'private-session.json', 'synthetic-fixture.json', 'server.pem', 'untrusted.pem', 'bundle-manifest.json'))
        self.assertTrue(set(reads) <= allowed)
        self.assertFalse(any(b'statistics' in path or b'sidecar' in path for path in reads))

    def test_changed_source_and_missing_baseline_fail_before_network(self):
        for mutate in (
            lambda fs: fs.__setitem__(PREFIX + b'client.lua', b'changed'),
            lambda fs: fs.__setitem__(b'git-rev', b'v2025.04'),
            lambda fs: fs.__setitem__(PREFIX + b'synthetic-fixture.json', b'x' * 65537),
        ):
            with self.subTest(mutate=mutate):
                self.setUp()
                report, _, output = self.driver(mutate=mutate)
                self.assertEqual(report['phase'], 'failed')
                self.assertEqual(output[b'exit_code'], 1)
                self.assertEqual(self.case.sent, [])

    def test_private_input_expiry_bad_scope_and_unknown_fields_cannot_start_a_sequence(self):
        for change in (
            lambda c: c.__setitem__('expires_at_epoch', c['not_before_epoch']),
            lambda c: c.__setitem__('run_id', 'f' * 32),
            lambda c: c.__setitem__('extra', 'PRIVATE_SENTINEL'),
            lambda c: c.__setitem__('token', 'PRIVATE_SENTINEL'),
        ):
            with self.subTest(change=change):
                self.setUp()
                report, _, output = self.driver(changed_config=change)
                self.assertEqual(report['phase'], 'failed')
                self.assertEqual(output[b'exit_code'], 1)
                self.assertNotIn('PRIVATE_SENTINEL', json.dumps(report))
                self.assertEqual(self.case.sent, [])

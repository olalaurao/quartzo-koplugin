"""Real LuaJIT/providers/codec with explicit injected TLS, never physical proof."""
import copy
import datetime
import hashlib
import json
import os
import pathlib
import ssl
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from unittest import mock

import test_sequence as legacy

ROOT=pathlib.Path(__file__).resolve().parent


def fixture_and_pairing(epoch=1792490460):
    fixture=copy.deepcopy(legacy.FIXTURE)
    fixture['binding'].update(binding_id='qrp_'+'a'*32,vault_scope='b'*64)
    utc=lambda value:datetime.datetime.fromtimestamp(value,datetime.timezone.utc).isoformat(
        timespec='milliseconds').replace('+00:00','Z')
    der=b'synthetic public DER fixture; not actual TLS'
    document=dict(pairing_version=1,receiver_role='canonical_reading_activity_v1',
        endpoint='https://127.0.0.1:8443',certificate_pem=ssl.DER_cert_to_PEM_cert(der),
        peer_certificate_sha256=hashlib.sha256(der).hexdigest(),binding=copy.deepcopy(fixture['binding']),
        token='t'*43,not_before_utc=utc(epoch-1),expires_at_utc=utc(epoch+1200))
    return fixture,document


def native_sdk(lua,callback,pin):
    return lua.execute('''
      local send,pin=...
      local counts={http=0,sends=0,closes=0}
      local https={_VERSION='1.3.2',tcp=function()
        return function()
          local c={settimeout=function() return 1 end,connect=function() return 1 end,
            getpeercertificate=function() return {digest=function(_,algorithm)
              assert(algorithm=='sha256');return pin end} end,
            send=function(_,bytes) counts.sends=counts.sends+1;return #bytes end,
            receive=function() return 'synthetic response' end,
            getfd=function() return 1 end,dirty=function() return false end}
          c.sock={close=function() counts.closes=counts.closes+1;return 1 end}
          c.close=function() return c.sock:close() end
          return c
        end
      end}
      local http={request=function(r)
        counts.http=counts.http+1
        local host,port=r.url:match('^https://([^:]+):(%d+)/reading/activity/v1$')
        assert(host and r.method=='POST' and r.protocol=='tlsv1_2' and r.verify=='peer' and not r.redirect)
        local c=r.create();assert(c:settimeout(5));assert(c:connect(host,tonumber(port)))
        assert(c:send('Authorization: '..r.headers.authorization..'\\r\\n'))
        local bytes=r.source();assert(#bytes==tonumber(r.headers['content-length']));assert(c:send(bytes))
        local status,body=send(bytes,r.headers.authorization:sub(8),'good')
        if not status then c:close();return nil,body end
        assert(r.sink(body));c:close();return 1,status,{}
      end}
      local ltn12={source={string=function(value)
        return function() local result=value;value=nil;return result end end}}
      return https,http,ltn12,counts
    ''',callback,pin.encode())


class PairedSequenceTest(unittest.TestCase):
    def setUp(self):
        self.case=legacy.WireSequenceTest();self.case.setUp()
        self.case.authenticated=2 # Normal receiver model, without legacy injected HTTP faults.
        self.lua=self.case.lua
        epoch=int(datetime.datetime(2026,10,20,10,1,tzinfo=datetime.timezone.utc).timestamp())
        self.fixture,self.document=fixture_and_pairing(epoch)
        encoded=lambda value:json.dumps(value,separators=(',',':')).encode()
        self.bytes=encoded(self.fixture)
        self.case.fixture=self.case.deps[b'decode_json'](self.bytes)
        self.case.binding=self.case.fixture[b'binding']
        self.raw=encoded(self.document)
        self.module=self.lua.execute((ROOT/'paired_sequence.lua').read_bytes())
        self.paired=self.lua.execute((ROOT.parents[1]/'quartzo.koplugin/quartzo/paired_exchange.lua').read_bytes())
        callback=self.lua.eval('function(fn) return function(...) return fn(...) end end')(self.case.transport)
        https,http,ltn12,self.counts=native_sdk(self.lua,callback,self.document['peer_certificate_sha256'])
        self.runtime=self.case.runtime
        self.runtime[b'document_bytes']=self.raw
        self.runtime[b'approved_sha256']=hashlib.sha256(self.raw).hexdigest().encode()
        self.runtime[b'carrier']=self.case.client
        self.runtime[b'ca_file']=b'/fixture/public.pem'
        self.runtime[b'https'],self.runtime[b'http'],self.runtime[b'ltn12']=https,http,ltn12

    def run_sequence(self):
        return self.module[b'run'](self.case.deps,self.case.codec_module,self.paired,self.case.fixture,self.runtime)

    def test_receipts_bind_all_three_batches_discard_and_replay_without_cursor(self):
        report=self.run_sequence()
        self.assertEqual(report[b'phase'],b'paired_receipts_checked')
        self.assertEqual(report[b'attempts'],6)
        self.assertEqual(report[b'checked_receipts'],5)
        self.assertEqual(report[b'deliberately_discarded_responses'],1)
        self.assertEqual(len(self.case.sent),6)
        self.assertEqual(len({json.loads(item[0])['request_id'] for item in self.case.sent}),6)
        self.assertEqual(len({json.loads(item[0])['batch_id'] for item in self.case.sent}),3)
        for index in range(0,6,2):
            self.assertEqual(json.loads(self.case.sent[index][0])['event_lines'],
                json.loads(self.case.sent[index+1][0])['event_lines'])
        for key in ('canonical_ack','physical_execution_attested','canonical_persistence_proven',
                    'source_cursor_changed','statistics_accessed','wifi_changed'):
            self.assertFalse(report[key.encode()])
        self.assertNotIn(b't'*43,self.case.json[b'encode'](report))

    def test_wrong_nonce_revision_outcome_or_provider_error_never_finishes(self):
        for mutation in ('wrong_nonce','wrong_revision','wrong_outcome','provider_error'):
            self.setUp();self.case.mutation=mutation
            report=self.run_sequence()
            self.assertEqual(report[b'phase'],b'failed')
            self.assertNotIn(b'PRIVATE',self.case.json[b'encode'](report))
            self.assertLessEqual(len(self.case.sent),2)

    def test_changed_approval_or_expired_pairing_stops_before_network(self):
        self.runtime[b'approved_sha256']=b'0'*64
        self.assertEqual(self.run_sequence()[b'phase'],b'failed')
        self.assertEqual(self.case.sent,[])
        self.setUp();self.case.current_time=b'2026-10-20T10:30:00.000Z'
        self.assertEqual(self.run_sequence()[b'phase'],b'failed')
        self.assertEqual(self.case.sent,[])

    def test_reused_nonce_preserves_first_fact_without_second_request(self):
        self.runtime[b'nonce']=self.lua.eval("function() return 'qrtr_'..string.rep('0',32) end")
        self.assertEqual(self.run_sequence()[b'phase'],b'failed')
        self.assertEqual(len(self.case.sent),1)

    def test_failed_attempt_reports_only_allowlisted_code_without_receipt_or_private_detail(self):
        for reason,expected in [(b'reading_peer_pin_mismatch',b'reading_peer_pin_mismatch'),
                (b'PRIVATE_TOKEN_PRIVATE_PATH',b'paired_sequence_failed')]:
            self.setUp()
            self.paired[b'attempt']=self.lua.eval('function(reason) return function() return nil,reason end end')(reason)
            report=self.run_sequence()
            self.assertEqual(report[b'phase'],b'failed')
            self.assertEqual(report[b'error_code'],expected)
            self.assertEqual(report[b'attempts'],1)
            self.assertEqual(report[b'checked_receipts'],0)
            self.assertEqual(self.case.sent,[])
            self.assertNotIn(b'PRIVATE',self.case.json[b'encode'](report))


@unittest.skipUnless(sys.platform=='linux','Actual pinned KOReader SQLite SDK requires Linux')
class NativeOutboxPairedSequenceTest(unittest.TestCase):
    run_sequence=PairedSequenceTest.run_sequence

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='reading-paired-outbox-test-')
        self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name)
        self.source=self.root/'quartzo_sync_state.sqlite3'
        self.native_fixture=json.loads((ROOT/'outbox_sequence_fixture.json').read_bytes())
        self.configure()
        queue=self.outbox[b'create'](os.fsencode(self.root),
            self.native_fixture['binding']['source_epoch'].encode(),self.outbox_runtime)
        self.assertNotIsInstance(queue,tuple)
        self.assertEqual(queue[b'context']()[b'device_id'],
            self.native_fixture['binding']['device_id'].encode())

    def configure(self):
        PairedSequenceTest.setUp(self)
        fixture=copy.deepcopy(self.native_fixture)
        fixture['binding'].update(binding_id='qrp_'+'a'*32,vault_scope='b'*64)
        raw=json.dumps(fixture,separators=(',',':')).encode()
        self.case.fixture=self.case.deps[b'decode_json'](raw)
        self.case.binding=self.case.fixture[b'binding']
        self.document['binding']=fixture['binding']
        self.raw=json.dumps(self.document,separators=(',',':')).encode()
        self.runtime[b'document_bytes']=self.raw
        self.runtime[b'approved_sha256']=hashlib.sha256(self.raw).hexdigest().encode()
        # Reuse the pinned SDK verifier; no replacement SQL implementation.
        sys.path.insert(0,str(ROOT.parent/'plugin'))
        try:
            from prepare_sqlite_reference import verify
        finally:
            sys.path.pop(0)
        reference=pathlib.Path(os.environ['READING_SQLITE_REFERENCE_DIR'])
        verify(reference)
        sdk=self.lua.execute('''
          local root=...
          bit=require('bit')
          local ffi=require('ffi')
          ffi.loadlib=function(name,version)
            assert(name=='sqlite3' and version=='0')
            return ffi.load(root..'/libs/libsqlite3.so.0')
          end
          package.path=root..'/?.lua;'..package.path
          return dofile(root..'/common/lua-ljsqlite3/init.lua')
        ''',os.fsencode(reference))
        wrap=self.lua.eval('function(fn) return function(...) return fn(...) end end')
        attributes=wrap(lambda path:self.lua.table_from({b'mode':b'file'})
            if pathlib.Path(os.fsdecode(path)).is_file() else None)
        self.outbox=self.lua.execute((ROOT.parents[1]/'quartzo.koplugin/quartzo/outbox.lua').read_bytes())
        self.outbox_runtime=self.lua.table_from({b'codec':self.case.codec,b'sqlite':sdk,
            b'attributes':attributes,b'entropy':self.lua.eval("function() return string.rep('A',16) end")})
        self.runtime[b'outbox']=self.outbox
        self.runtime[b'queue_root']=os.fsencode(self.root)
        self.runtime[b'sqlite']=sdk
        self.runtime[b'attributes']=attributes
        self.lua.globals().package.loaded[b'quartzo/paired_exchange']=self.paired

    def run_native(self):
        # Only the injected test response model consumes this generated fixture.
        # Opaque receipt issuance and pruning still use the real Lua owners.
        with mock.patch.object(legacy,'FIXTURE',self.native_fixture):
            return self.run_sequence()

    def rows(self):
        with closing(sqlite3.connect(self.source.resolve().as_uri()+'?mode=ro',uri=True)) as conn:
            context=conn.execute('SELECT device_id,source_epoch FROM identity').fetchone()
            lines={row[0] for row in conn.execute('SELECT line FROM pending')}
            review=conn.execute('SELECT COUNT(*) FROM review').fetchone()[0]
        return context,lines,review

    def seed(self):
        self.runtime[b'seed_only']=True
        self.runtime[b'nonce']=self.lua.eval("function() return 'qrtr_'..string.format('%032x',7) end")
        report=self.run_native()
        self.assertEqual(report[b'phase'],b'outbox_seed_receipt_discarded')
        self.assertEqual(report[b'attempts'],1)
        self.assertEqual(report[b'outbox_pruned'],0)
        self.assertEqual(report[b'outbox_final_pending'],3)
        self.assertEqual(report[b'deliberately_discarded_responses'],1)
        return report

    def test_lost_receipt_survives_fresh_vm_then_exact_receipts_prune_and_retain_review(self):
        self.seed()
        context,lines,review=self.rows()
        expected={batch['event_lines'][-1] for batch in self.native_fixture['batches']}
        self.assertEqual(lines,expected)
        self.assertEqual(review,1)
        old_vm=self.lua
        self.configure() # Fresh Lua VM and actual native SQLite handle composition.
        self.assertIsNot(self.lua,old_vm)
        self.runtime[b'expected_seed_pending']=True
        report=self.run_native()
        self.assertEqual(report[b'phase'],b'paired_receipts_checked')
        self.assertEqual(report[b'outbox_pruned'],3)
        self.assertEqual(report[b'outbox_final_pending'],0)
        self.assertEqual(report[b'outbox_raw_receipt_rejections'],5)
        self.assertEqual(set(report[b'outbox_selected_sha256'].values()),
            {hashlib.sha256(line.encode()).hexdigest().encode() for line in expected})
        self.assertTrue(report[b'outbox_identity_preserved'])
        self.assertEqual([step[b'outbox_pending'] for step in report[b'steps'].values()],
            [3,2,1,1,0,0])
        self.assertEqual(self.rows(),(context,set(),1))
        for key in ('canonical_ack','physical_execution_attested','canonical_persistence_proven',
                    'source_cursor_changed','statistics_accessed','wifi_changed'):
            self.assertFalse(report[key.encode()])

    def test_native_context_requires_existing_state_and_prior_seed_before_network(self):
        before=self.source.read_bytes()
        self.assertEqual(self.run_native()[b'phase'],b'failed')
        self.assertEqual(self.case.sent,[])
        self.assertEqual(self.source.read_bytes(),before)
        self.runtime[b'outbox']=None
        self.assertEqual(self.run_native()[b'phase'],b'failed')
        self.assertEqual(self.case.sent,[])

    def test_wrong_receipt_revision_after_restart_preserves_selected_bytes_and_review(self):
        self.seed()
        original=self.rows()
        self.configure()
        self.runtime[b'expected_seed_pending']=True
        self.case.mutation='wrong_revision'
        self.assertEqual(self.run_native()[b'phase'],b'failed')
        self.assertEqual(self.rows(),original)

    def test_native_fixture_provenance_and_false_acceptance_flags(self):
        raw=(ROOT/'outbox_sequence_fixture.json').read_bytes()
        proof=json.loads((ROOT/'outbox_sequence_fixture.provenance.json').read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),proof['fixtureSha256'])
        self.assertEqual(proof['sourceCommit'],'bdd95aa87491cd57d1914a265cb2c088928cfa17')
        for key in ('canonicalAck','physicalExecutionAttested','nativeEntropyProven','sourceGenerationVerified'):
            self.assertFalse(proof['proof'][key])


if __name__=='__main__':unittest.main()

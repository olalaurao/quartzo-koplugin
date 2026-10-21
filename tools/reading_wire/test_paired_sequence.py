"""Real LuaJIT/providers/codec with explicit injected TLS, never physical proof."""
import copy
import datetime
import hashlib
import json
import pathlib
import ssl
import unittest

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
        self.paired=self.lua.execute((ROOT/'paired_exchange.lua').read_bytes())
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


if __name__=='__main__':unittest.main()

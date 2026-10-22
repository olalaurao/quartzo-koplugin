"""Actual Lua logic with an injected SDK model, never native TLS/device proof."""
import unittest

import test_exchange as exchange_reference


class PinnedTransportTest(unittest.TestCase):
    def setUp(self):
        self.harness = exchange_reference.WireExchangeTest()
        self.harness.setUp()
        self.lua = self.harness.lua
        self.config = self.harness.config
        self.pin = b'1' * 64
        self.config[b'peer_certificate_sha256'] = self.pin

    def make(self, case='ok', digest=None, version='1.3.2'):
        self.lua.globals()[b'pin_case'] = case.encode()
        self.lua.globals()[b'peer_digest'] = self.pin if digest is None else digest
        self.lua.globals()[b'sdk_version'] = version.encode()
        return self.lua.execute(r'''
          local counts={http=0,tls=0,sends=0,closes=0}
          local https={_VERSION=sdk_version,TIMEOUT=60}
          https.tcp=function(params)
            tls_params=params
            return function()
              counts.tls=counts.tls+1
              local sock={close=function() counts.closes=counts.closes+1; return 1 end}
              local native={sock=sock,settimeout=function() return 1 end}
              function native:connect(host,port)
                assert(host=='127.0.0.1' and tonumber(port)==8443)
                if pin_case=='certificate_error' then error('certificate verify failed PRIVATE_PATH') end
                if pin_case=='timeout' then error('timeout PRIVATE_TOKEN') end
                self.close=function() return sock:close() end
                self.getpeercertificate=function()
                  if pin_case=='no_certificate' then return nil end
                  return {digest=function(_,algorithm)
                    assert(algorithm=='sha256')
                    if pin_case=='digest_error' then error('PRIVATE_CERTIFICATE') end
                    return peer_digest
                  end}
                end
                self.send=function(_,value) counts.sends=counts.sends+1; return #value end
                self.receive=function() return 'synthetic' end
                return 1
              end
              return native
            end
          end
          local http={request=function(r)
            counts.http=counts.http+1; captured=r
            if pin_case=='never_connect' then r.sink(response_bytes); return 1,200,{} end
            local c=r.create(); assert(c:settimeout(60))
            if pin_case=='early_send' then
              local ok=c:send('Authorization: PRIVATE_TOKEN')
              assert(not ok); r.sink(response_bytes); return 1,200,{}
            end
            assert(c:connect(pin_case=='wrong_destination' and '127.0.0.2' or '127.0.0.1',8443))
            if pin_case=='second_connection' then r.create() end
            assert(c:send('Authorization: '..r.headers.authorization..'\r\n'))
            captured_body=r.source(); assert(c:send(captured_body))
            r.sink(response_bytes); c:close()
            return 1,pin_case=='redirect' and 302 or 200,{}
          end}
          local ltn12={source={string=function(value)
            return function() local result=value;value=nil;return result end
          end}}
          local send=carrier.pinned_wire_transport(config,https,ltn12,http)
          return send,counts,http,https
        ''')

    def send(self, carrier, token=None, trust=b'good'):
        return carrier(self.harness.sent, self.harness.token if token is None else token, trust)

    def test_verified_native_api_pin_precedes_header_and_payload_and_delivery_is_not_ack(self):
        self.config[b'bad_ca_file'] = None
        send, counts, _, _ = self.make()
        status, body, _, delivery = self.send(send)
        self.assertEqual(status, 200)
        self.assertEqual(body, self.lua.globals()[b'response_bytes'])
        self.assertEqual(counts[b'sends'], 2)
        self.assertEqual(counts[b'closes'], 1)
        self.assertEqual(self.lua.globals()[b'tls_params'][b'verify'], b'peer')
        self.assertEqual(self.lua.globals()[b'tls_params'][b'protocol'], b'tlsv1_2')
        self.assertEqual(self.lua.globals()[b'captured_body'], self.harness.sent)
        self.assertEqual(self.lua.globals()[b'captured'][b'url'], b'https://127.0.0.1:8443/reading/activity/v1')
        self.assertFalse(self.lua.globals()[b'captured'][b'redirect'])
        self.assertIsNone(delivery[b'canonical_ack'])
        self.assertIsNone(delivery[b'accepted_events'])
        read = self.lua.globals()[b'carrier'][b'read_pinned_delivery']
        self.assertEqual(read(delivery, self.harness.sent, self.harness.token, self.config), (200, body))
        result, failure = self.harness.attempt(send)
        self.assertIsNone(failure)
        self.assertFalse(result[b'canonical_ack'])
        self.assertIsNone(result[b'accepted_events'])

    def test_mismatch_and_missing_certificate_api_close_without_sending_headers(self):
        for case, digest in [('ok', b'2'*64), ('ok', b'not-a-fingerprint'),
                             ('no_certificate', None), ('digest_error', None),
                             ('certificate_error', None), ('timeout', None)]:
            with self.subTest(case=case, digest=digest):
                send, counts, _, _ = self.make(case, digest)
                result = self.send(send)
                self.assertIsNone(result[0])
                self.assertNotIn(b'PRIVATE', result[1])
                self.assertEqual(counts[b'sends'], 0)
                self.assertEqual(counts[b'closes'], 1)

    def test_missing_handshake_early_write_or_second_connection_never_grants_delivery(self):
        for case in ['never_connect', 'early_send', 'second_connection', 'wrong_destination']:
            with self.subTest(case=case):
                send, counts, _, _ = self.make(case)
                result = self.send(send)
                self.assertIsNone(result[0])
                self.assertEqual(counts[b'sends'], 0)
                self.assertLessEqual(counts[b'tls'], 1)

    def test_proxy_redirect_bad_trust_and_header_injection_have_no_authority(self):
        send, counts, http, _ = self.make()
        http[b'PROXY'] = b'http://PRIVATE_PROXY'
        self.assertIsNone(self.send(send)[0])
        self.assertEqual(counts[b'http'], 0)
        send, counts, _, _ = self.make('redirect')
        result = self.send(send)
        self.assertEqual(result[0], 302)
        self.assertLessEqual(len(result), 3)
        for token, trust in [(b't'*43, b'bad'), (b'PRIVATE\r\nX: value', b'good')]:
            send, counts, _, _ = self.make()
            self.assertIsNone(self.send(send, token, trust)[0])
            self.assertEqual(counts[b'http'], 0)

    def test_pin_and_supported_sdk_are_mandatory_before_io(self):
        for pin in [None, b'', b'1'*63, b'A'*64, b'x'*64]:
            self.config[b'peer_certificate_sha256'] = pin
            with self.assertRaises(Exception):
                self.make()
        self.config[b'peer_certificate_sha256'] = self.pin
        with self.assertRaises(Exception):
            self.make(version='unsupported')

    def test_delivery_cannot_be_forged_retargeted_or_rebound_to_other_bytes_or_token(self):
        send, _, _, _ = self.make()
        _, body, _, delivery = self.send(send)
        read = self.lua.globals()[b'carrier'][b'read_pinned_delivery']
        self.assertEqual(read(delivery, self.harness.sent, self.harness.token, self.config), (200, body))
        self.assertIsNone(read(self.lua.table(), self.harness.sent, self.harness.token, self.config)[0])
        self.assertIsNone(read(delivery, self.harness.sent+b' ', self.harness.token, self.config)[0])
        self.assertIsNone(read(delivery, self.harness.sent, b'2'*43, self.config)[0])
        for key, value in [(b'endpoint', b'https://127.0.0.2:8443'),
                           (b'binding_id', b'other'), (b'peer_certificate_sha256', b'2'*64)]:
            original = self.config[key]
            self.config[key] = value
            self.assertIsNone(read(delivery, self.harness.sent, self.harness.token, self.config)[0])
            self.config[key] = original

    def test_response_bound_blocks_partial_success_and_closes_connection(self):
        self.lua.globals()[b'response_bytes'] = b'x'*524289
        send, counts, _, _ = self.make()
        result = self.send(send)
        self.assertIsNone(result[0])
        self.assertEqual(counts[b'closes'], 1)


if __name__ == '__main__':
    unittest.main()

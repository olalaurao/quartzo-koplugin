"""Real Lua/codec with injected HTTPS only; no native TLS or physical ACK proof."""
import copy
import pathlib
import unittest

import test_codec as reference


ROOT = pathlib.Path(__file__).resolve().parent


class WireExchangeTest(unittest.TestCase):
    def setUp(self):
        self.reference = reference.WireCodecTest()
        self.reference.setUp()
        self.lua = self.reference.lua
        self.exchange = self.lua.execute((ROOT / 'exchange.lua').read_text(encoding='utf-8'))
        self.lua.globals()[b'carrier'] = self.lua.execute(
            (ROOT.parent / 'transport_probe/client.lua').read_text(encoding='utf-8'))
        self.config = self.reference.to_lua(dict(endpoint='https://127.0.0.1:8443',
            binding_id=self.reference.binding['binding_id'], ca_file='/fixture/ca.pem',
            bad_ca_file='/fixture/bad-ca.pem'))
        self.lua.globals()[b'config'] = self.config
        self.lua.globals()[b'response_bytes'] = reference.VECTOR['response_json'].encode()
        self.lua.globals()[b'now_utc'] = reference.NOW.encode()
        self.token = b't' * 43
        self.now = self.lua.eval('function() return now_utc end')
        self.sent = reference.VECTOR['request_json'].encode()
        self.binding = self.reference.to_lua(self.reference.binding)

    def carrier(self, status=200, body=None, injected=''):
        self.lua.globals()[b'status'] = status
        if body is not None:
            self.lua.globals()[b'response_bytes'] = body
        # Fixed test source only, never code loaded from a response/document.
        return self.lua.execute('''
          local calls = 0
          local https = {request=function(r)
            calls = calls+1
            captured = r
            captured_body = r.source()
            INJECTED
            r.sink(response_bytes)
            return 1,status,{}
          end}
          local ltn12 = {source={string=function(value)
            return function() local result=value; value=nil; return result end
          end}}
          local send = carrier.wire_transport(config, https, ltn12)
          return send, function() return calls end
        '''.replace('INJECTED', injected))

    def attempt(self, send, request=None, token=None):
        return self.exchange[b'attempt'](self.reference.codec, self.binding, self.now,
            self.sent if request is None else request, send, self.token if token is None else token)

    def test_exact_wire_uses_shared_tls_carrier_and_remains_untrusted(self):
        send, calls = self.carrier()
        result, failure = self.attempt(send)
        self.assertIsNone(failure)
        self.assertFalse(result[b'canonical_ack'])
        self.assertIsNone(result[b'accepted_events'])
        self.assertEqual(result[b'untrusted_claims'][1][b'outcome'], b'committed')
        self.assertEqual(calls(), 1)
        self.assertEqual(self.lua.globals()[b'captured_body'], self.sent)
        r = self.lua.globals()[b'captured']
        self.assertEqual(r[b'url'], b'https://127.0.0.1:8443/reading/activity/v1')
        self.assertEqual(r[b'verify'], b'peer')
        self.assertEqual(r[b'protocol'], b'tlsv1_2')
        self.assertFalse(r[b'redirect'])
        self.assertEqual(r[b'headers'][b'authorization'], b'Bearer ' + self.token)
        self.assertEqual(r[b'headers'][b'x-quartzo-reading-binding'], self.binding[b'binding_id'])
        self.assertEqual(int(r[b'headers'][b'content-length']), len(self.sent))

    def test_invalid_request_is_refused_before_network(self):
        send, calls = self.carrier()
        self.assertEqual(self.attempt(send, request=b' ' + self.sent), (None, b'invalid_reading_wire'))
        self.assertEqual(calls(), 0)

    def test_header_injection_and_wrong_bearer_shape_never_reach_network(self):
        for token in (b'secret\r\nInjected: value', b't' * 64, b't' * 42, b'+' * 43):
            send, calls = self.carrier()
            self.assertEqual(self.attempt(send, token=token), (None, b'reading_transport_failed'))
            self.assertEqual(calls(), 0)

    def test_response_nonce_scope_and_position_are_rechecked_by_actual_codec(self):
        for field in ('request_id', 'vault_scope', 'line_digest'):
            changed = copy.deepcopy(reference.VECTOR['response'])
            if field == 'line_digest':
                changed['results'][0][field] = '0' * 64
            else:
                changed[field] = 'other'
            send, _ = self.carrier(body=reference.compact(changed))
            self.assertEqual(self.attempt(send), (None, b'invalid_reading_wire'))

    def test_expiry_after_network_prevents_a_matching_claim_from_being_returned(self):
        send, calls = self.carrier(injected="now_utc='2026-10-17T12:05:00.000Z'")
        self.assertEqual(self.attempt(send), (None, b'invalid_reading_wire'))
        self.assertEqual(calls(), 1)

    def test_http_failures_and_redirect_never_become_claims_or_hidden_retries(self):
        for status, reason in ((401, b'reading_http_unauthorized'), (429, b'reading_http_retryable'),
                               (503, b'reading_http_retryable'), (302, b'reading_transport_failed')):
            send, calls = self.carrier(status=status)
            self.assertEqual(self.attempt(send), (None, reason))
            self.assertEqual(calls(), 1)

    def test_provider_errors_never_expose_token_paths_or_remote_excerpts(self):
        send, _ = self.carrier(injected="error('PRIVATE_TOKEN_PRIVATE_PATH_REMOTE_EXCERPT')")
        result = self.attempt(send)
        self.assertEqual(result, (None, b'reading_transport_failed'))
        self.assertNotIn(b'PRIVATE', result[1])

    def test_response_bound_is_enforced_even_if_https_ignores_sink_rejection(self):
        send, calls = self.carrier(body=b'x' * 524289)
        self.assertEqual(self.attempt(send), (None, b'reading_transport_failed'))
        self.assertEqual(calls(), 1)

    def test_endpoint_trust_and_header_binding_are_captured_before_network(self):
        send, calls = self.carrier()
        self.config[b'endpoint'] = b'https://8.8.8.8:8443'
        self.config[b'ca_file'] = b'/other/trust.pem'
        self.config[b'binding_id'] = b'other-binding'
        result, failure = self.attempt(send)
        self.assertIsNone(failure)
        self.assertFalse(result[b'canonical_ack'])
        self.assertEqual(calls(), 1)
        self.assertEqual(self.lua.globals()[b'captured'][b'cafile'], b'/fixture/ca.pem')
        self.assertEqual(self.lua.globals()[b'captured'][b'headers'][b'x-quartzo-reading-binding'], self.binding[b'binding_id'])

    def test_changing_expected_binding_during_io_rejects_the_old_response(self):
        self.lua.globals()[b'expected_binding'] = self.binding
        send, _ = self.carrier(injected="expected_binding.vault_scope='other-vault'")
        self.assertEqual(self.attempt(send), (None, b'invalid_reading_wire'))

    def test_raw_carrier_rejects_oversize_and_empty_requests_before_network(self):
        send, calls = self.carrier()
        for body in (b'', b'x' * 1048577):
            self.assertEqual(send(body, self.token, b'good'), (None, b'invalid_diagnostic_request'))
        self.assertEqual(calls(), 0)

    def test_wire_binding_header_cannot_be_missing_ambiguous_or_injected(self):
        create = self.lua.eval('''function(config)
          return pcall(carrier.wire_transport, config, {}, {source={}})
        end''')
        for value in (b'', b'x' * 129, b'known\r\nInjected: value', b'other/path'):
            self.config[b'binding_id'] = value
            success, _ = create(self.config)
            self.assertFalse(success)


if __name__ == '__main__':
    unittest.main()

"""Actual Lua codec/shared carrier, injected SDK only; no device/approved user import proof."""
import copy
import hashlib
import pathlib
import unittest

import test_codec as reference
import test_pinned_transport as pinned

ROOT = pathlib.Path(__file__).resolve().parent


class PairedExchangeTest(unittest.TestCase):
    def setUp(self):
        self.pinned = pinned.PinnedTransportTest()
        self.pinned.setUp()
        self.harness = self.pinned.harness
        self.lua = self.harness.lua
        self.harness.reference.dependencies[b'object'] = self.lua.eval(
            "function(value) return setmetatable(value,{wire_kind='object'}) end")
        self.module = self.lua.execute((ROOT / 'paired_exchange.lua').read_text(encoding='utf-8'))
        self.document = dict(pairing_version=1, receiver_role='canonical_reading_activity_v1',
            endpoint='https://127.0.0.1:8443', certificate_pem='-----BEGIN CERTIFICATE-----\nsynthetic\n-----END CERTIFICATE-----\n',
            peer_certificate_sha256='1' * 64, binding=self.harness.reference.binding,
            token='t' * 43, not_before_utc='2026-10-17T12:00:00.000Z', expires_at_utc='2026-10-17T12:30:00.000Z')

    def open(self, document=None, approved=None, case='ok', digest=None, status=None, after_io=None):
        # Same injected native-SDK model as the existing pinned carrier tests;
        # the paired adapter itself constructs the real shared carrier.
        _, counts, http, https = self.pinned.make(case, digest)
        if status is not None or after_io is not None:
            self.lua.globals()[b'forced_http_status'] = status
            self.lua.globals()[b'after_io_now'] = after_io
            http[b'request'] = self.lua.eval('''function(original) return function(request)
                local first,code,headers=original(request)
                if after_io_now then now_utc=after_io_now end
                return first,forced_http_status or code,headers
            end end''')(http[b'request'])
        ltn12 = self.lua.eval('''{source={string=function(value)
            return function() local result=value;value=nil;return result end
        end}}''')
        runtime = self.lua.table_from({
            b'deps': self.harness.reference.dependencies, b'codec': self.harness.reference.codec,
            b'carrier': self.lua.globals()[b'carrier'], b'now': self.harness.now,
            b'https': https, b'http': http, b'ltn12': ltn12, b'ca_file': b'/fixture/ca.pem',
        })
        raw = reference.compact(self.document if document is None else document)
        # Test-only trusted local approval. A real importer must obtain this hash
        # independently from the issuer/human-approved out-of-band handoff.
        approved = approved if approved is not None else hashlib.sha256(raw).hexdigest().encode()
        handle = self.module[b'open'](raw, approved, runtime)
        return handle, counts, runtime

    def attempt(self, handle, request=None):
        return self.module[b'attempt'](handle, self.harness.sent if request is None else request)

    def acknowledged(self, handle, receipt, request=None):
        return self.module[b'acknowledged'](handle, receipt, self.harness.sent if request is None else request)

    def test_only_approved_bound_tls_response_exposes_exact_committed_event(self):
        handle, counts, _ = self.open()
        receipt, failure = self.attempt(handle)
        self.assertIsNone(failure)
        events = self.acknowledged(handle, receipt)
        self.assertEqual(len(events), 1)
        expected = reference.VECTOR['response']['results'][0]
        for key in ('index', 'line_digest', 'event_id', 'native_digest', 'canonical_commit'):
            value = expected[key].encode() if isinstance(expected[key], str) else expected[key]
            self.assertEqual(events[1][key.encode()], value)
        self.assertEqual(counts[b'sends'], 2)
        self.assertIsNone(receipt[b'accepted_events'])
        self.assertIsNone(receipt[b'canonical_ack'])
        events[1][b'event_id'] = b'forged'
        self.assertNotEqual(self.acknowledged(handle, receipt)[1][b'event_id'], b'forged')
        self.assertEqual(self.lua.eval('tostring')(handle), b'ReadingPairedExchange(redacted)')
        pure = self.harness.reference.response()
        self.assertFalse(pure[b'canonical_ack'])
        self.assertIsNone(pure[b'accepted_events'])

    def test_missing_or_changed_independent_approval_refuses_before_network(self):
        for approved in (b'', b'0'*64, b'x'*64, b'A'*64):
            result, counts, _ = self.open(approved=approved)
            self.assertEqual(result, (None, b'invalid_approved_reading_pairing'))
            self.assertEqual(counts[b'http'], 0)
            self.assertEqual(counts[b'sends'], 0)

    def test_approved_but_wrong_role_version_shape_or_expired_document_is_refused(self):
        changes = [('receiver_role', 'diagnostic'), ('pairing_version', 2),
                   ('extra', 'private'), ('token', 'PRIVATE\r\nX: bad'),
                   ('not_before_utc', '2026-10-17T12:00:02.000Z'),
                   ('expires_at_utc', '2026-10-17T12:31:00.000Z'),
                   ('expires_at_utc', '2026-10-17T12:00:01.000Z')]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                document = copy.deepcopy(self.document)
                document[key] = value
                result, counts, _ = self.open(document)
                self.assertEqual(result, (None, b'invalid_approved_reading_pairing'))
                self.assertEqual(counts[b'http'], 0)

    def test_wrong_pin_and_transport_shortcuts_cannot_manufacture_receipt(self):
        for case, digest, reason in [('ok', b'2'*64, b'reading_peer_pin_mismatch'),
                ('never_connect', None, b'reading_transport_failed'),
                ('early_send', None, b'reading_peer_unverified'),
                ('second_connection', None, b'reading_transport_failed'),
                ('certificate_error', None, b'reading_certificate_rejected'),
                ('timeout', None, b'reading_transport_failed')]:
            with self.subTest(case=case):
                handle, _, _ = self.open(case=case, digest=digest)
                result=self.attempt(handle)
                self.assertEqual(result, (None, reason))
                self.assertNotIn(b'PRIVATE',result[1])

    def test_claims_forged_session_receipt_and_retarget_cannot_grant_acknowledgement(self):
        handle, _, _ = self.open()
        receipt, _ = self.attempt(handle)
        self.assertEqual(self.acknowledged(self.lua.table(), receipt), (None, b'unverified_reading_receipt'))
        self.assertEqual(self.acknowledged(handle, self.lua.table()), (None, b'unverified_reading_receipt'))
        self.assertEqual(self.acknowledged(handle, self.harness.reference.response()), (None, b'unverified_reading_receipt'))
        self.assertEqual(self.acknowledged(handle, receipt, self.harness.sent+b' '), (None, b'unverified_reading_receipt'))
        second, _, _ = self.open()
        self.assertEqual(self.acknowledged(second, receipt), (None, b'unverified_reading_receipt'))
        receipt[b'accepted_events'] = self.lua.table()
        handle[b'binding_id'] = b'forged'
        self.assertEqual(len(self.acknowledged(handle, receipt)), 1)

    def test_http_auth_retry_and_redirect_never_create_receipt_or_hidden_retry(self):
        for status, reason in [(401, b'reading_http_unauthorized'), (429, b'reading_http_retryable'),
                               (503, b'reading_http_retryable'), (302, b'unverified_reading_receipt')]:
            handle, counts, _ = self.open(status=status)
            self.assertEqual(self.attempt(handle), (None, reason))
            self.assertEqual(counts[b'http'], 1)

    def test_expiry_after_actual_carrier_call_suppresses_even_matching_claims(self):
        handle, counts, _ = self.open(after_io=b'2026-10-17T12:30:00.000Z')
        self.assertEqual(self.attempt(handle), (None, b'unverified_reading_receipt'))
        self.assertEqual(counts[b'sends'], 2)

    def test_invalid_request_is_rejected_before_network_and_errors_are_redacted(self):
        handle, counts, runtime = self.open()
        for request in (b' '+self.harness.sent, b'PRIVATE_TOKEN_PRIVATE_PATH'):
            result = self.attempt(handle, request)
            self.assertEqual(result, (None, b'unverified_reading_receipt'))
            self.assertNotIn(b'PRIVATE', result[1])
        self.assertEqual(counts[b'http'], 0)

    def test_caller_runtime_mutation_cannot_retarget_pairing(self):
        handle, _, runtime = self.open()
        runtime[b'ca_file'] = b'/other/ca.pem'
        runtime[b'now'] = self.lua.eval('function() error("PRIVATE") end')
        receipt, _ = self.attempt(handle)
        self.assertEqual(len(self.acknowledged(handle, receipt)), 1)
        self.assertEqual(self.lua.globals()[b'tls_params'][b'cafile'], b'/fixture/ca.pem')

    def test_changed_response_nonce_scope_or_native_line_digest_is_never_acknowledged(self):
        for field in ('request_id', 'vault_scope', 'native_digest', 'line_digest'):
            changed = copy.deepcopy(reference.VECTOR['response'])
            if field in ('native_digest', 'line_digest'):
                changed['results'][0][field] = '0'*64
            else:
                changed[field] = 'other'
            self.lua.globals()[b'response_bytes'] = reference.compact(changed)
            handle, _, _ = self.open()
            self.assertEqual(self.attempt(handle), (None, b'unverified_reading_receipt'))

    def test_staged_and_retryable_claims_expose_no_acknowledged_event(self):
        for outcome in ('staged', 'retryable', 'review', 'conflict'):
            changed = copy.deepcopy(reference.VECTOR['response'])
            changed['results'][0]['outcome'] = outcome
            changed['results'][0]['canonical_commit'] = None
            self.lua.globals()[b'response_bytes'] = reference.compact(changed)
            handle, _, _ = self.open()
            receipt, failure = self.attempt(handle)
            self.assertIsNone(failure)
            self.assertEqual(len(self.acknowledged(handle, receipt)), 0)

    def test_expiry_backward_clock_and_close_invalidate_old_receipts(self):
        for invalidation in ('expiry', 'backward', 'close'):
            self.lua.globals()[b'now_utc'] = reference.NOW.encode()
            handle, _, _ = self.open()
            receipt, _ = self.attempt(handle)
            if invalidation == 'close':
                self.module[b'close'](handle)
            else:
                self.lua.globals()[b'now_utc'] = (b'2026-10-17T12:30:00.000Z' if invalidation == 'expiry'
                    else b'2026-10-17T12:00:00.000Z')
            self.assertEqual(self.acknowledged(handle, receipt), (None, b'unverified_reading_receipt'))
            self.lua.globals()[b'now_utc'] = reference.NOW.encode()
            self.assertEqual(self.acknowledged(handle, receipt), (None, b'unverified_reading_receipt'))


if __name__ == '__main__':
    unittest.main()

"""Actual LuaJIT codec/native providers; injected transport, never device proof."""
import copy
import hashlib
import json
import pathlib
import unittest

from lupa.luajit21 import LuaRuntime
from test_native_provider import provider_modules

ROOT = pathlib.Path(__file__).resolve().parent
FIXTURE_BYTES = (ROOT / 'sequence_fixture.json').read_bytes()
FIXTURE = json.loads(FIXTURE_BYTES)


class WireSequenceTest(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True, encoding=None)
        self.deps, self.json, _ = provider_modules(self.lua)
        self.codec_module = self.lua.execute((ROOT / 'codec.lua').read_bytes())
        self.codec = self.codec_module[b'new'](self.deps)
        self.exchange = self.lua.execute((ROOT / 'exchange.lua').read_bytes())
        self.client = self.lua.execute((ROOT.parent / 'transport_probe' / 'client.lua').read_bytes())
        self.sequence = self.lua.execute((ROOT / 'sequence.lua').read_bytes())
        self.fixture = self.deps[b'decode_json'](FIXTURE_BYTES)
        self.binding = self.fixture[b'binding']
        self.sent, self.pauses = [], []
        self.mutation = None
        self.token = b't' * 43
        self.authenticated = 0
        self.current_time = b'2026-10-20T10:01:00.000Z'
        wrap = self.lua.eval('function(fn) return function(...) return fn(...) end end')
        nonce = self.lua.eval("function() local n=0; return function() n=n+1; return 'qrtr_'..string.format('%032x',n) end end")()
        self.runtime = self.lua.table_from({
            b'transport': wrap(self.transport), b'token': self.token,
            b'now': wrap(lambda: self.current_time),
            b'window': self.lua.eval("function() return '2026-10-20T10:01:00.000Z','2026-10-20T10:02:00.000Z' end"),
            b'nonce': nonce, b'pause': wrap(self.pause),
            b'certificate_rejected': self.client[b'certificate_rejected'],
        })

    def pause(self, seconds):
        self.pauses.append(seconds)
        return True

    def transport(self, payload, token, trust):
        self.sent.append((payload, token, trust))
        if self.mutation == 'provider_error':
            raise RuntimeError('PRIVATE_TOKEN_PATH_REMOTE_EXCERPT')
        if trust == b'bad':
            errors = {'bad_ca_timeout': b'timeout', 'bad_ca_offline': b'connection refused',
                      'bad_ca_unclassified': b'tls_failed',
                      'bad_ca_certificate_file': b'error loading certificate file PRIVATE_SENTINEL',
                      'bad_ca_configuration': b'error loading CA file PRIVATE_SENTINEL'}
            return ((200, b'bad') if self.mutation == 'bad_ca_accepted'
                    else (None, errors.get(self.mutation, b'certificate verify failed')))
        if token != self.token:
            return (200, b'bad') if self.mutation == 'auth_accepted' else (401, b'auth_required')
        self.authenticated += 1
        if self.authenticated <= 2:
            status = 429 if self.authenticated == 1 else 503
            return (503 if self.mutation == 'wrong_retry_code' else status, b'retry')
        request = json.loads(payload)
        if self.mutation == 'expiry_after_io':
            self.current_time = b'2026-10-20T10:02:00.000Z'
        inspected = self.codec[b'inspect_request'](payload, self.binding, self.current_time)
        batch = next(batch for batch in FIXTURE['batches'] if batch['event_lines'] == request['event_lines'])
        results = []
        for index, outcome in enumerate(batch['expected_outcomes']):
            entry = inspected[b'entries'][index + 1]
            def public(key):
                value = entry[key.encode()]
                return value.decode() if isinstance(value, bytes) else None
            results.append(dict(index=index, line_digest=public('line_digest'),
                event_id=public('event_id'), native_digest=public('native_digest'), outcome=outcome,
                canonical_commit=batch['expected_revisions'][index]))
        response = {key: value for key, value in request.items()
                    if key not in ('event_lines', 'issued_at_utc', 'expires_at_utc')}
        response['results'] = results
        # The first successful response is deliberately discarded. Mutations
        # target every response so the next independently decoded one must fail.
        if self.mutation == 'wrong_nonce':
            response['request_id'] = 'qrtr_' + 'f' * 32
        if self.mutation == 'wrong_revision':
            response['results'][-1]['canonical_commit'] = 'qrc_' + '0' * 64
        if self.mutation == 'wrong_outcome':
            response['results'][-1]['outcome'] = 'retryable'
            response['results'][-1]['canonical_commit'] = None
        return 200, json.dumps(response, ensure_ascii=False, separators=(',', ':')).encode()

    def run_sequence(self):
        return self.sequence[b'run'](self.deps, self.codec_module, self.exchange, self.fixture, self.runtime)

    def test_actual_dart_fixture_provenance_and_native_hashes(self):
        provenance = json.loads((ROOT / 'sequence_fixture.provenance.json').read_bytes())
        self.assertEqual(hashlib.sha256(FIXTURE_BYTES).hexdigest(), provenance['fixtureSha256'])
        self.assertEqual(provenance['sourceCommit'], '93a0ddeeb25cc0e54cef4ca5bd3d0199706ba3a3')
        self.assertFalse(provenance['proof']['canonicalAck'])
        for shard in FIXTURE['expected_shards']:
            import base64
            data = base64.b64decode(shard['bytes_base64'], validate=True)
            self.assertEqual(hashlib.sha256(data).hexdigest(), shard['sha256'])
            self.assertTrue(shard['path'].endswith('/' + shard['sha256'] + '.jsonl'))

    def test_bounded_sequence_uses_fresh_nonces_and_identical_lines_without_ack(self):
        report = self.run_sequence()
        self.assertEqual(report[b'phase'], b'wire_claims_checked')
        self.assertEqual(report[b'attempts'], 10)
        self.assertEqual(report[b'checked_responses'], 5)
        self.assertEqual(report[b'deliberately_discarded_responses'], 1)
        self.assertEqual(self.pauses, [1])
        self.assertEqual(len(self.sent), 10)
        self.assertNotEqual(self.sent[0][1], self.token)
        requests = [json.loads(item[0]) for item in self.sent]
        self.assertEqual(len({item['request_id'] for item in requests}), 10)
        self.assertEqual(len({item['batch_id'] for item in requests}), 3)
        self.assertEqual(requests[4]['event_lines'], requests[5]['event_lines'])
        for key in (b'canonical_ack', b'canonical_persistence_proven', b'physical_execution_attested',
                    b'source_cursor_changed', b'statistics_accessed', b'wifi_changed'):
            self.assertFalse(report[key])
        self.assertIsNone(report[b'accepted_events'])
        encoded = self.json[b'encode'](report)
        self.assertLess(len(encoded), 8192)
        self.assertNotIn(self.token, encoded)
        self.assertNotIn(b'event_lines', encoded)

    def test_network_and_ca_configuration_failures_are_not_certificate_rejection(self):
        for mutation in ('bad_ca_timeout', 'bad_ca_offline', 'bad_ca_unclassified',
                         'bad_ca_configuration', 'bad_ca_certificate_file'):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.mutation = mutation
                report = self.run_sequence()
                self.assertEqual(report[b'phase'], b'failed')
                self.assertEqual(len(self.sent), 1)
                self.assertNotIn(b'PRIVATE_', self.json[b'encode'](report))

    def test_changed_trust_auth_http_and_bound_response_fail_closed(self):
        for mutation in ('bad_ca_accepted', 'auth_accepted', 'wrong_retry_code', 'wrong_nonce',
                         'wrong_revision', 'wrong_outcome', 'expiry_after_io', 'provider_error'):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.mutation = mutation
                report = self.run_sequence()
                self.assertEqual(report[b'phase'], b'failed')
                self.assertEqual(report[b'error_code'], b'wire_sequence_failed')
                self.assertNotIn(b'PRIVATE_', self.json[b'encode'](report))
                self.assertLessEqual(len(self.sent), 6)

    def test_reused_nonce_and_failed_backoff_stop_before_next_network_attempt(self):
        self.runtime[b'nonce'] = self.lua.eval("function() return 'qrtr_'..string.rep('0',32) end")
        self.assertEqual(self.run_sequence()[b'phase'], b'failed')
        self.assertEqual(len(self.sent), 1)
        self.setUp()
        self.runtime[b'pause'] = self.lua.eval('function() return false end')
        self.assertEqual(self.run_sequence()[b'phase'], b'failed')
        self.assertEqual(len(self.sent), 3)

    def test_changed_fixture_cannot_redefine_success_or_select_another_scope(self):
        for mutate in (
            lambda f: f['binding'].__setitem__('vault_scope', 'production'),
            lambda f: f['batches'][1]['expected_outcomes'].__setitem__(3, 'committed'),
            lambda f: f.__setitem__('canonical_ack', True),
            lambda f: f['batches'][0]['expected_revisions'].__setitem__(0, 'qrc_' + '0' * 64),
        ):
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(FIXTURE)
                mutate(changed)
                self.fixture = self.deps[b'decode_json'](json.dumps(changed, separators=(',', ':')).encode())
                self.assertEqual(self.run_sequence()[b'phase'], b'failed')
                self.assertEqual(self.sent, [])

    def test_fixture_mutation_during_io_does_not_change_captured_lines_or_expectations(self):
        wrap = self.lua.eval('function(send,fixture) return function(...) '
            "fixture.batches[2].event_lines[5]='private changed line'; "
            "fixture.batches[2].expected_outcomes[5]='retryable'; return send(...) end end")
        self.runtime[b'transport'] = wrap(self.runtime[b'transport'], self.fixture)
        self.assertEqual(self.run_sequence()[b'phase'], b'wire_claims_checked')

    def test_ack_claim_cannot_be_added_by_exchange(self):
        self.lua.eval('function(module) local original=module.attempt; module.attempt=function(...) '
            'local value,failure=original(...); if value then value.canonical_ack=true end; '
            'return value,failure end end')(self.exchange)
        self.assertEqual(self.run_sequence()[b'phase'], b'failed')

"""Actual Lua 5.1 logic; injected JSON/SHA providers, no native Kindle/ACK proof."""
import copy
import calendar
import datetime
import hashlib
import json
import pathlib
import unittest

from lupa.lua51 import LuaRuntime
from verify_upstream import verify

ROOT = pathlib.Path(__file__).resolve().parent
VECTOR = json.loads((ROOT / "upstream/transport_vectors.json").read_text(encoding="utf-8"))
NOW = "2026-10-17T12:00:01.000Z"


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class WireCodecTest(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True, encoding=None)
        self.assertEqual(self.lua.eval("_VERSION"), b"Lua 5.1")
        self.null = self.lua.table()
        self.mark = self.lua.eval("function(value, kind) return setmetatable(value, {wire_kind=kind}) end")
        self.lua.globals()[b"wire_null"] = self.null
        kind = self.lua.eval("function(value) if value==wire_null then return 'null' end; "
                             "if type(value)=='table' then local mt=getmetatable(value); return mt and mt.wire_kind end; return type(value) end")
        wrap = self.lua.eval("function(fn) return function(...) return fn(...) end end")
        dependencies = self.lua.table_from({b"sha256": wrap(lambda data: hashlib.sha256(data).hexdigest().encode("ascii")),
            b"decode_json": wrap(lambda data: self.to_lua(json.loads(data))), b"kind": kind, b"null": self.null})
        self.module = self.lua.execute((ROOT / "codec.lua").read_text(encoding="utf-8"))
        self.dependencies = dependencies
        self.codec = self.module[b"new"](dependencies)
        self.binding = {key: VECTOR["request"][key] for key in ("binding_id", "vault_scope", "device_id", "source_epoch")}

    def to_lua(self, value):
        if value is None:
            return self.null
        if isinstance(value, dict):
            return self.mark(self.lua.table_from({key.encode("utf-8"): self.to_lua(item) for key, item in value.items()}), b"object")
        if isinstance(value, list):
            return self.mark(self.lua.table_from([self.to_lua(item) for item in value]), b"array")
        return value.encode("utf-8") if isinstance(value, str) else value

    def rejected(self, result):
        self.assertEqual(result, (None, b"invalid_reading_wire"))

    def encode(self, request, now=NOW, binding=None):
        fields = copy.deepcopy(request)
        fields.pop("batch_id", None)
        return self.codec[b"encode_request"](self.to_lua(fields), self.to_lua(binding or self.binding), now.encode())

    def inspect(self, request, now=NOW, binding=None):
        data = request if isinstance(request, bytes) else compact(request)
        return self.codec[b"inspect_request"](data, self.to_lua(binding or self.binding), now.encode())

    def response(self, response=None, request=None, now=NOW, binding=None):
        data = VECTOR["response_json"].encode() if response is None else response if isinstance(response, bytes) else compact(response)
        request_bytes = VECTOR["request_json"].encode() if request is None else request if isinstance(request, bytes) else compact(request)
        return self.codec[b"decode_response"](data, request_bytes, self.to_lua(binding or self.binding), now.encode())

    def test_exact_upstream_pin(self):
        self.assertEqual(verify(), 6)

    def test_request_and_response_match_exact_canonical_vectors(self):
        self.assertEqual(self.encode(VECTOR["request"]), VECTOR["request_json"].encode())
        value = self.inspect(VECTOR["request"])
        self.assertEqual(value[b"batch_id"], VECTOR["batch_id"].encode())
        entry = value[b"entries"][1]
        self.assertEqual(entry[b"event_id"], VECTOR["response"]["results"][0]["event_id"].encode())
        self.assertEqual(entry[b"native_digest"], VECTOR["response"]["results"][0]["native_digest"].encode())
        claims = self.response()
        self.assertFalse(claims[b"canonical_ack"])
        self.assertEqual(claims[b"untrusted_claims"][1][b"outcome"], b"committed")
        self.assertIsNone(claims[b"accepted_events"])

    def test_all_upstream_negative_cases(self):
        for case in VECTOR["negative_cases"]:
            with self.subTest(case=case["id"]):
                target = copy.deepcopy(VECTOR[case["side"]])
                node = target
                for key in case["path"][:-1]:
                    node = node[key]
                node[case["path"][-1]] = case["value"]
                self.rejected(self.inspect(target) if case["side"] == "request" else self.response(target))

    def test_canonical_encoding_rejects_duplicate_keys_bom_whitespace_and_alternate_numbers(self):
        for side in ("request", "response"):
            canonical = VECTOR[side + "_json"].encode()
            for raw in (b" " + canonical, canonical + b"\n", b"\xef\xbb\xbf" + canonical,
                        canonical.replace(b'"protocol_version":1', b'"protocol_version":1,"protocol_version":1'),
                        canonical.replace(b'"protocol_version":1', b'"protocol_version":1.0'),
                        canonical.replace(b'"protocol_version":1', b'"protocol_version":1e0')):
                with self.subTest(side=side, sample=raw[:30]):
                    self.rejected(self.inspect(raw) if side == "request" else self.response(raw))

    def test_binding_and_live_request_window_are_explicit(self):
        for now in ("2026-10-17T11:59:59.999Z", "2026-10-17T12:05:00.000Z", "2026-02-30T12:00:01.000Z",
                    "2026-10-17T12:00:01Z", "2026-10-17T12:00:01.000000Z", "2026-10-17T12:00:01.000Z\n"):
            self.rejected(self.inspect(VECTOR["request"], now=now))
            self.rejected(self.response(now=now))
        for key in self.binding:
            changed = {**self.binding, key: "other"}
            self.rejected(self.inspect(VECTOR["request"], binding=changed))
            self.rejected(self.response(binding=changed))

    def test_every_success_outcome_remains_an_untrusted_claim(self):
        for outcome in ("committed", "duplicate", "staged", "retryable", "auth_required", "unsupported_version", "conflict", "review", "fatal_corruption"):
            changed = copy.deepcopy(VECTOR["response"])
            changed["results"][0]["outcome"] = outcome
            if outcome not in ("committed", "duplicate"):
                changed["results"][0]["canonical_commit"] = None
            claims = self.response(changed)
            self.assertFalse(claims[b"canonical_ack"])
            self.assertEqual(claims[b"untrusted_claims"][1][b"outcome"], outcome.encode())

    def test_response_cannot_claim_commit_for_an_ineligible_line(self):
        request = copy.deepcopy(VECTOR["request"])
        request["event_lines"] = ["not JSON"]
        encoded = self.encode(request)
        parsed = self.inspect(encoded)
        entry = parsed[b"entries"][1]
        self.assertEqual(entry[b"rejection"], b"fatal_corruption")
        response = copy.deepcopy(VECTOR["response"])
        response["batch_id"] = parsed[b"batch_id"].decode()
        claim = response["results"][0]
        claim.update(line_digest=hashlib.sha256(b"not JSON").hexdigest(), event_id=None, native_digest=None)
        self.rejected(self.response(response, encoded))
        claim.update(outcome="fatal_corruption", canonical_commit=None)
        self.assertFalse(self.response(response, encoded)[b"canonical_ack"])

    def test_bounds_reject_before_unbounded_input_is_serialized(self):
        for lines in ([], ["x"] * 1001, ["x" * 8193], ["x" * 8192] * 64, ["x\ny"], ["x\ry"], ["é" * 4097]):
            request = copy.deepcopy(VECTOR["request"])
            request["event_lines"] = lines
            self.rejected(self.encode(request))
        request = copy.deepcopy(VECTOR["request"])
        request["event_lines"] = ["x" * 8192]
        self.assertIsInstance(self.encode(request), bytes)
        self.rejected(self.inspect(b"x" * (1048576 + 1)))
        self.rejected(self.response(b"x" * (524288 + 1)))

    def test_exact_payload_event_and_escaped_wire_limits(self):
        request = copy.deepcopy(VECTOR["request"])
        request["event_lines"] = ["x" * 8192] * 63 + ["x" * 8128]
        self.assertEqual(sum(len(line.encode()) + 1 for line in request["event_lines"]), 524288)
        self.assertIsInstance(self.encode(request), bytes)
        request["event_lines"][-1] += "x"
        self.rejected(self.encode(request))
        request["event_lines"] = ["x"] * 1000
        self.assertIsInstance(self.encode(request), bytes)
        request["event_lines"] = ["\x00" * 8192] * 63
        self.rejected(self.encode(request))

    def test_exact_unicode_and_json_escaping_roundtrip(self):
        request = copy.deepcopy(VECTOR["request"])
        request["event_lines"] = ['{"text":"á水😀\\n\\t\\u0001"}']
        encoded = self.encode(request)
        self.assertIsInstance(encoded, bytes)
        parsed = self.inspect(encoded)
        self.assertFalse(parsed[b"canonical_ack"])
        self.assertEqual(parsed[b"entries"][1][b"rejection"], b"unsupported_version")

    def test_decoder_failures_do_not_expose_input_or_provider_exception(self):
        for raw in (b"secret-sentinel-invalid-json", b"\xff", b"\xed\xa0\x80", b"\xf4\x90\x80\x80"):
            self.rejected(self.inspect(raw))
            self.rejected(self.response(raw))

    def test_dependency_initialization_failure_is_sanitized_and_hash_is_checked(self):
        self.dependencies[b"sha256"] = self.lua.eval("function() error('private-provider-sentinel') end")
        self.rejected(self.module[b"new"](self.dependencies))
        self.dependencies[b"sha256"] = self.lua.eval("function() return string.rep('0',64) end")
        self.rejected(self.module[b"new"](self.dependencies))
        self.rejected(self.module[b"new"](self.lua.table()))

    def native_line(self, **changes):
        raw = json.loads(VECTOR["request"]["event_lines"][0])
        raw.update(changes)
        started = datetime.datetime.fromisoformat(raw["started_at_utc"].replace("Z", "+00:00"))
        preimage = ["quartzo-reading-event-v1", raw["device_id"], raw["source_epoch"], raw["book_row_id"], raw["page"], calendar.timegm(started.utctimetuple())]
        raw["event_id"] = "qre_" + hashlib.sha256(compact(preimage)).hexdigest()
        return compact(raw).decode()

    def inspect_lines(self, lines):
        request = copy.deepcopy(VECTOR["request"])
        request["event_lines"] = lines
        encoded = self.encode(request)
        self.assertIsInstance(encoded, bytes)
        return self.inspect(encoded)

    def test_native_same_id_payload_conflicts_quarantine_every_matching_position(self):
        original = VECTOR["request"]["event_lines"][0]
        observed_retry = self.native_line(observed_at_utc="2026-10-17T12:00:00.123456Z")
        duration_change = self.native_line(duration_seconds=31)
        inspected = self.inspect_lines([original, observed_retry, duration_change, "not JSON"])
        for index in range(1, 4):
            entry = inspected[b"entries"][index]
            self.assertEqual(entry[b"rejection"], b"conflict")
            self.assertTrue(self.lua.eval("function(value) return value==wire_null end")(entry[b"event_id"]))
        self.assertEqual(inspected[b"entries"][4][b"rejection"], b"fatal_corruption")
        repeated = self.inspect_lines([original, observed_retry])
        self.assertIsNone(repeated[b"entries"][1][b"rejection"])
        self.assertEqual(repeated[b"entries"][1][b"native_digest"], repeated[b"entries"][2][b"native_digest"])

    def test_malformed_future_and_foreign_entries_do_not_hide_valid_neighbors(self):
        original = VECTOR["request"]["event_lines"][0]
        result = self.inspect_lines(["not JSON", '{"schema_version":999}', self.native_line(device_id="other-device"), "[]", "{}", original])
        for index, reason in enumerate((b"fatal_corruption", b"unsupported_version", b"review", b"fatal_corruption", b"unsupported_version"), 1):
            self.assertEqual(result[b"entries"][index][b"rejection"], reason)
        self.assertIsNone(result[b"entries"][6][b"rejection"])
        self.assertFalse(result[b"canonical_ack"])

    def test_native_identity_handles_calendar_extremes_and_safe_integer_limit(self):
        for started in ("0001-01-01T00:00:00.000Z", "1969-12-31T23:59:59.000Z", "2000-02-29T12:00:00.000Z", "2100-02-28T12:00:00.000Z", "9999-12-31T23:59:59.000Z"):
            line = self.native_line(started_at_utc=started, book_row_id=9007199254740991, page=9007199254740991,
                                    total_pages=9007199254740991, source_schema_version="fixture-水😀", observed_at_utc="9999-12-31T23:59:59.123456Z")
            entry = self.inspect_lines([line])[b"entries"][1]
            self.assertIsNone(entry[b"rejection"], started)
            native = json.loads(line)
            native.pop("observed_at_utc")
            self.assertEqual(entry[b"native_digest"], hashlib.sha256(compact(native)).hexdigest().encode())

    def test_invalid_native_ranges_calendar_or_blank_schema_are_isolated(self):
        original = json.loads(VECTOR["request"]["event_lines"][0])
        for changes in ({"duration_seconds": 0}, {"duration_seconds": 86401}, {"book_row_id": 9007199254740992},
                        {"page": 0}, {"total_pages": 1.5}, {"started_at_utc": "2026-02-29T12:00:00.000Z"},
                        {"observed_at_utc": "2026-02-30T12:00:00.000Z"}, {"source_schema_version": "\u00a0\u2007\ufeff"}):
            with self.subTest(changes=changes):
                entry = self.inspect_lines([compact({**original, **changes}).decode()])[b"entries"][1]
                self.assertEqual(entry[b"rejection"], b"fatal_corruption")

    def test_microsecond_request_window_boundary_does_not_lose_precision(self):
        request = copy.deepcopy(VECTOR["request"])
        request.update(issued_at_utc="9999-12-31T23:59:59.123456Z", expires_at_utc="9999-12-31T23:59:59.123458Z")
        self.assertIsInstance(self.encode(request, now="9999-12-31T23:59:59.123457Z"), bytes)
        self.rejected(self.encode(request, now="9999-12-31T23:59:59.123458Z"))

    def test_actual_dart_native_reference_bytes_and_digests(self):
        provenance = json.loads((ROOT / "dart_reference.provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["sourceCommit"], "e7a661d4ed6d572cdbf722f4e697fea461005b69")
        self.assertEqual(hashlib.sha256((ROOT / "dart_reference.dart").read_bytes()).hexdigest(), provenance["generatorSha256"])
        fixture = (ROOT / "dart_reference.json").read_bytes()
        self.assertEqual(hashlib.sha256(fixture).hexdigest(), provenance["fixtureSha256"])
        reference = json.loads(fixture)
        self.assertTrue(reference["unicode_blank_rejected"])
        for case in reference["cases"]:
            entry = self.inspect_lines([case["line"]])[b"entries"][1]
            self.assertIsNone(entry[b"rejection"])
            self.assertEqual(entry[b"native_digest"], hashlib.sha256(case["native_payload"].encode()).hexdigest().encode())


if __name__ == "__main__":
    unittest.main()

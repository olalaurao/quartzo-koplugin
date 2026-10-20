# Pinned Reading wire consumer — Gate 0C

`codec.lua` is a pure Lua 5.1 consumer of the ratified upstream Reading transport
contract. It is outside the production plugin and the deployed TLS diagnostic.
It performs no network/filesystem I/O, credential lookup, Statistics/sidecar
access, queue write, Wi-Fi change, receipt issuance or source-cursor update.

The six files in `upstream/` were imported byte-for-byte from Quartzo
`e7a661d4ed6d572cdbf722f4e697fea461005b69`, after PR65 merged. The lock records
repository, exact revision, source paths, SHA-256 and Git blob hashes. They are
test inputs and remain upstream-owned. Never edit these copies independently or
substitute a proposed local schema. `.gitattributes` keeps their bytes stable.

```sh
python tools/reading_wire/verify_upstream.py
python tools/reading_wire/verify_upstream.py --remote
python -m unittest discover -s tools/reading_wire -p 'test_codec.py' -v
```

The remote check uses the existing `gh` login against the exact revision; it
neither reads/prints a token nor changes an account. CI performs the offline
hash check and tests with the same pinned Lupa 2.8 dependency as the existing
transport diagnostic suite.

## API and dependency boundary

`codec.new(deps)` requires trusted, explicit functions `sha256(bytes)`,
`decode_json(bytes)`, `kind(value)` and a stable `null` sentinel. JSON decoding
must preserve objects versus arrays (including empty containers), null and
string/number types. `kind` returns `object` or `array` for those tables.
SHA-256 returns lowercase hex and passes a known-answer check at construction.
The base host tests inject Python JSON and SHA providers while executing the
codec itself in real Lua 5.1. That base suite is not native-library proof.

`koreader_deps.load(require_module)` is the explicit dependency adapter. It loads
the existing `dkjson` and `ffi/sha2` APIs, supplies separate object/array metadata
and a stable null sentinel, and probes empty containers, null, safe integers and
SHA-256 before returning dependencies. Missing/incompatible modules fail with
`nil, "unsupported_reading_wire_dependencies"`; no simple-JSON or alternate-hash
fallback is used. `deps.object(table)` and `deps.array(table)` mark trusted
constructor input shapes. No runtime module is loaded until the caller invokes
this adapter explicitly. It is not wired to a production plugin or transport.

The complete suite also executes the same codec cases in host LuaJIT 2.1 using
actual pinned dkjson 2.10 and KOReader SHA source, rather than Python providers.
The dependency recipe/blob identities, SHA-256 and license are recorded in
`REFERENCE_RUNTIME.lock.json`. The reference preparer downloads only those exact
public sources to a fresh explicit directory, reads the one approved archive
member without extracting paths, verifies hashes before execution and never
overwrites/deletes an existing directory. Third-party sources are test-only
downloads, not vendored plugin files. The JSON API is probed rather than inferred
from a version string. Published reference APIs do not prove the installed PW3
library identity, ARM branch or actual KOReader lifecycle.

Prepare references, set `READING_WIRE_REFERENCE_DIR` to that directory's absolute
path, then run the complete suite:

```sh
python tools/reading_wire/prepare_reference_runtime.py <fresh-directory>
python -m unittest discover -s tools/reading_wire -p 'test_*.py' -v
```

Missing reference setup is an error, not a silent native-provider skip. CI
prepares the exact dependencies and sets the variable before executing all cases.

- `encode_request(fields, expected_binding, now_utc)` returns canonical UTF-8
  request bytes. Fields are the contracted request except `batch_id`, which is
  derived from captured scopes and exact lines. No nonce, clock, binding or
  credential is inferred. The caller supplies a fresh nonce; production replay
  prevention and authentication remain separate obligations.
- `inspect_request(bytes, expected_binding, now_utc)` checks exact encoding,
  scopes, UTC window, counts/byte bounds and batch identity, then independently
  classifies each line. Valid native events recompute their IDs/native digests;
  all positions for a same-ID/different-native-payload conflict are quarantined.
  Malformed, future-version and foreign-scope entries do not hide valid neighbors.
- `decode_response(bytes, request_bytes, expected_binding, now_utc)` revalidates
  the original request and binds every ordered claim to its scope/nonce/batch,
  position, exact line digest and eligible native ID/digest. Canonical revisions
  are syntactically permitted only for eligible committed/duplicate claims.

Inspect/decode projections explicitly contain `canonical_ack=false`; response
results are named `untrusted_claims`. There is no accepted-event projection or
cursor operation. A matching committed/duplicate string is not evidence that
the authenticated canonical owner durably saved anything. Failures return only
`nil, "invalid_reading_wire"`; external decoder/provider errors and input excerpts
are never forwarded or logged.

Strict canonical re-encoding rejects duplicate keys, unknown fields, BOM,
whitespace, alternate numeric/time encodings, invalid UTF-8 and lone surrogates.
UTC calendar arithmetic is independent of the host timezone and retains separate
seconds/microseconds through year 9999. Raw native start remains whole seconds.
The upstream 1000-event, 8192-byte line, 524288-byte payload/response,
1048576-byte request and 300-second lifetime caps are enforced. These are safety
bounds, not measured PW3 performance budgets.

## Cross-language reference

The upstream request/response golden bytes and all 12 negative mutations execute
in the Lua suite. `dart_reference.json` adds five synthetic cases generated by
the actual upstream `ReadingActivityEvent`, including pre-epoch/year 1/year 9999,
leap-calendar, maximum interoperable integers, microseconds and Unicode/control
escaping. Its provenance binds the upstream model blob, generator and output.

With the sibling Quartzo checkout at the recorded model source, regenerate using
that checkout's package configuration (run from `quartzo/`):

```sh
dart --packages=.dart_tool/package_config.json ../koreader/tools/reading_wire/dart_reference.dart
```

The generator does not write files. Normalize only the generated output's line
ending to LF before intentionally updating the consumer reference and its hashes.
Do not alter upstream copies to make a consumer test pass.

Actual PW3 provider/lifecycle acceptance, authenticated network binding, durable
receipt verification, persistent replay/outbox acknowledgements and PW3
offline/reboot/cancellation/lost-response tests remain required. This pure
consumer unlocks none of those gates by itself.

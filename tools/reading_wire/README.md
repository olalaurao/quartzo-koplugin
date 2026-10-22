# Pinned Reading wire consumer — Gate 0C

## Finite approved-pairing composition (G04, unregistered)

`paired_exchange.lua` reuses the existing codec and shared pinned carrier. It
accepts the exact private document issued by Quartzo's normal current-target
`ReadingTransportPairingSession`, plus its independently approved SHA256 from
an explicit trusted out-of-band handoff. Never compute approval from an
untrusted network document or trust a peer's role/hash advertisement. The
production delivery/import owner is still gated; this module performs no file
I/O or automatic pairing. The explicit synthetic KUAL driver now loads it only
from the identity-checked USB bundle. Its nine-field pairing_version1 document is a finite spike's private
handoff, not a replacement for the pinned event/wire contract.

The trusted local composition root provides the existing native SDK/provider
modules, clock and installed public CA path. Opening snapshots endpoint, pin,
token, binding and clock callback; the document must claim the exact canonical
receiver role, valid scope and at most thirty-minute UTC window. The codec's
existing canonical UTC parser also checks pairing validity and backward time;
it remains pure and grants no peer/ACK authority. Invalidity latches.

`open` returns an opaque process-local handle. `attempt(handle, requestBytes)`
checks the existing request codec, requires the carrier's exact opaque pinned
delivery, then fully decodes the bound response before constructing an opaque
session/request-bound receipt. Only `acknowledged(handle, receipt, requestBytes)`
can expose copies of its committed/duplicate event ID, position, line/native
digest and canonical revision. Staged/errors expose no acknowledged event;
forged tables, raw decoded claims, another session/request, expiry/backward time
and close cannot grant acceptance. No extra signature/HMAC protocol, retry,
outbox/cursor store or persisted receipt ledger is introduced. Existing pure
codec/exchange behavior and old diagnostic false-ACK reports remain unchanged.

Failed attempts preserve only an explicit allowlist of the pinned carrier's
fixed connection/certificate/pin categories. The synthetic sequence may copy
that category to its failure report; arbitrary SDK errors remain redacted.
No category is a receipt or permission to retry/advance a source cursor.

Twelve focused actual-Lua tests use an explicitly injected SDK model and a
synthetic locally approved document. They do not prove actual user-approved
import, canonical issuer interoperability, native TLS for this combined path or
new PW3 execution. Those proofs, real transport failure/retry/lifecycle and
source outbox persistence remain required before production ingestion. Merely
hashing a fixture inside a test does not establish out-of-band trust in use.

The separate actual normal-app/native LuaJIT/LuaSec join subsequently passed at
Quartzo bad10518 and consumer6cfdba8; the
[source-bound host report](../../docs/evidence/wire-paired-canonical-host-2026-10-20.json)
records actual receipt/publication/replay checks. It models a trusted host
handoff and does not certify this later KUAL/probe change or new device execution.

## Opt-in exact leaf pin preparation (2026-10-20)

`client.pinned_wire_transport(config, https, ltn12, http)` reuses the existing
shared carrier with mandatory explicit CA trust and a lowercase 64-hex
`peer_certificate_sha256`: SHA-256 of the leaf X509 DER, not of its PEM file.
It requires the target LuaSec1.3.2 native `https.tcp` factory and LuaSocket
`http.request`; `https.request` rejects caller create hooks. The connection
checks its actual certificate after handshake and before any HTTP send or
receive, permits one exact private endpoint, and closes failed connections.
Proxies and redirects cannot establish a delivery. This remains opt-in isolated
tooling, not a production plugin registration or session/credential owner.

Only verified HTTP200 can return an opaque delivery identity. The private weak
map reader requires the exact request/token/endpoint/binding/pin. Neither JSON
claims nor a cloned table can establish that identity. This authenticates
transport bytes only: canonical receiver authorization, durable per-event
receipt, revocation/cancel lifecycle and source cursor authority remain absent.
The codec/exchange still treats response claims as untrusted, with ACK false.
The existing five-second diagnostic timeout policy remains shared-process
tooling and needs production lifecycle composition before plugin use.

`test_pinned_transport.py` runs actual Lua with an injected SDK model; it is
not native TLS proof. `test_pinned_tls_native.py` additionally uses real native
Lua5.1/LuaSec1.3.2/LuaSocket and an ephemeral TLS1.2 loopback listener. Set
`READING_NATIVE_LUA51=/usr/bin/lua5.1` to require it; an absent setting explicitly
skips, while a configured missing/wrong runtime fails. CI installs those
test-only dependencies and requires exact version checks. Rejected CA and a
trusted-CA/wrong-leaf test must observe zero application bytes, including
incomplete HTTP. This host test never substitutes new-source physical PW3
acceptance or a canonical receiver/storage test.
The receive-timeout case uses the same authenticated native path with a finite
delayed synthetic response: credentials may reach the trusted peer, but timeout
must return no delivery. Its clock bound checks this fixture only, not total
production lifecycle or PW3 latency/performance budgets.

All four actual native cases passed at ac1ebd2 in Linux CI39525626234, with
93 wire and34 transport tests and no skips. Exact source fingerprints, CI-log
digest and explicit proof limits are recorded in
[`wire-leaf-pin-host-2026-10-20.json`](../../docs/evidence/wire-leaf-pin-host-2026-10-20.json).

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

## Explicit diagnostic wire exchange preparation

`exchange.attempt(codec, binding, now, request_bytes, transport, token)` composes
the actual pinned codec with one explicit HTTP attempt. It checks canonical
request/binding/time before network, then independently rechecks the complete
response against that exact request and a fresh UTC clock after network. It
returns the codec's `untrusted_claims` with `canonical_ack=false`, never an
accepted-event/cursor grant. Provider failures produce fixed errors without
tokens, paths or response excerpts. 401 and retryable HTTP statuses are distinct;
there is no hidden retry, nonce generation, credential lookup or queue mutation.
A later diagnostic runner must own its explicit bounded sequence and fresh
request nonce for each retry; production outbox remains gated.

`tools/transport_probe/client.lua.wire_transport(config, https, ltn12)` reuses
that diagnostic's one shared LuaSec carrier. It targets only the fixed
`/reading/activity/v1` path on an explicit private IPv4 HTTPS endpoint, supplies
the current 43-character bearer and captured binding in headers, and retains
explicit peer trust, TLS1.2, disabled redirects and timeout. Endpoint/trust/binding
are captured before I/O; request/response caps are the pinned 1MiB/512KiB bounds.
Distinct good/bad dedicated test CA files remain required. This is the existing
narrow dedicated-certificate diagnostic trust model, not production public-CA
hostname verification or a new network/receipt owner.

Real Lua5.1 tests compose the actual codec and carrier with injected HTTPS and
cover expiry/scope changes during I/O, per-position binding, redirects, 401/429/
5xx, header injection, bounds and error redaction. They are not native TLS,
physical Kindle-to-receiver delivery or canonical persistence proof. No combined
physical launcher/listener is installed. The earlier actual PW3 TLS report stays
bound to its old exact source; shared-carrier refactoring does not extend that
evidence. The independent offline codec report remains bound to its unchanged
codec/native sources.

## Finite native canonical-wire diagnostic (not production)

`sequence.lua` captures the three actual-Dart batches before network callbacks.
The earlier ten-attempt untrusted-claim sequence remains a host reference. The
current bundle's `sequence.lua` comes from `paired_sequence.lua`, and its
`exchange.lua` comes from the existing approved `paired_exchange.lua`; this is
one shared transport/launcher, not another network implementation. It performs
six fresh-nonce attempts over three batches, deliberately discards the first
receipt and requires five correctly bound per-event receipt lookups. Invalid
neighbors cannot be acknowledged, and each retry retains exact native lines.
Discarding a receipt is explicit application-level loss, not random connection
failure or persisted outbox recovery. Reports say `paired_receipts_checked`;
the report itself is no ACK/hardware/persistence/cursor grant. No production
extractor, outbox, credential owner or retry scheduler is installed.

`sequence_fixture.json` was generated by the actual upstream Dart event/shard
models at `93a0ddeeb25cc0e54cef4ca5bd3d0199706ba3a3`; its separate provenance
records exact model/generator blobs and fixture hash. It covers malformed,
unsupported, foreign-scope, existing-native conflict and within-request conflict
neighbors. Expected final storage is three exact shards, three unique events
and 120 native seconds. These diagnostic inputs do not change the ratified
six-file e7a661d4 contract pin. Regenerate from Quartzo with the exact recorded
arguments and package configuration; never maintain a Python event serializer.

The sibling Quartzo `tool/prepare_reading_wire_session.py` prepares fresh
short-lived network/window input in OS temporary storage with exact-source Dart
generation. Input version2 contains no token/key/certificate, and host OpenSSL
provisioning is removed. The isolated app generates its own actual normal
pairing; the checked APK/source/UID channel collects it and changes only fixture
transport binding, preserving all native lines/IDs/shard bytes. Only that exact
private pairing, its public leaf certificate and the synthetic fixture leave
the private phone session for the explicit USB bundle. No private key is exported.
Neither secrets nor private endpoints belong in public reports or command text.

`sequence_kindle.lua` composes installed KOReader native dependencies and the
existing verified TLS carrier under the existing single-use/watchdog launcher.
It requires the current v2026.07.1 baseline and an already-enabled network; it
does not change Wi-Fi. The only owned extension is `quartzo-wire-tls-probe`.
After exact-source host CI and phone readiness are verified:

```sh
python tools/reading_wire/sequence_bundle.py prepare --session <private-session-directory> --source-commit <full-commit> --output <fresh-private-temporary-bundle>
python tools/reading_wire/sequence_bundle.py install --bundle <private-bundle> --kindle-root <mounted-root> --observation <fresh-installation-observation.json>
```

Preparation copies only nine exact Git source blobs and three bounded runtime
inputs. It refuses a private-key certificate, changed source, linked/existing
outputs and unknown entries. Installation verifies the actual baseline/native
sources before and after and never overwrites a diagnostic or production file.
Runtime files and incomplete reports are preserved for investigation.

The collector requires the original bundle/install observation, completed PW3
sequence, and an independently collected isolated Android fixture after its
listener stops. It verifies fresh nonces, unchanged batches, actual owner
revocation and exact exported canonical bytes/inventory. It independently
recomputes request SHA/batch/nonce/window and acknowledged native/line/revision
bindings, then verifies native-ID/time counts from the three exact shards:

```sh
python tools/reading_wire/sequence_bundle.py collect --bundle <private-bundle> --kindle-root <mounted-root> --observation <installation-observation.json> --android-export <private-phone-fixture-export> --output <fresh-correlated-observation.json>
```

The result is deliberately `correlated_paired_receipts_and_owner_observations` with false
physical attestation/ACK/cloud-delivery fields. Even forged ARM-looking host
reports cannot make this tool attest hardware. Actual source-bound APK/UID,
phone execution/export, mounted target and KUAL execution observations remain
separate required evidence. No actual combined launcher/listener is installed
by development or tests. The old physical reports keep their original scope.

The earlier TLS/error diagnostic and source-specific physical evidence remain
historical proof for their exact sources. Current native carrier/pairing tests
still reject changed CA/pin, malformed bound replies, HTTP failures and timeouts;
no earlier PW3 proof is silently inherited by this new paired sequence.

## Single-use offline PW3 compatibility probe

`probe.lua` executes the three golden checks, all 12 negative wire mutations,
five actual-Dart reference cases, three same-ID conflict positions, three mixed
entries and expired-window rejection. Its clock is deliberately synthetic. It
never emits canonical ACK or advances a cursor. `probe_kindle.lua` is a separate
KUAL entry point, using the installed KOReader modules after `setupkoenv`, with
bounded fixture/native-source reads and a bounded public report. It loads no
Statistics, sidecar, Reader, device/UI framework or network service.

`probe_bundle.py` packages exact Git blobs from a full commit SHA, preserving
canonical bytes. The launcher is derived from the already-tested transport
diagnostic launcher by replacing only its fixed owned extension name; the
single-use lock and owned-PID deadline remain the same. The two diagnostic
profiles have separate directories and no shared runtime/session files.

After host tests/CI pass for the intended source:

```sh
python tools/reading_wire/probe_bundle.py prepare --source-commit <40-character-commit> --output <fresh-bundle-directory>
python tools/reading_wire/probe_bundle.py install --bundle <bundle-directory> --kindle-root <mounted-root> --observation <fresh-host-observation.json>
```

Installation requires the observed `v2026.07.1` baseline, its LuaJIT executable,
plain installed `common/dkjson.lua` / `ffi/sha2.lua`, an existing plain KUAL
extensions directory and at least 4 MiB free. It captures those source hashes
before/after installation and creates only the fresh
`extensions/quartzo-wire-probe` directory. Existing files/directories, junctions,
changed source, unknown entries and unavailable device storage fail without
replacement or automatic deletion. No credentials, reference libraries,
Statistics or real event data are packaged.

The required human step is safe USB disconnection, then KUAL → **Quartzo wire
diagnostic** → **Run synthetic offline wire test**, followed by USB reconnection.
The probe does not require a Wi-Fi change. The launcher's complete process is
bounded to 120 seconds plus termination grace and discards arbitrary native
stdout/stderr. A completed run is single-use; preserve its output for collection.

```sh
python tools/reading_wire/probe_bundle.py collect --bundle <bundle-directory> --kindle-root <mounted-root> --observation <installation-observation.json> --output <fresh-collected-report.json>
```

Collection revalidates exact source, run/manifest/commit identity, the installed
native hashes, all counts, actual LuaJIT/ARM metadata and strict false effect/ACK
fields. Changed modules, incomplete reports and leftover report staging reject.
Matching synthetic input observations alone never establish hardware origin:
the returned `physical_execution_attested` stays false. Any later source-specific
physical acceptance must additionally record the real mounted target and human
execution observation; a mocked mount or x64 host execution is not a PW3 PASS.

Host tests exercise the harness through actual pinned JSON/SHA libraries, the
driver with an explicit I/O/module/exit allow-list, and package/install/collect
against owned synthetic mounts. They include a real Windows junction or Unix
symlink guard, changed native source, low storage, malformed metadata,
incomplete/ACK-claiming reports and preservation of existing fixtures. These are
tool safety/compatibility tests, not Statistics extraction, durable storage,
production networking, performance-budget or release acceptance.

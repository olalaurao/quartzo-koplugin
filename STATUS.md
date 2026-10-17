# Implementation Status

## 2026-10-17 — Upstream wire contract candidate (no plugin runtime change)

- Corrected upstream HEAD is now `f0b4f98ec366916799a64e80afdae22cc122b16a`, with [fresh hosted CI 39031054949](https://github.com/olalaurao/aplicativo/actions/runs/39031054949) **in progress**. Earlier bb32e96e run39030194441 **FAILED** with 2563 PASS / one skipped / one failure: the strict Companion manifest test omitted the new transport-version key. Python schema/goldens, preflight, architecture and analysis passed; analysis had 17 baseline infos, zero warnings/errors. Corrected exactly the expected metadata key and 1.0.0 assertion without weakening the set check. Local full affected Companion-contract file plus wire suite: **60 PASS**. The earlier failure remains a failure; no corrected full-suite PASS is claimed before observation.
- Upstream app `bb32e96e42027ec3a411fd96268fbd49e2056483` adds separate `readingTransportContractVersion: 1.0.0`: current opaque pairing/vault/device/epoch binding, five-minute explicit UTC freshness, immutable line/batch digest, attempt-specific nonce and exact ordered per-event response matching. Invalid/unsupported lines remain isolated; same-ID divergent native facts quarantine matching positions. Staging/errors cannot carry canonical revisions, and parsed claims have no durable ACK/cursor authority. Raw event/shard versions are unchanged.
- Upstream validation: **242 protocol/contracts/shards/architecture PASS**, supplementary **40 protocol PASS**, clean scoped model/test analysis, preflight and independent Python checks of four schemas/12 shared negative wire vectors plus event/shard/batch/native SHA-256 goldens. [Hosted CI 39030194441](https://github.com/olalaurao/aplicativo/actions/runs/39030194441) is still pending. Initial source ddf73b69 omitted the ignored public requirements file; bb32e96e includes it plus a narrow ignore exception. No CI PASS is inferred for the new source.
- This is only the candidate wire/parser boundary. Authenticated production receiver, credential/revocation/replay lifecycle, canonical receipt issuer and actual per-event outbox acknowledgements remain unimplemented. Lua parity and Companion semantic/lock adoption must follow upstream ratification/merge. Production 0A/0B/0C and G08 remain open; no plugin extractor/outbox/transport is enabled by adding schemas.
- Kindle runtime source remains f080644a with its already-recorded narrow physical TLS diagnostic and verified manual cleanup. No Lua/device/Reader/Companion/Statistics/settings/Wi-Fi file or setting was changed. Validation here is document/diff inspection only; no new device execution is claimed. Exact next dependency remains canonical cross-process/Drive/Companion durability and authenticated receipt semantics; the protocol candidate makes those boundaries explicit without granting them.

## 2026-10-16 — Manual diagnostic cleanup verified complete

- The user confirmed removing the three owned diagnostic folders in Explorer. Read-only verification at **2026-10-17T00:31:31.2109438Z** confirmed all three absent: the isolated Kindle extension and private host session/bundle. D: was mounted, and KOReader still reported **v2026.07.1**, so the missing extension was not inferred from an unavailable volume.
- Updated the [physical evidence cleanup flags](docs/evidence/transport-probe-pw3-2026-10-16.json) to verified removed, preserving the two automatic-review rejections as history and recording manual removal separately. No further deletion command was attempted. The listener was already closed. **Diagnostic cleanup: COMPLETE**; the successful physical result and source hashes are unchanged.
- Validation: direct filesystem/version inspection and JSON/source-fingerprint integrity check; no runtime source changed, so the existing 34-test host CI and physical proof retain their original source boundary. Full G04/canonical persistence/ACK, Drive/Companion and device recovery gates remain open. Next finish those canonical contracts/proofs before production ingestion; temporary-file cleanup is no longer a blocker.

## 2026-10-16 — Physical PW3 synthetic TLS diagnostic PASS; full G04 open

- The user confirmed executing the installed KUAL diagnostic and reconnecting USB. The actual device observation and independently collected host observation agree on correlation `ba83c75346161f6b671c72b1c6a2406c`; the collector revalidated every installed bundle file against the clean-source manifest. **Physical synthetic TLS diagnostic: PASS** on the user-confirmed PW3, observed KOReader **v2026.07.1**, Lua **5.1**, LuaSec **1.3.2**. Runtime source: `f080644a7dbf9a16e7f9b94759ae0b42525fa9d8`; later commits so far are evidence-only.
- Actual device elapsed time **5.019867897 seconds**, **nine attempts**. Wrong CA rejected for a certificate reason; invalid and expired credentials returned 401; first 429 and 503 were observed and each retried once; replay returned the exact false-ACK receipt. Host: one unauthorized, one expired, one rate fault, one server fault, four successful responses, one unique fixed synthetic payload, TLSv1.2 and **zero server errors**. No canonical event was ingested or acknowledged.
- [Sanitized physical evidence](docs/evidence/transport-probe-pw3-2026-10-16.json) preserves source hashes, both original observations and separate human execution attestation. The automatic collector's physical-attestation false flag is retained verbatim: matching files alone never attest a device. The outer human attestation plus actual correlated observations supplies this narrow physical proof. No endpoint, token, private key, serial, book data or private runtime path is published.
- The ephemeral server stopped and its listener is closed. Installed Statistics public source still hashes to `da6db5e381bcfdaf05053d23bf75781166cc713b14076a65fcd2c527067fd088`; the harness never opened its database/sidecars. Reader/SimpleUI/settings were not modified. Wi-Fi was manually controlled by the user, never by the harness.
- **Cleanup PENDING, not PASS:** automatic approval review rejected both the guarded recursive cleanup and the safer individual-known-file/empty-directory cleanup with `blocked by policy`, without a more specific reason. Neither command ran. Diagnostic extension and private host session/bundle remain; the user was given the three exact owned paths for manual Explorer removal. Evidence flags stay false until absence is verified. No alternate execution engine or deletion method was used to bypass the rejection.
- Host source CI remains [38985034983](https://github.com/olalaurao/quartzo-koplugin/actions/runs/38985034983), **34 PASS**; evidence-only c5dc8dc also passed [38985333038](https://github.com/olalaurao/quartzo-koplugin/actions/runs/38985333038). This physical diagnostic closes only the bounded synthetic TLS/auth/error/retry/replay spike. **Full G04 / production 0B remains open**: canonical destination/Drive/Companion durability, authenticated canonical request/per-event ACK contract, revocation and device offline/reboot/cancellation recovery still require implementation/proof. No selected production backend, native extractor/outbox/receiver, Resource effect or plugin ZIP was introduced.
- Exact next step: verify the requested manual cleanup; then finish the upstream canonical durability/identity/ownership contracts and versioned request/ACK semantics before preparing any production receiver or native extraction. Preserve the successful diagnostic as evidence rather than treating its receipt as a cursor permission.

## 2026-10-16 — Clean-source diagnostic installed; physical KUAL run pending

- Harness source `f080644a7dbf9a16e7f9b94759ae0b42525fa9d8` passed [Linux CI 38985034983](https://github.com/olalaurao/quartzo-koplugin/actions/runs/38985034983): **34 PASS**, no skipped cases, in 12.260 seconds. Both actual POSIX single-use/watchdog tests passed and the unrelated process remained alive. Windows separately passed 32 cases and skipped those two platform-specific cases; shell syntax passed. These are host checks, not PW3 execution.
- Reconfirmed mounted D: / KOReader v2026.07.1 and absence of the diagnostic target. Started one explicit ephemeral LAN TLS fixture with a 30-minute bound, generated fresh synthetic-only credentials/certificates in private OS-temp storage, and installed/verified exactly **11 files** in the new `extensions/quartzo-transport-probe` folder. No existing extension, KOReader/Reader/SimpleUI/Statistics/settings file was overwritten; no firewall or Wi-Fi setting changed. Host private keys were not copied. Runtime source was clean at f080644a; later evidence-only changes do not alter the deployed byte manifest.
- Public correlation ID: `ba83c75346161f6b671c72b1c6a2406c`. Endpoint, token, expiry config and host private runtime paths are intentionally omitted. The live listener stops after the expected sequence, private stop request or expiry; credentials are diagnostic-only and short-lived.
- **Physical result: PENDING.** The user has been given the exact manual USB-disconnect / Wi-Fi-on / KUAL diagnostic / USB-reconnect step. Installation through USB does not prove launch, certificate verification or requests from Kindle. Collect only after actual execution/reconnection and match the clean-source manifests plus both reports. Failure/expiry requires a fresh session and explicit owned-folder cleanup; never loosen validation or overwrite an existing target.
- Upstream evidence-only 6e2a208c also passed [Hosted Docs Validation 38984197734](https://github.com/olalaurao/aplicativo/actions/runs/38984197734): **2524 PASS / one skipped**. A later local upstream handoff run passed **144 architecture tests**. The implemented runtime remains 754a2d57; no production ingestion/effect is enabled. All full G04/canonical durability/Drive/Companion exit requirements remain open.

## 2026-10-16 — Single-use physical diagnostic preparation

- Added a separate KUAL extension harness (`device.lua`, `kindle.lua`, `run.sh`, menu/config), not a `.koplugin`. It loads only minimal KOReader module setup/native JSON/socket/TLS, never production Reader/UI/Statistics. An atomic single-use directory guard prevents repeated execution; the watchdog bounds the disposable process to 120 seconds plus two seconds for termination and checks process-start identity before targeting it. Native stdout/stderr are discarded; results contain fixed codes only. Wi-Fi remains entirely manual.
- `bundle.py` prepares private bundles only in fresh OS-temp paths outside Git, copies an exact allowlist without private keys, verifies bytes, and installs only a new `extensions/quartzo-transport-probe` directory after checking mounted v2026.07.1/luajit. Existing targets are never overwritten or recursively deleted. Collection requires exact matching manifests, run IDs, baseline versions, all nine attempts, TLS/counter parity and false effect flags. Even a matched fixture keeps physical attestation false until actual KUAL execution is separately confirmed; it never becomes canonical ACK/persistence proof.
- Extended host validation: **32 PASS / two Linux-only process tests skipped** on Windows, including seven real-Lua harness cases and seven bundle/collection cases. Existing Reader/settings sentinel bytes were preserved in the owned fake mount. Git Bash shell syntax check passed. The two added POSIX tests exercise actual single-use/deadline process behavior and unrelated-process preservation on Linux; fresh source CI is required. No Kindle deployment/execution has occurred at this preparation checkpoint; all bundle/install/collection tests use owned synthetic host directories.
- The CLI fixture now closes on the expected complete request sequence, explicit private stop marker or expiry. No firewall/network setting is changed. Exact next step: clean-source Linux CI, then a fresh short-lived host session and isolated new-folder installation while D: is mounted; human safely disconnects USB, manually enables Wi-Fi and runs the KUAL diagnostic, then reconnects for correlated collection. If unreachable/expired, record failure and use a new session; never relax TLS or return a durable ACK.
- Production G04/0B remains open: a synthetic transport diagnostic cannot establish native extraction, canonical durability/ACK, Drive recovery, Companion adoption, revocation lifecycle or production transport selection. G08 and later dependent runtime phases remain blocked. Reader, Companion, SimpleUI/Extra, Statistics and production app/vault are unchanged.

## 2026-10-16 — Ephemeral TLS host fixture and corrected upstream verifier

- The isolated G04 tools now include `host.py`, a short-lived opt-in TLS 1.2 fixture bound to an explicit private IPv4. It creates ephemeral credentials/independent certificates only in a fresh OS-temp directory outside Git, never opens a vault/Statistics/Reader account, and accepts exactly the fixed synthetic fixture bytes. Only false canonical-ACK/persistence receipts are returned. Public reports omit secrets, endpoints, peer addresses and runtime paths, and always keep Kindle/canonical proof false.
- **18 host tests PASS twice**: nine real-Lua-5.1 injected-client tests plus nine real Python/OpenSSL loopback TLS/HTTP cases. They cover good/bad trust, auth/current expiry/expired marker/scope, malformed credentials, 429/503/retry/replay, receipt parity, input bounds and runtime/report privacy. First host suite had 15 PASS; the extended run had **17 PASS / one error** on Windows because an early 404 left TLS request bytes unread. Bounded body consumption before early replies fixed that connection reset; all 18 then passed and passed again with the OS-temp confinement guard. This is actual loopback TLS, not native Kindle LuaSec or physical transport proof.
- Added host-only GitHub CI for these tools, using Python 3.12 and pinned test-only Lupa 2.8. Corrected source `87e04a66fd6ad3e756b7ef368707a8702a74b803` passed [Diagnostic transport host tests 38984191702](https://github.com/olalaurao/quartzo-koplugin/actions/runs/38984191702): **18 PASS** on Linux in 7.062 seconds. It cannot mark any physical/plugin gate PASS. The Windows host run used Python 3.14 / Lua 5.1.
- Initial workflow attempt [38983893514](https://github.com/olalaurao/quartzo-koplugin/actions/runs/38983893514) is **FAILED before any job**. The unquoted plain `run` scalar contained `--only-binary=:all:` (colon followed by a space); changed command scalars to YAML literal blocks. A fresh actual CI run is required; no Linux/CI PASS is inferred from the earlier local tests.
- Upstream 754a2d579858ddb9ddc020a90d7f1ebe1589d36b corrected a real Android returning-mmap-pragma API failure. It now passes clean-source Android observed-local cross-batch verification/scratch cleanup/restart/retry/conflicts, 100k/500k host stress and [full hosted CI 38982194464](https://github.com/olalaurao/aplicativo/actions/runs/38982194464): **2524 PASS / one skipped**, 95 architecture/doc checks and analysis without errors/warnings (17 baseline infos). Its exact reports live upstream; the earlier fbd38101 Android attempt remains FAILED. Tiny physical inputs and host stress are synthetic, not native Kindle ingestion or Android scale budgets.
- The data/production gates remain open. No KUAL launcher, device provisioning/collection, plugin ZIP, native-event codec/extractor/outbox/receiver, canonical ACK or production backend selection was added. The next G04 step is an isolated bounded on-device harness with correlated host/device results and explicitly manual Wi-Fi, while preserving all existing Reader/SimpleUI/Statistics/settings. A real canonical ACK still needs upstream canonical/Drive/Companion durability proof; local fixture receipts never advance a cursor.

## 2026-10-16 — Isolated G04 client preparation (no device deployment)

- `tools/transport_probe/client.lua` adds only diagnostic request policy and a bounded LuaSec adapter, outside any `.koplugin` runtime. This is the independent non-production G04 spike preparation permitted by the adopted integrated gate matrix while G01–G03 remain open; it does not require or grant a production phase exit.
- The installed KOReader v2026.07.1 package contains LuaSec 1.3.2 and exposes explicit TLS/peer/cafile options. The new adapter supplies those options rather than inheriting the packaged `verify = "none"` default. It accepts only explicit private-IPv4 HTTPS targets, disables redirects, bounds bytes/timeouts/retries, and requires exact diagnostic receipts whose canonical ACK/persistence flags are false. No conclusion about the entire Reader runtime's TLS policy is inferred from this library inspection.
- Host validation: **9 PASS**, executed with real Lua 5.1 through Lupa 2.8 / Python 3.14, injecting HTTP/clock/sleep. Cases include wrong-CA certificate failure versus offline, invalid/expired auth, noncanonical receipt, private-target/trust/clock preflight, bounded Retry-After/retry exhaustion, TLS adapter options and response cap. These are logic tests, not native TLS, network or PW3 proof. Test dependency was installed only into the private host diagnostics directory; requirements are pinned for reproduction.
- Extending the adapter case with a CRLF-header injection fixture initially produced **one test error / eight passed**: the Python triple-quoted Lua fixture interpreted the escape before Lua parsed it. Constructed the synthetic CRLF value with `string.char(13,10)` instead; the final rerun is **9 PASS**, including rejection before network I/O. The earlier error remains an error; no physical result is inferred from these runs.
- No endpoint, production token, private key, runtime config, KUAL launcher, plugin ZIP or Kindle deployment is included yet. The ephemeral TLS fixture host, credential/cert setup, executable on-device harness and correlated collection remain next. No Statistics/config/sidecar/Reader/SimpleUI/Wi-Fi file or setting changed. The existing pure raw-event contracts are not replaced by this diagnostic receipt.
- Gate 0A remains partial, 0B **BLOCKED for production**, and 0C lacks the authenticated canonical request/ACK protocol. Before any production transport selection, prove actual data-owner durability and authenticated PW3 behavior, errors/retry/revocation and real canonical ACK. A staging receipt never advances a cursor.
- This entry supersedes earlier blanket descriptions of the repository as having no Lua: it now has diagnostic-only Lua, with no production plugin/codec/extractor/outbox/ingress implemented. See `tools/transport_probe/README.md` for exact boundaries and remaining steps.

## 2026-10-16 — Android local discovery proof and Kindle USB reconnection

This supplements the integrated reconciliation below; no production plugin phase is unlocked.

- Upstream source `e8c79a0620b7e9f137e4c0188a18cfe68f4ba47c` adds bounded local candidate discovery through the existing ObsidianService and a read-only scoped conflict check through SyncQueueService. Unexpected/temp/conflict artifacts, links/junctions and overflow fail without a partial inventory. Candidate paths certify no contents or atomic/global consistency. No new source of truth, runtime registration, distributed claim or ACK.
- Upstream local regression: **156 PASS**, including 13 new inventory/grammar/conflict/retarget/link cases and existing owner/queue/architecture suites. Scoped analysis exits 0 with no errors/warnings and four pre-existing ObsidianService infos. Initial test matcher and Windows junction-fixture failures are preserved in upstream STATUS and were corrected before this passing run. Contracts remain 1.0.0.
- Real SM-A546E / Android 16 API 36 probe on clean e8c79a06: **PASS**. Separate package/UID; actual process stop/relaunch; persisted files/native SQLite queue; retry/gap repair/native-payload conflict checks; candidate discovery, scan cap, unresolved sync row and unexpected artifact checks. Four events / 120 seconds are synthetic. The test package was removed and production package metadata remained unchanged. New APK SHA-256 `a1a1608bbccca0639c5400813ef5f786ed5da1132934073f6047afe9dbb748a2`; sanitized report and exact raw source fingerprints are in upstream `docs/reading-integration/android-discovery-probe-2026-10-16.json`. This is local Android proof only, not Drive, reboot/power-loss or canonical ACK.
- Upstream e8c79a06 passed [Hosted Docs Validation 38976318565](https://github.com/olalaurao/aplicativo/actions/runs/38976318565): **2506 full-suite PASS / one skipped**, **95 architecture/doc checks**, repository-policy analysis with 17 baseline infos and no errors/warnings. [Dial Focus CI 38976318614](https://github.com/olalaurao/aplicativo/actions/runs/38976318614) also passed. Agent Contract Gate was in progress and Windows Flutter CI queued at this checkpoint; later evidence-only pushes may start fresh runs. Prior c34799a7 also passed [38974540894](https://github.com/olalaurao/aplicativo/actions/runs/38974540894), certifying only its earlier source.
- The user reconnected Kindle D:. Read-only inspection again confirms KOReader v2026.07.1 and unchanged installed Statistics source SHA-256 `da6db5e381bcfdaf05053d23bf75781166cc713b14076a65fcd2c527067fd088`. No device files, Wi-Fi or Statistics database were modified. USB inspection is not KOReader runtime transport.
- Gate 0A remains partial: full-ledger/cross-batch stability, actual Drive recovery and Companion semantic adoption are pending. Gate 0B remains blocked without authenticated PW3 runtime transport. Gate 0C still lacks the authenticated canonical request/ACK protocol; later plugin phases remain blocked. No Lua implementation or plugin ZIP was created.
- Exact next dependency: review/merge the upstream candidates, prove complete canonical/Drive recovery and Companion consumption, then the approved smallest authenticated PW3 transport spike. Preserve Reader, SimpleUI/Extra, native Statistics, existing export ownership and all current statuses. The independently implemented upstream annotation projection still needs actual sanitized export/re-export proof.
- Validation here: documentation/diff inspection only; Lua unit/dev-check/package are not applicable to this documentation-only handoff. Reader and Companion remain unchanged.

## 2026-10-16 — Integrated Reading scope, Gate 0 reconciliation

This entry supersedes the planning-time current milestone below; historical entries remain evidence.

- Branch: `docs/reading-integration-gate0-reconciliation`; initial plugin HEAD `4fa9f3638617bfd973edb2adeb84672a6f432eab`.
- Upstream baseline: Quartzo `10e11ec93f52d1be34fa06c4d756342a8ae1e20e`, Companion `efa53aa64d8c08277aa7e68dbd79e8e9a61229be`, Reader `075458f6843df936b3810c12cd93851f57805eec`.
- Reader stable sequencing is satisfied by existing v1.0.0/v1.2.0 tags and documented acceptance. Main source constants say 1.2.1. Subsequent USB inspection found Reader 1.3.0-rc.1 installed, with all 86 runtime Lua files matching branch `feature/reader-metadata-editing-v1.3.0` at e82130ad3d0aeb8ee6d36543e397c64009b36001 after EOL normalization. PR 27 / its M10 acceptance remains open; no Reader code or branch was changed.
- User-confirmed latest physical baseline: PW3 / G090KB, firmware 5.16.2.1.1 (4097470002), KOReader **v2026.07.1**, package **kindlepw2**, functional jailbreak/KUAL. Reader `docs/KOREADER_UPGRADE.md` agrees. Reconfirm the actual installation before the next physical run. The user initially reported no connection, then identified the mounted Kindle drive. Read-only USB inspection confirmed KOReader git-rev v2026.07.1, SimpleUI 2.7.5 and SimpleUI Extra 1.15.0.
- Official v2026.07.1 Statistics source was inspected: schema 20221111, page_stat_data uniqueness `(id_book,page,start_time)`, book title/authors/md5 uniqueness, flush at close/save/suspend. Source SHA-256 `da6db5e381bcfdaf05053d23bf75781166cc713b14076a65fcd2c527067fd088`. Installed Statistics source hash matches the official source byte-for-byte; mounted DB header also says user_version 20221111, WAL format. Live SQL was skipped to avoid auxiliary WAL writes. This is inspection evidence, not a plugin extraction/concurrency or runtime transport test.
- A subsequent host-only immutable frozen-copy audit passed SQLite quick_check and confirmed 39 book rows, 5105 native events and two MD5 groups containing multiple book rows. Source bytes remained unchanged, no WAL appeared, and the temporary host copy was removed. No titles, raw private rows or credentials are recorded. This proves the need for row-scoped native identity; it does not establish Reader provenance or runtime transport.
- Adopted scope: one-way validated reading/status evidence and restricted opt-in Reader-origin KOReader promotion through upstream Resource owners. Ordinary/unmatched documents do not auto-create. Reader-only catalog/progress does not create Resource or minutes. No bidirectional progress/status writeback or highlights owner added.
- Quartzo candidate branch: `feature/reading-integration-contracts-g00-g03`; active spec `docs/specs/reading-integration.md`, ADR `docs/adrs/reading-integration-v1.md`, handoff `docs/reading-integration/STATUS.md`, versioned contracts in `contracts/quartzo/reading_identity`, `reading_evidence_status`, `reading_activity`. Candidate is not merged/deployed.
- Upstream draft review: [aplicativo PR 65](https://github.com/olalaurao/aplicativo/pull/65), implementation commits 83f084ec (contracts), 16a775de (source-specific approval/canonical parser) and dbd38dcb (independent read-only catalog). Final combined targeted run: 98 PASS; documentation/architecture: 95 PASS. Initial full suite had 2422 PASS, one skipped and two failures corrected and rerun in full affected test files; no full-suite PASS is claimed. CI state is tracked in upstream STATUS.
- Subsequent G03 progress upstream: be873875 (bounded canonical shard planner and independent Python golden path), 28d26b85962ea3250ae28225e8909e2759283bb0 (unregistered local file/queue adapter through existing owners). Final combined targeted run: 116 PASS; vault/sync owner regressions: 55 PASS / one skipped; native-shard SyncManager/in-memory Drive upload/replay/conflict cases: 2 PASS; post-store architecture/docs: 84 PASS. Hosted Docs Validation [38937822480](https://github.com/olalaurao/aplicativo/actions/runs/38937822480) passed on be873875; the newer local-store commit requires fresh CI. This does not prove actual cloud, cross-process, power-loss or physical transport durability. No ACK API was added.
- Further source-only B03 audit (Reader main 075458f6 and installed branch e82130ad): documents map `reader_id` to unique `local_path`, but the table has no account namespace. Config/UI token save/clear does not itself bind/reset this provenance. HTML `local_content_hash` is MD5 of rendered HTML; raw PDF/EPUB installation records it as nil, and its remote fingerprint includes updated time/category/byte count. Neither is proven equivalent to Statistics partial MD5. The status scanner exposes only partial-MD5 presence, not the digest as a public identity API. Main migrations expect schema 3; installed branch source expects schema 4 (metadata additions), not a live DB schema observation. Therefore a future optional adapter needs explicit account/device/epoch binding and format-specific artifact/Statistics proof; it cannot join these columns by textual hash equality or consume the private DB as a stable public API. No real Reader DB/config/token values were read for this source audit.
- User-supplied export-template audit upstream at ec12d0ef6e83ff7b22716943aea45bc4b101c2fb: current template has no fixed status, but marker-aware real-vault inspection found 110 export collision candidates under resources. Canonical parsing: 90 inProgress values with no persisted IDs, 20 invalid-YAML cases with IDs unknown, zero repeated export-book IDs. The prior YAML book_id-only scan was insufficient. A private local report stays outside all repos; every action is keep_current_blocked, status origin manual_or_unknown. No real Markdown/config/status/ID was changed. Promotion/status policies now explicitly default closed without export ownership/canonical writer proof. Synthetic template/ownership regression: 121 PASS combined; architecture/docs: 95 PASS; scoped analysis clean. Hosted CI on prior e437ece9 passed full suite 2459 / one skipped; ec12d0ef needs fresh CI. Existing export-as-Resource ownership/separation, protected backup/pilot and actual new export/re-export remain blockers; no mass migration is authorized by this audit.
- Final upstream implementation CI at ec12d0ef: [Hosted Docs Validation 38944221690](https://github.com/olalaurao/aplicativo/actions/runs/38944221690) **SUCCESS**, full suite **2464 PASS / one skipped**, architecture/docs **95 PASS**, analysis without errors/warnings (17 baseline infos). Agent Contract Gate and Dial Focus CI also succeeded; remaining Windows Flutter CI jobs were queued at the checkpoint. Later upstream bf86dad7 only records the handoff. These results do not close physical/export/Drive/Companion gates or authorize production plugin phases. The next independent read-only task is the existing annotation projection's supplied bullet/wiki-tag format, not a new writer/UI.
- Gate 0A: **IN_PROGRESS**, explicit upstream vault-domain/owner candidate and local adapter tested, actual cross-process/canonical/Drive durability and Companion adoption still pending.
- Gate 0B: **BLOCKED**, USB inspection succeeded but no selected runtime transport or authenticated payload/TLS/error/ACK proof exists. No endpoint or always-on backend assumed.
- Gate 0C: **IN_PROGRESS**, raw-event/identity/status vectors implemented upstream; versioned authenticated request/response/ACK protocol and Lua consumer not yet implemented. Changed native duration with the same tuple is conflict, never a new event.
- Gates 1–9 remain **BLOCKED**. No plugin runtime code, ZIP, live SQLite query, outbox, network action or Wi-Fi change was introduced. No runtime physical gate is marked PASS.
- Changes here: reconcile IMPLEMENTATION_SPEC/PLAN/README target and scope; preserve original historical planning. No credentials or private document data added.
- Validation here: documentation/Git diff inspection only; Lua unit/dev-check/package are not applicable because this repo still has no Lua implementation. Upstream Dart/architecture/schema/Companion compatibility results live in the upstream STATUS.
- Exact next step: review/merge upstream canonical contracts, prove actual vault shard persistence/Drive recovery and Companion consumption, then run the smallest authenticated transport spike on PW3 after leaving USB export mode safely with canonical ACK. Do not start production plugin phases while 0A/0B/0C remain open.


> **Repository:** `olalaurao/quartzo-koplugin`  
> **Canonical implementation spec:** `IMPLEMENTATION_SPEC.md`  
> **Product roadmap:** `PLAN.md`  
> **Last updated:** 2026-09-22

## Current milestone

**PLANNING COMPLETE — IMPLEMENTATION INTENTIONALLY DEFERRED**

No production plugin code has been implemented yet.

Default sequencing decision:

`olalaurao/reader` stable V1/tag → revalidate upstream Quartzo/Companion/KOReader state → open Gate 0 for this project.

Do not start Phase A merely because the repository now contains planning documents. Gate 0 must first settle the canonical Reading Activity owner, transport and protocol contract.

## Current branch / planning commits

- Branch: `main`
- Initial repository commit: `07f61a40d2e87675de03a29bd3ef8b9054e77feb`
- Agent bootstrap: `d5105b53c6c20b2f4acdce06567982c5e3e5c516`
- Detailed product/delivery plan: `3be2127f03f1edc027ba0fef81c81c66544bc27a`
- Canonical implementation specification: `cbfb41382d02d19207a1a38945b4dd74dfb35bcc`
- This status/README documentation pass follows those commits.

## Planning-time upstream snapshot

These SHAs are evidence for the planning pass only. Re-check them when implementation begins.

- Quartzo app `olalaurao/aplicativo`: `9910de0eadc53f4be9d420d3dab7ff8326e2267d`
- Quartzo Companion `olalaurao/quartzo-obsidian-companion`: observed current main around `ff10ff789eeec8b0f199afccf2ae612388428e3e`
- Readwise Reader plugin `olalaurao/reader`: Phase E merged to main at `e5de4a75a9e8e43dd270194201626c80d0c15802`
- KOReader target source: `v2025.04`

## Target environment

- Kindle Paperwhite 3 / 7th generation
- Serial family: `G090KB`
- Firmware: `5.16.2.1.1 (4097470002)`
- Jailbreak/KUAL functional
- KOReader: `2025.04`

## Gate status

| Gate | Status | Blocker / exit condition |
| --- | --- | --- |
| Gate 0A — canonical Reading Activity owner | **OPEN / NOT STARTED** | Quartzo upstream must document Reading Activity's canonical persisted source and owners. |
| Gate 0B — Kindle→Quartzo transport proof | **OPEN / NOT STARTED** | Selected authenticated transport must be proven on the real PW3. |
| Gate 0C — protocol/idempotency fixture | **OPEN / NOT STARTED** | Versioned request/response, deterministic event ID and duplicate semantics must be fixed by contract. |
| Gate 1 — plugin bootstrap | **BLOCKED** | Requires Gate 0. |
| Gate 2 — read-only Statistics probe | **BLOCKED** | Requires Gate 0 and bootstrap. |
| Gate 3 — deterministic event extraction | **BLOCKED** | Requires Gate 2. |
| Gate 4 — durable state/outbox | **BLOCKED** | Requires Gate 3. |
| Gate 5 — transport client | **BLOCKED** | Requires Gates 0–4. |
| Gate 6 — one-event end-to-end | **BLOCKED** | Requires canonical Quartzo ingestion + Gate 5. |
| Gate 7 — Resource association | **BLOCKED** | Requires Gate 6. |
| Gate 8 — full-history backfill | **BLOCKED** | Requires stable incremental ingestion. |
| Gate 9 — lifecycle/auto-sync | **BLOCKED** | Requires stable manual/backfill sync. |

## Research conclusions recorded for implementation

### KOReader Statistics

Verified against KOReader 2025.04:

- statistics database path is `settings/statistics.sqlite3`;
- schema version is `20221111`;
- raw reading events live in `page_stat_data`;
- event source fields are `id_book`, `page`, `start_time`, `duration`, `total_pages`;
- `book` includes metadata and the KOReader MD5;
- the unique key is title + authors + MD5, therefore multiple `book.id` rows can share one MD5;
- Statistics flushes on close/save-settings/suspend;
- Quartzo must never write to this DB.

### Sync model

Planned sync model:

- raw event ingestion rather than only accumulated totals;
- deterministic event IDs;
- random opaque device ID;
- ack-gated watermark;
- intentional overlap around timestamp batch boundaries;
- canonical receiver deduplicates retries;
- durable local pending work;
- resumable backfill;
- single/coalescing sync coordinator.

### Quartzo architecture

Current Quartzo architecture does not permit a feature-local parallel source of truth.

Before production implementation:

- Reading Activity must be added as an explicit canonical domain upstream;
- if it is not vault Markdown, that source must be documented in Quartzo's domain source-of-truth architecture;
- if it is vault-backed, its shard/write/conflict model must be documented;
- the plugin's local state remains transport/cursor/cache only.

### Transport

No production transport has been selected.

Gate 0 must compare/prove at least:

1. minimal authenticated HTTPS ingress/relay;
2. direct Google Drive API if practical and architecturally safe;
3. staging provider + Quartzo importer as fallback;
4. full Statistics DB upload only as migration/debug fallback, not the normal protocol.

### Identity

Hard rule:

- never merge reading history to a Resource by title alone.

Potential exact identities:

- persisted Quartzo Resource ID;
- explicit external identity in a proven namespace;
- prior user-approved KOReader digest association.

Quartzo currently persists `Resource.readwiseBookId` as `book_id`, but this project must **not** assume that value is the same namespace as a Readwise Reader API v3 document ID.

### Existing plugin references

Patterns were reviewed from:

- KOReader Reading Statistics;
- KOSync;
- Exporter;
- BookOrbit;
- KoInsight;
- Syncery;
- the existing `olalaurao/reader` project.

BookOrbit is particularly relevant for read-only Statistics access, grouped MD5 identity, ack-gated watermarks, overlap-safe batching, atomic local state and serialized sync work.

## Implementation dependency status

`olalaurao/reader` is **not yet treated as a frozen V1 dependency** by this project.

When resuming:

1. confirm the Reader plugin has reached the desired stable V1/tag, or record an explicit user decision to waive this sequencing constraint;
2. re-read its final state/mapping format;
3. do not make Quartzo depend on Reader for core statistics sync;
4. add Reader provenance only as an optional adapter.

## Exact next action when work begins

1. Pull/inspect all four relevant repositories.
2. Read this repo's `AGENT_BOOTSTRAP.md`, `STATUS.md`, `IMPLEMENTATION_SPEC.md`, `PLAN.md`.
3. Pin fresh upstream SHAs in this file.
4. Re-read current Quartzo canonical architecture and active specs.
5. Check whether Reading Activity or a suitable ingress API already exists upstream by then.
6. Create/update the active upstream Reading Activity contract.
7. Open a Gate 0 transport spike branch.
8. Prove the smallest authenticated payload from the real PW3.
9. Do not create general sync code until Gate 0A/0B/0C pass.

## No-code guarantee for this planning pass

This planning session intentionally did **not**:

- create `quartzo.koplugin/` implementation code;
- access or modify the user's Kindle;
- access or modify `statistics.sqlite3`;
- create a Quartzo backend;
- alter the Quartzo app or Companion;
- choose a transport without evidence;
- add secrets or credentials.

Only project documentation/planning was added.

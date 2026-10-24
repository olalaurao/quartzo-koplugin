# Quartzo ↔ KOReader — Implementation Specification

2026-10-23 PhaseD review validation correction:
The SAME outbox validator governs staged and restored pending-review descriptors.
Require integer start type, integer source text when its recorded SQLite type is
integer, and empty integer-field projection for noninteger source types, with the
existing field/count bounds. Reject inconsistent batches before BEGIN so valid
neighbors and existing recoverable state remain untouched. Schema-v1 CREATE bytes,
identity, receipts and source-cursor rules do not change. New inherited native SDK
cases must pass exact-head CI. Refresh source-bound 0.0.7/offline artifacts; prior
336a7a8 preparations remain historical, not installed. Physical Gate4 and verified
source-generation enrollment remain required; no later phase is enabled.


Exactc70a4e7 native CI39998554809 accepted0.0.7 host scope:400 cases/no skips
(251 plugin,34 transport,115 wire), with the same77,357-byte package on Linux and
Windows. See docs/evidence/outbox-recovery-ui-host-2026-10-23.json. Physical Gate4,
source generation and production registration remain OPEN; nothing is installed.

2026-10-23 PhaseD0.0.7 manual recovery controls:
Expose the SAME outbox owner through Offline reading queue, without initializing
state or enrolling a source. Load the sole codec/KOReader adapter lazily from the
plugin namespace; their previous tools copies are moved, not duplicated. Confirm
backup/restore, show progress next tick and guard repeated operations while busy.
Native ButtonDialog renders title; fixed errors omit private paths/SQL/content.
Metadata-only discovery visits at most512 entries and32 supported regular leaves;
no automatic selection. File dates sort display only, never identify a generation.
Restore supplies reviewed device/epoch/counts/canonical_ack=false, checked before
target creation and again in the copy transaction. Validate all canonical content
as before, retain original identity and refuse an existing primary. No full-snapshot
signature/lease is implied; an interrupted destination remains unregistered for
review. Schema-v1 CREATE bytes, ACK/cursor rules and source owner are unchanged.
Source-generation enrollment/reset lifecycle and physical Gate4 remain incomplete.


2026-10-22 PhaseD0.0.6 recovery validation correction:
Use the SAME owner declaration strings for CREATE and validation of schema-v1
identity/pending/review tables. Stored table_info alone cannot describe generated
columns, CHECK/UNIQUE/FK constraints, collation or table options. Accept exactly
the original CREATE declarations and two implicit PK indexes; unknown SQLite
internal objects are not silently dropped. Stored SQL projection is bounded and
there is no general SQL parser or second schema source. Unknown/equivalent edited
declarations require review, preserving input before any restore target creation.
Existing untouched owner CREATE bytes and schema version remain unchanged; this
requires no data migration. Exact9f7c3a7 CI passed373 cases/no skips, including
the actual native regression cases. Physical/source-enrollment gates remain.

2026-10-22 PhaseD offline acceptance preparation:
Use tools/plugin/outbox_probe_bundle.py as a definition of the existing wire
artifact owner and reuse its finite single-use KUAL launcher. No second installer,
production store, journal, receipt issuer, service or production lifecycle is
introduced. The same outbox/codec/paired consumer runs on synthetic isolated
state only. Six own child SIGKILL cases cover before/after stage, backup and
restore commits, with native entropy, live journal evidence, bounded waits and
kernel termination on parent death. Offline raw claims must not prune. Positive
receipt/prune acceptance still requires the normal scoped Android receiver.

Independent SQL only examines bounded private copies of synthetic outputs, never
mounted Statistics/user state. Exact expected schema/version0 partial files may
be zero bytes after native rollback, but cannot be enrolled or treated as healthy
empty outboxes. Unknown files/journals/schema/identity/bytes are refused. Matching
observations alone cannot attest hardware, source generation or canonical ACK.
Exactb081938 native x64 CI passed364 cases/no skips; actual PW3 proof is pending.
The user cannot operate devices; this block does not install or request execution.

2026-10-22 PhaseD0.0.5 recovery candidate:
Use the SAME SQLite outbox owner for explicit point-in-time recovery copies.
ATTACH/DELETE-journal/synchronous EXTRA transactions copy complete bounded
identity, pending and review tables; no alternate store, raw file copier,
serializer or custom journal. Every owner table/column/PK/default shape and
bounded content is validated. Unknown/future/foreign state cannot be silently
reinterpreted or dropped. Recovery filenames are strict own random leaves in
the same directory. Restore requires primary absence, keeps the original
device/epoch/selected bytes, never regenerates identity and never overwrites
damaged state. Ordinary open never selects backup automatically. Failed-copy
artifacts stay preserved/unregistered. A snapshot cannot recover selected facts
newer than its point in time or establish current Statistics generation.

Source-generation enrollment, reset UX/lifecycle and physical Gate4 remain open.
This extends only the existing PhaseD storage owner while user devices cannot
be operated; no installs, sessions, networking or production effects are enabled.
Exact92af1bd native CI passed357 cases/no skips, including eight actual
owned-process stage/prune/backup/restore interruption cases. This is host-only
acceptance, not physical Gate4 or hardware power-loss/source-generation proof.


2026-10-22 PhaseD0.0.4 candidate (supersedes historical .lua state example):
Use plugin-owned quartzo_sync_state.sqlite3 with existing native SQ3, DELETE
journal and synchronous EXTRA checked as3, not a new JSON/temp journaling layer.
It is a bounded outbox, not canonical Reading Activity. Explicit create generates
an OS-entropy device ID and takes an explicit source epoch; generation enrollment
is still a separate required production boundary. Existing-file open never
recreates missing/corrupt/future state, migrates unknown files or rotates identity.
Restore/review identity before historical replay. Native rw is required only for
this owned store's hot-journal recovery; Statistics always stays explicit ro.

Selected canonical bytes survive source deletion. Duplicate stage preserves the
first bytes; native conflict/capacity/commit failures rollback. Bounded pending
review cannot be auto-discarded. Native transactions replace snapshots atomically;
there is no independent staging/temp-file promotion or recovery framework.
The unchanged paired_exchange owner moves into quartzo.koplugin/quartzo with its
consumers updated. Only its opaque session/request-bound receipts can prune exact
per-event native/line bindings; there is no accepted-ID list/boolean shortcut.
No source watermark API is exposed: conservative replay must retain identity and
use canonical deduplication. Source-generation/reset/lifecycle integration remains
required before production; do not treat local scan positions as acknowledged.

Gate4 stays OPEN until full native tests and actual PW3 crash/restart/paired
receipt acceptance. Current host process-stop/SDK fixtures are not device/power
loss evidence. No lifecycle/network/configuration/ingestion hook is enabled;
user cannot operate devices now, so no new install or timed session is started.


2026-10-22 PhaseC0.0.3 accepted fixture/native Gate3 (historical SQL superseded):
Reuse the existing Statistics read-only/schema/snapshot owner and wire codec.
Book enumeration is keyset-bounded; event collection defaults50/max100 rows,
with one bounded lookahead and at most two native time-index seeks per batch.
A250-event same-second fixture proves simple overlap alone cannot progress
within a smaller batch. Use transient `(start_time,rowid)` scan ordering; native
event identity remains the ratified device/epoch/book/page/start tuple. Separate
`start_time = ? AND rowid > ?` and `start_time > ?` seeks avoid SQLite's observed
linear equal-time rescan for a combined row-value predicate. No new DB index,
write SQL or durable rowid/checkpoint is permitted. Restart from inclusive time
overlap; any acknowledged source position still requires trusted receipts in
later phases. Arbitrarily backdated mutations/DB maintenance require the later
lifecycle/epoch/backfill policy, not an inferred continuous-source guarantee.

Invalid numeric payloads remain bounded pending-review descriptors, retaining
exact integer text/type flags without arbitrary TEXT/BLOB. Unsafe scan keys
reject the whole batch without continuation. Native page zero is observed in
ten private-backup rows and remains outside the ratified canonical contract;
do not fabricate a page, discard the row or infer an ACK. Transient scanning
may reach valid neighbors, but later durable state must retain unresolved
review and cannot advance an acknowledged checkpoint across it. Never hide
invalid rows via `total_pages > 0`/duration filters or clamp values. Missing or
invalid MD5 and missing book metadata do not discard a valid native event: the
ratified native tuple, not file identity, owns raw evidence. Such rows establish
no cross-device/Reader/Resource association. Groups retain distinct book IDs
and cover only the current bounded projection. Minimal metadata preserves a
bounded valid native digest; title/author/display selection is deferred to the
optional provenance phase, so no metadata variant is selected as authoritative.
UTC event starts use native SQLite conversion with canonical codec validation,
not host timezone/os.date or another calendar implementation. Local date stays
unknown; no event-day, duration-policy or automation projection is fabricated.

The packaged collector takes an explicit codec/device/epoch/observation and has
no startup/menu/lifecycle caller. Existing tools codec is still the sole owner;
production composition may relocate it with its consumers, never copy it. No
state/outbox/ACK/network/production effect is enabled. Exact1cfd3ec passed262
native/fixture CI cases without skips; a full private-backup host comparison
accounted for5,717 valid events plus ten page-zero pending-review positions.
Gate3 is PASS; PhaseD is next. Actual installed0.0.2 Gate2 evidence remains
source-specific. This is not a new PW3 or release acceptance report.


2026-10-22: exact0.0.2 source5b22dd6 passed actual PW3 Gate2. The manual
read-only diagnostic preserved main DB bytes and logical counts/dates; the
separate normal-reading trial remained responsive and added one native event.
Other plugin sources and own settings remained unchanged. Empty WAL/SHM cache
lifecycle is recorded separately, not labeled identical files. See STATUS and
`docs/evidence/statistics-read-only-pw3-2026-10-22.json`. PhaseC bounded
deterministic extraction may proceed; outbox/ingestion and full release gates
remain open. No reading duration, canonical receipt or production effect is
inferred from this diagnostic.


The new exact47aa17f/profile7d3b6735 paired PW3/Android trial passed independent
receipt/canonical-byte/replay collection and verified normal completion,
revocation,package removal and full manual cleanup. The upstream G04 finite
transport exit audit and separate G03 audit establish Gate0A/0B/0C foundation
exit. PhaseA bootstrap/install-remove and PhaseB read-only Statistics/schema
probe are the next implementations; production ingestion is not enabled.
Both prior failed trials remain separately preserved, including the certificate
rejection and original-process LOW_MEMORY exit. No TLS/auth/receipt check or raw
wire schema was relaxed to obtain this new source-bound physical PASS.

Current physical preparation uses the same single-use bundle/launcher with
`paired_sequence.lua` and the existing approved-pairing consumer. Six requests
over three Dart-generated batches deliberately discard one receipt and verify
five per-event lookups. The actual normal Android receiver issues the document;
the checked host UID/source channel delivers it over USB. Host keys/OpenSSL
provisioning is removed. The collector independently reconstructs request and
event bindings and compares the complete exported canonical byte inventory.
This remains synthetic/unregistered; actual source-bound PW3/Android execution
passed the finite gate, while no Statistics/outbox/cursor or production feature is enabled.
The earlier untrusted-claim sequence remains a host reference, not the current
physical source. The successful bad10518/6cfdba8 native host join has a separate
exact-source report and does not silently certify this new orchestration.

The next G04 candidate `tools/reading_wire/paired_exchange.lua` composes the
existing pure codec and shared pinned TLS carrier only after exact private
pairing bytes have an independently approved out-of-band fingerprint. It binds
the normal Quartzo receiver role, endpoint/pin/token, scope/device/epoch and
finite window; opaque per-session/request receipts expose only completely
validated committed/duplicate positions. Raw parsers/delivery tables cannot
grant that acceptance. The canonical UTC parser is reused for pairing windows,
without a second date engine, crypto receipt protocol, ledger or retry loop.
This remains unregistered tooling. Source approval/import, actual normal-issuer
interoperability/native combined-path and fresh device proof remain required;
synthetic injected-SDK tests do not close G04 or permit G08 ingestion/cursors.

Current G04 preparation adds an opt-in exact-leaf DER SHA-256 gate to the
existing shared isolated LuaSec/LuaSocket carrier, before HTTP credentials are
sent. Its opaque process-local delivery capability binds bytes and connection
context only. It grants no canonical receiver role, durable event ACK, source
cursor or production registration. Native host acceptance is explicitly
required separately from injected-SDK tests and from new-source physical PW3
proof; see `tools/reading_wire/README.md` and current STATUS. Upstream G03 store
exit was separately audited PASS at Quartzo1db4c13b, using implementation
ad5986fa's four successful workflows and the original source-bound physical,
cloud conflict and canonical replay evidence. G04 and later gates stay open.
Exact ac1ebd2 passed Linux CI39525626234 with all four actual native TLS/pin/
timeout cases executed,93 wire and34 transport tests without skips. This
establishes host-carrier acceptance only; it does not satisfy the remaining
canonical pairing/receipt/lifecycle or new-source device requirements.

2026-10-20 checkpoint: actual exact-source PW3/Android finite canonical wire
diagnostic passed independent byte/report collection (three shards, three
synthetic events / 120 seconds; zero transport errors; credential revoked).
Owned device diagnostics and active private session material were removed.
See the current STATUS evidence. This supersedes earlier pending diagnostic
execution notes only; canonical ACK/cloud races/production lifecycle and later
gates remain open. No production activation follows this diagnostic.

> **Canonical execution specification**  
> **Repository:** `olalaurao/quartzo-koplugin`  
> **Target V1 device:** Kindle Paperwhite 3 / 7th gen (PW3), firmware 5.16.2.1.1, KUAL, KOReader v2026.07.1 (`kindlepw2`)
> **Product roadmap:** `PLAN.md`  
> **Progress ledger:** `STATUS.md`  
> **Implementation state:** Gate 0 and physical Phases A/B accepted; Phase C deterministic event extraction next
> **Last reconciled:** 2026-10-21 (historical planning pass: 2026-09-22)

This file is the implementation source of truth once implementation begins. If code and this specification disagree, either the code is wrong or this file must be deliberately updated in the same change, with the reason recorded in `STATUS.md`.

---

## 2026-10-16 reconciliation (takes precedence over the historical proposals below)

The user adopted the integrated Quartzo Reading Integration requirements. Upstream `olalaurao/aplicativo` PR65 merged as `e7a661d4ed6d572cdbf722f4e697fea461005b69` after its necessary checks, ratifying the active spec `docs/specs/reading-integration.md` and contracts `reading_identity`, `reading_evidence_status`, `reading_activity` including the versioned transport envelope. Companion adopted that exact upstream through its official lock process; authorized PR86 merged as `34d1244ec718cbd100f0f124ed76816dbde9008d`, with identical tested tree and green main CI. Its official exact-main Release Preflight passed. Separately authorized PR88 corrected pairing-mode preservation as 5ba99fd. Authorized PR89/90 subsequently merged as 5b69a6e/8c51589 with green main CIs and exact-main official Preflights. The verified final artifact is installed only in the existing paired Manual sandbox; actual byte repair, new create/update and restart/quiet-replay acceptance have narrow source-bound evidence. Complete cross-client cloud and canonical ACK acceptance remain open. Ratification is distinct from deployment, live interoperability and canonical ACK; Gate 0 is not PASS. STATUS records exact source/build/device proof boundaries.

- Physical documented baseline is KOReader **v2026.07.1**, **kindlepw2**, PW3/G090KB, firmware 5.16.2.1.1, functional jailbreak/KUAL, confirmed by the user and Reader migration guide. 2025.04 remains historical evidence. Confirm installed version before new tests; no firmware/KUAL/jailbreak updates.
- Actual official 5ba99fd Obsidian/Drive acceptance failed with three zero-byte synthetic uploads despite original hash properties. Authorized PR89 fixed actual renderer multipart/readback; authorized PR90 fixed reviewed adoption/pending feedback and existing canonical guards. Both merged, final official Preflight 39425583160 passed at 8c515898ab919a4b9e214ff84563cd36c6d4c243, and only the sandbox was upgraded. Actual full reconciliation preserved both good Reading originals; explicit Keep local repaired remote copies, and independent downloads verified exact bytes. New opaque Reading/binary creation, ordinary update, actual restart and zero-work replay also passed. Reviewed adoption also passed through the actual UI with an 83-byte fixture and six independently verified remote/local files; actual multi-client cloud races and source ACK remain separate; Gate 0A/0B/0C and production phases remain open. STATUS records sources and proof limits.
- Reader stable sequencing is satisfied by its stable v1.0.0/v1.2.0 tags and documented acceptance. This does not validate this plugin's transport or Statistics access.
- Reader-only remains external. Only proven Reader-origin KOReader reading can qualify for opt-in Resource promotion through the upstream canonical owner; ordinary USB/unmatched events never auto-create. Reader-only progress creates neither Resource nor minutes.
- One-way validated status evidence is now in scope: upstream may reconcile existing linked Resource status with explicit finished/abandoned or reliable progress, preserving manual/terminal intent. Bidirectional status/progress writeback, highlights and another Reader API client remain excluded.
- Ratified event ID is SHA-256 of compact UTF-8 JSON tuple `[domain,device_id,source_epoch,book_row_id,page,started_at_unix_seconds]`. MD5/title is not the native event key. Duration corrections for the same tuple are conflict, not new events. This supersedes the historical duration/MD5 example below. No production Lua codec has been implemented yet.
- Ratified canonical destination is immutable bounded vault JSONL shards under `sessions/reading_activity_v1/`, separate from Activity History. Existing vault/sync owners remain responsible. Android local persistence and actual-owner synthetic byte exchange have source-specific evidence; live Drive/Companion and canonical source acknowledgement still need proof.
- Gate 0A: PASS with ratified canonical domain/G03 ownership; 0B: PASS with actual PW3 HTTPS/auth/error/retry and normal-pairing receipt proof; 0C: PASS with ratified wire/native-ID/duplicate/error fixtures and verified finite receipt boundary. Next is PhaseA bootstrap/install-remove and PhaseB bounded read-only Statistics/schema. No ingestion,outbox/cursor,effect or release is enabled; staging never grants durable ACK or cursor advance. The G04 audit preserves the exact source limits and the separate G08/G16 requirements.
- The pure `tools/reading_wire/codec.lua` consumer now pins the ratified upstream revision and validates canonical request/response binding, bounded native entries and untrusted claims in Lua 5.1. It is not loaded by the production plugin or TLS diagnostic. The explicit `koreader_deps.lua` adapter targets existing dkjson/ffi-sha2 APIs, probes preserved object/array/null shape and known hashes, and fails without a fallback. Host LuaJIT tests execute the same contract suite through pinned real library source. The separate exact-source offline KUAL probe subsequently passed on the actual PW3 ARM runtime at 1af5a67 with installed native source hashes verified; the user confirmed manual execution. STATUS and the source-bound physical report record counts and narrow proof limits. Physical production performance/lifecycle, authenticated delivery and durable acknowledgement still require proof. No decoded claim grants ACK, durable receipt or source-cursor authority. This is Gate 0C compatibility work, not permission to start later production phases.
- A separate `quartzo-wire-probe` KUAL diagnostic may test those native providers/codec offline with synthetic fixtures before production gates close. Its exact-commit package and bounded installed-source/report checks must pass first; it can create only its fresh owned extension and diagnostic output, never replace an existing folder or load production Statistics/Reader/device/UI code. It reuses the tested single-use process deadline, performs no network/Wi-Fi operation and exposes no ACK/cursor authority. Host matching observations alone cannot prove physical execution; source-specific PW3 acceptance additionally requires the real mounted target and manual execution observation. See `tools/reading_wire/README.md` and STATUS.
- `tools/reading_wire/exchange.lua` prepares one explicit canonical-wire diagnostic attempt through the existing shared LuaSec carrier, with request/time checks before network and complete response/time binding afterward. `client.wire_transport` is fixed to the canonical receiver route and bounded header/body inputs under the existing dedicated-test-certificate/private-HTTPS policy. It creates no listener, production transport, automatic retry, credential/outbox owner or ACK/cursor grant. Host injected-HTTPS tests and a syntactically committed claim do not prove native TLS/canonical persistence. Existing physical reports stay source-specific; a combined source-to-canonical diagnostic still needs exact-source package, actual native receiver and new device execution evidence.
- The separate `sequence.lua` / `sequence_kindle.lua` diagnostic now owns a finite ten-attempt synthetic sequence through that same codec/carrier: rejected test CA, 401, 429 plus one-second pause, 503, deliberately discarded successful response, immutable retry and mixed/native-conflict neighbors. It captures exact input bytes before callbacks, requires fresh nonces and checks per-position claims/revisions against actual-Dart fixtures. Its source-pinned private bundle/collector excludes phone TLS private keys, preserves partial artifacts and compares exported canonical bytes and credential-revocation observations. Even matching reports retain false canonical ACK/physical-attestation fields; the deliberately discarded body is not a claimed random network failure. No combined physical execution or production source/outbox integration is inferred.
- Both diagnostics share the existing TLS client certificate-rejection classifier: only an absent HTTP status with explicit verification-failure text qualifies. The wrong-CA attempt sends an invalid bearer. Offline, generic TLS and certificate-file errors stop without a trust PASS; native error details are never copied into reports. New source requires its own CI/package/device proof.
- Proposed 30s promotion, session gaps and performance budgets remain unvalidated. No implicit Wi-Fi activation, SQLite writes, template edits or automatic effects.

# 0. Mission

Build `quartzo.koplugin`, a KOReader plugin that reads KOReader Reading Statistics safely and synchronizes normalized reading events into Quartzo through an explicitly approved cross-client Reading Activity contract.

The plugin must be:

- additive;
- optional;
- uninstallable without data loss;
- read-only with respect to KOReader Statistics;
- offline-safe;
- retry-safe;
- idempotent end-to-end;
- compatible first with the user's PW3 / KOReader v2026.07.1 (`kindlepw2`);
- architecturally subordinate to Quartzo's canonical persistence rules.

The plugin must not become:

- a replacement Statistics engine;
- a generic KOReader cloud backup;
- a second Quartzo database;
- a second Resource source of truth;
- a highlights/annotations sync owner;
- a hidden background daemon that changes Wi-Fi state unexpectedly.

---

# 1. Authority and startup procedure

Every implementation session must begin by:

1. pulling/inspecting the current `olalaurao/quartzo-koplugin` state;
2. reading `STATUS.md`;
3. reading this file;
4. reading `PLAN.md`;
5. checking the current `olalaurao/reader` V1 status;
6. checking current `olalaurao/aplicativo`:
   - `AGENT_BOOTSTRAP.md`;
   - `agents.md`;
   - applicable active specs;
   - current Resource model;
   - current Drive/vault architecture;
7. checking current `olalaurao/quartzo-obsidian-companion` contracts and upstream lock;
8. checking target KOReader version/source behavior;
9. checking the currently selected transport decision document after Gate 0;
10. recording current upstream SHAs in `STATUS.md`.

Do not rely on this planning snapshot when current upstream files disagree.

---

# 2. Sequencing constraint

Default sequencing:

`olalaurao/reader` stable V1/tag → start `quartzo-koplugin`.

Reason:

- both plugins target the same constrained device;
- the Reader project is still validating KOReader 2025.04 lifecycle/UI/network patterns;
- Quartzo can reuse proven local patterns after Reader V1 freezes;
- optional Reader provenance integration needs a stable mapping contract.

This sequencing may be changed only by an explicit user request.

---

# 3. Known target facts

## 3.1 Device

- Kindle Paperwhite 3 / 7th generation.
- Serial family: G090KB.
- Firmware: 5.16.2.1.1 (4097470002).
- Jailbreak/KUAL functional.
- KOReader target: v2026.07.1 (`kindlepw2`); current installation must be rechecked before physical tests.

## 3.2 KOReader Statistics DB

Verified against KOReader `v2025.04/plugins/statistics.koplugin/main.lua`.

Path:

`DataStorage:getSettingsDir() .. "/statistics.sqlite3"`

DB schema version:

`20221111`

Relevant `book` columns:

- `id`
- `title`
- `authors`
- `notes`
- `last_open`
- `highlights`
- `pages`
- `series`
- `language`
- `md5`
- `total_read_time`
- `total_read_pages`

Unique index:

`(title, authors, md5)`

Therefore **one MD5 may appear in multiple book rows** if metadata variants exist. Code must not assume one `book.id` per MD5.

Relevant raw event table:

`page_stat_data`

Columns:

- `id_book INTEGER`
- `page INTEGER`
- `start_time INTEGER`
- `duration INTEGER`
- `total_pages INTEGER`

Uniqueness:

`(id_book, page, start_time)`

Relevant derived view:

`page_stat`

It rescales historical page positions against current page counts. For ingestion we prefer raw `page_stat_data` because it preserves event-time `total_pages`.

KOReader Statistics:

- inserts only positive-duration events;
- flushes current volatile stats on document close;
- flushes on save-settings;
- flushes on suspend;
- may use WAL;
- owns all writes/migrations.

## 3.3 Quartzo architecture

As of the planning snapshot:

- vault content objects are canonical Markdown/frontmatter;
- feature-local parallel canonical stores are forbidden;
- a domain-specific canonical source is allowed only if explicitly documented;
- Resource already contains `readwiseBookId` persisted as `book_id`, but the exact identifier namespace must not be conflated with Reader API v3 IDs without proof;
- Companion is a second Quartzo client, not a remote control, and consumes vendored language-neutral contracts.

Reading Activity must therefore be added as an explicit upstream domain/contract before production ingestion.

---

# 4. V1 requirements

## 4.1 Required

- plugin bootstrap/menu/config/status;
- read-only Statistics access;
- deterministic raw event extraction;
- persistent random device ID;
- deterministic event IDs;
- incremental sync;
- durable pending state;
- idempotent remote/canonical ingestion;
- full-history import;
- cancellation/resume;
- multi-device-safe identity;
- safe Resource association;
- unmatched document preservation;
- manual sync;
- optional conservative auto-sync after device proof;
- diagnostics;
- protocol versioning;
- secret redaction;
- physical-device gates;
- CI/package tests.

## 4.2 Explicitly not V1

- progress pull/push;
- remote page jumps;
- highlights;
- notes;
- ratings;
- status writeback;
- document download;
- Quartzo browsing UI on Kindle;
- full Reading dashboard on Kindle;
- auto-create every Resource;
- direct Obsidian sync;
- arbitrary cloud backup.

---

# 5. Package identity

Tentative plugin directory:

`quartzo.koplugin`

Tentative plugin name:

`Quartzo`

Tentative settings:

- `settings/quartzo.lua` — user configuration;
- `settings/quartzo_sync_state.lua` — resumable transport state.

Do not store secrets in the same structure if a safer target-supported secret mechanism is available and proven. If KOReader lacks secure storage, document the local-file threat model clearly and minimize secret scope.

---

# 6. Module boundaries

Target logical boundaries:

## 6.1 `stats/*`

Responsible only for:

- DB path;
- schema validation;
- read-only connection;
- bounded queries;
- source row normalization;
- raw event extraction.

Must not:

- make HTTP calls;
- modify sync state;
- know UI widgets;
- write DB.

## 6.2 `storage/*`

Responsible only for:

- settings/state schema;
- migrations;
- atomic persistence;
- corruption detection/recovery.

Must not:

- query Statistics DB;
- call Quartzo API directly.

## 6.3 `sync/*`

Responsible for:

- deciding what work exists;
- batching;
- ack-gated cursor advancement;
- durable outbox;
- backfill coordinator;
- serializing/coalescing jobs.

Must not:

- directly render UI;
- silently change network state.

## 6.4 `transport/*`

Responsible for:

- selected protocol;
- auth;
- HTTP/request classification;
- timeouts;
- serialization;
- response validation.

Must not:

- invent analytics;
- own Resource matching;
- mutate Statistics.

## 6.5 `integrations/*`

Optional enrichment adapters, especially Readwise Reader.

Must:

- be absent-safe;
- be read-only relative to the other plugin;
- use documented stable mapping only.

## 6.6 `ui/*`

Projection/controller glue only.

UI must not:

- own queue truth;
- compute event IDs independently;
- write raw state structures ad hoc;
- parse SQLite;
- implement a parallel retry scheduler.

---

# 7. SQLite access contract

## 7.1 Open mode

Prefer:

~~~lua
SQ3.open(path, "ro")
~~~

when supported by pinned KOReader's sqlite wrapper.

If target behavior differs, Gate 2 must experimentally prove the safest read-only equivalent.

The Phase B diagnostic uses that exact native mode, a short `BEGIN DEFERRED`
read snapshot and unconditional connection closure. It validates schema20221111
columns and required index/foreign-key shapes, while allowing the observed
nonunique SimpleUI MD5 index. It never migrates or repairs Statistics.

To keep diagnostic work bounded on PW3, each count inspects at most100,001
rows. Counts above100,000 are explicitly reported as `100000+`, not an exact
total; first/last timestamps use the validated native start-time index. This
bounded summary is not the Phase C collector or full-history backfill. Version
0.0.2 performs this work only through the manual Reading Statistics menu action,
never on startup, page turns, close or suspend. Native fixture CI and actual
PW3 Gate2 remain required independently of the accepted bootstrap Gate1.

## 7.2 Busy handling

Use a bounded busy timeout, initially around 1000 ms unless device evidence suggests otherwise.

A busy DB is a transient read failure, not permission to write or copy/replace the DB.

## 7.3 Connection lifetime

Normal sync:

- open;
- execute bounded query set;
- close.

Full backfill may hold a reusable read-only session if device testing shows it is safe and materially reduces overhead.

Never hold a write transaction.

## 7.4 Transactions

The Quartzo plugin must not start a write transaction against Statistics.

Read transaction behavior must remain minimal. Avoid long snapshots that block checkpointing on constrained filesystems.

## 7.5 Unknown schema

Read:

`PRAGMA user_version;`

Supported initially:

`20221111`

If unknown:

- show clear unsupported-schema diagnostic;
- do not guess columns;
- do not sync;
- do not modify DB;
- preserve local pending outbox already collected previously.

Future versions may add explicit schema adapters.

---

# 8. Statistics source queries

Final SQL belongs in implementation, but the following shapes are canonical intent.

## 8.1 Book enumeration

Use keyset pagination, not OFFSET over large libraries.

Concept:

~~~sql
SELECT id, md5, title, authors, last_open, pages
FROM book
WHERE id > ?
ORDER BY id
LIMIT ?;
~~~

Rows with missing MD5:

- may be reported diagnostically;
- are not safe for automatic cross-device identity;
- may be excluded from normal event sync until an alternate identity is proven.

## 8.2 Group by MD5

Because `book` is unique on title+authors+md5, collect all row IDs sharing an MD5.

Logical grouped identity:

~~~text
md5
 ├─ id_book 12
 └─ id_book 97
~~~

Events from all matching row IDs belong to the same local file-digest identity unless an implementation spike proves a counterexample.

Metadata conflicts:

- choose the latest-open metadata only for display/suggestion;
- flag `metadata_ambiguous=true`;
- never let metadata variant change event identity.

## 8.3 Raw events

Preferred query source:

`page_stat_data`

Concept:

~~~sql
SELECT page, start_time, duration, total_pages
FROM page_stat_data
WHERE id_book IN (...)
  AND start_time > ?
  AND total_pages > 0
ORDER BY start_time, page
LIMIT ?;
~~~

Because multiple events can share the same second, watermark logic must intentionally overlap or use a stronger cursor.

---

# 9. Watermark/cursor contract

A timestamp-only strict `start_time > watermark` can lose rows when a batch boundary splits multiple events with the same timestamp.

Therefore V1 must use one of these proven patterns:

## Preferred simple pattern: overlap + deterministic dedupe

- query events after a watermark;
- when a full batch may end inside a timestamp group, move local next watermark back by one second;
- resend the overlap;
- rely on deterministic `event_id` and canonical dedupe.

Advance watermark only after valid remote ack.

Alternative stronger cursor:

- tuple cursor over stable source fields if validated;
- e.g. start_time + book digest + page + another deterministic discriminator.

Do not invent a complex cursor until fixture/device evidence requires it.

---

# 10. Event normalization

Tentative protocol object:

~~~json
{
  "schema_version": 1,
  "event_id": "qre_<digest>",
  "source": "koreader",
  "device_id": "qrd_<opaque>",
  "started_at_epoch": 1760000000,
  "duration_seconds": 42,
  "page": 183,
  "total_pages": 412,
  "document": {
    "koreader_md5": "hex",
    "title": "optional display metadata",
    "authors": "optional display metadata",
    "reader_document_id": null,
    "readwise_book_id": null,
    "quartzo_resource_id": null
  }
}
~~~

Exact field names are not final until Gate 0 upstream contract.

## 10.1 Required invariants

- integer Unix epoch seconds;
- positive duration;
- non-negative/positive page semantics matching KOReader source;
- positive `total_pages`;
- stable digest;
- versioned schema;
- no token/path/body content.

## 10.2 Duration safety

Reject/quarantine impossible values, not silently trust arbitrary corrupted integers.

Suggested hard safety ceiling for source normalization may be 24 hours/event, but the actual contract must be approved upstream.

Preserve raw source duration separately if Quartzo derivation clamps differently.

---

# 11. Event ID contract

Requirements:

- deterministic;
- same source event + same device → same event ID;
- retry does not produce new ID;
- title/author changes do not produce new ID;
- different device IDs do not collide;
- different document digests do not collide;
- does not contain secret/private cleartext.

Candidate canonical input:

~~~text
quartzo-reading-event-v1
  device_id
  koreader_md5
  start_time
  page
  duration
  total_pages
~~~

Hash algorithm must be available reliably in target KOReader and mirrored in Dart/TypeScript if they need to verify vectors.

Prefer a cryptographic digest already available in KOReader's Lua runtime.

The exact encoding and hash are Gate 0C contract decisions with golden vectors.

---

# 12. Device identity

Generate a random opaque installation ID once.

Requirements:

- not serial number;
- not MAC;
- not username;
- not filesystem path;
- stable across plugin updates;
- changes only on explicit reset/state loss;
- reset causes old events to be re-identified as another device, so UI must warn before destructive reset once V1 ships.

Format example:

`qrd_<random>`

Generation must use target-available entropy. If strong random bytes are not available, investigate a robust combination rather than inventing fake UUID security.

Device ID is identity, not authentication.

---

# 13. Document identity

## 13.1 Primary local identity

KOReader `partial_md5_checksum` / Statistics `book.md5`.

Do not recompute entire-file hashes during every sync if KOReader already exposes a stable digest.

## 13.2 Metadata

Title/author are descriptive only.

## 13.3 Quartzo association

Canonical association should live upstream, not only in plugin state.

Plugin may cache:

`koreader_md5 → quartzo_resource_id`

but this cache is a projection/optimization. Deleting it must not destroy the canonical association.

## 13.4 Readwise Reader enrichment

Only if `olalaurao/reader` exposes a stable contract after V1.

Potential provenance:

- Reader v3 document ID;
- source URL;
- category.

Never equate Reader v3 document ID with Quartzo's existing `book_id` / Readwise v2-style identity without explicit proof.

If needed, upstream Resource may gain a distinct field such as:

`readwise_reader_document_id`

The exact schema belongs in Quartzo active specs/models and must roundtrip through Markdown and Companion fixtures.

---

# 14. Resource matching policy

Matching runs in Quartzo canonical code.

Confidence levels:

## Exact auto-match

Allowed only when:

- persisted Quartzo Resource ID;
- exact known external namespace ID;
- prior explicit digest association;
- another exact identity contract says so.

## Suggested match only

- title + author;
- source URL;
- filename-like title;
- fuzzy metadata.

Suggested matches require user confirmation.

## No match

Reading remains valid and visible as an unmatched document.

Never drop reading events because a Resource does not exist.

---

# 15. Canonical Reading Activity upstream contract

Gate 0A requires an active spec in `olalaurao/aplicativo`, suggested:

`docs/specs/reading-activity.md`

It must document:

- source of truth;
- persisted format/location;
- schema version;
- event identity;
- device identity;
- dedupe;
- Resource association;
- unmatched documents;
- session derivation;
- timezone/local day;
- retention;
- deletion/reset semantics;
- cross-client contract/vector ownership;
- Companion consumption;
- privacy.

If the source is not vault Markdown, `agents.md` must explicitly add Reading Activity to the Domain Sources Of Truth table.

If it is vault-backed, the spec must define the canonical writer/reader and how high-churn event data avoids pathological conflict/performance behavior.

---

# 16. Canonical persistence candidate constraints

This spec intentionally does not choose a final sink before Gate 0, but any approved sink must:

- be reconstructible after plugin-local state loss;
- dedupe event IDs;
- accept multiple devices;
- preserve raw event evidence;
- avoid one giant frequently edited shared file;
- handle years of history;
- avoid forcing the generic ContentObject parser to treat every event as a normal object;
- be compatible with current Drive sync scope/conflict rules;
- have retention/backup behavior;
- be accessible to app and Companion through documented owners.

Possible safe shapes include immutable/bounded shards, but exact paths/formats are upstream decisions.

---

# 17. Transport protocol

Exact endpoint is Gate 0B/C dependent.

Preferred conceptual API if HTTPS ingress is selected:

## 17.1 Capabilities

~~~http
GET /v1/capabilities
Authorization: Bearer <token>
~~~

Response:

- protocol versions;
- max batch;
- max body;
- supported auth;
- server/canonical capabilities.

## 17.2 Batch upload

~~~http
POST /v1/reading/events
Authorization: Bearer <token>
Content-Type: application/json
~~~

Conceptual body:

~~~json
{
  "protocol_version": 1,
  "device": {
    "device_id": "qrd_...",
    "client": "quartzo-koplugin",
    "client_version": "0.x"
  },
  "events": []
}
~~~

Conceptual response:

~~~json
{
  "protocol_version": 1,
  "accepted": ["qre_..."],
  "duplicates": ["qre_..."],
  "rejected": [
    {"event_id":"qre_...","code":"invalid_field"}
  ]
}
~~~

Ack is per logical event or per fully atomic batch. Do not advance a local watermark if the response is ambiguous.

## 17.3 Idempotency

Canonical sink must enforce unique `event_id`.

Duplicate upload is success/no-op, not an error.

---

# 18. HTTP/network contract

Use KOReader-proven HTTP patterns from the Reader project after its V1 is stable.

Requirements:

- HTTPS by default;
- certificate validation;
- finite connect timeout;
- finite read timeout;
- bounded body;
- bounded redirects;
- redact Authorization;
- JSON schema validation;
- cancellation-aware manual long operations where appropriate.

## 18.1 Status handling

### 2xx

Validate body before ack.

### 400

Non-retryable protocol/data error. Quarantine/retain event and show diagnostics.

### 401

Auth invalid. Stop automatic retries until configuration changes.

### 403

Permission/policy error. Stop automatic retries unless response explicitly classifies temporary quota.

### 408

Retryable within budget.

### 409

Only retry/handle according to explicit protocol semantics.

### 413

Batch too large: split if protocol permits; otherwise fail visibly.

### 429

Honor numeric Retry-After when present; bounded fallback otherwise.

### 5xx

Retryable within bounded budget; retain outbox.

### network unavailable

No loss; retain outbox.

---

# 19. NetworkMgr rules

Manual Sync:

- may call KOReader's normal `NetworkMgr` path to establish network;
- may show expected user prompt.

Automatic/background:

- must first check existing network;
- must not nag on every close/page;
- must not force Wi-Fi on by default.

Suspend:

- follow target KOReader behavior;
- if selected transport requires network and KOReader must disable Wi-Fi before suspend, do not leave the device in an unsafe power state.

Physical gate required.

---

# 20. Local state

Tentative versioned state:

~~~lua
return {
    schema_version = 1,
    device_id = "qrd_...",
    protocol_version = 1,

    documents = {
        -- digest keyed state, bounded metadata
    },

    pending = {
        -- durable unsent/partially-acked work
    },

    global = {
        last_success_at = 0,
        last_error_code = nil,
        backfill_checkpoint = nil,
    },
}
~~~

Do not store arbitrary entire history.

## 20.1 Atomic persistence

Prefer KOReader/LuaSettings atomic flush if proven on target.

Otherwise:

1. serialize to temp file;
2. flush;
3. fsync if available/proven;
4. replace current atomically;
5. retain recoverable backup where useful.

State corruption must fail safe.

---

# 21. Outbox model

Two acceptable designs:

## A. event outbox

Persist normalized events until ack.

Pros:
- simple recovery.

Cons:
- can grow during long offline periods.

## B. cursor/checkpoint outbox

Persist source ranges/checkpoints and regenerate events deterministically from Statistics DB.

Pros:
- smaller state.

Cons:
- DB history may be deleted/changed before upload;
- more complex recovery.

V1 should prefer correctness. A hybrid is likely best:

- persist small pending batches/events once selected for send;
- keep ack watermarks for historical source;
- prune pending only after ack.

If source history can disappear due to user cleanup, selected pending events must survive independently until delivered.

---

# 22. Ack-gated advancement

Never mark source data synced merely because an HTTP request was sent.

Advance state only after:

- transport success;
- response parse success;
- schema/protocol validation;
- canonical sink acknowledges event(s).

Crash case:

`remote accepted → device crashed before local ack`

Recovery must resend same IDs and receive duplicates/no-ops.

That is the central idempotency requirement.

---

# 23. Backfill

Command:

`Import existing reading history`

Requirements:

- explicit user action;
- preflight event/book counts;
- visible progress;
- cancellation;
- resumability;
- bounded memory;
- bounded batch;
- checkpoint;
- safe duplicate re-run.

## 23.1 Pagination

Books: keyset by `book.id`.

Events: watermark/batch by grouped MD5/book IDs.

Avoid OFFSET over large data if possible.

## 23.2 Progress

Display meaningful phases:

- scanning books;
- collecting events;
- sending batch X;
- awaiting retry;
- finalizing.

Do not fake percent if total is unknown.

## 23.3 Cancellation

Cancellation stops after the current safe query/request boundary.

Never leave state claiming ack that did not occur.

---

# 24. Current-document flush problem

Manual sync while a document is open may have volatile Statistics events not yet written to SQLite.

Known native flush points include:

- close document;
- save settings;
- suspend.

Implementation must not call private internals blindly.

Phase B/C spike must identify a supported/safe way to ensure current Statistics data is flushed before an explicit manual sync, for example through an existing KOReader event path.

Acceptable fallback if no safe flush hook exists:

- manual sync clearly reports that it includes Statistics through the last native flush;
- close/suspend auto-sync captures the remaining activity.

Do not patch the stock Statistics plugin solely to force flush unless an upstream-compatible mechanism is proven and documented.

---

# 25. Sync coordinator

One canonical coordinator per plugin runtime.

Properties:

- one active sync job;
- pending jobs coalesced by family;
- manual jobs can outrank passive jobs;
- no concurrent outbox mutation;
- finalizer always releases busy state;
- status is read-only projection for UI.

Families may include:

- manual_incremental;
- lifecycle_incremental;
- backfill;
- connectivity_retry.

Do not create separate timers/controllers each mutating state.

---

# 26. Auto-sync

Not implemented until manual sync/backfill pass.

Potential triggers:

- close document;
- suspend;
- periodic pages;
- startup/resume.

Default for first release should be conservative.

Suggested settings:

- Auto sync: off by default during beta.
- Sync on close: optional.
- Sync on suspend: optional.
- Periodic page count: 0/disabled by default.

A later stable release can change defaults only after target-device evidence.

---

# 27. UI contract

Tools → Quartzo.

Tentative menu:

~~~text
Quartzo
├── Sync now
├── Import existing reading history
├── Status
│   ├── Last sync
│   ├── Pending events
│   ├── Device ID (short)
│   ├── Protocol version
│   └── Last error
├── Auto sync
├── Connection…
├── Document associations…
└── Diagnostics…
~~~

No dashboard-heavy Kindle UI in V1.

## 27.1 Interactive operations

Any operation that can take noticeable time on PW3 must:

- show visible progress/status;
- remain cancellable where safe;
- not freeze KOReader;
- use proven KOReader 2025.04 `Trapper` / subprocess patterns when applicable.

The Reader project already proved that `dismissableRunInSubprocess` without outer `Trapper:wrap()` falls back to blocking execution on 2025.04. Reuse the proven pattern, do not regress it.

---

# 28. Diagnostics

Safe diagnostics may expose:

- plugin version;
- KOReader version;
- Statistics schema;
- Statistics DB readable yes/no;
- book row count;
- event count;
- pending count;
- last success;
- last error code;
- transport protocol/capability version;
- state schema;
- short device ID;
- whether Readwise Reader adapter is present.

Never expose:

- auth token;
- Authorization header;
- document content;
- note/highlight text;
- full private local path by default.

Provide copyable sanitized diagnostics if KOReader UI supports it safely.

---

# 29. Readwise Reader integration

Optional adapter only.

Preconditions:

- `olalaurao/reader` V1 stable;
- mapping format documented;
- license/origin reviewed;
- no circular dependency.

Preferred integration:

`koreader_md5/local file → Reader v3 document ID`

The adapter may read stable state exported by Reader plugin.

It must not:

- call Reader API;
- archive documents;
- sync highlights;
- mutate Reader state;
- assume `readwiseBookId` equivalence.

If no adapter is available, Quartzo stats still sync normally.

---

# 30. Upstream Quartzo implementation

A production V1 is incomplete until the app repo has canonical owners.

Tentative components:

- `ReadingActivityEvent` pure model;
- `ReadingActivityCodec`;
- `ReadingActivityRepository`;
- `ReadingActivityIngestionService`;
- `ReadingDocumentIdentityService`;
- `ReadingActivityAggregator`;
- Resource association mutation owner;
- unmatched-document projection;
- contract vectors;
- tests.

Names are illustrative. Reuse existing owners if current architecture already has equivalents when implementation starts.

## 30.1 No UI-owned logic

Quartzo UI must not:

- parse raw transport JSON itself;
- implement duplicate logic;
- infer Resource identity ad hoc;
- compute separate session rules.

---

# 31. Companion integration

Once upstream contract is accepted:

- vendor contract through Companion's existing upstream lock workflow;
- add TypeScript codec/reader only if Companion needs direct Reading Activity access;
- use same golden vectors;
- do not create separate event/session semantics;
- expose read-only UI first;
- write Markdown projection only through canonical vault writers if product explicitly requires it.

Do not add KOReader-specific sync logic to Companion unless it is part of the approved ingestion architecture.

---

# 32. Session derivation

Raw events remain primary.

If Quartzo creates sessions, upstream spec must define:

- maximum inactivity gap;
- whether adjacent pages merge;
- cross-midnight split;
- local timezone;
- simultaneous multi-device events;
- maximum session duration;
- whether a document switch splits session;
- how zero/invalid durations are handled.

Do not make the Lua plugin derive authoritative sessions unless required for transport efficiency and mirrored exactly by contract.

---

# 33. Timezone semantics

KOReader stores Unix timestamps but Reading Activity UX is day-based.

Contract must preserve enough to answer:

- what local day did reading occur on?
- what happens after timezone travel?
- what happens if historical events are imported later?

Candidate event fields:

- UTC epoch;
- source local date;
- source UTC offset minutes when available/reliable.

If target Lua cannot reliably reconstruct historical offset, store UTC epoch and let Quartzo define import-time/local-zone semantics explicitly rather than fabricating accuracy.

---

# 34. Reading-time semantics

KOReader has both raw and capped calculations.

Quartzo must name its metrics precisely.

Suggested domain terms:

- `recorded_duration_seconds` — raw source event duration;
- `active_reading_seconds` — Quartzo-derived/clamped;
- `koreader_capped_reading_seconds` — optional compatibility metric.

Do not label a raw uncapped sum as "KOReader reading time" if it differs from what KOReader Statistics UI would show.

Golden tests should cover repeated visits to the same page.

---

# 35. Page/progress semantics

Because reflow changes page count:

- preserve raw `page`;
- preserve event-time `total_pages`;
- derive event progress fraction from those two if useful;
- do not compare raw page numbers across different layouts as exact positions;
- do not use this plugin for cross-device reading-position sync in V1.

---

# 36. Multi-device semantics

Every event includes `device_id`.

Deduplication key is `event_id`, not timestamp alone.

If the same physical source DB is cloned to another device and generates a new device ID, historical events could appear duplicated across device identities.

V1 must document this edge case.

Potential future import fingerprinting may detect clone/backups, but do not silently collapse devices without proof.

---

# 37. Deletion semantics

V1 is append-oriented.

If the user deletes a KOReader Statistics event/book later:

- do not automatically delete canonical Quartzo reading history;
- treat Quartzo history as imported evidence.

Remote deletion/forget controls are a separate explicit feature.

A future "Forget reading history" must have:

- scoped UI;
- canonical deletion owner;
- device/document/date filters;
- confirmation;
- audit-safe behavior.

---

# 38. Reset semantics

## Reset plugin sync state

Should:

- preserve canonical Quartzo data;
- warn that a full re-upload may occur;
- rely on canonical dedupe.

## Reset device identity

More dangerous.

Should:

- warn that past events may appear as a second device if re-imported;
- require explicit confirmation.

## Remove token

Should stop future sync but preserve local pending state unless user separately discards it.

---

# 39. Performance requirements

PW3 constraints:

- never load all history at once;
- bounded query results;
- bounded JSON body;
- avoid repeated full DB scans;
- avoid O(n²) queue operations;
- yield during backfill;
- no expensive hash of whole files per ordinary sync if KOReader digest exists;
- lifecycle jobs should be short;
- UI thread must not block on long network/database traversal.

Record empirical timings in `STATUS.md`.

---

# 40. Suggested batch limits

Initial conservative defaults for testing, not contract:

- book enumeration: 100–250 rows/query;
- event upload: 100–500 events/batch;
- request body hard cap: measure on PW3, likely well under a few MB;
- retry budget: small and bounded.

Tune from evidence.

Do not increase batch size merely to reduce request count if memory/UI latency worsens.

---

# 41. Security contract

## 41.1 Authentication

Selected transport must use a scoped revocable credential.

Do not use:

- Google account password;
- Readwise token;
- GitHub personal token;
- Kindle serial.

## 41.2 Secret storage

If plaintext local config is unavoidable on KOReader:

- document it;
- restrict secret scope;
- mask UI;
- never log;
- support rotate/revoke.

## 41.3 Transport

No insecure HTTP for production unless an explicit local-only development mode is clearly separated and disabled by default.

---

# 42. Logging

Levels:

- INFO: phase/status counts.
- WARN: transient/recoverable errors.
- ERROR: blocked sync/protocol/data failure.
- DEBUG: sanitized technical details.

Redaction helper should scrub:

- bearer token;
- endpoint query secrets;
- Authorization;
- signed URLs;
- user content.

Tests must assert redaction.

---

# 43. Licensing

Research references have different licenses.

Before copying code:

- inspect license;
- record source;
- preserve required notices;
- ensure this repository license is compatible.

BookOrbit: AGPL-3.0.

`olalaurao/reader`: AGPL-3.0.

KOReader: check exact project licensing/headers for copied modules before reuse.

Preferred approach:

- reuse architecture/patterns;
- write project-specific implementation;
- copy exact code only deliberately with attribution/license compliance.

Add `LICENSE` and `NOTICE.md` before first distributable release.

---

# 44. Testing matrix

## 44.1 Unit

- config defaults;
- state migration;
- event normalization;
- event ID;
- document grouping;
- cursor overlap;
- batch split;
- ack apply;
- retry classification;
- coordinator serialization;
- secret redaction;
- association policy.

## 44.2 SQLite fixture

Minimum fixtures:

1. empty supported schema;
2. one book / one event;
3. one book / same-page repeated events;
4. same second multiple events;
5. same MD5, multiple `book.id`;
6. metadata change;
7. layout/reflow total_pages change;
8. missing MD5;
9. invalid total_pages;
10. absurd duration;
11. thousands of events;
12. unsupported schema.

## 44.3 Protocol

- duplicate event accepted/no-op;
- partial response;
- invalid response body;
- version mismatch;
- auth error;
- rate limit;
- server error;
- timeout;
- request cancellation.

## 44.4 Crash recovery

- crash before send;
- crash during send;
- server accepted but no local ack;
- state temp written but not promoted;
- state backup recovery;
- full state deletion/reupload.

## 44.5 Integration

- one event Kindle→Quartzo;
- same event twice;
- offline then online;
- two devices;
- unmatched doc;
- exact Resource match;
- ambiguous same-title docs;
- Readwise article provenance.

---

# 45. Physical gate scripts

Create `docs/DEVICE_TESTS.md` during implementation.

Each gate script must specify:

- build/version;
- commit;
- files to install;
- preconditions;
- exact menu action;
- expected UI;
- expected filesystem/database state;
- failure evidence to collect;
- rollback.

Do not ask the user to test broad vague behavior.

---

# 46. Gate definitions

## Gate 0A — Quartzo canonical contract

Evidence:

- active upstream spec;
- agents/source-of-truth update if required;
- vectors/codec plan;
- no parallel owner.

## Gate 0B — transport spike

Evidence on PW3:

- authenticated ping/test payload;
- TLS works;
- timeout works;
- secret absent from logs;
- network returns to expected state.

## Gate 0C — protocol fixture

Evidence:

- request/response versioned;
- deterministic event ID vector;
- duplicate semantics;
- error classification.

## Gate 1 — bootstrap

Evidence:

- plugin menu;
- clean startup/removal;
- no data mutation.

## Gate 2 — DB read

Evidence:

- supported schema;
- plausible counts;
- read-only proof;
- no lock/freeze.

## Gate 3 — extraction

Evidence:

- deterministic fixture replay;
- overlap safety;
- no title identity.

## Gate 4 — state/outbox

Evidence:

- restart/crash tests;
- ack gating;
- atomic state.

## Gate 5 — network ingestion

Evidence:

- retry/error matrix;
- duplicate no-op.

## Gate 6 — E2E

Evidence:

- one actual reading event visible through Quartzo canonical owner and Companion.

## Gate 7 — association

Evidence:

- collision suite;
- ambiguous case requires user.

## Gate 8 — backfill

Evidence:

- actual history complete/cancellable/resumable;
- second import no duplicate totals.

## Gate 9 — lifecycle

Evidence:

- close/suspend/offline/online tests;
- no freeze;
- no prompt storm;
- no duplicate jobs.

No later gate may be declared complete while a blocking earlier gate remains open.

---

# 47. CI

Before release, CI should include:

- Lua syntax;
- unit tests;
- SQLite fixture tests;
- protocol/vector tests;
- package layout;
- secret scan;
- shell script checks;
- generated artifact smoke test.

If upstream Quartzo/Companion code changes as part of the same milestone, their own canonical gates remain mandatory.

---

# 48. Versioning

Plugin semantic versioning:

- `0.0.x` spikes/bootstrap;
- `0.1.x` first target-device usable beta;
- `1.0.0` only after all V1 release criteria.

Protocol version is independent of plugin version.

State schema version is independent of protocol version.

Keep all three explicit.

---

# 49. Status ledger requirements

After every meaningful session, `STATUS.md` must record:

- current milestone/gate;
- branch;
- commit;
- upstream SHAs;
- files changed;
- tests run;
- CI run IDs;
- physical-device evidence;
- bugs/root cause;
- unresolved decisions;
- exact next action.

Never leave the repo in a state where continuation depends on chat memory.

---

# 50. Implementation starting checklist

When user says to begin implementation:

- [ ] Pull repo.
- [ ] Read bootstrap/spec/plan/status.
- [ ] Verify Reader V1 sequencing.
- [ ] Pin current upstream SHAs.
- [ ] Re-read Quartzo agents/source-of-truth.
- [ ] Re-read Companion contracts/upstream lock.
- [ ] Re-read KOReader target Statistics source.
- [ ] Re-evaluate BookOrbit/KoInsight current patterns if still useful.
- [ ] Open Gate 0 decision branch.
- [ ] Write/update upstream Reading Activity spec before production code.
- [ ] Implement smallest target-device transport spike.
- [ ] Stop if transport/canonical owner is unresolved.

---

# 51. Planning references

Primary technical references reviewed during planning:

- KOReader v2025.04:
  - `plugins/statistics.koplugin/main.lua`
  - `plugins/kosync.koplugin/main.lua`
  - `plugins/exporter.koplugin/main.lua`
- BookOrbit:
  - KOReader plugin README
  - `bookorbit_stats_reader.lua`
  - `bookorbit_state.lua`
  - `bookorbit_queue.lua`
  - `bookorbit_sync_coordinator.lua`
- KoInsight:
  - reading statistics sync architecture/README
- Syncery:
  - Statistics/Vocabulary orchestration approach
- `olalaurao/reader`:
  - `PLAN.md`
  - `IMPLEMENTATION_SPEC.md`
  - `STATUS.md`
- Quartzo:
  - `AGENT_BOOTSTRAP.md`
  - `agents.md`
  - Resource model
  - Companion integration contracts
- Quartzo Companion:
  - `AGENT_BOOTSTRAP.md`
  - `agents.md`
  - V1 capability matrix
  - upstream lock

These references inform the plan but do not override current upstream canonical docs at implementation time.


## 2026-10-24 Phase D source review and recovery binding addendum (candidate0.0.8)

The existing Statistics and outbox owners implement explicit setup only. Plugin
startup remains inert and collection, historical import and network synchronization
are not registered. This addendum does not close Gate4 or authorize later phases.

Statistics schema20221111 has no intrinsic database-generation UUID. An opaque,
one-use review is minted from a validated short native read-only snapshot and
rechecked on confirmation. Counts, titles, dates, MD5, file hashes and caller
booleans never mint a review or prove a database generation. Fresh setup requires
an absent primary and no discoverable recovery copies; otherwise recover/review
existing state. It creates independent OS-random qrd_/qse_ values through the
same SQLite owner. Existing history is not imported by setup.

Fresh explicitly enrolled state uses private outbox schema2, adding one source
row to the unchanged schema1 tables. It stores bounded native file device/inode,
book AUTOINCREMENT sequence, two indexed immutable native-event witnesses and
the observed historical time boundary. These are conservative continuity guards,
not whole-database equality, an intrinsic generation identity or a canonical ACK.
File identity is checked before/after the read snapshot, native witnesses must
remain exact, and the book sequence cannot regress. Unknown/changed sources
preserve queued facts, review, identities and recovery copies. Existing schema1
state and recovery copies remain readable/restorable without automatic migration
or reassignment; they require separate source review before any production use.

Native file identity must not be assumed stable across filesystem maintenance or
reboots. Explicit reconfirmation of the SAME history can refresh only device/inode
when retained witnesses and sequence still match. This requires another one-use
review bound to that exact queue identity, confirmed by the user. It preserves
qrd_,qse_,all selected bytes,the original witnesses and original history boundary.
A missing witness, regressed sequence, initial empty-history enrollment or
indeterminate source fails closed. This cannot silently adopt a reset/different
history or mint a replacement epoch. Indistinguishable clones cannot be certified
by these guards; a full reset/new-generation/backfill reconciliation workflow
and real source/provenance evidence remain required before production collection.
The stored history boundary grants neither permission to skip older native facts
nor permission to reupload them under a new namespace. No watermark is advanced.

SQLite backup/restore copies the complete recognized schema version, including
source guards. Manual recovery review now binds the exact selected event lines
using the existing codec's line digests, all retained review descriptors and source
metadata, in deterministic bounded order. Identity/count equality alone is not
sufficient. Recheck both before destination creation and within the copy transaction;
preserve existing files and partial unregistered targets on failure. This local
review key is transient and is never a wire receipt or remote acceptance signal.

Host/native fixtures must cover explicit consent, stale/forged/foreign reviews,
new state and legacy recovery, native INTEGER cdata, reset/replacement and commit
failures, preserved pending data and fresh-process reopen. Actual LFS, entropy and
SQLite must run in native CI. Remaining PW3 proof is grouped for the changed0.0.8
setup/populated recovery/reconfirmation paths; prior exact0.0.7 empty UI, normal
reading/restart and paired outbox proofs remain valid only for their recorded
sources. No new device session is started while the user is unavailable.


### Owner-bound source preview (same candidate block)

The existing collector loop also runs inside Statistics.with_source_snapshot.
The outbox owner's preview_source supplies its own persisted device/epoch and
source guards, returning a bounded read-only dry run. It neither stages history
nor advances state/ACK. Legacy/unreviewed or changed sources and foreign transient
continuations fail closed before scanning raw events. This avoids a separate
extractor or a guard check detached from the actual source snapshot. No producer,
UI collection action or lifecycle registration is enabled by this API.


## 2026-10-24 Phase D reviewed collection, ACK frontier and empty reset (candidate0.0.9)

Fresh explicit enrollment now creates private schema3. Existing schema1/2 CREATE
bytes and recognized recovery remain supported without automatic migration. Schema3
adds one progress row (ack_watermark,scan_before) and a resolved flag on retained
review descriptors. Original identity/pending/source columns and canonical event
bytes do not change. A schema2 restore stays schema2; collection controls remain
disabled until a separate explicit migration. No source/vault/Markdown writer,
wire version, external ACK model or Companion contract is introduced.

A collection pass is an opaque, queue/identity/source-bound in-memory capability.
It reads the SAME collector under the SAME native guarded snapshot, using only
its internal transient continuation. Review displays bounded counts; confirmation
rechecks exact selected bytes/descriptors/schema cookie before the sole SQLite
owner atomically stages the batch and scan coverage. Raw stage(batch) is refused
for schema3. A failed/full/interrupted transaction preserves prior pending data,
coverage and witnesses. A committed pass may continue; a lost process restarts
from the persisted acknowledged boundary with inclusive overlap. Rowid is never
persisted or acknowledged. The schema cookie invalidates a transient pass after
VACUUM/DDL; it is not a database-generation identifier. Native Statistics must be
closed/flushed: manual collection/source actions require the file browser. No
startup/background collection, reader hooks, automatic network or Wi-Fi changes
are registered. The UI yields between at most ten100-position batches and stops
safely on capacity/source/error/work limits.

scan_before is a private candidate coverage bound (last observed second minus
one), not the extraction lower bound, a source ACK or permission to drop queued
facts. Only ack_watermark is used to restart ordinary collection. It advances
ONLY within the matching approved opaque-receipt prune transaction, and only
when a selected pending fact was actually acknowledged. Its upper bound is the
observed coverage and strictly before every pending event and unresolved review.
Out-of-order/partial ACKs cannot pass gaps. Already committed overlapping facts
retain their event identity and canonical deduplication remains required.
No response/claim table or boolean can advance this marker. Local status/preview
canonical_ack remains false; it is not an externally usable durability receipt.

Retained invalid entries can be explicitly reviewed in batches of at most100.
One-use owner-bound decisions recheck every exact descriptor inside a transaction.
Exclusion sets resolved=1, keeps the audit descriptor and Statistics untouched,
adds no minutes and advances no ACK marker. Duplicate re-extraction does not undo
the decision. Unresolved cases keep blocking further ACK advancement. Capacity
counts all retained entries, including resolved audit; no silent audit pruning.
Backup/restore and manual copy review bind progress and resolution flags as well
as all selected bytes, identity and source metadata.

Explicit all_history review uses the SAME device/source identity and rescans
native history. Confirming its first batch revokes the prior scan/ACK marker in
the same staging transaction; it does not grant ACK. Failed confirmation restores
prior progress atomically. Subsequent true per-event receipts re-establish the
frontier. This catches backdated additions through explicit rescan, without
inventing a persistent tuple cursor or re-namespacing already delivered facts.
It assumes the reviewed Statistics generation and native identities remain valid;
merged/replaced/rewritten histories still require provenance reconciliation.

An initially empty enrolled source gains indexed native continuity witnesses
when its first real selection is committed. This keeps its original device,
epoch and empty enrollment-history boundary. Witnesses, events and coverage share
one transaction. Old handles/passes must reopen afterward. Thus an in-place
Statistics reset after first collection cannot hide behind permanently empty
witnesses. Legacy schema2 validation remains unchanged; only schema3 accepts the
promoted-witness/empty-original-boundary state.

An actual empty replacement/reset can be explicitly enrolled as a NEW epoch
only when no pending fact or unresolved review remains. The old device ID stays
unchanged; a verified recovery copy of the old state is mandatory before the
transaction, which archives settled audit in that copy, draws a new random epoch
and resets progress. Recheck source review and old scope inside the operation;
rollback keeps the old identity and recovery copy. A still-matching source cannot
rotate its epoch, and a NONEMPTY replacement is blocked for canonical identity/
history reconciliation, never silently reuploaded under a new namespace.

Native/host tests cover acknowledged overlap, same-second groups, partial/foreign
receipts, explicit review, failed commits, before/after SIGKILL with live journals,
atomic empty-source witness promotion, legacy recovery and empty-generation
transitions. Synthetic native proof is not PW3/source-generation or hardware
power-loss acceptance. Gate4 remains OPEN for grouped changed0.0.9 physical/UI
proof, nonempty replacement/state-loss reconciliation and remaining migration/
performance cases. Production transport/lifecycle/effects remain unregistered.


### Explicit schema2-to3 upgrade

An existing schema2 queue can be upgraded only through a one-use reviewed action
bound to that same queue, identity and source guard. Verify all current selected
bytes/review descriptors and the current native Statistics snapshot; save a
verified schema2 recovery copy first. Inside one transaction recheck the old scope,
rebuild only the recognized review declaration with resolved=0 for existing rows,
create empty progress and set version3. Preserve device/epoch, original source
metadata, pending event bytes and every review descriptor. Failed DDL/commit
rolls back to recognized schema2 and leaves the recovery copy. No new identity,
old delivery ACK or source marker is inferred. Unknown schemas and schema1's
unverified diagnostic source remain in explicit recovery/reconciliation, never
silently upgraded. The UI requires a closed book and explicit confirmation.


The ACK frontier validates each remaining pending row's event ID and native
payload digest against its canonical line, just as delivery selection does.
An internally inconsistent neighbor rejects/rolls back another event's local
prune and marker update; a valid receipt does not certify unrelated local rows.

# Quartzo ↔ KOReader — Product & Delivery Plan

> **Repository:** `olalaurao/quartzo-koplugin`  
> **Status:** planned / intentionally deferred  
> **Primary target:** Kindle Paperwhite 3 / 7th gen (PW3), firmware 5.16.2.1.1, KUAL, KOReader 2025.04  
> **Implementation sequence dependency:** finish and stabilize `olalaurao/reader` V1 first  
> **Canonical execution spec:** `IMPLEMENTATION_SPEC.md`  
> **Progress ledger:** `STATUS.md`  
> **Last planning pass:** 2026-09-22

---

# 1. Mission

Build a KOReader plugin that synchronizes reading activity from KOReader into Quartzo without turning the Kindle into a second Quartzo implementation and without creating a parallel source of truth.

The intended user workflow is:

~~~text
Read any document normally in KOReader
        ↓
KOReader Reading Statistics records the activity
        ↓
quartzo.koplugin reads new statistics read-only
        ↓
events are normalized + deduplicated locally
        ↓
events are synced incrementally when network is available
        ↓
Quartzo receives/persists them through an approved canonical Reading Activity contract
        ↓
Quartzo derives reading analytics
        ↓
Obsidian Companion can display/materialize the same canonical analytics
~~~

The plugin should work for:

- EPUBs;
- PDFs;
- HTML/articles;
- newsletters;
- documents downloaded by the Readwise Reader plugin;
- ordinary files copied to the Kindle;
- future KOReader-supported document types that participate in Reading Statistics.

The plugin is **not** a replacement for KOReader Reading Statistics. KOReader remains the recorder/sensor. Quartzo becomes the downstream personal knowledge/analytics consumer.

---

# 2. Core product goals

## 2.1 V1 P0 goals

V1 must:

1. Read KOReader's Reading Statistics safely and read-only.
2. Detect and transmit only new reading events after the initial import.
3. Support a one-time backfill of existing reading history.
4. Survive offline usage, restarts and interrupted syncs without losing events.
5. Make retries idempotent so re-sending the same event never double-counts.
6. Never write to or migrate `statistics.sqlite3`.
7. Identify documents using stable technical identifiers, never title alone.
8. Preserve enough provenance to link events to a Quartzo Resource when a safe match exists.
9. Keep unmatched reading activity rather than discarding it.
10. Support multiple KOReader devices without merging unrelated events.
11. Expose a small, reliable KOReader UI:
    - connection/configuration;
    - Sync now;
    - Import existing history;
    - auto-sync setting;
    - pending count;
    - last successful sync;
    - diagnostics.
12. Avoid turning Wi-Fi on automatically during passive/background sync unless the user explicitly enables behavior that permits it.
13. Keep secrets out of Git, logs, diagnostics and exported fixtures.
14. Integrate with Quartzo's existing architecture through an explicit Reading Activity contract rather than bypassing canonical owners.
15. Make the same canonical Reading Activity data consumable by the Quartzo Obsidian Companion.

## 2.2 V1.1 product goals

After V1 transport/data correctness is stable:

- Today / week / month reading time.
- Reading calendar.
- Reading streak.
- Per-Resource reading time.
- Per-day/per-session history.
- Current / recently read Resources.
- Pages/events read.
- Device breakdown.
- Unmatched-document inbox.
- Manual association of an unmatched KOReader document to a Quartzo Resource.
- Safe preservation of the association for future events.
- Optional read-only Companion analytics surface.

## 2.3 Later / V2 candidates

Not required for V1:

- Quartzo → KOReader progress sync.
- Two-way reading status.
- Two-way ratings.
- Highlights/notes sync.
- Remote document delivery from Quartzo.
- Automatic creation of a Quartzo Resource for every unknown file.
- Editing Resource metadata from the Kindle.
- A full Quartzo dashboard on the Kindle.
- Social/community reading features.
- Cloud account abstraction for arbitrary users.
- General-purpose KOReader backup.

These are explicitly separate problems and must not be pulled into V1 opportunistically.

---

# 3. Non-negotiable architectural principles

## 3.1 KOReader Reading Statistics owns the source database

The stock Statistics plugin owns:

`<KOReader settings>/statistics.sqlite3`

The Quartzo plugin must:

- open it read-only;
- tolerate concurrent writes;
- use bounded queries;
- close connections cleanly;
- never issue UPDATE/INSERT/DELETE/ALTER/VACUUM/PRAGMA mutations;
- never rely on copying the whole DB as the normal sync protocol;
- never replace KOReader's statistics aggregation logic.

## 3.2 Quartzo owns canonical persistence

Current Quartzo architecture says:

- normal Quartzo content objects are canonical Markdown/frontmatter in the vault;
- a new domain-specific canonical store is allowed only when explicitly documented;
- feature-local parallel stores are forbidden.

Therefore the plugin's local state is **transport state only**. It may persist:

- device ID;
- sync cursor/watermark;
- outbox/pending batches;
- document match cache;
- configuration;
- last successful sync;
- protocol/capability version.

It must **not** become the canonical lifetime record of the user's reading history.

Before production sync is built, the Quartzo app repository must define the Reading Activity domain source of truth and update the applicable canonical architecture/specs in the same change.

## 3.3 Event log first; analytics are derived

The network protocol should carry immutable-ish reading events, not only accumulated totals.

Example conceptual source event:

~~~json
{
  "event_id": "qre_...",
  "device_id": "qrd_...",
  "document": {
    "koreader_md5": "...",
    "title": "...",
    "authors": "..."
  },
  "start_time": 178...,
  "duration_seconds": 42,
  "page": 183,
  "total_pages": 412
}
~~~

Quartzo should derive:

- minutes today;
- week/month totals;
- streaks;
- sessions;
- Resource totals;
- pages/progress analytics.

Why this matters:

- retries are naturally deduplicated;
- multiple devices can coexist;
- aggregates can be recalculated when product rules change;
- backfill is possible;
- bugs in an old aggregate do not destroy source evidence.

## 3.4 Single-writer boundaries where possible

If the eventual canonical persistence uses files/shards, prefer a layout where one device owns one shard at a time, for example device + month, rather than every client editing one giant reading-history file.

The exact persisted format is a Gate 0 contract decision, not something this plugin may invent locally.

## 3.5 Fail closed on identity

Never merge by title alone.

Safe identity candidates, in descending confidence:

1. explicit Quartzo Resource ID previously associated;
2. explicit external ID whose namespace is proven to match;
3. Readwise Reader document ID if Quartzo has a dedicated field for that exact namespace;
4. KOReader partial MD5 / file digest association previously approved by the user;
5. ISBN or another exact bibliographic ID;
6. exact source URL when the upstream contract says it is unique enough;
7. manual user association.

Title + author is useful for suggestions only, never as an automatic canonical merge key.

Important: Quartzo currently has `Resource.readwiseBookId` / `book_id`. Do **not** assume that identifier is the same namespace as Readwise Reader API v3 document IDs. The Reader integration must prove the mapping or introduce a distinct provenance field upstream.

## 3.6 No hidden Wi-Fi side effects

- Manual Sync may use KOReader's normal network prompt/manager.
- Passive/periodic sync must skip when offline unless the user deliberately enabled a mode that permits connecting.
- The plugin must not leave Wi-Fi enabled after suspend-specific work on devices where KOReader normally disables it.
- Network behavior must follow KOReader patterns rather than raw shell/network hacks.

---

# 4. Research/reference implementations

The project should learn from existing implementations without blindly copying them.

## 4.1 KOReader Reading Statistics — primary source model

Pinned target reference:

- KOReader `v2025.04`
- `plugins/statistics.koplugin/main.lua`

Relevant verified behavior:

- DB path is `settings/statistics.sqlite3`.
- Schema version on 2025.04 is `20221111`.
- `book` stores title/authors/pages/language/series/md5/last_open/highlight/note/aggregate fields.
- `page_stat_data` stores:
  - `id_book`
  - `page`
  - `start_time`
  - `duration`
  - `total_pages`
- uniqueness is `(id_book, page, start_time)`.
- `page_stat` is a derived view used to rescale page numbers when layout/page count changes.
- the Statistics plugin flushes on document close, save-settings and suspend.
- the database may use WAL where supported.

Use `page_stat_data` as the raw event source unless a later spike proves a better canonical source.

## 4.2 KOSync — lifecycle/network reference

Use stock `kosync.koplugin` as a pattern for:

- `NetworkMgr`;
- manual vs passive networking;
- debounce;
- lifecycle callbacks;
- retries/queueing;
- current-document identity;
- avoiding noisy Wi-Fi prompts;
- suspend behavior.

Do not copy progress-sync behavior that is unrelated to Reading Activity.

## 4.3 Exporter — transport separation reference

Use `exporter.koplugin` as a design reference for separating:

- collection/normalization;
- target/provider;
- network transport;
- UI.

This project should similarly keep Statistics reading independent of the Quartzo transport implementation.

## 4.4 BookOrbit — strongest stats-sync reference

BookOrbit's KOReader plugin demonstrates several highly relevant patterns:

- `statistics.sqlite3` opened read-only;
- short-lived/read-only SQLite access;
- busy timeout;
- no write transaction against Statistics;
- grouping Statistics rows by MD5;
- keyset pagination;
- per-book event watermarks;
- backfill in bounded batches;
- overlap around watermark boundaries;
- server-side idempotency;
- resumable full-library sweeps;
- persistent local sync state;
- serialized/coalesced sync jobs.

Its repository is AGPL-3.0. Our current `olalaurao/reader` project is also AGPL-3.0, but any direct code reuse here still requires deliberate license compliance and attribution. Prefer learning patterns and implementing independently unless a later license review explicitly approves copying a specific implementation.

## 4.5 KoInsight — server/dashboard reference

KoInsight demonstrates that:

- the Statistics DB can feed external analytics;
- a KOReader plugin can sync stats to a server;
- multi-device and identity semantics are non-trivial;
- uploading the whole SQLite database is convenient but is not necessarily the best incremental protocol for Quartzo.

Use it for API/dashboard ideas, not as the V1 data model.

## 4.6 Syncery — orchestration reference

Syncery intentionally triggers KOReader's own sync owners rather than merging their databases itself.

Lesson for this project:

- reuse KOReader owners where possible;
- do not fork native semantics;
- do not become a second Statistics engine.

## 4.7 `olalaurao/reader` — target-device compatibility reference

The existing Readwise Reader plugin is the best source for patterns already proven on the user's target PW3 / KOReader 2025.04:

- plugin packaging;
- menu wiring;
- HTTP client behavior;
- progress/cancellation surface;
- subprocess/trapper requirements;
- tests/CI;
- device gates;
- safe settings;
- logging;
- crash recovery.

The Quartzo plugin must remain a separate plugin/repository and must not require Readwise Reader to be installed.

---

# 5. Proposed logical architecture

~~~text
┌─────────────────────────────────────────────┐
│ KOReader                                    │
│                                             │
│  stock Reading Statistics                   │
│  statistics.sqlite3                         │
│             │                               │
│             ▼                               │
│  quartzo.koplugin                           │
│    ├─ stats reader (read-only)              │
│    ├─ identity normalizer                   │
│    ├─ deterministic event IDs               │
│    ├─ cursor/watermark state                │
│    ├─ durable outbox                        │
│    ├─ sync coordinator                      │
│    └─ transport adapter                     │
└──────────────────┬──────────────────────────┘
                   │ HTTPS / approved transport
                   ▼
        ┌────────────────────────┐
        │ Quartzo ingress        │
        │ idempotent + versioned │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ Canonical Reading      │
        │ Activity domain        │
        │ (decided upstream)     │
        └──────┬─────────┬───────┘
               │         │
               ▼         ▼
          Quartzo app   Companion
               │         │
               └────┬────┘
                    ▼
              derived analytics
~~~

The ingress layer is not automatically a new source of truth. Gate 0 must decide whether it is:

- transport only;
- a canonical domain store;
- or an adapter writing into another canonical store.

That decision must be reflected in Quartzo architecture docs before production implementation.

---

# 6. Transport decision — Gate 0 must prove it

Quartzo today does not expose a public always-on ingestion API. The KOReader plugin therefore cannot simply assume `POST /reading` exists.

The first implementation milestone must compare and experimentally validate these routes.

## Option A — minimal HTTPS Reading Ingress bridge

KOReader sends small authenticated JSON batches to a purpose-built endpoint.

Pros:

- simplest Kindle client;
- easy batching/retry/idempotency;
- avoids Google OAuth complexity on Kindle;
- can keep canonical persistence logic server-side/upstream;
- easiest to test.

Cons:

- introduces deployable infrastructure;
- requires auth/token management;
- must not accidentally become an undocumented canonical database.

This is the **first option to evaluate**, but it is not approved until Gate 0.

## Option B — direct Google Drive API from KOReader

Plugin writes approved Reading Activity artifacts directly to a dedicated Drive location.

Pros:

- no custom server;
- naturally reaches the same cloud used by Quartzo.

Risks/questions to prove:

- practical OAuth flow on a limited-input Kindle;
- token refresh/security;
- TLS/library compatibility;
- Drive API complexity and quotas;
- whether direct external writes can honor Quartzo sync/hash/identity contracts;
- whether doing so would bypass existing canonical Drive sync owners.

Do not build this based on an assumed OAuth flow. It must be experimentally proven on the target device first.

## Option C — staging provider (WebDAV/Dropbox/etc.) + Quartzo importer

KOReader writes event batches to an intermediate cloud provider, then Quartzo imports them.

Pros:

- KOReader already has cloud-storage patterns;
- can be self-hosted.

Cons:

- adds another account/provider;
- poorer UX;
- additional reconciliation;
- must define importer ownership and idempotency.

Keep as fallback unless the user already wants that provider.

## Option D — full Statistics DB upload

Uploading `statistics.sqlite3` is acceptable only as:

- a debugging tool;
- a migration/import fallback;
- a one-time recovery route.

It is **not** the preferred normal protocol because it is bulky, merges poorly across devices, exposes implementation-specific DB state and makes incremental acknowledgements harder.

## Gate 0 transport exit criteria

No production plugin sync code starts until one route proves all of:

- works on the target PW3;
- authenticated without committing secrets;
- supports HTTPS/TLS reliably;
- can send at least a small test payload;
- supports idempotent retry;
- does not require the Kindle to host a service;
- does not make a temporary transport database the undocumented canonical source;
- has a documented rotation/revocation story;
- can be implemented without breaking Quartzo's canonical sync architecture.

---

# 7. Canonical Reading Activity contract to add upstream

Before Phase C/D, create an active Quartzo spec, tentatively:

`docs/specs/reading-activity.md`

It should define:

## 7.1 Reading event

Required conceptual fields:

- `schema_version`
- `event_id`
- `device_id`
- `source = koreader`
- `source_event_version`
- `started_at_epoch`
- `duration_seconds`
- `page`
- `total_pages`
- document identity block
- ingestion timestamp
- optional local-date/timezone projection
- optional explicit Quartzo Resource association

## 7.2 Device identity

A random installation-local ID, not the Kindle serial.

Properties:

- generated once;
- persisted locally;
- revocable/resettable;
- opaque;
- no personally identifying hardware data required.

## 7.3 Document identity

Possible fields:

- `koreader_md5`
- `koreader_statistics_book_ids` only for diagnostics/local provenance, not global identity
- `title`
- `authors`
- `source_url`
- `isbn`
- `reader_document_id` in its explicit namespace
- `readwise_book_id` in its explicit namespace
- `quartzo_resource_id`
- `local_filename` only if privacy contract explicitly permits it

Avoid sending the full local path by default.

## 7.4 Event ID semantics

Event IDs must be deterministic enough for safe retry.

Candidate input:

- protocol namespace/version;
- device ID;
- stable document digest;
- `start_time`;
- page;
- duration;
- total pages.

Do not use title as the identity salt.

Final algorithm belongs in the cross-client contract and must have executable golden vectors shared between Lua/Dart/TypeScript when appropriate.

## 7.5 Sessions

Sessions should be derived from events, not required as the primary ingested truth.

The contract must specify:

- session gap threshold;
- midnight split rules;
- timezone semantics;
- duration clamping;
- handling events whose `total_pages` changed after reflow;
- multi-device overlap policy.

## 7.6 Aggregates

Derived only:

- daily seconds;
- weekly/monthly seconds;
- active days;
- streak;
- per-Resource seconds;
- sessions;
- progress estimates.

Never make an aggregate the only surviving evidence if raw canonical events are available.

---

# 8. Repository structure target

Tentative implementation layout:

~~~text
quartzo-koplugin/
├── AGENT_BOOTSTRAP.md
├── README.md
├── PLAN.md
├── IMPLEMENTATION_SPEC.md
├── STATUS.md
├── CHANGELOG.md
├── LICENSE
├── docs/
│   ├── DEVICE_TESTS.md
│   ├── PROTOCOL.md
│   ├── TRANSPORT_DECISION.md
│   ├── RESEARCH_REFERENCES.md
│   └── fixtures/
├── quartzo.koplugin/
│   ├── _meta.lua
│   ├── main.lua
│   ├── constants.lua
│   ├── config.lua
│   ├── stats/
│   │   ├── db.lua
│   │   ├── reader.lua
│   │   ├── events.lua
│   │   └── identity.lua
│   ├── sync/
│   │   ├── coordinator.lua
│   │   ├── collector.lua
│   │   ├── outbox.lua
│   │   ├── cursor.lua
│   │   └── backfill.lua
│   ├── transport/
│   │   ├── client.lua
│   │   ├── protocol.lua
│   │   └── auth.lua
│   ├── integrations/
│   │   └── readwisereader.lua
│   ├── storage/
│   │   ├── state.lua
│   │   ├── schema.lua
│   │   └── migrations.lua
│   ├── ui/
│   │   ├── menu.lua
│   │   ├── settings.lua
│   │   ├── status.lua
│   │   └── diagnostics.lua
│   └── tests/
│       └── ...
└── scripts/
    ├── package.sh
    └── test.sh
~~~

This is a planning layout, not a requirement to create unnecessary modules. Keep the final code as small as the proven behavior allows.

---

# 9. Delivery phases and gates

## Phase 0 — upstream revalidation and freeze

Before creating plugin code:

1. Confirm `olalaurao/reader` has reached stable V1/tag.
2. Pull current:
   - `olalaurao/quartzo-koplugin`
   - `olalaurao/aplicativo`
   - `olalaurao/quartzo-obsidian-companion`
   - `olalaurao/reader`
   - target KOReader source/tag.
3. Read current canonical docs, not only this plan.
4. Re-check whether Quartzo has gained a server/API or changed persistence since this plan.
5. Re-check Resource identity fields.
6. Re-check KOReader Statistics schema/behavior.
7. Pin exact upstream SHAs in `STATUS.md`.

### Gate 0A — canonical domain decision

Pass only when upstream Quartzo has a documented Reading Activity canonical source of truth and ownership path.

### Gate 0B — transport proof

Pass only when a real target-device test sends a tiny authenticated payload through the selected transport.

### Gate 0C — protocol skeleton

Pass only when request/response schema, idempotency semantics and auth rotation are documented and have golden fixtures.

No general sync implementation before all Gate 0 sub-gates pass.

---

## Phase A — plugin bootstrap

Implement:

- `quartzo.koplugin/_meta.lua`;
- minimal `main.lua`;
- Tools menu entry;
- version constant;
- safe config/state path;
- diagnostics screen;
- CI/package skeleton.

No Statistics DB access yet.

### Gate 1 — install/remove safety

On target PW3:

- KOReader starts normally with plugin installed;
- Quartzo menu appears;
- opening menu does not block;
- plugin can be removed without touching KOReader data;
- no Wi-Fi state change;
- no DB files modified.

---

## Phase B — read-only Statistics probe

Implement a tiny Statistics reader:

- locate `statistics.sqlite3`;
- open read-only;
- read `PRAGMA user_version`;
- validate supported schema;
- list counts only:
  - number of book rows;
  - number of raw events;
  - earliest/latest event;
- no network;
- no local sync-state mutation beyond diagnostics if possible.

Use short-lived connection and bounded timeout.

### Gate 2 — read-only DB safety

Pass when:

- target DB opens on KOReader 2025.04;
- schema is exactly understood;
- data counts are plausible;
- reading normally while the probe exists still works;
- probe does not lock/freeze KOReader;
- DB checksum/content is unchanged by the plugin;
- unknown schema fails closed with a clear message.

---

## Phase C — event extraction + deterministic identity

Implement:

- book-row enumeration;
- grouping by KOReader MD5;
- event enumeration from `page_stat_data`;
- deterministic event ID;
- bounded batch collector;
- overlap-safe watermark logic;
- normalization;
- optional local-date projection;
- privacy-safe metadata;
- fixture tests.

Important edge cases:

- multiple `book` rows sharing one MD5;
- same-second multiple events;
- same page revisited;
- reflow changes `total_pages`;
- missing MD5;
- blank metadata;
- corrupted row;
- absurd duration;
- statistics disabled;
- book deleted from device but history remains.

### Gate 3 — deterministic replay

Given the same DB snapshot:

- extraction produces byte-equivalent normalized events;
- repeated extraction after acknowledged watermark produces no new logical events;
- intentionally overlapping the previous second only creates duplicate event IDs, not new logical events;
- title changes do not change existing event identity;
- two distinct device IDs do not collide.

---

## Phase D — local state + durable outbox

Implement plugin-owned state:

- random `device_id`;
- schema version;
- per-document/per-source watermarks as required;
- pending batches;
- last ack;
- last success/error metadata;
- optional document→Resource association cache;
- migration version.

Requirements:

- atomic writes;
- crash-safe replace;
- recover from truncated temp/state file;
- state deletion causes safe re-upload, not loss of canonical data;
- server/canonical sink deduplicates re-upload.

### Gate 4 — crash/restart safety

Simulate/physically test:

- power/restart before send;
- after send before local ack;
- during state flush;
- after partial batch ack;
- state reset;
- queue retry.

No duplicate canonical reading time after recovery.

---

## Phase E — selected transport client

Implement only the Gate 0-selected transport.

Common requirements:

- explicit endpoint/config;
- secret masked in UI;
- TLS verification;
- finite connect/read timeout;
- request size bound;
- batch size bound;
- 429 handling;
- bounded retry;
- typed errors;
- no secret/body dump in logs;
- protocol version header/body;
- capability/version check.

Manual sync may ensure networking through KOReader `NetworkMgr`.

Passive sync must not nag/force networking.

### Gate 5 — idempotent remote ack

On real endpoint:

- same batch sent twice counts once;
- out-of-order retry is safe;
- partial rejection is represented per event/batch;
- 401/403 stops retry and asks user to reconnect;
- 429 respects retry timing;
- 5xx keeps data pending;
- malformed schema fails visibly;
- no event disappears silently.

---

## Phase F — Quartzo canonical ingestion

Implement upstream before claiming end-to-end completion.

Depending on Gate 0 architecture, this may involve:

- a Reading Activity repository/service;
- canonical persisted shards/store;
- parser/codec;
- ingestion adapter;
- event dedupe;
- Resource association service;
- unmatched-document records;
- derived analytics service;
- tests/golden vectors;
- Companion vendoring/contracts.

Rules:

- do not write Resource files directly from arbitrary network handler code;
- association changes must use canonical Quartzo owners;
- ingestion must preserve unknown future fields or reject unsupported versions safely;
- duplicates are no-ops;
- unsupported events stay quarantined/retryable, not discarded.

### Gate 6 — end-to-end one event

Prove:

1. read a test document on Kindle;
2. native Statistics records it;
3. Quartzo plugin extracts/sends it;
4. canonical Quartzo store contains exactly one event;
5. Quartzo UI/service derives the correct duration;
6. retry does not double-count;
7. Companion reads the same canonical result after its normal sync path.

---

## Phase G — document association

Implement matching in Quartzo, not via unsafe Kindle guesses.

Auto-match only when exact identity is proven.

Potential exact sources:

- stored Quartzo Resource ID from a previous association;
- exact external namespace ID;
- pre-approved KOReader digest association.

For unknown docs:

- show an unmatched entry;
- suggest Resources by title/author/source URL as UX only;
- require explicit selection;
- persist the mapping in the canonical Reading Activity/Resource identity contract.

### Gate 7 — collision safety

Test:

- two books with same title;
- same title + different author;
- same file digest with metadata change;
- Readwise Reader article whose title changes;
- v2 Readwise book ID vs Reader v3 document ID namespace mismatch;
- local document with no metadata.

No silent wrong association.

---

## Phase H — full history backfill

Add `Import existing reading history`.

Design:

- keyset/bounded enumeration;
- batches small enough for PW3 memory;
- cancellable progress UI;
- resumable checkpoint;
- server/canonical dedupe;
- no giant all-events Lua table;
- no O(n²) queue operations;
- can stop and resume.

Suggested first implementation target: batches on the order of 100–500 events, tuned by device testing rather than assumed.

### Gate 8 — real-history backfill

On the user's actual Statistics DB:

- complete full history;
- cancel and resume;
- restart and resume;
- run import twice;
- totals remain stable;
- KOReader stays usable;
- no statistics DB corruption;
- memory stays within target-device tolerance.

---

## Phase I — lifecycle/auto sync

After manual sync is stable:

Possible triggers:

- document close;
- suspend;
- periodic page count;
- KOReader startup/resume;
- manual only.

V1 default should remain conservative.

Recommended default:

- manual sync enabled;
- auto-sync on close/suspend optional and off until physical validation;
- periodic page-turn sync optional and off by default.

Every automatic trigger submits work to one canonical sync coordinator:

- single active job;
- coalesce duplicate requests;
- manual > auto priority where appropriate;
- bounded work per lifecycle event.

### Gate 9 — lifecycle safety

Physical-device proof:

- close document;
- suspend/resume;
- rapid open/close;
- offline;
- Wi-Fi already on;
- Wi-Fi off;
- multiple triggers.

No freeze, prompt storm, duplicate batch, or suspend regression.

---

## Phase J — Quartzo analytics UX

Only after data correctness.

Possible Quartzo surfaces:

- Reading dashboard;
- Resource detail Reading section;
- daily/weekly/monthly charts;
- streak;
- history list;
- unmatched documents;
- device filter;
- reading heatmap.

Possible Companion surfaces:

- read-only analytics panel;
- Resource detail reading projection;
- optional controlled Markdown materialization if explicitly desired.

Do not make the Companion or UI a second aggregation owner; both consume shared contract logic/vectors.

---

# 10. Local state design

Tentative plugin state file:

`settings/quartzo_sync_state.lua`

Configuration may be separate if needed:

`settings/quartzo.lua`

Example conceptual state:

~~~lua
return {
    schema_version = 1,
    device_id = "qrd_...",
    transport = {
        endpoint = "...",
        -- secret stored separately/masked as applicable
    },
    cursors = {
        -- implementation-specific acknowledged positions
    },
    pending = {
        -- bounded durable outbox descriptors
    },
    associations = {
        -- optional digest -> explicit Quartzo Resource ID cache
    },
    last_success_at = 0,
}
~~~

Do not store every historical reading event forever if the canonical sink has acknowledged it. Store only enough to resume safely.

---

# 11. Event collection details to preserve

The collector must preserve:

- raw event start time;
- duration;
- raw page number;
- raw `total_pages` at time of event;
- stable file/document digest;
- safe metadata snapshot;
- source schema/protocol version.

Do not replace raw source fields with only a computed percentage because reflow can change page counts.

Quartzo may derive a normalized progress estimate from `page / total_pages`, but that is a projection.

---

# 12. Reading time semantics

KOReader Statistics has nuanced behavior:

- raw events are inserted when duration > 0;
- the `book` table holds an uncapped total;
- some Statistics UI calculations clamp cumulative time per distinct page by the configured `max_sec`;
- raw event history can contain repeated visits.

Therefore V1 must explicitly distinguish:

1. **raw recorded event duration** — source evidence;
2. **Quartzo active reading duration** — derived according to the Reading Activity contract;
3. **KOReader Statistics displayed/capped metrics** — useful compatibility projection.

Do not silently claim all three are identical.

The upstream contract must choose what Quartzo charts mean and preserve enough raw data to change the derivation later.

---

# 13. Network/retry policy

Classify outcomes:

## Success

- 2xx with valid protocol response;
- ack only after body/schema validation.

## Retryable

- offline/unreachable;
- timeout;
- 408;
- 429;
- selected 5xx;
- transient canonical-sink busy state.

Use bounded backoff and retain outbox.

## Non-retryable until user/config action

- 400 schema invalid;
- 401 auth invalid;
- 403 permission/auth policy;
- unsupported protocol version;
- invalid device registration.

Keep events locally pending/quarantined; do not discard them.

---

# 14. Security and privacy

## Secrets

- never Git;
- never fixtures;
- never logs;
- never crash report strings;
- masked in UI;
- removable/rotatable.

## Metadata minimization

By default send only what matching/analytics need.

Do not send:

- full filesystem path;
- Kindle serial;
- Wi-Fi identifiers;
- device MAC;
- arbitrary document body;
- highlights/notes;
- unrelated settings.

## Logging

Safe:

- event count;
- batch number;
- protocol version;
- HTTP status;
- elapsed time;
- short non-secret diagnostic IDs.

Unsafe:

- bearer tokens;
- authorization headers;
- document text;
- private notes;
- signed URLs;
- full local paths unless explicit debug opt-in and sanitized.

---

# 15. Test strategy

## Pure Lua/unit tests

- event ID vectors;
- schema parsing;
- watermark overlap;
- grouping duplicate MD5 rows;
- state migrations;
- outbox ack/retry;
- coordinator coalescing;
- HTTP classification;
- identity confidence rules;
- privacy/log redaction.

## SQLite fixture tests

Use synthetic Statistics DBs with:

- empty DB;
- one book/one event;
- many books;
- duplicate MD5 across book rows;
- same timestamp events;
- layout changes;
- blank authors/title;
- huge history;
- unknown schema.

Never use the user's private DB in Git.

## Contract tests upstream

Dart/TypeScript/Lua golden vectors for:

- event ID;
- schema codec;
- dedupe;
- session derivation if cross-client;
- Resource identity association.

## Physical device tests

Every gate that touches lifecycle, network, DB concurrency or performance requires the real PW3.

Desktop tests do not replace:

- suspend behavior;
- e-ink responsiveness;
- low-memory behavior;
- Wi-Fi manager behavior;
- KOReader 2025.04 quirks.

---

# 16. Performance budget

Target hardware is old and resource constrained.

Rules:

- no full DB load into memory;
- no full-history JSON payload;
- bounded event batches;
- keyset/watermark queries;
- prepared statements where useful;
- no `table.remove(queue, 1)` on large queues;
- yield/cancellable UI for backfill;
- short lifecycle work;
- do not block page turns for ordinary auto-sync.

Measure rather than guess.

---

# 17. Compatibility policy

Primary support target for V1:

- Kindle Paperwhite 3 / 7th generation;
- firmware 5.16.2.1.1;
- KOReader 2025.04.

The code should avoid unnecessary target-specific hacks, but V1 is not blocked on every newer KOReader release.

After target V1:

- test current KOReader stable;
- add schema/version compatibility table;
- fail closed on unknown Statistics schema until validated.

---

# 18. Interaction with Readwise Reader plugin

This plugin must work without `readwisereader.koplugin`.

When it is installed, an optional integration adapter may enrich identity with Reader provenance.

Rules:

- no hard import dependency;
- no shared mutable global state;
- no duplicate ownership of highlights/notes;
- no Reader API calls from Quartzo plugin in V1;
- no assumption that Reader v3 IDs equal Readwise v2 IDs;
- use only a stable, documented mapping exported by the Reader plugin after its V1 architecture is frozen.

If the Reader plugin exposes a stable local mapping:

~~~text
local file / digest
      ↕
Reader v3 document ID
~~~

the Quartzo plugin may attach that ID as provenance to the reading event.

Quartzo remains responsible for deciding whether that provenance matches an existing Resource.

---

# 19. Obsidian strategy

Do not implement KOReader → Obsidian as a separate sync protocol.

Preferred flow:

~~~text
KOReader → canonical Quartzo Reading Activity → Quartzo Companion → Obsidian UI/projection
~~~

If the user later wants Markdown records, add them through the Companion/Quartzo canonical writer.

Examples of possible projections:

- daily note reading summary;
- Resource detail reading section;
- monthly reading note;
- Dataview-friendly derived file.

These are projections, not the event source of truth.

---

# 20. Release criteria for V1

V1 is complete only when all are true:

- [ ] Reader V1 dependency sequencing satisfied or explicitly waived.
- [ ] Gate 0 canonical source decision documented upstream.
- [ ] Gate 0 transport proven on target Kindle.
- [ ] Plugin installs/removes safely.
- [ ] Statistics DB read is read-only and schema-checked.
- [ ] Event extraction deterministic.
- [ ] Durable outbox survives restart.
- [ ] Remote/canonical dedupe proven.
- [ ] One-event E2E proven.
- [ ] Resource matching cannot merge by title alone.
- [ ] Full-history import completes and resumes.
- [ ] Offline use loses no data.
- [ ] Sync retry doubles no totals.
- [ ] Multi-device IDs are isolated.
- [ ] Auto/lifecycle sync does not freeze or nag unexpectedly.
- [ ] Secrets are absent from Git/logs/artifacts.
- [ ] App and Companion consume the same canonical contract.
- [ ] CI/package gates pass.
- [ ] Physical PW3 acceptance suite passes.
- [ ] `STATUS.md`, README and changelog reflect reality.

---

# 21. Known open decisions intentionally deferred to Gate 0

Do not "solve" these by assumption during implementation:

1. Exact transport from Kindle to Quartzo.
2. Exact canonical persistence location for Reading Activity.
3. Whether Reading Activity is a vault subdomain or explicit separate Drive-backed domain.
4. Exact event ID hash algorithm.
5. Exact timezone/local-day representation.
6. Exact session-gap rule.
7. Exact Quartzo definition of "reading time" vs KOReader capped/raw time.
8. Exact Resource field for Readwise Reader v3 document identity.
9. Whether unmatched reading automatically creates a Resource.
10. Whether Companion V1.x writes any Markdown projection or only displays analytics.
11. Whether auto-sync defaults to close/suspend, periodic pages, or manual only after device testing.
12. Whether the transport endpoint is user-hosted, app-hosted, Apps Script, Worker, direct Drive, or another approved route.

Each must become a deliberate contract decision with tests before production behavior depends on it.

---

# 22. Planning snapshot / repositories reviewed

Planning was based on current state observed on 2026-09-22, including:

- `olalaurao/aplicativo` main around `9910de0eadc53f4be9d420d3dab7ff8326e2267d`;
- `olalaurao/quartzo-obsidian-companion` current main/release line and its vendored upstream contract lock;
- `olalaurao/reader` after Phase E merge around `e5de4a75a9e8e43dd270194201626c80d0c15802`;
- KOReader `v2025.04` Statistics/KOSync/Exporter;
- current BookOrbit KOReader plugin;
- current KoInsight;
- current Syncery.

These are **research snapshots, not eternal pins**. Phase 0 must re-read current upstream state before coding.

---

# 23. Short implementation order

When the project is actually started, the correct order is:

~~~text
finish Reader V1
→ re-read current upstream architecture
→ define Reading Activity contract upstream
→ prove transport on PW3
→ bootstrap quartzo.koplugin
→ prove read-only Statistics access
→ implement deterministic event extraction
→ implement durable outbox
→ implement selected transport
→ implement canonical Quartzo ingestion
→ prove one-event E2E
→ implement safe Resource association
→ implement resumable history backfill
→ add conservative lifecycle sync
→ add Quartzo/Companion analytics UI
→ release
~~~

Do not skip forward because a later feature appears easier.

# Quartzo ↔ KOReader — Implementation Specification

> **Canonical execution specification**  
> **Repository:** `olalaurao/quartzo-koplugin`  
> **Target V1 device:** Kindle Paperwhite 3 / 7th gen (PW3), firmware 5.16.2.1.1, KUAL, KOReader 2025.04  
> **Product roadmap:** `PLAN.md`  
> **Progress ledger:** `STATUS.md`  
> **Implementation state:** NOT STARTED — planning only  
> **Last verified planning pass:** 2026-09-22

This file is the implementation source of truth once implementation begins. If code and this specification disagree, either the code is wrong or this file must be deliberately updated in the same change, with the reason recorded in `STATUS.md`.

---

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
- compatible first with the user's PW3 / KOReader 2025.04;
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
- KOReader target: 2025.04.

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

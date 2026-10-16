# Implementation Status

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

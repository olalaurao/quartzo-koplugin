# Implementation Status

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

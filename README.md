# Quartzo KOReader Plugin

KOReader plugin in development for synchronizing reading activity into Quartzo.

> **Status:** Gate 0 foundation criteria are met. The minimal Phase A bootstrap is implemented and host-tested; physical install/start/menu/remove Gate 1 remains open. Statistics access, ingestion and effects are inactive. See STATUS for source-bound evidence and remaining gates.

The bootstrap package and offline physical acceptance steps are documented in
[tools/plugin](tools/plugin/README.md). The plugin's Quartzo Tools entry currently
shows its version and inactive integration status.

Independent Gate 0B client preparation and real-Lua-5.1 host logic tests are in
[tools/transport_probe](tools/transport_probe/README.md). This is diagnostic-only,
with a temporary host TLS fixture, a single-use KUAL diagnostic launcher and
explicit fresh-folder bundle installation/collection. The [physical PW3 diagnostic](docs/evidence/transport-probe-pw3-2026-10-16.json)
passed TLS/auth/error/retry/replay on KOReader v2026.07.1. A later independently
collected normal-pairing trial passed the finite G04 spike; production outbox
acknowledgement remains separate. Temporary files were manually removed and their
absence verified with Kindle mounted, as recorded in STATUS. This is not the production plugin.

## Goal

Read KOReader's native Reading Statistics **read-only**, normalize new reading events, queue them safely while offline, and synchronize them into a canonical Quartzo Reading Activity domain.

The intended flow is:

~~~text
KOReader Reading Statistics
        ↓
quartzo.koplugin
        ↓
incremental/idempotent sync
        ↓
canonical Quartzo Reading Activity
        ↓
Quartzo app + Obsidian Companion
        ↓
derived reading analytics
~~~

The plugin is intended to work with ordinary KOReader documents as well as files downloaded by the separate Readwise Reader plugin. Readwise Reader is **not** a required dependency.

## Target V1 device

- Kindle Paperwhite 3 / 7th generation
- Firmware 5.16.2.1.1
- KUAL
- KOReader v2026.07.1 (`kindlepw2`), physically documented Reader baseline; confirm current installation before new tests

The 2026-10-16 integrated scope adds gated one-way status evidence and opt-in promotion only for proven Reader-origin KOReader reading, through the upstream Resource owner. Reader-only remains external, ordinary unmatched events remain preserved, and no staging ACK or automatic effect is enabled. See the precedence reconciliation in `IMPLEMENTATION_SPEC.md`.

## Project documents

Read these before implementation:

1. **`AGENT_BOOTSTRAP.md`** — mandatory startup/authority rules.
2. **`STATUS.md`** — current milestone, blockers, upstream SHAs and exact next action.
3. **`IMPLEMENTATION_SPEC.md`** — canonical technical execution specification and gates.
4. **`PLAN.md`** — detailed product scope, architecture, roadmap and research conclusions.

## Architectural rules

- Never write to KOReader's `statistics.sqlite3`.
- Never use title alone as document identity.
- Local plugin state is transport/cursor/outbox state, not the canonical reading-history database.
- Quartzo must define an explicit canonical Reading Activity owner before production sync.
- Retries must be idempotent end-to-end.
- Offline reading must never lose events.
- The plugin must not silently enable Wi-Fi during passive sync.
- KOReader → Obsidian is not a separate sync path; Companion should consume the same canonical Quartzo data.
- No highlights/notes/progress writeback in V1.

## Why the implementation starts with Gate 0

Quartzo currently centers normal content persistence on its vault/Google Drive architecture rather than exposing an assumed always-on ingestion API.

Gate 0 established the canonical owners and a finite app-hosted HTTPS route with
independently approved exact peer identity. Before general synchronization it
must retain proof of:

1. the canonical persisted owner of Reading Activity inside Quartzo;
2. the authenticated Kindle → Quartzo transport;
3. the versioned event/idempotency protocol.

Only after those are proven does the project proceed to plugin bootstrap, Statistics access, incremental extraction, durable outbox, backfill and lifecycle sync.

## Technical references

The planning pass reviewed:

- KOReader 2025.04 Reading Statistics;
- KOSync;
- Exporter;
- BookOrbit's KOReader plugin;
- KoInsight;
- Syncery;
- `olalaurao/reader`;
- current Quartzo app architecture;
- current Quartzo Obsidian Companion architecture/contracts.

The strongest implementation pattern for Statistics sync is:

**KOReader Statistics as sensor + read-only incremental collector + deterministic event IDs + ack-gated local state + canonical Quartzo ingestion.**

See `PLAN.md` and `IMPLEMENTATION_SPEC.md` for the complete design.

# Quartzo KOReader Plugin

Planned KOReader plugin for synchronizing reading activity from KOReader into Quartzo.

> **Status:** planning complete; implementation intentionally deferred until the current `olalaurao/reader` Readwise Reader plugin reaches the desired stable V1/tag, unless that sequencing is explicitly changed.

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
- KOReader 2025.04

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

So the project deliberately does **not** hard-code a transport yet. Before general plugin work, Gate 0 must establish:

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

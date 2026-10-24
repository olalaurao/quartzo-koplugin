# Reading queue recovery

The SQLite outbox owner is `quartzo/outbox.lua`; Statistics stays read-only.
Recovery retains the original device ID, source epoch and selected event bytes.
A new identity, title, MD5, row count, date or matching sample cannot replace the
original queue/recovery authority. No automatic reset or backup selection exists.

## Supported paths

For an existing primary, normal open lets the native SQLite SDK recover its own
hot journal. A failed open/status still permits **Review recovery copies**. Review
does not overwrite the primary or create an identity; restore refuses an existing
primary, including a damaged or future-schema file.

For an absent primary, choose and review an original supported recovery copy.
The owner rechecks its identity, exact selected bytes, retained review, source
guards and progress during the copy transaction. It restores the same recognized
schema version; older queues are not automatically upgraded. Source checks or
explicit same-history reconfirmation still apply before collection. A different
nonempty Statistics history remains blocked for reconciliation.

An absent destination with a journal, WAL or SHM is **not** a fresh destination.
Create, backup and restore refuse it before creating that database; restore
refuses before opening the selected backup. Even empty sidecars are preserved.
No unrelated file is opened as a recovery database.

## Preservation before assisted repair

Close KOReader before USB inspection. Preserve a fresh private copy and checksums
of the primary, all its sidecars and all recovery artifacts before changing any
file. Inspect SQL only on private copies. Identify the original supported copy
and record which later selected facts it cannot recover; a snapshot is not proof
that no newer pending facts existed.

If damaged state/sidecars prevent restore, keep the complete original set for
assisted review. A deliberate, reversible preservation step must retain exact
names and bytes together and be verified before restoring into the now-absent
destination. This is not an instruction to delete files, rename a backup over the
primary or run an automatic repair. The normal owner remains responsible for
the actual restore. Do not modify `statistics.sqlite3` or other plugins.

After restore, compare the original identity and selected bytes/review/progress
with the chosen copy. Retry uses those original native IDs; scan progress or a
successful local restore grants no delivery ACK. Only approved per-event durable
receipts can prune. Preserve every failed/partial destination for review.

If all authoritative identity copies are missing, stop rather than enroll the
same old history under a guessed new identity. Canonical source inventory is
read-only context, not restoration authority. Recovery of that case and nonempty
replacement-history reconciliation remain open production paths. Host fixtures
and this procedure do not close their physical or end-to-end gates.

# Plugin, read-only Statistics and owned delivery-state development

Phase A0.0.1 passed the actual PW3 install/start/menu/remove/restart gate. PhaseB
0.0.2 adds a separate, explicitly requested Reading Statistics diagnostic.
Synchronization remains inactive. KOReader's PluginLoader
loads `_meta.lua` into the plugin class; it is the single version owner.
`DataStorage:getSettingsDir()` supplies reserved Quartzo settings paths; normal
startup opens/writes neither. The inactive outbox API can explicitly own its
separate SQLite file. Reader, SimpleUI and Extra are not dependencies.

Run with the existing pinned test-only Lupa dependency:

```sh
python -m unittest discover -s tools/plugin -p 'test_*.py' -v
python tools/plugin/package.py --output /existing/output/directory/quartzo-bootstrap.zip
```

Packaging exclusively creates a fresh uncompressed ZIP containing
the eight exact Lua sources in `package.py`'s allowlist: main,metadata,Statistics,
collector,outbox,the unchanged paired owner and the sole codec/SDK adapter. Its JSON
output records ZIP and individual source SHA-256 hashes.
It never installs a plugin, replaces an archive or bundles diagnostics, fixtures,
credentials, contract copies or private data.

## Source-bound Phase A Gate 1 proof

Version0.0.1 completed the following script; see the committed
[report](../../docs/evidence/plugin-bootstrap-pw3-2026-10-21.json). This historical
bootstrap proof does not pass PhaseB/Gate2 for newly added Statistics access.

Host tests and package creation do not pass Gate 1. For an exact-source trial:

1. With the Kindle mounted, verify KOReader v2026.07.1 and the package hashes.
   Preserve a private before observation of Statistics DB/WAL/SHM and reserved
   Quartzo settings file existence/hash, plus existing plugin source hashes.
2. Install only into a fresh `koreader/plugins/quartzo.koplugin` directory. If
   it already exists, stop and review its identity; never overwrite it.
3. The user safely disconnects USB and starts KOReader without opening a book.
   Open Tools → More tools → Quartzo. Confirm the displayed version, responsive
   menu, inactive Statistics/synchronization and unchanged Wi-Fi state.
4. Reconnect USB. Verify the exact installed files, startup error observations,
   DB bytes and other plugin sources. If KOReader legitimately changed a DB,
   preserve that fact and investigate; do not label a changed hash unchanged.
5. Remove only the verified two files and their now-empty owned plugin directory.
   The user starts KOReader again, verifies normal startup and absent menu, then
   reconnects. Confirm plugin absence and preserved DB/other plugin sources.

No Wi-Fi change, KUAL network test, phone or timed pairing session is needed.

## Phase B behavior and required Gate 2 proof

Open Tools → Quartzo → Reading Statistics manually. The source opens only the
canonical Statistics path with SQ3's explicit `ro` mode, a1,000ms busy timeout
and a short read snapshot. It validates the20221111 columns, required unique/time
indexes and foreign key, allowing additional nonunique SimpleUI indexes. Counts
are exact up to100,000; larger counts display `100000+`. Earliest/latest queries
use the validated time index. It never loads book metadata or raw history into
memory, creates/migrates a DB, writes a cursor or enables network/Wi-Fi.

Host fixtures cover empty/corrupt/missing/unknown schema, duplicate MD5 book
rows, unsafe indexes, capped history, WAL concurrent writes, busy bounds and
close-failure redaction. Linux CI additionally runs those fixtures through the
hash-pinned actual official KOReader SQ3 source and SQLite binary. Windows
skips only that native POSIX class; it still executes real synthetic SQLite
behavior through the injected test-only SQ3 API on both Lua5.1 and LuaJIT.

Actual0.0.2 PW3 acceptance completed these two separate observations, recorded
in the [Gate2 report](../../docs/evidence/statistics-read-only-pw3-2026-10-22.json).
Future changed implementations still need their applicable physical evidence:

1. Preserve the mounted DB/WAL/SHM and other-plugin source baseline. Install a
   fresh exact-source0.0.2 package. The user starts without reading a document,
   opens the read-only diagnostic, reports schema/counts and responsiveness,
   closes KOReader and reconnects. Verify exact installed source and unchanged
   DB bytes; compare observed counts against an independent read-only check.
2. Confirm normal reading still works with the probe installed. The user's
   ordinary reading may legitimately change Statistics; preserve that separate
   observation without relabeling it as unchanged bytes or plugin ingestion.

Do not write a synthetic schema or test lock into the user's Statistics DB.
Unknown-schema/write-rejection/fault tests use synthetic fixtures only. Keep
Reader mappings,sidecars and other plugins untouched. PhaseC may proceed after
the real Gate2 proof; this0.0.2 acceptance is based on the actual human/USB/
private-copy trial, not inferred from CI alone.

## Phase C bounded collector

Candidate0.0.3 adds an inactive `quartzo/collector` module. `books` enumerates
at most100 native book rows using the primary key, including rows with no events.
`collect` emits at most100 events (default50) from the validated native time
index. Both call the same `Statistics.with_snapshot` owner with explicit `ro`.
Only bounded valid32-hex MD5 values accompany native IDs; titles,authors,paths,
annotations and Reader identifiers are not projected. Groups describe only the
rows in the current batch, not an authoritative whole-library association.

Pass an explicit codec from the existing `quartzo.koplugin/quartzo/codec.lua` owner,
device ID, database-generation epoch and canonical UTC observation. The codec
constructs/validates canonical event bytes with the ratified native tuple, not
MD5. Missing book/MD5 still permits an otherwise valid native event. No context
is generated or persisted here. No clock or local timezone is inferred.

Optional inclusive `from_started_at` begins a new overlap pass. Within a pass,
`next_scan` resumes indexed `(start_time,rowid)` pagination, including groups
larger than a batch. It is transient and scoped to the supplied device/epoch/
time bound, not a durable checkpoint or ACK. Discard it when restarting a pass
or after database maintenance; overlap/deterministic identity handles repeats.
Mutable snapshots and arbitrarily backdated insertions need later lifecycle/
epoch/backfill handling; this module establishes no continuous-source receipt.

Invalid numeric fields, including native page zero, remain bounded pending-review
descriptors: exact integer text and type flags, with arbitrary TEXT/BLOB omitted.
They grant no event, receipt or right to discard the source. Unsafe scan keys
reject the whole batch without continuation. Positive durations over86400 seconds
are rejected without clamping or changing identity. Later durable state must
preserve review and cannot advance an acknowledged checkpoint across it.
Safe earlier/later dates use SQLite UTC conversion, avoiding host timezone and
32-bit `os.date` limits. Close failure suppresses all collected results. Loading
the module has no DB access; the normal plugin still invokes only diagnostics.

## Phase D delivery-state candidate

`quartzo/outbox` owns only `DataStorage:getSettingsDir()/quartzo_sync_state.sqlite3`.
It uses existing native SQ3 transactions, DELETE journal and synchronous EXTRA,
checked as3; missing state never opens in create mode. Explicit `create` refuses
an existing file, generates a16-byte OS-entropy device ID and requires an explicit
source epoch. This does not establish source generation or enroll a production
device. Restore/review a missing identity before any historical reupload; do not
silently generate a new identity after state loss. The old unused `.lua` path is
not migrated or parsed automatically. No state is created by plugin startup.

`stage` persists at most100 selected source positions atomically. It retains
original canonical bytes/observation on duplicate, blocks native-payload conflict
and deduplicates identical review cases by their bounded integer/type content.
Review case counts are not canonical event counts or evidence that damaged
source rows can be discarded. All original source rows remain Statistics-owned.
The shared1000-entry capacity stops staging without dropping old work. `pending`
returns at most100 lines and512KiB; it validates stored canonical bytes/digests.

`consume_receipt` calls the unchanged `quartzo/paired_exchange` opaque receipt
owner. Only exact per-event native/line bindings can prune, inside one native
transaction. An absent/bad/expired/foreign/raw-claim receipt cannot prune. Review
is never removed; no source-watermark advancement API exists. Full conservative
replay therefore requires retained identity and canonical native-ID deduplication,
not another local archive/index. Existing canonical Reading Activity is upstream.

Host fixtures kill their own separate writer processes before/after commit and
during prune, forcing cache spill and checking a live journal before interruption.
Both real SQLite bridge VMs execute those cases; Linux CI must also use actual
official KOReader SQ3/SQLite and OS entropy. The joined receipt test uses the
actual paired owner/shared carrier with its existing injected SDK model. It is
not new native TLS, PW3 restart, hardware power-loss or full Gate4 acceptance.
No user database, existing Reader state, Wi-Fi, real credential or live listener
is involved. Device tests wait until the user is available; never start a finite
pairing/session in advance of that availability.

### Explicit recovery snapshots (0.0.5 candidate)

Correction0.0.6 recognizes the exact original table declarations plus two implicit
PK indexes from the same declaration map used by CREATE. Original v1 CREATE bytes
remain unchanged. table_info alone omits generated columns, constraints, collation
and table options; unfamiliar declarations/internal objects now require review
before copying. This deliberately refuses even equivalent hand-edited SQL rather
than adopting or silently rewriting it. No schema parser/migration is introduced.

`queue.backup()` creates a fresh `quartzo_sync_recovery_<32hex>.sqlite3` in the
same owner directory. Native SQLite ATTACH/DELETE-journal transactions copy the
complete bounded identity/pending/review state; a second serializer or bytewise
database-file copier is not used. `inspect_backup(root, leaf, runtime)` verifies
schema, every bounded selected canonical line/digest/scope and review fields.
`restore(root, leaf, runtime)` works only when the primary file is absent, copies
the same identity and selected data, then reopens through the normal owner.
It never calls entropy to create a replacement identity.

No unknown objects/columns are silently dropped; malformed/future/foreign or
oversized data fails. Existing primary/recovery files are preserved, including
damaged state; preserve/review them before any explicit restore. A failed copy
may leave an unregistered partial artifact, which is retained and rejected by
normal open/inspection. There is no automatic fallback, overwriting, pruning or
directory-wide scan. A recovery snapshot is point-in-time: newer selected facts
need their source or another verified recovery point; restored identity does
not verify the current Statistics generation or issue canonical receipts.

## Manual recovery controls (0.0.7 candidate; device proof pending)

Tools / Quartzo / Offline reading queue opens only existing owned state. It shows
pending/review counts and inactive synchronization. Create recovery copy requires
confirmation and reopens the owner before copying. Missing state disables backup;
there is no create/reset/enroll action. Review recovery copies lists at most32
supported leaves within512 directory entries using native filesystem metadata,
without DB opens. Choose explicitly; dates are informational and never establish
Statistics generation. Unknown/symbolic/nonregular entries are preserved.

Selected-copy inspection validates its bounded schema/content. Confirmation warns
that only that point in time is recovered and requires absent primary. Reviewed
identity/counts are copied and rechecked by restore, including inside its native
transaction; original device/epoch/bytes/review remain. Existing damaged primary
cannot be replaced. This is not a whole-snapshot cryptographic binding or source
enrollment. A late interrupted copy can leave an unregistered target for review.

UI fixtures cover missing SDK/state, confirmation/progress/coalescing, copied
review preconditions and fixed failures on both Lua VMs. Linux CI additionally
uses actual official LFS for bounded directory discovery and actual SQLite for
restore. These do not establish PW3 menu rendering/restart or physical Gate4.
Do not install/start a device session while the user is unavailable. Later manual
acceptance must use a fresh source-bound artifact; older proofs do not pass0.0.7.


## Explicit source controls (0.0.8 candidate; no physical proof)

See the2026-10-24 PhaseD addendum in `IMPLEMENTATION_SPEC.md` for source review,
private schema2, conservative continuity guards and preserved schema1 recovery.
The Statistics/outbox owners are reused. New setup and same-history reconfirmation
require opaque one-use reviews and manual confirmation; startup, collection,
historical import and synchronization remain inactive. Reset/new-generation
reconciliation and actual source provenance are still gated.

Recovery confirmation now binds selected line digests, review descriptors and
source metadata as well as identity/counts, before creation and inside the copy
transaction. This local key is not a remote receipt.

`test_source.py`, `test_enrollment.py` and updated bootstrap/recovery regressions
cover those paths on both Lua engines. Native CI additionally exercises official
SQ3 INTEGER cdata and `source_native_test.lua`: actual LFS, OS entropy, v2 backup/
restore and a fresh standalone process reopen. These synthetic host proofs do
not certify a Statistics generation on PW3 or pass the grouped0.0.8 device gate.


## Reviewed collection and progress (0.0.9 candidate)

The2026-10-24 schema3 addendum in IMPLEMENTATION_SPEC.md defines opaque reviewed
collection, atomic coverage, receipt-only progress, retained review decisions,
explicit history rescan and safe empty-generation transitions. Normal startup
stays inert; foreground UI collection requires a closed book and confirmation.
Existing schema1/2 recovery is recognized without migration. Schema2 collection
is disabled until an explicit upgrade; no identity is regenerated by open/restore.

`test_collection.py` covers source/selection changes, same-second groups, partial
ACK, reviewed invalid cases, rollback, recovery and owned child SIGKILL before/
after committing events+coverage+witnesses. Native CI repeats through the actual
SQ3/SQLite ABI and shared paired owner; source_native_test.lua reopens persisted
schema3 in a fresh official standalone process. These tests do not assert actual
PW3 UI/source-provenance or physical power-loss acceptance.

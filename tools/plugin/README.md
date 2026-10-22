# Plugin and read-only Statistics probe

Phase A0.0.1 passed the actual PW3 install/start/menu/remove/restart gate. PhaseB
0.0.2 adds a separate, explicitly requested Reading Statistics diagnostic.
Synchronization remains inactive. KOReader's PluginLoader
loads `_meta.lua` into the plugin class; it is the single version owner.
`DataStorage:getSettingsDir()` supplies the two reserved Quartzo settings paths.
Neither path is opened or written. Reader, SimpleUI and Extra are not dependencies.

Run with the existing pinned test-only Lupa dependency:

```sh
python -m unittest discover -s tools/plugin -p 'test_*.py' -v
python tools/plugin/package.py --output /existing/output/directory/quartzo-bootstrap.zip
```

Packaging exclusively creates a fresh uncompressed ZIP containing
`quartzo.koplugin/main.lua`, `_meta.lua` and `quartzo/statistics.lua`. Its JSON
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

Actual PW3 acceptance remains mandatory and separates two observations:

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
Reader mappings,sidecars and other plugins untouched. PhaseC is blocked until
the real Gate2 proof is recorded. No0.0.2 physical acceptance is inferred from CI.

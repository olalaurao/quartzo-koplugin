# Plugin bootstrap

Phase A provides only a Quartzo Tools entry and a local diagnostic showing the
version and inactive Statistics/synchronization status. KOReader's PluginLoader
loads `_meta.lua` into the plugin class; it is the single version owner.
`DataStorage:getSettingsDir()` supplies the two reserved Quartzo settings paths.
Neither path is opened or written. Reader, SimpleUI and Extra are not dependencies.

Run with the existing pinned test-only Lupa dependency:

```sh
python -m unittest discover -s tools/plugin -p 'test_*.py' -v
python tools/plugin/package.py --output /existing/output/directory/quartzo-bootstrap.zip
```

Packaging exclusively creates a fresh ZIP containing `quartzo.koplugin/main.lua`
and `_meta.lua`. Its JSON output records ZIP and individual source SHA-256 hashes.
It never installs a plugin, replaces an archive or bundles diagnostics, fixtures,
credentials, contract copies or private data.

## Required PW3 Gate 1 proof

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

No Wi-Fi change, KUAL network test, phone, timed pairing session or real document
is needed. Do not touch Statistics, Reader mappings, sidecars, other plugins or
existing settings. Preserve the real source-bound observations in STATUS before
starting Phase B. No read-only Statistics probe is included in this bootstrap.

# Isolated Gate 0B client preparation

This is diagnostic tooling outside `quartzo.koplugin`, not a production transport
or a runnable Kindle package yet. The local TLS host, ephemeral credential/cert
provisioning, bounded launcher, on-device run and correlated result collection
still need implementation/proof. Nothing here selects a production backend,
loads Reader credentials, reads Statistics/sidecars, changes Wi-Fi or supplies a
canonical ACK. Do not deploy it as a plugin or call it a physical/TLS PASS.

The integrated gate matrix explicitly allows a non-production G04 spike while
G01–G03 are open. It does not unlock ingestion or later production phases.

`client.lua` supplies the diagnostic request policy and a LuaSec adapter:

- Private IPv4 HTTPS endpoint only; explicit distinct test trust files, TLS 1.2,
  peer verification, redirects disabled, 5-second socket timeout, 8-KiB input
  and 2-KiB response limit.
- The wrong-CA request uses an invalid credential and must fail for a certificate
  reason. An offline timeout cannot satisfy that step.
- Invalid and expired test credentials must receive 401 without retry. A bounded
  Retry-After is required for 429; one bounded retry covers the 5xx scenario.
- Replay must return the exact diagnostic receipt with `canonical_ack: false`
  and `persisted_canonical: false`. Canonical/unknown receipts fail.
- A short explicit expiry and a compatible clock are required. Config has no
  defaults for endpoints, credentials or trust files. No tokens/URLs/body/errors
  are logged by this module.

The adapter matches the source of the installed KOReader v2026.07.1 LuaSec
1.3.2 stack (`common/ssl/https.lua`). Explicit peer/cafile parameters avoid
depending on its packaged `verify = "none"` default. This narrow self-signed
test-certificate configuration does not implement or prove production public-CA
hostname validation. It also makes no claim about the complete Reader runtime's
TLS policy; Reader is unchanged.

## Host validation

Nine tests execute the module in a real **Lua 5.1** VM through pinned Lupa 2.8,
with HTTP/sleep/clock dependencies injected. They exercise syntax/control flow,
trust configuration, authentication/error/retry/receipt rules and byte limits.
They do not execute the ARM KOReader runtime, native LuaSec or actual network
traffic. All credentials in these tests are fixed synthetic values.

Choose a fresh dependency directory outside repositories and production vaults:

```powershell
python -m pip install --only-binary=:all: --no-deps --target '<outside-repo-test-deps>' -r tools/transport_probe/requirements-test.txt
python -c "import sys,runpy; sys.path.insert(0,r'<outside-repo-test-deps>'); runpy.run_path('tools/transport_probe/test_client.py',run_name='__main__')"
```

Validated host: Python 3.14 / Lupa 2.8 / `lupa.lua51`, Lua `_VERSION == 'Lua 5.1'`.
No package ZIP/device installer exists at this preparation checkpoint. Next add
the tiny authenticated ephemeral TLS fixture host and a separate bounded KUAL
launcher without importing KOReader's production `reader.lua` bootstrap. Require
manual authorized Wi-Fi and preserve all existing plugins/settings/native data.

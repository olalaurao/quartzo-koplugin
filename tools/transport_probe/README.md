# Isolated Gate 0B transport diagnostics

This is diagnostic tooling outside `quartzo.koplugin`, not a production transport
or a runnable Kindle package yet. The ephemeral TLS fixture host is implemented;
on-device credential/cert provisioning, a bounded launcher, the Kindle run and
correlated result collection still need implementation/proof. Nothing here selects a production backend,
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

Nine additional tests run real loopback TLS 1.2 with Python's native SSL stack:
trusted/untrusted certificates, auth/expiry/scope, 429/503/retry/replay, fixed
synthetic payload/size, private report and runtime confinement. The two language
implementations must agree on the exact false-ACK receipt. This host network
proof does not prove the Kindle's LuaSec/network path.

Choose a fresh dependency directory outside repositories and production vaults:

```powershell
python -m pip install --only-binary=:all: --no-deps --target '<outside-repo-test-deps>' -r tools/transport_probe/requirements-test.txt
python -c "import sys,unittest; sys.path.insert(0,r'<outside-repo-test-deps>'); suite=unittest.defaultTestLoader.discover('tools/transport_probe',pattern='test_*.py'); result=unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(not result.wasSuccessful())"
```

The dedicated GitHub workflow installs the pinned test-only requirement in its
isolated runner environment and runs the same discovery suite on Linux.

`host.py` is opt-in: it binds only an explicit private IPv4, accepts exactly the
small synthetic fixture bytes, and returns only diagnostic false-ACK receipts.
It generates short-lived test credentials and two independent certificates in a
fresh OS-temp directory outside all Git repositories. Private keys never belong
on Kindle, in a vault, logs or Git. The listener has a bounded lifetime, handshake
timeout and hard per-request deadline; it logs no peer/header/body/credential.
It is not a native-event receiver and never forwards data to Quartzo/Drive.

```powershell
$taskRuntime = Join-Path $env:TEMP ('quartzo-transport-session-' + [guid]::NewGuid().ToString('N'))
python tools/transport_probe/host.py --runtime-directory $taskRuntime --bind '<explicit private IPv4>' --openssl '<OpenSSL executable>'
```

Do not start this as an always-on backend or provision a real account token. The
private session JSON is runtime input; the separate host-observation JSON has
only synthetic counts/hashes and always keeps Kindle/canonical proof false.

Validated host: Python 3.14 / Lupa 2.8 / `lupa.lua51`, Lua `_VERSION == 'Lua 5.1'`.
No package ZIP/device installer exists at this preparation checkpoint. Next add
the separate bounded KUAL launcher without importing KOReader's production `reader.lua` bootstrap. Require
manual authorized Wi-Fi and preserve all existing plugins/settings/native data.

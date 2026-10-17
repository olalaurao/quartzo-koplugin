# Isolated Gate 0B transport diagnostics

This is diagnostic tooling outside `quartzo.koplugin`, not a production transport.
The ephemeral TLS host, single-use KUAL launcher, explicit bundle preparation/
fresh-folder installation and correlated observation collection are implemented.
The [actual PW3 run](../../docs/evidence/transport-probe-pw3-2026-10-16.json) passed
on clean harness source f080644a: nine attempts in about five seconds with
KOReader v2026.07.1 / Lua 5.1 / LuaSec 1.3.2. Both reports agree on TLS/auth/
error/retry/replay. Full G04 canonical durability and recovery remain open.
Nothing here selects a production backend,
loads Reader credentials, reads Statistics/sidecars, changes Wi-Fi or supplies a
canonical ACK. Do not deploy it as a plugin or call host tests a Kindle TLS PASS.

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

Extended source f080644a passed all **34 Linux cases**, including actual POSIX
deadline/single-use process checks. The successful physical run additionally
has explicit user KUAL-execution confirmation and separately correlated native
observations. The server closed afterward. Removal of the diagnostic extension
and private host session/bundle remains pending: automatic review rejected both
guarded cleanup attempts, including individual known-file deletion. No command
was run to bypass that rejection; the user received exact owned paths for manual
removal. Evidence cleanup flags remain false until absence is verified.

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
The original 18 cases passed on Windows and Linux CI. The extended suite adds
seven real-Lua harness cases and seven bundle/collection cases. Two POSIX cases
execute the actual shell launcher against an owned mock runtime, testing its
single-use guard and deadline without terminating an unrelated process. These
two require Linux `/proc`; Windows skips them and checks shell syntax separately.

## Explicit physical diagnostic run

Keep the host and Kindle on the same trusted local network. Start the opt-in
host with the explicit actual LAN IPv4 and a fresh OS-temp runtime directory.
It never enables networking or adjusts firewall settings. The session lasts
at most 30 minutes; incompatible Kindle clocks fail rather than bypass expiry
or certificate checks. If the time expires, prepare a new session.

```powershell
$taskBundle = Join-Path $env:TEMP ('quartzo-transport-bundle-' + [guid]::NewGuid().ToString('N'))
python tools/transport_probe/bundle.py prepare --session $taskRuntime --output $taskBundle
python tools/transport_probe/bundle.py install --bundle $taskBundle --kindle-root 'D:\'
```

Installation verifies mounted `koreader/git-rev` is exactly `v2026.07.1`, requires
an existing plain `extensions` directory and creates only the fresh
`extensions/quartzo-transport-probe` folder. An existing folder is never
overwritten or recursively removed. Only allowlisted source, synthetic payload,
public certificates and ephemeral test credentials are copied, with byte hashes
verified. Server private keys stay on the host. No production token is used.
The bundle and its manifest are private runtime input, never Git/public evidence.

Safely disconnect USB, **manually** turn on Wi-Fi if needed, then open KUAL →
Quartzo transport diagnostic → Run synthetic TLS test. This does not launch
KOReader's production `reader.lua`, stop any framework, open Statistics or alter
Reader/SimpleUI/settings. The isolated Lua process loads only `setupkoenv`, JSON
and socket/TLS modules. Its outer shell watchdog limits the process to 120 seconds
plus two seconds for termination, checks process start identity before killing,
and never uses killall. Per-socket timeout is five seconds. `run.lock` makes this
session single-use even after failure. Output/errors are fixed public codes;
raw native stdout/stderr are discarded.

Reconnect USB after about 15 seconds (or at most 125 seconds on an unresponsive
network). The CLI host stops after the expected complete sequence, expiry or a
local `stop-requested` file in its private runtime directory. After it closes,
collect the two observations:

```powershell
python tools/transport_probe/bundle.py collect --bundle $taskBundle --kindle-root 'D:\' --host-report (Join-Path $taskRuntime 'host-observation.json') --output '<fresh sanitized report path>'
```

Collection requires matching run IDs, exact unchanged installed bytes, expected
runtime versions, completed launcher, all nine client attempts/scenarios and
host counters/TLS/no errors. Output is allowlisted and omits credentials and
endpoints. Even matching synthetic observations retain
`physical_execution_attested: false`: actual KUAL execution must be witnessed/
confirmed and recorded separately with source hashes; fixture files alone cannot
attest a physical device. Canonical ACK/persistence always remain false. This
diagnostic still does not pass the full G04 durable-ACK exit criterion.

After collecting, remove only the exact diagnostic folder and the owned private
host session/bundle after verifying paths and retaining sanitized evidence.
There is deliberately no recursive device cleanup command. Retrying needs a
fresh session and explicit removal of the previous owned extension; never edit
existing Reader, KOReader, SimpleUI or Statistics folders.

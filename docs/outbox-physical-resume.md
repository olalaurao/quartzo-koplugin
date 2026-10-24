# Current handoff, 2026-10-24: grouped validation still pending

This section supersedes the installation, candidate and pending-test statements
in the historical snapshots below. The latest observed installed plugin is
0.0.7; no 0.0.8/0.0.9 installation or physical acceptance is claimed. No device,
phone, listener, credential or timed session is in use while the user is
unavailable. Gate 4 and Phase D remain open.

The current candidate is 0.0.9, runtime commit
`d5bab063dfea59aa82cbf75ebe700d48baa087c7`: eight runtime files, 130544-byte ZIP,
SHA-256 `0d3eb413003fb4555ec15c2d834f3aa24a78529d3519428581f41d791641720b`.
Native CI 40109125180 passed 585 cases without skips. Documentation head
`9e6532003b300b0a6e7019662d872aeee6cb9af2` retains exactly those runtime blobs;
its CI 40109410581 also passed 585 cases. The private manifest/current pointer
identifies the archive. Earlier candidate archives are provenance, not installers.
Any later runtime change requires fresh exact-source proof/package verification.

Already accepted and not to be repeated without a relevant change: bootstrap
install/removal, read-only Statistics and normal reading, six offline native
stop/recovery cases, 0.0.7 empty-state UI/restart, and the grouped actual native
outbox/Android receipt-loss/retry/partial/review trial. The latter passed on its
recorded source: [paired evidence](evidence/outbox-paired-pw3-2026-10-23.json).
It is not proof of the new collection/progress/source lifecycle implementation.

## Block A: current plugin UI and real source, Kindle only

Prepare everything before asking the user to disconnect USB. Reconfirm the
current device/version and preserve a fresh private Statistics/settings/plugin
baseline, current own state and rollback. Read SQLite only on private copies.
Inspect existing own state/recovery artifacts before proposing enrollment;
missing primary with prior identity evidence must enter recovery, never silently
create a new identity. Verify the exact candidate bytes after installation.

Group these observations into one prepared trial, with the book closed and the
existing Wi-Fi state unchanged: Diagnostics 0.0.9; Reading source review and
explicit enrollment only when its preconditions hold; one confirmed Collect
reading into queue action; queue/review counts and inactive synchronization;
Create recovery copy and review of that copy; close/reopen KOReader and confirm
the same source identity/queue/copy remains usable. Collection includes existing
history and may safely pause at its 1000-entry queue cap; this is not complete
history import. Do not clear review entries or repeatedly collect to make a test
appear complete. Do not reset/replace Statistics or delete an existing primary
to simulate failure. Stop and preserve evidence if any source check fails.

After USB returns, independently verify the selected native IDs/payloads and
candidate scan progress on private copies, exact private schema and recovery
bytes, unchanged Statistics/settings/other plugins, and actual timings. No ACK
watermark may advance from collection. Separate any intentional normal reading
from this no-reading baseline. Synthetic native tests do not substitute for
these observed PW3 measurements or normal-use responsiveness.

## Block B: isolated source lifecycle and receipt frontier

The existing offline bundle now has an accepted `--source-lifecycle` mode at
exact `b35f0606e0e61aea259210a2adb844ad036b41e5`, prepared privately and not
installed. CI40113545022 passed 589 cases / no skips, including actual owned-child
collection stops and independent validation of 16 synthetic files. See
[host evidence](evidence/outbox-source-lifecycle-host-2026-10-24.json).
Use that mode consistently for prepare/install/collect; use the recorded exact
bundle, not an older six-stop bundle with the same extension name. No execution
is requested while the user is unavailable. This finite block needs only Kindle,
with Wi-Fi unchanged and no pairing session. The existing KUAL menu remains
Quartzo offline outbox diagnostic -> Run synthetic offline outbox test.

Use one newly owned synthetic diagnostic root to exercise the changed schema-3
collection/progress path on the PW3: source witness promotion from empty,
same-second continuation, review blocking/exclusion, schema-2 upgrade with its
verified backup, interruption/rollback, source-change refusal and reviewed empty
new-generation transition. Never mutate actual Statistics or seed synthetic facts
into the user's canonical outbox. These cases already pass native host fixtures;
their physical scope and performance remain pending. Do not repeat unchanged
transport-only or schema-1 stops under a new name.

Only if needed for changed schema-3 ACK/frontier behavior, extend that same
prepared trial to the isolated Android receiver and group lost receipt, replay
and partial acceptance. Reuse the accepted APK when its critical source blobs
match; rebuild only for relevant carrier changes. Start a finite pairing session
only once both devices and the human action are available. Revoke it and verify
cleanup before acceptance. Hardware power loss, lost-identity/nonempty-generation
reconciliation, clock/day accuracy, production transport and release/performance
gates remain separate; neither block closes them by implication.

All sections below are retained historical source-bound snapshots.

# Latest UI/reading acceptance, 2026-10-23

The user completed the0.0.7 missing-state UI and normal reading/restart trial.
USB/private-copy verification passed: empty-state inspection changed no tracked
bytes; normal reading added2nativeeventkeys, removed0 and changed0priorvalues.
All352Lua sources and reservedQuartzo state stayed intact. See
[physical UI/reading scope](evidence/outbox-ui-pw3-2026-10-23.json). Candidate0.0.7
remains installed with exact0.0.2 rollback retained privately. No timed session
is running and no new KUAL execution is requested. Earlier pending observations
below are historical. Populated recovery UI, verified source-generation lifecycle
and paired canonical receipt/prune/replay still need implementation/proof. The old
fixed synthetic paired fixture must not stand in for a generated outbox identity.

# Current actual-device state, 2026-10-23

The actual PW3 offline synthetic diagnostic passed six native stage/backup/restore
process-stop cases; collection/private-copy verification and scoped cleanup are
complete. See [bounded physical evidence](evidence/outbox-offline-pw3-2026-10-23.json).
Statistics/settings and 347 tracked Lua sources were unchanged during that test.
This is not source enrollment, paired ACK, hardware power loss or full Gate4 PASS.

The exact-source0.0.7 candidate is now installed for an empty-state UI trial,
with verified0.0.2 rollback retained privately. The human request is pending:
Diagnostics must show0.0.7; Offline reading queue must show no queue/inactive sync,
disabled Create recovery copy and no supported recovery copies, without reading
a book or changing Wi-Fi. After USB reconnection compare the private installed
baseline before claiming acceptance. No phone or timed session is needed.
Do not repeat the completed offline diagnostic or replace current installation
with an older artifact. Populated recovery UI and normal reading/restart need
their own evidence; current-generation enrollment and paired receipt remain open.

The preparation snapshots below retain historical source-bound context. Their
availability/installation statements describe those earlier observations only.

# Phase D physical resumption â€” not an active test request

## Current candidate: 0.0.7 manual recovery UI (not installed)

The current candidate retains manual recovery UI and shares review validation
with staging so an accepted descriptor cannot make its recovery copy unreadable.
Exact 4c99c7a passed 409 host/native cases without skips; see the
[current host evidence](evidence/outbox-review-validation-host-2026-10-23.json).
Fresh UI ZIP/offline bundles replace the historical 336a7a8 preparations; none
are installed. Use the private handoff manifest and verify the final source/CI.
Revalidate the final source/CI before any future trial; older0.0.6 and offline
proofs remain historical. See
STATUS and the private handoff for the current source-bound archive/manifest.
There is no installation, active request, phone session or timer in this block.

When availability returns, first revalidate the source/head/CI and preserve the
installed0.0.2 rollback/settings/Statistics/other-plugin baseline. A fresh UI trial
must confirm the menu, missing-state behavior, responsiveness, unchanged Wi-Fi
and normal reading/restart. It must not create an identity for missing state.
Populated backup/restore UI needs an explicitly isolated synthetic harness or an
already proven owned state; never seed the user's canonical settings with fake
reading facts. Existing/damaged primary must be preserved. Review changes must
stop restore, and late failures must retain unregistered targets for review.
Actual source enrollment, current-generation verification and paired receipt
proof remain separate obligations. Host-only UI/SQLite/LFS tests do not pass them.

The older source-bound offline procedure below is retained as a dependency/test
outline. Regenerate its bundle from the current accepted source before use;
never install an earlier artifact merely because its older host test passed.

The user cannot operate the Kindle/phone now. There is no installed0.0.7 trial,
pairing, listener, timer or one-time credential waiting. Do not ask the user to
run a menu that has not been installed. Existing development0.0.2 stays unchanged.
The [host report](evidence/outbox-host-2026-10-22.json) is not physical Gate4 PASS.

## Prepared offline block, awaiting availability

Recovery source0.0.6 supersedes the original8b73c6e candidate: it rejects unfamiliar
constraints/generated columns/internal schema objects instead of silently dropping
them during recovery. Exact9f7c3a7 native CI passed373 cases/no skips. See the
[source-bound correction](evidence/outbox-schema-preservation-host-2026-10-22.json).
The older prepared8b73c6e directory is historical and MUST NOT be installed for the
current trial. Use the fresh artifact/manifest recorded in the latest private
handoff, and verify the exact accepted source before installation. No device is
available or accessed during this host correction; installed0.0.2 is untouched.

`tools/plugin/outbox_probe_bundle.py prepare` now prepares committed source bytes
for a fresh `quartzo-outbox-probe` extension through the existing artifact owner.
Its exactb081938 [native host proof](evidence/outbox-offline-probe-host-2026-10-22.json)
passed364 cases without skips. This extension is NOT installed; no KUAL action is
currently requested. It does not replace installed0.0.2 or access Statistics.

Once the user can operate the Kindle, the engineer must revalidate exact source/
CI, KOReader baseline and preserved source/settings inventory, then install only
the new diagnostic extension with a fresh installation observation. It needs no
phone or Wi-Fi and has no timed network session. Only after installation is
verified, the single human step is to disconnect USB safely, execute KUAL →
Quartzo offline outbox diagnostic → Run synthetic offline outbox test, wait up to
125 seconds and reconnect USB. Do not ask the user to execute this now.

The engineer then collects with that same prepared bundle and installation
observation. The shared launcher must report completed; all six native stop cases
and seven native fingerprints must match. Collection checks exact fixed synthetic
identities/bytes/review on bounded PRIVATE COPIES, never on mounted user databases.
Every partial/journal/unknown file is preserved on failure; do not rerun in place.
Two expected version0 partial destinations may be zero bytes after rollback and
remain unregistered. A healthy empty outbox cannot pass in their place. Archive
evidence, compare the preserved unrelated baseline, then clean up only the owned
diagnostic when authorized and verify its absence. This is an offline sub-block;
it does not close Gate4 or prove Android canonical delivery/source enrollment.

## Before preparing a device trial

1. Confirm user/device availability, current Git head and all exact-head checks.
   Runtimeb90272c/tested92af1bd and the48,563-byte archive are source-bound candidates, not a
   release. If source changes, regenerate the package/proof rather than reuse a
   stale installer or reinterpret old observations.
2. Reconfirm KOReader v2026.07.1 kindlepw2/PW3 and mounted source hashes. Preserve
   the installed0.0.2 rollback bytes, Statistics DB/WAL/SHM, own reserved settings
   and existing Statistics/Reader/SimpleUI/Extra sources. Independent SQL belongs
   on private offline copies; never host-open the mounted Statistics database.
3. Prepare a fresh, source-bound isolated synthetic delivery-state trial. Use the
   same outbox/codec/paired owners and actual native SDK; never substitute a
   diagnostic receipt issuer or grant accepted positions from parsed claims.
   Its writable root must be a newly owned test location, separate from actual
   Statistics and any existing production outbox. Preserve partial evidence.
4. Revalidate/rebuild the isolated Android carrier against its exact critical
   source blobs before any live pairing. New source/identity context must be
   explicitly supported; do not relabel an older APK's fixed fixture identity as
   the newly generated native device ID. Prepare all host artifacts first, and
   start the finite session only when the user can execute the required step.

## Required physical evidence

- Offline first: explicit creation with actual entropy, selected synthetic bytes
  and review persist across close/restart; duplicate stage retains the first
  bytes; source/other-plugin baseline stays intact. No phone or Wi-Fi needed.
- Interruption: isolate and stop only the test's own native writer process before
  and after stage/prune commits, including a real live journal. Do not kill the
  user's normal KOReader process or induce battery/power loss. Reopen through
  the normal store and verify old/committed state without automatic reset.
- Explicit recovery: include backup/restore interruption before/after commit,
  same device/epoch and exact selected bytes/review after restore. Preserve an
  existing damaged primary and every partial recovery artifact; an incomplete
  destination stays unregistered, with the good backup retained for review.
  Do not substitute a new identity or silently select an older recovery point.
- Paired delivery: the normal scoped Android canonical receiver must commit the
  selected native facts. Discard a successful receipt deliberately, restart the
  source trial and resend identical IDs/bytes with a fresh request. Independently
  compare canonical bytes; only exact trusted per-event receipts may prune.
- Partial/error acceptance: retain unacknowledged neighbors and review through
  busy/offline/rejected/expired/closed sessions. No source checkpoint may pass
  unresolved review. DB/state loss must fail closed or restore the same identity,
  never silently re-identify historical events under a new device/epoch.

The engineer collects actual USB/private-copy/native reports after the human
execution; host fixture matches cannot attest hardware. Record synthetic source
times separately from user reading. No user book metadata, real rows, credential,
network address, serial or private backup is published. Verify normal completion,
revocation/listener absence, exact rollback and scoped cleanup before acceptance.

Source-generation enrollment, reset/current-source UX, physical recovery-UI proof
and full lifecycle integration remain explicit implementation obligations, not waived by this storage trial.
Do not advance PhaseE or mark Gate4/full goal complete from the host report.

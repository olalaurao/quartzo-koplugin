#!/bin/sh
# Single-use synthetic diagnostic; no Wi-Fi, framework, Reader or data changes.
set -u
umask 077
OWNED=/mnt/us/extensions/quartzo-transport-probe
cd "$OWNED" || exit 1
# Kept after failure/success: provisioning a fresh session is required to retry.
mkdir run.lock 2>/dev/null || exit 1
printf '%s\n' 'started' > launcher-status.txt
[ "$(cat /mnt/us/koreader/git-rev 2>/dev/null)" = 'v2026.07.1' ] || {
    printf '%s\n' 'baseline_mismatch' > launcher-status.txt; exit 1;
}
cd /mnt/us/koreader || exit 1
command -v awk >/dev/null 2>&1 && [ -r /proc/self/stat ] || {
    printf '%s\n' 'watchdog_unavailable' > "$OWNED/launcher-status.txt"; exit 1;
}
./luajit "$OWNED/kindle.lua" >/dev/null 2>&1 &
PROBE_PID=$!
PROBE_START=$(awk '{print $22}' "/proc/$PROBE_PID/stat" 2>/dev/null)
# Per-socket timeouts are insufficient against a trickling peer. Bound the
# entire disposable process. No killall, production PID or framework operation.
(
    DEADLINE_SECONDS=120
    ELAPSED_SECONDS=0
    while [ "$ELAPSED_SECONDS" -lt "$DEADLINE_SECONDS" ]; do
        sleep 1
        ELAPSED_SECONDS=$((ELAPSED_SECONDS + 1))
        kill -0 "$PROBE_PID" 2>/dev/null || exit 0
    done
    [ -n "$PROBE_START" ] && [ "$(awk '{print $22}' "/proc/$PROBE_PID/stat" 2>/dev/null)" = "$PROBE_START" ] && kill -TERM "$PROBE_PID" 2>/dev/null
    sleep 2
    [ -n "$PROBE_START" ] && [ "$(awk '{print $22}' "/proc/$PROBE_PID/stat" 2>/dev/null)" = "$PROBE_START" ] && kill -KILL "$PROBE_PID" 2>/dev/null
) >/dev/null 2>&1 &
GUARD_PID=$!
trap 'kill "$GUARD_PID" 2>/dev/null' 0
wait "$PROBE_PID"
RESULT=$?
kill "$GUARD_PID" 2>/dev/null
wait "$GUARD_PID" 2>/dev/null
if [ "$RESULT" -eq 0 ]; then
    printf '%s\n' 'completed' > "$OWNED/launcher-status.txt"
else
    printf '%s\n' 'failed_or_timed_out' > "$OWNED/launcher-status.txt"
fi
exit "$RESULT"

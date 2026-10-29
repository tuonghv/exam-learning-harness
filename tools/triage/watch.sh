#!/usr/bin/env bash
# watch.sh - keep watching .triage/inbox/ and run orchestrate.sh when a message lands (phase 71).
# The watcher itself costs nothing: it blocks in inotifywait (inotify-tools) or, without it, checks
# the inbox every --poll seconds. Only orchestrate.sh spends tokens (one call per message).
#
# usage: tools/triage/watch.sh [--poll SECS]      (runs until killed; one watcher per .triage/)
# env:   TRIAGE_DIR (default <repo>/.triage), TRIAGE_BACKOFF (seconds to wait after a service
#        failure such as a rate limit, default 900), TRIAGE_NO_INOTIFY=1 (force polling),
#        plus everything orchestrate.sh reads (CLAUDE_BIN, TRIAGE_MODEL, ...)
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
TDIR="${TRIAGE_DIR:-$REPO/.triage}"
POLL=5
BACKOFF="${TRIAGE_BACKOFF:-900}"
case "${1:-}" in
  --poll) POLL="${2:?--poll needs seconds}" ;;
  '') ;;
  *) sed -n '2,9p' "$0" >&2; exit 2 ;;
esac
case "$POLL$BACKOFF" in *[!0-9]*) echo "watch: --poll and TRIAGE_BACKOFF must be whole seconds" >&2; exit 2;; esac

mkdir -p "$TDIR/inbox" "$TDIR/logs"
PIDF="$TDIR/.watch.pid"
if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "watch: already running (pid $(cat "$PIDF"))" >&2; exit 11
fi
echo $$ > "$PIDF"
stop_children() {  # the inotifywait pipeline and naps; a running orchestrate.sh finishes its message
  local c; for c in $(pgrep -P $$); do pkill -P "$c" inotifywait 2>/dev/null; kill "$c" 2>/dev/null; done
}
trap 'rm -f "$PIDF"; stop_children' EXIT
trap 'exit 0' INT TERM

log() { printf '%s\t%s\n' "$(date +%Y-%m-%dT%H:%M:%S%z)" "$*" >> "$TDIR/logs/watch.log"; echo "watch: $*"; }
nap() { sleep "$1" & wait $!; }          # interruptible, so a stop never waits out a backoff
pending() { find "$TDIR/inbox" -maxdepth 1 -type f ! -name '.*' | grep -q .; }

drain() {  # run orchestrate.sh until the inbox is empty; back off on service failures
  local rc
  while pending; do
    # 72.5g: a run hold (orchestrate.sh wrote $TDIR/HOLD) means no call until a human releases it;
    # log once, then wait for the release (no BACKOFF loop, the inbox stays as it is)
    if [ -e "$TDIR/HOLD" ]; then
      [ -n "${HOLD_LOGGED:-}" ] || { log "run held ($TDIR/HOLD): no drain until tools/triage/orchestrate.sh --release run"; HOLD_LOGGED=1; }
      return 0
    fi
    HOLD_LOGGED=
    rc=0; bash "$HERE/orchestrate.sh" || rc=$?
    case "$rc" in
      0) ;;
      11) nap 5 ;;                                              # a manual run holds the lock
      3) log "service failure (auth/rate limit); retry in ${BACKOFF}s"; nap "$BACKOFF" ;;
      *) log "orchestrate.sh exit $rc; retry in ${BACKOFF}s"; nap "$BACKOFF" ;;
    esac
  done
}

if [ "${TRIAGE_NO_INOTIFY:-0}" != 1 ] && command -v inotifywait >/dev/null 2>&1; then
  log "started (inotify) on $TDIR/inbox"
  drain                                   # messages dropped while the watcher was down
  # -m keeps one watch open: events that arrive during a drain queue in the pipe, so none is missed
  # run the pipeline in the background and `wait`: a foreground pipeline would hold off the TERM trap forever
  inotifywait -m -q -e close_write -e moved_to --format '%f' "$TDIR/inbox" | while read -r _; do drain; done &
  wait $!
  log "inotifywait ended"; exit 1
fi
log "started (poll every ${POLL}s; install inotify-tools for instant pickup) on $TDIR/inbox"
while :; do drain; nap "$POLL"; done

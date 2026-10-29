#!/usr/bin/env bash
# Watch one launched role through its handoff file and print only the events the
# coordinator acts on (skill role-monitor, REQ-0024). Run it as a Monitor command.
#   watch-role.sh <TASK-ID> <role> <expect_min>   watch until COMPLETE or 2x Expect
#   watch-role.sh status <TASK-ID>                print the task's role log
# Events (one line each): START, PROGRESS <line 1>, IDLE, STALL <facts>, DONE, TIMEOUT.
# Env for tests: WATCH_POLL (s, default 10), WATCH_IDLE (s, default 300),
# WATCH_EXPECT_SECS (overrides expect_min * 60).
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"

usage() { echo "usage: $0 <TASK-ID> <designer|coder|tester|verifier> <expect_min> | status <TASK-ID>" >&2; exit 2; }

mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }

if [ "${1:-}" = "status" ]; then
  [ $# -eq 2 ] || usage
  log="$root/work/$2/roles.log"
  if [ -f "$log" ]; then cat "$log"; else echo "no role runs logged for $2"; fi
  exit 0
fi

[ $# -eq 3 ] || usage
task=$1; role=$2; expect_min=$3
case "$role" in
  designer) hf=design.md ;; coder) hf=code.md ;; tester) hf=test.md ;; verifier) hf=verify.md ;;
  *) usage ;;
esac
case "$expect_min" in ''|*[!0-9]*) usage ;; esac

dir="$root/work/$task"
handoff="$dir/handoff/$hf"
log="$dir/roles.log"
poll=${WATCH_POLL:-10}
idle_after=${WATCH_IDLE:-300}
expect=${WATCH_EXPECT_SECS:-$((expect_min * 60))}
mkdir -p "$dir/handoff"

now() { date +%s; }
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
record() { echo "$(stamp) $role $*" >> "$log"; }

# Newest write under work/<task> (handoff, patches, evidence, scratch) and the
# number of changed files in the git tree: the activity signals for IDLE/STALL.
last_write() {
  local newest=0 f m
  while IFS= read -r f; do
    m=$(mtime "$f"); [ "$m" -gt "$newest" ] && newest=$m
  done < <(find "$dir" -type f ! -name roles.log 2>/dev/null)
  echo "$newest"
}
tree_changes() { git -C "$root" status --porcelain 2>/dev/null | wc -l | tr -d ' '; }
# The coordinator's to-do block on DONE/STALL/TIMEOUT (team-status.sh); never fails the watch.
team() { "$root/.claude/scripts/team-status.sh" "$task" 2>/dev/null | sed 's/^/  /' || true; }
line1() { if [ -f "$handoff" ]; then head -1 "$handoff"; else echo "no handoff yet"; fi; }

start=$(now)
record "start expect=${expect_min}m"
echo "START $task $role expect=${expect_min}m handoff=work/$task/handoff/$hf"

prev_line="" prev_changes=$(tree_changes) last_act=$start idle_sent=0 stall_sent=0
while true; do
  t=$(now)
  l=$(line1)
  # A handoff left by an earlier run counts only once rewritten.
  fresh=0; [ -f "$handoff" ] && [ "$(mtime "$handoff")" -ge "$start" ] && fresh=1
  if [ -f "$handoff" ] && [ "$l" != "$prev_line" ]; then
    prev_line=$l
    if [ $fresh -eq 1 ]; then echo "PROGRESS $role: $l"; else echo "PROGRESS $role: $l (stale, earlier run)"; fi
  fi
  case "$fresh:$l" in
    1:*COMPLETE*)
      record "done after $(( (t - start) / 60 ))m"
      echo "DONE $role after $(( (t - start) / 60 ))m: read the reply, then work/$task/handoff/$hf only if needed"
      team; exit 0 ;;
  esac

  w=$(last_write); c=$(tree_changes)
  if [ "$w" -gt "$last_act" ] || [ "$c" != "$prev_changes" ]; then
    [ "$w" -gt "$last_act" ] && last_act=$w
    [ "$c" != "$prev_changes" ] && last_act=$t
    prev_changes=$c; idle_sent=0
  fi
  if [ $idle_sent -eq 0 ] && [ $((t - last_act)) -ge "$idle_after" ]; then
    idle_sent=1
    echo "IDLE $role: no writes for $(( (t - last_act) / 60 ))m (line 1: $l)"
  fi
  if [ $stall_sent -eq 0 ] && [ $((t - start)) -ge "$expect" ]; then
    stall_sent=1
    record "stall expect passed"
    echo "STALL $role: Expect ${expect_min}m passed; line 1: $l; last write $(( (t - last_act) / 60 ))m ago; changed files in tree: $c"
    team
  fi
  if [ $((t - start)) -ge $((2 * expect)) ]; then
    record "timeout at 2x expect"
    echo "TIMEOUT $role: 2x Expect with no COMPLETE (line 1: $l); root-cause per skill role-monitor"
    team; exit 0
  fi
  sleep "$poll"
done

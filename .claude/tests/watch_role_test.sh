#!/usr/bin/env bash
# Regression test for scripts/watch-role.sh (REQ-0024), in a throwaway git repo holding a copy
# of the script - the real repo's work/ is never touched. Short timings via WATCH_* env.
# Run: bash .claude/tests/watch_role_test.sh
set -Eeuo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }
check() { local name="$1"; shift; if "$@"; then ok "$name"; else bad "$name"; fi; }
has() { grep -q -- "$1" "$2"; }           # has <pattern> <file>

R="$WORK/repo"
mkdir -p "$R/.claude/scripts" "$R/work/TASK-900/handoff"
cp "$KIT/scripts/watch-role.sh" "$KIT/scripts/team-status.sh" "$R/.claude/scripts/"
git -C "$R" init -q
W="$R/.claude/scripts/watch-role.sh"
export WATCH_POLL=1

# 1. COMPLETE written during the run -> PROGRESS then DONE, exit 0, logged.
out="$WORK/complete.out"
( sleep 2; printf 'PROGRESS: IN_PROGRESS\nSKILLS: bash\n' > "$R/work/TASK-900/handoff/code.md"
  sleep 2; printf 'PROGRESS: COMPLETE\nSKILLS: bash\n' > "$R/work/TASK-900/handoff/code.md" ) &
WATCH_EXPECT_SECS=30 "$W" TASK-900 coder 1 > "$out"; rc=$?
wait
check "complete: exit 0" [ "$rc" -eq 0 ]
check "complete: START line" has '^START TASK-900 coder' "$out"
check "complete: PROGRESS IN_PROGRESS" has '^PROGRESS coder: PROGRESS: IN_PROGRESS' "$out"
check "complete: DONE line" has '^DONE coder' "$out"
check "complete: no STALL" bash -c "! grep -q STALL '$out'"
check "complete: team block after DONE" has '^  HANDOFF: code=COMPLETE' "$out"
check "complete: roles.log start+done" bash -c "grep -q 'coder start' '$R/work/TASK-900/roles.log' && grep -q 'coder done' '$R/work/TASK-900/roles.log'"

# 2. Stale COMPLETE from an earlier run is not DONE; no writes -> IDLE, STALL, TIMEOUT.
out="$WORK/stall.out"
printf 'PROGRESS: COMPLETE\nSKILLS: x\n' > "$R/work/TASK-900/handoff/design.md"
touch -t 202001010000 "$R/work/TASK-900/handoff/design.md"
WATCH_IDLE=2 WATCH_EXPECT_SECS=3 "$W" TASK-900 designer 1 > "$out"
check "stall: stale PROGRESS marked" has '^PROGRESS designer: PROGRESS: COMPLETE (stale, earlier run)' "$out"
check "stall: team block after STALL" has '^  TASK: TASK-900' "$out"
check "stall: stale COMPLETE ignored" bash -c "! grep -q '^DONE' '$out'"
check "stall: IDLE line" has '^IDLE designer: no writes' "$out"
check "stall: STALL with facts" has '^STALL designer: Expect 1m passed; line 1: PROGRESS: COMPLETE; last write' "$out"
check "stall: TIMEOUT at 2x" has '^TIMEOUT designer' "$out"
check "stall: roles.log timeout" has 'designer timeout' "$R/work/TASK-900/roles.log"

# 3. status prints the log; unknown task says so; bad args exit 2.
check "status: prints log" bash -c "'$W' status TASK-900 | grep -q 'designer stall'"
check "status: empty task" bash -c "'$W' status TASK-901 | grep -q 'no role runs logged'"
set +e; "$W" TASK-900 painter 1 >/dev/null 2>&1; rc=$?; set -e
check "args: unknown role exit 2" [ "$rc" -eq 2 ]
set +e; "$W" TASK-900 coder x >/dev/null 2>&1; rc=$?; set -e
check "args: non-numeric expect exit 2" [ "$rc" -eq 2 ]

# 4. team-status.sh: every line the coordinator must act on.
mkdir -p "$R/.claude/state" "$R/work/TASK-900/patches"
printf '%s\n' '{"task_id":"TASK-900","state":"IMPLEMENTING","next":"apply patches","blocked":{"reason":"guard refuses git apply","attempts":1}}' > "$R/.claude/state/task.json"
printf '%s\n' '[{"task_id":"TASK-900","status":"active"},{"task_id":"TASK-899","status":"done"}]' > "$R/.claude/state/backlog.json"
printf 'hello\n' > "$R/f.txt"; git -C "$R" add f.txt; git -C "$R" -c user.email=t@t -c user.name=t commit -qm init
cat > "$R/work/TASK-900/patches/a.patch" <<'P'
--- a/f.txt
+++ b/f.txt
@@ -1 +1 @@
-hello
+world
P
printf 'PROGRESS: IN_PROGRESS\nSKILLS: bash\nQUESTION: apply a.patch?\n' > "$R/work/TASK-900/handoff/code.md"
printf 'x\n' > "$R/new.txt"
echo '{"id":"F900-1"}' > "$R/work/TASK-900/findings.jsonl"
ts="$WORK/team.out"; "$R/.claude/scripts/team-status.sh" > "$ts"
check "team: TASK line with next" has '^TASK: TASK-900 IMPLEMENTING | next: apply patches' "$ts"
check "team: COMMIT lists state + new file" bash -c "grep -q '^COMMIT: .*includes .claude/state' '$ts' && grep -q 'new.txt' '$ts'"
check "team: PATCH pending" has '^PATCH: pending: a.patch' "$ts"
check "team: QUESTION surfaced" has '^QUESTION (code.md): QUESTION: apply a.patch?' "$ts"
check "team: FINDINGS count" has '^FINDINGS: 1 .*F900-1' "$ts"
check "team: BACKLOG open only" bash -c "grep -q '^BACKLOG: TASK-900\$' '$ts'"
check "team: BLOCKED line" has '^BLOCKED: guard refuses git apply (attempts 1)' "$ts"
git -C "$R" apply "$R/work/TASK-900/patches/a.patch"
check "team: applied patch not reported" bash -c "! '$R/.claude/scripts/team-status.sh' | grep -q '^PATCH'"

printf 'nope\n' > "$R/f.txt"; echo a.patch > "$R/work/TASK-900/patches/APPLIED"
check "team: APPLIED list beats a follow-up edit" bash -c "! '$R/.claude/scripts/team-status.sh' | grep -q '^PATCH'"

echo "watch_role_test: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]

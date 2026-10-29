#!/usr/bin/env bash
# checklist.sh --gate --task X and workflow-check --task X judge only X's rows (TASK-098 F3):
# with two active tasks, a DONE task is not failed for a row owned by the other active task.
# Run: bash .claude/tests/checklist_task_test.sh      (KIT_DIR=<kit> tests another copy)
set -Eeuo pipefail
KIT="${KIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }
# expect <name> <want-rc> <want-substring|""> <cmd...>
expect() {
  local name="$1" want_rc="$2" want_out="$3" out rc=0; shift 3
  out="$("$@" 2>&1)" || rc=$?
  if [ "$rc" -ne "$want_rc" ]; then bad "$name (rc=$rc, want $want_rc)"; printf '%s\n' "$out" | head -n 8; return; fi
  if [ -n "$want_out" ] && ! printf '%s' "$out" | grep -qF -- "$want_out"; then bad "$name (output lacks '$want_out')"; printf '%s\n' "$out" | head -n 8; return; fi
  ok "$name"
}

R="$WORK/r"
mkdir -p "$R/.claude/state" "$R/docs/design"
cp -r "$KIT/scripts" "$R/.claude/scripts"
find "$R/.claude" -name __pycache__ -prune -exec rm -rf {} +
# row 1 is shared by 70 and 75 and owned by 75 (the highest number)
cat > "$R/docs/design/phase-75-x.md" <<'MD'
| # | Item | Task / doc | Done |
|---|---|---|---|
| 1 | shared row | 070 + 075 | |
MD
printf '{"schema": 2, "active": [{"task_id": "TASK-70"}, {"task_id": "TASK-75"}]}\n' > "$R/.claude/state/task.json"
printf '{"schema": 2, "task_id": "TASK-70", "state": "DONE"}\n' > "$R/.claude/state/task.TASK-70.json"
printf '{"schema": 2, "task_id": "TASK-75", "state": "DESIGN"}\n' > "$R/.claude/state/task.TASK-75.json"
CK() { (cd "$R" && bash .claude/scripts/checklist.sh "$@"); }

expect "T1 DONE task ignores the other active task's open row" 0 "" CK --gate --task TASK-70
expect "T2 the owner still fails on its own open row" 1 "checklist row 1 still open" CK --gate --task TASK-75
expect "T3 bad --task id refused" 1 "bad --task" CK --gate --task '../x'
expect "T4 no --task: all-active view unchanged (owner 75 fails)" 1 "checklist row 1 still open" CK --gate
echo "SUMMARY(checklist_task): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

#!/usr/bin/env bash
# SessionStart: stdout becomes session context. Prints the resume point from
# .claude/state (active task, next action, last phase-log heading, queued
# backlog, uncommitted state, gate verdict) so no session starts by reading
# task.json/phase-log.md by hand. Never blocks: always exits 0.
set -uo pipefail
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
S="$ROOT/.claude/scripts"
[ -f "$ROOT/.claude/state/task.json" ] || exit 0

# REQ-0061 lead (97.13): a fresh start re-checks task leads (tasks.sh recover); resume/compact do not
SRC=""
if [ ! -t 0 ]; then
  SRC="$(python3 -c 'import json,sys
try:
    print(json.load(sys.stdin).get("source",""))
except Exception:
    pass' 2>/dev/null || true)"
fi
if [ "$SRC" = "startup" ] && ls "$ROOT"/.claude/state/task.TASK-*.json >/dev/null 2>&1; then
  bash "$S/tasks.sh" recover >/dev/null 2>&1 || true
fi
echo "== Workflow state (.claude/state) =="
# REQ-0060 multi (96.12): several tasks = compact status of all of them, not the single-task view
if ls "$ROOT"/.claude/state/task.TASK-*.json >/dev/null 2>&1; then
  bash "$S/tasks.sh" status 2>&1
  for tf in "$ROOT"/.claude/state/task.TASK-*.json; do
    tid="$(basename "$tf" .json)"; tid="${tid#task.}"
    wf="$(bash "$S/workflow-check.sh" --task "$tid" 2>&1)" || { echo "workflow-check FAILED for $tid:"; printf '%s\n' "$wf" | grep -E '^FAIL'; }
  done
  bash "$S/task_checkpoint.sh" brief 2>/dev/null || true
else
bash "$S/task-state.sh" 2>&1 | grep -vE '^(Design|Implementation|Unit test|Security|Verification|Report):'
fi
bash "$S/checklist.sh" 2>/dev/null
bash "$S/backlog.sh" notes 2>/dev/null
bash "$S/backlog.sh" list 2>/dev/null | awk '$2!="done"{q=q"\n  "$0} END{print "Backlog not done:" (q==""?" (none)":q)}'

dirty="$(git -C "$ROOT" status --porcelain -- .claude/state docs/design docs/report 2>/dev/null)"
if [ -n "$dirty" ]; then
  echo "UNCOMMITTED workflow state (commit it via the commit skill before new work):"
  echo "$dirty"
fi

if ls "$ROOT"/.claude/state/task.TASK-*.json >/dev/null 2>&1; then
  :  # per-task verdicts printed above
elif wf="$(bash "$S/workflow-check.sh" 2>&1)"; then
  printf '%s\n' "$wf" | grep '^WARN'
else
  echo "workflow-check FAILED - fix bookkeeping before new work:"
  printf '%s\n' "$wf" | grep -E '^(FAIL|WARN)'
fi
exit 0

#!/usr/bin/env bash
# Stop hook: a turn must not end with workflow state that is lost or false.
# Blocks (exit 2, stderr fed back to Claude) when:
#   - task.json is unreadable (fail closed, not open);
#   - .claude/state has uncommitted changes (a transition recorded but never
#     committed - the commit skill commits every transition in the same turn);
#   - state=DONE and workflow-check.sh fails, or the DONE task's design/report
#     docs are uncommitted.
# If Claude is already continuing because of this hook (stop_hook_active), it
# warns instead of blocking again, so an impossible commit cannot loop forever.
# Wired in .claude/settings.json; tested by .claude/tests/workflow_gates_test.sh.
set -Eeuo pipefail
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
TASK="$ROOT/.claude/state/task.json"

[ -f "$TASK" ] || exit 0
# REQ-0060 multi (96.6/96.17): task files present = several tasks; legacy keeps the single-task path below
TFILES="$(ls "$ROOT"/.claude/state/task.TASK-*.json 2>/dev/null || true)"

input="$(cat 2>/dev/null || true)"
active="$(printf '%s' "$input" | python3 -c 'import json,sys
try: print(str(json.load(sys.stdin).get("stop_hook_active", False)).lower())
except Exception: print("false")' 2>/dev/null || echo false)"

problems=""
add() { problems="${problems}- $1"$'\n'; }

if ! STATE="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("state",""))' "$TASK" 2>/dev/null)"; then
  add "task.json is unreadable/invalid JSON - restore it (git diff .claude/state/task.json) before stopping."
  STATE=""
fi

if git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  dirty="$(git -C "$ROOT" status --porcelain -- .claude/state)"
  # REQ-0061 s4 (F-97-1): a live lead writes its own task.<T>.json (and the task.json view); WARN, do not block
  if [ -n "$dirty" ] && [ -n "$TFILES" ]; then
    livet="$(bash "$ROOT/.claude/scripts/tasks.sh" status 2>/dev/null | sed -n 's/^ *lead: \(TASK-[A-Za-z0-9_-]*\) gen[0-9]* live .*/\1/p' || true)"
    skipped=""
    for lt in $livet; do
      if printf '%s\n' "$dirty" | grep -qF -- " .claude/state/task.$lt.json"; then
        dirty="$(printf '%s\n' "$dirty" | grep -vF -- " .claude/state/task.$lt.json" || true)"
        skipped="$skipped $lt"
        echo "WARN: $lt: lead live, its state is uncommitted" >&2
      fi
    done
    [ -z "$skipped" ] || dirty="$(printf '%s\n' "$dirty" | grep -vE -- ' \.claude/state/task\.json$' || true)"
  fi
  # TASK-098 fresh lead_at: warn, not block, while the task's lead_at is <= 15 min old
  if [ -n "$dirty" ] && [ -n "$TFILES" ]; then
    fresh="$(python3 - "$ROOT/.claude/state" <<'FRESH_EOF' 2>/dev/null || true
import calendar, glob, json, os, sys, time
for f in sorted(glob.glob(os.path.join(sys.argv[1], "task.TASK-*.json"))):
    try:
        t = calendar.timegm(time.strptime(str(json.load(open(f)).get("lead_at") or ""), "%Y-%m-%dT%H:%M:%SZ"))
    except Exception:
        continue
    if 0 <= time.time() - t <= 900:
        print(os.path.basename(f)[5:-5])
FRESH_EOF
)"
    skipped=""
    for lt in $fresh; do
      if printf '%s\n' "$dirty" | grep -qF -- " .claude/state/task.$lt.json"; then
        dirty="$(printf '%s\n' "$dirty" | grep -vF -- " .claude/state/task.$lt.json" || true)"
        skipped="$skipped $lt"
        echo "WARN: $lt: lead_at is fresh (<= 15 min), its state is uncommitted" >&2
      fi
    done
    [ -z "$skipped" ] || dirty="$(printf '%s\n' "$dirty" | grep -vE -- ' \.claude/state/task\.json$' || true)"
  fi
  [ -z "$dirty" ] || add "uncommitted workflow state (commit the transition via the commit skill: commit-check.sh then git commit):"$'\n'"$dirty"
  if [ "$STATE" = "DONE" ]; then
    docs="$(git -C "$ROOT" status --porcelain -- docs/design docs/report)"
    [ -z "$docs" ] || add "task is DONE but design/report docs are uncommitted:"$'\n'"$docs"
  fi
fi

if [ -z "$TFILES" ] && [ "$STATE" = "DONE" ] && ! wf="$("$ROOT/.claude/scripts/workflow-check.sh" 2>&1)"; then
  add "task.json claims state=DONE but workflow-check.sh failed - fix the evidence or move the state back:"$'\n'"$(printf '%s\n' "$wf" | grep -E '^FAIL')"
fi

if [ -n "$TFILES" ]; then
  while IFS= read -r tf; do
    [ -n "$tf" ] || continue
    tid="$(basename "$tf" .json)"; tid="${tid#task.}"
    row="$(python3 -c 'import json,sys
d=json.load(open(sys.argv[1]))
c=d.get("checkpoint") or {}
nx=str(c.get("next") or "").strip()
stale=bool(c.get("at")) and str(d.get("updated_at") or "")>str(c.get("at"))
print("%s|%s|%s" % (d.get("state",""), "empty" if not nx else ("stale" if stale else "ok"), d.get("status","")))' "$tf" 2>/dev/null || echo "?|?|")"
    st="${row%%|*}"; rest="${row#*|}"; ck="${rest%%|*}"
    case "$st" in
      DONE)
        if ! wf="$("$ROOT/.claude/scripts/workflow-check.sh" --task "$tid" 2>&1)"; then
          add "$tid claims state=DONE but workflow-check.sh --task failed:"$'\n'"$(printf '%s\n' "$wf" | grep -E '^FAIL')"
        fi ;;
      ""|"?") add "$tid: task file unreadable (git diff .claude/state/task.$tid.json)" ;;
      *) case "$ck" in
           empty) echo "WARN: $tid has no checkpoint.next - save one (tasks.sh hold or task_checkpoint.sh) so a resume knows the next step" >&2 ;;
           stale) echo "WARN: $tid checkpoint.next is older than its last update - refresh it" >&2 ;;
         esac ;;
    esac
  done <<< "$TFILES"
  # REQ-0061 lead (97.13): a lead that quit or ran out is shown as a WARN row
  bash "$ROOT/.claude/scripts/tasks.sh" status 2>/dev/null | grep -E '^ *quit:' | while IFS= read -r qrow; do
    echo "WARN: $qrow" >&2
  done || true
fi

[ -z "$problems" ] && exit 0
printf 'Workflow not persisted:\n%s' "$problems" >&2
if [ "$active" = "true" ]; then
  echo "(already blocked once this turn; allowing the stop so it cannot loop)" >&2
  exit 0
fi
exit 2

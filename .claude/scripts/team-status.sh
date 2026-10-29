#!/usr/bin/env bash
# The coordinator's "don't miss anything" block (skill role-monitor, REQ-0024 AC5): one compact
# read-only view of what needs doing before the next brief. Every non-empty line is an action.
#   team-status.sh [TASK-ID]     default: task_id in .claude/state/task.json
# Lines: TASK, COMMIT, PATCH, HANDOFF, FINDINGS, LEDGER, BACKLOG, BLOCKED, ROLES, PENDING, DUE.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
tj="$root/.claude/state/task.json"
bj="$root/.claude/state/backlog.json"
if [ "$(TASKS_ROOT="$root" python3 "$root/.claude/scripts/_tasks.py" mode)" = multi ]; then
  # REQ-0060: one block per active task (or the one named); state comes from its own file.
  if [ -z "${1:-}" ]; then
    act="$(TASKS_ROOT="$root" python3 "$root/.claude/scripts/_tasks.py" active)"
    [ -n "$act" ] || { echo "TASK: none active"; exit 0; }
    first=""
    for t in $act; do [ -n "$first" ] || first="$t"; TS_SUB=1 bash "$0" "$t" || true; done
    TS_GLOBAL=1 bash "$0" "$first" || true   # global lines once, not per task
    exit 0
  fi
  case "$1" in TASK-[0-9]*) ;; *) echo "bad task id: $1" >&2; exit 2 ;; esac
  [ -f "$root/.claude/state/task.$1.json" ] && tj="$root/.claude/state/task.$1.json"
fi
task=${1:-$(jq -r '.task_id // empty' "$tj" 2>/dev/null || true)}
[ -n "$task" ] || { echo "TASK: none active"; exit 0; }
dir="$root/work/$task"

cut80() { cut -c1-"${1:-110}"; }

if [ -n "${TS_GLOBAL:-}" ]; then :
elif [ -f "$tj" ] && [ "$(jq -r .task_id "$tj")" = "$task" ]; then
  echo "TASK: $task $(jq -r .state "$tj") | next: $(jq -r '.next // ""' "$tj" | cut80 90)"
else
  echo "TASK: $task (not the active task)"
fi

# Uncommitted work outside work/ (role edits waiting for a wip commit) and dirty state.
changed=""
[ -n "${TS_SUB:-}" ] || changed=$(git -C "$root" status --porcelain --untracked-files=all 2>/dev/null | awk '{print $NF}' | grep -v '^work/' || true)
if [ -n "$changed" ]; then
  n=$(printf '%s\n' "$changed" | wc -l | tr -d ' ')
  st=""; case "$changed" in .claude/state/*|*"
.claude/state/"*) st=" (includes .claude/state: finish the transition)" ;; esac
  more=""; [ "$n" -gt 6 ] && more=" +$((n - 6)) more"
  echo "COMMIT: $n uncommitted$st: $(printf '%s\n' "$changed" | head -6 | tr '\n' ' ')$more"
fi

# Patches from roles: pending (applies), applied (reverse applies), conflict (neither).
pend="" appl="" conf=""
for p in "$dir"/patches/*.patch; do
  [ -f "$p" ] || continue
  [ -z "${TS_GLOBAL:-}" ] || break
  b=$(basename "$p")
  # Recorded by main at `git apply` (a later follow-up edit would read as a conflict).
  if [ -f "$dir/patches/APPLIED" ] && grep -qx -- "$b" "$dir/patches/APPLIED"; then appl="$appl $b"
  elif git -C "$root" apply --check "$p" >/dev/null 2>&1; then pend="$pend $b"
  elif git -C "$root" apply --reverse --check "$p" >/dev/null 2>&1; then appl="$appl $b"
  else conf="$conf $b"; fi
done
[ -n "$pend$conf" ] && echo "PATCH: pending:${pend:- none} | conflict:${conf:- none} | applied:${appl:- none}"

# Handoffs: line 1 of each, plus any QUESTION line (a role waiting on main).
hs=""
for h in "$dir"/handoff/*.md; do
  [ -f "$h" ] || continue
  [ -z "${TS_GLOBAL:-}" ] || break
  hs="$hs $(basename "$h" .md)=$(head -1 "$h" | sed 's/^PROGRESS: //')"
  q=$(grep -m1 '^QUESTION:' "$h" || true)
  [ -n "$q" ] && echo "QUESTION ($(basename "$h")): $(echo "$q" | cut80)"
done
[ -n "$hs" ] && echo "HANDOFF:$hs"

if [ -z "${TS_GLOBAL:-}" ] && [ -f "$dir/findings.jsonl" ]; then
  echo "FINDINGS: $(grep -c . "$dir/findings.jsonl") in work/$task/findings.jsonl (last $(tail -1 "$dir/findings.jsonl" | jq -r '.id // "?"' 2>/dev/null))"
fi

new_raw=0
[ -n "${TS_SUB:-}" ] || new_raw=$(python3 "$root/.claude/req/req.py" raw list --new 2>/dev/null | grep -c '^RAW-' || true)
[ "${new_raw:-0}" -gt 0 ] && echo "LEDGER: $new_raw untriaged RAW (skill req-intake before the turn ends)"

if [ -z "${TS_SUB:-}" ] && [ -f "$bj" ]; then
  open=$(jq -r '[.[]|select(.status!="done")|.task_id]|join(" ")' "$bj")
  [ -n "$open" ] && echo "BACKLOG: $open"
fi

if [ -z "${TS_GLOBAL:-}" ] && [ -f "$tj" ] && [ "$(jq -r .task_id "$tj")" = "$task" ]; then
  bl=$(jq -r '.blocked.reason // empty' "$tj")
  [ -n "$bl" ] && echo "BLOCKED: $bl (attempts $(jq -r '.blocked.attempts // 0' "$tj"))"
fi

if [ -z "${TS_GLOBAL:-}" ] && [ -f "$dir/roles.log" ]; then
  echo "ROLES: $(tail -3 "$dir/roles.log" | cut -d' ' -f2- | tr '\n' ';' | cut80)"
fi

# Pending user questions and due reminders (the brief subcommand prints action lines only).
if [ -z "${TS_SUB:-}" ] && [ -f "$root/.claude/scripts/task_checkpoint.sh" ]; then
  bash "$root/.claude/scripts/task_checkpoint.sh" brief 2>/dev/null | while IFS= read -r l; do
    case "$l" in
      "Your turn:"*) echo "PENDING: ${l#Your turn: }" ;;
      DUE*) echo "$l" ;;
    esac
  done || true
fi

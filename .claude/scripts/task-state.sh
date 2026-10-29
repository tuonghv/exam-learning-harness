#!/usr/bin/env bash
# Print the active task's state, per-phase status, blocker, next action and
# the last phase-log heading - the resume point, without reading whole files.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPT_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPT_DIR")"
TASK="$ROOT/.claude/state/task.json"
PHASE_LOG="$ROOT/.claude/state/phase-log.md"

[ -f "$TASK" ] || { echo "Missing task.json; pick one with .claude/scripts/backlog.sh pick <id>"; exit 1; }

# Per-task state (REQ-0060): in multi mode print every active task (or the one named).
show() {
python3 - "$1" "$PHASE_LOG" <<'PY'
import json, os, re, sys
d=json.load(open(sys.argv[1]))
print("Task:", d.get("task_id"), "-", d.get("title"))
print("State:", d.get("state"))
print("Design:", d.get("design",{}).get("status"))
print("Implementation:", d.get("implementation",{}).get("status"))
print("Unit test:", d.get("unit_test",{}).get("status"))
print("Security:", d.get("security",{}).get("status"))
print("Verification:", d.get("verification",{}).get("status"))
print("Report:", d.get("report",{}).get("status"))
b = d.get("blocked")
if b:
    print(f"BLOCKED: {b.get('reason')} (attempts={b.get('attempts', 0)})")
print("Updated:", d.get("updated_at") or "(unset)", "by", d.get("updated_by") or "(unset)")
print("Next:", d.get("next"))
notes = d.get("user_notes") or []
if notes:
    clean = lambda s: re.sub(r"[\x00-\x1f\x7f]", " ", str(s))
    print(f"User notes ({len(notes)}):")
    for n in notes:
        print(f"  {clean(n.get('raw'))}: {clean(n.get('note'))}")
if os.path.isfile(sys.argv[2]):
    heads = re.findall(r"^## .+$", open(sys.argv[2]).read(), re.M)
    if heads:
        print("Last phase-log entry:", heads[-1][3:])
PY
}

if [ "$(python3 "$SCRIPT_DIR/_tasks.py" mode)" = multi ]; then
  if [ -n "${1:-}" ]; then ids="$1"; else ids="$(python3 "$SCRIPT_DIR/_tasks.py" active)"; fi
  [ -n "$ids" ] || { echo "No active task"; exit 0; }
  for t in $ids; do
    case "$t" in TASK-[0-9]*) ;; *) echo "bad task id: $t" >&2; exit 2 ;; esac
    [ -f "$ROOT/.claude/state/task.$t.json" ] || { echo "Missing task.$t.json" >&2; exit 1; }
    echo "== $t =="
    show "$ROOT/.claude/state/task.$t.json"
  done
else
  show "$TASK"
fi

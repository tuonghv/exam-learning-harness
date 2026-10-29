#!/usr/bin/env bash
# Single-command answer to "is anything not done yet": combines backlog.json
# (queued/active items) and the active task.json (per-phase status) into one
# report. Read-only. Exits 1 if anything is pending, 0 if fully done, so it
# can also be used as a check.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPT_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPT_DIR")"
BACKLOG="$ROOT/.claude/state/backlog.json"
TASK="$ROOT/.claude/state/task.json"

python3 - "$BACKLOG" "$TASK" <<'PY'
import json, os, sys

backlog_path, task_path = sys.argv[1], sys.argv[2]
pending = 0

print("=== Backlog ===")
if os.path.isfile(backlog_path):
    items = json.load(open(backlog_path))
    open_items = [i for i in items if i.get("status") != "done"]
    if open_items:
        for i in open_items:
            print(f"  {i['task_id']:<10} {i['status']:<8} {i.get('priority','normal'):<8} {i['title']}")
            pending += 1
    else:
        print("  (none queued or active - all backlog items done)")
else:
    print("  (no backlog.json)")

print("=== Active task ===")
st_dir = os.path.dirname(task_path)
multi = False
try:
    multi = json.load(open(task_path)).get("schema") == 2
except (OSError, ValueError, AttributeError):
    pass
paths = [task_path]
if multi:  # REQ-0060: every active task has its own file
    import re
    done = {i["task_id"] for i in (json.load(open(backlog_path)) if os.path.isfile(backlog_path) else [])
            if i.get("status") == "done"}
    paths = []
    for fn in sorted(os.listdir(st_dir)):
        m = re.fullmatch(r"task\.(TASK-[0-9]+)\.json", fn)
        if m and m.group(1) not in done:
            paths.append(os.path.join(st_dir, fn))
    if not paths:
        print("  (no active task)")
for tp in paths:
  if os.path.isfile(tp):
    d = json.load(open(tp))
    state = d.get("state")
    print(f"  {d.get('task_id')} - {d.get('title')}")
    print(f"  state: {state}")
    if state != "DONE":
        pending += 1
        for section in ("design", "implementation", "unit_test", "security", "verification", "report"):
            print(f"    {section}: {d.get(section, {}).get('status')}")
        print(f"  next: {d.get('next') or '(unset)'}")
  else:
    print("  (no task.json)")

print()
if pending:
    print(f"NOT DONE: {pending} item(s) need attention (see above)")
    raise SystemExit(1)
print("ALL DONE: no queued/active backlog items, active task is DONE")
PY

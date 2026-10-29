#!/usr/bin/env bash
# Move queued work between state/backlog.json and the single active
# state/task.json. Only one task is ever "active" (in task.json) at a time.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPT_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPT_DIR")"
BACKLOG="$ROOT/.claude/state/backlog.json"
TASK="$ROOT/.claude/state/task.json"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") list                 # show all backlog items
  $(basename "$0") next                 # print the next queued task_id (or "none")
  $(basename "$0") pick <task_id> [--force]
  $(basename "$0") complete <task_id> [--force "<reason>"]
  $(basename "$0") note <TASK-NNN|active> RAW-NNNNN "<one line>"   # record a user instruction on a task
  $(basename "$0") notes [<TASK-NNN|active>]                       # list notes, or queued note counts

complete records completed_at and the report path from task.json. --force closes
a task that never reached DONE and REQUIRES a reason, stored as the item's
"waiver" so workflow-check.sh can tell a deliberate closure from a hand-edit.
EOF
  exit 1
}

[ -f "$BACKLOG" ] || { echo "Missing .claude/state/backlog.json; create it as a JSON list of {task_id,title,status:\"queued\",requirement,acceptance_criteria}"; exit 1; }

cmd="${1:-}"; shift || true

# Per-task state (REQ-0060): legacy = one task.json (code below, unchanged); multi = task.<T>.json files.
MODE="$(python3 "$SCRIPT_DIR/_tasks.py" mode)"
case "$cmd:$MODE" in
  pick:mixed|complete:mixed|note:mixed|notes:mixed)
    echo "FAIL: mixed task state (task.<T>.json files without a schema-2 task.json); run .claude/scripts/tasks.sh migrate"
    exit 1 ;;
  pick:multi) exec python3 "$SCRIPT_DIR/_tasks.py" pick "$@" ;;
  complete:multi) exec python3 "$SCRIPT_DIR/_tasks.py" complete "$@" ;;
  note:multi|notes:multi)
    if [ -n "${1:-}" ]; then
      hold="$(python3 "$SCRIPT_DIR/_tasks.py" holder "$1")" || { echo "$hold"; exit 1; }
      set -- "${hold%%$'\t'*}" "${@:2}"
      TASK="${hold#*$'\t'}"
      case "$TASK" in */backlog.json) TASK="$ROOT/.claude/state/task.none.json" ;; esac
    fi ;;
esac

case "$cmd" in
  list)
    python3 - "$BACKLOG" <<'PY'
import json, sys
items = json.load(open(sys.argv[1]))
for it in items:
    print(f"{it['task_id']:<10} {it['status']:<8} {it.get('priority','normal'):<8} {it['title']}")
PY
    ;;

  next)
    python3 - "$BACKLOG" <<'PY'
import json, sys
items = json.load(open(sys.argv[1]))
queued = [i for i in items if i.get("status") == "queued"]
print(queued[0]["task_id"] if queued else "none")
PY
    ;;

  pick)
    task_id="${1:-}"; [ -n "$task_id" ] || usage
    force="${2:-}"
    if [ -n "$force" ] && [ "$force" != "--force" ]; then usage; fi
    [ -f "$TASK" ] || { echo "Missing .claude/state/task.json; restore it from git (git checkout -- .claude/state/task.json)"; exit 1; }
    # pick overwrites task.json: the previous task must already be in git.
    if [ "$force" != "--force" ] && git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 &&
       [ -n "$(git -C "$ROOT" status --porcelain -- .claude/state)" ]; then
      echo "FAIL: .claude/state has uncommitted changes; commit the previous task's last transition first"
      exit 1
    fi
    python3 - "$BACKLOG" "$TASK" "$task_id" "$force" "$SCRIPT_DIR" <<'PY'
import atexit, json, sys
from datetime import datetime, timezone

backlog_path, task_path, task_id, force, script_dir = sys.argv[1:6]
sys.dont_write_bytecode = True
sys.path.insert(0, script_dir)
import _tasks
_lk = _tasks.locked()
try:
    _lk.__enter__()
except ValueError as ex:
    raise SystemExit(f"FAIL: {ex}")
atexit.register(lambda: _lk.__exit__(None, None, None))
items = json.load(open(backlog_path))
current = json.load(open(task_path))

def fail(msg):
    raise SystemExit(f"FAIL: {msg}")

if any(i.get("status") == "active" for i in items):
    active = next(i for i in items if i["status"] == "active")
    fail(f"backlog item {active['task_id']} is already active; complete it first")

if current.get("state") not in ("TODO", "DONE") and force != "--force":
    fail(f"task.json is mid-flight (state={current.get('state')}); "
         f"finish it or rerun with --force to overwrite")

item = next((i for i in items if i["task_id"] == task_id), None)
if item is None:
    fail(f"no backlog item with task_id={task_id}")
if item["status"] != "queued" and force != "--force":
    fail(f"backlog item {task_id} has status={item['status']}, not queued")

new_task = {
    "task_id": item["task_id"],
    "title": item["title"],
    "state": "TODO",
    "requirement": item.get("requirement", ""),
    "acceptance_criteria": item.get("acceptance_criteria", []),
    "design": {"status": "pending", "path": "", "summary": "", "reuse": [], "risks": []},
    "implementation": {"status": "pending", "files": []},
    "unit_test": {"status": "pending", "command": "", "result": ""},
    "security": {"status": "pending", "result": ""},
    "verification": {"status": "pending", "evidence": []},
    "report": {"status": "pending", "path": ""},
    "roles_required": True,
    "crosscheck_required": True,
    "roles": {},
    "user_notes": item.get("user_notes", []),
    "picked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "updated_at": "",
    "updated_by": "",
    "next": "Enter DESIGN: understand the requirement and acceptance criteria, then draft "
            "docs/design/phase-<N>-<slug>.md (design skill) and record it in design.path.",
}
_tasks.write_json(task_path, new_task)

item["status"] = "active"
_tasks.write_json(backlog_path, items)

print(f"PICKED: {task_id} -> task.json (state=TODO)")
PY
    ;;

  complete)
    task_id="${1:-}"; [ -n "$task_id" ] || usage
    force="${2:-}"; reason="${3:-}"
    if [ -n "$force" ] && [ "$force" != "--force" ]; then usage; fi
    if [ "$force" = "--force" ] && [ -z "$reason" ]; then
      echo "FAIL: complete --force needs a reason: complete $task_id --force \"<why it closes without DONE>\""
      exit 1
    fi
    [ -f "$TASK" ] || { echo "Missing .claude/state/task.json; restore it from git (git checkout -- .claude/state/task.json)"; exit 1; }
    python3 - "$BACKLOG" "$TASK" "$task_id" "$force" "$reason" "$SCRIPT_DIR" <<'PY'
import atexit, json, sys
from datetime import datetime, timezone

backlog_path, task_path, task_id, force, reason, script_dir = sys.argv[1:7]
sys.dont_write_bytecode = True
sys.path.insert(0, script_dir)
import _tasks
_lk = _tasks.locked()
try:
    _lk.__enter__()
except ValueError as ex:
    raise SystemExit(f"FAIL: {ex}")
atexit.register(lambda: _lk.__exit__(None, None, None))
items = json.load(open(backlog_path))
current = json.load(open(task_path))

def fail(msg):
    raise SystemExit(f"FAIL: {msg}")

item = next((i for i in items if i["task_id"] == task_id), None)
if item is None:
    fail(f"no backlog item with task_id={task_id}")

if current.get("task_id") != task_id and force != "--force":
    fail(f"task.json is currently {current.get('task_id')}, not {task_id}")
if current.get("state") != "DONE" and force != "--force":
    fail(f"task.json state={current.get('state')}, not DONE; "
         f"finish it or rerun with --force \"<reason>\"")

item["status"] = "done"
item["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
if current.get("task_id") == task_id and current.get("report", {}).get("path"):
    item["report"] = current["report"]["path"]
if force == "--force":
    item["waiver"] = reason
if current.get("task_id") == task_id and current.get("user_notes"):
    merged = {n.get("raw"): n for n in item.get("user_notes", [])}
    merged.update({n.get("raw"): n for n in current["user_notes"]})
    item["user_notes"] = list(merged.values())
_tasks.write_json(backlog_path, items)

print(f"COMPLETED: {task_id}" + (f" (waiver: {reason})" if force == "--force" else ""))
print("Stage .claude/state/backlog.json in the DONE commit (commit-check fails if it is left unstaged).")
PY
    ;;

  note)
    target="${1:-}"; raw="${2:-}"; text="${3:-}"
    if [ -z "$target" ] || [ -z "$raw" ] || [ $# -ne 3 ]; then usage; fi
    [ -f "$TASK" ] || [ "$MODE" = multi ] || { echo "Missing .claude/state/task.json; restore it from git (git checkout -- .claude/state/task.json)"; exit 1; }
    python3 - "$BACKLOG" "$TASK" "$ROOT/${REQ_DIR:-docs/req}/raw" "$target" "$raw" "$text" "$SCRIPT_DIR" <<'PY'
import atexit, json, os, re, sys
from datetime import datetime, timezone

backlog_path, task_path, raw_dir, target, raw, text, script_dir = sys.argv[1:8]
sys.dont_write_bytecode = True
sys.path.insert(0, script_dir)
import _tasks

def fail(msg):
    raise SystemExit(f"FAIL: {msg}")

if not re.fullmatch(r"RAW-[0-9]{5}", raw):
    fail(f"bad RAW id '{raw[:20]}' (want RAW-NNNNN)")
if not re.fullmatch(r"TASK-[0-9]+|active", target):
    fail(f"bad task id '{target[:20]}' (want TASK-NNN or active)")
if not os.path.isfile(os.path.join(raw_dir, raw + ".md")):
    fail(f"{raw} does not exist in the requirement ledger")
if not text.strip():
    fail("note text is empty")
if len(text) > 200:
    fail("note is longer than 200 characters")
if re.search(r"[\x00-\x1f\x7f]", text):
    fail("note must be one line without control characters")
UNSAFE = (r"https?://", r"www\.", r"-----BEGIN", r"AKIA[0-9A-Z]{16}",
          r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]", r"[A-Za-z0-9+/=_-]{32,}")
if any(re.search(p, text) for p in UNSAFE):
    fail("note looks like a URL or a secret; write a short instruction in your own words")

_lk = _tasks.locked()
try:
    _lk.__enter__()
except ValueError as ex:
    fail(str(ex))
atexit.register(lambda: _lk.__exit__(None, None, None))
items = json.load(open(backlog_path))
current = json.load(open(task_path)) if os.path.isfile(task_path) else {}
if target == "active" or current.get("task_id") == target:
    holder, name, path, data = current, current.get("task_id"), task_path, current
else:
    holder = next((i for i in items if i.get("task_id") == target), None)
    if holder is None:
        fail(f"no backlog item with task_id={target}")
    name, path, data = target, backlog_path, items

notes = holder.setdefault("user_notes", [])
if any(n.get("raw") == raw for n in notes):
    print(f"ALREADY: {raw} on {name}")
    raise SystemExit(0)
notes.append({"raw": raw, "note": text,
              "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
_tasks.write_json(path, data)
print(f"NOTED: {raw} -> {name}")
PY
    ;;

  notes)
    python3 - "$BACKLOG" "$TASK" "${1:-}" <<'PY'
import json, os, re, sys

backlog_path, task_path, target = sys.argv[1:4]
clean = lambda s: re.sub(r"[\x00-\x1f\x7f]", " ", str(s))
if target:
    if not re.fullmatch(r"TASK-[0-9]+|active", target):
        raise SystemExit(f"FAIL: bad task id '{target[:20]}' (want TASK-NNN or active)")
    cur = json.load(open(task_path)) if os.path.isfile(task_path) else {}
    if target == "active" or cur.get("task_id") == target:
        holder = cur
    else:
        holder = next((i for i in json.load(open(backlog_path)) if i.get("task_id") == target), {})
    for n in holder.get("user_notes", []):
        print(f"{clean(n.get('raw'))}: {clean(n.get('note'))}")
else:
    parts = [f"{i['task_id']}={len(i['user_notes'])}" for i in json.load(open(backlog_path))
             if i.get("status") == "queued" and i.get("user_notes")]
    if parts:
        print("Queued user notes: " + " ".join(sorted(parts)))
PY
    ;;

  *)
    usage
    ;;
esac

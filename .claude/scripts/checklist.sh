#!/usr/bin/env bash
# Plan checklist tracker. Design docs may carry a table
#   | # | Item | Task / doc | Done |
# whose "Task / doc" cell names 3-digit task numbers ("025 / 25.1",
# "025-028", "025 + 026"). A row belongs to every task it names (a range
# covers each number in it) and is OWNED by the highest one: only the owner
# must tick it ("[x]") before reaching DONE.
#
#   checklist.sh            open rows of the active task (from task.json)
#   checklist.sh --all      every open row, all tasks
#   checklist.sh --gate     exit 1 if the active task still owns open rows
#   checklist.sh --gate --task TASK-N   the same for TASK-N alone (workflow-check --task)
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPT_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPT_DIR")"
MODE="${1:-active}"
ONLY=""   # --task TASK-N (with --gate): judge that one task, not every active one
if [ "${2:-}" = "--task" ]; then
  ONLY="${3:-}"
  case "$ONLY" in TASK-[0-9]*) ;; *) echo "FAIL: bad --task '$ONLY'"; exit 1 ;; esac
fi

python3 - "$ROOT" "$MODE" "$ONLY" <<'PY'
import glob, json, os, re, sys
root, mode, only = sys.argv[1], sys.argv[2], sys.argv[3]
tid = ""
try:
    tid = json.load(open(os.path.join(root, ".claude/state/task.json"))).get("task_id") or ""
except Exception:
    pass
m = re.search(r"(\d+)$", tid)
me = int(m.group(1)) if m else None
# REQ-0060: in multi mode every active task counts, not only the view's focus.
mes = {me} if me is not None else set()
try:
    if json.load(open(os.path.join(root, ".claude/state/task.json"))).get("schema") == 2:
        import subprocess
        out = subprocess.run([sys.executable, os.path.join(root, ".claude/scripts/_tasks.py"), "active"],
                             capture_output=True, text=True, env=dict(os.environ, TASKS_ROOT=root)).stdout.split()
        mes = {int(t[5:]) for t in out if re.fullmatch(r"TASK-[0-9]+", t)}
        tid = " ".join(out)
except Exception:
    pass
if re.fullmatch(r"TASK-[0-9]+", only):
    mes = {int(only[5:])}; tid = only

rows = []  # (doc, num, item, tasks, owner, done)
for doc in sorted(glob.glob(os.path.join(root, "docs/design/*.md"))):
    in_table = False
    for line in open(doc, encoding="utf-8"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) == 4 and cells[0] == "#" and cells[3] == "Done":
            in_table = True; continue
        if not in_table:
            continue
        if not cells:
            in_table = False; continue
        if len(cells) != 4 or set(cells[0]) <= set("-: "):
            continue
        tasks = set()
        for a, b in re.findall(r"\b(\d{3})(?:\s*-\s*(\d{3}))?\b", cells[2].split("/")[0]):
            lo, hi = int(a), int(b or a)
            tasks.update(range(lo, hi + 1))
        if not tasks:
            continue
        done = cells[3].lower() in ("[x]", "x", "done")
        rows.append((os.path.relpath(doc, root), cells[0], cells[1], tasks, max(tasks), done))

open_rows = [r for r in rows if not r[5]]
if mode == "--all":
    sel = open_rows
elif not mes:
    sel = []
else:
    sel = [r for r in open_rows if mes & r[3]]
total = len(rows); ticked = total - len(open_rows)

if mode == "--gate":
    owned = [r for r in sel if r[4] in mes]
    for r in owned:
        print(f"FAIL: checklist row {r[1]} still open ({r[0]}): {r[2]}")
    sys.exit(1 if owned else 0)

if not rows:
    sys.exit(0)
label = "all tasks" if mode == "--all" else (tid or "no active task")
print(f"Checklist ({label}): {ticked}/{total} rows ticked overall; open here:" + ("" if sel else " (none)"))
for r in sel:
    tag = "owns" if r[4] in mes else f"shared, owner {r[4]:03d}"
    print(f"  [ ] {r[1]:>3} {r[2]}  ({tag}; {r[0]})")
PY

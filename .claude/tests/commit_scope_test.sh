#!/usr/bin/env bash
# TASK-098 98.8 (P27): commit-check scopes the "changed but not staged" rule to the committed task.
# With a `Task: T` trailer in multi mode, another task's unstaged design/report (docs/(design|report)/phase-<M>-*,
# M != T's number) does not block; T's own unstaged design still FAILs; legacy single-task mode is unchanged.
# Throwaway git repos with a copy of the kit; the real state is never touched.
# Run: bash .claude/tests/commit_scope_test.sh      (KIT_DIR=<kit> tests another copy, the bite check)
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
  if [ "$rc" -ne "$want_rc" ]; then
    bad "$name (rc=$rc, want $want_rc)"; printf '%s\n' "$out" | sed 's/^/    /' | head -n 12; return
  fi
  if [ -n "$want_out" ] && ! printf '%s' "$out" | grep -qF -- "$want_out"; then
    bad "$name (output lacks '$want_out')"; printf '%s\n' "$out" | sed 's/^/    /' | head -n 12; return
  fi
  ok "$name"
}

# fixture <dir> <multi|legacy>: TASK-2 (+ TASK-4 in multi mode) with designs under docs/design, committed.
fixture() {
  local d="$1" mode="$2"
  rm -rf "$d"; mkdir -p "$d/.claude/state" "$d/docs/design" "$d/docs/report"
  cp -r "$KIT/." "$d/.claude/"
  find "$d/.claude" -name __pycache__ -prune -exec rm -rf {} +
  rm -rf "$d/.claude/tests" "$d/.claude/state"; mkdir -p "$d/.claude/state"
  printf '{"max_active": 2}\n' > "$d/.claude/workflow.json"  # fixture is a multi-task kit whatever the live config
  git -C "$d" init -q
  git -C "$d" config user.email t@example.invalid
  git -C "$d" config user.name test
  python3 - "$d" "$mode" <<'PY'
import json, sys
d, mode = sys.argv[1:3]
st = d + "/.claude/state/"
def task(tid, n):
    open("%s/docs/design/phase-%d-x.md" % (d, n), "w").write("design\n")
    return {"task_id": tid, "title": "t" + str(n), "state": "IMPLEMENTING", "requirement": "r",
            "acceptance_criteria": ["a"],
            "design": {"status": "completed", "summary": "s", "path": "docs/design/phase-%d-x.md" % n},
            "implementation": {"status": "pending", "files": ["src/a.py"]},
            "unit_test": {"status": "pending", "command": "", "result": ""},
            "security": {"status": "pending", "result": ""},
            "verification": {"status": "pending", "evidence": []},
            "report": {"status": "pending", "path": ""},
            "updated_at": "2026-01-01T00:00:00Z", "updated_by": "test", "next": "n"}
tasks = [("TASK-2", 2)] + ([("TASK-4", 4)] if mode == "multi" else [])
items = []
log = "# Phase Log\n"
for tid, n in tasks:
    t = task(tid, n)
    json.dump(t, open(st + ("task.%s.json" % tid if mode == "multi" else "task.json"), "w"), indent=2)
    items.append({"task_id": tid, "title": t["title"], "status": "active", "priority": "normal", "scope": ["src/*"]})
    log += "\n## DESIGN - %s - 2026-01-01T00:00:00Z\n## IMPLEMENTING - %s - 2026-01-01T00:00:00Z\n" % (tid, tid)
json.dump(items, open(st + "backlog.json", "w"), indent=2)
open(st + "phase-log.md", "w").write(log)
PY
  if [ "$mode" = multi ]; then
    # schema-2 view task.json
    python3 - "$d" <<'PY'
import json, sys
d = sys.argv[1]
json.dump({"schema": 2, "task_id": "TASK-2", "state": "IMPLEMENTING"}, open(d + "/.claude/state/task.json", "w"), indent=2)
PY
  fi
  : > "$d/docs/report/.keep"
  git -C "$d" add -A; git -C "$d" commit -qm fixture --no-verify
}

# msg <file> <task>: a no-state-change wip commit message
msg() { printf 'wip: x\n\nTask: %s\nState: IMPLEMENTING\n' "$2" > "$1"; }
CC() { (cd "$1" && bash .claude/scripts/commit-check.sh "$2"); }
touch_task() { # bump a task file so it is staged content
  python3 - "$1" "$2" <<'PY'
import json, sys
p = sys.argv[1] + "/.claude/state/" + sys.argv[2]
d = json.load(open(p)); d["next"] = "edited"; json.dump(d, open(p, "w"), indent=2)
PY
}

R="$WORK/multi"; M="$WORK/msg"
fixture "$R" multi
touch_task "$R" task.TASK-2.json
# U (TASK-4) has an unstaged tracked design edit, an untracked unrecorded design and an unstaged report of its number.
echo "edit" >> "$R/docs/design/phase-4-x.md"
echo "new" > "$R/docs/design/phase-4-extra.md"
echo "rep" > "$R/docs/report/phase-4-report.md"
(cd "$R" && bash .claude/scripts/tasks.sh sync >/dev/null 2>&1) || true
git -C "$R" add .claude/state/task.TASK-2.json .claude/state/task.json
msg "$M" TASK-2
expect "P27a T commit passes with U's design/report unstaged" 0 "commit-check: OK" CC "$R" "$M"

# T's own unstaged design still FAILs.
echo "edit" >> "$R/docs/design/phase-2-x.md"
expect "P27b T's own unstaged design FAILs" 1 "docs/design/phase-2-x.md" CC "$R" "$M"
git -C "$R" checkout -q -- docs/design/phase-2-x.md
echo "new" > "$R/docs/report/phase-2-report.md"
expect "P27c T's own untracked report FAILs" 1 "docs/report/phase-2-report.md" CC "$R" "$M"
rm -f "$R/docs/report/phase-2-report.md"

# Non-phase docs and the shared workflow files stay covered.
echo "x" >> "$R/.claude/state/phase-log.md"
expect "P27d unstaged phase-log.md FAILs" 1 "phase-log.md" CC "$R" "$M"
git -C "$R" checkout -q -- .claude/state/phase-log.md
echo "x" > "$R/docs/design/notes.md"
expect "P27e unstaged design without a phase number FAILs" 1 "docs/design/notes.md" CC "$R" "$M"
rm -f "$R/docs/design/notes.md"
expect "P27f clean again passes" 0 "commit-check: OK" CC "$R" "$M"

# Phase 2 vs 20: the number is compared as a whole, not by prefix.
echo "x" > "$R/docs/design/phase-20-y.md"
expect "P27g phase-20 doc is not TASK-2's (no prefix match)" 0 "commit-check: OK" CC "$R" "$M"
rm -f "$R/docs/design/phase-20-y.md"

# Legacy single-task mode: unchanged (an unstaged design FAILs, whatever its number).
L="$WORK/legacy"
fixture "$L" legacy
touch_task "$L" task.json
echo "edit" >> "$L/docs/design/phase-2-x.md"
echo "new" > "$L/docs/design/phase-9-other.md"
git -C "$L" add .claude/state/task.json
msg "$M" TASK-2
expect "P27h legacy: unstaged design FAILs" 1 "docs/design/phase-2-x.md" CC "$L" "$M"
expect "P27i legacy: another phase's untracked design FAILs too" 1 "docs/design/phase-9-other.md" CC "$L" "$M"

echo "SUMMARY(commit_scope): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

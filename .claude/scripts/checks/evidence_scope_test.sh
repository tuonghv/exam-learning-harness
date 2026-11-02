#!/usr/bin/env bash
# TASK-057 57.6: commit-check (multi mode, `Task: T` trailer) treats docs/report/evidence/<other>/ as foreign
# but still requires T's own evidence dir and INDEX.md to be staged. Reuses the fixture of commit_scope_test.sh.
# Run: bash .claude/scripts/checks/evidence_scope_test.sh      (KIT_DIR=<kit> tests another copy, the bite check)
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRE="$(mktemp)"
trap 'rm -f "$PRE"' EXIT
sed -n '1,/^R="\$WORK\/multi"/p' "$HERE/../../tests/commit_scope_test.sh" | sed '$d' \
  | sed "s|^KIT=.*|KIT=\"\${KIT_DIR:-$HERE/../..}\"|" > "$PRE"
# shellcheck disable=SC1090
. "$PRE"

R="$WORK/multi"; M="$WORK/msg"
fixture "$R" multi
# a tracked earlier evidence dir, as in the real repo (git status then lists new dirs per task, not the parent)
mkdir -p "$R/docs/report/evidence/TASK-1"; echo old > "$R/docs/report/evidence/TASK-1/o.txt"
git -C "$R" add -A; git -C "$R" commit -qm ev1 --no-verify
touch_task "$R" task.TASK-2.json
(cd "$R" && bash .claude/scripts/tasks.sh sync >/dev/null 2>&1) || true
git -C "$R" add .claude/state/task.TASK-2.json .claude/state/task.json
msg "$M" TASK-2

mkdir -p "$R/docs/report/evidence/TASK-4"
echo "other task evidence" > "$R/docs/report/evidence/TASK-4/a.txt"
expect "E1 another task's unstaged evidence dir is foreign (OK)" 0 "commit-check: OK" CC "$R" "$M"
rm -rf "$R/docs/report/evidence/TASK-4"

mkdir -p "$R/docs/report/evidence/TASK-2"
echo "own evidence" > "$R/docs/report/evidence/TASK-2/a.txt"
expect "E2 own unstaged evidence file FAILs" 1 "docs/report/evidence/TASK-2/" CC "$R" "$M"
git -C "$R" add docs/report/evidence/TASK-2/a.txt
expect "E3 own evidence staged passes" 0 "commit-check: OK" CC "$R" "$M"

mkdir -p "$R/docs/report"
echo "| TASK-2 t |" > "$R/docs/report/INDEX.md"
expect "E4 unstaged INDEX.md FAILs (only a DONE commit rewrites it)" 1 "docs/report/INDEX.md" CC "$R" "$M"
git -C "$R" add docs/report/INDEX.md
expect "E5 staged INDEX.md passes" 0 "commit-check: OK" CC "$R" "$M"

# E6 (D2): no tracked evidence anywhere -> git status would collapse the new dir to docs/report/evidence/
R2="$WORK/multi2"
fixture "$R2" multi
touch_task "$R2" task.TASK-2.json
(cd "$R2" && bash .claude/scripts/tasks.sh sync >/dev/null 2>&1) || true
git -C "$R2" add .claude/state/task.TASK-2.json .claude/state/task.json
mkdir -p "$R2/docs/report/evidence/TASK-4"; echo x > "$R2/docs/report/evidence/TASK-4/a.txt"
expect "E6 foreign evidence dir, no tracked evidence yet (OK)" 0 "commit-check: OK" CC "$R2" "$M"

echo "SUMMARY(evidence-scope): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

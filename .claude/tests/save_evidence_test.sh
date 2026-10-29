#!/usr/bin/env bash
# Regression test for scripts/save-evidence.sh, in a throwaway git repo holding a copy of the
# kit - the real repo's work/ and state are never touched. Run: bash .claude/tests/save_evidence_test.sh
set -Eeuo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }
# check <name> <cmd...>: pass when the command succeeds
check() { local name="$1"; shift; if "$@"; then ok "$name"; else bad "$name"; fi; }
has() { grep -qx -- "$1" "$2"; }          # has <exact line> <file>
absent() { [ ! -e "$1" ]; }

R="$WORK/repo"
mkdir -p "$R/.claude/state"
cp -r "$KIT/scripts" "$R/.claude/scripts"
git -C "$R" init -q
git -C "$R" config user.email t@example.invalid
git -C "$R" config user.name test
echo '{"task_id": "TASK-9"}' >"$R/.claude/state/task.json"
git -C "$R" add -A && git -C "$R" commit -qm init
SE="$R/.claude/scripts/save-evidence.sh"
E="$R/work/TASK-9/evidence"

# success: header + output, rc 0, summary line
rc=0; out="$("$SE" unit-a -- bash -c 'echo hello; echo "two words" >&2')" || rc=$?
check "success rc 0" test "$rc" -eq 0
check "summary line" grep -qF "saved work/TASK-9/evidence/unit-a.txt rc=0 lines=2" <<<"$out"
check "header rc" has "# rc: 0" "$E/unit-a.txt"
check "header task" has "# task: TASK-9" "$E/unit-a.txt"
check "header head" grep -q "^# head: [0-9a-f]\{7,\}$" "$E/unit-a.txt"
check "stdout kept" has "hello" "$E/unit-a.txt"
check "stderr kept" has "two words" "$E/unit-a.txt"

# failure: rc passed through and recorded
rc=0; "$SE" fail-b -- bash -c 'echo boom; exit 3' >/dev/null || rc=$?
check "failure rc passed through" test "$rc" -eq 3
check "failure rc recorded" has "# rc: 3" "$E/fail-b.txt"

# args with spaces are kept as one argument in the header
"$SE" quoted -- printf '%s\n' 'a b' >/dev/null
check "quoted cmd header" grep -qF '# cmd: printf %s\\n a\ b' "$E/quoted.txt"

# TASK env overrides task.json
TASK=TASK-X "$SE" env-c -- true >/dev/null
check "TASK override" test -f "$R/work/TASK-X/evidence/env-c.txt"

# bad input
rc=0; "$SE" "../x" -- true >/dev/null 2>&1 || rc=$?
check "bad name refused" test "$rc" -eq 2
check "bad name wrote nothing" absent "$R/work/TASK-9/x.txt"
rc=0; "$SE" only-name true >/dev/null 2>&1 || rc=$?
check "missing -- refused" test "$rc" -eq 2
echo '{"task_id": "../evil"}' >"$R/.claude/state/task.json"
rc=0; "$SE" d -- true >/dev/null 2>&1 || rc=$?
check "unsafe task id refused" test "$rc" -eq 2
check "unsafe task id wrote nothing" absent "$R/work/evil"
rm "$R/.claude/state/task.json"
rc=0; "$SE" d -- true >/dev/null 2>&1 || rc=$?
check "no task refused" test "$rc" -eq 2

echo "SUMMARY(save-evidence): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

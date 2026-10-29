#!/usr/bin/env bash
# TASK-074 74.7: `lessons.py revert KEY` stays inside <root>/.claude/skills/<name>/SKILL.md (QA round U2), $0.
# A hand-edited or hostile ledger row must not make revert write outside the skills dir.
# Run: bash .claude/tests/lessons_revert_confine_test.sh      (KIT_DIR=<.claude copy> tests another copy)
set -Eeuo pipefail
KIT="${KIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LP="$KIT/scripts/lessons.py"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }

expect() {
  local name="$1" want_rc="$2" want_out="$3" out rc=0; shift 3
  out="$("$@" 2>&1)" || rc=$?
  if [ "$rc" -ne "$want_rc" ]; then
    bad "$name (rc=$rc, want $want_rc)"; printf '%s\n' "$out" | sed 's/^/    /' | head -n 6; return
  fi
  if [ -n "$want_out" ] && ! printf '%s' "$out" | grep -qF -- "$want_out"; then
    bad "$name (output lacks '$want_out')"; printf '%s\n' "$out" | sed 's/^/    /' | head -n 6; return
  fi
  ok "$name"
}

R="$WORK/r"
L() { python3 -B "$LP" --root "$R" "$@"; }
KEY="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

# row <skill>: one watch row (revert=replace, new "NEWLINE", hunk "OLDLINE") for the given skill value
row() {
  python3 -c 'import json,sys
print(json.dumps({"key":sys.argv[1],"status":"watch","revert":"replace","skill":sys.argv[2],
 "new":"NEWLINE","hunk":"OLDLINE","task":"TASK-9","ts":"2026-10-12T00:00:00Z","commit":"x","roles":[]}))' "$KEY" "$1"
}
fixture() {
  rm -rf "$R" "$WORK/outside"
  mkdir -p "$R/.claude/skills/good" "$R/.claude/lessons" "$R/.claude/evil" "$R/docs" "$WORK/outside"
  printf 'NEWLINE\n' > "$R/.claude/skills/good/SKILL.md"
  printf 'NEWLINE\n' > "$R/.claude/evil/SKILL.md"
  printf 'NEWLINE\n' > "$R/docs/SKILL.md"
  printf 'NEWLINE\n' > "$WORK/outside/SKILL.md"
  row "$1" > "$R/.claude/lessons/ledger.jsonl"
}
untouched() { # <file>: still holds NEWLINE
  grep -qx NEWLINE "$1"
}

fixture good
expect "U2e1 control: a plain skill name reverts" 0 "reverted" L revert "$KEY"
expect "U2e2 control: the block was replaced" 0 "OLDLINE" cat "$R/.claude/skills/good/SKILL.md"

fixture "../evil"
expect "U2e3 skill ../evil refused" 1 "bad skill name" L revert "$KEY"
expect "U2e4 .claude/evil/SKILL.md untouched" 0 "" untouched "$R/.claude/evil/SKILL.md"

fixture "../../outside"
expect "U2e5 skill ../../outside refused" 1 "" L revert "$KEY"
expect "U2e6 file outside root untouched" 0 "" untouched "$WORK/outside/SKILL.md"

fixture "$WORK/outside"
expect "U2e7 absolute skill path refused" 1 "bad skill name" L revert "$KEY"
expect "U2e8 absolute target untouched" 0 "" untouched "$WORK/outside/SKILL.md"

fixture "."
expect "U2e9 skill . refused" 1 "bad skill name" L revert "$KEY"

fixture "good/.."
expect "U2e10 skill with slash refused" 1 "bad skill name" L revert "$KEY"

fixture "lnk"
ln -s "$WORK/outside" "$R/.claude/skills/lnk"
expect "U2e11 skill dir symlinked outside root refused" 1 "outside root" L revert "$KEY"
expect "U2e12 outside file untouched" 0 "" untouched "$WORK/outside/SKILL.md"

fixture "lnk"
ln -s "$R/docs" "$R/.claude/skills/lnk"
expect "U2e13 skill dir symlinked inside root but outside .claude/skills refused" 1 "" L revert "$KEY"
expect "U2e14 docs/SKILL.md untouched" 0 "" untouched "$R/docs/SKILL.md"

echo "SUMMARY(lessons_revert_confine): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

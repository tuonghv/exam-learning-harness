#!/usr/bin/env bash
# Regression test for the requirement ledger (.claude/req: req.py, hook_*.py,
# task_gate.py) and how it sits next to the workflow hooks. Each case runs in a
# throwaway git repo holding a copy of .claude and docs/req/config.json, so the
# real ledger is never touched. Run: bash .claude/tests/req_kit_test.sh
set -Eeuo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }
# check <name> <cmd...>: pass when cmd succeeds
check() { local name="$1"; shift; if "$@"; then ok "$name"; else bad "$name"; fi; }
empty() { [ -z "$1" ] || { echo "    got: $1"; return 1; }; }

# expect <name> <want-rc> <want-substring|""> <cmd...>
expect() {
  local name="$1" want_rc="$2" want_out="$3" out rc=0; shift 3
  out="$("$@" 2>&1)" || rc=$?
  if [ "$rc" -ne "$want_rc" ]; then
    bad "$name (rc=$rc, want $want_rc)"; printf '%s\n' "$out" | sed 's/^/    /'; return
  fi
  if [ -n "$want_out" ] && ! printf '%s' "$out" | grep -qF -- "$want_out"; then
    bad "$name (output lacks '$want_out')"; printf '%s\n' "$out" | sed 's/^/    /'; return
  fi
  ok "$name"
}

D="$WORK/p"
mkdir -p "$D/docs/req"
cp -r "$KIT" "$D/.claude"
rm -rf "$D/.claude/tests" "$D/.claude/state"; mkdir -p "$D/.claude/state"
find "$D/.claude" -name __pycache__ -prune -exec rm -rf {} +
cp "$KIT/../docs/req/config.json" "$D/docs/req/config.json"
git -C "$D" init -q
export CLAUDE_PROJECT_DIR="$D"
cd "$D"
REQ=(python3 .claude/req/req.py)
"${REQ[@]}" init >/dev/null

hook() { printf '%s' "$2" | python3 ".claude/req/$1.py"; }
set_task() { # set_task <task_id> <state> [backlog-status-of-TASK-001]
  python3 - "$D/.claude/state" "$1" "$2" "${3:-queued}" <<'PY'
import json, os, sys
d, tid, st, bst = sys.argv[1:]
os.makedirs(d, exist_ok=True)
json.dump({"task_id": tid, "state": st}, open(os.path.join(d, "task.json"), "w"))
json.dump([{"task_id": "TASK-001", "status": bst}, {"task_id": tid, "status": "active"}],
          open(os.path.join(d, "backlog.json"), "w"))
PY
}

# --- 1 capture
expect "1.1 long prompt is captured as RAW" 0 "prompt saved as RAW-00001" \
  hook hook_capture '{"prompt":"please add an export of the report as csv files","session_id":"s"}'
expect "1.2 short ack is saved auto-ignored" 0 "short prompt saved as RAW-00002 (auto-ignored" hook hook_capture '{"prompt":"ok go"}'
check "1.2b short ack file is IGNORED with a reason" grep -q "^reason: short ack (auto, under 25 chars)" docs/req/raw/RAW-00002.md
expect "1.3 bare slash command is not captured" 0 "" hook hook_capture '{"prompt":"/next"}'
expect "1.6 background task notification is not captured" 0 "" \
  hook hook_capture '{"prompt":"<task-notification>\n<task-id>b1</task-id>\n<status>completed</status>\n</task-notification>"}'
expect "1.7 subagent hand-back is not captured" 0 "" \
  hook hook_capture '{"prompt":"<agent-message from=\"a1\">\n[Subagent hand-back] STATUS: DONE\n</agent-message>"}'
check "1.4 exactly two RAW files (long + short ack)" [ "$(find docs/req/raw -name 'RAW-*.md' | wc -l | tr -d ' ')" = 2 ]
expect "1.5 bad hook input never fails the prompt" 0 "" hook hook_capture 'not json'

# --- 2 stop gate
expect "2.1 stop blocked on untriaged RAW" 0 '"decision": "block"' hook hook_stop '{"stop_hook_active":false}'
out="$(hook hook_stop '{"stop_hook_active":true}')"
check "2.2 second stop in a turn is allowed" empty "$out"
out="$(REQ_GATE=0 hook hook_stop '{"stop_hook_active":false}')"
check "2.3 REQ_GATE=0 disables the gate" empty "$out"
expect "2.4 multi-line --reason is stored on one line" 0 "RAW-00001 -> IGNORED" \
  "${REQ[@]}" raw ignore RAW-00001 --reason $'chatter\nsecond line'
expect "2.5 ledger stays parseable after it" 0 "[REQ] ledger OK" "${REQ[@]}" check
out="$(hook hook_stop '{"stop_hook_active":false}')"
check "2.6 stop allowed once triaged" empty "$out"

# --- 3 lifecycle gates
"${REQ[@]}" new --title "CSV export" --text "WHEN asked, the report SHALL be written as CSV." >/dev/null
expect "3.1 cannot skip a state" 2 "cannot skip TODO -> IMPLEMENTING" "${REQ[@]}" status REQ-1 IMPLEMENTING
expect "3.2 TODO -> DESIGN with a Requirement" 0 "REQ-0001: TODO -> DESIGN" "${REQ[@]}" status REQ-1 DESIGN
python3 - docs/req/items/REQ-0001.md <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
s = s.replace("- [ ] AC1:\n", "- [x] AC1: csv written\n")
s = s.replace("## Design\n", "## Design\nSee docs/design/phase-1-csv.md\n", 1)
open(p, "w").write(s)
PY

# --- 4 task_gate: a REQ never runs ahead of its TASK
expect "4.1 IMPLEMENTING refused with no TASK linked" 2 "no TASK linked" "${REQ[@]}" status REQ-1 IMPLEMENTING
"${REQ[@]}" task REQ-1 TASK-002 >/dev/null
set_task TASK-002 DESIGN
expect "4.2 refused while the TASK is behind" 2 "TASK-002 is DESIGN" "${REQ[@]}" status REQ-1 IMPLEMENTING
set_task TASK-002 IMPLEMENTING
expect "4.3 allowed once the TASK caught up" 0 "DESIGN -> IMPLEMENTING" "${REQ[@]}" status REQ-1 IMPLEMENTING
check "4.4 check recorded as evidence" grep -q "task_gate.py REQ-0001 IMPLEMENTING. passed" docs/req/items/REQ-0001.md
"${REQ[@]}" task REQ-1 TASK-404 >/dev/null
expect "4.5 unknown linked TASK is refused" 2 "TASK-404 not found" \
  "${REQ[@]}" status REQ-1 UNIT_TESTED --evidence "tests pass"
"${REQ[@]}" new --title "Other" >/dev/null
"${REQ[@]}" task REQ-2 TASK-001 >/dev/null
set_task TASK-002 IMPLEMENTING "done"
expect "4.6 a done backlog TASK counts as DONE" 0 "at or past DONE" python3 .claude/req/task_gate.py REQ-2 DONE

# --- 5 hooks leave no bytecode in .claude (commit-check rejects it)
check "5.1 no __pycache__ under .claude" empty "$(find "$D/.claude" -name __pycache__)"

# --- 6 PreCompact ignores per-prompt ledger churn but not real work
git add -A >/dev/null && git -c user.email=t@example.invalid -c user.name=t commit -qm base
hook hook_capture '{"prompt":"another requirement worth capturing here"}' >/dev/null
expect "6.1 new RAW alone does not trip PreCompact" 0 "" bash .claude/hooks/pre-compact-check.sh
echo x >> docs/req/items/REQ-0001.md
expect "6.2 an edited REQ is listed but never blocks PreCompact" 0 "REQ-0001.md" bash .claude/hooks/pre-compact-check.sh
# a blocked compaction at a full context leaves only /clear (RAW-00290..00297): no PreCompact exit 2
expect "6.3 PreCompact hook has no blocking exit" 1 "" grep -nE 'exit +[1-9]' .claude/hooks/pre-compact-check.sh

# --- 7 SessionStart after compaction points back to the ledger
"${REQ[@]}" focus REQ-1 --next "write csv test" >/dev/null
expect "7.1 compact brief shows focus and next step" 0 "next step (STATE): write csv test" \
  hook hook_context '{"source":"compact"}'

# --- 8 one-call helpers: status --next, ac
"${REQ[@]}" new --title "Ticks" --text "WHEN x, the report SHALL y." >/dev/null
python3 - docs/req/items/REQ-0003.md <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
s = s.replace("- [ ] AC1:\n", "- [ ] AC1: one\n- [ ] AC2: two\n- [ ] AC3: three\n")
open(p, "w").write(s)
PY
expect "8.1 status --next moves and focuses in one call" 0 "focus=REQ-0003  next=design it" \
  "${REQ[@]}" status REQ-3 DESIGN --next "design it"
expect "8.2 state holds the new focus" 0 "focus=REQ-0003  next=design it" "${REQ[@]}" focus
expect "8.3 ac ticks by id with evidence" 0 "ticked AC1,AC3; 1 Acceptance item(s) left" \
  "${REQ[@]}" ac REQ-3 AC1,ac3 --evidence "run X"
check "8.4 AC2 still open, evidence recorded" grep -q '^- \[ \] AC2: two' docs/req/items/REQ-0003.md
check "8.5 evidence line" grep -q '\[AC AC1,AC3\] run X' docs/req/items/REQ-0003.md
expect "8.6 unknown AC id refused, nothing ticked" 2 "unknown Acceptance id(s) AC9" \
  "${REQ[@]}" ac REQ-3 AC2,AC9 --evidence "y"
expect "8.7 all ticks the rest" 0 "0 Acceptance item(s) left" "${REQ[@]}" ac REQ-3 all --evidence "z"

# 8.8-8.11 template placeholder and duplicate ids are not Acceptance ids
"${REQ[@]}" new --title "Placeholder" --text "WHEN x, the report SHALL y." >/dev/null
python3 - docs/req/items/REQ-0004.md <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
s = s.replace("- [ ] AC1:\n", "- [ ] AC1:\n- [ ] AC1: one\n- [ ] AC2: two\n- [ ] AC3:\n")
open(p, "w").write(s)
PY
expect "8.8 empty placeholder id is refused as unknown" 2 "unknown Acceptance id(s) AC3" \
  "${REQ[@]}" ac REQ-4 AC3 --evidence "y"
expect "8.9 all lists each filled id once" 0 "ticked AC1,AC2; 0 Acceptance item(s) left" \
  "${REQ[@]}" ac REQ-4 all --evidence "z"
check "8.10 placeholders stay open" grep -q '^- \[ \] AC3:$' docs/req/items/REQ-0004.md
check "8.11 empty AC1 placeholder not ticked" grep -q '^- \[ \] AC1:$' docs/req/items/REQ-0004.md

# --- 9 hook output size (REQ-0006 AC4): one line per prompt, with or without a captured RAW
out="$(hook hook_capture '{"prompt":"another long requirement for the one line output check","session_id":"s"}')"
check "9.1 captured prompt prints exactly one line" [ "$(printf '%s\n' "$out" | wc -l | tr -d ' ')" = 1 ]
check "9.2 the one line keeps the saved-RAW notice and the focus brief" sh -c "printf '%s' \"\$1\" | grep -q 'prompt saved as RAW-' && printf '%s' \"\$1\" | grep -q '\\[REQ\\]'" _ "$out"
out="$(hook hook_capture '{"prompt":"/next"}')"
check "9.3 bare slash command prints at most one line" [ "$(printf '%s' "$out" | grep -c '')" -le 1 ]

echo "SUMMARY(req-kit): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

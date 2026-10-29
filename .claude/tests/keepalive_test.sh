#!/usr/bin/env bash
# TASK-154 / REQ-0121: tasks.sh keepalive (verdicts, --watch) and tasks.sh nextpick (Stop hook).
# Design items 154.2, 154.5, 154.6, 154.7; checks U1-U10. Every case runs in a throwaway git repo
# holding a copy of the scripts; the real .claude/state is never touched.
# Run: bash .claude/tests/keepalive_test.sh      (KIT_DIR=<kit> tests another copy, the bite check)
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
    bad "$name (rc=$rc, want $want_rc)"; printf '%s\n' "$out" | sed 's/^/    /' | head -n 8; return
  fi
  if [ -n "$want_out" ] && ! printf '%s' "$out" | grep -qF -- "$want_out"; then
    bad "$name (output lacks '$want_out')"; printf '%s\n' "$out" | sed 's/^/    /' | head -n 8; return
  fi
  ok "$name"
}
# refute <name> <substring> <cmd...>: output must NOT contain the substring (rc ignored)
refute() {
  local name="$1" nope="$2" out; shift 2
  out="$("$@" 2>&1)" || true
  if printf '%s' "$out" | grep -qF -- "$nope"; then bad "$name (output has '$nope')"; else ok "$name"; fi
}
# silent <name> <cmd...>: rc 0 and empty output
silent() {
  local name="$1" out rc=0; shift
  out="$("$@" 2>&1)" || rc=$?
  if [ "$rc" -eq 0 ] && [ -z "$out" ]; then ok "$name"; else bad "$name (rc=$rc out='$(printf '%s' "$out" | head -c 100)')"; fi
}

E=1577836800   # fixture commit time: 2020-01-01T00:00:00Z
ASKED="2020-01-01T00:00:00Z"

# fresh <dir> <backlog python list literal> [active-task-id]: scripts + state, committed at time E
fresh() {
  local d="$1" items="$2" act="${3:-}"
  rm -rf "$d"; mkdir -p "$d/.claude/state"
  cp -r "$KIT/scripts" "$d/.claude/scripts"
  find "$d/.claude" -name __pycache__ -prune -exec rm -rf {} +
  printf '{"max_active": 1}\n' > "$d/.claude/workflow.json"
  python3 - "$d" "$items" "$act" <<'PY'
import json, sys
d, items, act = sys.argv[1], eval(sys.argv[2]), sys.argv[3]
json.dump(items, open(d + "/.claude/state/backlog.json", "w"))
if act:
    json.dump({"task_id": act, "status": "IMPLEMENTING"}, open("%s/.claude/state/task.%s.json" % (d, act), "w"))
PY
  git -C "$d" init -q
  git -C "$d" config user.email t@example.invalid
  git -C "$d" config user.name test
  git -C "$d" add -A
  GIT_AUTHOR_DATE="$E +0000" GIT_COMMITTER_DATE="$E +0000" git -C "$d" commit -qm fixture --no-verify
}
# pending <dir> <task> <asked_at>: one open question
pending() {
  printf '[{"id":"Q1","task_id":"%s","asked_at":"%s","question":"q"}]\n' "$2" "$3" > "$1/.claude/state/pending.json"
}
Q='[{"task_id":"TASK-9","status":"queued","title":"work","priority":"normal"}]'
QNU='[{"task_id":"TASK-9","status":"queued","title":"work","needs_user":"decide","priority":"normal"}]'

# KA <dir> <tasks.sh args>: tasks.sh in the scratch kit with a hermetic env (extra env: set before calling)
KA() { local d="$1"; shift
  (cd "$d" && KEEPALIVE_PROCS="${KEEPALIVE_PROCS:-none}" KEEPALIVE_POLL_SEC=1 KEEPALIVE_MAX_MIN="${KEEPALIVE_MAX_MIN:-1}" \
     TASK_CHECKPOINT_TIMEOUT_MIN=10 bash .claude/scripts/tasks.sh "$@"); }
# KAT <dir> <epoch>: keepalive at a fake clock (both clocks)
KAT() { KEEPALIVE_NOW="$2" TASK_CHECKPOINT_NOW="$2" KA "$1" keepalive; }
# NP <dir> <stdin-json> [VAR=val ...]: nextpick with that stdin
NP() { local d="$1" in="$2"; shift 2
  (cd "$d" && printf '%s' "$in" | env KEEPALIVE_PROCS=none TASK_CHECKPOINT_TIMEOUT_MIN=10 "$@" bash .claude/scripts/tasks.sh nextpick); }

R="$WORK/r"

# --- 154.5 / U9 keepalive verdicts ----------------------------------------------------------------
fresh "$R" "$Q"
expect "154.5 U9 STALL pick (no active, workable queued) rc 4" 4 "STALL pick TASK-9" KA "$R" keepalive
fresh "$R" "$QNU"
expect "154.5 U9 OK idle (only needs_user items) rc 0" 0 "OK idle" KA "$R" keepalive
fresh "$R" "[]" TASK-1
expect "154.5 U9 OK active (young state commit) rc 0" 0 "OK active TASK-1" KAT "$R" $((E + 60))
expect "154.5 U9 STALL resume (active, old state commit) rc 4" 4 "STALL resume TASK-1" KAT "$R" $((E + 7200))
expect "154.5 U9 KEEPALIVE_STALL_MIN widens the window (no resume)" 0 "OK active" env KEEPALIVE_STALL_MIN=500 bash -c "$(declare -f KA KAT); KAT '$R' $((E + 7200))"
# WAIT: open young question; DUE: old one
pending "$R" TASK-1 "$ASKED"
expect "154.5 U9 WAIT open young question rc 0" 0 "WAIT question Q1" KAT "$R" $((E + 60))
expect "154.5 U9 DUE old question rc 4" 4 "DUE TASK-1 Q1" KAT "$R" $((E + 7200))
# a question on a held task is ignored
python3 - "$R" <<'PY'
import json, sys
p = sys.argv[1] + "/.claude/state/task.TASK-1.json"
d = json.load(open(p)); d["status"] = "held"; json.dump(d, open(p, "w"))
PY
refute "154.5 U9 question of a held task is not DUE" "DUE" KAT "$R" $((E + 7200))
# WAIT: IN_PROGRESS handoff of the active task (real clock: the file mtime is now)
fresh "$R" "[]" TASK-1
mkdir -p "$R/work/TASK-1/handoff"
printf 'PROGRESS: IN_PROGRESS\nx\n' > "$R/work/TASK-1/handoff/test.md"
expect "154.5 U9 WAIT role with an IN_PROGRESS handoff rc 0" 0 "WAIT TASK-1 test" KA "$R" keepalive
printf 'PROGRESS: COMPLETE\nx\n' > "$R/work/TASK-1/handoff/test.md"
refute "154.5 U9 COMPLETE handoff is not a WAIT" "WAIT" KA "$R" keepalive
# WAIT: a live process named in KEEPALIVE_PROCS
fresh "$R" "$Q"
cp /bin/sleep "$WORK/kajob.sh"
"$WORK/kajob.sh" 30 & SLP=$!
expect "154.5 U9 WAIT live kajob.sh process" 0 "WAIT kajob.sh" env KEEPALIVE_PROCS=kajob.sh bash -c "$(declare -f KA); KA '$R' keepalive"
kill "$SLP" 2>/dev/null || true; wait "$SLP" 2>/dev/null || true
expect "154.5 U9 process gone -> STALL pick again" 4 "STALL pick" env KEEPALIVE_PROCS=kajob.sh bash -c "$(declare -f KA); KA '$R' keepalive"
expect "154.5 keepalive bad usage is rc 2" 2 "usage" KA "$R" keepalive --bogus

# --- 154.6 / U10 watcher --------------------------------------------------------------------------
fresh "$R" "$Q"
expect "154.6 U10 --watch exits 4 on STALL with the line" 4 "STALL pick TASK-9" KA "$R" keepalive --watch
if [ ! -e "$R/.claude/state/.keepalive.pid" ]; then ok "154.6 U10 pid file removed on exit"; else bad "154.6 U10 pid file removed on exit"; fi
fresh "$R" "$QNU"
S0=$(date +%s)
expect "154.6 U10 --watch exits 0 on OK idle after max" 0 "OK idle" env KEEPALIVE_MAX_MIN=0 bash -c "$(declare -f KA); KA '$R' keepalive --watch"
if [ $(( $(date +%s) - S0 )) -lt 20 ]; then ok "154.6 U10 --watch with max 0 returns promptly"; else bad "154.6 U10 --watch with max 0 returns promptly"; fi
# a second watcher is refused while the first lives
fresh "$R" "$QNU"
( cd "$R" && KEEPALIVE_PROCS=none KEEPALIVE_POLL_SEC=1 KEEPALIVE_MAX_MIN=1 exec bash .claude/scripts/tasks.sh keepalive --watch >/dev/null 2>&1 ) & W1=$!
i=0; while [ ! -s "$R/.claude/state/.keepalive.pid" ] && [ "$i" -lt 50 ]; do i=$((i + 1)); sleep 0.1; done
expect "154.6 U10 second watcher is refused" 1 "watcher already running" KA "$R" keepalive --watch
kill "$W1" 2>/dev/null || true; wait "$W1" 2>/dev/null || true
rm -f "$R/.claude/state/.keepalive.pid"

# --- 154.2 / U1-U7 nextpick (print) ---------------------------------------------------------------
fresh "$R" "$Q"
OUT="$(NP "$R" '{"last_assistant_message":"Done."}' NEXT_PICK_BLOCK=0)"
if printf '%s' "$OUT" | grep -qF 'NEXT: pick TASK-9'; then ok "154.2 U1 free slot, workable, last=Done. -> NEXT"; else bad "154.2 U1 NEXT (got '$OUT')"; fi
if printf '%s' "$OUT" | grep -qF 'backlog.sh pick TASK-9' && ! printf '%s' "$OUT" | grep -qF 'tasks.sh pick'; then ok "155.2 NEXT names backlog.sh pick"; else bad "155.2 NEXT hint (got '$OUT')"; fi
if printf '%s' "$OUT" | jq -e 'has("systemMessage") and (has("decision")|not)' >/dev/null; then ok "154.2 U1 systemMessage only, no decision"; else bad "154.2 U1 systemMessage only"; fi
expect "154.2 U1 rc 0" 0 "" NP "$R" '{"last_assistant_message":"Done."}' NEXT_PICK_BLOCK=0
silent "154.2 U4 last starts with Wait for -> no output" NP "$R" '{"last_assistant_message":"x\nWait for tester"}'
expect "154.2 U3 Your turn, no pending entry, free slot -> NEXT" 0 "NEXT: pick TASK-9" NP "$R" '{"last_assistant_message":"Your turn: pick A"}' NEXT_PICK_BLOCK=0
fresh "$R" "$Q" TASK-1
printf '{"max_active": 2}\n' > "$R/.claude/workflow.json"
pending "$R" TASK-1 "$ASKED"
silent "154.2 U3 Your turn with an open unheld question (free slot) -> none" NP "$R" '{"last_assistant_message":"Your turn: answer Q1"}' NEXT_PICK_BLOCK=0 TASK_CHECKPOINT_NOW=$((E + 60)) KEEPALIVE_NOW=$((E + 60))
rm -f "$R/.claude/state/pending.json"
expect "154.2 U3 same fixture, no question registered -> NEXT" 0 "NEXT: pick TASK-9" NP "$R" '{"last_assistant_message":"Your turn: x"}' NEXT_PICK_BLOCK=0 KEEPALIVE_NOW=$((E + 60))
# U2: active task fills the slot
fresh "$R" "$Q" TASK-1
silent "154.2 U2 active task fills the slot -> no output" NP "$R" '{"last_assistant_message":"Done."}' KEEPALIVE_NOW=$((E + 60))
expect "154.2 U2 Your turn, no question, no slot -> NOTE" 0 "NOTE: " NP "$R" '{"last_assistant_message":"Your turn: x"}' KEEPALIVE_NOW=$((E + 60))
# U5: AC3-like fixture
B5='[{"task_id":"TASK-144","status":"queued","title":"a","needs_user":"decide","priority":"high"},{"task_id":"TASK-145","status":"queued","title":"PAID run","priority":"high"},{"task_id":"TASK-147","status":"queued","title":"x","paid":True,"priority":"high"},{"task_id":"TASK-141","status":"queued","title":"low one","priority":"low"},{"task_id":"TASK-146","status":"queued","title":"hi one","priority":"high"}]'
fresh "$R" "$B5"
expect "154.2 U5 NEXT names the workable high-priority item" 0 "NEXT: pick TASK-146" NP "$R" '{"last_assistant_message":"Done."}' NEXT_PICK_BLOCK=0
expect "154.2 U5 (+1 more) shown" 0 "(+1 more)" NP "$R" '{"last_assistant_message":"Done."}' NEXT_PICK_BLOCK=0
expect "154.2 U5 workable: needs_user is skipped" 0 "SKIP TASK-144 needs user" KA "$R" workable
expect "154.2 U5 workable: PAID title is skipped" 0 "SKIP TASK-145 paid" KA "$R" workable
expect "154.2 U5 workable: paid flag is skipped" 0 "SKIP TASK-147 paid" KA "$R" workable
# U6: fail open
fresh "$R" "$Q"
silent "154.2 U6 stop_hook_active -> nothing" NP "$R" '{"stop_hook_active":true,"last_assistant_message":"Done."}'
silent "154.2 U6 NEXT_PICK_CHECK=0 -> silent" NP "$R" '{"last_assistant_message":"Done."}' NEXT_PICK_CHECK=0
expect "154.2 U6 empty stdin rc 0" 0 "" NP "$R" ''
refute "154.2 U6 invalid stdin never emits decision key" '"decision"' NP "$R" 'not json {' NEXT_PICK_BLOCK=0
expect "154.2 U6 invalid stdin rc 0" 0 "" NP "$R" 'not json {'
expect "154.2 U6 non-object JSON rc 0" 0 "" NP "$R" '[1,2]'
silent "154.2 U6 non-object JSON prints nothing" NP "$R" '[1,2]'
expect "154.2 U6 missing transcript rc 0" 0 "" NP "$R" '{"transcript_path":"/nonexistent/t.jsonl"}' NEXT_PICK_BLOCK=0
# U7: last_assistant_message used without reading the transcript; transcript fallback
expect "154.2 U7 last_assistant_message wins over a missing transcript" 0 "NEXT: pick" NP "$R" '{"last_assistant_message":"Done.","transcript_path":"/nonexistent/t.jsonl"}' NEXT_PICK_BLOCK=0
TR="$WORK/tr.jsonl"
{
  printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"text","text":"Your turn: old"}]}}'
  printf '%s\n' 'garbled {{{ line'
  printf '%s\n' '{"type":"assistant","parent_tool_use_id":"x","message":{"content":[{"type":"text","text":"Done sub"}]}}'
  printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"text","text":"Done.\nWait for tester"}]}}'
  printf '%s\n' 'garbled again'
} > "$TR"
silent "154.2 U7 transcript fallback: last main reply 'Wait for' -> none (garbled lines skipped)" NP "$R" "{\"transcript_path\":\"$TR\"}"
{
  printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"text","text":"Wait for old"}]}}'
  printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"x"}]}}'
  printf '%s\n' '{"type":"assistant","parent_tool_use_id":"x","message":{"content":[{"type":"text","text":"Wait for sub"}]}}'
  printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"text","text":"All done here."}]}}'
} > "$TR"
expect "154.2 U7 transcript fallback: last text reply 'All done' -> NEXT" 0 "NEXT: pick TASK-9" NP "$R" "{\"transcript_path\":\"$TR\"}" NEXT_PICK_BLOCK=0

# --- 154.7 / U8 block ------------------------------------------------------------------------------
fresh "$R" "$Q"
OUT="$(NP "$R" '{"last_assistant_message":"Done."}')"
if printf '%s' "$OUT" | jq -e '.decision=="block" and (.reason|test("STALL pick TASK-9"))' >/dev/null; then ok "154.7 U8 STALL -> decision block with the STALL line"; else bad "154.7 U8 block JSON (got '$OUT')"; fi
silent "154.7 U8 stop_hook_active -> no block" NP "$R" '{"stop_hook_active":true,"last_assistant_message":"Done."}'
silent "154.7 U8 last line 'Wait for' -> no block" NP "$R" '{"last_assistant_message":"Wait for tester"}'
refute "154.7 U8 NEXT_PICK_BLOCK=0 -> print-only (no decision)" '"decision"' NP "$R" '{"last_assistant_message":"Done."}' NEXT_PICK_BLOCK=0
# DUE blocks too
fresh "$R" "[]" TASK-1
pending "$R" TASK-1 "$ASKED"
OUT="$(NP "$R" '{"last_assistant_message":"Done."}' TASK_CHECKPOINT_NOW=$((E + 7200)) KEEPALIVE_NOW=$((E + 7200)))"
if printf '%s' "$OUT" | jq -e '.decision=="block" and (.reason|test("DUE TASK-1 Q1"))' >/dev/null; then ok "154.7 U8 DUE -> block"; else bad "154.7 U8 DUE block (got '$OUT')"; fi
# counter: 3 blocks then none, until a new HEAD
fresh "$R" "$Q"
N=0; for i in 1 2 3 4 5; do
  o="$(NP "$R" '{"last_assistant_message":"Done."}')"
  case "$o" in *'"decision"'*) N=$((N + 1));; esac
done
if [ "$N" -eq 3 ]; then ok "154.7 U8 blocks stop after KEEPALIVE_MAX_CONTINUE=3 without a new HEAD"; else bad "154.7 U8 3-in-a-row cap (blocked $N times)"; fi
refute "154.7 U8 over the cap there is no decision" '"decision"' NP "$R" '{"last_assistant_message":"Done."}'
expect "154.7 U8 over the cap it still prints NEXT" 0 "NEXT: pick TASK-9" NP "$R" '{"last_assistant_message":"Done."}'
echo y > "$R/new.txt"; git -C "$R" add -A; git -C "$R" commit -qm "new head" --no-verify
expect "154.7 U8 a new HEAD resets the counter -> block again" 0 '"decision"' NP "$R" '{"last_assistant_message":"Done."}'
fresh "$R" "$Q"
N=0; for i in 1 2 3; do
  o="$(NP "$R" '{"last_assistant_message":"Done."}' KEEPALIVE_MAX_CONTINUE=1)"
  case "$o" in *'"decision"'*) N=$((N + 1));; esac
done
if [ "$N" -eq 1 ]; then ok "154.7 U8 KEEPALIVE_MAX_CONTINUE=1 is honoured"; else bad "154.7 U8 MAX_CONTINUE=1 (blocked $N times)"; fi
fresh "$R" "$QNU"
refute "154.7 U8 OK idle never blocks" '"decision"' NP "$R" '{"last_assistant_message":"Done."}'

echo "SUMMARY: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]

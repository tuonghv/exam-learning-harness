#!/usr/bin/env bash
# TASK-064 64.4-64.9: independent QA for the (not yet applied) agent_setup.py/json/settings.json
# patches in work/TASK-064/patches/*.patch. Builds one patched copy of .claude/ in a scratch dir,
# applying the three patches only if the copy still lacks `def cmd_event` (so this test is a no-op
# once the coordinator applies the real patches to the real .claude/). Every case then works on a
# throwaway git repo copied from that patched kit - the real .claude/ is never touched.
# Run: bash .claude/tests/agent_setup_hook_test.sh
set -Eeuo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(dirname "$KIT")"
PATCHES="$ROOT/work/TASK-064/patches"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
# agent_setup.py's hook keeps its "once"-flag state file in $TMPDIR, keyed only on
# session_id+role (not on repo) - point it at our own scratch dir so a leftover file from a
# previous run of this suite (same hardcoded fixture session ids) can never suppress a warning.
export TMPDIR="$WORK/tmp"
mkdir -p "$TMPDIR"

PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); printf '%s\n' "$2" | sed 's/^/    /'; }

# --- build one patched kit copy, applied idempotently -----------------------------------------
KITPATCHED="$WORK/kit-patched"
mkdir -p "$KITPATCHED"
cp -r "$KIT" "$KITPATCHED/.claude"
find "$KITPATCHED/.claude" -name __pycache__ -prune -exec rm -rf {} +
rm -rf "$KITPATCHED/.claude/tests" "$KITPATCHED/.claude/state"; mkdir -p "$KITPATCHED/.claude/state"
if ! grep -q "def cmd_event" "$KITPATCHED/.claude/hooks/agent_setup.py"; then
  for p in 64.4-agent_setup_py 64.5-agent_setup_json 64.7-settings_json; do
    patch -p1 -d "$KITPATCHED" < "$PATCHES/$p.patch" >/tmp/agent_setup_hook_test_patch.log 2>&1 \
      || { bad "patch $p applied" "$(cat /tmp/agent_setup_hook_test_patch.log)"; }
  done
fi
if python3 -m py_compile "$KITPATCHED/.claude/hooks/agent_setup.py"; then
  ok "patched agent_setup.py compiles"
else
  bad "patched agent_setup.py compiles" "py_compile failed"
fi
if python3 -c "import json; json.load(open('$KITPATCHED/.claude/agent_setup.json'))"; then
  ok "patched agent_setup.json parses"
else
  bad "patched agent_setup.json parses" "json.load failed"
fi

# --- fixtures -----------------------------------------------------------------------------------

# fresh <dir>: a throwaway git repo holding a copy of the patched kit, committed clean.
fresh() {
  local dir="$1"
  rm -rf "$dir"; mkdir -p "$dir"
  cp -r "$KITPATCHED/.claude" "$dir/.claude"
  mkdir -p "$dir/work"
  git -C "$dir" init -q
  git -C "$dir" config user.email t@example.invalid
  git -C "$dir" config user.name test
  git -C "$dir" add -A
  git -C "$dir" commit -q -m init --allow-empty
}

# write_task <dir> <tid> [grants-json] [coder-waiver]
write_task() {
  python3 - "$1" "$2" "${3:-}" "${4:-}" <<'PY'
import json, os, sys
d, tid, grants, waiver = sys.argv[1:5]
os.makedirs(f"{d}/.claude/state", exist_ok=True)
doc = {"task_id": tid}
roles = {}
if grants:
    roles["grants"] = json.loads(grants)
if waiver:
    roles["coder"] = {"waiver": waiver}
if roles:
    doc["roles"] = roles
json.dump(doc, open(f"{d}/.claude/state/task.json", "w"))
PY
}

# ev <tool_name> <tool_input-json> <agent_type> <session_id> <hook_event_name> [transcript_path] [agent_id]
ev() {
  python3 - "$@" <<'PY'
import json, sys
a = sys.argv[1:] + [""] * (7 - len(sys.argv[1:]))
tool_name, tool_input, agent_type, session_id, hook_event_name, transcript_path, agent_id = a[:7]
o = {"tool_name": tool_name, "tool_input": json.loads(tool_input) if tool_input else {},
     "session_id": session_id, "hook_event_name": hook_event_name, "cwd": "/tmp"}
if agent_type:
    o["agent_type"] = agent_type
if transcript_path:
    o["transcript_path"] = transcript_path
if agent_id:
    o["agent_id"] = agent_id
print(json.dumps(o))
PY
}

# run <dir> <subcmd: hook|event|stats> <json-or-empty> [CTXGUARD_TASK] [extra-args...]
# sets OUT, ERR, RC
run() {
  local dir="$1" sub="$2" json="$3" task="${4:-}"; shift 4 || true
  local errf; errf="$(mktemp)"
  if [ -n "$task" ]; then
    OUT="$(CTXGUARD_TASK="$task" python3 "$dir/.claude/hooks/agent_setup.py" "$sub" \
           --config "$dir/.claude/agent_setup.json" "$@" <<<"$json" 2>"$errf")" && RC=0 || RC=$?
  else
    OUT="$(python3 "$dir/.claude/hooks/agent_setup.py" "$sub" \
           --config "$dir/.claude/agent_setup.json" "$@" <<<"$json" 2>"$errf")" && RC=0 || RC=$?
  fi
  ERR="$(cat "$errf")"; rm -f "$errf"
}

check_eq() { # check_eq <name> <actual> <expected>
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "got [$2] want [$3]"; fi
}

# assert_one_warn <name> <json-blob>: exactly one JSON object, hookSpecificOutput.additionalContext
# set, no permissionDecision anywhere.
assert_one_warn() {
  local name="$1" blob="$2"
  if python3 - "$blob" <<'PY'
import json, sys
lines = [l for l in sys.argv[1].splitlines() if l.strip()]
assert len(lines) == 1, f"expected 1 json line, got {len(lines)}"
obj = json.loads(lines[0])
assert "permissionDecision" not in json.dumps(obj), "permissionDecision must never appear"
hso = obj.get("hookSpecificOutput") or {}
assert hso.get("additionalContext"), "hookSpecificOutput.additionalContext missing/empty"
PY
  then ok "$name"; else bad "$name" "blob=$blob"; fi
}

assert_dirty_warn() { # 69.10: one systemMessage naming the files, nothing for the role's context
  local name="$1" blob="$2"
  if python3 - "$blob" <<'PY'
import json, sys
lines = [l for l in sys.argv[1].splitlines() if l.strip()]
assert len(lines) == 1, f"expected 1 json line, got {len(lines)}"
obj = json.loads(lines[0])
assert "uncommitted edits" in obj["systemMessage"] and "wip commit" in obj["systemMessage"]
assert "hookSpecificOutput" not in obj and "additionalContext" not in lines[0]
assert "permissionDecision" not in lines[0]
PY
  then ok "$name"; else bad "$name" "blob=$blob"; fi
}

assert_silent() { # assert_silent <name> <blob>
  if [ -z "$2" ]; then ok "$1"; else bad "$1" "expected no output, got: $2"; fi
}

log_has() { # log_has <path> <python-cond-on-obj>
  python3 - "$1" "$2" <<'PY'
import json, sys
path, cond = sys.argv[1], sys.argv[2]
try:
    lines = [json.loads(l) for l in open(path) if l.strip()]
except OSError:
    lines = []
sys.exit(0 if any(eval(cond, {}, {"c": c}) for c in lines) else 1)
PY
}

assert_log_has() { # assert_log_has <name> <path> <python-cond-on-obj>
  if log_has "$2" "$3"; then
    ok "$1"
  else
    bad "$1" "$(cat "$2" 2>/dev/null)"
  fi
}

# =========================================================== 1. tid for every role
D="$WORK/c1"; fresh "$D"
write_task "$D" "TASK-T1"
run "$D" hook "$(ev Read '{"file_path":"README.md"}' "" s1 PreToolUse)" ""
check_eq "64.4 hook rc for session Read" "$RC" 0
assert_log_has "64.4 session tid comes from task.json (no CTXGUARD_TASK)" \
  "$D/.claude/agent_setup_calls.jsonl" 'c.get("role")=="session" and c.get("task")=="TASK-T1"'

D="$WORK/c1b"; fresh "$D"   # no task.json at all: tid must come only from CTXGUARD_TASK
run "$D" hook "$(ev Read '{"file_path":"README.md"}' coder s2 PreToolUse)" "TASK-ENV"
check_eq "64.4 hook rc for coder Read (CTXGUARD_TASK)" "$RC" 0
assert_log_has "64.4 role tid comes from CTXGUARD_TASK" \
  "$D/.claude/agent_setup_calls.jsonl" 'c.get("role")=="coder" and c.get("task")=="TASK-ENV"'

# =========================================================== 2. stop flag scope
D="$WORK/c2"; fresh "$D"; mkdir -p "$D/work"; : > "$D/work/STOP_ALL"
run "$D" hook "$(ev Read '{"file_path":"README.md"}' "" s1 PreToolUse)" ""
check_eq "64.4 stop flag spares interactive session (rc)" "$RC" 0
if [ -z "$ERR" ]; then
  ok "64.4 stop flag spares interactive session (no stop message)"
else
  bad "64.4 stop flag spares interactive session (no stop message)" "$ERR"
fi

run "$D" hook "$(ev Write '{"file_path":"app/main.py"}' coder s3 PreToolUse)" "TASK-ST"
check_eq "64.4 stop flag blocks a CTXGUARD_TASK role outside work/ (rc)" "$RC" 2
if printf '%s' "$ERR" | grep -qF "stop requested"; then
  ok "64.4 stop flag blocks a CTXGUARD_TASK role outside work/ (message)"
else
  bad "64.4 stop flag blocks a CTXGUARD_TASK role outside work/ (message)" "$ERR"
fi

# =========================================================== 3. warn kinds
D="$WORK/c3"; fresh "$D"; write_task "$D" "TASK-O"   # own task.json: the live one may carry a coder waiver
run "$D" hook "$(ev Edit '{"file_path":"app/main.py"}' "" s1 PreToolUse)" ""
check_eq "64.5 orch_work rc" "$RC" 0
assert_one_warn "64.5 orch_work: session Edit outside work/ warns" "$OUT"

for tool in Read Grep Bash; do
  case "$tool" in
    Read) ti='{"file_path":"README.md"}' ;;
    Grep) ti='{"pattern":"foo","path":"."}' ;;
    Bash) ti='{"command":"ls"}' ;;
  esac
  run "$D" hook "$(ev "$tool" "$ti" "" s1 PreToolUse)" ""
  assert_silent "64.5 no warn for session $tool" "$OUT"
done

run "$D" hook "$(ev Edit '{"file_path":"work/TASK-T1/handoff/code.md"}' "" s1 PreToolUse)" ""
assert_silent "64.5 no warn for a work/ path" "$OUT"

run "$D" hook "$(ev Edit '{"file_path":"docs/design/phase-9-x.md"}' "" s1 PreToolUse)" ""
assert_silent "64.5 no warn for a design/ path (coordinator-owned)" "$OUT"

run "$D" hook "$(ev Edit '{"file_path":".claude/state/task.json"}' "" s1 PreToolUse)" ""
assert_silent "64.5 no warn for a ledger path (coordinator-owned)" "$OUT"

D2="$WORK/c3w"; fresh "$D2"; write_task "$D2" "TASK-W" "" "approved for TASK-064"
run "$D2" hook "$(ev Edit '{"file_path":"app/main.py"}' "" s1 PreToolUse)" ""
assert_silent "64.5 no warn for session edit with a coder waiver" "$OUT"

D3="$WORK/c3big"; fresh "$D3"
TR="$D3/transcript.jsonl"
python3 -c "import json; print(json.dumps({'message':{'usage':{'input_tokens':50000}}}))" > "$TR"
run "$D3" hook "$(ev Read '{"file_path":"README.md"}' "" s1 PreToolUse "$TR")" ""
check_eq "64.5 orch_big rc" "$RC" 0
assert_one_warn "64.5 orch_big: large transcript context warns" "$OUT"

# =========================================================== 4. grants
D="$WORK/c4a"; fresh "$D"; write_task "$D" "TASK-G" '{"coder": [".claude/scripts/*"]}'
run "$D" hook "$(ev Write '{"file_path":".claude/scripts/new.sh"}' coder s4 PreToolUse)" "TASK-G"
check_eq "64.6 grant of a grantable glob allows the write" "$RC" 0

D="$WORK/c4b"; fresh "$D"; write_task "$D" "TASK-G2" '{"coder": [".claude/state/*"]}'
run "$D" hook "$(ev Write '{"file_path":".claude/state/evil.json"}' coder s5 PreToolUse)" "TASK-G2"
check_eq "64.6 grant of a non-grantable glob is still refused (rc)" "$RC" 2
assert_log_has "64.6 non-grantable grant logs grant_ignored" \
  "$D/.claude/agent_setup_violations.jsonl" 'c.get("kind")=="grant_ignored"'

# =========================================================== 5. SubagentStart/Stop events
D="$WORK/c5"; fresh "$D"
run "$D" event "$(ev "" "" coder s6 SubagentStart)" "TASK-E"
check_eq "64.7 SubagentStart rc" "$RC" 0
assert_log_has "64.7 SubagentStart logged" "$D/.claude/agent_setup_calls.jsonl" \
  'c.get("tool")=="SubagentStart" and c.get("role")=="coder" and c.get("task")=="TASK-E"'

echo dirty > "$D/src_dirty.txt"
mkdir -p "$D/work/TASK-E/handoff"
printf 'PROGRESS: IN_PROGRESS\nSKILLS: bash\n' > "$D/work/TASK-E/handoff/code.md"
run "$D" hook "$(ev Write '{"file_path":"src_dirty.txt"}' coder s6 PreToolUse "" agentE)" "TASK-E"
run "$D" event "$(ev "" "" coder s6 SubagentStop "" agentE)" "TASK-E"
check_eq "64.7 SubagentStop rc" "$RC" 0
if python3 - "$OUT" <<'PY'
import json, sys
lines = [json.loads(l) for l in sys.argv[1].splitlines() if l.strip()]
assert len(lines) == 2, f"expected 2 warn lines, got {len(lines)}"
d = [l for l in lines if "uncommitted edits" in l["systemMessage"]]
p = [l for l in lines if "IN_PROGRESS" in l["systemMessage"]]
assert len(d) == 1 and len(p) == 1, lines
assert "src_dirty.txt" in d[0]["systemMessage"] and "additionalContext" not in json.dumps(d[0])
assert p[0]["hookSpecificOutput"]["additionalContext"]
assert "permissionDecision" not in json.dumps(lines)
PY
then
  ok "64.7 SubagentStop prints dirty_stop + partial_stop, no permissionDecision"
else
  bad "64.7 SubagentStop prints dirty_stop + partial_stop" "$OUT"
fi
assert_log_has "64.7 dirty_stop logged" \
  "$D/.claude/agent_setup_violations.jsonl" 'c.get("kind")=="dirty_stop"'
assert_log_has "64.7 partial_stop logged" \
  "$D/.claude/agent_setup_violations.jsonl" 'c.get("kind")=="partial_stop"'

# F064-A: dirty_stop only names paths the stopping agent itself wrote/edited
D="$WORK/c5b"; fresh "$D"
mkdir -p "$D/docs/req"; echo main > "$D/docs/req/x"   # main-owned, uncommitted
run "$D" event "$(ev "" "" coder s8 SubagentStop "" agentB)" "TASK-F"
assert_silent "F064-A main-owned dirty file, role made no edits: no dirty_stop" "$OUT"
if grep '"TASK-F"' "$D/.claude/agent_setup_violations.jsonl" 2>/dev/null | grep -q dirty_stop; then
  bad "F064-A no dirty_stop record for main-owned file" "logged"
else
  ok "F064-A no dirty_stop record for main-owned file"
fi
echo mine > "$D/src_mine.txt"
run "$D" hook "$(ev Write '{"file_path":"src_mine.txt"}' coder s8 PreToolUse "" agentB)" "TASK-F"
run "$D" event "$(ev "" "" coder s8 SubagentStop "" agentB)" "TASK-F"
assert_dirty_warn "F064-A role edit left uncommitted warns" "$OUT"
case "$OUT" in *src_mine.txt*) ok "F064-A warning names the role's file";; *) bad "F064-A warning names the role's file" "$OUT";; esac
case "$OUT" in *docs/req/x*) bad "F064-A warning omits main's file" "$OUT";; *) ok "F064-A warning omits main's file";; esac
run "$D" event "$(ev "" "" coder s8 SubagentStop "" agentOther)" "TASK-F"
assert_silent "F064-A another agent's stop does not inherit the edit" "$OUT"
git -C "$D" add src_mine.txt
git -C "$D" commit -q -m mine
run "$D" event "$(ev "" "" coder s8 SubagentStop "" agentB)" "TASK-F"
assert_silent "F064-A role edit then committed: silent" "$OUT"

# F064-A: no agent id -> match on sid+role; git failure never breaks the hook
D="$WORK/c5c"; fresh "$D"
echo mine > "$D/src_noid.txt"
run "$D" hook "$(ev Write '{"file_path":"src_noid.txt"}' coder s9 PreToolUse)" "TASK-G"
run "$D" event "$(ev "" "" coder s9 SubagentStop)" "TASK-G"
assert_dirty_warn "F064-A no agent id: same sid+role edit warns" "$OUT"
case "$OUT" in *src_noid.txt*) ok "F064-A no agent id: warning names the file";; *) bad "F064-A no agent id: warning names the file" "$OUT";; esac
run "$D" event "$(ev "" "" coder s10 SubagentStop)" "TASK-G"
assert_silent "F064-A no agent id: other sid does not inherit the edit" "$OUT"
rm -rf "$D/.git"
run "$D" event "$(ev "" "" coder s9 SubagentStop)" "TASK-G"
check_eq "F064-A git error (no repo): hook still exits 0" "$RC" 0
assert_silent "F064-A git error (no repo): no warning" "$OUT"

# =========================================================== 6. msg_budget (design: warns ONCE)
D="$WORK/c6"; fresh "$D"
n=1
while [ "$n" -le 3 ]; do
  run "$D" hook "$(ev SendMessage '{"to":"main","message":"hi"}' coder agentA PreToolUse)" "TASK-M"
  n=$((n + 1))
done
assert_silent "64.8 SendMessage 1-3 under budget stay silent" "$OUT"
run "$D" hook "$(ev SendMessage '{"to":"main","message":"hi"}' coder agentA PreToolUse)" "TASK-M"
assert_one_warn "64.8 4th SendMessage over budget warns" "$OUT"
run "$D" hook "$(ev SendMessage '{"to":"main","message":"hi"}' coder agentA PreToolUse)" "TASK-M"
assert_silent "64.8 5th SendMessage does not warn again (design: once) - KNOWN GAP, expected to FAIL" "$OUT"

# =========================================================== 7. stats
D="$WORK/c7"; fresh "$D"
run "$D" event "$(ev "" "" coder s7 SubagentStart)" "TASK-S"
run "$D" hook "$(ev Read '{"file_path":"README.md"}' coder s7 PreToolUse)" "TASK-S"
run "$D" hook "$(ev SendMessage '{"to":"main","message":"hi"}' coder s7 PreToolUse)" "TASK-S"
run "$D" event "$(ev "" "" coder s7 SubagentStop)" "TASK-S"
run "$D" stats "" "" --task TASK-S
check_eq "64.9 stats rc" "$RC" 0
if printf '%s' "$OUT" | grep -qF "TASK-S"; then
  ok "64.9 stats mentions the task"
else
  bad "64.9 stats mentions the task" "$OUT"
fi
if printf '%s' "$OUT" | grep -qF "starts=1 stops=1 calls=2 sendmessage=1"; then
  ok "64.9 stats prints per-role starts/stops/calls"
else
  bad "64.9 stats prints per-role starts/stops/calls" "$OUT"
fi

# 69.10b: the rendered agent template tells roles the main session commits their edits
TMPL_OUT="$(cd "$KITPATCHED/.claude/hooks" && python3 -c 'import agent_setup as a
r = a.ROLES["coder"]
print(a.AGENT_TMPL.format(name="coder", desc="d", tools="t", turns=9, read=1, out=2, files=3, rules="", handoff=r["handoff"], spec=r["spec"]))' 2>&1)" || true
if printf '%s' "$TMPL_OUT" | grep -qF "The main session commits your edits"; then
  ok "69.10b agent template says the main session commits role edits"
else
  bad "69.10b agent template says the main session commits role edits" "$TMPL_OUT"
fi

# 74.4: skill-curator (patch route) may write patches under work/<T>/patches/, never a skill.
# Passes only once skill-curator is in .claude/agent_setup.json protect.roles.
D="$WORK/c74"; fresh "$D"
run "$D" hook "$(ev Write '{"file_path":".claude/skills/x/SKILL.md"}' skill-curator s74a PreToolUse)" "TASK-C"
check_eq "74.4 skill-curator Write to a skill is refused" "$RC" 2
run "$D" hook "$(ev Write '{"file_path":"work/TASK-C/patches/x.py"}' skill-curator s74b PreToolUse)" "TASK-C"
check_eq "74.4 skill-curator Write to work/<T>/patches is allowed" "$RC" 0

# 74.7 / RAW-00537: .claude/skills/* is grantable; a recorded grant lets the curator write a skill.
D="$WORK/c74g"; fresh "$D"; write_task "$D" "TASK-G" '{"skill-curator": [".claude/skills/*"]}'
run "$D" hook "$(ev Write '{"file_path":".claude/skills/x/SKILL.md"}' skill-curator s74c PreToolUse)" "TASK-G"
check_eq "74.7 skill-curator with a .claude/skills/* grant may Write a skill" "$RC" 0
run "$D" hook "$(ev Write '{"file_path":".claude/agents/coder.md"}' skill-curator s74d PreToolUse)" "TASK-G"
check_eq "74.7 the skills grant does not open agent files" "$RC" 2

echo "SUMMARY(agent-setup-hook): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

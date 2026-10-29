#!/usr/bin/env bash
# TASK-096 slice 3 (96.7 guard binding + B1/B2/U2, 96.18 quotes, 96.17 ask-once checkpoint, 96.6/96.12 hooks).
# Builds a throwaway repo from a copy of the kit; applies work/TASK-096/patches/*.py only while the
# copy lacks `def bound_task` / the hooks marker (a no-op once main applied them). Never touches the real .claude/.
# Run: bash .claude/tests/multi_guard_test.sh
set -Eeuo pipefail
unset TASK CTXGUARD_TASK || true
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(dirname "$KIT")"
PATCHES="$ROOT/work/TASK-096/patches"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export TMPDIR="$WORK/tmp"; mkdir -p "$TMPDIR"
PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); printf '%s\n' "$2" | sed 's/^/    /'; }
check_eq() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "got [$2] want [$3]"; fi; }

KP="$WORK/kit"; mkdir -p "$KP"
cp -r "$KIT" "$KP/.claude"
find "$KP/.claude" -name __pycache__ -prune -exec rm -rf {} +
rm -rf "$KP/.claude/tests" "$KP/.claude/state"; mkdir -p "$KP/.claude/state"
if ! grep -q "def bound_task" "$KP/.claude/hooks/agent_setup.py"; then
  python3 "$PATCHES/agent-setup-multi.py" "$KP/.claude/hooks/agent_setup.py" >/dev/null
fi
if ! grep -q "REQ-0060 multi" "$KP/.claude/hooks/stop-check.sh"; then
  python3 "$PATCHES/hooks-multi.py" "$KP/.claude/hooks" >/dev/null
fi

fresh() { # fresh <dir> [multi|legacy]
  local d="$1"; rm -rf "$d"; mkdir -p "$d/work" "$d/.claude/state"
  cp -r "$KP/.claude/." "$d/.claude/"
  printf '[]' > "$d/.claude/state/backlog.json"
  python3 - "$d" "${2:-multi}" <<'PY'
import json, sys
d, mode = sys.argv[1:3]
st = d + "/.claude/state/"
if mode == "multi":
    for t, sc in (("TASK-1", ["src/a/*"]), ("TASK-2", ["src/b/*"])):
        json.dump({"task_id": t, "state": "IMPLEMENTING", "scope": sc, "next": "x",
                   "roles": {"grants": {"coder": [".claude/scripts/*"]}} if t == "TASK-1" else {}},
                  open(st + "task.%s.json" % t, "w"))
    json.dump({"schema": 2, "task_id": "TASK-1", "state": "IMPLEMENTING"}, open(st + "task.json", "w"))
else:
    json.dump({"task_id": "TASK-1", "state": "IMPLEMENTING"}, open(st + "task.json", "w"))
PY
  git -C "$d" init -q; git -C "$d" config user.email t@e.invalid; git -C "$d" config user.name t
  git -C "$d" add -A; git -C "$d" commit -q -m init --allow-empty
}

ev() { python3 - "$@" <<'PY'
import json, sys
a = sys.argv[1:] + [""] * (7 - len(sys.argv[1:]))
tool, ti, typ, sid, he, extra, aid = a[:7]
o = {"tool_name": tool, "tool_input": json.loads(ti) if ti else {}, "session_id": sid,
     "hook_event_name": he or "PreToolUse", "cwd": "/tmp"}
if typ: o["agent_type"] = typ
if aid: o["agent_id"] = aid
if extra: o["stop_hook_active"] = True
print(json.dumps(o))
PY
}
run() { # run <dir> <hook|event> <json> [CTXGUARD_TASK]
  local d="$1" sub="$2" j="$3" t="${4:-}" e; e="$(mktemp)"
  if [ -n "$t" ]; then
    CTXGUARD_TASK="$t" python3  "$d/.claude/hooks/agent_setup.py" "$sub" --config "$d/.claude/agent_setup.json" <<<"$j" >/dev/null 2>"$e" && RC=0 || RC=$?
  else
    python3 "$d/.claude/hooks/agent_setup.py" "$sub" --config "$d/.claude/agent_setup.json" <<<"$j" >/dev/null 2>"$e" && RC=0 || RC=$?
  fi
  ERR="$(cat "$e")"; rm -f "$e"
}
W() { printf '{"file_path":"%s","content":"x"}' "$1"; }
B() { python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$1"; }

D="$WORK/r"
# --- B1 / B2 / U2 via env binding
fresh "$D"
run "$D" hook "$(ev Write "$(W "$D/work/TASK-2/x.md")" coder s1)" TASK-1; check_eq "B1 other task's work/ -> 2" "$RC" 2
case "$ERR" in *B1*) ok "B1 reason";; *) bad "B1 reason" "$ERR";; esac
run "$D" hook "$(ev Write "$(W "$D/work/TASK-1/x.md")" coder s1)" TASK-1; check_eq "own work/ -> 0" "$RC" 0
run "$D" hook "$(ev Write "$(W "$D/src/b/f.py")" coder s1)" TASK-1; check_eq "B2 other scope -> 2" "$RC" 2
case "$ERR" in *"owned by TASK-2"*) ok "B2 reason";; *) bad "B2 reason" "$ERR";; esac
run "$D" hook "$(ev Write "$(W "$D/src/a/f.py")" coder s1)" TASK-1; check_eq "own scope -> 0" "$RC" 0
run "$D" hook "$(ev Write "$(W "$D/misc/z.py")" coder s1)" TASK-1; check_eq "U2 outside every scope -> 0" "$RC" 0
if grep -q scope_out "$D/.claude/agent_setup_violations.jsonl" 2>/dev/null; then ok "U2 scope_out logged"; else bad "U2 scope_out logged" "no row"; fi
# --- 96.18 quotes
run "$D" hook "$(ev Bash "$(B 'echo x >"work/TASK-2/y"')" coder s1)" TASK-1; check_eq "quoted B1 redirect -> 2" "$RC" 2
run "$D" hook "$(ev Bash "$(B "echo x > 'src/b/f'")" coder s1)" TASK-1; check_eq "quoted B2 redirect -> 2" "$RC" 2
run "$D" hook "$(ev Bash "$(B 'echo x > work/TASK-1/y')" coder s1)" TASK-1; check_eq "own bash redirect -> 0" "$RC" 0
run "$D" hook "$(ev Bash "$(B 'ls work/TASK-2')" coder s1)" TASK-1; check_eq "read of other task -> 0" "$RC" 0
# --- per-task grants
run "$D" hook "$(ev Write "$(W "$D/.claude/scripts/x.sh")" coder s1)" TASK-1; check_eq "grant in own task file -> 0" "$RC" 0
run "$D" hook "$(ev Write "$(W "$D/.claude/scripts/x.sh")" coder s1)" TASK-2; check_eq "grant of another task -> 2" "$RC" 2
# --- launch queue + sticky bind (no env)
fresh "$D"
run "$D" hook "$(ev Agent '{"subagent_type":"coder","prompt":"TASK-2 item 1: go"}' "" m1)"; check_eq "main Agent call recorded -> 0" "$RC" 0
run "$D" hook "$(ev Write "$(W "$D/work/TASK-1/a.md")" coder m1 PreToolUse "" a1)"; check_eq "launch bound TASK-2: work/TASK-1 -> 2" "$RC" 2
run "$D" hook "$(ev Write "$(W "$D/work/TASK-2/a.md")" coder m1 PreToolUse "" a1)"; check_eq "sticky bind: work/TASK-2 -> 0" "$RC" 0
# --- first write under work/TASK-x binds
fresh "$D"
run "$D" hook "$(ev Write "$(W "$D/work/TASK-1/a.md")" tester m2 PreToolUse "" b1)"; check_eq "first write binds TASK-1" "$RC" 0
run "$D" hook "$(ev Write "$(W "$D/work/TASK-2/a.md")" tester m2 PreToolUse "" b1)"; check_eq "then work/TASK-2 -> 2" "$RC" 2
# --- legacy mode untouched
fresh "$D" legacy
run "$D" hook "$(ev Write "$(W "$D/work/TASK-2/x.md")" coder s3)" TASK-1; check_eq "legacy: no B1" "$RC" 0
# --- 96.17 ask-once checkpoint
fresh "$D"
SE() { ev "" "" coder s4 SubagentStop "$1"; }
run "$D" event "$(SE "")" TASK-1; check_eq "stop without handoff -> 2" "$RC" 2
case "$ERR" in *checkpoint*) ok "ask-once names checkpoint";; *) bad "ask-once names checkpoint" "$ERR";; esac
run "$D" event "$(SE 1)" TASK-1; check_eq "second stop is free" "$RC" 0
mkdir -p "$D/work/TASK-1/handoff"
printf 'PROGRESS: PARTIAL\nSKILLS: x\n' > "$D/work/TASK-1/handoff/code.md"
run "$D" event "$(SE "")" TASK-1; check_eq "PARTIAL without next: -> 2" "$RC" 2
printf 'PROGRESS: PARTIAL\nSKILLS: x\nnext: finish tests\n' > "$D/work/TASK-1/handoff/code.md"
run "$D" event "$(SE "")" TASK-1; check_eq "PARTIAL with next: -> 0" "$RC" 0
printf 'PROGRESS: COMPLETE\nSKILLS: x\n' > "$D/work/TASK-1/handoff/code.md"
run "$D" event "$(SE "")" TASK-1; check_eq "COMPLETE -> 0" "$RC" 0
rm -f "$D/work/TASK-1/handoff/code.md"
printf 'PROGRESS: COMPLETE\nSKILLS: x\n' > "$D/work/TASK-1/handoff/code-s9.md"
run "$D" event "$(SE "")" TASK-1; check_eq "only code-s9.md COMPLETE -> 0 (stem match)" "$RC" 0
printf 'PROGRESS: PARTIAL\nSKILLS: x\n' > "$D/work/TASK-1/handoff/code-s10.md"
run "$D" event "$(SE "")" TASK-1; check_eq "newest slice PARTIAL without next -> 2" "$RC" 2
fresh "$D" legacy
run "$D" event "$(SE "")" TASK-1; check_eq "legacy: no checkpoint block" "$RC" 0
# --- hooks (96.6 / 96.12 / 96.17 main)
fresh "$D"
hrc() { CLAUDE_PROJECT_DIR="$D" bash "$D/.claude/hooks/$1" <<<'{}' >"$WORK/o" 2>"$WORK/e" && echo 0 || echo $?; }
check_eq "stop-check clean multi -> 0" "$(hrc stop-check.sh)" 0
if grep -q "TASK-1 has no checkpoint.next" "$WORK/e"; then ok "stop-check WARN empty checkpoint"; else bad "stop-check WARN" "$(cat "$WORK/e")"; fi
python3 - "$D" <<'PY'
import json, sys
p = sys.argv[1] + "/.claude/state/task.TASK-1.json"
d = json.load(open(p)); d["checkpoint"] = {"done": [], "notes": "", "next": "go"}; json.dump(d, open(p, "w"))
PY
git -C "$D" add -A; git -C "$D" commit -q -m c
check_eq "stop-check with checkpoint -> 0" "$(hrc stop-check.sh)" 0
if grep -q "TASK-1 has no checkpoint" "$WORK/e"; then bad "no WARN when set" "$(cat "$WORK/e")"; else ok "no WARN when checkpoint set"; fi
echo dirty >> "$D/.claude/state/task.TASK-2.json"
check_eq "stop-check dirty state -> 2" "$(hrc stop-check.sh)" 2
git -C "$D" checkout -q -- .claude/state
python3 - "$D" <<'PY'
import json, sys
p = sys.argv[1] + "/.claude/state/task.TASK-2.json"
d = json.load(open(p)); d["state"] = "DONE"; json.dump(d, open(p, "w"))
PY
git -C "$D" add -A; git -C "$D" commit -q -m d
check_eq "stop-check DONE task failing workflow-check -> 2" "$(hrc stop-check.sh)" 2
check_eq "session-start multi -> 0" "$(hrc session-start.sh)" 0
if grep -q "TASK-2" "$WORK/o"; then ok "session-start lists tasks"; else bad "session-start lists tasks" "$(head -n 5 "$WORK/o")"; fi
check_eq "pre-compact multi -> 0" "$(hrc pre-compact-check.sh)" 0

echo "SUMMARY: pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

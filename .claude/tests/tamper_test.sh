#!/usr/bin/env bash
# TASK-069 69.9 (REQ-0026): tamper check after every role Bash call. A fake PreToolUse (`hook`) + Bash +
# PostToolUse (`post`) sequence in a scratch git repo that holds a copy of the kit:
#  T1 no change -> silent; T2 real python3 -c write to .claude/settings.json -> one `tamper`, a block that
#  names the file; T3 main session is never checked; T4 another actor's call in the window -> `tamper_unsure`,
#  no block; T5 untracked / .claude/state / docs changes -> silent; T6 fail-open (no snapshot, bad snapshot,
#  no git) -> `tamper_error`, rc 0, no block; T7 snapshot file removed after `post`; T8 settings.json wiring.
# Run: bash .claude/tests/tamper_test.sh   (KIT=<dir holding .claude/> tests another copy, e.g. git archive HEAD)
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KIT="${KIT:-$HERE}"
W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT
export TMPDIR="$W/tmp"
mkdir -p "$TMPDIR"
unset CTXGUARD_ROLE CTXGUARD_TASK || true

PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); printf '%s\n' "$2" | sed 's/^/    /'; }

R="$W/repo"
mkdir -p "$R"
cp -r "$KIT/.claude" "$R/.claude"
find "$R/.claude" -name __pycache__ -prune -exec rm -rf {} +
rm -rf "$R/.claude/tests" "$R/.claude/state"
mkdir -p "$R/.claude/state" "$R/docs/req"
echo '{}' > "$R/.claude/state/task.json"
echo x > "$R/docs/req/a.md"
echo "# c" > "$R/CLAUDE.md"
echo "# p" > "$R/security_prompt.md"
printf '.claude/agent_setup_*.jsonl\n__pycache__/\n' > "$R/.gitignore"
( cd "$R" && git init -q && git add -A >/dev/null 2>&1 && git -c user.name=t -c user.email=t@t commit -qm base )
VIOL="$R/.claude/agent_setup_violations.jsonl"

ev() { # ev <hook_event> <agent_type|-> <agent_id|-> <cmd>
  python3 - "$@" <<'PY'
import json, sys
he, role, aid, cmd = sys.argv[1:5]
o = {"tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": "s1", "hook_event_name": he}
if role != "-":
    o["agent_type"] = role
if aid != "-":
    o["agent_id"] = aid
print(json.dumps(o))
PY
}
pre()  { RC=0; (cd "$R" && python3 .claude/hooks/agent_setup.py hook --config .claude/agent_setup.json \
           <<<"$(ev PreToolUse "$1" "$2" "$3")" >"$W/pre.out" 2>"$W/pre.err") || RC=$?; }
post() { RC=0; (cd "$R" && python3 .claude/hooks/agent_setup.py post --config .claude/agent_setup.json \
           <<<"$(ev PostToolUse "$1" "$2" "x")" >"$W/post.out" 2>"$W/post.err") || RC=$?; }
count() { # count <kind>: number of violations_log lines of that kind
  if [ -f "$VIOL" ]; then python3 - "$VIOL" "$1" <<'PY'
import json, sys
n = 0
for l in open(sys.argv[1]):
    try:
        n += json.loads(l).get("kind") == sys.argv[2]
    except ValueError:
        pass
print(n)
PY
  else echo 0; fi
}
reset_repo() { # back to the committed state, no logs
  git -C "$R" checkout -q -- . || true
  git -C "$R" clean -qfdx >/dev/null 2>&1 || true
  rm -f "$VIOL" "$R/.claude/agent_setup_calls.jsonl" "$TMPDIR"/ctxguard-* 2>/dev/null || true
}
pyw() { python3 -c "open('$R/$1','a').write('\n# tamper\n')"; }

# T1 no change
reset_repo
pre coder a1 "echo hi"; post coder a1
if [ "$RC" = 0 ] && [ "$(count tamper)" = 0 ] && [ ! -s "$W/post.out" ]; then ok "T1 no change: silent"; else bad "T1 no change" "rc=$RC $(cat "$W/post.out")"; fi

# T2 a real write to .claude/settings.json by python3 -c
reset_repo
pre coder a1 "python3 -c x"; pyw .claude/settings.json; post coder a1
if [ "$RC" = 0 ] && [ "$(count tamper)" = 1 ]; then ok "T2a one tamper event, rc 0"; else bad "T2a" "rc=$RC tamper=$(count tamper)"; fi
if grep -q '"decision": "block"' "$W/post.out" && grep -q '.claude/settings.json' "$W/post.out"; then ok "T2b block names the file"; else bad "T2b" "$(cat "$W/post.out")"; fi
if grep -q 'TAMPER' "$W/post.err" && grep -q '.claude/settings.json' "$W/post.err"; then ok "T2c stderr line for the coordinator"; else bad "T2c" "$(cat "$W/post.err")"; fi
if ! ls "$TMPDIR"/ctxguard-* >/dev/null 2>&1; then ok "T7 snapshot removed after post"; else bad "T7" "$(ls "$TMPDIR")"; fi

# T2d other watched files and roles
for f in .claude/agent_setup.json .claude/hooks/agent_setup.py CLAUDE.md security_prompt.md; do
  reset_repo
  pre tester t1 "x"; pyw "$f"; post tester t1
  if [ "$(count tamper)" = 1 ] && grep -q "$f" "$W/post.out"; then ok "T2d tester changes $f"; else bad "T2d $f" "tamper=$(count tamper) $(cat "$W/post.out")"; fi
done
# a deleted tracked file
reset_repo
pre coder a1 "x"; rm -f "$R/CLAUDE.md"; post coder a1
if [ "$(count tamper)" = 1 ] && grep -q 'CLAUDE.md' "$W/post.out"; then ok "T2e deleted tracked file"; else bad "T2e" "$(cat "$W/post.out")"; fi

# T2f the route bash_deny leaves open (69.8 narrowed): bare `cd .claude && echo x > settings.json`
reset_repo
pre coder a1 "cd .claude && echo x > settings.json"
(cd "$R" && bash -c 'cd .claude && echo x > settings.json')
post coder a1
if [ "$(count tamper)" = 1 ] && grep -q '.claude/settings.json' "$W/post.out"; then ok "T2f cd .claude && echo > settings.json is caught as tamper"; else bad "T2f" "tamper=$(count tamper) $(cat "$W/post.out")"; fi

# T3 main session is never checked (no snapshot, no event, even when a file changes)
reset_repo
pre - - "x"; pyw .claude/settings.json; post - -
if [ "$RC" = 0 ] && [ "$(count tamper)" = 0 ] && [ "$(count tamper_error)" = 0 ] && [ ! -s "$W/post.out" ]; then ok "T3 main session skipped"; else bad "T3" "rc=$RC $(cat "$W/post.out")"; fi

# T4 another actor's call inside the window -> unsure, no block
reset_repo
pre coder a1 "x"; pyw .claude/settings.json
pre - - "coordinator edit"            # main session call in the window
post coder a1
if [ "$(count tamper_unsure)" = 1 ] && [ "$(count tamper)" = 0 ] && ! grep -q '"decision"' "$W/post.out"; then ok "T4a session call in window: tamper_unsure, no block"; else bad "T4a" "unsure=$(count tamper_unsure) tamper=$(count tamper) $(cat "$W/post.out")"; fi
reset_repo
pre coder a1 "x"; pyw .claude/settings.json
pre tester t1 "other role"
post coder a1
if [ "$(count tamper_unsure)" = 1 ] && [ "$(count tamper)" = 0 ]; then ok "T4b other role's call in window: tamper_unsure"; else bad "T4b" "unsure=$(count tamper_unsure) tamper=$(count tamper)"; fi
# two roles of one session keep separate snapshots, and each is not "another actor" to itself
reset_repo
pre coder a1 "x"; pre coder a2 "y"; post coder a2; pyw CLAUDE.md; post coder a1
if [ "$(count tamper_unsure)" = 1 ] && [ "$(count tamper)" = 0 ]; then ok "T4c per-agent snapshot; other agent's call seen"; else bad "T4c" "unsure=$(count tamper_unsure) tamper=$(count tamper)"; fi

# T5 not watched: untracked, .claude/state, docs/req, bytecode
reset_repo
pre coder a1 "x"
echo y >> "$R/.claude/state/task.json"; echo y >> "$R/docs/req/a.md"
mkdir -p "$R/.claude/hooks/__pycache__"; echo y > "$R/.claude/hooks/__pycache__/a.pyc"; echo y > "$R/.claude/hooks/new_untracked.py"
post coder a1
if [ "$RC" = 0 ] && [ "$(count tamper)" = 0 ] && [ "$(count tamper_unsure)" = 0 ] && [ ! -s "$W/post.out" ]; then ok "T5 state/docs/untracked/bytecode: silent"; else bad "T5" "$(cat "$W/post.out") $(cat "$VIOL" 2>/dev/null)"; fi

# T6 fail-open
reset_repo
post coder a9
if [ "$RC" = 0 ] && [ "$(count tamper_error)" = 1 ] && [ ! -s "$W/post.out" ]; then ok "T6a no snapshot: tamper_error, no block"; else bad "T6a" "rc=$RC err=$(count tamper_error)"; fi
reset_repo
pre coder a1 "x"; echo '{not json' > "$TMPDIR/ctxguard-s1-a1.json"; pyw .claude/settings.json; post coder a1
if [ "$RC" = 0 ] && [ "$(count tamper_error)" = 1 ] && [ "$(count tamper)" = 0 ] && ! grep -q decision "$W/post.out"; then ok "T6b corrupt snapshot: tamper_error, no block"; else bad "T6b" "rc=$RC $(cat "$W/post.out")"; fi
reset_repo
mv "$R/.git" "$W/git.off"
pre coder a1 "x"; RC1=$RC; post coder a1
mv "$W/git.off" "$R/.git"
if [ "$RC1" = 0 ] && [ "$RC" = 0 ] && [ "$(count tamper_error)" -ge 1 ] && ! grep -q decision "$W/post.out"; then ok "T6c no git repo: tamper_error, both calls rc 0"; else bad "T6c" "pre=$RC1 post=$RC err=$(count tamper_error)"; fi
reset_repo
post coder a1 </dev/null; RC=0
(cd "$R" && python3 .claude/hooks/agent_setup.py post --config .claude/agent_setup.json <<<"not json" >/dev/null 2>&1) || RC=$?
if [ "$RC" = 0 ]; then ok "T6d bad stdin: rc 0"; else bad "T6d" "rc=$RC"; fi

# T9 two concurrent Bash calls of one agent: the 2nd snapshot overwrites the 1st, so the 2nd post has
# none -> tamper_error (fail-open); the first post still checks against the newer snapshot
reset_repo
pre coder a1 "call one"; pre coder a1 "call two"; post coder a1; RC_A=$RC; post coder a1
if [ "$RC_A" = 0 ] && [ "$RC" = 0 ] && [ "$(count tamper_error)" = 1 ] && [ "$(count tamper)" = 0 ] && [ ! -s "$W/post.out" ]; then ok "T9a concurrent calls: 2nd post tamper_error, rc 0, no block"; else bad "T9a" "rc=$RC_A/$RC err=$(count tamper_error) $(cat "$W/post.out")"; fi
reset_repo
pre coder a1 "call one"; pre coder a1 "call two"; pyw .claude/settings.json; post coder a1
if [ "$(count tamper)" = 1 ] && grep -q '.claude/settings.json' "$W/post.out"; then ok "T9b concurrent calls: a real change is still caught"; else bad "T9b" "tamper=$(count tamper) $(cat "$W/post.out")"; fi

# T10 a call the guard refuses takes no snapshot (it never runs, so no post); a stale one would be overwritten anyway
reset_repo
pre coder a1 "git commit -m x"; REFUSED=$RC
if [ "$REFUSED" = 2 ] && ! ls "$TMPDIR"/ctxguard-* >/dev/null 2>&1; then ok "T10a refused call: rc 2, no snapshot left behind"; else bad "T10a" "rc=$REFUSED $(ls "$TMPDIR")"; fi
echo '{"files":{},"offset":0}' > "$TMPDIR/ctxguard-s1-a1.json"   # force a stale snapshot
pyw CLAUDE.md                      # a change after it, before the next call
pre coder a1 "echo ok"; post coder a1
if [ "$RC" = 0 ] && [ "$(count tamper)" = 0 ] && [ "$(count tamper_error)" = 0 ] && [ ! -s "$W/post.out" ]; then ok "T10b next call overwrites the stale snapshot: no false tamper"; else bad "T10b" "tamper=$(count tamper) err=$(count tamper_error) $(cat "$W/post.out")"; fi

# T11 a broken agent_setup.json (default role list) is still caught
reset_repo
pre coder a1 "x"; echo '{broken' > "$R/.claude/agent_setup.json"; post coder a1
if [ "$RC" = 0 ] && [ "$(count tamper)" = 1 ] && grep -q '.claude/agent_setup.json' "$W/post.out"; then ok "T11 broken agent_setup.json: tamper caught"; else bad "T11" "rc=$RC tamper=$(count tamper) $(cat "$W/post.out")"; fi

# T12 a watched file the coordinator already left dirty (uncommitted) before the role's call
reset_repo
pyw CLAUDE.md
pre coder a1 "x"; post coder a1
if [ "$RC" = 0 ] && [ "$(count tamper)" = 0 ] && [ "$(count tamper_unsure)" = 0 ] && [ ! -s "$W/post.out" ]; then ok "T12a pre-existing dirty file, unchanged by the call: silent"; else bad "T12a" "tamper=$(count tamper) $(cat "$W/post.out")"; fi
reset_repo
pyw CLAUDE.md
pre coder a1 "x"; pyw CLAUDE.md; post coder a1
if [ "$(count tamper)" = 1 ] && grep -q 'CLAUDE.md' "$W/post.out"; then ok "T12b pre-existing dirty file changed again by the call: tamper"; else bad "T12b" "tamper=$(count tamper) $(cat "$W/post.out")"; fi

# T13 a change covered by the acting role's own grant (task.json roles.grants, F69-7)
GF=.claude/scripts/scratch-kit.sh
setgrant() { python3 - "$R/.claude/state/task.json" "$1" <<'PY13'
import json, sys
json.dump({"roles": {"grants": {sys.argv[2]: [".claude/scripts/*"]}}}, open(sys.argv[1], "w"))
PY13
}
reset_repo; setgrant coder
pre coder a1 "x"; pyw "$GF"; post coder a1
if [ "$RC" = 0 ] && [ "$(count tamper)" = 0 ] && [ "$(count tamper_unsure)" = 0 ] && [ ! -s "$W/post.out" ]; then ok "T13a own grant covers the path: no event, no block"; else bad "T13a" "tamper=$(count tamper) $(cat "$W/post.out")"; fi
reset_repo
pre coder a1 "x"; pyw "$GF"; post coder a1
if [ "$(count tamper)" = 1 ] && grep -q "$GF" "$W/post.out"; then ok "T13b no grant: tamper"; else bad "T13b" "tamper=$(count tamper) $(cat "$W/post.out")"; fi
reset_repo; setgrant tester
pre coder a1 "x"; pyw "$GF"; post coder a1
if [ "$(count tamper)" = 1 ] && grep -q "$GF" "$W/post.out"; then ok "T13c another role's grant does not cover coder: tamper"; else bad "T13c" "tamper=$(count tamper) $(cat "$W/post.out")"; fi
reset_repo; setgrant coder
pre coder a1 "x"; pyw "$GF"; pyw CLAUDE.md; post coder a1
if [ "$(count tamper)" = 1 ] && grep -q 'CLAUDE.md' "$W/post.out" && ! grep -q "$GF" "$W/post.out"; then ok "T13d grant covers only its glob: CLAUDE.md still tamper"; else bad "T13d" "tamper=$(count tamper) $(cat "$W/post.out")"; fi

# T8 settings.json wiring
if python3 - "$KIT/.claude/settings.json" <<'PY'
import json, sys
h = json.load(open(sys.argv[1]))["hooks"]["PostToolUse"]
ok = [e for e in h if e.get("matcher") == "Bash" and any("agent_setup.py" in x["command"] and " post " in x["command"] for x in e["hooks"])]
sys.exit(0 if len(ok) == 1 else 1)
PY
then ok "T8 settings.json PostToolUse Bash -> agent_setup.py post"; else bad "T8" "entry missing"; fi

echo "SUMMARY(tamper): pass=$PASS fail=$FAIL"
[ "$FAIL" = 0 ]

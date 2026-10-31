#!/usr/bin/env bash
# TASK-098 process speed-up tools: brief.sh (P10-P12), run_all.sh --changed (P21-P23),
# process_metrics.py (P24-P26). Fixtures live in mktemp dirs; no real .claude/state is copied.
# 98.2 raw link --ac / --note (P6-P9) runs in a scratch git repo copied from $SRC/.claude.
set -Eeuo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="${PS_SRC:-$KIT}"        # PS_SRC = a git archive of old scripts, for the bite proof
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
    bad "$name (rc=$rc, want $want_rc)"; printf '%s\n' "$out" | sed 's/^/    /'; return
  fi
  if [ -n "$want_out" ] && ! printf '%s' "$out" | grep -qF -- "$want_out"; then
    bad "$name (output lacks '$want_out')"; printf '%s\n' "$out" | sed 's/^/    /'; return
  fi
  ok "$name"
}

tree_hash() { (cd "$1" && find . -type f -print0 | sort -z | xargs -0 cksum | cksum); }

# ---- brief.sh fixture ----
BR="$WORK/brief"
mkdir -p "$BR/.claude/state" "$BR/docs/design" "$BR/work/TASK-900/handoff"
cat > "$BR/docs/design/phase-900-x.md" <<'EOF'
# Phase 900
### 900.1 First item, do the thing
body
### 900.2 Second item
Skills: crosscheck, commit, nosuch
body
EOF
for n in bash python crosscheck commit security; do
  mkdir -p "$BR/.claude/skills/$n"; printf '# %s\n' "$n" > "$BR/.claude/skills/$n/SKILL.md"
done
mkdir -p "$BR/.claude/agents"
printf -- '---\nname: coder\nskills: coding, token-efficiency\n---\n' > "$BR/.claude/agents/coder.md"
cat > "$BR/.claude/state/task.TASK-902.json" <<'EOF'
{"design":{"path":"docs/design/phase-900-x.md"},
 "scope":["CLAUDE.md",".claude/scripts/foo.sh","docs/x.md"],
 "roles":{"grants":{"coder":[".claude/scripts/*"]}}}
EOF
cat > "$BR/.claude/state/task.TASK-903.json" <<'EOF'
{"design":{"path":"docs/design/phase-900-x.md"},"scope":["docs/a.md","x.json"]}
EOF
cat > "$BR/.claude/state/task.TASK-904.json" <<'EOF'
{"design":{"path":"docs/design/phase-900-x.md"},"scope":["a.sh","x.py"]}
EOF
cat > "$BR/.claude/state/task.TASK-900.json" <<'EOF'
{"design":{"path":"docs/design/phase-900-x.md"},
 "scope":[".claude/scripts/foo.sh","tests/run_all.sh"],
 "roles":{"grants":{"coder":[".claude/scripts/*"]}}}
EOF
cat > "$BR/.claude/agent_setup.json" <<'EOF'
{"protect":{"read_globs":["/x/pentest_source_code*"],"write_globs":["CLAUDE.md",".claude/scripts/*",".claude/agents/*"]}}
EOF
printf 'PROGRESS: COMPLETE\n' > "$BR/work/TASK-900/handoff/design.md"
BRIEF="$SRC/.claude/scripts/brief.sh"

out="$(BRIEF_ROOT="$BR" bash "$BRIEF" TASK-900 900.1 coder --turns 20 --peers "Nova (designer)=abc" 2>&1)" || out="RC-FAIL: $out"
p10=1
for s in "TASK-900 item 900.1: First item, do the thing" "tasks.sh show TASK-900" \
         "docs/design/phase-900-x.md §900.1" "work/TASK-900/handoff/design.md" \
         "Scope: .claude/scripts/foo.sh, tests/run_all.sh" "Grants (coder): .claude/scripts/*" \
         "Forbidden: " "reports/" "Edit/Write only" "Peers: Nova (designer)=abc" \
         "Turns: 20. Expect: 4 min." "Checks: tests/run_all.sh --changed" \
         "Output: work/TASK-900/handoff/code.md. Reply ≤ 5 lines."; do
  printf '%s' "$out" | grep -qF -- "$s" || { p10=0; echo "    missing: $s"; }
done
if [ "$p10" -eq 1 ]; then ok "P10 brief has every field"; else bad "P10 brief has every field"; printf '%s\n' "$out" | sed 's/^/    /'; fi
l1="$(printf '%s\n' "$out" | head -n 1)"
case "$l1" in "TASK-900 item 900.1:"*) ok "P10b line 1 is task + item" ;; *) bad "P10b line 1 ($l1)" ;; esac

expect "P11a unknown item rc 1" 1 "not found" env BRIEF_ROOT="$BR" bash "$BRIEF" TASK-900 900.9 coder
expect "P11b unknown role rc 1" 1 "unknown role" env BRIEF_ROOT="$BR" bash "$BRIEF" TASK-900 900.1 janitor
expect "P11c unknown task rc 1" 1 "no state file" env BRIEF_ROOT="$BR" bash "$BRIEF" TASK-901 900.1 coder
expect "P11d tester default turns" 0 "Turns: 30. Expect: 6 min." env BRIEF_ROOT="$BR" bash "$BRIEF" TASK-900 900.2 tester

B() { BRIEF_ROOT="$BR" bash "$BRIEF" "$@"; }
expect "P13 coder .sh scope -> Load: bash" 0 "Load: bash (Skill tool; preloaded: coding, token-efficiency)" B TASK-900 900.1 coder
expect "P13b .sh + .py scope -> bash, python" 0 "Load: bash, python (" B TASK-904 900.1 coder
out="$(B TASK-900 900.2 tester 2>&1)" || true
if printf '%s' "$out" | grep -qE "^Load: .*bash.*crosscheck" ; then ok "P14 tester 900.2 loads bash + crosscheck"; else bad "P14 tester 900.2 loads bash + crosscheck"; fi
out="$(B TASK-900 900.1 tester 2>&1)" || true
if printf '%s' "$out" | grep -E "^Load:" | grep -qF crosscheck; then bad "P14b 900.1 has no crosscheck"; else ok "P14b 900.1 has no crosscheck"; fi
out="$(B TASK-900 900.2 tester 2>&1)" || true
if printf '%s' "$out" | grep -qF "nosuch" && ! printf '%s' "$out" | grep -E "^Load:" | grep -qE "commit|nosuch"; then
  ok "P15 commit + nosuch skipped with a warning"; else bad "P15 commit + nosuch skipped with a warning"; printf '%s\n' "$out" | sed 's/^/    /'; fi
printf -- '---\nname: coder\nskills: coding, bash\n---\n' > "$BR/.claude/agents/coder.md"
out="$(B TASK-900 900.1 coder 2>&1)" || true
if printf '%s' "$out" | grep -qF "Load: (none)"; then ok "P16 preloaded bash not repeated"; else bad "P16 preloaded bash not repeated"; fi
printf -- '---\nname: coder\nskills: coding, token-efficiency\n---\n' > "$BR/.claude/agents/coder.md"
expect "P17 docs-only coder -> none" 0 "Load: (none)" B TASK-903 900.1 coder
expect "P17b docs-only tester -> bash" 0 "Load: bash" B TASK-903 900.1 tester
expect "P18 --refresh designer" 0 "model: sonnet" B TASK-900 900.1 designer --refresh
expect "P18b --refresh coder rc 1" 1 "designer only" B TASK-900 900.1 coder --refresh
expect "P18c --load adds a skill" 0 "Load: bash, security" B TASK-900 900.1 coder --load security
out="$(B TASK-902 900.1 coder 2>&1)" || true
if printf '%s' "$out" | grep -qF "Patch route: CLAUDE.md" && ! printf '%s' "$out" | grep -F "Patch route:" | grep -qF "foo.sh"; then
  ok "P19 Patch route lists CLAUDE.md, not the granted script"; else bad "P19 Patch route"; printf '%s\n' "$out" | sed 's/^/    /'; fi
if printf '%s' "$(B TASK-900 900.1 coder 2>&1)" | grep -qF "Patch route:"; then bad "P19b no Patch route when all granted"; else ok "P19b no Patch route when all granted"; fi

h0="$(tree_hash "$BR")"
BRIEF_ROOT="$BR" bash "$BRIEF" TASK-900 900.1 verifier >/dev/null 2>&1 || true
h1="$(tree_hash "$BR")"
if [ "$h0" = "$h1" ]; then ok "P12 brief writes no file"; else bad "P12 brief writes no file"; fi

# ---- run_all.sh --changed fixture ----
RA="$WORK/ra"
mkdir -p "$RA/tests" "$RA/.claude/tests" "$RA/lib"
cp "$SRC/tests/run_all.sh" "$RA/tests/run_all.sh"
for n in alpha beta; do
  printf '#!/usr/bin/env bash\necho "SUMMARY(%s): pass=1 fail=0"\n' "$n" > "$RA/tests/${n}_test.sh"
done
printf 'lib/a.sh\talpha\nlib/b.sh\tbeta\n' > "$RA/tests/suite_map.txt"
git -C "$RA" init -q
git -C "$RA" -c user.email=t@t -c user.name=t add -A
git -C "$RA" -c user.email=t@t -c user.name=t commit -q -m init
echo x > "$RA/lib/a.sh"
RUN="$RA/tests/run_all.sh"

out="$(bash "$RUN" --changed 2>&1)" || true
if printf '%s' "$out" | grep -qF "PASS alpha_test.sh" && ! printf '%s' "$out" | grep -qF "beta_test.sh" \
   && printf '%s' "$out" | grep -qF "SUMMARY(run_all:changed): 1 suite(s), all passed"; then
  ok "P21 mapped file runs only its suite"; else bad "P21 mapped file runs only its suite"; printf '%s\n' "$out" | sed 's/^/    /'; fi

echo y > "$RA/lib/zzz.sh"
out="$(bash "$RUN" --changed 2>&1)" || true
if printf '%s' "$out" | grep -qF -- "--changed: unmapped lib/zzz.sh, full run" \
   && printf '%s' "$out" | grep -qF "SUMMARY(run_all:changed): 2 suite(s)"; then
  ok "P22 unmapped file runs the full set"; else bad "P22 unmapped file runs the full set"; printf '%s\n' "$out" | sed 's/^/    /'; fi
rm -f "$RA/lib/zzz.sh" "$RA/lib/a.sh"
git -C "$RA" checkout -q -- . 2>/dev/null || true
out="$(bash "$RUN" --changed 2>&1)" || true
if printf '%s' "$out" | grep -qF "no changed files, full run" && printf '%s' "$out" | grep -qF "2 suite(s)"; then
  ok "P22b no change runs the full set"; else bad "P22b no change runs the full set"; printf '%s\n' "$out" | sed 's/^/    /'; fi

echo z > "$RA/lib/b.sh"
out="$(bash "$RUN" 2>&1)" || true
if printf '%s' "$out" | grep -qE "^SUMMARY\(run_all\): 2 suite" ; then
  ok "P23 plain run keeps the evidence label"; else bad "P23 plain run keeps the evidence label"; printf '%s\n' "$out" | sed 's/^/    /'; fi
out="$(bash "$RUN" --changed 2>&1)" || true
if printf '%s' "$out" | grep -qE "^SUMMARY\(run_all\):"; then
  bad "P23b --changed never prints the evidence label"; else ok "P23b --changed never prints the evidence label"; fi

# ---- process_metrics.py fixture ----
PM="$WORK/pm"
mkdir -p "$PM/.claude/state" "$PM/docs/req/raw" "$PM/work/TASK-800/handoff"
git -C "$PM" init -q
echo a > "$PM/f"; git -C "$PM" add f
git -C "$PM" -c user.email=t@t -c user.name=t commit -q -m "wip(x): TASK-800 a" -m "Task: TASK-800"
git -C "$PM" -c user.email=t@t -c user.name=t commit -q --allow-empty -m "feat: TASK-800 b" -m "Task: TASK-800" -m "State: IMPLEMENTING"
git -C "$PM" -c user.email=t@t -c user.name=t commit -q --allow-empty -m "other" -m "Task: TASK-801"
cat > "$PM/.claude/state/phase-log.md" <<'EOF'
## DESIGN - TASK-800 - 2026-10-01T10:00:00Z
x
## IMPLEMENTING - TASK-800 - 2026-10-01T10:30:00Z
x
## DONE - TASK-800 - 2026-10-01T11:30:00Z
EOF
printf '{"picked_at":"2026-10-01T10:00:00Z","user_notes":["a","b"]}\n' > "$PM/.claude/state/task.TASK-800.json"
printf 'PROGRESS: PARTIAL\n' > "$PM/work/TASK-800/handoff/code.md"
{
  echo '{"ts":1,"task":"TASK-800","tool":"SubagentStart"}'
  echo '{"ts":2,"task":"TASK-800","tool":"SubagentStart"}'
  echo '{"ts":3,"task":"TASK-801","tool":"SubagentStart"}'
} > "$PM/.claude/agent_setup_calls.jsonl"
{
  echo '{"ts":1,"task":"TASK-800","kind":"protected"}'
  echo '{"ts":2,"task":"TASK-800","kind":"scope_out"}'
  echo '{"ts":3,"task":"TASK-800","kind":"orch_work"}'
  echo '{"ts":4,"task":"TASK-801","kind":"protected"}'
} > "$PM/.claude/agent_setup_violations.jsonl"
METRICS="$SRC/.claude/scripts/process_metrics.py"

js="$(python3 "$METRICS" TASK-800 --root "$PM" --json 2>/dev/null || echo '{}')"
chk() { printf '%s' "$js" | jq -e "$1" >/dev/null 2>&1; }
if chk '.tasks["TASK-800"] | .commits==2 and .wip==1 and .transitions==1 and .briefs==2 and .refusals==1 and .scope_out==1 and .partial==1 and .user_notes==2 and .minutes_total==90 and .minutes_by_state.DESIGN==30'; then
  ok "P24 metrics counted from git, logs and phase-log"
else bad "P24 metrics counted from git, logs and phase-log"; printf '%s\n' "$js" | sed 's/^/    /'; fi

python3 "$METRICS" TASK-800 --root "$PM" --json > "$WORK/base.json" 2>/dev/null || true
expect "P25 compare against itself has zero delta" 0 "commits	2.0	2.0	+0.0" \
  python3 "$METRICS" TASK-800 --root "$PM" --compare "$WORK/base.json"
expect "P25b unreadable baseline fails" 1 "cannot read baseline" \
  python3 "$METRICS" TASK-800 --root "$PM" --compare "$WORK/nope.json"

EM="$WORK/empty"; mkdir -p "$EM"; git -C "$EM" init -q
expect "P26 missing logs: zeros, rc 0, WARN" 0 "WARN" python3 "$METRICS" TASK-800 --root "$EM"
js="$(python3 "$METRICS" TASK-800 --root "$EM" --json 2>/dev/null || echo '{}')"
if chk '.tasks["TASK-800"] | .commits==0 and .briefs==0 and .minutes_total==0'; then
  ok "P26b zeros for a task with no data"; else bad "P26b zeros for a task with no data"; fi

# ---- 98.2 raw link --ac / --note (P6-P9) ----
RL="$WORK/rawlink"
mkdir -p "$RL/docs/req" "$RL/.claude/state"
cp -r "$SRC/.claude/req" "$SRC/.claude/scripts" "$RL/.claude/"
find "$RL/.claude" -name __pycache__ -prune -exec rm -rf {} +
cp "$KIT/docs/req/config.json" "$RL/docs/req/config.json"
git -C "$RL" init -q
RLREQ() { (cd "$RL" && CLAUDE_PROJECT_DIR="$RL" python3 .claude/req/req.py "$@"); }
REQ1="$RL/docs/req/items/REQ-0001.md"; REQ2="$RL/docs/req/items/REQ-0002.md"
RLREQ init >/dev/null 2>&1 || true
RLREQ new --title "Link target" --text "WHEN x, the tool SHALL y." >/dev/null 2>&1 || true
RLREQ new --title "Done target" --text "WHEN x, the tool SHALL y." >/dev/null 2>&1 || true
for t in "first long prompt about export formats" "second long prompt about json export" \
         "third long prompt for the done item" "fourth long prompt for the note" "fifth long prompt without backlog"; do
  RLREQ raw add --text "$t" >/dev/null 2>&1 || true
done

expect "P6 --ac appends AC1" 0 "REQ-0001 +AC1" RLREQ raw link RAW-00001 --to REQ-0001 --ac "export as csv"
expect "P6b second --ac gets AC2" 0 "REQ-0001 +AC2" RLREQ raw link RAW-00002 --to REQ-0001 --ac "export as json"
if grep -qF -- "- [ ] AC1: export as csv (RAW-00001)" "$REQ1" && grep -qF -- "- [ ] AC2: export as json (RAW-00002)" "$REQ1" \
   && grep -qF "RAW-00002: added AC2" "$REQ1"; then
  ok "P6c AC lines and progress log are in the REQ"; else bad "P6c AC lines and progress log are in the REQ"; fi

expect "P7 ac ticks the new id" 0 "" RLREQ ac REQ-0001 AC2 --evidence "unit"
if grep -qF -- "- [x] AC2: export as json" "$REQ1" && grep -qF -- "- [ ] AC1: export as csv" "$REQ1"; then
  ok "P7b only AC2 is ticked"; else bad "P7b only AC2 is ticked"; fi

sed -i.bak 's/^status: .*/status: DONE/' "$REQ2"; rm -f "$REQ2.bak"
h_before="$(cksum "$REQ2" "$RL/docs/req/raw/RAW-00003.md")"
expect "P8 --ac on a DONE REQ is refused" 2 "VERIFIED/DONE" RLREQ raw link RAW-00003 --to REQ-0002 --ac "late ac"
h_after="$(cksum "$REQ2" "$RL/docs/req/raw/RAW-00003.md")"
if [ "$h_before" = "$h_after" ]; then ok "P8b REQ and RAW files are byte-unchanged"; else bad "P8b REQ and RAW files are byte-unchanged"; fi

printf '%s\n' '{"task_id": "TASK-901", "state": "DESIGN"}' > "$RL/.claude/state/task.json"
printf '%s\n' '[]' > "$RL/.claude/state/backlog.json"
expect "P9 --note active notes the raw id" 0 "NOTED: RAW-00004" \
  RLREQ raw link RAW-00004 --to REQ-0001 --ac "keep a note" --note active
if grep -qE '"raw": *"RAW-00004"' "$RL/.claude/state/task.json"; then ok "P9b user_notes row holds the raw id"; else bad "P9b user_notes row holds the raw id"; fi
rm -f "$RL/.claude/state/backlog.json" "$RL/.claude/state/task.json"
expect "P9c missing backlog: WARN, rc 0" 0 "WARN note" \
  RLREQ raw link RAW-00005 --to REQ-0001 --ac "no backlog" --note active
if grep -qF -- "- [ ] AC4: no backlog" "$REQ1"; then ok "P9d ledger write stands after a failed note"; else bad "P9d ledger write stands after a failed note"; fi

# ---- 98.1 wip.sh (P1-P5), 98.4 auto grants (P13-P17), F-97-7 (P18) ----
WF="$WORK/wipfix"
wfix() { # wfix <dir> [scope-json]: throwaway repo with TASK-1 (DESIGN) and a queued TASK-2
  local d="$1" sc="${2:-[\"src/a/*\"]}"
  rm -rf "$d"; mkdir -p "$d/.claude/state" "$d/src/a" "$d/src/b" "$d/work/TASK-1" "$d/docs/req/items"
  cp -r "$SRC/.claude/scripts" "$SRC/.claude/hooks" "$SRC/.claude/req" "$SRC/.claude/agent_setup.json" "$d/.claude/"
  find "$d/.claude" -name __pycache__ -prune -exec rm -rf {} +
  printf -- '---\nid: REQ-0007\ntasks: [TASK-1]\n---\nbody\n' > "$d/docs/req/items/REQ-0007.md"
  printf -- '---\nid: REQ-0008\ntasks: [TASK-9]\n---\nbody\n' > "$d/docs/req/items/REQ-0008.md"
  printf 'idx\n' > "$d/docs/req/INDEX.md"
  python3 - "$d" "$sc" <<'PY'
import json, sys
d, sc = sys.argv[1], json.loads(sys.argv[2])
st = d + "/.claude/state/"
import os
os.makedirs(d + "/docs/design", exist_ok=True)
open(d + "/docs/design/phase-1-one.md", "w").write("design\n")
task = {"task_id": "TASK-1", "title": "one", "state": "DESIGN", "requirement": "r",
        "acceptance_criteria": ["a"],
        "design": {"status": "completed", "summary": "s", "path": "docs/design/phase-1-one.md"},
        "implementation": {"status": "pending", "files": []},
        "unit_test": {"status": "pending", "command": "", "result": ""},
        "security": {"status": "pending", "result": ""},
        "verification": {"status": "pending", "evidence": []},
        "report": {"status": "pending", "path": ""},
        "updated_at": "2026-01-01T00:00:00Z", "updated_by": "test", "next": "go"}
json.dump(task, open(st + "task.json", "w"), indent=2)
json.dump([{"task_id": "TASK-1", "status": "active", "title": "t1", "priority": "normal", "scope": sc},
           {"task_id": "TASK-2", "status": "queued", "title": "t2", "priority": "normal", "scope": sc}],
          open(st + "backlog.json", "w"))
PY
  printf '# Phase Log\n\n## DESIGN - TASK-1 - 2026-01-01T00:00:00Z\n' > "$d/.claude/state/phase-log.md"
  git -C "$d" init -q; git -C "$d" config user.email t@e.invalid; git -C "$d" config user.name t
  git -C "$d" add -A; git -C "$d" commit -q -m init --no-verify
  (cd "$d" && TASKS_ROOT="$d" bash "$d/.claude/scripts/tasks.sh" migrate >/dev/null 2>&1) || true
  git -C "$d" add -A; git -C "$d" commit -q -m migrated --no-verify
}
WIP() { (cd "$WF" && TASKS_ROOT="$WF" bash "$WF/.claude/scripts/wip.sh" "$@"); }
WTASKS() { (cd "$WF" && TASKS_ROOT="$WF" bash "$WF/.claude/scripts/tasks.sh" "$@"); }
wstate() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("state"))' "$WF/.claude/state/task.TASK-1.json"; }

wfix "$WF"
echo x > "$WF/src/a/f.py"
rc=0; out="$(WIP TASK-1 "add f" -- src/a/f.py 2>&1)" || rc=$?
if [ "$rc" -eq 0 ] && [ "$(printf '%s\n' "$out" | wc -l)" -eq 1 ] && printf '%s' "$out" | grep -qE '^COMMITTED [0-9a-f]{7} TASK-1 DESIGN$'; then ok "P1 wip commit: one line plus sha"; else bad "P1 wip commit: one line plus sha (rc=$rc)"; printf '%s\n' "$out" | sed 's/^/    /'; fi
if git -C "$WF" show --name-only --format= HEAD | grep -qF ".claude/state/task.TASK-1.json"; then ok "P1b task file is in the commit"; else bad "P1b task file is in the commit"; fi

echo y > "$WF/src/a/g.py"
expect "P2 skip IMPLEMENTING->UNIT_TESTED needs a step (DESIGN->UNIT_TESTED refused)" 1 "FAIL" WIP TASK-1 "ut" --state UNIT_TESTED --tests "t -> pass" -- src/a/g.py
expect "P2a step to IMPLEMENTING commits" 0 "COMMITTED" WIP TASK-1 "impl" --state IMPLEMENTING -- src/a/g.py
echo y2 > "$WF/src/a/g.py"
head1="$(git -C "$WF" rev-parse HEAD)"
expect "P2b UNIT_TESTED without --tests refused" 1 "FAIL" WIP TASK-1 "ut" --state UNIT_TESTED -- src/a/g.py
if [ "$(wstate)" = "IMPLEMENTING" ] && [ "$(git -C "$WF" rev-parse HEAD)" = "$head1" ]; then ok "P2c no commit, state unchanged"; else bad "P2c no commit, state unchanged ($(wstate))"; fi
expect "P3 path outside scope refused" 1 "FAIL" WIP TASK-1 "bad path" -- src/b/x.py
expect "P4 skipping a state refused" 1 "FAIL" WIP TASK-1 "skip" --state VERIFIED --verified-by x -- src/a/g.py
if [ "$(wstate)" = "IMPLEMENTING" ]; then ok "P4b state unchanged after refused skip"; else bad "P4b state unchanged ($(wstate))"; fi
echo z > "$WF/src/b/pre.py"; git -C "$WF" add src/b/pre.py
expect "P5 pre-staged foreign file refused" 1 "FAIL" WIP TASK-1 "staged" -- src/a/g.py
if [ "$(git -C "$WF" diff --cached --name-only | grep -vc '^src/b/pre.py$' || true)" = "0" ]; then ok "P5b index holds only the foreign file"; else bad "P5b index restored"; git -C "$WF" diff --cached --name-only | sed 's/^/    /'; fi
git -C "$WF" reset -q

# P13-P17: auto grants
G="$WORK/grantfix"
rolegrants() { python3 -c 'import json,sys
d=json.load(open(sys.argv[1])); g=(d.get("roles") or {}).get("grants") or {}
print(sorted(g.get(sys.argv[2]) or []))' "$G/.claude/state/task.TASK-1.json" "$1"; }
GT() { (cd "$G" && TASKS_ROOT="$G" bash "$G/.claude/scripts/tasks.sh" "$@"); }
wfix "$G" '["src/a/*"]'
GT scope TASK-1 --set '.claude/scripts/foo.sh,src/a/*' >/dev/null 2>&1 || true
if [ "$(rolegrants coder)" = "['.claude/scripts/foo.sh']" ] && [ "$(rolegrants tester)" = "['.claude/scripts/foo.sh']" ]; then ok "P13 scope grants coder and tester"; else bad "P13 scope grants ($(rolegrants coder) $(rolegrants tester))"; fi
GT scope TASK-1 --add '.claude/hooks/x' >/dev/null 2>&1 || true
if [ "$(rolegrants coder)" = "['.claude/scripts/foo.sh']" ]; then ok "P14 hooks glob gives no grant"; else bad "P14 hooks glob gives no grant ($(rolegrants coder))"; fi
GT scope TASK-1 --add '.claude/*' >/dev/null 2>&1 || true
if [ "$(rolegrants coder)" = "['.claude/scripts/foo.sh']" ]; then ok "P17 .claude/* gives no grant"; else bad "P17 .claude/* gives no grant ($(rolegrants coder))"; fi
# P15: the guard, patched on a scratch copy, allows foo.sh and refuses bar.sh
PATCH98="$KIT/work/TASK-098/patches/01-guard-scope-grant.py"
GW() { python3 - "$G" "$1" <<'PY'
import json, subprocess, sys
g, path = sys.argv[1], sys.argv[2]
ev = {"tool_name": "Write", "tool_input": {"file_path": g + "/" + path, "content": "x"}, "session_id": "s1",
      "hook_event_name": "PreToolUse", "cwd": g, "agent_type": "coder"}
env = {"CLAUDE_PROJECT_DIR": g, "PATH": "/usr/bin:/bin:/usr/local/bin", "CTXGUARD_TASK": "TASK-1"}
r = subprocess.run(["python3", g + "/.claude/hooks/agent_setup.py", "hook", "--config", g + "/.claude/agent_setup.json"],
                   input=json.dumps(ev), capture_output=True, text=True, env=env, cwd=g)
print(r.returncode)
PY
}
if [ -f "$PATCH98" ]; then
  GT scope TASK-1 --set '.claude/scripts/foo.sh,src/a/*' >/dev/null 2>&1 || true
  python3 "$PATCH98" "$G/.claude" >/dev/null 2>&1 || true
  p15a_out=$(python3 "$PATCH98" "$G/.claude" 2>&1 || true)
  if printf '%s' "$p15a_out" | grep -q "already patched"; then ok "P15a patch is idempotent"; else bad "P15a patch is idempotent"; fi
  if [ "$(GW .claude/scripts/foo.sh)" = "0" ] && [ "$(GW .claude/scripts/bar.sh)" != "0" ]; then ok "P15 guard allows foo.sh, refuses bar.sh"; else bad "P15 guard allows foo.sh ($(GW .claude/scripts/foo.sh)), refuses bar.sh ($(GW .claude/scripts/bar.sh))"; fi
else
  bad "P15 patch script missing"
fi
GT scope TASK-1 --set 'src/a/*' >/dev/null 2>&1 || true
if [ "$(rolegrants coder)" = "[]" ]; then ok "P16 --set without foo removes the grant"; else bad "P16 --set removes the grant ($(rolegrants coder))"; fi

# P18 (F-97-7): the task's commit accepts the REQ file that lists it
echo q >> "$WF/docs/req/items/REQ-0007.md"; echo q >> "$WF/docs/req/items/REQ-0008.md"; echo q >> "$WF/docs/req/INDEX.md"
expect "P18 linked REQ item accepted" 0 "COMMITTED" WIP TASK-1 "req" -- docs/req/items/REQ-0007.md docs/req/INDEX.md
expect "P18b unlinked REQ item refused" 1 "FAIL" WIP TASK-1 "req2" -- docs/req/items/REQ-0008.md

# ---- F4: new #! file committed as 100755 ----
wfix "$WF"
printf 'plain\n' > "$WF/src/a/old.txt"; git -C "$WF" add src/a/old.txt; git -C "$WF" commit -q -m old --no-verify
printf '#!/bin/bash\necho hi\n' > "$WF/src/a/run.sh"
printf 'no shebang\n' > "$WF/src/a/data.txt"
printf '#!/bin/sh\n' > "$WF/src/a/old.txt"
out="$(WIP TASK-1 "modes" -- src/a/run.sh src/a/data.txt src/a/old.txt 2>&1)" || true
mode() { git -C "$WF" ls-tree HEAD -- "$1" | cut -d' ' -f1; }
if [ "$(mode src/a/run.sh)" = "100755" ]; then ok "F4-1 new #! script is 100755"; else bad "F4-1 new #! script is 100755 ($(mode src/a/run.sh))"; fi
if [ "$(mode src/a/data.txt)" = "100644" ]; then ok "F4-2 new non-#! file stays 100644"; else bad "F4-2 new non-#! file stays 100644 ($(mode src/a/data.txt))"; fi
if [ "$(mode src/a/old.txt)" = "100644" ]; then ok "F4-3 existing file keeps its mode"; else bad "F4-3 existing file keeps its mode ($(mode src/a/old.txt))"; fi
printf '#!/bin/bash\n' > "$WF/src/a/run2.sh"; printf 'x\n' > "$WF/src/a/data2.txt"
printf 'wip(x): TASK-1 direct\n\nTask: TASK-1\nState: DESIGN\n' > "$WORK/direct-msg.txt"
out="$(WTASKS commit TASK-1 "$WORK/direct-msg.txt" --log - -- src/a/run2.sh src/a/data2.txt 2>&1)" || true
if printf '%s\n' "$out" | grep -qxF "CHMOD +x src/a/run2.sh" && ! printf '%s\n' "$out" | grep -qF "CHMOD +x src/a/data2.txt"; then ok "F4-4 CHMOD line printed for the script only"; else bad "F4-4 CHMOD line printed"; printf '%s\n' "$out" | sed 's/^/    /'; fi

# ---- F6: scope --from-design ----
wfix "$WF"
cat > "$WF/docs/design/phase-1-one.md" <<'EOF'
# Phase 1
## 1.x Files
- `src/a/*` and `src/b/new.py` are touched; also `docs/req/items/REQ-1.md` (excluded).
### 1.2 Thing. New: `tools/x.sh`
## Notes
- mention of `other/ignored.py` here is not scope
EOF
before="$(cat "$WF/.claude/state/task.TASK-1.json")"
out="$(WTASKS scope TASK-1 --from-design 2>&1)"; rc=$?
if [ "$rc" -eq 0 ] && printf '%s\n' "$out" | grep -qxF "src/b/new.py" && printf '%s\n' "$out" | grep -qxF "tools/x.sh" \
   && printf '%s\n' "$out" | grep -qxF "tasks.sh scope TASK-1 --add src/b/new.py,tools/x.sh" \
   && ! printf '%s\n' "$out" | grep -qE 'src/a/\*|ignored|REQ-1'; then ok "F6-1 missing paths and one add line"; else bad "F6-1 missing paths (rc=$rc)"; printf '%s\n' "$out" | sed 's/^/    /'; fi
if [ "$before" = "$(cat "$WF/.claude/state/task.TASK-1.json")" ]; then ok "F6-2 read-only"; else bad "F6-2 read-only"; fi
WTASKS scope TASK-1 --add 'src/b/new.py,tools/x.sh' >/dev/null 2>&1 || true
expect "F6-3 nothing missing prints SCOPE OK" 0 "SCOPE OK" WTASKS scope TASK-1 --from-design

echo "SUMMARY(process_speed): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

#!/usr/bin/env bash
# Test for advance.sh (TASK-032, REQ-0037, design phase-32): one gated TASK step per call,
# the first failing gate with a restore, idempotent re-run, dry-run, req-catchup.
# Every case runs in a throwaway git repo holding a copy of the kit (fixture style of
# .claude/tests/workflow_gates_test.sh); the real state is never touched.
# Run: bash .claude/scripts/checks/advance_test.sh
set -Eeuo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
unset CLAUDE_PROJECT_DIR TASKS_ROOT || true

PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }

# expect <name> <want-rc> <want-substring|""> <cmd...>
expect() {
  local name="$1" want_rc="$2" want_out="$3" out rc=0; shift 3
  out="$("$@" 2>&1)" || rc=$?
  if [ "$rc" -ne "$want_rc" ]; then
    bad "$name (rc=$rc, want $want_rc)"; printf '%s\n' "$out" | sed 's/^/    /' | head -n 14; return
  fi
  if [ -n "$want_out" ] && ! printf '%s' "$out" | grep -qF -- "$want_out"; then
    bad "$name (output lacks '$want_out')"; printf '%s\n' "$out" | sed 's/^/    /' | head -n 14; return
  fi
  ok "$name"
}
check() { local name="$1"; shift; if "$@"; then ok "$name"; else bad "$name"; fi; }

D=""   # the repo under test (functions below read it)
adv() { (cd "$D" && CLAUDE_PROJECT_DIR="$D" bash .claude/scripts/advance.sh "$@"); }
sh_() { (cd "$D" && CLAUDE_PROJECT_DIR="$D" "$@"); }
REQ_() { sh_ python3 .claude/req/req.py "$@"; }

# fp <dir>: fingerprint of everything advance may write (work/ excluded) + git state
fp() {
  ( cd "$1"
    { cat .claude/state/*.json .claude/state/phase-log.md docs/req/STATE.json docs/req/INDEX.md docs/req/items/*.md 2>/dev/null || true
      git rev-parse HEAD
      git status --porcelain | grep -v ' work/' || true
      git diff --cached --name-only
    } | cksum )
}
head_has() { git -C "$D" log -1 --format=%B | grep -qxF -- "$1"; }
tracked() { git -C "$D" ls-files --error-unmatch -- "$1" >/dev/null 2>&1; }
commits() { git -C "$D" rev-list --count HEAD; }

# fixture <dir> [nodesign]: git repo with a kit copy, TASK-9 at TODO, REQ-0001 (TODO) linked to it
fixture() {
  D="$1"; rm -rf "$D"; mkdir -p "$D/docs/req"
  cp -r "$KIT" "$D/.claude"
  find "$D/.claude" -name __pycache__ -prune -exec rm -rf {} +
  rm -rf "$D/.claude/tests" "$D/.claude/state"; mkdir -p "$D/.claude/state"
  cp "$KIT/../docs/req/config.json" "$D/docs/req/config.json"
  printf '{"max_active": 3}\n' > "$D/.claude/workflow.json"
  git -C "$D" init -q
  git -C "$D" config user.email t@example.invalid
  git -C "$D" config user.name test
  REQ_ init >/dev/null
  REQ_ new --title "Gates" --text "WHEN x, the report SHALL y." >/dev/null
  python3 - "$D" "${2:-}" <<'PY'
import json, sys
d, nodesign = sys.argv[1:3]
p = d + "/docs/req/items/REQ-0001.md"
s = open(p).read().replace("- [ ] AC1:\n", "- [ ] AC1: one\n- [ ] AC2: two\n")
if not nodesign:
    s = s.replace("## Design\n", "## Design\nSee docs/design/phase-9-gates.md.\n", 1)
open(p, "w").write(s)
t = {"task_id": "TASK-9", "title": "t", "state": "TODO", "requirement": "r", "acceptance_criteria": [],
     "design": {"status": "pending", "summary": "", "path": ""},
     "implementation": {"status": "pending", "files": []},
     "unit_test": {"status": "pending", "command": "", "result": ""},
     "security": {"status": "pending", "result": ""},
     "verification": {"status": "pending", "evidence": []},
     "report": {"status": "pending", "path": ""},
     "picked_at": "2099-01-01T00:00:00Z", "updated_at": "2099-01-01T00:00:00Z", "updated_by": "test", "next": "design"}
json.dump(t, open(d + "/.claude/state/task.TASK-9.json", "w"), indent=2)
json.dump([{"task_id": "TASK-9", "title": "t", "status": "active"}], open(d + "/.claude/state/backlog.json", "w"), indent=2)
open(d + "/.claude/state/phase-log.md", "w").write("# Phase Log\n")
PY
  REQ_ task REQ-0001 TASK-9 >/dev/null
  sh_ bash .claude/scripts/tasks.sh sync >/dev/null
  mkdir -p "$D/work/TASK-9" "$D/docs/design" "$D/docs/report"
  echo "design doc" > "$D/docs/design/phase-9-gates.md"
  echo "impl" > "$D/work/TASK-9/impl.txt"
  echo "evidence" > "$D/work/TASK-9/ev.txt"
  echo "crosscheck" > "$D/work/TASK-9/cc.txt"
  git -C "$D" add -A -- . ':!work' ':!docs/design'
  git -C "$D" commit -qm fixture --no-verify
}

# mkspec <STATE> [mutation]: writes work/TASK-9/advance-<STATE>.json
mkspec() {
  python3 - "$D" "$1" "${2:-}" <<'PY'
import json, sys
d, st, mut = sys.argv[1:4]
lg = {"action": "did " + st, "result": "ok", "decision": "go on", "next": "next step"}
B = {
 "DESIGN": {"set": {"design": {"status": "completed", "path": "docs/design/phase-9-gates.md", "summary": "s"},
                    "acceptance_criteria": ["a"]},
            "commit": {"subject": "docs(design): phase 9 gates", "paths": []}},
 "IMPLEMENTING": {"set": {"implementation": {"status": "completed", "summary": "s", "files": ["x.sh"]}},
            "commit": {"subject": "feat(x): implement", "paths": ["work/TASK-9/impl.txt"]}},
 "UNIT_TESTED": {"set": {"unit_test": {"status": "passed", "command": "bash t.sh", "result": "3 pass"}},
            "commit": {"subject": "test(x): unit tested", "paths": []}},
 "VERIFIED": {"set": {"verification": {"status": "passed", "command": "run x", "result": "ok",
                                       "evidence": ["work/TASK-9/ev.txt"]},
                      "security": {"status": "completed", "result": "checked"}},
            "req": {"ac": "all", "ac_evidence": "ran x, see work/TASK-9/ev.txt"},
            "commit": {"subject": "chore(x): verified", "paths": []}},
 "DONE": {"set": {"report": {"status": "completed"}},
          "quality": {"kind": "crosscheck", "evidence": ["work/TASK-9/cc.txt"]},
          "commit": {"subject": "docs(report): done", "paths": []}},
}
s = B[st]
s["next"] = "" if st == "DONE" else "do the next step"
s["log"] = lg
if mut == "badjson":
    open("%s/work/TASK-9/advance-%s.json" % (d, st), "w").write("{not json")
    sys.exit(0)
if mut == "nonext": s["next"] = ""
if mut == "nolog": del s["log"]["decision"]
if mut == "noschema": s["set"][next(iter(s["set"]))] = {"status": "pending"}
if mut == "noevidence": s["set"]["verification"]["evidence"] = ["work/TASK-9/missing.txt"]
if mut == "emptyevidence": s["set"]["verification"]["evidence"] = ["work/TASK-9/empty.txt"]
if mut == "noquality": del s["quality"]
if mut == "na": s["quality"] = {"kind": "n/a", "reason": "no content"}
if mut == "nosec": s["set"]["security"] = {"status": "pending", "result": "x"}
if mut == "forbidden": s["commit"]["paths"] = ["work/TASK-9/node_modules/x.txt"]
json.dump(s, open("%s/work/TASK-9/advance-%s.json" % (d, st), "w"), indent=1)
PY
}

# prep <STATE>: files a step needs on disk
prep() {
  case "$1" in
    VERIFIED) : > "$D/work/TASK-9/empty.txt" ;;
    DONE) echo "report doc" > "$D/docs/report/phase-9-gates.md" ;;
  esac
}
# to_state <STATE>: advance D step by step to STATE (every step must PASS)
to_state() {
  local st out
  for st in DESIGN IMPLEMENTING UNIT_TESTED VERIFIED DONE; do
    prep "$st"; mkspec "$st"
    out="$(adv TASK-9 "$st" --spec "work/TASK-9/advance-$st.json" 2>&1)" || { echo "to_state $st failed: $out"; return 1; }
    [ "$st" = "$1" ] && return 0
  done
}
clone() { rm -rf "$2"; cp -a "$1" "$2"; D="$2"; }

# gatecase <name> <STATE> <mutation> <gate> [substring]: mutated spec fails at <gate>, nothing changed
gatecase() {
  local name="$1" st="$2" mut="$3" gate="$4" want="${5:-}" before after out rc=0
  prep "$st"; mkspec "$st" "$mut"
  before="$(fp "$D")"
  out="$(adv TASK-9 "$st" --spec "work/TASK-9/advance-$st.json" 2>&1)" || rc=$?
  after="$(fp "$D")"
  if [ "$rc" -ne 1 ]; then bad "$name (rc=$rc, want 1)"; printf '%s\n' "$out" | head -n 8 | sed 's/^/    /'; return; fi
  if ! printf '%s' "$out" | grep -qF "FAIL [$gate]"; then bad "$name (no 'FAIL [$gate]')"; printf '%s\n' "$out" | head -n 8 | sed 's/^/    /'; return; fi
  if [ -n "$want" ] && ! printf '%s' "$out" | grep -qF -- "$want"; then bad "$name (lacks '$want')"; printf '%s\n' "$out" | head -n 8 | sed 's/^/    /'; return; fi
  if ! printf '%s' "$out" | grep -q '^fix:'; then bad "$name (no fix: hint)"; return; fi
  if [ "$before" != "$after" ]; then bad "$name (state bytes changed after the failure)"; return; fi
  ok "$name"
}

# ---------------------------------------------------------------- 2 gates at TODO
A="$WORK/a"; fixture "$A"
expect "0 workflow-check passes on the fixture" 0 "PASS" sh_ bash .claude/scripts/workflow-check.sh
expect "0 usage: no args" 2 "Usage" adv
gatecase "2a bad spec JSON -> spec" DESIGN badjson spec
gatecase "2b missing next -> spec" DESIGN nonext spec
gatecase "2c log lacks decision -> spec" DESIGN nolog spec
gatecase "2d schema field missing (design.path/summary) -> spec" DESIGN noschema spec
gatecase "2e two-step jump TODO -> IMPLEMENTING -> state" IMPLEMENTING none state
expect "2f spec outside work/TASK-9/ refused" 1 "FAIL [spec]" adv TASK-9 DESIGN --spec .claude/state/backlog.json
# REQ Design empty (pre-check before any write)
B="$WORK/b"; fixture "$B" nodesign
gatecase "2g REQ Design empty at DESIGN -> req" DESIGN none req "Design"

# ---------------------------------------------------------------- 1 happy path + 3 idempotence + 4 dry-run
D="$A"
mkspec DESIGN
expect "1.1 DESIGN PASS" 0 "PASS: TASK-9 -> DESIGN committed" adv TASK-9 DESIGN --spec work/TASK-9/advance-DESIGN.json
check "1.1b commit has Task trailer" head_has 'Task: TASK-9'
check "1.1c commit has State trailer" head_has 'State: DESIGN'
check "1.1d design doc is in the commit" tracked docs/design/phase-9-gates.md
c1="$(commits)"
expect "3.1 re-run of a committed step is idempotent" 0 "PASS (already" adv TASK-9 DESIGN --spec work/TASK-9/advance-DESIGN.json
check "3.1b no new commit" test "$(commits)" = "$c1"

clone "$A" "$WORK/a2"
gatecase "2h forbidden path -> commit (undo + restore)" IMPLEMENTING forbidden commit
mkspec IMPLEMENTING
expect "3.2 re-run after a commit failure passes" 0 "PASS: TASK-9 -> IMPLEMENTING committed" adv TASK-9 IMPLEMENTING --spec work/TASK-9/advance-IMPLEMENTING.json
D="$A"; mkspec IMPLEMENTING   # the failed run happened in a2 only; A continues
expect "1.2 IMPLEMENTING PASS (A)" 0 "PASS: TASK-9 -> IMPLEMENTING committed" adv TASK-9 IMPLEMENTING --spec work/TASK-9/advance-IMPLEMENTING.json

# 4 dry-run before UNIT_TESTED
mkspec UNIT_TESTED
before="$(fp "$A")"
out="$(adv TASK-9 UNIT_TESTED --spec work/TASK-9/advance-UNIT_TESTED.json --dry-run 2>&1)" || true
if printf '%s' "$out" | grep -qF "DRY-RUN: commit paths"; then ok "4.1 dry-run prints the commit paths"; else bad "4.1 dry-run plan"; printf '%s\n' "$out" | head -n 12; fi
if printf '%s' "$out" | grep -qF "PASS (dry-run)"; then ok "4.2 dry-run verdict"; else bad "4.2 dry-run verdict"; fi
check "4.3 dry-run leaves every file and git state unchanged" test "$before" = "$(fp "$A")"
expect "1.3 UNIT_TESTED PASS" 0 "PASS: TASK-9 -> UNIT_TESTED committed" adv TASK-9 UNIT_TESTED --spec work/TASK-9/advance-UNIT_TESTED.json
check "1.3b Tests trailer" bash -c "git -C '$A' log -1 --format=%B | grep -q '^Tests: bash t.sh'"

# gates at VERIFIED (clone per case)
prep VERIFIED
for c in "noevidence|quality|missing.txt" "emptyevidence|quality|empty" "nosec|workflow|security"; do
  m="${c%%|*}"; r="${c#*|}"; g="${r%%|*}"; w="${r#*|}"
  clone "$A" "$WORK/v"; gatecase "2i VERIFIED $m -> $g" VERIFIED "$m" "$g" "$w"
done
D="$A"; mkspec VERIFIED
expect "1.4 VERIFIED PASS (ticks ACs, steps REQ)" 0 "PASS: TASK-9 -> VERIFIED committed" adv TASK-9 VERIFIED --spec work/TASK-9/advance-VERIFIED.json
check "1.4b Verified-by trailer" bash -c "git -C '$A' log -1 --format=%B | grep -q '^Verified-by: run x'"
check "1.4c REQ-0001 is VERIFIED with every AC ticked" bash -c "grep -q '^status: VERIFIED' '$A/docs/req/items/REQ-0001.md' && ! grep -q '^- \[ \] AC[12]: ' '$A/docs/req/items/REQ-0001.md'"

# gates at DONE
prep DONE
clone "$A" "$WORK/d"; gatecase "2j DONE without quality -> quality" DONE noquality quality
python3 - "$WORK/d" <<'PY'
import json, sys
p = sys.argv[1] + "/.claude/state/task.TASK-9.json"
t = json.load(open(p)); t["crosscheck_required"] = True; json.dump(t, open(p, "w"), indent=2)
PY
git -C "$WORK/d" commit -qam "crosscheck_required" --no-verify
gatecase "2k n/a on a crosscheck task -> quality" DONE na quality "content task needs"
D="$A"; prep DONE; mkspec DONE
expect "1.5 DONE PASS" 0 "PASS: TASK-9 -> DONE committed" adv TASK-9 DONE --spec work/TASK-9/advance-DONE.json
check "1.5b Report trailer" bash -c "git -C '$A' log -1 --format=%B | grep -q '^Report: docs/report/phase-9-gates.md'"
check "1.6 five phase-log headings" test "$(grep -c '^## [A-Z_]* - TASK-9 - ' "$A/.claude/state/phase-log.md")" = 5
check "1.7 view agrees with the task file" python3 - "$A" <<'PY'
import json, sys
d = sys.argv[1] + "/.claude/state/"
t = json.load(open(d + "task.TASK-9.json")); v = json.load(open(d + "task.json"))
sys.exit(0 if (t["state"], t["next"]) == ("DONE", "") and (v["state"], v["next"]) == (t["state"], t["next"]) else 1)
PY
check "1.8 REQ-0001 DONE" grep -q '^status: DONE' "$A/docs/req/items/REQ-0001.md"
check "1.9 backlog item done" grep -q '"status": "done"' "$A/.claude/state/backlog.json"
check "1.10 six commits (fixture + 5 steps)" test "$(git -C "$A" rev-list --count HEAD)" = 6
check "1.11 nothing dirty outside work/" test -z "$(git -C "$A" status --porcelain | grep -v ' work/' || true)"
expect "3.3 re-run of the DONE step is idempotent" 0 "PASS (already" adv TASK-9 DONE --spec work/TASK-9/advance-DONE.json
check "3.3b no new commit" test "$(git -C "$A" rev-list --count HEAD)" = 6
D="$A"
expect "1.12 workflow-check passes after DONE" 0 "PASS" sh_ bash .claude/scripts/workflow-check.sh --task TASK-9

# ---------------------------------------------------------------- 5 req-catchup
C="$WORK/c"; fixture "$C"
python3 - "$C" <<'PY'
import json, sys
d = sys.argv[1] + "/.claude/state/"
t = json.load(open(d + "task.TASK-9.json")); t["state"] = "DONE"
t["unit_test"] = {"status": "passed", "command": "bash t.sh", "result": "3 pass"}
json.dump(t, open(d + "task.TASK-9.json", "w"), indent=2)
b = json.load(open(d + "backlog.json")); b[0]["status"] = "done"
json.dump(b, open(d + "backlog.json", "w"), indent=2)
PY
git -C "$C" commit -qam "task done" --no-verify
D="$C"
before="$(fp "$C")"
expect "5.1 refuses unticked ACs without --ac-evidence" 1 "FAIL [req]" adv req-catchup REQ-0001
check "5.1b REQ files restored" test "$before" = "$(fp "$C")"
expect "5.2 --ac-evidence must name an existing file" 1 "FAIL [req]" adv req-catchup REQ-0001 --ac-evidence "ran it, see work/TASK-9/nope.txt"
check "5.2b REQ files restored" test "$before" = "$(fp "$C")"
out="$(adv req-catchup REQ-0001 --ac-evidence "ran it, see work/TASK-9/ev.txt" --dry-run 2>&1)" || true
check "5.3 dry-run changes nothing" test "$before" = "$(fp "$C")"
if printf '%s' "$out" | grep -q "dry-run"; then ok "5.3b dry-run says so"; else bad "5.3b dry-run output"; fi
expect "5.4 catch-up TODO -> DONE, stage line printed" 0 "stage: docs/req/items/REQ-0001.md" adv req-catchup REQ-0001 --ac-evidence "ran it, see work/TASK-9/ev.txt"
check "5.4b REQ is DONE" grep -q '^status: DONE' "$C/docs/req/items/REQ-0001.md"
expect "5.4c re-run says already DONE" 0 "PASS (already DONE)" adv req-catchup REQ-0001
E="$WORK/e"; fixture "$E"; D="$E"
expect "5.5 refuses when a linked task is not DONE" 1 "FAIL [req]" adv req-catchup REQ-0001 --ac-evidence "see work/TASK-9/ev.txt"

# ---------------------------------------------------------------- 6 style
P='map''file|declare -''A'
for f in "$KIT/scripts/advance.sh" "$KIT/scripts/_advance.py" "$KIT/scripts/checks/advance_test.sh"; do
  check "6.1 bash -n / python compile: $(basename "$f")" bash -c "case '$f' in *.sh) bash -n '$f';; *) python3 -I -c \"import ast,sys; ast.parse(open(sys.argv[1]).read())\" '$f';; esac"
  check "6.2 Bash 3.2 clean: $(basename "$f")" bash -c "! grep -nE '$P' '$f'"
done

echo "SUMMARY(advance): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

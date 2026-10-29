#!/usr/bin/env bash
# Regression test for the workflow gates (workflow-check.sh, commit-check.sh,
# backlog.sh, hooks/stop-check.sh). Each case copies .claude/ into a throwaway
# git repo, writes a fixture state, and asserts the gate's verdict - so the
# real repo's state is never touched. Run: bash .claude/tests/workflow_gates_test.sh
set -Eeuo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

# fresh <dir>: a git repo holding a copy of the kit
fresh() {
  rm -rf "$1"; mkdir -p "$1"
  cp -r "$KIT" "$1/.claude"
  find "$1/.claude" -name __pycache__ -prune -exec rm -rf {} +
  rm -rf "$1/.claude/tests" "$1/.claude/state"; mkdir -p "$1/.claude/state"
  git -C "$1" init -q
  git -C "$1" config user.email t@example.invalid
  git -C "$1" config user.name test
}

# state <dir> <STATE> [key=value ...]: fully evidenced TASK-9 up to STATE,
# tagged phase-log entries for each phase, backlog item matching. Overrides:
#   security=<status>  secresult=<text>  log=untagged|other|none
#   done_items=<json list of extra backlog items>
#   tid=<task id>  dpath=<design.path>  rpath=<report.path>
#   nofiles=1 (no design/report files on disk)
state() {
  local dir="$1" st="$2"; shift 2
  python3 - "$dir" "$st" "$@" <<'PY'
import json, os, shutil, sys
d, st, *kv = sys.argv[1:]
o = dict(x.split("=", 1) for x in kv)
SEQ = ["TODO", "DESIGN", "IMPLEMENTING", "UNIT_TESTED", "VERIFIED", "DONE"]
i = SEQ.index(st)
done = lambda s: i >= SEQ.index(s)
os.makedirs(f"{d}/docs", exist_ok=True)
open(f"{d}/docs/R.md", "w").write("report\n")
tid = o.get("tid", "TASK-9")
dpath = o.get("dpath", "docs/design/phase-9-gates.md")
rpath = o.get("rpath", "docs/report/phase-9-gates.md")
for sub in ("design", "report"):
    shutil.rmtree(f"{d}/docs/{sub}", ignore_errors=True)
    os.makedirs(f"{d}/docs/{sub}")
    if not o.get("nofiles"):
        open(f"{d}/docs/{sub}/phase-9-gates.md", "w").write("doc\n")
t = {"task_id": tid, "title": "t", "state": st, "requirement": "r",
     "acceptance_criteria": ["a"],
     "design": {"status": "completed" if done("DESIGN") else "pending", "summary": "s",
                "path": dpath if done("DESIGN") else ""},
     "implementation": {"status": "completed" if done("IMPLEMENTING") else "pending", "files": ["x.sh"]},
     "unit_test": {"status": "passed" if done("UNIT_TESTED") else "pending", "command": "c", "result": "r"},
     "security": {"status": o.get("security", "completed" if done("VERIFIED") else "pending"),
                  "result": o.get("secresult", "checked")},
     "verification": {"status": "passed" if done("VERIFIED") else "pending", "evidence": ["e"]},
     "report": {"status": "completed" if done("DONE") else "pending", "path": rpath if done("DONE") else ""},
     "updated_at": "2099-01-01T00:00:00Z", "updated_by": "test",
     "next": "" if st == "DONE" else "n"}
if o.get("implstatus"):
    t["implementation"]["status"] = o["implstatus"]
if o.get("roles_required"):
    t["roles_required"] = True
    t["roles"] = json.loads(o.get("roles", "{}"))
if o.get("crosscheck_required"):
    t["crosscheck_required"] = True
if o.get("incident"):
    t["incident"] = json.loads(o["incident"])
if o.get("files"):
    t["implementation"]["files"] = json.loads(o["files"])
json.dump(t, open(f"{d}/.claude/state/task.json", "w"), indent=2)
log = "# Phase Log\n"
tag = {"untagged": None, "other": "TASK-8", "none": "", "": tid}[o.get("log", "")]
for s in SEQ[1:i + 1]:
    if tag is None:
        log += f"\n## {s} - 2099-01-01T00:00:00Z\n"
    elif tag:
        log += f"\n## {s} - {tag} - 2099-01-01T00:00:00Z\n"
open(f"{d}/.claude/state/phase-log.md", "w").write(log)
items = [{"task_id": tid, "title": "t", "status": "active"}]
items += json.loads(o.get("done_items", "[]"))
json.dump(items, open(f"{d}/.claude/state/backlog.json", "w"), indent=2)
PY
}

WC() { bash "$1/.claude/scripts/workflow-check.sh"; }
R="$WORK/r"

# --- AC2: phase-log audit is per task ---------------------------------------
fresh "$R"
state "$R" VERIFIED
expect "AC2 tagged entries for the active task pass" 0 "PASS: workflow state" WC "$R"
state "$R" VERIFIED log=untagged
expect "AC2 untagged entries do not count" 1 "no '## DESIGN - TASK-9" WC "$R"
state "$R" VERIFIED log=other
expect "AC2 another task's entries do not count" 1 "no '## VERIFIED - TASK-9" WC "$R"
state "$R" TODO log=none
expect "AC2 TODO needs no log entries" 0 "PASS: workflow state" WC "$R"

# --- AC4: security gate --------------------------------------------------------
state "$R" VERIFIED security=pending
expect "AC4 VERIFIED with security pending fails" 1 "security.status=completed|not_applicable" WC "$R"
state "$R" DONE security=completed secresult=
expect "AC4 DONE with empty security.result fails" 1 "security.result is empty" WC "$R"
state "$R" VERIFIED security=not_applicable secresult="docs only"
expect "AC4 not_applicable with a reason passes" 0 "PASS: workflow state" WC "$R"
state "$R" UNIT_TESTED security=pending
expect "AC4 security not required before VERIFIED" 0 "PASS: workflow state" WC "$R"

# --- AC3: every done backlog item is audited ------------------------------
state "$R" DESIGN done_items='[{"task_id":"TASK-1","title":"a","status":"done"}]'
expect "AC3 hand-edited done item fails" 1 "backlog TASK-1 is 'done' but has no existing report" WC "$R"
state "$R" DESIGN done_items='[{"task_id":"TASK-1","title":"a","status":"done","waiver":"legacy"}]'
expect "AC3 done item with waiver passes" 0 "PASS: workflow state" WC "$R"
state "$R" DESIGN done_items='[{"task_id":"TASK-1","title":"a","status":"done","report":"docs/nope.md"}]'
expect "AC3 done item whose report file is missing fails" 1 "report='docs/nope.md'" WC "$R"
state "$R" DESIGN done_items='[{"task_id":"TASK-1","title":"a","status":"done","report":"docs/R.md"}]'
expect "AC3 done item without tagged DONE entry fails" 1 "no '## DONE - TASK-1" WC "$R"
state "$R" DESIGN done_items='[{"task_id":"TASK-1","title":"a","status":"done","report":"docs/R.md"}]'
printf '\n## DONE - TASK-1 - 2099-01-01T00:00:00Z\n' >> "$R/.claude/state/phase-log.md"
expect "AC3 done item with report + tagged DONE passes" 0 "PASS: workflow state" WC "$R"
state "$R" DESIGN done_items='[{"task_id":"TASK-2","title":"b","status":"active"}]'
expect "AC3 two active items fail" 1 "2 active items" WC "$R"
state "$R" DESIGN
echo '{not json' > "$R/.claude/state/backlog.json"
expect "AC3 malformed backlog fails loudly" 1 "backlog.json is unreadable" WC "$R"

# backlog.sh complete
BL() { bash "$R/.claude/scripts/backlog.sh" "$@"; }
jqf() { python3 -c 'import json,sys;i=[x for x in json.load(open(sys.argv[1])) if x["task_id"]=="TASK-9"][0];print(i.get(sys.argv[2],""))' "$R/.claude/state/backlog.json" "$1"; }
state "$R" VERIFIED
expect "AC3 complete of a non-DONE task is refused" 1 "not DONE" BL complete TASK-9
expect "AC3 complete --force without a reason is refused" 1 "needs a reason" BL complete TASK-9 --force
expect "AC3 complete with a junk flag prints usage" 1 "Usage" BL complete TASK-9 -f
expect "AC3 complete --force with a reason succeeds" 0 "waiver: abandoned" BL complete TASK-9 --force "abandoned"
expect "AC3 --force reason is stored as waiver" 0 "abandoned" jqf waiver
state "$R" DONE
expect "AC3 complete of a DONE task succeeds" 0 "COMPLETED: TASK-9" BL complete TASK-9
expect "AC3 complete records the report path" 0 "docs/report/phase-9-gates.md" jqf report
expect "AC3 complete records completed_at" 0 "T" jqf completed_at
expect "AC3 completed DONE task passes the audit" 0 "PASS: workflow state" WC "$R"
expect "AC3 pick with a junk flag prints usage" 1 "Usage" BL pick TASK-9 -f

# --- phase 5: design/report path convention -----------------------------------
mark_done() {  # close TASK-9 in the fixture backlog so a DONE state is consistent
  python3 -c 'import json,sys;p=sys.argv[1];b=json.load(open(p));b[0].update(status="done",waiver="t");json.dump(b,open(p,"w"))' \
    "$R/.claude/state/backlog.json"
}
state "$R" DESIGN
expect "5.1 convention design path passes" 0 "PASS: workflow state" WC "$R"
state "$R" DONE; mark_done
expect "5.2 convention report path passes at DONE" 0 "PASS: workflow state" WC "$R"
# plan checklist: rows owned by this task must be ticked before DONE
CK="$R/docs/design/phase-9-plan.md"
printf '| # | Item | Task / doc | Done |\n|---|---|---|---|\n| 1 | owned row | 009 / 9.1 | [ ] |\n| 2 | shared row | 009-010 | [ ] |\n' > "$CK"
expect "CK DONE with an owned open checklist row fails" 1 "checklist row 1 still open" WC "$R"
expect "CK session view lists owned and shared rows" 0 "shared, owner 010" bash "$R/.claude/scripts/checklist.sh"
sed -i.bak 's/| owned row | 009 \/ 9.1 | \[ \] |/| owned row | 009 \/ 9.1 | [x] |/' "$CK"
expect "CK DONE with only a later-owned shared row open passes" 0 "PASS: workflow state" WC "$R"
rm -f "$CK" "$CK.bak"
state "$R" DESIGN dpath=docs/DESIGN-gates.md
expect "5.1 legacy-style design path fails" 1 "must be docs/design/phase-9-<slug>.md" WC "$R"
state "$R" DESIGN dpath=docs/design/phase-8-gates.md
expect "5.1 wrong phase number fails" 1 "design.path='docs/design/phase-8-gates.md' must be" WC "$R"
state "$R" DESIGN dpath=docs/design/phase-09-gates.md
expect "5.1 zero-padded phase number fails" 1 "must be docs/design/phase-9-<slug>.md" WC "$R"
state "$R" DESIGN dpath=docs/design/phase-9-Bad_Slug.md
expect "5.1 non-kebab slug fails" 1 "slug: lowercase words" WC "$R"
state "$R" DESIGN dpath=
expect "5.1 empty design.path fails" 1 "design.path='' must be" WC "$R"
state "$R" DESIGN nofiles=1
expect "5.1 missing design file fails" 1 "design.path='docs/design/phase-9-gates.md' does not exist" WC "$R"
state "$R" DESIGN tid=TASK-47 dpath=docs/design/phase-47-gates.md
printf '# Phase 47\n\n## Design\n' > "$R/docs/design/phase-47-gates.md"
expect "PM design from phase 47 without Plan modes fails" 1 "has no '## Plan modes' section" WC "$R"
printf '# Phase 47\n\n## Plan modes\n| Mode | Impact |\n' > "$R/docs/design/phase-47-gates.md"
expect "PM design from phase 47 with Plan modes passes" 0 "PASS: workflow state" WC "$R"
state "$R" DESIGN tid=TASK-X
expect "5.1 task_id without a number fails" 1 "has no number" WC "$R"
state "$R" DESIGN tid=TASK-012 dpath=docs/design/phase-12-gates.md
touch "$R/docs/design/phase-12-gates.md"
expect "5.1 TASK-012 maps to phase-12" 0 "PASS: workflow state" WC "$R"
state "$R" TODO log=none dpath=junk
expect "5.1 no path required before design is completed" 0 "PASS: workflow state" WC "$R"
state "$R" DONE rpath=docs/report/phase-9-other.md; mark_done
expect "5.2 report basename mismatch fails" 1 "must be docs/report/phase-9-gates.md" WC "$R"
state "$R" DONE; mark_done; rm "$R/docs/report/phase-9-gates.md"
expect "5.2 missing report file fails" 1 "report.path='docs/report/phase-9-gates.md' does not exist" WC "$R"
python3 -c 'import json,sys;p=sys.argv[1];b=json.load(open(p));b.append({"task_id":"TASK-7","title":"q","status":"queued"});json.dump(b,open(p,"w"))' \
  "$R/.claude/state/backlog.json"
BL pick TASK-7 --force >/dev/null
expect "5.3 pick template has an empty design.path" 0 "design.path=''" \
  python3 -c 'import json,sys;print("design.path=%r" % json.load(open(sys.argv[1]))["design"]["path"])' "$R/.claude/state/task.json"

# --- AC1: commit-check trailer guard -----------------------------------------
state "$R" DESIGN
git -C "$R" add -A
MSG="$WORK/msg"
CC() { (cd "$R" && bash .claude/scripts/commit-check.sh "$MSG"); }
printf 'docs: x\n\nwhy\n\nTask: TASK-9\nState: DESIGN\n\nCo-Authored-By: A <a@example.invalid>\n' > "$MSG"
expect "AC1 trailer block split by a blank line fails" 1 "not parsed as trailer" CC
printf 'docs: x\n\nwhy\n\nTask: TASK-9\nState: DESIGN\nCo-Authored-By: A <a@example.invalid>\n' > "$MSG"
expect "AC1 single trailer block passes" 0 "commit-check: OK" CC
printf 'docs: x\n\nwhy\n\nTask: TASK-9\nState: VERIFIED\nCo-Authored-By: A <a@example.invalid>\n' > "$MSG"
expect "AC1 parsed trailers are really checked now" 1 "needs a \`Verified-by:\` trailer" CC
printf 'chore: x\n\nplain body, no trailers\n' > "$MSG"
expect "AC1 non-task commit is unaffected" 0 "commit-check: OK" CC

# --- AC5: Stop hook ------------------------------------------------------------
HOOK() { printf '%s' "${HOOK_IN:-{\}}" | CLAUDE_PROJECT_DIR="$R" bash "$R/.claude/hooks/stop-check.sh"; }
commit_all() { git -C "$R" add -A && git -C "$R" commit -qm fixture --no-verify --allow-empty; }
state "$R" DONE; mark_done; commit_all
expect "AC5 hook allows stop at a committed consistent DONE" 0 "" HOOK
state "$R" DONE security=pending; commit_all
expect "AC5 hook blocks stop at a broken DONE" 2 "claims state=DONE" HOOK
state "$R" IMPLEMENTING security=pending log=none; commit_all
expect "AC5 hook ignores gate evidence before DONE" 0 "" HOOK
echo "note" >> "$R/.claude/state/phase-log.md"
expect "6.1 hook blocks stop with uncommitted .claude/state" 2 "uncommitted workflow state" HOOK
HOOK_IN='{"stop_hook_active":true}'
expect "6.1 hook does not block twice (stop_hook_active)" 0 "allowing the stop" HOOK
HOOK_IN=
git -C "$R" checkout -q -- .claude/state
state "$R" DONE; mark_done; commit_all
echo "draft" > "$R/docs/report/phase-9-extra.md"
expect "6.1 hook blocks a DONE with uncommitted report docs" 2 "design/report docs are uncommitted" HOOK
rm "$R/docs/report/phase-9-extra.md"
echo '{broken' > "$R/.claude/state/task.json"
expect "6.1 hook fails closed on unreadable task.json" 2 "task.json is unreadable" HOOK
git -C "$R" checkout -q -- .claude/state
expect "AC5 .claude/settings.json wires the Stop hook" 0 "stop-check.sh" \
  python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["hooks"]["Stop"][0]["hooks"][0]["command"])' "$KIT/settings.json"

# --- 6.2: commit-check needs the workflow files fully staged --------------------
state "$R" DESIGN
git -C "$R" add -A
echo "unstaged" >> "$R/.claude/state/phase-log.md"
printf 'docs: x\n\nwhy\n\nTask: TASK-9\nState: DESIGN\n' > "$MSG"
expect "6.2 task commit with unstaged state fails" 1 "changed but not staged" CC
git -C "$R" add -A
touch "$R/docs/report/phase-9-new.md"
expect "6.2 task commit with an untracked report fails" 1 "docs/report/phase-9-new.md" CC
git -C "$R" add -A
expect "6.2 fully staged task commit passes" 0 "commit-check: OK" CC

# --- 33.9: model prompts are frozen ---------------------------------------------
mkdir -p "$R/docs/prompts"; echo "changed" > "$R/docs/prompts/phase2b-x.md"; git -C "$R" add -A
printf 'chore: x\n\nplain body\n' > "$MSG"
expect "33.9 staged prompt without Prompt-change fails" 1 "prompts are frozen" CC
printf 'chore: x\n\nwhy\n\nPrompt-change: phase 1 output has no id to join on\n' > "$MSG"
expect "33.9 staged prompt with Prompt-change passes" 0 "commit-check: OK" CC
echo "p" > "$R/security_prompt.md"; git -C "$R" add -A
printf 'chore: x\n\nplain body\n' > "$MSG"
expect "33.9 security_prompt.md is guarded too" 1 "security_prompt.md" CC
git -C "$R" reset -q -- docs/prompts security_prompt.md; rm -rf "$R/docs/prompts" "$R/security_prompt.md"
expect "33.9 no prompt staged is unaffected" 0 "commit-check: OK" CC

# --- F: engine files without architecture.md warn, never fail (RAW-00299) -------
echo "x" > "$R/engine_x.sh"; git -C "$R" add -A
printf 'chore: x\n\nplain body\n' > "$MSG"
expect "F engine file without architecture.md warns (rc 0)" 0 "without docs/guide/architecture.md" CC
printf 'chore: x\n\nwhy\n\nArch-unchanged: internal refactor, same flow\n' > "$MSG"
expect "F Arch-unchanged trailer silences it" 0 "commit-check: OK" CC
if (cd "$R" && bash .claude/scripts/commit-check.sh "$MSG" 2>&1) | grep -q "architecture.md"; then bad "F trailer still warns"; else ok "F trailer: no warning"; fi
mkdir -p "$R/docs/guide"; echo "a" > "$R/docs/guide/architecture.md"; git -C "$R" add -A
printf 'chore: x\n\nplain body\n' > "$MSG"
if (cd "$R" && bash .claude/scripts/commit-check.sh "$MSG" 2>&1) | grep -q "without docs/guide/architecture.md"; then bad "F staged architecture.md still warns"; else ok "F staged architecture.md: no warning"; fi
git -C "$R" reset -q -- engine_x.sh docs/guide; rm -rf "$R/engine_x.sh" "$R/docs/guide"
mkdir -p "$R/ext" "$R/sub"; echo "x" > "$R/ext/e.json"; git -C "$R" add -A
printf 'chore: x\n\nplain body\n' > "$MSG"
expect "F ext/** file without architecture.md warns (rc 0)" 0 "without docs/guide/architecture.md" CC
git -C "$R" reset -q -- ext; rm -rf "$R/ext"; echo "y" > "$R/sub/n.py"; echo "z" > "$R/top_y.py"; git -C "$R" add -A
if (cd "$R" && bash .claude/scripts/commit-check.sh "$MSG" 2>&1) | grep -F "engine files staged" | grep -q "sub/n.py"; then bad "F nested .py counted as engine"; else ok "F nested .py is not an engine file"; fi
expect "F top-level .py warns (rc 0)" 0 "top_y.py" CC
git -C "$R" reset -q -- sub top_y.py; rm -rf "$R/sub" "$R/top_y.py"

# --- 6.3: blocked side condition ----------------------------------------------
setblk() { python3 -c 'import json,sys;p=sys.argv[1];t=json.load(open(p));t["blocked"]=json.loads(sys.argv[2]);json.dump(t,open(p,"w"))' "$R/.claude/state/task.json" "$1"; }
state "$R" IMPLEMENTING; setblk '{"reason":"fake claude hangs","attempts":1}'
expect "6.3 blocked with a reason passes" 0 "PASS: workflow state" WC "$R"
setblk '{"attempts":1}'
expect "6.3 blocked without a reason fails" 1 "blocked must be" WC "$R"
setblk '{"reason":"r","attempts":3}'
expect "6.3 third attempt warns to ask the user" 0 "stop retrying and ask the user" WC "$R"
state "$R" DONE; mark_done; setblk '{"reason":"r","attempts":0}'
expect "6.3 DONE while blocked fails" 1 "'blocked' is still set" WC "$R"
state "$R" IMPLEMENTING; setblk '{"reason":"r","attempts":2}'
expect "6.3 task-state shows the blocker" 0 "BLOCKED: r (attempts=2)" bash "$R/.claude/scripts/task-state.sh"

# --- 6.4: archived phase-log entries still count ------------------------------
state "$R" DESIGN done_items='[{"task_id":"TASK-1","title":"a","status":"done","report":"docs/R.md"}]'
printf '\n## DONE - TASK-1 - 2099-01-01T00:00:00Z\n' > "$R/.claude/state/phase-log-archive.md"
expect "6.4 DONE entry in phase-log-archive.md counts" 0 "PASS: workflow state" WC "$R"
rm "$R/.claude/state/phase-log-archive.md"

# --- 6.5: backlog pick never overwrites an uncommitted task --------------------
state "$R" DONE; mark_done; commit_all
python3 -c 'import json,sys;p=sys.argv[1];b=json.load(open(p));b.append({"task_id":"TASK-10","title":"q","status":"queued"});json.dump(b,open(p,"w"))' \
  "$R/.claude/state/backlog.json"
expect "6.5 pick refuses while .claude/state is dirty" 1 "uncommitted changes" BL pick TASK-10
commit_all
expect "6.5 pick works once state is committed" 0 "PICKED: TASK-10" BL pick TASK-10

# --- 6.6: SessionStart / PostToolUse hooks ------------------------------------
state "$R" IMPLEMENTING; commit_all
SS() { CLAUDE_PROJECT_DIR="$R" bash "$R/.claude/hooks/session-start.sh"; }
expect "6.6 session-start prints the task and next action" 0 "Next: n" SS
expect "6.6 session-start prints the last phase-log heading" 0 "Last phase-log entry: IMPLEMENTING - TASK-9" SS
echo "x" >> "$R/.claude/state/phase-log.md"
expect "6.6 session-start lists uncommitted state" 0 "UNCOMMITTED workflow state" SS
git -C "$R" checkout -q -- .claude/state
PE() { printf '{"tool_input":{"file_path":"%s"}}' "$1" | CLAUDE_PROJECT_DIR="$R" bash "$R/.claude/hooks/post-edit-test.sh"; }
printf '#!/usr/bin/env bash\nif then\n' > "$R/bad.sh"
expect "6.6 post-edit rejects a .sh with a syntax error" 2 "bash -n failed" PE "$R/bad.sh"
printf '#!/usr/bin/env bash\necho ok\n' > "$R/good.sh"
expect "6.6 post-edit accepts a clean .sh" 0 "" PE "$R/good.sh"
echo '{bad' > "$R/.claude/state/backlog.json"
expect "6.6 post-edit rejects invalid state JSON" 2 "invalid JSON" PE "$R/.claude/state/backlog.json"
printf 'def f(:\n' > "$R/bad.py"
expect "6.6 post-edit rejects a .py that does not compile" 2 "py_compile failed" PE "$R/bad.py"
printf 'x = 1\n' > "$R/tool.py"
expect "6.6 post-edit accepts a clean .py" 0 "" PE "$R/tool.py"
printf 'notes\n' > "$R/notes.md"
expect "6.6 post-edit is a no-op for other files" 0 "" PE "$R/notes.md"
git -C "$R" checkout -q -- .claude/state

# --- TASK-064: required-role gate (roles_required + roles.<role>) -----------
# mkhandoff <path-under-R> <line1> [line2]: writes a fixture handoff file.
mkhandoff() {
  local rel="$1" l1="$2" l2="${3:-}"
  mkdir -p "$R/$(dirname "$rel")"
  if [ -n "$l2" ]; then printf '%s\n%s\n' "$l1" "$l2" > "$R/$rel"; else printf '%s\n' "$l1" > "$R/$rel"; fi
}

fresh "$R"
DPATH="work/TASK-9/handoff/design.md"
CPATH="work/TASK-9/handoff/code.md"
VPATH="work/TASK-9/handoff/verify.md"
mkhandoff "$DPATH" "PROGRESS: COMPLETE" "SKILLS: design"
mkhandoff "$CPATH" "PROGRESS: COMPLETE" "SKILLS: bash, coding"
mkhandoff "$VPATH" "PROGRESS: COMPLETE" "SKILLS: verify"

state "$R" VERIFIED roles_required=1 \
  roles="{\"designer\":\"$DPATH\",\"coder\":\"$CPATH\",\"verifier\":\"$VPATH\"}"
expect "64 marker + valid handoffs at VERIFIED passes" 0 "PASS: workflow state" WC "$R"

state "$R" VERIFIED roles_required=1 roles="{\"coder\":\"$CPATH\",\"verifier\":\"$VPATH\"}"
expect "64 missing designer after design completed fails" 1 "roles.designer is missing" WC "$R"

mkhandoff "docs/notes/design.md" "PROGRESS: COMPLETE" "SKILLS: design"
state "$R" VERIFIED roles_required=1 \
  roles="{\"designer\":\"docs/notes/design.md\",\"coder\":\"$CPATH\",\"verifier\":\"$VPATH\"}"
expect "64 handoff outside work/<tid>/handoff fails" 1 "is not under work/TASK-9/handoff/" WC "$R"

state "$R" UNIT_TESTED roles_required=1 roles="{\"designer\":\"$DPATH\"}"
expect "64 missing coder at UNIT_TESTED fails" 1 "roles.coder is missing" WC "$R"

state "$R" UNIT_TESTED roles_required=1 \
  roles="{\"designer\":\"$DPATH\",\"coder\":{\"waiver\":\"pairing session, no separate coder\"}}"
expect "64 coder waiver at UNIT_TESTED passes" 0 "PASS: workflow state" WC "$R"

state "$R" UNIT_TESTED roles_required=1 \
  roles="{\"designer\":\"$DPATH\",\"coder\":{\"waiver\":\"\"}}"
expect "64 empty coder waiver fails" 1 "roles.coder waiver is empty" WC "$R"

state "$R" UNIT_TESTED roles_required=1 \
  roles="{\"designer\":\"$DPATH\",\"coder\":\"work/TASK-9/handoff/missing.md\"}"
expect "64 missing handoff path fails" 1 "does not exist" WC "$R"

mkhandoff "work/TASK-9/handoff/noskills.md" "PROGRESS: COMPLETE" "no skills line here"
state "$R" UNIT_TESTED roles_required=1 \
  roles="{\"designer\":\"$DPATH\",\"coder\":\"work/TASK-9/handoff/noskills.md\"}"
expect "64 handoff without SKILLS line fails" 1 "role coder handoff not complete" WC "$R"

mkhandoff "work/TASK-9/handoff/partial.md" "PROGRESS: IN_PROGRESS" "SKILLS: bash"
state "$R" UNIT_TESTED roles_required=1 \
  roles="{\"designer\":\"$DPATH\",\"coder\":\"work/TASK-9/handoff/partial.md\"}"
expect "64 PARTIAL (IN_PROGRESS) handoff fails" 1 "role coder handoff not complete" WC "$R"

state "$R" VERIFIED roles_required=1 roles="{\"designer\":\"$DPATH\",\"coder\":\"$CPATH\"}"
expect "64 missing verifier at VERIFIED fails" 1 "roles.verifier is missing" WC "$R"

state "$R" IMPLEMENTING implstatus=pending roles_required=1 roles="{\"designer\":\"$DPATH\"}"
expect "64 entering IMPLEMENTING with implementation pending passes" 0 "PASS: workflow state" WC "$R"

state "$R" VERIFIED
expect "64 legacy task (no roles_required key) is exempt" 0 "PASS: workflow state" WC "$R"

state "$R" DONE; mark_done
python3 -c 'import json,sys;p=sys.argv[1];b=json.load(open(p));b.append({"task_id":"TASK-10","title":"q","status":"queued"});json.dump(b,open(p,"w"))' \
  "$R/.claude/state/backlog.json"
commit_all
expect "64 pick writes the roles_required marker" 0 "PICKED: TASK-10" BL pick TASK-10
python3 - "$R/.claude/state/task.json" <<'PY'
import json, sys
t = json.load(open(sys.argv[1]))
assert t.get("roles_required") is True, "pick did not write roles_required:true"
assert t.get("roles") == {}, "pick did not write roles:{}"
print("PASS: pick marker fields present")
PY

# --- 94.x: user notes in tasks (REQ-0059) ---------------------------------------
mkraw() {  # mkraw <num5> <status> <created> [reason] [links]
  mkdir -p "$R/docs/req/raw"
  printf -- '---\nid: RAW-%s\nstatus: %s\ncreated: %s\nsession: s\nlinks: %s\n' "$1" "$2" "$3" "${5:-[]}" > "$R/docs/req/raw/RAW-$1.md"
  if [ -n "${4:-}" ]; then printf 'reason: %s\n' "$4" >> "$R/docs/req/raw/RAW-$1.md"; fi
  printf -- '---\ntext\n' >> "$R/docs/req/raw/RAW-$1.md"
}
notes_n() {  # notes_n <task.json|backlog> <TASK> -> count
  python3 - "$R" "$1" "$2" <<'PY'
import json, sys
r, w, t = sys.argv[1:4]
if w == "task.json":
    print(len(json.load(open(f"{r}/.claude/state/task.json")).get("user_notes", [])))
else:
    print(len(next(i for i in json.load(open(f"{r}/.claude/state/backlog.json")) if i["task_id"] == t).get("user_notes", [])))
PY
}
hashst() { sha256sum "$R/.claude/state/task.json" "$R/.claude/state/backlog.json" | cut -d' ' -f1 | tr -d '\n'; }
HASH0=""
same_hash() { [ "$(hashst)" = "$HASH0" ] && echo "HASH-SAME"; }

fresh "$R"
state "$R" IMPLEMENTING
python3 - "$R/.claude/state/backlog.json" <<'PY'
import json, sys
p = sys.argv[1]
b = json.load(open(p))
b.append({"task_id": "TASK-8", "title": "q", "status": "queued", "user_notes": [
    {"raw": "RAW-00011", "note": "first queued"}, {"raw": "RAW-00012", "note": "second queued"}]})
b.append({"task_id": "TASK-10", "title": "q2", "status": "queued"})
json.dump(b, open(p, "w"), indent=2)
PY
mkraw 00001 TRIAGED "2020-01-01 00:00"
mkraw 00011 TRIAGED "2020-01-01 00:00"
mkraw 00012 TRIAGED "2020-01-01 00:00"
mkraw 00013 TRIAGED "2020-01-01 00:00"
commit_all
expect "94.1 note adds to the active task" 0 "NOTED: RAW-00001 -> TASK-9" BL note active RAW-00001 "keep the gate lines"
expect "94.1 note is in task.json" 0 "1" notes_n task.json TASK-9
HASH0="$(hashst)"
expect "94.1 repeat note is ALREADY" 0 "ALREADY: RAW-00001 on TASK-9" BL note TASK-9 RAW-00001 "other text"
expect "94.1 repeat note writes nothing" 0 "HASH-SAME" same_hash
expect "94.1 note on a queued target goes to the backlog item" 0 "NOTED: RAW-00013 -> TASK-10" BL note TASK-10 RAW-00013 "for the next task"
expect "94.1 queued item has the note" 0 "1" notes_n backlog TASK-10
expect "94.1 unknown RAW is refused" 1 "FAIL:" BL note active RAW-00099 "x"
expect "94.1 bad RAW id is refused" 1 "FAIL:" BL note active RAW-1 "x"
expect "94.1 path-like task id is refused" 1 "FAIL:" BL note ../x RAW-00001 "x"
expect "94.1 unknown task is refused" 1 "FAIL:" BL note TASK-77 RAW-00001 "x"
expect "94.1 newline in note is refused" 1 "FAIL:" BL note active RAW-00011 "a
b"
expect "94.1 URL in note is refused" 1 "FAIL:" BL note active RAW-00011 "see https://example.invalid/x"
expect "94.1 secret-like note is refused" 1 "FAIL:" BL note active RAW-00011 "password=hunter2"
expect "94.1 40-char token is refused" 1 "FAIL:" BL note active RAW-00011 "use abcdefghijklmnopqrstuvwxyzABCDEFGHIJ0123"
expect "94.1 over-long note is refused" 1 "FAIL:" BL note active RAW-00011 "$(printf 'a b %.0s' $(seq 1 80))"
expect "94.1 32-char token (boundary) is refused" 1 "FAIL:" BL note active RAW-00011 "$(printf 'a%.0s' $(seq 1 32))"
expect "94.1 201-char note (boundary) is refused" 1 "FAIL:" BL note active RAW-00011 "$(printf 'a %.0s' $(seq 1 100))x"
expect "94.1 refused notes wrote nothing" 0 "1" notes_n task.json TASK-9
expect "94.1 31-char word is accepted" 0 "NOTED: RAW-00011 -> TASK-9" BL note active RAW-00011 "$(printf 'a%.0s' $(seq 1 31))"
expect "94.1 200-char note is accepted" 0 "NOTED: RAW-00012 -> TASK-9" BL note active RAW-00012 "$(printf 'a %.0s' $(seq 1 100))"
expect "94.1 notes <id> lists RAW lines" 0 "RAW-00001: keep the gate lines" BL notes active
expect "94.1 notes lists queued counts" 0 "Queued user notes: TASK-10=1 TASK-8=2" BL notes

# 94.2: pick copies, complete keeps
state "$R" DONE; mark_done
python3 - "$R/.claude/state/backlog.json" <<'PY'
import json, sys
p = sys.argv[1]
b = json.load(open(p))
b.append({"task_id": "TASK-8", "title": "q", "status": "queued", "user_notes": [
    {"raw": "RAW-00011", "note": "first queued"}, {"raw": "RAW-00012", "note": "second queued"}]})
json.dump(b, open(p, "w"), indent=2)
PY
commit_all
expect "94.2 pick carries the queued notes" 0 "PICKED: TASK-8" BL pick TASK-8
expect "94.2 task.json has both notes" 0 "2" notes_n task.json TASK-8
tjq() { python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2],""))' "$R/.claude/state/task.json" "$1"; }
expect "94.2 pick records picked_at" 0 "Z" tjq picked_at
expect "94.2 note on the active task" 0 "NOTED: RAW-00013 -> TASK-8" BL note active RAW-00013 "added while active"
python3 - "$R/.claude/state/task.json" <<'PY'
import json, sys
p = sys.argv[1]
t = json.load(open(p))
t.update(state="DONE", report={"status": "completed", "path": "docs/R.md"})
json.dump(t, open(p, "w"), indent=2)
PY
expect "94.2 complete merges notes into the backlog item" 0 "COMPLETED: TASK-8" BL complete TASK-8 --force "test"
expect "94.2 backlog item keeps all 3 notes" 0 "3" notes_n backlog TASK-8

# 94.3: print in task-state and session-start
fresh "$R"
state "$R" IMPLEMENTING
python3 - "$R/.claude/state/backlog.json" <<'PY'
import json, sys
p = sys.argv[1]
b = json.load(open(p))
b.append({"task_id": "TASK-8", "title": "q", "status": "queued", "user_notes": [
    {"raw": "RAW-00011", "note": "a"}, {"raw": "RAW-00012", "note": "b"}]})
json.dump(b, open(p, "w"), indent=2)
PY
mkraw 00001 TRIAGED "2020-01-01 00:00"
TS() { bash "$R/.claude/scripts/task-state.sh"; }
TS_BEFORE="$(TS)"
expect "94.3 no notes -> no notes block" 0 "Last phase-log entry" TS
if printf '%s' "$TS_BEFORE" | grep -qF "User notes"; then bad "94.3 task without notes prints no block"; else ok "94.3 task without notes prints no block"; fi
commit_all
BL note active RAW-00001 "honour the gates" >/dev/null
expect "94.3 task-state prints the count" 0 "User notes (1):" TS
expect "94.3 task-state prints the RAW line" 0 "  RAW-00001: honour the gates" TS
git -C "$R" add -A && git -C "$R" commit -qm n --no-verify
SS() { CLAUDE_PROJECT_DIR="$R" bash "$R/.claude/hooks/session-start.sh"; }
expect "94.3 backlog.sh notes prints queued counts" 0 "Queued user notes: TASK-8=2" BL notes

# 94.4: workflow-check WARN
fresh "$R"
state "$R" IMPLEMENTING
mkraw 00020 IGNORED "2031-01-01 00:00" "instruction for current step"
mkraw 00021 IGNORED "2031-01-01 00:00" "not task-related chatter"
mkraw 00022 IGNORED "2029-01-01 00:00" "instruction for current step"
mkraw 00023 IGNORED "2031-01-01 00:00" "short ack (auto, ok)"
mkdir -p "$R/docs/req/items"
printf -- '---\nid: REQ-0900\ntasks: []\n---\n' > "$R/docs/req/items/REQ-0900.md"
mkraw 00024 TRIAGED "2031-01-01 00:00" "" "[REQ-0900]"
expect "94.4 no picked_at -> no WARN" 0 "PASS: workflow state is consistent" WC "$R"
python3 - "$R/.claude/state/task.json" <<'PY'
import json, sys
p = sys.argv[1]
t = json.load(open(p))
t["picked_at"] = "2030-01-01T00:00:00Z"
json.dump(t, open(p, "w"), indent=2)
PY
expect "94.4 un-noted RAW after pick WARNs" 0 "RAW-00020 (triaged since TASK-9 pick) is in no task's user_notes" WC "$R"
out94="$(WC "$R" 2>&1 || true)"
if printf '%s' "$out94" | grep -qE 'RAW-0002[1234]|RAW-00022'; then bad "94.4 exempt and old RAWs do not WARN"; printf '%s\n' "$out94" | sed 's/^/    /'; else ok "94.4 exempt and old RAWs do not WARN"; fi
expect "94.4 WARN keeps rc 0 and PASS" 0 "PASS: workflow state is consistent (1 warning(s))" WC "$R"
BL note active RAW-00020 "steers this task" >/dev/null
expect "94.4 noted RAW clears the WARN" 0 "PASS: workflow state is consistent" WC "$R"
if WC "$R" 2>&1 | grep -qF "WARN:"; then bad "94.4 no WARN after note"; else ok "94.4 no WARN after note"; fi
printf -- '---\nid: REQ-0901\ntasks: [TASK-1]\n---\n' > "$R/docs/req/items/REQ-0901.md"
mkraw 00025 TRIAGED "2031-01-01 00:00" "" "[REQ-0901]"
expect "94.4 TRIAGED RAW linked to a REQ with tasks WARNs" 0 "RAW-00025 (triaged since TASK-9 pick)" WC "$R"
# DONE report line
state "$R" DONE rpath=docs/report/phase-9-gates.md; mark_done
python3 - "$R/.claude/state/task.json" <<'PY'
import json, sys
p = sys.argv[1]
t = json.load(open(p))
t["user_notes"] = [{"raw": "RAW-00020", "note": "n"}]
json.dump(t, open(p, "w"), indent=2)
PY
expect "94.4 DONE report without the line WARNs" 0 "User instructions honoured" WC "$R"
printf 'User instructions honoured: RAW-00020\n' >> "$R/docs/report/phase-9-gates.md"
if WC "$R" 2>&1 | grep -qF "User instructions honoured"; then bad "94.4 DONE report with the line is quiet"; else ok "94.4 DONE report with the line is quiet"; fi

# --- TASK-095: report cross-check DONE gate (crosscheck_required) ------------
fresh "$R"
XPATH="work/TASK-9/handoff/crosscheck.md"
state "$R" DONE rpath=docs/report/phase-9-gates.md; mark_done
expect "95.6 DONE without the key WARNs" 0 "no report cross-check recorded" WC "$R"
state "$R" DONE rpath=docs/report/phase-9-gates.md roles_required=1 crosscheck_required=1 roles='{}'; mark_done
expect "95.6 key set, no crosscheck handoff fails" 1 "roles.crosscheck" WC "$R"
mkdir -p "$R/work/TASK-9/handoff"
printf 'PROGRESS: COMPLETE\nSKILLS: crosscheck\nRESULT: MISS\n' > "$R/$XPATH"
state "$R" DONE rpath=docs/report/phase-9-gates.md roles_required=1 crosscheck_required=1 roles="{\"crosscheck\":\"$XPATH\"}"; mark_done
expect "95.6 RESULT: MISS handoff fails" 1 "RESULT: MISS" WC "$R"
printf 'PROGRESS: COMPLETE\nSKILLS: crosscheck\nRESULT: OK\n' > "$R/$XPATH"
if WC "$R" 2>&1 | grep -qF "RESULT: MISS"; then bad "95.6 RESULT: OK handoff is not a MISS"; else ok "95.6 RESULT: OK handoff is not a MISS"; fi

# --- 124.6 incident gate / 124.10 learn-forward WARN ------------------------
IJ='{"ledger":"I9","guard":"g.sh","bite":"bite.txt"}'
INC="$R/docs/notes/incidents.md"
inc_fix() {  # DONE fixture with ledger row I9, guard g.sh, bite.txt (FAIL line)
  state "$R" DONE rpath=docs/report/phase-9-gates.md incident="$IJ"; mark_done
  mkdir -p "$R/docs/notes"
  printf '| id | date |\n|---|---|\n| I9 | d | s | root in scripts/foo.sh:12 | `g.sh` | TASK-9 |\n' > "$INC"
  echo x > "$R/g.sh"; echo "FAIL: case" > "$R/bite.txt"
}
inc_fix
expect "124.6 all present passes" 0 "PASS: workflow state" WC "$R"
rm "$R/bite.txt"
expect "124.6 bite file missing fails" 1 "incident bite 'bite.txt' does not exist" WC "$R"
echo "PASS: only" > "$R/bite.txt"
expect "124.6 bite without FAIL fails" 1 "has no FAIL line" WC "$R"
echo "FAIL: case" > "$R/bite.txt"; rm "$R/g.sh"
expect "124.6 guard missing fails" 1 "incident guard 'g.sh' does not exist" WC "$R"
echo x > "$R/g.sh"; printf '| I8 | d | s | r | g | t |\n' > "$INC"
expect "124.6 ledger row absent fails" 1 "incident ledger row 'I9' not found" WC "$R"
state "$R" DONE rpath=docs/report/phase-9-gates.md; mark_done
expect "124.6 no key unchanged" 0 "PASS: workflow state" WC "$R"

printf '| I9 | d | s | root in scripts/foo.sh:12 | `g.sh` | TASK-9 |\n' > "$INC"
state "$R" DESIGN files='["scripts/foo.sh"]'
expect "124.10 match and no section WARNs" 0 "incident I9 names scripts/foo.sh" WC "$R"
printf 'prose names `## Known incidents` only\n' >> "$R/docs/design/phase-9-gates.md"
expect "124.10 prose mention is not a section: WARNs" 0 "incident I9 names scripts/foo.sh" WC "$R"
printf '\n## Known incidents\nI9\n' >> "$R/docs/design/phase-9-gates.md"
if WC "$R" 2>&1 | grep -qF "incident I9"; then bad "124.10 section present: no WARN"; else ok "124.10 section present: no WARN"; fi
state "$R" DESIGN files='["other/bar.sh"]'
if WC "$R" 2>&1 | grep -qF "incident I9"; then bad "124.10 no match: no WARN"; else ok "124.10 no match: no WARN"; fi

echo "SUMMARY(workflow-gates): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

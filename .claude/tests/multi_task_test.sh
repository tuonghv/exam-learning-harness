#!/usr/bin/env bash
# Regression test for several active tasks (REQ-0060, phase 96, slice 1): per-task state files,
# tasks.sh, multi-mode pick/complete/note, workflow-check per task, commit-check one task per
# commit, the readers, and legacy / mixed / migrate. Every case runs in a throwaway git repo
# holding a copy of the kit; the real state is never touched.
# Run: bash .claude/tests/multi_task_test.sh      (KIT_DIR=<kit> tests another copy, the bite check)
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
    bad "$name (rc=$rc, want $want_rc)"; printf '%s\n' "$out" | sed 's/^/    /' | head -n 12; return
  fi
  if [ -n "$want_out" ] && ! printf '%s' "$out" | grep -qF -- "$want_out"; then
    bad "$name (output lacks '$want_out')"; printf '%s\n' "$out" | sed 's/^/    /' | head -n 12; return
  fi
  ok "$name"
}
# refute <name> <substring> <cmd...>: output must NOT contain the substring (rc ignored)
refute() {
  local name="$1" nope="$2" out; shift 2
  out="$("$@" 2>&1)" || true
  if printf '%s' "$out" | grep -qF -- "$nope"; then bad "$name (output has '$nope')"; else ok "$name"; fi
}

fresh() {
  rm -rf "$1"; mkdir -p "$1"
  cp -r "$KIT" "$1/.claude"
  find "$1/.claude" -name __pycache__ -prune -exec rm -rf {} +
  rm -rf "$1/.claude/tests" "$1/.claude/state"; mkdir -p "$1/.claude/state"
  printf '{"max_active": 3}\n' > "$1/.claude/workflow.json"  # fixture pinned: independent of the real setting
  git -C "$1" init -q
  git -C "$1" config user.email t@example.invalid
  git -C "$1" config user.name test
}
commit_all() { git -C "$1" add -A && git -C "$1" commit -qm "${2:-fixture}" --no-verify; }

# legacy <dir>: single task.json for TASK-1 (IMPLEMENTING, evidenced) + queued TASK-2..5, committed.
legacy() {
  local d="$1"
  fresh "$d"
  python3 - "$d" <<'PY'
import json, os, sys
d = sys.argv[1]
for sub in ("docs/design", "docs/report", "src"):
    os.makedirs(f"{d}/{sub}", exist_ok=True)
os.makedirs(f"{d}/docs/req/raw", exist_ok=True)
for n in (1, 2):
    open(f"{d}/docs/req/raw/RAW-0000{n}.md", "w").write("raw\n")
for n in "abcd":
    open(f"{d}/src/{n}.py", "w").write("x = 1\n")
open(f"{d}/docs/design/phase-1-one.md", "w").write("design\n")
def task(tid, title, state="IMPLEMENTING"):
    return {"task_id": tid, "title": title, "state": state, "requirement": "r",
            "acceptance_criteria": ["a"],
            "design": {"status": "completed", "summary": "s", "path": "docs/design/phase-1-one.md"},
            "implementation": {"status": "pending", "files": ["src/a.py"]},
            "unit_test": {"status": "pending", "command": "", "result": ""},
            "security": {"status": "pending", "result": ""},
            "verification": {"status": "pending", "evidence": []},
            "report": {"status": "pending", "path": ""},
            "updated_at": "2026-01-01T00:00:00Z", "updated_by": "test", "next": "n"}
json.dump(task("TASK-1", "one"), open(f"{d}/.claude/state/task.json", "w"), indent=2)
items = [{"task_id": "TASK-1", "title": "one", "status": "active", "priority": "normal", "scope": ["src/a.py"]}]
for i, f in ((2, "b"), (3, "a"), (4, "c"), (5, "d")):
    items.append({"task_id": f"TASK-{i}", "title": f"t{i}", "status": "queued",
                  "priority": "normal", "scope": [f"src/{f}.py"]})
json.dump(items, open(f"{d}/.claude/state/backlog.json", "w"), indent=2)
log = "# Phase Log\n"
for s in ("DESIGN", "IMPLEMENTING"):
    log += f"\n## {s} - TASK-1 - 2026-01-01T00:00:00Z\n"
open(f"{d}/.claude/state/phase-log.md", "w").write(log)
PY
  commit_all "$d" legacy
}

# multi <dir>: legacy + migrate, committed (TASK-1 active in schema-2 mode)
# Until commit-check.sh is multi-aware in the kit, try the coder's patch on the fixture copy.
PATCH="$KIT/../work/TASK-096/patches/commit-check-multi.py"
multi() { legacy "$1"
  if ! grep -q '_tasks.py' "$1/.claude/scripts/commit-check.sh" && [ -f "$PATCH" ]; then
    python3 "$PATCH" "$1/.claude/scripts/commit-check.sh" >/dev/null
  fi
  (cd "$1" && bash .claude/scripts/tasks.sh migrate >/dev/null); commit_all "$1" migrated; }

TS() { local d="$1"; shift; (cd "$d" && bash .claude/scripts/tasks.sh "$@"); }
BL() { local d="$1"; shift; (cd "$d" && bash .claude/scripts/backlog.sh "$@"); }
WC() { local d="$1"; shift; (cd "$d" && bash .claude/scripts/workflow-check.sh "$@"); }
R="$WORK/r"

# --- M9: legacy, mixed, migrate ------------------------------------------------------------
legacy "$R"
expect "M9 legacy repo: mode is legacy" 0 "legacy" bash -c "cd '$R' && python3 .claude/scripts/_tasks.py mode"
expect "M9 legacy repo: workflow-check passes as before" 0 "PASS: workflow state" WC "$R"
refute "M9 legacy repo: no TASK- prefix on lines" "TASK-1: " WC "$R"
expect "M9 legacy repo: task-state prints the single task" 0 "Task: TASK-1" bash -c "cd '$R' && bash .claude/scripts/task-state.sh"
BEFORE="$(cat "$R/.claude/state/task.json")"
expect "M9 legacy: note on active still works" 0 "" BL "$R" note active RAW-00001 "legacy note"
if [ "$(cat "$R/.claude/state/task.json")" != "$BEFORE" ]; then ok "M9 legacy note wrote task.json"; else bad "M9 legacy note wrote task.json"; fi
git -C "$R" checkout -q -- .claude/state

# mixed: a task file without the schema -> FAIL naming migrate
cp "$R/.claude/state/task.json" "$R/.claude/state/task.TASK-1.json"
expect "M9 mixed mode: workflow-check fails" 1 "tasks.sh migrate" WC "$R"
expect "M9 mixed mode: pick refuses" 1 "tasks.sh migrate" BL "$R" pick TASK-2
rm "$R/.claude/state/task.TASK-1.json"

# migrate
expect "M9 migrate succeeds" 0 "" TS "$R" migrate
if [ -f "$R/.claude/state/task.TASK-1.json" ]; then ok "M9 migrate wrote task.TASK-1.json"; else bad "M9 migrate wrote task.TASK-1.json"; fi
expect "M9 view has schema 2" 0 "2" bash -c "jq -r .schema '$R/.claude/state/task.json'"
expect "M9 view lists the active task" 0 "TASK-1" bash -c "jq -r '.active[].task_id' '$R/.claude/state/task.json'"
expect "M9 mode is multi after migrate" 0 "multi" bash -c "cd '$R' && python3 .claude/scripts/_tasks.py mode"
expect "M9 workflow-check passes in multi mode" 0 "PASS" WC "$R"
expect "M9 tasks.sh list shows TASK-1" 0 "TASK-1" TS "$R" list
expect "M9 stale with no recorded inputs is clean" 0 "OK" TS "$R" stale TASK-1
expect "M9 bad task id refused (scope)" 1 "" TS "$R" scope '../x' --set a
expect "M9 bad pick id refused" 1 "" BL "$R" pick '../x'

# --- M1: two disjoint picks pass -----------------------------------------------------------
multi "$R"
expect "M1 pick TASK-2 (disjoint scope)" 0 "" BL "$R" pick TASK-2
commit_all "$R" "pick 2"
expect "M1 pick TASK-4 (disjoint scope)" 0 "" BL "$R" pick TASK-4
commit_all "$R" "pick 4"
expect "M1 three tasks active" 0 "TASK-4" TS "$R" list
expect "M1 workflow-check passes with three active tasks" 0 "PASS" WC "$R"
expect "M1 each task has its own file" 0 "" bash -c "test -f '$R/.claude/state/task.TASK-2.json' && test -f '$R/.claude/state/task.TASK-4.json'"
# --- M2: overlap / depends_on / empty scope / max_active ---------------------------------
expect "M2 4th pick refused at max_active" 1 "max_active" BL "$R" pick TASK-5
multi "$R"
expect "M2 overlap with TASK-1 keeps the item queued" 1 "queued behind TASK-1" BL "$R" pick TASK-3
expect "M2 blocked_by recorded" 0 "TASK-1" bash -c "jq -r '.[]|select(.task_id==\"TASK-3\")|.blocked_by' '$R/.claude/state/backlog.json'"
commit_all "$R" "blocked"
# complete clears blocked_by: make TASK-1 completable via a waiver-free path -> use the helper directly
expect "M2 depends_on unmet keeps queued" 1 "queued behind" bash -c "
  cd '$R' && python3 - <<'PY'
import json
p='.claude/state/backlog.json'; b=json.load(open(p))
for i in b:
    if i['task_id']=='TASK-5': i['depends_on']=['TASK-3']
json.dump(b,open(p,'w'),indent=2)
PY
  git add -A && git commit -qm dep --no-verify && bash .claude/scripts/backlog.sh pick TASK-5"
expect "M2 empty scope while others active fails" 1 "empty scope" bash -c "
  cd '$R' && git checkout -q -- .claude/state && python3 - <<'PY'
import json
p='.claude/state/backlog.json'; b=json.load(open(p))
for i in b:
    if i['task_id']=='TASK-4': i['scope']=[]
json.dump(b,open(p,'w'),indent=2)
PY
  git add -A && git commit -qm noscope --no-verify && bash .claude/scripts/backlog.sh pick TASK-4"

# --- M3: one task per commit ---------------------------------------------------------------
multi "$R"
BL "$R" pick TASK-2 >/dev/null; commit_all "$R" "pick 2"
BL "$R" pick TASK-4 >/dev/null; commit_all "$R" "pick 4"
for t in TASK-2 TASK-4; do
  python3 - "$R" "$t" <<'PY2'
import json, sys
p = "%s/.claude/state/task.%s.json" % (sys.argv[1], sys.argv[2])
d = json.load(open(p)); d["next"] = "edited"; json.dump(d, open(p, "w"), indent=2)
PY2
done
TS "$R" sync >/dev/null
MSG="$WORK/msg"
printf 'wip: x\n\nTask: TASK-2\nState: TODO\n' > "$MSG"
CC() { (cd "$R" && bash .claude/scripts/commit-check.sh "$MSG"); }
if grep -q '_tasks.py' "$R/.claude/scripts/commit-check.sh"; then
  git -C "$R" add -A
  expect "M3 two tasks staged in one commit fails" 1 "one task per commit" CC
  git -C "$R" reset -q
  git -C "$R" add .claude/state/task.TASK-2.json .claude/state/backlog.json .claude/state/task.json .claude/state/phase-log.md
  expect "M3 only the named task staged: dirty TASK-4 file does not block" 0 "commit-check: OK" CC
  python3 - "$R" <<'PY'
import json, sys
p = sys.argv[1] + "/.claude/state/task.TASK-2.json"
d = json.load(open(p)); d["state"] = "IMPLEMENTING"; json.dump(d, open(p, "w"), indent=2)
PY
  git -C "$R" add .claude/state/task.TASK-2.json
  expect "M3 trailer vs per-task state drift fails" 1 "state drift" CC
else
  echo "SKIP: M3 commit-check is not multi-aware yet (apply work/TASK-096/patches/commit-check-multi.py)"
fi

# --- M4: DONE of A leaves B byte-equal; M2 complete clears blocked_by ----------------------
multi "$R"
BL "$R" pick TASK-2 >/dev/null
commit_all "$R" "pick 2"
BL "$R" pick TASK-3 >/dev/null 2>&1 || true   # queued behind TASK-1 (blocked_by)
commit_all "$R" "blocked 3"
B_BEFORE="$(cat "$R/.claude/state/task.TASK-2.json")"
python3 - "$R" <<'PY'
import json, os, sys
d = sys.argv[1]
t = json.load(open(d + "/.claude/state/task.TASK-1.json"))
os.makedirs(d + "/docs/report", exist_ok=True)
open(d + "/docs/report/phase-1-one.md", "w").write("report\n")
for s, k in (("UNIT_TESTED", "unit_test"), ("VERIFIED", "verification")):
    pass
t.update(state="DONE")
t["implementation"]["status"] = "completed"
t["unit_test"] = {"status": "passed", "command": "c", "result": "r"}
t["security"] = {"status": "not_applicable", "result": "test fixture"}
t["verification"] = {"status": "passed", "evidence": ["e"]}
t["report"] = {"status": "completed", "path": "docs/report/phase-1-one.md"}
t["next"] = ""
json.dump(t, open(d + "/.claude/state/task.TASK-1.json", "w"), indent=2)
log = open(d + "/.claude/state/phase-log.md").read()
for s in ("UNIT_TESTED", "VERIFIED", "DONE"):
    log += f"\n## {s} - TASK-1 - 2026-01-02T00:00:00Z\n"
open(d + "/.claude/state/phase-log.md", "w").write(log)
PY
commit_all "$R" "TASK-1 done state"
expect "M2 complete TASK-1 unblocks TASK-3" 0 "unblocked" BL "$R" complete TASK-1
if [ "$(cat "$R/.claude/state/task.TASK-2.json")" = "$B_BEFORE" ]; then ok "M4 DONE of TASK-1 leaves TASK-2 byte-equal"; else bad "M4 DONE of TASK-1 leaves TASK-2 byte-equal"; fi
expect "M2 blocked_by cleared after complete" 0 "null" bash -c "jq -r '.[]|select(.task_id==\"TASK-3\")|.blocked_by' '$R/.claude/state/backlog.json'"
expect "M4 TASK-1 is no longer active" 0 "" bash -c "! python3 '$R/.claude/scripts/_tasks.py' active | grep -qx TASK-1"
expect "M4 workflow-check still passes" 0 "PASS" WC "$R"

# --- M5: crosscheck MISS is scoped to the task (workflow-check --task) ---------------------
multi "$R"
BL "$R" pick TASK-2 >/dev/null; commit_all "$R" "pick 2"
python3 - "$R" <<'PY'
import json, sys
p = sys.argv[1] + "/.claude/state/task.TASK-2.json"
d = json.load(open(p)); d["crosscheck_required"] = True; json.dump(d, open(p, "w"), indent=2)
PY
expect "M5 --task TASK-1 ignores TASK-2's missing crosscheck" 0 "PASS" WC "$R" --task TASK-1
expect "M5 --task TASK-2 reports its own state" 0 "" WC "$R" --task TASK-2
expect "M5 --task with a bad id is refused" 1 "" WC "$R" --task '../x'

# --- M6: note active with several active tasks ---------------------------------------------
expect "M6 note active is refused (name the task)" 1 "name the task" BL "$R" note active RAW-00001 "hello"
expect "M6 note TASK-2 lands in task.TASK-2.json" 0 "" BL "$R" note TASK-2 RAW-00002 "named note"
expect "M6 note stored on TASK-2 only" 0 "named note" bash -c "jq -r '.user_notes[].note' '$R/.claude/state/task.TASK-2.json'"
refute "M6 TASK-1 untouched by the TASK-2 note" "named note" bash -c "cat '$R/.claude/state/task.TASK-1.json'"

# --- M7: readers show every active task ----------------------------------------------------
expect "M7 task-state shows TASK-1" 0 "TASK-1" bash -c "cd '$R' && bash .claude/scripts/task-state.sh"
expect "M7 task-state shows TASK-2" 0 "TASK-2" bash -c "cd '$R' && bash .claude/scripts/task-state.sh"
expect "M7 status shows TASK-2" 1 "TASK-2 - t2" bash -c "cd '$R' && bash .claude/scripts/status.sh"
expect "M7 team-status names both tasks" 0 "TASK: TASK-2" bash -c "cd '$R' && bash .claude/scripts/team-status.sh"
expect "M7 team-status names TASK-1 too" 0 "TASK: TASK-1" bash -c "cd '$R' && bash .claude/scripts/team-status.sh"
expect "M7 checklist runs in multi mode" 0 "" bash -c "cd '$R' && bash .claude/scripts/checklist.sh"
expect "M7 save-evidence without TASK fails with several active" 2 "several active" bash -c "cd '$R' && env -u TASK -u CTXGUARD_TASK bash .claude/scripts/save-evidence.sh e -- true"
expect "M7 save-evidence with TASK=TASK-2 writes under work/TASK-2" 0 "" bash -c "cd '$R' && TASK=TASK-2 bash .claude/scripts/save-evidence.sh e -- true && test -f work/TASK-2/evidence/e.txt"
expect "M7 save-evidence honours CTXGUARD_TASK" 0 "" bash -c "cd '$R' && CTXGUARD_TASK=TASK-1 bash .claude/scripts/save-evidence.sh f -- true && test -f work/TASK-1/evidence/f.txt"

# --- held tasks and workflow.json (96.16) ---------------------------------------------------
multi "$R"
printf '{"max_active": 2}\n' > "$R/.claude/workflow.json"
commit_all "$R" cfg
BL "$R" pick TASK-2 >/dev/null; commit_all "$R" "pick 2"
expect "cfg workflow.json max_active=2 refuses the 3rd pick" 1 "max_active" BL "$R" pick TASK-4
expect "cfg env WORKFLOW_MAX_ACTIVE overrides the file" 0 "" bash -c "cd '$R' && WORKFLOW_MAX_ACTIVE=3 bash .claude/scripts/backlog.sh pick TASK-4"
commit_all "$R" "pick 4"
python3 - "$R" <<'PY3'
import json, sys
p = sys.argv[1] + "/.claude/state/task.TASK-2.json"
d = json.load(open(p)); d["status"] = "held"; d["scope"] = ["src/b.py", "src/d.py"]; json.dump(d, open(p, "w"), indent=2)
PY3
expect "held task is not in active" 0 "" bash -c "! python3 '$R/.claude/scripts/_tasks.py' active | grep -qx TASK-2"
commit_all "$R" "hold 2"
expect "held task still blocks an overlapping scope" 1 "queued behind TASK-2" bash -c "cd '$R' && WORKFLOW_MAX_ACTIVE=5 bash .claude/scripts/backlog.sh pick TASK-5"

# --- M10 pending question / due in multi mode (96.8) -----------------------------------------
multi "$R"
BL "$R" pick TASK-2 >/dev/null; commit_all "$R" "pick 2"
CK() { TASK_CHECKPOINT_NOW="$2" bash "$1/.claude/scripts/task_checkpoint.sh" "${@:3}"; }
expect "M10 ask on a non-active task is refused" 1 "not an active task" CK "$R" 1800000000 ask TASK-4 --question "q?" --recommend r --kind paid
expect "M10 ask on an active task works" 0 "ASKED: Q-1800000000 (TASK-1)" CK "$R" 1800000000 ask TASK-1 --question "A or B?" --recommend A --kind paid
expect "M10 9 minutes is not due" 0 "" CK "$R" 1800000540 due
expect "M10 10 minutes is due, rc 3" 3 "DUE TASK-1 Q-1800000000 age=10m" CK "$R" 1800000600 due
expect "M10 due names the other active task" 3 "work on: TASK-2 (" CK "$R" 1800000600 due
refute "M10 due does not name the waiting task" "work on: TASK-1" CK "$R" 1800000600 due
expect "M10 brief is rc 0 and names it" 0 "work on: TASK-2" CK "$R" 1800000600 brief

# --- M12 tasks.sh status (96.12) ---------------------------------------------------------------
python3 - "$R" <<'PY4'
import json, sys
p = sys.argv[1] + "/.claude/state/task.TASK-2.json"
d = json.load(open(p)); d["next"] = "x" * 200 + "\x1b[31mred"; json.dump(d, open(p, "w"), indent=2)
PY4
expect "M12 status rc 0, has running rows" 0 "running: TASK-1" TS "$R" status
expect "M12 status lists the open question" 0 "needs you: Q-1800000000" TS "$R" status
expect "M12 status lists queued tasks" 0 "queued: TASK-3" TS "$R" status
expect "M12 status is 25 lines at most" 0 "" bash -c "[ \"\$(bash '$R/.claude/scripts/tasks.sh' status | wc -l)\" -le 25 ]"
expect "M12 every status line is 80 characters at most" 0 "" bash -c "! bash '$R/.claude/scripts/tasks.sh' status | awk 'length(\$0) > 80 {f=1} END{exit !f}'"
expect "M12 control characters are stripped" 0 "" bash -c "! bash '$R/.claude/scripts/tasks.sh' status | grep -q \$'\\x1b'"
expect "M12 order: needs you before running before queued" 0 "" bash -c "bash '$R/.claude/scripts/tasks.sh' status | awk '/^needs you/{a=NR} /^running/{if(!b)b=NR} /^queued/{if(!c)c=NR} END{exit !(a<b && b<c)}'"
expect "M12 status is read-only" 0 "" bash -c "cd '$R' && git add -A && git commit -qm q --no-verify && bash .claude/scripts/tasks.sh status >/dev/null && test -z \"\$(git status --porcelain)\""

# --- M15 hold / resume / show (96.16) ----------------------------------------------------------
expect "M15 hold without --reason is a usage error" 2 "" TS "$R" hold TASK-2
expect "M15 hold of an unknown task is refused" 1 "" TS "$R" hold TASK-9 --reason r --next n
expect "M15 hold works" 0 "HELD: TASK-2" TS "$R" hold TASK-2 --reason "wait for user" --next "resume at 96.9"
expect "M15 held task is not active" 0 "" bash -c "! python3 '$R/.claude/scripts/_tasks.py' active | grep -qx TASK-2"
expect "M15 status shows the held task" 0 "held: TASK-2 age=0m Q=- (wait for user)" TS "$R" status
expect "M15 hold twice is refused" 1 "held" TS "$R" hold TASK-2 --reason r --next n
expect "M15 held scope stays reserved" 1 "TASK-2" bash -c "cd '$R' && git add -A && git commit -qm h --no-verify && bash .claude/scripts/backlog.sh pick TASK-2"
expect "M15 show prints the held reason" 0 "wait for user" TS "$R" show TASK-2
expect "M15 show is 15 lines at most" 0 "" bash -c "[ \"\$(bash '$R/.claude/scripts/tasks.sh' show TASK-2 | wc -l)\" -le 15 ]"
expect "M15 resume of an active task is refused" 1 "not held" TS "$R" resume TASK-1
expect "M15 resume works" 0 "RESUMED: TASK-2" TS "$R" resume TASK-2
expect "M15 resumed task is active again" 0 "" bash -c "python3 '$R/.claude/scripts/_tasks.py' active | grep -qx TASK-2"
printf '{"max_active": 2}\n' > "$R/.claude/workflow.json"
TS "$R" hold TASK-2 --reason r --next n >/dev/null
commit_all "$R" h2
BL "$R" pick TASK-4 >/dev/null || true
expect "M15 resume is refused at max_active" 1 "max_active" TS "$R" resume TASK-2

# --- scope helper --------------------------------------------------------------------------
expect "scope --add stores globs" 0 "" TS "$R" scope TASK-2 --add 'src/new/*'
expect "scope show prints them" 0 "src/new/*" TS "$R" scope TASK-2
expect "scope rejects a path outside the repo" 1 "" TS "$R" scope TASK-2 --set '../etc'

# --- M11 stale inputs (96.13) ------------------------------------------------------------------
multi "$R"
expect "M11 inputs --set records hashes" 0 "" TS "$R" inputs TASK-1 --set src/a.py,src/b.py
expect "M11 design doc is always an input" 0 "docs/design/phase-1-one.md" TS "$R" inputs TASK-1
expect "M11 stale is clean after --set" 0 "OK" TS "$R" stale TASK-1
expect "M11 workflow-check passes while clean" 0 "PASS" WC "$R"
echo "x = 2" > "$R/src/b.py"
expect "M11 changed input is stale, rc 4" 4 "STALE" TS "$R" stale TASK-1
expect "M11 stale text names the file and the rehash hint" 4 "src/b.py" TS "$R" stale TASK-1
expect "M11 workflow-check FAILs on stale inputs" 1 "stale" WC "$R"
expect "M11 status lists nothing for a running stale task" 0 "" TS "$R" status
expect "M11 rehash needs a reason" 1 "" TS "$R" inputs TASK-1 --rehash
expect "M11 rehash with reason works" 0 "" TS "$R" inputs TASK-1 --rehash --reason "designer delta: NOT AFFECTED"
expect "M11 stale is clean after rehash" 0 "OK" TS "$R" stale TASK-1
expect "M11 workflow-check passes after rehash" 0 "PASS" WC "$R"
expect "M11 reason is kept in inputs_reviews" 0 "NOT AFFECTED" bash -c "jq -r '.inputs_reviews[].reason' '$R/.claude/state/task.TASK-1.json'"
expect "M11 path outside the repo refused" 1 "" TS "$R" inputs TASK-1 --set ../etc/passwd
expect "M11 absolute path outside the repo refused" 1 "" TS "$R" inputs TASK-1 --set /etc/hostname
expect "M11 source-tree path refused" 1 "" TS "$R" inputs TASK-1 --set "pentest_source_code/x.py"
MANY=""; for i in $(seq 1 31); do echo "v" > "$R/src/m$i.txt"; MANY="$MANY,src/m$i.txt"; done
expect "M11 more than 30 inputs refused" 1 "30" TS "$R" inputs TASK-1 --set "${MANY#,}"

# --- M14 questions_open gate (96.15) -----------------------------------------------------------
multi "$R"
expect "M14 question shows the count" 0 "0" TS "$R" question TASK-1
expect "M14 question --set 1" 0 "" TS "$R" question TASK-1 --set 1
expect "M14 workflow-check FAILs while questions are open" 1 "question" WC "$R"
expect "M14 --decide needs a reason" 1 "" TS "$R" question TASK-1 --decide "use A"
expect "M14 --decide with reason clears it" 0 "" TS "$R" question TASK-1 --decide "use A" --reason "architect call"
expect "M14 decision is recorded as coordinator" 0 "coordinator" bash -c "jq -r '.decisions[-1].decided_by' '$R/.claude/state/task.TASK-1.json'"
expect "M14 decision keeps the reason" 0 "architect call" bash -c "jq -r '.decisions[-1].reason' '$R/.claude/state/task.TASK-1.json'"
expect "M14 workflow-check passes after the decision" 0 "PASS" WC "$R"
TS "$R" question TASK-1 --set 1 >/dev/null
expect "M14 --answer clears it too" 0 "" TS "$R" question TASK-1 --answer
expect "M14 workflow-check passes after the answer" 0 "PASS" WC "$R"

# --- M13 task reader inventory (96.14) ---------------------------------------------------------
TR="$KIT/scripts/checks/task_readers.sh"
if [ -f "$TR" ]; then
  expect "M13 the real tree has no unlisted reader" 0 "fail=0" bash "$TR" "$(cd "$KIT/.." && pwd)"
  FX="$WORK/fx"; rm -rf "$FX"; mkdir -p "$FX/.claude/scripts/checks" "$FX/.claude/hooks" "$FX/.claude/req"
  cp "$KIT/scripts/checks/task_readers.sh" "$FX/.claude/scripts/checks/"
  : > "$FX/.claude/scripts/checks/task_readers.allow"
  printf '#!/usr/bin/env bash\ncat .claude/state/task.json\n' > "$FX/.claude/scripts/newreader.sh"
  expect "M13 an unlisted reader FAILs" 1 "newreader.sh" bash "$FX/.claude/scripts/checks/task_readers.sh" "$FX"
  printf '.claude/scripts/newreader.sh | test reason\n' > "$FX/.claude/scripts/checks/task_readers.allow"
  expect "M13 a listed reader passes" 0 "fail=0" bash "$FX/.claude/scripts/checks/task_readers.sh" "$FX"
  printf '#!/usr/bin/env bash\nbash .claude/scripts/helper.sh\n' > "$FX/.claude/hooks/h.sh"
  printf '{"hooks":{"Stop":[{"hooks":[{"type":"command","command":".claude/hooks/h.sh"}]}]}}\n' > "$FX/.claude/settings.json"
  printf '#!/usr/bin/env bash\njq .task_id .claude/state/task.json\n' > "$FX/.claude/scripts/helper.sh"
  expect "M13 a reader behind a hook is found via the chain" 1 "helper.sh" bash "$FX/.claude/scripts/checks/task_readers.sh" "$FX"
  printf '.claude/scripts/ghost.sh | stale row\n' >> "$FX/.claude/scripts/checks/task_readers.allow"
  expect "M13 an allow row without a reader FAILs" 1 "ghost.sh" bash "$FX/.claude/scripts/checks/task_readers.sh" "$FX"
else
  bad "M13 checks/task_readers.sh missing"
fi

# --- 96.18 hardening ---------------------------------------------------------------------------
multi "$R"
expect "H corrupt task file FAILs naming the file" 1 "task.TASK-1.json" bash -c "cd '$R' && cp .claude/state/task.TASK-1.json /tmp/h.$$ && echo '{bad' > .claude/state/task.TASK-1.json && bash .claude/scripts/workflow-check.sh; rc=\$?; cp /tmp/h.$$ .claude/state/task.TASK-1.json; rm -f /tmp/h.$$; exit \$rc"
expect "H file restored, check passes" 0 "PASS" WC "$R"
expect "H no tmp files are left behind" 0 "" bash -c "test -z \"\$(ls '$R/.claude/state' | grep '\\.tmp\$')\""
BL "$R" pick TASK-2 >/dev/null; commit_all "$R" "pick 2"
expect "H empty scope refused while another task is active" 1 "empty scope" TS "$R" scope TASK-2 --set ""
GD="$R/.git/tasks-state.lock"
mkdir "$GD"; touch -d '20 minutes ago' "$GD"
expect "H a stale lock (older than 10 min) is broken" 0 "" TS "$R" hold TASK-2 --reason r --next n
expect "H the lock is released after the command" 0 "" bash -c "test ! -d '$GD'"
expect "H blocked_reason shows in status" 0 "held: TASK-2 age=0m Q=- (r)" TS "$R" status
python3 - "$R" <<'PY5'
import json, sys
p = sys.argv[1] + "/.claude/state/task.TASK-1.json"
d = json.load(open(p)); d["blocked"] = {"reason": "old", "attempts": 1}; d["blocked_reason"] = "waits for RAW-9"; json.dump(d, open(p, "w"), indent=2)
PY5
expect "H blocked_reason of a task is shown" 0 "waits for RAW-9" TS "$R" status
mkdir "$GD"
expect "H a fresh lock makes the command fail after waiting" 1 "lock" bash -c "cd '$R' && TASKS_LOCK_WAIT=1 bash .claude/scripts/tasks.sh resume TASK-2"
rmdir "$GD"

# --- 100.1-100.3 held task: workflow-check, commit, pick next to it ------------------------------
multi "$R"
expect "100.1 hold TASK-1" 0 "HELD: TASK-1" TS "$R" hold TASK-1 --reason "waits on Q" --next "answer Q"
commit_all "$R" "hold 1"
expect "100.1 workflow-check accepts a held task (rc 0)" 0 "" WC "$R"
refute "100.1 no FAIL line with a held task" "FAIL" WC "$R"
cp "$R/.claude/state/task.TASK-1.json" "$WORK/t1.json"
python3 - "$R" <<'PY6'
import json, sys
p = sys.argv[1] + "/.claude/state/task.TASK-1.json"
d = json.load(open(p)); d["checkpoint"]["next"] = ""; json.dump(d, open(p, "w"), indent=2)
PY6
expect "100.1 held task without checkpoint.next fails" 1 "lacks checkpoint.next" WC "$R"
cp "$WORK/t1.json" "$R/.claude/state/task.TASK-1.json"
printf 'Msg\n\nTask: TASK-1\nState: IMPLEMENTING\n' > "$R/msg.txt"
refute "100.2 commit of a held task is not refused as inactive" "not an active task" TS "$R" commit TASK-1 msg.txt -- nosuch.txt
python3 - "$R" <<'PY8'
import json, sys
p = sys.argv[1] + "/.claude/state/backlog.json"
b = json.load(open(p)); items = b if isinstance(b, list) else b.get("items", [])
for i in items:
    if i.get("task_id") == "TASK-3": i["scope"] = []
json.dump(b, open(p, "w"), indent=2)
PY8
commit_all "$R" "bl"
expect "100.3 scope-less pick next to a held task seeds work/T/" 0 "PICKED: TASK-3" BL "$R" pick TASK-3
expect "100.3 seeded scope is work/TASK-3/" 0 "work/TASK-3/" bash -c "jq -c .scope '$R/.claude/state/task.TASK-3.json'"

# --- 100.4-100.9 workable, autohold, recover rows, all-held PASS ----------------------------------
bl_edit() { python3 - "$1" "$2" <<'PYE'
import json, sys
p = sys.argv[1] + "/.claude/state/backlog.json"
b = json.load(open(p)); items = b if isinstance(b, list) else b.get("items", [])
for i in items:
    exec(sys.argv[2])
json.dump(b, open(p, "w"), indent=2)
PYE
}
CKA() { (cd "$1" && CTXGUARD_ROLE="${ROLE:-main}" TASK_CHECKPOINT_NOW="${NOW:-1800000600}" bash .claude/scripts/tasks.sh "${@:2}"); }
TCP() { bash "$R/.claude/scripts/task_checkpoint.sh" "$@"; }
multi "$R"
bl_edit "$R" 'if i["task_id"] == "TASK-2": i["paid"] = True
if i["task_id"] == "TASK-3": i["title"] = "PAID x"
if i["task_id"] == "TASK-4": i["needs_user"] = "user must decide"
if i["task_id"] == "TASK-5": i["priority"] = "high"'
expect "100.7 workable: paid flag is skipped" 0 "SKIP TASK-2 paid" TS "$R" workable
expect "100.7 workable: PAID title is skipped" 0 "SKIP TASK-3 paid" TS "$R" workable
expect "100.7 workable: needs_user is skipped" 0 "SKIP TASK-4 needs user" TS "$R" workable
expect "100.7 workable: high priority first" 0 "WORKABLE TASK-5" bash -c "cd '$R' && bash .claude/scripts/tasks.sh workable | head -n 1"
refute "100.7 workable --exclude drops the candidate" "TASK-5" TS "$R" workable --exclude TASK-5
expect "100.7 workable bad usage is rc 2" 2 "usage" TS "$R" workable --bogus
bl_edit "$R" 'if i["task_id"] == "TASK-2": i["paid"] = False; i["depends_on"] = ["TASK-4"]
if i["task_id"] == "TASK-3": i["title"] = "x"; i["blocked_by"] = "TASK-4"
if i["task_id"] == "TASK-4": i["needs_user"] = ""; i["scope"] = ["src/a.py"]'
expect "100.7 workable: depends_on not done" 0 "SKIP TASK-2 depends on TASK-4" TS "$R" workable
expect "100.7 workable: blocked_by not done" 0 "SKIP TASK-3 blocked by TASK-4" TS "$R" workable
expect "100.7 workable: scope overlap with an open task" 0 "SKIP TASK-4 scope overlaps TASK-1" TS "$R" workable

# autohold, in a fixture repo only
fix_ah() {
  multi "$R"
  bl_edit "$R" 'if i["task_id"] == "TASK-5": i["priority"] = "high"'
  CK "$R" 1800000000 ask TASK-1 --question "Go paid?" --recommend "yes" --kind paid >/dev/null
  commit_all "$R" "ask"
}
fix_ah
expect "100.4 ask without --kind is refused" 2 "not a user-only question" CK "$R" 1800000000 ask TASK-1 --question "q?" --recommend r
expect "100.4 ask with a bad kind is refused" 2 "RAW-00511" CK "$R" 1800000000 ask TASK-1 --question "q?" --recommend r --kind other
expect "100.4 entry stores kind" 0 "paid" bash -c "jq -r '.[0].kind' '$R/.claude/state/pending.json'"
expect "100.6 autohold before the timeout is rc 4" 4 "not due" env NOW=1800000300 bash -c "$(declare -f CKA); CKA '$R' autohold TASK-1 Q-1800000000"
expect "100.6 autohold of a wrong task is rc 4" 4 "belongs to" CKA "$R" autohold TASK-5 Q-1800000000
expect "100.6 autohold of an unknown question is rc 4" 4 "no pending question" CKA "$R" autohold TASK-1 Q-1
expect "100.6 a worker role is refused" 1 "main or the task's lead" env ROLE=coder bash -c "$(declare -f CKA); CKA '$R' autohold TASK-1 Q-1800000000"
expect "100.5 watch says DUE with the run line" 3 "run: tasks.sh autohold TASK-1 Q-1800000000" env TASK_CHECKPOINT_POLL_SEC=0 TASK_CHECKPOINT_NOW=1800000600 bash "$R/.claude/scripts/task_checkpoint.sh" watch Q-1800000000
expect "100.5 watch before the timeout is rc 1" 1 "WAITING" env TASK_CHECKPOINT_POLL_SEC=0 TASK_CHECKPOINT_NOW=1800000100 bash "$R/.claude/scripts/task_checkpoint.sh" watch Q-1800000000
expect "100.5 watch bad POLL is rc 2" 2 "TASK_CHECKPOINT_POLL_SEC" env TASK_CHECKPOINT_POLL_SEC=500 bash "$R/.claude/scripts/task_checkpoint.sh" watch Q-1800000000
expect "100.5 watch unknown question is rc 4" 4 "GONE" env TASK_CHECKPOINT_POLL_SEC=0 bash "$R/.claude/scripts/task_checkpoint.sh" watch Q-7
expect "100.6 autohold holds, picks, briefs (rc 0)" 0 "PICKED TASK-5" CKA "$R" autohold TASK-1 Q-1800000000
expect "100.6 TASK-1 is held on the question" 0 "held Q-1800000000" bash -c "jq -r '.status+\" \"+.held_question' '$R/.claude/state/task.TASK-1.json'"
expect "100.6 hold commit has the Task trailer" 0 "Task: TASK-1" bash -c "git -C '$R' log --format=%B | grep 'Task: TASK-1' | head -n 1"
expect "100.6 the pick commit exists" 0 "TASK-5 picked (auto, TASK-1 held)" bash -c "git -C '$R' log --format=%s -n 3"
expect "100.6 the tree is clean after both commits" 0 "" bash -c "test -z \"\$(git -C '$R' status --porcelain)\""
expect "100.9 due shows HELD, rc 0" 0 "HELD TASK-1 Q-1800000000" env TASK_CHECKPOINT_NOW=1800000700 bash "$R/.claude/scripts/task_checkpoint.sh" due
expect "100.5 watch of a held task is rc 4" 4 "HELD" env TASK_CHECKPOINT_POLL_SEC=0 TASK_CHECKPOINT_NOW=1800000700 bash "$R/.claude/scripts/task_checkpoint.sh" watch Q-1800000000
expect "100.6 autohold again is refused (already held)" 4 "already held" CKA "$R" autohold TASK-1 Q-1800000000
expect "100.8 recover prints the held row" 0 "held: TASK-1 Q=Q-1800000000 answered=n -> tasks.sh resume TASK-1" TS "$R" recover
# 100.10: status held row (age from held_at, before running) and the brief's first line
HF="$R/.claude/state/task.TASK-1.json"
HAT=$(jq -r .held_at "$HF")
jq '.held_at="2020-01-01T00:00:00Z"' "$HF" > "$HF.t" && mv "$HF.t" "$HF"
expect "100.10 status held row has age and Q" 0 "held: TASK-1 age=" TS "$R" status
expect "100.10 status held row names the question" 0 "Q=Q-1800000000 (" TS "$R" status
expect "100.10 status: held row before running rows" 0 "" bash -c "bash '$R/.claude/scripts/tasks.sh' status | awk '/^held:/{a=NR} /^running/{if(!b)b=NR} END{exit !(a && a<b)}'"
expect "100.10 status stays within 25 lines" 0 "" bash -c "test \$(bash '$R/.claude/scripts/tasks.sh' status | wc -l) -le 25"
jq --arg h "$HAT" '.held_at=$h' "$HF" > "$HF.t" && mv "$HF.t" "$HF"
expect "100.10 brief first line is the held question" 0 "Your turn: answer Q-1800000000 (TASK-1, held " bash -c "TASK_CHECKPOINT_NOW=1800000700 bash '$R/.claude/scripts/task_checkpoint.sh' brief | head -n 1"
expect "100.10 brief held line names the resume" 0 "then tasks.sh resume TASK-1" env TASK_CHECKPOINT_NOW=1800000700 bash "$R/.claude/scripts/task_checkpoint.sh" brief
expect "100.10 brief does not repeat the question" 0 "1" bash -c "TASK_CHECKPOINT_NOW=1800000700 bash '$R/.claude/scripts/task_checkpoint.sh' brief | grep -c 'Your turn: answer Q-1800000000'"
expect "100.8 answer prints the resume line" 0 "then: resume TASK-1" TCP answer Q-1800000000 "yes go"
expect "100.8 recover shows answered=y" 0 "answered=y" TS "$R" recover
expect "100.8 resume clears held_question" 0 "none" bash -c "cd '$R' && bash .claude/scripts/tasks.sh resume TASK-1 >/dev/null; jq -r '.held_question // \"none\"' .claude/state/task.TASK-1.json"

# nothing workable: rc 5, T stays held
fix_ah
bl_edit "$R" 'if i.get("status") == "queued": i["paid"] = True'
commit_all "$R" "all paid"
expect "100.9 autohold with nothing workable is rc 5" 5 "NONE" CKA "$R" autohold TASK-1 Q-1800000000
expect "100.9 rc 5 lists the SKIP rows" 5 "SKIP TASK-" env NOW=1800000600 bash -c "$(declare -f CKA); git -C '$R' reset -q --hard HEAD~1; CKA '$R' autohold TASK-1 Q-1800000000"
fix_ah
bl_edit "$R" 'if i.get("status") == "queued": i["paid"] = True'
commit_all "$R" "all paid"
CKA "$R" autohold TASK-1 Q-1800000000 >/dev/null || true
expect "100.6 the hold stays committed on rc 5" 0 "held on Q-1800000000 (auto)" bash -c "git -C '$R' log -n 1 --format=%s"

# a failing gate undoes the hold
fix_ah
printf '#!/usr/bin/env bash\nexit 1\n' > "$R/.claude/scripts/commit-check.sh"
commit_all "$R" "gate fails"
expect "100.6 a gate FAIL returns rc 1" 1 "hold undone" CKA "$R" autohold TASK-1 Q-1800000000
expect "100.6 a gate FAIL leaves the task unheld" 0 "none" bash -c "jq -r '.status // \"none\"' '$R/.claude/state/task.TASK-1.json'"

# every task held: workflow-check prints a PASS line
multi "$R"
TS "$R" hold TASK-1 --reason "waits on Q" --next "answer Q" >/dev/null
expect "100.9 all held: workflow-check prints PASS" 0 "all held" WC "$R"

# QA-1 edge cases (Nemesis)
python3 - "$R" <<'PY9'
import json, sys
p = sys.argv[1] + "/.claude/state/task.TASK-1.json"
d = json.load(open(p)); d["held_reason"] = ""; json.dump(d, open(p, "w"), indent=2)
PY9
expect "100.1 held task without held_reason fails" 1 "lacks held_reason" WC "$R"
cp "$WORK/t1.json" "$R/.claude/state/task.TASK-1.json"
expect "100.2 commit of an unknown task is still refused" 1 "not an active task" TS "$R" commit TASK-77 msg.txt -- nosuch.txt

# QA-2: end to end ask -> watch -> autohold -> answer -> resume, workflow-check at each step
fix_ah
expect "QA2 e2e: workflow-check PASS after ask" 0 "" WC "$R"
refute "QA2 e2e: no FAIL after ask" "FAIL" WC "$R"
WOUT="$(TASK_CHECKPOINT_POLL_SEC=0 TASK_CHECKPOINT_NOW=1800000700 bash "$R/.claude/scripts/task_checkpoint.sh" watch Q-1800000000 || true)"
RUNL="$(printf '%s\n' "$WOUT" | sed -n 's/^run: tasks.sh //p' | head -n 1)"
if [ "$RUNL" = "autohold TASK-1 Q-1800000000" ]; then ok "QA2 e2e: watch prints the autohold line"; else bad "QA2 e2e: watch prints the autohold line ($RUNL)"; fi
# shellcheck disable=SC2086  # the run line is two words per design
expect "QA2 e2e: autohold from the watch line" 0 "PICKED TASK-5" env NOW=1800000700 bash -c "$(declare -f CKA); CKA '$R' $RUNL"
expect "QA2 e2e: workflow-check rc 0 after autohold" 0 "" WC "$R"
refute "QA2 e2e: no FAIL after autohold" "FAIL" WC "$R"
expect "QA2 e2e: watch of the held task is HELD" 4 "HELD" env TASK_CHECKPOINT_POLL_SEC=0 TASK_CHECKPOINT_NOW=1800000800 bash "$R/.claude/scripts/task_checkpoint.sh" watch Q-1800000000
expect "QA2 e2e: answer names the resume line" 0 "then: resume TASK-1" TCP answer Q-1800000000 "yes"
commit_all "$R" "answered"
# a stale lock (dead pid) on a held task must not block resume
mkdir -p "$GD"
printf '{"pid": 999999, "start": null}' > "$GD/owner.json"
expect "QA2 stale lock: resume of the held task breaks it" 0 "RESUMED" TS "$R" resume TASK-1
expect "QA2 e2e: held_question cleared after resume" 0 "none" bash -c "jq -r '.held_question // \"none\"' '$R/.claude/state/task.TASK-1.json'"
expect "QA2 e2e: workflow-check rc 0 after resume" 0 "" WC "$R"
refute "QA2 e2e: no FAIL after resume" "FAIL" WC "$R"

# F-100-V10: autohold at UNIT_TESTED / VERIFIED needs the gate's Tests: / Verified-by: trailer
v10_set() {  # v10_set STATE SUBKEY JSONOBJ: a task that really is at STATE, with its phase-log entries
  jq --arg s "$1" --arg k "$2" --argjson o "$3" '.state=$s
    | .implementation={status:"completed",files:["a.txt"]}
    | .unit_test={status:"passed",command:"t",result:"ok"}
    | (if $s=="VERIFIED" then .verification={status:"passed",evidence:"e"} | .security={status:"not_applicable",result:"fixture"} else . end)
    | .[$k]=($o + (if $k=="verification" then {evidence:"e"} else {} end))' \
    "$R/.claude/state/task.TASK-1.json" > "$WORK/v10.json" && cat "$WORK/v10.json" > "$R/.claude/state/task.TASK-1.json"
  printf '\n## UNIT_TESTED - TASK-1 - 2026-01-01T00:00:00Z\n\n## VERIFIED - TASK-1 - 2026-01-01T00:00:01Z\n' >> "$R/.claude/state/phase-log.md"
}
for ST_ in UNIT_TESTED VERIFIED; do
  case "$ST_" in UNIT_TESTED) TK=Tests; SUB=unit_test;; *) TK=Verified-by; SUB=verification;; esac
  fix_ah
  v10_set "$ST_" "$SUB" '{"status":"passed","command":"run x\ty","result":"ok 3/0"}'
  commit_all "$R" "state $ST_"
  expect "F-100-V10 $ST_: autohold rc 0" 0 "PICKED TASK-5" CKA "$R" autohold TASK-1 Q-1800000000
  expect "F-100-V10 $ST_: hold commit carries $TK" 0 "$TK: run x y -> ok 3/0" bash -c "git -C '$R' log --format=%B | grep '^$TK:' | head -n 1"
  expect "F-100-V10 $ST_: hold and pick commits in the log" 0 "TASK-5 picked" bash -c "git -C '$R' log --format=%s -n 3"
  expect "F-100-V10 $ST_: tree clean" 0 "" bash -c "test -z \"\$(git -C '$R' status --porcelain)\""
done

# held + active at max_active 2: a held task does not use a slot
multi "$R"
TS "$R" hold TASK-1 --reason "waits" --next "answer" >/dev/null
commit_all "$R" "hold1"
expect "QA2 max_active 2: pick beside held and one active" 0 "PICKED: TASK-5" env WORKFLOW_MAX_ACTIVE=2 bash -c "$(declare -f BL); BL '$R' pick TASK-5 --scope work/TASK-5/"
commit_all "$R" "pick5"
expect "QA2 max_active 2: a third non-held pick still fits" 0 "PICKED: TASK-4" env WORKFLOW_MAX_ACTIVE=2 bash -c "$(declare -f BL); BL '$R' pick TASK-4 --scope work/TASK-4/"
commit_all "$R" "pick4"
expect "QA2 max_active 2: a fourth pick is refused" 1 "max_active=2" env WORKFLOW_MAX_ACTIVE=2 bash -c "$(declare -f BL); BL '$R' pick TASK-3 --scope work/TASK-3/"

echo "SUMMARY(multi_task): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

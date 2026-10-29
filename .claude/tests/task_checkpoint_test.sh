#!/usr/bin/env bash
# Regression test for the pending-question record (REQ-0038, REQ-0060 96.8): ask / answer /
# due / brief, the multi-mode active check and the `work on:` lines, plus the backlog.sh
# pick/complete rules after the checkpointed status was dropped.
# Every case works in a throwaway git repo holding a copy of the kit (the real state is
# never touched); a fake clock (TASK_CHECKPOINT_NOW) stands in for the 10-minute wait.
# Run: bash .claude/tests/task_checkpoint_test.sh
set -Eeuo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export GIT_CONFIG_NOSYSTEM=1

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
# expect_not <name> <cmd...>: the output must be empty
expect_empty() {
  local name="$1" out; shift
  out="$("$@" 2>&1 || true)"
  if [ -z "$out" ]; then ok "$name"; else bad "$name (output: $out)"; fi
}
# check <name> <dir> <file> <python expr over d>: the expression must be true
check() {
  local name="$1" dir="$2" file="$3" expr="$4"
  if python3 - "$dir/$file" "$expr" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if eval(sys.argv[2]) else 1)
PY
  then ok "$name"; else bad "$name ($file: $expr)"; fi
}

fresh() {
  rm -rf "$1"; mkdir -p "$1"
  cp -r "$KIT" "$1/.claude"
  find "$1/.claude" -name __pycache__ -prune -exec rm -rf {} +
  rm -rf "$1/.claude/tests" "$1/.claude/state"; mkdir -p "$1/.claude/state"
  printf '{"max_active": 2}\n' > "$1/.claude/workflow.json"  # fixture is a multi-task kit whatever the live config
  git -C "$1" init -q
  git -C "$1" config user.email t@example.invalid
  git -C "$1" config user.name test
}
commit() { git -C "$1" add -A && git -C "$1" commit -q -m "${2:-step}" ; }

# fx <dir> [state]: TASK-080 mid-flight (default IMPLEMENTING) with notes, picked_at and
# the crosscheck fields, TASK-081 and TASK-082 queued, one handoff, all committed.
fx() {
  local d="$1" st="${2:-IMPLEMENTING}"
  fresh "$d"
  python3 - "$d" "$st" <<'PY'
import json, os, sys
d, st = sys.argv[1:3]
SEQ = ["TODO", "DESIGN", "IMPLEMENTING", "UNIT_TESTED", "VERIFIED", "DONE"]
i = SEQ.index(st)
os.makedirs(f"{d}/docs/design", exist_ok=True)
open(f"{d}/docs/design/phase-80-x.md", "w").write("# d\n\n## Plan modes\nboth\n")
os.makedirs(f"{d}/docs/req/raw", exist_ok=True)
for r in ("RAW-00476", "RAW-00477", "RAW-00479", "RAW-00480"):
    open(f"{d}/docs/req/raw/{r}.md", "w").write("raw\n")
os.makedirs(f"{d}/work/TASK-080/handoff", exist_ok=True)
open(f"{d}/work/TASK-080/handoff/code.md", "w").write("PROGRESS: IN_PROGRESS\nSKILLS: x\n")
t = {"task_id": "TASK-080", "title": "t", "state": st, "requirement": "r",
     "acceptance_criteria": ["a"],
     "design": {"status": "completed", "summary": "s", "path": "docs/design/phase-80-x.md"},
     "implementation": {"status": "pending", "files": ["x.sh"]},
     "unit_test": {"status": "pending", "command": "", "result": ""},
     "security": {"status": "pending", "result": ""},
     "verification": {"status": "pending", "evidence": []},
     "report": {"status": "pending", "path": ""},
     "crosscheck_required": True, "roles": {"coder": "work/TASK-080/handoff/code.md"},
     "user_notes": [{"raw": "RAW-00476", "note": "n1", "at": "2026-10-08T00:00:00Z"}],
     "picked_at": "2026-10-08T00:00:00Z",
     "updated_at": "2099-01-01T00:00:00Z", "updated_by": "test", "next": "finish 80.2"}
json.dump(t, open(f"{d}/.claude/state/task.json", "w"), indent=2)
log = "# Phase Log\n"
for s in SEQ[1:i + 1]:
    log += f"\n## {s} - TASK-080 - 2099-01-01T00:00:00Z\n"
open(f"{d}/.claude/state/phase-log.md", "w").write(log)
items = [{"task_id": "TASK-080", "title": "t", "status": "active",
          "user_notes": [{"raw": "RAW-00477", "note": "n2", "at": "2026-10-08T00:00:00Z"}]},
         {"task_id": "TASK-081", "title": "u", "status": "queued", "requirement": "r2"},
         {"task_id": "TASK-082", "title": "v", "status": "queued"}]
json.dump(items, open(f"{d}/.claude/state/backlog.json", "w"), indent=2)
PY
  rm -f "$d/.claude/state/pending.json"
  rm -rf "$d/.claude/state/task-checkpoints"
  commit "$d" init
}

TC() { bash "$1/.claude/scripts/task_checkpoint.sh" "${@:2}"; }
BL() { bash "$1/.claude/scripts/backlog.sh" "${@:2}"; }
WC() { bash "$1/.claude/scripts/workflow-check.sh"; }
ST() { bash "$1/.claude/scripts/status.sh"; }
TS() { bash "$1/.claude/scripts/team-status.sh"; }
R="$WORK/r"
T0=1800000000


# --- T6 pending questions and due (legacy mode) ----------------------------------
fx "$R"
export TASK_CHECKPOINT_NOW=$T0
expect "T6 ask records a question" 0 "ASKED: Q-$T0 (TASK-080)" TC "$R" ask TASK-080 --question "A or B?" --recommend "A" --kind paid
check "T6 pending.json entry" "$R" .claude/state/pending.json "d[0]['id']=='Q-$T0' and d[0]['task_id']=='TASK-080' and d[0]['recommendation']=='A' and d[0]['asked_at'].endswith('Z')"
expect "T6 ask refuses a bad task id" 2 "bad task id" TC "$R" ask ../x --question "q?" --recommend r --kind paid
expect "T6 ask refuses a URL" 2 "URL or a secret" TC "$R" ask TASK-080 --question "see http://x.y" --recommend r --kind paid
expect "T6 legacy ask does not need an active list" 0 "ASKED" TC "$R" ask TASK-099 --question "other?" --recommend r --kind block
commit "$R" ask
export TASK_CHECKPOINT_NOW=$((T0 + 540))
expect "T6 9 minutes is not due" 0 "" TC "$R" due
export TASK_CHECKPOINT_NOW=$((T0 + 600))
expect "T6 10 minutes is due" 3 "DUE TASK-080 Q-$T0 age=10m" TC "$R" due
expect "T6 legacy due has no work-on line" 0 "" bash -c "! bash '$R/.claude/scripts/task_checkpoint.sh' due | grep -q 'work on:'"
expect "T6 brief reports it, rc 0" 0 "DUE TASK-080 Q-$T0" TC "$R" brief
expect "T6 brief asks for the answer" 0 "Your turn: answer Q-$T0 (TASK-080)" TC "$R" brief
TASK_CHECKPOINT_TIMEOUT_MIN=15 expect "T6 timeout is configurable" 0 "" TC "$R" due
TASK_CHECKPOINT_TIMEOUT_MIN=0 expect "T6 a bad timeout is a usage error" 2 "TASK_CHECKPOINT_TIMEOUT_MIN" TC "$R" due
TASK_CHECKPOINT_TIMEOUT_MIN=abc expect "T6 brief is rc 0 even with a bad timeout" 0 "" TC "$R" brief
export TASK_CHECKPOINT_NOW=$((T0 - 60))
expect "T6 a future asked_at is not due" 0 "" TC "$R" due
export TASK_CHECKPOINT_NOW=$((T0 + 600))
expect "T6 due is read-only" 0 "" bash -c "cd '$R' && test -z \"\$(git status --porcelain)\""
expect "T6 answer rejects a bad id" 2 "bad question id" TC "$R" answer ../x yes
expect "T6 answer rejects an unknown id" 1 "no pending question" TC "$R" answer Q-1 yes
expect "T6 answer works" 0 "ANSWERED: Q-$T0" TC "$R" answer "Q-$T0" "take A"
expect "T6 answer twice is refused" 1 "already answered" TC "$R" answer "Q-$T0" "again"
expect "T6 an answered question is not due" 0 "" bash -c "! bash '$R/.claude/scripts/task_checkpoint.sh' due | grep -q 'Q-$T0 '"
for c in save load list; do
  expect "T6 dropped command $c is a usage error" 2 "Usage" TC "$R" "$c" TASK-080
done

# --- T7 multi mode: ask needs an active task, due/brief name the other tasks -------
fx "$R"
bash "$R/.claude/scripts/tasks.sh" migrate >/dev/null
commit "$R" migrate
BL "$R" pick TASK-081 --scope "zz/*" >/dev/null
commit "$R" multi
export TASK_CHECKPOINT_NOW=$T0
expect "T7 ask on an unknown task is refused in multi mode" 1 "not an active task" TC "$R" ask TASK-082 --question "q?" --recommend r --kind paid
expect "T7 ask on an active task works" 0 "ASKED: Q-$T0 (TASK-080)" TC "$R" ask TASK-080 --question "A or B?" --recommend A --kind paid
commit "$R" ask
export TASK_CHECKPOINT_NOW=$((T0 + 540))
expect "T7 9 minutes is not due" 0 "" TC "$R" due
export TASK_CHECKPOINT_NOW=$((T0 + 600))
expect "T7 10 minutes is due" 3 "DUE TASK-080 Q-$T0 age=10m" TC "$R" due
expect "T7 due names the other active task" 3 "work on: TASK-081 (TODO;" TC "$R" due
expect "T7 brief names it too, rc 0" 0 "work on: TASK-081" TC "$R" brief
expect "T7 due does not name the waiting task" 0 "" bash -c "! bash '$R/.claude/scripts/task_checkpoint.sh' due | grep -q 'work on: TASK-080'"
expect "T7 team-status prints the global lines once" 0 "" bash -c "[ \"\$(bash '$R/.claude/scripts/team-status.sh' | grep -c '^PENDING')\" -le 1 ]"
unset TASK_CHECKPOINT_NOW

# --- T10 kind and watch (100.4, 100.5) ----------------------------------------------------
fx "$R"
export TASK_CHECKPOINT_NOW=$T0
expect "T10 ask without --kind is refused" 2 "not a user-only question" TC "$R" ask TASK-080 --question "q?" --recommend r
expect "T10 ask with another kind is refused" 2 "RAW-00511" TC "$R" ask TASK-080 --question "q?" --recommend r --kind other
expect "T10 ask stores the kind" 0 "ASKED" TC "$R" ask TASK-080 --question "q?" --recommend r --kind permission
check "T10 entry has kind" "$R" .claude/state/pending.json "d[0]['kind']=='permission'"
export TASK_CHECKPOINT_POLL_SEC=0
expect "T10 watch before the timeout is rc 1" 1 "WAITING" TC "$R" watch "Q-$T0"
expect "T10 watch bad id is rc 2" 2 "bad question id" TC "$R" watch ../x
expect "T10 watch unknown id is rc 4" 4 "GONE" TC "$R" watch Q-5
TASK_CHECKPOINT_POLL_SEC=999 expect "T10 watch bad poll is rc 2" 2 "TASK_CHECKPOINT_POLL_SEC" TC "$R" watch "Q-$T0"
export TASK_CHECKPOINT_NOW=$((T0 + 600))
expect "T10 watch past the timeout is rc 3 with the run line" 3 "run: tasks.sh autohold TASK-080 Q-$T0" TC "$R" watch "Q-$T0"
expect "T10 answer then watch is rc 0" 0 "ANSWERED" bash -c "bash '$R/.claude/scripts/task_checkpoint.sh' answer 'Q-$T0' ok >/dev/null; bash '$R/.claude/scripts/task_checkpoint.sh' watch 'Q-$T0'"
unset TASK_CHECKPOINT_NOW TASK_CHECKPOINT_POLL_SEC

# --- T8 backlog.sh after the checkpointed status was dropped -------------------------
fx "$R"
expect "T8 pick over an active backlog item is refused" 1 "already active" BL "$R" pick TASK-081
expect "T8 notes summary lists queued items only" 0 "" bash -c "! bash '$R/.claude/scripts/backlog.sh' notes | grep -q TASK-080"
# an interrupted task: its backlog item is queued again (no checkpointed status any more)
python3 - "$R/.claude/state/backlog.json" <<'PY2'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d[0]["status"] = "queued"
d[0]["user_notes"] = [{"raw": "RAW-00477", "note": "n2", "at": "2026-10-08T00:00:00Z"}, {"raw": "RAW-00476", "note": "n1", "at": "2026-10-08T00:00:00Z"}]
json.dump(d, open(p, "w"), indent=2)
PY2
commit "$R" requeue
expect "T8 pick of a queued task over a mid-flight one is refused" 1 "mid-flight" BL "$R" pick TASK-081
expect "T8 notes summary lists the queued item" 0 "TASK-080=2" BL "$R" notes
expect "T8 workflow-check passes" 0 "PASS: workflow state" WC "$R"
n=$( (grep -c "checkpointed\|task-checkpoints" "$KIT/scripts/workflow-check.sh" "$KIT/scripts/status.sh" "$KIT/scripts/backlog.sh" || true) | awk -F: '{s+=$2} END{print s+0}')
if [ "$n" = 0 ]; then ok "T8 no checkpointed leftovers in the readers"; else bad "T8 checkpointed leftovers ($n)"; fi

# --- T9 naming: disjoint from the pipeline checkpoints ----------------------------
n=$(grep -c PIPELINE_CHECKPOINTS "$KIT/scripts/task_checkpoint.sh" || true)
if [ "$n" = 0 ]; then ok "T9 script never mentions PIPELINE_CHECKPOINTS"; else bad "T9 PIPELINE_CHECKPOINTS in task_checkpoint.sh"; fi

echo "Summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]

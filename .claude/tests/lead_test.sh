#!/usr/bin/env bash
# Regression test for locked state writes and crash recovery (REQ-0061, phase 97, slice 1):
# 97.12 owner-protocol state lock (L14-L21) and 97.13 `tasks.sh recover` (L24, L25). Every case
# runs in a throwaway git repo holding a copy of the kit; the real state is never touched.
# Run: bash .claude/tests/lead_test.sh      (KIT_DIR=<kit> tests another copy, the bite check)
# shellcheck disable=SC2015  # `[ test ] && ok || bad`: ok() always returns 0, so bad never double-fires
set -Eeuo pipefail
unset TASK CTXGUARD_TASK CTXGUARD_ROLE || true
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
# check <name> <cmd...>: passes when the command exits 0
check() { local name="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$name"; else bad "$name"; fi; }

fresh() {
  rm -rf "$1"; mkdir -p "$1"
  cp -r "$KIT" "$1/.claude"
  find "$1/.claude" -name __pycache__ -prune -exec rm -rf {} +
  rm -rf "$1/.claude/tests" "$1/.claude/state"; mkdir -p "$1/.claude/state"
  printf '{"max_active": 2}\n' > "$1/.claude/workflow.json"  # fixture is a multi-task kit whatever the live config
  rm -f "$1"/.claude/agent_setup_*.jsonl  # git-ignored live runtime rows: keep the fixture isolated
  git -C "$1" init -q
  git -C "$1" config user.email t@example.invalid
  git -C "$1" config user.name test
}
commit_all() { git -C "$1" add -A && git -C "$1" commit -qm "${2:-fixture}" --no-verify; }

# legacy <dir>: single task.json for TASK-1 plus queued TASK-2..4 and RAW-01001..01020, committed.
legacy() {
  local d="$1"
  fresh "$d"
  python3 - "$d" <<'PY'
import json, os, sys
d = sys.argv[1]
for sub in ("docs/design", "docs/report", "src", "docs/req/raw"):
    os.makedirs(f"{d}/{sub}", exist_ok=True)
for n in range(1001, 1021):
    open(f"{d}/docs/req/raw/RAW-0{n}.md", "w").write("raw\n")
open(f"{d}/docs/req/raw/RAW-00001.md", "w").write("raw\n")
for n in "abc":
    open(f"{d}/src/{n}.py", "w").write("x = 1\n")
open(f"{d}/docs/design/phase-1-one.md", "w").write("design\n")
task = {"task_id": "TASK-1", "title": "one", "state": "IMPLEMENTING", "requirement": "r",
        "acceptance_criteria": ["a"],
        "design": {"status": "completed", "summary": "s", "path": "docs/design/phase-1-one.md"},
        "implementation": {"status": "pending", "files": ["src/a.py"]},
        "unit_test": {"status": "pending", "command": "", "result": ""},
        "security": {"status": "pending", "result": ""},
        "verification": {"status": "pending", "evidence": []},
        "report": {"status": "pending", "path": ""},
        "updated_at": "2026-01-01T00:00:00Z", "updated_by": "test", "next": "finish the slice"}
json.dump(task, open(f"{d}/.claude/state/task.json", "w"), indent=2)
items = [{"task_id": "TASK-1", "title": "one", "status": "active", "priority": "normal", "scope": ["src/a.py"]}]
for i, f in ((2, "b"), (3, "c")):
    items.append({"task_id": f"TASK-{i}", "title": f"t{i}", "status": "queued",
                  "priority": "normal", "scope": [f"src/{f}.py"]})
json.dump(items, open(f"{d}/.claude/state/backlog.json", "w"), indent=2)
open(f"{d}/.claude/state/phase-log.md", "w").write("# Phase Log\n\n## DESIGN - TASK-1 - 2026-01-01T00:00:00Z\n")
PY
  commit_all "$d" legacy
}
# multi <dir>: legacy + migrate, committed
multi() { legacy "$1"; "$1/.claude/scripts/tasks.sh" migrate >/dev/null; commit_all "$1" multi; }

# lockdir <dir> <pid> <start|null> [age-seconds]: a held lock with an owner.json
lockdir() {
  python3 - "$1/.git/${5:-tasks-state.lock}" "$2" "$3" "${4:-0}" <<'PY'
import json, os, sys, time
p, pid, start, age = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
os.makedirs(p)
json.dump({"pid": pid, "start": None if start == "null" else int(start), "task": None,
           "role": "main", "ts": "2026-01-01T00:00:00Z"}, open(p + "/owner.json", "w"))
if age:
    t = time.time() - age
    os.utime(p, (t, t))
PY
}
# procstart <pid>: field 22 of /proc/<pid>/stat, or "null"
procstart() {
  python3 - "$1" <<'PY'
import sys
try:
    print(int(open("/proc/%s/stat" % sys.argv[1]).read().rsplit(")", 1)[1].split()[19]))
except (OSError, ValueError, IndexError):
    print("null")
PY
}
# age <path> <seconds>: set mtime into the past
age() { python3 -c 'import os,sys,time; t=time.time()-int(sys.argv[2]); os.utime(sys.argv[1], (t, t))' "$1" "$2"; }
# jq-free JSON probes
notes() { python3 -c 'import json,sys; print(len([i for i in json.load(open(sys.argv[1])) if i["task_id"]==sys.argv[2]][0].get("user_notes", [])))' "$1/.claude/state/backlog.json" "$2"; }
decisions() { python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1])).get("decisions", [])))' "$1"; }
reasons() { python3 -c 'import json,sys
for l in open(sys.argv[1]): print(json.loads(l)["reason"])' "$1/.git/tasks-locks.log" 2>/dev/null || true; }
litter() { find "$1/.claude/state" "$1/.git" -maxdepth 1 \( -name '*.tmp*' -o -name '*.broken.*' \) 2>/dev/null | head -n 5; }

HAVE_PROC=0; [ -r /proc/self/stat ] && HAVE_PROC=1

# ---- L14: 20 concurrent notes, none lost
D="$WORK/l14"; legacy "$D"
pids=()
for i in $(seq 1001 1020); do
  "$D/.claude/scripts/backlog.sh" note TASK-2 "RAW-0$i" "note $i" >/dev/null 2>&1 & pids+=("$!")
done
for p in "${pids[@]}"; do wait "$p" || true; done
[ "$(notes "$D" TASK-2)" = 20 ] && ok "L14 20 concurrent notes -> 20 notes" || bad "L14 notes=$(notes "$D" TASK-2)"
check "L14 backlog.json is valid JSON" python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$D/.claude/state/backlog.json"
[ -z "$(litter "$D")" ] && ok "L18 no tmp or .broken. left after 20 writers" || bad "L18 litter: $(litter "$D")"

# ---- L15: a live owner holds the lock: note/sync/migrate FAIL "holds", bytes unchanged
D="$WORK/l15"; legacy "$D"
lockdir "$D" "$$" "$(procstart "$$")"
before="$(cksum "$D"/.claude/state/*.json | tr '\n' ' ')"
export TASKS_LOCK_WAIT=0.5
expect "L15 note fails while held" 1 "holds" "$D/.claude/scripts/backlog.sh" note TASK-2 RAW-01001 "n"
expect "L15 sync fails while held" 1 "holds" "$D/.claude/scripts/tasks.sh" sync
expect "L15 migrate fails while held" 1 "holds" "$D/.claude/scripts/tasks.sh" migrate
unset TASKS_LOCK_WAIT
after="$(cksum "$D"/.claude/state/*.json | tr '\n' ' ')"
[ "$before" = "$after" ] && ok "L15 state bytes unchanged" || bad "L15 state changed while the lock was held"

# ---- L17: concurrent question --decide writers on one task, none lost
D="$WORK/l17"; multi "$D"
pids=()
for i in 1 2 3 4 5 6 7 8; do
  "$D/.claude/scripts/tasks.sh" question TASK-1 --decide "d$i" --reason "r$i" >/dev/null 2>&1 & pids+=("$!")
done
for p in "${pids[@]}"; do wait "$p" || true; done
[ "$(decisions "$D/.claude/state/task.TASK-1.json")" = 8 ] && ok "L17 8 concurrent decisions kept" \
  || bad "L17 decisions=$(decisions "$D/.claude/state/task.TASK-1.json")"
[ -z "$(litter "$D")" ] && ok "L18 no litter after concurrent task writers" || bad "L18 litter: $(litter "$D")"

# ---- L19: killed holder, a writer goes on within the wait and the break is logged
D="$WORK/l19"; multi "$D"
TASKS_ROOT="$D" python3 -c '
import os, sys, time
sys.path.insert(0, sys.argv[1] + "/.claude/scripts")
import _tasks
lk = _tasks.locked(); lk.__enter__()
d = _tasks.load("TASK-1"); d.setdefault("decisions", []).append({"text": "holder"})
_tasks.write_json(_tasks.task_path("TASK-1"), d)
open(sys.argv[1] + "/ready", "w").close()
time.sleep(120)' "$D" &
hpid=$!
for _ in $(seq 1 100); do [ -f "$D/ready" ] && break; sleep 0.1; done
kill -9 "$hpid" 2>/dev/null || true; wait "$hpid" 2>/dev/null || true
t0=$SECONDS
TASKS_LOCK_WAIT=5 "$D/.claude/scripts/tasks.sh" question TASK-1 --decide writer --reason r >/dev/null 2>&1 \
  && ok "L19 writer succeeds after the holder was killed" || bad "L19 writer failed"
[ $((SECONDS - t0)) -lt 5 ] && ok "L19 writer was quick (<5 s, not the 600 s limit)" || bad "L19 writer waited $((SECONDS - t0)) s"
[ "$(decisions "$D/.claude/state/task.TASK-1.json")" = 2 ] && ok "L19 both updates present" || bad "L19 decisions lost"
reasons "$D" | grep -qx pid_gone && ok "L19 tasks-locks.log reason pid_gone" || bad "L19 no pid_gone row"
expect "L19 status shows lock broken" 0 "lock broken:" "$D/.claude/scripts/tasks.sh" status

# ---- L20: pid reuse
if [ "$HAVE_PROC" = 1 ]; then
  D="$WORK/l20"; legacy "$D"
  lockdir "$D" "$$" 1
  TASKS_LOCK_WAIT=5 expect "L20 wrong start breaks the lock" 0 "NOTED" "$D/.claude/scripts/backlog.sh" note TASK-2 RAW-01001 n
  reasons "$D" | grep -qx pid_reused && ok "L20 reason pid_reused" || bad "L20 no pid_reused row"
  D="$WORK/l20b"; legacy "$D"
  lockdir "$D" "$$" "$(procstart "$$")"
  TASKS_LOCK_WAIT=0.5 expect "L20 right start, young: waits then fails" 1 "holds" "$D/.claude/scripts/backlog.sh" note TASK-2 RAW-01001 n
else
  echo "SKIP: L20 needs /proc"
fi

# ---- L21: a live owner older than 600 s is broken once, two waiters keep both writes
D="$WORK/l21"; legacy "$D"
lockdir "$D" "$$" "$(procstart "$$")" 601
pids=()
for i in 1001 1002; do
  TASKS_LOCK_WAIT=10 "$D/.claude/scripts/backlog.sh" note TASK-2 "RAW-0$i" "n$i" >/dev/null 2>&1 & pids+=("$!")
done
for p in "${pids[@]}"; do wait "$p" || true; done
[ "$(notes "$D" TASK-2)" = 2 ] && ok "L21 both waiters wrote" || bad "L21 notes=$(notes "$D" TASK-2)"
[ "$(reasons "$D" | grep -cx stale)" = 1 ] && ok "L21 one stale break logged" || bad "L21 stale rows=$(reasons "$D" | grep -cx stale)"

# ---- L24: crash recovery
D="$WORK/l24"; multi "$D"
sleep 0 & dead=$!; wait "$dead" || true
lockdir "$D" "$dead" 1
echo junk > "$D/.claude/state/x.tmp123"; age "$D/.claude/state/x.tmp123" 120
python3 - "$D/.claude/state/task.TASK-1.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); d["next"] = "resume me"
json.dump(d, open(sys.argv[1], "w"), indent=2)
PY
out="$("$D/.claude/scripts/tasks.sh" recover 2>&1)" || true
printf '%s' "$out" | grep -qF "Recovery: 1 locks broken, 1 tmp removed, 0 agents ended" && ok "L24 recover counts" || { bad "L24 recover counts"; printf '%s\n' "$out" | head -n 6; }
printf '%s' "$out" | grep -qF "TASK-1 state=IMPLEMENTING next=resume me dirty=1" && ok "L24 resume line" || bad "L24 resume line"
[ ! -e "$D/.git/tasks-state.lock" ] && [ ! -e "$D/.claude/state/x.tmp123" ] && ok "L24 lock and tmp gone" || bad "L24 lock or tmp left"
expect "L24 second run is clean" 0 "Recovery: clean" "$D/.claude/scripts/tasks.sh" recover
expect "L24 note works after recover" 0 "NOTED" "$D/.claude/scripts/backlog.sh" note TASK-2 RAW-00001 n
commit_all "$D" after-note
expect "L24 pick works after recover" 0 "PICKED" "$D/.claude/scripts/backlog.sh" pick TASK-2

# ---- L25: a live lock with the current pid and start is kept
D="$WORK/l25"; multi "$D"
lockdir "$D" "$$" "$(procstart "$$")"
TASKS_LOCK_WAIT=0.5 expect "L25 recover keeps a live lock (waits, does not break)" 1 "holds" "$D/.claude/scripts/tasks.sh" recover
[ -d "$D/.git/tasks-state.lock" ] && ok "L25 lock dir kept" || bad "L25 live lock was removed"

# ---- slice 2: lead, set, checkpoint, commit, status rows, recover step 3 (97.4, 97.5, 97.7, 97.13)
# calls_row <file> <tool> <sid> <agent> <task> <age-seconds>
calls_row() {
  python3 - "$@" <<'PY'
import json, sys, time
f, tool, sid, agent, task, age = sys.argv[1:7]
row = {"ts": int(time.time()) - int(age), "tool": tool, "sid": sid, "agent": agent, "role": agent}
if task != "-":
    row["task"] = task
open(f, "a").write(json.dumps(row) + "\n")
PY
}
jget() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))' "$1" "$2"; }

# L8 (tasks.sh part) + L9: lead generations, refusal at gen 3, live lead refused
D="$WORK/l8"; multi "$D"; T1="$D/.claude/state/task.TASK-1.json"; export TASKS_CALLS_LOG="$D/calls.jsonl"; : > "$TASKS_CALLS_LOG"
expect "L8 lead prints the brief with show first" 0 "tasks.sh show TASK-1" "$D/.claude/scripts/tasks.sh" lead TASK-1
[ "$(jget "$T1" lead_gen)" = 1 ] && ok "L8 lead_gen 1" || bad "L8 lead_gen=$(jget "$T1" lead_gen)"
"$D/.claude/scripts/tasks.sh" lead TASK-1 >/dev/null 2>&1; "$D/.claude/scripts/tasks.sh" lead TASK-1 >/dev/null 2>&1
[ "$(jget "$T1" lead_gen)" = 3 ] && ok "L8 lead_gen grows to 3" || bad "L8 lead_gen=$(jget "$T1" lead_gen)"
before="$(cksum "$T1")"
expect "L8 gen 3 refused as stuck" 1 "stuck" "$D/.claude/scripts/tasks.sh" lead TASK-1
[ "$before" = "$(cksum "$T1")" ] && ok "L8 refusal changes no state" || bad "L8 state changed on refusal"
expect "L8 queued task refused" 1 "FAIL" "$D/.claude/scripts/tasks.sh" lead TASK-2
expect "L8 role session refused" 1 "FAIL" env CTXGUARD_ROLE=coder "$D/.claude/scripts/tasks.sh" lead TASK-1

D="$WORK/l9"; multi "$D"; T1="$D/.claude/state/task.TASK-1.json"; export TASKS_CALLS_LOG="$D/calls.jsonl"; : > "$TASKS_CALLS_LOG"
calls_row "$TASKS_CALLS_LOG" SubagentStart s1 lead TASK-1 60
expect "L9 live lead refused" 1 "live lead" "$D/.claude/scripts/tasks.sh" lead TASK-1
calls_row "$TASKS_CALLS_LOG" SubagentStop s1 lead TASK-1 30
expect "L9 stopped lead accepted" 0 "tasks.sh show TASK-1" "$D/.claude/scripts/tasks.sh" lead TASK-1

# L12 / L23: status rows, quit lead replaced
D="$WORK/l23"; multi "$D"; export TASKS_CALLS_LOG="$D/calls.jsonl"; : > "$TASKS_CALLS_LOG"
"$D/.claude/scripts/tasks.sh" lead TASK-1 >/dev/null
calls_row "$TASKS_CALLS_LOG" SubagentStart s1 lead TASK-1 1500
calls_row "$TASKS_CALLS_LOG" PreToolUse s1 lead TASK-1 1200
expect "L23 status lead row quit" 0 "lead: TASK-1 gen1 quit idle=20m" "$D/.claude/scripts/tasks.sh" status
expect "L23 status quit row" 0 "quit: TASK-1" "$D/.claude/scripts/tasks.sh" status
expect "L23 quit lead replaced" 0 "tasks.sh show TASK-1" "$D/.claude/scripts/tasks.sh" lead TASK-1
[ "$(jget "$D/.claude/state/task.TASK-1.json" lead_gen)" = 2 ] && ok "L23 gen 2" || bad "L23 gen"
D="$WORK/l12"; multi "$D"; export TASKS_CALLS_LOG="$D/calls.jsonl"; : > "$TASKS_CALLS_LOG"
"$D/.claude/scripts/tasks.sh" lead TASK-1 >/dev/null
calls_row "$TASKS_CALLS_LOG" SubagentStart s1 lead TASK-1 120
expect "L12 live lead row" 0 "lead: TASK-1 gen1 live idle=2m" "$D/.claude/scripts/tasks.sh" status

# L13: checkpoint, a replacement resumes from it
D="$WORK/l13"; multi "$D"; export TASKS_CALLS_LOG="$D/calls.jsonl"; : > "$TASKS_CALLS_LOG"
expect "L13 checkpoint done" 0 "" "$D/.claude/scripts/tasks.sh" checkpoint TASK-1 --done "item 1.1 coded"
expect "L13 checkpoint next" 0 "" "$D/.claude/scripts/tasks.sh" checkpoint TASK-1 --next "write item 1.2 tests"
expect "L13 show prints the checkpoint next" 0 "write item 1.2 tests" "$D/.claude/scripts/tasks.sh" show TASK-1
expect "L13 replacement brief" 0 "tasks.sh show TASK-1" "$D/.claude/scripts/tasks.sh" lead TASK-1
grep -qF "write item 1.2 tests" "$D/.claude/state/task.TASK-1.json" && ok "L13 next kept" || bad "L13 next lost"
grep -qF "item 1.1 coded" "$D/.claude/state/task.TASK-1.json" && ok "L13 done item kept" || bad "L13 done item lost"

# set --merge: whitelist
mkdir -p "$D/work/TASK-1"
printf '{"implementation": {"status": "completed"}}\n' > "$D/work/TASK-1/m.json"
expect "L10 merge whitelisted key" 0 "" "$D/.claude/scripts/tasks.sh" set TASK-1 --merge work/TASK-1/m.json
printf '{"state": "DONE"}\n' > "$D/work/TASK-1/bad.json"
expect "L10 merge of state refused" 1 "FAIL" "$D/.claude/scripts/tasks.sh" set TASK-1 --merge work/TASK-1/bad.json
[ "$(jget "$D/.claude/state/task.TASK-1.json" state)" = IMPLEMENTING ] && ok "L10 state unchanged" || bad "L10 state changed"
# L30 (F-97-5): set --state moves one step forward or rolls back to IMPLEMENTING, nothing else
expect "L30 skip two states refused" 1 "FAIL" "$D/.claude/scripts/tasks.sh" set TASK-1 --state VERIFIED
expect "L30 unknown state refused" 1 "FAIL" "$D/.claude/scripts/tasks.sh" set TASK-1 --state BOGUS
expect "L30 one step forward" 0 "IMPLEMENTING -> UNIT_TESTED" "$D/.claude/scripts/tasks.sh" set TASK-1 --state UNIT_TESTED
[ "$(jget "$D/.claude/state/task.TASK-1.json" state)" = UNIT_TESTED ] && ok "L30 state moved" || bad "L30 state not moved"
expect "L30 backwards to DESIGN refused" 1 "FAIL" "$D/.claude/scripts/tasks.sh" set TASK-1 --state DESIGN
expect "L30 rollback to IMPLEMENTING" 0 "UNIT_TESTED -> IMPLEMENTING" "$D/.claude/scripts/tasks.sh" set TASK-1 --state IMPLEMENTING
printf '{"next": "x"}\n' > "$D/m2.json"
expect "L10 merge file outside work/T refused" 1 "FAIL" "$D/.claude/scripts/tasks.sh" set TASK-1 --merge "$D/m2.json"

# L10: commit refusals
printf 'msg\n\nTask: TASK-2\n' > "$D/work/TASK-1/msg2"; printf '## IMPLEMENTING - TASK-1 - 2026-01-02T00:00:00Z\nAction: x\n' > "$D/work/TASK-1/entry"
printf 'wip(x): TASK-1 slice\n\nTask: TASK-1\nState: IMPLEMENTING\n' > "$D/work/TASK-1/msg1"
expect "L10 trailer for another task refused" 1 "FAIL" "$D/.claude/scripts/tasks.sh" commit TASK-1 work/TASK-1/msg2 --log work/TASK-1/entry -- src/a.py
expect "L10 foreign path refused" 1 "FAIL" "$D/.claude/scripts/tasks.sh" commit TASK-1 work/TASK-1/msg1 --log work/TASK-1/entry -- src/b.py
printf 'bad entry\n' > "$D/work/TASK-1/entry2"
expect "L10 bad log entry refused" 1 "FAIL" "$D/.claude/scripts/tasks.sh" commit TASK-1 work/TASK-1/msg1 --log work/TASK-1/entry2 -- src/a.py
lockdir "$D" "$$" "$(procstart "$$")" 0 tasks-commit.lock
TASKS_LOCK_WAIT=0.5 expect "L10 held commit lock refused" 1 "holds" "$D/.claude/scripts/tasks.sh" commit TASK-1 work/TASK-1/msg1 --log work/TASK-1/entry -- src/a.py
rm -rf "$D/.git/tasks-commit.lock"
[ -z "$(git -C "$D" diff --cached --name-only)" ] && ok "L10 nothing staged after refusals" || bad "L10 staged: $(git -C "$D" diff --cached --name-only)"
echo "x = 2" > "$D/src/a.py"
c0="$(git -C "$D" rev-list --count HEAD)"
out="$("$D/.claude/scripts/tasks.sh" commit TASK-1 work/TASK-1/msg1 --log work/TASK-1/entry -- src/a.py 2>&1)" && rc=0 || rc=$?
[ "$rc" = 0 ] && ok "L10 scoped commit succeeds" || { bad "L10 scoped commit rc=$rc"; printf '%s\n' "$out" | head -n 8; }
[ "$(git -C "$D" rev-list --count HEAD)" = $((c0 + 1)) ] && ok "L10 one commit made" || bad "L10 commit count"
git -C "$D" show -s --format=%B HEAD | grep -qx "Task: TASK-1" && ok "L10 trailer in the commit" || bad "L10 trailer"
grep -q "IMPLEMENTING - TASK-1 - 2026-01-02" "$D/.claude/state/phase-log.md" && ok "L10 phase-log entry appended" || bad "L10 phase-log entry"
[ -z "$(git -C "$D" status --porcelain -- src .claude/state)" ] && ok "L10 scoped paths and state committed" || bad "L10 left: $(git -C "$D" status --porcelain -- src .claude/state)"
# L31 (F-97-6): a state-only commit may name the task's own state file, or no path at all
"$D/.claude/scripts/tasks.sh" checkpoint TASK-1 --next "l31 a" >/dev/null 2>&1
expect "L31 own state file after -- accepted" 0 "" "$D/.claude/scripts/tasks.sh" commit TASK-1 work/TASK-1/msg1 --log work/TASK-1/entry -- .claude/state/task.TASK-1.json
"$D/.claude/scripts/tasks.sh" checkpoint TASK-1 --next "l31 b" >/dev/null 2>&1
expect "L31 empty path list accepted" 0 "" "$D/.claude/scripts/tasks.sh" commit TASK-1 work/TASK-1/msg1 --log work/TASK-1/entry --
[ -z "$(git -C "$D" status --porcelain -- .claude/state)" ] && ok "L31 state committed" || bad "L31 left: $(git -C "$D" status --porcelain -- .claude/state)"
expect "L31 another task's state file refused" 1 "FAIL" "$D/.claude/scripts/tasks.sh" commit TASK-1 work/TASK-1/msg1 --log work/TASK-1/entry -- .claude/state/task.TASK-2.json

# L24 (rest): Start-without-Stop agent from another session is ended by recover; stale binds pruned
D="$WORK/l24b"; multi "$D"; export TASKS_CALLS_LOG="$D/calls.jsonl"; : > "$TASKS_CALLS_LOG"
calls_row "$TASKS_CALLS_LOG" SubagentStart sOld coder TASK-1 3600
calls_row "$TASKS_CALLS_LOG" SubagentStart sNow coder TASK-1 60
out="$("$D/.claude/scripts/tasks.sh" recover 2>&1)" || true
printf '%s' "$out" | grep -qF "1 agents ended" && ok "L24 recover ends the idle agent" || { bad "L24 agents ended"; printf '%s\n' "$out" | head -n 6; }
grep -q '"recovered"' "$TASKS_CALLS_LOG" && ok "L24 Stop row reason recovered" || bad "L24 no recovered row"
out="$("$D/.claude/scripts/tasks.sh" recover 2>&1)" || true
printf '%s' "$out" | grep -qF "0 agents ended" || printf '%s' "$out" | grep -qF "Recovery: clean" && ok "L24 second recover ends nothing" || bad "L24 second recover"
unset TASKS_CALLS_LOG

# ======================= guard cases (97.2 .. 97.12), bundle applied to a scratch copy =======================
# LEAD_APPLY=0 skips the 097 bundle (bite check: these cases must then fail). Needs the TASK-096 bundle first.
ROOT_REPO="$(cd "$KIT/.." && pwd)"
KG="$WORK/kg"; rm -rf "$KG"; mkdir -p "$KG"
cp -r "$KIT" "$KG/.claude"
find "$KG/.claude" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf "$KG/.claude/tests" "$KG/.claude/state"; mkdir -p "$KG/.claude/state"
if ! grep -q "def bound_task" "$KG/.claude/hooks/agent_setup.py"; then
  python3 "$ROOT_REPO/work/TASK-096/patches/agent-setup-multi.py" "$KG/.claude/hooks/agent_setup.py" >/dev/null
  python3 "$ROOT_REPO/work/TASK-096/patches/hooks-multi.py" "$KG/.claude/hooks" >/dev/null
fi
if [ "${LEAD_APPLY:-1}" = 1 ]; then
  bash "$ROOT_REPO/work/TASK-097/patches/apply.sh" "$KG" >/dev/null
fi
# S4_APPLY=0 skips the slice 4 bundle (bite check for L27-L29)
if [ "${LEAD_APPLY:-1}" = 1 ] && [ "${S4_APPLY:-1}" = 1 ]; then
  bash "$ROOT_REPO/work/TASK-097/patches/s4/apply.sh" "$KG" >/dev/null
fi

gfresh() { # gfresh <dir>: TASK-1 (scope src/a/*, lead_gen 1) and TASK-2; REQ-0061 lists TASK-1
  local d="$1"; rm -rf "$d"; mkdir -p "$d/work/TASK-1" "$d/work/TASK-2" "$d/docs/req/items" "$d/docs/design" "$d/.claude/state"
  cp -r "$KG/.claude/." "$d/.claude/"
  printf '[]' > "$d/.claude/state/backlog.json"
  printf -- '---\nid: REQ-0061\ntasks: [TASK-1]\n---\n' > "$d/docs/req/items/REQ-0061.md"
  printf -- '---\nid: REQ-0099\ntasks: [TASK-2]\n---\n' > "$d/docs/req/items/REQ-0099.md"
  python3 - "$d" <<'PY'
import json, sys
st = sys.argv[1] + "/.claude/state/"
for t, sc in (("TASK-1", ["src/a/*"]), ("TASK-2", ["src/b/*"])):
    json.dump({"task_id": t, "state": "IMPLEMENTING", "scope": sc, "next": "x", "lead_gen": 1,
               "updated_at": "2026-01-01T00:00:00Z", "roles": {}}, open(st + "task.%s.json" % t, "w"))
json.dump({"schema": 2, "task_id": "TASK-1", "state": "IMPLEMENTING"}, open(st + "task.json", "w"))
PY
  git -C "$d" init -q; git -C "$d" config user.email t@e.invalid; git -C "$d" config user.name t
  git -C "$d" add -A; git -C "$d" commit -q -m init --allow-empty
}
gev() { python3 - "$@" <<'PY'
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
grun() { # grun <dir> <hook|event> <json> [CTXGUARD_TASK]: sets RC, ERR
  local d="$1" sub="$2" j="$3" t="${4:-}" e; e="$(mktemp)"
  if [ -n "$t" ]; then
    CTXGUARD_TASK="$t" python3 "$d/.claude/hooks/agent_setup.py" "$sub" --config "$d/.claude/agent_setup.json" <<<"$j" >/dev/null 2>"$e" && RC=0 || RC=$?
  else
    python3 "$d/.claude/hooks/agent_setup.py" "$sub" --config "$d/.claude/agent_setup.json" <<<"$j" >/dev/null 2>"$e" && RC=0 || RC=$?
  fi
  ERR="$(cat "$e")"; rm -f "$e"
}
GW() { printf '{"file_path":"%s","content":"x"}' "$1"; }
GB() { python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$1"; }
geq() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (got [$2] want [$3])"; printf '%s\n' "$ERR" | head -n 3 | sed 's/^/    /'; fi; }
gviol() { grep -q "$2" "$1/.claude/agent_setup_violations.jsonl" 2>/dev/null; }
LD="$WORK/lg"

# ---- L1: the lead writes its own task docs only
gfresh "$LD"
grun "$LD" hook "$(gev Write "$(GW "$LD/docs/design/phase-1-x.md")" lead s1)" TASK-1; geq "L1 lead writes its design doc" "$RC" 0
grun "$LD" hook "$(gev Write "$(GW "$LD/docs/report/phase-1-x.md")" lead s1)" TASK-1; geq "L1 lead writes its report doc" "$RC" 0
grun "$LD" hook "$(gev Write "$(GW "$LD/docs/design/phase-2-x.md")" lead s1)" TASK-1; geq "L1 other task's design refused" "$RC" 2
grun "$LD" hook "$(gev Write "$(GW "$LD/.claude/settings.json")" lead s1)" TASK-1; geq "L1 settings refused" "$RC" 2
grun "$LD" hook "$(gev Write "$(GW "$LD/.claude/hooks/agent_setup.py")" lead s1)" TASK-1; geq "L1 hooks refused" "$RC" 2
grun "$LD" hook "$(gev Write "$(GW "$LD/.claude/agent_setup.json")" lead s1)" TASK-1; geq "L1 agent_setup.json refused" "$RC" 2
grun "$LD" hook "$(gev Write "$(GW "$LD/docs/design/phase-1-x.md")" coder s1)" TASK-1; geq "L1 a coder gets no such right" "$RC" 2

# ---- L2: the lead's own task commands
for c in "bash .claude/scripts/tasks.sh show TASK-1" "bash .claude/scripts/tasks.sh commit TASK-1 work/TASK-1/m" \
         "bash .claude/scripts/tasks.sh set TASK-1 --next go" "bash .claude/scripts/backlog.sh complete TASK-1" \
         "bash .claude/scripts/task_checkpoint.sh ask TASK-1 q 2>&1"; do
  grun "$LD" hook "$(gev Bash "$(GB "$c")" lead s1)" TASK-1; geq "L2 allowed: $c" "$RC" 0
done
for c in "bash .claude/scripts/tasks.sh commit TASK-2 m" "bash .claude/scripts/tasks.sh set TASK-10 x" "bash .claude/scripts/backlog.sh complete TASK-2" \
         "bash .claude/scripts/tasks.sh pick TASK-1" "bash .claude/scripts/tasks.sh lead TASK-1" "bash .claude/scripts/tasks.sh resume TASK-1"; do
  grun "$LD" hook "$(gev Bash "$(GB "$c")" lead s1)" TASK-1; geq "L2 refused: $c" "$RC" 2
done

# ---- L3: req.py only for a REQ that lists the lead's task
grun "$LD" hook "$(gev Bash "$(GB "python3 .claude/req/req.py status REQ-0061 --to DONE")" lead s1)" TASK-1; geq "L3 req.py on its own REQ" "$RC" 0
grun "$LD" hook "$(gev Bash "$(GB "python3 .claude/req/req.py ac REQ-0061 1")" lead s1)" TASK-1; geq "L3 req.py ac on its own REQ" "$RC" 0
grun "$LD" hook "$(gev Bash "$(GB "python3 .claude/req/req.py status REQ-0099 --to DONE")" lead s1)" TASK-1; geq "L3 other task's REQ refused" "$RC" 2
grun "$LD" hook "$(gev Bash "$(GB "python3 .claude/req/req.py status REQ-0777 --to DONE")" lead s1)" TASK-1; geq "L3 unknown REQ refused" "$RC" 2
grun "$LD" hook "$(gev Bash "$(GB "python3 .claude/req/req.py status REQ-0061 --to DONE")" coder s1)" TASK-1; geq "L3 req.py for a coder refused" "$RC" 2

# ---- L4: chained commands and redirects are refused even inside an allowed command
for c in "bash .claude/scripts/tasks.sh set TASK-1 --next go; rm -rf x" "bash .claude/scripts/tasks.sh show TASK-1 && touch .claude/settings.json" \
         "bash .claude/scripts/tasks.sh show TASK-1 | tee .claude/hooks/x" 'bash .claude/scripts/tasks.sh set TASK-1 --next $(id)' \
         "bash .claude/scripts/tasks.sh set TASK-1 --next a > b" "bash .claude/scripts/tasks.sh show TASK-1 > .claude/agent_setup.json"; do
  grun "$LD" hook "$(gev Bash "$(GB "$c")" lead s1)" TASK-1; geq "L4 refused: $c" "$RC" 2
done

# ---- L26 / 97.2c: state-writing commands are denied for the other roles; a lead is held to its task
for r in coder tester designer; do
  grun "$LD" hook "$(gev Bash "$(GB "bash .claude/scripts/tasks.sh commit TASK-1 m")" $r s1)" TASK-1; geq "L26 $r: tasks.sh commit refused" "$RC" 2
done
grun "$LD" hook "$(gev Bash "$(GB "bash .claude/scripts/tasks.sh set TASK-1 --next x")" coder s1)" TASK-1; geq "L26 coder: tasks.sh set refused" "$RC" 2
grun "$LD" hook "$(gev Bash "$(GB "bash .claude/scripts/wip.sh TASK-1 x")" coder s1)" TASK-1; geq "L26 coder: wip.sh refused" "$RC" 2
grun "$LD" hook "$(gev Bash "$(GB "bash .claude/scripts/tasks.sh checkpoint TASK-1 --next x")" tester s1)" TASK-1; geq "L26 tester: tasks.sh checkpoint refused" "$RC" 2
grun "$LD" hook "$(gev Bash "$(GB "bash .claude/scripts/tasks.sh lead TASK-1")" coder s1)" TASK-1; geq "L26 coder: tasks.sh lead refused" "$RC" 2
grun "$LD" hook "$(gev Bash "$(GB "bash .claude/scripts/tasks.sh status")" coder s1)" TASK-1; geq "L26 coder: tasks.sh status still free" "$RC" 0
grun "$LD" hook "$(gev Bash "$(GB "bash .claude/scripts/tasks.sh set TASK-1 --next x")" lead s1)" TASK-1; geq "L26 lead on TASK-1: set allowed" "$RC" 0
grun "$LD" hook "$(gev Bash "$(GB "bash .claude/scripts/tasks.sh set TASK-2 --next x")" lead s1)" TASK-1; geq "L26 lead on TASK-1: set TASK-2 refused" "$RC" 2

# ---- L5: a lead launches a child; the child binds to the lead's task
gfresh "$LD"
grun "$LD" hook "$(gev Agent '{"subagent_type":"coder","prompt":"TASK-1 item 1.1: go"}' lead s5 PreToolUse "" la)" TASK-1; geq "L5 lead launches a coder for its task" "$RC" 0
grun "$LD" hook "$(gev Write "$(GW "$LD/work/TASK-2/a.md")" coder s5 PreToolUse "" c1)"; geq "L5 child bound to TASK-1: work/TASK-2 refused" "$RC" 2
grun "$LD" hook "$(gev Write "$(GW "$LD/work/TASK-1/a.md")" coder s5 PreToolUse "" c1)"; geq "L5 child bound to TASK-1: work/TASK-1 ok" "$RC" 0
python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))==[] else 1)' "$LD/.claude/agent_setup_launch.json" && ok "L5 queue entry consumed" || bad "L5 queue not empty"

# ---- L6: two leads at once; their children bind by the task named in the call
gfresh "$LD"
grun "$LD" hook "$(gev Write "$(GW "$LD/work/TASK-1/n.md")" lead s6 PreToolUse "" la)"; geq "L6 lead A first write" "$RC" 0
grun "$LD" hook "$(gev Write "$(GW "$LD/work/TASK-2/n.md")" lead s6 PreToolUse "" lb)"; geq "L6 lead B first write" "$RC" 0
grun "$LD" hook "$(gev Agent '{"subagent_type":"coder","prompt":"TASK-1 item 1: go"}' lead s6 PreToolUse "" la)"; geq "L6 A launches a coder" "$RC" 0
grun "$LD" hook "$(gev Agent '{"subagent_type":"coder","prompt":"TASK-2 item 1: go"}' lead s6 PreToolUse "" lb)"; geq "L6 B launches a coder" "$RC" 0
grun "$LD" hook "$(gev Write "$(GW "$LD/src/z.md")" coder s6 PreToolUse "" cx)"; geq "L6 a write naming no task is refused while ambiguous" "$RC" 2
gviol "$LD" bind_pending && ok "L6 bind_pending logged" || bad "L6 bind_pending not logged"
grun "$LD" hook "$(gev Bash "$(GB "ls work/TASK-2")" coder s6 PreToolUse "" c2)"; geq "L6 child naming TASK-2 claims TASK-2" "$RC" 0
grun "$LD" hook "$(gev Write "$(GW "$LD/work/TASK-1/q.md")" coder s6 PreToolUse "" c2)"; geq "L6 its work/TASK-1 write is refused" "$RC" 2
grun "$LD" hook "$(gev Bash "$(GB "ls work/TASK-1")" coder s6 PreToolUse "" c1)"; geq "L6 other child claims TASK-1" "$RC" 0
grun "$LD" hook "$(gev Write "$(GW "$LD/work/TASK-1/q.md")" coder s6 PreToolUse "" c1)"; geq "L6 its work/TASK-1 write is ok" "$RC" 0

# ---- L7: a lead may launch only role types, only for its own task
gfresh "$LD"
grun "$LD" hook "$(gev Agent '{"subagent_type":"lead","prompt":"TASK-1 item 1: go"}' lead s7 PreToolUse "" la)" TASK-1; geq "L7 lead to lead refused" "$RC" 2
grun "$LD" hook "$(gev Agent '{"subagent_type":"coder","prompt":"TASK-2 item 1: go"}' lead s7 PreToolUse "" la)" TASK-1; geq "L7 lead to another task refused" "$RC" 2
grun "$LD" hook "$(gev Agent '{"subagent_type":"general-purpose","prompt":"TASK-1 go"}' lead s7 PreToolUse "" la)" TASK-1; geq "L7 non-role agent type refused" "$RC" 2
grun "$LD" hook "$(gev Agent '{"subagent_type":"coder","prompt":"do things"}' lead s7 PreToolUse "" la)" TASK-1; geq "L7 line 1 without a task id refused" "$RC" 2
gviol "$LD" lead_launch && ok "L7 lead_launch logged" || bad "L7 lead_launch not logged"
grun "$LD" hook "$(gev Agent '{"subagent_type":"tester","prompt":"TASK-1 item 2: go"}' lead s7 PreToolUse "" la)" TASK-1; geq "L7 tester for its own task ok" "$RC" 0

# ---- L24 (bind part): a newer generation fences the old lead (97.4)
gfresh "$LD"
grun "$LD" hook "$(gev Write "$(GW "$LD/work/TASK-1/n.md")" lead s24 PreToolUse "" la)"; geq "L24 lead claims TASK-1" "$RC" 0
grun "$LD" hook "$(gev Write "$(GW "$LD/work/TASK-1/n2.md")" lead s24 PreToolUse "" la)"; geq "L24 same gen: ok" "$RC" 0
python3 - "$LD/.claude/state/task.TASK-1.json" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["lead_gen"] = 2; json.dump(d, open(p, "w"))
PY
grun "$LD" hook "$(gev Bash "$(GB "ls")" lead s24 PreToolUse "" la)"; geq "L24 replaced lead: any tool refused" "$RC" 2
gviol "$LD" lead_fence && ok "L24 lead_fence logged" || bad "L24 lead_fence not logged"

# ---- L11 / L24 (Start part): the stop gate asks once; a child Start without Stop within 15 min blocks too
gfresh "$LD"
LDLOG="$LD/.claude/agent_setup_calls.jsonl"
grun "$LD" event "$(gev "" "" lead s11 SubagentStop "" la)" TASK-1; geq "L11 empty checkpoint.next: stop asked" "$RC" 2
grun "$LD" event "$(gev "" "" lead s11 SubagentStop 1 la)" TASK-1; geq "L11 second stop is free" "$RC" 0
python3 - "$LD/.claude/state/task.TASK-1.json" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["checkpoint"] = {"next": "go on", "at": "2099-01-01T00:00:00Z"}; json.dump(d, open(p, "w"))
PY
grun "$LD" event "$(gev "" "" lead s11 SubagentStop "" la)" TASK-1; geq "L11 checkpoint set, clean scope: stop free" "$RC" 0
calls_row "$LDLOG" SubagentStart s11 coder TASK-1 60
grun "$LD" event "$(gev "" "" lead s11 SubagentStop "" la)" TASK-1; geq "L24 child started 60 s ago, no Stop: stop asked" "$RC" 2
: > "$LDLOG"; calls_row "$LDLOG" SubagentStart s11 coder TASK-1 3600
grun "$LD" event "$(gev "" "" lead s11 SubagentStop "" la)" TASK-1; geq "L24 child Start older than 15 min: stop free" "$RC" 0
: > "$LDLOG"; calls_row "$LDLOG" SubagentStart s11 coder TASK-1 60; calls_row "$LDLOG" SubagentStop s11 coder TASK-1 30
grun "$LD" event "$(gev "" "" lead s11 SubagentStop "" la)" TASK-1; geq "L24 child Start then Stop: stop free" "$RC" 0
: > "$LDLOG"; mkdir -p "$LD/src/a"; echo y > "$LD/src/a/f.py"
grun "$LD" event "$(gev "" "" lead s11 SubagentStop "" la)" TASK-1; geq "L11 dirty scope: stop asked" "$RC" 2

# ---- L16: two parallel claims keep both binds and drain the queue (10 rounds)
l16_bad=0
for i in 1 2 3 4 5 6 7 8 9 10; do
  gfresh "$LD"
  grun "$LD" hook "$(gev Agent '{"subagent_type":"coder","prompt":"TASK-1 item 1: go"}' "" s16 PreToolUse "" m)"
  grun "$LD" hook "$(gev Agent '{"subagent_type":"coder","prompt":"TASK-2 item 1: go"}' "" s16 PreToolUse "" m)"
  j1="$(gev Bash "$(GB "ls work/TASK-1")" coder s16 PreToolUse "" c1)"
  j2="$(gev Bash "$(GB "ls work/TASK-2")" coder s16 PreToolUse "" c2)"
  python3 "$LD/.claude/hooks/agent_setup.py" hook --config "$LD/.claude/agent_setup.json" <<<"$j1" >/dev/null 2>&1 & p1=$!
  python3 "$LD/.claude/hooks/agent_setup.py" hook --config "$LD/.claude/agent_setup.json" <<<"$j2" >/dev/null 2>&1 & p2=$!
  wait "$p1" || true; wait "$p2" || true
  python3 - "$LD" <<'PY' || l16_bad=$((l16_bad + 1))
import json, sys
d = sys.argv[1] + "/.claude/"
b = json.load(open(d + "agent_setup_binds.json"))
q = json.load(open(d + "agent_setup_launch.json"))
sys.exit(0 if b.get("s16/c1") == "TASK-1" and b.get("s16/c2") == "TASK-2" and q == [] else 1)
PY
done
[ "$l16_bad" = 0 ] && ok "L16 10 rounds of two parallel claims: both binds kept, queue empty" || bad "L16 $l16_bad of 10 rounds lost a bind"

# ---- L22: a killed holder does not stall a claim: broken at once and logged
if [ "$HAVE_PROC" = 1 ]; then
  gfresh "$LD"
  grun "$LD" hook "$(gev Agent '{"subagent_type":"coder","prompt":"TASK-1 item 1: go"}' "" s22 PreToolUse "" m)"
  sleep 0 & dead=$!; wait "$dead" || true
  lockdir "$LD" "$dead" 1 0 agent-setup-binds.lock
  t0=$(date +%s)
  grun "$LD" hook "$(gev Bash "$(GB "ls work/TASK-1")" coder s22 PreToolUse "" c1)"
  t1=$(date +%s)
  [ $((t1 - t0)) -lt 2 ] && ok "L22 claim passes a dead holder in under 2 s" || bad "L22 took $((t1 - t0)) s"
  python3 -c 'import json,sys; b=json.load(open(sys.argv[1])); sys.exit(0 if b.get("s22/c1")=="TASK-1" else 1)' "$LD/.claude/agent_setup_binds.json" && ok "L22 the claim was made" || bad "L22 no bind"
  gviol "$LD" lock_break && ok "L22 lock_break logged" || bad "L22 lock_break not logged"
  [ ! -d "$LD/.git/agent-setup-binds.lock" ] && ok "L22 lock released afterwards" || bad "L22 lock left behind"
fi

# ---- L27 (F-97-4): quoted text is not chaining; real chaining, $( and unbalanced quotes still refused
if [ "${LEAD_APPLY:-1}" = 1 ]; then
  gfresh "$LD"
  TS="bash .claude/scripts/tasks.sh set TASK-1 --next"
  grun "$LD" hook "$(gev Bash "$(GB "$TS 'a; b'")" lead s1)" TASK-1; geq "L27 single-quoted ; allowed" "$RC" 0
  grun "$LD" hook "$(gev Bash "$(GB "$TS \"a; b | c\"")" lead s1)" TASK-1; geq "L27 double-quoted ; and | allowed" "$RC" 0
  grun "$LD" hook "$(gev Bash "$(GB "$TS \"\$(id)\"")" lead s1)" TASK-1; geq "L27 \$( in double quotes refused" "$RC" 2
  grun "$LD" hook "$(gev Bash "$(GB "$TS x \$(id)")" lead s1)" TASK-1; geq "L27 bare \$( refused" "$RC" 2
  grun "$LD" hook "$(gev Bash "$(GB "$TS x | cat")" lead s1)" TASK-1; geq "L27 pipe refused" "$RC" 2
  grun "$LD" hook "$(gev Bash "$(GB "$TS 'a'; ls")" lead s1)" TASK-1; geq "L27 chain after a quote refused" "$RC" 2
  grun "$LD" hook "$(gev Bash "$(GB "$TS 'a")" lead s1)" TASK-1; geq "L27 unbalanced quote refused" "$RC" 2
  grun "$LD" hook "$(gev Bash "$(GB "$TS 'a\`id\`'")" lead s1)" TASK-1; geq "L27 backtick refused even in quotes" "$RC" 2

# ---- L28 (F-97-3): guard runtime files raise no tamper; a protected file still does
  gfresh "$LD"
  tev() { python3 -c 'import json,sys;print(json.dumps({"tool_name":"Bash","tool_input":{"command":"x"},"session_id":"s1","hook_event_name":sys.argv[1],"agent_type":"coder","agent_id":"a1"}))' "$1"; }
  tcall() { (cd "$LD" && python3 .claude/hooks/agent_setup.py hook --config .claude/agent_setup.json <<<"$(tev PreToolUse)" >/dev/null 2>&1) || true
            "$@"
            (cd "$LD" && python3 .claude/hooks/agent_setup.py post --config .claude/agent_setup.json <<<"$(tev PostToolUse)" >"$LD/post.out" 2>/dev/null) || true; }
  rtw() { local f; for f in binds.json launch.json hookkeys.json; do echo '{}' >> "$LD/.claude/agent_setup_$f"; done; echo '{}' >> "$LD/.claude/agent_setup_violations.jsonl"; }
  rm -f "$LD/.claude/agent_setup_violations.jsonl"
  tcall rtw
  if gviol "$LD" '"kind": "tamper"' || [ -s "$LD/post.out" ]; then bad "L28 runtime file change raised tamper"; else ok "L28 runtime file change: no tamper"; fi
  stw() { echo ' ' >> "$LD/.claude/agent_setup.json"; }
  tcall stw
  if grep -q 'agent_setup.json' "$LD/post.out"; then ok "L28 agent_setup.json change still raises tamper"; else bad "L28 no tamper for agent_setup.json"; fi

# ---- L29 (F-97-1): Stop WARNs, not blocks, on the uncommitted state of a task with a live lead
  gfresh "$LD"; export TASKS_CALLS_LOG="$LD/calls.jsonl"; : > "$TASKS_CALLS_LOG"
  sc() { SO="$(cd "$LD" && CLAUDE_PROJECT_DIR="$LD" bash .claude/hooks/stop-check.sh <<<'{}' 2>&1)" && RC=0 || RC=$?; }
  echo ' ' >> "$LD/.claude/state/task.TASK-1.json"; echo ' ' >> "$LD/.claude/state/task.json"
  sc; [ "$RC" = 2 ] && ok "L29 no live lead: dirty state blocks" || bad "L29 no lead: rc=$RC"
  calls_row "$TASKS_CALLS_LOG" SubagentStart s1 lead TASK-1 120
  sc
  if [ "$RC" = 0 ] && printf '%s' "$SO" | grep -q 'TASK-1: lead live, its state is uncommitted'; then ok "L29 live lead: WARN, no block"; else bad "L29 live lead: rc=$RC $SO"; fi
  echo ' ' >> "$LD/.claude/state/task.TASK-2.json"
  sc; if [ "$RC" = 2 ] && printf '%s' "$SO" | grep -q 'task.TASK-2.json'; then ok "L29 other dirty state still blocks"; else bad "L29 other state: rc=$RC"; fi
  unset TASKS_CALLS_LOG
fi

echo "SUMMARY(lead): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

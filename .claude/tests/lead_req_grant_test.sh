#!/usr/bin/env bash
# TASK-098 F7 (RAW-00510): the narrow REQ grant for a lead (work/TASK-098/patches/05-lead-req-grant.py).
# A lead bound to task T may edit the body of a REQ file whose own tasks: list names T, run req.py focus/log
# for it, and nothing else in docs/req/. Builds a scratch kit (TASK-096 + 097 bundles, then patch 05),
# drives the guard hook like lead_test.sh. Never touches the real .claude or state.
# Run: bash .claude/tests/lead_req_grant_test.sh     (F7_APPLY=0 skips patch 05: the bite check, allowed cases must fail)
set -Eeuo pipefail
unset TASK CTXGUARD_TASK CTXGUARD_ROLE || true
KIT="${KIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ROOT_REPO="$(cd "$KIT/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export TMPDIR="$WORK"
PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }

KG="$WORK/kg"; mkdir -p "$KG"
cp -r "$KIT" "$KG/.claude"
find "$KG/.claude" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf "$KG/.claude/tests" "$KG/.claude/state"; mkdir -p "$KG/.claude/state"
if ! grep -q "def bound_task" "$KG/.claude/hooks/agent_setup.py"; then
  python3 "$ROOT_REPO/work/TASK-096/patches/agent-setup-multi.py" "$KG/.claude/hooks/agent_setup.py" >/dev/null
  python3 "$ROOT_REPO/work/TASK-096/patches/hooks-multi.py" "$KG/.claude/hooks" >/dev/null
fi
if ! grep -q "_lead_ok_write" "$KG/.claude/hooks/agent_setup.py"; then
  bash "$ROOT_REPO/work/TASK-097/patches/apply.sh" "$KG" >/dev/null
  bash "$ROOT_REPO/work/TASK-097/patches/s4/apply.sh" "$KG" >/dev/null
fi
if [ "${F7_APPLY:-1}" = 1 ]; then
  python3 "$ROOT_REPO/work/TASK-098/patches/05-lead-req-grant.py" "$KG/.claude" >/dev/null
fi

REQ_TXT='---
id: REQ-0061
status: DESIGN
epic: EPIC-001
source: [RAW-00001]
supersedes: 
tasks: [TASK-1]
---
## Original (verbatim, never edit)
> **[RAW-00001]** user words here
## Requirement
Body line one
Body line two
'
gfresh() { # gfresh <dir>: TASK-1 (lead) and TASK-2; REQ-0061 lists TASK-1, REQ-0099 lists TASK-2
  local d="$1"; rm -rf "$d"
  mkdir -p "$d/work/TASK-1" "$d/docs/req/items" "$d/docs/req/raw" "$d/docs/req/epics" "$d/.claude/state"
  cp -r "$KG/.claude/." "$d/.claude/"
  printf '[]' > "$d/.claude/state/backlog.json"
  printf '%s' "$REQ_TXT" > "$d/docs/req/items/REQ-0061.md"
  printf -- '---\nid: REQ-0099\nstatus: TODO\ntasks: [TASK-2]\n---\nOther body\n' > "$d/docs/req/items/REQ-0099.md"
  printf -- '---\nid: REQ-0050\nstatus: TODO\ntasks: [TASK-1]\n---\nOutside\n' > "$d/outside.md"
  ln -s ../../../outside.md "$d/docs/req/items/REQ-0050.md"
  echo raw > "$d/docs/req/raw/RAW-00001.md"; echo epic > "$d/docs/req/epics/EPIC-001.md"; echo idx > "$d/docs/req/INDEX.md"
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
# ev <tool> <role> key=value...: the hook event; a value starting with @ is a JSON literal
ev() {
  python3 - "$@" <<'PY'
import json, sys
tool, role = sys.argv[1:3]
ti = {}
for kv in sys.argv[3:]:
    k, v = kv.split("=", 1)
    ti[k] = json.loads(v[1:]) if v.startswith("@") else v
print(json.dumps({"tool_name": tool, "tool_input": ti, "session_id": "s1", "hook_event_name": "PreToolUse",
                  "cwd": "/tmp", "agent_type": role}))
PY
}
run() { # run <dir> <json>: sets RC, ERR (lead bound to TASK-1)
  local e; e="$(mktemp)"
  CTXGUARD_TASK=TASK-1 python3 "$1/.claude/hooks/agent_setup.py" hook --config "$1/.claude/agent_setup.json" <<<"$2" >/dev/null 2>"$e" && RC=0 || RC=$?
  ERR="$(cat "$e")"; rm -f "$e"
}
geq() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (got [$2] want [$3])"; printf '%s\n' "$ERR" | head -n 3 | sed 's/^/    /'; fi; }
# expect <name> <want-rc> <dir> <tool> <role> key=value...
expect() { local n="$1" w="$2" d="$3"; shift 3; run "$d" "$(ev "$@")"; geq "$n" "$RC" "$w"; }
bash_ev() { python3 -c 'import json,sys;print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.argv[1]},"session_id":"s1","hook_event_name":"PreToolUse","cwd":"/tmp","agent_type":sys.argv[2]}))' "$1" "$2"; }
bexp() { run "$1" "$(bash_ev "$3" "${4:-lead}")"; geq "$2: $3" "$RC" "${5:-0}"; }

D="$WORK/g"; gfresh "$D"
R61="$D/docs/req/items/REQ-0061.md"; R99="$D/docs/req/items/REQ-0099.md"

# ---- allowed: the body of the lead's own REQ
expect "F7 Edit own REQ body" 0 "$D" Edit lead "file_path=$R61" "old_string=Body line one" "new_string=Body line 1 changed"
expect "F7 Write own REQ body (status/tasks same)" 0 "$D" Write lead "file_path=$R61" "content=$REQ_TXT
more"
expect "F7 MultiEdit own REQ body" 0 "$D" MultiEdit lead "file_path=$R61" 'edits=@[{"old_string":"Body line one","new_string":"A"},{"old_string":"Body line two","new_string":"B"}]'
bexp "$D" "F7 req.py focus own REQ" "python3 .claude/req/req.py focus REQ-0061 --next go"
bexp "$D" "F7 req.py log own REQ" "python3 .claude/req/req.py log REQ-0061 progress note"

# ---- refused: every other REQ file and doc area
expect "F7 other REQ refused" 2 "$D" Edit lead "file_path=$R99" "old_string=Other body" "new_string=x"
expect "F7 other REQ Write refused" 2 "$D" Write lead "file_path=$R99" "content=x"
expect "F7 new REQ file refused" 2 "$D" Write lead "file_path=$D/docs/req/items/REQ-0777.md" "content=---
tasks: [TASK-1]
---
"
expect "F7 symlinked REQ refused" 2 "$D" Edit lead "file_path=$D/docs/req/items/REQ-0050.md" "old_string=Outside" "new_string=x"
expect "F7 raw refused" 2 "$D" Write lead "file_path=$D/docs/req/raw/RAW-00001.md" "content=x"
expect "F7 epic refused" 2 "$D" Write lead "file_path=$D/docs/req/epics/EPIC-001.md" "content=x"
expect "F7 INDEX refused" 2 "$D" Write lead "file_path=$D/docs/req/INDEX.md" "content=x"
expect "F7 non-REQ name in items refused" 2 "$D" Write lead "file_path=$D/docs/req/items/notes.md" "content=x"
expect "F7 NotebookEdit refused" 2 "$D" NotebookEdit lead "notebook_path=$R61" "new_source=x"

# ---- refused: a status or tasks line may not change (Edit, Write, MultiEdit)
expect "F7 Edit status line refused" 2 "$D" Edit lead "file_path=$R61" "old_string=status: DESIGN" "new_string=status: DONE"
expect "F7 Edit status via wider match refused" 2 "$D" Edit lead "file_path=$R61" "old_string=status: DESIGN
tasks" "new_string=status: DONE
tasks"
expect "F7 Write with new status refused" 2 "$D" Write lead "file_path=$R61" "content=---
id: REQ-0061
status: DONE
tasks: [TASK-1]
---
Body line one
"
expect "F7 Write dropping status refused" 2 "$D" Write lead "file_path=$R61" "content=---
id: REQ-0061
tasks: [TASK-1]
---
Body
"
expect "F7 Write adding a second status refused" 2 "$D" Write lead "file_path=$R61" "content=$REQ_TXT
status: DONE
"
expect "F7 Edit status case change refused" 2 "$D" Edit lead "file_path=$R61" "old_string=status: DESIGN" "new_string=Status: DESIGN"
expect "F7 MultiEdit with a status edit second refused" 2 "$D" MultiEdit lead "file_path=$R61" 'edits=@[{"old_string":"Body line one","new_string":"A"},{"old_string":"status: DESIGN","new_string":"status: DONE"}]'
expect "F7 MultiEdit body then new status line refused" 2 "$D" MultiEdit lead "file_path=$R61" 'edits=@[{"old_string":"Body line one","new_string":"x\nstatus: DONE"}]'
expect "F7 Edit tasks line refused" 2 "$D" Edit lead "file_path=$R61" "old_string=tasks: [TASK-1]" "new_string=tasks: [TASK-1, TASK-2]"
expect "F7 Edit tasks line to drop task refused" 2 "$D" Edit lead "file_path=$R61" "old_string=tasks: [TASK-1]" "new_string=tasks: []"
# anti-spoof: a REQ that does not list TASK-1 cannot be made to list it with the same call
expect "F7 spoof: add own task to a foreign REQ refused" 2 "$D" Edit lead "file_path=$R99" "old_string=tasks: [TASK-2]" "new_string=tasks: [TASK-2, TASK-1]"
expect "F7 spoof: Write a foreign REQ listing own task refused" 2 "$D" Write lead "file_path=$R99" "content=---
id: REQ-0099
status: TODO
tasks: [TASK-1, TASK-2]
---
x
"
expect "F7 Edit with absent old_string refused" 2 "$D" Edit lead "file_path=$R61" "old_string=not in the file" "new_string=x"
expect "F7 relative path form still checked" 2 "$D" Edit lead "file_path=docs/req/items/../items/REQ-0099.md" "old_string=Other body" "new_string=x"

# ---- refused: id/source/epic/supersedes lines and the verbatim Original section (F-D-2)
expect "F7 Edit id line refused" 2 "$D" Edit lead "file_path=$R61" "old_string=id: REQ-0061" "new_string=id: REQ-0099"
expect "F7 Edit source line refused" 2 "$D" Edit lead "file_path=$R61" "old_string=source: [RAW-00001]" "new_string=source: [RAW-00001, RAW-00002]"
expect "F7 Edit epic line refused" 2 "$D" Edit lead "file_path=$R61" "old_string=epic: EPIC-001" "new_string=epic: EPIC-002"
expect "F7 Edit supersedes line refused" 2 "$D" Edit lead "file_path=$R61" "old_string=supersedes: " "new_string=supersedes: REQ-0099"
expect "F7 Edit Original section refused" 2 "$D" Edit lead "file_path=$R61" "old_string=user words here" "new_string=other words"
expect "F7 Write with changed Original refused" 2 "$D" Write lead "file_path=$R61" "content=$(printf '%s' "$REQ_TXT" | sed 's/user words here/changed/')"
expect "F7 Write dropping Original refused" 2 "$D" Write lead "file_path=$R61" "content=$(printf '%s' "$REQ_TXT" | grep -v 'RAW-00001\]\*\*' | grep -v '^## Original')"
expect "F7 MultiEdit body then Original refused" 2 "$D" MultiEdit lead "file_path=$R61" 'edits=@[{"old_string":"Body line one","new_string":"A"},{"old_string":"user words here","new_string":"x"}]'

# ---- refused: a non-lead role keeps no right; the lead of another task has none on this REQ
expect "F7 coder refused on the lead's REQ" 2 "$D" Edit coder "file_path=$R61" "old_string=Body line one" "new_string=x"
expect "F7 designer refused on the lead's REQ" 2 "$D" Write designer "file_path=$R61" "content=$REQ_TXT"
run "$D" "$(ev Edit lead "file_path=$R61" "old_string=Body line one" "new_string=x")"; RC1=$RC
CTXGUARD_TASK=TASK-2 python3 "$D/.claude/hooks/agent_setup.py" hook --config "$D/.claude/agent_setup.json" <<<"$(ev Edit lead "file_path=$R61" "old_string=Body line one" "new_string=x")" >/dev/null 2>&1 && RC=0 || RC=$?
if [ "$RC1" = 0 ] || [ "${F7_APPLY:-1}" != 1 ]; then geq "F7 lead of TASK-2 refused on a TASK-1 REQ" "$RC" 2; else bad "F7 setup: own-REQ edit should be allowed"; fi

# ---- req.py: rule unchanged from HEAD (status|ac|focus|log, only for a REQ that lists the task)
for c in "status REQ-0061 --to DONE" "ac REQ-0061 1" "focus REQ-0061 --next go" "log REQ-0061 note"; do
  bexp "$D" "F7 req.py on own REQ stays allowed" "python3 .claude/req/req.py $c" lead 0
done
bexp "$D" "F7 refused req.py status other REQ" "python3 .claude/req/req.py status REQ-0099 --to DONE" lead 2
for c in "raw add x" "task REQ-0061 TASK-1" "new x" "epic x"; do
  bexp "$D" "F7 refused req.py" "python3 .claude/req/req.py $c" lead 2
done
bexp "$D" "F7 refused req.py focus other REQ" "python3 .claude/req/req.py focus REQ-0099 --next go" lead 2
bexp "$D" "F7 refused req.py log other REQ" "python3 .claude/req/req.py log REQ-0099 note" lead 2
bexp "$D" "F7 refused req.py focus unknown REQ" "python3 .claude/req/req.py focus REQ-0777 --next go" lead 2
bexp "$D" "F7 refused req.py focus for a coder" "python3 .claude/req/req.py focus REQ-0061 --next go" coder 2
bexp "$D" "F7 refused chained focus" "python3 .claude/req/req.py focus REQ-0061 --next go; rm -rf x" lead 2
bexp "$D" "F7 refused redirect into REQ file" "echo x >> docs/req/items/REQ-0061.md" lead 2
bexp "$D" "F7 refused sed -i on REQ file" "sed -i s/DESIGN/DONE/ docs/req/items/REQ-0061.md" lead 2

echo "SUMMARY(lead_req_grant): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]

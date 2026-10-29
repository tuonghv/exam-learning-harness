#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPT_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPT_DIR")"
TASK="$ROOT/.claude/state/task.json"
PHASE_LOG="$ROOT/.claude/state/phase-log.md"
BACKLOG="$ROOT/.claude/state/backlog.json"

[ -f "$TASK" ] || { echo "FAIL: $TASK missing"; exit 1; }

WANT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --task) WANT="${2:-}"; shift 2 || { echo "FAIL: --task needs TASK-N"; exit 1; } ;;
    *) echo "Usage: $(basename "$0") [--task TASK-N]"; exit 1 ;;
  esac
done

# One task's checks (body unchanged since phase 1; multi mode runs it per task file).
run_body() {
python3 - "$1" "$PHASE_LOG" "$BACKLOG" "$ROOT" <<'PY'
import json, sys, os, re
from datetime import datetime, timezone

task_path, log_path = sys.argv[1], sys.argv[2]
backlog_path = sys.argv[3] if len(sys.argv) > 3 else ""
root = sys.argv[4] if len(sys.argv) > 4 else "."
d = json.load(open(task_path))

SEQUENCE = ["TODO", "DESIGN", "IMPLEMENTING", "UNIT_TESTED", "VERIFIED", "DONE"]
state = d.get("state")

# Accumulate every problem so one run surfaces all of them (a resuming
# session should see the full picture, not just the first stop).
fails, warns = [], []
def fail(msg): fails.append(msg)
def warn(msg): warns.append(msg)

print(f"STATE: {state}")
if state not in SEQUENCE:
    print(f"FAIL: invalid state '{state}'")
    raise SystemExit(1)

def get(*path):
    node = d
    for p in path:
        node = node.get(p, {}) if isinstance(node, dict) else {}
    return node

idx = SEQUENCE.index(state)

# --- per-section status vocab ---
vocab = {
    "design": {"pending", "completed"},
    "implementation": {"pending", "completed"},
    "unit_test": {"pending", "passed", "failed"},
    "security": {"pending", "completed", "not_applicable"},
    "verification": {"pending", "passed", "failed"},
    "report": {"pending", "completed"},
}
for section, allowed in vocab.items():
    status = get(section, "status")
    if status not in allowed:
        fail(f"{section}.status='{status}' not in {sorted(allowed)}")

# --- forward gating: each state requires the prior phase's evidence ---
if idx >= SEQUENCE.index("IMPLEMENTING"):
    if get("design", "status") != "completed":
        fail("reaching IMPLEMENTING+ requires design.status=completed")
    if not get("design", "summary"):
        fail("design.summary is empty")

if idx >= SEQUENCE.index("UNIT_TESTED"):
    if get("implementation", "status") != "completed":
        fail("reaching UNIT_TESTED+ requires implementation.status=completed")
    if not get("implementation", "files"):
        fail("implementation.files is empty")
    if get("unit_test", "status") != "passed":
        fail("reaching UNIT_TESTED+ requires unit_test.status=passed")
    if not get("unit_test", "command") or not get("unit_test", "result"):
        fail("unit_test.command/result must be recorded")

if idx >= SEQUENCE.index("VERIFIED"):
    if get("unit_test", "status") != "passed":
        fail("reaching VERIFIED+ requires unit_test.status=passed")
    if get("verification", "status") != "passed":
        fail("reaching VERIFIED+ requires verification.status=passed")
    if not get("verification", "evidence"):
        fail("verification.evidence is empty")
    if get("security", "status") not in ("completed", "not_applicable"):
        fail("reaching VERIFIED+ requires security.status=completed|not_applicable")
    if not get("security", "result"):
        fail("security.result is empty (record what was checked, or why it does not apply)")

# --- role gate (TASK-064): a task opted in via roles_required carries named
#     role-subagent evidence per phase; tasks without the key (legacy, incl.
#     TASK-064 itself) are exempt. Valid per-role value: a path under
#     work/<tid>/handoff/ that exists, or {"waiver": "<non-empty reason>"}. ---
if d.get("roles_required") is True:
    roles_tid = d.get("task_id")
    roles = d.get("roles") if isinstance(d.get("roles"), dict) else {}
    hint = f"work/{roles_tid}/handoff/"

    def check_role(role):
        val = roles.get(role)
        if isinstance(val, str) and val:
            if not os.path.normpath(val).startswith(hint):
                fail(f"roles.{role}='{val}' is not under {hint}")
                return
            full = os.path.join(root, val)
            if not os.path.isfile(full):
                fail(f"roles.{role}='{val}' does not exist (need a path under {hint} "
                     f"or {{\"waiver\": \"<reason>\"}})")
                return
            lines = open(full, encoding="utf-8").read().splitlines()
            line1 = lines[0] if len(lines) > 0 else ""
            line2 = lines[1] if len(lines) > 1 else ""
            if line1 != "PROGRESS: COMPLETE" or not re.match(r"^SKILLS: \S", line2):
                fail(f"role {role} handoff not complete: re-brief or waive")
        elif isinstance(val, dict):
            if not str(val.get("waiver", "")).strip():
                fail(f"roles.{role} waiver is empty (need a non-empty reason, or a path "
                     f"under {hint})")
        else:
            fail(f"roles.{role} is missing (need a path under {hint} or "
                 f"{{\"waiver\": \"<reason>\"}})")

    if get("design", "status") == "completed" or idx >= SEQUENCE.index("IMPLEMENTING"):
        check_role("designer")
    if get("implementation", "status") == "completed" or idx >= SEQUENCE.index("UNIT_TESTED"):
        check_role("coder")
    if idx >= SEQUENCE.index("VERIFIED"):
        check_role("verifier")
    if roles.get("tester") is not None:
        check_role("tester")

if idx >= SEQUENCE.index("DONE"):
    if get("verification", "status") != "passed":
        fail("DONE requires verification.status=passed")
    if get("report", "status") != "completed":
        fail("DONE requires report.status=completed")
    if not get("report", "path"):
        fail("report.path is empty")
    # report cross-check (TASK-095, REQ-0058): a task picked with crosscheck_required needs the cross-check
    # role's handoff (or a waiver) in roles.crosscheck; a handoff whose line 3 is "RESULT: MISS" blocks DONE.
    # Tasks without the key (picked before TASK-095) only get a WARN.
    if d.get("crosscheck_required") is True:
        if d.get("roles_required") is True:
            check_role("crosscheck")
        else:
            fail("crosscheck_required needs roles_required (roles.crosscheck is a role handoff)")
        cval = (d.get("roles") or {}).get("crosscheck") if isinstance(d.get("roles"), dict) else None
        if isinstance(cval, str) and cval:
            cfull = os.path.join(root, cval)
            if os.path.isfile(cfull):
                clines = open(cfull, encoding="utf-8").read().splitlines()
                if len(clines) > 2 and clines[2].strip() == "RESULT: MISS":
                    fail(f"roles.crosscheck='{cval}' reports RESULT: MISS: fix the generator (never the data), "
                         f"re-run the cross-check, then record the new handoff")
    else:
        warn("no report cross-check recorded (crosscheck_required not set; tasks picked after TASK-095 carry it)")
    # incident gate (TASK-124, 124.6): opt-in key incident:{ledger,guard,bite}
    inc = d.get("incident")
    if isinstance(inc, dict):
        ledger, iguard, ibite = (str(inc.get(k) or "") for k in ("ledger", "guard", "bite"))
        if not (ledger and iguard and ibite):
            fail("incident needs ledger, guard and bite")
        else:
            if not os.path.isfile(os.path.join(root, iguard)):
                fail(f"incident guard '{iguard}' does not exist")
            bp = os.path.join(root, ibite)
            if not os.path.isfile(bp):
                fail(f"incident bite '{ibite}' does not exist")
            elif "FAIL" not in open(bp, encoding="utf-8", errors="replace").read():
                fail(f"incident bite '{ibite}' has no FAIL line (the guard must fail on the old state)")
            ip = os.path.join(root, "docs/notes/incidents.md")
            rows = open(ip, encoding="utf-8").read().splitlines() if os.path.isfile(ip) else []
            if not any(r.startswith(f"| {ledger} |") for r in rows):
                fail(f"incident ledger row '{ledger}' not found in docs/notes/incidents.md")
    # plan checklist rows this task owns must be ticked (checklist.sh)
    import subprocess
    ck = os.path.join(root, ".claude/scripts/checklist.sh")
    if os.path.isfile(ck):
        gate = ["bash", ck, "--gate"]
        if re.fullmatch(r"TASK-[0-9]+", str(d.get("task_id") or "")):
            gate += ["--task", d["task_id"]]  # judge this task only, not every active one
        r = subprocess.run(gate, capture_output=True, text=True)
        for line in r.stdout.splitlines():
            fail(line[len("FAIL: "):] if line.startswith("FAIL: ") else line)

# --- doc paths (design skill convention): the task number IS the phase number,
#     so design and report are findable from task_id alone:
#     docs/design/phase-<N>-<slug>.md and docs/report/<same basename>. ---
PLAN_MODES_FROM = 47  # phase from which a design needs a "Plan modes" section
DESIGN_PATH = re.compile(r"^docs/design/phase-(\d+)-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
nums = re.findall(r"\d+", str(d.get("task_id") or ""))
phase = str(int(nums[-1])) if nums else None
dpath = get("design", "path") or ""
if get("design", "status") == "completed":
    if phase is None:
        fail(f"task_id '{d.get('task_id')}' has no number to derive the phase N of docs/design/phase-<N>-<slug>.md")
    else:
        want = f"docs/design/phase-{phase}-<slug>.md"
        m = DESIGN_PATH.match(dpath)
        if not m or m.group(1) != phase:
            fail(f"design.path='{dpath}' must be {want} (slug: lowercase words joined by '-')")
        elif not os.path.isfile(os.path.join(root, dpath)):
            fail(f"design.path='{dpath}' does not exist")
        elif int(phase) >= PLAN_MODES_FROM and not re.search(
                r"^#{2,3} .*Plan modes", open(os.path.join(root, dpath)).read(), re.M):
            # user, 2026-09-27: every design states its impact on both plan modes
            fail(f"design '{dpath}' has no '## Plan modes' section (impact on single-source and pipeline plans; design skill)")
# learn forward (TASK-124, 124.10): an incident row naming a file of this task needs "## Known incidents"
if get("design", "status") == "completed" and dpath and os.path.isfile(os.path.join(root, dpath)):
    import fnmatch
    ipath = os.path.join(root, "docs/notes/incidents.md")
    scope = [str(x) for x in (get("implementation", "files") or [])] + [str(x) for x in (d.get("scope") or [])]
    if os.path.isfile(ipath) and scope and not re.search(r"^#{2,3} Known incidents", open(os.path.join(root, dpath)).read(), re.M):
        for row in open(ipath, encoding="utf-8").read().splitlines():
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) < 6 or not re.fullmatch(r"I\d+", cells[0]):
                continue
            hit = None
            for tok in re.findall(r"[\w./*-]+\.(?:sh|py|json|conf|md)\b", cells[3] + " " + cells[4]):
                if any(fnmatch.fnmatch(tok, g) or fnmatch.fnmatch(g, tok) for g in scope):
                    hit = tok
                    break
            if hit:
                warn(f"incident {cells[0]} names {hit}, in this task's scope, but design '{dpath}' has no '## Known incidents' section")
if get("report", "status") == "completed" and DESIGN_PATH.match(dpath):
    rwant = "docs/report/" + os.path.basename(dpath)
    rpath = get("report", "path") or ""
    if rpath != rwant:
        fail(f"report.path='{rpath}' must be {rwant} (same basename as design.path)")
    elif not os.path.isfile(os.path.join(root, rpath)):
        fail(f"report.path='{rpath}' does not exist")

# --- backward invariants: a later phase cannot be finished while an earlier
#     one is not (catches a session that recorded phase N but never recorded
#     phase N-1 — the trail must stay monotonic regardless of `state`) ---
if get("implementation", "status") == "completed" and get("design", "status") != "completed":
    fail("implementation.status=completed but design.status!=completed (earlier phase not recorded)")
if get("unit_test", "status") == "passed" and get("implementation", "status") != "completed":
    fail("unit_test.status=passed but implementation.status!=completed (earlier phase not recorded)")
if get("verification", "status") == "passed" and get("unit_test", "status") != "passed":
    fail("verification.status=passed but unit_test.status!=passed (earlier phase not recorded)")
if get("report", "status") == "completed" and get("verification", "status") != "passed":
    fail("report.status=completed but verification.status!=passed (earlier phase not recorded)")

# --- state-vs-evidence drift: `state` must not lag behind what the recorded
#     evidence proves is finished. One phase behind = the "just finished,
#     about to transition / awaiting go-ahead" boundary (warn). Two or more
#     behind = a status update was clearly missed (fail). ---
implied = 0
if get("design", "status") == "completed":        implied = max(implied, SEQUENCE.index("DESIGN"))
if get("implementation", "status") == "completed": implied = max(implied, SEQUENCE.index("IMPLEMENTING"))
if get("unit_test", "status") == "passed":         implied = max(implied, SEQUENCE.index("UNIT_TESTED"))
if get("verification", "status") == "passed":      implied = max(implied, SEQUENCE.index("VERIFIED"))
if get("report", "status") == "completed":         implied = max(implied, SEQUENCE.index("DONE"))
drift = implied - idx
if drift == 1:
    warn(f"state={state} lags one phase behind recorded evidence "
         f"({SEQUENCE[implied]} looks done) — advance `state` once you move on, "
         f"or this reads as a missed status update")
elif drift >= 2:
    fail(f"state={state} but evidence shows {SEQUENCE[implied]} completed "
         f"({drift} phases ahead) — a status/state update was missed; "
         f"advance `state` or correct the phase statuses")

# --- blocker: optional side condition on a non-DONE state (never its own
#     state, so SEQUENCE stays monotonic). Present = work cannot proceed. ---
b = d.get("blocked")
if b is not None:
    if not isinstance(b, dict) or not str(b.get("reason", "")).strip():
        fail("blocked must be {\"reason\": \"<what stops progress>\", \"attempts\": <n>} (remove the key when unblocked)")
    elif state == "DONE":
        fail("state=DONE but 'blocked' is still set - remove it once the blocker is resolved")
    else:
        att = b.get("attempts", 0)
        if not isinstance(att, int) or att < 0:
            fail(f"blocked.attempts='{att}' must be a non-negative integer")
        elif att >= 3:
            warn(f"blocked after {att} attempts: stop retrying and ask the user ({b.get('reason')})")

# --- forward-planning: every non-terminal state records the next step ---
if state != "DONE" and not d.get("next"):
    fail("'next' must be non-empty while state != DONE (so any session/role can resume)")

# --- freshness / ownership: so a later session knows when and by whom the
#     status last moved, and can spot a stale/abandoned task ---
ts = d.get("updated_at", "")
if state != "TODO":
    if not ts:
        fail("updated_at is empty — stamp ISO8601 UTC (YYYY-MM-DDTHH:MM:SSZ) each time you change status")
    elif not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts):
        fail(f"updated_at='{ts}' is not ISO8601 UTC (YYYY-MM-DDTHH:MM:SSZ)")
    else:
        try:
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - dt).days
            if age_days > 14:
                warn(f"task last updated {age_days} days ago (updated_at={ts}) — may be stale/abandoned; confirm before continuing")
        except ValueError:
            pass
    if not d.get("updated_by"):
        warn("updated_by is empty — record which role/session last changed status (helps the next session)")

# --- phase log: complete audit trail from DESIGN up to the current state.
#     phase-log.md is shared by every task, so only headings tagged with a
#     task id count: '## <STATE> - <TASK-ID> - <ISO8601Z>'. Untagged entries
#     predate this rule and prove nothing about the active task. ---
HEADING = re.compile(r"^## ([A-Z_]+) - (\S+) - \S+[ \t]*$", re.M)
log_entries = set()  # (state, task_id)
# phase-log-archive*.md holds entries of finished tasks moved out of the live
# log (context-compaction skill); they still count for backlog 'done' audits.
import glob
for p in [log_path] + sorted(glob.glob(os.path.join(os.path.dirname(log_path), "phase-log-archive*.md"))):
    if os.path.isfile(p):
        log_entries |= {(m.group(1), m.group(2)) for m in HEADING.finditer(open(p).read())}
tid = d.get("task_id")
if state != "TODO":
    if not os.path.isfile(log_path):
        fail(f"phase log missing: {log_path} (restore it from git: git checkout -- .claude/state/phase-log.md)")
    else:
        for s in SEQUENCE[1:idx + 1]:
            if (s, tid) not in log_entries:
                fail(f"phase-log.md has no '## {s} - {tid} - <timestamp>' entry — incomplete "
                     f"audit trail (each transition records Action/Result/Decision/Next)")

# --- cross-file consistency: task.json vs backlog.json ---
if backlog_path and os.path.isfile(backlog_path):
    try:
        items = json.load(open(backlog_path))
        match = next((i for i in items if i.get("task_id") == tid), None)
        if match and state == "DONE" and match.get("status") != "done":
            fail(f"task.json state=DONE but backlog.json still lists {tid} as "
                 f"'{match.get('status')}' — run `.claude/scripts/backlog.sh complete {tid}`")
        elif match and match.get("status") not in ("active", "done") and state not in ("TODO",):
            warn(f"backlog.json lists {tid} as '{match.get('status')}' but it is the active "
                 f"task (state={state}); reconcile via backlog.sh pick, or mark it active")
        # A backlog item may be 'done' only if it really reached DONE (report
        # on disk + tagged DONE log entry) or was closed with an explicit,
        # recorded waiver (backlog.sh complete --force "<reason>").
        for it in items:
            if it.get("status") != "done" or it.get("waiver"):
                continue
            iid = it.get("task_id")
            rpt = it.get("report", "")
            if not rpt or not os.path.isfile(os.path.join(root, rpt)):
                fail(f"backlog {iid} is 'done' but has no existing report file "
                     f"(report='{rpt}') and no waiver — close it with backlog.sh complete")
            if ("DONE", iid) not in log_entries:
                fail(f"backlog {iid} is 'done' but phase-log.md has no '## DONE - {iid} - ...' entry")
        active = [i.get("task_id") for i in items if i.get("status") == "active"]
        if len(active) > 1 and not os.environ.get("WF_MULTI"):
            fail(f"backlog has {len(active)} active items {active}; only one task may be active")
        # User notes (REQ-0059): WARN only, never a FAIL.
        try:
            if state == "DONE" and d.get("user_notes"):
                rp = d.get("report", {}).get("path", "")
                rf = os.path.join(root, rp) if rp else ""
                if rf and os.path.isfile(rf) and "User instructions honoured:" not in open(rf, errors="replace").read():
                    warn(f"{tid} has user_notes but its report lacks a 'User instructions honoured:' line")
            raw_dir = os.path.join(root, os.environ.get("REQ_DIR", "docs/req"), "raw")
            picked = d.get("picked_at")
            if picked and os.path.isdir(raw_dir):
                pick_local = datetime.strptime(picked, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
                noted = {n.get("raw") for n in d.get("user_notes") or []}
                for it in items:
                    noted |= {n.get("raw") for n in it.get("user_notes") or []}
                req_dir = os.path.join(root, os.environ.get("REQ_DIR", "docs/req"), "items")

                def fm(text):
                    out = {}
                    for ln in text.split("---")[1].splitlines() if text.startswith("---") else []:
                        if ":" in ln:
                            k, v = ln.split(":", 1)
                            out[k.strip()] = v.strip()
                    return out

                def no_task_links(links):
                    reqs = re.findall(r"REQ-[0-9]{4}", links)
                    if not reqs:
                        return False
                    for r in reqs:
                        rp2 = os.path.join(req_dir, r + ".md")
                        if not os.path.isfile(rp2):
                            return False
                        tk = fm(open(rp2, errors="replace").read()).get("tasks", "")
                        if re.search(r"TASK-", tk):
                            return False
                    return True

                for fn in sorted(os.listdir(raw_dir)):
                    if not re.fullmatch(r"RAW-[0-9]{5}\.md", fn):
                        continue
                    try:
                        m = fm(open(os.path.join(raw_dir, fn), errors="replace").read())
                        created = datetime.strptime(m.get("created", ""), "%Y-%m-%d %H:%M")
                    except (ValueError, IndexError, OSError):
                        continue
                    rid = fn[:-3]
                    st = m.get("status")
                    if st not in ("TRIAGED", "IGNORED") or rid in noted:
                        continue
                    if created < pick_local.replace(second=0, microsecond=0):
                        continue
                    reason = m.get("reason", "").lower()
                    if st == "IGNORED" and ("not task-related" in reason or reason.startswith("short ack")):
                        continue
                    if st == "TRIAGED" and no_task_links(m.get("links", "")):
                        continue
                    warn(f"{rid} (triaged since {tid} pick) is in no task's user_notes: "
                         f"backlog.sh note active {rid} \"<line>\", or ignore it with reason 'not task-related'")
        except (ValueError, KeyError, TypeError, AttributeError, OSError):
            pass
    except (ValueError, KeyError, TypeError, AttributeError):
        fail(f"backlog.json is unreadable or malformed: {backlog_path}")

# --- report ---
for w in warns:
    print(f"WARN: {w}")
if fails:
    for f in fails:
        print(f"FAIL: {f}")
    raise SystemExit(1)
tail = f" ({len(warns)} warning(s))" if warns else ""
print(f"PASS: workflow state is consistent{tail}")
PY
}

TMODE="$(python3 "$SCRIPT_DIR/_tasks.py" mode)"
case "$TMODE" in
  legacy) run_body "$TASK" ;;
  mixed) echo "FAIL: mixed task state (task.<T>.json files without a schema-2 task.json); run .claude/scripts/tasks.sh migrate"; exit 1 ;;
  *)
    rc=0
    gout="$(python3 "$SCRIPT_DIR/_tasks.py" check)" || rc=1
    [ -z "$gout" ] || printf '%s\n' "$gout"
    if [ -n "$WANT" ]; then
      case "$WANT" in TASK-[0-9]*) ;; *) echo "FAIL: bad --task '$WANT'"; exit 1 ;; esac
      [ -f "$ROOT/.claude/state/task.$WANT.json" ] || { echo "FAIL: no task.$WANT.json"; exit 1; }
      ids="$WANT"
    else
      ids="$(python3 "$SCRIPT_DIR/_tasks.py" active)"
    fi
    n=0; for _ in $ids; do n=$((n + 1)); done
    for t in $ids; do
      out="$(WF_MULTI=1 run_body "$ROOT/.claude/state/task.$t.json" 2>&1)" || rc=1
      if [ "$n" -gt 1 ]; then printf '%s\n' "$out" | sed "s/^/$t: /"; else printf '%s\n' "$out"; fi
    done
    exit "$rc"
    ;;
esac

#!/usr/bin/env bash
# Deterministic pre-commit gate for this kit. Validates the STAGED tree and,
# when given a message file, the commit message trailers, then runs
# workflow-check.sh so a commit never records task.json/phase-log state that
# the workflow gate would reject. Run it right before `git commit`:
#
#     printf '%s\n' "...message..." > "$f"
#     .claude/scripts/commit-check.sh "$f" && git commit -q -F "$f"
#
# Exit 0 = safe to commit (WARN lines may still print). Exit 1 = do not commit;
# each FAIL line says what to fix. Exit 2 = usage/environment error.
#
# Composes, does not replace: workflow-check.sh (task.json/phase-log integrity)
# and the same secret patterns as checks/secrets.sh. It reads only; it writes
# nothing and runs no test suite (the coding/unit-test skills already do).
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPT_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPT_DIR")"
cd "$ROOT" || exit 2
git rev-parse --git-dir >/dev/null 2>&1 || { echo "not a git repo" >&2; exit 2; }

MSG_FILE=""; ARG_TASK=""
while [ $# -gt 0 ]; do
  case "$1" in
    --task) ARG_TASK="${2:-}"; shift 2 || { echo "--task needs TASK-N" >&2; exit 2; } ;;
    *) MSG_FILE="$1"; shift ;;
  esac
done
if [ -n "$MSG_FILE" ] && [ ! -f "$MSG_FILE" ]; then
  echo "message file not found: $MSG_FILE" >&2
  exit 2
fi

# --- compose the workflow gate first: the state being committed must be valid.
# Per-task state (REQ-0060): in multi mode the task is the `Task:` trailer or --task.
TMODE="$(python3 "$SCRIPT_DIR/_tasks.py" mode)"
TID="$ARG_TASK"
if [ -z "$TID" ] && [ "$TMODE" = multi ] && [ -n "$MSG_FILE" ]; then
  TID="$(git interpret-trailers --parse "$MSG_FILE" 2>/dev/null | sed -n 's/^Task: *\(TASK-[0-9][0-9]*\).*/\1/p' | head -n 1)"
fi
case "$TID" in ""|TASK-[0-9]*) ;; *) echo "bad --task '$TID'" >&2; exit 2 ;; esac
WF_OUT=""; WF_RC=0
if [ "$TMODE" = multi ] && [ -n "$TID" ]; then
  WF_OUT="$("$SCRIPT_DIR/workflow-check.sh" --task "$TID" 2>&1)" || WF_RC=$?
else
  WF_OUT="$("$SCRIPT_DIR/workflow-check.sh" 2>&1)" || WF_RC=$?
fi

python3 - "$MSG_FILE" "$WF_RC" "$WF_OUT" "$TMODE" "$TID" <<'PY'
import os, re, subprocess, sys

msg_file = sys.argv[1]
wf_rc = int(sys.argv[2])
wf_out = sys.argv[3]
tid = sys.argv[5]
multi = sys.argv[4] == "multi" and bool(tid)
state_file = ".claude/state/task.%s.json" % tid if multi else ".claude/state/task.json"
fails, warns = [], []

def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)

staged = [p for p in git("diff", "--cached", "--name-only").stdout.splitlines() if p]
if not staged:
    print("commit-check: nothing staged (git add first).", file=sys.stderr)
    sys.exit(2)

# --- A. forbidden paths (generated / env / editor noise; state JSON is tracked)
FORBIDDEN = [
    (r"(^|/)\.env(\.|$)",        "secret env file"),
    (r"(^|/)node_modules/",      "vendored deps"),
    (r"(^|/)dist/",              "build artifact"),
    (r"(^|/)build/",             "build artifact"),
    (r"(^|/)__pycache__/",       "bytecode"),
    (r"(^|/)\.pytest_cache/",    "pytest cache"),
    (r"(^|/)[^/]*\.egg-info/",   "packaging artifact"),
    (r"(^|/)\.DS_Store$",        "editor noise"),
]
for path in staged:
    for pat, why in FORBIDDEN:
        if re.search(pat, path):
            fails.append(f"forbidden path staged: {path}  ({why}) -- unstage it")
            break

# --- B. secrets in the added diff. Strong tokens FAIL; inline creds WARN.
#     Skip files that legitimately carry secret-shaped strings.
SKIP = re.compile(r"(^|/)(tests?/|docs/|\.claude/)|fixtures|\.md$")
STRONG = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key block"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"),               "AWS access key id"),
    (re.compile(r"\bghp_[0-9A-Za-z]{36}\b"),            "GitHub PAT"),
    (re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}"),     "Slack token"),
]
WEAK = re.compile(r'(api|secret)[_-]?key\s*[:=]\s*"[A-Za-z0-9/+_=-]{16,}"'
                  r'|password\s*[:=]\s*"[^"]{6,}"', re.I)
scan_paths = [p for p in staged if not SKIP.search(p)]
if scan_paths:
    diff = git("diff", "--cached", "-U0", "--", *scan_paths).stdout
    cur = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            for rx, label in STRONG:
                if rx.search(line):
                    fails.append(f"possible {label} in staged diff ({cur}) -- redact before committing")
            if WEAK.search(line):
                warns.append(f"possible inline credential in staged diff ({cur}) -- confirm it is a placeholder")

# --- E. model prompts are frozen (user rule, CLAUDE.md; phase 33): a staged prompt
#     change needs a `Prompt-change: <why no Python mapping can join the data>` trailer.
PROMPTS = re.compile(r"^(security_prompt\.md|docs/prompts/.+\.md)$")
prompt_paths = [p for p in staged if PROMPTS.search(p)]
if prompt_paths:
    reason = ""
    if msg_file:
        for ln in git("interpret-trailers", "--parse", msg_file).stdout.splitlines():
            if ln.lower().startswith("prompt-change:"):
                reason = ln.split(":", 1)[1].strip()
    if not reason:
        fails.append("model prompt staged (" + ", ".join(prompt_paths) + "): prompts are frozen "
                     "(CLAUDE.md). Map it in Python first, or add a `Prompt-change: <reason>` trailer")

# --- F. architecture stays current (user, RAW-00299; skill commit): engine-flow files staged
#     without docs/guide/architecture.md -> WARN only (never FAIL). `Arch-unchanged: <why>` silences it.
ENGINE = re.compile(r"^([^/]+\.(sh|py)|ext/.+)$")
engine_paths = [p for p in staged if ENGINE.search(p)]
if engine_paths and "docs/guide/architecture.md" not in staged:
    why = ""
    if msg_file:
        for ln in git("interpret-trailers", "--parse", msg_file).stdout.splitlines():
            if ln.lower().startswith("arch-unchanged:"):
                why = ln.split(":", 1)[1].strip()
    if not why:
        shown = ", ".join(engine_paths[:5]) + (" ..." if len(engine_paths) > 5 else "")
        warns.append(f"engine files staged ({shown}) without docs/guide/architecture.md: update the flow/step "
                     "table/chosen standard, or add an `Arch-unchanged: <why>` trailer")

# --- C. workflow gate result (task.json / phase-log integrity)
if wf_rc != 0:
    tail = "\n".join(f"    {l}" for l in wf_out.splitlines()[-8:])
    fails.append("workflow-check.sh failed for the state being committed:\n" + tail)

# --- D. message / trailer checks (only when a message file is supplied)
VALID = {"TODO", "DESIGN", "IMPLEMENTING", "UNIT_TESTED", "VERIFIED", "DONE"}
NEEDS = {"UNIT_TESTED": ("Tests", "command + result"),
         "VERIFIED":    ("Verified-by", "real-run command + observed result"),
         "DONE":        ("Report", "report path")}

def staged_task_state():
    out = git("show", ":" + state_file)
    if out.returncode != 0:
        return None
    import json
    try:
        return json.loads(out.stdout).get("state")
    except json.JSONDecodeError:
        return "<unparseable>"

if msg_file:
    trailers = {}
    parsed = git("interpret-trailers", "--parse", msg_file).stdout
    for ln in parsed.splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            trailers.setdefault(k.strip(), []).append(v.strip())

    # git only parses the LAST paragraph as trailers, so a blank line between
    # `Task:`/`State:` and `Co-Authored-By:` silently hides them and every
    # check below would be skipped. Catch workflow keys the parser missed.
    WORKFLOW_KEYS = ("Task", "State", "Tests", "Verified-by", "Report", "Prompt-change")
    raw = [ln for ln in open(msg_file).read().splitlines() if not ln.startswith("#")]
    missed = sorted({k for ln in raw for k in WORKFLOW_KEYS
                     if re.match(rf"{k}:\s*\S", ln) and k not in trailers})
    if missed:
        fails.append(f"{', '.join(missed)} not parsed as trailer(s): the trailer block is split "
                     f"(blank line before Co-Authored-By?) -- make it one block, attribution last")

    if "Task" in trailers:
        state = (trailers.get("State") or [""])[0]
        if not state:
            fails.append("task commit missing `State:` trailer")
        elif state not in VALID:
            fails.append(f"`State: {state}` is not one of {sorted(VALID)}")
        elif state in NEEDS and NEEDS[state][0] not in trailers:
            key, what = NEEDS[state]
            fails.append(f"`State: {state}` needs a `{key}:` trailer ({what})")

        if multi:
            gone = set(git("diff", "--cached", "--name-only", "--diff-filter=D").stdout.split())
            for sp in staged:
                m = re.fullmatch(r"\.claude/state/task\.(TASK-[0-9]+)\.json", sp)
                if m and m.group(1) != tid and sp not in gone:
                    fails.append("one task per commit: %s is staged but this commit is for %s" % (sp, tid))
        if state_file not in staged:
            fails.append("task commit must stage %s (its persisted state)" % state_file)
        else:
            st = staged_task_state()
            if st is None:
                warns.append("could not read staged task.json state")
            elif state and st != state:
                fails.append(f"state drift: trailer says {state} but staged task.json says {st}")
        if ".claude/state/phase-log.md" not in staged:
            warns.append("phase-log.md not staged: record Action->Result->Decision->Next for a phase transition")

        # workflow-check.sh read the WORKING TREE; its verdict only holds for
        # this commit if the workflow files are fully staged. Otherwise HEAD
        # can record DONE with backlog.json still 'active' or no report file.
        porcelain = git("status", "--porcelain", "--",
                        ".claude/state", "docs/design", "docs/report").stdout
        partial = [l[3:] for l in porcelain.splitlines()
                   if l.startswith("??") or (len(l) > 1 and l[1] != " ")]
        if multi:
            # Other tasks' own files and docs are theirs to commit (REQ-0060).
            import json
            others = set()
            for fn in os.listdir(".claude/state"):
                m = re.fullmatch(r"task\.(TASK-[0-9]+)\.json", fn)
                if m and m.group(1) != tid:
                    others.add(".claude/state/" + fn)
                    try:
                        u = json.load(open(".claude/state/" + fn))
                        others.add((u.get("design") or {}).get("path", ""))
                        others.add((u.get("report") or {}).get("path", ""))
                    except (OSError, ValueError, AttributeError):
                        pass
            others.discard("")
            # A design/report named for another phase number is that task's (98.8);
            # T's own phase files, the view, phase-log.md and backlog.json stay covered.
            mine = int(re.sub(r"\D", "", tid) or 0)
            def _foreign_phase_doc(x):
                m2 = re.fullmatch(r"docs/(?:design|report)/phase-([0-9]+)-.*", x)
                return bool(m2) and int(m2.group(1)) != mine
            partial = [x for x in partial if x not in others and not _foreign_phase_doc(x)]
        if partial:
            fails.append("workflow files changed but not staged (git add them; the gate checked "
                         "the working tree): " + ", ".join(partial))
    else:
        for k in ("State", "Tests", "Verified-by"):
            if k in trailers:
                warns.append(f"non-task commit carries `{k}:` but no `Task:` -- add Task or drop the trailer")
else:
    warns.append("no message file passed: trailer/state checks skipped (staged-tree + workflow checks still ran)")

# --- report
for w in warns:
    print(f"WARN: {w}", file=sys.stderr)
for f in fails:
    print(f"FAIL: {f}", file=sys.stderr)
if fails:
    print(f"commit-check: {len(fails)} problem(s) -- do not commit yet.", file=sys.stderr)
    sys.exit(1)
print("commit-check: OK" + (f" ({len(warns)} warning(s))" if warns else ""), file=sys.stderr)
sys.exit(0)
PY

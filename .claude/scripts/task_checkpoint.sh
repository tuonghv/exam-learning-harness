#!/usr/bin/env bash
# Pending-question record (REQ-0038, REQ-0060 AC7; .claude/state/pending.json) and its timeout
# check. A waiting task stays active; due/brief name the other active tasks to work on.
#   task_checkpoint.sh ask <TASK> --question T --recommend T --kind paid|permission|block
#                                     # record a pending question; only user-only kinds (RAW-00511)
#   task_checkpoint.sh answer <Q-id> T
#   task_checkpoint.sh due            # DUE rows for questions past the timeout; rc 3 if any unheld
#   task_checkpoint.sh watch <Q-id>   # read-only poll: rc 0 answered, 3 due, 4 gone/held, 1 still waiting, 2 usage
#   task_checkpoint.sh brief          # action lines only, always rc 0 (hooks, team-status)
# Env: TASK_CHECKPOINT_TIMEOUT_MIN (default 10), TASK_CHECKPOINT_NOW (epoch, tests),
#      TASK_CHECKPOINT_POLL_SEC (watch, default 30, 0-120; 0 = one pass, which ends rc 1 WAITING if not yet due).
# Multi mode (task.json schema 2): ask needs T to be an active task. Legacy: no such check.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPT_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPT_DIR")"

python3 - "$ROOT" "$@" <<'PY'
import calendar, json, os, re, subprocess, sys, time
from datetime import datetime, timezone

root, cmd, *args = sys.argv[1:] if len(sys.argv) > 2 else (sys.argv[1], "")
ST = os.path.join(root, ".claude", "state")
PJ = os.path.join(ST, "pending.json")
TASKS = os.path.join(root, ".claude", "scripts", "_tasks.py")

USAGE = """Usage:
  task_checkpoint.sh ask <TASK> --question T --recommend T --kind paid|permission|block
  task_checkpoint.sh answer <Q-id> T
  task_checkpoint.sh watch <Q-id>
  task_checkpoint.sh due | brief"""

def die(msg, rc=1):
    print(("FAIL: " if rc == 1 else "USAGE: ") + msg, file=sys.stderr)
    raise SystemExit(rc)

def usage():
    print(USAGE, file=sys.stderr)
    raise SystemExit(2)

def now():
    v = os.environ.get("TASK_CHECKPOINT_NOW", "")
    if v:
        if not re.fullmatch(r"[0-9]+", v):
            die("bad TASK_CHECKPOINT_NOW (want epoch seconds)", 2)
        return int(v)
    return int(time.time())

def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def epoch(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))

def timeout_min():
    v = os.environ.get("TASK_CHECKPOINT_TIMEOUT_MIN", "10")
    if not re.fullmatch(r"[0-9]+", v) or int(v) < 1:
        die("bad TASK_CHECKPOINT_TIMEOUT_MIN (want an integer >= 1)", 2)
    return int(v)

def tid_ok(t):
    if not re.fullmatch(r"TASK-[0-9]+", t or ""):
        die(f"bad task id '{(t or '')[:20]}' (want TASK-NNN)", 2)
    return t

UNSAFE = (r"https?://", r"www\.", r"-----BEGIN", r"AKIA[0-9A-Z]{16}",
          r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]", r"[A-Za-z0-9+/=_-]{32,}")

def text_ok(label, t):
    if not t or not t.strip():
        die(f"{label} is empty", 2)
    if len(t) > 200:
        die(f"{label} is longer than 200 characters", 2)
    if re.search(r"[\x00-\x1f\x7f]", t):
        die(f"{label} must be one line without control characters", 2)
    if any(re.search(p, t) for p in UNSAFE):
        die(f"{label} looks like a URL or a secret; write a short sentence in your own words", 2)
    return t

def clean(s):
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(s))

def read_json(p, what):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        die(f"unreadable {what} ({os.path.relpath(p, root)})")

def write_json(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = "%s.%d.%s.tmp" % (p, os.getpid(), os.urandom(4).hex())
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, p)

def state_lock():
    """The shared state lock (97.12): a pending.json read-modify-write runs under it."""
    import contextlib
    sys.dont_write_bytecode = True
    os.environ["TASKS_ROOT"] = root
    sys.path.insert(0, os.path.dirname(TASKS))
    import _tasks
    if not os.path.isdir(os.path.dirname(_tasks._lock_dir())):
        return contextlib.nullcontext() if hasattr(contextlib, "nullcontext") else contextlib.suppress()
    return _tasks.locked()

def load_pending():
    if not os.path.isfile(PJ):
        return []
    data = read_json(PJ, "pending.json")
    if not isinstance(data, list):
        die("pending.json is not a list")
    return data

def parse_opts(argv, allowed, nargs_pos):
    pos, opts, i = [], {}, 0
    while i < len(argv):
        a = argv[i]
        if a in allowed:
            if i + 1 >= len(argv):
                usage()
            opts[a] = argv[i + 1]
            i += 2
        elif a.startswith("--"):
            usage()
        else:
            pos.append(a)
            i += 1
    if len(pos) != nargs_pos:
        usage()
    return pos, opts

def multi_active():
    """(multi mode?, [(task_id, state, next)] for the active tasks) via the resolver."""
    env = dict(os.environ, TASKS_ROOT=root)
    try:
        m = subprocess.run([sys.executable, TASKS, "mode"], capture_output=True, text=True, env=env)
        if m.stdout.strip() != "multi":
            return False, []
        a = subprocess.run([sys.executable, TASKS, "active"], capture_output=True, text=True, env=env)
    except OSError:
        return False, []
    rows = []
    for t in a.stdout.split():
        try:
            with open(os.path.join(ST, f"task.{t}.json")) as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        rows.append((t, d.get("state", ""), d.get("next", "")))
    return True, rows

KINDS = ("paid", "permission", "block")

def task_held(t):
    try:
        with open(os.path.join(ST, f"task.{t}.json")) as f:
            return json.load(f).get("status") == "held"
    except (OSError, ValueError, AttributeError):
        return False

def held_min(t):
    try:
        with open(os.path.join(ST, f"task.{t}.json")) as f:
            return max(0, (now() - epoch(json.load(f).get("held_at"))) // 60)
    except (OSError, ValueError, AttributeError, TypeError):
        return 0

def work_on(task):
    """`work on:` lines for the active tasks other than the one that waits."""
    return [f"work on: {clean(u)} ({clean(s)}; {clean(n)[:60]})"
            for u, s, n in multi_active()[1] if u != task]

# ---------------------------------------------------------------- pending
def cmd_ask():
    pos, o = parse_opts(args, ("--question", "--recommend", "--kind"), 1)
    t = tid_ok(pos[0])
    if "--question" not in o or "--recommend" not in o:
        usage()
    if o.get("--kind") not in KINDS:
        die("not a user-only question: decide it with the recommended option (RAW-00511)", 2)
    text_ok("question", o["--question"]); text_ok("recommendation", o["--recommend"])
    multi, act = multi_active()
    if multi and t not in [u for u, _, _ in act]:
        die(f"{t} is not an active task; only an active task can wait on a question")
    try:
        with state_lock():
            pend = load_pending()
            n = now()
            while any(e.get("id") == f"Q-{n}" for e in pend):
                n += 1
            pend.append({"id": f"Q-{n}", "task_id": t, "question": o["--question"],
                         "recommendation": o["--recommend"], "kind": o["--kind"], "asked_at": iso(now())})
            write_json(PJ, pend)
    except ValueError as ex:
        die(str(ex))
    print(f"ASKED: Q-{n} ({t})")
    print("Stage: .claude/state/pending.json")

def cmd_answer():
    if len(args) != 2:
        usage()
    qid, text = args
    if not re.fullmatch(r"Q-[0-9]+", qid):
        die(f"bad question id '{qid[:20]}' (want Q-<epoch>)", 2)
    text_ok("answer", text)
    try:
        with state_lock():
            pend = load_pending()
            e = next((x for x in pend if x.get("id") == qid), None)
            if e is None:
                die(f"no pending question {qid}")
            if e.get("answered_at"):
                die(f"{qid} is already answered")
            e["answered_at"], e["answer"] = iso(now()), text
            write_json(PJ, pend)
    except ValueError as ex:
        die(str(ex))
    print(f"ANSWERED: {qid} ({e.get('task_id')})")
    print("Stage: .claude/state/pending.json")
    if task_held(str(e.get("task_id"))):
        print(f"then: resume {e.get('task_id')} at the next safe point (tasks.sh resume {e.get('task_id')}; slot needed)")

def due_rows():
    tmo, n = timeout_min(), now()
    rows = []
    for e in load_pending():
        if e.get("answered_at"):
            continue
        try:
            age = n - epoch(e.get("asked_at"))
        except (ValueError, TypeError):
            continue
        if age >= tmo * 60:
            if task_held(str(e.get("task_id"))):
                rows.append(f"HELD {e.get('task_id')} {e.get('id')} age={age // 60}m")
                continue
            rows.append(f"DUE {e.get('task_id')} {e.get('id')} age={age // 60}m")
            rows.extend(work_on(str(e.get("task_id"))))
    return rows

def cmd_due():
    rows = due_rows()
    for r in rows:
        print(r)
    raise SystemExit(3 if any(r.startswith("DUE ") for r in rows) else 0)

def cmd_watch():
    """100.5: read-only poll of one question, no model call. rc 0 answered, 3 due, 4 gone or held, 1 still waiting."""
    if len(args) != 1:
        usage()
    qid = args[0]
    if not re.fullmatch(r"Q-[0-9]+", qid):
        die(f"bad question id '{qid[:20]}' (want Q-<epoch>)", 2)
    v = os.environ.get("TASK_CHECKPOINT_POLL_SEC", "30")
    if not re.fullmatch(r"[0-9]+", v) or int(v) > 120:
        die("bad TASK_CHECKPOINT_POLL_SEC (want an integer 0-120)", 2)
    poll, tmo = int(v), timeout_min()
    first = now()
    while True:
        e = next((x for x in load_pending() if x.get("id") == qid), None)
        if e is None:
            print(f"GONE {qid}")
            raise SystemExit(4)
        if e.get("answered_at"):
            print(f"ANSWERED {qid}")
            raise SystemExit(0)
        t = clean(e.get("task_id"))
        if task_held(t):
            print(f"HELD {t} {qid}")
            raise SystemExit(4)
        try:
            age = now() - epoch(e.get("asked_at"))
        except (ValueError, TypeError):
            age = 0
        if age >= tmo * 60:
            print(f"DUE {t} {qid} age={age // 60}m")
            print(f"run: tasks.sh autohold {t} {qid}")
            raise SystemExit(3)
        if poll == 0 or now() - first > tmo * 60 + 2 * poll:
            print(f"WAITING {t} {qid} age={max(age, 0) // 60}m")
            raise SystemExit(1)
        time.sleep(poll)

def cmd_brief():
    try:
        pend = load_pending()
    except SystemExit:
        pend = []
    held = []
    for e in pend:
        t = clean(e.get("task_id"))
        if not e.get("answered_at") and task_held(t):
            held.append(e)
            print(f"Your turn: answer {clean(e.get('id'))} ({t}, held {held_min(t)}m) "
                  f"{clean(e.get('question'))[:100]} Recommended: {clean(e.get('recommendation'))[:100]}; "
                  f"then tasks.sh res" f"ume {t}")
    try:
        for r in due_rows():
            print(r)
    except SystemExit:
        pass
    for e in pend:
        if not e.get("answered_at") and e not in held:
            print(f"Your turn: answer {clean(e.get('id'))} ({clean(e.get('task_id'))}) "
                  f"{clean(e.get('question'))[:100]} Recommended: {clean(e.get('recommendation'))[:100]}")

DISPATCH = {"ask": cmd_ask, "answer": cmd_answer, "due": cmd_due, "brief": cmd_brief, "watch": cmd_watch}
if cmd not in DISPATCH:
    usage()
if cmd in ("due", "brief") and args:
    usage()
DISPATCH[cmd]()
PY

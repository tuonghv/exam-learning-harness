#!/usr/bin/env python3
"""Per-task workflow state (REQ-0060, phase 96). Stdlib only.

Layout: .claude/state/task.<TASK>.json holds one task; task.json becomes a
schema-2 view written only by `sync`. No task.<T> file and no schema = legacy
mode (today's single task.json). Both present in a mixed way = `migrate`.

CLI: python3 _tasks.py mode|max|active|path T|view|sync|overlap A B|check|
     list|scope T [--set g,..|--add g,..]|migrate|status|hold T --reason R|resume T|show T|
     stale T|inputs T [--set p,..|--rehash --reason R]|question T [--set N|--answer|--decide TEXT --reason R]
"""
import fnmatch
import json
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True

ROOT = os.environ.get("TASKS_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ST = os.path.join(ROOT, ".claude", "state")
VIEW = os.path.join(ST, "task.json")
BACKLOG = os.path.join(ST, "backlog.json")
ID_RE = re.compile(r"TASK-[0-9]+")
FILE_RE = re.compile(r"task\.(TASK-[0-9]+)\.json")
EXCLUDED = (".claude/state/", "docs/req/", "docs/design/", "docs/report/", "work/")
MAX_SCOPE = 20


def max_active():
    """Env WORKFLOW_MAX_ACTIVE, else .claude/workflow.json max_active, else 3 (valid: 1-9)."""
    raw = os.environ.get("WORKFLOW_MAX_ACTIVE")
    if raw is None:
        cfg = read_json(os.path.join(ROOT, ".claude", "workflow.json"), {})
        raw = cfg.get("max_active", 3) if isinstance(cfg, dict) else 3
    try:
        n = int(raw)
    except (ValueError, TypeError):
        return 3
    return n if 1 <= n <= 9 else 3


def task_path(t):
    if not isinstance(t, str) or not ID_RE.fullmatch(t):
        raise ValueError("bad task id %r (want TASK-NNN)" % str(t)[:20])
    return os.path.join(ST, "task.%s.json" % t)


def read_json(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(p, obj):
    """Unique tmp in the same dir, fsync, then atomic replace (96.18)."""
    tmp = "%s.%d.%s.tmp" % (p, os.getpid(), os.urandom(4).hex())
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


LOCK_STALE_S = 600
LOCK_NOOWNER_S = 5


def _lock_dir(name="tasks-state.lock"):
    r = subprocess.run(["git", "-C", ROOT, "rev-parse", "--git-dir"], capture_output=True, text=True)
    g = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else ".git"
    if not os.path.isabs(g):
        g = os.path.join(ROOT, g)
    return os.path.join(g, name)


def _proc_start(pid):
    """Field 22 of /proc/<pid>/stat (start time in ticks), or None without /proc."""
    try:
        with open("/proc/%d/stat" % pid, encoding="utf-8") as f:
            return int(f.read().rsplit(")", 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _dead_reason(path):
    """Why the lock dir may be broken, or None when its owner still holds it."""
    import time
    try:
        age = time.time() - os.path.getmtime(path)
    except OSError:
        return None
    try:
        with open(os.path.join(path, "owner.json"), encoding="utf-8") as f:
            own = json.load(f)
        pid = int(own["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return "no_owner" if age > LOCK_NOOWNER_S else None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "pid_gone"
    except OSError:
        pass
    st = own.get("start")
    if st is not None:
        now = _proc_start(pid)
        if now is not None and now != st:
            return "pid_reused"
    if age >= LOCK_STALE_S:
        return "stale"
    return None


def _break_lock(path, reason):
    """Rename away (atomic: one waiter wins), log, remove. True when this process broke it."""
    import shutil
    import time
    dead = "%s.broken.%d.%s" % (path, os.getpid(), os.urandom(3).hex())
    try:
        own = read_json(os.path.join(path, "owner.json"), None)
    except OSError:
        own = None
    try:
        os.rename(path, dead)
    except OSError:
        return False
    if _dead_reason(dead) is None:
        # a waiter replaced the lock between our check and the rename: put the live one back
        try:
            os.rename(dead, path)
        except OSError:
            pass
        return False
    try:
        with open(os.path.join(os.path.dirname(path), "tasks-locks.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "lock": os.path.basename(path), "owner": own, "reason": reason,
                                "by_pid": os.getpid()}) + "\n")
    except OSError:
        pass
    shutil.rmtree(dead, ignore_errors=True)
    return True


class locked(object):
    """mkdir lock .git/<name> with owner.json; a dead, reused or over-age (10 min) owner is broken (97.12)."""

    def __init__(self, wait=30.0, name="tasks-state.lock", task=None):
        try:
            wait = float(os.environ.get("TASKS_LOCK_WAIT", wait))
        except ValueError:
            pass
        self.wait, self.name, self.task, self.path = wait, name, task, None

    def _owner(self):
        pid = os.getpid()
        import time
        o = {"pid": pid, "start": _proc_start(pid), "task": self.task,
             "role": os.environ.get("CTXGUARD_ROLE") or "main",
             "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        try:
            write_json(os.path.join(self.path, "owner.json"), o)
        except OSError:
            pass

    def __enter__(self):
        import time
        path = _lock_dir(self.name)
        end = time.time() + self.wait
        while True:
            try:
                os.mkdir(path)
                self.path = path
                self._owner()
                return self
            except FileExistsError:
                why = _dead_reason(path)
                if why and _break_lock(path, why):
                    continue
                if time.time() > end:
                    raise ValueError("another tasks.sh command holds %s; retry, or remove it if older than 10 min" % path)
                time.sleep(0.05)
            except OSError as e:
                raise ValueError("cannot create lock %s: %s" % (path, e))

    def __exit__(self, *a):
        if self.path:
            own = read_json(os.path.join(self.path, "owner.json"), None)
            if isinstance(own, dict) and own.get("pid") == os.getpid():
                import shutil
                dead = "%s.broken.%d.%s" % (self.path, os.getpid(), os.urandom(3).hex())
                try:
                    os.rename(self.path, dead)
                    shutil.rmtree(dead, ignore_errors=True)
                except OSError:
                    pass
        return False


def task_ids():
    out = []
    for fn in (os.listdir(ST) if os.path.isdir(ST) else []):
        m = FILE_RE.fullmatch(fn)
        if m:
            out.append(m.group(1))
    return sorted(out, key=lambda t: int(t[5:]))


def backlog_items():
    b = read_json(BACKLOG, [])
    return [i for i in b if isinstance(i, dict)] if isinstance(b, list) else []


def active_ids():
    """Task files whose backlog item is not done (DONE-but-not-completed still counts)."""
    return [t for t in scope_ids() if load(t).get("status") != "held"]


def scope_ids():
    """Active plus held tasks: the set whose file scopes still count for overlap (B2)."""
    done = {i.get("task_id") for i in backlog_items() if i.get("status") == "done"}
    return [t for t in task_ids() if t not in done]


def mode():
    tj = read_json(VIEW)
    if isinstance(tj, dict) and tj.get("schema") == 2:
        return "multi"
    return "mixed" if task_ids() else "legacy"


def load(t):
    """Strict: a task file that exists but does not parse as a JSON object is an error naming it."""
    p = task_path(t)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError("corrupt %s: %s" % (os.path.relpath(p, ROOT), str(e)[:80]))
    if not isinstance(d, dict):
        raise ValueError("corrupt %s: not a JSON object" % os.path.relpath(p, ROOT))
    return d


def _stamp(d):
    return (d.get("updated_at") or d.get("picked_at") or "", d.get("task_id") or "")


def view():
    ids = active_ids()
    pool = ids or task_ids()
    tasks = [load(t) for t in pool]
    focus = max(tasks, key=_stamp) if tasks else {}
    return {
        "schema": 2,
        "task_id": focus.get("task_id", ""),
        "state": focus.get("state", ""),
        "next": focus.get("next", ""),
        "title": focus.get("title", ""),
        "active": [{"task_id": t, "state": load(t).get("state", ""), "next": load(t).get("next", ""),
                    "updated_at": load(t).get("updated_at", "")} for t in ids],
        "max_active": max_active(),
    }


def sync():
    v = view()
    if read_json(VIEW) == v:
        return False
    write_json(VIEW, v)
    return True


def check_scope(globs):
    if not isinstance(globs, list) or not all(isinstance(g, str) for g in globs):
        return "scope must be a list of glob strings"
    if len(globs) > MAX_SCOPE:
        return "scope has %d globs (max %d)" % (len(globs), MAX_SCOPE)
    for g in globs:
        if not g or not g.isprintable() or ".." in g or g.startswith("/"):
            return "bad scope glob %r (printable, relative, no '..')" % g[:40]
    return None


def _norm(g):
    return g + "*" if g.endswith("/") else g


def _tracked():
    r = subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return [p for p in r.stdout.splitlines() if p and not p.startswith(EXCLUDED)]


def overlap(a, b):
    """First shared match of two glob lists, or None."""
    ga = [_norm(g) for g in a if not g.startswith(EXCLUDED)]
    gb = [_norm(g) for g in b if not g.startswith(EXCLUDED)]
    if not ga or not gb:
        return None
    for x in ga:
        for y in gb:
            if x == y or fnmatch.fnmatchcase(x, y) or fnmatch.fnmatchcase(y, x):
                return "%s ~ %s" % (x, y)
    for f in _tracked():
        ma = next((g for g in ga if fnmatch.fnmatchcase(f, g)), None)
        mb = next((g for g in gb if fnmatch.fnmatchcase(f, g)), None) if ma else None
        if ma and mb:
            return "%s (%s ~ %s)" % (f, ma, mb)
    return None


def scope_of(t):
    s = load(t).get("scope", [])
    return s if isinstance(s, list) else []


AUTO_GRANT_ROLES = ("coder", "tester")


def grants_for(scope):
    """98.4: scope globs that fall inside protect.grantable (e.g. .claude/scripts/foo.sh); never wider."""
    cfg = read_json(os.path.join(ROOT, ".claude", "agent_setup.json"), {})
    gr = ((cfg.get("protect") or {}).get("grantable")) if isinstance(cfg, dict) else None
    gr = [g for g in (gr or []) if isinstance(g, str)]
    return [g for g in scope if isinstance(g, str) and ".." not in g
            and any(fnmatch.fnmatchcase(g, x) for x in gr)]


def apply_auto_grants(d, scope):
    """Set roles.grants for coder/tester from scope; entries added earlier (roles.grants_auto) that left the scope go."""
    roles = d.setdefault("roles", {})
    old_auto = roles.get("grants_auto") if isinstance(roles.get("grants_auto"), list) else []
    auto = grants_for(scope)
    gr = roles.get("grants") if isinstance(roles.get("grants"), dict) else {}
    for r in AUTO_GRANT_ROLES:
        cur = [g for g in (gr.get(r) if isinstance(gr.get(r), list) else []) if g not in old_auto]
        cur += [g for g in auto if g not in cur]
        if cur:
            gr[r] = cur
        else:
            gr.pop(r, None)
    if gr:
        roles["grants"] = gr
    else:
        roles.pop("grants", None)
    if auto:
        roles["grants_auto"] = auto
    else:
        roles.pop("grants_auto", None)


MAX_INPUTS = 30
GATED = ("IMPLEMENTING", "UNIT_TESTED", "VERIFIED")


def _rel_input(path):
    """Repo-relative path of a toolkit input, or raise ValueError (inside repo, a regular file)."""
    if not path or not path.isprintable():
        raise ValueError("bad input path")
    real = os.path.realpath(os.path.join(ROOT, path))
    root = os.path.realpath(ROOT)
    if real != root and not real.startswith(root + os.sep):
        raise ValueError("input %r is outside the repo" % path[:60])
    rel = os.path.relpath(real, root)
    parts = rel.split(os.sep)
    if parts[0] == ".git" or any(fnmatch.fnmatchcase(x, "pentest_source_code*") or x.endswith(".link")
                                 for x in parts):
        raise ValueError("input %r is a source tree or link path" % path[:60])
    rp = os.environ.get("REPOS_ROOT")
    if rp and (real + os.sep).startswith(os.path.realpath(rp) + os.sep):
        raise ValueError("input %r is under REPOS_ROOT" % path[:60])
    if not os.path.isfile(real):
        raise ValueError("input %r is not a file" % path[:60])
    return rel


def _sha(rel):
    import hashlib
    h = hashlib.sha256()
    with open(os.path.join(ROOT, rel), "rb") as f:
        for blk in iter(lambda: f.read(65536), b""):
            h.update(blk)
    return h.hexdigest()


def stale_list(t):
    """Inputs of t whose hash changed or whose file vanished: [(path, why)]."""
    inp = load(t).get("inputs")
    out = []
    for rel, h in sorted((inp if isinstance(inp, dict) else {}).items()):
        full = os.path.join(ROOT, rel)
        if not os.path.isfile(full):
            out.append((rel, "missing"))
        elif _sha(rel) != h:
            out.append((rel, "changed"))
    return out


def cmd_inputs(args):
    usage = 'usage: inputs TASK-N [--set p1,p2 | --rehash --reason "<designer delta: NOT AFFECTED|updated>"]'
    if not args:
        print(usage)
        return 2
    t = args[0]
    p = task_path(t)
    if not os.path.isfile(p):
        print("FAIL: %s is not an active task" % t)
        return 1
    d = load(t)
    cur = d.get("inputs") if isinstance(d.get("inputs"), dict) else {}
    if len(args) == 1:
        for rel in sorted(cur):
            print("%s %s" % (cur[rel][:12], rel))
        if not cur:
            print("(no inputs recorded)")
        return 0
    if args[1] == "--set" and len(args) == 3:
        names = [x.strip() for x in args[2].split(",") if x.strip()]
        dp = (d.get("design") or {}).get("path") if isinstance(d.get("design"), dict) else ""
        if dp and dp not in names:
            names.append(dp)
        rels = []
        for n in names:
            r = _rel_input(n)
            if r not in rels:
                rels.append(r)
        if len(rels) > MAX_INPUTS:
            print("FAIL: %d inputs (max %d)" % (len(rels), MAX_INPUTS))
            return 1
        d["inputs"] = dict((r, _sha(r)) for r in rels)
        write_json(p, d)
        print("inputs of %s: %d file(s) hashed" % (t, len(rels)))
        return 0
    if args[1] == "--rehash":
        reason = _opt(args, "--reason")
        if not reason or not reason.strip():
            print('FAIL: --rehash needs --reason "<designer delta: NOT AFFECTED|updated>"')
            return 1
        names = sorted(cur)
        dp = (d.get("design") or {}).get("path") if isinstance(d.get("design"), dict) else ""
        if dp and dp not in names:
            names.append(dp)
        d["inputs"] = dict((r, _sha(_rel_input(r))) for r in names)
        rev = d.get("inputs_reviews") if isinstance(d.get("inputs_reviews"), list) else []
        rev.append({"at": now(), "reason": _txt(reason, 200)})
        d["inputs_reviews"] = rev
        write_json(p, d)
        print("rehashed %d input(s) of %s; reason kept in inputs_reviews" % (len(d["inputs"]), t))
        return 0
    print(usage)
    return 2


def cmd_stale(args):
    if len(args) != 1:
        print("usage: stale TASK-N")
        return 2
    t = args[0]
    if not os.path.isfile(task_path(t)):
        print("FAIL: %s is not an active task" % t)
        return 1
    s = stale_list(t)
    if not s:
        print("OK: inputs of %s unchanged (%d file(s))" % (t, len(load(t).get("inputs") or {})))
        return 0
    print("STALE: %s inputs changed since they were hashed:" % t)
    for rel, why in s[:10]:
        print("  %s (%s)" % (rel, why))
    print('Ask the designer for a delta, then: tasks.sh inputs %s --rehash --reason "NOT AFFECTED|updated: <what>"' % t)
    return 4


def check():
    """Global checks over every active task: (fails, warns)."""
    fails, warns = [], []
    ids = active_ids()
    if len(ids) > max_active():
        fails.append("%d active tasks %s exceed max_active=%d" % (len(ids), ids, max_active()))
    items = {i.get("task_id"): i for i in backlog_items()}
    for t in ids:
        it = items.get(t)
        if it is None:
            fails.append("%s has task.%s.json but no backlog item" % (t, t))
        elif it.get("status") not in ("active", "done"):
            fails.append("task.%s.json exists but backlog lists %s as '%s'" % (t, t, it.get("status")))
        if load(t).get("task_id") != t:
            fails.append("task.%s.json holds task_id=%s" % (t, load(t).get("task_id")))
    sids = scope_ids()
    for t, it in items.items():
        if it.get("status") == "active" and t not in sids:  # 100.1: a held task is valid
            fails.append("backlog %s is active but task.%s.json is missing" % (t, t))
    for t in sids:
        d = load(t)
        if d.get("status") == "held":
            cpn = d.get("checkpoint") if isinstance(d.get("checkpoint"), dict) else {}
            miss = [k for k, v in (("held_at", d.get("held_at")), ("held_reason", d.get("held_reason")),
                                   ("checkpoint.next", str(cpn.get("next", "")).strip())) if not v]
            if miss:
                fails.append("held task %s lacks %s" % (t, ", ".join(miss)))
    for t in ids:
        d = load(t)
        if d.get("state") not in GATED:
            continue
        qo = d.get("questions_open", 0)
        if isinstance(qo, bool) or not isinstance(qo, int) or qo < 0:
            fails.append("%s questions_open=%r is not a count" % (t, qo))
        elif qo > 0:
            fails.append("%s has %d open user question(s) at %s; get the answers before IMPLEMENTING "
                         "(tasks.sh question %s --answer / --decide)" % (t, qo, d.get("state"), t))
        st = stale_list(t)
        if st:
            fails.append("%s inputs are stale (%s: %s); run tasks.sh stale %s, then inputs --rehash --reason"
                         % (t, st[0][0], st[0][1], t))
    if read_json(VIEW) != view():
        fails.append("task.json view is stale: run .claude/scripts/tasks.sh sync")
    sids = scope_ids()
    for i, a in enumerate(sids):
        for b in sids[i + 1:]:
            o = overlap(scope_of(a), scope_of(b))
            if o:
                fails.append("active scopes of %s and %s overlap: %s" % (a, b, o))
    if len(ids) > 1:
        for t in ids:
            if not scope_of(t):
                warns.append("%s has an empty scope while %d tasks are active" % (t, len(ids)))
    return fails, warns


def migrate():
    m = mode()
    if m == "multi":
        print("already migrated (task.json schema 2)")
        return 0
    tj = read_json(VIEW)
    tid = tj.get("task_id") if isinstance(tj, dict) else None
    if tid is None and not task_ids():
        print("FAIL: no task.json and no task.<T>.json files to migrate")
        return 1
    if isinstance(tid, str) and ID_RE.fullmatch(tid) and not os.path.exists(task_path(tid)):
        t = dict(tj)
        bi = next((x for x in backlog_items() if x.get("task_id") == tid), {})
        t.setdefault("scope", bi.get("scope") if isinstance(bi.get("scope"), list) else [])
        t.setdefault("depends_on", [])
        t.setdefault("inputs", {})
        t.setdefault("checkpoint", {"done": [], "notes": ""})
        write_json(task_path(tid), t)
        print("wrote task.%s.json" % tid)
    sync()
    print("migrated: task.json is now a schema-2 view (%d task file(s))" % len(task_ids()))
    return 0


def cmd_scope(args):
    if not args:
        print("usage: tasks.sh scope TASK-N [--set g1,g2 | --add g1,g2 | --from-design]")
        return 2
    t = args[0]
    p = task_path(t)
    if not os.path.isfile(p):
        print("FAIL: %s is not an active task (no task.%s.json)" % (t, t))
        return 1
    d = load(t)
    cur = scope_of(t)
    if len(args) == 1:
        print("\n".join(cur) if cur else "(empty scope)")
        return 0
    if len(args) == 2 and args[1] == "--from-design":
        return _scope_from_design(t, d, cur)
    if len(args) != 3 or args[1] not in ("--set", "--add"):
        print("usage: tasks.sh scope TASK-N [--set g1,g2 | --add g1,g2 | --from-design]")
        return 2
    new = [g.strip() for g in args[2].split(",") if g.strip()]
    new = new if args[1] == "--set" else cur + [g for g in new if g not in cur]
    err = check_scope(new)
    if err:
        print("FAIL: " + err)
        return 1
    others = [u for u in active_ids() if u != t]
    if not new and others:
        print("FAIL: empty scope refused while %s active" % ",".join(others))
        return 1
    for u in others:
        o = overlap(new, scope_of(u))
        if o:
            print("FAIL: scope of %s would overlap %s: %s" % (t, u, o))
            return 1
    d["scope"] = new
    apply_auto_grants(d, new)
    write_json(p, d)
    print("scope of %s: %d glob(s)" % (t, len(new)))
    return 0


def _design_paths(text):
    """F6: backticked repo paths/globs from Files/Scope sections and `New:`/`Edit` in item headings."""
    out, on = [], False
    for line in text.splitlines():
        m = re.match(r"(#+)\s+(.*)", line)
        cands = []
        if m:
            on = bool(re.search(r"files|scope", m.group(2), re.I))
            if len(m.group(1)) >= 3:
                cands = re.findall(r"(?:\bNew:|\bEdit)\s+`([^`]+)`", m.group(2))
        elif on:
            cands = re.findall(r"`([^`]+)`", line)
        for c in cands:
            c = c.strip()
            if (re.match(r"^[A-Za-z0-9_.*?\[\]{},/-]+$", c) and ("/" in c or re.search(r"\.\w+$", c))
                    and not c.startswith(("/", "../")) and not c.startswith(EXCLUDED) and c not in out):
                out.append(c)
    return out


def _scope_from_design(t, d, cur):
    """F6: read-only; print design paths missing from scope and the one add command."""
    dd = d.get("design")
    dp = dd.get("path") if isinstance(dd, dict) else ""
    if not dp:
        import glob
        n = re.sub(r"\D", "", t).lstrip("0")
        hits = sorted(glob.glob(os.path.join(ROOT, "docs", "design", "phase-%s-*.md" % n)))
        dp = os.path.relpath(hits[0], ROOT) if hits else ""
    fp = dp if os.path.isabs(dp) else os.path.join(ROOT, dp)
    if not dp or not os.path.isfile(fp):
        print("FAIL: no design doc for %s (design.path empty, no docs/design/phase-<N>-*.md)" % t)
        return 1
    with open(fp, encoding="utf-8", errors="replace") as f:
        want = _design_paths(f.read())
    import fnmatch
    miss = [w for w in want if w not in cur and not any(fnmatch.fnmatch(w, g) for g in cur)]
    if not miss:
        print("SCOPE OK")
        return 0
    print("\n".join(miss))
    print("tasks.sh scope %s --add %s" % (t, ",".join(miss)))
    return 0


def now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dirty(paths):
    r = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--"] + paths,
                       capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def save_backlog(items):
    write_json(BACKLOG, items)


PICK_USAGE = "usage: pick TASK-N [--scope g1,g2] [--force]"
COMPLETE_USAGE = 'usage: complete TASK-N [--force "<reason>"]'


def cmd_pick(args):
    """Multi-mode pick: T [--scope g,..] [--force]."""
    if not args:
        print(PICK_USAGE)
        return 2
    t, force, scope_arg, i = args[0], False, None, 1
    while i < len(args):
        if args[i] == "--force":
            force = True
        elif args[i] == "--scope" and i + 1 < len(args):
            i += 1
            scope_arg = [g.strip() for g in args[i].split(",") if g.strip()]
        else:
            print(PICK_USAGE)
            return 2
        i += 1
    p = task_path(t)
    items = backlog_items()
    item = next((x for x in items if x.get("task_id") == t), None)
    if item is None:
        print("FAIL: no backlog item with task_id=%s" % t)
        return 1
    if item.get("status") != "queued" and not force:
        print("FAIL: backlog item %s has status=%s, not queued" % (t, item.get("status")))
        return 1
    if not force and _dirty([".claude/state/backlog.json", ".claude/state/task.json",
                             ".claude/state/task.%s.json" % t]):
        print("FAIL: .claude/state has uncommitted changes (backlog/view/%s); commit the last transition first" % t)
        return 1
    act = [a for a in scope_ids() if a != t]
    if len([a for a in act if a in active_ids()]) >= max_active():
        print("FAIL: %d active tasks (max_active=%d); complete one first" % (len(act), max_active()))
        return 1
    scope = scope_arg if scope_arg is not None else (item.get("scope") or [])
    if not scope and act and all(load(a).get("status") == "held" for a in act):
        scope = ["work/%s/" % t]  # 100.3: design-only placeholder next to held tasks
    err = check_scope(scope)
    if err:
        print("FAIL: " + err)
        return 1
    done = {x.get("task_id") for x in items if x.get("status") == "done"}
    block = next((d for d in item.get("depends_on", []) if d not in done), None)
    if block is None and act:
        if not scope:
            print("FAIL: empty scope while %s active; pass --scope g1,g2" % ",".join(act))
            return 1
        for u in act:
            if overlap(scope, scope_of(u)):
                block = u
                break
    if block:
        item["blocked_by"] = block
        save_backlog(items)
        print("queued behind %s: %s stays queued (blocked_by=%s)" % (block, t, block))
        return 1
    new = {
        "task_id": t, "title": item.get("title", ""), "state": "TODO",
        "requirement": item.get("requirement", ""),
        "acceptance_criteria": item.get("acceptance_criteria", []),
        "design": {"status": "pending", "path": "", "summary": "", "reuse": [], "risks": []},
        "implementation": {"status": "pending", "files": []},
        "unit_test": {"status": "pending", "command": "", "result": ""},
        "security": {"status": "pending", "result": ""},
        "verification": {"status": "pending", "evidence": []},
        "report": {"status": "pending", "path": ""},
        "roles_required": True, "crosscheck_required": True, "roles": {},
        "user_notes": item.get("user_notes", []),
        "picked_at": now(), "updated_at": "", "updated_by": "",
        "scope": scope, "depends_on": item.get("depends_on", []), "inputs": {},
        "checkpoint": {"done": [], "notes": ""},
        "next": "Enter DESIGN: understand the requirement and acceptance criteria, then draft "
                "docs/design/phase-<N>-<slug>.md (design skill) and record it in design.path.",
    }
    apply_auto_grants(new, scope)
    write_json(p, new)
    item["status"] = "active"
    item.pop("blocked_by", None)
    save_backlog(items)
    sync()
    print("PICKED: %s -> task.%s.json (state=TODO)" % (t, t))
    return 0


def cmd_complete(args):
    if not args:
        print(COMPLETE_USAGE)
        return 2
    t = args[0]
    force = len(args) > 1 and args[1] == "--force"
    reason = args[2] if len(args) > 2 else ""
    if len(args) > 1 and not force:
        print(COMPLETE_USAGE)
        return 2
    if force and not reason:
        print('FAIL: complete --force needs a reason: complete %s --force "<why it closes without DONE>"' % t)
        return 1
    p = task_path(t)
    items = backlog_items()
    item = next((x for x in items if x.get("task_id") == t), None)
    if item is None:
        print("FAIL: no backlog item with task_id=%s" % t)
        return 1
    cur = load(t) if os.path.isfile(p) else {}
    if not cur and not force:
        print("FAIL: no task.%s.json (not an active task)" % t)
        return 1
    if cur and cur.get("state") != "DONE" and not force:
        print('FAIL: %s state=%s, not DONE; finish it or rerun with --force "<reason>"' % (t, cur.get("state")))
        return 1
    item["status"] = "done"
    item["completed_at"] = now()
    if cur.get("report", {}).get("path"):
        item["report"] = cur["report"]["path"]
    if force:
        item["waiver"] = reason
    if cur.get("user_notes"):
        merged = {n.get("raw"): n for n in item.get("user_notes", [])}
        merged.update({n.get("raw"): n for n in cur["user_notes"]})
        item["user_notes"] = list(merged.values())
    freed = []
    for x in items:
        if x.get("blocked_by") == t:
            x.pop("blocked_by", None)
            freed.append(x.get("task_id"))
    save_backlog(items)
    sync()
    print("COMPLETED: %s" % t + (" (waiver: %s)" % reason if force else ""))
    if freed:
        print("unblocked: %s" % ", ".join(freed))
    print("Stage .claude/state/backlog.json in the DONE commit (commit-check fails if it is left unstaged).")
    return 0


def note_holder(target):
    """(holder, name, path, data) for a note target in multi mode, or an error string."""
    items = backlog_items()
    ids = active_ids()
    if target == "active":
        if len(ids) != 1:
            return "%d active tasks; name the task (TASK-NNN) instead of 'active'" % len(ids)
        target = ids[0]
    if target in ids:
        d = load(target)
        return d, target, task_path(target), d
    it = next((x for x in items if x.get("task_id") == target), None)
    if it is None:
        return "no backlog item with task_id=%s" % target
    return it, target, BACKLOG, items


def cmd_holder(args):
    """Print 'name<TAB>path' of the note target, or FAIL (used by backlog.sh note/notes)."""
    r = note_holder(args[0]) if args else "missing target"
    if isinstance(r, str):
        print("FAIL: " + r)
        return 1
    print("%s\t%s" % (r[1], r[2]))
    return 0


def cmd_list():
    print("mode: %s  max_active: %d" % (mode(), max_active()))
    for t in active_ids():
        d = load(t)
        print("%-10s %-12s scope=%d  %s" % (t, d.get("state", ""), len(scope_of(t)),
                                            str(d.get("next", ""))[:60]))
    return 0


ORDER = ("VERIFIED", "UNIT_TESTED", "IMPLEMENTING", "DESIGN", "TODO", "DONE")
CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")
MAX_LINES = 25


def _txt(v, n=80):
    return CTRL_RE.sub(" ", str(v if v is not None else ""))[:n]


def _log_lines():
    try:
        with open(os.path.join(ST, "phase-log.md"), encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except OSError:
        return []


def _last_lock_break():
    """One `lock broken:` line for the newest row of .git/tasks-locks.log within 24 h, else None."""
    import calendar
    import time
    log = os.path.join(os.path.dirname(_lock_dir()), "tasks-locks.log")
    try:
        with open(log, encoding="utf-8") as f:
            rows = f.read().splitlines()[-20:]
    except OSError:
        return None
    for line in reversed(rows):
        try:
            r = json.loads(line)
            at = calendar.timegm(time.strptime(r["ts"], "%Y-%m-%dT%H:%M:%SZ"))
        except (ValueError, KeyError, TypeError):
            continue
        if time.time() - at > 86400:
            return None
        o = r.get("owner") if isinstance(r.get("owner"), dict) else {}
        return "lock broken: %s %s (pid %s, %s) at %s" % (_txt(r.get("lock"), 24), _txt(r.get("reason"), 12),
                                                      _txt(o.get("pid"), 8), _txt(o.get("role"), 10), _txt(r["ts"], 20))
    return None


QUIT_IDLE_S = 900          # 97.4: Start without Stop and idle this long = quit
CALLS_TAIL = 2000


def calls_log_path():
    return os.environ.get("TASKS_CALLS_LOG") or os.path.join(ROOT, ".claude", "agent_setup_calls.jsonl")


def _calls_rows():
    """Last CALLS_TAIL rows of the guard's calls_log (list of dicts, oldest first)."""
    try:
        with open(calls_log_path(), encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()[-CALLS_TAIL:]
    except OSError:
        return []
    rows = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def _ts_epoch(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    import calendar
    import time
    try:
        return float(calendar.timegm(time.strptime(str(v)[:19], "%Y-%m-%dT%H:%M:%S")))
    except ValueError:
        return 0.0


def agent_entries(rows=None):
    """One entry per SubagentStart: {sid, agent, role, task, start, last, stopped}; newest Start of a (sid, agent) wins."""
    ents = {}
    for r in (rows if rows is not None else _calls_rows()):
        key = (r.get("sid"), r.get("agent") or r.get("role"))
        ts = _ts_epoch(r.get("ts"))
        tool = r.get("tool")
        if tool == "SubagentStart":
            ents[key] = {"sid": r.get("sid"), "agent": r.get("agent"), "role": r.get("role"),
                         "task": r.get("task"), "start": ts, "last": ts, "stopped": False}
        elif key in ents:
            if tool == "SubagentStop":
                ents[key]["stopped"] = True
            ents[key]["last"] = max(ents[key]["last"], ts)
    return sorted(ents.values(), key=lambda e: e["start"])


def _astate(e, at):
    if e["stopped"]:
        return "ended"
    return "quit" if at - e["last"] >= QUIT_IDLE_S else "live"


def agent_info(t, role, ents=None):
    """Newest entry of `role` on task t as (state, idle_minutes), or (None, 0). state: live | quit | ended."""
    import time
    at = time.time()
    mine = [e for e in (ents if ents is not None else agent_entries()) if e["task"] == t and e["role"] == role]
    if not mine:
        return None, 0
    e = mine[-1]
    return _astate(e, at), int(max(0, at - e["last"]) // 60)


def agent_live(t, role, ents=None):
    """97.4: a Start (role, task t) without Stop whose newest row is under 15 min old."""
    import time
    at = time.time()
    return any(e["task"] == t and e["role"] == role and _astate(e, at) == "live"
               for e in (ents if ents is not None else agent_entries()))


LEAD_MAX_GEN = 3
FLOW = ("TODO", "DESIGN", "IMPLEMENTING", "UNIT_TESTED", "VERIFIED", "DONE")


def _set_state(t, st):
    """F-97-5: the lead's (and main's) one-step state move, under the state lock."""
    if st not in FLOW:
        print("FAIL: unknown state %s (one of %s)" % (_txt(st, 20), ", ".join(FLOW)))
        return 1
    if not _need_active(t):
        return 1
    d = load(t)
    cur = d.get("state")
    if st == cur:
        print("STATE %s: %s (unchanged)" % (t, cur))
        return 0
    ok = cur in FLOW and (FLOW.index(st) == FLOW.index(cur) + 1
                          or (st == "IMPLEMENTING" and cur in ("UNIT_TESTED", "VERIFIED")))
    if not ok:
        print("FAIL: %s -> %s is not one step forward (or a rollback to IMPLEMENTING)" % (cur, st))
        return 1
    d["state"], d["updated_at"], d["updated_by"] = st, now(), os.environ.get("CTXGUARD_ROLE") or "main"
    write_json(task_path(t), d)
    sync()
    print("STATE %s: %s -> %s" % (t, cur, st))
    return 0


MERGE_KEYS = ("design", "implementation", "unit_test", "security", "verification", "report",
              "roles", "next", "acceptance_criteria")


def _is_main():
    return (os.environ.get("CTXGUARD_ROLE") or "main") == "main"


def _need_active(t, held_ok=False):
    if not os.path.isfile(task_path(t)) or t not in (scope_ids() if held_ok else active_ids()):
        print("FAIL: %s is not an active task" % t)
        return False
    return True


def cmd_lead(args):
    """97.4: bump lead_gen and print the brief of a new lead (main only, under the state lock)."""
    if len(args) != 1:
        print("usage: lead TASK-N")
        return 2
    t = args[0]
    if not _is_main():
        print("FAIL: tasks.sh lead is for the main session only")
        return 1
    if not _need_active(t):
        return 1
    d = load(t)
    if agent_live(t, "lead"):
        print("FAIL: %s has a live lead (idle < 15 min); wait for it to stop, or ask it to checkpoint" % t)
        return 1
    gen = d.get("lead_gen") if isinstance(d.get("lead_gen"), int) and not isinstance(d.get("lead_gen"), bool) else 0
    if gen >= LEAD_MAX_GEN:
        print("FAIL: stuck: %s already had %d leads; decide yourself (hold, re-scope, or run the step as main)" % (t, gen))
        return 1
    d["lead_gen"], d["lead_at"] = gen + 1, now()
    write_json(task_path(t), d)
    sync()
    print("LEAD: %s gen%d (agent type lead). Launch: Agent(subagent_type=lead, prompt line 1 names %s)" % (t, gen + 1, t))
    print("Brief for gen%d:" % (gen + 1))
    print("1. Your first call: tasks.sh show %s (resume from checkpoint.next; do not redo done items)." % t)
    print("2. Run the TASK workflow for %s only; every Agent prompt line 1 names %s." % (t, t))
    print("3. Keep the checkpoint fresh: tasks.sh checkpoint %s --done X / --next N." % t)
    print("4. Commit with tasks.sh commit %s <msgfile> --log <entry> -- <paths>." % t)
    print("5. Paid runs, new blocks, permissions and user questions: SendMessage to main.")
    return 0


def cmd_set(args):
    """97.5: set T --merge work/T/x.json; whitelisted top-level keys only (dict values merge one level).
    F-97-5: set T --state S moves one step forward (or rolls back to IMPLEMENTING); the commit gate checks evidence."""
    if len(args) == 3 and args[1] == "--state":
        return _set_state(args[0], args[2])
    if len(args) != 3 or args[1] != "--merge":
        print("usage: set TASK-N --merge work/TASK-N/file.json | set TASK-N --state STATE")
        return 2
    t, src = args[0], args[2]
    if not _need_active(t):
        return 1
    real = os.path.realpath(os.path.join(ROOT, src) if not os.path.isabs(src) else src)
    base = os.path.realpath(os.path.join(ROOT, "work", t))
    if not real.startswith(base + os.sep):
        print("FAIL: merge file must be under work/%s/" % t)
        return 1
    patch = read_json(real, None)
    if not isinstance(patch, dict) or not patch:
        print("FAIL: merge file is not a non-empty JSON object")
        return 1
    bad = [k for k in patch if k not in MERGE_KEYS]
    if bad:
        print("FAIL: key(s) not allowed in set --merge: %s (allowed: %s)" % (
            ", ".join(_txt(k, 20) for k in bad[:5]), ", ".join(MERGE_KEYS)))
        return 1
    d = load(t)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k].update(v)
        else:
            d[k] = v
    d["updated_at"], d["updated_by"] = now(), os.environ.get("CTXGUARD_ROLE") or "main"
    write_json(task_path(t), d)
    sync()
    print("MERGED: %s keys %s" % (t, ",".join(sorted(patch))))
    return 0


def cmd_checkpoint(args):
    """97.5: checkpoint T [--done X] [--next N] under the state lock."""
    usage = 'usage: checkpoint TASK-N [--done "<item>"] [--next "<next step>"]'
    if not args:
        print(usage)
        return 2
    t = args[0]
    done, nxt = _opt(args, "--done"), _opt(args, "--next")
    extra = [a for a in args[1:] if a not in ("--done", "--next", done, nxt)]
    if (done is None and nxt is None) or extra or ("--done" in args and not done) or ("--next" in args and not nxt):
        print(usage)
        return 2
    if not _need_active(t):
        return 1
    d = load(t)
    cp = d.get("checkpoint") if isinstance(d.get("checkpoint"), dict) else {}
    cp.setdefault("done", [])
    cp.setdefault("notes", "")
    if not isinstance(cp["done"], list):
        cp["done"] = []
    if done:
        cp["done"].append(_txt(done, 200))
    if nxt:
        cp["next"] = _txt(nxt, 200)
    d["checkpoint"] = cp
    write_json(task_path(t), d)
    print("CHECKPOINT %s: done=%d next: %s" % (t, len(cp["done"]), _txt(cp.get("next", "-"), 60)))
    return 0


def _git(*a):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True)


def _path_ok(t, p):
    if not p or os.path.isabs(p) or ".." in p.replace("\\", "/").split("/") or p.startswith("-"):
        return False
    if p.startswith("work/%s/" % t):
        return True
    d = load(t)
    for sec in ("design", "report"):
        s = d.get(sec)
        if isinstance(s, dict) and s.get("path") == p:
            return True
    if _req_lists(t, p):
        return True
    return any(fnmatch.fnmatch(p, g) for g in scope_of(t))


def _req_lists(t, p):
    """F-97-7: docs/req/items/REQ-*.md whose `tasks: [...]` line lists t, and docs/req/INDEX.md when any does."""
    items = os.path.join(ROOT, "docs", "req", "items")
    if p == "docs/req/INDEX.md":
        names = sorted(os.listdir(items)) if os.path.isdir(items) else []
        return any(_req_lists(t, "docs/req/items/" + n) for n in names if n.startswith("REQ-") and n.endswith(".md"))
    if not (p.startswith("docs/req/items/REQ-") and p.endswith(".md") and p.count("/") == 3):
        return False
    try:
        with open(os.path.join(ROOT, p), encoding="utf-8", errors="replace") as f:
            txt = f.read(8192)
    except OSError:
        return False
    m = re.search(r"^tasks:\s*\[([^\]]*)\]", txt, re.M)
    return bool(m) and t in [x.strip().strip("'\"") for x in m.group(1).split(",")]


def _shebang(p):
    try:
        with open(os.path.join(ROOT, p), "rb") as f:
            return f.read(2) == b"#!"
    except OSError:
        return False


def cmd_commit(args):
    """97.5: commit T <msgfile> --log <entryfile> -- <paths>, under tasks-commit.lock (order commit -> state)."""
    usage = "usage: commit TASK-N <msgfile> [--log <entryfile>|--log -] -- [<path>...]"
    if len(args) >= 5 and args[2] == "--log" and args[4] == "--":
        entry, paths = args[3], args[5:]
    elif len(args) >= 3 and args[2] == "--":
        entry, paths = "-", args[3:]
    else:
        print(usage)
        return 2
    t, msg = args[0], args[1]
    nolog = entry == "-"
    msg = msg if os.path.isabs(msg) else os.path.join(ROOT, msg)
    entry = entry if nolog or os.path.isabs(entry) else os.path.join(ROOT, entry)
    if not _need_active(t, held_ok=True):  # 100.2: autohold commits the hold
        return 1
    for f in ((msg,) if nolog else (msg, entry)):
        if not os.path.isfile(f):
            print("FAIL: file not found: %s" % _txt(f, 60))
            return 1
    with open(msg, encoding="utf-8", errors="replace") as f:
        trailers = re.findall(r"^Task:\s*(\S+)\s*$", f.read(), re.M)
    if trailers != [t]:
        print("FAIL: commit message needs exactly one `Task: %s` trailer (found %s)" % (t, _txt(",".join(trailers) or "none", 40)))
        return 1
    ent = ""
    if not nolog:
        with open(entry, encoding="utf-8", errors="replace") as f:
            ent = f.read().rstrip("\n")
    first = ent.split("\n", 1)[0]
    if not nolog and (not first.startswith("## ") or t not in first):
        print("FAIL: log entry must start with `## ...` and name %s on its first line" % t)
        return 1
    own = set(_EXTRA_OWN) | {os.path.relpath(task_path(t), ROOT), os.path.relpath(os.path.join(ST, "phase-log.md"), ROOT),
           os.path.relpath(os.path.join(ST, "task.json"), ROOT),
           os.path.relpath(os.path.join(ST, "pending.json"), ROOT)}  # F-97-6: always committed; naming them is fine
    foreign = [p for p in paths if p not in own and not _path_ok(t, p)]
    if foreign:
        print("FAIL: path(s) outside %s (scope, work/%s/, design/report path): %s" % (t, t, ", ".join(_txt(p, 50) for p in foreign[:5])))
        return 1
    rel_state = os.path.relpath(task_path(t), ROOT)
    rel_log = os.path.relpath(os.path.join(ST, "phase-log.md"), ROOT)
    rel_view = os.path.relpath(os.path.join(ST, "task.json"), ROOT)
    allowed = set(paths) | {rel_state, rel_log, rel_view}
    with locked(name="tasks-commit.lock", task=t):
        staged = [l for l in _git("diff", "--cached", "--name-only").stdout.splitlines() if l]
        extra = [p for p in staged if p not in allowed]
        if extra:
            print("FAIL: already staged outside this commit: %s" % ", ".join(_txt(p, 50) for p in extra[:5]))
            return 1
        logp = os.path.join(ST, "phase-log.md")
        old = None
        if not nolog:
            with locked(task=t):
                try:
                    with open(logp, encoding="utf-8") as f:
                        old = f.read()
                except OSError:
                    old = ""
                with open(logp, "w", encoding="utf-8") as f:
                    f.write(old.rstrip("\n") + "\n\n" + ent + "\n")
                sync()
        if nolog:  # a commit with no state move still records the task as touched (commit-check wants it staged)
            with locked(task=t):
                d = load(t)
                d["updated_at"], d["updated_by"] = now(), os.environ.get("CTXGUARD_ROLE") or "main"
                write_json(task_path(t), d)
                sync()
        def undo():
            _git("reset", "-q", "--", *sorted(allowed))
            if old is not None:
                with locked(task=t):
                    with open(logp, "w", encoding="utf-8") as f:
                        f.write(old)
        r = _git("add", "-A", "--", *sorted(allowed))
        if r.returncode != 0:
            undo()
            print("FAIL: git add: %s" % _txt(r.stderr, 100))
            return 1
        for p in _git("diff", "--cached", "--name-only", "--diff-filter=A").stdout.splitlines():
            if _shebang(p):  # F4: roles cannot chmod; a new #! script lands 100755
                if _git("update-index", "--chmod=+x", "--", p).returncode == 0:
                    print("CHMOD +x %s" % _txt(p, 80))
        extra = [p for p in _git("diff", "--cached", "--name-only").stdout.splitlines() if p and p not in allowed]
        chk = os.path.join(SCRIPT_DIR, "commit-check.sh")
        c = subprocess.run([chk, msg, "--task", t], capture_output=True, text=True)
        if extra or c.returncode != 0:
            undo()
            print("FAIL: commit-check refused" if c.returncode else "FAIL: staged outside allowed paths")
            print("\n".join(_txt(l, 120) for l in (c.stdout + c.stderr).splitlines()[-8:]))
            return 1
        r = _git("commit", "-q", "-F", msg)
        if r.returncode != 0:
            undo()
            print("FAIL: git commit: %s" % _txt(r.stderr or r.stdout, 120))
            return 1
    print("COMMITTED: %s (%d path(s) + state%s)" % (t, len(paths), "" if nolog else " + phase-log"))
    return 0


def _prune_runtime(rows, at):
    """97.13 step 3 (guard runtime): drop launch entries older than _BIND_TTL, binds of sessions with no row in 24 h."""
    n = 0
    lp = os.path.join(ROOT, ".claude", "agent_setup_launch.json")
    q = read_json(lp, None)
    if isinstance(q, list):
        keep = [e for e in q if isinstance(e, dict) and at - _ts_epoch(e.get("ts")) < BIND_TTL]
        if len(keep) != len(q):
            write_json(lp, keep)
            n += len(q) - len(keep)
    bp = os.path.join(ROOT, ".claude", "agent_setup_binds.json")
    b = read_json(bp, None)
    if isinstance(b, dict) and rows:
        recent = {r.get("sid") for r in rows if at - _ts_epoch(r.get("ts")) < 86400}
        keep = {k: v for k, v in b.items() if k.replace("gen:", "", 1).split("/", 1)[0] in recent}
        if len(keep) != len(b):
            write_json(bp, keep)
            n += len(b) - len(keep)
    return n


BIND_TTL = 3600


def _recover_agents(at):
    """97.13 step 3 (calls_log): a `SubagentStop reason=recovered` row for each Start without Stop from another
    session that has been idle for 15 min. Returns how many agents were ended."""
    rows = _calls_rows()
    cur = os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CTXGUARD_SID")
    n = 0
    for e in agent_entries(rows):
        if e["stopped"] or e["sid"] == cur or at - e["last"] < QUIT_IDLE_S:
            continue
        row = {"ts": int(at), "sid": e["sid"], "agent": e["agent"], "role": e["role"], "task": e["task"],
               "tool": "SubagentStop", "reason": "recovered"}
        try:
            with open(calls_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            n += 1
        except OSError:
            break
    _prune_runtime(rows, at)
    return n


def cmd_recover():
    """97.13 steps 1-4: break dead locks, remove litter, end dead agents, print the resume lines (idempotent)."""
    import glob
    import time
    gdir = os.path.dirname(_lock_dir())
    broken = removed = 0
    for lk in sorted(glob.glob(os.path.join(gdir, "*.lock"))):
        if os.path.isdir(lk):
            why = _dead_reason(lk)
            if why and _break_lock(lk, why):
                broken += 1
    with locked():
        pats = [os.path.join(ST, "*.tmp*"), os.path.join(gdir, "*.lock.broken.*"),
                os.path.join(ROOT, ".claude", "*.tmp.*"), os.path.join(gdir, "*.tmp.*")]
        for pat in pats:
            for p in glob.glob(pat):
                try:
                    if time.time() - os.path.getmtime(p) < 60:
                        continue
                    if os.path.isdir(p):
                        import shutil
                        shutil.rmtree(p)
                    else:
                        os.unlink(p)
                    removed += 1
                except OSError:
                    pass
        ended = _recover_agents(time.time())
        wt = os.path.join(ROOT, "tests", "run_worktree.sh")
        if os.path.isfile(wt):  # 102.4: break a crashed test-worktree run's stale lock
            r = subprocess.run(["bash", wt, "clean", "--stale"], cwd=ROOT, capture_output=True, text=True)
            for l in (r.stdout + r.stderr).splitlines():
                print(l)
        if not (broken or removed or ended):
            print("Recovery: clean")
            for l in _held_rows()[:6]:
                print(l)
            return 0
        out = ["Recovery: %d locks broken, %d tmp removed, %d agents ended" % (broken, removed, ended)]
        for t in active_ids():
            p = task_path(t)
            rel = os.path.relpath(p, ROOT)
            r = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", rel],
                               capture_output=True, text=True)
            dirty = len([l for l in r.stdout.splitlines() if l.strip()])
            cmd = "/next"
            if dirty:
                cmd = "commit, or git checkout -- %s" % rel
            out.append("%s state=%s next=%s dirty=%d -> %s" % (
                t, _txt(load(t).get("state"), 12), _txt(load(t).get("next"), 50), dirty, cmd))
        out += _held_rows()
        print("\n".join(_txt(l, 160) for l in out[:14]))
    return 0


def _held_rows():
    """100.8: one resume line per held task, with the state of the question it waits on."""
    pend = read_json(os.path.join(ST, "pending.json"), [])
    pend = pend if isinstance(pend, list) else []
    rows = []
    for t in scope_ids():
        d = load(t)
        if d.get("status") != "held":
            continue
        q = str(d.get("held_question") or "")
        e = next((x for x in pend if isinstance(x, dict) and x.get("id") == q), None) if q else None
        rows.append("held: %s Q=%s answered=%s -> tasks.sh resume %s" % (
            t, _txt(q or "-", 20), "y" if e and e.get("answered_at") else "n", t))
    return rows


def cmd_status():
    """C7 view: <=25 lines, read-only, each line cut at 80 chars, control chars stripped."""
    out = ["STATUS " + now()]
    pend = read_json(os.path.join(ST, "pending.json"), [])
    for e in pend if isinstance(pend, list) else []:
        if isinstance(e, dict) and not e.get("answered_at"):
            out.append("needs you: %s (%s) rec: %s" % (_txt(e.get("id"), 12), _txt(e.get("task_id"), 12),
                                                       _txt(e.get("recommendation"), 40)))
    ids = active_ids()
    import calendar
    import time as _t
    for t in scope_ids():
        if t not in ids:
            d = load(t)
            try:
                age = max(0, int((_t.time() - calendar.timegm(
                    _t.strptime(str(d.get("held_at"))[:19], "%Y-%m-%dT%H:%M:%S"))) // 60))
            except (ValueError, TypeError, OverflowError):
                age = 0
            out.append("held: %s age=%dm Q=%s (%s)" % (t, age, _txt(d.get("held_question") or "-", 20),
                                                       _txt(d.get("held_reason"), 40)))
    for t in ids:
        d = load(t)
        b = d.get("blocked")
        if b:
            why = d.get("blocked_reason") or (b.get("reason") if isinstance(b, dict) else b)
            out.append("blocked: %s %s" % (t, _txt(why, 60)))
    for t in ids:
        if load(t).get("state") == "DONE" and stale_list(t):
            out.append("stale: %s inputs changed (tasks.sh stale %s)" % (t, t))
    def rank(t):
        st = load(t).get("state")
        return (ORDER.index(st) if st in ORDER else len(ORDER), int(t[5:]))
    for t in sorted(ids, key=rank):
        d = load(t)
        out.append("running: %s (%s; %s)" % (t, _txt(d.get("state"), 12), _txt(d.get("next"), 50)))
    ents = agent_entries()
    import time
    at = time.time()
    for t in sorted(ids, key=rank):
        d = load(t)
        gen = d.get("lead_gen") if isinstance(d.get("lead_gen"), int) else 0
        if gen > 0:
            st, idle = agent_info(t, "lead", ents)
            cp = d.get("checkpoint") if isinstance(d.get("checkpoint"), dict) else {}
            out.append("lead: %s gen%d %s idle=%dm next=%s" % (
                t, gen, st or "ended", idle, _txt(cp.get("next") or d.get("next"), 50)))
        for e in ents:
            if e["task"] == t and _astate(e, at) == "quit" and at - e["last"] < 86400:
                idle = int((at - e["last"]) // 60)
                out.append("quit: %s %s gen%d idle=%dm -> %s" % (
                    t, _txt(e["role"], 10), gen, idle,
                    "tasks.sh lead %s" % t if e["role"] == "lead" else "relaunch %s" % _txt(e["role"], 10)))
    for i in backlog_items():
        if i.get("status") == "queued":
            b = i.get("blocked_by")
            out.append("queued: %s%s" % (_txt(i.get("task_id"), 12), " (blocked_by %s)" % _txt(b, 30) if b else ""))
    last = [l for l in _log_lines() if l.startswith("## DONE")]
    if last:
        out.append("done since: " + _txt(last[-1].lstrip("# ")))
    lb = _last_lock_break()
    if lb:
        out.append(lb)
    if len(out) > MAX_LINES:
        extra = len(out) - (MAX_LINES - 1)
        out = out[:MAX_LINES - 1] + ["... %d more line(s)" % extra]
    print("\n".join(_txt(l) for l in out))
    return 0


def _opt(args, name):
    if name in args:
        i = args.index(name)
        return args[i + 1] if i + 1 < len(args) else None
    return None


def cmd_hold(args):
    if not args or "--reason" not in args:
        print('usage: hold TASK-N --reason "<why>" [--next "<next step>"]')
        return 2
    t = args[0]
    p = task_path(t)
    if not os.path.isfile(p):
        print("FAIL: %s is not an active task" % t)
        return 1
    d = load(t)
    if d.get("status") == "held":
        print("FAIL: %s is already held" % t)
        return 1
    reason, nxt = _opt(args, "--reason"), _opt(args, "--next")
    if not reason or not reason.strip():
        print("FAIL: --reason is empty")
        return 2
    cp = d.get("checkpoint") if isinstance(d.get("checkpoint"), dict) else {"done": [], "notes": ""}
    if nxt:
        cp["next"] = _txt(nxt, 200)
    if not str(cp.get("next", "")).strip():
        print("FAIL: checkpoint.next is empty (pass --next \"<next step>\")")
        return 1
    globs = [":(glob)" + g for g in scope_of(t)]
    if globs and _dirty(globs):
        print("FAIL: uncommitted changes in the scope of %s; commit them first" % t)
        return 1
    d["checkpoint"] = cp
    d["status"], d["held_at"], d["held_reason"] = "held", now(), _txt(reason, 200)
    write_json(p, d)
    sync()
    print("HELD: %s (state=%s) next: %s" % (t, d.get("state"), _txt(cp["next"])))
    print("Commit as: State: %s" % d.get("state"))
    return 0


def cmd_resume(args):
    if len(args) != 1:
        print("usage: resume TASK-N")
        return 2
    t = args[0]
    p = task_path(t)
    if not os.path.isfile(p):
        print("FAIL: no task file for %s" % t)
        return 1
    d = load(t)
    if d.get("status") != "held":
        print("FAIL: %s is not held" % t)
        return 1
    if len(active_ids()) >= max_active():
        print("FAIL: %d active task(s) already (max_active=%d); hold or complete one first"
              % (len(active_ids()), max_active()))
        return 1
    for k in ("status", "held_at", "held_reason", "held_question"):
        d.pop(k, None)
    write_json(p, d)
    sync()
    print("RESUMED: %s (state=%s)" % (t, d.get("state")))
    return cmd_show([t])


def cmd_show(args):
    if len(args) != 1:
        print("usage: show TASK-N")
        return 2
    t = args[0]
    if not os.path.isfile(task_path(t)):
        print("FAIL: no task file for %s" % t)
        return 1
    d = load(t)
    cp = d.get("checkpoint") if isinstance(d.get("checkpoint"), dict) else {}
    done = cp.get("done") if isinstance(cp.get("done"), list) else []
    lines = ["%s state=%s status=%s" % (t, _txt(d.get("state"), 14), _txt(d.get("status") or "active", 8))]
    if d.get("status") == "held":
        lines.append("held: %s (%s)" % (_txt(d.get("held_reason"), 50), _txt(d.get("held_at"), 20)))
    lines.append("done: " + _txt("; ".join(_txt(x, 30) for x in done[-3:]) or "-"))
    lines.append("next: " + _txt(cp.get("next") or d.get("next") or "-"))
    lines.append("notes: " + _txt(cp.get("notes") or "-"))
    lines.append("open questions: %s" % _txt(d.get("questions_open", 0), 5))
    logs = [l for l in _log_lines() if t in l and l.startswith("##")]
    lines.append("last log: " + _txt(logs[-1].lstrip("# ") if logs else "-"))
    hd = os.path.join(ROOT, "work", t, "handoff")
    hs = sorted(os.listdir(hd)) if os.path.isdir(hd) else []
    lines.append("handoffs: " + _txt(" ".join(hs[:6]) or "-"))
    print("\n".join(lines[:15]))
    return 0


def cmd_question(args):
    usage = 'usage: question TASK-N [--set N | --answer | --decide "<text>" --reason "<why>"]'
    if not args:
        print(usage)
        return 2
    t = args[0]
    p = task_path(t)
    if not os.path.isfile(p):
        print("FAIL: %s is not an active task" % t)
        return 1
    d = load(t)
    qo = d.get("questions_open", 0)
    qo = qo if isinstance(qo, int) and not isinstance(qo, bool) and qo >= 0 else 0
    if len(args) == 1:
        print("questions_open: %d" % qo)
        for x in (d.get("decisions") if isinstance(d.get("decisions"), list) else [])[-5:]:
            print("decided_by %s: %s (%s)" % (_txt(x.get("decided_by"), 12), _txt(x.get("text"), 50), _txt(x.get("reason"), 40)))
        return 0
    if args[1] == "--set" and len(args) == 3 and args[2].isdigit():
        d["questions_open"] = int(args[2])
    elif args[1] == "--answer" and len(args) == 2:
        d["questions_open"] = max(0, qo - 1)
    elif args[1] == "--decide" and len(args) >= 3:
        reason = _opt(args, "--reason")
        if not reason or not reason.strip():
            print('FAIL: --decide needs --reason "<one-line why>"')
            return 1
        dl = d.get("decisions") if isinstance(d.get("decisions"), list) else []
        dl.append({"text": _txt(args[2], 200), "decided_by": "coordinator", "reason": _txt(reason, 200), "at": now()})
        d["decisions"] = dl
        d["questions_open"] = max(0, qo - 1)
    else:
        print(usage)
        return 2
    write_json(p, d)
    print("questions_open of %s: %d" % (t, d["questions_open"]))
    return 0


PRIO = {"high": 0, "normal": 1, "low": 2}
USER_KINDS = ("paid", "permission", "block")
_EXTRA_OWN = []  # paths cmd_commit also accepts as state (autohold's pick commit: backlog.json)


def _workable_rows(exclude=None):
    """100.7: [(task_id, skip reason or None)] for the queued items, priority then backlog order."""
    items = backlog_items()
    done = {x.get("task_id") for x in items if x.get("status") == "done"}
    queued = [x for x in items if x.get("status") == "queued" and x.get("task_id") != exclude]
    queued.sort(key=lambda x: PRIO.get(x.get("priority"), 1))  # stable: backlog order inside a priority
    held_scopes = [(u, scope_of(u)) for u in scope_ids()]
    rows = []
    for it in queued:
        c, why = it.get("task_id"), None
        nu = it.get("needs_user")
        dep = next((d for d in (it.get("depends_on") or []) if d not in done), None)
        blk = it.get("blocked_by")
        if it.get("paid") is True or re.match(r"PAID\b", str(it.get("title", ""))):
            why = "paid"
        elif isinstance(nu, str) and nu.strip():
            why = "needs user: " + _txt(nu, 40)
        elif dep:
            why = "depends on %s" % dep
        elif blk and blk not in done:
            why = "blocked by %s" % blk
        else:
            sc = it.get("scope") or []
            for u, us in held_scopes:
                if u != c and sc and us and overlap(sc, us):
                    why = "scope overlaps %s" % u
                    break
        rows.append((c, why))
    return rows


def cmd_workable(args):
    """100.7: read-only list of the queued tasks a stuck lead may pick next."""
    exclude = None
    if args:
        if len(args) == 2 and args[0] == "--exclude" and ID_RE.fullmatch(args[1]):
            exclude = args[1]
        else:
            print("usage: workable [--exclude TASK-N]")
            return 2
    rows = _workable_rows(exclude)
    out = ["SKIP %s %s" % (c, w) if w else "WORKABLE %s" % c for c, w in rows]
    print("\n".join(_txt(l, 100) for l in out[:30]) if out else "NONE")
    return 0


def _pend_path():
    return os.path.join(ST, "pending.json")


def _due_age(e):
    """Seconds since the question was asked on the task_checkpoint clock (TASK_CHECKPOINT_NOW), or None."""
    import calendar
    import time
    v = os.environ.get("TASK_CHECKPOINT_NOW", "")
    n = int(v) if v.isdigit() else int(time.time())
    try:
        return n - calendar.timegm(time.strptime(str(e.get("asked_at")), "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError):
        return None


def _gate_trailer(t, state):
    """F-100-V10: the gate wants Tests: at UNIT_TESTED and Verified-by: at VERIFIED; take them from the task itself."""
    key, sub = {"UNIT_TESTED": ("Tests", "unit_test"), "VERIFIED": ("Verified-by", "verification")}.get(state, (None, None))
    if key is None:
        return ""
    s = load(t).get(sub)
    s = s if isinstance(s, dict) else {}
    cmd, res = _txt(s.get("command"), 120).strip(), _txt(s.get("result"), 70).strip()
    val = _txt("%s -> %s" % (cmd, res), 200) if cmd and res else "n/a (hold commit, state unchanged)"
    return "%s: %s\n" % (key, val)


def _auto_commit(t, subject, state, paths):
    import shutil
    import tempfile
    d = tempfile.mkdtemp(prefix="autohold.")
    try:
        mf = os.path.join(d, "msg")
        with open(mf, "w", encoding="utf-8") as f:
            f.write("%s\n\nTask: %s\nState: %s\n%s" % (subject, t, state, _gate_trailer(t, state)))
        _EXTRA_OWN[:] = [os.path.relpath(BACKLOG, ROOT)]
        try:
            return cmd_commit([t, mf, "--"] + paths)
        finally:
            del _EXTRA_OWN[:]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def cmd_autohold(args):
    """100.6: hold T on its due, unanswered user-only question, commit, pick the next workable task, commit."""
    if len(args) != 2 or not ID_RE.fullmatch(args[0]) or not re.fullmatch(r"Q-[0-9]+", args[1]):
        print("usage: autohold TASK-N Q-<epoch>")
        return 2
    t, q = args
    if (os.environ.get("CTXGUARD_ROLE") or "main") not in ("main", "lead"):
        print("FAIL: autohold is for main or the task's lead")
        return 1
    v = os.environ.get("TASK_CHECKPOINT_TIMEOUT_MIN", "10")
    if not v.isdigit() or int(v) < 1:
        print("FAIL: bad TASK_CHECKPOINT_TIMEOUT_MIN")
        return 2
    tmo = int(v)
    rel_t = os.path.relpath(task_path(t), ROOT)
    rel_v = os.path.relpath(VIEW, ROOT)
    rel_p = os.path.relpath(_pend_path(), ROOT)
    with locked():
        pend = read_json(_pend_path(), [])
        e = next((x for x in pend if isinstance(x, dict) and x.get("id") == q), None) if isinstance(pend, list) else None
        why = None
        if e is None:
            why = "no pending question %s" % q
        elif e.get("answered_at"):
            why = "%s is answered" % q
        elif e.get("task_id") != t:
            why = "%s belongs to %s" % (q, _txt(e.get("task_id"), 20))
        elif e.get("kind") is not None and e.get("kind") not in USER_KINDS:
            why = "%s is not a user-only question" % q
        elif t not in scope_ids():
            why = "%s is not an open task" % t
        elif load(t).get("status") == "held":
            why = "%s is already held" % t
        else:
            age = _due_age(e)
            if age is None or age < tmo * 60:
                why = "%s is not due yet" % q
        if why:
            print("FAIL: " + why)
            return 4
        with open(task_path(t), "rb") as f:
            saved_t = f.read()
        saved_v = b""
        if os.path.isfile(VIEW):
            with open(VIEW, "rb") as f:
                saved_v = f.read()
        with open(_pend_path(), "rb") as f:
            saved_p = f.read()
        d = load(t)
        if not (d.get("scope") or []) and d.get("state") in ("IMPLEMENTING", "UNIT_TESTED", "VERIFIED", "DONE"):
            files = [x for x in ((d.get("implementation") or {}).get("files") or []) if isinstance(x, str)]
            if files and not check_scope(files):
                d["scope"] = files  # a held task keeps a scope so overlap still guards it
                write_json(task_path(t), d)
        cp = d.get("checkpoint") if isinstance(d.get("checkpoint"), dict) else {}
        old = str(cp.get("next") or d.get("next") or "").strip() or "continue"
        rc = cmd_hold([t, "--reason", "waits on %s: %s" % (q, _txt(e.get("question"), 60)),
                       "--next", "answer %s, then: %s" % (q, old)])
        if rc != 0:
            with open(task_path(t), "wb") as f:
                f.write(saved_t)
            return rc
        d = load(t)
        d["held_question"] = q
        write_json(task_path(t), d)
        e["held_at"] = d.get("held_at")
        write_json(_pend_path(), pend)
        sync()
        state = d.get("state")
    if _auto_commit(t, "chore(state): %s held on %s (auto)" % (t, q), state, [rel_t, rel_v, rel_p]) != 0:
        with locked():
            for pth, b in ((task_path(t), saved_t), (VIEW, saved_v), (_pend_path(), saved_p)):
                with open(pth, "wb") as f:
                    f.write(b)
        print("FAIL: hold commit refused; hold undone")
        return 1
    print("HELD %s" % t)
    rows = _workable_rows(t)
    cand = next((c for c, w in rows if not w), None)
    ask = "Your turn: answer %s (%s) %s Recommended: %s" % (
        q, t, _txt(e.get("question"), 80), _txt(e.get("recommendation"), 80))
    if cand is None:
        for c, w in [(c, w) for c, w in rows if w][:5]:
            print("SKIP %s %s" % (c, _txt(w, 60)))
        print("NONE")
        print(ask)
        return 5
    with locked():
        rc = cmd_pick([cand])
    if rc != 0:
        print("FAIL: pick %s refused; %s stays held" % (cand, t))
        return 1
    if _auto_commit(cand, "chore(state): %s picked (auto, %s held)" % (cand, t), "TODO",
                    [os.path.relpath(BACKLOG, ROOT), os.path.relpath(task_path(cand), ROOT), rel_v]) != 0:
        print("FAIL: pick commit refused; %s picked but uncommitted" % cand)
        return 1
    print("PICKED %s" % cand)
    print("brief: .claude/scripts/brief.sh %s designer" % cand)
    print(ask)
    return 0


LOCKED = ("pick", "complete", "hold", "resume", "inputs", "question", "migrate", "sync",
          "lead", "set", "checkpoint")


# ---- 154.2/154.5/154.6/154.7 keepalive: one verdict for the Stop hook (nextpick) and the watcher ----
def _now():
    import time
    v = os.environ.get("KEEPALIVE_NOW", "")
    return int(v) if v.isdigit() else int(time.time())


def _env_int(name, default):
    v = os.environ.get(name, "")
    return int(v) if v.isdigit() else default


def _open_questions():
    """Pending entries with no answer: [(entry, held)]."""
    pend = read_json(_pend_path(), [])
    out = []
    for e in pend if isinstance(pend, list) else []:
        if isinstance(e, dict) and not e.get("answered_at"):
            t = e.get("task_id")
            held = False
            if isinstance(t, str) and ID_RE.fullmatch(t):
                try:
                    held = load(t).get("status") == "held"
                except ValueError:
                    held = False
            out.append((e, held))
    return out


def _proc_running():
    """A live run_all.sh / pipeline.sh (KEEPALIVE_PROCS = comma list of script names, 'none' = off)."""
    names = [n for n in os.environ.get("KEEPALIVE_PROCS", "run_all.sh,pipeline.sh").split(",") if n and n != "none"]
    if not names:
        return None
    try:
        out = subprocess.run(["ps", "-eo", "pid=,args="], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             universal_newlines=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[0] == str(os.getpid()):
            continue
        for x in parts[1:4]:
            if os.path.basename(x) in names:
                return os.path.basename(x)
    return None


def _role_running(now, stall_s):
    """An active task whose handoff says PROGRESS: IN_PROGRESS and was written within stall_s."""
    for t in active_ids():
        d = os.path.join(ROOT, "work", t, "handoff")
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for n in names:
            p = os.path.join(d, n)
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    first = f.readline().strip()
                if first.startswith("PROGRESS: IN_PROGRESS") and now - os.path.getmtime(p) < stall_s:
                    return "%s %s" % (t, n[:-3] if n.endswith(".md") else n)
            except OSError:
                continue
    return None


def _last_state_commit():
    try:
        out = subprocess.run(["git", "-C", ROOT, "log", "-1", "--format=%ct", "--", ".claude/state"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True, timeout=10).stdout
        return int(out.strip()) if out.strip().isdigit() else None
    except (OSError, subprocess.SubprocessError):
        return None


def _first_workable():
    rows = [c for c, w in _workable_rows() if not w]
    return (rows[0] if rows else None), len(rows)


def _keepalive_verdict():
    """154.5: (kind, text) with kind in OK|WAIT|DUE|STALL; text is the one output line."""
    now = _now()
    tmo = max(1, _env_int("TASK_CHECKPOINT_TIMEOUT_MIN", 10))
    stall_s = max(1, _env_int("KEEPALIVE_STALL_MIN", 30)) * 60
    waiting = None
    for e, held in _open_questions():
        if held:
            continue
        age = _due_age(e)
        if age is not None and age >= tmo * 60:
            return "DUE", "DUE %s %s" % (_txt(e.get("task_id"), 20), _txt(e.get("id"), 24))
        waiting = waiting or "question %s" % _txt(e.get("id"), 24)
    waiting = waiting or _role_running(now, stall_s) or _proc_running()
    if waiting:
        return "WAIT", "WAIT " + _txt(waiting, 60)
    act = active_ids()
    if act:
        last = _last_state_commit()
        if last is not None and now - last >= stall_s:
            return "STALL", "STALL resume %s" % act[0]
        return "OK", "OK active %s" % act[0]
    w, _n = _first_workable()
    if w:
        return "STALL", "STALL pick %s" % w
    return "OK", "OK idle"


def cmd_keepalive(args):
    """154.5/154.6: print the verdict; rc 0 for OK/WAIT, 4 for STALL/DUE. --watch polls until STALL/DUE or the max."""
    import time
    if args not in ([], ["--watch"]):
        print("usage: keepalive [--watch]")
        return 2
    try:
        if not args:
            kind, line = _keepalive_verdict()
            print(line)
            return 4 if kind in ("STALL", "DUE") else 0
        pidf = os.path.join(ST, ".keepalive.pid")
        try:
            old = int(open(pidf).read().strip())
            os.kill(old, 0)
            print("FAIL: watcher already running (pid %d)" % old)
            return 1
        except (OSError, ValueError):
            pass
        with open(pidf, "w") as f:
            f.write(str(os.getpid()))
        try:
            end = time.time() + _env_int("KEEPALIVE_MAX_MIN", 180) * 60
            poll = _env_int("KEEPALIVE_POLL_SEC", 60)
            while True:
                kind, line = _keepalive_verdict()
                if kind in ("STALL", "DUE"):
                    print(line)
                    return 4
                if time.time() >= end:
                    print(line)
                    return 0
                time.sleep(poll)
        finally:
            try:
                os.unlink(pidf)
            except OSError:
                pass
    except Exception as e:  # a watcher must not die silently into a false OK
        print("FAIL: keepalive: " + _txt(e, 80))
        return 1


def _last_reply_line(data):
    """Last non-empty line of main's final reply: stdin key, else the transcript tail; '' on any problem."""
    txt = data.get("last_assistant_message")
    if not isinstance(txt, str):
        txt = ""
        try:
            with open(str(data.get("transcript_path")), "rb") as f:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - 256 * 1024))
                lines = f.read().decode("utf-8", "ignore").splitlines()
            for line in reversed(lines):
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(ev, dict) or ev.get("type") != "assistant" or ev.get("parent_tool_use_id"):
                    continue
                c = (ev.get("message") or {}).get("content")
                parts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"] if isinstance(c, list) else []
                if any(parts):
                    txt = "\n".join(parts)
                    break
        except (OSError, AttributeError, TypeError, ValueError):
            txt = ""
    ls = [x.strip() for x in txt.splitlines() if x.strip()]
    return ls[-1] if ls else ""


def _block_allowed():
    """154.7: at most KEEPALIVE_MAX_CONTINUE blocks in a row without a new commit (counter in .keepalive.json)."""
    p = os.path.join(ST, ".keepalive.json")
    try:
        head = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, universal_newlines=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        head = ""
    st = read_json(p, {})
    n = st.get("n", 0) if isinstance(st, dict) and st.get("head") == head and isinstance(st.get("n"), int) else 0
    if n >= _env_int("KEEPALIVE_MAX_CONTINUE", 3):
        return False
    write_json(p, {"head": head, "n": n + 1})
    return True


def cmd_nextpick(args):
    """154.2/154.7: Stop-hook check. Prints at most one JSON line; always rc 0 (fails open)."""
    try:
        if os.environ.get("NEXT_PICK_CHECK") == "0":
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            data = {}
        if not isinstance(data, dict) or data.get("stop_hook_active"):
            return 0
        last = _last_reply_line(data)
        waits = last.startswith("Wait for")
        kind, line = _keepalive_verdict()
        if kind in ("STALL", "DUE") and not waits and os.environ.get("NEXT_PICK_BLOCK") != "0" and _block_allowed():
            print(json.dumps({"decision": "block", "reason": _txt(
                line + " - pick/resume it now, or end with Wait for/Your turn on a registered question", 300)}))
            return 0
        free = len(active_ids()) < max_active()
        w, n = _first_workable()
        open_q = any(not h for _e, h in _open_questions())
        turn = last.startswith("Your turn:")
        msg = None
        if free and w and ((not active_ids() and not waits) or (turn and not open_q)):
            msg = "NEXT: pick %s (workable) - backlog.sh pick %s; brief: .claude/scripts/brief.sh %s designer%s" % (
                w, w, w, " (+%d more)" % (n - 1) if n > 1 else "")
        elif turn and not open_q:
            msg = ('NOTE: "Your turn" with no registered question - register it (task_checkpoint.sh a' 'sk --kind) '
                   'or decide it (RAW-00511)')
        if msg:
            print(json.dumps({"systemMessage": _txt(msg, 300)}))
    except Exception:
        pass
    return 0


def main(argv):
    cmd = argv[0] if argv else ""
    rest = argv[1:]
    try:
        if cmd in LOCKED or (cmd == "scope" and len(rest) > 1):
            with locked():
                return dispatch(cmd, rest)
        return dispatch(cmd, rest)
    except ValueError as e:
        print("FAIL: %s" % e)
        return 1


def dispatch(cmd, rest):
    if True:
        if cmd == "mode":
            print(mode())
        elif cmd == "max":
            print(max_active())
        elif cmd == "active":
            print("\n".join(active_ids()))
        elif cmd == "path" and len(rest) == 1:
            print(task_path(rest[0]))
        elif cmd == "view":
            print(json.dumps(view(), indent=2))
        elif cmd == "sync":
            print("synced task.json view" if sync() else "task.json view unchanged")
        elif cmd == "overlap" and len(rest) == 2:
            o = overlap(scope_of(rest[0]), scope_of(rest[1]))
            if o:
                print(o)
                return 1
        elif cmd == "check":
            fails, warns = check()
            for w in warns:
                print("WARN: " + w)
            for f in fails:
                print("FAIL: " + f)
            if not fails and not active_ids() and scope_ids():
                print("PASS: %d task(s), all held, none active" % len(scope_ids()))
            return 1 if fails else 0
        elif cmd == "list":
            return cmd_list()
        elif cmd == "scope":
            return cmd_scope(rest)
        elif cmd == "migrate":
            return migrate()
        elif cmd == "status":
            return cmd_status()
        elif cmd == "recover":
            return cmd_recover()
        elif cmd == "hold":
            return cmd_hold(rest)
        elif cmd == "resume":
            return cmd_resume(rest)
        elif cmd == "show":
            return cmd_show(rest)
        elif cmd == "pick":
            return cmd_pick(rest)
        elif cmd == "complete":
            return cmd_complete(rest)
        elif cmd == "holder":
            return cmd_holder(rest)
        elif cmd == "inputs":
            return cmd_inputs(rest)
        elif cmd == "stale":
            return cmd_stale(rest)
        elif cmd == "question":
            return cmd_question(rest)
        elif cmd == "lead":
            return cmd_lead(rest)
        elif cmd == "set":
            return cmd_set(rest)
        elif cmd == "checkpoint":
            return cmd_checkpoint(rest)
        elif cmd == "commit":
            return cmd_commit(rest)
        elif cmd == "workable":
            return cmd_workable(rest)
        elif cmd == "autohold":
            return cmd_autohold(rest)
        elif cmd == "keepalive":
            return cmd_keepalive(rest)
        elif cmd == "nextpick":
            return cmd_nextpick(rest)
        else:
            print("usage: _tasks.py mode|max|active|path T|view|sync|overlap A B|check|list|scope T ...|migrate|"
                  "inputs T|stale T|question T|recover|lead T|set T --merge F|checkpoint T ...|commit T M --log E -- P|workable [--exclude T]|autohold T Q|keepalive [--watch]|nextpick")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

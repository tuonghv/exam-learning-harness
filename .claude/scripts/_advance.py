#!/usr/bin/env python3
"""advance.sh logic (REQ-0037, phase 32): one gated TASK step per call, and REQ catch-up.

Orchestrates the existing tools (tasks.sh set/commit, workflow-check.sh, backlog.sh complete, req.py status/ac);
it adds only the spec schema, the AC7 product-quality checks, the snapshot/restore and the dry-run.
Exit 0 = PASS, 1 = first failing gate, 2 = usage. Python stdlib only."""
import fnmatch
import json
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import _tasks  # noqa: E402  (ROOT, FLOW, MERGE_KEYS, locked, load, task_path, now, active_ids)

ROOT = _tasks.ROOT
ST = _tasks.ST
FLOW = _tasks.FLOW
ORDER = list(FLOW)  # req.py ORDER is the same six names
SIDE = ("SUPERSEDED", "REJECTED")
REQ_DIR = os.path.join(ROOT, "docs", "req")
SPEC_KEYS = ("set", "next", "log", "commit", "req", "quality")
SET_KEYS = ("design", "implementation", "unit_test", "security", "verification", "report", "roles",
            "acceptance_criteria")
# state -> {section: required non-empty sub-keys}; lists are marked with a trailing []
SCHEMA = {
    "DESIGN": {"design": ("status", "path", "summary"), "acceptance_criteria": ()},
    "IMPLEMENTING": {"implementation": ("status", "summary", "files[]")},
    "UNIT_TESTED": {"unit_test": ("status", "command", "result")},
    "VERIFIED": {"verification": ("status", "command", "result", "evidence[]"), "security": ("status", "result")},
    "DONE": {"report": ("status",)},
}
FIX = {
    "spec": "fix the spec JSON (see skill advance for the template of this state)",
    "state": "advance one state at a time, from the current state; run tasks.sh show <TASK>",
    "quality": "record real evidence files under work/<TASK>/ and a `quality` block (skill advance, AC7)",
    "workflow": "fix the field workflow-check names in the spec `set`, then re-run",
    "set": "check the spec `set` keys (tasks.sh set --merge whitelist)",
    "req": "see the message; REQ more than one step behind: advance.sh req-catchup <REQ>",
    "backlog": "run backlog.sh complete by hand only after finding why it refused",
    "commit": "fix what commit-check names (paths, trailers, staged files), then re-run",
}


class Fail(Exception):
    def __init__(self, gate, msg, fix=None):
        Exception.__init__(self, msg)
        self.gate, self.msg, self.fix = gate, msg, fix or FIX.get(gate, "")


def env():
    e = dict(os.environ)
    e["CLAUDE_PROJECT_DIR"] = ROOT
    return e


def run(argv):
    r = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT, env=env())
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def tasks_sh(*a):
    return run(["bash", os.path.join(SCRIPT_DIR, "tasks.sh")] + list(a))


def req_py(*a):
    return run([sys.executable, os.path.join(ROOT, ".claude", "req", "req.py")] + list(a))


def git(*a):
    return run(["git", "-C", ROOT] + list(a))


def first(out, pat=None):
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    if pat:
        for l in lines:
            if re.search(pat, l):
                return l
    return lines[0] if lines else "(no output)"


def rel(p):
    return os.path.relpath(p, ROOT)


def short(s, n=160):
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[:n - 3] + "..."


def nonempty(v):
    return isinstance(v, str) and v.strip() != ""


# ---------------------------------------------------------------- snapshot / restore (step 4, R)
def snapshot(paths):
    snap = {}
    for p in paths:
        try:
            with open(p, "rb") as f:
                snap[p] = f.read()
        except OSError:
            snap[p] = None
    return snap


def restore(snap):
    for p, b in snap.items():
        try:
            if b is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                with open(p, "wb") as f:
                    f.write(b)
        except OSError as e:
            print("WARN: could not restore %s: %s" % (rel(p), e))


def changed(snap):
    out = []
    for p, b in snap.items():
        try:
            with open(p, "rb") as f:
                now = f.read()
        except OSError:
            now = None
        if now != b:
            out.append(p)
    return out


# ---------------------------------------------------------------- REQ helpers
def req_files_for(t):
    items = os.path.join(REQ_DIR, "items")
    out = []
    for n in sorted(os.listdir(items)) if os.path.isdir(items) else []:
        if not (n.startswith("REQ-") and n.endswith(".md")):
            continue
        txt = read_head(os.path.join(items, n))
        m = re.search(r"^tasks:\s*\[([^\]]*)\]", txt, re.M)
        if m and t in [x.strip().strip("'\"") for x in m.group(1).split(",")]:
            out.append(os.path.join(items, n))
    return out


def read_head(p, n=1 << 20):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read(n)
    except OSError:
        return ""


def req_status(p):
    m = re.search(r"^status:\s*(\S+)", read_head(p), re.M)
    return m.group(1) if m else "TODO"


def req_id(p):
    return os.path.basename(p)[:-3]


def section(txt, name):
    m = re.search(r"^## %s[ \t]*\n(.*?)(?=^## |\Z)" % re.escape(name), txt, re.M | re.S)
    return re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S).strip() if m else ""


def design_empty(p):
    return not section(read_head(p), "Design")


def req_cmd_fail(out, what):
    return Fail("req", "%s: %s" % (what, short(first(out, r"gate for|requires|cannot|refus|unknown|empty|not "), 200)))


def step_req(p, st, spec_req, ev, nxt, plan):
    """Move one REQ to st (one step); runs req.py ac first when the spec asks for it."""
    rid = req_id(p)
    if spec_req.get("ac"):
        ae = spec_req.get("ac_evidence") or ev
        plan.append("req.py ac %s %s --evidence %s" % (rid, spec_req["ac"], short(ae, 60)))
        rc, out = req_py("ac", rid, spec_req["ac"], "--evidence", ae)
        if rc != 0:
            raise req_cmd_fail(out, "req.py ac %s" % rid)
    plan.append("req.py status %s %s --evidence %s" % (rid, st, short(ev, 60)))
    args = ["status", rid, st, "--evidence", ev]
    if nxt:
        args += ["--next", nxt]
    rc, out = req_py(*args)
    if rc != 0:
        raise req_cmd_fail(out, "req.py status %s %s" % (rid, st))


# ---------------------------------------------------------------- evidence files (AC7)
def evfile(p):
    """Existing, non-empty regular file under ROOT given as a relative path; else a reason string."""
    if not nonempty(p) or os.path.isabs(p) or ".." in p.replace("\\", "/").split("/"):
        return "bad evidence path %r" % short(p, 40)
    real = os.path.realpath(os.path.join(ROOT, p))
    if not real.startswith(os.path.realpath(ROOT) + os.sep):
        return "evidence %s is outside the repo" % short(p, 60)
    if not os.path.isfile(real):
        return "evidence file %s does not exist" % short(p, 60)
    if os.path.getsize(real) == 0:
        return "evidence file %s is empty" % short(p, 60)
    return None


def eff(task, spec_set, key, sub=None):
    """Effective value after the merge: spec.set one level over the task file."""
    base = task.get(key)
    over = spec_set.get(key)
    if isinstance(over, dict):
        merged = dict(base) if isinstance(base, dict) else {}
        merged.update(over)
        base = merged
    elif key in spec_set:
        base = over
    return base.get(sub) if sub is not None and isinstance(base, dict) else (None if sub is not None else base)


def quality(st, task, spec):
    """32.5: product-quality gates. Returns the quality block to store (DONE) or None."""
    sset = spec.get("set") or {}
    if st in ("VERIFIED", "DONE"):
        ev = eff(task, sset, "verification", "evidence")
        if not isinstance(ev, list) or not ev:
            raise Fail("quality", "verification.evidence is empty (a list of existing evidence files is required)")
        for p in ev:
            why = evfile(p)
            if why:
                raise Fail("quality", why)
    if st != "DONE":
        return None
    q = spec.get("quality")
    if not isinstance(q, dict):
        raise Fail("quality", "DONE needs a `quality` block {kind, evidence[], reason}")
    kind = q.get("kind")
    if kind not in ("crosscheck", "rendered", "real-run", "n/a"):
        raise Fail("quality", "quality.kind must be crosscheck|rendered|real-run|n/a (got %s)" % short(kind, 20))
    out = {"kind": kind}
    if kind == "n/a":
        if not nonempty(q.get("reason")):
            raise Fail("quality", "quality.kind=n/a needs a non-empty reason")
        files = [str(x) for x in (eff(task, sset, "implementation", "files") or [])] + \
                [str(x) for x in (task.get("scope") or [])]
        content = task.get("crosscheck_required") is True or any(
            fnmatch.fnmatch(f, g) for f in files for g in ("examples/*", "docs/report/*"))
        if content:
            raise Fail("quality", "content task needs crosscheck|rendered|real-run evidence (n/a refused)")
        out["reason"] = q["reason"]
        return out
    ev = q.get("evidence")
    if not isinstance(ev, list) or not ev:
        raise Fail("quality", "quality.kind=%s needs evidence: >=1 existing non-empty file" % kind)
    for p in ev:
        why = evfile(p)
        if why:
            raise Fail("quality", why)
    out["evidence"] = ev
    if nonempty(q.get("reason")):
        out["reason"] = q["reason"]
    return out


# ---------------------------------------------------------------- spec
def load_spec(t, arg):
    if not arg:
        raise Fail("spec", "missing --spec work/%s/advance-<STATE>.json" % t)
    real = os.path.realpath(arg if os.path.isabs(arg) else os.path.join(ROOT, arg))
    if not real.startswith(os.path.realpath(os.path.join(ROOT, "work", t)) + os.sep):
        raise Fail("spec", "spec must sit under work/%s/" % t)
    try:
        with open(real, encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, ValueError) as e:
        raise Fail("spec", "cannot read spec %s: %s" % (short(arg, 60), short(e, 80)))
    if not isinstance(spec, dict):
        raise Fail("spec", "spec is not a JSON object")
    bad = [k for k in spec if k not in SPEC_KEYS]
    if bad:
        raise Fail("spec", "unknown spec key(s): %s (allowed: %s)" % (", ".join(bad), ", ".join(SPEC_KEYS)))
    return spec


def check_schema(st, spec):
    sset = spec.get("set")
    if not isinstance(sset, dict) or not sset:
        raise Fail("spec", "spec.set must be a non-empty object")
    bad = [k for k in sset if k not in SET_KEYS]
    if bad:
        raise Fail("spec", "set key(s) not allowed: %s (allowed: %s)" % (", ".join(bad), ", ".join(SET_KEYS)))
    for sec, subs in SCHEMA[st].items():
        v = sset.get(sec)
        if not subs:
            if not isinstance(v, list) or not v:
                raise Fail("spec", "set.%s must be a non-empty list for %s" % (sec, st))
            continue
        if not isinstance(v, dict):
            raise Fail("spec", "set.%s is required for %s" % (sec, st))
        for s in subs:
            if s.endswith("[]"):
                if not isinstance(v.get(s[:-2]), list) or not v.get(s[:-2]):
                    raise Fail("spec", "set.%s.%s must be a non-empty list" % (sec, s[:-2]))
            elif not nonempty(v.get(s)):
                raise Fail("spec", "set.%s.%s is required and non-empty for %s" % (sec, s, st))
    nxt = spec.get("next")
    if not isinstance(nxt, str) or (st != "DONE" and not nxt.strip()):
        raise Fail("spec", "spec.next is required (a concrete next step; empty only at DONE)")
    lg = spec.get("log")
    if not isinstance(lg, dict) or not all(nonempty(lg.get(k)) for k in ("action", "result", "decision", "next")):
        raise Fail("spec", "spec.log needs non-empty action, result, decision, next")
    cm = spec.get("commit")
    if not isinstance(cm, dict) or not nonempty(cm.get("subject")):
        raise Fail("spec", "spec.commit.subject is required")
    paths = cm.get("paths", [])
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise Fail("spec", "spec.commit.paths must be a list of strings")
    if "req" in spec and not isinstance(spec["req"], dict):
        raise Fail("spec", "spec.req must be an object")
    if "quality" in spec and st != "DONE":
        raise Fail("spec", "spec.quality is for DONE only")


# ---------------------------------------------------------------- helpers on the task
def has_heading(st, t):
    return re.search(r"^## %s - %s - \S+[ \t]*$" % (re.escape(st), re.escape(t)),
                     read_head(os.path.join(ST, "phase-log.md")), re.M) is not None


def backlog_item(t):
    return next((i for i in _tasks.backlog_items() if i.get("task_id") == t), None)


def backlog_done(t):
    i = backlog_item(t)
    return bool(i) and i.get("status") == "done"


def append_log(st, t, lg):
    ts = _tasks.now()
    entry = "## %s - %s - %s\nAction: %s\nResult: %s\nDecision: %s\nNext: %s" % (
        st, t, ts, one_line(lg["action"]), one_line(lg["result"]), one_line(lg["decision"]),
        one_line(lg["next"]))
    p = os.path.join(ST, "phase-log.md")
    with _tasks.locked(task=t):
        old = read_head(p)
        with open(p, "w", encoding="utf-8") as f:
            f.write(old.rstrip("\n") + "\n\n" + entry + "\n")
    return "## %s - %s - %s" % (st, t, ts)


def one_line(v):
    return " ".join(str(v).split())


def trailers(st, t, task):
    out = ["Task: " + t, "State: " + st]
    if st == "UNIT_TESTED":
        u = task.get("unit_test") or {}
        out.append("Tests: %s -> %s" % (one_line(u.get("command")), one_line(u.get("result"))))
    elif st == "VERIFIED":
        v = task.get("verification") or {}
        out.append("Verified-by: %s -> %s" % (one_line(v.get("command")), one_line(v.get("result"))))
    elif st == "DONE":
        out.append("Report: " + one_line((task.get("report") or {}).get("path")))
    return out


def already(t, st, task, reqs):
    """Step committed already: state, log heading, REQs, clean files, HEAD trailers (32.4 idempotence)."""
    if task.get("state") != st or not has_heading(st, t):
        return None
    if any(ORDER.index(req_status(p)) < ORDER.index(st) for p in reqs if req_status(p) in ORDER):
        return None
    paths = [rel(_tasks.task_path(t)), rel(_tasks.VIEW), rel(os.path.join(ST, "phase-log.md")),
             rel(_tasks.BACKLOG)] + [rel(p) for p in reqs]
    rc, out = git("status", "--porcelain", "--", *paths)
    if rc != 0 or out.strip():
        return None
    rc, msg = git("log", "-1", "--format=%B")
    if rc != 0 or not re.search(r"^Task: %s\s*$" % re.escape(t), msg, re.M) or \
            not re.search(r"^State: %s\s*$" % re.escape(st), msg, re.M):
        return None
    return git("rev-parse", "--short", "HEAD")[1]


def diff_lines(before, after):
    out = []
    for k in sorted(set(before) | set(after)):
        b, a = before.get(k), after.get(k)
        if b == a or k in ("updated_at", "updated_by"):
            continue
        if isinstance(b, dict) and isinstance(a, dict):
            for s in sorted(set(b) | set(a)):
                if b.get(s) != a.get(s):
                    out.append("set %s.%s: %s -> %s" % (k, s, short(b.get(s), 40), short(a.get(s), 60)))
        else:
            out.append("set %s: %s -> %s" % (k, short(b, 40), short(a, 60)))
    return out


# ---------------------------------------------------------------- advance
def advance(t, st, spec_arg, dry):
    if st not in FLOW[1:]:
        raise Fail("state", "unknown target state %s (one of %s)" % (short(st, 20), ", ".join(FLOW[1:])))
    spec = load_spec(t, spec_arg)
    tp = _tasks.task_path(t)
    if not os.path.isfile(tp):
        raise Fail("state", "%s has no task file (not an active task)" % t)
    task = _tasks.load(t)
    cur = task.get("state")
    if cur not in FLOW:
        raise Fail("state", "%s has an invalid state %r" % (t, cur))
    if cur != st:
        if t not in _tasks.active_ids():
            raise Fail("state", "%s is not an active task" % t)
        if FLOW.index(st) != FLOW.index(cur) + 1:
            raise Fail("state", "%s -> %s is not one step (current state of %s: %s)" % (cur, st, t, cur))
    check_schema(st, spec)
    qblock = quality(st, task, spec)
    reqs = req_files_for(t)
    sp_req = spec.get("req") or {}
    if not dry:
        done = already(t, st, task, reqs)
        if done:
            print("PASS (already at %s, %s): %s" % (st, done, t))
            return 0
    # REQ pre-checks: nothing is written when a REQ is too far behind or its Design is empty
    si = ORDER.index(st)
    to_step = []
    for p in reqs:
        s = req_status(p)
        if s in SIDE or s not in ORDER or ORDER.index(s) >= si:
            continue
        if ORDER.index(s) < si - 1:
            raise Fail("req", "%s is %s, more than one step behind %s" % (req_id(p), s, st),
                       "run: advance.sh req-catchup %s (after its TASKs are DONE), or step it with the earlier states" % req_id(p))
        if st == "DESIGN" and design_empty(p):
            raise Fail("req", "%s has an empty ## Design section (the next REQ step, IMPLEMENTING, needs it)" % req_id(p),
                       "write a short ## Design in %s (the main session owns REQ bodies), then re-run" % rel(p))
        to_step.append(p)
    snap_paths = [tp, _tasks.VIEW, os.path.join(ST, "phase-log.md"), _tasks.BACKLOG,
                  os.path.join(REQ_DIR, "STATE.json"), os.path.join(REQ_DIR, "INDEX.md")] + reqs
    snap = snapshot(snap_paths)
    plan = []
    try:
        return _apply(t, st, spec, dry, cur, task, qblock, reqs, to_step, sp_req, snap, plan)
    except Fail:
        restore(snap)
        raise
    except BaseException:
        restore(snap)
        raise


def _apply(t, st, spec, dry, cur, task, qblock, reqs, to_step, sp_req, snap, plan):
    tp = _tasks.task_path(t)
    before = dict(task)
    resume = cur == st
    # 5 fields + state + log
    if not resume:
        patch = dict(spec["set"])
        patch["next"] = spec["next"]
        if st == "DONE":
            rp = dict(patch.get("report") or {})
            dpath = eff(task, spec["set"], "design", "path")
            if not nonempty(rp.get("path")):
                if not nonempty(dpath):
                    raise Fail("spec", "report.path cannot be derived: design.path is empty")
                rp["path"] = "docs/report/" + os.path.basename(dpath)
            patch["report"] = rp
            ver = dict(patch.get("verification") or {})
            ver["quality"] = qblock
            patch["verification"] = ver
        wdir = os.path.join(ROOT, "work", t, "advance")
        os.makedirs(wdir, exist_ok=True)
        wp = os.path.join(wdir, "%s.set.json" % st)
        with open(wp, "w", encoding="utf-8") as f:
            json.dump(patch, f, indent=1)
        rc, out = tasks_sh("set", t, "--merge", rel(wp))
        if rc != 0:
            raise Fail("set", short(first(out, "FAIL"), 200))
        rc, out = tasks_sh("set", t, "--state", st)
        if rc != 0:
            raise Fail("state", short(first(out, "FAIL"), 200))
    task = _tasks.load(t)
    if not has_heading(st, t):
        plan.append("log " + append_log(st, t, spec["log"]))
    else:
        plan.append("log heading present: " + st)
    # DONE: close the backlog item first (workflow-check audits a DONE task against it)
    if st == "DONE" and not backlog_done(t):
        rc, out = run(["bash", os.path.join(SCRIPT_DIR, "backlog.sh"), "complete", t])
        if rc != 0:
            raise Fail("backlog", short(first(out, "FAIL"), 200))
        plan.append("backlog.sh complete " + t)
    # 6 workflow-check
    rc, out = run(["bash", os.path.join(SCRIPT_DIR, "workflow-check.sh"), "--task", t])
    wf = "PASS" if rc == 0 else short(first(out, r"^FAIL"), 200)
    if rc != 0:
        raise Fail("workflow", wf[len("FAIL: "):] if wf.startswith("FAIL: ") else wf)
    # 7 linked REQs
    ev = req_evidence(st, t, task, spec)
    nxt = sp_req.get("next") or spec["next"]
    for p in to_step:
        if req_status(p) == st:
            continue
        step_req(p, st, sp_req, ev, nxt, plan)
    # 9 commit paths
    paths = list(spec["commit"].get("paths") or [])
    if st == "DESIGN":
        paths.append(task["design"]["path"])
    if st == "DONE":
        paths.append(task["report"]["path"])
    paths += [rel(p) for p in changed(snap) if p.startswith(REQ_DIR + os.sep)]
    if st == "DONE":
        paths.append(rel(_tasks.BACKLOG))
    seen, final = set(), []
    for p in paths:
        if p and p not in seen:
            seen.add(p)
            final.append(p)
    if dry:
        for l in diff_lines(before, task):
            print("DRY-RUN: " + l)
        print("DRY-RUN: workflow-check %s" % wf)
        for l in plan:
            print("DRY-RUN: " + l)
        print("DRY-RUN: commit paths: " + ", ".join(final))
        restore(snap)
        print("PASS (dry-run): %s -> %s would commit; files restored" % (t, st))
        return 0
    msgp = os.path.join(ROOT, "work", t, "advance", "%s.msg" % st)
    cm = spec["commit"]
    body = (cm.get("body") or "").strip()
    tr = trailers(st, t, task) + [one_line(x) for x in (cm.get("trailers") or []) if isinstance(x, str)]
    with open(msgp, "w", encoding="utf-8") as f:
        f.write(one_line(cm["subject"]) + "\n\n" + (body + "\n\n" if body else "") + "\n".join(tr) + "\n")
    rc, out = tasks_sh("commit", t, rel(msgp), "--log", "-", "--", *final)
    if rc != 0:
        tail = "\n".join(out.splitlines()[-8:])
        raise Fail("commit", short(first(out, "FAIL"), 200) + ("\n" + tail if tail else ""))
    sha = git("rev-parse", "--short", "HEAD")[1]
    print("PASS: %s -> %s committed %s" % (t, st, sha))
    return 0


def req_evidence(st, t, task, spec):
    r = spec.get("req") or {}
    if nonempty(r.get("evidence")):
        return r["evidence"]
    if st == "UNIT_TESTED":
        u = task.get("unit_test") or {}
        return "%s: %s" % (one_line(u.get("command")), one_line(u.get("result")))
    if st == "VERIFIED":
        v = task.get("verification") or {}
        return "%s: %s" % (one_line(v.get("command")), one_line(v.get("result")))
    return "advance %s -> %s: %s" % (t, st, one_line(spec["log"]["result"]))


# ---------------------------------------------------------------- req-catchup
def catchup(rid, ac_evidence, dry):
    p = os.path.join(REQ_DIR, "items", rid + ".md")
    if not re.fullmatch(r"REQ-[0-9]+", rid) or not os.path.isfile(p):
        raise Fail("req", "no such REQ: %s (docs/req/items/REQ-NNNN.md)" % short(rid, 20))
    txt = read_head(p)
    m = re.search(r"^tasks:\s*\[([^\]]*)\]", txt, re.M)
    tasks = [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()] if m else []
    if not tasks:
        raise Fail("req", "%s has no linked TASK" % rid, "req.py task %s TASK-NNN (main session)" % rid)
    notdone, tinfo = [], []
    for t in tasks:
        tp = _tasks.task_path(t)
        d = _tasks.load(t) if os.path.isfile(tp) else {}
        item = backlog_item(t) or {}
        ok = d.get("state") == "DONE" if d else (item.get("status") == "done" and not item.get("waiver"))
        if not ok:
            notdone.append("%s (%s)" % (t, d.get("state") or item.get("status") or "unknown"))
        tinfo.append(d)
    if notdone:
        raise Fail("req", "linked TASK not DONE: %s" % ", ".join(notdone), "finish the TASK with advance.sh first")
    cur = req_status(p)
    if cur == "DONE":
        print("PASS (already DONE): %s" % rid)
        return 0
    if cur not in ORDER:
        raise Fail("req", "%s is %s; catch-up only handles the six workflow states" % (rid, cur))
    paths = [p, os.path.join(REQ_DIR, "STATE.json"), os.path.join(REQ_DIR, "INDEX.md")]
    snap = snapshot(paths)
    try:
        for s in ORDER[ORDER.index(cur) + 1:]:
            ev = "catch-up: %s DONE" % ", ".join(tasks)
            if s == "IMPLEMENTING" and design_empty(p):
                raise Fail("req", "%s has an empty ## Design section" % rid,
                           "write a short ## Design in %s (the main session owns REQ bodies), then re-run" % rel(p))
            if s == "UNIT_TESTED":
                u = [d.get("unit_test") or {} for d in tinfo if d]
                if u and u[0].get("command"):
                    ev = "%s: %s" % (one_line(u[0].get("command")), one_line(u[0].get("result")))
            if s == "VERIFIED":
                left = re.findall(r"^\s*- \[ \]\s*(AC\d+):(?=[ \t]*\S)", section_raw(read_head(p), "Acceptance"), re.M)
                if left:
                    named = ac_evidence and any(
                        os.path.isfile(os.path.join(ROOT, w.strip(".,;:()[]\"'"))) for w in ac_evidence.split())
                    if not named:
                        raise Fail("req", "unticked Acceptance item(s) %s need --ac-evidence naming an existing file" %
                                   ", ".join(left),
                                   "advance.sh req-catchup %s --ac-evidence \"verified in <report or evidence path>\"" % rid)
                    rc, out = req_py("ac", rid, "all", "--evidence", ac_evidence)
                    if rc != 0:
                        raise req_cmd_fail(out, "req.py ac %s" % rid)
                ev = "catch-up: every linked TASK DONE" + ("; " + ac_evidence if ac_evidence else "")
            rc, out = req_py("status", rid, s, "--evidence", ev)
            if rc != 0:
                raise req_cmd_fail(out, "req.py status %s %s" % (rid, s))
    except BaseException:
        restore(snap)
        raise
    stage = [rel(x) for x in paths if os.path.exists(x)]
    if dry:
        restore(snap)
        print("PASS (dry-run): %s %s -> DONE would be stepped; files restored" % (rid, cur))
        return 0
    print("stage: " + " ".join(stage))
    print("PASS: %s -> DONE (from %s); stage the files above in the main session's commit" % (rid, cur))
    return 0


def section_raw(txt, name):
    m = re.search(r"^## %s[ \t]*\n(.*?)(?=^## |\Z)" % re.escape(name), txt, re.M | re.S)
    return re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S) if m else ""


# ---------------------------------------------------------------- main
def usage():
    print("usage: advance.sh <TASK-N> <STATE> --spec work/<TASK-N>/advance-<STATE>.json [--dry-run]\n"
          "       advance.sh req-catchup <REQ-N> [--ac-evidence \"<text naming an existing file>\"] [--dry-run]")
    return 2


def main(argv):
    dry = "--dry-run" in argv
    a = [x for x in argv if x != "--dry-run"]
    opts = {}
    pos = []
    i = 0
    while i < len(a):
        if a[i] in ("--spec", "--ac-evidence"):
            if i + 1 >= len(a):
                return usage()
            opts[a[i]] = a[i + 1]
            i += 2
        elif a[i].startswith("--"):
            return usage()
        else:
            pos.append(a[i])
            i += 1
    try:
        with run_lock():
            return dispatch(pos, opts, dry)
    except Fail as e:
        print("FAIL [%s]: %s" % (e.gate, e.msg))
        if e.fix:
            print("fix: " + e.fix)
        return 1
    except ValueError as e:
        print("FAIL [spec]: %s" % short(e, 200))
        print("fix: " + FIX["spec"])
        return 1


class run_lock(object):
    """One advance at a time: non-blocking flock on a gitignored file (state stays clean)."""

    def __enter__(self):
        import fcntl
        d = os.path.join(_tasks.ROOT, "work")
        if not os.path.isdir(d):
            os.makedirs(d)
        self.f = open(os.path.join(d, ".advance.lock"), "w")
        try:
            fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            self.f.close()
            raise Fail("lock", "another advance is running", "wait for it to finish, then re-run")
        return self

    def __exit__(self, *exc):
        self.f.close()
        return False


def dispatch(pos, opts, dry):
    if True:
        if len(pos) == 2 and pos[0] == "req-catchup" and "--spec" not in opts:
            return catchup(pos[1], opts.get("--ac-evidence", ""), dry)
        if len(pos) == 2 and re.fullmatch(r"TASK-[0-9]+", pos[0]) and "--ac-evidence" not in opts:
            return advance(pos[0], pos[1].upper(), opts.get("--spec"), dry)
        return usage()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

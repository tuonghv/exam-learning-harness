#!/usr/bin/env python3
"""Tiered unit-test runner (TASK-088 / REQ-0096).

  python3 -I tools/run_tests.py --list
  python3 -I tools/run_tests.py --fast            # all but the slow tier
  python3 -I tools/run_tests.py --affected        # tests covering changed files
  python3 -I tools/run_tests.py --full [--wait]   # gate: HEAD in a throwaway worktree
  python3 -I tools/run_tests.py --time [--fast]   # timing report
  python3 -I tools/run_tests.py --clean           # remove stale worktrees/locks

Registry: config/test_tiers.json (single source). Tests are never edited:
selection is a load-time filter on test ids. Python stdlib only.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

RUNNER_VERSION = "1"
TIMEOUT_S = 1800
WT_PREFIX = "elh-test-"
DEFAULT_CMD = [sys.executable, "-I", "-m", "unittest", "discover", "-s", "tests/unit"]

# ---------------------------------------------------------------- registry


def load_registry(repo):
    path = os.path.join(repo, "config", "test_tiers.json")
    reg = {"threshold_s": 2.0, "slow": [], "known_failures": [], "affected_map": {},
           "affected_ignore": [], "cache_ignore": []}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            reg.update(json.load(fh))
    return reg


def matches(test_id, entries):
    """An entry is a module, class or method id (prefix at a '.' or ' ' boundary)."""
    for e in entries:
        if test_id == e or test_id.startswith(e + ".") or test_id.startswith(e + " "):
            return True
    return False


def tier_of(test_id, reg):
    return "slow" if matches(test_id, reg["slow"]) else "fast"


# ---------------------------------------------------------------- loading


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            for sub in flatten(item):
                yield sub
        else:
            yield item


def load_tests(repo):
    """All tests found by discover, as a flat list (import errors are _FailedTest items)."""
    start = os.path.join(repo, "tests", "unit")
    if start not in sys.path:
        sys.path.insert(0, start)
    return list(flatten(unittest.defaultTestLoader.discover(start, top_level_dir=start)))


def select(tests, reg, tier):
    """tier: 'fast' | 'slow' | 'all'. Load failures are always kept."""
    out = []
    for t in tests:
        if t.__class__.__name__ == "_FailedTest" or tier == "all":
            out.append(t)
        elif tier_of(t.id(), reg) == tier:
            out.append(t)
    return out


def suite_of(tests):
    s = unittest.TestSuite()
    s.addTests(tests)
    return s


# ---------------------------------------------------------------- timing


class TimingResult(unittest.TextTestResult):
    """Per-test wall time; the gap before the first test of a class is charged to the class."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.times = {}
        self.class_times = {}
        self._t0 = None
        self._last_stop = time.monotonic()
        self._last_cls = None

    def startTest(self, test):
        now = time.monotonic()
        cls = "%s.%s" % (test.__class__.__module__, test.__class__.__name__)
        if cls != self._last_cls:
            self.class_times[cls] = self.class_times.get(cls, 0.0) + (now - self._last_stop)
            self._last_cls = cls
        self._t0 = now
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        now = time.monotonic()
        self.times[test.id()] = self.times.get(test.id(), 0.0) + (now - self._t0)
        self._last_stop = now


def run_suite(tests, timing=False, stream=None):
    runner = unittest.TextTestRunner(
        stream=stream or sys.stderr, verbosity=0,
        resultclass=TimingResult if timing else unittest.TextTestResult)
    t0 = time.monotonic()
    result = runner.run(suite_of(tests))
    return result, time.monotonic() - t0


def classify(ids, reg):
    known = [i for i in ids if matches(i, reg["known_failures"])]
    new = [i for i in ids if i not in known]
    return known, new


def result_ids(result):
    ids = []
    for t, _tb in list(result.failures) + list(result.errors):
        i = t.id()
        if i not in ids:
            ids.append(i)
    return ids


def print_verdict(result, dur, reg, skipped_slow):
    ids = result_ids(result)
    known, new = classify(ids, reg)
    ok = result.wasSuccessful()
    print("Ran %d tests in %.1fs" % (result.testsRun, dur))
    print("OK" if ok else "FAILED (failures=%d, errors=%d, skipped=%d)" % (
        len(result.failures), len(result.errors), len(result.skipped)))
    print("KNOWN: %d NEW: %d" % (len(known), len(new)))
    for i in known:
        print("  known  " + i)
    for i in new:
        print("  NEW    " + i)
    print("SKIPPED_SLOW: %d" % skipped_slow)
    print("SKIPPED: %d" % len(result.skipped))
    print("DURATION: %.1f s" % dur)
    return 0 if not new else 1


# ---------------------------------------------------------------- commands


def cmd_list(repo, reg):
    tests = load_tests(repo)
    n_fast = n_slow = 0
    ids = []
    for t in tests:
        i = t.id()
        ids.append(i)
        tr = tier_of(i, reg)
        n_fast += tr == "fast"
        n_slow += tr == "slow"
        print("%s\t%s" % (tr, i))
    rc = 0
    for e in reg["slow"] + reg["known_failures"]:
        if not any(matches(i, [e]) for i in ids):
            print("STALE %s" % e)
            rc = 1
    if n_fast + n_slow != len(tests):
        rc = 1
    print("COUNT all=%d fast=%d slow=%d" % (len(tests), n_fast, n_slow))
    return rc


def cmd_fast(repo, reg):
    tests = load_tests(repo)
    fast = select(tests, reg, "fast")
    result, dur = run_suite(fast)
    return print_verdict(result, dur, reg, len(tests) - len(fast))


def cmd_time(repo, reg, fast_only):
    tests = load_tests(repo)
    chosen = select(tests, reg, "fast" if fast_only else "all")
    result, dur = run_suite(chosen, timing=True)
    times = result.times
    files = {}
    for i, s in times.items():
        files[i.split(".")[0]] = files.get(i.split(".")[0], 0.0) + s
    for c, s in result.class_times.items():
        files[c.split(".")[0]] = files.get(c.split(".")[0], 0.0) + s
    total = sum(times.values()) + sum(result.class_times.values())
    out = {"tests": {k: round(v, 3) for k, v in times.items()},
           "classes": {k: round(v, 3) for k, v in result.class_times.items()},
           "files": {k: round(v, 3) for k, v in files.items()},
           "total_s": round(total, 3), "wall_s": round(dur, 3),
           "failed": result_ids(result)}
    outdir = os.path.join(repo, "work", "test-runs")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "timing-%s.json" % ("fast" if fast_only else "all"))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print("TOP 15 tests")
    for i, s in sorted(times.items(), key=lambda kv: -kv[1])[:15]:
        print("  %7.2f  %s" % (s, i))
    print("TOP class setup (gap before first test)")
    for c, s in sorted(result.class_times.items(), key=lambda kv: -kv[1])[:8]:
        print("  %7.2f  %s" % (s, c))
    print("PER FILE (top 15)")
    for f, s in sorted(files.items(), key=lambda kv: -kv[1])[:15]:
        print("  %7.2f  %s" % (s, f))
    print("TOTAL %.1f s (wall %.1f s) ran=%d -> %s" % (total, dur, result.testsRun, path))
    thr = float(reg["threshold_s"])
    for i, s in sorted(list(times.items()) + list(result.class_times.items()), key=lambda kv: -kv[1]):
        if s > thr and not matches(i, reg["slow"]):
            cls_slow = any(matches(i.rsplit(".", 1)[0], [e]) for e in reg["slow"])
            if not cls_slow:
                print("SUGGEST: %s (%.1f s)" % (i, s))
    return 0


# ---------------------------------------------------------------- affected


def git(repo, *args):
    p = subprocess.run(["git"] + list(args), cwd=repo, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True)
    return p.returncode, p.stdout


def changed_files(repo, base):
    _, a = git(repo, "diff", "--name-only", base or "HEAD")
    _, b = git(repo, "ls-files", "-o", "--exclude-standard")
    seen = []
    for f in (a + b).splitlines():
        if f and f not in seen:
            seen.append(f)
    return seen


def _ignored(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def _import_hits(text, dotted):
    """True if the file imports module `dotted` (import a.b / from a.b import x / from a import b)."""
    if re.search(r"^\s*(?:from|import)\s+%s\b" % re.escape(dotted), text, re.M):
        return True
    if "." in dotted:
        pkg, leaf = dotted.rsplit(".", 1)
        for m in re.finditer(r"^\s*from\s+%s\s+import\s+(\([^)]*\)|[^\n]*)" % re.escape(pkg),
                             text, re.M):
            if re.search(r"\b%s\b" % re.escape(leaf), m.group(1)):
                return True
    return False


def map_file(repo, path, test_files, reg):
    """-> {test_module: reason} for one changed file."""
    hits = {}
    mods = [os.path.splitext(os.path.basename(f))[0] for f in test_files]
    if path.startswith("tests/unit/") and path.endswith(".py"):
        mod = os.path.splitext(os.path.basename(path))[0]
        if mod in mods:
            hits[mod] = "test file changed"
        for m, f in zip(mods, test_files):
            if m != mod and _import_hits(_read(repo, f), mod):
                hits.setdefault(m, "imports changed test helper %s" % mod)
    for pat, tmods in reg["affected_map"].items():
        if fnmatch.fnmatch(path, pat):
            for m in tmods:
                hits.setdefault(m, "affected_map %s" % pat)
    if path.startswith("src/") and path.endswith(".py"):
        rel = path[4:-3].split("/")
        if rel[-1] == "__init__":
            rel = rel[:-1]
        dotted = ".".join(rel)
        leaf = rel[-1] if rel else ""
        for m, f in zip(mods, test_files):
            if m == "test_" + leaf or m.startswith("test_" + leaf + "_"):
                hits.setdefault(m, "name matches %s" % leaf)
            elif dotted and _import_hits(_read(repo, f), dotted):
                hits.setdefault(m, "imports %s" % dotted)
    if path.startswith("tools/") and path.endswith(".py"):
        base = os.path.basename(path)
        for m, f in zip(mods, test_files):
            txt = _read(repo, f)
            if path in txt or base in txt:
                hits.setdefault(m, "mentions %s" % base)
    return hits


_cache = {}


def _read(repo, rel):
    key = (repo, rel)
    if key not in _cache:
        try:
            with open(os.path.join(repo, rel), encoding="utf-8", errors="replace") as fh:
                _cache[key] = fh.read()
        except OSError:
            _cache[key] = ""
    return _cache[key]


def cmd_affected(repo, reg, base, files, with_slow):
    changed = files if files else changed_files(repo, base)
    changed = [f for f in changed if not _ignored(f, reg["affected_ignore"])]
    if not changed:
        print("NOTHING CHANGED")
        return 0
    tdir = os.path.join(repo, "tests", "unit")
    test_files = sorted("tests/unit/" + f for f in os.listdir(tdir)
                        if f.startswith("test_") and f.endswith(".py"))
    chosen = {}
    for f in changed:
        hit = map_file(repo, f, test_files, reg)
        if not hit:
            print("FALLBACK --fast (%s unmapped)" % f)
            return cmd_fast(repo, reg)
        for m, why in hit.items():
            chosen.setdefault(m, "%s: %s" % (f, why))
    for m in sorted(chosen):
        print("%s\t%s" % (m, chosen[m]))
    tests = [t for t in load_tests(repo)
             if t.__class__.__name__ == "_FailedTest" and t.id().split(".")[-1] in chosen
             or t.id().split(".")[0] in chosen]
    run, skipped = [], 0
    for t in tests:
        if not with_slow and t.__class__.__name__ != "_FailedTest" and tier_of(t.id(), reg) == "slow":
            skipped += 1
            continue
        run.append(t)
    shown = []
    for t in tests:
        if t not in run:
            sid = next((e for e in reg["slow"] if matches(t.id(), [e])), t.id())
            if sid not in shown:
                shown.append(sid)
                print("SKIPPED_SLOW %s (gate covers)" % sid)
    result, dur = run_suite(run)
    return print_verdict(result, dur, reg, skipped)


# ---------------------------------------------------------------- full gate


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def tree_key(repo, reg):
    _, out = git(repo, "ls-tree", "-r", "HEAD")
    ign = tuple(reg["cache_ignore"])
    lines = [ln for ln in out.splitlines() if not ln.split("\t", 1)[-1].startswith(ign)]
    h = hashlib.sha256()
    h.update("\n".join(lines).encode("utf-8"))
    h.update(("|py%d.%d|v%s" % (sys.version_info[0], sys.version_info[1], RUNNER_VERSION)).encode())
    return h.hexdigest()[:16]


def dirty_count(repo, reg):
    _, out = git(repo, "status", "--porcelain", "--untracked-files=no")
    ign = tuple(reg["cache_ignore"])
    n = 0
    for ln in out.splitlines():
        p = ln[3:].split(" -> ")[-1].strip('"')
        if not p.startswith(ign):
            n += 1
    return n


def write_json(path, data):
    tmp = path + ".tmp%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def acquire_lock(outdir):
    lock = os.path.join(outdir, ".full.lock")
    for _ in range(2):
        try:
            os.mkdir(lock)
            with open(os.path.join(lock, "pid"), "w") as fh:
                fh.write(str(os.getpid()))
            return lock
        except FileExistsError:
            try:
                with open(os.path.join(lock, "pid")) as fh:
                    pid = fh.read().strip()
            except OSError:
                pid = ""
            if pid_alive(pid):
                return None
            shutil.rmtree(lock, ignore_errors=True)
    return None


def worktree_paths(repo):
    _, out = git(repo, "worktree", "list", "--porcelain")
    return [ln[9:] for ln in out.splitlines() if ln.startswith("worktree ")]


def cleanup_stale(repo, keep=None):
    """Prune dead registrations and drop leftover elh-test-* worktrees (caller holds the lock)."""
    git(repo, "worktree", "prune")
    n = 0
    for p in worktree_paths(repo):
        if os.path.basename(p).startswith(WT_PREFIX) and p != keep:
            git(repo, "worktree", "remove", "--force", p)
            shutil.rmtree(p, ignore_errors=True)
            n += 1
    git(repo, "worktree", "prune")
    return n


def assert_outside(repo, path):
    r, p = os.path.realpath(repo), os.path.realpath(path)
    if p == r or p.startswith(r + os.sep):
        print("REFUSED: worktree path %s is inside the repo" % p, file=sys.stderr)
        sys.exit(2)


FAIL_RE = re.compile(r"^(FAIL|ERROR): (\S+) \(([\w.]+)\)", re.M)
RAN_RE = re.compile(r"^Ran (\d+) tests? in ([\d.]+)s", re.M)
END_RE = re.compile(r"^(OK|FAILED)(?: \(([^)]*)\))?\s*$", re.M)


def parse_output(text, reg):
    """3.10 'FAIL: test_x (mod.Cls)' and 3.11+ 'FAIL: test_x (mod.Cls.test_x)' -> ids."""
    ids = []
    for _kind, name, ctx in FAIL_RE.findall(text):
        i = ctx if ctx.endswith("." + name) else ctx + "." + name
        if i not in ids:
            ids.append(i)
    known, new = classify(ids, reg)
    ran = RAN_RE.search(text)
    end = END_RE.findall(text)
    detail = end[-1][1] if end else ""
    m = re.search(r"skipped=(\d+)", detail)
    return {"ran": int(ran.group(1)) if ran else 0,
            "summary": ("%s (%s)" % (end[-1][0], detail) if detail else end[-1][0]) if end else "NO RESULT",
            "failed": ids, "known": known, "new": new,
            "skipped": int(m.group(1)) if m else 0}


def run_gate(repo, reg, key, head, outdir, cmd, timeout=TIMEOUT_S):
    """Child step: run `cmd` in a throwaway worktree of `head`; always remove it."""
    result_path = os.path.join(outdir, key + ".json")
    started = time.time()
    base = {"status": "running", "pid": os.getpid(), "key": key, "head": head,
            "started": started, "cmd": " ".join(cmd)}
    lock = acquire_lock(outdir)
    if lock is None:
        print("LOCKED: another --full is running", file=sys.stderr)
        return 3
    wt = None
    res = dict(base)
    try:
        write_json(result_path, base)
        cleanup_stale(repo)
        wt = tempfile.mkdtemp(prefix=WT_PREFIX)
        assert_outside(repo, wt)
        rc_add, _ = git(repo, "worktree", "add", "--detach", wt, head)
        if rc_add != 0:
            res.update(status="error", rc=2, error="git worktree add failed")
            return 2
        env = {k: v for k, v in os.environ.items() if k not in ("TASK", "CTXGUARD_TASK")}
        env["CLAUDE_PROJECT_DIR"] = wt
        logp = os.path.join(outdir, key + ".out")
        with open(logp, "w", encoding="utf-8") as lf:
            proc = subprocess.Popen(cmd, cwd=wt, env=env, stdin=subprocess.DEVNULL,
                                    stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                rc = proc.wait(timeout=timeout)
                status = "done"
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                rc, status = 124, "timeout"
                print("TIMEOUT %d s" % timeout)
        with open(logp, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        res.update(parse_output(text, reg))
        res.update(status=status, rc=rc, gate_ok=(status == "done" and not res["new"]),
                   duration_s=round(time.time() - started, 1), log=logp)
        return 0 if res.get("gate_ok") else 1
    except Exception as exc:  # recorded, then re-raised after cleanup
        res.update(status="error", rc=2, error=repr(exc))
        raise
    finally:
        removed = True
        if wt:
            git(repo, "worktree", "remove", "--force", wt)
            shutil.rmtree(wt, ignore_errors=True)
            git(repo, "worktree", "prune")
            removed = not os.path.exists(wt)
        res.update(worktree_removed=removed, dirty=dirty_count(repo, reg))
        if res.get("status") == "running":
            res["status"] = "error"
        write_json(result_path, res)
        shutil.rmtree(lock, ignore_errors=True)


def print_summary(r):
    print("%s ran=%s rc=%s known=%d new=%d skipped=%s %ss" % (
        r.get("summary"), r.get("ran"), r.get("rc"), len(r.get("known", [])),
        len(r.get("new", [])), r.get("skipped"), r.get("duration_s")))
    for i in r.get("new", []):
        print("  NEW  " + i)


def result_exit(r):
    if r.get("status") != "done":
        return 2
    return 0 if r.get("gate_ok") else 1


def cmd_full(repo, reg, args, outdir):
    os.makedirs(outdir, exist_ok=True)
    cmd = shlex.split(args.test_cmd) if args.test_cmd else list(DEFAULT_CMD)
    if args.child:
        return run_gate(repo, reg, args.key, args.head, outdir, cmd)
    key = tree_key(repo, reg)
    _, head = git(repo, "rev-parse", "HEAD")
    head = head.strip()
    n = dirty_count(repo, reg)
    if n:
        print("DIRTY: %d files not in the gate (commit first)" % n)
    path = os.path.join(outdir, key + ".json")
    old = read_json(path)
    if old and not args.force:
        if old.get("status") == "done":
            print("REUSED %s" % path)
            print_summary(old)
            return result_exit(old)
        if old.get("status") == "running":
            if pid_alive(old.get("pid")):
                print("RUNNING pid %s -> %s" % (old.get("pid"), path))
                return 0
            print("STALE RUN %s, restarting" % key)
    if args.wait:
        rc = run_gate(repo, reg, key, head, outdir, cmd)
        r = read_json(path) or {}
        print("RESULT %s" % path)
        print_summary(r)
        return rc
    child = [sys.executable, "-I", os.path.abspath(__file__), "--repo", repo, "--out", outdir,
             "--full", "--child", "--key", key, "--head", head]
    if args.test_cmd:
        child += ["--test-cmd", args.test_cmd]
    log = open(os.path.join(outdir, key + ".log"), "w")
    proc = subprocess.Popen(child, cwd=repo, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                            start_new_session=True)
    write_json(path, {"status": "running", "pid": proc.pid, "key": key, "head": head,
                      "started": time.time()})
    print("STARTED pid %d -> %s" % (proc.pid, path))
    return 0


def cmd_clean(repo):
    n = cleanup_stale(repo)
    print("CLEANED %d stale worktrees" % n)
    return 0


# ---------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--fast", action="store_true", help="run all but the slow tier")
    mode.add_argument("--affected", action="store_true", help="run tests covering changed files")
    mode.add_argument("--full", action="store_true", help="gate: HEAD in a worktree, detached")
    mode.add_argument("--list", action="store_true", help="tier of every test + COUNT")
    mode.add_argument("--clean", action="store_true", help="remove stale worktrees")
    ap.add_argument("--time", action="store_true",
                    help="timing report in-process (all tests; with --fast only the fast tier)")
    ap.add_argument("--wait", action="store_true", help="--full in the foreground")
    ap.add_argument("--force", action="store_true", help="--full ignores a stored result")
    ap.add_argument("--base", help="--affected: diff against REV (default HEAD)")
    ap.add_argument("--files", nargs="+", help="--affected: use these paths as the change set")
    ap.add_argument("--with-slow", action="store_true", help="--affected: also run slow tests")
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    ap.add_argument("--out", help="result dir (default <repo>/work/test-runs)")
    ap.add_argument("--test-cmd", help="--full: command run in the worktree (default unittest discover)")
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--key", help=argparse.SUPPRESS)
    ap.add_argument("--head", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    repo = os.path.realpath(args.repo)
    os.chdir(repo)
    reg = load_registry(repo)
    outdir = args.out or os.path.join(repo, "work", "test-runs")
    if args.time:
        return cmd_time(repo, reg, fast_only=args.fast)
    if args.list:
        return cmd_list(repo, reg)
    if args.fast:
        return cmd_fast(repo, reg)
    if args.affected:
        return cmd_affected(repo, reg, args.base, args.files, args.with_slow)
    if args.full:
        return cmd_full(repo, reg, args, outdir)
    if args.clean:
        return cmd_clean(repo)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())

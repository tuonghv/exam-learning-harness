#!/usr/bin/env python3
"""Advisory post-commit checks on HEAD (TASK-149, REQ-0155). Never blocks: always exit 0.

Prints `post-commit: WARN <check>: ...` per issue, or `post-commit: OK <sha>`, on stderr.
  left-behind  tracked files still changed (staged, modified or deleted) after the commit
  big-file     a file added or changed by HEAD is larger than BIG_BYTES
  no-task      HEAD changes code (src/, tools/, tests/, .claude/ scripts) without a `Task:` trailer
  ledger       HEAD touched review reports or the findings ledger and tools/review_ledger.py reports problems
Off with POST_COMMIT_CHECK=0. Run by .githooks/post-commit (git config core.hooksPath .githooks).
--stale-backup (TASK-150, REQ-0156): exit 0 when a file under plans/, input/ or config/published_reports.json is
newer than the newest ~/exam-harness-backup/exam-inputs-*.tar.gz (or none exists), else 1; prints nothing.
Usage: python3 -I tools/post_commit_check.py [--root DIR] [--stale-backup [--backup-dir DIR]]
"""
import argparse
import os
import re
import subprocess
import sys

BIG_BYTES = 1024 * 1024
SHOW = 5
CODE = re.compile(r"^(src|tools|tests)/|^\.claude/(scripts|hooks|req)/|^\.githooks/")
LEDGER = re.compile(r"^docs/report/fable-review/|^docs/review/")
TASK = re.compile(r"(?m)^Task: TASK-\d+\s*$")


def git(root, *args):
    r = subprocess.run(("git", "-C", root) + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, timeout=10)
    if r.returncode:
        raise RuntimeError("git %s: %s" % (args[0], r.stderr.strip()[:120]))
    return r.stdout


def head_files(root):
    """[(status, path)] of HEAD vs its first parent (root commit: all files)."""
    out = git(root, "diff-tree", "--root", "--no-commit-id", "-r", "-z", "--name-status", "--no-renames", "HEAD")
    parts = [p for p in out.split("\0") if p]
    return list(zip(parts[0::2], parts[1::2]))


def left_behind(root):
    out = git(root, "status", "--porcelain", "-z", "--untracked-files=no")
    paths = [e[3:] for e in out.split("\0") if len(e) > 3]
    if not paths:
        return []
    paths.sort(key=lambda p: (not p.startswith(".claude/state/"), p))
    more = " (+%d more)" % (len(paths) - SHOW) if len(paths) > SHOW else ""
    return ["left-behind: %d tracked file(s) still changed after the commit: %s%s"
            % (len(paths), ", ".join(paths[:SHOW]), more)]


def big_files(root, files):
    out = []
    for st, p in files:
        if st == "D":
            continue
        size = int(git(root, "cat-file", "-s", "HEAD:" + p).strip() or 0)
        if size > BIG_BYTES:
            out.append("big-file: %s is %.1f MiB (committed by HEAD; meant to be tracked?)" % (p, size / 1048576.0))
    return out


def no_task(root, files):
    code = [p for _, p in files if CODE.search(p)]
    if not code or TASK.search(git(root, "log", "-1", "--format=%B", "HEAD")):
        return []
    return ["no-task: code changed without a `Task:` trailer (one task per commit): %s"
            % ", ".join(code[:SHOW])]


def ledger(root, files):
    if not any(LEDGER.search(p) for _, p in files):
        return []
    sys.path.insert(0, os.path.join(root, "tools"))
    sys.dont_write_bytecode = True  # a hook leaves no files behind
    import review_ledger  # noqa: E402 - repo tool, only when needed
    _, _, probs = review_ledger.check(root)
    return ["ledger: " + p for p in probs[:SHOW]]


BACKUP_SOURCES = ("plans", "input", "config/published_reports.json")


def newest_mtime(path):
    if os.path.isfile(path):
        return os.path.getmtime(path)
    best = 0.0
    for d, _, files in os.walk(path):
        for f in files:
            try:
                best = max(best, os.path.getmtime(os.path.join(d, f)))
            except OSError:
                pass
    return best


def backup_stale(root, backup_dir):
    """True when the ignored inputs/outputs changed after the newest backup archive."""
    data = max([newest_mtime(os.path.join(root, s)) for s in BACKUP_SOURCES] + [0.0])
    if not data:
        return False
    try:
        arcs = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
                if f.startswith("exam-inputs-") and f.endswith(".tar.gz")]
    except OSError:
        arcs = []
    last = max([os.path.getmtime(a) for a in arcs] + [0.0])
    return data > last


def run(root):
    files = head_files(root)
    warns = left_behind(root) + big_files(root, files) + no_task(root, files) + ledger(root, files)
    if warns:
        return ["post-commit: WARN " + w for w in warns]
    return ["post-commit: OK " + git(root, "rev-parse", "--short", "HEAD").strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--stale-backup", action="store_true")
    ap.add_argument("--backup-dir", default=os.path.expanduser(os.path.join("~", "exam-harness-backup")))
    a = ap.parse_args(argv)
    if a.stale_backup:
        try:
            return 0 if backup_stale(a.root, a.backup_dir) else 1
        except Exception:  # noqa: BLE001 - advisory
            return 1
    if os.environ.get("POST_COMMIT_CHECK") == "0":
        return 0
    try:
        lines = run(a.root)
    except Exception as exc:  # noqa: BLE001 - advisory hook: never break a commit
        lines = ["post-commit: skipped (%s)" % exc]
    for ln in lines:
        print(ln, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

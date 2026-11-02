#!/usr/bin/env python3
"""User-facing evidence (TASK-057, REQ-0061; design phase-57). Stdlib only, pure regex: no exam or key file is read.

  _evidence.py scan <file|dir>...        refuse exam text / answer keys / URLs / secrets / oversize (rc 1)
  _evidence.py publish TASK-N <src>...   work/TASK-N/... -> docs/report/evidence/TASK-N/ (scan first, redact paths)
  _evidence.py index [--check]           regenerate docs/report/INDEX.md (--check: rc 1 when stale)
Roles cannot write docs/report: main runs publish/index (advance.sh VERIFIED/DONE).
"""
import glob
import json
import os
import re
import sys

sys.dont_write_bytecode = True

ROOT = os.environ.get("TASKS_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR") or os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
EXTS = (".txt", ".md", ".tsv")
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.(txt|md|tsv)$")
MAX_LINES, MAX_BYTES, MAX_FILES, MAX_DIR_BYTES = 200, 32 * 1024, 20, 256 * 1024
RE_HEAD = re.compile(r"^#{1,3}\s*(Question|Passage|Câu)\b\s*\d*")
RE_OPT = re.compile(r"^\s*([A-Ea-e])[.)]\s+\S")
RE_ANSLINE = re.compile(r"(?i)^\W*(final|correct)\s+answer\s*:|đáp án\s*:")
RE_ANSJSON = re.compile(r'"answer"\s*:\s*"[A-Ea-e](-[a-e])*"')
RE_ANSTSV = re.compile(r"^\s*\d{1,3}[\t ,:.]+[A-Ea-e]\s*$")
RE_URL = re.compile(r"https?://")
RE_SECRET = re.compile(r"(?<![A-Za-z])sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|"
                       r"-----BEGIN [A-Z ]*PRIVATE KEY|(?i:(api[_-]?key|password|secret|token))\s*[=:]\s*\S{8,}")


def scan_bytes(label, data):
    """-> [(label, line, rule)] for one file's bytes; label's extension is checked."""
    out = []
    if not label.lower().endswith(EXTS):
        out.append((label, 0, "ext"))
    if b"\x00" in data:
        return out + [(label, 0, "binary")]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return out + [(label, 0, "binary")]
    lines = text.splitlines()
    if len(lines) > MAX_LINES or len(data) > MAX_BYTES:
        out.append((label, 0, "size"))
    opts, tsv = [], []
    for n, l in enumerate(lines, 1):
        for rx, rule in ((RE_HEAD, "exam-heading"), (RE_ANSLINE, "answer-line"), (RE_ANSJSON, "answer-json"),
                         (RE_URL, "url"), (RE_SECRET, "secret")):
            if rx.search(l):
                out.append((label, n, rule))
        m = RE_OPT.match(l)
        if m:
            opts.append((n, m.group(1).upper()))
        if RE_ANSTSV.match(l):
            tsv.append(n)
    for i, (n, c) in enumerate(opts):
        if any(n2 - n <= 6 and c2 != c for n2, c2 in opts[i + 1:]):
            out.append((label, n, "options"))
            break
    if len(tsv) >= 3:
        out.append((label, tsv[0], "answer-tsv"))
    return out


PRIVATE = ("plans", "reports")  # git-ignored dirs holding exam text and answers


def private_dir(path, root=None):
    """True when path is under plans/ or reports/ (first component inside the repo, any component outside)."""
    root = os.path.abspath(root or ROOT)
    rel = os.path.relpath(os.path.abspath(os.path.join(root, path)), root)
    parts = rel.replace("\\", "/").split("/")
    return (parts[0] in PRIVATE) if not rel.startswith("..") else any(c in PRIVATE for c in path.split("/"))


def scan_file(path):
    if private_dir(path):
        return [(path, 0, "private-dir")]
    with open(path, "rb") as f:
        return scan_bytes(path, f.read())


def scan_paths(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for dp, _, fs in sorted(os.walk(p)):
                files = sorted(os.path.join(dp, f) for f in fs)
                if len(files) > MAX_FILES or sum(os.path.getsize(f) for f in files) > MAX_DIR_BYTES:
                    out.append((dp, 0, "size"))
                for f in files:
                    out += scan_file(f)
        elif os.path.isfile(p):
            out += scan_file(p)
        else:
            out.append((p, 0, "missing"))
    return out


def redact(root, text):
    """G1: no local username or checkout path in published files."""
    text = text.replace(root.rstrip("/"), ".")
    return re.sub(r"/home/[^/\s]+", "/home/<user>", text)


def publish(root, task, srcs):
    """-> (dests, errors); all-or-nothing, idempotent (same bytes are not rewritten)."""
    errs, jobs = [], []
    prefix = "work/%s/" % task
    for s in srcs:
        norm = os.path.normpath(s)
        base = os.path.basename(norm)
        if any(c in PRIVATE for c in s.split("/")):
            errs.append("FAIL: %s:0 private-dir" % s)
        elif ".." in s.split("/") or not s.startswith(prefix) or os.path.isabs(s):
            errs.append("FAIL: %s outside %s" % (s, prefix))
        elif not NAME_RE.match(base):
            errs.append("FAIL: %s name (want %s)" % (s, NAME_RE.pattern))
        elif not os.path.isfile(os.path.join(root, s)):
            errs.append("FAIL: %s missing" % s)
        elif os.path.islink(os.path.join(root, s)) or os.path.realpath(os.path.join(root, s)).find(os.path.realpath(os.path.join(root, prefix))) != 0:
            errs.append("FAIL: %s symlink or outside %s" % (s, prefix))
        else:
            with open(os.path.join(root, s), "rb") as f:
                raw = f.read()
            try:
                data = redact(root, raw.decode("utf-8")).encode("utf-8")
            except UnicodeDecodeError:
                data = raw
            for _, n, rule in scan_bytes(base, data):
                errs.append("FAIL: %s:%d %s" % (s, n, rule))
            jobs.append(("docs/report/evidence/%s/%s" % (task, base), data))
    if errs:
        return [], errs
    for dest, data in jobs:
        full = os.path.join(root, dest)
        if os.path.isfile(full):
            with open(full, "rb") as f:
                if f.read() == data:
                    continue
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)
    return [d for d, _ in jobs], []


HEADER = """# Where to crosscheck (user-facing paths)

Generated by `.claude/scripts/_evidence.py index` (advance.sh DONE); do not edit by hand.
`work/` is the agents' scratch area (git-ignored). Everything you need to check a result is in these committed paths.

| Kind | Path |
|---|---|
| Plans / designs | `docs/design/phase-N-*.md` |
| Reports (verdict, limits) | `docs/report/phase-N-*.md` |
| Evidence summaries (test output, recount TSV, metrics, verify/test handoffs) | `docs/report/evidence/TASK-NNN/` |
| Requirements and their status | `docs/req/items/REQ-NNNN.md` |
| Run history (git-ignored, answer letters) | `reports/run-history.jsonl` via `exam.py run-stats trend` |

| Task | Design | Report | Evidence | Run history | Review pack |
|---|---|---|---|---|---|
"""
FOOTER = ("\nRule (RAW-00171, REQ-0061): evidence summaries are small text with no exam content or answer "
          "keys; heavy artifacts stay in `work/` and are only referenced (workflow-roles.md section 9).\n")


def _num(t):
    return int(re.sub(r"\D", "", t) or 0)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def index_text(root):
    with open(os.path.join(root, ".claude", "state", "backlog.json"), encoding="utf-8") as f:
        items = json.load(f)
    rows = []
    for it in sorted(items, key=lambda i: _num(i.get("task_id", ""))):
        t = it.get("task_id", "")
        edir = os.path.join(root, "docs", "report", "evidence", t)
        efiles = sorted(os.listdir(edir)) if os.path.isdir(edir) else []
        if it.get("status") != "done" and not efiles:
            continue
        design = ""
        try:
            design = json.loads(_read(os.path.join(root, ".claude", "state", "task.%s.json" % t)))["design"]["path"]
        except (ValueError, KeyError, TypeError):
            pass
        if not design or not os.path.isfile(os.path.join(root, design)):
            g = sorted(glob.glob(os.path.join(root, "docs", "design", "phase-%d-*.md" % _num(t))))
            design = os.path.relpath(g[0], root) if g else ""
        report = it.get("report") or ""
        rtext = _read(os.path.join(root, report)) if report else ""
        if not rtext:
            report = ""
        hist = re.search(r"(?:reports|results)/run-history[A-Za-z0-9_.-]*", rtext)
        rev = re.search(r"review/[^\s`)|,;]*", rtext)
        title = (it.get("title") or "").replace("|", "/")[:40].rstrip()
        cells = ["%s %s" % (t, title), design, report,
                 "docs/report/evidence/%s/ (%d)" % (t, len(efiles)) if efiles else "",
                 hist.group(0) if hist else "", rev.group(0) if rev else ""]
        rows.append("| " + " | ".join(c if c else "-" for c in cells) + " |")
    return HEADER + "\n".join(rows) + "\n" + FOOTER


def index(root, check):
    path = os.path.join(root, "docs", "report", "INDEX.md")
    new = index_text(root)
    if _read(path) == new:
        return 0
    if check:
        print("FAIL: docs/report/INDEX.md is stale (run _evidence.py index)")
        return 1
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print("wrote docs/report/INDEX.md")
    return 0


def main(argv):
    if len(argv) >= 2 and argv[0] == "scan":
        hits = scan_paths(argv[1:])
        for p, n, rule in hits:
            print("FAIL: %s:%d %s" % (p, n, rule))
        return 1 if hits else 0
    if len(argv) >= 3 and argv[0] == "publish":
        dests, errs = publish(ROOT, argv[1], argv[2:])
        for e in errs:
            print(e)
        for d in dests:
            print(d)
        return 1 if errs else 0
    if argv and argv[0] == "index" and argv[1:] in ([], ["--check"]):
        return index(ROOT, bool(argv[1:]))
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

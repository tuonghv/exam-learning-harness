#!/usr/bin/env python3
"""lessons.py - role lessons helper (TASK-074, design phase-74 item 74.2). Stdlib only, Python 3.8.

  lessons.py [--root DIR] collect <work_dir>...      new lessons as JSONL + `TOTAL new=N seen=N bad=N`
  lessons.py [--root DIR] similar "<text>" [--top N] path:line score raw=<RAW-id|->
  lessons.py [--root DIR] patch --file F --anchor LINE (--replace T | --after T) --out work/<T>/patches/NN-slug.py
  lessons.py [--root DIR] mark-from <curate.md> [--base REV]  append verdicts to .claude/lessons/ledger.jsonl (only writer)
  lessons.py [--root DIR] watch [--set KEY kept|reverted|kept-unproven]   skill edits under watch (74.7)
  lessons.py [--root DIR] revert KEY   undo a watch row's skill edit (multi-line block), status reverted
  lessons.py [--root DIR] scope [--base REV] [--allow GLOB]...

Root: --root, else env LESSONS_ROOT, else the repo this script lives in.
Exit: 0 ok, 1 usage/input error, 2 key already in ledger or no-evidence applied/merged row (mark-from), unknown watch key, 3 path outside allowed set,
4 skill grew over 80 lines or agent frontmatter changed (scope), 6 drift rows found (drift).

  lessons.py [--root DIR] drift [--task T | --base REV] [--all] [--sweep-every N] [--emit work/<T>] [--skills a,b]
    TSV `MISSING|CHANGED<TAB>skill_file:line<TAB>class<TAB>token<TAB>detail` + `TOTAL missing=N changed=N` (TASK-103).
    No --task/--base means --all. --emit writes work/<T>/handoff/drift.md (kind=stale lessons).
"""
import argparse
import fnmatch
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True

KINDS = ("missing-skill", "wrong-rule", "repeat-failure", "tip", "stale")
APP_SKILLS = ("api-platform-security", "run-security-review", "ext-scan", "pentest-report-qa")
CODE_EXT = (".sh", ".py", ".yml", ".yaml", ".json")
VERDICTS = ("merged", "merge", "new", "applied", "rejected", "reject")
LESSON_RE = re.compile(
    r"^- L: kind=(\S+) target=(\S+) \| (.+?) \| evidence=(\S.*)$")
KEY_RE = re.compile(r"^[0-9a-f]{64}$")
TASK_RE = re.compile(r"^[A-Za-z0-9_-]+$")
PATCH_NAME_RE = re.compile(r"^[0-9]{2}-[a-z0-9][a-z0-9-]*\.py$")
REV_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._/~^@{}-]*$")
HEAD_RE = re.compile(r"^#{2,3}\s+lessons\s*$", re.I)
ANY_HEAD_RE = re.compile(r"^#{1,6}\s")
SKILL_LIMIT = 80
STOP = {"the", "and", "for", "that", "this", "with", "from", "are", "not",
        "you", "use", "one", "any", "all", "its", "has", "have", "when", "into"}


class Fail(Exception):
    def __init__(self, msg, rc=1):
        Exception.__init__(self, msg)
        self.rc = rc


def default_root():
    env = os.environ.get("LESSONS_ROOT")
    if env:
        return os.path.realpath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.realpath(os.path.join(here, "..", ".."))


def inside(root, path):
    """realpath of path if it is root or below root, else raise."""
    real = os.path.realpath(path)
    if real != root and not real.startswith(root + os.sep):
        raise Fail("path outside root: %s" % path)
    return real


def rel(root, path):
    return os.path.relpath(path, root)


def ledger_path(root):
    return os.path.join(root, ".claude", "lessons", "ledger.jsonl")


def read_ledger(root):
    keys = set()
    p = ledger_path(root)
    if not os.path.isfile(p):
        return keys
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                k = json.loads(line).get("key")
            except ValueError:
                continue
            if isinstance(k, str):
                keys.add(k)
    return keys


def evidence_ok(root, ev):
    """True when ev names an existing repo file (optional :line or #anchor)."""
    ev = (ev or "").strip().split()[0] if (ev or "").strip() else ""
    if not ev or ev == "-":
        return False
    path = re.split(r"[:#]", ev, 1)[0]
    if not path:
        return False
    try:
        real = inside(root, os.path.join(root, path))
    except Fail:
        return False
    return os.path.isfile(real)


def lesson_key(task, role, text):
    return hashlib.sha256(("%s|%s|%s" % (task, role, text)).encode("utf-8")).hexdigest()


def parse_work_dir(root, wd):
    """(lessons, bad) for one work/<TASK> dir."""
    real = inside(os.path.join(root, "work"), wd if os.path.isabs(wd) else os.path.join(os.getcwd(), wd))
    task = os.path.basename(real)
    if not TASK_RE.match(task):
        raise Fail("bad task dir name: %s" % task)
    hdir = os.path.join(real, "handoff")
    lessons, bad = [], 0
    if not os.path.isdir(hdir):
        return lessons, bad
    for name in sorted(os.listdir(hdir)):
        if not name.endswith(".md"):
            continue
        role = name[:-3]
        path = os.path.join(hdir, name)
        if not os.path.isfile(path):
            continue
        in_sec = False
        with open(path, encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if ANY_HEAD_RE.match(line):
                    in_sec = bool(HEAD_RE.match(line))
                    continue
                if not in_sec or not line.startswith("- L:"):
                    continue
                m = LESSON_RE.match(line)
                if not m or m.group(1) not in KINDS:
                    bad += 1
                    continue
                kind, target, text, ev = m.groups()
                lessons.append({
                    "key": lesson_key("stale" if kind == "stale" else task, role, text), "task": task, "role": role,
                    "file": rel(root, path), "kind": kind, "target": target,
                    "text": text, "evidence": ev.strip()})
    return lessons, bad


def cmd_collect(root, a):
    seen_keys = read_ledger(root)
    new = seen = bad = 0
    emitted = set()
    for wd in a.work_dirs:
        lessons, b = parse_work_dir(root, wd)
        bad += b
        for item in lessons:
            if item["key"] in seen_keys or item["key"] in emitted:
                seen += 1
                continue
            emitted.add(item["key"])
            item["evidence_ok"] = evidence_ok(root, item["evidence"])
            new += 1
            print(json.dumps(item, sort_keys=True))
    print("TOTAL new=%d seen=%d bad=%d" % (new, seen, bad))
    return 0


def tokens(text):
    return set(t for t in re.findall(r"[a-z0-9]{3,}", text.lower()) if t not in STOP)


def corpus(root):
    files = []
    sk = os.path.join(root, ".claude", "skills")
    for dp, _dn, fn in os.walk(sk):
        for n in fn:
            if n.endswith(".md"):
                files.append(os.path.join(dp, n))
    ag = os.path.join(root, ".claude", "agents")
    if os.path.isdir(ag):
        files += [os.path.join(ag, n) for n in os.listdir(ag) if n.endswith(".md")]
    cm = os.path.join(root, "CLAUDE.md")
    if os.path.isfile(cm):
        files.append(cm)
    wr = os.path.join(root, "docs", "guide", "workflow-roles.md")
    if os.path.isfile(wr):
        files.append(wr)
    return sorted(files)


def cmd_similar(root, a):
    q = tokens(a.text)
    if not q:
        raise Fail("no usable words in text")
    hits = []
    for p in corpus(root):
        with open(p, encoding="utf-8", errors="replace") as f:
            for n, line in enumerate(f, 1):
                t = tokens(line)
                if not t:
                    continue
                common = len(q & t)
                if common == 0:
                    continue
                hits.append((common / math.sqrt(len(q) * len(t)), rel(root, p), n, line))
    hits.sort(key=lambda h: (-h[0], h[1], h[2]))
    for score, p, n, line in hits[:max(a.top, 0)]:
        m = re.search(r"RAW-\d+", line)
        print("%s:%d %.3f raw=%s" % (p, n, score, m.group(0) if m else "-"))
    return 0


PATCH_TEMPLATE = '''#!/usr/bin/env python3
# generated by lessons.py patch (TASK-074); apply-patches contract: python3 <patch> <target-dir>
import os
import sys

MARK = %(mark)s
FILE = %(file)s
ANCHOR = %(anchor)s
TEXT = %(text)s
MODE = %(mode)s

path = os.path.join(sys.argv[1], FILE)
with open(path, encoding="utf-8") as f:
    lines = f.read().split("\\n")
if TEXT in lines:
    print("%%s: already applied" %% MARK)
    sys.exit(0)
hits = [i for i, l in enumerate(lines) if l == ANCHOR]
if len(hits) != 1:
    sys.stderr.write("%%s: anchor matched %%d times in %%s (want 1)\\n" %% (MARK, len(hits), path))
    sys.exit(1)
i = hits[0]
if MODE == "replace":
    lines[i] = TEXT
else:
    lines.insert(i + 1, TEXT)
with open(path, "w", encoding="utf-8") as f:
    f.write("\\n".join(lines))
print("%%s: applied" %% MARK)
'''


def cmd_patch(root, a):
    target = inside(root, os.path.join(root, a.file))
    if not os.path.isfile(target):
        raise Fail("no such file: %s" % a.file)
    if not allowed_path(rel(root, target)):
        raise Fail("file not in the allowed set: %s" % a.file, 3)
    text = a.replace if a.replace is not None else a.after
    mode = "replace" if a.replace is not None else "after"
    for v in (a.anchor, text):
        if "\n" in v or "\r" in v or not v.strip():
            raise Fail("anchor and text must be one non-empty line")
    out = inside(root, os.path.join(root, a.out) if not os.path.isabs(a.out) else a.out)
    name = os.path.basename(out)
    pdir = os.path.dirname(out)
    m = re.match(r"^work/([A-Za-z0-9_-]+)/patches$", rel(root, pdir))
    if not m or not PATCH_NAME_RE.match(name):
        raise Fail("--out must be work/<TASK>/patches/NN-slug.py")
    with open(target, encoding="utf-8") as f:
        if a.anchor not in f.read().split("\n"):
            raise Fail("anchor is not an exact line of %s" % a.file)
    os.makedirs(pdir, exist_ok=True)
    tdir = os.path.dirname(rel(root, target)) or "."
    src = PATCH_TEMPLATE % {
        "mark": json.dumps("lessons-" + name[:-3]), "file": json.dumps(os.path.basename(target)),
        "anchor": json.dumps(a.anchor), "text": json.dumps(text), "mode": json.dumps(mode)}
    with open(out, "w", encoding="utf-8") as f:
        f.write(src)
    bundle = os.path.join(pdir, "bundle.txt")
    entry = "%s\t%s" % (name, tdir)
    existing = []
    if os.path.isfile(bundle):
        with open(bundle, encoding="utf-8") as f:
            existing = f.read().split("\n")
    if entry not in existing:
        with open(bundle, "a", encoding="utf-8") as f:
            if existing and existing[-1] != "":
                f.write("\n")
            f.write(entry + "\n")
    print("patch %s -> %s" % (rel(root, out), tdir))
    return 0


def allowed_path(path, extra=()):
    if path.startswith(".claude/skills/") or path.startswith(".claude/lessons/"):
        return True
    if fnmatch.fnmatchcase(path, ".claude/agents/*.md"):
        return True
    return any(fnmatch.fnmatchcase(path, g) for g in extra)


def cmd_mark_from(root, a):
    cur = inside(root, a.curate if os.path.isabs(a.curate) else os.path.join(os.getcwd(), a.curate))
    m = re.match(r"^work/([A-Za-z0-9_-]+)/handoff/[^/]+\.md$", rel(root, cur))
    if not m or not os.path.isfile(cur):
        raise Fail("curate file must be work/<TASK>/handoff/<name>.md")
    task = m.group(1)
    lessons, _bad = parse_work_dir(root, os.path.join(root, "work", task))
    texts = dict((x["key"], x["text"]) for x in lessons)
    rows = []
    with open(cur, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 3 or not KEY_RE.match(cells[0]):
                continue
            verdict = cells[1].lower()
            if verdict not in VERDICTS:
                raise Fail("bad verdict %r for key %s" % (cells[1], cells[0][:12]))
            if cells[0] not in texts:
                raise Fail("key %s is not a lesson of %s" % (cells[0][:12], task))
            rows.append((cells[0], verdict, cells[2], cells[3] if len(cells) > 3 else ""))
            if verdict in ("rejected", "reject"):
                continue
            ev = [x for x in lessons if x["key"] == cells[0]][0]["evidence"]
            if not evidence_ok(root, ev):
                raise Fail("key %s: no-evidence" % cells[0][:12], 2)
    if not rows:
        raise Fail("no verdict rows in %s" % a.curate)
    evid = dict((x["key"], x["evidence"]) for x in lessons)
    marked = read_ledger(root)
    old = ledger_rows(root)
    base = getattr(a, "base", "HEAD")
    used = set()
    upd = {}
    dup = []
    for key, verdict, filecell, reason in rows:
        if key not in marked:
            continue
        r = old.get(key)
        if (r and r.get("status") == "watch" and not r.get("hunk") and r.get("revert", "manual") == "manual"
                and verdict not in ("rejected", "reject") and filecell.startswith(".claude/skills/")):
            w = watch_fields(root, task, filecell, texts[key], evid[key], used, base)
            ch = dict((k, w[k]) for k in ("hunk", "new", "revert") if r.get(k) != w[k])
            if ch:
                upd[key] = ch
                continue
        dup.append(key)
    for k in dup:
        sys.stderr.write("already in ledger: %s\n" % k)
    if not upd and not any(r[0] not in marked for r in rows):
        return 2
    if upd:
        rewrite_ledger(root, upd)
    out = []
    for key, verdict, filecell, reason in rows:
        if key in marked:
            continue
        if verdict in ("rejected", "reject"):
            where = reason or filecell
        else:
            where = locate(root, filecell, texts[key])
        row = {"key": key, "verdict": verdict, "where": where, "task": task,
               "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        if verdict not in ("rejected", "reject") and filecell.startswith(".claude/skills/"):
            row.update(watch_fields(root, task, filecell, texts[key], evid[key], used, base))
        out.append(row)
    lp = ledger_path(root)
    os.makedirs(os.path.dirname(lp), exist_ok=True)
    with open(lp, "a", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    print("marked %d" % len(out) + (" updated %d" % len(upd) if upd else ""))
    return 0


def ledger_rows(root):
    d = {}
    lp = ledger_path(root)
    if os.path.isfile(lp):
        with open(lp, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line) if line.strip() else None
                except ValueError:
                    r = None
                if isinstance(r, dict) and isinstance(r.get("key"), str):
                    d[r["key"]] = r
    return d


def rewrite_ledger(root, upd):
    """Update fields of existing rows in place (same key, same order)."""
    lp = ledger_path(root)
    with open(lp, encoding="utf-8") as f:
        lines = f.read().split("\n")
    for i, line in enumerate(lines):
        try:
            r = json.loads(line) if line.strip() else None
        except ValueError:
            r = None
        if isinstance(r, dict) and r.get("key") in upd:
            r.update(upd[r["key"]])
            lines[i] = json.dumps(r, sort_keys=True)
    with open(lp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


PATCH_VAR_RE = re.compile(r"^(FILE|ANCHOR|TEXT|MODE) = (.*)$")


def patch_vars(path):
    v = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = PATCH_VAR_RE.match(line.rstrip("\n"))
            if m:
                try:
                    v[m.group(1)] = json.loads(m.group(2))
                except ValueError:
                    pass
    return v


def watch_fields(root, task, filecell, text, ev, used, base="HEAD"):
    """Ledger fields for a skill edit that must be re-checked at the next DONE."""
    path = re.match(r"^(.*?)(?::\d+)?$", filecell).group(1)
    skill = path.split("/")[2] if path.count("/") >= 3 else path
    roles = []
    ag = os.path.join(root, ".claude", "agents")
    if os.path.isdir(ag):
        for n in sorted(os.listdir(ag)):
            if not n.endswith(".md"):
                continue
            with open(os.path.join(ag, n), encoding="utf-8", errors="replace") as f:
                body = f.read()
            fm = [l for l in frontmatter(body).split("\n") if l.startswith("skills:")]
            if (fm and skill in fm[0]) or skill in body:
                roles.append(n[:-3])
    hunk, new, revert = "", text, "manual"
    pdir = os.path.join(root, "work", task, "patches")
    if os.path.isdir(pdir):
        tdirs = {}
        bp = os.path.join(pdir, "bundle.txt")
        if os.path.isfile(bp):
            with open(bp, encoding="utf-8") as f:
                for l in f.read().split("\n"):
                    if "\t" in l:
                        tdirs[l.split("\t", 1)[0]] = l.split("\t", 1)[1]
        want = re.match(r"^.*?:(\d+)$", filecell)
        cand = []
        for n in sorted(os.listdir(pdir)):
            if not n.endswith(".py") or n in used:
                continue
            v = patch_vars(os.path.join(pdir, n))
            full = os.path.normpath(os.path.join(tdirs.get(n, os.path.dirname(path)), v.get("FILE", "")))
            if "TEXT" in v and full == os.path.normpath(path):
                cand.append((n, v))
        if want and cand:
            lines = []
            with open(os.path.join(root, path), encoding="utf-8", errors="replace") as f:
                lines = f.read().split("\n")
            ln = int(want.group(1))
            at = lines[ln - 1] if 0 < ln <= len(lines) else None
            cand = [c for c in cand if c[1]["TEXT"] == at] + [c for c in cand if c[1]["TEXT"] != at]
        if cand:
            n, v = cand[0]
            used.add(n)
            new = v["TEXT"]
            hunk = v.get("ANCHOR", "") if v.get("MODE") == "replace" else ""
            revert = "replace" if hunk else "delete"
    if revert == "manual":
        g = git_pair(root, filecell, base, text, used)
        if g:
            hunk, new, revert = g
    rc, head = git(root, "rev-parse", "HEAD")
    return {"skill": skill, "commit": head.strip() if rc == 0 else "", "roles": roles,
            "evidence": ev, "status": "watch", "hunk": hunk, "new": new, "revert": revert}


HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _norm(t):
    return " ".join(t.split())


TEXT_MIN_COMMON = 3   # shared tokens (lesson text vs added lines)
TEXT_MIN_SCORE = 0.2  # cosine; real pairs score 0.57-0.67, wrong ones <= 0.09
TEXT_MARGIN = 2.0     # best must be 2x the runner-up


def git_pair(root, filecell, base, text="", used=None):
    """(removed block, added block, revert) of the diff hunk holding the edit; None if unpaired.

    The hunk is chosen by the lesson text (whitespace-normalised) first, then by the cited line,
    then by the content of the cited line in the working file. Blocks are multi-line, exact."""
    m = re.match(r"^(.*?)(?::(\d+))?$", filecell)
    if not m or not re.match(r"^[A-Za-z0-9_][A-Za-z0-9_.^~/@{}-]*$", base):
        return None
    path, ln = m.group(1), int(m.group(2) or 0)
    inside(root, os.path.join(root, path))
    rc, out = git(root, "diff", "-U0", "--no-color", base, "--", path)
    if rc != 0 or not out:
        return None
    hunks = []
    cur = None
    for line in out.split("\n"):
        h = HUNK_RE.match(line)
        if h:
            cur = {"c": int(h.group(1)), "del": [], "add": []}
            hunks.append(cur)
        elif cur is not None and line.startswith("-") and not line.startswith("---"):
            cur["del"].append(line[1:])
        elif cur is not None and line.startswith("+") and not line.startswith("+++"):
            cur["add"].append(line[1:])
    used = used if used is not None else set()
    free = [h for h in hunks if h["add"] and (path, h["c"]) not in used]
    t = _norm(text)
    pick = []
    if t:
        pick = [h for h in free if t in _norm(" ".join(h["add"]))]
        if not pick:
            pick = [h for h in free if _norm(" ".join(h["add"])) in t]
    if len(pick) != 1:
        pick = [h for h in free if h["c"] <= ln < h["c"] + len(h["add"])]
    if len(pick) != 1 and ln:
        try:
            with open(os.path.join(root, path), encoding="utf-8", errors="replace") as f:
                cl = f.read().split("\n")
        except OSError:
            cl = []
        at = _norm(cl[ln - 1]) if 0 < ln <= len(cl) else ""
        if at:
            pick = [h for h in free if any(_norm(x) == at for x in h["add"])]
    if len(pick) != 1 and ln and not any(h["c"] <= ln < h["c"] + len(h["add"]) for h in hunks):
        sys.stderr.write("warning: %s: cited line %d not in any hunk; paired by text\n" % (path, ln))
    if len(pick) != 1 and t:
        # last resort: token overlap with the added lines. Needs >= TEXT_MIN_COMMON shared
        # tokens, a cosine score >= TEXT_MIN_SCORE and a best score >= TEXT_MARGIN x the runner-up.
        q = tokens(text)
        sc = []
        for h in free:
            a = tokens(" ".join(h["add"]))
            c = len(q & a)
            if c and q and a:
                sc.append((c / math.sqrt(len(q) * len(a)), c, h))
        sc.sort(key=lambda x: -x[0])
        if sc and sc[0][1] >= TEXT_MIN_COMMON and sc[0][0] >= TEXT_MIN_SCORE and (
                len(sc) == 1 or sc[0][0] >= TEXT_MARGIN * sc[1][0]):
            pick = [sc[0][2]]
    if len(pick) != 1:
        return None
    h = pick[0]
    used.add((path, h["c"]))
    return "\n".join(h["del"]), "\n".join(h["add"]), ("replace" if h["del"] else "delete")


def cmd_revert(root, a):
    want = a.rev_key
    if not re.match(r"^[0-9a-f]{8,64}$", want):
        raise Fail("usage: revert KEY (8-64 hex)")
    rows = [r for k, r in ledger_rows(root).items() if k.startswith(want)]
    if len(rows) != 1:
        raise Fail("key %s matches %d ledger rows" % (want, len(rows)))
    r = rows[0]
    if r.get("status") != "watch":
        raise Fail("row %s status is %s, not watch" % (r["key"][:12], r.get("status")))
    rv = r.get("revert", "manual")
    if rv not in ("replace", "delete") or not r.get("new"):
        raise Fail("row %s is revert: manual; revert it by hand" % r["key"][:12])
    sk = r.get("skill", "")
    if not re.match(r"^[A-Za-z0-9_-]+$", sk):
        raise Fail("bad skill name in row %s" % r["key"][:12])
    path = ".claude/skills/%s/SKILL.md" % sk
    full = inside(root, os.path.join(root, path))
    if not os.path.isfile(full):
        raise Fail("missing %s" % path)
    real = os.path.realpath(full)
    base = os.path.realpath(os.path.join(root, ".claude", "skills"))
    if not real.startswith(base + os.sep) or not real.endswith("/%s/SKILL.md" % sk):
        raise Fail("%s resolves outside .claude/skills/%s/SKILL.md; refusing" % (path, sk))
    with open(full, encoding="utf-8", newline="") as f:
        body = f.read()
    blk, old = r["new"], r.get("hunk", "")
    n = body.count(blk)
    if n != 1:
        raise Fail("new block occurs %d times in %s (need exactly 1)" % (n, path))
    if rv == "replace":
        out = body.replace(blk, old)
    elif body.count(blk + "\n") == 1:
        out = body.replace(blk + "\n", "")
    elif body.endswith("\n" + blk):
        out = body[:-len(blk) - 1]
    else:
        out = body.replace(blk, "")
    with open(full, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    rewrite_ledger(root, {r["key"]: {"status": "reverted"}})
    print("reverted %s in %s" % (r["key"][:12], path))
    return 0


def cmd_watch(root, a):
    lp = ledger_path(root)
    rows = []
    if os.path.isfile(lp):
        with open(lp, encoding="utf-8") as f:
            rows = f.read().split("\n")
    if a.set_key:
        if a.set_key[1] not in ("kept", "reverted", "kept-unproven") or not KEY_RE.match(a.set_key[0]):
            raise Fail("usage: watch --set KEY kept|reverted|kept-unproven")
        hit = 0
        for i, line in enumerate(rows):
            try:
                r = json.loads(line) if line.strip() else None
            except ValueError:
                r = None
            if r and r.get("key") == a.set_key[0] and r.get("status") == "watch":
                r["status"] = a.set_key[1]
                rows[i] = json.dumps(r, sort_keys=True)
                hit += 1
        if not hit:
            raise Fail("no watch row for key %s" % a.set_key[0][:12], 2)
        tmp = lp + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(rows))
        os.replace(tmp, lp)
        print("set %s %s" % (a.set_key[0][:12], a.set_key[1]))
        return 0
    n = 0
    for line in rows:
        try:
            r = json.loads(line) if line.strip() else None
        except ValueError:
            r = None
        if r and r.get("status") == "watch":
            n += 1
            print("%s\t%s\t%s\t%s\t%s%s" % (r["key"], r.get("task", ""), r.get("skill", ""),
                                             ",".join(r.get("roles", [])), r.get("where", ""),
                                             "\trevert: manual" if r.get("revert", "manual") == "manual" else ""))
    print("TOTAL watch=%d" % n)
    return 0


def locate(root, filecell, text):
    """path:line for the curated file; the line is the one holding the lesson text, else any given line."""
    m = re.match(r"^(.*?)(?::(\d+))?$", filecell)
    path, line = m.group(1), m.group(2)
    real = inside(root, os.path.join(root, path))
    if not os.path.isfile(real):
        raise Fail("curated file missing: %s" % path)
    if line:
        return "%s:%s" % (path, line)
    with open(real, encoding="utf-8", errors="replace") as f:
        for n, l in enumerate(f, 1):
            if text in l:
                return "%s:%d" % (path, n)
    return path


def git(root, *args):
    p = subprocess.run(["git", "-C", root] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True)
    return p.returncode, p.stdout


def frontmatter(text):
    if not text.startswith("---"):
        return ""
    return text[3:].split("\n---", 1)[0]


def cmd_scope(root, a):
    base = a.base
    if not REV_RE.match(base):
        raise Fail("bad rev: %s" % base)
    rc, out = git(root, "diff", "--name-only", base)
    if rc != 0:
        raise Fail("git diff failed (bad base?)")
    paths = set(p for p in out.split("\n") if p)
    rc, out = git(root, "ls-files", "--others", "--exclude-standard")
    if rc == 0:
        paths |= set(p for p in out.split("\n") if p)
    outside = sorted(p for p in paths if not allowed_path(p, a.allow))
    if outside:
        for p in outside:
            print("OUTSIDE %s" % p)
        return 3
    bad = []
    for p in sorted(paths):
        full = os.path.join(root, p)
        now = ""
        if os.path.isfile(full):
            with open(full, encoding="utf-8", errors="replace") as f:
                now = f.read()
        rc, old = git(root, "show", "%s:%s" % (base, p))
        if rc != 0:
            old = None
        if p.startswith(".claude/skills/") and p.endswith(".md"):
            n_now = len(now.splitlines())
            n_old = len(old.splitlines()) if old is not None else 0
            if n_now > SKILL_LIMIT and n_now > n_old:
                bad.append("GREW %s %d -> %d" % (p, n_old, n_now))
        elif fnmatch.fnmatchcase(p, ".claude/agents/*.md") and old is not None:
            if frontmatter(now) != frontmatter(old):
                bad.append("FRONTMATTER %s" % p)
    for b in bad:
        print(b)
    return 4 if bad else 0


# ---- drift (TASK-103, design phase-103) ----
FLAG_RE = re.compile(r"^--[a-z][a-z0-9-]*")
KEY_TOK_RE = re.compile(r"^[A-Z][A-Z0-9]*_[A-Z0-9_]+")
SCRIPT_RE = re.compile(r"^\w[\w.-]*\.(sh|py)$")
SPAN_RE = re.compile(r"`([^`]+)`")
SKIP_SUB = ("<", ">", "$", "...", "~", "://", "{")


def tracked_files(root):
    rc, out = git(root, "ls-files")
    if rc != 0:
        raise Fail("git ls-files failed")
    return [p for p in out.split("\n") if p]


def is_code_file(p):
    if p.startswith((".claude/skills/", "docs/", "work/")) or p.endswith(".md"):
        return False
    return p.endswith(CODE_EXT) or os.path.basename(p).startswith("Dockerfile")


def read_text(root, p):
    try:
        with open(os.path.join(root, p), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def word_re(cls, tok):
    if cls == "flag":
        return re.compile(r"(?<![\w-])" + re.escape(tok) + r"(?![\w-])")
    return re.compile(r"\b" + re.escape(tok) + r"\b")


def extract_cites(text, tops):
    """[(line, class, token, led_script)] for one skill file text."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for span in SPAN_RE.findall(line):
            toks = [t.strip("\"'()[],.;:") for t in re.split(r"[\s|\\]+", span)]
            toks = [t for t in toks if t and not any(x in t for x in SKIP_SUB) and not t.startswith("/")]
            led = None
            for t in toks:
                if "=" in t and not t.startswith("-"):
                    continue
                b = t[2:] if t.startswith("./") else t
                led = b if SCRIPT_RE.match(os.path.basename(b)) else ""
                break
            for t in toks:
                t = t[2:] if t.startswith("./") else t
                core = t.split("=", 1)[0]
                if FLAG_RE.match(core):
                    if led or len(toks) == 1:
                        out.append((n, "flag", FLAG_RE.match(core).group(0), led or ""))
                elif KEY_TOK_RE.match(core):
                    out.append((n, "key", KEY_TOK_RE.match(core).group(0), ""))
                elif "/" in t and t.split("/", 1)[0] in tops:
                    out.append((n, "path", t.rstrip("/"), ""))
                elif SCRIPT_RE.match(t):
                    out.append((n, "script", t, ""))
    return out


def diff_facts(root, base, code):
    rc, out = git(root, "diff", "--name-only", base)
    if rc != 0:
        raise Fail("git diff failed (bad base?)")
    names = set(p for p in out.split("\n") if p)
    removed, added = [], []
    rc, out = git(root, "diff", "-U0", base)
    if rc != 0:
        raise Fail("git diff failed (bad base?)")
    cur = ""
    for l in out.split("\n"):
        if l.startswith("+++ "):
            cur = l[6:] if l.startswith("+++ b/") else ""
        elif l.startswith("--- "):
            continue
        elif l.startswith("-") and (cur in code or not cur):
            removed.append(l[1:])
        elif l.startswith("+") and cur in code:
            added.append(l[1:])
    return names, "\n".join(removed), "\n".join(added)


def task_base(root, task):
    rc, out = git(root, "log", "--grep", "^Task: %s$" % task, "--reverse", "--format=%H")
    first = out.split() if rc == 0 else []
    if first:
        rc, p = git(root, "rev-parse", first[0] + "^")
        if rc == 0 and p.strip():
            return p.strip()
    return "HEAD"


def sweep_decision(root, task, every):
    done, ok = 0, True
    try:
        with open(os.path.join(root, ".claude", "state", "backlog.json"), encoding="utf-8") as f:
            items = json.load(f)
        ids = set()
        for it in items:
            if it.get("status") == "done":
                done += 1
                ids.add(it.get("task_id"))
        if task and task not in ids:
            done += 1
    except (OSError, ValueError, AttributeError):
        ok = False
        sys.stderr.write("lessons.py: backlog.json unreadable, no sweep\n")
    return (ok and every > 0 and done % every == 0), (done if ok else "?")


def cmd_drift(root, a):
    if a.task and not TASK_RE.match(a.task):
        raise Fail("bad task id: %s" % a.task)
    if a.base and not REV_RE.match(a.base):
        raise Fail("bad rev: %s" % a.base)
    skills = [s for s in a.skills.split(",") if s] if a.skills else list(APP_SKILLS)
    for s in skills:
        if not TASK_RE.match(s):
            raise Fail("bad skill name: %s" % s)
    use_all = a.all
    if a.sweep_every > 0 and (a.task or a.base):
        yes, done = sweep_decision(root, a.task, a.sweep_every)
        print("SWEEP %s done=%s" % ("yes" if yes else "no", done))
        use_all = use_all or yes
    base = a.base or (task_base(root, a.task) if a.task else None)
    if base is None:
        use_all = True
    files = tracked_files(root)
    tops = set(p.split("/", 1)[0] for p in files)
    code = set(p for p in files if is_code_file(p))
    hay = "\n".join(read_text(root, p) for p in sorted(code))
    names, removed, added = (set(), "", "")
    if base:
        names, removed, added = diff_facts(root, base, code)
    bases = set(os.path.basename(p) for p in files)
    rows, seen = [], set()
    for sk in skills:
        sdir = os.path.join(root, ".claude", "skills", sk)
        found = []
        for dp, dn, fn in os.walk(sdir):
            dn.sort()
            found += [os.path.join(dp, f) for f in sorted(fn) if f.endswith(".md")]
        for fp in found:
            rel_f = os.path.relpath(fp, root)
            with open(fp, encoding="utf-8", errors="replace") as f:
                text = f.read()
            for n, cls, tok, led in extract_cites(text, tops):
                if (rel_f, cls, tok) in seen:
                    continue
                seen.add((rel_f, cls, tok))
                status, detail = None, ""
                if cls in ("path", "script"):
                    if cls == "path" and "*" in tok:
                        hits = [p for p in files if fnmatch.fnmatchcase(p, tok)]
                        exists = bool(hits)
                        hit_diff = any(h in names for h in hits)
                    elif cls == "path":
                        exists = os.path.exists(os.path.join(root, tok)) or any(p.startswith(tok + "/") for p in files)
                        hit_diff = tok in names or any(x.startswith(tok + "/") for x in names)
                    else:
                        exists = tok in bases or os.path.isfile(os.path.join(root, tok))
                        hit_diff = any(os.path.basename(x) == tok for x in names)
                    if not exists:
                        if use_all or hit_diff:
                            status, detail = "MISSING", "not in tree"
                    elif hit_diff:
                        status, detail = "CHANGED", "file touched in diff"
                else:
                    rx = word_re(cls, tok)
                    present = False
                    if led:
                        lp = led if os.path.isfile(os.path.join(root, led)) else next(
                            (p for p in files if os.path.basename(p) == os.path.basename(led)), "")
                        present = bool(lp) and bool(rx.search(read_text(root, lp)))
                    present = present or bool(rx.search(hay))
                    in_removed = bool(rx.search(removed))
                    gone_in_diff = in_removed and not rx.search(added)
                    if not present:
                        if use_all or in_removed:
                            status, detail = "MISSING", "not found in code files"
                    elif gone_in_diff:
                        status, detail = "CHANGED", "removed from code in diff"
                if status:
                    rows.append((status, "%s:%d" % (rel_f, n), cls, tok, detail, sk))
    miss = sum(1 for r in rows if r[0] == "MISSING")
    for r in rows:
        print("\t".join(r[:5]))
    print("TOTAL missing=%d changed=%d" % (miss, len(rows) - miss))
    if a.emit and rows:
        wd = inside(os.path.join(root, "work"), a.emit if os.path.isabs(a.emit) else os.path.join(root, a.emit))
        tid = os.path.basename(wd)
        if not TASK_RE.match(tid):
            raise Fail("bad task dir name: %s" % tid)
        lines, texts = [], set()
        for status, loc, cls, tok, detail, sk in rows:
            by = " by %s" % tid if status == "CHANGED" else ""
            t = "%s: `%s` %s %s%s: %s" % (sk, tok, cls, status, by, detail)
            if t in texts:
                continue
            texts.add(t)
            lines.append("- L: kind=stale target=%s | %s | evidence=%s" % (sk, t, loc))
        hd = os.path.join(wd, "handoff")
        os.makedirs(hd, exist_ok=True)
        tmp = os.path.join(hd, ".drift.md.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("PROGRESS: COMPLETE\nSKILLS: -\n## Lessons\n" + "\n".join(lines) + "\n")
        os.replace(tmp, os.path.join(hd, "drift.md"))
    return 6 if rows else 0


def build_parser():
    ap = argparse.ArgumentParser(prog="lessons.py", description="role lessons helper")
    ap.add_argument("--root", default=None)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("collect")
    s.add_argument("work_dirs", nargs="+")
    s = sub.add_parser("similar")
    s.add_argument("text")
    s.add_argument("--top", type=int, default=5)
    s = sub.add_parser("patch")
    s.add_argument("--file", required=True)
    s.add_argument("--anchor", required=True)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--replace")
    g.add_argument("--after")
    s.add_argument("--out", required=True)
    s = sub.add_parser("mark-from")
    s.add_argument("curate")
    s.add_argument("--base", default="HEAD", help="git rev the edit is diffed against (default HEAD)")
    s = sub.add_parser("revert")
    s.add_argument("rev_key", metavar="KEY")
    s = sub.add_parser("watch")
    s.add_argument("--set", dest="set_key", nargs=2, metavar=("KEY", "STATUS"))
    s = sub.add_parser("scope")
    s.add_argument("--base", default="HEAD")
    s.add_argument("--allow", action="append", default=[])
    s = sub.add_parser("drift")
    s.add_argument("--task")
    s.add_argument("--base")
    s.add_argument("--all", action="store_true")
    s.add_argument("--sweep-every", type=int, default=5)
    s.add_argument("--emit")
    s.add_argument("--skills")
    return ap


def main(argv=None):
    ap = build_parser()
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 1 if e.code else 0
    if not a.cmd:
        ap.print_usage(sys.stderr)
        return 1
    root = os.path.realpath(a.root) if a.root else default_root()
    fn = {"collect": cmd_collect, "similar": cmd_similar, "patch": cmd_patch,
          "mark-from": cmd_mark_from, "scope": cmd_scope, "revert": cmd_revert, "watch": cmd_watch,
          "drift": cmd_drift}[a.cmd]
    try:
        return fn(root, a)
    except Fail as e:
        sys.stderr.write("lessons.py: %s\n" % e)
        return e.rc
    except (OSError, UnicodeError) as e:
        sys.stderr.write("lessons.py: %s\n" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())

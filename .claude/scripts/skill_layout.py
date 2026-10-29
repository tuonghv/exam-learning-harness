#!/usr/bin/env python3
"""Skill layout check (phase 93): size, references/, frontmatter, pointers, --moved. Read-only, stdlib.

TSV rows: LEVEL<TAB>check<TAB>path[:line]<TAB>detail ; last line SUMMARY fail=N warn=N debt=N.
rc 0 = no FAIL, 1 = FAIL, 2 = usage or git error.
"""
import argparse
import os
import re
import subprocess
import sys
from collections import Counter

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = []


def row(level, check, loc, detail):
    ROWS.append((level, check, loc, detail))


def read_lines(p):
    with open(p, encoding="utf-8", errors="replace") as fh:
        return fh.read().split("\n")


def nlines(p):
    with open(p, encoding="utf-8", errors="replace") as fh:
        return sum(1 for _ in fh)


def load_allow(path):
    allow = {}
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln or ln.startswith("#"):
                    continue
                parts = [x.strip() for x in ln.split("|")]
                if len(parts) >= 2 and parts[1].isdigit():
                    allow[parts[0]] = int(parts[1])
    return allow


def check_size(key, path, rel, limit, allow, split):
    n = nlines(path)
    if n <= limit:
        return
    if split:
        row("WARN", "core-size", rel, "core has %d lines (limit %d) with references/" % (n, limit))
        return
    mx = allow.get(key)
    if mx is not None and n <= mx:
        row("DEBT", "size", rel, "%d lines, allowed up to %d" % (n, mx))
    else:
        extra = "" if mx is None else " (allow max %d)" % mx
        row("FAIL", "size", rel, "%d lines over limit %d%s" % (n, limit, extra))


def frontmatter(path, rel, dirname):
    ls = read_lines(path)
    if not ls or ls[0].strip() != "---":
        row("FAIL", "frontmatter", rel + ":1", "line 1 is not ---")
        return
    end = None
    for i in range(1, len(ls)):
        if ls[i].strip() == "---":
            end = i
            break
    if end is None:
        row("FAIL", "frontmatter", rel + ":1", "frontmatter block not closed")
        return
    fm = {}
    for ln in ls[1:end]:
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", ln)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    for k in ("name", "description"):
        if not fm.get(k):
            row("FAIL", "frontmatter", rel + ":1", "missing or empty " + k)
    if fm.get("name") and fm["name"] != dirname:
        row("FAIL", "frontmatter", rel + ":1", "name %s != dir %s" % (fm["name"], dirname))


LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
REFTOK_RE = re.compile(r"(?<![A-Za-z0-9_/.-])references/[A-Za-z0-9_.-]+\.md")
SKILLTOK_RE = re.compile(r"(?<![A-Za-z0-9_/.-])([a-z][a-z0-9-]*)/(references/[A-Za-z0-9_.-]+\.md)")
TICK_RE = re.compile(r"`([A-Za-z0-9_-]+)`")


def check_links(path, rel, sdir, skills_dir):
    for i, ln in enumerate(read_lines(path), 1):
        targets = []
        for t in LINK_RE.findall(ln):
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", t) or t.startswith("#"):
                continue
            targets.append(t.split("#")[0])
        targets += REFTOK_RE.findall(ln)
        for sk, rest in SKILLTOK_RE.findall(ln):
            if not os.path.exists(os.path.join(skills_dir, sk, rest)):
                row("FAIL", "link", "%s:%d" % (rel, i), "unresolved %s/%s" % (sk, rest))
        for t in targets:
            if not t:
                continue
            bases = [sdir] + [os.path.join(skills_dir, s) for s in TICK_RE.findall(ln)
                              if os.path.isdir(os.path.join(skills_dir, s))]
            if not any(os.path.exists(os.path.join(b, t)) for b in bases):
                row("FAIL", "link", "%s:%d" % (rel, i), "unresolved " + t)


def git(root, *args):
    r = subprocess.run(["git", "-C", root] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True)
    if r.returncode != 0:
        sys.stderr.write("git %s failed: %s\n" % (" ".join(args), r.stderr.strip()))
        sys.exit(2)
    return r.stdout


def check_moved(root, rev):
    git(root, "rev-parse", "--verify", rev + "^{commit}")
    changed = git(root, "diff", "--name-only", rev, "--", ".claude/skills").split()
    skills = sorted(set(p.split("/")[2] for p in changed if p.count("/") >= 3))
    for s in skills:
        old_p = ".claude/skills/%s/SKILL.md" % s
        r = subprocess.run(["git", "-C", root, "cat-file", "-e", "%s:%s" % (rev, old_p)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0:
            continue
        old = git(root, "show", "%s:%s" % (rev, old_p)).split("\n")
        cur = []
        sdir = os.path.join(root, ".claude/skills", s)
        files = [os.path.join(sdir, "SKILL.md")]
        rd = os.path.join(sdir, "references")
        if os.path.isdir(rd):
            files += [os.path.join(rd, f) for f in sorted(os.listdir(rd)) if f.endswith(".md")]
        for f in files:
            if os.path.isfile(f):
                cur += read_lines(f)
        have = Counter(x for x in cur if x.strip())
        need = Counter(x for x in old if x.strip())
        for ln, c in need.items():
            if have[ln] < c:
                row("FAIL", "moved", ".claude/skills/%s" % s, "lost line (x%d): %s" % (c - have[ln], ln))
        for ln, c in have.items():
            if need[ln] < c:
                row("INFO", "moved", ".claude/skills/%s" % s, "added: %s" % ln[:100])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=os.path.abspath(os.path.join(HERE, "..", "..")))
    ap.add_argument("--limit", type=int, default=80)
    ap.add_argument("--allow", default=None)
    ap.add_argument("--moved", default=None)
    a = ap.parse_args()
    allow_p = a.allow or os.path.join(a.root, ".claude/scripts/checks/skill_layout.allow")
    allow = load_allow(allow_p)
    skills_dir = os.path.join(a.root, ".claude/skills")
    if os.path.isdir(skills_dir):
        for s in sorted(os.listdir(skills_dir)):
            sdir = os.path.join(skills_dir, s)
            md = os.path.join(sdir, "SKILL.md")
            if not os.path.isfile(md):
                continue
            rel = ".claude/skills/%s/SKILL.md" % s
            rdir = os.path.join(sdir, "references")
            refs = sorted(f for f in os.listdir(rdir) if f.endswith(".md")) if os.path.isdir(rdir) else []
            check_size(s, md, rel, a.limit, allow, bool(refs))
            for f in refs:
                check_size("%s/references/%s" % (s, f), os.path.join(rdir, f),
                           ".claude/skills/%s/references/%s" % (s, f), a.limit, allow, False)
            frontmatter(md, rel, s)
            check_links(md, rel, sdir, skills_dir)
            for f in refs:
                check_links(os.path.join(rdir, f), ".claude/skills/%s/references/%s" % (s, f),
                            sdir, skills_dir)
    if a.moved:
        check_moved(a.root, a.moved)
    cnt = Counter(r[0] for r in ROWS)
    for r in ROWS:
        print("\t".join(r))
    print("SUMMARY fail=%d warn=%d debt=%d" % (cnt["FAIL"], cnt["WARN"], cnt["DEBT"]))
    return 1 if cnt["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())

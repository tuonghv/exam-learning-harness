#!/usr/bin/env python3
"""Review findings ledger check (TASK-130, REQ-0137).

Every finding of a code-review report (docs/report/fable-review/<date>-phase<N>-<slug>.md, or the older
docs/report/phase-<N>-<slug>.md, with a `### Fnnn – [SEV]` heading) must have one row in
docs/review/findings.tsv with a disposition:
  fixed         ref = TASK-NNN that fixed it
  not-a-defect  ref = TASK-NNN that triaged it
  waived        note = the reason
  open          ref = TASK-NNN that is queued or active in .claude/state/backlog.json
Prints `LEDGER: <n> ids, <k> open, <e> problem(s)` and one `PROBLEM: ...` line each; exit 1 on problems.
Usage: python3 -I tools/review_ledger.py [--root DIR]
"""
import argparse
import json
import os
import re
import sys

HEAD = re.compile(r"(?m)^### F(\d{3}) – \[")
PHASE = re.compile(r"^(?:\d{4}-\d{2}-\d{2}-)?phase-?(\d+)-")
REPORT_DIRS = ("docs/report/fable-review", "docs/report")
TASK = re.compile(r"^TASK-\d{3,}$")
DISPOSITIONS = ("fixed", "not-a-defect", "waived", "open")
COLUMNS = ["id", "report", "class", "disposition", "ref", "note"]


def review_ids(root):
    """{id: report file name} for every finding heading of every review report."""
    out = {}
    for d in REPORT_DIRS:
        rep = os.path.join(root, d)
        for fn in sorted(os.listdir(rep)) if os.path.isdir(rep) else ():
            m = PHASE.match(fn)
            if not (m and fn.endswith(".md")):
                continue
            with open(os.path.join(rep, fn), encoding="utf-8", errors="replace") as fh:
                nums = HEAD.findall(fh.read())
            for n in nums:
                out.setdefault("%s-F%s" % (m.group(1), n), fn)
    return out


def read_ledger(path):
    """(rows, problems); rows = list of dicts keyed by COLUMNS."""
    if not os.path.isfile(path):
        return [], ["ledger file missing: %s" % path]
    rows, probs = [], []
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    if not lines or lines[0].split("\t") != COLUMNS:
        return [], ["ledger header must be: %s" % "\t".join(COLUMNS)]
    for k, ln in enumerate(lines[1:], 2):
        if not ln.strip():
            continue
        cells = ln.split("\t")
        if len(cells) != len(COLUMNS):
            probs.append("line %d: %d columns, expected %d" % (k, len(cells), len(COLUMNS)))
            continue
        rows.append(dict(zip(COLUMNS, cells), line=k))
    return rows, probs


def task_states(root):
    """{task_id: backlog status}."""
    p = os.path.join(root, ".claude", "state", "backlog.json")
    try:
        with open(p, encoding="utf-8") as fh:
            items = json.load(fh)
    except (OSError, ValueError):
        return {}
    items = items.get("items", []) if isinstance(items, dict) else items
    return {it.get("task_id"): it.get("status") for it in items if isinstance(it, dict)}


def check(root):
    ids = review_ids(root)
    rows, probs = read_ledger(os.path.join(root, "docs/review/findings.tsv"))
    states = task_states(root)
    seen = {}
    for r in rows:
        rid, where = r["id"], "line %d (%s)" % (r["line"], r["id"])
        if rid in seen:
            probs.append("%s: duplicate row (first at line %d)" % (where, seen[rid]))
            continue
        seen[rid] = r["line"]
        if rid not in ids:
            probs.append("%s: no such finding in any review report" % where)
        elif r["report"] != ids[rid]:
            probs.append("%s: report is %s, not %s" % (where, ids[rid], r["report"]))
        disp, ref = r["disposition"], r["ref"]
        if disp not in DISPOSITIONS:
            probs.append("%s: disposition %r not in %s" % (where, disp, "/".join(DISPOSITIONS)))
        elif disp == "waived":
            if not r["note"].strip():
                probs.append("%s: waived without a reason in note" % where)
        elif not TASK.match(ref):
            probs.append("%s: %s needs a TASK-NNN ref, got %r" % (where, disp, ref))
        elif disp == "open" and states.get(ref) not in ("queued", "active"):
            probs.append("%s: open on %s, which is %s (not queued/active)" % (where, ref, states.get(ref, "not in backlog")))
        elif disp == "fixed" and states.get(ref) not in (None, "done") and ref in states:
            probs.append("%s: fixed by %s, which is %s, not done" % (where, ref, states[ref]))
    for rid in sorted(set(ids) - set(seen)):
        probs.append("%s (%s): no ledger row" % (rid, ids[rid]))
    n_open = sum(r["disposition"] == "open" for r in rows)
    return len(ids), n_open, probs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    a = ap.parse_args(argv)
    n, n_open, probs = check(a.root)
    print("LEDGER: %d ids, %d open, %d problem(s)" % (n, n_open, len(probs)))
    for p in probs:
        print("PROBLEM: " + p)
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())

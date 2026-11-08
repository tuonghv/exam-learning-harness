#!/usr/bin/env python3
"""Independent QA of a report pack (TASK-085 85.6, REQ-0092 AC8/AC10). Stdlib only (re, json, os).

Reads config/report_kinds.json, the plan result.json files and the answer key itself; imports nothing from
exam_engine, so it does not trust the code that wrote the pack. Fails (exit 1) when a file has an
unregistered kind OR a registered kind that applies has no file. Output: TSV `check expected got ok`.

usage: python3 -I tools/check_report_pack.py PACK_DIR PLAN_DIR... [--key FILE] [--expect-correct N] [--registry FILE]
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PART = re.compile(r"^[a-z0-9-]+$")


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")


def parse_name(base, kinds):
    stem, dot, ext = base.rpartition(".")
    parts = stem.split("_")
    if not dot or len(parts) != 4 or not all(PART.match(x) for x in parts):
        return None
    exam, subject, kind, run = parts
    if kind not in kinds or ext not in kinds[kind]["ext"] or not run.startswith("run-"):
        return None
    sc = kinds[kind]["scope"]
    if sc == "all" and subject != "all" or sc == "subject" and subject == "all":
        return None
    return {"exam": exam, "subject": subject, "kind": kind, "run": run, "ext": ext}


def key_map(path):
    with open(path, encoding="utf-8") as fh:
        toks = re.findall(r"[^\W\d_]+|\d+", fh.read())
    out = {}
    for a, b in zip(toks, toks[1:]):
        if a.isdigit() and re.fullmatch(r"[A-Da-d]", b):
            out.setdefault(int(a), b.upper())
    return out


def offset_of(plan):
    try:
        with open(os.path.join(plan, "input", "exam.md"), encoding="utf-8") as fh:
            m = re.search(r"printed exam number of question N is N \+ (\d+)", fh.read())
        return int(m.group(1)) if m else 0
    except OSError:
        return 0


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


SOURCE_LINE = re.compile(r"^- (?:Ngu\u1ed3n \u0111\u00e1p \u00e1n|Answer source): ", re.M)


def question_text(plan, qid):
    """Whitespace-collapsed '### Question text' section of question qid in plan/input/exam.md ('' when absent)."""
    m = re.search(r"^## Question %s[ \t]*$(.*?)(?=^## |\Z)" % re.escape(str(qid)), read(os.path.join(plan, "input", "exam.md")),
                  re.M | re.S)
    t = re.search(r"^### Question text[ \t]*$(.*)", m.group(1), re.M | re.S) if m else None
    return " ".join(t.group(1).split()) if t else ""


def main(argv):
    args, key, expect, reg = [], None, None, os.path.join(HERE, "..", "config", "report_kinds.json")
    i = 0
    while i < len(argv):
        if argv[i] == "--key":
            key, i = argv[i + 1], i + 2
        elif argv[i] == "--expect-correct":
            expect, i = int(argv[i + 1]), i + 2
        elif argv[i] == "--registry":
            reg, i = argv[i + 1], i + 2
        else:
            args.append(argv[i])
            i += 1
    if len(args) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    pack, plans = args[0], args[1:]
    kinds = jload(reg)["kinds"]
    rows = []

    def chk(name, exp, got):
        rows.append((name, exp, got, "ok" if str(exp) == str(got) else "FAIL"))

    results = []
    for pd in plans:
        r = jload(os.path.join(pd, "result.json"))
        results.append({"plan": pd, "r": r, "slug": slug(r["exam"].get("subject")), "n": len(r["questions"])})
    files = sorted(f for f in os.listdir(pack) if f not in ("INDEX.md", "run.json") and os.path.isfile(os.path.join(pack, f)))
    parsed = {f: parse_name(f, kinds) for f in files}
    if os.path.isfile(os.path.join(pack, "run.json")):  # TASK-087: run manifest is not a kind; it must match the plans
        try:
            man = jload(os.path.join(pack, "run.json"))
            got = [str(p.get("result_sha256")) for p in man.get("plan_runs", [])]
        except (OSError, ValueError, AttributeError):
            man, got = {}, []
        chk("run.json plan_runs", len(plans), len(got))
        want = []
        for pd in plans:
            with open(os.path.join(pd, "result.json"), "rb") as fh:
                want.append(hashlib.sha256(fh.read()).hexdigest())
        chk("run.json result_sha256 mismatches", 0, sum(1 for w in want if w not in got))
    overlays = [o for o in (man.get("overlays") or []) if isinstance(o, dict)] if os.path.isfile(os.path.join(pack, "run.json")) else []
    ovl = {}  # (subject, base id) -> overlay letter
    if overlays:
        bad_sha = bad_text = 0
        for o in overlays:
            rpath = os.path.join(o.get("dir") or "", "result.json")
            try:
                with open(rpath, "rb") as fh:
                    bad_sha += hashlib.sha256(fh.read()).hexdigest() != o.get("result_sha256")
                ores = jload(rpath)
            except (OSError, ValueError):
                bad_sha, ores = bad_sha + 1, {"questions": []}
            base_dir = next((x["plan"] for x in results if x["r"]["exam"].get("subject") == o.get("subject")), None)
            for q in o.get("questions", []):
                if base_dir is None or not question_text(o.get("dir") or "", q["id"]) \
                        or question_text(o["dir"], q["id"]) != question_text(base_dir, q["base_id"]):
                    bad_text += 1
                oq = next((x for x in ores["questions"] if str(x["id"]) == str(q["id"])), {})
                a = (oq.get("answer") or "").strip().upper() if isinstance(oq.get("answer"), str) else ""
                ovl[(o.get("subject"), str(q["base_id"]))] = a if a in ("A", "B", "C", "D") else "-"
        chk("overlay result_sha256 mismatches", 0, bad_sha)
        chk("overlay text differs", 0, bad_text)
    chk("unregistered files", 0, sum(1 for v in parsed.values() if v is None))
    chk("exam/run parts", 1, len({(v["exam"], v["run"]) for v in parsed.values() if v}))
    # AC10: every applicable registered kind has exactly its expected files
    active = {"", "sheet"} | ({"key"} if key else set())
    for kind, spec in sorted(kinds.items()):
        if spec.get("needs", "") not in active:
            continue
        per = (len(plans) if spec["scope"] in ("subject", "both") else 0) + (1 if spec["scope"] in ("all", "both") else 0)
        for ext in spec["ext"]:
            if ext in spec.get("optional_ext", []):
                continue
            got = sum(1 for v in parsed.values() if v and v["kind"] == kind and v["ext"] == ext)
            chk("count %s.%s" % (kind, ext), per, got)
    if jload(reg).get("pdf_with_md"):  # registry flag: no kind is named here
        stems = {}
        for f, v in parsed.items():
            if v and v["ext"] in ("md", "pdf"):
                stems.setdefault(f.rpartition(".")[0], set()).add(v["ext"])
        chk("md without pdf", 0, sum(1 for e in stems.values() if "md" in e and "pdf" not in e))
        chk("pdf without md", 0, sum(1 for e in stems.values() if "pdf" in e and "md" not in e))
    by = {}
    for f, v in parsed.items():
        if v:
            by[(v["kind"], v["subject"], v["ext"])] = os.path.join(pack, f)
    total = sum(x["n"] for x in results)
    qsum = 0
    for x in results:
        s, n = x["slug"], x["n"]
        sr = read(by.get(("solution-report", s, "md"), ""))
        heads = re.findall(r"^### \S+ (\d+)\s*$", sr, re.M)
        chk("questions solution-report %s" % s, n, len(heads))
        qsum += len(heads)
        m = re.search(r"(\d+) Questions", read(by.get(("answer-sheet", s, "md"), "")))
        chk("questions answer-sheet %s" % s, n, m.group(1) if m else 0)
        nt = sum(1 for ln in sr.splitlines() if re.match(r"^<[^<>]+>$", ln.strip()))
        chk("with_text %s" % s, n, len(heads) - nt)
        if overlays:
            chk("overlay source lines %s" % s, sum(len(o["questions"]) for o in overlays if slug(o.get("subject")) == s),
                len(SOURCE_LINE.findall(sr)))
        chk("raw-JSON doubt lines %s" % s, 0, len(re.findall(r"""[{]\s*["']level["']""", sr)))
        chk("log copy %s" % s, 1, 1 if ("run-log", s, "log") in by else 0)
        meta = jload(by[("result-data", s, "json")]) if ("result-data", s, "json") in by else {}
        chk("result-data plan_run_id %s" % s, jload(os.path.join(x["plan"], "plan.json")).get("plan_run_id"), meta.get("plan_run_id"))
    chk("questions total", total, qsum)
    allsr = read(by.get(("solution-report", "all", "md"), ""))
    chk("questions combined solution-report", total, len(re.findall(r"^### \S+ (\d+)\s*$", allsr, re.M)))
    if overlays:
        chk("overlay source lines combined", sum(len(o["questions"]) for o in overlays), len(SOURCE_LINE.findall(allsr)))
    # answer-table letters = result answers
    tab = [ln.split("\t") for ln in read(by.get(("answer-table", "all", "tsv"), "")).splitlines()[1:] if ln.strip()]
    chk("answer-table rows", total, len(tab))
    want = {}
    for x in results:
        for q in x["r"]["questions"]:
            a = (q.get("answer") or "").strip().upper() if isinstance(q.get("answer"), str) else ""
            want[(x["r"]["exam"].get("subject"), str(q["id"]))] = a if a in ("A", "B", "C", "D") else "-"
    want.update(ovl)
    chk("answer-table letters differ", 0, sum(1 for r in tab if want.get((r[0], r[1])) != r[3]))
    if key:
        km = key_map(key)
        correct = wrong = declined = 0
        for x in results:
            off = offset_of(x["plan"])
            for q in x["r"]["questions"]:
                a = want[(x["r"]["exam"].get("subject"), str(q["id"]))]
                k = km.get(int(q["id"]) + off)
                if a == "-":
                    declined += 1
                elif a == k:
                    correct += 1
                else:
                    wrong += 1
        sk = [ln.split("\t") for ln in read(by.get(("score-vs-key", "all", "tsv"), "")).splitlines()[1:] if ln.strip()]
        chk("score-vs-key rows", total, len(sk))
        chk("score-vs-key correct", correct, sum(1 for r in sk if r[4] == "correct"))
        chk("score-vs-key WRONG", wrong, sum(1 for r in sk if r[4] == "WRONG"))
        chk("score-vs-key declined", declined, sum(1 for r in sk if r[4] == "declined"))
        try:
            sj = jload(by[("score-summary", "all", "json")])
        except (KeyError, OSError, ValueError):
            sj = {}
        chk("score-summary json total_correct", correct, sj.get("total_correct"))
        smd = read(by.get(("score-summary", "all", "md"), ""))
        chk("score-summary md total", "%d / %d" % (correct, total), (re.search(r"\*\*(\d+ / \d+)", smd) or [0, None])[1])
        if expect is not None:
            chk("correct vs expected", expect, correct)
    # INDEX totals = directory listing
    idx = read(os.path.join(pack, "INDEX.md"))
    m = re.search(r"^- total: (\d+)$", idx, re.M)
    chk("INDEX total", len(files), m.group(1) if m else None)
    for kind in sorted(kinds):
        n = sum(1 for v in parsed.values() if v and v["kind"] == kind)
        m = re.search(r"^- %s: (\d+)$" % re.escape(kind), idx, re.M)
        chk("INDEX kind %s" % kind, n, m.group(1) if m else 0)
    chk("INDEX unregistered", 0, (re.search(r"^- unregistered: (\d+)$", idx, re.M) or [0, None])[1])
    print("check\texpected\tgot\tok")
    for r in rows:
        print("\t".join(str(c) for c in r))
    bad = sum(1 for r in rows if r[3] != "ok")
    print("RESULT\t%d checks\t%d failed\t%s" % (len(rows), bad, "FAIL" if bad else "ok"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

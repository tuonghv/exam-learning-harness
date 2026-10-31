"""Extraction accuracy benchmark (REQ-0025): exact question-level match vs a gold file, $0, no LLM.

Exact = NFC + whitespace collapse only. Never fold/norm/similarity: diacritic, case and sign
errors are exactly what is measured. No accuracy gate here (REQ-0024 owns gating).
"""
import json
import math
import os
import unicodedata

from exam_engine.ingest.refine import FORBIDDEN, norm_id
from exam_engine.ingest.schema import VERIFY_STATUSES

FIELDS = ("text", "formula", "options", "figures")
TARGETS = (0.99, 0.999, 0.99999)
Z95 = 1.959963984540054


def canon(s):
    return " ".join(unicodedata.normalize("NFC", s).split())


def wilson(k, n, z=Z95):
    """Wilson score interval (lo, hi) for k successes in n; None when n == 0."""
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def zero_error_n(target, conf=0.95):
    """Error-free samples needed to claim accuracy >= target at confidence conf."""
    return int(math.ceil(math.log(1 - conf) / math.log(target)))


def _rate(k, n):
    w = wilson(k, n)
    return {"k": k, "n": n, "rate": k / n if n else None, "wilson": list(w) if w else None}


def _page(f):
    return f.get("page") if isinstance(f, dict) else f


def _record(q):
    if not isinstance(q, dict):
        raise ValueError("question is not an object")
    for k in FORBIDDEN:
        if k in q:
            raise ValueError("forbidden key %r in a question" % k)
    qid = norm_id(q.get("id", q.get("n")))
    if qid is None:
        raise ValueError("question without a numeric id/n")
    lat = q.get("latex")
    formula = (lat.get("text") if isinstance(lat, dict) else None) or q.get("formula") or ""
    opts = q.get("options") or {}
    if isinstance(opts, list):
        opts = {str(o.get("key")): o.get("text", "") for o in opts if isinstance(o, dict)}
    elif not isinstance(opts, dict):
        raise ValueError("question %s: options must be a list or object" % qid)
    ver = q.get("verification")
    status = (ver.get("status") if isinstance(ver, dict) else None) or "unverified"
    if status not in VERIFY_STATUSES:
        raise ValueError("question %s: bad verification status %r" % (qid, status))
    figs = sorted(p for p in (_page(f) for f in q.get("figures") or []) if p is not None)
    return {"id": qid, "text": str(q.get("text") or ""), "formula": str(formula),
            "options": {str(k): str(v) for k, v in opts.items()}, "figures": figs, "status": status}


def load_questions(path):
    """{id: canonical record}; ValueError on unreadable/invalid input."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ValueError("cannot read %s: %s" % (path, exc))
    if isinstance(data, dict):
        for k in FORBIDDEN:
            if k in data:
                raise ValueError("forbidden key %r in %s" % (k, path))
        data = data.get("questions")
    if not isinstance(data, list) or not data:
        raise ValueError("no questions in %s" % path)
    out = {}
    for q in data:
        r = _record(q)
        if r["id"] in out:
            raise ValueError("duplicate question id %s in %s" % (r["id"], path))
        out[r["id"]] = r
    return out


def _wrong(g, e):
    """Fields of gold record g that differ in extracted record e (None = missing)."""
    if e is None:
        return list(FIELDS)
    bad = []
    if canon(g["text"]) != canon(e["text"]):
        bad.append("text")
    if canon(g["formula"]) != canon(e["formula"]):
        bad.append("formula")
    go = {k: canon(v) for k, v in g["options"].items()}
    eo = {k: canon(v) for k, v in e["options"].items()}
    if go != eo:
        bad.append("options")
    if g["figures"] != e["figures"]:
        bad.append("figures")
    return bad


def evaluate(gold, extracted):
    """Summary dict of exact question-level accuracy, verified precision, needs_review rate."""
    n = len(gold)
    rows, fails = [], dict((f, 0) for f in FIELDS)
    app = {"formula": [0, 0], "figures": [0, 0]}
    ver = [0, 0]
    counts = dict((s, 0) for s in VERIFY_STATUSES)
    for qid in sorted(gold, key=int):
        g, e = gold[qid], extracted.get(qid)
        bad = _wrong(g, e)
        status = e["status"] if e else "missing"
        if e:
            counts[status] += 1
        for f in bad:
            fails[f] += 1
        for f in app:
            if g[f]:
                app[f][1] += 1
                app[f][0] += f not in bad
        if status == "verified":
            ver[1] += 1
            ver[0] += not bad
        rows.append({"id": qid, "status": status, "wrong": bad})
    overall = _rate(sum(1 for r in rows if not r["wrong"]), n)
    return {"n": n, "matched": sum(1 for q in gold if q in extracted),
            "missing": [q for q in sorted(gold, key=int) if q not in extracted],
            "extra": sorted((q for q in extracted if q not in gold), key=int),
            "overall": overall,
            "fields": dict((f, _rate(n - fails[f], n)) for f in FIELDS),
            "applicable": dict((f, _rate(v[0], v[1])) for f, v in app.items()),
            "verified_precision": _rate(*ver),
            "needs_review": _rate(counts["needs_review"], n),
            "status_counts": counts,
            "claims": {"targets": dict((str(t), zero_error_n(t)) for t in TARGETS),
                       "supported_lower": overall["wilson"][0] if overall["wilson"] else None},
            "questions": rows}


def _fmt(r, na=""):
    if r["rate"] is None:
        return na or "n/a"
    return "%d/%d = %.1f%% (Wilson 95%% %.1f%%-%.1f%%)" % (
        r["k"], r["n"], 100 * r["rate"], 100 * r["wilson"][0], 100 * r["wilson"][1])


def _lines(sm):
    ls = ["overall %s" % _fmt(sm["overall"])]
    ls += ["%s %s" % (f, _fmt(sm["fields"][f])) for f in FIELDS]
    ls += ["%s (applicable only) %s" % (f, _fmt(sm["applicable"][f], "n/a (0 gold)")) for f in sm["applicable"]]
    ls.append("verified precision %s" % _fmt(sm["verified_precision"], "n/a (0 verified)"))
    ls.append("needs_review %s" % _fmt(sm["needs_review"]))
    return ls


def claim_line(sm):
    t = sm["claims"]["targets"]["0.99999"]
    lo = sm["claims"]["supported_lower"]
    return "99.999%% is NOT claimed: needs >= %d error-free questions (n=%d); 95%% lower bound %s." % (
        t, sm["n"], "%.2f%%" % (100 * lo) if lo is not None else "n/a")


def report_lines(sm):
    return _lines(sm) + [claim_line(sm)]


def report_md(sm, gold_path="", extracted_path=""):
    md = ["# Extraction accuracy (exact match)", "",
          "gold: %s  extracted: %s" % (gold_path, extracted_path),
          "n=%d matched=%d missing=%s extra=%s" % (sm["n"], sm["matched"], sm["missing"] or "none",
                                                  sm["extra"] or "none"), "", "## Metrics", "",
          "| Metric | k/n | rate | Wilson 95% |", "|---|---|---|---|"]
    rows = [("overall", sm["overall"])] + [(f, sm["fields"][f]) for f in FIELDS]
    rows += [("%s (applicable only)" % f, sm["applicable"][f]) for f in sm["applicable"]]
    rows += [("verified precision", sm["verified_precision"]), ("needs_review", sm["needs_review"])]
    for name, r in rows:
        if r["rate"] is None:
            md.append("| %s | %d/%d | n/a | n/a |" % (name, r["k"], r["n"]))
        else:
            md.append("| %s | %d/%d | %.1f%% | %.1f%%-%.1f%% |" % (
                name, r["k"], r["n"], 100 * r["rate"], 100 * r["wilson"][0], 100 * r["wilson"][1]))
    md += ["", "Lines:", ""] + ["- " + ln for ln in _lines(sm)]
    if sm["verified_precision"]["n"] == 0:
        md.append("- verified precision: n/a (0 verified)")
    md += ["", "## Claims", "", claim_line(sm), "", "| target | n needed (error-free, 95%) |", "|---|---|"]
    md += ["| %g%% | %d |" % (round(float(t) * 100, 3), v) for t, v in sorted(sm["claims"]["targets"].items())]
    md += ["", "## Wrong questions", ""]
    bad = [r for r in sm["questions"] if r["wrong"]]
    md += ["- Q%s [%s]: %s" % (r["id"], r["status"], ", ".join(r["wrong"])) for r in bad] or ["none"]
    return "\n".join(md) + "\n"


def write(sm, out_dir, gold_path="", extracted_path=""):
    os.makedirs(out_dir, exist_ok=True)
    jp, mp = (os.path.join(out_dir, "extract_eval.json"), os.path.join(out_dir, "extract_eval.md"))
    with open(jp, "w", encoding="utf-8") as fh:
        json.dump(sm, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    with open(mp, "w", encoding="utf-8") as fh:
        fh.write(report_md(sm, gold_path, extracted_path))
    return jp, mp

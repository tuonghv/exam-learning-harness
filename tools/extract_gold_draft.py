#!/usr/bin/env python3
"""DGNL extraction gold draft (TASK-151, REQ-0078): sample published questions for a hand-checked gold.

build:  sample N questions (seeded, stratified over the published exams) from the solver inputs
        (plan run `input/exam.md` + `input/assembly.json`) and write to OUT:
          extracted.json   the questions as the solver saw them (extract-eval question format)
          gold-draft.json  the same text, `checked: false` - the starting point the user corrects
          review.html      page image(s) beside editable stem/options; exports the corrected gold JSON
store:  check a corrected gold (every question `checked`, same ids as extracted.json) and write it to DEST.
$0, no model call. Shared passages and figures are out of scope (stem + options only).
Usage:
  python3 -I tools/extract_gold_draft.py build [--config F] [--n 40] [--seed 151] [--out work/TASK-151] [--no-images]
  python3 -I tools/extract_gold_draft.py store CORRECTED.json EXTRACTED.json DEST.json
"""
import argparse
import base64
import html
import json
import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import parser as ep  # noqa: E402

DPI = 100
NOTE = ("Fix content only: digits, words, diacritics, signs, missing or extra text, option text. Keep the "
        "plain-text math notation of the extraction (sqrt(..), x^2, log_2 3, a/b): exact match is scored.")


def _printed(run_dir):
    """{local id: printed number} from input/assembly.json (empty when missing)."""
    try:
        with open(os.path.join(run_dir, "input", "assembly.json"), encoding="utf-8") as fh:
            qs = json.load(fh).get("questions") or []
    except (OSError, ValueError):
        return {}
    out = {}
    for q in qs:
        try:
            out[int(q["id"])] = int(q.get("printed") or q["id"])
        except (KeyError, TypeError, ValueError):
            pass
    return out


def exam_year(exam_id):
    digits = "".join(c for c in exam_id if c.isdigit())
    if len(digits) < 2:
        raise ValueError("exam id %r has no year" % exam_id)
    return int(digits[-2:])


def collect(config_path, root=ROOT):
    """{exam_id: [question record]} from the published plan runs."""
    with open(config_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    out = {}
    for exam_id, ex in sorted(cfg.get("exams", {}).items()):
        yy = exam_year(exam_id)
        key = ex.get("key") or ""
        pdf = os.path.join(root, key[:-len(".answer.txt")] + ".pdf") if key.endswith(".answer.txt") else None
        recs, seen = [], set()
        for run in ex.get("plan_runs") or []:
            run_dir = os.path.join(root, run)
            exam_md = os.path.join(run_dir, "input", "exam.md")
            parsed = ep.parse_exam(exam_md)
            subject = parsed.get("fields", {}).get("Subject", "")
            printed = _printed(run_dir)
            for q in parsed.get("questions") or []:
                opts = q.get("options") or {}
                text = (q.get("stem") or q.get("text") or "").strip()
                if not text or len(opts) < 2:
                    continue
                num = printed.get(int(q["id"]), int(q["id"]))
                qid = yy * 1000 + num
                if qid in seen:
                    continue
                seen.add(qid)
                recs.append({"id": str(qid), "exam": exam_id, "subject": subject, "printed": num,
                             "text": text, "formula": "", "options": dict(opts), "figures": [],
                             "pages": [p for p in q.get("pages") or [] if isinstance(p, int)],
                             "pdf": os.path.relpath(pdf, root) if pdf else None, "run": run})
        out[exam_id] = recs
    return out


def sample(by_exam, n, seed):
    """n questions, spread as evenly as possible over the exams, seeded; sorted by id."""
    rng = random.Random(seed)
    exams = [e for e in sorted(by_exam) if by_exam[e]]
    if not exams:
        raise ValueError("no questions to sample")
    quota = {e: n // len(exams) for e in exams}
    for e in exams[:n % len(exams)]:
        quota[e] += 1
    picked = []
    for e in exams:
        pool = by_exam[e]
        if quota[e] > len(pool):
            raise ValueError("%s has %d questions, %d asked" % (e, len(pool), quota[e]))
        picked += rng.sample(pool, quota[e])
    return sorted(picked, key=lambda r: int(r["id"]))


def gold_doc(recs, origin, checked=False):
    qs = []
    for r in recs:
        q = {k: r[k] for k in ("id", "exam", "subject", "printed", "text", "formula", "options", "figures", "pages")}
        q["checked"] = checked
        qs.append(q)
    return {"gold_version": 1, "origin": origin, "questions": qs}


def page_images(recs, root=ROOT):
    """{(pdf, page): data URI} for every page of the sample (empty without PyMuPDF or the PDF)."""
    try:
        import fitz  # noqa: PLC0415 - optional
    except ImportError:
        return {}
    out = {}
    for pdf in sorted({r["pdf"] for r in recs if r["pdf"]}):
        path = os.path.join(root, pdf)
        if not os.path.isfile(path):
            continue
        doc = fitz.open(path)
        for p in sorted({p for r in recs if r["pdf"] == pdf for p in r["pages"]}):
            if 1 <= p <= doc.page_count:
                pix = doc[p - 1].get_pixmap(dpi=DPI)
                out[(pdf, p)] = "data:image/jpeg;base64," + base64.b64encode(pix.tobytes("jpeg", jpg_quality=60)).decode()
        doc.close()
    return out


PAGE = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>DGNL extraction gold</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#ddd;--ok:#1b7f3b;--card:#fafafa}
@media (prefers-color-scheme: dark){:root{--bg:#161616;--fg:#eee;--mut:#aaa;--line:#333;--ok:#5ec27e;--card:#1e1e1e}}
body{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;margin:0 16px 80px}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 0;z-index:2}
.q{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:16px;border:1px solid var(--line);
border-radius:8px;padding:12px;margin:16px 0;background:var(--card)}
.q.done{border-color:var(--ok)}
.imgs{max-height:80vh;overflow:auto}.imgs img{width:100%;display:block;margin-bottom:6px;background:#fff}
textarea,input[type=text]{width:100%;box-sizing:border-box;font:inherit;background:var(--bg);color:var(--fg);
border:1px solid var(--line);border-radius:4px;padding:6px}
textarea{min-height:110px}.mut{color:var(--mut);font-size:13px}label.opt{display:block;margin-top:6px}
button{font:inherit;padding:6px 12px}
@media (max-width:800px){.q{grid-template-columns:1fr}}
</style></head><body>
<header><b>DGNL extraction gold</b> - <span id="count"></span> checked
<button id="dl">Download gold JSON</button>
<div class="mut">__NOTE__ Tick "checked" only after comparing every word with the page image.</div></header>
__CARDS__
<script>
const DRAFT = __DRAFT__;
const KEY = "dgnl-gold-" + DRAFT.origin;
let saved = {};
try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { saved = {}; }
function store() { try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {} }
function field(id, k) { return document.querySelector('[data-q="' + id + '"][data-k="' + k + '"]'); }
function refresh() {
  let n = 0;
  for (const q of DRAFT.questions) {
    const done = field(q.id, "checked").checked; if (done) n++;
    document.getElementById("q" + q.id).classList.toggle("done", done);
  }
  document.getElementById("count").textContent = n + " / " + DRAFT.questions.length;
}
for (const q of DRAFT.questions) {
  const s = saved[q.id] || {};
  for (const el of document.querySelectorAll('[data-q="' + q.id + '"]')) {
    const k = el.dataset.k;
    if (k === "checked") el.checked = !!s.checked;
    else if (s[k] !== undefined) el.value = s[k];
    el.addEventListener("input", () => {
      saved[q.id] = saved[q.id] || {};
      saved[q.id][k] = k === "checked" ? el.checked : el.value; store(); refresh();
    });
  }
}
refresh();
document.getElementById("dl").addEventListener("click", () => {
  const out = JSON.parse(JSON.stringify(DRAFT));
  let open = 0;
  for (const q of out.questions) {
    q.text = field(q.id, "text").value;
    for (const k of Object.keys(q.options)) q.options[k] = field(q.id, "opt" + k).value;
    q.checked = field(q.id, "checked").checked; if (!q.checked) open++;
  }
  if (open && !confirm(open + " question(s) not checked yet. Download anyway?")) return;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {type: "application/json"}));
  a.download = "dgnl-real-001.json"; a.click();
});
</script></body></html>
"""


def review_html(gold, recs, images):
    by_id = {r["id"]: r for r in recs}
    cards = []
    for q in gold["questions"]:
        r = by_id[q["id"]]
        imgs = "".join('<img alt="%s page %d" src="%s">' % (html.escape(r["pdf"] or ""), p, images[(r["pdf"], p)])
                       for p in r["pages"] if (r["pdf"], p) in images) or '<p class="mut">no page image</p>'
        opts = "".join('<label class="opt">%s. <input type="text" data-q="%s" data-k="opt%s" value="%s"></label>'
                       % (html.escape(k), q["id"], html.escape(k), html.escape(v)) for k, v in q["options"].items())
        cards.append(
            '<section class="q" id="q%s"><div class="imgs">%s</div><div><div><b>%s</b> - %s - printed %d - '
            'PDF page %s</div><textarea data-q="%s" data-k="text">%s</textarea>%s'
            '<label class="opt"><input type="checkbox" data-q="%s" data-k="checked"> checked against the page</label>'
            '</div></section>' % (q["id"], imgs, html.escape(q["exam"]), html.escape(q["subject"]), q["printed"],
                                  ", ".join(str(p) for p in r["pages"]) or "?", q["id"], html.escape(q["text"]),
                                  opts, q["id"]))
    draft = json.dumps(gold, ensure_ascii=False).replace("</", "<\\/")
    return (PAGE.replace("__NOTE__", html.escape(NOTE)).replace("__CARDS__", "\n".join(cards))
            .replace("__DRAFT__", draft))


def build(a):
    recs = sample(collect(a.config, a.root), a.n, a.seed)
    os.makedirs(a.out, exist_ok=True)
    origin = "dgnl-real seed %d n %d" % (a.seed, a.n)
    extracted = gold_doc(recs, origin + " (solver input)")
    draft = gold_doc(recs, origin)
    for name, doc in (("extracted.json", extracted), ("gold-draft.json", draft)):
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=1)
    images = {} if a.no_images else page_images(recs, a.root)
    with open(os.path.join(a.out, "review.html"), "w", encoding="utf-8") as fh:
        fh.write(review_html(draft, recs, images))
    per = {}
    for r in recs:
        per[r["exam"]] = per.get(r["exam"], 0) + 1
    print("SAMPLE: %d questions %s; pages imaged %d; out %s" % (len(recs), per, len(images), a.out))
    return 0


def check_corrected(corrected, extracted):
    """Problems (list of str) of a corrected gold against the extracted file."""
    probs = []
    cq = {q.get("id"): q for q in corrected.get("questions") or []}
    eq = {q.get("id"): q for q in extracted.get("questions") or []}
    if set(cq) != set(eq):
        probs.append("ids differ from extracted.json: missing %s, extra %s"
                     % (sorted(set(eq) - set(cq)), sorted(set(cq) - set(eq))))
    for qid in sorted(set(cq) & set(eq)):
        q = cq[qid]
        if q.get("checked") is not True:
            probs.append("question %s is not checked" % qid)
        if not str(q.get("text") or "").strip():
            probs.append("question %s has an empty stem" % qid)
        if sorted(q.get("options") or {}) != sorted(eq[qid].get("options") or {}):
            probs.append("question %s option letters changed" % qid)
    return probs


def store(a):
    with open(a.corrected, encoding="utf-8") as fh:
        corrected = json.load(fh)
    with open(a.extracted, encoding="utf-8") as fh:
        extracted = json.load(fh)
    probs = check_corrected(corrected, extracted)
    for p in probs:
        print("PROBLEM: " + p)
    if probs:
        return 1
    corrected["origin"] = corrected.get("origin", "") + " (hand-checked, REQ-0078)"
    os.makedirs(os.path.dirname(os.path.abspath(a.dest)), exist_ok=True)
    with open(a.dest, "w", encoding="utf-8") as fh:
        json.dump(corrected, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("STORED: %s (%d questions)" % (a.dest, len(corrected["questions"])))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--config", default=os.path.join(ROOT, "config", "published_reports.json"))
    b.add_argument("--root", default=ROOT)
    b.add_argument("--n", type=int, default=40)
    b.add_argument("--seed", type=int, default=151)
    b.add_argument("--out", default=os.path.join(ROOT, "work", "TASK-151"))
    b.add_argument("--no-images", action="store_true")
    s = sub.add_parser("store")
    s.add_argument("corrected")
    s.add_argument("extracted")
    s.add_argument("dest")
    a = ap.parse_args(argv)
    try:
        return build(a) if a.cmd == "build" else store(a)
    except (OSError, ValueError, KeyError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""51.6 before/after OCR measurement (helper, not a test):
`python3 -I tests/unit/ocr_before_after.py [out.tsv]` (needs tesseract vie+eng; synthetic text only).

Scanned synthetic exams, families A/B/C (fonts of ocr_gap_sweep), 10 questions per family, one column.
before = bridge text (no char-box respacing) and no ocr_doubt marker (commit 6b9b996-era behaviour);
after = current code. Per family and arm: n, real errors (extracted text/options != gold under
extract_eval.canon), wrong questions with no ocr_doubt marker (reach the solver), glued tokens (letters
aligned to the gold, diacritic-folded), marked correct questions (false alarm). Wilson via extract_eval.
"""
import copy
import os
import sys
import tempfile
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import optional  # noqa: E402
from exam_engine.ingest.adapters import pdf as pdfmod  # noqa: E402
from exam_engine.pipeline import extract_eval as ee  # noqa: E402

import ocr_gap_sweep as sw  # noqa: E402

NQ, PER_PAGE = 10, 5
STEM = "Tìm giá trị của biểu thức khi x bằng %d và y bằng %d trong bài toán sau đây."
SHORT = "Đề thi thử có %d câu, mỗi câu ở mức %d điểm; tử số và kỳ này ủy ban đổi mã đề 101."
MILD = "Cho biet x bang %d va y bang %d, tinh tong cua hai so do trong bai toan nay."
OPTS_MILD = ["Bang %d.", "La %d.", "Lon hon %d.", "Khong doi %d."]
OPTS = ["Giá trị bằng %d.", "Kết quả là %d.", "Số lớn hơn %d.", "Đáp số không đổi %d."]


def gold_questions(kind, nq=NQ):
    out = []
    for n in range(1, nq + 1):
        stem = (STEM if kind == "prose" else MILD if kind == "mild" else SHORT) % (n + 1, n + 2)
        opts = OPTS_MILD if kind == "mild" else OPTS
        out.append({"n": n, "text": stem, "options": dict(
            (k, o % (n + i)) for i, (k, o) in enumerate(zip("ABCD", opts)))})
    return out


def render(fitz, gold, font, size, path):
    doc = fitz.open()
    for p in range(0, len(gold), PER_PAGE):
        pg = doc.new_page()
        y = 70
        for q in gold[p:p + PER_PAGE]:
            pg.insert_text((50, y), "Câu %d. %s" % (q["n"], q["text"]), fontsize=size, fontname="f", fontfile=font)
            y += size * 1.8
            for k, v in q["options"].items():
                pg.insert_text((70, y), "%s. %s" % (k, v), fontsize=size, fontname="f", fontfile=font)
                y += size * 1.8
            y += size * 1.2
    sw.scan(fitz, doc).save(path)
    doc.close()


def _opts(q):
    o = q.get("options") or {}
    if isinstance(o, list):
        o = dict((str(x.get("key")), x.get("text", "")) for x in o if isinstance(x, dict))
    return dict((str(k), ee.canon(v)) for k, v in o.items())


def run_arm(path, after):
    cfg = {"asset_dir": tempfile.mkdtemp()}
    if after:
        return pdfmod.ingest(path, cfg)
    with mock.patch.object(pdfmod, "_ocr_blocks", lambda page, tp, gap=0: pdfmod._page_blocks(page, tp)), \
            mock.patch.object(pdfmod, "_ocr_doubt", lambda *a, **k: None):
        return pdfmod.ingest(path, cfg)


def score(gold, doc):
    ex = dict((q.get("n"), q) for q in doc.get("questions", ()))
    n = len(gold)
    wrong = wrong_unmarked = marked_ok = correct = 0
    soft_flagged = soft_wrong = soft_ok = 0
    kinds = {}
    gtext, otext = [], []
    for g in gold:
        e = ex.get(g["n"])
        gt = ee.canon(g["text"]) + " " + " ".join(g["options"].values())
        gtext.append(gt)
        if e is None:
            wrong += 1
            wrong_unmarked += 1
            continue
        otext.append(ee.canon(e.get("text", "")) + " " + " ".join(_opts(e).values()))
        bad = ee.canon(e.get("text", "")) != ee.canon(g["text"]) or _opts(e) != dict(
            (k, ee.canon(v)) for k, v in g["options"].items())
        marked = bool(e.get("ocr_doubt"))
        soft = "option_parity" in (e.get("structure") or ())
        for kd in e.get("ocr_doubt") or ():
            kinds[kd] = kinds.get(kd, 0) + 1
        soft_flagged += soft
        if bad:
            wrong += 1
            wrong_unmarked += not marked
            soft_wrong += soft
        else:
            correct += 1
            marked_ok += marked
            soft_ok += soft
    glued, split, cer = sw.compare("\n".join(gtext), "\n".join(otext))
    return {"n": n, "wrong": wrong, "wrong_unmarked": wrong_unmarked, "correct": correct,
            "marked_correct": marked_ok, "glued": glued, "cer": round(cer, 4),
            "soft_flagged": soft_flagged, "soft_wrong": soft_wrong, "soft_correct": soft_ok,
            "marked_by_kind": kinds}


# ---- 71.5: calibration of the 71.1-71.4 signals (one ingest per family, then offline replay) ----
# Cm = family C font/size with unaccented text (accented text is never read right there): the correct-question pool for C (C itself has none)
FAMILIES71 = dict(sw.FAMILIES, Cm=(sw.CALADEA, 14, "mild"), D=(sw.DEJAVU, 11, "prose"))  # D = clean DejaVuSans 11 (14 overflows the page width), false-alarm pool
NQ71, PER_PAGE71 = 30, 5
FLOORS = (50, 60, 70, 75, 80, 85, 90)
MARGINS = (0, 5, 10)
NO_WEAK = -1000  # margin that disables the weak token shapes (low_conf alone)


def record(path):
    """Ingest once with the real pipeline; capture each _ocr_doubt call (pre-marker questions + inputs)."""
    rec = []
    real = pdfmod._ocr_doubt

    def spy(qs, *a, **k):
        rec.append((copy.deepcopy(qs), a, dict(k)))
        return real(qs, *a, **k)

    with mock.patch.object(pdfmod, "_ocr_doubt", spy):
        pdfmod.ingest(path, {"asset_dir": tempfile.mkdtemp(), "ocr_conf": "auto"})
    return rec[0] if rec else None


def replay(rec, conf=True, floor=70, margin=0, tokens=True, parity=False):
    """Re-run the doubt signals on a recorded call; -> {"questions": qs}. Arm a51: conf=False tokens=False."""
    qs, a, k = rec
    qs = copy.deepcopy(qs)
    k = dict(k, floor=floor, conf=k.get("conf") if conf else None)
    with mock.patch.object(pdfmod, "TOKEN_MARGIN", margin):
        if tokens:
            ocr_q = pdfmod._ocr_doubt(qs, *a, **k)
        else:
            with mock.patch.object(pdfmod, "_odd_token", lambda *x, **y: False):
                ocr_q = pdfmod._ocr_doubt(qs, *a, **k)
    if parity:
        pdfmod._option_parity(qs, ocr_q)
    return {"questions": qs}


def measure71():
    """{family: (gold, record)}; None without vie data / fitz."""
    fitz = optional.load("fitz", "pymupdf")
    _, lang, have = pdfmod.pick_ocr_language({})
    if "vie" not in have:
        return None
    out = {}
    for fam, (font, size, kind) in FAMILIES71.items():
        gold = gold_questions(kind, NQ71)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, fam + ".pdf")
            render(fitz, gold, font, size, path)
            out[fam] = (gold, record(path))
    return out


def sweep71(data):
    """(sweep rows, arm rows). Sweep: low_conf alone and low_conf+weak tokens per floor/margin."""
    arms, sweep = [], []
    for fam, (gold, rec) in data.items():
        for name, kw in (("after51", dict(conf=False, tokens=False)), ("strong_token", dict(conf=False)),
                         ("parity", dict(conf=False, tokens=False, parity=True))):
            arms.append((fam, name, score(gold, replay(rec, **kw))))
        for fl in FLOORS:
            for mg in (NO_WEAK,) + MARGINS:
                s = score(gold, replay(rec, floor=fl, margin=mg))
                sweep.append((fam, fl, mg, s))
    return sweep, arms


def pick(sweep):
    """Largest floor with marked_correct 0 on every family for margin NO_WEAK; then the smallest margin
    keeping that floor at 0 false alarms with the best wrong_unmarked total."""
    def tot(fl, mg, key):
        return sum(s[key] for f, f_, m, s in sweep if f_ == fl and m == mg)
    ok = [fl for fl in FLOORS if tot(fl, NO_WEAK, "marked_correct") == 0]
    if not ok:
        return None, None
    fl = max(ok)
    best = min(MARGINS, key=lambda mg: (tot(fl, mg, "wrong_unmarked") if tot(fl, mg, "marked_correct") == 0 else 10 ** 6, mg))
    return fl, best


def sweep_table(sweep):
    out = ["family\tfloor\tmargin\twrong\twrong_unmarked\tmarked_correct\tkinds"]
    for fam, fl, mg, s in sweep:
        out.append("\t".join([fam, str(fl), "low_conf_only" if mg == NO_WEAK else str(mg), str(s["wrong"]),
                              str(s["wrong_unmarked"]), str(s["marked_correct"]),
                              ",".join("%s=%d" % kv for kv in sorted(s["marked_by_kind"].items()))]))
    return "\n".join(out)


def arms_table(arms, extra=()):
    out = ["family\tarm\tn\twrong\twrong_unmarked\tcorrect\tmarked_correct\tsoft_flagged\tsoft_wrong\t"
           "soft_correct\tmarked_by_kind"]
    for fam, name, s in list(arms) + list(extra):
        out.append("\t".join([fam, name, str(s["n"]), str(s["wrong"]), str(s["wrong_unmarked"]), str(s["correct"]),
                              str(s["marked_correct"]), str(s["soft_flagged"]), str(s["soft_wrong"]),
                              str(s["soft_correct"]), ",".join("%s=%d" % kv for kv in sorted(s["marked_by_kind"].items()))]))
    return "\n".join(out)


def main71(sweep_path, arms_path):
    data = measure71()
    if data is None:
        sys.exit("vie+eng tesseract data not available")
    sweep, arms = sweep71(data)
    fl, mg = pick(sweep)
    extra = []
    if fl is not None:
        for fam, (gold, rec) in data.items():
            extra.append((fam, "after71(floor=%d,margin=%d)" % (fl, mg),
                          score(gold, replay(rec, floor=fl, margin=mg, parity=True))))
            extra.append((fam, "lowconf_only(floor=%d)" % fl, score(gold, replay(rec, floor=fl, margin=NO_WEAK, tokens=True))))
    for path, text in ((sweep_path, sweep_table(sweep) + "\n# pick floor=%s margin=%s\n" % (fl, mg)),
                       (arms_path, arms_table(arms, extra) + "\n")):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(arms_table(arms, extra))
    print("# pick floor=%s margin=%s" % (fl, mg))


def _ci(k, n):
    w = ee.wilson(k, n)
    return "%d/%d=%.2f [%.2f-%.2f]" % (k, n, k / n, w[0], w[1]) if w else "0/0"


def measure():
    fitz = optional.load("fitz", "pymupdf")
    _, lang, have = pdfmod.pick_ocr_language({})
    if "vie" not in have:
        return None
    rows = []
    for fam, (font, size, kind) in sw.FAMILIES.items():
        gold = gold_questions(kind)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, fam + ".pdf")
            render(fitz, gold, font, size, path)
            for arm, after in (("before", False), ("after", True)):
                rows.append((fam, arm, score(gold, run_arm(path, after))))
    return rows


def table(rows):
    out = ["family\tarm\tn\treal_error\twrong_unmarked\tglued\tcer\tfalse_alarm(marked of correct)"]
    for fam, arm, s in rows:
        out.append("\t".join([fam, arm, str(s["n"]), _ci(s["wrong"], s["n"]), _ci(s["wrong_unmarked"], s["n"]),
                              str(s["glued"]), str(s["cer"]),
                              _ci(s["marked_correct"], s["correct"]) if s["correct"] else "n/a (0 correct)"]))
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--calibrate":  # --calibrate sweep.tsv arms.tsv
        main71(sys.argv[2], sys.argv[3])
        sys.exit(0)
    rows = measure()
    if rows is None:
        sys.exit("vie+eng tesseract data not available")
    text = table(rows)
    print(text)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as fh:
            fh.write(text + "\n")

"""51.6 before/after OCR measurement (helper, not a test):
`python3 -I tests/unit/ocr_before_after.py [out.tsv]` (needs tesseract vie+eng; synthetic text only).

Scanned synthetic exams, families A/B/C (fonts of ocr_gap_sweep), 10 questions per family, one column.
before = bridge text (no char-box respacing) and no ocr_doubt marker (commit 6b9b996-era behaviour);
after = current code. Per family and arm: n, real errors (extracted text/options != gold under
extract_eval.canon), wrong questions with no ocr_doubt marker (reach the solver), glued tokens (letters
aligned to the gold, diacritic-folded), marked correct questions (false alarm). Wilson via extract_eval.
"""
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
OPTS = ["Giá trị bằng %d.", "Kết quả là %d.", "Số lớn hơn %d.", "Đáp số không đổi %d."]


def gold_questions(kind):
    out = []
    for n in range(1, NQ + 1):
        stem = (STEM if kind == "prose" else SHORT) % (n + 1, n + 2)
        out.append({"n": n, "text": stem, "options": dict(
            (k, o % (n + i)) for i, (k, o) in enumerate(zip("ABCD", OPTS)))})
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
        if bad:
            wrong += 1
            wrong_unmarked += not marked
        else:
            correct += 1
            marked_ok += marked
    glued, split, cer = sw.compare("\n".join(gtext), "\n".join(otext))
    return {"n": n, "wrong": wrong, "wrong_unmarked": wrong_unmarked, "correct": correct,
            "marked_correct": marked_ok, "glued": glued, "cer": round(cer, 4)}


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
    rows = measure()
    if rows is None:
        sys.exit("vie+eng tesseract data not available")
    text = table(rows)
    print(text)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as fh:
            fh.write(text + "\n")

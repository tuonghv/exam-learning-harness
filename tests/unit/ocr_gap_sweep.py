"""51.7 OCR_GAP sweep (helper, not a test): `python3 -I tests/unit/ocr_gap_sweep.py [out.tsv]`.

Renders 2-page image-only synthetic families A/B/C, OCRs each page once, rebuilds the text for every
candidate gap and prints TSV: family, gap, glued, split, cer. Compared diacritic-folded (eng-only host).
"""
import difflib
import os
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import optional  # noqa: E402
from exam_engine.ingest.adapters import pdf as pdfmod  # noqa: E402

GAPS = [round(0.05 * i, 2) for i in range(1, 9)]
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
CARLITO = "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf"
CALADEA = "/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf"
FAMILIES = {  # name: (font, size, vocabulary kind)
    "A": (DEJAVU, 10, "prose"), "B": (CARLITO, 11, "prose"), "C": (CALADEA, 14, "short"),
}
PROSE = ("Câu %d. Tìm giá trị của biểu thức sau đây khi x bằng %d và y bằng %d. Chọn đáp án đúng nhất "
         "trong các phương án dưới đây cho bài toán này.")
SHORT = "Câu %d. Đề thi thử có %d câu, mỗi câu ở mức %d điểm; tử số và mẫu số của kỳ này ủy ban đã đổi mã đề 101."


def fold(s):
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if not unicodedata.combining(c))


def family_pages(name, fitz):
    font, size, kind = FAMILIES[name]
    doc = fitz.open()
    gold = []
    for pno in range(2):
        pg = doc.new_page()
        lines = [(PROSE if kind == "prose" else SHORT) % (pno * 10 + i + 1, i + 2, i + 3) for i in range(14)]
        # wrap long lines at ~70 words-chars so the line fits the page
        wrapped = []
        for ln in lines:
            w, cur = ln.split(), ""
            for t in w:
                if len(cur) + len(t) + 1 > 62:
                    wrapped.append(cur)
                    cur = t
                else:
                    cur = (cur + " " + t).strip()
            wrapped.append(cur)
        y = 60
        for ln in wrapped:
            if y > pg.rect.height - 50:
                break
            pg.insert_text((50, y), ln, fontsize=size, fontname="f", fontfile=font)
            gold.append(ln)
            y += size * 1.8
    return doc, gold


def scan(fitz, doc):
    out = fitz.open()
    for pg in doc:
        png = pg.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes("png")
        new = out.new_page(width=pg.rect.width, height=pg.rect.height)
        new.insert_image(new.rect, stream=png)
    return out


def _stream(text):
    """(letters without whitespace, set of letter indexes that start a word)."""
    chars, starts, new = [], set(), True
    for ch in fold(text):
        if ch.isspace():
            new = True
            continue
        if new:
            starts.add(len(chars))
        new = False
        chars.append(ch)
    return "".join(chars), starts


def compare(gold_text, ocr_text):
    """(glued, split, cer): word starts of the gold missing in the OCR / extra in the OCR, on the aligned letters."""
    g, gs = _stream(gold_text)
    o, os_ = _stream(ocr_text)
    glued = split = 0
    sm = difflib.SequenceMatcher(None, g, o, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            continue
        for k in range(i2 - i1):
            if k and ((i1 + k) in gs) != ((j1 + k) in os_):  # k=0: block edge, may follow an OCR error
                if (i1 + k) in gs:
                    glued += 1
                else:
                    split += 1
    cer = 1 - sm.ratio()
    return glued, split, cer


def sweep(families=("A", "B", "C"), gaps=GAPS, bridge=True):
    """[(family, gap, glued, split, cer)]; None when fitz or tesseract data is missing."""
    fitz = optional.load("fitz", "pymupdf")
    tess, lang, _ = pdfmod.pick_ocr_language({})
    if not lang:
        return None
    rows = []
    for fam in families:
        src, gold = family_pages(fam, fitz)
        img = scan(fitz, src)
        pages = []
        for pg in img:
            tp = pg.get_textpage_ocr(language=lang, dpi=pdfmod.OCR_DPI, full=True, tessdata=tess)
            pages.append((pg, tp))
        gtext = "\n".join(gold)
        for gap in gaps:
            ocr = "\n".join(b[1] for pg, tp in pages for b in pdfmod._ocr_blocks(pg, tp, gap))
            g, s, c = compare(gtext, ocr)
            rows.append((fam, gap, g, s, round(c, 4)))
        if bridge:  # gap 0.00 row = today's bridge text, the baseline
            ocr = "\n".join(b[1] for pg, tp in pages for b in pdfmod._page_blocks(pg, tp))
            g, s, c = compare(gtext, ocr)
            rows.append((fam, 0.0, g, s, round(c, 4)))
    return rows


def best_gap(rows):
    tot = {}
    for _, gap, g, s, _c in rows:
        if gap == 0.0:
            continue
        tot[gap] = tot.get(gap, 0) + g + s
    return min(sorted(tot), key=lambda k: tot[k]), tot


def main(argv):
    rows = sweep()
    if rows is None:
        print("no tesseract data")
        return 1
    lines = ["family\tgap\tglued\tsplit\tcer"] + ["%s\t%.2f\t%d\t%d\t%.4f" % r for r in rows]
    gap, tot = best_gap(rows)
    lines.append("# best_gap\t%.2f\ttotal_errors\t%s" % (gap, ",".join("%.2f=%d" % kv for kv in sorted(tot.items()))))
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    if len(argv) > 1:
        with open(argv[1], "w") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

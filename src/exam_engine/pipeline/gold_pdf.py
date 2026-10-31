"""Render an extraction gold file to a born-digital PDF (REQ-0039, tier 0, $0, no network).

Purpose: a deterministic input for the real PDF adapter, so `extract-eval` can score PDF-level
extraction. Clean single-column text layer: an optimistic upper bound, not a scanned-page test.
"""
import glob
import os

from exam_engine.ingest import optional
from exam_engine.pipeline import extract_eval

VARIANTS = ("text", "formula-image")
FONT_GLOB = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PAGE_W, PAGE_H, MARGIN, SIZE, LEAD = 595, 842, 50, 11, 14
FIG_W, FIG_H = 80, 60


def _font(font):
    path = font or (glob.glob(FONT_GLOB) or [None])[0]
    if not path or not os.path.isfile(path):
        raise ValueError("font file not found: %s" % (path or FONT_GLOB))
    return path


def _lines(q):
    """[(kind, text)] for one question; kind is text|formula|blank."""
    parts = q["text"].split("\n")
    out = [("text", "Câu %s. %s" % (q["id"], parts[0]))] + [("text", t) for t in parts[1:]]
    if q["formula"]:
        out.append(("formula", q["formula"]))
    for key in "ABCD":
        if key in q["options"]:
            out.append(("text", "%s. %s" % (key, q["options"][key])))
    return out


def _formula_pixmap(fitz, text, font):
    """Rasterise one formula line (150 dpi): visible to vision, absent from the text layer."""
    tmp = fitz.open()
    pg = tmp.new_page(width=PAGE_W - 2 * MARGIN, height=LEAD + 6)
    pg.insert_text((2, LEAD - 2), text, fontsize=SIZE, fontname="dj", fontfile=font)
    pix = pg.get_pixmap(dpi=150)
    tmp.close()
    return pix


def render(gold_path, out_pdf, variant="text", font=None):
    """Write OUT.pdf from the gold; return {"pages": int, "placed": {question id: page}}."""
    if variant not in VARIANTS:
        raise ValueError("variant must be one of %s, got %r" % (", ".join(VARIANTS), variant))
    font = _font(font)
    gold = extract_eval.load_questions(gold_path)
    fitz = optional.load("fitz", "pymupdf")
    width = PAGE_W - 2 * MARGIN
    doc = fitz.open()
    try:
        page, y, pno, placed = None, 0, 0, {}

        def new_page():
            nonlocal page, y, pno
            page, y, pno = doc.new_page(width=PAGE_W, height=PAGE_H), MARGIN, pno + 1

        new_page()
        for qid in sorted(gold, key=int):
            q = gold[qid]
            lines = _lines(q)
            for kind, t in lines:
                if kind != "formula" or variant == "text":
                    if _too_wide(fitz, t, font, width):
                        raise ValueError("question %s: line wider than the page: %r" % (qid, t[:40]))
            fig = bool(q["figures"])
            need = len(lines) * LEAD + (FIG_H + 10 if fig else 0) + LEAD
            if fig:
                want = q["figures"][0]
                if pno > want:
                    raise ValueError("question %s: figure page %d already passed (page %d)" % (qid, want, pno))
                while pno < want:
                    new_page()
            if y + need > PAGE_H - MARGIN and y > MARGIN:
                if fig and pno >= q["figures"][0]:
                    raise ValueError("question %s: does not fit on its figure page %d" % (qid, pno))
                new_page()
            if y + need > PAGE_H - MARGIN:
                raise ValueError("question %s: block taller than a page" % qid)
            placed[int(qid)] = pno
            for kind, t in lines:
                if kind == "formula" and variant == "formula-image":
                    rect = fitz.Rect(MARGIN, y - LEAD + 4, PAGE_W - MARGIN, y + 6)
                    page.insert_image(rect, pixmap=_formula_pixmap(fitz, t, font))
                else:
                    page.insert_text((MARGIN, y), t, fontsize=SIZE, fontname="dj", fontfile=font)
                y += LEAD
            if fig:
                x0, y0 = MARGIN, y + 4
                r = fitz.Rect(x0, y0, x0 + FIG_W, y0 + FIG_H)
                page.draw_rect(r, color=(0, 0, 0), width=1)
                page.draw_polyline([(x0 + 5, y0 + FIG_H - 5), (x0 + FIG_W - 5, y0 + FIG_H - 5),
                                    (x0 + FIG_W / 2, y0 + 5), (x0 + 5, y0 + FIG_H - 5)],
                                   color=(0, 0, 0), width=1)
                y = y0 + FIG_H + 6
            y += LEAD
        try:
            doc.save(out_pdf)
        except Exception as exc:  # fitz raises its own error types for I/O
            raise OSError("cannot write %s: %s" % (out_pdf, exc))
        return {"pages": pno, "placed": placed}
    finally:
        doc.close()


def _too_wide(fitz, text, font, width):
    f = fitz.Font(fontfile=font)
    return f.text_length(text, fontsize=SIZE) > width

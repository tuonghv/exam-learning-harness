"""Render an extraction gold file to a born-digital PDF (REQ-0039, tier 0, $0, no network).

Purpose: a deterministic input for the real PDF adapter, so `extract-eval` can score PDF-level
extraction. Clean single-column text layer: an optimistic upper bound, not a scanned-page test.
"""
import glob
import json
import os

from exam_engine.ingest import optional
from exam_engine.pipeline import extract_eval

VARIANTS = ("text", "formula-image")
LAYOUTS = ("block", "split")  # block: a question moves whole to the next page (default); split: it may cross at a line
FONT_GLOB = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PAGE_W, PAGE_H, MARGIN, SIZE, LEAD = 595, 842, 50, 11, 14
FIG_W, FIG_H = 80, 60


def _font(font):
    path = font or (glob.glob(FONT_GLOB) or [None])[0]
    if not path or not os.path.isfile(path):
        raise ValueError("font file not found: %s" % (path or FONT_GLOB))
    return path


def _lines(q):
    """[(kind, text, role)] for one question; kind is text|formula, role is stem0|stem|formula|opt:K."""
    parts = q["text"].split("\n")
    out = [("text", "Câu %s. %s" % (q["id"], parts[0]), "stem0")] + [("text", t, "stem") for t in parts[1:]]
    if q["formula"]:
        out += [("formula", t, "formula") for t in q["formula"].split("\n")]  # one line per \n (F7: cut formula)
    for key in "ABCD":
        if key in q["options"]:
            out.append(("text", "%s. %s" % (key, q["options"][key]), "opt:" + key))
    return out


def _formula_pixmap(fitz, text, font):
    """Rasterise one formula line (150 dpi): visible to vision, absent from the text layer."""
    tmp = fitz.open()
    pg = tmp.new_page(width=PAGE_W - 2 * MARGIN, height=LEAD + 6)
    pg.insert_text((2, LEAD - 2), text, fontsize=SIZE, fontname="dj", fontfile=font)
    pix = pg.get_pixmap(dpi=150)
    tmp.close()
    return pix


def render(gold_path, out_pdf, variant="text", font=None, layout="block", furniture=False, gold_out=None):
    """Write OUT.pdf from the gold; return {"pages", "placed": {id: first page}, "pages_of": {id: [pages]},
    "page_lines": {page: [[id, role, text]]}}.

    layout "split": a block may cross the page at a line and a figure goes where it fits (its page replaces
    the gold `figures`); `furniture`: header, footer and page number on every page; `gold_out`: a copy of the
    gold whose records carry `pages` (and the real figure pages for the split layout).
    """
    if variant not in VARIANTS:
        raise ValueError("variant must be one of %s, got %r" % (", ".join(VARIANTS), variant))
    if layout not in LAYOUTS:
        raise ValueError("layout must be one of %s, got %r" % (", ".join(LAYOUTS), layout))
    font = _font(font)
    gold = extract_eval.load_questions(gold_path)
    fitz = optional.load("fitz", "pymupdf")
    width = PAGE_W - 2 * MARGIN
    split = layout == "split"
    doc = fitz.open()
    try:
        page, y, pno, placed = None, 0, 0, {}
        pages_of, page_lines, figs = {}, {}, {}

        def new_page():
            nonlocal page, y, pno
            page, y, pno = doc.new_page(width=PAGE_W, height=PAGE_H), MARGIN, pno + 1
            page_lines[pno] = []
            if furniture:
                page.insert_text((MARGIN, 30), "Đề thi thử - Môn Toán - Mã đề 101", fontsize=9,
                                 fontname="dj", fontfile=font)
                page.insert_text((MARGIN, PAGE_H - 25), "Trang %d" % pno, fontsize=9,
                                 fontname="dj", fontfile=font)

        def put_line(qid, kind, t, role):
            nonlocal y
            if kind == "formula" and variant == "formula-image":
                rect = fitz.Rect(MARGIN, y - LEAD + 4, PAGE_W - MARGIN, y + 6)
                page.insert_image(rect, pixmap=_formula_pixmap(fitz, t, font))
            else:
                page.insert_text((MARGIN, y), t, fontsize=SIZE, fontname="dj", fontfile=font)
            page_lines[pno].append([int(qid), role, t])
            pages_of.setdefault(int(qid), [])
            if pno not in pages_of[int(qid)]:
                pages_of[int(qid)].append(pno)
            y += LEAD

        def put_figure(qid):
            nonlocal y
            x0, y0 = MARGIN, y + 4
            r = fitz.Rect(x0, y0, x0 + FIG_W, y0 + FIG_H)
            page.draw_rect(r, color=(0, 0, 0), width=1)
            page.draw_polyline([(x0 + 5, y0 + FIG_H - 5), (x0 + FIG_W - 5, y0 + FIG_H - 5),
                                (x0 + FIG_W / 2, y0 + 5), (x0 + 5, y0 + FIG_H - 5)],
                               color=(0, 0, 0), width=1)
            y = y0 + FIG_H + 6
            figs[int(qid)] = pno
            if pno not in pages_of[int(qid)]:
                pages_of[int(qid)].append(pno)

        new_page()
        for qid in sorted(gold, key=int):
            q = gold[qid]
            lines = _lines(q)
            for kind, t, _role in lines:
                if kind != "formula" or variant == "text":
                    if _too_wide(fitz, t, font, width):
                        raise ValueError("question %s: line wider than the page: %r" % (qid, t[:40]))
            fig = bool(q["figures"])
            if split:
                for kind, t, role in lines:
                    if y + LEAD > PAGE_H - MARGIN:
                        new_page()
                    if int(qid) not in placed:
                        placed[int(qid)] = pno
                    put_line(qid, kind, t, role)
                if fig:
                    if y + 4 + FIG_H > PAGE_H - MARGIN:
                        new_page()
                    put_figure(qid)
                y += LEAD
                continue
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
            for kind, t, role in lines:
                put_line(qid, kind, t, role)
            if fig:
                put_figure(qid)
            y += LEAD
        try:
            doc.save(out_pdf)
        except Exception as exc:  # fitz raises its own error types for I/O
            raise OSError("cannot write %s: %s" % (out_pdf, exc))
        if gold_out:
            _write_gold(gold_path, gold_out, pages_of, figs if split else None)
        return {"pages": pno, "placed": placed, "pages_of": dict((k, sorted(v)) for k, v in pages_of.items()),
                "page_lines": page_lines}
    finally:
        doc.close()


def _write_gold(gold_path, out, pages_of, figs):
    """Copy of the gold file whose questions carry `pages` (figure pages too when `figs` is given)."""
    with open(gold_path, encoding="utf-8") as fh:
        data = json.load(fh)
    for q in (data["questions"] if isinstance(data, dict) else data):
        qid = int(extract_eval.norm_id(q.get("id", q.get("n"))))
        q["pages"] = sorted(pages_of[qid])
        if figs is not None and qid in figs:
            q["figures"] = [figs[qid]]
    try:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    except OSError as exc:
        raise OSError("cannot write %s: %s" % (out, exc))


def scan_pdf(src_pdf, out_pdf, zoom=2.0):
    """Image-only copy of src_pdf (every page rasterised): no text layer, as a scan."""
    fitz = optional.load("fitz", "pymupdf")
    src, out = fitz.open(src_pdf), fitz.open()
    try:
        for pg in src:
            png = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes("png")
            new = out.new_page(width=pg.rect.width, height=pg.rect.height)
            new.insert_image(new.rect, stream=png)
        out.save(out_pdf)
    except Exception as exc:
        raise OSError("cannot write %s: %s" % (out_pdf, exc))
    finally:
        src.close()
        out.close()


def vision_replies(info):
    """Oracle mock replies (JSON text per page) built from the rendered lines: what a perfect vision
    model would read. A question cut by the page break gets `cut`; its rest is `continues` on the next page."""
    last = dict((q, ps[-1]) for q, ps in info["pages_of"].items())
    out = []
    for p in sorted(info["page_lines"]):
        qs, cont, seen = [], {"text": [], "options": {}}, {}
        for qid, role, t in info["page_lines"][p]:
            if role == "stem0":
                seen[qid] = {"id": qid, "text": [t.split(". ", 1)[1] if ". " in t else t], "options": {}}
                qs.append(seen[qid])
                continue
            tgt = seen.get(qid)
            if role.startswith("opt:"):
                (tgt["options"] if tgt else cont["options"])[role[4:]] = t.split(". ", 1)[1]
            else:
                (tgt["text"] if tgt else cont["text"]).append(t)
        reply = {"questions": [dict(q, text="\n".join(q["text"]), figures=[],
                                    **({"cut": True} if last[q["id"]] > p else {})) for q in qs]}
        if cont["text"] or cont["options"]:
            reply["continues"] = {"text": "\n".join(cont["text"]), "options": cont["options"], "figures": []}
        out.append(json.dumps(reply, ensure_ascii=False))
    return out


def _too_wide(fitz, text, font, width):
    f = fitz.Font(fontfile=font)
    return f.text_length(text, fontsize=SIZE) > width

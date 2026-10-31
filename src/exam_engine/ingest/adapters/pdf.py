"""PDF adapter (PyMuPDF via the optional loader): native text first, OCR only on flagged pages,
crops only where text cannot carry the content. No network, original never written."""
import glob
import hashlib
import os
import unicodedata

from exam_engine.ingest import optional, segment
from exam_engine.ingest.schema import SCHEMA_VERSION, IngestError

CROP_DPI = 150
OCR_DPI = 200
MAX_CROPS = 6
MIN_CHARS = 20
MATH_FONTS = ("math", "cmsy", "cmmi", "cmex", "symbol")
TESSDATA_DIRS = ["/usr/share/tesseract-ocr/*/tessdata", "/usr/local/share/tessdata",
                 "/usr/share/tessdata", "/usr/share/tesseract-ocr/tessdata"]


def _warn(code, msg, page=None, level="warning"):
    w = {"level": level, "code": code, "message": msg}
    if page is not None:
        w["page"] = page
    return w


def tessdata_candidates(config=None):
    """Existing tessdata folders in priority order (config, $TESSDATA_PREFIX, known dirs)."""
    cands = [(config or {}).get("tessdata"), os.environ.get("TESSDATA_PREFIX")]
    for pat in TESSDATA_DIRS:
        cands.extend(sorted(glob.glob(pat)))
    out = []
    for c in cands:
        if not c:
            continue
        for d in (c, os.path.join(c, "tessdata")):
            if os.path.isdir(d) and d not in out:
                out.append(d)
    return out


def _langs(folder):
    return set(os.path.basename(p)[:-len(".traineddata")]
               for p in glob.glob(os.path.join(folder, "*.traineddata")))


def pick_ocr_language(config=None):
    """(folder, 'vie+eng' | 'vie' | 'eng' | None, available wanted langs)."""
    best_dir, best = None, []
    for d in tessdata_candidates(config):
        have = [lg for lg in ("vie", "eng") if lg in _langs(d)]
        if len(have) > len(best):
            best_dir, best = d, have
    return best_dir, ("+".join(best) if best else None), best


def _nfc(s):
    return unicodedata.normalize("NFC", s)


def _page_blocks(page, textpage=None):
    """[(bbox, text, fonts)] of the text blocks of one page, PyMuPDF order."""
    d = page.get_text("dict", textpage=textpage) if textpage else page.get_text("dict")
    out = []
    for b in d.get("blocks", ()):
        if b.get("type") != 0:
            continue
        lines, fonts = [], set()
        for ln in b.get("lines", ()):
            spans = ln.get("spans", ())
            fonts.update(s.get("font", "") for s in spans)
            lines.append("".join(s.get("text", "") for s in spans))
        text = _nfc("\n".join(lines)).strip()
        if text:
            out.append((tuple(round(v, 2) for v in b["bbox"]), text, fonts))
    return out


def _line_blocks(page):
    """Line-level (bbox, text, fonts) items, used when MuPDF merged both columns into one block."""
    out = []
    for b in page.get_text("dict").get("blocks", ()):
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", ()):
            text = _nfc("".join(s.get("text", "") for s in ln.get("spans", ()))).strip()
            if text:
                out.append((tuple(round(v, 2) for v in ln["bbox"]), text,
                            set(s.get("font", "") for s in ln.get("spans", ()))))
    return out


def _merge_column(lines):
    """Merge vertically adjacent lines of one column back into paragraphs."""
    out = []
    for bb, text, fonts in sorted(lines, key=lambda b: b[0][1]):
        if out and bb[1] - out[-1][0][3] < 0.6 * (bb[3] - bb[1]):
            pb = out[-1][0]
            out[-1] = ((min(pb[0], bb[0]), pb[1], max(pb[2], bb[2]), bb[3]),
                       out[-1][1] + "\n" + text, out[-1][2] | fonts)
        else:
            out.append((bb, text, set(fonts)))
    return out


def _inside(box, outer):
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3]


def _overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > 1 and min(a[3], b[3]) - max(a[1], b[1]) > 1


def _order(blocks, width):
    """Conservative reading order; returns (blocks, two_column)."""
    mid = width / 2.0
    left = [b for b in blocks if b[0][2] <= mid]
    right = [b for b in blocks if b[0][0] >= mid]
    if len(left) >= 2 and len(right) >= 2 and len(left) + len(right) == len(blocks):
        return sorted(left, key=lambda b: b[0][1]) + sorted(right, key=lambda b: b[0][1]), True
    return blocks, False


def _order_page(page, blocks, width):
    """_order on blocks; if that fails, retry on lines (MuPDF merges same-baseline columns)."""
    res, two = _order(blocks, width)
    if two or not blocks:
        return res, two
    lines = _line_blocks(page)
    mid = width / 2.0
    if not any(b[0][0] < mid < b[0][2] for b in blocks):
        return res, False
    res2, two2 = _order(lines, width)
    if two2:
        lf = [b for b in res2 if b[0][2] <= mid]
        return _merge_column(lf) + _merge_column(res2[len(lf):]), True
    return res, False


def _suspect(text):
    """Heuristic flags (warnings, not proof) for one page's text."""
    flags = []
    if len(text.strip()) < MIN_CHARS:
        return ["missing_text"]
    bad = sum(1 for c in text if c == "�" or (unicodedata.category(c) == "Cc"
                                                     and c not in "\n\t\r"))
    if bad / float(len(text)) > 0.01:
        flags.append("bad_encoding")
    if not any(c.isalpha() for c in text):
        flags.append("no_letters")
    return flags


def _save_crop(page, rect, folder, rel_dir, name):
    os.makedirs(folder, exist_ok=True)
    full = os.path.join(folder, name)
    page.get_pixmap(clip=rect, dpi=min(CROP_DPI, 200)).save(full)
    with open(full, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    return "/".join([rel_dir, name]), sha


def _rel_dir(folder):
    rel = os.path.relpath(folder).replace(os.sep, "/")
    return os.path.basename(os.path.normpath(folder)) if rel.startswith("..") else rel


def ingest(path, config=None):
    config = config or {}
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise IngestError("corrupt", "cannot read %s: %s" % (path, exc))
    if not raw:
        raise IngestError("empty", "%s has no content" % path)
    fitz = optional.load("fitz", "pymupdf")
    try:
        pdf = fitz.open(stream=raw, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - any parse failure is data
        raise IngestError("corrupt", "cannot open PDF %s: %s" % (os.path.basename(path), exc))
    try:
        return _extract(fitz, pdf, raw, path, config)
    finally:
        pdf.close()


def _extract(fitz, pdf, raw, path, config):
    name = os.path.basename(path)
    if pdf.needs_pass:
        raise IngestError("encrypted", "%s is password protected" % name)
    if pdf.page_count == 0:
        raise IngestError("empty", "%s has no pages" % name)
    sha = hashlib.sha256(raw).hexdigest()
    ocr_mode = config.get("ocr", "auto")
    asset_dir = config.get("asset_dir") or os.path.join("work", "ingest", sha[:8])
    rel_dir = _rel_dir(asset_dir)
    warnings, assets, pages, all_lines = [], [], [], []
    counter = [0]
    tess_dir, lang, have = (None, None, [])
    if ocr_mode != "off":
        tess_dir, lang, have = pick_ocr_language(config)
    lang_warned = False
    any_content = False

    for pno in range(pdf.page_count):
        n = pno + 1
        page = pdf[pno]
        pw, ph = page.rect.width, page.rect.height
        pwarn, items, tables = [], [], []
        try:
            for t in page.find_tables().tables:
                rows = [[_nfc(c or "") for c in r] for r in t.extract()]
                if rows:
                    tables.append((tuple(round(v, 2) for v in t.bbox), rows))
        except Exception:  # noqa: BLE001 - table detection is best effort
            tables = []
        tbbox = [t[0] for t in tables]
        text_blocks = [b for b in _page_blocks(page) if not any(_inside(b[0], t) for t in tbbox)]
        text_blocks, two_col = _order_page(page, text_blocks, pw)
        native_text = "\n".join(b[1] for b in text_blocks)
        fonts = set()
        for b in text_blocks:
            fonts |= b[2]
        try:
            images = [tuple(i["bbox"]) for i in page.get_image_info()]
        except Exception:  # noqa: BLE001
            images = []
        try:
            drawings = page.get_drawings()
        except Exception:  # noqa: BLE001
            drawings = []
        flags = _suspect(native_text)
        method, status = "native", "native_text"
        if not two_col and any(_overlap(a[0], b[0]) for i, a in enumerate(text_blocks)
                               for b in text_blocks[i + 1:]):
            pwarn.append(_warn("reading_order_uncertain", "text blocks overlap", n))
        for f in flags:
            code = "missing_text" if f == "missing_text" else "bad_encoding"
            pwarn.append(_warn(code, "page text suspicious (%s)" % f, n))
        if flags:
            status = "needs_review"
            if ocr_mode == "off":
                pass
            elif not lang:
                pwarn.append(_warn("ocr_unavailable", "no tesseract language data found", n))
            else:
                if len(have) < 2 and not lang_warned:
                    warnings.append(_warn("ocr_language_missing",
                                          "OCR language data missing, using %s" % lang))
                    lang_warned = True
                try:
                    tp = page.get_textpage_ocr(language=lang, dpi=OCR_DPI, full=True,
                                               tessdata=tess_dir)
                    ocr_blocks = [b for b in _page_blocks(page, tp)
                                  if not any(_inside(b[0], t) for t in tbbox)]
                    ocr_text = "\n".join(b[1] for b in ocr_blocks)
                    if len(ocr_text.strip()) >= MIN_CHARS and len(ocr_text) > len(native_text):
                        text_blocks, method = ocr_blocks, "ocr"
                        native_text = ocr_text
                        status = "needs_review" if _suspect(ocr_text) else "ocr"
                except Exception as exc:  # noqa: BLE001 - OCR failure is data
                    pwarn.append(_warn("ocr_unavailable", "OCR failed: %s" % exc, n))
        extra = {"method": "ocr"} if method == "ocr" else {}
        for b in text_blocks:
            items.append(("paragraph", b[0], b[1], dict(extra)))
        for bbox, rows in tables:
            tx = "\n".join(" | ".join(r) for r in rows)
            pos = next((i for i, it in enumerate(items) if it[1][1] > bbox[1]), len(items))
            items.insert(pos, ("table", bbox, tx, {"rows": rows}))
        # visual preservation
        crops = []
        for bb in images:
            whole = (bb[2] - bb[0]) * (bb[3] - bb[1]) >= 0.9 * pw * ph
            if not (whole and method == "ocr"):  # OCR text already carries a scanned page
                crops.append(tuple(bb))
        try:
            clusters = page.cluster_drawings(drawings=drawings) if drawings else []
        except Exception:  # noqa: BLE001
            clusters = []
        for c in clusters:
            c = tuple(c)
            if (c[2] - c[0] >= 30 and c[3] - c[1] >= 30
                    and not any(_inside(c, t) for t in tbbox)):
                crops.append(c)
        if len(crops) > MAX_CROPS:
            pwarn.append(_warn("crops_capped", "more than %d visuals; kept first" % MAX_CROPS, n))
            crops = crops[:MAX_CROPS]
        jobs = [(c, "p%d_v%d.png" % (n, i + 1)) for i, c in enumerate(crops)]
        if any(m in f.lower() for f in fonts for m in MATH_FONTS):
            pwarn.append(_warn("math_possible", "math fonts on page; page image kept", n))
            jobs.append((None, "p%d_page.png" % n))
        for c, fname in jobs:
            rect = (fitz.Rect(c) if c else fitz.Rect(page.rect)) & page.rect
            if rect.is_empty:
                continue
            rel, h = _save_crop(page, rect, asset_dir, rel_dir, fname)
            aid = "a%d" % (len(assets) + 1)
            bbox = [round(v, 2) for v in tuple(rect)]
            assets.append({"id": aid, "path": rel, "mime": "image/png", "sha256": h,
                           "page": n, "bbox": bbox})
            pos = next((i for i, it in enumerate(items) if it[1][1] > bbox[1]), len(items))
            items.insert(pos, ("image", tuple(bbox), "", {"asset": aid}))
        blocks = []
        for kind, bbox, text, ex in items:
            counter[0] += 1
            blk = {"id": "b%d" % counter[0], "order": len(blocks), "type": kind, "text": text,
                   "level": None, "bbox": list(bbox), "origin": "extracted", "asset": None}
            blk.update(ex)
            blocks.append(blk)
        if native_text.strip() or images or drawings:
            any_content = True
        for kind, _bb, text, _ex in items:
            if kind == "paragraph":
                all_lines.extend(text.split("\n"))
        pages.append({"n": n, "width": round(pw, 2), "height": round(ph, 2), "blocks": blocks,
                      "chars": len(native_text.strip()), "images": len(images),
                      "drawings": len(drawings), "status": status, "method": method,
                      "warnings": pwarn})
        warnings.extend(pwarn)
    if not any_content:
        raise IngestError("empty", "%s has no text and no images" % name)
    intro, qs, ok = segment.segment(all_lines)
    keep = ok
    if not qs:
        warnings.append(_warn("no_question_numbering", "no question numbering found"))
    elif ok:
        pass
    elif segment.numbering(qs)["usable"]:
        keep = True
        warnings.extend(_warn(c, m) for c, m in segment.numbering_warnings(qs))
    else:
        warnings.append(_warn("segmentation_skipped",
                              "question numbering not consecutive or a question has no text"))
        warnings.extend(_warn(c, m) for c, m in segment.numbering_warnings(qs))
    sts = [p["status"] for p in pages]
    if "needs_review" in sts:
        status = "needs_review"
    elif all(s == "ocr" for s in sts):
        status = "ocr"
    elif "ocr" in sts:
        status = "mixed"
    else:
        status = "native_text"
    doc = {"schema_version": SCHEMA_VERSION, "status": status,
           "extraction": {"method": "pdf", "tool": "pymupdf %s" % fitz.VersionBind,
                          "ocr": ocr_mode},
           "meta": {}, "pages": pages, "assets": assets, "warnings": warnings,
           "source": {"path": name, "name": name, "format": "pdf", "sha256": sha,
                      "size": len(raw)}}
    if keep:
        doc["questions"] = qs
        doc["intro"] = "\n".join(intro).strip()
    return doc

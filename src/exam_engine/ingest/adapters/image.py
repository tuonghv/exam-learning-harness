"""Image adapter (PNG/JPEG/WEBP): one page holding the image as a visual asset.

The original bytes are never changed; header parsing is stdlib only. An image above
`max_image_bytes` gets a resized derived asset (lazy PIL) next to the original, never a silent
drop. OCR is opt-in (config ocr == "on") and only adds an extracted text block.
"""
import hashlib
import io
import math
import os
import struct

from exam_engine.ingest import optional
from exam_engine.ingest.adapters import pdf
from exam_engine.ingest.schema import SCHEMA_VERSION, IngestError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MIME = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}
_EXT_FMT = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _warn(code, msg, page=None):
    w = {"level": "warning", "code": code, "message": msg}
    if page is not None:
        w["page"] = page
    return w


def sniff(raw):
    """Image format from the magic bytes, else None."""
    if raw.startswith(PNG_MAGIC):
        return "png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return None


def _png_size(raw):
    if len(raw) < 33 or raw[12:16] != b"IHDR" or raw[-12:-8] != b"\x00\x00\x00\x00" \
            or raw[-8:-4] != b"IEND":
        return None
    return struct.unpack(">II", raw[16:24])


def _jpeg_size(raw):
    if not raw.rstrip(b"\x00").endswith(b"\xff\xd9"):
        return None
    i, n = 2, len(raw)
    while i + 4 <= n:
        if raw[i] != 0xFF:
            return None
        marker = raw[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seglen = struct.unpack(">H", raw[i + 2:i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if i + 9 > n:
                return None
            h, w = struct.unpack(">HH", raw[i + 5:i + 9])
            return w, h
        i += 2 + seglen
    return None


def _webp_size(raw):
    if len(raw) < 30 or struct.unpack("<I", raw[4:8])[0] + 8 > len(raw):
        return None
    kind = raw[12:16]
    if kind == b"VP8 " and raw[23:26] == b"\x9d\x01\x2a":
        w, h = struct.unpack("<HH", raw[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if kind == b"VP8L" and raw[20:21] == b"\x2f":
        bits = struct.unpack("<I", raw[21:25])[0]
        return 1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF)
    if kind == b"VP8X":
        return (1 + int.from_bytes(raw[24:27], "little"),
                1 + int.from_bytes(raw[27:30], "little"))
    return None


_SIZERS = {"png": _png_size, "jpeg": _jpeg_size, "webp": _webp_size}


def _shrink(raw, fmt, limit):
    """Resized copy of `raw` (same format) of at most `limit` bytes, via lazy PIL."""
    pil = optional.load("PIL.Image", "pillow")
    try:
        img = pil.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:  # noqa: BLE001 - any decode failure is data
        raise IngestError("corrupt", "cannot decode image: %s" % exc)
    if fmt == "jpeg" and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    scale = math.sqrt(float(limit) / len(raw)) * 0.9
    opts = {"optimize": True} if fmt == "png" else {"quality": 85}
    for _ in range(8):
        w, h = max(1, int(img.width * scale)), max(1, int(img.height * scale))
        buf = io.BytesIO()
        img.resize((w, h)).save(buf, format=fmt.upper(), **opts)
        if buf.tell() <= limit or (w == 1 and h == 1):
            return buf.getvalue()
        scale *= 0.8
    raise IngestError("corrupt", "cannot shrink image below %d bytes" % limit)


def _ocr(raw, fmt, config):
    """(text, None) or (None, reason) via PyMuPDF's tesseract bridge (no process started here)."""
    tess_dir, lang, _ = pdf.pick_ocr_language(config)
    if not lang:
        return None, "no tesseract language data found"
    try:
        fitz = optional.load("fitz", "pymupdf")
        doc = fitz.open(stream=raw, filetype=fmt)
        try:
            tp = doc[0].get_textpage_ocr(language=lang, dpi=pdf.OCR_DPI, full=True,
                                         tessdata=tess_dir)
            return doc[0].get_text(textpage=tp).strip(), None
        finally:
            doc.close()
    except Exception as exc:  # noqa: BLE001 - OCR failure is data
        return None, "OCR failed: %s" % exc


def _store(folder, rel_dir, fname, blob):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, fname), "wb") as fh:
        fh.write(blob)
    return "/".join([rel_dir, fname])


def ingest(path, config=None):
    config = config or {}
    name = os.path.basename(path)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise IngestError("corrupt", "cannot read %s: %s" % (path, exc))
    if not raw:
        raise IngestError("empty", "%s has no content" % name)
    ext = os.path.splitext(name)[1].lower()
    fmt = sniff(raw)
    if fmt is None:
        raise IngestError("corrupt", "%s is not a PNG, JPEG or WEBP image" % name)
    if _EXT_FMT.get(ext) != fmt:
        raise IngestError("format_mismatch", "%s has extension %s but holds %s data"
                          % (name, ext, fmt))
    size = _SIZERS[fmt](raw)
    if not size or size[0] < 1 or size[1] < 1:
        raise IngestError("corrupt", "%s is truncated or has an unreadable header" % name)
    width, height = size
    sha = hashlib.sha256(raw).hexdigest()
    limit = int(config.get("max_image_bytes") or MAX_IMAGE_BYTES)
    folder = config.get("asset_dir")
    warnings, assets = [], []
    if folder:
        rel_dir = pdf._rel_dir(folder)
        ref = _store(folder, rel_dir, name, raw)
    else:
        rel_dir, ref = None, name  # source reference, nothing copied
    assets.append({"id": "a1", "path": ref, "mime": MIME[fmt], "sha256": sha,
                   "page": 1, "bbox": None, "origin": "source"})
    if len(raw) > limit:
        small = _shrink(raw, fmt, limit)  # missing_dependency without PIL
        if not folder:
            folder = os.path.join("work", "ingest", sha[:8])
            rel_dir = pdf._rel_dir(folder)
        dname = "%s.small%s" % (os.path.splitext(name)[0], ext)
        assets.append({"id": "a2", "path": _store(folder, rel_dir, dname, small),
                       "mime": MIME[fmt], "sha256": hashlib.sha256(small).hexdigest(),
                       "page": 1, "bbox": None, "origin": "normalized", "derived_from": "a1"})
        warnings.append(_warn("image_resized", "%d bytes > %d: resized copy a2 added, original "
                              "kept as a1" % (len(raw), limit), 1))
    blocks = [{"id": "b1", "order": 0, "type": "image", "text": "", "level": None,
               "bbox": None, "origin": "source", "asset": "a1"}]
    ocr_mode = config.get("ocr", "off")
    if ocr_mode == "on":
        text, why = _ocr(raw, fmt, config)
        if text:
            blocks.append({"id": "b2", "order": 1, "type": "paragraph", "text": text,
                           "level": None, "bbox": None, "origin": "extracted", "asset": None})
        else:
            warnings.append(_warn("ocr_unavailable", why or "OCR found no text", 1))
    if len(blocks) == 1:
        warnings.append(_warn("image_only", "image without text; it goes to the solver as a "
                              "visual (OCR is off or found nothing)", 1))
    return {"schema_version": SCHEMA_VERSION, "status": "needs_review",
            "extraction": {"method": "image", "tool": "stdlib header parse",
                           "ocr": "on" if ocr_mode == "on" else "off"},
            "meta": {},
            "pages": [{"n": 1, "width": width, "height": height, "blocks": blocks,
                       "chars": sum(len(b["text"]) for b in blocks),
                       "status": "needs_review", "method": "image", "warnings": warnings[:]}],
            "assets": assets, "warnings": warnings,
            "source": {"path": name, "name": name, "format": ext.lstrip("."),
                       "sha256": sha, "size": len(raw)}}


def ingest_sequence(paths, config=None):
    """One document from several image files: file k = page k, in the given order (source format
    `image_seq`; per-file name + sha256 under source.files). Tiles of one tall image are such a
    sequence. Each file goes through `ingest` (OCR, resize); ids are made unique per page."""
    if not paths:
        raise IngestError("empty", "no image files given")
    docs = [ingest(p, config) for p in paths]
    pages, assets, warnings, files = [], [], [], []
    for k, d in enumerate(docs, 1):
        amap = dict((a["id"], "a%d_%s" % (k, a["id"][1:])) for a in d["assets"])
        page = d["pages"][0]
        blocks = [dict(b, id="p%d%s" % (k, b["id"]), asset=amap.get(b.get("asset")))
                  for b in page["blocks"]]
        warns = [dict(w, page=k) for w in d["warnings"]]
        pages.append(dict(page, n=k, blocks=blocks, warnings=warns[:]))
        assets += [dict(a, id=amap[a["id"]], page=k,
                        **({"derived_from": amap[a["derived_from"]]} if "derived_from" in a
                           else {})) for a in d["assets"]]
        warnings += warns
        s = d["source"]
        files.append({"name": s["name"], "sha256": s["sha256"], "size": s["size"]})
    names = [f["name"] for f in files]
    joined = "\n".join(f["sha256"] for f in files)
    return {"schema_version": SCHEMA_VERSION, "status": "needs_review",
            "extraction": dict(docs[0]["extraction"]), "meta": {},
            "pages": pages, "assets": assets, "warnings": warnings,
            "source": {"path": names[0], "name": names[0], "format": "image_seq",
                       "sha256": hashlib.sha256(joined.encode("ascii")).hexdigest(),
                       "size": sum(f["size"] for f in files), "files": files}}


def render(paths, n, limit=MAX_IMAGE_BYTES):
    """PNG bytes of file n (1-based) of `paths` for a vision call: a JPEG/WEBP is re-encoded as PNG,
    anything above `limit` is shrunk (lazy PIL); a small PNG is returned as it is."""
    if not 1 <= n <= len(paths):
        raise IngestError("invalid_pages", "file %d not in the sequence of %d" % (n, len(paths)))
    try:
        with open(paths[n - 1], "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise IngestError("corrupt", "cannot read %s: %s" % (paths[n - 1], exc))
    fmt = sniff(raw)
    if fmt is None:
        raise IngestError("corrupt", "%s is not a PNG, JPEG or WEBP image" % paths[n - 1])
    if fmt != "png":
        pil = optional.load("PIL.Image", "pillow")
        buf = io.BytesIO()
        pil.open(io.BytesIO(raw)).convert("RGB").save(buf, format="PNG")
        raw = buf.getvalue()
    return _shrink(raw, "png", limit) if len(raw) > limit else raw

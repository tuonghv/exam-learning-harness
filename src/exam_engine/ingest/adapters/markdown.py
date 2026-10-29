"""Markdown adapter: UTF-8 file -> canonical blocks in file order (one logical page)."""
import hashlib
import mimetypes
import os
import re

from exam_engine.ingest.schema import SCHEMA_VERSION, IngestError

_HEAD = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)$")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_FENCE = re.compile(r"^\s*(```|~~~)")
_PARENT = ".."


def _resolve(base, ref):
    """Real path of a local image ref, only inside `base`; raises IngestError."""
    if os.path.isabs(ref) or ref.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", ref):
        raise IngestError("invalid_document", "absolute image path not allowed: %s" % ref)
    if _PARENT in re.split(r"[\\/]+", ref):
        raise IngestError("invalid_document", "image path escapes the folder: %s" % ref)
    root = os.path.realpath(base)
    real = os.path.realpath(os.path.join(root, ref))
    if os.path.commonpath([root, real]) != root:
        raise IngestError("invalid_document", "image path escapes the folder: %s" % ref)
    if not os.path.isfile(real):
        raise IngestError("missing_asset", "image not found: %s" % ref)
    return real


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_source(path):
    """Decoded UTF-8 text of a source file; IngestError decode/empty/corrupt."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise IngestError("corrupt", "cannot read %s: %s" % (path, exc))
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngestError("decode", "%s is not valid UTF-8: %s" % (path, exc))
    if not text.strip():
        raise IngestError("empty", "%s has no content" % path)
    return text


def _para_end(lines, i, kind):
    j = i + 1
    while j < len(lines):
        ln = lines[j]
        s = ln.strip()
        if not s or _HEAD.match(ln) or _FENCE.match(ln) or s.startswith("$$") or _IMAGE.match(s):
            break
        if kind == "table" and not s.startswith("|"):
            break
        if kind == "list" and not (_LIST.match(ln) or ln.startswith(" ")):
            break
        if kind == "paragraph" and (_LIST.match(ln) or s.startswith("|")):
            break
        j += 1
    return j


def ingest(path, config=None):
    text = read_source(path)
    base = os.path.dirname(os.path.abspath(path))
    blocks, assets = [], []

    def add(btype, body, level=None, asset=None):
        blocks.append({"id": "b%d" % (len(blocks) + 1), "order": len(blocks), "type": btype,
                       "text": body, "level": level, "bbox": None, "origin": "source",
                       "asset": asset})

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        fence = _FENCE.match(line)
        head = _HEAD.match(line)
        img = _IMAGE.match(s)
        if not s:
            i += 1
        elif fence:
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith(fence.group(1)):
                j += 1
            add("code", "\n".join(lines[i:j + 1]))
            i = j + 1
        elif s.startswith("$$"):
            j = i
            if not (s.endswith("$$") and len(s) > 2):
                j = i + 1
                while j < len(lines) and "$$" not in lines[j]:
                    j += 1
            add("math", "\n".join(lines[i:j + 1]))
            i = j + 1
        elif head:
            add("heading", head.group(2), level=len(head.group(1)))
            i += 1
        elif img and not _SCHEME.match(img.group(2)):
            ref = img.group(2)
            real = _resolve(base, ref)
            aid = "a%d" % (len(assets) + 1)
            assets.append({"id": aid, "path": ref, "page": 1, "bbox": None,
                           "mime": mimetypes.guess_type(real)[0] or "application/octet-stream",
                           "sha256": _sha(real)})
            add("image", s, asset=aid)
            i += 1
        else:
            kind = ("list" if _LIST.match(line) else
                    "table" if s.startswith("|") else "paragraph")
            j = _para_end(lines, i, kind)
            add(kind, "\n".join(lines[i:j]))
            i = j
    return {"schema_version": SCHEMA_VERSION, "source": {}, "status": "native_text",
            "extraction": {"method": "markdown", "tool": "builtin"}, "meta": {},
            "pages": [{"n": 1, "width": None, "height": None, "blocks": blocks}],
            "assets": assets, "warnings": []}

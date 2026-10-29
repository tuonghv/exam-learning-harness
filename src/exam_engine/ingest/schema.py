"""Canonical ingest document v1: validation and the structured error (Python 3.8 stdlib only)."""
from exam_engine.core.schema import validate

SCHEMA_VERSION = "1"
CODES = ("unsupported_format", "empty", "decode", "missing_asset", "missing_dependency",
         "invalid_document", "corrupt", "missing_header")
STATUSES = ["native_text", "ocr", "mixed", "needs_review"]
BLOCK_TYPES = ["heading", "paragraph", "list", "table", "code", "math", "image"]
ORIGINS = ["source", "extracted", "normalized", "ai"]

_BLOCK = {"type": "object", "required": ["id", "order", "type", "text", "origin"],
          "properties": {"id": {"type": "string"}, "order": {"type": "integer"},
                         "type": {"enum": BLOCK_TYPES}, "text": {"type": "string"},
                         "level": {"type": ["integer", "null"]},
                         "bbox": {"type": ["array", "null"]},
                         "origin": {"enum": ORIGINS},
                         "asset": {"type": ["string", "null"]}}}
_PAGE = {"type": "object", "required": ["n", "blocks"],
         "properties": {"n": {"type": "integer", "minimum": 1},
                        "blocks": {"type": "array", "items": _BLOCK}}}
_ASSET = {"type": "object", "required": ["id", "path", "mime", "sha256"],
          "properties": {"id": {"type": "string"}, "path": {"type": "string"},
                         "mime": {"type": "string"}, "sha256": {"type": "string"}}}
DOCUMENT = {
    "type": "object",
    "required": ["schema_version", "source", "status", "extraction", "meta", "pages",
                 "assets", "warnings"],
    "properties": {
        "schema_version": {"enum": [SCHEMA_VERSION]},
        "source": {"type": "object", "required": ["path", "name", "format", "sha256", "size"]},
        "status": {"enum": STATUSES},
        "extraction": {"type": "object", "required": ["method", "tool"]},
        "meta": {"type": "object"},
        "pages": {"type": "array", "items": _PAGE},
        "assets": {"type": "array", "items": _ASSET},
        "questions": {"type": "array"},
        "warnings": {"type": "array", "items": {"type": "object",
                                                "required": ["level", "code", "message"]}},
    },
}


class IngestError(Exception):
    """Structured ingest failure: `code` is one of CODES."""

    def __init__(self, code, message):
        Exception.__init__(self, "%s: %s" % (code, message))
        self.code = code
        self.message = message


def validate_document(doc):
    """Problems of a canonical document as a list of strings (empty = valid); never raises."""
    errs = validate(doc, DOCUMENT)
    if errs or not isinstance(doc, dict):
        return errs
    assets = set(a["id"] for a in doc["assets"] if isinstance(a, dict) and "id" in a)
    seen = set()
    for page in doc["pages"]:
        for blk in page.get("blocks", ()):
            if not isinstance(blk, dict) or "id" not in blk:
                continue
            if blk["id"] in seen:
                errs.append("duplicate block id %s" % blk["id"])
            seen.add(blk["id"])
            if blk.get("asset") and blk["asset"] not in assets:
                errs.append("block %s: asset %s not in assets" % (blk["id"], blk["asset"]))
    return errs

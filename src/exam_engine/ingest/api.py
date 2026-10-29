"""Ingestion boundary: ingest_document(path) -> validated canonical doc; to_exam_text(doc)."""
import hashlib
import os

from exam_engine.ingest import adapters
from exam_engine.ingest.adapters.markdown import read_source
from exam_engine.ingest.schema import IngestError, validate_document
from exam_engine.pipeline import parser

REQUIRED = ("Subject", "Level", "Exam type", "Task", "Mode")


def ingest_document(path, config=None, meta=None):
    ext = os.path.splitext(path)[1].lower()
    fn = adapters.get(ext)
    if fn is None:
        raise IngestError("unsupported_format", "%r not supported (have: %s)"
                          % (ext or path, ", ".join(adapters.extensions())))
    doc = fn(path, config)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise IngestError("corrupt", "cannot read %s: %s" % (path, exc))
    doc["source"] = {"path": os.path.abspath(path), "name": os.path.basename(path),
                     "format": ext.lstrip("."), "sha256": hashlib.sha256(raw).hexdigest(),
                     "size": len(raw)}
    fields = parser.header_fields(raw.decode("utf-8")) if ext == ".md" else {}
    fields.update(meta or {})
    doc["meta"] = fields
    errs = validate_document(doc)
    if errs:
        raise IngestError("invalid_document", "; ".join(errs[:5]))
    return doc


def _is_exam_format(text):
    fields = parser.header_fields(text)
    return all(fields.get(k) for k in REQUIRED) and bool(parser.sections(text, 2))


def to_exam_text(doc):
    """Exam file text for `solve`: an exam-format Markdown source is returned unchanged."""
    src = doc["source"]
    if src.get("format") == "md":
        text = read_source(src["path"])
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != src["sha256"]:
            raise IngestError("corrupt", "source changed since ingest: %s" % src["path"])
        if _is_exam_format(text):
            return text
    meta = doc.get("meta") or {}
    missing = [k for k in REQUIRED if not meta.get(k)]
    if missing:
        raise IngestError("missing_header", "missing exam header(s): %s (use --meta K=V)"
                          % ", ".join(missing))
    out = ["# Exam Input", ""]
    out += ["%s: %s" % (k, v) for k, v in meta.items()]
    out.append("")
    for page in doc["pages"]:
        for blk in page["blocks"]:
            if blk["type"] == "heading":
                out.append("%s %s" % ("#" * (blk.get("level") or 2), blk["text"]))
            else:
                out.append(blk["text"])
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"

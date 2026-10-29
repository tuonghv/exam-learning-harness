"""Adapter registry by file extension; each adapter is fn(path, config) -> canonical doc.

Adapters with optional dependencies import them lazily and raise
IngestError("missing_dependency", "pip install <pkg>").
"""
from exam_engine.ingest.adapters import docx, markdown, pdf

_REGISTRY = {".docx": docx.ingest, ".md": markdown.ingest, ".pdf": pdf.ingest}


def register(ext, fn):
    _REGISTRY[ext.lower()] = fn


def get(ext):
    return _REGISTRY.get(ext.lower())


def extensions():
    return sorted(_REGISTRY)

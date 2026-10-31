"""Pure check: does a question text refer to a paragraph or figure/table it does not contain?

No model, no key, no IO. Heuristic: a miss is a false negative, never a claim of correctness.
"""
import re

_PAR_VI = re.compile(r"\bđoạn(?:\s+(?:văn|thơ|trích))?\s*(?:(\()(\d{1,2})\)|(?<=\s)(\d{1,2})\b)", re.I)
_PAR_EN = re.compile(r"\bparagraph\s*(?:(\()(\d{1,2})\)?|(\d{1,2})\b)", re.I)
_MARKER = re.compile(r"(?m)^[\s\"“”'‘’*_\-\[]*\((\d{1,2})\)\s")
_FIG = re.compile(
    r"\b(?:hình|bảng|biểu đồ|đồ thị|sơ đồ)(?:\s+vẽ)?\s+(?:bên|dưới|trên|sau|\d+)\b"
    r"|\bbảng số liệu\b"
    r"|\b(?:figure|table|chart|graph|diagram)\s+(?:above|below|\d+)\b"
    r"|\b(?:following|above|below)\s+(?:figure|table|chart|graph|diagram)\b", re.I)
_FIG_PRESENT = re.compile(r"(?m)^\[Figure/table:|^\s*\|.*\|")


def _refs(text):
    out = []
    for rx in (_PAR_VI, _PAR_EN):
        for m in rx.finditer(text):
            n = m.group(2) or m.group(3)
            out.append((int(n), bool(m.group(1))))
    return out


def has_figure(text):
    return bool(_FIG_PRESENT.search(text or ""))


def referenced_parts(text, shared_figure=False):
    """-> missing references like ["paragraph (5)", "figure/table"]; [] = nothing missing."""
    text = text or ""
    markers = {int(n) for n in _MARKER.findall(text)}
    out = []
    for n, paren in _refs(text):
        if (n not in markers if markers else paren) and "paragraph (%d)" % n not in out:
            out.append("paragraph (%d)" % n)
    if _FIG.search(text) and not shared_figure and not has_figure(text):
        out.append("figure/table")
    return out


def _first_line(text):
    for ln in (text or "").split("\n"):
        if ln.strip():
            return ln.strip()
    return None


def missing_by_question(texts):
    """Per text, as referenced_parts; a figure on any text with the same first line (a passage
    repeated with every question of its group) counts for all of them."""
    with_fig = {_first_line(t) for t in texts if has_figure(t)} - {None}
    return [referenced_parts(t, shared_figure=_first_line(t) in with_fig) for t in texts]

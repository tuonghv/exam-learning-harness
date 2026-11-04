"""Pure check: does a question text refer to a paragraph or figure/table it does not contain?

No model, no key, no IO. Heuristic: a miss is a false negative, never a claim of correctness.
"""
import re
import unicodedata

from ..ingest.segment import _Q
from ..utils import langtable

_PAR_VI = re.compile(r"\bđoạn(?:\s+(?:văn|thơ|trích))?\s*(?:(\()(\d{1,2})\)|(?<=\s)(\d{1,2})\b)", re.I)
_PAR_EN = re.compile(r"\bparagraph\s*(?:(\()(\d{1,2})\)?|(\d{1,2})\b)", re.I)
_MARKER = re.compile(r"(?m)^[ \t\"“”'‘’*_\-\[]*\((\d{1,2})\)\s")
_FIG_BASE = (
    r"\b(?:hình|bảng|biểu đồ|đồ thị|sơ đồ)(?:\s+vẽ)?\s+(?:bên|dưới|trên|sau|\d+)\b"
    r"|\bbảng số liệu\b"
    r"|\b(?:figure|table|chart|graph|diagram)\s+(?:above|below|\d+)\b"
    r"|\b(?:following|above|below)\s+(?:figure|table|chart|graph|diagram)\b")
_FIG_PRESENT = re.compile(r"(?m)^\[Figure/table:|^\s*\|.*\|")


def _refs(text):
    out = []
    for rx in (_PAR_VI, _PAR_EN) + _PAR_X:
        for m in rx.finditer(text):
            n = m.group(2) or m.group(3)
            out.append((int(n), bool(m.group(1))))
    return out


def has_figure(text):
    return bool(_FIG_PRESENT.search(text or ""))


def referenced_parts(text, shared_figure=False):
    """-> missing references like ["paragraph (5)", "figure/table"]; [] = nothing missing."""
    text = unicodedata.normalize("NFC", text or "")
    markers = {int(n) for n in _MARKER.findall(text)}
    out = []
    for n, paren in _refs(text):
        if (n not in markers if markers else paren) and "paragraph (%d)" % n not in out:
            out.append("paragraph (%d)" % n)
    if _FIG.search(text) and not shared_figure and not has_figure(text):
        out.append("figure/table")
    return out


_STRUCT = re.compile(r"(Source pages:|#{1,6}\s)")


def _first_line(text):
    for ln in unicodedata.normalize("NFC", text or "").split("\n"):
        if ln.strip() and not _STRUCT.match(ln.strip()):  # the page-span line and section heads are no group key
            return ln.strip()
    return None


def _shared_figure_flags(texts):
    """True per text whose first line is shared with a text that holds a figure."""
    with_fig = {_first_line(t) for t in texts if has_figure(t)} - {None}
    return [_first_line(t) in with_fig for t in texts]


def missing_by_question(texts):
    """Per text, as referenced_parts; a figure on any text with the same first line (a passage
    repeated with every question of its group) counts for all of them."""
    return [referenced_parts(t, shared_figure=s)
            for t, s in zip(texts, _shared_figure_flags(texts))]


def _option_keys(options):
    if isinstance(options, dict):
        return set(options)
    return {o.get("key") for o in options or ()}


_OPEN, _CLOSE = "([{", ")]}"
_TRAIL = "=+-×÷/^\\"
_ENUM = re.compile(r"(?m)^[ \t]*(?:[A-Za-z]|\d{1,2}|[ivxIVX]+)\)")
_OPT_LINE = re.compile(r"(?m)^\s*A\s*[.)]\s")


def _option_texts(options):
    if isinstance(options, dict):
        return [str(v) for v in options.values()]
    return [str(o.get("text") or "") for o in options or ()]


def _unbalanced(q):
    """Brackets counted together ([a;b) stays balanced), or an odd number of unescaped `$`."""
    t = "\n".join([q.get("text") or ""] + _option_texts(q.get("options")))
    t = _ENUM.sub("", t)  # a line-start `a)` / `1)` / `iv)` marker closes nothing
    if sum(map(t.count, _OPEN)) != sum(map(t.count, _CLOSE)):
        return True
    return len(re.findall(r"(?<!\\)\$", t)) % 2 == 1


def _merge_suspect(q):
    """Another question's number starts a line of the stem, or the stem holds two A-D option runs.
    Limit: a numbered sub-list inside a stem that uses the question-number form matches too."""
    text = q.get("text") or ""
    own = str(q.get("id") if q.get("id") is not None else q.get("n", ""))
    for ln in text.split("\n"):
        m = _Q.match(ln)
        if m and (m.group(1) or m.group(2)) != own and (m.group(1) or "").strip():
            return True
    return len(_OPT_LINE.findall(text)) >= 2


def incomplete_reasons(q, shared_figure=False, text=None, last_on_page=False):
    """Structural signs that a question is not whole -> reasons ([] = complete).

    `q`: text, options (dict or [{key,text}]), cut, continued_pages, orphan_page, unreadable; `text`
    overrides q["text"] for the referenced-part check (context and figure lines included);
    `last_on_page`: no later question on its page (formula/operator checks run only for those,
    cut or continued questions: a mid-page unbalanced bracket is usually the exam's own math)."""
    out = []
    if 0 < len(_option_keys(q.get("options")) & set("ABCD")) < 4:
        out.append("options_incomplete")
    if q.get("cut") and not q.get("continued_pages"):
        out.append("cut_unresolved")
    out += ["referenced_part_missing " + x
            for x in referenced_parts(q.get("text") if text is None else text, shared_figure)]
    if q.get("orphan_page"):
        out.append("orphan_on_page %s" % q["orphan_page"])
    if q.get("unreadable"):
        out.append("unreadable")
    if q.get("cut") or q.get("continued_pages") or last_on_page:
        if _unbalanced(q):
            out.append("formula_unbalanced")
        if (q.get("text") or "").rstrip()[-1:] in tuple(_TRAIL) and not _option_keys(q.get("options")):
            out.append("trailing_operator")
    if _merge_suspect(q):
        out.append("merge_suspect")
    out += ["ocr_doubt " + k for k in q.get("ocr_doubt") or ()]
    return out


def incomplete_by_question(qs, texts):
    """incomplete_reasons per question; `texts[i]` = full text of qs[i] (shared figures as above)."""
    pages = [q.get("page") for q in qs]
    last = [i + 1 == len(qs) or pages[i] != pages[i + 1] for i in range(len(qs))]
    return [incomplete_reasons(q, s, t, bool(pages[i]) and last[i])
            for i, (q, t, s) in enumerate(zip(qs, texts, _shared_figure_flags(texts)))]


_MARKER_LINE = re.compile(r"(?m)^\[Incomplete: missing_text ([^\]\n]*)\]\s*$")


def marker(reasons):
    """The exam-text line that makes the engine decline the question (never sent to the solver)."""
    return "[Incomplete: missing_text %s]" % ", ".join(reasons)


def marker_reasons(text):
    """Reasons string of the marker line in `text`, or None."""
    m = _MARKER_LINE.search(text or "")
    return m.group(1) if m else None


_NEEDS_BASE = (
    r"(?i)\bread\s+(?:the\s+)?(?:following\s+)?(?:passage|text)|đọc\s+(?:đoạn|bài|văn bản)"
    r"|bảng số liệu sau|use the following data|dữ kiện sau")


def build(table):
    """-> (extra paragraph regexes, _FIG, _NEEDS_TEXT): the vi+en literals plus the extra words."""
    par = langtable.words("paragraph", table)
    pars = (re.compile(r"\b(?:" + "|".join(par) + r")\s*(?:(\()(\d{1,2})\)?|(\d{1,2})\b)", re.I),) if par else ()

    def more(slot):
        ws = langtable.words(slot, table)
        return r"|\b(?:" + "|".join(ws) + r")\b" if ws else ""
    return pars, re.compile(_FIG_BASE + more("figure"), re.I), re.compile(_NEEDS_BASE + more("needs_text"))


_PAR_X, _FIG, _NEEDS_TEXT = build(langtable.load())


_SENT = re.compile(r"[.!?。]+(?:\s|$)")


def has_own_text(q):
    """The stem itself carries the passage (options excluded): >= 200 chars or >= 3 sentences."""
    stem = (q.get("stem") or "").strip()
    return len(stem) >= 200 or len(_SENT.findall(stem)) >= 3


def missing_group_parts(exam, groups, deps):
    """{id: [reasons]} of questions whose group context is cut: a dependency (`deps`: id -> ids) on a
    question not in the file -> `question N`; a passage-asking instruction with no passage -> `passage`.
    Uncertain links are not decided here (exam_warnings)."""
    known = {q["id"] for q in exam["questions"]}
    out = {}
    for i, refs in deps.items():
        for r in refs:
            if r not in known:
                out.setdefault(i, []).append("question %d" % r)
    if not exam.get("passage"):
        for g in groups:
            if g["instruction"] and not g["passage"] and _NEEDS_TEXT.search(g["instruction"]):
                for q in exam["questions"]:
                    if (q["id"] in g["ids"] and (q.get("instruction") or "") == g["instruction"]
                            and not has_own_text(q)):
                        out.setdefault(q["id"], []).append("passage")
    return out

"""Optional AI refine stage (REQ-0021): flagged pages -> vision reply -> checked suggestion.

The model only transcribes (origin "ai"); the source blocks are never changed. The one real
call site is `make_real_llm`; tests and --mock inject a reply source. Python 3.8 stdlib only.
"""
import copy
import difflib
import hashlib
import re
import os

from exam_engine import settings
from exam_engine.adapters import claude
from exam_engine.ingest import optional, parts as partsmod
from exam_engine.ingest.adapters import image as imgmod
from exam_engine.ingest.schema import IngestError
from exam_engine.utils.text import fold

MIN_SIMILARITY = 0.6
MAX_ATTEMPTS = 2
FLAG_CODES = ("missing_text", "bad_encoding", "no_question_numbering", "math_possible")
FORBIDDEN = ("answer", "answers", "solution", "solutions", "key", "explanation")
PROMPT_REL = os.path.join("dev", "ingest", "refine.md")


class RefineError(Exception):
    """Structured refine failure (exit 3): stream_format, call_failed, invalid_reply, cost_cap."""

    def __init__(self, code, message):
        Exception.__init__(self, "%s: %s" % (code, message))
        self.code = code


def template():
    with open(os.path.join(settings.PROMPTS_DIR, PROMPT_REL), encoding="utf-8") as fh:
        return fh.read()


def build_prompt(n):
    return "%s\nPage: %d\n" % (template().rstrip("\n"), n)


def pick_pages(doc, spec):
    """Pages in `spec` that are flagged unreliable; a page not in the document is refused."""
    want = partsmod.parse_pages(spec)
    have = [p["n"] for p in doc["pages"]]
    bad = [n for n in want if n not in have]
    if bad:
        raise IngestError("invalid_pages", "page(s) %s not in the document"
                          % ", ".join(map(str, bad)))
    flagged = set(w["page"] for w in doc.get("warnings", ())
                  if w.get("page") and w.get("code") in FLAG_CODES)
    flagged |= set(p["n"] for p in doc["pages"] if p.get("status") == "ocr")
    return [n for n in want if n in flagged]


def check_key_pages(doc, spec, allow=False):
    """answer_key_present when a selected page lies in a detected answer-key part."""
    if allow:
        return
    want = partsmod.parse_pages(spec)
    for p in doc.get("parts") or partsmod.find_parts(doc):
        if p["kind"] == "answer_key" and any(p["pages"][0] <= n <= p["pages"][1] for n in want):
            raise IngestError("answer_key_present", "pages %d-%d of %s hold the answer key; "
                              "select the exam pages or pass --allow-key-pages"
                              % (p["pages"][0], p["pages"][1], doc["source"]["name"]))


def render_page(path, n):
    """PNG bytes of page n (zoom 2, lower zoom until <= 5 MB); header-checked."""
    fitz = optional.load("fitz", "pymupdf")
    pdf = fitz.open(path)
    try:
        for zoom in (2.0, 1.5, 1.0, 0.7):
            data = pdf[n - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes("png")
            if len(data) <= claude.MAX_IMAGE_BYTES:
                break
    finally:
        pdf.close()
    if imgmod.sniff(data) != "png" or len(data) > claude.MAX_IMAGE_BYTES:
        raise RefineError("call_failed", "page %d: no PNG within the size limit" % n)
    return data


def make_real_llm(model, timeout_s, cwd, runner=None, trace=None):
    """llm(prompt, png) through the Claude CLI (tools off, empty cwd); the only real call site."""
    def llm(prompt, png):
        extra = {"runner": runner} if runner else {}
        call = claude.run_claude_images(prompt, [("image/png", png)], model=model,
                                        timeout_s=timeout_s, cwd=cwd, **extra)
        if trace is not None:
            trace.append({"ok": call.ok, "cls": call.cls, "cost_usd": call.cost_usd,
                          "text": call.text, "reason": call.reason})
        low = call.reason.casefold()
        if not call.ok and ("input-format" in low or "stream-json" in low or "stream_json" in low):
            raise RefineError("stream_format", "the CLI rejected the image input mode: %s"
                              % call.reason)
        return call
    return llm


def mock_llm(path):
    """llm(prompt, png) replaying a JSON list of reply strings (same file format as solve)."""
    from exam_engine import engine
    base = engine.mock_llm(path)
    return lambda prompt, png: base(prompt)


def norm_id(v):
    """'3', 3, 'Câu 3.', 'Question 3' -> '3'; None when no number is present."""
    if isinstance(v, bool) or not isinstance(v, (int, str)):
        return None
    m = re.search(r"\d+", str(v))
    return str(int(m.group(0))) if m else None


PART_RE = re.compile(r"^\s*PH[ẦA]N\s+(IV|V|I{1,3})\b[^\n]*(?:\n|$)", re.I)


def split_part(text):
    """(roman part or None, text without the leading part heading line)."""
    m = PART_RE.match(text)
    return (m.group(1).upper(), text[m.end():].strip()) if m else (None, text)


def _gaps(questions):
    """(part, id) pairs that do not follow the previous id of their part by 1 or restart at 1."""
    out, prev = set(), {}
    for q in questions:
        qid = norm_id(q.get("id"))
        if qid is None:
            continue
        p = q.get("part")
        if p in prev and int(qid) not in (prev[p] + 1, 1):
            out.add((p, qid))
        prev[p] = int(qid)
    return out


def validate_refined(obj, originals=None):
    """Problems of a reply (empty = valid). `originals` = {id: source question}."""
    if not isinstance(obj, dict) or not isinstance(obj.get("questions"), list):
        return ["reply needs a 'questions' list"]
    errs = ["forbidden field %r (solver-like reply)" % k for k in FORBIDDEN if k in obj]
    for i, q in enumerate(obj["questions"], 1):
        if not isinstance(q, dict):
            errs.append("question %d: not an object" % i)
            continue
        errs += ["question %d: forbidden field %r (solver-like reply)" % (i, k)
                 for k in FORBIDDEN if k in q]
        qid = norm_id(q.get("id"))
        if qid is None:
            errs.append("question %d: id must be the question number" % i)
        if not isinstance(q.get("text"), str) or not q["text"].strip():
            errs.append("question %d: text must be a non-empty string" % i)
        opts = q.get("options", {})
        if not isinstance(opts, dict) or not all(isinstance(v, str) for v in opts.values()):
            errs.append("question %d: options must be an object of strings" % i)
            continue
        if not isinstance(q.get("unreadable", False), bool):
            errs.append("question %d: unreadable must be a boolean" % i)
        if not isinstance(q.get("figures", []), list):
            errs.append("question %d: figures must be a list" % i)
        orig = (originals or {}).get(qid)
        if orig and orig["options"] and not q.get("unreadable") and not set("ABCD") <= set(opts):
            errs.append("question %s: options A-D expected (the source has options)" % qid)
    return errs


def _page_text(doc, n):
    for p in doc["pages"]:
        if p["n"] == n:
            return "\n".join(b["text"] for b in p["blocks"] if b["type"] != "image")
    return ""


def similarity(refined_q, original_q, page_text):
    """difflib ratio of folded text: vs the same-numbered source question, else the share found in the page."""
    opts = refined_q.get("options", {})
    mine = fold(" ".join([refined_q["text"]] + [opts[k] for k in sorted(opts)]))
    if original_q:
        theirs = fold(" ".join([original_q["text"]] + [o["text"] for o in original_q["options"]]))
        return round(difflib.SequenceMatcher(None, mine, theirs, autojunk=False).ratio(), 3)
    theirs = fold(page_text)
    if not mine or not theirs:
        return 0.0
    m = difflib.SequenceMatcher(None, mine, theirs, autojunk=False)
    return round(sum(b.size for b in m.get_matching_blocks()) / float(len(mine)), 3)


def _ask(llm, n, png, originals):
    """(reply, calls, cost) for one page; at most MAX_ATTEMPTS calls (one retry on a bad reply)."""
    prompt, calls, cost, why = build_prompt(n), 0, 0.0, ""
    for _ in range(MAX_ATTEMPTS):
        call = llm(prompt, png)
        calls += 1
        cost += call.cost_usd
        if not call.ok:
            raise RefineError("call_failed", "page %d: %s %s" % (n, call.cls, call.reason))
        obj, why = claude.extract_json(call.text)
        if obj is not None:
            why = "; ".join(validate_refined(obj, originals))
        if not why:
            return obj, calls, cost
    raise RefineError("invalid_reply", "page %d: %s (after %d attempts)" % (n, why, calls))


def refine(doc, spec, llm, source_path=None, max_cost=1.0, model="sonnet", allow_key=False,
           min_similarity=MIN_SIMILARITY, render=render_page):
    """Copy of `doc` plus doc["refined"]; the source pages are untouched.

    `source_path` is the file to render pages from (None: no image is sent, mock runs).
    """
    check_key_pages(doc, spec, allow_key)
    pages = pick_pages(doc, spec)
    out = copy.deepcopy(doc)
    by_id = dict((str(q["n"]), q) for q in doc.get("questions") or ())
    qs, calls, cost, part = [], 0, 0.0, None
    for n in pages:
        if cost >= max_cost:
            raise RefineError("cost_cap", "cost $%.2f reached the cap $%.2f before page %d"
                              % (cost, max_cost, n))
        obj, used, spent = _ask(llm, n, render(source_path, n) if source_path else b"", by_id)
        calls += used
        cost += spent
        text = _page_text(doc, n)
        items = []
        for q in obj["questions"]:
            found, rest = split_part(q["text"])
            part = found or part
            if not rest and not q.get("options"):
                continue
            items.append(dict(q, text=rest, part=part))
        gaps = _gaps(items)
        for q in items:
            qid = norm_id(q["id"])
            sim = similarity(q, by_id.get(qid), text)
            qs.append({"id": qid, "part": q["part"], "text": q["text"],
                       "options": q.get("options", {}),
                       "figures": q.get("figures", []), "origin": "ai", "page": n,
                       "similarity": sim,
                       "needs_review": bool(q.get("unreadable")) or sim < min_similarity
                       or (q["part"], qid) in gaps})
    out["refined"] = {"model": model,
                      "prompt_sha256": hashlib.sha256(template().encode("utf-8")).hexdigest(),
                      "pages": pages, "questions": qs, "calls": calls,
                      "cost_usd": round(cost, 6)}
    nr = sum(1 for q in qs if q["needs_review"])
    out["warnings"].append({
        "level": "warning" if nr else "info", "code": "refined_by_ai",
        "message": "%d question(s) from %d page(s) suggested by AI, %d need review"
                   % (len(qs), len(pages), nr)})
    return out

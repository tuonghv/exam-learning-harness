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
from exam_engine.ingest import optional, parts as partsmod, segment
from exam_engine.ingest.adapters import image as imgmod
from exam_engine.ingest.schema import IngestError
from exam_engine.utils.text import fold

MIN_SIMILARITY = 0.6
MAX_ATTEMPTS = 2
MIN_OVERLAP = 20  # chars of a repeated continuation prefix treated as overlap
FLAG_CODES = ("missing_text", "bad_encoding", "no_question_numbering", "math_possible",
              "image_only", "ocr_unavailable")  # the last two: picture pages
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


def pick_pages(doc, spec, all_pages=False):
    """Pages in `spec` that are flagged unreliable (all of them with all_pages); a page not in the document is refused."""
    want = partsmod.parse_pages(spec)
    have = [p["n"] for p in doc["pages"]]
    bad = [n for n in want if n not in have]
    if bad:
        raise IngestError("invalid_pages", "page(s) %s not in the document"
                          % ", ".join(map(str, bad)))
    if all_pages:
        return want
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


def _continues_errors(c):
    if c is None:
        return []
    if not isinstance(c, dict):
        return ["continues must be an object"]
    errs = []
    if not isinstance(c.get("text", ""), str):
        errs.append("continues: text must be a string")
    if not isinstance(c.get("options", {}), dict) or not all(
            isinstance(v, str) for v in c.get("options", {}).values()):
        errs.append("continues: options must be an object of strings")
    if not isinstance(c.get("figures", []), list):
        errs.append("continues: figures must be a list")
    if not isinstance(c.get("passage", False), bool):
        errs.append("continues: passage must be a boolean")
    return errs


def validate_refined(obj, originals=None):
    """Problems of a reply (empty = valid). `originals` = {id: source question}."""
    if not isinstance(obj, dict) or not isinstance(obj.get("questions"), list):
        return ["reply needs a 'questions' list"]
    errs = ["forbidden field %r (solver-like reply)" % k for k in FORBIDDEN if k in obj]
    errs += _continues_errors(obj.get("continues"))
    for i, q in enumerate(obj["questions"], 1):
        if not isinstance(q, dict):
            errs.append("question %d: not an object" % i)
            continue
        errs += ["question %d: forbidden field %r (solver-like reply)" % (i, k)
                 for k in FORBIDDEN if k in q]
        qid = norm_id(q.get("id"))
        # an entry without a number is a continuation of the previous page (legacy form)
        frag = isinstance(q.get("text"), str) and (
            (isinstance(q.get("options"), dict) and bool(q["options"]))
            or (bool(q["text"].strip()) and q.get("id") in ("", None)))
        if qid is None and not frag:
            errs.append("question %d: id must be the question number" % i)
        if not isinstance(q.get("text"), str) or (not q["text"].strip() and not q.get("unreadable") and not frag):
            errs.append("question %d: text must be a non-empty string" % i)
        opts = q.get("options", {})
        if not isinstance(opts, dict) or not all(isinstance(v, str) for v in opts.values()):
            errs.append("question %d: options must be an object of strings" % i)
            continue
        if not isinstance(q.get("unreadable", False), bool):
            errs.append("question %d: unreadable must be a boolean" % i)
        if not isinstance(q.get("figures", []), list):
            errs.append("question %d: figures must be a list" % i)
        if not isinstance(q.get("cut", False), bool):
            errs.append("question %d: cut must be a boolean" % i)
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


def _cont(obj):
    """(continuation, numbered entries): the legacy `id:""` entries are folded into the continuation."""
    c = obj.get("continues") or {}
    cont = {"text": str(c.get("text") or "").strip(), "options": dict(c.get("options") or {}),
            "figures": list(c.get("figures") or []), "passage": bool(c.get("passage")),
            "legacy": False}
    rest = []
    for q in obj["questions"]:
        if norm_id(q.get("id")) is not None:
            rest.append(q)
            continue
        cont["legacy"] = True
        cont["text"] = (cont["text"] + "\n" + str(q.get("text") or "")).strip()
        cont["options"].update(q.get("options") or {})
        cont["figures"] += list(q.get("figures") or [])
    return cont, rest


def _dedupe(owner, text):
    """`text` without a prefix the owner already ends with (tile overlap, repeated line) or "" when contained."""
    for k in range(min(len(owner), len(text)), MIN_OVERLAP - 1, -1):
        if owner.endswith(text[:k]):
            return text[k:].strip()
    if len(text) >= MIN_OVERLAP and fold(text) in fold(owner):
        return ""
    return text


def _attach(qs, st, n, cont):
    """Merge continuation `cont` of page n into the open question of page n-1 -> orphan kind or None."""
    if st["open"] is None or st["page"] != n - 1:
        return "no_owner"
    o = qs[st["open"]]
    if segment._Q.match(cont["text"]):
        kind = "starts_with_number"
    elif cont["options"] and o["options"]:
        kind = "owner_has_options"
    else:
        kind = None
    if kind:
        o.update(needs_review=True, orphan_page=n)
        return kind
    text = _dedupe(o["context"] if cont["passage"] and o["context"] else o["text"], cont["text"])
    if text:
        key = "context" if cont["passage"] and o["context"] else "text"
        o[key] = (o[key] + "\n" + text).strip()
    if cont["options"]:
        o["options"] = cont["options"]
    o["figures"] = list(o["figures"]) + cont["figures"]
    o["continued_pages"] = o.get("continued_pages", []) + [n]
    if cont["legacy"]:
        o.update(needs_review=True, joined_page=n)
    return None


def _files_hint(doc, orphans):
    """" (file(s) a.png)" naming the files of the pages before an orphan, for image sequences."""
    files = doc["source"].get("files")
    if not files:
        return ""
    return " (file(s) %s)" % ", ".join(files[o["page"] - 2]["name"] for o in orphans
                                       if 2 <= o["page"] <= len(files) + 1)


def refine(doc, spec, llm, source_path=None, max_cost=1.0, model="sonnet", allow_key=False,
           min_similarity=MIN_SIMILARITY, render=render_page, all_pages=False):
    """Copy of `doc` plus doc["refined"]; the source pages are untouched.

    `source_path` is the file to render pages from (None: no image is sent, mock runs).
    """
    check_key_pages(doc, spec, allow_key)
    pages = pick_pages(doc, spec, all_pages)
    out = copy.deepcopy(doc)
    dq = doc.get("questions") or ()
    # restarted numbering repeats ids: originals are ambiguous, so none (as before for such docs)
    by_id = dict((str(q["n"]), q) for q in dq)
    if len(by_id) != len(dq):
        by_id = {}
    qs, calls, cost, part, carry = [], 0, 0.0, None, ""
    st, orphans = {"open": None, "page": None}, []  # open: index in qs of the last question of page st["page"]
    for n in pages:
        if cost >= max_cost:
            raise RefineError("cost_cap", "cost $%.2f reached the cap $%.2f before page %d"
                              % (cost, max_cost, n))
        obj, used, spent = _ask(llm, n, render(source_path, n) if source_path else b"", by_id)
        calls += used
        cost += spent
        text = _page_text(doc, n)
        items = []
        carried, carry = carry, str(obj.get("carry") or "").strip()
        cont, numbered = _cont(obj)
        if cont["text"] or cont["options"] or cont["figures"]:
            if cont["passage"] and carried:
                # more paragraphs of a passage whose questions start on a later page
                carried = "\n".join([carried, cont["text"]] + ["[Figure/table: %s]" % f
                                                               for f in cont["figures"]]).strip()
            else:
                kind = _attach(qs, st, n, cont)
                if kind:
                    orphans.append({"page": n, "kind": kind})
        for q in numbered:
            if carried:
                # passage printed on the previous page whose questions start here
                q = dict(q, context=(carried + "\n" + str(q.get("context") or "")).strip())
                carried = ""
            found, rest = split_part(q["text"])
            part = found or part
            if not rest and not q.get("options"):
                continue
            items.append(dict(q, text=rest, part=part))
        if carried and "continues" in obj and not numbered:
            carry = (carried + "\n" + carry).strip()  # the passage goes on over this page
        if items:
            st["open"], st["page"] = len(qs) + len(items) - 1, n
        elif st["open"] is not None and st["page"] == n - 1:
            st["page"] = n  # a page of pure continuation: the chain goes on
        else:
            st["open"] = None
        gaps = _gaps(items)
        for q in items:
            qid = norm_id(q["id"])
            sim = similarity(q, by_id.get(qid), text)
            qs.append({"id": qid, "part": q["part"], "text": q["text"],
                       "options": q.get("options", {}), "context": str(q.get("context") or ""),
                       "figures": q.get("figures", []), "origin": "ai", "page": n,
                       "similarity": sim,
                       "needs_review": bool(q.get("unreadable")) or sim < min_similarity
                       or (q["part"], qid) in gaps})
            if q.get("cut") is True:
                qs[-1]["cut"] = True
    out["refined"] = {"model": model,
                      "prompt_sha256": hashlib.sha256(template().encode("utf-8")).hexdigest(),
                      "pages": pages, "questions": qs, "calls": calls,
                      "cost_usd": round(cost, 6)}
    if orphans:
        out["refined"]["orphans"] = orphans
    nr = sum(1 for q in qs if q["needs_review"])
    out["warnings"].append({
        "level": "warning" if nr else "info", "code": "refined_by_ai",
        "message": "%d question(s) from %d page(s) suggested by AI, %d need review"
                   % (len(qs), len(pages), nr)})
    if orphans:
        out["warnings"].append({
            "level": "warning", "code": "orphan_continuation",
            "message": "continuation on page(s) %s not merged (no question on the page before, or it "
                       "does not fit): add page(s) %s to --pages" % (
                           ", ".join(str(o["page"]) for o in orphans),
                           ", ".join(str(o["page"] - 1) for o in orphans)) + _files_hint(doc, orphans)})
    return out

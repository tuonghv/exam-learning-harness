"""Ingestion boundary: ingest_document(path) -> validated canonical doc; to_exam_text(doc)."""
import hashlib
import os
import re

from exam_engine.core import refcheck
from exam_engine.ingest import adapters, parts, segment
from exam_engine.ingest.schema import IngestError, validate_document
from exam_engine.pipeline import parser

REQUIRED = ("Subject", "Level", "Exam type", "Task", "Mode")


def ingest_document(path, config=None, meta=None):
    """Canonical doc for `path`; `config` is reserved for adapters (unused by Markdown).

    source.path is the file name only (no local absolute path); the adapter hashes the
    same bytes it parsed.
    """
    ext = os.path.splitext(path)[1].lower()
    fn = adapters.get(ext)
    if fn is None:
        raise IngestError("unsupported_format", "%r not supported (have: %s)"
                          % (ext or path, ", ".join(adapters.extensions())))
    doc = fn(path, config)
    if not doc.get("source"):
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            raise IngestError("corrupt", "cannot read %s: %s" % (path, exc))
        name = os.path.basename(path)
        doc["source"] = {"path": name, "name": name, "format": ext.lstrip("."),
                         "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
    return _finish(doc, config, meta)


def ingest_sequence(paths, config=None, meta=None):
    """Canonical doc for several image files (file k = page k); same post-steps as ingest_document."""
    return _finish(adapters.image.ingest_sequence(paths, config), config, meta)


def _finish(doc, config, meta):
    if doc["source"].get("format") != "md":
        doc["parts"] = parts.find_parts(doc)
        if (config or {}).get("pages"):
            doc = parts.select_pages(doc, config["pages"], config.get("boundary"))
    fields = parser.header_fields(doc["source"]["text"]) if "text" in doc["source"] else {}
    fields.update(meta or {})
    doc["meta"] = fields
    errs = validate_document(doc)
    if errs:
        raise IngestError("invalid_document", "; ".join(errs[:5]))
    return doc


def _is_exam_format(text):
    fields = parser.header_fields(text)
    return all(fields.get(k) for k in REQUIRED) and bool(parser.sections(text, 2))


def to_exam_text(doc, config=None):
    """Exam file text for `solve`: an exam-format Markdown source is returned unchanged.

    Refuses a document that still holds answer-key pages unless config["allow_key_pages"].
    """
    if parts.has_key(doc) and not (config or {}).get("allow_key_pages"):
        raise IngestError("answer_key_present", "answer-key pages %s in %s; select the exam "
                          "pages (--pages) or pass --allow-key-pages"
                          % (", ".join("%d-%d" % tuple(p["pages"]) for p in doc["parts"]
                                       if p["kind"] == "answer_key"), doc["source"]["name"]))
    src = doc["source"]
    if (config or {}).get("use_refined"):
        return _from_refined(doc, config.get("questions"))
    if (doc.get("extraction") or {}).get("method") == "image" and not any(
            b["type"] != "image" and b["text"].strip()
            for pg in doc["pages"] for b in pg["blocks"]):
        raise IngestError("no_text", "%s is an image without text; it goes to the solver as a "
                          "visual (image solving arrives with REQ-0021); no text is guessed"
                          % src["name"])
    if src.get("format") == "md":
        text = src.get("text")
        if text is not None and hashlib.sha256(text.encode("utf-8")).hexdigest() != src["sha256"]:
            raise IngestError("corrupt", "source text does not match its hash: %s" % src["name"])
        if text is not None and _is_exam_format(text):
            return text
    meta = doc.get("meta") or {}
    missing = [k for k in REQUIRED if not meta.get(k)]
    if missing:
        raise IngestError("missing_header", "missing exam header(s): %s (use --meta K=V)"
                          % ", ".join(missing))
    out = ["# Exam Input", ""]
    out += ["%s: %s" % (k, v) for k, v in meta.items()]
    out.append("")
    if src.get("format") != "md":
        return _from_questions(doc, out)
    for page in doc["pages"]:
        for blk in page["blocks"]:
            if blk["type"] == "heading":
                out.append("%s %s" % ("#" * (blk.get("level") or 2), blk["text"]))
            else:
                out.append(blk["text"])
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


GROUP_RE = segment.GROUP_RE


def _flag(q, code):
    """q with structure flag `code` (key only when non-empty; flags never decline a question)."""
    cur = q.get("structure") or []
    return q if code in cur else dict(q, structure=cur + [code])


def _flag(q, code):
    """q with structure flag `code` (key only when non-empty; flags never decline a question)."""
    cur = q.get("structure") or []
    return q if code in cur else dict(q, structure=cur + [code])


def _share_context(qs):
    """Repeat a passage with every question of its group ("Questions 46-52", "câu từ 103 đến 105").

    A range stays inside its section (numbering may restart in the next one); a question's own
    context inside a range is kept as the first line(s) of its text. Doubts go to q["structure"]."""
    out, cur, sec, ghost, stack = [], None, "", None, []  # ghost: the (lo, hi) of a range cut by a section change

    def close():  # a range that ended before its last number: the carrier shows it
        if cur and cur["last"] < cur["hi"]:
            out[cur["at"]] = _flag(out[cur["at"]], "range_overrun")

    for q in qs:
        heads, ctx = segment.split_heading(q.get("context") or "")
        for h in heads:
            segment.push_heading(stack, h)
        new_sec = " > ".join(t for _, t in stack) or sec  # a section stays until the next heading
        m = segment.GROUP_ANY.search(ctx)
        num = int(q["id"]) if q["id"].isdigit() else None
        if new_sec != sec:
            ghost = (cur["lo"], cur["hi"]) if cur else None
            close()
            cur = None
        sec = new_sec
        q = dict(q, context=ctx, section=sec) if heads or sec else q
        if m:
            lo, hi = segment.group_span(m)
            if cur and cur["ctx"] == ctx and (cur["lo"], cur["hi"]) == (lo, hi):
                cur["last"] = max(cur["last"], num or 0)  # the group line repeated on a member
                q = dict(q, context=ctx)
            else:
                close()
                cur = {"lo": lo, "hi": hi, "ctx": ctx, "at": len(out), "last": num or 0}
            ghost = None
        elif cur and num is not None and cur["lo"] < num <= cur["hi"]:
            cur["last"] = max(cur["last"], num)
            if ctx.strip() and ctx != cur["ctx"]:  # nearer text wins: own line leads the question text
                q = _flag(dict(q, text=(ctx + "\n" + (q.get("text") or "")).strip()), "instruction_override")
            q = dict(q, context=cur["ctx"])
        elif ghost and num is not None and ghost[0] <= num <= ghost[1]:
            q = _flag(q, "range_cut_by_section")
        out.append(q)
    close()
    return out


def refined_questions(doc):
    """doc["refined"] questions with a question cut by a page break merged into one."""
    qs = []
    for q in (doc.get("refined") or {}).get("questions") or []:
        if qs and qs[-1]["id"] == q["id"]:
            # one question cut by a page break: stem on the first page, options on the next
            cp = sorted(set(qs[-1].get("continued_pages", [])) | set(q.get("continued_pages", [])))
            qs[-1] = dict(qs[-1], text=(qs[-1]["text"] + "\n" + q["text"]).strip(),
                          options=q["options"] or qs[-1]["options"], cut=bool(q.get("cut")))
            if cp:
                qs[-1]["continued_pages"] = cp  # the last part's cut stays; the first part's is joined
        else:
            qs.append(q)
    return qs


def question_lines(q):
    """Question block lines of the exam text, without options: context, text, figure lines."""
    out = []
    guide, passage = segment.split_guide(q.get("context") or "")
    pg = sorted({q["page"]} | set(q.get("continued_pages") or ())) if q.get("page") else []
    if pg:  # the image check needs the pages of every question; the parser strips the line from the prompt text
        out += ["Source pages: %s" % ("%d-%d" % (pg[0], pg[-1]) if pg[-1] - pg[0] + 1 == len(pg)
                                      and len(pg) > 1 else ",".join(map(str, pg))), ""]
    if guide:  # four-level form: instruction / passage / question text (FORMAT.md)
        out += ["### Instruction for this group", "", guide, ""]
        if passage:
            out += ["### Passage", "", passage, ""]
        out += ["### Question text", ""]
    elif q.get("context"):
        out += [q["context"], ""]
    out += [q.get("text") or "", ""]
    return out + ["[Figure/table: %s]" % f for f in q.get("figures") or ()]


def _section_lines(q, prev):
    """`## Section:` line when the section changes; -> (lines, section)."""
    sec = q.get("section") or ""
    return (["## Section: %s" % sec, ""] if sec and sec != prev else []), (sec or prev)


def _selected_refined(doc, spec=None):
    """(questions, their question_lines, incomplete reasons) as written to the exam text."""
    qs = _share_context(refined_questions(doc))  # before the slice: a group's carrier may lie outside `spec`
    if spec:
        want = set(parts.parse_pages(spec))
        qs = [q for q in qs if q["id"].isdigit() and int(q["id"]) in want]
    lines = [question_lines(q) for q in qs]
    return qs, lines, refcheck.incomplete_by_question(qs, ["\n".join(ln) for ln in lines])


def _from_refined(doc, spec=None):
    """Exam text from doc["refined"] questions (origin ai); `spec` keeps question numbers like 61-90."""
    meta = doc.get("meta") or {}
    missing = [k for k in REQUIRED if not meta.get(k)]
    if missing:
        raise IngestError("missing_header", "missing exam header(s): %s (use --meta K=V)"
                          % ", ".join(missing))
    qs, lines, why = _selected_refined(doc, spec)
    if not qs:
        raise IngestError("no_questions", "no refined questions selected in %s" % doc["source"]["name"])
    out = ["# Exam Input", ""] + ["%s: %s" % (k, v) for k, v in meta.items()]
    first = int(qs[0]["id"])
    out += ["", "## Instructions", "", "Choose the best answer and explain why."]
    if first != 1:
        out += ["", "Questions are numbered from 1 here; the printed exam number of question N is N + %d "
                "(passages may refer to printed numbers)." % (first - 1)]
    out.append("")
    prev = ""
    for k, (q, ln, w) in enumerate(zip(qs, lines, why), 1):
        sl, prev = _section_lines(q, prev)
        out += sl + ["## Question %d" % k, ""] + ln
        if w:
            out += [refcheck.marker(w), ""]
        out += ["%s. %s" % (k, q["options"][k]) for k in sorted(q["options"])]
        if q["options"]:
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def _printed(qs):
    """"1=1, 2=150" (restarts: "11=s2.1"): exam position = printed number."""
    sec, parts_ = 0, []
    multi = len(segment.runs(qs)) > 1
    for k, q in enumerate(qs, 1):
        if q["n"] == 1 and k > 1:
            sec += 1
        parts_.append("%d=%s" % (k, "s%d.%d" % (sec + 1, q["n"]) if multi else q["n"]))
    return ", ".join(parts_)


def _selected_questions(doc):
    """(context-shared segmented questions, incomplete reasons) as written to the exam text."""
    qs = doc.get("questions") or []
    ctx = _share_context([dict(q, id=str(q["n"])) for q in qs])
    return ctx, refcheck.incomplete_by_question(qs, [q["text"] for q in qs])


UNCERTAIN = ("cut_unresolved", "orphan_on_page", "merge_suspect", "unreadable", "ocr_doubt")


def assembly(doc, config=None):
    """Provenance rows, one per exam-file question (same selection as `to_exam_text`).

    Row: id (exam position), printed, source_pages ([] on the text path: no per-question page),
    assembly_status complete|uncertain, validation_status passed|failed, reasons, and `structure`
    (scope doubts, _flag codes; key only when non-empty). Never raises."""
    cfg = config or {}
    rows = []
    if cfg.get("use_refined"):
        qs, _, why = _selected_refined(doc, cfg.get("questions"))
        flags = [q.get("structure") or [] for q in qs]
        pages = [sorted(({q["page"]} if q.get("page") else set()) | set(q.get("continued_pages") or ()))
                 for q in qs]
        printed = [q["id"] for q in qs]
    else:
        raw = doc.get("questions") or []
        ctx, why = _selected_questions(doc)
        flags = [q.get("structure") or [] for q in ctx]
        pages = [[] for _ in raw]
        sec, multi, printed = 0, len(segment.runs(raw)) > 1, []
        for k, q in enumerate(raw, 1):
            if q["n"] == 1 and k > 1:
                sec += 1
            printed.append("s%d.%d" % (sec + 1, q["n"]) if multi else str(q["n"]))
    for k, (pr, pg, w, fl) in enumerate(zip(printed, pages, why, flags), 1):
        unc = any(r.split(" ")[0] in UNCERTAIN for r in w)
        rows.append(dict({"id": str(k), "printed": pr, "source_pages": pg,
                          "assembly_status": "uncertain" if unc else "complete",
                          "validation_status": "failed" if w else "passed", "reasons": list(w)},
                         **({"structure": list(fl)} if fl else {})))
    return rows


def _from_questions(doc, out):
    """Exam text from the segmented `questions` (non-Markdown sources); never edits the text."""
    qs = doc.get("questions") or []
    if not qs:
        raise IngestError("no_questions", "no segmented questions in %s; fix the saved "
                          "document (--out) by hand" % doc["source"]["name"])
    renum = [q["n"] for q in qs] != list(range(1, len(qs) + 1))
    if doc.get("intro") or renum:
        out += ["## Instructions", ""]
        if doc.get("intro"):
            out += [doc["intro"], ""]
        if renum:
            out += ["Questions are numbered from 1 here; printed numbers: %s." % _printed(qs), ""]
    ctx, why = _selected_questions(doc)
    prev = ""
    for k, (q, w) in enumerate(zip(ctx, why), 1):
        sl, prev = _section_lines(q, prev)
        out += sl + ["## Question %d" % k, ""] + question_lines(dict(q, figures=()))  # text path: no figure lines
        if w:
            out += [refcheck.marker(w), ""]
        out += ["%s. %s" % (o["key"], o["text"]) for o in q["options"]]
        if q["options"]:
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"

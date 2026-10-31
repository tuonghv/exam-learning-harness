"""Ingestion boundary: ingest_document(path) -> validated canonical doc; to_exam_text(doc)."""
import hashlib
import os
import re

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
    if doc["source"].get("format") != "md":
        doc["parts"] = parts.find_parts(doc)
        if (config or {}).get("pages"):
            doc = parts.select_pages(doc, config["pages"])
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


GROUP_RE = re.compile(r"(?:Questions?|Câu|câu)\s*(?:từ\s*)?(\d+)\s*(?:-|–|đến|to)\s*(\d+)")


def _share_context(qs):
    """Repeat a passage with every question of its group ("Questions 46-52", "câu từ 103 đến 105")."""
    out, cur = [], None
    for q in qs:
        ctx = q.get("context") or ""
        m = GROUP_RE.search(ctx)
        if m:
            cur = (int(m.group(1)), int(m.group(2)), ctx)
        elif cur and q["id"].isdigit() and cur[0] < int(q["id"]) <= cur[1]:
            q = dict(q, context=cur[2])
        out.append(q)
    return out


def refined_questions(doc):
    """doc["refined"] questions with a question cut by a page break merged into one."""
    qs = []
    for q in (doc.get("refined") or {}).get("questions") or []:
        if qs and qs[-1]["id"] == q["id"]:
            # one question cut by a page break: stem on the first page, options on the next
            qs[-1] = dict(qs[-1], text=(qs[-1]["text"] + "\n" + q["text"]).strip(),
                          options=q["options"] or qs[-1]["options"])
        else:
            qs.append(q)
    return qs


def question_lines(q):
    """Question block lines of the exam text, without options: context, text, figure lines."""
    out = []
    if q.get("context"):
        out += [q["context"], ""]
    out += [q.get("text") or "", ""]
    return out + ["[Figure/table: %s]" % f for f in q.get("figures") or ()]


def _from_refined(doc, spec=None):
    """Exam text from doc["refined"] questions (origin ai); `spec` keeps question numbers like 61-90."""
    meta = doc.get("meta") or {}
    missing = [k for k in REQUIRED if not meta.get(k)]
    if missing:
        raise IngestError("missing_header", "missing exam header(s): %s (use --meta K=V)"
                          % ", ".join(missing))
    qs = refined_questions(doc)
    if spec:
        want = set(parts.parse_pages(spec))
        qs = [q for q in qs if q["id"].isdigit() and int(q["id"]) in want]
    if not qs:
        raise IngestError("no_questions", "no refined questions selected in %s" % doc["source"]["name"])
    out = ["# Exam Input", ""] + ["%s: %s" % (k, v) for k, v in meta.items()]
    qs = _share_context(qs)
    first = int(qs[0]["id"])
    out += ["", "## Instructions", "", "Choose the best answer and explain why."]
    if first != 1:
        out += ["", "Questions are numbered from 1 here; the printed exam number of question N is N + %d "
                "(passages may refer to printed numbers)." % (first - 1)]
    out.append("")
    for k, q in enumerate(qs, 1):
        out += ["## Question %d" % k, ""]
        out += question_lines(q)
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
    for k, q in enumerate(qs, 1):
        out += ["## Question %d" % k, "", q["text"], ""]
        out += ["%s. %s" % (o["key"], o["text"]) for o in q["options"]]
        if q["options"]:
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"

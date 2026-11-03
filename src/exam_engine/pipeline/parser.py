"""Shared parser for exam input/expected Markdown files (examples/FORMAT.md).

Python 3.8 stdlib only.
"""
import re
import unicodedata

from exam_engine.core import refcheck
from exam_engine.pipeline import router
from exam_engine.utils.text import norm  # noqa: F401  (re-exported)

LEGACY_HEADINGS = ("Solution", "Explanation", "Verification", "Grading")
_QHEAD = re.compile(r"^##\s+Question\s+(\d+)\s*$")
_LEGACY_QHEAD = re.compile(r"^Question\s+(\d+)\s*$")
_HEAD = re.compile(r"^(#+)\s+(.*?)\s*$")
_LEVELS = {"Instruction for this group", "Passage", "Question text"}


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return unicodedata.normalize("NFC", fh.read())


def header_fields(text):
    """`Key: value` lines before the first `## ` heading; `#` comments stripped."""
    out = {}
    for line in text.splitlines():
        if line.startswith("## "):
            break
        if line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z][A-Za-z ]*?):\s*(.*)$", line)
        if m:
            val = re.sub(r"\s+#.*$", "", m.group(2)).strip()
            out[m.group(1).strip()] = val
    return out


def sections(text, level):
    """Split on headings of exactly `level` #; returns [(title, body)]."""
    prefix = "#" * level
    out = []
    title = None
    buf = []
    for line in text.splitlines():
        m = _HEAD.match(line)
        if m and m.group(1) == prefix:
            if title is not None:
                out.append((title, "\n".join(buf).strip("\n")))
            title, buf = m.group(2), []
        elif title is not None:
            buf.append(line)
    if title is not None:
        out.append((title, "\n".join(buf).strip("\n")))
    return out


_PAGES_RE = re.compile(r"\A\s*Source pages:[ \t]*([\d,\s-]+?)[ \t]*(?:\n|\Z)")


def _source_pages(text):
    """-> (pages, text without the leading `Source pages: 1-2` line); pages [] when absent."""
    m = _PAGES_RE.match(text)
    if not m:
        return [], text
    pages = []
    for part in m.group(1).split(","):
        a, _, b = part.strip().partition("-")
        if a.strip().isdigit():
            pages += range(int(a), int(b) + 1) if b.strip().isdigit() else [int(a)]
    return sorted(set(pages)), text[m.end():].strip()


def strip_unlabelled_pages(text):
    """Exam text without the `Source pages:` line of unlabelled questions (only the parser needs it there;
    the prompt stays as it was before ingest emitted the line). Labelled (four-level) questions keep it."""
    out = []
    for chunk in re.split(r"(?m)^(?=## )", text):
        m = re.match(r"## Question\s+\d+[ \t]*\n(\s*)Source pages:[^\n]*\n\n?", chunk)
        if m and not re.search(r"(?m)^### (?:%s)\s*$" % "|".join(map(re.escape, _LEVELS)), chunk):
            chunk = chunk[:m.end(1)] + chunk[m.end():]
        out.append(chunk)
    return "".join(out)


def parse_exam(path):
    text = read_text(path)
    secs = sections(text, 2)
    res = {"fields": header_fields(text), "instructions": "", "passage": "",
           "learner_answer": None, "questions": [], "sections": [], "section_subjects": {}}
    cur_section = ""
    for title, body in secs:
        sm = re.match(r"^Section:\s*(.+)$", title)
        if sm:
            cur_section = sm.group(1).strip()
            res["sections"].append(cur_section)
            fn = getattr(router, "heading_subject", None)
            res["section_subjects"][cur_section] = fn(cur_section) if fn else None
            continue
        m = re.match(r"^Question\s+(\d+)$", title)
        if m:
            opts = {}
            lines = []
            blines = body.splitlines()
            # labelled file: options only after `### Question text`; instruction/passage lines stay verbatim
            qt = next((i for i, ln in enumerate(blines) if re.match(r"^### Question text\s*$", ln)), None)
            for i, line in enumerate(blines):
                om = re.match(r"^([A-D])\.\s+\S", line) if qt is None or i > qt else None
                if om:
                    opts[om.group(1)] = line[2:].strip()
                else:
                    lines.append(line)
            text = "\n".join(lines).strip()
            pages, text = _source_pages(text)
            lab = dict(sections(text, 3)) if "###" in text else {}
            if not set(lab) & _LEVELS:
                lab = {}  # unlabelled (today's form): the whole body is the stem
            ins = lab.get("Instruction for this group", "").strip()
            pas = lab.get("Passage", "").strip()
            if lab and not opts and pas:  # a shared option bank filed as passage: its trailing A-D lines are the options
                pl = [ln for ln in pas.splitlines() if ln.strip()]  # blank lines between options are skipped
                k = len(pl)
                while k and re.match(r"^[A-Ea-e][.)]\s+\S", pl[k - 1].strip()):
                    k -= 1
                if len(pl) - k >= 2:
                    opts = {ln.strip()[0].upper(): ln.strip()[2:].strip() for ln in pl[k:]}
                    pas = "\n".join(pl[:k]).strip()
            stem = lab.get("Question text", "").strip() if lab else text
            if lab:  # labelled: text = instruction + passage + stem (labels dropped)
                text = "\n\n".join(p for p in (ins, pas, stem) if p)
            res["questions"].append({"id": int(m.group(1)), "text": text, "options": opts,
                                     "section": cur_section, "instruction": ins,
                                     "passage": pas, "stem": stem, **({"pages": pages} if pages else {})})
        elif title == "Instructions":
            res["instructions"] = body
        elif title == "Passage":
            res["passage"] = body
        elif title == "Learner answer":
            res["learner_answer"] = body
    return res


def _value(line, key):
    m = re.match(r"^\s*[-*]?\s*" + key + r":\s*(.*?)\s*$", line, re.I)
    return m.group(1) if m else None


def parse_expected(path, legacy=False):
    text = read_text(path)
    qs = []
    cur = None
    block = None
    pending = {}
    for line in text.splitlines():
        s = line.strip()
        qid = None
        m = _QHEAD.match(line) or (legacy and _LEGACY_QHEAD.match(s))
        if m:
            qid = int(m.group(1))
        if qid is not None:
            cur = {"id": qid, "final": None, "correct": None, "blocks": {}}
            qs.append(cur)
            for k, v in pending.items():
                cur["blocks"][k] = v
            pending = {}
            block = None
            continue
        name = None
        hm = _HEAD.match(line)
        if hm and len(hm.group(1)) == 3:
            name = hm.group(2)
        elif legacy and s in LEGACY_HEADINGS:
            name = s
        if name is not None:
            target = cur["blocks"] if cur else pending
            target.setdefault(name, "")
            block = (target, name)
            continue
        if hm:  # other heading (e.g. `# Expected Output`)
            block = None
            continue
        if block is not None:
            block[0][block[1]] += line + "\n"
        elif cur is not None:
            v = _value(line, "Final answer")
            if v is not None and cur["final"] is None:
                cur["final"] = v
            v = _value(line, "Correct answer")
            if v is not None and cur["correct"] is None:
                cur["correct"] = v
    for q in qs:
        q["blocks"] = {k: v.strip("\n") for k, v in q["blocks"].items()}
        if legacy and q["final"] is None and q["correct"]:
            lm = re.match(r"^([A-D])\b", q["correct"])
            if lm:
                q["final"] = lm.group(1)
    return {"questions": qs}


_REQUIRED_HEADERS = ("Subject", "Level", "Exam type", "Task", "Mode")
_SUPPORTED_MODES = ("Solve",)


def validate_exam(exam):
    """Errors of a parse_exam result as a list of strings (empty = valid); never raises."""
    errs = []
    fields = exam.get("fields") or {}
    for key in _REQUIRED_HEADERS:
        if not fields.get(key):
            errs.append("missing header: %s" % key)
    subj = fields.get("Subject")
    if subj and not router.subject_key(subj):
        errs.append("unsupported Subject: %s" % subj)
    mode = fields.get("Mode")
    if mode and mode not in _SUPPORTED_MODES:
        errs.append("unsupported Mode: %s" % mode)
    qs = exam.get("questions") or []
    if not qs:
        errs.append("no questions")
    for pos, q in enumerate(qs, 1):
        if q["id"] != pos:
            errs.append("question numbering: expected %d, found %d" % (pos, q["id"]))
            break
    seen = set()
    for q in qs:
        if q["id"] in seen:
            errs.append("duplicate question %d" % q["id"])
        seen.add(q["id"])
    mc = (fields.get("Task") or "").strip().casefold() == "multiple choice"
    for q in qs:
        if not q["text"].strip() and not q["options"]:
            errs.append("question %d: empty body" % q["id"])
        if ((mc or q["options"]) and sorted(q["options"]) != ["A", "B", "C", "D"]
                and refcheck.marker_reasons(q["text"]) is None):  # a marked one is declined, not solved
            errs.append("question %d: options must be exactly A-D" % q["id"])
    return errs


def exam_warnings(exam):
    """Non-fatal findings of a parse_exam result (section headings vs subject); never raises."""
    warns = []
    subj = (exam.get("fields") or {}).get("Subject")
    want = router.subject_key(subj) if subj else None
    for sec, key in (exam.get("section_subjects") or {}).items():
        if key is None:
            warns.append("section_subject_unknown: %s" % sec)
        elif want and key != want:
            warns.append("section_subject_mismatch: %s -> %s vs Subject %s" % (sec, key, subj))
    if labelled(exam) and not exam.get("passage"):  # a ref word with no number and no text to link to
        for q in exam["questions"]:
            if not (q.get("instruction") or q.get("passage")) and _VAGUE_RE.search(q.get("stem") or ""):
                warns.append("group_link_uncertain: q %d" % q["id"])
        for g in groups(exam):  # passage promised, none given, but the stem carries text: solve, warn
            if g["instruction"] and not g["passage"] and refcheck._NEEDS_TEXT.search(g["instruction"]):
                warns.extend("group_link_uncertain: q %d" % q["id"] for q in exam["questions"]
                             if q["id"] in g["ids"] and (q.get("instruction") or "") == g["instruction"]
                             and refcheck.has_own_text(q))
    return warns


_VAGUE_RE = re.compile(r"(?i)\b(?:the|this) (?:text|passage)\b|(?:đoạn|văn bản|bài) (?:văn )?(?:trên|sau)\b")


_REF_RE = re.compile(r"(?i)\b(?:câu|question)\s+(\d+)|\bý\s*\([a-d]\)|kết quả (?:câu|ý) trên"
                     r"|previous (?:question|answer)")
_OFFSET_RE = re.compile(r"printed exam number of question N is N \+ (\d+)")
_TABLE_RE = re.compile(r"(?m)^(?:\s*\|.*\||\[Figure/table:.*)$")


def _passage(q):
    """Passage text of a question: the labelled level, else its table / figure lines."""
    return q.get("passage") or "\n".join(m.group(0).strip() for m in _TABLE_RE.finditer(q["text"]))


def deps(exam):
    """{id: [ids]} each question's stem refers to (câu N / question N mapped printed->id by the
    offset line; ý (a), `kết quả câu trên`, `previous question` -> the question before)."""
    off = _OFFSET_RE.search(exam.get("instructions") or "")
    off = int(off.group(1)) if off else 0
    out, prev = {}, None
    for q in exam["questions"]:
        refs = []
        for m in _REF_RE.finditer(q.get("stem") or q["text"]):
            if m.group(1):
                refs.append(int(m.group(1)) - off)
            elif prev is not None:
                refs.append(prev)
        refs = sorted({r for r in refs if r != q["id"]})
        if refs:
            out[q["id"]] = refs
        prev = q["id"]
    return out


def labelled(exam):
    """True when the file carries group levels (instruction / passage); only then are prompts group-aware.
    Accepts an exam dict or a list of questions."""
    qs = exam if isinstance(exam, list) else exam.get("questions", [])
    return any(q.get("instruction") or q.get("passage") for q in qs)


def groups(exam):
    """Pure, derived: [{"key","kind","ids","instruction","passage"}] in exam order.

    Consecutive questions with equal (section, instruction, passage), at least one non-empty, form a
    group; any other question is its own. kind: dependent (a stem refers to another question; the
    referenced ids join the group) > passage (non-empty passage) > independent."""
    dep = deps(exam)
    known = {q["id"] for q in exam["questions"]}
    runs, last = [], None
    for q in exam["questions"]:
        sig = (q.get("section") or "", q.get("instruction") or "", _passage(q))
        if last == sig and (sig[1] or sig[2]):
            runs[-1].append(q)
        else:
            runs.append([q])
        last = sig
    out = []
    for run in runs:
        ids = [q["id"] for q in run]
        refs = sorted({r for i in ids for r in dep.get(i, ()) if r in known} - set(ids))
        pas = _passage(run[0])
        kind = "dependent" if any(i in dep for i in ids) else "passage" if pas else "independent"
        out.append({"key": "g%d" % ids[0], "kind": kind, "ids": sorted(ids + refs),
                    "instruction": run[0].get("instruction") or "", "passage": pas})
    return out

"""Shared parser for exam input/expected Markdown files (examples/FORMAT.md).

Python 3.8 stdlib only. Import from a CLI after putting this directory on sys.path.
"""
import re
import unicodedata

LEGACY_HEADINGS = ("Solution", "Explanation", "Verification", "Grading")
_QHEAD = re.compile(r"^##\s+Question\s+(\d+)\s*$")
_LEGACY_QHEAD = re.compile(r"^Question\s+(\d+)\s*$")
_HEAD = re.compile(r"^(#+)\s+(.*?)\s*$")


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return unicodedata.normalize("NFC", fh.read())


def norm(s):
    s = unicodedata.normalize("NFC", s).casefold()
    s = " ".join(s.split())
    while s.endswith("."):
        s = s[:-1].rstrip()
    return s


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


def parse_exam(path):
    text = read_text(path)
    secs = sections(text, 2)
    res = {"fields": header_fields(text), "instructions": "", "passage": "",
           "learner_answer": None, "questions": []}
    for title, body in secs:
        m = re.match(r"^Question\s+(\d+)$", title)
        if m:
            opts = {}
            lines = []
            for line in body.splitlines():
                om = re.match(r"^([A-D])\.\s+\S", line)
                if om:
                    opts[om.group(1)] = line[2:].strip()
                else:
                    lines.append(line)
            res["questions"].append({"id": int(m.group(1)),
                                     "text": "\n".join(lines).strip(),
                                     "options": opts})
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
_SUBJECTS = ("mathematics", "math", "physics", "english", "literature")
_SUPPORTED_MODES = ("Solve",)


def validate_exam(exam):
    """Errors of a parse_exam result as a list of strings (empty = valid); never raises."""
    errs = []
    fields = exam.get("fields") or {}
    for key in _REQUIRED_HEADERS:
        if not fields.get(key):
            errs.append("missing header: %s" % key)
    subj = fields.get("Subject")
    if subj and subj.strip().casefold() not in _SUBJECTS:
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
        if (mc or q["options"]) and sorted(q["options"]) != ["A", "B", "C", "D"]:
            errs.append("question %d: options must be exactly A-D" % q["id"])
    return errs

"""Human review path (TASK-052 / REQ-0055): `review-pack` writes one readable file per subject under
review/<exam-id>/ (gitignored, copyright); the user ticks a line per question; `review-apply` reads the lines
back (counts, Wilson agreement, improvements by kind). No model call; marks are never lost on a re-run."""
import json
import os
import re

from exam_engine.core import refcheck
from exam_engine.pipeline import extract_eval
from exam_engine.pipeline.reporter import _one_line

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FORBIDDEN_OUT = ("examples", "evals", "tests")
KINDS = ("extraction", "solution", "flawed", "other")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
ZWSP = "​"
TEMPLATE = ("Your review: [ ] agree [ ] disagree [ ] unsure | correct: _ | kind: %s | note: " % "|".join(KINDS))
HOWTO = ("How to review: on each question's `Your review:` line change one `[ ]` to `[x]` (agree / disagree / "
         "unsure); if you disagree type the right letter after `correct:`, keep one kind word, and add a note; "
         "then run `exam.py review-apply --exam-id %s`. Do not edit lines starting with `## Q`.")
HEAD_RE = re.compile(r"^## Q(\d+)  p\.(\S+)  (\S+)  answer (\S)  conf (\S+)\s*$")
SUBJECT_SKIP = ("INDEX.md", "improvements.md")


def _check_name(label, v):
    if not NAME_RE.match(v or ""):
        raise ValueError("%s must match [A-Za-z0-9_.-]+ (got %r)" % (label, v))
    return v


def review_dir(out, exam_id):
    """<out>/<exam-id>, refusing a location inside examples/, evals/ or tests/ of the repo."""
    d = os.path.realpath(os.path.join(out, _check_name("exam-id", exam_id)))
    for bad in FORBIDDEN_OUT:
        b = os.path.realpath(os.path.join(ROOT, bad))
        if d == b or d.startswith(b + os.sep):
            raise ValueError("refusing --out inside %s/" % bad)
    return d


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise ValueError("cannot read %s: %s" % (path, exc))


def exam_sections(path):
    """{question number (int): verbatim text} from the `## Question N` sections of an exam file."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise ValueError("cannot read %s: %s" % (path, exc))
    out = {}
    for chunk in re.split(r"(?m)^(?=## )", text):
        head, _, body = chunk.partition("\n")
        m = re.match(r"## Question\s+(\d+)\s*$", head)
        if m:
            out[int(m.group(1))] = body.strip()
    return out


def refined_info(path):
    """{printed number (str): (page, needs_review)} from an ingest-refine document."""
    from exam_engine.ingest import api
    doc = _load(path)
    return {str(q.get("id")): (q.get("page"), bool(q.get("needs_review")))
            for q in api.refined_questions(doc if isinstance(doc, dict) else {})}


def _guard(text):
    """Exam text is data: no line may open a section or fake a review line."""
    return "\n".join(ZWSP + ln if ln.startswith(("#", "Your review:", "Engine:", "Flags:")) else ln
                     for ln in text.split("\n"))


def _flags(q, stem, needs_review):
    f = []
    if refcheck.marker_reasons(stem) is not None:
        f.append("incomplete")
    if needs_review:
        f.append("needs_review")
    if any(c.get("kind") == "quote" and c.get("result") == "fail" for c in q.get("checks") or []):
        f.append("quote_fail")
    if q.get("answer") is None:
        f.append("declined")
    return ",".join(f) or "none"


def _conf(q):
    lv = str((q.get("uncertainty") or {}).get("level") or "").lower()
    return {"low": "high", "medium": "medium", "high": "low"}.get(lv, "low")


def _engine_line(q):
    steps = [s for s in (q.get("solution") or []) if str(s).strip()][:3]
    txt = " / ".join(_one_line(s) for s in steps) or _one_line(q.get("explanation"))
    return "Engine: " + (txt[:400] or "-")


def build_sections(result, exam, refined, offset):
    """[(printed n, header dict, markdown lines)] in result order."""
    secs = []
    for q in result.get("questions") or []:
        try:
            k = int(q["id"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("result question id %r is not a number" % (q.get("id"),))
        n = k + offset
        stem = exam.get(k, "(question text not found in the exam file)")
        page, nr = refined.get(str(n), ("-", False))
        h = {"n": n, "page": "-" if page is None else str(page),
             "status": str(q.get("verification_status") or "-"),
             "answer": q["answer"] if q.get("answer") in ("A", "B", "C", "D") else "-",
             "conf": _conf(q), "flags": _flags(q, stem, nr)}
        lines = ["## Q%d  p.%s  %s  answer %s  conf %s" % (n, h["page"], h["status"], h["answer"], h["conf"]),
                 "", _guard(stem), "", _engine_line(q), "Flags: " + h["flags"], TEMPLATE, ""]
        secs.append((n, h, lines))
    return secs


def parse_subject(text):
    """[{n, page, status, answer, conf, flags, review}] where review is the raw `Your review:` line or None."""
    rows, cur = [], None
    for ln in text.split("\n"):
        m = HEAD_RE.match(ln)
        if m:
            cur = {"n": int(m.group(1)), "page": m.group(2), "status": m.group(3), "answer": m.group(4),
                   "conf": m.group(5), "flags": "none", "review": None}
            rows.append(cur)
        elif cur is not None:
            if ln.startswith("Flags: "):
                cur["flags"] = ln[7:].strip() or "none"
            elif ln.startswith("Your review:") and cur["review"] is None:
                cur["review"] = ln.rstrip()
    return rows


BOX_RE = re.compile(r"\[([^\]]*)\]\s*(agree|disagree|unsure)\b")


def parse_review(line):
    """(state, correct, kind): state blank|agree|disagree|unsure|unparsed; never guesses."""
    if line is None or line.strip() == TEMPLATE.strip():
        return ("blank", None, None)
    parts = [p.strip() for p in line[len("Your review:"):].split("|")]
    boxes = BOX_RE.findall(parts[0]) if parts else []
    if [w for _, w in boxes] != ["agree", "disagree", "unsure"] or any(b not in (" ", "", "x", "X") for b, _ in boxes):
        return ("unparsed", None, None)
    ticked = [w for b, w in boxes if b in ("x", "X")]
    val = {}
    for p in parts[1:]:
        k, _, v = p.partition(":")
        val.setdefault(k.strip().lower(), v.strip())
    correct = val.get("correct", "_")
    if correct in ("", "_"):
        correct = None
    elif correct not in ("A", "B", "C", "D", "-"):
        return ("unparsed", None, None)
    kv = val.get("kind", "")
    found = [w for w in re.findall(r"[a-z]+", kv.lower()) if w in KINDS]
    kind = None
    if len(set(found)) == 1 and len(re.findall(r"[a-z]+", kv.lower())) == len(found):
        kind = found[0]
    elif kv and (not found or set(found) != set(KINDS)):
        return ("unparsed", None, None)
    if len(ticked) > 1:
        return ("unparsed", None, None)
    if not ticked:
        return ("blank", None, None) if correct is None and kind is None else ("unparsed", None, None)
    return (ticked[0], correct, kind)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _subject_files(d):
    return sorted(f for f in os.listdir(d) if f.endswith(".md") and f not in SUBJECT_SKIP
                  and not f.endswith(".new.md"))


def pack(exam_id, subject, result_path, exam_path, refined_path=None, offset=0, out="review",
         force_reset=False):
    """Write <out>/<exam-id>/<subject>.md and regenerate INDEX.md; returns (path, message)."""
    _check_name("subject", subject)
    d = review_dir(out, exam_id)
    secs = build_sections(_load(result_path), exam_sections(exam_path),
                          refined_info(refined_path) if refined_path else {}, offset)
    path = os.path.join(d, subject + ".md")
    old = {}
    if os.path.exists(path) and not force_reset:
        with open(path, encoding="utf-8") as fh:
            old = {r["n"]: r["review"] for r in parse_subject(fh.read())
                   if r["review"] is not None and r["review"].strip() != TEMPLATE.strip()}
    new_ns = {n for n, _, _ in secs}
    lost = sorted(set(old) - new_ns)
    msg = "wrote %s (%d questions)" % (path, len(secs))
    if lost:
        path = os.path.join(d, subject + ".new.md")
        msg = "kept your marks in %s.md (Q%s not in the new pack); wrote %s instead" % (
            subject, ",".join(map(str, lost)), path)
        old = {}
    elif old:
        msg += "; merged %d existing marks by printed number" % len(old)
    body = ["# %s - %s" % (exam_id, subject), "", HOWTO % exam_id, ""]
    for n, _, lines in secs:
        body += [(old[n] if (n in old and l == TEMPLATE) else l) for l in lines]
    _write(path, "\n".join(body))
    write_index(d, exam_id)
    return path, msg


def write_index(d, exam_id):
    rows = []
    for f in _subject_files(d):
        with open(os.path.join(d, f), encoding="utf-8") as fh:
            rows.append((f[:-3], parse_subject(fh.read())))
    rows.sort(key=lambda s: (min([r["n"] for r in s[1]] or [0]), s[0]))
    md = ["# Review index - %s" % exam_id, "", HOWTO % exam_id, "",
          "| subject | n | page | status | answer | conf | flags | review |", "|---|---|---|---|---|---|---|---|"]
    tot = {}
    for sub, rs in rows:
        for r in rs:
            st = parse_review(r["review"])[0]
            tot[sub] = tot.setdefault(sub, {})
            tot[sub][st] = tot[sub].get(st, 0) + 1
            md.append("| %s | %d | %s | %s | %s | %s | %s | %s |" % (
                sub, r["n"], r["page"], r["status"], r["answer"], r["conf"], r["flags"], st))
    md += ["", "Totals (review state per subject):"]
    for sub, rs in rows:
        c = tot.get(sub, {})
        md.append("- %s: %d questions; %s" % (sub, len(rs), ", ".join(
            "%s %d" % (s, c.get(s, 0)) for s in ("blank", "agree", "disagree", "unsure", "unparsed"))))
    _write(os.path.join(d, "INDEX.md"), "\n".join(md) + "\n")


def apply(exam_id, out="review"):
    """Read every subject file; returns (report lines, summary dict). Writes improvements.md."""
    d = review_dir(out, exam_id)
    if not os.path.isdir(d):
        raise ValueError("no review folder %s (run review-pack first)" % d)
    lines, imp, summary = [], {}, {}
    unparsed_all, unsure_all = [], []
    for f in _subject_files(d):
        sub = f[:-3]
        with open(os.path.join(d, f), encoding="utf-8") as fh:
            rs = parse_subject(fh.read())
        c = {"blank": 0, "agree": 0, "disagree": 0, "unsure": 0, "unparsed": 0}
        dis, doubt, unp = [], [], []
        for r in rs:
            st, corr, kind = parse_review(r["review"])
            c[st] += 1
            if st == "disagree":
                dis.append((r["n"], kind or "unspecified", corr))
                imp.setdefault(kind or "unspecified", []).append((sub, r["n"]))
            elif st == "agree" and (r["conf"] == "low" or r["flags"] != "none"):
                doubt.append(r["n"])
            elif st == "unsure":
                unsure_all.append((sub, r["n"]))
            elif st == "unparsed":
                unp.append(r["n"])
                unparsed_all.append((sub, r["n"]))
        rev = c["agree"] + c["disagree"] + c["unsure"]
        w = extract_eval.wilson(c["agree"], rev)
        agr = ("agreement %d/%d = %.1f%% (Wilson 95%% %.1f-%.1f%%)" % (
            c["agree"], rev, 100.0 * c["agree"] / rev, 100 * w[0], 100 * w[1])) if rev else "agreement n/a (0 reviewed)"
        lines.append("%s: %d questions; agree %d, disagree %d, unsure %d, blank %d, unparsed %d; %s" % (
            sub, len(rs), c["agree"], c["disagree"], c["unsure"], c["blank"], c["unparsed"], agr))
        if dis:
            lines.append("  disagreements: " + ", ".join("Q%d (%s%s)" % (n, k, ", correct " + o if o else "")
                                                         for n, k, o in dis))
        if doubt:
            lines.append("  agreed but engine doubtful: " + ", ".join("Q%d" % n for n in doubt))
        if unp:
            lines.append("  unparsed: " + ", ".join("Q%d" % n for n in unp))
        summary[sub] = dict(c, n=len(rs))
    md = ["# Improvements from review - %s" % exam_id, "", "Question numbers and kinds only (no question text).", ""]
    for kind in list(KINDS) + ["unspecified"]:
        if kind in imp:
            md.append("- %s: %s" % (kind, ", ".join("%s Q%d" % x for x in imp[kind])))
    if unsure_all:
        md.append("- unsure: " + ", ".join("%s Q%d" % x for x in unsure_all))
    if unparsed_all:
        md.append("- unparsed (fix the line): " + ", ".join("%s Q%d" % x for x in unparsed_all))
    if len(md) == 4:
        md.append("- nothing to improve yet")
    _write(os.path.join(d, "improvements.md"), "\n".join(md) + "\n")
    return lines, summary

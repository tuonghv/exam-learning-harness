"""Human review path (TASK-052 / REQ-0055): `review-pack` writes one readable file per subject under
review/<exam-id>/ (gitignored, copyright); the user ticks a line per question; `review-apply` reads the lines
back (counts, Wilson agreement, improvements by kind). No model call; marks are never lost on a re-run."""
import json
import os
import re
import unicodedata

from exam_engine.core import refcheck
from exam_engine.pipeline import extract_eval, verifier
from exam_engine.pipeline.reporter import _one_line

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FORBIDDEN_OUT = ("examples", "evals", "tests")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
ZWSP = "​"
PREFIX = "Your review: extraction"
TEMPLATE = ("Your review: extraction [ ] ok [ ] defect | solution (optional) [ ] agree [ ] disagree [ ] unsure"
            " | correct: _ | note: ")
HOWTO = ("How to review: you review the EXTRACTION (is the question text and every option as in the exam?). "
         "On each `Your review:` line change one `[ ]` after `extraction` to `[x]` (ok / defect) and add a note for "
         "a defect. The answer is the QA's job; reading the solution is optional (then tick agree / disagree / "
         "unsure, and type the right letter after `correct:`). Then run `exam.py review-apply --exam-id %s`. "
         "Do not edit lines starting with `## Q`.")
HEAD_RE = re.compile(r"^## Q(\d+)  p\.(\S+)  (\S+)  answer (\S)  conf (\S+)\s*$")
LOOSE_RE = re.compile(r"^##\s*Q?\s*(\d+)")
QA_HEAD = ("QA: in-session independent reads of the source (same model family as the engine: not an official "
           "key, agreement is not proof). You review the extraction; the answer is QA's job. Verdicts: agrees, "
           "differs, flawed, qa-only, unresolved, engine-nonletter.")
QA_RE = re.compile(r"^QA: (\S+) conf (\S+) \| ([^|]+?) \|")
VERDICTS = ("agrees", "differs", "flawed", "qa-only", "unresolved", "engine-nonletter")
OPT_RE = re.compile(r"(?m)^\s*\(?([A-D])[.)]\s*(.+?)\s*$")
QA_HEADER_CELLS = ("n", "#", "no", "no.", "q", "number")
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
    a = q.get("answer")
    pre = "answer %s; " % _one_line(a)[:80] if a is not None and a not in ("A", "B", "C", "D") else ""
    return "Engine: " + pre + (txt[:400] or "-")


def parse_qa(paths):
    """({printed n: {answer, conf, flawed, why}}, [unparsed row descriptions]): pipe tables, later files win,
    header/separator rows and prose skipped, a malformed row is listed, never guessed."""
    rows, bad = {}, []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().split("\n")
        except OSError as exc:
            raise ValueError("cannot read %s: %s" % (path, exc))
        base = os.path.basename(path)
        for i, ln in enumerate(lines, 1):
            if "|" not in ln:
                continue
            cells = [c.strip() for c in ln.strip().split("|")]
            if cells and cells[0] == "":
                cells = cells[1:]
            if cells and cells[-1] == "":
                cells = cells[:-1]
            if not cells or set("".join(cells)) <= set("-: "):
                continue
            if cells[0].lower() in QA_HEADER_CELLS:
                continue
            ans = cells[1].upper() if len(cells) > 1 else ""
            if not cells[0].isdigit() or ans not in ("A", "B", "C", "D", "-"):
                bad.append("%s:%d" % (base, i))
                continue
            rest = cells[3:]
            fl = rest[0].lower() if len(rest) > 1 else ""  # 4 columns: the 4th is the note, no flawed column
            flawed = fl.startswith(("yes", "mild")) if fl.split(" ")[0] in ("yes", "no", "mild") else False
            if fl.split(" ")[0] in ("yes", "no", "mild"):
                rest = rest[1:]
            rows[int(cells[0])] = {"answer": ans, "conf": (cells[2] if len(cells) > 2 and cells[2] else "-"),
                                   "flawed": flawed, "why": _one_line(" | ".join(rest))[:300] or "-"}
    return rows, bad


def verdict_text(engine, qa):
    """Verdict plus, for a flawed question whose engine and QA letters both exist and differ, the pair."""
    v = qa_verdict(engine, qa)
    if v == "flawed" and engine in ("A", "B", "C", "D") and qa["answer"] in ("A", "B", "C", "D") \
            and engine != qa["answer"]:
        return "flawed (engine %s vs QA %s)" % (engine, qa["answer"])
    return v


def _norm_value(t):
    t = unicodedata.normalize("NFC", str(t)).lower()
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    return re.sub(r"[^\w.\-]|_", "", t).strip(".")


def value_letter(answer, stem):
    """Letter of the single option whose text equals the engine's value answer, else None."""
    v = _norm_value(answer)
    hits = [m.group(1) for m in OPT_RE.finditer(stem) if v and _norm_value(m.group(2)) == v]
    if len(hits) == 1:
        return hits[0]
    if hits:
        return None
    # value + trailing note, "12,7" vs "12.7%": same number rule as the solver (60.1, D4)
    opts = {m.group(1): m.group(2) for m in OPT_RE.finditer(stem)}
    return verifier.option_for_value(answer, opts)


def qa_verdict(engine, qa):
    if qa["flawed"]:
        return "flawed"
    if qa["answer"] == "-":
        return "unresolved"
    if engine == "-":
        return "qa-only"
    if engine not in ("A", "B", "C", "D"):
        return "engine-nonletter"
    return "agrees" if engine == qa["answer"] else "differs"


def _parse_qaline(ln):
    """Kept QA line back to a qa row (verdict is recomputed from the current engine answer; flawed round-trips
    as the verdict `flawed`), None for `QA: -` or a line not in our format."""
    m = QA_RE.match(ln or "")
    if not m:
        return None
    return {"answer": m.group(1), "conf": m.group(2), "flawed": m.group(3).split(" ")[0] == "flawed",
            "why": ln.split(" | ", 2)[2] if ln.count(" | ") >= 2 else "-"}


def build_sections(result, exam, refined, offset, qa=None, keep=None):
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
             "answer": q["answer"] if q.get("answer") in ("A", "B", "C", "D") else ("-" if q.get("answer") is None else "?"),
             "conf": _conf(q), "flags": _flags(q, stem, nr)}
        h["eff"] = h["answer"]
        if h["answer"] == "?":
            h["eff"] = value_letter(q["answer"], stem) or "?"
        qline = "QA: -"
        x = qa[n] if qa and n in qa else (keep or {}).get(n)
        if x:
            qline = "QA: %s conf %s | %s | %s" % (x["answer"], x["conf"].replace(" ", "_"),
                                                  verdict_text(h["eff"], x), x["why"])
        lines = ["## Q%d  p.%s  %s  answer %s  conf %s" % (n, h["page"], h["status"], h["answer"], h["conf"]),
                 "", _guard(stem), "", _engine_line(q), qline, "Flags: " + h["flags"], TEMPLATE, ""]
        secs.append((n, h, lines))
    return secs


def parse_subject(text):
    """[{n, page, status, answer, conf, flags, review, changed, bad}]: review is the raw `Your review:` line or
    None; bad = heading edited (n kept) or unnumbered `## ` section (n None)."""
    rows, cur = [], None
    for ln in text.split("\n"):
        if ln.startswith("## "):
            m, lm = HEAD_RE.match(ln), LOOSE_RE.match(ln)
            cur = {"n": int((m or lm).group(1)) if (m or lm) else None, "page": "-", "status": "-",
                   "answer": "-", "conf": "-", "flags": "none", "qa": "-", "verdict": "-", "vfull": "-", "review": None, "changed": None,
                   "bad": not m, "qaline": None}
            if m:
                cur.update(page=m.group(2), status=m.group(3), answer=m.group(4), conf=m.group(5))
            rows.append(cur)
        elif cur is not None:
            if ln.startswith("QA: "):
                cur["qaline"] = ln.rstrip()
                qm = QA_RE.match(ln)
                if qm:
                    cur["qa"], cur["verdict"] = qm.group(1), qm.group(3).split(" ")[0]
                    cur["vfull"] = qm.group(3)
            elif ln.startswith("Flags: "):
                cur["flags"] = ln[7:].strip() or "none"
            elif ln.startswith("Answer changed:"):
                cur["changed"] = ln.rstrip()
            elif ln.startswith("Your review:") and cur["review"] is None:
                cur["review"] = ln.rstrip()
    return rows


BOX_RE = re.compile(r"\[([^\]]*)\]\s*([a-z]+)")


def _group(seg, words):
    """Ticked word of one box group, "" when none, None when malformed."""
    boxes = BOX_RE.findall(seg)
    if [w for _, w in boxes] != list(words) or any(b not in (" ", "", "x", "X") for b, _ in boxes):
        return None
    ticked = [w for b, w in boxes if b in ("x", "X")]
    return ticked[0] if len(ticked) == 1 else ("" if not ticked else None)


def parse_review(line):
    """(extraction, solution, correct, note): extraction blank|ok|defect|unparsed, solution
    blank|agree|disagree|unsure|unparsed; a line not in the current format is unparsed, never guessed."""
    bad = ("unparsed", "unparsed", None, "")
    if line is None or not line.startswith(PREFIX):
        return bad
    parts = line.split("|", 3)
    if len(parts) < 4 or not parts[1].strip().startswith("solution (optional)"):
        return bad
    ext = _group(parts[0][len(PREFIX):], ("ok", "defect"))
    sol = _group(parts[1], ("agree", "disagree", "unsure"))
    c = parts[2].partition(":")
    correct = c[2].strip().upper()
    if c[0].strip() != "correct" or correct not in ("", "_", "A", "B", "C", "D", "-"):
        return bad
    n = parts[3].partition(":")
    if n[0].strip() != "note" or ext is None or sol is None:
        return bad
    return (ext or "blank", sol or "blank", None if correct in ("", "_") else correct, n[2].strip())


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _subject_files(d):
    return sorted(f for f in os.listdir(d) if f.endswith(".md") and f not in SUBJECT_SKIP
                  and not f.endswith(".new.md"))


def _is_marked(r):
    return r["review"] is not None and r["review"].startswith(PREFIX) and r["review"].strip() != TEMPLATE.strip()


def pack(exam_id, subject, result_path, exam_path, refined_path=None, offset=0, out="review",
         force_reset=False, note="", qa_files=None):
    """Write <out>/<exam-id>/<subject>.md and regenerate INDEX.md; returns (path, message)."""
    _check_name("subject", subject)
    d = review_dir(out, exam_id)
    qa, qa_bad = parse_qa(qa_files or [])
    result, exam = _load(result_path), exam_sections(exam_path)
    refined = refined_info(refined_path) if refined_path else {}
    path = os.path.join(d, subject + ".md")
    old, olds, keep = {}, {}, {}
    if os.path.exists(path) and not force_reset:
        with open(path, encoding="utf-8") as fh:
            rows = parse_subject(fh.read())
        olds = {r["n"]: r for r in rows if r["n"] is not None}
        old = {n: r for n, r in olds.items() if _is_marked(r)}
        keep = {n: x for n, x in ((n, _parse_qaline(r["qaline"])) for n, r in olds.items()) if x}
        # a mark in the previous format cannot be merged; keep the whole old file beside the new one
        legacy = [r for r in rows if r["review"] and not r["review"].startswith(PREFIX)
                  and "[x]" in r["review"].lower()]
        if legacy:
            os.makedirs(d, exist_ok=True)
            with open(path, encoding="utf-8") as src, open(os.path.join(d, subject + ".old.md"), "w",
                                                          encoding="utf-8") as dst:
                dst.write(src.read())
    secs = build_sections(result, exam, refined, offset, qa, keep)
    unmatched = sorted(set(qa) - {n for n, _, _ in secs})
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
    if qa_files or keep:
        body += [QA_HEAD, ""]
    if note:
        body += ["Note: " + _one_line(note), ""]
    changed = 0
    for n, h, lines in secs:
        o = old.get(n)
        out_lines = []
        for l in lines:
            if l == TEMPLATE and o:
                if o["changed"] and o["answer"] == h["answer"]:
                    out_lines.append(o["changed"])
                elif o["answer"] != h["answer"]:
                    out_lines.append("Answer changed: was %s now %s" % (o["answer"], h["answer"]))
                    changed += 1
                out_lines.append(o["review"])
            else:
                out_lines.append(l)
        body += out_lines
    if qa_files:
        cnt = dict.fromkeys(VERDICTS, 0)
        for n, h, _ in secs:
            if n in qa:
                cnt[qa_verdict(h["eff"], qa[n])] += 1
        msg += "; QA " + ", ".join("%s %d" % (v, cnt[v]) for v in VERDICTS if cnt[v] or v != "engine-nonletter")
        msg += "; qa_unmatched %d%s" % (len(unmatched), " (%s)" % ",".join(map(str, unmatched)) if unmatched else "")
        msg += "; qa_unparsed %d%s" % (len(qa_bad), " (%s)" % ", ".join(qa_bad) if qa_bad else "")
    if changed:
        msg += "; %d marked answers changed (flagged)" % changed
    _write(path, "\n".join(body))
    write_index(d, exam_id)
    return path, msg


def _state(r):
    ext, sol, _, _ = parse_review(r["review"])
    return ext, sol


def _verdict_counts(rs):
    c = [(v, sum(1 for r in rs if r["verdict"] == v)) for v in VERDICTS]
    c.append(("flawed_differs", sum(1 for r in rs if r["vfull"].startswith("flawed ("))))
    return ", ".join("%s %d" % (v, k) for v, k in c if k or v not in ("engine-nonletter", "flawed_differs"))


def write_index(d, exam_id):
    rows = []
    for f in _subject_files(d):
        with open(os.path.join(d, f), encoding="utf-8") as fh:
            rows.append((f[:-3], parse_subject(fh.read())))
    rows.sort(key=lambda s: (min([r["n"] for r in s[1] if r["n"] is not None] or [0]), s[0]))
    has_qa = any(r["qa"] != "-" for _, rs in rows for r in rs)
    md = ["# Review index - %s" % exam_id, "", HOWTO % exam_id, "",
          "| subject | n | page | status | answer | conf | flags | extraction | solution |"
          + (" qa | verdict |" if has_qa else ""),
          "|---|---|---|---|---|---|---|---|---|" + ("---|---|" if has_qa else "")]
    tot = {}
    for sub, rs in rows:
        c = tot.setdefault(sub, {})
        for r in rs:
            ext, sol = _state(r)
            c[ext] = c.get(ext, 0) + 1
            fl = [r["flags"]] if r["flags"] != "none" else []
            if r["changed"]:
                fl.append("answer_changed")
            if r["bad"]:
                fl.append("heading_edited")
            md.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                sub, "?" if r["n"] is None else r["n"], r["page"], r["status"], r["answer"], r["conf"],
                ",".join(fl) or "none", ext, sol) + (" %s | %s |" % (r["qa"], r["vfull"]) if has_qa else ""))
    md += ["", "Totals (extraction review state per subject):"]
    for sub, rs in rows:
        c = tot.get(sub, {})
        md.append("- %s: %d sections; %s" % (sub, len(rs), ", ".join(
            "%s %d" % (s, c.get(s, 0)) for s in ("blank", "ok", "defect", "unparsed"))))
    if has_qa:
        md += ["", "QA verdicts per subject (same-family independent reads, not an official key):"]
        for sub, rs in rows:
            md.append("- %s: %s" % (sub, _verdict_counts(rs)))
    _write(os.path.join(d, "INDEX.md"), "\n".join(md) + "\n")


def _pct(k, n):
    w = extract_eval.wilson(k, n)
    return ("%d/%d = %.1f%% (Wilson 95%% %.1f-%.1f%%)" % (k, n, 100.0 * k / n, 100 * w[0], 100 * w[1])
            if n else "n/a (0 reviewed)")


def apply(exam_id, out="review"):
    """Read every subject file; returns (report lines, summary dict). Writes improvements.md."""
    d = review_dir(out, exam_id)
    if not os.path.isdir(d):
        raise ValueError("no review folder %s (run review-pack first)" % d)
    lines, summary = [], {}
    defects, sdis, sunsure, unp, edited, secbad = [], [], [], [], [], []
    for f in _subject_files(d):
        sub = f[:-3]
        with open(os.path.join(d, f), encoding="utf-8") as fh:
            rs = parse_subject(fh.read())
        e = {"blank": 0, "ok": 0, "defect": 0, "unparsed": 0}
        s = {"blank": 0, "agree": 0, "disagree": 0, "unsure": 0, "unparsed": 0}
        dl, chg = [], []
        for r in rs:
            ext, sol, corr, nt = parse_review(r["review"])
            e[ext] += 1
            s[sol] += 1
            tag = "%s Q%s" % (sub, r["n"])
            if r["n"] is None:
                secbad.append(sub)
            elif r["bad"]:
                edited.append(tag)
            if ext == "defect":
                dl.append("Q%d%s" % (r["n"], " (%s)" % nt if nt else ""))
                defects.append(tag)
            if sol == "disagree":
                sdis.append("%s%s" % (tag, " correct " + corr if corr else ""))
            elif sol == "unsure":
                sunsure.append(tag)
            if "unparsed" in (ext, sol):
                unp.append(tag)
            if r["changed"]:
                chg.append("  %s: %s" % (tag, r["changed"]))
        lines.append("%s: %d sections; extraction ok %d, defect %d, blank %d, unparsed %d; extraction ok rate %s; "
                     "solution (optional) agree %d, disagree %d, unsure %d" % (
                         sub, len(rs), e["ok"], e["defect"], e["blank"], e["unparsed"],
                         _pct(e["ok"], e["ok"] + e["defect"]), s["agree"], s["disagree"], s["unsure"]))
        if dl:
            lines.append("  extraction defects: " + ", ".join(dl))
        lines += chg
        if any(r["qa"] != "-" for r in rs):
            lines.append("  QA verdicts: " + _verdict_counts(rs))
        summary[sub] = dict(e, n=len(rs), **{"sol_" + k: v for k, v in s.items()})
    if edited:
        lines.append("heading edited (marks kept by number): " + ", ".join(edited))
    if secbad:
        lines.append("unparsed section (unnumbered `## ` heading): in " + ", ".join(sorted(set(secbad))))
    md = ["# Improvements from review - %s" % exam_id, "",
          "Question numbers only (no question text, no notes).", ""]
    if defects:
        md.append("- extraction defects: " + ", ".join(defects))
    if sdis:
        md.append("- solution disagreements: " + ", ".join(sdis))
    if sunsure:
        md.append("- solution unsure: " + ", ".join(sunsure))
    if unp:
        md.append("- unparsed (fix the line): " + ", ".join(unp))
    if secbad:
        md.append("- unparsed section: " + ", ".join(sorted(set(secbad))))
    if len(md) == 4:
        md.append("- nothing to improve yet")
    _write(os.path.join(d, "improvements.md"), "\n".join(md) + "\n")
    return lines, summary

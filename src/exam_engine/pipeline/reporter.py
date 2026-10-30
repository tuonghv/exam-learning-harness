#!/usr/bin/env python3
"""Report stage: result dict -> report.md, report.html, report.pdf (best effort).

All model text is data: it is escaped by md2html and never executed. The PDF
needs a local renderer (Chrome, weasyprint, wkhtmltopdf); without one the HTML
is kept and report.md says so. Nothing here raises on a render problem.
Library only; engine.run calls write_reports().
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from exam_engine.core.decision import KINDS, evidence_kind  # noqa: F401
from exam_engine.utils import md2html
from exam_engine.utils.text import detect_lang

CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
NO_RENDERER = "no PDF renderer found (Chrome, weasyprint, wkhtmltopdf); HTML kept"
ZWSP = "\u200b"
CIRCLED = {"A": "\u24b6", "B": "\u24b7", "C": "\u24b8", "D": "\u24b9"}
DASH = "\u2014"
VIEWS = ("sheet", "learn")


def _one_line(text):
    """One line of model text. A zero-width space before a leading markdown marker
    (fence, heading, list, quote) and inside `**` keeps the model from opening
    structure or faking a verdict pill; the visible text is unchanged."""
    t = " ".join(str(text if text is not None else "").split())
    t = re.sub(r"^([#>`~|+*-]+|\d+[.)])", lambda m: ZWSP + m.group(1), t)
    return t.replace("**", "*" + ZWSP + "*")


def _cell(text):
    """Table cell: one line, pipes escaped so the model cannot add columns."""
    return _one_line(text).replace("\\", "\\\\").replace("|", "\\|") or "-"


def _is_open(q, exam):
    return q.get("answer") == "Open" or str(exam.get("task") or "").strip().lower() == "literature"


def _num(x):
    return "-" if x is None else ("%g" % x)


def _sheet_id(qid):
    """Question id as stored; pure digits are zero-padded to 2 ("7" -> "07")."""
    s = _one_line(qid)
    if re.fullmatch(r"[0-9]+", s):
        return s.zfill(2)
    return s or "?"


def _sheet_mark(q, exam):
    """Circled A-D, else a dash (null, Open, anything that is not exactly A-D)."""
    if _is_open(q, exam):
        return DASH
    a = q.get("answer")
    return CIRCLED.get(a.strip(), DASH) if isinstance(a, str) else DASH


def _pad(mark, w):
    """Pad a mark to w columns; circled letters render 2 columns wide (Noto Mono CJK in the PDF)."""
    return mark + " " * (w - (2 if mark in CIRCLED.values() else 1))


def build_answer_sheet(result):
    """Fenced monospace answer grid: 5 questions per row, ids over circled letters."""
    exam, qs = result["exam"], result["questions"]
    out = ["```text", "%s \u2013 %d Questions" % (_one_line(exam.get("subject")) or "Exam", len(qs))]
    ids = [_sheet_id(q["id"]) for q in qs]
    marks = [_sheet_mark(q, exam) for q in qs]
    w = max([2] + [len(i) for i in ids])
    for k in range(0, len(qs), 5):
        out += ["", "   ".join(i.ljust(w) for i in ids[k:k + 5]).rstrip(),
                "   ".join(_pad(m, w) for m in marks[k:k + 5]).rstrip()]
    return "\n".join(out + ["```"]) + "\n"


LABELS = {
    "en": {"title": "Learning view", "question": "Question", "answer": "Answer",
           "open": "Open (needs a human rubric)", "verdict": "verdict", "why": "Why",
           "steps": "Steps", "key_concept": "Key concept", "common_mistake": "Common mistake"},
    "vi": {"title": "Ph\u1ea7n h\u1ecdc", "question": "C\u00e2u", "answer": "\u0110\u00e1p \u00e1n",
           "open": "M\u1edf (c\u1ea7n ch\u1ea5m theo thang \u0111i\u1ec3m)", "verdict": "k\u1ebft qu\u1ea3",
           "why": "V\u00ec sao", "steps": "C\u00e1c b\u01b0\u1edbc",
           "key_concept": "Kh\u00e1i ni\u1ec7m ch\u00ednh", "common_mistake": "L\u1ed7i th\u01b0\u1eddng g\u1eb7p"},
}


def learn_lang(result):
    """Label language: the result's own vi|en, else detected from its explanation text."""
    lang = (result.get("exam") or {}).get("language")
    if lang in LABELS:
        return lang
    parts = []
    for q in result.get("questions", []):
        parts += [q.get("explanation") or ""] + list(q.get("solution") or [])
    return detect_lang(" ".join(parts))


def build_learning_view(result):
    """Markdown study view: the engine's answer, why, steps; verdict only when not PASS."""
    exam = result["exam"]
    L = LABELS[learn_lang(result)]
    md = ["## %s" % L["title"], ""]
    for q in result["questions"]:
        md += ["### %s %s" % (L["question"], _sheet_id(q["id"])), ""]
        if _is_open(q, exam):
            ans = L["open"]
        else:
            mark = _sheet_mark(q, exam)
            ans = mark if mark == DASH else "%s (%s)" % (mark, q["answer"].strip())
        if q["verification_status"] != "PASS":
            ans += " %s %s %s" % (DASH, L["verdict"], q["verification_status"])
        md.append("- %s: %s" % (L["answer"], ans))
        if q.get("explanation"):
            md.append("- %s: %s" % (L["why"], _one_line(q["explanation"])))
        if q.get("solution"):
            md.append("- %s:" % L["steps"])
            md += ["  %d. %s" % (n, _one_line(t)) for n, t in enumerate(q["solution"], 1)]
        if q.get("key_concept"):
            md.append("- %s: %s" % (L["key_concept"], _one_line(q["key_concept"])))
        if q.get("common_mistake"):
            md.append("- %s: %s" % (L["common_mistake"], _one_line(q["common_mistake"])))
        md.append("")
    return "\n".join(md)


def _compose(result, view):
    """report.md text: the title, then the chosen view, then the full body."""
    body = build_markdown(result)
    title, rest = body.split("\n", 1)
    block = ("## Answer sheet\n\n" + build_answer_sheet(result)) if view == "sheet" \
        else build_learning_view(result)
    return title + "\n\n" + block + "\n" + rest.lstrip("\n")


def build_markdown(result):
    exam, run, s = result["exam"], result["run"], result["summary"]
    md = ["# Exam report: %s" % _one_line(exam.get("subject") or exam.get("path")), ""]
    md.append("- Exam: %s, %s, %s, task %s, mode %s" % (
        _one_line(exam.get("subject")), _one_line(exam.get("level")),
        _one_line(exam.get("exam_type")), _one_line(exam.get("task")), _one_line(exam.get("mode"))))
    md.append("- Run: %s (%s), %d call(s), cost $%.4f%s" % (
        run.get("llm"), _one_line(run.get("model")), run.get("calls", 0), run.get("cost_usd", 0),
        ", stopped: %s" % _one_line(run["stopped"]) if run.get("stopped") else ""))
    md.append("- Totals: PASS %d, FAIL %d, UNCERTAIN %d, unresolved %d" % (
        s["pass"], s["fail"], s["uncertain"], s["unresolved"]))
    if s.get("points") is not None or s.get("max_points") is not None:
        md.append("- Points: %s / %s" % (_num(s.get("points")), _num(s.get("max_points"))))
    md.append("")
    for q in result["questions"]:
        verdict = q["verification_status"]
        opened = _is_open(q, exam)
        md += ["## Question %s" % _one_line(q["id"]), ""]
        md.append("- Answer: %s" % ("Open (needs a human rubric)" if opened else
                                    _one_line(q.get("answer")) or "none"))
        md.append("- Verdict: **%s**" % verdict)
        md.append("- Reason: %s" % (_one_line(q.get("status_reason")) or "-"))
        md.append("- Evidence: %s" % (q.get("evidence_kind") or evidence_kind(q)))
        sc = q.get("score") or {}
        md.append("- Score: %s / %s (%s)" % (_num(sc.get("points")), _num(sc.get("max")),
                                              _one_line(sc.get("basis"))))
        if opened:
            md.append("- Open question: no automatic score; a human rubric is needed.")
        if q.get("error"):
            md.append("- Error: %s: %s" % (_one_line(q["error"].get("cls")),
                                           _one_line(q["error"].get("message"))))
        md.append("")
        if q.get("checks"):
            md += ["| Check | Result | Independent | Detail |", "| --- | --- | --- | --- |"]
            for c in q["checks"]:
                md.append("| %s | %s | %s | %s |" % (
                    _cell(c.get("kind")), _cell(c.get("result")),
                    "yes" if c.get("independent") else "no", _cell(c.get("detail"))))
            md.append("")
        if q.get("qa_findings"):
            md += ["### QA findings", ""]
            md += ["- %s / %s: %s" % (_one_line(f.get("source")), _one_line(f.get("code")),
                                      _one_line(f.get("message"))) for f in q["qa_findings"]]
            md.append("")
        if q.get("explanation"):
            md += ["### Explanation", "", _one_line(q["explanation"]), ""]
        if q.get("solution"):
            md += ["### Solution", ""]
            md += ["%d. %s" % (n, _one_line(t)) for n, t in enumerate(q["solution"], 1)]
            md.append("")
        u = q.get("uncertainty") or {}
        md += ["### Uncertainty", "", "%s: %s" % (_one_line(u.get("level")) or "-",
                                                  _one_line(u.get("reason")) or "-"), ""]
    return "\n".join(md).rstrip("\n") + "\n"


def find_pdf_renderer(env=None, which=shutil.which):
    """("chrome"|"weasyprint"|"wkhtmltopdf", path) or None. CHROME_BIN wins."""
    env = os.environ if env is None else env
    forced = env.get("CHROME_BIN")
    if forced and which(forced):
        return ("chrome", which(forced))
    for name in CHROME_NAMES:
        p = which(name)
        if p:
            return ("chrome", p)
    for name in ("weasyprint", "wkhtmltopdf"):
        p = which(name)
        if p:
            return (name, p)
    return None


def _pdf_ok(pdf):
    try:
        if os.path.getsize(pdf) <= 0:
            return False
        with open(pdf, "rb") as fh:
            return fh.read(4) == b"%PDF"
    except OSError:
        return False


def _reap(proc):
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        else:
            proc.wait()
    except Exception:  # noqa: BLE001 - cleanup must not raise
        pass


def _size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return -1


def _wait(proc, pdf, timeout):
    """Wait for the renderer. Chrome can linger after writing: once the pdf
    exists and its size is unchanged for 1 s, stop waiting. Returns True when
    the deadline passed with the process still running and no finished pdf."""
    deadline = time.monotonic() + timeout
    last = -1
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        size = _size(pdf)
        if size > 0 and size == last:
            return False
        last = size
        time.sleep(1)
    return proc.poll() is None and not _pdf_ok(pdf)


def md_to_pdf(md_path, pdf_path, *, lang="en", renderer=None, timeout=None,
              runner=subprocess.Popen):
    """Render md_path to pdf_path. Returns (ok, note); never raises. On success
    the intermediate html is removed, otherwise it is kept next to the pdf."""
    html_path = os.path.splitext(pdf_path)[0] + ".html"
    profile = proc = None
    try:
        if timeout is None:
            try:
                timeout = float(os.environ.get("PDF_RENDER_TIMEOUT", "120"))
            except ValueError:
                timeout = 120.0
        with open(md_path, encoding="utf-8") as fh:
            md = fh.read()
        title = (md.split("\n", 1)[0].lstrip("# ").strip() or "Report")
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(md2html.convert(md, False, title, lang))
        renderer = renderer or find_pdf_renderer()
        if renderer is None:
            return False, NO_RENDERER
        kind, binary = renderer
        absh, absp = os.path.abspath(html_path), os.path.abspath(pdf_path)
        if os.path.exists(absp):
            os.remove(absp)
        if kind == "chrome":
            profile = tempfile.mkdtemp(prefix="exam_chrome_")
            argv = [binary, "--headless=new", "--disable-gpu", "--no-first-run",
                    "--no-default-browser-check", "--no-pdf-header-footer",
                    "--hide-scrollbars", "--disable-extensions",
                    "--disable-background-networking", "--disable-sync",
                    "--virtual-time-budget=10000", "--user-data-dir=" + profile,
                    "--print-to-pdf=" + absp, "file://" + absh]
        elif kind == "weasyprint":
            argv = [binary, absh, absp]
        elif kind == "wkhtmltopdf":
            argv = [binary, "--quiet", "--enable-local-file-access", absh, absp]
        else:
            return False, "unknown PDF renderer %r; HTML kept" % kind
        proc = runner(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        timed_out = _wait(proc, absp, timeout)
        _reap(proc)
        proc = None
        if _pdf_ok(absp):
            os.remove(html_path)
            return True, "PDF written with %s" % kind
        if os.path.exists(absp):  # D1: a rejected file must not stay named report.pdf
            os.remove(absp)
        if timed_out:
            return False, "%s timed out after %gs; HTML kept" % (kind, timeout)
        return False, "%s produced no valid PDF; HTML kept" % kind
    except Exception as exc:  # noqa: BLE001 - a report problem is never fatal
        return False, "PDF render failed (%s: %s); HTML kept" % (type(exc).__name__, exc)
    finally:
        if proc is not None:
            _reap(proc)
        if profile:
            shutil.rmtree(profile, ignore_errors=True)


def write_reports(result, out_dir, *, pdf=True, renderer=None, runner=subprocess.Popen,
                  view="sheet"):
    """Write report.md and answers.md always; report.html/report.pdf when a render is asked for.
    Returns dict(md, answers, html, pdf, pdf_status); html/pdf are paths or None."""
    if view not in VIEWS:
        raise ValueError("unknown view %r" % view)
    os.makedirs(out_dir, exist_ok=True)
    md_path = os.path.join(out_dir, "report.md")
    html_path = os.path.join(out_dir, "report.html")
    pdf_path = os.path.join(out_dir, "report.pdf")
    answers_path = os.path.join(out_dir, "answers.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(_compose(result, view))
    with open(answers_path, "w", encoding="utf-8") as fh:
        fh.write(build_answer_sheet(result))
    info = {"md": md_path, "answers": answers_path, "html": None, "pdf": None, "pdf_status": "not requested"}
    if not pdf:
        return info
    lang = learn_lang(result)
    ok, note = md_to_pdf(md_path, pdf_path, lang=lang, renderer=renderer, runner=runner)
    if ok:
        info.update(pdf=pdf_path, pdf_status="ok: " + note)
        return info
    info["pdf_status"] = "skipped: " + note
    if os.path.exists(html_path):
        info["html"] = html_path
    with open(md_path, "a", encoding="utf-8") as fh:
        fh.write("\nPDF skipped: %s\n" % note)
    return info

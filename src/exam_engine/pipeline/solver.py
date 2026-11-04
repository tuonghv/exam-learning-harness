"""SOLVE stage: build the solve/retry prompts and apply one solver reply to the records.

Python 3.8 stdlib only. The key is never read here (fewshot skips the --key file).
"""
import os
import re

from exam_engine import settings
from exam_engine.adapters import claude
from exam_engine.core import schema as sch
from exam_engine.core.decision import declined, decide_rec, finding
from exam_engine.pipeline import router, verifier
from exam_engine.pipeline import parser
from exam_engine.pipeline.parser import read_text
from exam_engine.utils.text import norm


def base_prompt(exam):
    """Common rules + task wording + the subject addendum from config/subjects.json."""
    lang = router.language(exam)
    parts = [settings.read_prompt("system.md", lang), settings.read_prompt("exam/solve.md", lang)]
    extra = router.policy(exam["fields"].get("Subject")).get("prompt")
    if extra:
        parts.append(settings.read_prompt(extra, lang))
    return "\n".join(p.strip("\n") + "\n" for p in parts)


def fewshot(exam, exam_text, key_path):
    """Worked example of the same subject from examples/<subject>/, or ''.

    Never the exam itself or the --key file; never anything under evals/."""
    sub = router.subject_key(exam["fields"].get("Subject"))
    root = os.path.join(settings.ROOT, "examples", sub or "-")
    if not sub or not os.path.isdir(root):
        return ""
    for name in sorted(os.listdir(root)):
        if not (name.startswith("input-") and name.endswith(".md")):
            continue
        inp, exp = os.path.join(root, name), os.path.join(root, name.replace("input-", "expected-"))
        if not os.path.isfile(exp):
            continue
        if key_path and os.path.realpath(exp) == os.path.realpath(key_path):
            continue
        if norm(read_text(inp)) == norm(exam_text):
            continue
        return ("Worked example (orientation only; your reply is still the single JSON object).\n"
                "Example input:\n%s\n\nExample answer:\n%s\n\n" % (read_text(inp), read_text(exp)))
    return ""


labelled = parser.labelled


def solve_prompt(exam, exam_text, key_path, ids=None):
    """Round 1. A labelled file is rendered from the parse (each group's context once) over `ids`."""
    base = base_prompt(exam)
    shot = fewshot(exam, exam_text, key_path)
    if ids is not None and labelled(exam):
        exam_text = exam_context(exam) + render_questions(exam, set(ids))
    return "%s\n\nLanguage: %s\n\n%sExam file:\n%s\n" % (base, router.language(exam), shot, exam_text)


def exam_context(exam):
    head = "\n".join("%s: %s" % kv for kv in exam["fields"].items())
    ctx = head + "\n\n## Instructions\n\n%s\n" % exam["instructions"]
    if exam["passage"]:
        ctx += "\n## Passage\n\n%s\n" % exam["passage"]
    return ctx


def _one(q):
    opts = "".join("\n%s. %s" % (k, v) for k, v in sorted(q["options"].items()))
    body = "### Question text\n\n%s" % q["stem"] if parser.labelled([q]) else q["text"]
    return "## Question %d\n\n%s\n%s" % (q["id"], body, opts)


def render_questions(exam, ids, recs=None):
    """Prompt text of the questions `ids`. Labelled file: per group the instruction and passage once,
    then its questions; a dependent group also lists sibling stems + answers as context."""
    if not labelled(exam):
        return _render_plain(exam, ids)
    qs = {q["id"]: q for q in exam["questions"]}
    dep = parser.deps(exam)
    parts, sec, done = [], "", set()
    for g in parser.groups(exam):
        own = [i for i in g["ids"] if i in ids and i not in done
               and (qs[i].get("instruction") or "") == g["instruction"]
               and parser._passage(qs[i]) == g["passage"]]
        if not own:
            continue
        done.update(own)
        if qs[own[0]].get("section") and qs[own[0]]["section"] != sec:
            sec = qs[own[0]]["section"]
            parts.append("## Section: %s" % sec)
        if g["instruction"] or g["passage"]:
            if len(own) > 1 or g["passage"]:  # a lone guide-only question needs no group frame
                parts.append("## Group %d-%d" % (own[0], own[-1]))
            parts.extend("### %s\n\n%s" % (lab, val) for lab, val in (
                ("Instruction for this group", g["instruction"]), ("Passage", g["passage"])) if val)
        if g["kind"] == "dependent":
            sib = sorted({r for i in own for r in dep.get(i, ()) if r in qs and r not in ids})
            if sib:
                parts.append("### Sibling answers (context, do not re-answer)\n\n" + "\n\n".join(
                    _sibling(qs[r], recs) for r in sib))
        parts.extend(_one(qs[i]) for i in own)
    return "\n\n".join(parts)


def _sibling(q, recs):
    a = ((recs or {}).get(q["id"]) or {}).get("ans") or {}
    return "Question %d: %s\nAnswer: %s" % (q["id"], q["stem"], a.get("answer") or "(none yet)")


def _render_plain(exam, ids):
    parts, sec = [], ""
    for q in exam["questions"]:
        if q["id"] in ids:
            opts = "".join("\n%s. %s" % (k, v) for k, v in sorted(q["options"].items()))
            if q.get("section") and q["section"] != sec:
                sec = q["section"]
                parts.append("## Section: %s" % sec)
            parts.append("## Question %d\n\n%s\n%s" % (q["id"], q["text"], opts))
    return "\n\n".join(parts)


def retry_prompt(exam, recs, ids):
    base = base_prompt(exam)
    ctx = exam_context(exam)
    notes = []
    for i in sorted(ids):
        msgs = [f["message"] for f in recs[i]["findings"]] or [recs[i]["reason"] or "no answer"]
        notes.append("Question %d: %s" % (i, "; ".join(msgs)))
    return ("%s\n\nLanguage: %s\n\nRetry: a first attempt was not accepted. Solve only the questions "
            "below, keep their ids, and return only those ids. Review notes (not a key, not "
            "authoritative):\n%s\n\nExam file (only the open questions):\n%s\n%s\n" % (
                base, router.language(exam), "\n".join(notes), ctx, render_questions(exam, set(ids), recs)))


def solve_round(exam, rn, recs, ids, prompt, tag="solve"):
    for i in ids:
        recs[i]["attempts"] += 1
    c = rn.call(prompt, tag)
    if not c.ok:
        for i in ids:
            recs[i]["error"] = {"cls": c.cls, "message": c.reason}
            recs[i]["findings"].append(finding("deterministic", "call_failed", c.reason))
            if recs[i]["status"] is None:
                recs[i]["status"], recs[i]["reason"] = "UNCERTAIN", "call_failed"
        return
    obj, err = claude.extract_json(c.text, sch.SOLVE_OUT)
    problems = [err] if err else sch.validate(obj, sch.SOLVE_OUT)
    if problems:
        for i in ids:
            recs[i]["error"] = None
            recs[i]["findings"].append(finding("deterministic", "malformed_output", problems[0]))
            if recs[i]["status"] is None:
                recs[i]["status"], recs[i]["reason"] = "UNCERTAIN", "malformed_output"
        return
    got = {}
    for a in obj["questions"]:
        got.setdefault(a["id"], a)
    qs = {q["id"]: q for q in exam["questions"]}
    for i in ids:
        r = recs[i]
        r["error"] = None
        a = got.get(str(i))
        if a is None:
            r.update(ans=None, checks=[], code_checks=[], review=None, status="FAIL",
                     reason="missing_in_output",
                     findings=[finding("deterministic", "missing_in_output",
                                        "question %d not in the solver output" % i)])
            continue
        r.update(ans=a, review=None, findings=[])
        mapped = None
        if qs[i].get("options") and not re.match(r"^[A-D]$", str(a.get("answer")).strip()):
            mapped = verifier.option_for_value(a.get("answer"), qs[i]["options"])
        if mapped:  # option value given instead of its letter (60.1)
            r["findings"].append(finding("deterministic", "answer_mapped",
                                          '"%s" -> %s' % (str(a.get("answer"))[:40], mapped)))
            a["answer"] = mapped
        r["code_checks"] = verifier.det_checks(qs[i], a, exam)
        r["checks"] = list(r["code_checks"])
        if declined(a):
            r["findings"].append(finding("deterministic", "solver_declined",
                                          "; ".join(a.get("issues") or []) or "solver declined"))
        for k in r["code_checks"]:
            if k["result"] == "fail":
                r["findings"].append(finding("deterministic", k["kind"], k["detail"]))
        decide_rec(r)


# 75.2: shapes whose meaning depends on the option slots or on other questions (structural, no model call).
# Stem: a keyword then a standalone uppercase letter ("option B", "phương án A"); "A(1;2)" point names do not match.
_STEM_LETTER = re.compile(r"(?i:ph[uư][oơ]ng [aá]n|đ[aá]p [aáàả]n|dap an|option|choice|answer|statement|câu|cau|ý)"
                          r"\s*[:(]?\s*[A-E](?![\w(])")
# Option: "all/none of the above", "tất cả các đáp án trên", "không có đáp án nào" (letter references are
# caught separately: any standalone option key inside an option text).
_OPT_ALL = re.compile(r"(?i:\b(?:all|none|neither|both) of (?:the|these|those)\b|\bthe above\b"
                      r"|t[aấ]t c[aả] c[aá]c|không có (?:đáp|phương) án|khong co (?:dap|phuong) an"
                      r"|c[aá]c (?:đáp án|phương án|ý) (?:trên|còn lại))")


_STEM_REF = re.compile(r"(?i:\b(?:c[aâ]u|question)\s*\d+)")  # ASCII "cau 1" that parser.deps may not read


def _unsafe(q, keys, depends):
    stem = str(q.get("stem") or q.get("text") or "")
    texts = [str(t) for t in q["options"].values()]
    return (depends or _STEM_REF.search(stem) is not None or _STEM_LETTER.search(stem) is not None
            or any(_OPT_ALL.search(t) for t in texts)
            or any(re.search(r"(?<!\w)%s(?!\w)" % re.escape(x), t) for x in keys for t in texts))


def permuted(exam, ids):
    """75.2: (exam2, back). exam2 holds only the `ids` questions, in reverse order, each with its option texts
    rotated by 1 + id % (k-1) so the correct position always moves; back[id][new letter] = original letter.
    An id left out of back is `permutation_unsafe` (stem or option names a letter, "all of the above",
    or the stem depends on another question) and is not sampled; exam2["unsafe"] lists them."""
    qs, out, back = {q["id"]: q for q in exam["questions"]}, [], {}
    dep = parser.deps(exam)
    for i in sorted(ids, reverse=True):
        q = dict(qs[i])
        keys = sorted(q.get("options") or {})
        k = len(keys)
        out.append(q)
        if k < 2 or _unsafe(q, keys, bool(dep.get(i))):
            continue
        sh = 1 + i % (k - 1)
        texts = [q["options"][x] for x in keys]
        q["options"] = {keys[j]: texts[(j + sh) % k] for j in range(k)}
        back[i] = {keys[j]: keys[(j + sh) % k] for j in range(k)}
    exam2 = dict(exam, questions=[q for q in out if q["id"] in back],
                 unsafe=[i for i in sorted(ids) if i not in back])
    return exam2, back


def second_prompt(exam2, ids):
    """Independent re-solve: the rules, the context and the permuted questions only (no key, no first answer,
    no review notes, no few-shot)."""
    return ("%s\n\nLanguage: %s\n\n%s\n%s\n\nSolve independently.\n" % (
        base_prompt(exam2), router.language(exam2), exam_context(exam2), render_questions(exam2, set(ids))))

"""SOLVE stage: build the solve/retry prompts and apply one solver reply to the records.

Python 3.8 stdlib only. The key is never read here (fewshot skips the --key file).
"""
import os

from exam_engine import settings
from exam_engine.adapters import claude
from exam_engine.core import schema as sch
from exam_engine.core.decision import declined, decide_rec, finding
from exam_engine.pipeline import router, verifier
from exam_engine.pipeline.parser import read_text
from exam_engine.utils.text import norm


def base_prompt(exam):
    """Common rules + task wording + the subject addendum from config/subjects.json."""
    parts = [settings.read_prompt("system.md"), settings.read_prompt("exam/solve.md")]
    extra = router.policy(exam["fields"].get("Subject")).get("prompt")
    if extra:
        parts.append(settings.read_prompt(extra))
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


def solve_prompt(exam, exam_text, key_path):
    base = base_prompt(exam)
    return "%s\n\nLanguage: %s\n\n%sExam file:\n%s\n" % (
        base, router.language(exam), fewshot(exam, exam_text, key_path), exam_text)


def render_questions(exam, ids):
    parts = []
    for q in exam["questions"]:
        if q["id"] in ids:
            opts = "".join("\n%s. %s" % (k, v) for k, v in sorted(q["options"].items()))
            parts.append("## Question %d\n\n%s\n%s" % (q["id"], q["text"], opts))
    return "\n\n".join(parts)


def retry_prompt(exam, recs, ids):
    base = base_prompt(exam)
    head = "\n".join("%s: %s" % kv for kv in exam["fields"].items())
    ctx = head + "\n\n## Instructions\n\n%s\n" % exam["instructions"]
    if exam["passage"]:
        ctx += "\n## Passage\n\n%s\n" % exam["passage"]
    notes = []
    for i in sorted(ids):
        msgs = [f["message"] for f in recs[i]["findings"]] or [recs[i]["reason"] or "no answer"]
        notes.append("Question %d: %s" % (i, "; ".join(msgs)))
    return ("%s\n\nLanguage: %s\n\nRetry: a first attempt was not accepted. Solve only the questions "
            "below, keep their ids, and return only those ids. Review notes (not a key, not "
            "authoritative):\n%s\n\nExam file (only the open questions):\n%s\n%s\n" % (
                base, router.language(exam), "\n".join(notes), ctx, render_questions(exam, set(ids))))


def solve_round(exam, rn, recs, ids, prompt):
    for i in ids:
        recs[i]["attempts"] += 1
    c = rn.call(prompt)
    if not c.ok:
        for i in ids:
            recs[i]["error"] = {"cls": c.cls, "message": c.reason}
            recs[i]["findings"].append(finding("deterministic", "call_failed", c.reason))
            if recs[i]["status"] is None:
                recs[i]["status"], recs[i]["reason"] = "UNCERTAIN", "call_failed"
        return
    obj, err = claude.extract_json(c.text)
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
        r["code_checks"] = verifier.det_checks(qs[i], a, exam)
        r["checks"] = list(r["code_checks"])
        if declined(a):
            r["findings"].append(finding("deterministic", "solver_declined",
                                          "; ".join(a.get("issues") or []) or "solver declined"))
        for k in r["code_checks"]:
            if k["result"] == "fail":
                r["findings"].append(finding("deterministic", k["kind"], k["detail"]))
        decide_rec(r)

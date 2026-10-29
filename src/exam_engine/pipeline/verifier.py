"""Verification: deterministic code checks (no model) and the AI review round (QA).

Python 3.8 stdlib only. No key access here (the key is read only in scorer.py).
"""
import json
import re

from exam_engine import settings
from exam_engine.adapters import claude
from exam_engine.core import schema as sch
from exam_engine.core.decision import declined, decide_rec, finding, is_open
from exam_engine.core.safe_eval import safe_eval
from exam_engine.pipeline import router
from exam_engine.utils.text import norm

_NUM = re.compile(r"-?\d+(?:[.,]\d+)?")


def _policy(exam):
    return router.policy((exam.get("fields") or {}).get("Subject"))


def _chk(kind, detail, result, independent):
    return {"kind": kind, "detail": detail, "result": result, "independent": independent}


def _ws(s):
    return " ".join(str(s).split())


def _letters(text):
    return re.findall(r"(?m)^\s*\(?([a-e])[.)]\s", text)


def _format(q, ans, exam):
    a = str(ans.get("answer")).strip()
    task = ((exam.get("fields") or {}).get("Task") or "").strip().casefold()
    if is_open(ans) or _policy(exam)["task"] == "Open":
        ok = a == "Open"
        return _chk("format", "answer is Open" if ok else "Literature answer must be Open",
                    "pass" if ok else "fail", False)
    if q.get("options"):
        ok = bool(re.match(r"^[A-D]$", a)) and a in q["options"]
        return _chk("format", "single letter A-D", "pass" if ok else "fail", False)
    letters = _letters(q.get("text", ""))
    if task == "sentence ordering" or re.match(r"^[a-z](?:-[a-z])+$", a):
        parts = a.replace(" ", "").casefold().split("-")
        want = sorted(letters)
        ok = (all(len(p) == 1 for p in parts) and len(set(parts)) == len(parts)
              and (sorted(parts) == want if want else len(parts) > 1))
        return _chk("format", "ordering uses each given letter once",
                    "pass" if ok else "fail", False)
    return None


def _answer_number(a):
    m = _NUM.search(a.replace("−", "-"))
    return m.group(0).replace(",", ".") if m else None


def _computed(ans):
    expr = ans.get("expr")
    if not expr:
        return None
    detail = "arithmetic only: %s" % expr
    try:
        val = safe_eval(expr)
    except ValueError as exc:
        return _chk("computed", "arithmetic only: %s" % exc, "unknown", False)
    num = _answer_number(str(ans.get("answer")))
    if num is None:
        return _chk("computed", "arithmetic only: answer has no number", "unknown", False)
    dec = len(num.split(".")[1]) if "." in num else None
    tol = 0.5 * 10 ** (-dec) + 1e-12 if dec is not None else 1e-6 * max(1.0, abs(float(num)))
    ok = abs(val - float(num)) <= tol
    return _chk("computed", detail + " = %.10g, answer %s" % (val, num),
                "pass" if ok else "fail", True)


def _quotes(q, ans, exam):
    quotes = [x for x in (ans.get("evidence") or [])
              if isinstance(x, str) and x.strip() and x.strip().casefold() != "null"]
    hay = _ws("\n".join([exam.get("passage") or "", q.get("text", ""),
                         " ".join((q.get("options") or {}).values())]))
    out = []
    for x in quotes:
        ok = _ws(x) in hay
        out.append(_chk("quote", "verbatim in passage/question: %s" % x[:80],
                        "pass" if ok else "fail", False))
    if not out and is_open(ans):
        out.append(_chk("quote", "no quote given", "unknown", False))
    return out


def det_checks(q, ans, exam):
    """Code-only checks for one question (empty when the solver declined, D4)."""
    if declined(ans):
        return []
    want = _policy(exam)["checks"]
    quote = lambda: _quotes(q, ans, exam) if "quote" in want else []  # noqa: E731
    fmt = _format(q, ans, exam) if "format" in want else None
    if is_open(ans):
        return [fmt] + quote() if fmt else quote()  # D7: format + quote only
    out = [c for c in (fmt, _computed(ans) if "computed" in want else None) if c]
    return out + quote()


def qa_prompt(exam, recs, ids):
    base = settings.read_prompt("verification/verify_answer.md", router.language(exam))
    qs = {q["id"]: q for q in exam["questions"]}
    items = []
    for i in sorted(ids):
        r, a = recs[i], recs[i]["ans"]
        items.append({"id": str(i), "question": qs[i]["text"], "options": qs[i]["options"],
                      "answer": a.get("answer"), "solution": a.get("solution"),
                      "explanation": a.get("explanation"),
                      "code_checks": [{"kind": c["kind"], "detail": c["detail"],
                                       "result": c["result"]} for c in r["checks"]]})
    ctx = "Instructions:\n%s\n" % exam["instructions"]
    if exam["passage"]:
        ctx += "\nPassage:\n%s\n" % exam["passage"]
    return "%s\n\nLanguage: %s\n\n%s\nAnswers to review (JSON):\n%s\n" % (
        base, router.language(exam), ctx, json.dumps(items, ensure_ascii=False, indent=1))


def qa_round(exam, rn, recs, ids):
    cand = [i for i in ids if recs[i]["ans"] is not None and not declined(recs[i]["ans"])
            and not any(k["result"] == "fail" for k in recs[i]["code_checks"])]
    try:
        if not cand:
            return
        c = rn.call(qa_prompt(exam, recs, cand))
        if not c.ok:
            for i in cand:
                recs[i]["findings"].append(finding("ai_review", "review_failed", c.reason))
            return
        obj, err = claude.extract_json(c.text)
        problems = [err] if err else sch.validate(obj, sch.QA_OUT)
        if problems:
            for i in cand:
                recs[i]["findings"].append(finding("ai_review", "review_malformed", problems[0]))
            return
        rev = {}
        for x in obj["reviews"]:
            rev.setdefault(x["id"], x)
        for i in cand:
            x = rev.get(str(i))
            if x is None:
                recs[i]["findings"].append(finding("ai_review", "review_missing",
                                                    "reviewer gave no verdict"))
                continue
            r = recs[i]
            r["review"] = {"verdict": x["verdict"], "findings": x["findings"]}
            r["checks"].append({"kind": "ai_review", "detail": "reviewer: %s" % x["verdict"],
                                "result": {"agree": "pass", "disagree": "fail"}.get(
                                    x["verdict"], "unknown"), "independent": False})
            for f in x["findings"]:
                r["findings"].append(finding("ai_review", x["verdict"], f))
    finally:
        for i in ids:
            if recs[i]["ans"] is not None:
                decide_rec(recs[i])

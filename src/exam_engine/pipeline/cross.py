"""cross-solve: the same exam solved from two independent inputs, compared at answer level.

Route A = exam text (as `solve` reads it), route B = page images only. Equal answers -> agree,
anything else -> needs_review. Agreement is evidence, not proof. Reuses the solver prompt and the
SOLVE_OUT schema; the solving engine is not touched. Python 3.8 stdlib only.
"""
import re

from exam_engine.adapters import claude
from exam_engine.core import schema as sch
from exam_engine.core.decision import declined
from exam_engine.pipeline import solver, verifier
from exam_engine.utils.text import fold

MAX_ATTEMPTS = 2
_TF = {"đúng": "T", "true": "T", "t": "T", "đ": "T", "sai": "F", "false": "F", "f": "F", "s": "F"}
IMAGE_RULES = (
    "The exam is in the attached page images, not in text. Number the questions 1..%d in reading "
    "order across the pages (ignore a restart of the numbering at a new part) and use these numbers "
    "as ids. Read figures, tables and formulas from the images. If something is unreadable, set "
    "answer_status to a non-answered value instead of guessing.")


class CrossError(Exception):
    """Structured failure (exit 3): call_failed, invalid_reply, cost_cap."""

    def __init__(self, code, message):
        Exception.__init__(self, "%s: %s" % (code, message))
        self.code = code


def route_a_prompt(exam, text):
    return solver.solve_prompt(exam, text, None)


def route_b_prompt(exam):
    from exam_engine.pipeline import router
    n = len(exam["questions"])
    return "%s\n\nLanguage: %s\n\n%s\n" % (solver.base_prompt(exam), router.language(exam),
                                           IMAGE_RULES % n)


def canon(answer):
    """Comparable form of an answer: letter, four verdicts, a number, else folded text."""
    s = str(answer).strip()
    if re.fullmatch(r"[A-Da-d]", s):
        return "L:" + s.upper()
    verdicts = [_TF[w.lower()] for w in verifier._VERDICT.findall(s)]
    if len(verdicts) == 4:
        return "V:" + "".join(verdicts)
    num = verifier._answer_number(s)
    if num is not None:
        rest = re.sub(r"^\s*[a-z]\w*\s*=", "", fold(s), count=1)
        rest = re.sub(r"-?\d+(?:[.,]\d+)?", "", rest, count=1)
        return "N:%.9g:%s" % (float(num), re.sub(r"[^a-z0-9^/]", "", rest))
    return "S:" + " ".join(fold(s).split())


def same_answer(a, b):
    return canon(a) == canon(b)


def parse_reply(text):
    """({id: answer dict}, None) or (None, reason)."""
    obj, err = claude.extract_json(text)
    problems = [err] if err else sch.validate(obj, sch.SOLVE_OUT)
    if problems:
        return None, problems[0]
    out = {}
    for a in obj["questions"]:
        out.setdefault(str(a["id"]), a)
    return out, None


def _answer(rec):
    return None if rec is None or declined(rec) else str(rec["answer"]).strip()


def compare(exam, got_a, got_b):
    """Per question {id, answer_a, answer_b, status, reason}; unaligned routes never agree."""
    ids = [str(q["id"]) for q in exam["questions"]]
    mismatch = len(got_b) != len(ids)
    out = []
    for i in ids:
        ra, rb = got_a.get(i), got_b.get(i)
        a, b = _answer(ra), _answer(rb)
        if mismatch:
            status, why = "needs_review", "count_mismatch"
        elif ra is None:
            status, why = "needs_review", "missing_a"
        elif rb is None:
            status, why = "needs_review", "missing_b"
        elif a is None:
            status, why = "needs_review", "declined_a"
        elif b is None:
            status, why = "needs_review", "declined_b"
        elif same_answer(a, b):
            status, why = "agree", ""
        else:
            status, why = "needs_review", "differ"
        out.append({"id": i, "answer_a": a, "answer_b": b, "status": status, "reason": why})
    return out


def _ask(call, prompt, route, state, max_cost):
    why = ""
    for _ in range(MAX_ATTEMPTS):
        if state["cost"] >= max_cost:
            raise CrossError("cost_cap", "cost $%.2f reached the cap $%.2f before route %s"
                             % (state["cost"], max_cost, route))
        c = call(prompt)
        state["calls"] += 1
        state["cost"] += c.cost_usd or 0.0
        if not c.ok:
            raise CrossError("call_failed", "route %s: %s %s" % (route, c.cls, c.reason))
        got, why = parse_reply(c.text)
        if got is not None:
            return got
    raise CrossError("invalid_reply", "route %s: %s (after %d attempts)" % (route, why, MAX_ATTEMPTS))


def cross_solve(exam, exam_text, llm_text, llm_images, pngs, max_cost=1.0, model="sonnet"):
    """Result dict; `llm_text(prompt)` and `llm_images(prompt, pngs)` return a claude.Call."""
    state = {"calls": 0, "cost": 0.0}
    got_a = _ask(llm_text, route_a_prompt(exam, exam_text), "A", state, max_cost)
    got_b = _ask(lambda p: llm_images(p, pngs), route_b_prompt(exam), "B", state, max_cost)
    qs = compare(exam, got_a, got_b)
    bad = [q for q in qs if q["status"] != "agree"]
    return {"routes": {"A": "exam text", "B": "page images"}, "model": model, "questions": qs,
            "summary": {"questions": len(qs), "agree": len(qs) - len(bad),
                        "needs_review": len(bad)},
            "calls": state["calls"], "cost_usd": round(state["cost"], 6)}


def review_md(result):
    lines = ["# Cross-solve review", "",
             "agree %(agree)d / %(questions)d, needs review %(needs_review)d. Agreement is "
             "evidence, not proof." % result["summary"], ""]
    bad = [q for q in result["questions"] if q["status"] != "agree"]
    if not bad:
        return "\n".join(lines + ["Nothing to review."]) + "\n"
    lines += ["| Question | Route A (text) | Route B (images) | Reason |", "|---|---|---|---|"]
    for q in bad:
        lines.append("| %s | %s | %s | %s |" % (
            q["id"], q["answer_a"] or "-", q["answer_b"] or "-", q["reason"]))
    return "\n".join(lines) + "\n"

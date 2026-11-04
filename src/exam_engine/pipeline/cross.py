"""cross-solve: the same exam solved from two independent inputs, compared at answer level.

Route A = exam text (as `solve` reads it), route B = page images only. Equal answers -> agree,
anything else -> needs_review. Agreement is evidence, not proof. Reuses the solver prompt and the
SOLVE_OUT schema; the solving engine is not touched. Python 3.8 stdlib only.
"""
import re

from exam_engine.adapters import claude
from exam_engine.core import schema as sch
from exam_engine.core.decision import declined
from exam_engine.ingest import segment
from exam_engine.pipeline import solver, verifier
from exam_engine.utils import langtable
from exam_engine.utils.text import fold

MAX_ATTEMPTS = 2


def tf_map(table):
    """Verdict word -> T/F: today's vi+en words plus the extra-language words (casefolded)."""
    m = {"đúng": "T", "true": "T", "t": "T", "đ": "T", "sai": "F", "false": "F", "f": "F", "s": "F"}
    for slot, v in (("true", "T"), ("false", "F")):
        m.update({w.casefold(): v for w in langtable.raw(slot, table)})
    return m


_TF = tf_map(langtable.load())

IMAGE_RULES = (
    "The exam is in the attached page images, not in text. There are exactly %d questions in total. "
    "%s; do NOT use the "
    "printed numbers: count continuously in reading order, so the first question of a later part "
    "gets the previous count + 1, and use 1..%d as ids. Answer every question in every part. "
    "Read figures, tables and formulas from the images. If something is unreadable, set "
    "answer_status to a non-answered value instead of guessing.")

FLAGGED_RULES = (
    "Only these questions are asked, in the attached pages:\n%s\n"
    "Identify each by its first words (printed numbers may restart per part); answer with exactly "
    "these ids. Read figures/tables from the images. If the question or its figure is not readable "
    "or not on the pages, set answer_status to a non-answered value with the reason; never guess.")


class CrossError(Exception):
    """Structured failure (exit 3): call_failed, invalid_reply, cost_cap."""

    def __init__(self, code, message):
        Exception.__init__(self, "%s: %s" % (code, message))
        self.code = code


def route_a_prompt(exam, text):
    return solver.solve_prompt(exam, text, None)


_HEAD = re.compile(r"^\s*([^\W\d_]{3,12})\s+(IV|V|I{1,3}|\d{1,2})\s*[.:)]?(?:\s|$)")
_HINT_FALLBACK = "Printed numbering may restart per part or section"


_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


def structure_hint(text, n=None):
    """Clause naming the parts and their printed question spans, read from the exam text's own
    headings (`PART I`, `SECTION 2`, `PHẦN III`). Falls back to the generic clause unless the spans
    are consistent: >= 2 parts numbered 1, 2, ... each after a blank line, every part non-empty,
    numbered contiguously from 1 (numbering really restarts), and, when `n` is given, summing to n."""
    parts = []
    prev = ""
    for line in (text or "").splitlines():
        s = line.strip()
        m = _HEAD.match(s) if len(s) <= 80 else None
        if m and m.group(1).isupper() and not segment._Q.match(s):
            parts.append([m.group(1).capitalize(), m.group(2), [], not prev.strip()])
        else:
            q = segment._Q.match(s)
            if q and parts:
                parts[-1][2].append(int(q.group(1) or q.group(2)))
        prev = line
    if len(parts) < 2 or not all(p[3] and p[2] for p in parts):
        return _HINT_FALLBACK
    seq = [_ROMAN.get(p[1]) or (int(p[1]) if p[1].isdigit() else 0) for p in parts]
    if seq != list(range(seq[0], seq[0] + len(seq))) or seq[0] != 1 or len(set(p[0] for p in parts)) != 1:
        return _HINT_FALLBACK
    if any(sorted(p[2]) != list(range(1, len(p[2]) + 1)) for p in parts):
        return _HINT_FALLBACK
    if n is not None and sum(len(p[2]) for p in parts) != n:
        return _HINT_FALLBACK
    spans = ["%s %s 1-%d" % (p[0], p[1], len(p[2])) for p in parts]
    return "The printed numbering restarts in each part (%s)" % ", ".join(spans)


def route_b_prompt(exam, text=None):
    from exam_engine.pipeline import router
    n = len(exam["questions"])
    return "%s\n\nLanguage: %s\n\n%s\n" % (solver.base_prompt(exam), router.language(exam),
                                           IMAGE_RULES % (n, structure_hint(text, n), n))


def flagged_items(exam, ids):
    """[(id, printed number or None, first 80 chars of the stem's first line)] for the flagged `ids`."""
    from exam_engine.pipeline import parser
    off = parser._OFFSET_RE.search(exam.get("instructions") or "")
    qs = {q["id"]: q for q in exam["questions"]}
    out = []
    for i in ids:
        body = (qs[i].get("stem") or qs[i]["text"]).strip()
        out.append((i, i + int(off.group(1)) if off else None, (body.split("\n", 1)[0])[:80]))
    return out


CONTINUES = "A question may continue on the next attached page.\n"
ADJUDICATE_RULES = (
    "Two readings of the same question disagree: one from the exam text, one from the page image. "
    "For each question below choose ONE final answer and explain why in the explanation. "
    "Use exactly these ids.\n%s")


def adjudicate_prompt(exam, items):
    """Text-only prompt; items = [(id, text answer dict, image answer dict)]."""
    from exam_engine.pipeline import router
    qs = {q["id"]: q for q in exam["questions"]}
    blocks = []
    for i, ta, ia in items:
        opts = "".join("\n%s. %s" % (k, v) for k, v in sorted((qs[i].get("options") or {}).items()))
        blocks.append("id %s: %s%s\n  text answer: %s | %s\n  image answer: %s | %s" % (
            i, qs[i]["text"].strip(), opts, ta.get("answer"), ta.get("explanation") or "",
            ia.get("answer"), ia.get("explanation") or ""))
    return "%s\n\nLanguage: %s\n\n%s\n" % (solver.base_prompt(exam), router.language(exam),
                                               ADJUDICATE_RULES % "\n\n".join(blocks))


def flagged_prompt(exam, items, continues=False):
    """Image prompt for flagged questions: asked by id + stem prefix, never by reading-order counting.
    `continues` (wider --image-scope only) adds the cut-question rule; the default text is unchanged."""
    from exam_engine.pipeline import router
    lines = "\n".join('id %s%s: "%s..."' % (i, " (printed %s)" % p if p is not None else "", pre)
                      for i, p, pre in items)
    return "%s\n\nLanguage: %s\n\n%s\n" % (solver.base_prompt(exam), router.language(exam),
                                           FLAGGED_RULES % lines + (CONTINUES if continues else ""))


def canon(answer):
    """Comparable form of an answer: letter, four verdicts, a number, else folded text."""
    s = re.sub(r"(?<=\d)\s*\(.*$", "", str(answer).strip(), flags=re.S)
    if re.fullmatch(r"[A-Da-d]", s):
        return "L:" + s.upper()
    verdicts = [_TF[w.casefold()] for w in verifier._VERDICT.findall(s)]
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
    obj, err = claude.extract_json(text, sch.SOLVE_OUT)
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
        state["trace"].append({"route": route, "ok": c.ok, "cost_usd": c.cost_usd, "text": c.text,
                               "reason": c.reason})
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
    state = {"calls": 0, "cost": 0.0, "trace": []}
    got_a = _ask(llm_text, route_a_prompt(exam, exam_text), "A", state, max_cost)
    got_b = _ask(lambda p: llm_images(p, pngs), route_b_prompt(exam, exam_text), "B", state, max_cost)
    qs = compare(exam, got_a, got_b)
    bad = [q for q in qs if q["status"] != "agree"]
    return {"routes": {"A": "exam text", "B": "page images"}, "model": model, "questions": qs,
            "summary": {"questions": len(qs), "agree": len(qs) - len(bad),
                        "needs_review": len(bad)},
            "calls": state["calls"], "cost_usd": round(state["cost"], 6),
            "trace": state["trace"]}


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

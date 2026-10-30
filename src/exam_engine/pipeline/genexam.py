"""gen-exams: write Vietnamese-style exams with keys for the benchmark, and lessons from its failures (REQ-0027).

The generator only writes files; the engine, solver prompt and scorer are untouched, and the key is
opened later only by the scorer. Python 3.8 stdlib only.
"""
import hashlib
import json
import os

from exam_engine import settings
from exam_engine.adapters import claude
from exam_engine.core.safe_eval import safe_eval
from exam_engine.pipeline import verifier

PROMPT_REL = os.path.join("dev", "genexam.md")
SUBJECTS = {"math": "Mathematics"}
FIRST_NUMBER = 101
MAX_ATTEMPTS = 2


class GenError(Exception):
    """Structured failure: call_failed, invalid_reply, cost_cap, bad_key, leak (exit 3 / 1)."""

    def __init__(self, code, message):
        Exception.__init__(self, "%s: %s" % (code, message))
        self.code = code


def template():
    with open(os.path.join(settings.PROMPTS_DIR, PROMPT_REL), encoding="utf-8") as fh:
        return fh.read()


def build_prompt(subject, seed, idx):
    return "%s\nSeed: %s-%d\nSubject key: %s\n" % (template().rstrip("\n"), seed, idx, subject)


def check_reply(obj):
    """Problems of a reply (empty = ok), including a key whose `check` does not give the answer."""
    errs = []
    for k in ("skill", "question", "final_answer", "solution", "check"):
        if not isinstance(obj.get(k), str) or not obj[k].strip():
            errs.append("%s must be a non-empty string" % k)
    if errs:
        return errs
    try:
        want = safe_eval(obj["check"])
    except ValueError as exc:
        return ["check: %s" % exc]
    got = verifier._answer_value(obj["final_answer"])
    if got is None:
        try:
            got = (safe_eval(obj["final_answer"].replace(",", ".")), 1e-9)
        except ValueError:
            return ["final_answer is not a number or fraction"]
    if abs(want - got[0]) > max(got[1], 1e-9):
        errs.append("bad_key: check = %g but final_answer = %s" % (want, obj["final_answer"]))
    return errs


def leak_check(input_text, obj):
    """Problems when the solution or the final-answer line of the key appears in the input."""
    out = []
    for label, s in (("solution", obj["solution"]), ("final answer line", "Final answer: " + obj["final_answer"])):
        if s.strip() and s.strip() in input_text:
            out.append("key text (%s) appears in the input" % label)
    return out


def input_md(subject, obj):
    return "\n".join([
        "# Exam Input", "", "Subject: %s" % SUBJECTS[subject], "Level: Grade 12",
        "Exam type: High School Graduation", "Task: Short Answer", "Mode: Solve",
        "Skill: %s" % obj["skill"].strip(), "Language: vi", "", "## Instructions", "",
        "Giải bài toán, trình bày lời giải và nêu đáp án cuối cùng.", "", "## Question 1", "",
        obj["question"].strip(), ""])


def key_md(obj):
    a = obj["final_answer"].strip()
    return "\n".join([
        "# Expected Output", "", "## Question 1", "", "Final answer: %s" % a, "", "### Solution", "",
        obj["solution"].strip(), "", "### Explanation", "", "- Generated item, not reviewed.", "",
        "### Verification", "", "- Check: %s = %s. Pass" % (obj["check"].strip(), a),
        "- Final answer: %s" % a, "- Status: Verified", "", "### Grading", "",
        "- 1 điểm: %s (hoặc giá trị tương đương). 0 điểm: giá trị khác." % a, ""])


def _ask(llm, prompt):
    """(obj, cost) with one retry on a bad reply; a reply with a wrong key is a bad reply."""
    cost, why = 0.0, ""
    for _ in range(MAX_ATTEMPTS):
        call = llm(prompt)
        cost += call.cost_usd
        if not call.ok:
            raise GenError("call_failed", "%s %s" % (call.cls, call.reason))
        obj, why = claude.extract_json(call.text)
        if obj is not None:
            why = "; ".join(check_reply(obj))
        if not why:
            return obj, cost
    raise GenError("invalid_reply", "%s (after %d attempts)" % (why, MAX_ATTEMPTS))


def generate(subject, n, seed, llm, max_cost=0.5):
    """[(obj, input text, key text)] for n exams; stops with cost_cap when the cap is reached."""
    if subject not in SUBJECTS:
        raise GenError("invalid_reply", "subject %r not supported (have: %s)"
                       % (subject, ", ".join(sorted(SUBJECTS))))
    out, cost = [], 0.0
    for i in range(1, n + 1):
        if cost >= max_cost:
            raise GenError("cost_cap", "cost $%.2f reached the cap $%.2f before exam %d" % (cost, max_cost, i))
        obj, spent = _ask(llm, build_prompt(subject, seed, i))
        cost += spent
        text = input_md(subject, obj)
        bad = leak_check(text, obj)
        if bad:
            raise GenError("leak", "exam %d: %s" % (i, "; ".join(bad)))
        out.append((obj, text, key_md(obj)))
    return out, round(cost, 6)


def write(subject, items, out, meta):
    """Files under out/inputs and out/keys (numbers from 101 up, never overwriting); manifest.json."""
    d_in, d_key = (os.path.join(out, k, subject) for k in ("inputs", "keys"))
    for d in (d_in, d_key):
        os.makedirs(d, exist_ok=True)
    start = FIRST_NUMBER
    while os.path.exists(os.path.join(d_in, "input-%d.md" % start)):
        start += 1
    names = []
    for i, (obj, text, key) in enumerate(items):
        n = start + i
        with open(os.path.join(d_in, "input-%d.md" % n), "w", encoding="utf-8") as fh:
            fh.write(text)
        with open(os.path.join(d_key, "expected-%d.md" % n), "w", encoding="utf-8") as fh:
            fh.write(key)
        names.append("%s/%d" % (subject, n))
    mp = os.path.join(out, "manifest.json")
    try:
        with open(mp, encoding="utf-8") as fh:
            man = json.load(fh)
    except (OSError, ValueError):
        man = {"generated": True, "reviewed": False, "runs": []}
    man["runs"].append(dict(meta, items=names,
                            prompt_sha256=hashlib.sha256(template().encode("utf-8")).hexdigest()))
    with open(mp, "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return names


def classify(q):
    """Cause class of a non-PASS question: bad_key | engine | variance (a human may reclassify)."""
    codes = " ".join(q.get("findings") or ())
    if q.get("basis") == "code oracle" and "key" in (q.get("reason") or "").casefold():
        return "bad_key"
    if q.get("verdict") == "FAIL" and any(w in codes for w in ("check", "quote", "mismatch")):
        return "engine"
    return "variance"


def lessons(summary):
    """One lesson per FAIL / UNCERTAIN question of a benchmark summary."""
    out = []
    for it in summary.get("items", ()):
        for q in it.get("questions", ()):
            if q.get("verdict") in ("FAIL", "UNCERTAIN"):
                out.append({"item": "%s/%s" % (it["subject"], it["item"]), "question": q.get("id"),
                            "verdict": q["verdict"], "cause": classify(q), "answer": q.get("answer"),
                            "reason": q.get("reason"), "evidence": q.get("findings") or [],
                            "status": "open"})
    return out


def lessons_md(ls):
    rows = ["# Lessons", "", "%d open" % sum(1 for x in ls if x["status"] == "open"), ""]
    rows += ["- %s q%s %s [%s]: %s" % (x["item"], x["question"], x["verdict"], x["cause"], x["reason"])
             for x in ls]
    return "\n".join(rows) + "\n"

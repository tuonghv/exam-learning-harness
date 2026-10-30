"""gen-exams: write Vietnamese-style exams with keys for the benchmark, and lessons from its failures (REQ-0027).

The generator only writes files; the engine, solver prompt and scorer are untouched, and the key is
opened later only by the scorer. Python 3.8 stdlib only.
"""
import hashlib
import json
import os
import re

from exam_engine import settings
from exam_engine.adapters import claude
from exam_engine.core.safe_eval import safe_eval
from exam_engine.pipeline import verifier

PROMPT_REL = os.path.join("dev", "genexam.md")
QA_REL = os.path.join("dev", "genexam_qa.md")
DGNL_REL = os.path.join("dev", "genexam_dgnl.md")
PROFILES = ("hs", "dgnl")
LETTERS = "ABCD"
TOPICS = {
    "hs": ["logarit và phương trình mũ", "tích phân", "số phức", "hình học Oxyz", "xác suất",
           "đạo hàm và cực trị", "cấp số cộng và cấp số nhân", "thể tích khối đa diện"],
    "dgnl": ["cấp số cộng/nhân và quy luật dãy số", "phần trăm, tỉ lệ, lãi suất", "xác suất cơ bản",
             "logic: suy luận từ các điều kiện cho trước", "đọc số liệu cho trong lời (trung bình, tỉ lệ)",
             "chuyển động, công việc chung, bài toán thực tế", "tổ hợp và đếm", "bất phương trình, hàm số đơn giản"],
}
SOURCE_NOTE = "model knowledge, not an official exam"
SUBJECTS = {"math": "Mathematics"}
FIRST_NUMBER = 101
MAX_ATTEMPTS = 2


class GenError(Exception):
    """Structured failure: call_failed, invalid_reply, cost_cap, bad_key, leak (exit 3 / 1)."""

    def __init__(self, code, message):
        Exception.__init__(self, "%s: %s" % (code, message))
        self.code = code


def template(rel=PROMPT_REL):
    with open(os.path.join(settings.PROMPTS_DIR, rel), encoding="utf-8") as fh:
        return fh.read()


def topic(seed, idx, profile="hs"):
    """Topic for exam idx of a round: consecutive topics from a seed-dependent start, so no two repeat."""
    ts = TOPICS[profile]
    return ts[(int(hashlib.sha256(str(seed).encode("utf-8")).hexdigest(), 16) + idx) % len(ts)]


def build_prompt(subject, seed, idx, level="hard", profile="hs"):
    return "%s\nSeed: %s-%d\nSubject key: %s\nLevel: %s\nTopic (use exactly this): %s\n" % (
        template(DGNL_REL if profile == "dgnl" else PROMPT_REL).rstrip("\n"), seed, idx, subject, level,
        topic(seed, idx, profile))


def qa_prompt(obj):
    """Review prompt: the question and the worked solution; the model's own final answer is asked for."""
    opts = "".join("%s. %s\n" % (k, v) for k, v in sorted((obj.get("options") or {}).items()))
    return "%s\nQuestion:\n%s\n%s\nSolution to review:\n%s\nClaimed final answer: %s\n" % (
        template(QA_REL).rstrip("\n"), obj["question"].strip(), opts, obj["solution"].strip(),
        obj["final_answer"].strip())


def qa(llm, obj):
    """(status 'pass'|'fail'|'unknown', note, cost): independent review; its own answer must match the key."""
    call = llm(qa_prompt(obj))
    if not call.ok:
        return "unknown", "%s %s" % (call.cls, call.reason), call.cost_usd
    rep, why = claude.extract_json(call.text)
    if rep is None:
        return "unknown", why, call.cost_usd
    if obj.get("options"):
        same = str(rep.get("my_answer", "")).strip().upper()[:1] == obj["final_answer"]
    else:
        mine, theirs = value(str(rep.get("my_answer", ""))), value(obj["final_answer"])
        same = mine is not None and theirs is not None and abs(mine[0] - theirs[0]) <= max(theirs[1], 1e-9)
    if rep.get("verdict") == "ok" and same:
        return "pass", "", call.cost_usd
    return "fail", "%s | reviewer answer %s" % (rep.get("bad_step") or rep.get("verdict"), rep.get("my_answer")), call.cost_usd


def value(a):
    """(number, tolerance) of an answer: fraction, sqrt, sci form, or a plain number; None if unreadable."""
    a = re.sub(r"^\s*[A-Za-z]\w*\s*=\s*", "", a)
    got = verifier._answer_value(a)
    if got is None:
        try:
            got = (safe_eval(re.sub(r"\s+\([^)]*\)\s*$", "", a.strip()).replace(",", ".")), 1e-9)
        except ValueError:
            return None
    return got


def check_dgnl(obj):
    """Problems of a 4-option reply; sets obj["final_answer"] to the correct letter."""
    errs = []
    for k in ("skill", "question", "solution", "check"):
        if not isinstance(obj.get(k), str) or not obj[k].strip():
            errs.append("%s must be a non-empty string" % k)
    opts = obj.get("options")
    if not isinstance(opts, dict) or sorted(opts) != list(LETTERS) or not all(
            isinstance(v, str) and v.strip() for v in opts.values()):
        errs.append("options must be exactly A, B, C, D (non-empty strings)")
    if obj.get("correct") not in tuple(LETTERS):
        errs.append("correct must be one of A, B, C, D")
    if errs:
        return errs
    vals = [value(opts[k]) for k in LETTERS]
    if any(v is None for v in vals):
        return ["every option must be a number or fraction"]
    nums = [v[0] for v in vals]
    if any(abs(a - b) <= 1e-9 for i, a in enumerate(nums) for b in nums[i + 1:]):
        return ["two options have the same value"]
    try:
        want = safe_eval(obj["check"])
    except ValueError as exc:
        return ["check: %s" % exc]
    got = vals[LETTERS.index(obj["correct"])]
    if abs(want - got[0]) > max(got[1], 1e-9):
        return ["bad_key: check = %g but option %s = %s" % (want, obj["correct"], opts[obj["correct"]])]
    obj["final_answer"] = obj["correct"]
    return []


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
    got = value(obj["final_answer"])
    if got is None:
        return ["final_answer is not a number or fraction"]
    if abs(want - got[0]) > max(got[1], 1e-9):
        errs.append("bad_key: check = %g but final_answer = %s" % (want, obj["final_answer"]))
    return errs


def leak_check(input_text, obj):
    """Problems when the solution or the final-answer line of the key appears in the input."""
    out = []
    for label, s in (("solution", obj["solution"]), ("final answer line", "Final answer: " + obj["final_answer"]),
                     ("correct answer line", "Correct answer:")):
        if s.strip() and s.strip() in input_text:
            out.append("key text (%s) appears in the input" % label)
    return out


def input_md(subject, obj):
    if obj.get("options"):
        return "\n".join([
            "# Exam Input", "", "Subject: %s" % SUBJECTS[subject], "Level: Grade 12",
            "Exam type: University Entrance (DGNL)", "Task: Multiple Choice", "Mode: Solve",
            "Skill: %s" % obj["skill"].strip(), "Language: vi", "", "## Instructions", "",
            "Chọn đáp án đúng nhất và giải thích ngắn gọn.", "", "## Question 1", "",
            obj["question"].strip(), "", ""] + ["%s. %s" % (k, obj["options"][k].strip()) for k in LETTERS] + [""])
    return "\n".join([
        "# Exam Input", "", "Subject: %s" % SUBJECTS[subject], "Level: Grade 12",
        "Exam type: High School Graduation", "Task: Short Answer", "Mode: Solve",
        "Skill: %s" % obj["skill"].strip(), "Language: vi", "", "## Instructions", "",
        "Giải bài toán, trình bày lời giải và nêu đáp án cuối cùng.", "", "## Question 1", "",
        obj["question"].strip(), ""])


def key_md(obj):
    if obj.get("options"):
        a, o = obj["final_answer"], obj["options"]
        return "\n".join([
            "# Expected Output", "", "## Question 1", "", "Final answer: %s" % a,
            "Correct answer: %s. %s" % (a, o[a].strip()), "", "### Solution", "", obj["solution"].strip(), "",
            "### Explanation", "", "- Generated item, not reviewed.", "", "### Verification", "",
            "- Check: %s = %s. Pass" % (obj["check"].strip(), o[a].strip()), "- Final answer: %s" % a,
            "- Status: Verified", "", "### Grading", "", "- 1 point: %s. 0 points: any other answer." % a, ""])
    a = obj["final_answer"].strip()
    return "\n".join([
        "# Expected Output", "", "## Question 1", "", "Final answer: %s" % a, "", "### Solution", "",
        obj["solution"].strip(), "", "### Explanation", "", "- Generated item, not reviewed.", "",
        "### Verification", "", "- Check: %s = %s. Pass" % (obj["check"].strip(), a),
        "- Final answer: %s" % a, "- Status: Verified", "", "### Grading", "",
        "- 1 điểm: %s (hoặc giá trị tương đương). 0 điểm: giá trị khác." % a, ""])


def _ask(llm, prompt, profile="hs"):
    """(obj, cost) with one retry on a bad reply; a reply with a wrong key is a bad reply."""
    cost, why = 0.0, ""
    for _ in range(MAX_ATTEMPTS):
        call = llm(prompt)
        cost += call.cost_usd
        if not call.ok:
            raise GenError("call_failed", "%s %s" % (call.cls, call.reason))
        obj, why = claude.extract_json(call.text)
        if obj is not None:
            why = "; ".join(check_dgnl(obj) if profile == "dgnl" else check_reply(obj))
        if not why:
            return obj, cost
    raise GenError("invalid_reply", "%s (after %d attempts)" % (why, MAX_ATTEMPTS))


def generate(subject, n, seed, llm, max_cost=0.5, level="hard", review=True, profile="hs"):
    """[(obj, input text, key text)] for n exams; each obj gets obj["qa"] / obj["qa_note"].

    Stops with cost_cap when the cap is reached.
    """
    if subject not in SUBJECTS:
        raise GenError("invalid_reply", "subject %r not supported (have: %s)"
                       % (subject, ", ".join(sorted(SUBJECTS))))
    out, cost = [], 0.0
    for i in range(1, n + 1):
        if cost >= max_cost:
            raise GenError("cost_cap", "cost $%.2f reached the cap $%.2f before exam %d" % (cost, max_cost, i))
        obj, spent = _ask(llm, build_prompt(subject, seed, i, level, profile), profile)
        cost += spent
        obj["qa"], obj["qa_note"] = "skipped", ""
        if review:
            obj["qa"], obj["qa_note"], spent = qa(llm, obj)
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
    while os.path.exists(os.path.join(d_in, "input-%d.md" % start)) or os.path.exists(
            os.path.join(out, "rejected", subject, "input-%d.md" % start)):
        start += 1
    names, rejected = [], []
    for i, (obj, text, key) in enumerate(items):
        n = start + i
        if obj.get("qa") == "fail":
            rd = os.path.join(out, "rejected", subject)
            os.makedirs(rd, exist_ok=True)
            for f, body in (("input-%d.md" % n, text), ("expected-%d.md" % n, key),
                            ("qa-%d.txt" % n, obj["qa_note"] + "\n")):
                with open(os.path.join(rd, f), "w", encoding="utf-8") as fh:
                    fh.write(body)
            rejected.append("%s/%d" % (subject, n))
            continue
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
    man["runs"].append(dict(meta, source=SOURCE_NOTE, items=names, qa_rejected=rejected,
                            qa_counts={k: sum(1 for o, _, _ in items if o.get("qa") == k)
                                       for k in ("pass", "fail", "unknown", "skipped")},
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

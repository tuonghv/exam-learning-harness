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
BLIND_REL = os.path.join("dev", "genexam_blind.md")
LETTERS = "ABCD"
SOURCE_NOTE = "model knowledge, not an official exam"
CHECK_NAMES = ("reply", "mc4", "mc")  # -> check_reply, check_dgnl, check_mc (see CHECKS)
_KEYS = ("subject", "subject_label", "prompt", "qa_prompt", "topics", "check", "blind", "exam_type", "level",
         "lang", "instructions")


class GenError(Exception):
    """Structured failure: call_failed, invalid_reply, cost_cap, bad_key, leak, bad_profile (exit 3 / 1)."""

    def __init__(self, code, message):
        Exception.__init__(self, "%s: %s" % (code, message))
        self.code = code


def load_profiles(config_dir=None):
    """config/genexam_profiles.json as {name: profile}; a bad file or profile -> GenError bad_profile."""
    path = os.path.join(config_dir or settings.config_dir(), "genexam_profiles.json")
    try:
        table = settings.load_json(path)
    except (OSError, ValueError) as exc:
        raise GenError("bad_profile", "%s: %s" % (path, exc))
    if not isinstance(table, dict) or not table:
        raise GenError("bad_profile", "%s: expected a non-empty object of profiles" % path)
    for name, pr in table.items():
        if not isinstance(pr, dict):
            raise GenError("bad_profile", "%s: profile %r is not an object" % (path, name))
        miss = [k for k in _KEYS if k not in pr]
        if miss:
            raise GenError("bad_profile", "%s: profile %r lacks %s" % (path, name, ", ".join(miss)))
        for k in ("prompt", "qa_prompt"):
            v = pr[k]
            parts = v.replace("\\", "/").split("/") if isinstance(v, str) else []
            if not parts or not all(parts) or ".." in parts or os.path.isabs(v):
                raise GenError("bad_profile", "%s: profile %r %s must be a relative path inside prompts/ (got %r)"
                               % (path, name, k, v))
        if pr["check"] not in CHECK_NAMES:
            raise GenError("bad_profile", "%s: profile %r has unknown check %r (have: %s)"
                           % (path, name, pr["check"], ", ".join(CHECK_NAMES)))
        if not isinstance(pr["topics"], list) or not pr["topics"]:
            raise GenError("bad_profile", "%s: profile %r needs topics" % (path, name))
    return table


def _rel(p):
    return os.path.join(*p.split("/"))


def apply_profiles(table):
    """Point the module views (PROFILES, TOPICS, ...) at `table`; the names stay for tests and the CLI."""
    g = globals()
    g["PROFILE_TABLE"] = table
    g["PROFILES"] = tuple(table)
    g["BLIND"] = tuple(n for n, p in table.items() if p["blind"])
    g["PROFILE_SUBJECT"] = {n: p["subject"] for n, p in table.items()}
    g["PROMPT_OF"] = {n: _rel(p["prompt"]) for n, p in table.items()}
    g["QA_OF"] = {n: _rel(p["qa_prompt"]) for n, p in table.items()}
    g["TOPICS"] = {n: list(p["topics"]) for n, p in table.items()}
    g["SUBJECTS"] = {}
    for p in table.values():
        g["SUBJECTS"].setdefault(p["subject"], p["subject_label"])
    g["LANG_MC"] = {}
    for p in table.values():
        if p["check"] == "mc":
            g["LANG_MC"].setdefault(p["subject"], (p["lang"], p["instructions"]))


apply_profiles(load_profiles())


def _prof(subject, *checks):
    """First profile of `subject` with one of `checks` (else any profile of the subject)."""
    rows = [p for p in PROFILE_TABLE.values() if p["subject"] == subject]
    for p in rows:
        if p["check"] in checks:
            return p
    return rows[0]


FIRST_NUMBER = 101
MAX_ATTEMPTS = 2


def template(rel=PROMPT_REL):
    with open(os.path.join(settings.PROMPTS_DIR, rel), encoding="utf-8") as fh:
        return fh.read()


def topic(seed, idx, profile=None):
    """Topic for exam idx of a round: consecutive topics from a seed-dependent start, so no two repeat."""
    profile = profile or PROFILES[0]
    ts = TOPICS[profile]
    return ts[(int(hashlib.sha256(str(seed).encode("utf-8")).hexdigest(), 16) + idx) % len(ts)]


def build_prompt(subject, seed, idx, level="hard", profile=None):
    profile = profile or PROFILES[0]
    return "%s\nSeed: %s-%d\nSubject key: %s\nLevel: %s\nTopic (use exactly this): %s\n" % (
        template(PROMPT_OF[profile]).rstrip("\n"), seed, idx, subject, level,
        topic(seed, idx, profile))


def qa_prompt(obj, profile=None):
    """Review prompt: the question and the worked solution; the model's own final answer is asked for."""
    profile = profile or PROFILES[0]
    opts = "".join("%s. %s\n" % (k, v) for k, v in sorted((obj.get("options") or {}).items()))
    return "%s\nQuestion:\n%s\n%s\nSolution to review:\n%s\nClaimed final answer: %s\n" % (
        template(QA_OF[profile]).rstrip("\n"), obj["question"].strip(), opts, obj["solution"].strip(),
        obj["final_answer"].strip())


def qa(llm, obj, profile=None):
    """(status 'pass'|'fail'|'unknown', note, cost): independent review; its own answer must match the key."""
    profile = profile or PROFILES[0]
    call = llm(qa_prompt(obj, profile))
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


def check_mc(obj):
    """Problems of a 4-option reply without a code oracle; sets obj["final_answer"] to the letter."""
    errs = []
    for k in ("skill", "question", "solution"):
        if not isinstance(obj.get(k), str) or not obj[k].strip():
            errs.append("%s must be a non-empty string" % k)
    if not isinstance(obj.get("passage", ""), str):
        errs.append("passage must be a string")
    opts = obj.get("options")
    if not isinstance(opts, dict) or sorted(opts) != list(LETTERS) or not all(
            isinstance(v, str) and v.strip() for v in opts.values()):
        errs.append("options must be exactly A, B, C, D (non-empty strings)")
    elif len(set(v.strip().casefold() for v in opts.values())) < 4:
        errs.append("two options have the same text")
    if obj.get("correct") not in tuple(LETTERS):
        errs.append("correct must be one of A, B, C, D")
    if not errs:
        obj["final_answer"] = obj["correct"]
    return errs


def blind_prompt(obj):
    """The question (and passage) with options only: no key, no solution."""
    opts = "".join("%s. %s\n" % (k, obj["options"][k].strip()) for k in LETTERS)
    text = "%s\n" % obj["question"].strip()
    if obj.get("passage", "").strip():
        text = "Passage:\n%s\n\nQuestion:\n%s" % (obj["passage"].strip(), text)
    return "%s\n%s\n%s" % (template(BLIND_REL).rstrip("\n"), text, opts)


def blind_qa(llm, obj, reviews=2):
    """(status, note, cost): pass only if every blind review picks the key letter."""
    letters, cost = [], 0.0
    for _ in range(reviews):
        call = llm(blind_prompt(obj))
        cost += call.cost_usd
        rep = claude.extract_json(call.text)[0] if call.ok else None
        letters.append(str((rep or {}).get("answer", "")).strip().upper()[:1] or "?")
    if "?" in letters:
        return "unknown", "unreadable review: %s" % ",".join(letters), cost
    if all(x == obj["final_answer"] for x in letters):
        return "pass", "", cost
    return "fail", "key %s, blind reviewers %s" % (obj["final_answer"], ",".join(letters)), cost


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
    if obj.get("options") and subject in LANG_MC:
        pr = _prof(subject, "mc")
        lang, instr = LANG_MC[subject]
        body = ["## Instructions", "", instr, ""]
        if obj.get("passage", "").strip():
            body += ["## Passage", "", obj["passage"].strip(), ""]
        return "\n".join([
            "# Exam Input", "", "Subject: %s" % SUBJECTS[subject], "Level: %s" % pr["level"],
            "Exam type: %s" % pr["exam_type"], "Task: Multiple Choice", "Mode: Solve",
            "Skill: %s" % obj["skill"].strip(), "Language: %s" % lang, ""] + body + [
            "## Question 1", "", obj["question"].strip(), ""] + [
            "%s. %s" % (k, obj["options"][k].strip()) for k in LETTERS] + [""])
    if obj.get("options"):
        pr = _prof(subject, "mc4")
        return "\n".join([
            "# Exam Input", "", "Subject: %s" % SUBJECTS[subject], "Level: %s" % pr["level"],
            "Exam type: %s" % pr["exam_type"], "Task: Multiple Choice", "Mode: Solve",
            "Skill: %s" % obj["skill"].strip(), "Language: %s" % pr["lang"], "", "## Instructions", "",
            pr["instructions"], "", "## Question 1", "",
            obj["question"].strip(), "", ""] + ["%s. %s" % (k, obj["options"][k].strip()) for k in LETTERS] + [""])
    pr = _prof(subject, "reply")
    return "\n".join([
        "# Exam Input", "", "Subject: %s" % SUBJECTS[subject], "Level: %s" % pr["level"],
        "Exam type: %s" % pr["exam_type"], "Task: Short Answer", "Mode: Solve",
        "Skill: %s" % obj["skill"].strip(), "Language: %s" % pr["lang"], "", "## Instructions", "",
        pr["instructions"], "", "## Question 1", "",
        obj["question"].strip(), ""])


def _grading_line():
    """Grading line of the first short-answer (check reply) profile; English default when none has one."""
    for p in PROFILE_TABLE.values():
        if p["check"] == "reply" and p.get("grading_line"):
            return p["grading_line"]
    return "- 1 point: %s. 0 points: any other answer."


def key_md(obj):
    if obj.get("options"):
        a, o = obj["final_answer"], obj["options"]
        return "\n".join([
            "# Expected Output", "", "## Question 1", "", "Final answer: %s" % a,
            "Correct answer: %s. %s" % (a, o[a].strip()), "", "### Solution", "", obj["solution"].strip(), "",
            "### Explanation", "", "- Generated item, not reviewed.", "", "### Verification", "",
            ("- Check: %s = %s. Pass" % (obj["check"].strip(), o[a].strip())) if obj.get("check") else
            "- Check: two blind reviews chose %s. Pass" % a, "- Final answer: %s" % a,
            "- Status: Verified", "", "### Grading", "", "- 1 point: %s. 0 points: any other answer." % a, ""])
    a = obj["final_answer"].strip()
    return "\n".join([
        "# Expected Output", "", "## Question 1", "", "Final answer: %s" % a, "", "### Solution", "",
        obj["solution"].strip(), "", "### Explanation", "", "- Generated item, not reviewed.", "",
        "### Verification", "", "- Check: %s = %s. Pass" % (obj["check"].strip(), a),
        "- Final answer: %s" % a, "- Status: Verified", "", "### Grading", "",
        _grading_line() % a, ""])


_CHECK_FN = {"reply": lambda o: check_reply(o), "mc4": lambda o: check_dgnl(o), "mc": lambda o: check_mc(o)}


class _Checks(dict):
    """profile -> check function, read through the live profile table (tests swap it with apply_profiles)."""

    def __missing__(self, name):
        return _CHECK_FN[PROFILE_TABLE[name]["check"]]

    def __iter__(self):
        return iter(PROFILE_TABLE)


CHECKS = _Checks()


def _ask(llm, prompt, profile=None):
    """(obj, cost) with one retry on a bad reply; a reply with a wrong key is a bad reply."""
    profile = profile or PROFILES[0]
    cost, why = 0.0, ""
    for _ in range(MAX_ATTEMPTS):
        call = llm(prompt)
        cost += call.cost_usd
        if not call.ok:
            raise GenError("call_failed", "%s %s" % (call.cls, call.reason))
        obj, why = claude.extract_json(call.text)
        if obj is not None:
            why = "; ".join(CHECKS[profile](obj))
        if not why:
            return obj, cost
    raise GenError("invalid_reply", "%s (after %d attempts)" % (why, MAX_ATTEMPTS))


def generate(subject, n, seed, llm, max_cost=0.5, level="hard", review=True, profile=None):
    """[(obj, input text, key text)] for n exams; each obj gets obj["qa"] / obj["qa_note"].

    Stops with cost_cap when the cap is reached.
    """
    profile = profile or PROFILES[0]
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
            obj["qa"], obj["qa_note"], spent = (blind_qa(llm, obj) if profile in BLIND else qa(llm, obj, profile))
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
                            prompt_sha256=hashlib.sha256(
                                template(PROMPT_OF[meta.get("profile") or PROFILES[0]]).encode("utf-8")).hexdigest()))
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

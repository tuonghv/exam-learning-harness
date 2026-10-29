"""Run one exam file through solve -> checks -> QA -> decide -> (key) -> result.json.

Usage: python3 -I tools/examples/exam_run.py EXAM.md --out DIR [--key EXPECTED.md]
           (--mock FILE | --dry-run | --real) [--max-attempts 2] [--max-cost-usd 1.00]
           [--timeout 300] [--model sonnet]
Exit 0 all PASS, 1 any FAIL/UNCERTAIN/unresolved, 2 invalid input or usage, 3 blocking stop.
Without --mock, --dry-run or --real nothing runs (never defaults to a real call).
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exam_checks as ck  # noqa: E402
import exam_llm  # noqa: E402
import exam_parse as ep  # noqa: E402
import exam_schema as sch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCKING = ("auth", "rate_limit", "service")
SUBJECT_DIRS = {"mathematics": "math", "math": "math", "physics": "physics",
                "english": "english", "literature": "literature"}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def call_cap(cfg):
    return 1 + 2 * cfg["max_attempts"]


def language(exam):
    f = exam["fields"]
    if f.get("Language"):
        return f["Language"].strip()
    return "en" if (f.get("Subject") or "").strip().casefold() == "english" else "vi"


def fewshot(exam, exam_text, key_path):
    """Worked example of the same subject from examples/<subject>/, or ''.

    Never the exam itself or the --key file; never anything under evals/."""
    sub = SUBJECT_DIRS.get((exam["fields"].get("Subject") or "").strip().casefold())
    root = os.path.join(HERE, "..", "..", "examples", sub or "-")
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
        if ep.norm(_read(inp)) == ep.norm(exam_text):
            continue
        return ("Worked example (orientation only; your reply is still the single JSON object).\n"
                "Example input:\n%s\n\nExample answer:\n%s\n\n" % (_read(inp), _read(exp)))
    return ""


def solve_prompt(exam, exam_text, key_path):
    base = _read(os.path.join(HERE, "prompts", "solve.md"))
    return "%s\n\nLanguage: %s\n\n%sExam file:\n%s\n" % (
        base, language(exam), fewshot(exam, exam_text, key_path), exam_text)


def render_questions(exam, ids):
    parts = []
    for q in exam["questions"]:
        if q["id"] in ids:
            opts = "".join("\n%s. %s" % (k, v) for k, v in sorted(q["options"].items()))
            parts.append("## Question %d\n\n%s\n%s" % (q["id"], q["text"], opts))
    return "\n\n".join(parts)


def retry_prompt(exam, recs, ids):
    base = _read(os.path.join(HERE, "prompts", "solve.md"))
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
                base, language(exam), "\n".join(notes), ctx, render_questions(exam, set(ids))))


def qa_prompt(exam, recs, ids):
    base = _read(os.path.join(HERE, "prompts", "qa.md"))
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
        base, language(exam), ctx, json.dumps(items, ensure_ascii=False, indent=1))


class Stop(Exception):
    def __init__(self, cls, message):
        Exception.__init__(self, message)
        self.cls, self.message = cls, message


class Runner(object):
    """Counts calls and cost, enforces the caps, logs one line per call."""

    def __init__(self, cfg, llm, log):
        self.cfg, self.llm, self.log = cfg, llm, log
        self.calls, self.cost = 0, 0.0

    def call(self, prompt):
        if self.cost >= self.cfg["max_cost_usd"]:
            raise Stop("cost_cap", "cost cap $%.2f reached" % self.cfg["max_cost_usd"])
        if self.calls >= call_cap(self.cfg):
            raise Stop("call_cap", "call cap %d reached" % call_cap(self.cfg))
        c = self.llm(prompt)
        self.calls += 1
        self.cost += c.cost_usd or 0.0
        self.log.append("call %d ok=%s cls=%s dur=%.1fs cost=%.4f prompt_bytes=%d answer_bytes=%d" % (
            self.calls, c.ok, c.cls or "-", c.duration_s or 0.0, c.cost_usd or 0.0,
            len(prompt.encode("utf-8")), len((c.text or "").encode("utf-8"))))
        if not c.ok and c.cls in BLOCKING:
            raise Stop(c.cls, c.reason)
        return c


def _finding(source, code, message):
    return {"source": source, "code": code, "message": message}


def _new_rec():
    return {"ans": None, "checks": [], "review": None, "findings": [], "status": None,
            "reason": "", "attempts": 0, "error": None, "score": None, "code_checks": []}


def _is_open(a):
    return a is not None and ep.norm(str(a.get("answer") or "")) == "open"


def _decide(rec):
    a = rec["ans"]
    rec["status"], rec["reason"] = ck.decide(rec["code_checks"], rec["review"], a)


def solve_round(exam, rn, recs, ids, prompt):
    for i in ids:
        recs[i]["attempts"] += 1
    c = rn.call(prompt)
    if not c.ok:
        for i in ids:
            recs[i]["error"] = {"cls": c.cls, "message": c.reason}
            recs[i]["findings"].append(_finding("deterministic", "call_failed", c.reason))
            if recs[i]["status"] is None:
                recs[i]["status"], recs[i]["reason"] = "UNCERTAIN", "call_failed"
        return
    obj, err = exam_llm.extract_json(c.text)
    problems = [err] if err else sch.validate(obj, sch.SOLVE_OUT)
    if problems:
        for i in ids:
            recs[i]["error"] = None
            recs[i]["findings"].append(_finding("deterministic", "malformed_output", problems[0]))
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
                     findings=[_finding("deterministic", "missing_in_output",
                                        "question %d not in the solver output" % i)])
            continue
        r.update(ans=a, review=None, findings=[])
        r["code_checks"] = ck.det_checks(qs[i], a, exam)
        r["checks"] = list(r["code_checks"])
        if ck.declined(a):
            r["findings"].append(_finding("deterministic", "solver_declined",
                                          "; ".join(a.get("issues") or []) or "solver declined"))
        for k in r["code_checks"]:
            if k["result"] == "fail":
                r["findings"].append(_finding("deterministic", k["kind"], k["detail"]))
        _decide(r)


def qa_round(exam, rn, recs, ids):
    cand = [i for i in ids if recs[i]["ans"] is not None and not ck.declined(recs[i]["ans"])
            and not any(k["result"] == "fail" for k in recs[i]["code_checks"])]
    try:
        if not cand:
            return
        c = rn.call(qa_prompt(exam, recs, cand))
        if not c.ok:
            for i in cand:
                recs[i]["findings"].append(_finding("ai_review", "review_failed", c.reason))
            return
        obj, err = exam_llm.extract_json(c.text)
        problems = [err] if err else sch.validate(obj, sch.QA_OUT)
        if problems:
            for i in cand:
                recs[i]["findings"].append(_finding("ai_review", "review_malformed", problems[0]))
            return
        rev = {}
        for x in obj["reviews"]:
            rev.setdefault(x["id"], x)
        for i in cand:
            x = rev.get(str(i))
            if x is None:
                recs[i]["findings"].append(_finding("ai_review", "review_missing",
                                                    "reviewer gave no verdict"))
                continue
            r = recs[i]
            r["review"] = {"verdict": x["verdict"], "findings": x["findings"]}
            r["checks"].append({"kind": "ai_review", "detail": "reviewer: %s" % x["verdict"],
                                "result": {"agree": "pass", "disagree": "fail"}.get(
                                    x["verdict"], "unknown"), "independent": False})
            for f in x["findings"]:
                r["findings"].append(_finding("ai_review", x["verdict"], f))
    finally:
        for i in ids:
            if recs[i]["ans"] is not None:
                _decide(recs[i])


def retry_ids(recs):
    return [i for i, r in recs.items()
            if r["status"] in ("FAIL", "UNCERTAIN") and not _is_open(r["ans"])
            and r["reason"] != "no_independent_check"]  # a re-solve cannot create one


def apply_key(recs, key_path):
    """SCORE: the key is opened only here, after every call."""
    keyq = {q["id"]: q for q in ep.parse_expected(key_path, legacy=True)["questions"]}
    for i, r in recs.items():
        a = r["ans"]
        if a is None or ck.declined(a) or _is_open(a):
            r["score"] = {"points": None, "max": None, "basis": "none",
                          "detail": "no key comparison (no answer or open task)"}
            continue
        s = ck.score(a, keyq.get(i))
        r["score"] = s
        if s["basis"] != "official_key":
            continue
        if s["points"] == 0:
            r["status"], r["reason"] = "FAIL", "differs_from_key"
            r["findings"].append(_finding("score", "differs_from_key", "answer differs from the key"))
        else:
            r["code_checks"].append({"kind": "key_match", "detail": "matches the key",
                                     "result": "pass", "independent": True})
            r["checks"].append(r["code_checks"][-1])
            if r["status"] == "UNCERTAIN":
                _decide(r)


def build_result(exam, exam_path, recs, cfg, rn, stopped):
    qs = []
    for i in sorted(recs):
        r = recs[i]
        a = r["ans"] or {}
        if stopped and r["status"] != "PASS" and r["error"] is None:
            r["error"] = {"cls": stopped[0], "message": exam_llm.mask(stopped[1])[:200]}
        if r["status"] is None:
            r["status"], r["reason"] = "UNCERTAIN", "not_solved"
        sc = r["score"] or {"points": None, "max": None, "basis": "none", "detail": "no key"}
        qs.append({
            "id": str(i), "answer": a.get("answer"), "solution": a.get("solution") or [],
            "explanation": a.get("explanation") or "",
            "uncertainty": a.get("uncertainty") or {"level": "high", "reason": "no answer"},
            "checks": r["checks"], "verification_status": r["status"],
            "status_reason": r["reason"], "qa_findings": r["findings"], "score": sc,
            "attempts": max(1, r["attempts"]), "unresolved": r["status"] != "PASS" and r["reason"] != "no_independent_check",
            "error": r["error"]})
    pts = [q["score"]["points"] for q in qs if q["score"]["points"] is not None]
    mx = [q["score"]["max"] for q in qs if q["score"]["max"] is not None]
    f = exam["fields"]
    return {
        "schema_version": 1,
        "exam": {"path": exam_path, "subject": f.get("Subject"), "level": f.get("Level"),
                 "exam_type": f.get("Exam type"), "task": f.get("Task"), "mode": f.get("Mode"),
                 "language": language(exam)},
        "run": {"llm": cfg["llm_name"], "model": cfg["model"], "max_attempts": cfg["max_attempts"],
                "timeout_s": cfg["timeout"], "max_cost_usd": cfg["max_cost_usd"],
                "cost_usd": round(rn.cost, 6), "calls": rn.calls,
                "stopped": stopped[0] if stopped else None},
        "questions": qs,
        "summary": {"pass": sum(q["verification_status"] == "PASS" for q in qs),
                    "fail": sum(q["verification_status"] == "FAIL" for q in qs),
                    "uncertain": sum(q["verification_status"] == "UNCERTAIN" for q in qs),
                    "unresolved": sum(q["unresolved"] for q in qs),
                    "points": sum(pts) if pts else None, "max_points": sum(mx) if mx else None}}


def run(exam_path, out_dir, cfg, llm):
    """(result, exit_code); result is None on exit 2."""
    try:
        text = _read(exam_path)
    except (OSError, UnicodeDecodeError) as exc:
        print("ERROR: input: cannot read %s: %s" % (exam_path, exc), file=sys.stderr)
        return None, 2
    exam = ep.parse_exam(exam_path)
    errs = ep.validate_exam(exam)
    if errs:
        for e in errs:
            print("ERROR: input: %s" % e, file=sys.stderr)
        return None, 2
    log = []
    rn = Runner(cfg, llm, log)
    recs = {q["id"]: _new_rec() for q in exam["questions"]}
    stopped = None
    try:
        ids = sorted(recs)
        prompt = solve_prompt(exam, text, cfg.get("key"))
        for attempt in range(1, cfg["max_attempts"] + 1):
            solve_round(exam, rn, recs, ids, prompt if attempt == 1 else retry_prompt(exam, recs, ids))
            qa_round(exam, rn, recs, ids)
            ids = retry_ids(recs)
            if not ids:
                break
    except Stop as stop:
        stopped = (stop.cls, stop.message)
        for i, r in recs.items():  # a stop inside a round: decide what has an answer
            if r["ans"] is not None and r["status"] is None:
                _decide(r)
    if not stopped and cfg.get("key"):
        apply_key(recs, cfg["key"])
    result = build_result(exam, exam_path, recs, cfg, rn, stopped)
    problems = sch.validate(result, sch.RESULT)
    if problems:
        print("ERROR: internal: result.json invalid: %s" % problems[0], file=sys.stderr)
        return result, 2
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(os.path.join(out_dir, "run.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log) + ("\n" if log else ""))
    if stopped:
        return result, 3
    s = result["summary"]
    return result, 0 if s["pass"] == len(result["questions"]) and not s["unresolved"] else 1


def mock_llm(path):
    with open(path, encoding="utf-8") as fh:
        replies = json.load(fh)
    if not isinstance(replies, list) or not all(isinstance(x, str) for x in replies):
        raise ValueError("mock file must be a JSON list of reply strings")
    it = iter(replies)

    def llm(prompt):
        try:
            return exam_llm.Call(True, next(it), 0.0, "", "", 0.0)
        except StopIteration:
            return exam_llm.Call(False, "", 0.0, "other", "mock replies exhausted", 0.0)
    return llm


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("exam")
    ap.add_argument("--out")
    ap.add_argument("--key")
    ap.add_argument("--mock")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--max-attempts", type=int, default=2)
    ap.add_argument("--max-cost-usd", type=float, default=1.00)
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--model", default="sonnet")
    a = ap.parse_args(argv)
    modes = [bool(a.mock), a.dry_run, a.real]
    if sum(modes) != 1:
        print("usage: choose exactly one of --mock FILE, --dry-run, --real (never defaults to real)",
              file=sys.stderr)
        return 2
    if a.max_attempts < 1 or a.max_cost_usd < 0 or a.timeout <= 0:
        print("usage: --max-attempts >= 1, --max-cost-usd >= 0, --timeout > 0", file=sys.stderr)
        return 2
    if not a.dry_run and not a.out:
        print("usage: --out DIR is required", file=sys.stderr)
        return 2
    cfg = {"max_attempts": a.max_attempts, "max_cost_usd": a.max_cost_usd, "timeout": a.timeout,
           "model": a.model, "key": a.key, "llm_name": "claude-p" if a.real else "mock"}
    if a.dry_run:
        try:
            text = _read(a.exam)
        except (OSError, UnicodeDecodeError) as exc:
            print("ERROR: input: cannot read %s: %s" % (a.exam, exc), file=sys.stderr)
            return 2
        exam = ep.parse_exam(a.exam)
        errs = ep.validate_exam(exam)
        if errs:
            for e in errs:
                print("ERROR: input: %s" % e, file=sys.stderr)
            return 2
        print("calls <= %d, cap $%.2f (dry run: no call made)" % (call_cap(cfg), a.max_cost_usd))
        print("=== SOLVE prompt ===")
        print(solve_prompt(exam, text, a.key))
        print("=== QA prompt template (answers are filled in from the SOLVE reply) ===")
        print(_read(os.path.join(HERE, "prompts", "qa.md")))
        print("=== retry prompt: solve.md + only the open questions + non-key QA findings ===")
        return 0
    tmp = None
    try:
        if a.real:
            print("calls <= %d, cap $%.2f" % (call_cap(cfg), a.max_cost_usd), flush=True)
            tmp = tempfile.mkdtemp(prefix="exam_run_")

            def llm(prompt):
                return exam_llm.run_claude(prompt, model=a.model, timeout_s=a.timeout, cwd=tmp)
        else:
            llm = mock_llm(a.mock)
        result, code = run(a.exam, a.out, cfg, llm)
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    if result is not None:
        s = result["summary"]
        print("pass=%d fail=%d uncertain=%d unresolved=%d calls=%d stopped=%s -> %s" % (
            s["pass"], s["fail"], s["uncertain"], s["unresolved"], result["run"]["calls"],
            result["run"]["stopped"], os.path.join(a.out, "result.json")))
    return code


if __name__ == "__main__":
    sys.exit(main())

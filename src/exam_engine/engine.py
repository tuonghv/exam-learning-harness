"""Engine: solve -> checks -> QA -> decide -> (key) -> result.json + reports.

Counts calls and cost, enforces the caps, logs one line per call. run() returns
(result, exit_code); exit 0 all PASS, 1 any FAIL/UNCERTAIN/unresolved, 2 invalid input,
3 blocking stop.
"""
import json
import os
import sys

from exam_engine.adapters import claude
from exam_engine.core import schema as sch
from exam_engine.core.decision import decide_rec, evidence_kind, is_open, new_rec
from exam_engine.pipeline import parser, prompts, reporter, router, scorer, solver, verifier

BLOCKING = ("auth", "rate_limit", "service")


def call_cap(cfg):
    return 1 + 2 * cfg["max_attempts"]


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


def retry_ids(recs):
    return [i for i, r in recs.items()
            if r["status"] in ("FAIL", "UNCERTAIN") and not is_open(r["ans"])
            and r["reason"] != "no_independent_check"]  # a re-solve cannot create one


def build_result(exam, exam_path, recs, cfg, rn, stopped):
    qs = []
    for i in sorted(recs):
        r = recs[i]
        a = r["ans"] or {}
        if stopped and r["status"] != "PASS" and r["error"] is None:
            r["error"] = {"cls": stopped[0], "message": claude.mask(stopped[1])[:200]}
        if r["status"] is None:
            r["status"], r["reason"] = "UNCERTAIN", "not_solved"
        sc = r["score"] or {"points": None, "max": None, "basis": "none", "detail": "no key"}
        qs.append({
            "id": str(i), "evidence_kind": evidence_kind(r), "answer": a.get("answer"), "solution": a.get("solution") or [],
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
                 "language": router.language(exam)},
        "run": {"llm": cfg["llm_name"], "model": cfg["model"], "max_attempts": cfg["max_attempts"],
                "timeout_s": cfg["timeout"], "max_cost_usd": cfg["max_cost_usd"],
                "cost_usd": round(rn.cost, 6), "calls": rn.calls,
                "stopped": stopped[0] if stopped else None,
                "prompt": prompts.prompt_info()},
        "questions": qs,
        "summary": {"pass": sum(q["verification_status"] == "PASS" for q in qs),
                    "fail": sum(q["verification_status"] == "FAIL" for q in qs),
                    "uncertain": sum(q["verification_status"] == "UNCERTAIN" for q in qs),
                    "unresolved": sum(q["unresolved"] for q in qs),
                    "points": sum(pts) if pts else None, "max_points": sum(mx) if mx else None}}


def run(exam_path, out_dir, cfg, llm):
    """(result, exit_code); result is None on exit 2."""
    try:
        text = parser.read_text(exam_path)
    except (OSError, UnicodeDecodeError) as exc:
        print("ERROR: input: cannot read %s: %s" % (exam_path, exc), file=sys.stderr)
        return None, 2
    exam = parser.parse_exam(exam_path)
    router.apply_lang(exam, cfg.get("lang"))
    errs = parser.validate_exam(exam)
    if errs:
        for e in errs:
            print("ERROR: input: %s" % e, file=sys.stderr)
        return None, 2
    log = []
    rn = Runner(cfg, llm, log)
    recs = {q["id"]: new_rec() for q in exam["questions"]}
    stopped = None
    try:
        ids = sorted(recs)
        prompt = solver.solve_prompt(exam, text, cfg.get("key"))
        for attempt in range(1, cfg["max_attempts"] + 1):
            solver.solve_round(exam, rn, recs, ids, prompt if attempt == 1 else solver.retry_prompt(exam, recs, ids))
            verifier.qa_round(exam, rn, recs, ids)
            ids = retry_ids(recs)
            if not ids:
                break
    except Stop as stop:
        stopped = (stop.cls, stop.message)
        for i, r in recs.items():  # a stop inside a round: decide what has an answer
            if r["ans"] is not None and r["status"] is None:
                decide_rec(r)
    if (not stopped and cfg.get("key")
            and router.policy(exam["fields"].get("Subject"))["score_basis"] != "none"):
        scorer.apply_key(recs, cfg["key"])
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
    result["reports"] = reporter.write_reports(result, out_dir, pdf=cfg.get("pdf", False))
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
            return claude.Call(True, next(it), 0.0, "", "", 0.0)
        except StopIteration:
            return claude.Call(False, "", 0.0, "other", "mock replies exhausted", 0.0)
    return llm

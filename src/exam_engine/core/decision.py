"""PASS/FAIL/UNCERTAIN decision, evidence kind and the per-question record helpers.

No model call and no key access. phase-2 2.2 step 4: ai_review alone never gives PASS.
"""
from exam_engine.utils.text import norm

KINDS = ("code oracle", "key match", "Claude review only", "none")


def declined(ans):
    """D4: the solver gave up on this question."""
    return (ans.get("answer_status") != "answered" or ans.get("answer") is None
            or not str(ans.get("answer")).strip())


def is_open(ans):
    return ans is not None and norm(str(ans.get("answer") or "")) == "open"


def decide(checks, review, ans):
    """(status, reason)."""
    if declined(ans):
        return "UNCERTAIN", "solver_declined"
    if is_open(ans):
        bad = [c["kind"] for c in checks if c["result"] == "fail"]
        return "UNCERTAIN", "open_task_no_rubric" + (" (failed: %s)" % ",".join(bad) if bad else "")
    for c in checks:
        if c["result"] == "fail":
            return "FAIL", "check_failed: %s" % c["kind"]
    verdict = (review or {}).get("verdict")
    if verdict == "disagree":
        return "FAIL", "reviewer_disagrees"
    if verdict != "agree":
        return "UNCERTAIN", "reviewer_unsure" if verdict == "unsure" else "no_review"
    if (ans.get("uncertainty") or {}).get("level") != "low":
        return "UNCERTAIN", "solver_uncertainty_not_low"
    if not any(c["independent"] and c["result"] == "pass" for c in checks):
        return "UNCERTAIN", "no_independent_check"
    return "PASS", "independent check passed and reviewer agrees"


def evidence_kind(q):
    """Where the confidence in a question comes from, taken from its checks."""
    passed = [c for c in q.get("checks") or [] if c.get("result") == "pass"]
    if any(c.get("kind") == "computed" and c.get("independent") for c in passed):
        return "code oracle"
    if any(c.get("kind") == "key_match" for c in passed):
        return "key match"
    return "Claude review only" if passed else "none"


def finding(source, code, message):
    return {"source": source, "code": code, "message": message}


def new_rec():
    return {"ans": None, "checks": [], "review": None, "findings": [], "status": None,
            "reason": "", "attempts": 0, "error": None, "score": None, "code_checks": []}


def decide_rec(rec):
    rec["status"], rec["reason"] = decide(rec["code_checks"], rec["review"], rec["ans"])

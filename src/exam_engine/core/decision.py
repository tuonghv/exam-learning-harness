"""PASS/FAIL/UNCERTAIN decision, evidence kind and the per-question record helpers.

No model call and no key access. phase-2 2.2 step 4: ai_review alone never gives PASS.
"""
import re

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


TIERS = ("verified", "likely_ok", "unknown", "likely_wrong")
_WRONG_CODES = {"second_differs", "image_differs", "adjudicated", "option_mismatch"}
_SOFT_CODES = {"malformed_output", "review_malformed"}  # a first round that needed repair
_OPERATOR = r"(?!\s*[=\u2248<>+*/^])"  # "A = 5" is a variable, not option A


def names_other_option(ans, keys):
    """75.3: the solver is only medium sure and its reason/issues name another option letter (an alternative
    reading, REQ-0082). Structural: standalone uppercase option key, not followed by an operator, level medium."""
    u = ans.get("uncertainty") or {}
    if u.get("level") != "medium" or not keys:
        return False
    text = " ".join([str(u.get("reason") or "")] + [str(x) for x in ans.get("issues") or []])
    chosen = str(ans.get("answer") or "").strip()
    return any(k != chosen and re.search(r"(?<![\w.])%s(?!\w)%s" % (re.escape(k), _OPERATOR), text)
               for k in keys)


def confidence(rec, keys=None):
    """75.3 tier beside the status, never an input to decide(): verified | likely_ok | unknown | likely_wrong,
    None for declined/open/no answer. Negative signals only; likely_ok needs an outside positive channel
    (image agrees) and no negative one. keys = option letters of the question."""
    ans = rec.get("ans")
    if not ans or declined(ans) or is_open(ans):
        return None
    if rec.get("status") == "PASS":
        return "verified"
    codes = {f.get("code") for f in rec.get("findings") or []}
    verdict = (rec.get("review") or {}).get("verdict")
    level = (ans.get("uncertainty") or {}).get("level")
    if (rec.get("status") == "FAIL" or verdict in ("disagree", "unsure") or codes & _WRONG_CODES
            or level == "high" or names_other_option(ans, keys)):
        return "likely_wrong"
    soft = (rec.get("attempts") or 0) > 1 or codes & _SOFT_CODES or level != "low"
    if (rec.get("reason") == "no_independent_check" and not soft
            and codes & {"second_agrees", "image_agrees"}):
        return "likely_ok"
    return "unknown"

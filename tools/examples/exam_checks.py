"""Deterministic checks, the PASS/FAIL/UNCERTAIN decision and key scoring.

Python 3.8 stdlib only. No model call and no key access here: `score` receives one
already-parsed key question from the caller (exam_run, SCORE stage only).
"""
import ast
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exam_parse as ep  # noqa: E402
import score_eval  # noqa: E402

MAX_EXPONENT = 100
MAX_EXPR_LEN = 200
_FUNCS = {"sqrt": math.sqrt, "log": math.log10, "ln": math.log, "exp": math.exp,
          "sin": math.sin, "cos": math.cos, "tan": math.tan, "abs": abs, "round": round}
_CONSTS = {"pi": math.pi, "e": math.e}
_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)
_NUM = re.compile(r"-?\d+(?:[.,]\d+)?")


MAX_DEPTH = 40
MAX_VALUE = 1e100


def safe_eval(expr):
    """Evaluate plain arithmetic; raises ValueError for anything outside the whitelist."""
    if not isinstance(expr, str) or not expr.strip() or len(expr) > MAX_EXPR_LEN:
        raise ValueError("bad expression")
    try:
        val = _ev(ast.parse(expr.strip(), mode="eval").body, 0)
    except (SyntaxError, ArithmeticError, TypeError, ValueError, MemoryError,
            RecursionError) as exc:
        if isinstance(exc, ValueError) and not str(exc).startswith("cannot evaluate"):
            raise
        raise ValueError("cannot evaluate: %s" % type(exc).__name__)
    if isinstance(val, complex) or not isinstance(val, (int, float)):
        raise ValueError("result is not a real number")
    return float(val)


def _lim(v):
    if isinstance(v, complex) or not isinstance(v, (int, float)):
        raise ValueError("result is not a real number")
    v = float(v)
    if not math.isfinite(v) or abs(v) > MAX_VALUE:
        raise ValueError("value out of range")
    return v


def _ev(n, depth):
    if depth > MAX_DEPTH:
        raise ValueError("expression too deep")
    d = depth + 1
    if isinstance(n, ast.Constant):
        if isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return _lim(n.value)
        raise ValueError("constant not allowed")
    if isinstance(n, ast.Name):
        if n.id in _CONSTS:
            return _CONSTS[n.id]
        raise ValueError("name not allowed: %s" % n.id)
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
        v = _ev(n.operand, d)
        return -v if isinstance(n.op, ast.USub) else v
    if isinstance(n, ast.BinOp) and isinstance(n.op, _BINOPS):
        a, b = _ev(n.left, d), _ev(n.right, d)
        op = n.op
        if isinstance(op, ast.Add):
            r = a + b
        elif isinstance(op, ast.Sub):
            r = a - b
        elif isinstance(op, ast.Mult):
            r = a * b
        elif isinstance(op, ast.Div):
            r = a / b
        elif isinstance(op, ast.Mod):
            r = a % b
        else:
            if abs(b) > MAX_EXPONENT:
                raise ValueError("exponent too large")
            r = a ** b
        return _lim(r)
    if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id in _FUNCS and not n.keywords
            and 1 <= len(n.args) <= (2 if n.func.id == "round" else 1)):
        args = [_ev(x, d) for x in n.args]
        if n.func.id == "round" and len(args) == 2:
            if args[1] != int(args[1]) or abs(args[1]) > 15:
                raise ValueError("round digits out of range")
            args[1] = int(args[1])
        return _lim(_FUNCS[n.func.id](*args))
    raise ValueError("node not allowed: %s" % type(n).__name__)


def declined(ans):
    """D4: the solver gave up on this question."""
    return (ans.get("answer_status") != "answered" or ans.get("answer") is None
            or not str(ans.get("answer")).strip())


def _chk(kind, detail, result, independent):
    return {"kind": kind, "detail": detail, "result": result, "independent": independent}


def _ws(s):
    return " ".join(str(s).split())


def _is_open(ans):
    return ep.norm(str(ans.get("answer") or "")) == "open"


def _letters(text):
    return re.findall(r"(?m)^\s*\(?([a-e])[.)]\s", text)


def _format(q, ans, exam):
    a = str(ans.get("answer")).strip()
    task = ((exam.get("fields") or {}).get("Task") or "").strip().casefold()
    if _is_open(ans) or (exam.get("fields") or {}).get("Subject", "").strip().casefold() \
            == "literature":
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
    if not out and _is_open(ans):
        out.append(_chk("quote", "no quote given", "unknown", False))
    return out


def det_checks(q, ans, exam):
    """Code-only checks for one question (empty when the solver declined, D4)."""
    if declined(ans):
        return []
    out = []
    if _is_open(ans):
        return [_format(q, ans, exam)] + _quotes(q, ans, exam)  # D7: format + quote only
    for c in (_format(q, ans, exam), _computed(ans)):
        if c:
            out.append(c)
    return out + _quotes(q, ans, exam)


def decide(checks, review, ans):
    """(status, reason); phase-2 2.2 step 4. ai_review alone never gives PASS."""
    if declined(ans):
        return "UNCERTAIN", "solver_declined"
    if _is_open(ans):
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


def score(ans, key_q):
    """{points, max, basis, detail}; the key is one parsed expected question."""
    final = (key_q or {}).get("final")
    if final is None:
        return {"points": None, "max": None, "basis": "none", "detail": "no key"}
    m = score_eval.match(ans.get("answer"), final)
    if m is None:
        return {"points": None, "max": None, "basis": "none", "detail": "open item"}
    return {"points": 1 if m else 0, "max": 1, "basis": "official_key",
            "detail": "matches key" if m else "differs_from_key"}

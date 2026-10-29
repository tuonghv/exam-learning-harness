"""Whitelisted arithmetic evaluator (no names, attributes or calls beyond _FUNCS)."""
import ast
import math

MAX_EXPONENT = 100
MAX_EXPR_LEN = 200
_FUNCS = {"sqrt": math.sqrt, "log": math.log10, "ln": math.log, "exp": math.exp,
          "sin": math.sin, "cos": math.cos, "tan": math.tan, "abs": abs, "round": round}
_CONSTS = {"pi": math.pi, "e": math.e}
_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)


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

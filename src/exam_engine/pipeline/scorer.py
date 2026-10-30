"""SCORE stage: the ONLY reader of answer keys (apply_key, score_file) and the eval scorer.

Usage: python3 -I scripts/exam.py score --answers-dir D [--keys-dir evals/keys]
Answers: D/<subject>/answer-NNN.md in the FORMAT expected layout; never prints key values.
Exit 0 scored, 2 usage error / overlapping dirs.
"""
import os
import re
import sys

from exam_engine import settings
from exam_engine.core.decision import declined, decide_rec, finding, is_open
from exam_engine.pipeline import parser
from exam_engine.utils.text import norm

_NUM = re.compile(r"^(-?\d+(?:[.,]\d+)?)\s*(.*)$")
_ORDER = re.compile(r"^[a-z](?:-[a-z])+$")


def _strip(s):
    return re.sub(r"^\s*[-*]\s*", "", s or "").strip()


def match(answer, key):
    """True/False, or None when the key is an open (rubric) item."""
    if answer is None:
        return False
    a, k = _strip(answer), _strip(key)
    if norm(k) == "open (rubric)":
        return None
    na, nk = norm(a), norm(k)
    if re.match(r"^[a-d]$", nk):
        m = re.match(r"^([a-d])(?:\.|\s|$)", na)
        return bool(m) and m.group(1) == nk
    sa, sk = na.replace(" ", ""), nk.replace(" ", "")
    if _ORDER.match(sk):
        return sa == sk
    mk, ma = _numparse(k), _numparse(a)
    if mk and not ma:
        tail = re.search(r"=\s*(-?\d+(?:[.,]\d+)?)\s*[.)]?\s*$", a)
        ma = _numparse(tail.group(1)) if tail else None
    if mk and ma:
        (kv, d, ke, unit_k), (av, _, ae, unit_a) = mk, ma
        return (_unit_ok(unit_k, unit_a)
                and abs(av * 10 ** ae - kv * 10 ** ke) <= (0.5 * 10 ** (-d) + 1e-12) * 10 ** ke)
    return na == nk


_SCI = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:[.·×x*]|\s)\s*10\s*\^\s*\{?(-?\d+)\}?")
_NUMX = re.compile(r"^(-?\d+(?:[.,]\d+)?)(?:e(-?\d+))?\s*(.*)$")


def _numparse(s):
    """(mantissa, decimals, exponent, unit) of a leading number; remarks in (...) are dropped."""
    t = re.sub(r"\s\([^)]*\)", " ", s.replace("−", "-"))
    t = _SCI.sub(lambda m: "%se%s" % (m.group(1), m.group(2)), t.strip())
    m = _NUMX.match(t.strip())
    if not m:
        return None
    mant = m.group(1).replace(",", ".")
    return (float(mant), len(mant.split(".")[1]) if "." in mant else 0,
            int(m.group(2) or 0), norm(m.group(3)).strip())


def _unit_ok(uk, ua):
    """Equal, one side bare, or one unit's words contained in the other's ('host' in 'dia chi host')."""
    if uk == ua or not uk or not ua:
        return True
    wk, wa = set(uk.split()), set(ua.split())
    return wk <= wa or wa <= wk


def score_file(ans, key):
    """[(question id, 'correct'|'wrong'|'missing'|'manual')]; ans may not exist."""
    keys = parser.parse_expected(key)["questions"]
    got = {}
    if ans and os.path.isfile(ans):
        got = dict((q["id"], q["final"]) for q in parser.parse_expected(ans)["questions"])
    out = []
    for q in keys:
        a = got.get(q["id"])
        if norm(q["final"] or "") == "open (rubric)":
            out.append((q["id"], "manual" if a else "missing"))
        elif not a:
            out.append((q["id"], "missing"))
        else:
            out.append((q["id"], "correct" if match(a, q["final"] or "") else "wrong"))
    return out


def score(ans, key_q):
    """{points, max, basis, detail}; the key is one parsed expected question."""
    final = (key_q or {}).get("final")
    if final is None:
        return {"points": None, "max": None, "basis": "none", "detail": "no key"}
    m = match(ans.get("answer"), final)
    if m is None:
        return {"points": None, "max": None, "basis": "none", "detail": "open item"}
    return {"points": 1 if m else 0, "max": 1, "basis": "official_key",
            "detail": "matches key" if m else "differs_from_key"}


def apply_key(recs, key_path):
    """SCORE: the key is opened only here, after every call."""
    keyq = {q["id"]: q for q in parser.parse_expected(key_path, legacy=True)["questions"]}
    for i, r in recs.items():
        a = r["ans"]
        if a is None or declined(a) or is_open(a):
            r["score"] = {"points": None, "max": None, "basis": "none",
                          "detail": "no key comparison (no answer or open task)"}
            continue
        s = score(a, keyq.get(i))
        r["score"] = s
        if s["basis"] != "official_key":
            continue
        if s["points"] == 0:
            r["status"], r["reason"] = "FAIL", "differs_from_key"
            r["findings"].append(finding("score", "differs_from_key", "answer differs from the key"))
        else:
            r["code_checks"].append({"kind": "key_match", "detail": "matches the key",
                                     "result": "pass", "independent": True})
            r["checks"].append(r["code_checks"][-1])
            if r["status"] == "UNCERTAIN":
                decide_rec(r)


def _inside(a, b):
    a, b = os.path.realpath(a), os.path.realpath(b)
    return a == b or a.startswith(b + os.sep) or b.startswith(a + os.sep)


def score_main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ans_dir, keys_dir = None, os.path.join(settings.ROOT, "evals", "keys")
    i = 0
    while i < len(argv):
        if argv[i] == "--answers-dir" and i + 1 < len(argv):
            ans_dir = argv[i + 1]
        elif argv[i] == "--keys-dir" and i + 1 < len(argv):
            keys_dir = argv[i + 1]
        else:
            ans_dir = None
            break
        i += 2
    if not ans_dir:
        print("usage: exam.py score --answers-dir D [--keys-dir evals/keys]", file=sys.stderr)
        return 2
    if _inside(ans_dir, keys_dir):
        print("ERROR: answers dir overlaps keys dir", file=sys.stderr)
        return 2
    if not os.path.isdir(ans_dir) or not os.path.isdir(keys_dir):
        print("ERROR: answers dir or keys dir not found", file=sys.stderr)
        return 2
    correct = total = 0
    for sub in sorted(os.listdir(keys_dir)):
        d = os.path.join(keys_dir, sub)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            m = re.match(r"^expected-(\d{3})\.md$", name)
            if not m:
                continue
            ans = os.path.join(ans_dir, sub, "answer-%s.md" % m.group(1))
            for qid, res in score_file(ans, os.path.join(d, name)):
                print("%s/%s Q%d: %s" % (sub, m.group(1), qid, res))
                if res != "manual":
                    total += 1
                    correct += res == "correct"
    print("TOTAL %d/%d" % (correct, total))
    return 0


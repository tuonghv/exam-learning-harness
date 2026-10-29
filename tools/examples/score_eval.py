"""Score solver answers against evals/keys (never prints key values).

Usage: python3 -I tools/examples/score_eval.py --answers-dir D [--keys-dir evals/keys]
Answers: D/<subject>/answer-NNN.md in the FORMAT expected layout.
Exit 0 scored, 2 usage error / overlapping dirs.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exam_parse as ep  # noqa: E402

_NUM = re.compile(r"^(-?\d+(?:[.,]\d+)?)\s*(.*)$")
_ORDER = re.compile(r"^[a-z](?:-[a-z])+$")


def _strip(s):
    return re.sub(r"^\s*[-*]\s*", "", s or "").strip()


def match(answer, key):
    """True/False, or None when the key is an open (rubric) item."""
    if answer is None:
        return False
    a, k = _strip(answer), _strip(key)
    if ep.norm(k) == "open (rubric)":
        return None
    na, nk = ep.norm(a), ep.norm(k)
    if re.match(r"^[a-d]$", nk):
        m = re.match(r"^([a-d])(?:\.|\s|$)", na)
        return bool(m) and m.group(1) == nk
    sa, sk = na.replace(" ", ""), nk.replace(" ", "")
    if _ORDER.match(sk):
        return sa == sk
    mk, ma = _NUM.match(k.replace("−", "-")), _NUM.match(a.replace("−", "-"))
    if mk and ma:
        kv, av = mk.group(1).replace(",", "."), ma.group(1).replace(",", ".")
        d = len(kv.split(".")[1]) if "." in kv else 0
        unit_k = ep.norm(mk.group(2)).replace(" ", "")
        unit_a = ep.norm(ma.group(2)).replace(" ", "")
        return unit_k == unit_a and abs(float(av) - float(kv)) <= 0.5 * 10 ** (-d) + 1e-12
    return na == nk


def score_file(ans, key):
    """[(question id, 'correct'|'wrong'|'missing'|'manual')]; ans may not exist."""
    keys = ep.parse_expected(key)["questions"]
    got = {}
    if ans and os.path.isfile(ans):
        got = dict((q["id"], q["final"]) for q in ep.parse_expected(ans)["questions"])
    out = []
    for q in keys:
        a = got.get(q["id"])
        if ep.norm(q["final"] or "") == "open (rubric)":
            out.append((q["id"], "manual" if a else "missing"))
        elif not a:
            out.append((q["id"], "missing"))
        else:
            out.append((q["id"], "correct" if match(a, q["final"] or "") else "wrong"))
    return out


def _inside(a, b):
    a, b = os.path.realpath(a), os.path.realpath(b)
    return a == b or a.startswith(b + os.sep) or b.startswith(a + os.sep)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ans_dir, keys_dir = None, os.path.join(root, "evals", "keys")
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
        print("usage: score_eval.py --answers-dir D [--keys-dir evals/keys]", file=sys.stderr)
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


if __name__ == "__main__":
    sys.exit(main())

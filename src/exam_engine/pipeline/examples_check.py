"""Validate few-shot and eval example pairs against examples/FORMAT.md.

Usage: python3 -I scripts/exam.py check-examples [--root DIR]
Exit 0 ok, 1 defects (one ERROR line each), 2 usage error.
"""
import hashlib
import os
import re
import sys

from exam_engine import settings
from exam_engine.pipeline import parser as ep, router

SUBJECTS = tuple(router.subjects())
TASKS = ("Multiple Choice", "Short Answer", "Sentence Ordering",
         "Reading Comprehension", "Essay")
MODES = ("Solve", "Grade", "Teach")
REQUIRED_HEADERS = ("Subject", "Level", "Exam type", "Task", "Mode")
BLOCKS = ("Solution", "Explanation", "Verification", "Grading")
KEY_HEADINGS = ("Solution", "Explanation", "Verification", "Grading",
                "Accepted interpretations", "Model answer outline")
LEGACY = {"examples/english/expected-001.md":
          "562d65e29cf5d1768cfa981dc2f6557f090c6273477a21c98bf21fb1ae251b8c"}
_FILE = re.compile(r"^(input|expected)-(\d{3})\.md$")
_QUOTE = re.compile(r'"([^"]+)"|“([^”]+)”')
_KEYLINE = re.compile(r"^\s*[-*]?\s*(Final answer|Correct answer|Status):", re.I)


def _rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _scan(root, base, errs):
    """{(subject, nnn, kind): path} under base/<subject>/."""
    found = {}
    if not os.path.isdir(base):
        return found
    for sub in sorted(os.listdir(base)):
        d = os.path.join(base, sub)
        if not os.path.isdir(d):
            continue
        if sub not in SUBJECTS:
            errs.append("ERROR: %s: pairing: unknown subject dir" % _rel(root, d))
            continue
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name)
            m = _FILE.match(name)
            if not m or not os.path.isfile(p):
                errs.append("ERROR: %s: pairing: stray file" % _rel(root, p))
            else:
                found[(sub, m.group(2), m.group(1))] = p
    return found


def _check_input(root, path, sub, errs):
    rel = _rel(root, path)

    def err(chk, msg):
        errs.append("ERROR: %s: %s: %s" % (rel, chk, msg))

    text = ep.read_text(path)
    ex = ep.parse_exam(path)
    f = ex["fields"]
    for k in REQUIRED_HEADERS:
        if not f.get(k):
            err("header", "missing %s" % k)
    if f.get("Subject") and router.subject_key(f["Subject"]) != sub:
        err("header", "Subject %r does not match dir %s" % (f["Subject"], sub))
    if f.get("Task") and f["Task"] not in TASKS:
        err("header", "bad Task %r" % f["Task"])
    if f.get("Mode") and f["Mode"] not in MODES:
        err("header", "bad Mode %r" % f["Mode"])
    if "Language" in f and f["Language"] not in ("vi", "en"):
        err("header", "bad Language %r" % f["Language"])
    titles = [t for t, _ in ep.sections(text, 2)]
    if "Instructions" not in titles:
        err("sections", "missing ## Instructions")
    ids = [q["id"] for q in ex["questions"]]
    if not ids:
        err("sections", "no ## Question N")
    elif ids != list(range(1, len(ids) + 1)):
        err("sections", "question ids not 1..n: %r" % ids)
    if f.get("Mode") == "Grade" and ex["learner_answer"] is None:
        err("sections", "Mode Grade needs ## Learner answer")
    # options
    mc = f.get("Task") == "Multiple Choice"
    for title, body in ep.sections(text, 2):
        if not re.match(r"^Question\s+\d+$", title):
            continue
        letters = re.findall(r"(?m)^([A-Z])\.\s+\S", body)
        if (mc or letters) and letters != ["A", "B", "C", "D"]:
            err("options", "%s: options are %s, need A,B,C,D once each in order"
                % (title, ",".join(letters) or "none"))
    # input-key
    for n, line in enumerate(text.splitlines(), 1):
        hm = re.match(r"^#+\s+(.*?)\s*$", line)
        if hm and (hm.group(1) == "Expected Output" or hm.group(1) in KEY_HEADINGS):
            err("input-key", 'line %d "%s"' % (n, line.strip()))
        elif _KEYLINE.match(line):
            err("input-key", 'line %d "%s:"' % (n, _KEYLINE.match(line).group(1)))
    return ex, f


def _verif(block):
    chk, fin, stat = 0, None, None
    for line in block.splitlines():
        if ep._value(line, "Check") is not None:
            chk += 1
        v = ep._value(line, "Final answer")
        if v is not None and fin is None:
            fin = v
        v = ep._value(line, "Status")
        if v is not None and stat is None:
            stat = v
    return chk, fin, stat


def _check_expected(root, path, sub, ex, fields, notes, errs):
    rel = _rel(root, path)

    def err(chk, msg):
        errs.append("ERROR: %s: %s: %s" % (rel, chk, msg))

    legacy = LEGACY.get(rel) == _sha(path)
    if legacy:
        notes.append("NOTE: legacy allowance: %s" % rel)
    exp = ep.parse_expected(path, legacy=legacy)
    qs = exp["questions"]
    want = [q["id"] for q in ex["questions"]]
    got = [q["id"] for q in qs]
    if got != want:
        err("sections", "question ids %r differ from input %r" % (got, want))
    mc = fields.get("Task") == "Multiple Choice"
    passage = ep.norm(ex["passage"])
    for q in qs:
        tag = "Question %d" % q["id"]
        b = q["blocks"]
        if not q["final"] and not legacy:
            err("sections", "%s: missing Final answer:" % tag)
        for name in BLOCKS:
            if name == "Grading" and legacy:
                continue
            if name not in b:
                err("sections", "%s: missing ### %s" % (tag, name))
        if mc and q["final"] and not re.match(r"^[A-D]\.?$", q["final"].strip()):
            err("options", "%s: Final answer %r not in A-D" % (tag, q["final"]))
        if "Verification" in b:
            chk, fin, stat = _verif(b["Verification"])
            if chk < 1 and not legacy:
                err("verification", "%s: no '- Check:' line" % tag)
            if fin is None or q["final"] is None or ep.norm(fin) != ep.norm(q["final"]):
                err("verification", "%s: Final answer %r differs from top %r"
                    % (tag, fin, q["final"]))
            if stat is None or ep.norm(stat) != "verified":
                err("verification", "%s: Status is not Verified" % tag)
        if sub == "literature":
            if not q["final"] or ep.norm(q["final"]) != "open (rubric)":
                err("literature", "%s: Final answer must be Open (rubric)" % tag)
            if "Model answer outline" not in b:
                err("literature", "%s: missing ### Model answer outline" % tag)
            interp = b.get("Accepted interpretations")
            if interp is None:
                err("literature", "%s: missing ### Accepted interpretations" % tag)
                continue
            quotes = [a or c for a, c in _QUOTE.findall(interp)]
            if len(quotes) < 2:
                err("literature", "%s: needs >= 2 quotes" % tag)
            for qt in quotes:
                if ep.norm(qt) not in passage:
                    err("literature", '%s: quote not in Passage: "%s"' % (tag, qt))


def _key_lines(path, legacy):
    """Normalised leak-prone lines of an eval key (quoted spans removed)."""
    out = []
    for q in ep.parse_expected(path, legacy=legacy)["questions"]:
        for name in ("Solution", "Explanation", "Accepted interpretations"):
            for line in q["blocks"].get(name, "").splitlines():
                line = ep.norm(_QUOTE.sub(" ", line))
                if len(line) >= 40:
                    out.append(line)
    return out


def _run(root):
    errs, notes = [], []
    few = _scan(root, os.path.join(root, "examples"), errs)
    ein = _scan(root, os.path.join(root, "evals", "inputs"), errs)
    ekey = _scan(root, os.path.join(root, "evals", "keys"), errs)
    # pairing
    for (sub, n, kind), p in sorted(few.items()):
        other = "expected" if kind == "input" else "input"
        if (sub, n, other) not in few:
            errs.append("ERROR: %s: pairing: no %s-%s.md" % (_rel(root, p), other, n))
    for (sub, n, kind), p in sorted(ein.items()):
        if kind != "input":
            errs.append("ERROR: %s: pairing: eval inputs dir holds only input files" % _rel(root, p))
        elif (sub, n, "expected") not in ekey:
            errs.append("ERROR: %s: pairing: no evals/keys/%s/expected-%s.md" % (_rel(root, p), sub, n))
    for (sub, n, kind), p in sorted(ekey.items()):
        if kind != "expected":
            errs.append("ERROR: %s: pairing: keys dir holds only expected files" % _rel(root, p))
        elif (sub, n, "input") not in ein:
            errs.append("ERROR: %s: pairing: no evals/inputs/%s/input-%s.md" % (_rel(root, p), sub, n))
    # disjoint ids
    few_ids = set((s, n) for (s, n, _k) in few)
    eval_ids = set((s, n) for (s, n, _k) in list(ein) + list(ekey))
    for s, n in sorted(few_ids & eval_ids):
        errs.append("ERROR: evals/inputs/%s/input-%s.md: disjoint-id: (%s, %s) also in few-shot"
                    % (s, n, s, n))
    # per-input checks, texts for disjoint-text
    seen = {}
    parsed = {}
    for group in (few, ein):
        for (sub, n, kind), p in sorted(group.items()):
            if kind != "input":
                continue
            ex, f = _check_input(root, p, sub, errs)
            parsed[(group is ein, sub, n)] = (ex, f)
            for q in ex["questions"]:
                key = ep.norm(q["text"] + " " + " ".join(
                    "%s. %s" % (k, v) for k, v in sorted(q["options"].items())))
                prev = seen.get(key)
                if prev and prev[0] != _rel(root, p):
                    errs.append("ERROR: %s: disjoint-text: Question %d repeats %s"
                                % (_rel(root, p), q["id"], prev[0]))
                else:
                    seen[key] = (_rel(root, p), q["id"])
    # expected checks (few-shot only: keys are checked below)
    for (sub, n, kind), p in sorted(few.items()):
        if kind == "expected" and (False, sub, n) in parsed:
            ex, f = parsed[(False, sub, n)]
            _check_expected(root, p, sub, ex, f, notes, errs)
    for (sub, n, kind), p in sorted(ekey.items()):
        if kind == "expected" and (True, sub, n) in parsed:
            ex, f = parsed[(True, sub, n)]
            _check_expected(root, p, sub, ex, f, notes, errs)
    # key-leak
    corpus = [(_rel(root, p), ep.norm(ep.read_text(p)))
              for (s, n, k), p in list(ein.items()) + list(few.items())]
    for (sub, n, kind), p in sorted(ekey.items()):
        if kind != "expected":
            continue
        rel = _rel(root, p)
        for line in _key_lines(p, LEGACY.get(rel) == _sha(p)):
            for crel, ctext in corpus:
                if line in ctext:
                    errs.append('ERROR: %s: key-leak: line appears in %s: "%s..."'
                                % (rel, crel, line[:30]))
    counts = (sum(1 for k in few if k[2] == "input"),
              sum(1 for k in ein if k[2] == "input"))
    return errs, notes, counts


def run_checks(root):
    return _run(root)[0]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = settings.ROOT
    if argv[:1] == ["--root"] and len(argv) == 2:
        root = argv[1]
    elif argv:
        print("usage: exam.py check-examples [--root DIR]", file=sys.stderr)
        return 2
    if not os.path.isdir(root):
        print("ERROR: root not found: %s" % root, file=sys.stderr)
        return 2
    errs, notes, (f, e) = _run(root)
    for line in notes:
        print(line)
    if errs:
        for line in errs:
            print(line)
        return 1
    print("OK: %d pairs (%d few-shot, %d eval)" % (f + e, f, e))
    return 0


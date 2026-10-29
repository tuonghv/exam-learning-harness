"""Command line: `solve` and the other subcommands behind scripts/exam.py.

solve: run one exam file through solve -> checks -> QA -> decide -> (key) -> result.json.
Exit 0 all PASS, 1 any FAIL/UNCERTAIN/unresolved, 2 invalid input or usage, 3 blocking stop.
Without --mock, --dry-run or --real nothing runs (never defaults to a real call).
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

from exam_engine import engine, settings
from exam_engine.adapters import claude
from exam_engine.core import schema as sch
from exam_engine.core.decision import decide
from exam_engine.pipeline import examples_check, parser, reporter, scorer, solver, verifier

COMMANDS = ("solve", "parse", "verify", "report", "check-examples", "score")
USAGE = "usage: exam.py {%s} ..." % "|".join(COMMANDS)


def solve_main(argv=None):
    d = settings.load_config("engine")
    ap = argparse.ArgumentParser(prog="exam solve",
                                 description="Run one exam file through solve -> checks -> QA "
                                             "-> decide -> (key) -> result.json.")
    ap.add_argument("exam")
    ap.add_argument("--out")
    ap.add_argument("--key")
    ap.add_argument("--mock")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--max-attempts", type=int, default=d["max_attempts"])
    ap.add_argument("--max-cost-usd", type=float, default=d["max_cost_usd"])
    ap.add_argument("--timeout", type=float, default=d["timeout"])
    ap.add_argument("--model", default=d["model"])
    ap.add_argument("--no-pdf", action="store_true", help="write report.md only")
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
           "model": a.model, "key": a.key, "llm_name": "claude-p" if a.real else "mock",
           "pdf": not a.no_pdf}
    if a.dry_run:
        try:
            text = parser.read_text(a.exam)
        except (OSError, UnicodeDecodeError) as exc:
            print("ERROR: input: cannot read %s: %s" % (a.exam, exc), file=sys.stderr)
            return 2
        exam = parser.parse_exam(a.exam)
        errs = parser.validate_exam(exam)
        if errs:
            for e in errs:
                print("ERROR: input: %s" % e, file=sys.stderr)
            return 2
        print("calls <= %d, cap $%.2f (dry run: no call made)" % (
            engine.call_cap(cfg), a.max_cost_usd))
        print("=== SOLVE prompt ===")
        print(solver.solve_prompt(exam, text, a.key))
        print("=== QA prompt template (answers are filled in from the SOLVE reply) ===")
        print(settings.read_prompt("verification/verify_answer.md"))
        print("=== retry prompt: solve prompt + only the open questions + non-key QA findings ===")
        return 0
    tmp = None
    try:
        if a.real:
            print("calls <= %d, cap $%.2f" % (engine.call_cap(cfg), a.max_cost_usd), flush=True)
            tmp = tempfile.mkdtemp(prefix="exam_run_")

            def llm(prompt):
                return claude.run_claude(prompt, model=a.model, timeout_s=a.timeout, cwd=tmp)
        else:
            llm = engine.mock_llm(a.mock)
        result, code = engine.run(a.exam, a.out, cfg, llm)
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
        rep_ = result.get("reports") or {}
        for key in ("md", "html", "pdf"):
            if rep_.get(key):
                print("report %s -> %s" % (key, rep_[key]))
        if rep_.get("pdf_status", "").startswith("skipped"):
            print("PDF %s" % rep_["pdf_status"])
    return code


def _load_exam(path):
    """(exam, None) or (None, exit code) after printing the errors."""
    try:
        exam = parser.parse_exam(path)
    except (OSError, UnicodeDecodeError) as exc:
        print("ERROR: input: cannot read %s: %s" % (path, exc), file=sys.stderr)
        return None, 2
    errs = parser.validate_exam(exam)
    for e in errs:
        print("ERROR: input: %s" % e, file=sys.stderr)
    return (None, 2) if errs else (exam, None)


def parse_main(argv):
    """parse EXAM.md: print the parsed exam as JSON (exit 2 when invalid)."""
    if len(argv) != 1:
        print("usage: exam.py parse EXAM.md", file=sys.stderr)
        return 2
    exam, code = _load_exam(argv[0])
    if exam is None:
        return code
    print(json.dumps(exam, ensure_ascii=False, indent=2))
    return 0


def verify_main(argv):
    """verify EXAM.md SOLVE_OUT.json: code checks + decision per question, no model call."""
    if len(argv) != 2:
        print("usage: exam.py verify EXAM.md SOLVE_OUT.json", file=sys.stderr)
        return 2
    exam, code = _load_exam(argv[0])
    if exam is None:
        return code
    try:
        obj, err = claude.extract_json(parser.read_text(argv[1]))
    except (OSError, UnicodeDecodeError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    problems = [err] if err else sch.validate(obj, sch.SOLVE_OUT)
    if problems:
        print("ERROR: solver output: %s" % problems[0], file=sys.stderr)
        return 2
    qs = dict((str(q["id"]), q) for q in exam["questions"])
    out = []
    for a in obj["questions"]:
        q = qs.get(a["id"])
        if q is None:
            continue
        checks = verifier.det_checks(q, a, exam)
        status, reason = decide(checks, None, a)
        out.append({"id": a["id"], "checks": checks, "status": status, "reason": reason})
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def report_main(argv):
    """report RESULT.json --out DIR [--no-pdf]: write report.md/html/pdf from a result."""
    args = [x for x in argv if x != "--no-pdf"]
    if len(args) != 3 or args[1] != "--out":
        print("usage: exam.py report RESULT.json --out DIR [--no-pdf]", file=sys.stderr)
        return 2
    try:
        result = settings.load_json(args[0])
        rep = reporter.write_reports(result, args[2], pdf="--no-pdf" not in argv)
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    for key in ("md", "html", "pdf"):
        if rep.get(key):
            print("report %s -> %s" % (key, rep[key]))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd, rest = (argv[0], argv[1:]) if argv else (None, [])
    table = {"solve": solve_main, "parse": parse_main, "verify": verify_main,
             "report": report_main, "check-examples": examples_check.main,
             "score": scorer.score_main}
    if cmd not in table:
        print(USAGE, file=sys.stderr)
        return 2
    return table[cmd](rest)

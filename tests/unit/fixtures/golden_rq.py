"""Retry + QA prompt hashes for every examples/ and evals/ input (TASK-055 golden).

compute(root) imports exam_engine from root/src; used by test_group_golden.py and to
regenerate golden_retry_qa.json from the baseline checkout (083d0e4)."""
import glob
import hashlib
import json
import os
import sys


def compute(root):
    sys.path.insert(0, os.path.join(root, "src"))
    from exam_engine.pipeline import parser, solver, verifier
    out = {}
    paths = sorted(glob.glob(os.path.join(root, "examples", "*", "input-*.md")) +
                   glob.glob(os.path.join(root, "evals", "inputs", "**", "*.md"), recursive=True))
    for p in paths:
        ex = parser.parse_exam(p)
        ids = [q["id"] for q in ex["questions"]]
        recs = {i: {"findings": [{"message": "check failed"}], "reason": "r", "checks": [
            {"kind": "k", "detail": "d", "result": "FAIL"}],
            "ans": {"answer": "A", "solution": "s", "explanation": "e"}} for i in ids}
        row = {}
        for name, fn in (("retry", lambda: solver.retry_prompt(ex, recs, ids)),
                         ("qa", lambda: verifier.qa_prompt(ex, recs, ids))):
            try:
                row[name] = hashlib.sha256(fn().encode()).hexdigest()
            except FileNotFoundError:
                row[name] = "NOPROMPT"
        out[os.path.relpath(p, root)] = row
    return out


if __name__ == "__main__":
    print(json.dumps(compute(os.path.abspath(sys.argv[1])), indent=1, sort_keys=True))

"""TASK-060 (60.1-60.3, 60.7): option value -> letter, saved-run recheck, needs_review_why, metrics rows.
Synthetic text, mock LLM, temp dirs only."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.core.decision import new_rec  # noqa: E402
from exam_engine.ingest import refine  # noqa: E402
from exam_engine.pipeline import metrics, review, solver, verifier  # noqa: E402

OPTS = {"A": "180%", "B": "205%", "C": "230%.", "D": "250%"}


class TestOptionForValue(unittest.TestCase):
    def test_value_matches_option(self):
        self.assertEqual(verifier.option_for_value("230%", OPTS), "C")

    def test_trailing_note_stripped(self):
        self.assertEqual(verifier.option_for_value("230% (rounded to integer)", OPTS), "C")

    def test_comma_and_dot_folded_unit_ignored(self):
        self.assertEqual(verifier.option_for_value("12,7", {"A": "9.1%/yr", "B": "12.7%/yr"}), "B")

    def test_same_number_twice_is_none(self):
        self.assertIsNone(verifier.option_for_value("5", {"A": "5 m", "B": "5 km", "C": "7"}))

    def test_option_with_two_numbers_never_matched(self):
        self.assertIsNone(verifier.option_for_value("2", {"A": "2 and 3", "B": "4"}))

    def test_no_number_or_no_match_is_none(self):
        self.assertIsNone(verifier.option_for_value("because", OPTS))
        self.assertIsNone(verifier.option_for_value("999", OPTS))

    def test_review_value_letter_with_note(self):
        stem = "Q?\nA. 180%\nB. 205%\nC. 230%\nD. 250%"
        self.assertEqual(review.value_letter("230% (rounded)", stem), "C")
        self.assertEqual(review.value_letter("230%", stem), "C")
        self.assertIsNone(review.value_letter("999", stem))


class FakeRn:
    def __init__(self, text):
        self.text = text

    def call(self, prompt, tag):
        return claude.Call(True, self.text, 0.0, "", "", 0.0)


class TestSolveRoundMapping(unittest.TestCase):
    def exam(self):
        return {"fields": {"Subject": "Science", "Task": "Multiple Choice"},
                "questions": [{"id": "1", "text": "Growth?", "options": dict(OPTS)}]}

    def run_round(self, answer):
        reply = {"schema_version": "1.0", "input_issues": [], "questions": [{
            "id": "1", "type": "multiple_choice", "answer": answer, "answer_status": "answered",
            "solution": ["s"], "explanation": "e", "checks": ["c"], "expr": None, "evidence": [],
            "uncertainty": {"level": "low", "reason": "r"},
            "reasoning_status": "not_independently_verified", "issues": []}]}
        recs = {"1": new_rec()}
        recs["1"]["attempts"] = 0
        solver.solve_round(self.exam(), FakeRn(json.dumps(reply)), recs, ["1"], "p")
        return recs["1"]

    def test_value_answer_mapped_and_format_passes(self):
        r = self.run_round("230%")
        self.assertEqual(r["ans"]["answer"], "C")
        self.assertIn("answer_mapped", [f["code"] for f in r["findings"]])
        fmt = [c for c in r["code_checks"] if c["kind"] == "format"][0]
        self.assertEqual(fmt["result"], "pass")

    def test_letter_answer_untouched(self):
        r = self.run_round("B")
        self.assertEqual(r["ans"]["answer"], "B")
        self.assertNotIn("answer_mapped", [f["code"] for f in r["findings"]])

    def test_unmatched_value_still_fails_format(self):
        r = self.run_round("999")
        self.assertEqual(r["ans"]["answer"], "999")
        fmt = [c for c in r["code_checks"] if c["kind"] == "format"][0]
        self.assertEqual(fmt["result"], "fail")


class TestRecheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="t60_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    @staticmethod
    def read(path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_cleared_and_read_only(self):
        exam_path = os.path.join(self.tmp, "exam.md")
        with open(exam_path, "w", encoding="utf-8") as f:
            f.write("# Exam Input\n\nSubject: Science\nLevel: Grade 12\nExam type: Test\n"
                    "Task: Multiple Choice\nMode: Solve\n\n## Instructions\n\nChoose.\n\n"
                    "## Question 1\n\nGrowth rate?\n\nA. 180%\nB. 230%\nC. 250%\nD. 300%\n\n"
                    "## Question 2\n\nPick the sum 4+4?\n\nA. 6\nB. 8\nC. 10\nD. 12\n")
        fmt_fail = [{"kind": "format", "detail": "single letter A-D", "result": "fail", "independent": False}]
        res = {"exam": {"subject": "Science"}, "run": {"calls": 1}, "questions": [
            {"id": "1", "answer": "230%", "status_reason": "check_failed: format",
             "verification_status": "FAIL", "checks": fmt_fail},
            {"id": "2", "answer": "8 (computed)", "status_reason": "check_failed: format",
             "verification_status": "FAIL", "checks": fmt_fail},
            {"id": "3", "answer": "B", "status_reason": "ok", "verification_status": "PASS", "checks": []}]}
        d = os.path.join(self.tmp, "run")
        os.makedirs(d)
        rp = os.path.join(d, "result.json")
        with open(rp, "w", encoding="utf-8") as f:
            json.dump(res, f)
        before = sorted(os.listdir(d)), self.read(rp)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["run-stats", "recheck", d, "--exam", exam_path,
                             "--history", os.path.join(self.tmp, "h.jsonl")])
        self.assertEqual(code, 0, err.getvalue())
        self.assertIn("cleared 2 still_failed 0", out.getvalue())
        self.assertEqual(before, (sorted(os.listdir(d)), self.read(rp)))


class TestMetricsRows(unittest.TestCase):
    def base(self, **extra):
        q = {"id": "1", "answer": "C", "verification_status": "PASS", "status_reason": "",
             "score": {"points": None, "max": None}, "uncertainty": {"level": "low", "reason": ""}}
        q.update(extra)
        return {"exam": {"subject": "Science"}, "questions": [q],
                "run": {"calls": 1, "cost_usd": 0.1, "stopped": None}}

    def test_pre60_has_no_new_keys(self):
        c = metrics.compute(self.base())["counts"]
        self.assertNotIn("answer_mapped", c)
        self.assertNotIn("needs_review_by_why", c)

    def test_new_counts_and_block(self):
        r = self.base(qa_findings=[{"code": "answer_mapped"}])
        m = metrics.compute(r, needs_review_why={"1": ["similarity", "gap"], "2": ["gap"]})
        self.assertEqual(m["counts"]["answer_mapped"], 1)
        self.assertEqual(m["counts"]["needs_review_by_why"], {"similarity": 1, "gap": 2})
        line = metrics.block(m)[0]
        self.assertIn("mapped 1", line)
        self.assertIn("gap=2", line)


class TestNeedsReviewWhy(unittest.TestCase):
    def test_codes(self):
        self.assertEqual(refine._why(False, True, False), ["similarity"])
        self.assertEqual(refine._why(False, False, True), ["gap"])
        self.assertEqual(refine._why(True, True, False), ["unreadable", "similarity"])
        self.assertEqual(refine._why(False, False, False), [])
        self.assertEqual(refine._add_why({"needs_review_why": ["gap"]}, "orphan_page"),
                         ["gap", "orphan_page"])


if __name__ == "__main__":
    unittest.main()

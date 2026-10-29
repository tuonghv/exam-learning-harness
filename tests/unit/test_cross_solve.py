"""Phase 20 (REQ-0023): cross-solve, two routes compared at answer level; $0, mocked calls only."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import test_ingest_refine as R  # noqa: E402
from exam_engine import cli  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.pipeline import cross, parser  # noqa: E402

EXAM = """# Exam Input

Subject: Mathematics
Level: Grade 12
Exam type: High School Graduation
Task: Short Answer
Mode: Solve
Language: vi

## Instructions

Giải.

## Question 1

Tính 1+1. Chọn:

A. 1
B. 2
C. 3
D. 4

## Question 2

Cho f.
a) A
b) B
c) C
d) D

## Question 3

Tính khoảng cách.
"""


def ans(i, a, status="answered"):
    return {"id": str(i), "answer": a, "answer_status": status, "solution": ["s"],
            "explanation": "e", "uncertainty": {"level": "low", "reason": ""},
            "reasoning_status": "not_independently_verified"}


def reply(*xs):
    return json.dumps({"questions": list(xs)})


A_OK = reply(ans(1, "B"), ans(2, "a-Đúng, b-Sai, c-Đúng, d-Sai"), ans(3, "3,46"))
B_OK = reply(ans(1, "B"), ans(2, "Đ, S, Đ, S"), ans(3, "3.46"))


class Fake:
    def __init__(self, texts):
        self.texts, self.calls = list(texts), []

    def __call__(self, prompt, imgs=None):
        self.calls.append(prompt)
        if not self.texts:
            return claude.Call(False, "", 0.0, "other", "exhausted", 0.0)
        return claude.Call(True, self.texts.pop(0), 0.01, "", "", 0.0)


class Base(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.dir = t.name
        self.exam_path = os.path.join(self.dir, "exam.md")
        with open(self.exam_path, "w", encoding="utf-8") as fh:
            fh.write(EXAM)
        self.exam = parser.parse_exam(self.exam_path)
        p = mock.patch.object(claude, "run_claude_images", side_effect=AssertionError("real"))
        p.start()
        self.addCleanup(p.stop)
        q = mock.patch.object(claude, "run_claude", side_effect=AssertionError("real"))
        q.start()
        self.addCleanup(q.stop)

    def go(self, a, b, **kw):
        fa, fb = Fake([a]), Fake([b])
        return cross.cross_solve(self.exam, EXAM, fa, fb, [b"x"], **kw), fa, fb


class Compare(Base):
    def test_agree_across_forms(self):
        res, fa, fb = self.go(A_OK, B_OK)
        self.assertEqual(res["summary"], {"questions": 3, "agree": 3, "needs_review": 0})
        self.assertEqual((len(fa.calls), len(fb.calls), res["calls"]), (1, 1, 2))
        self.assertIn("attached page images", fb.calls[0])
        self.assertNotIn("Tính khoảng cách", fb.calls[0])

    def test_seeded_corruptions_detected(self):
        for b2 in ("C", "-3,46", "3,64", "3,46 m^2"):
            a = reply(ans(1, "B"), ans(2, "Đ, S, Đ, S"), ans(3, "3,46"))
            b = reply(ans(1, "B" if b2 != "C" else "C"), ans(2, "Đ, S, Đ, S"),
                      ans(3, b2 if b2 != "C" else "3,46"))
            res, _, _ = self.go(a, b)
            self.assertEqual(res["summary"]["needs_review"], 1, b2)
            bad = [q for q in res["questions"] if q["status"] != "agree"][0]
            self.assertEqual(bad["reason"], "differ")

    def test_part_ii_one_verdict_flipped(self):
        b = reply(ans(1, "B"), ans(2, "Đ, S, S, S"), ans(3, "3.46"))
        res, _, _ = self.go(A_OK, b)
        self.assertEqual([q["id"] for q in res["questions"] if q["status"] != "agree"], ["2"])

    def test_missing_declined_and_count_mismatch(self):
        res, _, _ = self.go(A_OK, reply(ans(1, "B"), ans(2, "Đ, S, Đ, S"), ans(3, None, "uncertain")))
        self.assertEqual(res["questions"][2]["reason"], "declined_b")
        res, _, _ = self.go(reply(ans(1, "B"), ans(2, "Đ, S, Đ, S")), B_OK)
        self.assertEqual(res["questions"][2]["reason"], "missing_a")
        res, _, _ = self.go(A_OK, reply(ans(1, "B"), ans(2, "Đ, S, Đ, S")))
        self.assertEqual(set(q["reason"] for q in res["questions"]), {"count_mismatch"})
        self.assertEqual(res["summary"]["agree"], 0)

    def test_retry_then_error(self):
        fa, fb = Fake(["not json", A_OK]), Fake([B_OK])
        res = cross.cross_solve(self.exam, EXAM, fa, fb, [b"x"])
        self.assertEqual(res["calls"], 3)
        with self.assertRaises(cross.CrossError) as cm:
            cross.cross_solve(self.exam, EXAM, Fake(["x", "y"]), Fake([B_OK]), [b"x"])
        self.assertEqual(cm.exception.code, "invalid_reply")

    def test_cost_cap_and_failed_call(self):
        with self.assertRaises(cross.CrossError) as cm:
            cross.cross_solve(self.exam, EXAM, Fake([A_OK]), Fake([B_OK]), [b"x"], max_cost=0.01)
        self.assertEqual(cm.exception.code, "cost_cap")
        with self.assertRaises(cross.CrossError) as cm:
            cross.cross_solve(self.exam, EXAM, Fake([]), Fake([B_OK]), [b"x"])
        self.assertEqual(cm.exception.code, "call_failed")

    def test_mutation_compare_always_agree_is_caught(self):
        with mock.patch.object(cross, "same_answer", lambda a, b: True):
            res, _, _ = self.go(A_OK, reply(ans(1, "A"), ans(2, "Đ, S, Đ, S"), ans(3, "9")))
        self.assertEqual(res["summary"]["needs_review"], 0)  # the mutant hides it ...
        res, _, _ = self.go(A_OK, reply(ans(1, "A"), ans(2, "Đ, S, Đ, S"), ans(3, "9")))
        self.assertEqual(res["summary"]["needs_review"], 2)  # ... the real code does not


class Cli(Base):
    def doc(self, key=False):
        d = R.make_doc(key_page=key)
        path = os.path.join(self.dir, "doc.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        return path

    def run_cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["cross-solve"] + args)
        return code, out.getvalue(), err.getvalue()

    def mockfile(self, *texts):
        path = os.path.join(self.dir, "m.json")
        with open(path, "w") as fh:
            json.dump(list(texts), fh)
        return path

    def test_dry_run_no_call_and_prompts(self):
        code, out, _ = self.run_cli([self.exam_path, "--pdf", self.doc(), "--pages", "1-2",
                                     "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("calls <= 4", out)
        self.assertIn("ROUTE B prompt", out)

    def test_no_mode_is_usage_error(self):
        code, _, err = self.run_cli([self.exam_path, "--pdf", self.doc(), "--pages", "1"])
        self.assertEqual(code, 2)
        self.assertIn("never defaults to real", err)

    def test_mock_writes_cross_and_review(self):
        out_dir = os.path.join(self.dir, "o")
        code, out, _ = self.run_cli([self.exam_path, "--pdf", self.doc(), "--pages", "1-2",
                                     "--mock", self.mockfile(A_OK, B_OK), "--out", out_dir])
        self.assertEqual(code, 0, out)
        with open(os.path.join(out_dir, "review.md"), encoding="utf-8") as fh:
            self.assertIn("Nothing to review", fh.read())
        code, _, _ = self.run_cli([self.exam_path, "--pdf", self.doc(), "--pages", "1-2", "--mock",
                                   self.mockfile(A_OK, reply(ans(1, "C"), ans(2, "Đ, S, Đ, S"),
                                                             ans(3, "3.46"))), "--out", out_dir])
        self.assertEqual(code, 1)
        with open(os.path.join(out_dir, "review.md"), encoding="utf-8") as fh:
            self.assertIn("| 1 | B | C | differ |", fh.read())

    def test_key_pages_refused_and_absent_page(self):
        code, _, err = self.run_cli([self.exam_path, "--pdf", self.doc(key=True), "--pages", "3-4",
                                     "--dry-run"])
        self.assertEqual(code, 3)
        self.assertIn("answer_key_present", err)
        code, _, err = self.run_cli([self.exam_path, "--pdf", self.doc(), "--pages", "9",
                                     "--dry-run"])
        self.assertEqual(code, 2)
        self.assertIn("invalid_pages", err)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for tools/examples/exam_parse.py (design 3.1, AC1/AC4 support)."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TOOLS = os.path.join(ROOT, "tools", "examples")  # the old-command shims
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import parser as ep  # noqa: E402

INPUT = """# Exam Input

Subject: English
Level: Grade 12   # a comment
Task: Multiple Choice

## Instructions

Pick one.

## Passage

Some passage.

## Question 1

Fill ___ in.

A. have
B. had
C. will have
D. would have

## Question 2

Second?
"""

EXPECTED = """# Expected Output

## Question 1

Final answer: B

### Solution
because.

### Verification
- Check: ok
- Final answer: B
- Status: Verified

## Question 2

- Final answer: 2.5 m/s^2
"""

LEGACY = """Solution

Question 1

Correct answer: A. have

Explanation

why

Verification

* Final answer: A.
* Status: Verified.
"""


def _write(d, name, text):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


class ParseTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.d = self._td.name

    def test_norm(self):
        self.assertEqual(ep.norm("  Hello   WORLD. "), "hello world")
        self.assertEqual(ep.norm("A"), ep.norm(" a. "))

    def test_header_fields_strips_comment_and_stops_at_section(self):
        f = ep.header_fields(INPUT + "\nLate: x\n")
        self.assertEqual(f["Level"], "Grade 12")
        self.assertEqual(f["Subject"], "English")
        self.assertNotIn("Late", f)

    def test_parse_exam(self):
        ex = ep.parse_exam(_write(self.d, "input-001.md", INPUT))
        self.assertEqual([q["id"] for q in ex["questions"]], [1, 2])
        self.assertEqual(sorted(ex["questions"][0]["options"]), ["A", "B", "C", "D"])
        self.assertEqual(ex["questions"][0]["text"], "Fill ___ in.")
        self.assertEqual(ex["passage"], "Some passage.")
        self.assertIsNone(ex["learner_answer"])
        self.assertEqual(ex["instructions"], "Pick one.")

    def test_parse_expected_strict(self):
        qs = ep.parse_expected(_write(self.d, "e.md", EXPECTED))["questions"]
        self.assertEqual([q["id"] for q in qs], [1, 2])
        self.assertEqual(qs[0]["final"], "B")
        self.assertEqual(set(qs[0]["blocks"]), {"Solution", "Verification"})
        self.assertEqual(qs[1]["final"], "2.5 m/s^2")

    def test_parse_expected_legacy_only_when_asked(self):
        p = _write(self.d, "e.md", LEGACY)
        self.assertEqual(ep.parse_expected(p)["questions"], [])
        q = ep.parse_expected(p, legacy=True)["questions"][0]
        self.assertEqual(q["final"], "A")
        self.assertIn("Explanation", q["blocks"])
        self.assertIn("Solution", q["blocks"])


if __name__ == "__main__":
    unittest.main()

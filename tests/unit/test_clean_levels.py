"""TASK-054 (54.1-54.4): four-level labelled exam text at emission and parse."""
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import api, segment  # noqa: E402
from exam_engine.pipeline import parser, router  # noqa: E402

GUIDE = "Questions 31-35: Choose a suitable word or phrase (A, B, C, or D) to fill in each blank."
OPTS = {"A": "one", "B": "two", "C": "three", "D": "four"}
META = {"Subject": "English", "Level": "Grade 12", "Exam type": "Test", "Task": "Multiple Choice",
        "Mode": "Solve"}


class TestSplitHeading(unittest.TestCase):
    def test_subheading(self):
        self.assertEqual(segment.split_heading("1.2. TIẾNG ANH\n" + GUIDE), (["1.2. TIẾNG ANH"], GUIDE))

    def test_two_levels(self):
        h, rest = segment.split_heading("PHẦN 1: NGÔN NGỮ\n1.1. TIẾNG VIỆT\n" + GUIDE)
        self.assertEqual((h, rest), (["PHẦN 1: NGÔN NGỮ", "1.1. TIẾNG VIỆT"], GUIDE))

    def test_part_roman(self):
        self.assertEqual(segment.split_heading("PHẦN II\nText here."), (["PHẦN II"], "Text here."))

    @unittest.skipUnless(hasattr(router, "heading_subject"), "router.heading_subject (54.5)")
    def test_bare_subject(self):
        self.assertEqual(segment.split_heading("TOÁN\nCho hàm số")[0], ["TOÁN"])

    def test_not_peeled(self):
        for ctx in ("THE HISTORY OF TEA\nTea is old.", GUIDE, "", "Plain passage."):
            self.assertEqual(segment.split_heading(ctx), ([], ctx))

    def test_split_guide(self):
        self.assertEqual(segment.split_guide(GUIDE + "\nA passage."), (GUIDE, "A passage."))
        self.assertEqual(segment.split_guide("A passage."), ("", "A passage."))


def _qs():
    return [{"id": str(n), "text": "Stem %d ____ x." % n, "options": dict(OPTS),
             **({"context": "1.2. TIẾNG ANH\n" + GUIDE} if n == 31 else {})} for n in range(31, 36)]


def _check(tc, text, n_q=5):
    tc.assertEqual(text.count("## Section: 1.2. TIẾNG ANH"), 1)
    blocks = re.split(r"(?m)^## Question \d+$", text)[1:]
    tc.assertEqual(len(blocks), n_q)
    guide = "Choose a suitable word"
    for b in blocks[-5:]:
        tc.assertEqual(b.count("### Instruction for this group"), 1)
        tc.assertIn(guide, b)
        tc.assertIn("### Question text", b)
        tc.assertNotIn("TIẾNG ANH", b)


class TestEmission(unittest.TestCase):
    def test_refined_path(self):
        doc = {"source": {"name": "x"}, "meta": dict(META),
               "refined": {"questions": [dict(q, options=q["options"]) for q in _qs()]}}
        _check(self, api._from_refined(doc))

    def test_text_path(self):
        guide = GUIDE.replace("31-35", "2-6")
        opts = ["%s. %s" % kv for kv in OPTS.items()]
        lines = ["Câu 1. First ____."] + opts + ["1.2. TIẾNG ANH", guide]
        for n in range(2, 7):
            lines += ["Câu %d. Stem %d ____ x." % (n, n)] + opts
        _i, qs, _ok = segment.segment(lines)
        text = api._from_questions({"source": {"name": "x"}, "meta": dict(META), "questions": qs},
                                   ["# Exam Input", ""])
        _check(self, text, 6)

    def test_no_guide_keeps_old_lines(self):
        self.assertEqual(api.question_lines({"context": "Passage.", "text": "S"}), ["Passage.", "", "S", ""])


LABELLED = """# Exam Input

Subject: English
Level: Grade 12
Task: Multiple Choice

## Instructions

Pick one.

## Section: PHẦN 1 > 1.2. TIẾNG ANH

## Question 1

### Instruction for this group

%s

### Passage

Some text.

### Question text

Stem ____.

A. one
B. two
C. three
D. four

## Question 2

Plain stem.

A. a
B. b
C. c
D. d
""" % GUIDE


class TestParser(unittest.TestCase):
    def _parse(self, text):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "in.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
            return parser.parse_exam(p)

    def test_labelled(self):
        r = self._parse(LABELLED)
        self.assertEqual(r["sections"], ["PHẦN 1 > 1.2. TIẾNG ANH"])
        q1, q2 = r["questions"]
        self.assertEqual((q1["section"], q1["instruction"], q1["passage"], q1["stem"]),
                         ("PHẦN 1 > 1.2. TIẾNG ANH", GUIDE, "Some text.", "Stem ____."))
        self.assertEqual(q1["text"], GUIDE + "\n\nSome text.\n\nStem ____.")
        self.assertEqual(sorted(q1["options"]), ["A", "B", "C", "D"])
        self.assertEqual((q2["text"], q2["stem"], q2["instruction"]), ("Plain stem.", "Plain stem.", ""))

    def test_unlabelled_unchanged(self):
        r = self._parse(LABELLED.split("## Section")[0] + "## Question 1\n\nFill ___.\n\nA. a\nB. b\nC. c\nD. d\n")
        q = r["questions"][0]
        self.assertEqual((q["text"], q["stem"], q["section"], q["instruction"], q["passage"]),
                         ("Fill ___.", "Fill ___.", "", "", ""))
        self.assertEqual(r["sections"], [])


if __name__ == "__main__":
    unittest.main()

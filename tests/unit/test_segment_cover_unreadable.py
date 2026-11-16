"""TASK-122 (REQ-0129): cover run -> intro, image-only question kept as unreadable. Synthetic, $0."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import engine  # noqa: E402
from exam_engine.ingest import api  # noqa: E402
from exam_engine.ingest import segment  # noqa: E402

OPTS = ["%s. x" % k for k in "ABCD"]


def run(lines):
    starts = []
    intro, qs, ok = segment.segment(lines, starts=starts)
    return intro, qs, ok, starts


class CoverRun(unittest.TestCase):
    def test_t1_cover_becomes_intro(self):
        lines = ["1. Structure", "2. Strategy prose", "Part 1 (3 items)", "PART 1",
                 "1. Q a"] + OPTS + ["2. Q b"] + OPTS + ["3. Q c"] + OPTS
        intro, qs, ok, starts = run(lines)
        self.assertEqual([q["n"] for q in qs], [1, 2, 3])
        self.assertEqual(intro, lines[:2])
        self.assertEqual(qs[0]["context"], "Part 1 (3 items)\nPART 1")  # q1 keeps its whole context
        self.assertEqual(starts, [4, 9, 14])
        self.assertTrue(ok)

    def test_t2_leading_run_with_options_unchanged(self):
        lines = ["PART I", "1. a"] + OPTS + ["2. b"] + OPTS + ["PART II", "1. short", "2. short two"]
        _, qs, _, starts = run(lines)
        self.assertEqual(segment.runs(qs), [[1, 2], [1, 2]])
        self.assertEqual(len(starts), 4)

    def test_t3_both_runs_optionless_unchanged(self):
        lines = ["PART I", "1. essay a", "2. essay b", "PART II", "1. essay c", "2. essay d"]
        _, qs, _, _ = run(lines)
        self.assertEqual(segment.runs(qs), [[1, 2], [1, 2]])

    def test_t4_longer_leading_run_unchanged(self):
        lines = ["1. h", "2. h", "3. h", "PART 1", "1. a"] + OPTS + ["2. b"] + OPTS
        _, qs, _, _ = run(lines)
        self.assertEqual(segment.runs(qs), [[1, 2, 3], [1, 2]])

    def test_t8_essay_part_with_heading_stays(self):
        lines = ["PART I", "1. essay a", "PART II", "1. m a"] + OPTS + ["2. m b"] + OPTS + ["3. m c"] + OPTS
        intro, qs, _, starts = run(lines)
        self.assertEqual(segment.runs(qs), [[1], [1, 2, 3]])
        self.assertIn("PART I", intro)
        self.assertEqual(len(starts), 4)


class Unreadable(unittest.TestCase):
    def test_t5_empty_question_kept(self):
        _, qs, ok, _ = run(["1. a"] + OPTS + ["2."] + ["3. c"] + OPTS)
        self.assertEqual([q["n"] for q in qs], [1, 2, 3])
        self.assertEqual(qs[1]["text"], "")
        self.assertIs(qs[1]["unreadable"], True)
        self.assertNotIn("unreadable", qs[0])
        self.assertFalse(ok)
        self.assertTrue(segment.numbering(qs)["usable"])
        self.assertEqual(segment.numbering_warnings(qs), [])

    def test_t6_all_empty_not_usable(self):
        _, qs, _, _ = run(["1.", "2."])
        self.assertFalse(segment.numbering(qs)["usable"])

    def test_t7_decline_chain(self):
        _, qs, _, _ = run(["1. a"] + OPTS + ["2."] + ["3. c"] + OPTS)
        doc = {"source": {"name": "x.pdf"}, "intro": "", "questions": qs}
        text = api._from_questions(doc, ["## Header"])
        self.assertIn("[Incomplete: missing_text unreadable]", text.split("## Question 2")[1].split("## Question 3")[0])
        ex = {"questions": [{"id": k, "text": t} for k, t in
                            enumerate(text.split("## Question")[1:], 1)]}
        self.assertEqual(list(engine.incomplete_ids(ex)), [2])


if __name__ == "__main__":
    unittest.main()

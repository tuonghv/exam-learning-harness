"""TASK-121 (REQ-0128): segment rejects implausible question starts. $0, no network."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import boundary, segment  # noqa: E402


def q(n, text="Question"):
    return ["%d. %s %d" % (n, text, n)] + ["%s. opt %s" % (k, k) for k in "ABCD"]


def run(lines, **kw):
    starts = []
    _, qs, ok = segment.segment(lines, starts=starts, **kw)
    return qs, ok, starts


class TestPlausible(unittest.TestCase):
    def test_passage_paragraphs_are_context(self):
        lines = (q(45) + ["Questions 46-47: Read the passage.", "1. Para one.", "2. Para two."]
                 + q(46) + q(47))
        qs, _, starts = run(lines)
        self.assertEqual([x["n"] for x in qs], [45, 46, 47])
        self.assertEqual(len(starts), 3)
        ctx = qs[1].get("context", "")
        for part in ("Questions 46-47", "Para one", "Para two"):
            self.assertIn(part, ctx)

    def test_year_is_context(self):
        lines = (q(108) + ["Questions 109-110: Use the text.", "1991. In 1991 the war ended."]
                 + q(109) + q(110))
        qs, _, _ = run(lines)
        self.assertEqual([x["n"] for x in qs], [108, 109, 110])
        self.assertIn("1991", qs[1].get("context", ""))

    def test_figures_glue_to_option(self):
        lines = q(62) + ["3) + ac", "2) + bc"] + q(63)
        qs, _, _ = run(lines)
        self.assertEqual([x["n"] for x in qs], [62, 63])
        self.assertIn("3) + ac", qs[0]["options"][-1]["text"])

    def test_restart_at_heading_kept(self):
        lines = ["PART I"] + q(1) + q(2) + q(3) + ["PART II"] + q(1) + q(2)
        qs, _, _ = run(lines)
        self.assertEqual([x["n"] for x in qs], [1, 2, 3, 1, 2])
        info = segment.numbering(qs)
        self.assertTrue(info["usable"])
        self.assertIn("numbering_restarted", [c for c, _ in segment.numbering_warnings(qs)])

    def test_restart_without_heading_kept(self):
        lines = []
        for n in (1, 2, 3, 1, 2, 3, 4, 5):
            lines += q(n)
        qs, _, _ = run(lines)
        self.assertEqual([x["n"] for x in qs], [1, 2, 3, 1, 2, 3, 4, 5])

    def test_duplicate_merged_only_when_next_comes(self):
        lines = []
        for n in (1, 2, 3, 4):
            lines += q(n)
        lines += ["4) x"] + q(5)
        qs, _, _ = run(lines)
        self.assertEqual([x["n"] for x in qs], [1, 2, 3, 4, 5])
        qs, _, _ = run(q(1) + q(2) + q(2))
        self.assertEqual([x["n"] for x in qs], [1, 2, 2])

    def test_hint_on_rejected_line_reported(self):
        lines = q(45) + ["1. Para one."] + q(46)
        idx = lines.index("1. Para one.")
        rep = []
        qs, _, _ = run(lines, hints={idx: ("question_start", 0.9)}, report=rep)
        self.assertEqual([x["n"] for x in qs], [45, 46])
        rej = [r for r in rep if r["code"] == "boundary_ai_rejected"]
        self.assertEqual([(r["line"], r["reason"]) for r in rej], [(idx, "numbering")])
        warns = boundary.report_warnings(rep)
        self.assertEqual(warns[0]["code"], "boundary_ai_rejected")
        self.assertIn("rejected (numbering)", warns[0]["message"])

    def test_implausible_table(self):
        f = segment._implausible
        self.assertTrue(f(1, 45, [2, 3, 46]))
        self.assertFalse(f(1, 4, [2, 3, 4, 5]))
        self.assertFalse(f(150, 1, []))
        self.assertTrue(f(4, 4, [1, 2, 5]))
        self.assertFalse(f(1, 2, [2, 3]))


if __name__ == "__main__":
    unittest.main()

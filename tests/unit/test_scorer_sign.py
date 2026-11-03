"""TASK-068 / 68.1: scorer.match keeps a leading sign."""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import scorer  # noqa: E402


class SignTest(unittest.TestCase):
    def test_68_neg_answer_pos_key(self):
        self.assertFalse(scorer.match("-x", "x"))
        self.assertFalse(scorer.match("-sqrt(2)", "sqrt(2)"))

    def test_68_pos_answer_neg_key(self):
        self.assertFalse(scorer.match("x", "-x"))
        self.assertFalse(scorer.match("sqrt(2)", "-sqrt(2)"))

    def test_68_unicode_minus(self):
        self.assertFalse(scorer.match("−x", "x"))
        self.assertFalse(scorer.match("x", "−x"))
        self.assertTrue(scorer.match("−x", "-x"))

    def test_68_bullet_is_not_sign(self):
        self.assertTrue(scorer.match("- x", "x"))
        self.assertTrue(scorer.match("- sqrt(2)", "sqrt(2)"))

    def test_68_same_sign_matches(self):
        self.assertTrue(scorer.match("-3", "-3"))
        self.assertTrue(scorer.match("-x", "-x"))

    def test_68_numbers_and_fractions(self):
        self.assertFalse(scorer.match("-3", "3"))
        self.assertFalse(scorer.match("3", "-3"))
        self.assertFalse(scorer.match("-1/2", "1/2"))
        self.assertFalse(scorer.match("1/2", "-1/2"))
        self.assertTrue(scorer.match("x = -3", "-3"))

    def test_68_unchanged_kinds(self):
        self.assertTrue(scorer.match("b", "b"))
        self.assertTrue(scorer.match("b. text", "b"))
        self.assertFalse(scorer.match("c", "b"))
        self.assertTrue(scorer.match("a-b-c", "a-b-c"))
        self.assertTrue(scorer.match("Dung", "Dung"))
        self.assertIsNone(scorer.match("x", "open (rubric)"))
        self.assertFalse(scorer.match(None, "x"))

    def test_68_note_cases_unchanged(self):
        self.assertTrue(scorer.match("sqrt(2) (1.41)", "sqrt(2)"))
        self.assertFalse(scorer.match("sqrt(2) (1.5)", "sqrt(2)"))
        self.assertTrue(scorer.match("-sqrt(2) (-1.41)", "-sqrt(2)"))
        self.assertFalse(scorer.match("-sqrt(2) (1.41)", "-sqrt(2)"))


if __name__ == "__main__":
    unittest.main()

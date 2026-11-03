"""TASK-068 / 68.1 QA: sign adversarial table and mutation-killing cases (extends test_scorer_sign)."""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import scorer  # noqa: E402

M = "−"


class SignQaTest(unittest.TestCase):
    def test_68_unicode_minus_numbers(self):
        self.assertTrue(scorer.match(M + "3", "-3"))
        self.assertTrue(scorer.match("-3", M + "3"))
        self.assertTrue(scorer.match(M + "x", M + "x"))
        self.assertFalse(scorer.match(M + "3", "3"))
        self.assertFalse(scorer.match("3", M + "3"))

    def test_68_unicode_minus_with_space_is_sign(self):
        # U+2212 is never a bullet, so "- x" style spacing after it still carries the sign
        self.assertFalse(scorer.match(M + " x", "x"))
        self.assertFalse(scorer.match(M + " 3", "3"))

    def test_68_bullet_with_space_vs_number_and_star(self):
        self.assertTrue(scorer.match("- 3", "3"))
        self.assertTrue(scorer.match("3", "- 3"))
        self.assertTrue(scorer.match("* x", "x"))
        self.assertTrue(scorer.match("- 1", "1"))

    def test_68_dash_is_binary_not_sign(self):
        self.assertFalse(scorer.match("x-1", "x+1"))
        self.assertTrue(scorer.match("x-1", "x-1"))
        self.assertTrue(scorer.match("a-b-c", "a-b-c"))
        self.assertFalse(scorer.match("-a-b-c", "a-b-c"))

    def test_68_en_em_dash_not_sign(self):
        self.assertFalse(scorer.match("–x", "x"))
        self.assertFalse(scorer.match("—x", "x"))
        self.assertFalse(scorer.match("x", "–x"))

    def test_68_option_letters_and_bool(self):
        self.assertFalse(scorer.match("-a", "a"))
        self.assertFalse(scorer.match("a", "-a"))
        self.assertTrue(scorer.match("a.", "a"))
        self.assertTrue(scorer.match("true", "true"))
        self.assertFalse(scorer.match("-true", "true"))

    def test_68_open_rubric_ignores_sign(self):
        self.assertIsNone(scorer.match("-x", "open (rubric)"))
        self.assertIsNone(scorer.match("x", "- open (rubric)"))

    def test_68_decimals_and_zero(self):
        self.assertFalse(scorer.match("-1.5", "1.5"))
        self.assertFalse(scorer.match("-1,5", "1,5"))
        self.assertTrue(scorer.match("-1.5", "-1.5"))
        self.assertTrue(scorer.match("-0", "0"))

    def test_68_notes_with_sign(self):
        self.assertTrue(scorer.match("3 (approx)", "3"))
        self.assertFalse(scorer.match("-3 (approx)", "3"))
        self.assertFalse(scorer.match("3 (approx)", "-3"))
        self.assertTrue(scorer.match("-3 (approx)", "-3"))
        self.assertTrue(scorer.match("-sqrt(2) (-1.41)", "-sqrt(2)"))
        self.assertFalse(scorer.match("-sqrt(2) (1.41)", "-sqrt(2)"))
        self.assertTrue(scorer.match("sqrt(2) (1.41)", "sqrt(2)"))
        self.assertFalse(scorer.match("-sqrt(2) (-1.41)", "sqrt(2)"))


if __name__ == "__main__":
    unittest.main()

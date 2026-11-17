"""TASK-144 / 144.1-144.2: numeric tolerance is exclusive at the half unit; no decimal for a fraction key."""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import scorer  # noqa: E402


class StrictHalfTest(unittest.TestCase):
    def test_exact_half_is_wrong(self):
        for ans, key in (("5.5", "5"), ("4.5", "5"), ("3.465", "3.46"), ("0.125", "0.12")):
            self.assertFalse(scorer.match(ans, key), (ans, key))

    def test_rounding_still_correct(self):
        for ans, key in (("5.49", "5"), ("4.51", "5"), ("3.457", "3.46"), ("5", "5"), ("3.46", "3.46")):
            self.assertTrue(scorer.match(ans, key), (ans, key))

    def test_scientific_unchanged(self):
        self.assertTrue(scorer.match("1.8e-19", "1,8.10^-19"))
        self.assertTrue(scorer.match("1.8e-19", "1.8e-19"))
        self.assertFalse(scorer.match("1.85e-19", "1.8e-19"))

    def test_note_match_half(self):
        self.assertFalse(scorer._note_match("1.5 (1)", "1.5"))
        self.assertFalse(scorer._note_match("0.125 (0.12)", "0.125"))
        self.assertTrue(scorer._note_match("1.49 (1)", "1.49"))

    def test_fraction_key_no_decimal(self):
        # 144.2: passes on the old code too (exact fraction compare since TASK-138)
        self.assertFalse(scorer.match("4.67", "14/3"))
        self.assertTrue(scorer.match("28/6", "14/3"))


if __name__ == "__main__":
    unittest.main()

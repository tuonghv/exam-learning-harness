"""TASK-067 (phase 67): a trailing note keeps the key match."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
from exam_engine.pipeline import scorer as se  # noqa: E402
from exam_engine.pipeline import verifier as vf  # noqa: E402


class AnswerNoteMatch(unittest.TestCase):
    def test_67_note_consistent(self):
        self.assertTrue(se.match("sqrt(2) (xấp xỉ 1.4142)", "sqrt(2)"))
        self.assertTrue(se.match("sqrt(2) (khoảng 1.4142)", "sqrt(2)"))
        self.assertTrue(se.match("sqrt(2) (approx)", "sqrt(2)"))

    def test_67_wrong_value_or_note_fails(self):
        self.assertFalse(se.match("sqrt(3) (xấp xỉ 1.4142)", "sqrt(2)"))
        self.assertFalse(se.match("sqrt(3) (khoảng 1.7321)", "sqrt(2)"))
        self.assertFalse(se.match("sqrt(2) (xấp xỉ 1.7321)", "sqrt(2)"))
        self.assertFalse(se.match("sqrt(2) (or 2, 3)", "sqrt(2)"))
        self.assertFalse(se.match("abc (1.5)", "abc"))
        self.assertFalse(se.match("x(2)", "x"))

    def test_67_sign_kept(self):
        self.assertFalse(se.match("-sqrt(2) (xấp xỉ 1.4142)", "sqrt(2)"))
        self.assertFalse(se.match("-sqrt(2) (xấp xỉ -1.4142)", "sqrt(2)"))
        self.assertFalse(se.match("\u2212sqrt(2) (xấp xỉ 1.4142)", "sqrt(2)"))
        self.assertFalse(se.match("sqrt(2) (xấp xỉ 1.4142)", "-sqrt(2)"))
        self.assertFalse(se.match("sqrt(2) (xấp xỉ 1.4142)", "\u2212sqrt(2)"))
        self.assertTrue(se.match("-sqrt(2) (xấp xỉ -1.4142)", "-sqrt(2)"))
        self.assertTrue(se.match("\u2212sqrt(2) (xấp xỉ -1.4142)", "-sqrt(2)"))
        self.assertTrue(se.match("-sqrt(2) (approx)", "\u2212sqrt(2)"))
        self.assertFalse(se.match("-sqrt(2) (approx)", "sqrt(2)"))

    def test_67_unchanged(self):
        self.assertTrue(se.match("2.5 (approx) m/s^2", "2.50 m/s^2"))
        self.assertTrue(se.match("1/2", "1/2"))
        self.assertFalse(se.match("1/3 (0.5)", "1/2"))
        self.assertFalse(se.match("1/2; 3", "1/2"))
        self.assertTrue(se.match("sqrt(2)", "sqrt(2)"))
        self.assertFalse(se.match("foo", "foo (rubric)"))
        self.assertTrue(se.match("foo (rubric)", "foo (rubric)"))

    def test_67_tail_note_not_mangled(self):
        self.assertEqual(vf._TAIL_NOTE.sub("", "sqrt(2)"), "sqrt(2)")
        self.assertEqual(vf._TAIL_NOTE.sub("", "f(2)"), "f(2)")
        self.assertEqual(vf._TAIL_NOTE.sub("", "3 (approx)"), "3")

    def test_67_replay_apply_key(self):
        with tempfile.TemporaryDirectory() as d:
            kp = os.path.join(d, "key.md")
            with open(kp, "w") as f:
                f.write("# Expected Output\n\n## Question 1\n\nFinal answer: sqrt(2)\n")
            def rec(a):
                return {1: {"ans": {"answer": a, "answer_status": "answered"}, "status": "PASS", "reason": "",
                              "findings": [], "code_checks": [], "checks": []}}
            r = rec("sqrt(2) (xấp xỉ 1.4142)")
            se.apply_key(r, kp)
            self.assertEqual(r[1]["score"]["points"], 1)
            self.assertEqual(r[1]["status"], "PASS")
            self.assertEqual(r[1]["code_checks"][0]["kind"], "key_match")
            r = rec("sqrt(3) (xấp xỉ 1.4142)")
            se.apply_key(r, kp)
            self.assertEqual(r[1]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()

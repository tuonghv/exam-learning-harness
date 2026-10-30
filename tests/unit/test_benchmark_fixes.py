"""REQ-0009 AC4: false FAILs found by the real benchmark (work/exam-runs/2026-10-30-v120/FINDINGS.md)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))
from exam_engine.pipeline import scorer, verifier  # noqa: E402


def comp(expr, answer):
    return verifier._computed({"expr": expr, "answer": answer})["result"]


class Fixes(unittest.TestCase):
    def test_computed_fraction_sqrt_sci(self):  # math/004, math/005, physics/005
        self.assertEqual(comp("1 - 10/84", "37/42"), "pass")
        self.assertEqual(comp("(10/5)**0.5", "sqrt(2)"), "pass")
        self.assertEqual(comp("6.625e-34*3e8/0.30e-6 - 3.0*1.6e-19", "1.8e-19 J (làm tròn)"), "pass")

    def test_computed_still_catches_wrong(self):
        self.assertEqual(comp("1 - 10/84", "36/42"), "fail")
        self.assertEqual(comp("(10/5)**0.5", "sqrt(3)"), "fail")
        self.assertEqual(comp("6.625e-34*3e8/0.30e-6 - 3.0*1.6e-19", "1.8e-18 J"), "fail")
        self.assertEqual(comp("2+2", "5"), "fail")
        self.assertEqual(comp("2+2", "4"), "pass")

    def test_quote_with_label(self):  # english/004
        exam = {"passage": "", "questions": []}
        q = {"text": "a. However, she soon realised.\nb. Last year, Linh decided.", "options": {}}
        ok = verifier._quotes(q, {"evidence": ["b: Last year, Linh decided."]}, exam)
        bad = verifier._quotes(q, {"evidence": ["b: Never said this."]}, exam)
        self.assertEqual((ok[0]["result"], bad[0]["result"]), ("pass", "fail"))

    def test_key_match_remarks_units_sci(self):  # physics/004, informatics/005, physics/005
        m = scorer.match
        self.assertTrue(m("9 điểm", "9 (cực đại)"))
        self.assertTrue(m("62 host", "62 địa chỉ host"))
        self.assertTrue(m("1.8e-19 J (làm tròn đến 2 chữ số có nghĩa)", "1,8.10^-19 J"))

    def test_key_match_still_strict(self):
        m = scorer.match
        self.assertFalse(m("10", "9 (cực đại)"))
        self.assertFalse(m("5 m", "5 s"))
        self.assertFalse(m("1.8e-18 J", "1,8.10^-19 J"))
        self.assertFalse(m("63 host", "62 địa chỉ host"))
        self.assertTrue(m("3,46", "3.46"))
        self.assertTrue(m("B. 2", "B"))


if __name__ == "__main__":
    unittest.main()

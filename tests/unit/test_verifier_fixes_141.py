"""TASK-141: verifier fixes from review batch 4 (one test per id)."""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import scorer  # noqa: E402
from exam_engine.pipeline import verifier as v  # noqa: E402


def _comp(expr, answer):
    return v._computed({"expr": expr, "answer": answer})["result"]


class VerifierFixes141(unittest.TestCase):
    def test_f005_label_before_value(self):
        self.assertEqual(_comp("1/2", "x = 1/2"), "pass")
        self.assertEqual(_comp("10", "v2 = 10"), "pass")
        self.assertEqual(_comp("1/2", "1/2"), "pass")

    def test_f006_sqrt_sign(self):
        self.assertEqual(_comp("sqrt(3)/2", "√3/2"), "pass")
        self.assertEqual(_comp("2*sqrt(3)", "2√3"), "pass")
        self.assertEqual(_comp("sqrt(3)/2", "√3/3"), "fail")
        self.assertAlmostEqual(scorer._exact_value("√3/2"), 0.8660254, places=6)
        self.assertAlmostEqual(scorer._exact_value("2√3"), 3.4641016, places=6)

    def test_f007_ordering_six_letters(self):
        text = "".join("%s. s%s\n" % (c, c) for c in "abcdef")
        q = {"text": text}
        exam = {"fields": {"Task": "Sentence ordering", "Subject": "English"}}
        r = v._format(q, {"answer": "a-b-c-d-e-f"}, exam)
        self.assertEqual(r["result"], "pass")

    def test_d4_label_only_quote(self):
        q = {"text": "Q", "options": {"A": "x", "B": "y"}}
        exam = {"passage": "some passage text"}
        for quote in ("B. ", "B."):
            out = v._quotes(q, {"evidence": [quote]}, exam)
            self.assertEqual([c["result"] for c in out], ["fail"], quote)


if __name__ == "__main__":
    unittest.main()

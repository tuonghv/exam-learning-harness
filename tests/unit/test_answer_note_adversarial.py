"""TASK-067 QA: adversarial false-pass / false-fail probes for the value-part note match."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
from exam_engine.pipeline import scorer as se  # noqa: E402
from exam_engine.pipeline import verifier as vf  # noqa: E402

MUST_FAIL = [
    ("sqrt(3) (approx 1.4142)", "sqrt(2)"),
    ("sqrt(3) (sqrt(2))", "sqrt(2)"),
    ("sqrt(3) (= sqrt(2))", "sqrt(2)"),
    ("sqrt(2) (1.7)", "sqrt(2)"),
    ("sqrt(2) (xấp xỉ 1.5)", "sqrt(2)"),
    ("sqrt(2) (xấp xỉ -1.4142)", "sqrt(2)"),
    ("sqrt(2) (xấp xỉ 1,4143)", "sqrt(2)"),
    ("2", "sqrt(2)"),
    ("sqrt(2); 3", "sqrt(2)"),
    ("sqrt(2) (xấp xỉ 1.4142); 3", "sqrt(2)"),
    ("1/2", "2/1"),
    ("2/1", "1/2"),
    ("(xấp xỉ 1.4142)", "sqrt(2)"),
    ("(sqrt(2))", "sqrt(2)"),
    ("sqrt(2) (a) (xấp xỉ 1.4142)", "sqrt(2)"),
    ("sqrt(2) m (approx 1.4142)", "sqrt(2)"),
    ("2sqrt(2) (xấp xỉ 1.4142)", "sqrt(2)"),
    ("sqrt(2) (2.0)", "sqrt(2)"),
    ("sqrt(2)+1 (approx)", "sqrt(2)"),
    ("2sqrt(2) (approx)", "sqrt(2)"),
    ("sqrt(2) (xấp xỉ 1.4142 hoặc 3)", "sqrt(2)"),
    ("sqrt(2) (xấp xỉ 1.4142, 2)", "sqrt(2)"),
    ("abc (1.5)", "abc"),
]
MUST_PASS = [
    ("sqrt(2) (xấp xỉ 1,4142)", "sqrt(2)"),
    ("sqrt(2) (xấp xỉ 1.41)", "sqrt(2)"),
    ("sqrt(2) (xấp xỉ 1.4142).", "sqrt(2)"),
    ("−sqrt(2) (xấp xỉ −1.4142)", "−sqrt(2)"),
    ("1/2 (0.5)", "1/2"),
]


class NoteAdversarial(unittest.TestCase):
    def test_67_qa_must_fail(self):
        for a, k in MUST_FAIL:
            with self.subTest(a=a, k=k):
                self.assertFalse(se.match(a, k))

    def test_67_qa_must_pass(self):
        for a, k in MUST_PASS:
            with self.subTest(a=a, k=k):
                self.assertTrue(se.match(a, k))

    def test_67_qa_tail_note(self):
        for s in ("sqrt(2)", "f(2)", "x(m)", "5(x)"):
            self.assertEqual(vf._TAIL_NOTE.sub("", s), s)
        self.assertEqual(vf._TAIL_NOTE.sub("", "x (m)"), "x")
        self.assertEqual(vf._TAIL_NOTE.sub("", "3 (approx)."), "3")

    def test_67_qa_key_never_stripped(self):
        # a key that itself carries a (note) is compared whole, not value-part only
        self.assertFalse(se.match("foo", "foo (1.5)"))
        self.assertFalse(se.match("foo (2.5)", "foo (1.5)"))


if __name__ == "__main__":
    unittest.main()

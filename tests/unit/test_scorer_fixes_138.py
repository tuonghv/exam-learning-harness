"""TASK-138: scorer fixes from review batch 4 (one test per ledger id)."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.core.decision import new_rec  # noqa: E402
from exam_engine.pipeline import scorer  # noqa: E402


def _file(d, name, text):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _key(final, legacy=False):
    head = "Correct answer: %s" if legacy else "Final answer: %s"
    return "# Expected Output\n\n## Question 1\n\n" + head % final + "\n"


class ScorerFixes138(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_137_F001_fraction_key(self):
        m = scorer.match
        self.assertFalse(m("14", "14/3"))
        self.assertTrue(m("28/6", "14/3"))
        self.assertTrue(m("14 / 3", "14/3"))
        self.assertFalse(m("14/5", "14/3"))
        self.assertFalse(m("4.67", "14/3"))  # no decimal-for-fraction acceptance

    def test_137_F002_second_value_in_reply(self):
        m = scorer.match
        self.assertFalse(m("8 hoặc 9", "8"))
        self.assertFalse(m("8; 9", "8"))
        self.assertTrue(m("62 host", "62"))
        self.assertTrue(m("1.8e-19 J", "1.8e-19 J"))
        self.assertTrue(m("3 m/s2", "3 m/s2"))
        self.assertTrue(m("4 m^2", "4 m^2"))

    def test_137_F003_thousands_separators(self):
        self.assertTrue(scorer.match("19975000", "19.975.000 đồng"))
        self.assertFalse(scorer.match("19.975", "19.975.000 đồng"))

    def test_137_F004_unicode_minus_tail(self):
        self.assertTrue(scorer.match("x = −3", "-3"))
        self.assertTrue(scorer.match("x = -3", "-3"))

    def test_137_F008_key_letters_ordering(self):
        d = self.tmp.name
        self.assertIsNone(scorer.key_letters(_file(d, "o.md", _key("b-d-a-e-c"))))
        for v in ("B", "B. 2", "B)"):
            self.assertEqual(scorer.key_letters(_file(d, "k.md", _key(v))), {"1": "B"})

    def test_137_F010_score_file_legacy_key(self):
        d = self.tmp.name
        key = _file(d, "legacy.md", _key("B", legacy=True))
        ans = _file(d, "a.md", _key("B"))
        self.assertEqual(scorer.score_file(ans, key), [(1, "correct")])
        nokey = _file(d, "nokey.md", "# Expected Output\n\n## Question 1\n\nno final here\n")
        self.assertEqual(scorer.score_file(ans, nokey), [(1, "manual")])

    def _apply(self, answer, final):
        r = new_rec()
        r.update(ans={"answer": answer, "answer_status": "answered"}, status="UNCERTAIN",
                 reason="open_task_no_rubric")
        key = _file(self.tmp.name, "k.md", _key(final))
        scorer.apply_key({1: r}, key)
        return r

    def test_136_F004_gapfill_open_scores(self):
        r = self._apply("open", "open")
        self.assertEqual(r["score"]["points"], 1)

    def test_137_F009_open_vs_letter_key(self):
        r = self._apply("Open", "B")
        self.assertEqual(r["score"]["points"], 0)
        self.assertEqual((r["status"], r["reason"]), ("FAIL", "differs_from_key"))
        self.assertIsNone(self._apply("Open", "Open (rubric)")["score"]["points"])


if __name__ == "__main__":
    unittest.main()

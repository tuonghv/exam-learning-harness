"""TASK-053 / REQ-0056: solve QA merged into the review pack (synthetic data only)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_review import Base, q, tick  # noqa: E402
from exam_engine.pipeline import review  # noqa: E402

QA1 = "\n".join([
    "n | answer | conf | flawed | reasoning",
    "|---|---|---|---|---|",
    "1 | A | high | no | same as engine",
    "2 | C | low | no | differs | extra col",
    "3 | B | mid | yes | broken stem",
    "4 | D | high | no | engine declined",
    "5 | - | low | no | cannot tell",
    "bad row here | x",
    "7 | Z | high | no | bad letter",
    "99 | A | high | no | outside",
    "prose without pipes",
])


class QaTests(Base):
    def qa(self, text, name="qa.md"):
        return self.w(name, text)

    def qs(self):
        return [q(1, "A"), q(2, "A"), q(3, "A"), q(4, None), q(5, "B")]

    def pack_qa(self, files, **kw):
        r = self.result(self.qs(), "s.json")
        e = self.w("s.md", "\n".join(["# E", ""] + ["## Question %d\n\nStem %d?\n" % (i, i) for i in range(1, 6)]))
        return review.pack("X1", "s", r, e, None, 0, self.out, False, "", files)

    def test_verdicts_and_index(self):
        _, msg = self.pack_qa([self.qa(QA1)])
        t = self.read("s.md")
        self.assertIn("QA: A conf high | agrees | same as engine", t)
        self.assertIn("QA: C conf low | differs |", t)
        self.assertIn("QA: B conf mid | flawed |", t)
        self.assertIn("QA: D conf high | qa-only |", t)
        self.assertIn("QA: - conf low | unresolved |", t)
        self.assertIn("not an official key", t)
        ix = self.read("INDEX.md")
        self.assertIn("| qa | verdict |", ix)
        self.assertIn("- s: agrees 1, differs 1, flawed 1, qa-only 1, unresolved 1", ix)
        self.assertIn("qa_unparsed 2", msg)
        self.assertIn("qa_unmatched 1 (99)", msg)

    def test_later_file_overrides(self):
        self.pack_qa([self.qa(QA1), self.qa("2 | A | high | no | adjudicated\n", "b.md")])
        self.assertIn("QA: A conf high | agrees | adjudicated", self.read("s.md"))

    def test_without_qa_identical_and_marks_kept(self):
        self.pack_qa([])
        base = self.read("s.md")
        self.assertIn("\nQA: -\n", base)
        self.assertNotIn("| qa |", self.read("INDEX.md"))
        self.fill("s", 2, tick(ext="ok", note="n2"))
        self.pack_qa([self.qa(QA1)])
        t = self.read("s.md")
        self.assertIn(tick(ext="ok", note="n2"), t)
        self.assertIn("QA: C conf low | differs |", t)
        rc, out, _ = self.run_cli("review-apply", "--exam-id", "X1", "--out", self.out)
        self.assertIn("QA verdicts: agrees 1, differs 1", out)


if __name__ == "__main__":
    unittest.main()

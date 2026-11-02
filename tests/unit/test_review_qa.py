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
        self.assertIn("QA: B conf mid | flawed (engine A vs QA B) |", t)
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

    def test_flawed_words_and_dash_and_header(self):
        t = "\n".join(["| # | answer | conf | flawed? | why |", "|:--|:-:|---|---|---|",
                       "| 1 | a | high | mild (close) | one |", "| 2 | B | high | NO | two |",
                       "| 3 | - | low | yes | three |", "| 4 | D | high | yes | four |"])
        _, msg = self.pack_qa([self.qa(t)])
        s = self.read("s.md")
        self.assertIn("QA: A conf high | flawed | one", s)
        self.assertIn("QA: B conf high | differs | two", s)
        self.assertIn("QA: - conf low | flawed | three", s)
        self.assertIn("QA: D conf high | flawed | four", s)
        self.assertIn("qa_unparsed 0", msg)

    def test_crlf_unicode_and_pipe_in_reasoning(self):
        p = os.path.join(self.t, "c.md")
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write("1 | A | high | no | m\u1ed9t | hai \u00e9\r\n2 | C | mid high | no | x\r\n")
        self.pack_qa([p])
        s = self.read("s.md")
        self.assertIn("QA: A conf high | agrees | m\u1ed9t | hai \u00e9\n", s)
        self.assertIn("QA: C conf mid_high | differs | x\n", s)
        self.assertNotIn("\r", s)
        self.assertIn("agrees 1", self.read("INDEX.md"))

    def test_no_qa_index_header_unchanged(self):
        self.pack_qa([])
        ix = self.read("INDEX.md")
        self.assertIn("| subject | n | page | status | answer | conf | flags | extraction | solution |\n"
                      "|---|---|---|---|---|---|---|---|---|\n", ix)
        self.assertNotIn("QA verdicts", ix)
        self.assertNotIn("independent reads", self.read("s.md"))

    def test_note_starting_with_a_flag_word_four_columns(self):
        # D3: handoff tables have 4 columns (n | answer | conf | note): a note starting with "no"/"yes" is not a flag
        self.pack_qa([self.qa("1 | A | high | no option fits well\n2 | C | low | yes the stem is clear\n")])
        s = self.read("s.md")
        self.assertIn("QA: A conf high | agrees | no option fits well", s)
        self.assertIn("QA: C conf low | differs | yes the stem is clear", s)

    def test_engine_without_a_letter_is_not_differs(self):
        # D2: engine answer "230%" prints as "?"; comparing it with QA's letter must not say "differs"
        r = self.result([q(1, "230%")], "f.json")
        e = self.w("f.md", "# E\n\n## Question 1\n\nStem?\n")
        review.pack("X1", "f", r, e, None, 0, self.out, False, "", [self.qa("1 | C | high | no | x\n")])
        self.assertNotIn("| differs |", self.read("f.md"))
        self.assertIn("| engine-nonletter |", self.read("f.md"))
        self.assertIn("engine-nonletter 1", self.read("INDEX.md"))

    def _val(self, ans, opts, qa="C"):
        r = self.result([q(1, ans)], "v.json")
        e = self.w("v.md", "# E\n\n## Question 1\n\nStem?\n\n" + "\n".join(opts) + "\n")
        review.pack("X1", "v", r, e, None, 0, self.out, False, "", [self.qa("1 | %s | high | no | x\n" % qa)])
        return self.read("v.md")

    def test_value_answer_maps_to_single_option(self):
        o = ["A. 100 %", "B. 200%", "C. 230 %", "D. 4,5"]
        self.assertIn("| agrees |", self._val("230%", o))
        self.assertIn("| differs |", self._val("230%", o, "B"))
        self.assertIn("| agrees |", self._val("4.5", o, "D"))

    def test_value_answer_no_or_two_options(self):
        self.assertIn("| engine-nonletter |", self._val("999", ["A. 1", "B. 2", "C. 3", "D. 4"]))
        self.assertIn("| engine-nonletter |", self._val("2", ["A. 2", "B. 2 ", "C. 3", "D. 4"]))

    def test_rerun_without_qa_keeps_qa_lines(self):
        # D1: a re-run without --qa resets QA lines to "-" (marks are kept, QA data is lost)
        self.pack_qa([self.qa(QA1)])
        self.pack_qa([])
        self.assertIn("QA: C conf low | differs |", self.read("s.md"))

    def test_flawed_survives_rerun(self):
        self.pack_qa([self.qa(QA1)])
        self.pack_qa([])
        self.pack_qa([])
        self.assertIn("QA: B conf mid | flawed (engine A vs QA B) | broken stem", self.read("s.md"))

    def test_flawed_differs_shows_pair(self):
        self.pack_qa([self.qa("1 | C | high | yes | bad\n2 | A | high | yes | same\n")])
        s = self.read("s.md")
        self.assertIn("QA: C conf high | flawed (engine A vs QA C) | bad", s)
        self.assertIn("QA: A conf high | flawed | same", s)
        ix = self.read("INDEX.md")
        self.assertIn("flawed (engine A vs QA C) |", ix)
        self.assertIn("flawed 2,", ix)
        self.assertIn("flawed_differs 1", ix)
        self.pack_qa([])
        self.assertIn("QA: C conf high | flawed (engine A vs QA C) | bad", self.read("s.md"))

    def test_rerun_with_partial_qa_replaces_only_covered(self):
        self.pack_qa([self.qa(QA1)])
        self.pack_qa([self.qa("2 | A | high | no | new\n", "n.md")])
        s = self.read("s.md")
        self.assertIn("QA: A conf high | agrees | new", s)
        self.assertIn("QA: A conf high | agrees | same as engine", s)  # uncovered numbers keep their QA line (D1)
        self.assertNotIn("\nQA: -\n", s.split("## Q4")[0])


    def test_third_run_changed_answer_keeps_mark_flag_and_qa(self):
        self.pack_qa([self.qa(QA1)])
        self.fill("s", 1, tick(ext="ok", note="n1"))
        self.pack_qa([])
        qs = self.qs()
        qs[0] = q(1, "B")
        r = self.result(qs, "s2.json")
        e = self.w("s.md", "\n".join(["# E", ""] + ["## Question %d\n\nStem %d?\n" % (i, i) for i in range(1, 6)]))
        _, msg = review.pack("X1", "s", r, e, None, 0, self.out, False, "", [])
        t = self.read("s.md")
        self.assertIn(tick(ext="ok", note="n1"), t)
        self.assertIn("Answer changed: was A now B", t)
        self.assertIn("1 marked answers changed", msg)
        self.assertIn("QA: A conf high |", t)

    def test_changed_answer_kept_qa_verdict_follows_engine(self):
        # D4: kept QA line must not claim "agrees" when the engine answer is now B and QA says A
        self.pack_qa([self.qa(QA1)])
        qs = self.qs()
        qs[0] = q(1, "B")
        r = self.result(qs, "s2.json")
        e = self.w("s.md", "\n".join(["# E", ""] + ["## Question %d\n\nStem %d?\n" % (i, i) for i in range(1, 6)]))
        review.pack("X1", "s", r, e, None, 0, self.out, False, "", [])
        self.assertNotIn("QA: A conf high | agrees |", self.read("s.md"))

    def test_four_column_row_with_yes_no_word_not_flawed(self):
        self.pack_qa([self.qa("1 | A | high | yes it matches\n2 | C | low | no | five col reason\n")])
        s = self.read("s.md")
        self.assertIn("QA: A conf high | agrees | yes it matches", s)
        self.assertIn("QA: C conf low | differs | five col reason", s)


    def test_d4_roundtrip_differs_flawed_and_marks(self):
        self.pack_qa([self.qa(QA1)])
        self.fill("s", 1, tick(ext="ok", note="m1"))
        self.fill("s", 3, tick(ext="defect", note="m3"))
        qs = self.qs()
        qs[0] = q(1, "B")  # QA A vs engine B -> differs
        qs[2] = q(3, "D")  # flawed row stays flawed
        r = self.result(qs, "s2.json")
        e = self.w("s.md", "\n".join(["# E", ""] + ["## Question %d\n\nStem %d?\n" % (i, i) for i in range(1, 6)]))
        review.pack("X1", "s", r, e, None, 0, self.out, False, "", [])
        t = self.read("s.md")
        self.assertIn("QA: A conf high | differs | same as engine", t)
        self.assertIn("QA: B conf mid | flawed (engine D vs QA B) | broken stem", t)
        self.assertIn(tick(ext="ok", note="m1"), t)
        self.assertIn(tick(ext="defect", note="m3"), t)
        self.assertIn("| s | 1 |", self.read("INDEX.md"))


if __name__ == "__main__":
    unittest.main()

"""65.1/65.2/65.6 (+65.8 flags): section-scoped ranges, question-own override, labelled option scan.
Synthetic refined documents through the real api._from_refined + parser.parse_exam (no model call)."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.core import refcheck  # noqa: E402
from exam_engine.ingest import api  # noqa: E402
from exam_engine.pipeline import parser  # noqa: E402

META = {"Subject": "English", "Level": "Grade 12", "Exam type": "Synthetic", "Task": "Multiple Choice",
        "Mode": "Solve"}
OPTS = {"A": "alpha", "B": "beta", "C": "gamma", "D": "delta"}
PAS = "Line one of a synthetic passage. Line two follows. Line three ends it."


def q(i, text="Pick one.", ctx="", opts=OPTS, **kw):
    return dict({"id": str(i), "text": text, "options": dict(opts) if opts else {}, "context": ctx,
                 "page": 1}, **kw)


def emit(qs):
    doc = {"refined": {"questions": qs}, "meta": META, "source": {"name": "t"}}
    text = api._from_refined(doc)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "exam.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return text, parser.parse_exam(path), doc


class TestSectionScopedRange(unittest.TestCase):  # P1
    def setUp(self):
        self.qs = [q(1, ctx="PART I\nQuestions 1-3: Choose the synonym."), q(2), q(3),
                   q(1, ctx="PART II\nAnswer each question."), q(2), q(3)]

    def test_no_carry_over(self):
        text, ex, _ = emit(self.qs)
        part2 = ex["questions"][4:]
        for x in part2:
            self.assertEqual(x["instruction"], "")
            self.assertNotIn("synonym", x["text"])
        self.assertEqual(text.count("Choose the synonym"), 3)

    def test_flag_range_cut_by_section(self):
        sh = api._share_context(self.qs)
        self.assertIn("range_cut_by_section", sh[4]["structure"])
        self.assertNotIn("structure", sh[0])

    def test_assembly_row_key_only_when_flagged(self):
        _, _, doc = emit(self.qs)
        rows = api.assembly(doc, {"use_refined": True})
        self.assertEqual(rows[4]["structure"], ["range_cut_by_section"])
        self.assertTrue(all("structure" not in r for r in rows[:3]))

    def test_range_overrun(self):
        sh = api._share_context([q(1, ctx="Questions 1-5: Choose."), q(2), q(3)])
        self.assertEqual(sh[0]["structure"], ["range_overrun"])

    def test_plain_range_unflagged_and_shared(self):
        sh = api._share_context([q(1, ctx="Questions 1-3: Choose."), q(2), q(3)])
        self.assertTrue(all("structure" not in x for x in sh))
        self.assertEqual({x["context"] for x in sh}, {"Questions 1-3: Choose."})


class TestOwnOverride(unittest.TestCase):  # P2
    def test_own_line_kept_in_text(self):
        qs = [q(1, ctx="Questions 1-4: Choose the synonym."), q(2),
              q(3, ctx="Choose the antonym instead."), q(4)]
        text, ex, _ = emit(qs)
        x3 = ex["questions"][2]
        self.assertIn("antonym", x3["stem"])
        self.assertTrue(x3["stem"].startswith("Choose the antonym instead."))
        self.assertTrue(x3["instruction"].startswith("Questions 1-4"))
        self.assertEqual(text.count("antonym"), 1)
        sh = api._share_context(qs)
        self.assertEqual(sh[2]["structure"], ["instruction_override"])
        self.assertNotIn("structure", sh[1])

    def test_same_context_repeated_is_no_override(self):
        c = "Questions 1-2: Choose."
        sh = api._share_context([q(1, ctx=c), q(2, ctx=c)])
        self.assertTrue(all("structure" not in x for x in sh))


class TestLabelledOptionScan(unittest.TestCase):  # P10b (labelled form), P11
    def test_passage_letter_line_kept(self):
        qs = [q(1, ctx="Questions 1-2: Read the passage.\nA. Smith wrote this. " + PAS), q(2)]
        _, ex, _ = emit(qs)
        for x in ex["questions"]:
            self.assertIn("A. Smith wrote this.", x["passage"])
            self.assertEqual(sorted(x["options"]), list("ABCD"))
            self.assertEqual(x["options"]["A"], "alpha")
        self.assertEqual(parser.validate_exam(ex), [])
        gs = parser.groups(ex)
        self.assertEqual(refcheck.missing_group_parts(ex, gs, parser.deps(ex)), {})

    def test_instruction_letter_line_no_option_error(self):
        qs = [q(1, ctx="Questions 1-2: Write the word.\nB. Vocabulary notes", opts=None), q(2, opts=None)]
        _, ex, _ = emit(qs)
        self.assertEqual(ex["questions"][0]["options"], {})
        self.assertFalse([e for e in parser.validate_exam(ex) if "A-D" in e and "question 1" in e
                          and "A" in ex["questions"][0]["options"]])

    def test_unlabelled_scan_unchanged(self):
        body = "## Question 1\n\nPick one.\n\nA. a1\nB. b1\nC. c1\nD. d1\n"
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "e.md")
            with open(p, "w", encoding="utf-8") as f:
                f.write("# Exam Input\n\nSubject: S\n\n" + body)
            ex = parser.parse_exam(p)
        self.assertEqual(ex["questions"][0]["options"], {"A": "a1", "B": "b1", "C": "c1", "D": "d1"})
        self.assertEqual(ex["questions"][0]["stem"], "Pick one.")


class TestEnumeratedHeadings(unittest.TestCase):  # 65.5: P10, real P10b, stack, 65.3
    def test_p10b_real_heading_not_an_option(self):
        text, ex, _ = emit([q(1, ctx="A. GRAMMAR\nQuestions 1-2: Write the word."), q(2)])
        self.assertEqual(parser.validate_exam(ex), [])
        self.assertEqual(ex["questions"][0]["options"]["A"], "alpha")
        self.assertEqual(ex["sections"], ["A. GRAMMAR"])
        self.assertEqual(text.count("GRAMMAR"), 1)

    def test_p10_section_path(self):
        text, ex, _ = emit([q(1, ctx="I. READING\nB. VOCABULARY\nQuestions 1-2: Choose the synonym."), q(2)])
        self.assertEqual(ex["sections"], ["I. READING > B. VOCABULARY"])
        self.assertNotIn("READING", ex["questions"][0]["stem"])
        self.assertEqual(text.count("READING"), 1)

    def test_stack(self):
        sh = api._share_context([q(1, ctx="I. READING\nA. ONE\nQuestions 1-1: x."),
                                 q(2, ctx="B. TWO"), q(3, ctx="II. LISTENING"), q(4)])
        self.assertEqual([x["section"] for x in sh], ["I. READING > A. ONE", "I. READING > B. TWO",
                                                      "II. LISTENING", "II. LISTENING"])

    def test_part_then_subsection_keeps_parent(self):  # the design-named Section-line change (G9)
        sh = api._share_context([q(1, ctx="PHẦN 1: NGÔN NGỮ\n1.1. TOÁN HỌC"), q(2, ctx="1.2. TIẾNG ANH")])
        self.assertEqual(sh[1]["section"], "PHẦN 1: NGÔN NGỮ > 1.2. TIẾNG ANH")

    def test_option_like_passage_line_not_peeled(self):
        sh = api._share_context([q(1, ctx="Questions 1-2: Read.\nA. Smith wrote this.")])
        self.assertNotIn("section", sh[0])

    def test_lowercase_range_word(self):  # 65.3
        sh = api._share_context([q(5, ctx="Read the text below.\n" + PAS + "\nanswer questions 5-7."),
                                 q(6), q(7)])
        self.assertEqual({x["context"] for x in sh}, {sh[0]["context"]})


if __name__ == "__main__":
    unittest.main()

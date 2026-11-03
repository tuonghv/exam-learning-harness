"""65.x QA suite (TASK-065): nested headings, override inside a passage group, false-positive hunt for the
heading peel and the labelled option scan. Synthetic refined documents, no model call."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_structure_scope import PAS, emit, q  # noqa: E402
from exam_engine.core import refcheck  # noqa: E402
from exam_engine.ingest import api, segment  # noqa: E402
from exam_engine.pipeline import parser  # noqa: E402


class TestNestedHeadings(unittest.TestCase):
    def setUp(self):
        self.qs = [q(1, ctx="I. READING\nA. VOCABULARY\nQuestions 1-2: Choose the synonym."), q(2),
                   q(3, ctx="B. GRAMMAR\nQuestions 3-4: Pick the correct form."), q(4),
                   q(5, ctx="II. WRITING\nA. SENTENCES\nQuestions 5-6: Rewrite."), q(6)]

    def test_65_5_nested_paths_and_groups(self):
        _, ex, _ = emit(self.qs)
        self.assertEqual([x["section"] for x in ex["questions"]],
                         ["I. READING > A. VOCABULARY"] * 2 + ["I. READING > B. GRAMMAR"] * 2
                         + ["II. WRITING > A. SENTENCES"] * 2)
        self.assertEqual([g["ids"] for g in parser.groups(ex)], [[1, 2], [3, 4], [5, 6]])
        for x in ex["questions"]:  # no heading text leaks into the stem
            self.assertEqual(x["stem"], "Pick one.")

    def test_65_1_nested_sections_do_not_share_instruction(self):
        _, ex, _ = emit(self.qs)
        self.assertIn("synonym", ex["questions"][1]["instruction"])
        self.assertNotIn("synonym", ex["questions"][2]["instruction"])
        self.assertNotIn("correct form", ex["questions"][4]["instruction"])


class TestOverrideInPassageGroup(unittest.TestCase):
    def test_65_2_override_keeps_passage_and_group(self):
        _, ex, _ = emit([q(1, ctx="Questions 1-3: Read the passage.\n" + PAS),
                         q(2, ctx="Answer using line two only."), q(3)])
        x = ex["questions"][1]
        self.assertEqual(x["passage"], ex["questions"][0]["passage"])
        self.assertTrue(x["stem"].startswith("Answer using line two only."))
        self.assertEqual([g["ids"] for g in parser.groups(ex) if g["kind"] == "passage"], [[1, 2, 3]])

    def test_65_2_new_range_inside_range_is_not_an_override(self):
        sh = api._share_context([q(1, ctx="Questions 1-4: Choose synonym."), q(2),
                                 q(3, ctx="Questions 3-4: Choose antonym."), q(4)])
        self.assertTrue(all("instruction_override" not in (s.get("structure") or []) for s in sh))
        self.assertIn("antonym", sh[3]["context"])


class TestSectionsAcrossRestart(unittest.TestCase):
    def test_65_1_two_passages_one_per_part(self):
        _, ex, _ = emit([q(1, ctx="PART I\nQuestions 1-2: Read.\n" + PAS), q(2),
                         q(1, ctx="PART II\nQuestions 1-2: Read.\nOther passage text here, quite different."), q(2)])
        ps = [x["passage"] for x in ex["questions"]]
        self.assertEqual(ps[0], ps[1])
        self.assertEqual(ps[2], ps[3])
        self.assertNotEqual(ps[1], ps[2])

    def test_65_5_mixed_subject_parts(self):
        _, ex, _ = emit([q(1, ctx="PHẦN 1. TOÁN HỌC\nQuestions 1-2: Solve."), q(2),
                         q(3, ctx="PHẦN 2. TIẾNG ANH\nQuestions 3-4: Choose."), q(4)])
        self.assertEqual([x["section"] for x in ex["questions"]], ["PHẦN 1. TOÁN HỌC"] * 2 + ["PHẦN 2. TIẾNG ANH"] * 2)


class TestFalsePositives(unittest.TestCase):
    """The peel must never eat a genuine answer choice; the labelled scan must still find them."""

    def test_65_5_heading_then_real_options(self):
        _, ex, _ = emit([q(1, ctx="A. GRAMMAR\nQuestions 1-2: Choose."), q(2)])
        self.assertEqual(ex["questions"][0]["section"], "A. GRAMMAR")
        self.assertEqual(sorted(ex["questions"][0]["options"]), list("ABCD"))
        self.assertEqual(parser.validate_exam(ex), [])

    def test_65_6_options_still_read_after_question_text(self):
        _, ex, _ = emit([q(1, ctx="Questions 1-2: Read.\nA. Smith wrote this. " + PAS), q(2)])
        self.assertEqual(ex["questions"][0]["options"], {k: v for k, v in q(1)["options"].items()})
        self.assertIn("A. Smith wrote this.", ex["questions"][0]["passage"])

    def test_65_5_lowercase_option_lines_not_headings(self):
        for c in ("A. Paris\nB. Rome\nQuestions 1-2: x", "I. Paris is nice. Read below"):
            self.assertEqual(segment.split_heading(c)[0], [])

    def test_65_5_cross_page_context_keeps_range(self):
        qs = [q(7, ctx="Questions 7-9: Read.\n" + PAS), q(8), q(9, text="Stem begins", opts=None),
              dict(q(9, text="and ends."), page=2, continued_pages=[2])]
        _, ex, _ = emit(qs)
        self.assertEqual([g["ids"] for g in parser.groups(ex)], [[1, 2, 3]])

    @unittest.expectedFailure  # DEFECT D1 (QA): upper-case shared answer bank at the start of a context is peeled as headings
    def test_65_5_shared_option_bank_not_swallowed(self):
        text, ex, _ = emit([q(1, ctx="A. HISTORY\nB. GEOGRAPHY\nC. CIVICS\nD. ECONOMICS\n"
                                     "Questions 1-2: Match each text with a subject above.", opts=None),
                            q(2, opts=None)])
        for w in ("HISTORY", "GEOGRAPHY", "CIVICS", "ECONOMICS"):
            self.assertIn(w, text.split("## Question 1")[1])

    @unittest.expectedFailure  # DEFECT D2 (QA): numeric bank "A. 25" is peeled (label letter counts as upper case)
    def test_65_5_numeric_bank_not_heading(self):
        self.assertEqual(segment.split_heading("A. 25\nB. 36\nC. 49\nD. 64\nQuestions 1-2: pick.")[0], [])

    @unittest.expectedFailure  # DEFECT D3 (QA): a bank after the range line is read as passage, options lost
    def test_65_6_bank_after_range_line_still_options(self):
        _, ex, _ = emit([q(1, ctx="Questions 1-2: Match.\nA. HISTORY\nB. GEOGRAPHY\nC. CIVICS\nD. ECONOMICS", opts=None),
                         q(2, opts=None)])
        self.assertEqual(parser.validate_exam(ex), [])


if __name__ == "__main__":
    unittest.main()

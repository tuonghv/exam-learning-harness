"""TASK-070 (70.1/70.2): route B structure hint read from the exam's own headings; generic dev prompts."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import cross, parser  # noqa: E402

FALLBACK = "Printed numbering may restart per part or section"


def exam():
    path = os.path.join(ROOT, "examples", "math", "input-001.md")
    return parser.parse_exam(path)


class StructureHint(unittest.TestCase):
    def test_section_headings(self):
        t = "SECTION 1\n1. a\n2. b\nSECTION 2\n1. c\n2. d\n3. e\n"
        self.assertIn("(Section 1 1-2, Section 2 1-3)", cross.structure_hint(t))

    def test_part_roman_headings(self):
        t = "PART I\nCâu 1. a\nCâu 12. b\nPART II\nCâu 1. c\nCâu 4. d\nPART III\n1. e\n6. f\n"
        self.assertIn("(Part I 1-12, Part II 1-4, Part III 1-6)", cross.structure_hint(t))

    def test_trial_exam_spans_equal_old_literal(self):
        t = ("PHẦN I: Thí sinh trả lời từ câu 1 đến câu 12.\nCâu 1. x\nCâu 12. y\n"
             "PHẦN II: ...\nCâu 1. x\nCâu 4. y\n")
        h = cross.structure_hint(t)
        self.assertIn("Phần I 1-12", h)
        self.assertIn("Phần II 1-4", h)

    def test_no_heading_falls_back(self):
        for t in ("Câu 1. a\nCâu 2. b\n", "", None, "PART I\n1. a\n"):
            self.assertEqual(cross.structure_hint(t), FALLBACK)

    def test_non_vietnamese_header(self):
        t = "Subject: Deutsch\nLanguage: de\n\nTEIL 1\nFrage 1. a\n1. b\nTEIL 2\n1. c\n"
        self.assertIn("Teil 1 1-1", cross.structure_hint(t))

    def test_prompt_uses_hint(self):
        p = cross.route_b_prompt(exam(), "SECTION 1\n1. a\nSECTION 2\n1. b\n")
        self.assertIn("Section 2 1-1", p)
        self.assertIn("Answer every question in every part.", p)
        self.assertNotIn("Part II and III", p)
        g = cross.route_b_prompt(exam())
        self.assertIn(FALLBACK + "; do NOT use", g)
        self.assertEqual(g, cross.route_b_prompt(exam(), "no headings"))


class StructureHintQA(unittest.TestCase):
    """70.1 QA: the hint states only spans read from the text; otherwise the fallback."""

    def test_mixed_headings_use_own_words(self):
        t = "PART I\n1. a\n2. b\nSECTION 2\n1. c\n2. d\n"
        self.assertIn("(Part I 1-2, Section 2 1-2)", cross.structure_hint(t))

    def test_heading_numbers_not_trusted(self):
        # heading text claims questions 1-40 / 41-50; only the markers actually read are named
        t = "PART I: answer questions 1 to 40\n1. a\n2. b\nPART II: questions 41-50\n1. c\n"
        h = cross.structure_hint(t)
        self.assertIn("Part I 1-2, Part II 1-1", h)
        for bad in ("40", "41", "50"):
            self.assertNotIn(bad, h)

    def test_prose_and_lowercase_are_not_headings(self):
        for t in ("Section 3 of the law applies.\n1. a\nPart 2 is hard\n1. b\n",
                  "IN SECTION 5 BELOW\n1. a\nPART 2\n1. b\n"):
            self.assertEqual(cross.structure_hint(t), FALLBACK)

    def test_empty_part_is_skipped_not_invented(self):
        t = "PART I\n1. a\n2. b\nPART II\nPART III\n1. x\n"
        h = cross.structure_hint(t)
        self.assertNotIn("Part II ", h.replace("Part III", ""))
        self.assertIn("Part III 1-1", h)

    def test_only_one_part_with_questions_falls_back(self):
        self.assertEqual(cross.structure_hint("PART I\n1. a\nPART II\n"), FALLBACK)

    def test_huge_input_is_fast_and_bounded(self):
        import time
        t0 = time.time()
        h = cross.structure_hint("x\n" * 500000 + "".join("PART %d\n1. a\n" % i for i in range(1, 300)))
        self.assertLess(time.time() - t0, 5)
        self.assertTrue(h.startswith("The printed numbering restarts"))
        self.assertEqual(cross.structure_hint("y" * 200000), FALLBACK)

    def test_headerless_exam_route_b_prompt_does_not_crash(self):
        for t in (None, "", "no headings at all\n1. a\n", "\x00\ufffd\n"):
            p = cross.route_b_prompt(exam(), t)
            self.assertIn("exactly", p)
            self.assertIn("count continuously", p)

    def test_hint_never_names_a_count(self):
        h = cross.structure_hint("PART I\n1. a\n2. b\nPART II\n1. c\n")
        self.assertNotIn("exactly", h)
        self.assertNotIn("total", h)


class DevPromptsGeneric(unittest.TestCase):
    FILES = ["system.md", "lang/vi/system.md", "verification/verify_answer.md",
             "exam/solve.md", "lang/vi/exam/solve.md"]

    def test_no_fixed_subject_list(self):
        for f in self.FILES:
            with open(os.path.join(ROOT, "prompts", "dev", f), encoding="utf-8") as fh:
                s = fh.read()
            for w in ("Grade 12", "Literature", "Ngữ văn", "lớp 12 ", "Vật lí"):
                self.assertNotIn(w, s, "%s: %s" % (f, w))


if __name__ == "__main__":
    unittest.main()

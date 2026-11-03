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

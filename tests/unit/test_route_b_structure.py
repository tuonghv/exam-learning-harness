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
    e = parser.parse_exam(path)
    e["questions"] = e["questions"] * 4  # only the count matters to the prompt
    return e


def qs(k):
    return "".join("%d. q\n" % i for i in range(1, k + 1))


def doc(*parts):
    """(heading, k) pairs -> text with blank-line-separated headings and k numbered questions."""
    return "".join("\n%s\n%s" % (h, qs(k)) for h, k in parts)


class StructureHint(unittest.TestCase):
    def test_section_headings(self):
        t = doc(("SECTION 1", 2), ("SECTION 2", 3))
        self.assertIn("(Section 1 1-2, Section 2 1-3)", cross.structure_hint(t, 5))

    def test_part_roman_headings(self):
        t = doc(("PART I", 12), ("PART II", 4), ("PART III", 6))
        self.assertIn("(Part I 1-12, Part II 1-4, Part III 1-6)", cross.structure_hint(t, 22))

    def test_trial_exam_spans_equal_old_literal(self):
        t = doc(("PHẦN I: Thí sinh trả lời từ câu 1 đến câu 12.", 12), ("PHẦN II: ...", 4))
        h = cross.structure_hint(t, 16)
        self.assertIn("Phần I 1-12", h)
        self.assertIn("Phần II 1-4", h)

    def test_no_heading_falls_back(self):
        for t in ("Câu 1. a\nCâu 2. b\n", "", None, doc(("PART I", 1))):
            self.assertEqual(cross.structure_hint(t), FALLBACK)

    def test_non_vietnamese_header(self):
        t = "Subject: Deutsch\nLanguage: de\n" + doc(("TEIL 1", 1), ("TEIL 2", 1))
        self.assertIn("Teil 1 1-1", cross.structure_hint(t, 2))

    def test_prompt_uses_hint_only_when_count_matches(self):
        e = exam()
        n = len(e["questions"])
        t = doc(("SECTION 1", 1), ("SECTION 2", n - 1))
        p = cross.route_b_prompt(e, t)
        self.assertIn("Section 2 1-%d" % (n - 1), p)
        self.assertIn("Answer every question in every part.", p)
        self.assertNotIn("Part II and III", p)
        g = cross.route_b_prompt(e)
        self.assertIn(FALLBACK + "; do NOT use", g)
        self.assertEqual(g, cross.route_b_prompt(e, "no headings"))
        self.assertEqual(g, cross.route_b_prompt(e, doc(("SECTION 1", 1), ("SECTION 2", n + 5))))

    def test_heading_like_line_inside_passage(self):
        # `PART II` mid-paragraph (no blank line before) must not split a part
        t = doc(("PART I", 1)) + "The text says:\nPART II\n" + qs(0) + "2. next\n" + doc(("PART II", 2))
        self.assertEqual(cross.structure_hint(t, 4), FALLBACK)

    def test_count_mismatch_falls_back(self):
        t = doc(("PART I", 2), ("PART II", 2))
        self.assertIn("Part II 1-2", cross.structure_hint(t, 4))
        self.assertEqual(cross.structure_hint(t, 5), FALLBACK)

    def test_duplicated_or_out_of_order_parts_fall_back(self):
        self.assertEqual(cross.structure_hint(doc(("PART I", 2), ("PART I", 2)), 4), FALLBACK)
        self.assertEqual(cross.structure_hint(doc(("PART II", 2), ("PART I", 2)), 4), FALLBACK)
        self.assertEqual(cross.structure_hint(doc(("PART I", 2), ("PART III", 2)), 4), FALLBACK)

    def test_gaps_or_continued_numbering_fall_back(self):
        gap = "\nPART I\n1. a\n5. b\n" + doc(("PART II", 1))
        self.assertEqual(cross.structure_hint(gap, 3), FALLBACK)
        cont = "\nPART I\n1. a\n2. b\n\nPART II\n3. c\n4. d\n"
        self.assertEqual(cross.structure_hint(cont, 4), FALLBACK)

    def test_empty_part_falls_back(self):
        t = doc(("PART I", 2)) + "\nPART II\n" + doc(("PART III", 1))
        self.assertEqual(cross.structure_hint(t, 3), FALLBACK)

    def test_mixed_heading_words_fall_back(self):
        self.assertEqual(cross.structure_hint(doc(("PART I", 2), ("SECTION 2", 2)), 4), FALLBACK)

    def test_heading_numbers_not_trusted(self):
        t = doc(("PART I: answer questions 1 to 40", 2), ("PART II: questions 41-50", 1))
        h = cross.structure_hint(t, 3)
        self.assertIn("Part I 1-2, Part II 1-1", h)
        for bad in ("40", "41", "50"):
            self.assertNotIn(bad, h)

    def test_prose_and_lowercase_are_not_headings(self):
        for t in ("Section 3 of the law applies.\n1. a\nPart 2 is hard\n1. b\n",
                  "IN SECTION 5 BELOW\n1. a\nPART 2\n1. b\n"):
            self.assertEqual(cross.structure_hint(t), FALLBACK)

    def test_huge_input_is_fast_and_bounded(self):
        import time
        t0 = time.time()
        cross.structure_hint("x\n" * 500000 + "".join("\nPART %d\n1. a\n" % i for i in range(1, 300)))
        self.assertLess(time.time() - t0, 5)
        self.assertEqual(cross.structure_hint("y" * 200000), FALLBACK)

    def test_headerless_exam_route_b_prompt_does_not_crash(self):
        for t in (None, "", "no headings at all\n1. a\n", "\x00\ufffd\n"):
            p = cross.route_b_prompt(exam(), t)
            self.assertIn("exactly", p)
            self.assertIn("count continuously", p)

    def test_hint_never_names_a_count(self):
        h = cross.structure_hint(doc(("PART I", 2), ("PART II", 1)), 3)
        self.assertNotIn("exactly", h)
        self.assertNotIn("total", h)


class DevPromptsGeneric(unittest.TestCase):
    FILES = ["system.md", "lang/vi/system.md", "verification/verify_answer.md",
             "lang/vi/verification/verify_answer.md",
             "exam/solve.md", "lang/vi/exam/solve.md"]

    def test_no_fixed_subject_list(self):
        for f in self.FILES:
            with open(os.path.join(ROOT, "prompts", "dev", f), encoding="utf-8") as fh:
                s = fh.read()
            for w in ("Grade 12", "Literature", "Ngữ văn", "lớp 12", "Vật lí"):
                self.assertNotIn(w, s, "%s: %s" % (f, w))


if __name__ == "__main__":
    unittest.main()

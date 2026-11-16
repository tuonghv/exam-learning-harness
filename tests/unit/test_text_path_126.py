"""TASK-126 (REQ-0133): free text path - MC question without options declined, wrapped group instruction. $0."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import api  # noqa: E402
from exam_engine.ingest import segment  # noqa: E402
from exam_engine.pipeline import parser  # noqa: E402

OPTS = [{"key": k, "text": "x"} for k in "ABCD"]
META = {"Subject": "English", "Level": "Grade 12", "Exam type": "X", "Mode": "Solve"}


def doc(task, qs):
    return {"source": {"name": "x.pdf", "format": "pdf"}, "intro": "", "meta": dict(META, Task=task),
            "pages": [], "questions": qs}


def qs3():
    return [{"n": 1, "text": "a", "options": OPTS},
            {"n": 2, "text": "I ate the bread, but it kept me going. A B C D", "options": []},
            {"n": 3, "text": "c", "options": OPTS}]


def block(text, k):
    return text.split("## Question %d" % k)[1].split("## Question")[0]


class OptionsMissing(unittest.TestCase):
    def test_ac1_mc_without_options_marked_and_parses(self):
        text = api.to_exam_text(doc("Multiple Choice", qs3()))
        self.assertIn("[Incomplete: missing_text options_missing]", block(text, 2))
        self.assertNotIn("options_missing", block(text, 1) + block(text, 3))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "e.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            exam = parser.parse_exam(path)
        self.assertEqual(parser.validate_exam(exam), [])

    def test_ac2_non_mc_unmarked(self):
        text = api.to_exam_text(doc("Short Answer", qs3()))
        self.assertNotIn("options_missing", text)


class WrappedGuide(unittest.TestCase):
    def test_ac3_wrapped_instruction_joined(self):
        g, p = segment.split_guide("Questions 36-40: Each sentence has one error. Find it and blacken your\n"
                                   "choice on your answer sheet.")
        self.assertEqual(g, "Questions 36-40: Each sentence has one error. Find it and blacken your "
                            "choice on your answer sheet.")
        self.assertEqual(p, "")

    def test_ac3_complete_instruction_keeps_passage(self):
        g, p = segment.split_guide("Questions 46-52: Read the passage.\nthe passage starts lower case.")
        self.assertEqual(g, "Questions 46-52: Read the passage.")
        self.assertEqual(p, "the passage starts lower case.")

    def test_ac3_capitalised_next_line_is_passage(self):
        g, p = segment.split_guide("Questions 46-52: Read the passage and answer\nPASSAGE A text")
        self.assertEqual(g, "Questions 46-52: Read the passage and answer")
        self.assertEqual(p, "PASSAGE A text")


if __name__ == "__main__":
    unittest.main()

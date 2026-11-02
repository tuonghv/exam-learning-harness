"""TASK-055 (55.1-55.2): slice after sharing; wider group range forms."""
import os
import re
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import api, segment  # noqa: E402

META = {"Subject": "english", "Level": "Grade 12", "Exam type": "Test", "Task": "Multiple Choice",
        "Mode": "Solve"}
CTX = "Questions 46-52: Read the passage and choose the best answer.\nTea is old and widely drunk."
OPTS = {"A": "one", "B": "two", "C": "three", "D": "four"}


def _doc():
    # page 1 carries guide+passage on q46; page 2 holds q47-52
    qs = [{"id": str(n), "text": "Stem %d?" % n, "options": dict(OPTS), "page": 1 if n == 46 else 2,
           **({"context": CTX} if n == 46 else {})} for n in range(46, 53)]
    return {"source": {"name": "x"}, "meta": dict(META), "refined": {"questions": qs}}


class TestSliceAfterShare(unittest.TestCase):
    def test_slice_keeps_passage(self):
        text = api._from_refined(_doc(), "48-52")
        blocks = re.split(r"(?m)^## Question \d+$", text)[1:]
        self.assertEqual(len(blocks), 5)
        for b in blocks:
            self.assertIn("Tea is old", b)
            self.assertIn("choose the best answer", b)

    def test_full_run_unchanged_shape(self):
        text = api._from_refined(_doc())
        self.assertEqual(len(re.split(r"(?m)^## Question \d+$", text)[1:]), 7)


class TestGroupForms(unittest.TestCase):
    def test_table(self):
        cases = [("Questions 46-52 read", (46, 52)), ("Câu 3 – 5", (3, 5)),
                 ("câu từ 103 đến 105", (103, 105)), ("Questions 1 to 4", (1, 4)),
                 ("từ câu 1 đến câu 5", (1, 5)), ("Câu 3, 4", (3, 4)),
                 ("Câu 3, 4, 6 sử dụng", (3, 6)), ("Questions 7 and 9", (7, 9)),
                 ("Câu hỏi 2 đến 3", (2, 3))]
        for text, want in cases:
            m = segment.GROUP_RE.search(text)
            self.assertIsNotNone(m, text)
            self.assertEqual(segment.group_span(m), want, text)

    def test_no_match(self):
        for text in ("Câu 3", "Question 5.", "no group"):
            self.assertIsNone(segment.GROUP_RE.search(text), text)


if __name__ == "__main__":
    unittest.main()

"""Phase 44 (TASK-044, REQ-0048): page furniture and passage-after-option-D on the text route.

Synthetic placeholder text only; $0, no network."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import api, optional, segment  # noqa: E402
from exam_engine.ingest.adapters import pdf as pdfmod  # noqa: E402
from exam_engine.ingest.schema import IngestError  # noqa: E402

try:
    fitz = optional.load("fitz", "pymupdf")
except IngestError:
    fitz = None
try:
    docx = optional.load("docx", "python-docx")
except IngestError:
    docx = None

META = {"Subject": "S", "Level": "L", "Exam type": "E", "Task": "T", "Mode": "M"}
PASSAGE = "Questions 3-4 Read the passage below about the placeholder topic."
OPTS = ["A. one", "B. two", "C. three", "D. four"]


def strip(pages):
    return pdfmod._strip_furniture(pages)


class TestFurniture(unittest.TestCase):
    def test_page_number_lines_removed(self):
        pages = [["Trang 3/22", "Câu 1. stem", "A. a", "- 3 -"],
                 ["Page 4", "B. b", "Trang 4"]]
        out, n = strip(pages)
        self.assertEqual(out, [["Câu 1. stem", "A. a"], ["B. b"]])
        self.assertEqual(n, 4)

    def test_repeated_header_on_half_of_pages_removed(self):
        pages = [["Placeholder Exam Code 101 p%d" % i, "Câu %d. stem" % i, "A. a"]
                 for i in range(1, 7)]
        out, n = strip(pages)
        self.assertEqual(n, 6)
        self.assertTrue(all(len(p) == 2 for p in out))

    def test_repeated_middle_line_kept_and_two_pages_kept(self):
        pages = [["top %s" % c, "mid-a %s" % c, "Choose the best answer.", "mid-b %s" % c,
                  "end %s" % c] for c in "abcde"]
        out, n = strip(pages)
        self.assertEqual((n, out[0][2]), (0, "Choose the best answer."))
        two = [["Only twice", "Câu 1. s"], ["Only twice", "Câu 2. s"], ["Câu 3. s", "A. a"]]
        out, n = strip(two)
        self.assertEqual((n, out[0][0]), (0, "Only twice"))

    def test_no_removal_returns_same_lines(self):
        pages = [["Câu 1. s", "A. a"], ["Câu 2. s", "A. b"]]
        self.assertEqual(strip(pages), (pages, 0))


@unittest.skipIf(fitz is None, "PyMuPDF (fitz) not installed")
class TestPdfWarning(unittest.TestCase):
    def build(self, footer):
        d = fitz.open()
        for i in range(1, 4):
            pg = d.new_page()
            pg.insert_text((72, 72), "Câu %d. stem number %d" % (i, i), fontsize=12)
            pg.insert_text((72, 100), "A. one", fontsize=12)
            if footer:
                pg.insert_text((72, 800), "Trang %d/3" % i, fontsize=10)
        path = os.path.join(self.dir, "t.pdf")
        d.save(path)
        d.close()
        return path

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def doc(self, footer):
        return api.ingest_document(self.build(footer),
                                   config={"asset_dir": os.path.join(self.dir, "a")})

    def test_warning_with_count_and_clean_text(self):
        doc = self.doc(True)
        w = [x for x in doc["warnings"] if x["code"] == "page_furniture_removed"]
        self.assertEqual(len(w), 1)
        self.assertEqual(w[0]["level"], "info")
        self.assertIn("3", w[0]["message"])
        self.assertTrue(all("Trang" not in q["text"] and
                            all("Trang" not in o["text"] for o in q["options"])
                            for q in doc["questions"]))

    def test_no_warning_when_nothing_removed(self):
        doc = self.doc(False)
        self.assertFalse([x for x in doc["warnings"] if x["code"] == "page_furniture_removed"])


class TestPassageAfterOption(unittest.TestCase):
    LINES = ["Câu 1. first stem", *OPTS, "Câu 2. second stem", *OPTS, PASSAGE,
             "Câu 3. third stem", *OPTS, "Câu 4. fourth stem", *OPTS]

    def test_group_intro_opens_context_not_glued(self):
        _i, qs, ok = segment.segment(self.LINES)
        self.assertTrue(ok)
        self.assertEqual(qs[1]["options"][3]["text"], "four")
        self.assertEqual(qs[2]["context"], PASSAGE)
        self.assertNotIn("context", qs[0])

    def test_part_heading_opens_context(self):
        lines = ["Câu 1. s", *OPTS, "PHẦN II. Placeholder part", "Câu 2. s2", *OPTS]
        _i, qs, _ok = segment.segment(lines)
        self.assertEqual(qs[0]["options"][3]["text"], "four")
        self.assertEqual(qs[1]["context"], "PHẦN II. Placeholder part")

    def test_wrapped_option_lines_still_join(self):
        lines = ["Câu 1. s", "A. one", "B. two", "C. three", "D. four and", "more words",
                 "Câu 2. s2", *OPTS]
        _i, qs, _ok = segment.segment(lines)
        self.assertEqual(qs[0]["options"][3]["text"], "four and more words")

    def test_group_regex_shared_with_api(self):
        self.assertIs(api.GROUP_RE, segment.GROUP_RE)

    def test_context_repeated_to_group(self):
        _i, qs, _ok = segment.segment(self.LINES)
        doc = {"source": {"name": "x"}, "meta": dict(META), "questions": qs}
        text = api._from_questions(doc, ["# Exam Input", ""])
        self.assertEqual(text.count(PASSAGE), 2)  # questions 3 and 4
        q4 = text.split("## Question 4")[1]
        self.assertIn(PASSAGE, q4)
        self.assertNotIn(PASSAGE, text.split("## Question 3")[0])
        self.assertNotIn(PASSAGE, text.split("## Question 3")[0].split("D. four")[-1])


@unittest.skipIf(docx is None, "python-docx not installed")
class TestDocxPassage(unittest.TestCase):
    def test_docx_same_split(self):
        d = docx.Document()
        for line in TestPassageAfterOption.LINES:
            d.add_paragraph(line)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.docx")
            d.save(path)
            doc = api.ingest_document(path, config={"asset_dir": os.path.join(tmp, "a")})
        qs = doc["questions"]
        self.assertEqual(qs[1]["options"][3]["text"], "four")
        self.assertEqual(qs[2]["context"], PASSAGE)


if __name__ == "__main__":
    unittest.main()

"""Phase 15 (REQ-0018): one test per case of the ten-case list (tmp/input-exam-format.md s.8).

Deterministic extraction only: synthetic fixtures, no Claude call, no network. PDF/DOCX cases reuse
the helpers of test_ingest_pdf / test_ingest_docx and skip with a reason when a library is absent.
"""
import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
import test_ingest_docx as D  # noqa: E402
import test_ingest_pdf as P  # noqa: E402
from exam_engine import cli  # noqa: E402
from exam_engine.ingest import api  # noqa: E402
from exam_engine.ingest.schema import IngestError  # noqa: E402
from exam_engine.adapters import claude as exam_llm  # noqa: E402

INPUT_001 = os.path.join(ROOT, "examples", "english", "input-001.md")


class PdfCases(P.PdfBase):
    def test_1_digital_pdf(self):
        doc = self.ingest(self.save(self.lines_doc(P.QTEXT)))
        self.assertEqual(doc["status"], "native_text")
        self.assertEqual([q["n"] for q in doc["questions"]], [1, 2])

    @unittest.skipUnless("eng" in P._have, "tesseract eng data not found")
    def test_2_scanned_pdf_ocr(self):
        doc = self.ingest(self.save(P._scanned(self, ["Question 1. What is the capital",
                                                      "of France today"])))
        self.assertEqual(doc["status"], "ocr")

    @unittest.skipUnless(P.FONTS, "no DejaVu TTF with diacritics")
    def test_3_vietnamese_pdf(self):
        text = "Câu 1. Tính giá trị của biểu thức ắ ữ ơ đ"
        doc = self.ingest(self.save(self.lines_doc([text, "A. một", "B. hai"], P.FONTS[0])))
        self.assertIn(text, doc["pages"][0]["blocks"][0]["text"])

    def test_4_math_pdf(self):
        d = P.fitz.open()
        p = d.new_page()
        p.insert_text((72, 100), "The integral sign and alpha follow here: abcdefg", fontsize=12)
        p.insert_text((72, 140), "abc", fontsize=12, fontname="symb")
        doc = self.ingest(self.save(d))
        self.assertIn("math_possible", [w["code"] for w in doc["warnings"]])

    def test_5_table_and_diagram_pdf(self):
        d = P.fitz.open()
        p = d.new_page()
        for r in range(3):
            p.draw_line((72, 100 + r * 30), (272, 100 + r * 30))
        for c in range(3):
            p.draw_line((72 + c * 100, 100), (72 + c * 100, 160))
        for r in range(2):
            for c in range(2):
                p.insert_text((80 + c * 100, 120 + r * 30), "cell%d%d" % (r, c))
        p.draw_rect(P.fitz.Rect(250, 300, 400, 400))
        p.draw_circle((325, 350), 40)
        doc = self.ingest(self.save(d))
        types = [b["type"] for b in doc["pages"][0]["blocks"]]
        self.assertIn("table", types)
        self.assertIn("image", types)

    def test_6_multi_column_pdf(self):
        d = P.fitz.open()
        p = d.new_page()
        for i in range(3):
            p.insert_text((50, 100 + i * 100), "LEFT%d some words here" % i, fontsize=11)
            p.insert_text((330, 100 + i * 100), "RIGHT%d some words here" % i, fontsize=11)
        doc = self.ingest(self.save(d))
        order = [b["text"].split()[0] for b in doc["pages"][0]["blocks"]]
        self.assertEqual(order, ["LEFT0", "LEFT1", "LEFT2", "RIGHT0", "RIGHT1", "RIGHT2"])


class DocxCase(D.DocxBase):
    def test_7_docx(self):
        d = self.questions_doc()
        d.add_heading("Part", 1)
        doc = self.ingest(self.save(d))
        self.assertEqual([q["n"] for q in doc["questions"]], [1, 2])
        self.assertEqual([b["type"] for b in doc["pages"][0]["blocks"]].count("heading"), 1)
        self.assertEqual(doc["source"]["format"], "docx")


class MarkdownAndRest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_8_markdown(self):
        path = self.write("a.md", "# Title\n\nSome text.\n\n- item\n\n| a | b |\n| - | - |\n")
        doc = api.ingest_document(path)
        self.assertEqual([b["type"] for b in doc["pages"][0]["blocks"]],
                         ["heading", "paragraph", "list", "table"])
        self.assertEqual(doc["source"]["format"], "md")

    def test_9_invalid_or_unsupported_input(self):
        def code(path):
            with self.assertRaises(IngestError) as cm:
                api.ingest_document(path)
            return cm.exception.code
        self.assertEqual(code(self.write("a.xyz", "x")), "unsupported_format")
        self.assertEqual(code(self.write("a.md", "  \n")), "empty")
        self.assertEqual(code(self.write("a.pdf", "not a pdf")), "corrupt")
        self.assertEqual(code(self.write("a.docx", "not a zip")), "corrupt")
        self.assertEqual(code(os.path.join(self.dir, "missing.pdf")), "corrupt")

    def test_10_backward_compat_exam_md_and_dry_run(self):
        with open(INPUT_001, encoding="utf-8") as fh:
            text = fh.read()
        doc = api.ingest_document(INPUT_001)
        self.assertEqual(api.to_exam_text(doc), text)  # byte for byte
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(exam_llm, "run_claude", side_effect=AssertionError("called")):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.solve_main([INPUT_001, "--dry-run"])
        self.assertEqual((code, err.getvalue()), (0, ""))
        self.assertIn("calls <=", out.getvalue())


if __name__ == "__main__":
    unittest.main()

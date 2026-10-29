"""REQ-0015: Vietnamese/English subject names resolve to one key; informatics routes with its overlay."""
import contextlib
import io
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import parser, router  # noqa: E402
from exam_engine.utils.text import fold  # noqa: E402

CASES = {
    "math": ("Toán", "Toan", "TOÁN", "toan", "Mathematics"),
    "physics": ("Vật lý", "Vat ly", "VẬT LÝ", "Physics"),
    "literature": ("Ngữ văn", "Ngu van", "Văn", "Van", "Literature"),
    "english": ("Tiếng Anh", "Tieng Anh", "TIẾNG ANH", "English"),
    "informatics": ("Tin học", "Tin hoc", "TIN HỌC", "IT", "it", "Information Technology",
                    "Informatics", "CNTT"),
}
HEADER = """# Exam Input

Subject: Tin hoc
Level: Grade 12
Exam type: High School Graduation
Task: Multiple Choice
Mode: Solve

## Question 1

Số nhị phân 101 bằng số thập phân nào?

A. 3
B. 5
C. 6
D. 7
"""


class Names(unittest.TestCase):
    def test_every_alias_resolves(self):
        for key, names in CASES.items():
            for n in names:
                self.assertEqual(router.subject_key(n), key, n)
                self.assertIn(fold(n), router.known_names())

    def test_fold(self):
        self.assertEqual(fold("  Đại  Số "), "dai so")

    def test_unknown_rejected(self):
        for n in ("Chemistry", "Hóa học", "", None):
            self.assertIsNone(router.subject_key(n))
        d = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, d, True)
        p = os.path.join(d, "input.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(HEADER.replace("Tin hoc", "Hóa học"))
        self.assertIn("unsupported Subject: Hóa học", parser.validate_exam(parser.parse_exam(p)))


class Routing(unittest.TestCase):
    def test_header_without_diacritics_routes_and_uses_overlay(self):
        d = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, d, True)
        p = os.path.join(d, "input.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(HEADER)
        self.assertEqual(router.subject_key("Tin hoc"), "informatics")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.solve_main([p, "--dry-run", "--channel", "dev"])
        self.assertEqual(code, 0)
        self.assertIn("Quy tắc môn (Tin học)", buf.getvalue())


if __name__ == "__main__":
    unittest.main()

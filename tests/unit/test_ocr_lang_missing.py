"""Phase 51 (51.5): vie.traineddata absent -> hard lang_missing marker, error warning, run completes. $0.

The language list is faked (pick_ocr_language patched); the host keeps its real data.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from exam_engine.core import refcheck  # noqa: E402
from exam_engine.ingest import api, optional  # noqa: E402
from exam_engine.ingest.adapters import pdf as pdfmod  # noqa: E402

import ocr_gap_sweep as sweep  # noqa: E402

try:
    fitz = optional.load("fitz", "pymupdf")
except Exception:  # noqa: BLE001
    fitz = None
_dir, _lang, _have = pdfmod.pick_ocr_language({}) if fitz else (None, None, [])
READY = bool(fitz and _dir and "eng" in _have and os.path.exists(sweep.DEJAVU))


def _scanned(path):
    src = fitz.open()
    pg = src.new_page()
    y = 70
    for i in range(1, 4):
        pg.insert_text((50, y), "Cau %d. Tim gia tri cua bieu thuc sau day." % i, fontsize=11,
                       fontname="f", fontfile=sweep.DEJAVU)
        pg.insert_text((70, y + 20), "A. mot    B. hai", fontsize=11, fontname="f", fontfile=sweep.DEJAVU)
        y += 70
    out = sweep.scan(fitz, src)
    out.save(path)


@unittest.skipUnless(READY, "needs pymupdf, tesseract eng data, DejaVu font")
class TestLangMissing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pdf = os.path.join(cls.tmp.name, "scan.pdf")
        _scanned(cls.pdf)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_with(self, have):
        fake = (_dir, "+".join(have) or None, have)
        with mock.patch.object(pdfmod, "pick_ocr_language", return_value=fake):
            return pdfmod.ingest(self.pdf, {"asset_dir": os.path.join(self.tmp.name, "a")})

    def test_vie_absent_marks_every_ocr_question(self):
        doc = self.run_with(["eng"])
        qs = doc["questions"]
        self.assertGreaterEqual(len(qs), 3)
        for q in qs:
            self.assertIn("lang_missing", q.get("ocr_doubt", []))
            self.assertIn("ocr_doubt lang_missing", refcheck.incomplete_reasons(q))

    def test_warning_is_error_with_install_note(self):
        w = [x for x in self.run_with(["eng"])["warnings"] if x["code"] == "ocr_language_missing"]
        self.assertEqual(len(w), 1)
        self.assertEqual(w[0]["level"], "error")
        for part in ("vie.traineddata", "TESSDATA_PREFIX", "/usr/share/tesseract-ocr/",
                     "never fetch"):
            self.assertIn(part, w[0]["message"])

    def test_run_completes_and_questions_declined(self):
        doc = self.run_with(["eng"])
        self.assertIn("questions", doc)
        self.assertTrue(doc["pages"])
        self.assertIn("ocr_doubt", api.UNCERTAIN)

    def test_vie_present_no_lang_missing(self):
        doc = self.run_with(["vie", "eng"])
        self.assertFalse([w for w in doc["warnings"] if w["code"] == "ocr_language_missing"])
        for q in doc["questions"]:
            self.assertNotIn("lang_missing", q.get("ocr_doubt", []))

    def test_vie_alone_is_fine(self):
        doc = self.run_with(["vie"])
        self.assertFalse([w for w in doc["warnings"] if w["code"] == "ocr_language_missing"])


class TestBeforeAfterScore(unittest.TestCase):
    """51.6 helper: scoring on fake extraction (no OCR)."""

    def test_score_and_table(self):
        import ocr_before_after as ba
        gold = [{"n": 1, "text": "a b", "options": {"A": "x y"}},
                {"n": 2, "text": "c d", "options": {"A": "p"}},
                {"n": 3, "text": "e f", "options": {"A": "q"}}]
        doc = {"questions": [
            {"n": 1, "text": "a b", "options": {"A": "x y"}},
            {"n": 2, "text": "cd", "options": {"A": "p"}, "ocr_doubt": ["glued"]}]}
        s = ba.score(gold, doc)
        self.assertEqual((s["wrong"], s["wrong_unmarked"], s["correct"], s["marked_correct"]),
                         (2, 1, 1, 0))  # q2 wrong+marked, q3 missing = wrong+unmarked
        self.assertIn("1/3=0.33", ba.table([("A", "after", s)]))


if __name__ == "__main__":
    unittest.main()

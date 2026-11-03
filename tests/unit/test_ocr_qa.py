"""51.4/51.5/51.6 QA: end to end from scanned PDF to the engine decline, plus mutation guards."""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from exam_engine import engine  # noqa: E402
from exam_engine.ingest import api, optional  # noqa: E402
from exam_engine.ingest.adapters import pdf as pdfmod  # noqa: E402
from exam_engine.pipeline import parser  # noqa: E402

import ocr_gap_sweep as sweep  # noqa: E402
import test_ocr_lang_missing as lm  # noqa: E402

fitz = optional.load("fitz", "pymupdf")


def _parse_text(text):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "e.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return parser.parse_exam(p)


class TestOcrConstants(unittest.TestCase):
    def test_51_1_ocr_gap_pinned(self):
        # measured plateau 0.05-0.30 (ocr-gap-sweep.tsv); 0.40 over-glues family B
        self.assertEqual(pdfmod.OCR_GAP, 0.15)


@unittest.skipUnless(lm.READY, "needs pymupdf, tesseract eng data, DejaVu font")
class TestLangMissingEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pdf = os.path.join(cls.tmp.name, "scan.pdf")
        lm._scanned(cls.pdf)
        fake = (lm._dir, "eng", ["eng"])
        with mock.patch.object(pdfmod, "pick_ocr_language", return_value=fake):
            cls.doc = pdfmod.ingest(cls.pdf, {"asset_dir": os.path.join(cls.tmp.name, "a"),
                                                  "ocr_conf": "off"})  # 71: low_conf would add a kind

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_51_5_6_sidecar_rows_uncertain(self):
        rows = api.assembly(self.doc)
        self.assertGreaterEqual(len(rows), 3)
        self.assertTrue(all(r["assembly_status"] == "uncertain" for r in rows))
        self.assertTrue(all(any(x.startswith("ocr_doubt lang_missing") for x in r["reasons"]) for r in rows))

    def test_51_6_engine_declines_every_question(self):
        doc = dict(self.doc, meta=dict((k, "x") for k in api.REQUIRED))
        text = api.to_exam_text(doc)
        self.assertEqual(text.count("ocr_doubt lang_missing]"), 3)
        ex = _parse_text(text)
        got = engine.incomplete_ids(ex)
        self.assertEqual(len(got), len(ex["questions"]))
        self.assertTrue(all("ocr_doubt lang_missing" in v for v in got.values()))

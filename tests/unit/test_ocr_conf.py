"""Phase 71 (71.1-71.4): per-word OCR confidence, low_conf / token kinds, option_parity flag. $0, offline."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from exam_engine.ingest import optional, segment  # noqa: E402
from exam_engine.ingest.adapters import pdf as pdfmod  # noqa: E402

try:
    fitz = optional.load("fitz", "pymupdf")
except Exception:  # noqa: BLE001
    fitz = None

HEAD = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
TSV = (HEAD + "1\t1\t0\t0\t0\t0\t0\t0\t10\t10\t-1\t\n"
       "5\t1\t1\t1\t1\t1\t0\t0\t5\t5\t91.5\tCâu\n"
       "5\t1\t1\t1\t1\t2\t0\t0\t5\t5\t40\t$6,\n"
       "5\t1\t1\t1\t1\t3\t0\t0\t5\t5\t-1\tghost\n"
       "5\t1\t1\t1\t1\t4\t0\t0\t5\t5\t88\t(Câu)\n"
       "5\t1\t1\t1\t1\t5\t0\t0\t5\t5\t60\t.\n")


class FakePage:
    def get_pixmap(self, dpi=None):
        class P:
            def tobytes(self, fmt):
                return b"png"
        return P()


class TestParse(unittest.TestCase):
    def test_parse_tsv(self):
        got = pdfmod._parse_tsv(TSV)
        self.assertEqual(got, {"Câu": 88.0, "$6": 40.0})  # dup keeps min, conf -1 and level 1 skipped
        self.assertEqual(pdfmod._parse_tsv(""), {})
        self.assertEqual(pdfmod._parse_tsv(HEAD + "5\tx\n5\t1\t1\t1\t1\t1\t0\t0\t5\t5\tNaNx\tw\n"), {})

    def test_nfc_key(self):
        self.assertEqual(pdfmod._tok_key("Cậu.".replace("ậ", "ậ")), "Cậu")


class TestTsvConf(unittest.TestCase):
    def test_off_never_runs(self):
        with mock.patch.object(pdfmod.subprocess, "run") as run:
            self.assertIsNone(pdfmod._tsv_conf(FakePage(), "eng", None, {"ocr_conf": "off"}))
        run.assert_not_called()

    def test_missing_binary(self):
        why = []
        with mock.patch.object(pdfmod.shutil, "which", return_value=None):
            self.assertIsNone(pdfmod._tsv_conf(FakePage(), "eng", None, {"ocr_conf": "auto"}, why))
        self.assertEqual(len(why), 1)

    def test_timeout_and_exit(self):
        import subprocess
        with mock.patch.object(pdfmod.shutil, "which", return_value="/bin/t"):
            with mock.patch.object(pdfmod.subprocess, "run",
                                   side_effect=subprocess.TimeoutExpired("t", 1)):
                self.assertIsNone(pdfmod._tsv_conf(FakePage(), "eng", None, {"ocr_conf": "auto"}))
            r = mock.Mock(returncode=1, stdout=b"")
            with mock.patch.object(pdfmod.subprocess, "run", return_value=r):
                self.assertIsNone(pdfmod._tsv_conf(FakePage(), "eng", "/d", {"ocr_conf": "auto"}))

    def test_ok_argv_is_list_no_shell(self):
        r = mock.Mock(returncode=0, stdout=TSV.encode())
        with mock.patch.object(pdfmod.shutil, "which", return_value="/bin/t"), \
                mock.patch.object(pdfmod.subprocess, "run", return_value=r) as run:
            got = pdfmod._tsv_conf(FakePage(), "vie+eng", "/d", {"ocr_conf": "auto"})
        self.assertEqual(got["$6"], 40.0)
        argv = run.call_args[0][0]
        self.assertIsInstance(argv, list)
        self.assertEqual(argv[-1], "tsv")
        self.assertIn("/d", argv)
        self.assertNotIn("shell", run.call_args[1])


class TestOddToken(unittest.TestCase):
    def test_shapes(self):
        for t in ("h0n", "$o", "c6u"):
            self.assertTrue(pdfmod._odd_token(t), t)
        for t in ("x2", "H2O", "$5", "2x", "101", "US$", "R$", "Fe2O3", "¢ó"):
            self.assertFalse(pdfmod._odd_token(t, None), t)

    def test_weak_needs_low_conf(self):
        self.assertFalse(pdfmod._odd_token("$6"))
        self.assertFalse(pdfmod._odd_token("$6", 95, 70))
        self.assertTrue(pdfmod._odd_token("$6", 50, 70))
        with mock.patch.object(pdfmod, "TOKEN_MARGIN", 10):
            self.assertTrue(pdfmod._odd_token("$6", 75, 70))
        self.assertFalse(pdfmod._odd_token("x2", 10, 70))  # lower-case + digit is not a weak shape


class TestDoubtConf(unittest.TestCase):
    def _run(self, pages, ocr_pages, conf, floor=None):
        lines = [l for p in pages for l in p]
        starts = []
        _, qs, _ = segment.segment(lines, starts=starts)
        ocr_q = pdfmod._ocr_doubt(qs, starts, lines, [len(p) for p in pages], set(ocr_pages), set(), True,
                                  conf=conf, floor=floor)
        return qs, ocr_q

    PAGES = [["Câu 1. giá trị gia", "A. một", "B. hai"], ["Câu 2. giá trị gia", "A. một", "B. hai"]]

    def test_low_conf_only_on_ocr_page(self):
        conf = {0: {"gia": 55.0}, 1: {"gia": 55.0}}
        qs, ocr_q = self._run(self.PAGES, [0], conf)
        self.assertEqual(qs[0]["ocr_doubt"], ["low_conf"])
        self.assertNotIn("ocr_doubt", qs[1])  # native page
        self.assertEqual(ocr_q, [0])

    def test_none_conf_is_old_behaviour_and_floor_override(self):
        qs, _ = self._run(self.PAGES, [0, 1], None)
        self.assertNotIn("ocr_doubt", qs[0])
        conf = {0: {"gia": 75.0}}
        qs, _ = self._run(self.PAGES, [0], conf)
        self.assertNotIn("ocr_doubt", qs[0])
        qs, _ = self._run(self.PAGES, [0], conf, floor=80)
        self.assertEqual(qs[0]["ocr_doubt"], ["low_conf"])

    def test_missing_word_no_flag(self):
        qs, _ = self._run(self.PAGES, [0], {0: {"other": 1.0}})
        self.assertNotIn("ocr_doubt", qs[0])

    def test_token_kind(self):
        qs, _ = self._run([["Câu 1. h0n gì", "A. a", "B. b"]], [0], None)
        self.assertEqual(qs[0]["ocr_doubt"], ["token"])

    def test_science_exam_no_flags(self):
        pages = [["Câu 1. H2O boils at x2 = $5 per CO2 unit", "A. 1", "B. 2", "C. 3", "D. 4", "E. 5"],
                 ["Câu 2. Cost of Fe2O3 is $5", "A. a", "B. b", "C. c", "D. d", "E. e"]]
        conf = {0: {"H2O": 95.0, "$5": 90.0}, 1: {"Fe2O3": 92.0}}
        qs, ocr_q = self._run(pages, [0, 1], conf)
        pdfmod._option_parity(qs, ocr_q)
        for q in qs:
            self.assertNotIn("ocr_doubt", q)
            self.assertNotIn("structure", q)


def _q(texts):
    return {"n": 1, "text": "t", "options": [{"key": "ABCDE"[i], "text": t} for i, t in enumerate(texts)]}


class TestParity(unittest.TestCase):
    def test_odd_one_out(self):
        qs = [_q(["Giá trị", "Kết quả", "$6 lớn", "Đáp số"])]
        pdfmod._option_parity(qs, [0])
        self.assertEqual(qs[0]["structure"], ["option_parity"])

    def test_numeric_options_ok(self):
        qs = [_q(["1", "2", "3", "4"])]
        pdfmod._option_parity(qs, [0])
        self.assertNotIn("structure", qs[0])

    def test_count_vs_mode(self):
        qs = [_q(["a", "b", "c", "d"]) for _ in range(5)] + [_q(["a", "b", "c", "d", "e"])]
        pdfmod._option_parity(qs, list(range(6)))
        self.assertEqual([("structure" in q) for q in qs], [False] * 5 + [True])

    def test_mixed_counts_no_flag(self):
        qs = [_q(["a", "b"]), _q(["a", "b", "c", "d"]), _q(["a", "b"]), _q(["a", "b", "c", "d"])]
        pdfmod._option_parity(qs, [0, 1, 2, 3])
        self.assertFalse(any("structure" in q for q in qs))

    def test_native_untouched(self):
        qs = [_q(["Giá", "Kết", "$6", "Đáp"])]
        pdfmod._option_parity(qs, [])
        self.assertNotIn("structure", qs[0])


@unittest.skipUnless(fitz and shutil.which("tesseract"), "needs fitz and the tesseract binary")
class TestImage(unittest.TestCase):
    def test_tsv_conf_on_rendered_page(self):
        d, lang, _ = pdfmod.pick_ocr_language({})
        if not lang:
            self.skipTest("no tesseract language data")
        doc = fitz.open()
        pg = doc.new_page()
        pg.insert_text((50, 80), "The quick brown fox jumps over the lazy dog", fontsize=10)
        pg.insert_text((50, 120), "Another line of plain text here", fontsize=6)
        got = pdfmod._tsv_conf(pg, lang, d, {"ocr_conf": "auto"})
        self.assertTrue(got)
        self.assertTrue(all(0 <= v <= 100 for v in got.values()))


@unittest.skipUnless(fitz and shutil.which("tesseract"), "needs fitz and the tesseract binary")
class TestGolden(unittest.TestCase):
    def test_conf_off_equals_signals_removed(self):
        import json
        import test_ocr_lang_missing as lm
        if not lm.READY:
            self.skipTest("needs eng data and DejaVu")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "s.pdf")
            lm._scanned(path)
            cfg = {"asset_dir": os.path.join(td, "a"), "ocr_conf": "off"}
            new = pdfmod.ingest(path, dict(cfg))
            with mock.patch.object(pdfmod, "_odd_token", lambda *a, **k: False), \
                    mock.patch.object(pdfmod, "_option_parity", lambda *a, **k: None):
                old = pdfmod.ingest(path, dict(cfg))
        self.assertEqual(json.dumps(new, sort_keys=True), json.dumps(old, sort_keys=True))


class TestCalibrationPool(unittest.TestCase):
    def test_family_c_has_clean_pool_family(self):
        import ocr_before_after as ba
        self.assertIn("Cm", ba.FAMILIES71)
        self.assertEqual(ba.FAMILIES71["Cm"][:2], ba.FAMILIES71["C"][:2])
        g = ba.gold_questions("mild", 12)
        self.assertEqual(len(g), 12)
        self.assertTrue(all(ord(ch) < 128 or ch == "â" for q in g for ch in q["text"] + "".join(q["options"].values())))


if __name__ == "__main__":
    unittest.main()

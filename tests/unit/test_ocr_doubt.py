"""Phase 51 (51.2-51.4): OCR-tolerant furniture key, near-miss leaks, ocr_doubt marker. $0."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from exam_engine.core import refcheck  # noqa: E402
from exam_engine.ingest import api, segment  # noqa: E402
from exam_engine.ingest.adapters import pdf as pdfmod  # noqa: E402


def _page(top, n, bottom):
    return [top, "Câu %d. Nội dung số %d là gì" % (n, n), "A. một", "B. hai", bottom]


class TestFurnitureKey(unittest.TestCase):
    def test_spacing_and_case_variants_removed(self):
        pages = [_page("Đề thi thử - Môn Toán", 1, "Trang 1"),
                 _page("Đề thi thử- Môn Toán", 2, "Trang 2"),
                 _page("ĐỀ THI THỬ - MÔN  TOÁN", 3, "Trang 3"),
                 _page("Đềthi thử -Môn Toán", 4, "Trang 4")]
        leaks = set()
        out, removed = pdfmod._strip_furniture(pages, leaks)
        self.assertEqual(removed, 8)
        self.assertEqual(leaks, set())
        self.assertTrue(all(len(p) == 3 for p in out))

    def test_garbled_header_kept_and_marked(self):
        pages = [_page("Đề thi thử - Môn Toán", 1, "Trang 1"),
                 _page("Đề thi thử - Môn Toán", 2, "Trang 2"),
                 _page("Đề thi thử - Môn Toán", 3, "Trang 3"),
                 _page("Đề thi thử - Môn Toan", 4, "Trang 4")]
        leaks = set()
        out, removed = pdfmod._strip_furniture(pages, leaks)
        self.assertEqual(removed, 7)
        self.assertEqual(out[3][0], "Đề thi thử - Môn Toan")
        self.assertEqual(leaks, {(3, 0)})

    def test_far_garbled_not_marked(self):
        pages = [_page("Đề thi thử - Môn Toán", i, "Trang %d" % i) for i in (1, 2, 3)]
        pages.append(_page("Zxqv wkj plm", 4, "Trang 4"))
        leaks = set()
        pdfmod._strip_furniture(pages, leaks)
        self.assertEqual(leaks, set())

    def test_numbered_line_at_page_top_kept(self):
        pages = [["Câu 1. abc", "A. x", "B. y"] for _ in range(4)]
        out, removed = pdfmod._strip_furniture(pages)
        self.assertEqual(removed, 0)


class TestSegmentStarts(unittest.TestCase):
    def test_starts_match_and_output_equal(self):
        lines = ["Đề", "Câu 1. a", "A. x", "B. y", "Câu 2. b", "A. x", "B. y"]
        s = []
        got = segment.segment(lines, starts=s)
        self.assertEqual(s, [1, 4])
        self.assertEqual(got, segment.segment(lines))


class TestTokens(unittest.TestCase):
    def test_glued(self):
        for t in ("tửtửánh", "sốđơn"):
            self.assertTrue(pdfmod._glued(t), t)
        for t in ("trường", "Nguyễn", "x2", "Hello", "đề", "người"):
            self.assertFalse(pdfmod._glued(t), t)

    def test_odd_chars(self):
        self.assertTrue(pdfmod._odd_chars("¢ó"))
        for t in ("x²", "≤", "Nguyễn", "(a+b)^2=5%", "√3", "“ok”"):
            self.assertFalse(pdfmod._odd_chars(t), t)


class TestOcrDoubt(unittest.TestCase):
    def _run(self, texts, ocr_pages, leaks=(), lang_ok=True):
        lines = [l for p in texts for l in p]
        pl = [len(p) for p in texts]
        starts = []
        _, qs, _ = segment.segment(lines, starts=starts)
        pdfmod._ocr_doubt(qs, starts, lines, pl, set(ocr_pages), set(leaks), lang_ok)
        return qs

    def test_kinds_and_native_untouched(self):
        pages = [["Câu 1. tửtửánh sai", "A. một", "B. hai", "Câu 2. ¢ó gì", "A. a", "B. b"],
                 ["Câu 3. sạch sẽ", "A. a", "B. b"]]
        qs = self._run(pages, [0], leaks=[(0, 4)])
        self.assertEqual(qs[0]["ocr_doubt"], ["glued"])
        self.assertEqual(qs[1]["ocr_doubt"], ["chars", "furniture"])
        self.assertNotIn("ocr_doubt", qs[2])  # native page 1

    def test_lang_missing(self):
        qs = self._run([["Câu 1. sạch", "A. a", "B. b"]], [0], lang_ok=False)
        self.assertEqual(qs[0]["ocr_doubt"], ["lang_missing"])

    def test_no_ocr_pages_no_doubt(self):
        qs = self._run([["Câu 1. tửtửánh", "A. a", "B. b"]], [])
        self.assertNotIn("ocr_doubt", qs[0])


class TestGate(unittest.TestCase):
    def test_reason_marker_and_uncertain(self):
        q = {"n": 1, "text": "x", "options": [], "ocr_doubt": ["glued", "chars"]}
        r = refcheck.incomplete_reasons(q)
        self.assertIn("ocr_doubt glued", r)
        self.assertIn("ocr_doubt chars", r)
        self.assertEqual(refcheck.marker(r),
                         "[Incomplete: missing_text ocr_doubt glued, ocr_doubt chars]")
        self.assertIn("ocr_doubt", api.UNCERTAIN)

    def test_clean_question_unaffected(self):
        q = {"n": 1, "text": "x", "options": []}
        self.assertFalse(any(x.startswith("ocr_doubt") for x in refcheck.incomplete_reasons(q)))


if __name__ == "__main__":
    unittest.main()

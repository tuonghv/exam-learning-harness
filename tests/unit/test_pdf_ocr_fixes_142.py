"""TASK-142 (REQ-0149): PDF OCR-route fixes 138-F005/F007/F008/F009/F010. Fake fitz objects, no real OCR, $0."""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from exam_engine.ingest import optional  # noqa: E402
from exam_engine.ingest.adapters import pdf  # noqa: E402
from exam_engine.ingest.schema import IngestError  # noqa: E402

GARBLED = "�" * 60
OPTS = "\nA. một\nB. hai\nC. ba\nD. bốn"


class Rect(tuple):
    is_empty = False
    width = 600
    height = 800

    def __new__(cls, *a):
        return tuple.__new__(cls, a[0] if len(a) == 1 else a)

    def __and__(self, other):
        return self


class FakeTable:
    def __init__(self, bbox):
        self.bbox = bbox

    def extract(self):
        return [["x", "y"], ["1", "2"]]


class FakePage:
    rect = Rect(0, 0, 600, 800)

    def __init__(self, tables=()):
        self._tables = tables

    def find_tables(self):
        return mock.Mock(tables=[FakeTable(b) for b in self._tables])

    def get_image_info(self):
        return []

    def get_drawings(self):
        return []

    def cluster_drawings(self, drawings=None):
        return []

    def get_textpage_ocr(self, **kw):
        return object()


class FakeDoc:
    needs_pass = False

    def __init__(self, pages):
        self.pages = pages
        self.page_count = len(pages)

    def __getitem__(self, i):
        return self.pages[i]

    def close(self):
        pass


class FakeFitz:
    VersionBind = "fake"
    Rect = Rect


def blk(y, text):
    return ((40, y, 500, y + 40), text, set())


def run(pages, native, ocr, config=None):
    """pages: list of FakePage; native/ocr: per page lists of blocks."""
    it_n, it_o = iter(native), iter(ocr)
    cfg = {"ocr_conf": "off", "asset_dir": tempfile.mkdtemp()}
    cfg.update(config or {})
    with mock.patch.object(pdf, "_page_blocks", lambda page, textpage=None: next(it_n)), \
            mock.patch.object(pdf, "_ocr_blocks", lambda page, tp, gap=0: next(it_o)), \
            mock.patch.object(pdf, "_order_page", lambda page, blocks, w: (blocks, False)), \
            mock.patch.object(pdf, "pick_ocr_language", lambda c=None: (None, "vie+eng", ["vie", "eng"])):
        return pdf._extract(FakeFitz, FakeDoc(pages), b"%PDF-fake", "x.pdf", cfg)


class OcrFixes(unittest.TestCase):
    def test_f005_ocr_page_drops_native_tables(self):
        # table box covers the OCR block; OCR text must stay and no native table block may repeat it
        page = FakePage(tables=[(30, 100, 520, 300)])
        ocr = [blk(120, "Câu 1. Bảng số liệu dưới đây cho biết gì?" + OPTS)]
        doc = run([page], [[blk(10, GARBLED)]], [ocr])
        p = doc["pages"][0]
        self.assertEqual(p["method"], "ocr")
        self.assertEqual([b["type"] for b in p["blocks"]], ["paragraph"])
        self.assertIn("Câu 1.", p["blocks"][0]["text"])

    def test_f005_missing_text_keeps_table_and_ocr_stem(self):
        page = FakePage(tables=[(30, 100, 520, 300)])
        ocr = [blk(20, "Câu 1. Đọc bảng sau và trả lời câu hỏi?" + OPTS), blk(120, "x y 1 2 cell text in table")]
        doc = run([page], [[]], [ocr])
        p = doc["pages"][0]
        self.assertEqual(p["method"], "ocr")
        self.assertEqual([b["type"] for b in p["blocks"]].count("table"), 1)
        self.assertEqual(sum("Câu 1." in b["text"] for b in p["blocks"]), 1)
        self.assertFalse(any("cell text in table" in b["text"] for b in p["blocks"]))

    def test_f007_clean_ocr_beats_longer_garbled_native(self):
        page = FakePage()
        ocr = [blk(10, "Câu 1. Nội dung ngắn?" + OPTS)]
        self.assertLess(len(ocr[0][1]), len(GARBLED * 2))
        doc = run([page], [[blk(10, GARBLED * 2)]], [ocr])
        self.assertEqual(doc["pages"][0]["method"], "ocr")
        self.assertEqual(doc["pages"][0]["status"], "ocr")

    def test_f008_ocr_doubt_gets_suspect_ocr_pages(self):
        good = "Câu 1. Nội dung trang một khá dài?" + OPTS
        bad = "Câu 2. Nội dung trang hai khá dài ??����?" + OPTS
        seen = []
        real = pdf._ocr_doubt

        def spy(*a, **kw):
            seen.append(set(a[7]))
            return real(*a, **kw)

        with mock.patch.object(pdf, "_ocr_doubt", spy):
            # page 0: garbled native (bad_encoding warning) + clean OCR; page 1: empty native + suspect OCR
            doc = run([FakePage(), FakePage()], [[blk(10, GARBLED)], []],
                      [[blk(10, good)], [blk(10, bad)]])
        self.assertEqual([p["status"] for p in doc["pages"]], ["ocr", "needs_review"])
        self.assertEqual(seen, [{1}])

    def test_f009_ocr_pages_skip_page_cut_check(self):
        def pg(n):
            return {"n": n, "status": "needs_review", "method": "ocr", "chars": 500, "blocks": []}
        lines = [["Câu 1. stem", "A. x", "B. y"], ["continued text", "Câu 2. z"]]
        self.assertEqual(pdf._cut_boundaries([pg(1), pg(2)], lines), [])
        nat = dict(pg(1), status="native_text", method="native")
        self.assertTrue(pdf._cut_boundaries([nat, dict(nat, n=2)], lines))

    def test_f010_page_access_error_is_ingest_error(self):
        class Boom(FakeDoc):
            def __getitem__(self, i):
                raise RuntimeError("broken page tree")

        fitz = mock.Mock(VersionBind="fake")
        fitz.open.return_value = Boom([FakePage()])
        with tempfile.NamedTemporaryFile(suffix=".pdf") as fh:
            fh.write(b"%PDF-fake")
            fh.flush()
            with mock.patch.object(optional, "load", lambda m, p: fitz):
                with self.assertRaises(IngestError) as cm:
                    pdf.ingest(fh.name)
        self.assertEqual(cm.exception.code, "corrupt")
        self.assertIn("RuntimeError", cm.exception.message)


if __name__ == "__main__":
    unittest.main()

"""Phase 51 (51.1/51.7): OCR text rebuilt from rawdict char boxes. $0, no network."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from exam_engine.ingest import optional  # noqa: E402
from exam_engine.ingest.adapters import pdf as pdfmod  # noqa: E402

import ocr_gap_sweep as sweep  # noqa: E402

try:
    fitz = optional.load("fitz", "pymupdf")
except Exception:  # noqa: BLE001
    fitz = None
_dir, _lang, _have = pdfmod.pick_ocr_language({}) if fitz else (None, None, [])


def _chars(text, h=10.0, w=5.0, gap_after=None, x=0.0):
    """rawdict chars for text; gap_after = {index: extra gap before char index}."""
    out = []
    for i, ch in enumerate(text):
        x += (gap_after or {}).get(i, 0.0)
        out.append({"c": ch, "bbox": (x, 0.0, x + w, h)})
        x += w
    return out


class FakePage:
    def __init__(self, blocks):
        self.blocks = blocks

    def get_text(self, kind, textpage=None):
        if kind == "rawdict":
            return {"blocks": self.blocks}
        raise AssertionError(kind)


def _block(lines):
    return {"type": 0, "bbox": (0, 0, 100, 10), "lines": [
        {"spans": [{"font": "f", "text": t, "chars": c}]} for t, c in lines]}


class TestOcrBlocks(unittest.TestCase):
    def blocks(self, text, gaps, **kw):
        page = FakePage([_block([(text, _chars(text, gap_after=gaps))])])
        return pdfmod._ocr_blocks(page, None, **kw)[0][1]

    def test_gap_thresholds(self):
        self.assertEqual(self.blocks("abcd", {2: 0.1 * 10}, gap=0.15), "abcd")
        self.assertEqual(self.blocks("abcd", {2: 0.3 * 10}, gap=0.15), "ab cd")

    def test_bridge_space_kept_once(self):
        self.assertEqual(self.blocks("ab cd", {3: 4.0}), "ab cd")

    def test_missing_bbox_uses_span_text(self):
        chars = _chars("abcd")
        del chars[1]["bbox"]
        page = FakePage([_block([("ab cd", chars)])])
        self.assertEqual(pdfmod._ocr_blocks(page, None)[0][1], "ab cd")

    def test_no_chars_uses_span_text(self):
        page = FakePage([_block([("ab cd", [])])])
        self.assertEqual(pdfmod._ocr_blocks(page, None)[0][1], "ab cd")


@unittest.skipUnless(fitz and "eng" in _have, "PyMuPDF or tesseract eng data not found")
class TestOcrFamilies(unittest.TestCase):
    def test_glued_tokens_per_page(self):
        rows = sweep.sweep(families=("A", "B"), gaps=[pdfmod.OCR_GAP], bridge=False)
        for fam, _gap, glued, split, _cer in rows:
            self.assertLessEqual(glued, 3 * 2, fam)  # 2 pages; bridge text has ~30 here
            self.assertEqual(split, 0, fam)

    @unittest.skipUnless("vie" in _have, "vie data missing")
    def test_respacing_beats_bridge_text_with_vie(self):
        rows = sweep.sweep(families=("A",), gaps=[pdfmod.OCR_GAP])
        new, old = rows[0], rows[1]  # gap row, then the bridge baseline
        self.assertLess(new[2], old[2])


if __name__ == "__main__":
    unittest.main()

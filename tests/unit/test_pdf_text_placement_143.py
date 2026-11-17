"""TASK-143 (REQ-0150): PDF text placement fixes 138-F001..F004. Synthetic items/pages, $0, no PDF, no OCR."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from exam_engine.ingest import parts  # noqa: E402
from exam_engine.ingest.adapters import pdf  # noqa: E402


class TestPlacement(unittest.TestCase):
    def test_f001_table_stays_in_its_column(self):
        rows = [["a", "b"], ["1", "2"]]
        items = [("paragraph", (40, 50, 280, 90), "Câu 1. left top", {}),
                 ("paragraph", (40, 400, 280, 440), "Câu 2. left bottom", {}),
                 ("paragraph", (320, 100, 560, 140), "Câu 3. right top", {}),
                 ("paragraph", (320, 290, 560, 330), "Câu 4. right mid", {}),
                 ("table", (40, 300, 280, 380), "a | b\n1 | 2", {"rows": rows})]
        lines = pdf._text_lines(items, 297.5)
        self.assertEqual(lines.index("| a | b |"), lines.index("Câu 1. left top") + 1)
        # no mid -> single-column behaviour unchanged
        self.assertGreater(pdf._text_lines(items).index("| a | b |"), 3)

    def test_f001_d1_block_order_per_column(self):
        items = [("paragraph", (40, 50, 280, 90), "L1", {}), ("paragraph", (320, 100, 560, 140), "R1", {}),
                 ("paragraph", (320, 400, 560, 440), "R2", {})]
        self.assertEqual(pdf._insert_pos(items, (40, 300, 280, 380), 297.5), 1)  # after L1, not inside the right column
        self.assertEqual(pdf._insert_pos(items, (40, 300, 280, 380)), 2)  # single column: before the first lower item

    def test_f002_rows_keep_multiline_cells_and_pipes(self):
        rows = [["Tỉnh", "Số"], ["Đắk\nNông", "1,064"]]
        items = [("table", (0, 0, 10, 10), "Tỉnh | Số\nĐắk\nNông | 1,064", {"rows": rows})]
        self.assertEqual(pdf._text_lines(items), ["| Tỉnh | Số |", "| Đắk Nông | 1,064 |"])
        box = [("table", (0, 0, 10, 10), "Cho |x - 1| < 3", {"rows": [["Cho |x - 1| < 3"], ["line two"]]})]
        self.assertEqual(pdf._text_lines(box), ["Cho |x - 1| < 3", "line two"])

    def test_f002_select_pages_passes_rows(self):
        rows = [["Tỉnh", "Số"], ["Đắk\nNông", "1,064"]]
        blocks = [{"type": "paragraph", "bbox": [40, 50, 500, 70], "text": "Câu 1. Tỉ lệ?\nA. 1\nB. 2\nC. 3\nD. 4"},
                  {"type": "table", "bbox": [40, 100, 500, 160], "text": "Tỉnh | Số\nĐắk\nNông | 1,064", "rows": rows}]
        doc = {"pages": [{"n": 1, "blocks": blocks}], "assets": [], "warnings": [],
               "source": {"format": "pdf", "name": "t.pdf"}}
        new = parts.select_pages(doc, "1")
        self.assertIn("| Đắk Nông | 1,064 |", json.dumps(new["questions"], ensure_ascii=False))

    def test_f003_options_in_a_row_are_not_columns(self):
        class Page:
            pass
        blocks = [((40, 100, 560, 140), "Câu 1. stem\nA. 1 B. 2   C. 3 D. 4", set())]
        lines = []
        for q, y in ((1, 100), (2, 200), (3, 300)):
            lines.append(((40, y, 200, y + 12), "Câu %d. short stem" % q, set()))
            lines.append(((40, y + 15, 250, y + 27), "A. %d   B. %d" % (q, q + 1), set()))
            lines.append(((320, y + 15, 520, y + 27), "C. %d   D. %d" % (q + 2, q + 3), set()))
        orig = pdf._line_blocks
        pdf._line_blocks = lambda page: lines
        try:
            res, two = pdf._order_page(Page(), blocks, 595.0)
        finally:
            pdf._line_blocks = orig
        self.assertFalse(two)
        # a true right column (stems) is still detected
        cols = [((40, 100, 250, 112), "Câu 1. left a", set()), ((40, 200, 250, 212), "Câu 2. left b", set()),
                ((320, 100, 520, 112), "Câu 3. right a", set()), ((320, 200, 520, 212), "Câu 4. right b", set())]
        pdf._line_blocks = lambda page: cols
        try:
            res, two = pdf._order_page(Page(), blocks, 595.0)
        finally:
            pdf._line_blocks = orig
        self.assertTrue(two)

    def test_f004_group_lead_line_survives_furniture_strip(self):
        lead = "Dựa vào thông tin dưới đây để trả lời các câu từ %d đến %d"
        pages = []
        for p in range(6):
            body = ["Câu %d. stem" % (p * 2 + 1), "A. x", "B. y", "Câu %d. stem b" % (p * 2 + 2), "A. x", "B. y"]
            pages.append(([lead % (p * 2 + 1, p * 2 + 3)] if p % 2 == 0 else []) + body)
        pages[1] = ["Read the following passage and mark the answer."] + pages[1]
        pages[3] = ["Read the following passage and mark the answer."] + pages[3]
        pages[5] = ["Read the following passage and mark the answer."] + pages[5]
        out, _removed = pdf._strip_furniture(pages)
        self.assertEqual(sum(1 for pg in out for ln in pg if ln.startswith("Dựa vào")), 3)
        self.assertEqual(sum(1 for pg in out for ln in pg if ln.startswith("Read the")), 3)


if __name__ == "__main__":
    unittest.main()

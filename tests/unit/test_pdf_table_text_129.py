"""TASK-129 (REQ-0136): PDF table blocks reach the free text path (boxed passage, data table). Synthetic, $0."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import parts, segment  # noqa: E402
from exam_engine.ingest.adapters import pdf  # noqa: E402

BOX = " | “Survey text line one |  | \nline two of the survey. |  |  | \n(Source: News)"
DATA = "TT | Province | Ratio\n1 | Dak Nong | 1,064\n2 | Lang Son | 1,045"
OPTS = "A. 1\nB. 2\nC. 3\nD. 4"


def items():
    """Page items as the adapter lists them: tables first, a footer early, then the reading order."""
    return [("table", (100, 300, 500, 360), DATA, {}),
            ("table", (60, 520, 540, 600), BOX, {}),
            ("paragraph", (290, 810, 310, 827), "13", {}),
            ("paragraph", (40, 100, 550, 120), "Câu 1: First question?\n" + OPTS, {}),
            ("paragraph", (40, 250, 550, 290), "Dựa vào thông tin dưới đây để trả lời các câu từ 2 đến 3\n"
                                               "Bảng sau thể hiện tỉ lệ", {}),
            ("paragraph", (40, 370, 550, 400), "Câu 2: Ratio of row 1?\n" + OPTS, {}),
            ("paragraph", (40, 410, 550, 440), "Câu 3: Ratio of row 2?\n" + OPTS, {}),
            ("paragraph", (40, 480, 550, 510), "Dựa vào thông tin dưới đây để trả lời các câu từ 4 đến 4", {}),
            ("paragraph", (40, 610, 550, 640), "Câu 4: Why do firms train staff?\n" + OPTS, {})]


class TableLines(unittest.TestCase):
    def test_box_is_plain_passage(self):
        self.assertEqual(segment.table_lines(BOX),
                         ["“Survey text line one", "line two of the survey.", "(Source: News)"])

    def test_data_rows_are_pipe_rows(self):
        self.assertEqual(segment.table_lines(DATA),
                         ["| TT | Province | Ratio |", "| 1 | Dak Nong | 1,064 |", "| 2 | Lang Son | 1,045 |"])


class Placement(unittest.TestCase):
    def test_tables_after_last_block_above_footer_ignored(self):
        lines = pdf._text_lines(items())
        self.assertLess(lines.index("Bảng sau thể hiện tỉ lệ"), lines.index("| TT | Province | Ratio |"))
        self.assertLess(lines.index("| 2 | Lang Son | 1,045 |"), lines.index("Câu 2: Ratio of row 1?"))
        self.assertLess(lines.index("(Source: News)"), lines.index("Câu 4: Why do firms train staff?"))
        self.assertEqual(lines[0], "13")  # the early-listed footer keeps its place (furniture filter drops it)

    def test_side_by_side_tables_left_first(self):
        its = [("table", (330, 434, 548, 499), "right half", {}), ("table", (95, 434, 256, 486), "left half", {}),
               ("paragraph", (66, 357, 451, 369), "Question three stem", {}),
               ("paragraph", (66, 421, 104, 434), "Câu 4:", {})]
        self.assertEqual(pdf._text_lines(its), ["Question three stem", "Câu 4:", "left half", "right half"])

    def test_segmented_context_and_no_row_question(self):
        intro, qs, ok = segment.segment([ln for ln in pdf._text_lines(items()) if ln != "13"])
        self.assertEqual([q["n"] for q in qs], [1, 2, 3, 4])
        self.assertTrue(all(len(q["options"]) == 4 for q in qs))
        self.assertIn("| 1 | Dak Nong | 1,064 |", qs[1]["context"])
        self.assertIn("line two of the survey.", qs[3]["context"])


class SelectPages(unittest.TestCase):
    def test_pages_resegment_keeps_tables(self):
        blocks = [{"type": k, "bbox": list(bb), "text": t} for k, bb, t, _ in items()]
        doc = {"pages": [{"n": 1, "blocks": blocks}], "assets": [], "warnings": [],
               "source": {"format": "pdf", "name": "t.pdf"}}
        new = parts.select_pages(doc, "1")
        qs = {q["n"]: q for q in new["questions"]}
        self.assertIn("| 2 | Lang Son | 1,045 |", qs[2]["context"])
        self.assertIn("line two of the survey.", qs[4]["context"])


if __name__ == "__main__":
    unittest.main()

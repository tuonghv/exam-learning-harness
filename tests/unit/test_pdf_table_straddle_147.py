"""TASK-147 (REQ-0153): 138-F006 - a text block that only partly covers a table keeps its lines outside the table.
Synthetic blocks/lines, $0, no PDF, no OCR."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from exam_engine.ingest.adapters import pdf  # noqa: E402

TABLE = (50, 120, 500, 200)


class TestStraddle(unittest.TestCase):
    def test_f006_review_case_keeps_stem_line(self):
        # the review's case: block (50,100,500,200) = stem line + first cells, centre y=150 inside the table
        blocks = [((50, 40, 500, 90), "Câu 1. intro", set()),
                  ((50, 100, 500, 200), "Câu 2. Cho bảng sau:\na | b\n1 | 2", set()),
                  ((50, 210, 500, 230), "A. 1", set())]
        lines = [((50, 40, 500, 90), "Câu 1. intro", set()),
                 ((50, 100, 500, 118), "Câu 2. Cho bảng sau:", {"F"}),
                 ((50, 125, 500, 160), "a | b", set()), ((50, 165, 500, 198), "1 | 2", set()),
                 ((50, 210, 500, 230), "A. 1", set())]
        out = pdf._drop_table_blocks(blocks, [TABLE], lambda: lines)
        self.assertEqual([b[1] for b in out], ["Câu 1. intro", "Câu 2. Cho bảng sau:", "A. 1"])
        self.assertEqual(out[1][2], {"F"})

    def test_f006_contained_block_dropped_without_line_lookup(self):
        blocks = [((50, 40, 500, 90), "stem", set()), ((51, 121, 499, 199), "a | b", set()),
                  ((49, 119, 501, 201), "within 2pt", set())]

        def no_lines():
            raise AssertionError("line lookup only for straddling blocks")
        out = pdf._drop_table_blocks(blocks, [TABLE], no_lines)
        self.assertEqual([b[1] for b in out], ["stem"])

    def test_f006_line_inside_other_table_dropped(self):
        t2 = (50, 300, 500, 400)
        blocks = [((50, 100, 500, 200), "x", set())]
        lines = [((50, 100, 500, 118), "keep", set()), ((50, 130, 500, 150), "cell", set())]
        out = pdf._drop_table_blocks(blocks, [TABLE, t2], lambda: lines)
        self.assertEqual([b[1] for b in out], ["keep"])

    def test_no_tables_unchanged(self):
        blocks = [((0, 0, 10, 10), "a", set()), ((0, 20, 10, 30), "b", set())]
        self.assertEqual(pdf._drop_table_blocks(blocks, [], lambda: []), blocks)


if __name__ == "__main__":
    unittest.main()

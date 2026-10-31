import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.abspath(os.path.join(HERE, "..", "..")), "src"))
from exam_engine.core import refcheck  # noqa: E402

P = refcheck.referenced_parts


class Paragraph(unittest.TestCase):
    def test_vi_ref_outside_markers_flagged(self):
        t = "(1) aaa\n(2) bbb\n(3) ccc\n(4) ddd\nÝ chính của đoạn (5) là gì?"
        self.assertEqual(P(t), ["paragraph (5)"])

    def test_vi_ref_inside_markers_clean(self):
        t = "(1) aaa\n(2) bbb\n(3) ccc\n(4) ddd\n(5) eee\nÝ chính của đoạn (5) là gì?"
        self.assertEqual(P(t), [])

    def test_marker_after_quote_counts(self):
        t = "“(1) aaa\n“(2) bbb\nÝ của đoạn (2)?"
        self.assertEqual(P(t), [])

    def test_gap_in_markers_flagged(self):
        t = "(1) a\n(2) b\n(4) d\nNói về đoạn (3)?"
        self.assertEqual(P(t), ["paragraph (3)"])

    def test_bare_vi_ref_with_markers_outside_flagged(self):
        t = "(1) a\n(2) b\nTheo đoạn 3, ý nào đúng?"
        self.assertEqual(P(t), ["paragraph (3)"])

    def test_en_bare_without_markers_clean(self):
        self.assertEqual(P("The word in paragraph 2 means what?"), [])

    def test_vi_parenthesized_without_markers_flagged(self):
        self.assertEqual(P("Ý chính của đoạn (2) là gì?"), ["paragraph (2)"])

    def test_en_parenthesized_ref_outside_markers(self):
        self.assertEqual(P("(1) a\n(2) b\nIn paragraph (3) what?"), ["paragraph (3)"])

    def test_bare_number_in_formula_clean(self):
        self.assertEqual(P("Cho biểu thức f(x) = (5) + 2x, tính f(1)."), [])
        self.assertEqual(P("Chọn (5) trong danh sách sau"), [])

    def test_only_first_of_list_checked_and_deduped(self):
        t = "(1) a\n(2) b\nĐoạn (2), (3) và đoạn (2) nói gì?"
        self.assertEqual(P(t), [])

    def test_other_shapes_clean(self):
        self.assertEqual(P("Đoạn thẳng AB dài 5 cm."), [])

    def test_empty_and_none(self):
        self.assertEqual(P(""), [])
        self.assertEqual(P(None), [])


class Figure(unittest.TestCase):
    def test_shapes_and_function_graph_clean(self):
        for t in ("Hình chữ nhật ABCD", "Hình chóp S.ABCD", "Đồ thị (C) của hàm số y = x",
                  "Cho bảng và biểu đồ", "This is suitable"):
            self.assertEqual(P(t), [], t)

    def test_vi_without_description_flagged(self):
        self.assertEqual(P("Sơ đồ dưới đây mô tả gì?"), ["figure/table"])
        self.assertEqual(P("Quan sát hình 2 và trả lời"), ["figure/table"])
        self.assertEqual(P("Cho bảng số liệu sau"), ["figure/table"])

    def test_with_figure_line_clean(self):
        self.assertEqual(P("Sơ đồ dưới đây?\n[Figure/table: x]"), [])

    def test_with_table_row_clean(self):
        self.assertEqual(P("Sơ đồ dưới đây?\n| a | b |"), [])

    def test_en(self):
        self.assertEqual(P("Look at the table below."), ["figure/table"])
        self.assertEqual(P("The graph above shows"), ["figure/table"])
        self.assertEqual(P("See Figure 1."), ["figure/table"])
        self.assertEqual(P("Look at the table below.\n[Figure/table: x]"), [])

    def test_shared_figure_flag(self):
        self.assertEqual(P("Sơ đồ dưới đây?", shared_figure=True), [])

    def test_both_reported_in_order(self):
        t = "Xem hình bên và đoạn (2)"
        self.assertEqual(P(t), ["paragraph (2)", "figure/table"])


class Grouped(unittest.TestCase):
    def test_figure_on_first_covers_group(self):
        head = "Passage line for 3 questions\nSơ đồ dưới đây"
        texts = [head + "\n[Figure/table: c]\nQ one", head + "\nQ two", head + "\nQ three"]
        self.assertEqual(refcheck.missing_by_question(texts), [[], [], []])

    def test_no_figure_anywhere_flags_all(self):
        head = "Passage line\nSơ đồ dưới đây"
        self.assertEqual(refcheck.missing_by_question([head + "\nA", head + "\nB"]),
                         [["figure/table"], ["figure/table"]])

    def test_unrelated_stays_flagged(self):
        r = refcheck.missing_by_question(["One\nhình bên\n[Figure/table: c]", "Two\nhình bên"])
        self.assertEqual(r, [[], ["figure/table"]])

    def test_empty_and_none(self):
        self.assertEqual(refcheck.missing_by_question([]), [])
        self.assertEqual(refcheck.missing_by_question([None, ""]), [[], []])


if __name__ == "__main__":
    unittest.main()

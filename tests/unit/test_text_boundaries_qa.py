"""Phase 44 QA (TASK-044): adversarial generated page sets for the furniture filter and the
passage-after-option-D split. Synthetic placeholder text only; $0, no network."""
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import api, refine, segment  # noqa: E402
from exam_engine.ingest.adapters import pdf as pdfmod  # noqa: E402

BODY = ["Cau %d. stem %d", "A. one", "B. two", "C. three", "D. four"]


def word(i):  # unique, digit-free token so digit folding never makes two pages look alike
    return "".join(chr(97 + (i // 26 ** k) % 26) for k in range(4))


def page(i, extra_top=(), extra_bottom=(), mid=()):
    """Edge lines are unique per page; header / footer extras sit outside them."""
    body = [BODY[0] % (i, i)] + list(mid) + BODY[1:]
    return (list(extra_top) + ["top " + word(i), "sub " + word(i + 1000)] + body
            + ["pen " + word(i + 2000), "end " + word(i + 3000)] + list(extra_bottom))


def seg(lines):
    _intro, qs, _ok = segment.segment(lines)
    return qs


class TestFurnitureAdversarial(unittest.TestCase):
    def test_44_1_five_page_number_formats_removed_at_page_bottom(self):
        for fmt in ("%d", "Trang %d/22", "- %d -", "%d | Title", "Page %d of 22"):
            pages = [page(i, extra_bottom=[fmt % i]) for i in range(1, 5)]
            out, removed = pdfmod._strip_furniture(pages)
            self.assertEqual(removed, 4, fmt)
            self.assertEqual(out, [page(i) for i in range(1, 5)], fmt)

    def test_44_1_explicit_patterns_removed_even_on_one_page(self):
        for fmt in ("Trang %d/22", "Page %d", "- %d -"):
            out, removed = pdfmod._strip_furniture([page(1, extra_bottom=[fmt % 1])])
            self.assertEqual((removed, out), (1, [page(1)]), fmt)

    def test_44_2_header_on_two_pages_kept_three_removed(self):
        two = [page(i, extra_top=["Placeholder Header"] if i <= 2 else []) for i in range(1, 5)]
        out, removed = pdfmod._strip_furniture(two)
        self.assertEqual((removed, out), (0, two))
        three = [page(i, extra_top=["Placeholder Header"] if i <= 3 else []) for i in range(1, 5)]
        out, removed = pdfmod._strip_furniture(three)
        self.assertEqual(removed, 3)
        self.assertTrue(all("Placeholder Header" not in p for p in out))

    def test_44_2_middle_of_page_number_like_lines_kept(self):
        mid = ["note", "12", "3", "more", "text"]
        pages = [page(i, mid=mid) for i in range(1, 9)]
        out, removed = pdfmod._strip_furniture(pages)
        self.assertEqual((removed, out), (0, pages))

    def test_44_2_question_numbers_and_numeric_options_at_edges_kept(self):
        pages = [["3.", "stem " + word(i), "A. 3", "B. 12", "C. 7", "D. 9"] for i in range(8)]
        out, removed = pdfmod._strip_furniture(pages)
        self.assertEqual((removed, out), (0, pages))
        pages = [["Cau 3.", "A. 3", "B. 12", "C. 3", "D. 12"] for _ in range(8)]
        out, removed = pdfmod._strip_furniture(pages)
        self.assertEqual((removed, out), (0, pages))

    def test_44_2_repeated_real_stem_line_mid_page_kept(self):
        mid = ["Which is correct?"]
        pages = [page(i, mid=mid + ["a%d" % i, "b%d" % i]) for i in range(1, 9)]
        out, removed = pdfmod._strip_furniture(pages)
        self.assertEqual((removed, out), (0, pages))

    def test_44_2_bare_number_page_footer_on_two_page_doc_kept(self):
        pages = [page(i, extra_bottom=["%d" % i]) for i in (1, 2)]
        out, removed = pdfmod._strip_furniture(pages)
        self.assertEqual((removed, out), (0, pages))  # below max(3, half): ambiguous, kept

    def test_44_3_empty_and_single_pages(self):
        self.assertEqual(pdfmod._strip_furniture([]), ([], 0))
        self.assertEqual(pdfmod._strip_furniture([[], [""], ["  "]]), ([[], [""], ["  "]], 0))
        one = [page(1, extra_bottom=["bare text"])]
        self.assertEqual(pdfmod._strip_furniture(one), (one, 0))

    def test_44_3_five_hundred_pages_fast(self):
        pages = [["Head %d" % i, "t " + word(i), "u " + word(i + 1000)]
                 + ["m %s %s" % (word(i), word(j)) for j in range(60)]
                 + ["v " + word(i + 2000), "w " + word(i + 3000), "Trang %d/500" % i]
                 for i in range(500)]
        t0 = time.time()
        out, removed = pdfmod._strip_furniture(pages)
        self.assertLess(time.time() - t0, 5.0)
        self.assertEqual(removed, 1000)
        self.assertTrue(all(len(p) == 66 - 2 for p in out))

    def test_44_3_explicit_page_number_mid_page_is_not_touched(self):
        pages = [page(i, mid=["Trang %d" % i]) for i in range(1, 9)]
        out, removed = pdfmod._strip_furniture(pages)
        self.assertEqual((removed, out), (0, pages))


class TestSegmentAdversarial(unittest.TestCase):
    D = ["Cau 1. s1", "A. a", "B. b", "C. c", "D. d"]
    NEXT = ["Cau 2. s2", "A. a"]

    def test_44_4_intro_variants_move_to_context(self):
        for intro in ("Questions 46-52 Read the passage", "Questions 46 to 52 look",
                      "Dựa vào bảng sau, trả lời câu từ 46 đến 52",
                      "Dựa vào bảng sau, trả lời Questions 46 to 52"):
            qs = seg(self.D + [intro, "tail"] + self.NEXT)
            self.assertEqual(qs[0]["options"][3]["text"], "d", intro)
            self.assertEqual(qs[1].get("context"), intro + "\ntail", intro)

    def test_44_4_d1_vi_en_variants_move_to_context(self):
        for intro in ("Dựa vào thông tin dưới đây, trả lời câu hỏi từ 46 đến 52",
                      "Dựa vào bảng sau, trả lời câu từ 46 đến 52",
                      "Read the passage below and answer the questions",
                      "Questions 46-52 Read the passage"):
            qs = seg(self.D + [intro] + self.NEXT)
            self.assertEqual(qs[0]["options"][3]["text"], "d", intro)
            self.assertEqual(qs[1].get("context"), intro, intro)

    def test_44_4_d2_wrapped_d_line_mentioning_cau_range_stays_in_d(self):
        for extra in ("see câu 3-5 for this", "so Câu 3-5 words wrapped", "refer to Questions 3 to 5"):
            qs = seg(self.D + [extra] + self.NEXT)
            self.assertEqual(qs[0]["options"][3]["text"], "d " + extra, extra)
            self.assertNotIn("context", qs[1])

    def test_44_4_d3_page_n_of_m_removed_on_one_page(self):
        out, removed = pdfmod._strip_furniture([page(1, extra_bottom=["Page 3 of 22"])])
        self.assertEqual((removed, out), (1, [page(1)]))

    def test_44_4_part_heading_after_d_moves_to_context(self):
        qs = seg(self.D + ["PHAN II", "heading text"] + self.NEXT)
        self.assertEqual(qs[0]["options"][3]["text"], "d")
        self.assertEqual(qs[1]["context"], "PHAN II\nheading text")

    def test_44_4_wrapped_stray_and_plain_unnumbered_lines_stay_in_d(self):
        for extra in ("wrapped tail", "7", "Note: a placeholder remark"):
            qs = seg(self.D + [extra] + self.NEXT)
            self.assertEqual(qs[0]["options"][3]["text"], "d " + extra)
            self.assertNotIn("context", qs[1])

    def test_44_4_pending_context_does_not_leak_to_later_question(self):
        lines = (self.D + ["Questions 2-2 intro"] + self.NEXT + ["B. b", "C. c", "D. d"]
                 + ["Cau 3. s3", "A. a", "B. b", "C. c", "D. d"])
        qs = seg(lines)
        self.assertEqual(qs[1]["context"], "Questions 2-2 intro")
        self.assertNotIn("context", qs[2])
        self.assertEqual(qs[1]["options"][3]["text"], "d")

    def test_44_4_second_group_replaces_first_not_stacks(self):
        lines = (self.D + ["Questions 2-2 first"] + self.NEXT + ["D. d", "Questions 3-3 second",
                 "Cau 3. s3", "A. a"])
        qs = seg(lines)
        self.assertEqual(qs[1]["context"], "Questions 2-2 first")
        self.assertEqual(qs[2]["context"], "Questions 3-3 second")

    def test_44_4_share_context_stops_at_group_end(self):
        qs = [dict(n=n, id=str(n), text="s", options=[]) for n in (1, 2, 3, 4, 5)]
        qs[1]["context"] = "Questions 2-3 passage"
        out = api._share_context(qs)
        self.assertEqual([bool(q.get("context")) for q in out], [False, True, True, False, False])

    def test_44_4_trailing_group_line_without_next_question_rejoins_d(self):
        qs = seg(self.D + ["Questions 2-3 dangling"])
        self.assertEqual(qs[0]["options"][3]["text"], "d Questions 2-3 dangling")
        self.assertNotIn("context", qs[0])


class TestPartPatternParity(unittest.TestCase):
    def test_44_5_part_pattern_equals_refine_part_re_on_50_headings(self):
        heads = []
        for w in ("PHẦN", "PHAN", "Phần", "phan", "PHẦNI"):
            for r in ("I", "II", "III", "IV", "V", "VI", "IIII", "1", ""):
                heads.append("%s %s" % (w, r))
        heads += ["PHẦN II. TOÁN", "  PHẦN III", "Phần  IV: x", "PHẦN V\n", "PHẦN 2", "x PHẦN I"]
        self.assertGreaterEqual(len(heads), 50)
        for h in heads:
            self.assertEqual(bool(segment._PART.match(h)), bool(refine.PART_RE.match(h)), repr(h))


if __name__ == "__main__":
    unittest.main()

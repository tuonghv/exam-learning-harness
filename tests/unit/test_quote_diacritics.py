"""TASK-049 / REQ-0047: quote check accepts a quote that lost diacritics (synthetic text only)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))
from exam_engine.pipeline import verifier  # noqa: E402

PASSAGE = "Bạn Lan đi học bằng xe đạp mỗi sáng."
EXACT = "verbatim in passage/question: "
FOLD = "verbatim (diacritics-insensitive)"
EXAM = {"passage": PASSAGE, "questions": []}
Q = {"text": "Con mèo đang ngủ trên ghế.", "options": {"A": "Cái bàn gỗ", "B": "Quả cam"}}


def chk(quote, q=Q, exam=EXAM):
    return verifier._quotes(q, {"evidence": [quote]}, exam)


class QuoteDiacritics(unittest.TestCase):
    def test_exact_unchanged(self):
        r = chk("đi học bằng xe đạp")[0]
        self.assertEqual((r["result"], r["detail"]), ("pass", EXACT + "đi học bằng xe đạp"))

    def test_folded_passage_and_question(self):
        for x in ("Ban Lan di hoc bang xe dap", "con meo dang ngu"):
            r = chk(x)[0]
            self.assertEqual((r["result"], r["detail"]), ("pass", FOLD))

    def test_fabricated_and_other_question_fail(self):
        self.assertEqual(chk("con voi dang chay")[0]["result"], "fail")
        other = {"passage": PASSAGE, "questions": [{"text": "Con chó sủa to"}]}
        self.assertEqual(chk("con cho sua to", exam=other)[0]["result"], "fail")

    def test_case_whitespace(self):
        self.assertEqual(chk("  BAN   LAN\n di HOC ")[0]["result"], "pass")

    def test_short_folded_rejected(self):
        self.assertEqual(chk("mat")[0]["result"], "fail")
        self.assertEqual(chk("meo")[0]["result"], "fail")

    def test_label_strip_on_folded_route(self):
        self.assertEqual(chk("B: qua cam")[0]["result"], "pass")

    def test_empty_null(self):
        self.assertEqual(verifier._quotes(Q, {"evidence": ["", " ", "null"]}, EXAM), [])


class Elision(unittest.TestCase):
    EL = "verbatim (elided, diacritics-insensitive)"

    def test_in_order_pass(self):
        r = chk("Ban Lan di hoc (...) moi sang")[0]
        self.assertEqual((r["result"], r["detail"]), ("pass", self.EL))

    def test_markers_and_edges(self):
        for x in ("ban lan di hoc [...] xe dap", "ban lan di hoc ... xe dap",
                  "ban lan di hoc \u2026 xe dap", "(...) di hoc bang xe dap", "ban lan di hoc bang (...)"):
            self.assertEqual(chk(x)[0]["result"], "pass", x)

    def test_fail_cases(self):
        for x in ("xe dap (...) ban lan di hoc",          # out of order
                  "ban lan di hoc (...) con voi chay",    # fabricated segment
                  "ban (...) lan (...) xe",               # only short segments
                  "(...)", "...", "\u2026"):             # elision only
            self.assertEqual(chk(x)[0]["result"], "fail", x)

    def test_short_segment_dropped(self):
        self.assertEqual(chk("ban lan di hoc (...) xy")[0]["result"], "pass")

    def test_min8_and_overlap_and_repeat(self):
        # mutation-found gaps: segments of 4-7 chars only, overlapping segments, a segment needed twice
        for x in ("lan di (...) xe dap",
                  "ban lan di hoc bang (...) hoc bang xe dap",
                  "xe dap moi (...) xe dap moi"):
            self.assertEqual(chk(x)[0]["result"], "fail", x)


if __name__ == "__main__":
    unittest.main()

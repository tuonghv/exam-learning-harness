"""TASK-114 (phase 114, Fix-F ingest): option-less heading, upper-case group intro, carried passage
kept by the window, failed backward re-run keeps the first pass. Tier 0: synthetic text, fake llm."""
import json
import os
import sys
import unittest
from collections import namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))

from exam_engine.ingest import refine, segment  # noqa: E402

C = namedtuple("C", "ok text cost_usd cls reason duration_s")
ABCD = {"A": "a", "B": "b", "C": "c", "D": "d"}
ABCD_LINES = ["A. a", "B. b", "C. c", "D. d"]
# literal snapshot of segment.GROUP_RE at HEAD before TASK-114 (phase-108: api.py uses it)
GROUP_RE_PATTERN = (r'(?:Questions?|[Cc]âu(?:\s*hỏi)?)\s*(?:từ\s*)?(\d+)(?:\s*(?:-|–|đến|to)\s*'
                    r'(?:[Cc]âu\s*)?(\d+)|\s+and\s+(\d+)|((?:\s*,\s*\d+)+))')
GROUP_RE_FLAGS = 32


def doc_of(n_pages):
    return {"source": {"name": "x.pdf"}, "warnings": [], "meta": {},
            "pages": [{"n": i, "blocks": []} for i in range(1, n_pages + 1)]}


def q(i, text, opts=None, **kw):
    d = {"id": str(i), "text": text, "options": opts or {}, "figures": []}
    d.update(kw)
    return d


def seg(lines):
    return segment.segment(lines)


class TestSegment(unittest.TestCase):
    def test_a_optionless_question_keeps_part_heading_out(self):
        _, qs, ok = seg(["Câu 1. Viết đoạn văn", "PHẦN II. ĐỌC HIỂU", "Câu 2. q"] + ABCD_LINES)
        self.assertEqual(qs[0]["text"], "Viết đoạn văn")
        self.assertEqual(qs[1]["context"], "PHẦN II. ĐỌC HIỂU")
        self.assertTrue(ok)

    def test_b_optionless_question_keeps_next_intro_out(self):
        lines = (["Câu 1. Viết", "Câu 2 - 3: Đọc đoạn văn sau", "Para.", "Câu 2. x"] + ABCD_LINES
                 + ["Câu 3. y"] + ABCD_LINES)
        _, qs, _ = seg(lines)
        self.assertEqual(qs[1]["context"], "Câu 2 - 3: Đọc đoạn văn sau\nPara.")

    def test_b2_optionless_question_keeps_english_intro_out(self):
        lines = (["Câu 1. Viết", "Questions 2-3", "Read the passage.", "Câu 2. x"] + ABCD_LINES
                 + ["Câu 3. y"] + ABCD_LINES)
        _, qs, _ = seg(lines)
        self.assertEqual(qs[0]["text"], "Viết")
        self.assertTrue(qs[1]["context"].startswith("Questions 2-3"))

    def test_c_read_line_and_far_span_stay_in_stem(self):
        _, qs, _ = seg(["Câu 1.", "Read the text and write a summary.", "Câu 2. q"] + ABCD_LINES)
        self.assertIn("Read the text and write a summary.", qs[0]["text"])
        _, qs, _ = seg(["Câu 1. Viết", "Câu 5 - 7 có liên quan", "Câu 2. q"] + ABCD_LINES)
        self.assertIn("Câu 5 - 7", qs[0]["text"])

    def test_d_heading_at_end_of_input(self):
        _, qs, _ = seg(["Câu 1. Viết", "PHẦN II. X"])
        self.assertEqual(qs[0]["text"], "Viết PHẦN II. X")

    def test_e_uppercase_and_diacritic_less_intro(self):
        self.assertIsNone(segment._q_start("CÂU 31 - 35: ĐỌC ĐOẠN VĂN"))
        self.assertIsNone(segment._q_start("Cau 31 - 35: Doc doan van"))

    def test_f_uppercase_intro_is_context(self):
        lines = (["Câu 1. q"] + ABCD_LINES + ["CÂU 2 - 3: ĐỌC ĐOẠN VĂN", "Para.", "Câu 2. x"] + ABCD_LINES
                 + ["Câu 3. y"] + ABCD_LINES)
        _, qs, ok = seg(lines)
        self.assertEqual(len(qs), 3)
        self.assertTrue(ok)
        self.assertTrue(qs[1]["context"].startswith("CÂU 2 - 3"))

    def test_g_group_re_unchanged(self):
        self.assertEqual(segment.GROUP_RE.pattern, GROUP_RE_PATTERN)
        self.assertEqual(int(segment.GROUP_RE.flags), GROUP_RE_FLAGS)
        self.assertIsNone(segment.GROUP_RE.match("CÂU 31 - 35"))
        # a lower-case lead word is still not an intro
        self.assertIsNone(segment._INTRO.match("read questions 3-5"))


class TestRefine(unittest.TestCase):
    def _llm(self, replies, calls):
        it = iter(replies)

        def llm(prompt, png):
            calls.append(1)
            try:
                return next(it)
            except StopIteration:
                return C(False, "", 0.0, "", "fail", 0.0)
        return llm

    def _window_run(self, window_ctx):
        stem = "Stem thirty one"
        replies = [C(True, json.dumps({"questions": [], "carry": "PASSAGE TEXT LONG ENOUGH"}), 0.0, "", "", 0.0),
                   C(True, json.dumps({"questions": [q(31, stem, {"A": "a", "B": "b"}, cut=True)]}), 0.0, "", "", 0.0),
                   C(True, json.dumps({"questions": [q(31, stem, ABCD, context=window_ctx)]}), 0.0, "", "", 0.0)]
        out = refine.refine(doc_of(3), "1-3", self._llm(replies, []), None, all_pages=True, window=True)
        self.assertNotEqual(out["refined"]["windows"][0]["result"], "fallback")
        return out["refined"]["questions"][0]["context"]

    def test_h_window_keeps_carried_passage(self):
        self.assertEqual(self._window_run("Questions 31-35"), "PASSAGE TEXT LONG ENOUGH\nQuestions 31-35")

    def test_i_window_with_passage_not_duplicated(self):
        s = "PASSAGE TEXT LONG ENOUGH\nQuestions 31-35"
        self.assertEqual(self._window_run(s), s)

    def test_h2_window_empty_context_gets_carried_passage(self):
        self.assertEqual(self._window_run(""), "PASSAGE TEXT LONG ENOUGH")

    def _orphan(self, cost=0.0):
        return C(True, json.dumps({"questions": [], "continues": {"text": "tail"}}), cost, "", "", 0.0)

    def test_j_failed_rerun_keeps_first_pass(self):
        calls = []
        out = refine.refine(doc_of(2), "2", self._llm([self._orphan()], calls), None, all_pages=True, window=True)
        r = out["refined"]
        self.assertEqual(r["pages"], [2])
        self.assertEqual([(o["page"], o["kind"]) for o in r["orphans"]], [(2, "no_owner")])
        self.assertIn("recover_failed", [w["code"] for w in out["warnings"]])
        self.assertEqual(r["calls"], len(calls))

    def test_k_cost_cap_counts_run_totals(self):
        calls = []
        replies = [self._orphan(0.1),
                   C(True, json.dumps({"questions": [q(1, "s", cut=True)]}), 0.95, "", "", 0.0)]
        out = refine.refine(doc_of(3), "2", self._llm(replies, calls), None, max_cost=1.0, all_pages=True, window=True)
        r = out["refined"]
        self.assertEqual((r["calls"], r["cost_usd"]), (2, 1.05))
        self.assertIn("recover_failed", [w["code"] for w in out["warnings"]])

    def test_l_invalid_reply_keeps_first_pass(self):
        calls = []
        bad = C(True, "not json", 0.0, "", "", 0.0)
        out = refine.refine(doc_of(2), "2", self._llm([self._orphan(), bad, bad, bad], calls), None, all_pages=True, window=True)
        self.assertIn("recover_failed", [w["code"] for w in out["warnings"]])
        self.assertEqual(out["refined"]["calls"], len(calls))


if __name__ == "__main__":
    unittest.main()

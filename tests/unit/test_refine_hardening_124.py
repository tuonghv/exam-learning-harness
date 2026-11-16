"""TASK-124 (REQ-0131): refine hardening 124.1-124.5. Mock replies only, synthetic text."""
import json
import os
import sys
import unittest
from collections import namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))

from exam_engine.ingest import refine as r  # noqa: E402

C = namedtuple("C", "ok text cost_usd cls reason duration_s")
ABCD = {"A": "a", "B": "b", "C": "c", "D": "d"}


def doc_of(n):
    return {"source": {"name": "x.pdf"}, "warnings": [], "meta": {},
            "pages": [{"n": i, "blocks": []} for i in range(1, n + 1)]}


def run(replies, spec, n=3, window=False):
    it = iter(replies)
    llm = lambda prompt, png: C(True, json.dumps(next(it)), 0.0, "", "", 0.0)  # noqa: E731
    return r.refine(doc_of(n), spec, llm, None, all_pages=True, window=window)


def tdoc(text):
    return {"pages": [{"n": 1, "blocks": [{"type": "table", "text": text}]}]}


def pq(figures, text="t", options=None):
    return {"page": 1, "text": text, "context": "", "options": options or {}, "figures": figures}


class TestRefineHardening(unittest.TestCase):
    def test_124_1_figures_must_be_strings(self):
        bad = {"questions": [{"id": "1", "text": "t", "figures": [{"d": "x"}]}]}
        self.assertTrue(r.validate_refined(bad))
        self.assertTrue(r.validate_refined({"questions": [], "continues": {"figures": [1]}}))
        r._native_tables(tdoc("a | 1"), [pq([{"d": "x"}])])  # no TypeError

    def test_124_2_data_cell_whole_token(self):
        q = [pq(["bảng"], "Năm 2025", {"A": "13", "B": "45"})]
        r._native_tables(tdoc("1 | 2 | 3 | 4 | 5"), q)
        self.assertEqual(len(q[0]["figures"]), 2)

    def test_124_3_labelless_table_placed(self):
        q = [pq(["bảng số liệu"])]
        self.assertEqual(r._native_tables(tdoc("10 | 20\n30 | 40"), q), [])
        self.assertEqual(len(q[0]["figures"]), 2)

    def test_124_3_guard_two_candidates_warn(self):
        q = [pq(["bảng A"]), pq(["bảng B"])]
        w = r._native_tables(tdoc("10 | 20\n30 | 40"), q)
        self.assertEqual([x["code"] for x in w], ["native_table_unplaced"])
        self.assertEqual([len(x["figures"]) for x in q], [1, 1])

    def test_124_4_no_page_zero_advice(self):
        out = run([{"questions": [], "continues": {"text": "tail"}}], "1", n=1)
        msg = [w["message"] for w in out["warnings"] if w["code"] == "orphan_continuation"][0]
        self.assertNotIn("page(s) 0", msg)

    def test_124_5_order_reason(self):
        q13 = {"id": "13", "text": "stem", "options": {}, "figures": [], "cut": True}
        win = {"questions": [
            {"id": "13", "text": "stem", "options": ABCD, "figures": []},
            {"id": "15", "text": "fifteen", "options": ABCD, "figures": []},
            {"id": "14", "text": "fourteen", "options": ABCD, "figures": []}]}
        out = run([{"questions": [q13]}, win], "1", n=2, window=True)
        by = {x["id"]: x for x in out["refined"]["questions"]}
        self.assertIn("order", by["14"].get("needs_review_why", []))


if __name__ == "__main__":
    unittest.main()

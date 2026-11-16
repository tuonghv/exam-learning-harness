"""TASK-134 (REQ-0141): refine hardening 108-F003/F006/F007/F008/F009. Fake llm only, $0."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exam_engine.ingest import refine  # noqa: E402
from test_ingest_refine import make_doc, blk, Fake, reply, q  # noqa: E402

F4 = {"A": "1", "B": "2", "C": "3", "D": "4"}


def cont(text="", options=None):
    return {"text": text, "options": options or {}, "figures": [], "passage": False, "legacy": False}


def owner(options):
    return [{"id": "7", "text": "Q", "options": dict(options), "context": "", "figures": []}]


class TestReviewFixB134(unittest.TestCase):
    def test_134_1_multiline_numbered_continuation_is_orphan(self):  # 108-F003
        qs = owner({})
        kind = refine._attach(qs, {"open": 0, "page": 4}, 5, cont("13. Tinh\nA. 2"))
        self.assertEqual(kind, "starts_with_number")
        self.assertEqual(qs[0]["orphan_page"], 5)

    def test_134_1_neg_numbered_list_line_is_orphan_by_design(self):
        # designed: a continuation whose first line looks like `2) ...` counts as a numbered question
        # (already so for single-line text); it becomes an orphan, never glued into the owner.
        qs = owner({})
        self.assertEqual(refine._attach(qs, {"open": 0, "page": 4}, 5, cont("2) item\nmore")),
                         "starts_with_number")
        self.assertEqual(qs[0]["text"], "Q")

    def test_134_1_multiline_plain_continuation_still_joins(self):
        qs = owner({})
        self.assertIsNone(refine._attach(qs, {"open": 0, "page": 4}, 5, cont("rest of stem\nand more")))
        self.assertIn("rest of stem", qs[0]["text"])

    def test_134_2_disjoint_options_merge(self):  # 108-F006
        qs = owner({"A": "a", "B": "b"})
        kind = refine._attach(qs, {"open": 0, "page": 4}, 5, cont("", {"C": "c", "D": "d"}))
        self.assertIsNone(kind)
        self.assertEqual(sorted(qs[0]["options"]), ["A", "B", "C", "D"])
        self.assertNotIn("orphan_page", qs[0])

    def test_134_2_overlapping_options_still_flagged(self):
        qs = owner({"A": "a", "B": "b"})
        kind = refine._attach(qs, {"open": 0, "page": 4}, 5, cont("", {"B": "x", "C": "c"}))
        self.assertEqual(kind, "owner_has_options")

    def test_134_3_carry_kept_when_continues_missing(self):  # 108-F007
        out = refine.refine(make_doc(), "1-3", Fake([json.dumps({"questions": [], "carry": "PASSAGE P"}),
                                                     json.dumps({"questions": []}),
                                                     reply(q(3, "Plain page", F4))]), all_pages=True)
        self.assertEqual(out["refined"]["questions"][0]["context"], "PASSAGE P")

    def test_134_4_heading_only_entry_keeps_carry(self):  # 108-F008
        out = refine.refine(make_doc(), "1-2", Fake([
            json.dumps({"questions": [], "carry": "PASSAGE P"}),
            reply(q(1, "PHẦN II"), q(2, "Real question", F4))]))
        qs = out["refined"]["questions"]
        self.assertEqual([x["id"] for x in qs], ["2"])
        self.assertEqual(qs[0]["context"], "PASSAGE P")

    def test_134_5_window_gap_uses_pending_pages_only(self):  # 108-F009
        doc = make_doc()
        doc["pages"] = [
            {"n": 1, "status": "native_text", "blocks": [blk(1, "Cau 5. Alpha beta?\nA. 1\nB. 2\nC. 3\nD. 4")]},
            {"n": 3, "status": "native_text", "blocks": [blk(3, "Cau 20. Gamma delta?\nA. 1\nB. 2")]},
            {"n": 4, "status": "native_text", "blocks": [blk(4, "C. 3\nD. 4")]}]
        out = refine.refine(doc, "1,3-4", Fake([
            reply(q(5, "Alpha beta?", F4)),
            reply(q(20, "Gamma delta?", {"A": "1", "B": "2"})),
            reply(q(20, "Gamma delta?", F4))]), all_pages=True)
        q20 = [x for x in out["refined"]["questions"] if x["id"] == "20"][0]
        self.assertNotIn("gap", q20.get("needs_review_why", ""), q20)


if __name__ == "__main__":
    unittest.main()

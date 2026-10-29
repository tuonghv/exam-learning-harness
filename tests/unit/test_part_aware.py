"""Phase 19 (REQ-0026): part heading split, per-part numbering, Part II/III format checks; $0."""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "..", "src"))
import test_ingest_refine as R  # noqa: E402
from exam_engine.ingest import refine  # noqa: E402
from exam_engine.pipeline import verifier as vf  # noqa: E402

MATH = {"fields": {"Subject": "Mathematics", "Task": "Short Answer"}, "passage": ""}
ENG = {"fields": {"Subject": "English", "Task": "Short Answer"}, "passage": ""}
Q2 = {"id": 1, "text": "Cho f.\na) A\nb) B\nc) C\nd) D", "options": {}}
Q3 = {"id": 1, "text": "Tính khoảng cách.", "options": {}}


def doc0():
    d = R.make_doc()
    d["questions"] = []
    return d


def fmt(q, answer, exam=MATH):
    a = {"id": "1", "answer": answer, "answer_status": "answered", "expr": None,
         "evidence": [], "uncertainty": {"level": "low", "reason": ""}}
    return [c for c in vf.det_checks(q, a, exam) if c["kind"] == "format"]


class SplitPart(unittest.TestCase):
    def test_heading_stripped(self):
        self.assertEqual(refine.split_part("PHẦN II: Thí sinh chọn đúng sai.\nCâu 1. Nội dung"),
                         ("II", "Câu 1. Nội dung"))
        self.assertEqual(refine.split_part("Phần III: x")[0], "III")
        self.assertEqual(refine.split_part("Câu 1. Phần II của bài"), (None, "Câu 1. Phần II của bài"))

    def test_heading_only_item_dropped_and_part_carried(self):
        r = R.reply(R.q(1, "PHẦN II: chọn đúng sai.\nCâu 1. Ý a"), R.q(2, "Câu 2. Ý b"),
                    R.q(3, "PHẦN III: trả lời ngắn."))
        out = refine.refine(doc0(), "1", R.Fake([r]))
        qs = out["refined"]["questions"]
        self.assertEqual([(x["id"], x["part"]) for x in qs], [("1", "II"), ("2", "II")])
        self.assertTrue(qs[0]["text"].startswith("Câu 1."))

    def test_part_carried_across_pages_and_restart_not_gap(self):
        p1 = R.reply(R.q(11, "PHẦN I: x\nCâu 11. a"), R.q(12, "Câu 12. b"))
        p2 = R.reply(R.q(1, "PHẦN II: y\nCâu 1. c"), R.q(2, "Câu 2. d"))
        out = refine.refine(doc0(), "1-2", R.Fake([p1, p2]), min_similarity=0.0)
        self.assertEqual([x["part"] for x in out["refined"]["questions"]], ["I", "I", "II", "II"])
        self.assertFalse(any(x["needs_review"] for x in out["refined"]["questions"]))

    def test_gap_inside_part_still_flagged(self):
        p1 = R.reply(R.q(1, "PHẦN I: x\nCâu 1. a"), R.q(3, "Câu 3. b"))
        out = refine.refine(doc0(), "1", R.Fake([p1]), min_similarity=0.0)
        self.assertEqual([x["needs_review"] for x in out["refined"]["questions"]], [False, True])

    def test_mutation_split_disabled_keeps_heading(self):
        r = R.reply(R.q(1, "PHẦN II: z.\nCâu 1. Ý a"))
        with mock.patch.object(refine, "split_part", lambda t: (None, t)):
            out = refine.refine(doc0(), "1", R.Fake([r]))
        self.assertTrue(out["refined"]["questions"][0]["text"].startswith("PHẦN"))


class FormatChecks(unittest.TestCase):
    def test_part_ii(self):
        self.assertEqual(fmt(Q2, "a-Đúng, b-Sai, c-Đúng, d-Sai")[0]["result"], "pass")
        self.assertEqual(fmt(Q2, "Đ, S, Đ, S")[0]["result"], "pass")
        self.assertEqual(fmt(Q2, "a: true, b: false, c: true, d: false")[0]["result"], "pass")
        self.assertEqual(fmt(Q2, "a-Đúng, b-Sai, c-Đúng")[0]["result"], "fail")
        self.assertEqual(fmt(Q2, "12")[0]["result"], "fail")

    def test_part_iii(self):
        self.assertEqual(fmt(Q3, "3,46")[0]["result"], "pass")
        self.assertEqual(fmt(Q3, "khoảng cách là 7 m")[0]["result"], "pass")
        self.assertEqual(fmt(Q3, "không biết")[0]["result"], "fail")

    def test_other_types_unchanged(self):
        self.assertEqual(fmt(Q3, "không biết", ENG), [])
        mc = {"id": 1, "text": "q", "options": {"A": "1", "B": "2", "C": "3", "D": "4"}}
        self.assertEqual(fmt(mc, "B")[0]["detail"], "single letter A-D")

    def test_mutation_part_format_removed(self):
        with mock.patch.object(vf, "_part_format", lambda q, a, e: None):
            self.assertEqual(fmt(Q3, "không biết"), [])


if __name__ == "__main__":
    unittest.main()

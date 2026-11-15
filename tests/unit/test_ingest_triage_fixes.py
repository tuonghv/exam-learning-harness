"""TASK-108 (REQ-0115): ingest boundary fixes 108.1-108.4. Tier 0, synthetic text, mock replies."""
import json
import os
import sys
import unittest
from collections import namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))

from exam_engine.core import refcheck  # noqa: E402
from exam_engine.ingest import refine, segment  # noqa: E402

C = namedtuple("C", "ok text cost_usd cls reason duration_s")
ABCD = {"A": "a", "B": "b", "C": "c", "D": "d"}
O = ["A. a", "B. b", "C. c", "D. d"]


def _doc(n_pages):
    return {"source": {"name": "x.pdf"}, "warnings": [], "meta": {},
            "pages": [{"n": i, "blocks": []} for i in range(1, n_pages + 1)]}


def _q(i, text, opts=None, **kw):
    return dict({"id": str(i), "text": text, "options": opts or {}, "figures": []}, **kw)


def _run(replies, spec, doc=None, window=False):
    it = iter(replies)
    seen = []

    def llm(prompt, png):
        seen.append(prompt)
        return C(True, json.dumps(next(it)), 0.0, "", "", 0.0)
    out = refine.refine(doc or _doc(3), spec, llm, None, all_pages=True, window=window)
    return out, seen


class TestFix108(unittest.TestCase):
    def test_108_f001_cut_reply_valid(self):
        orig = {"12": {"options": [{"key": "A", "text": "a"}]}}
        part = {"id": "12", "text": "t", "options": {"A": "a", "B": "b"}}
        self.assertEqual(refine.validate_refined({"questions": [dict(part, cut=True)]}, orig), [])
        self.assertEqual(len(refine.validate_refined({"questions": [part]}, orig)), 1)
        doc = _doc(2)
        doc["questions"] = [{"n": 12, "text": "stem", "options": [{"key": k, "text": v} for k, v in ABCD.items()]}]
        replies = [{"questions": [_q(12, "stem", {"A": "a", "B": "b"}, cut=True)]},
                   {"questions": [_q(12, "stem", ABCD)]},
                   {"questions": []}]
        out, seen = _run(replies, "1-2", doc, window=True)
        self.assertEqual(len(seen), 2)  # p1, then window p1-2 (page 2 is covered by it)
        qs = out["refined"]["questions"]
        self.assertEqual([x["id"] for x in qs], ["12"])
        self.assertEqual(qs[0]["options"], ABCD)

    def test_108_f002_range_intro_not_question(self):
        for intro in ("Câu 31-35: Đọc đoạn văn sau", "Câu 31 đến 35: Đọc đoạn văn sau"):
            qs = segment.segment(["Câu 30. x"] + O + [intro, "Câu 31. Hỏi gì"] + O)[1]
            self.assertEqual([x["n"] for x in qs], [30, 31], intro)
            self.assertEqual(qs[1]["context"], intro)
        for stem, n in (("Câu 31. Hỏi", 31), ("Câu 3: 1, 2", 3), ("Câu 3 (0,5 điểm)", 3)):
            self.assertEqual([x["n"] for x in segment.segment([stem] + O)[1]], [n], stem)

    def test_108_f005_intro_den_cau(self):
        self.assertTrue(segment._INTRO.match("Đọc đoạn văn và trả lời câu 31 đến câu 35"))
        self.assertTrue(segment._INTRO.match("Questions 5 and 6 refer to the text"))
        self.assertFalse(segment._INTRO.match("see câu 3-5 in the passage"))
        lines = ["Câu 30. x"] + O + ["Đọc đoạn văn và trả lời câu 31 đến câu 35", "passage line",
                                      "Câu 31. Hỏi"] + O
        qs = segment.segment(lines)[1]
        self.assertEqual(qs[0]["options"][3]["text"], "d")
        self.assertIn("passage line", qs[1]["context"])

    def test_108_f004_unreadable_kept(self):
        out, _ = _run([{"questions": [_q(1, "q", ABCD), _q(2, "", unreadable=True)]}], "1", _doc(3))
        qs = out["refined"]["questions"]
        self.assertEqual([x["id"] for x in qs], ["1", "2"])
        self.assertTrue(qs[1]["unreadable"])
        self.assertTrue(refcheck.incomplete_reasons(qs[1]))

    def test_108_f010_part_word_stem(self):
        for t in ("Phần I của văn bản nêu gì?", "Part II of the passage\nmainly about"):
            self.assertEqual(refine.split_part(t), (None, t))
        for t, body in (("PHẦN II\nbody", "body"), ("PHẦN II. TOÁN\nx", "x"),
                        ("Phần IV: x\ny", "y"), ("PHẦN II TƯ DUY ĐỊNH LƯỢNG\nq", "q")):
            self.assertEqual(refine.split_part(t)[1], body, t)
        self.assertEqual(refine.split_part("PHẦN II\nbody")[0], "II")

    def test_108_f010_real_heading_shapes(self):
        # expected = pre-change result: roman part + text after the heading line when PART_RE matches
        for t in ("PHẦN 1: SỬ DỤNG NGÔN NGỮ\nq", "PHẦN 3. TƯ DUY KHOA HỌC\nq",
                  "Phần 2. Toán học (30 câu).\nq", "PHẦN 2. TOÁN HỌC. Một hình chữ nhật có\nq"):
            m = refine.PART_RE.match(t)
            old = (m.group(1).upper(), t[m.end():].strip()) if m else (None, t)
            self.assertEqual(refine.split_part(t), old, t)


if __name__ == "__main__":
    unittest.main()

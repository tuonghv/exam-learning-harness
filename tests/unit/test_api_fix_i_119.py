"""TASK-119 Fix-I api: cut merge, group restart, mention range, offset note (docs/design/phase-119-*.md)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from exam_engine.ingest import api  # noqa: E402


def _refined(*qs):
    return {"refined": {"questions": list(qs)}}


class CutMerge(unittest.TestCase):
    def test_119_1_union_options_figures_pages(self):
        q = api.refined_questions(_refined(
            {"id": "12", "page": 3, "text": "s", "options": {"A": "a", "B": "b"}, "cut": True},
            {"id": "12", "page": 4, "text": "", "options": {"C": "c", "D": "d"}, "figures": ["f1"]}))[0]
        self.assertEqual(sorted(q["options"]), ["A", "B", "C", "D"])
        self.assertEqual(q["figures"], ["f1"])
        self.assertEqual(q["continued_pages"], [4])

    def test_119_1_full_repeat_second_part_wins(self):
        q = api.refined_questions(_refined(
            {"id": "12", "page": 3, "text": "s", "options": {k: "old" for k in "ABCD"}, "cut": True},
            {"id": "12", "page": 4, "text": "", "options": {k: "new" for k in "ABCD"}}))[0]
        self.assertEqual(q["options"], {k: "new" for k in "ABCD"})


class Share(unittest.TestCase):
    def test_119_2_restart_closes_group(self):
        qs = [{"id": "1", "context": "Questions 1-5: Read the passage.\nPASSAGE A", "text": "a1"}] \
            + [{"id": str(i), "text": "a"} for i in range(2, 6)] + [{"id": str(i), "text": "b"} for i in range(1, 6)]
        out = api._share_context(qs)
        self.assertEqual([q.get("context") or None for q in out[5:]], [None] * 5)
        self.assertTrue(all(q.get("context") for q in out[1:5]))

    def test_119_3_mention_must_cover_carrier(self):
        qs = [{"id": "10", "context": "Questions 10-15: Read.\nPASSAGE", "text": "x"}, {"id": "11", "text": "x"},
              {"id": "12", "context": "Use your answers to questions 3, 4 here.", "text": "x"}] \
            + [{"id": str(i), "text": "x"} for i in (13, 14, 15)]
        out = {q["id"]: q for q in api._share_context(qs)}
        for i in ("13", "14", "15"):
            self.assertTrue(out[i]["context"].startswith("Questions"))
        self.assertIsNone(out["10"].get("structure"))
        self.assertEqual(out["12"]["structure"], ["instruction_override"])

    def _ids(self, qs):
        return {q["id"]: q for q in api._share_context(qs)}

    def test_119_3_guard_false_carrier_outside_span(self):
        # real exam: a passage line read as question "1" carries the group line of 46-52
        qs = [{"id": "45", "text": "x"},
              {"id": "1", "context": "Questions 46-52: Read.\nPASSAGE", "text": "x"}] \
            + [{"id": str(i), "text": "x"} for i in (2, 3, 46, 47, 48, 49, 50, 51, 52)]
        out = self._ids(qs)
        for i in range(47, 53):
            self.assertTrue((out[str(i)].get("context") or "").startswith("Questions 46-52"), i)

    def test_119_2_guard_stray_low_id_inside_group(self):
        qs = [{"id": "67", "context": "Dựa vào bài đọc, trả lời câu từ 67 đến 69\nPASSAGE", "text": "x"},
              {"id": "1", "text": "x"}, {"id": "68", "text": "x"}, {"id": "69", "text": "x"}]
        out = self._ids(qs)
        for i in ("68", "69"):
            self.assertIn("PASSAGE", out[i].get("context") or "", i)
        self.assertNotIn("range_overrun", out["67"].get("structure") or [])

    def test_119_2_guard_dhqg_year_line_carrier(self):
        qs = [{"id": "1991", "context": "Dựa vào câu từ 109 đến 111\nP", "text": "x"}] \
            + [{"id": str(i), "text": "x"} for i in (109, 110, 111)]
        out = self._ids(qs)
        for i in ("110", "111"):
            self.assertIn("P", out[i].get("context") or "", i)


class OffsetNote(unittest.TestCase):
    def _doc(self, ids):
        o = {k: k.lower() for k in "ABCD"}
        return {"meta": {k: "x" for k in api.REQUIRED}, "source": {"name": "t"},
                "refined": {"questions": [{"id": str(i), "text": "t", "options": o} for i in ids]}}

    def _note(self, ids, spec=None):
        return [ln for ln in api._from_refined(self._doc(ids), spec, {}).splitlines() if "numbered" in ln]

    def test_119_4_gap_prints_mapping(self):
        note = self._note((61, 62, 81), "61-62,81")
        self.assertEqual(len(note), 1)
        self.assertIn("printed numbers: 1=61, 2=62, 3=81.", note[0])
        self.assertNotIn("N + 60", note[0])

    def test_119_4_gap_without_spec(self):
        self.assertIn("printed numbers: 1=1, 2=3, 3=5.", self._note((1, 3, 5))[0])

    def test_119_4_consecutive_keeps_offset(self):
        note = self._note((61, 62, 63))
        self.assertEqual(len(note), 1)
        self.assertIn("N + 60", note[0])
        self.assertEqual(self._note((1, 2, 3)), [])


if __name__ == "__main__":
    unittest.main()

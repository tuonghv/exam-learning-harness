"""TASK-135 (REQ-0142): metrics/report_kinds/review hardening 109-F003/F005/F006, 111-F001/F002/F008/F009. $0."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from exam_engine.pipeline import metrics, report_kinds, review  # noqa: E402


def _q(i, ans, key_ok):
    return {"id": i, "answer": ans, "key_ok": key_ok, "reason": None, "status": "PASS"}


class FixC(unittest.TestCase):
    def test_135_1_proxy_flag_on_qa_flip(self):  # 109-F003
        ma = {"questions": [_q("1", "A", True), _q("2", "A", None)]}
        mb = {"questions": [_q("1", "A", True), _q("2", "B", None)]}
        qa = {"2": {"answer": "B", "flawed": False}}
        d = metrics.classify(ma, mb, qa)
        self.assertTrue(d["proxy"])
        self.assertFalse(metrics.classify(ma, ma, qa)["proxy"])
        flat = {k: 0 for k in metrics._POOL}
        flat.update(fixed=10, basis="key", proxy=True, n=10)
        p = metrics.pool([flat])
        self.assertTrue(p["proxy"])
        self.assertEqual(metrics.verdict(p)[0], "better (proxy)")
        flat["proxy"] = False
        self.assertEqual(metrics.verdict(metrics.pool([flat]))[0], "better")

    def test_135_2_causes_text_skips_row_without_primary(self):  # 109-F005
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "e.tsv")
            with open(p, "w", encoding="utf-8") as f:
                f.write("id\tprimary\toutcome\n1\tocr\twrong\n2\n")
            self.assertIn("ocr=1", metrics.causes_text([p]))

    def test_135_3_backfill_skips_unreadable_result(self):  # 109-F006
        with tempfile.TemporaryDirectory() as t:
            dirs = []
            for n, body in (("a", '{"questions": ['), ("b", "[]")):
                d = os.path.join(t, n)
                os.makedirs(d)
                with open(os.path.join(d, "result.json"), "w", encoding="utf-8") as f:
                    f.write(body)
                dirs.append(d)
            self.assertEqual(metrics.backfill(dirs, os.path.join(t, "h.jsonl")), (0, 2))

    def test_135_4_superseded_note_null(self):  # 111-F001
        self.assertEqual(report_kinds.superseded_note("a.md", None, [{"glob": "*", "note": None}]), "")

    def test_135_5_has_text_single_letter_run_resets(self):  # 111-F002
        self.assertTrue(report_kinds._has_text("Stem\nA. Fleming found\nmore stem\nA. x\nB. y\nĐáp án: A"))

    def test_135_6_guard_prefixes_qa_lines(self):  # 111-F008
        for ln in ("QA: B conf high | differs | x", "Answer changed: A -> B"):
            self.assertNotEqual(review._guard(ln), ln)
        self.assertEqual(review._guard("plain"), "plain")

    def test_135_7_reserved_subject_names(self):  # 111-F009
        for bad in ("INDEX", "index", "Improvements", "x.new", "x.OLD"):
            with self.assertRaises(ValueError, msg=bad):
                review._check_name("subject", bad)
        self.assertEqual(review._check_name("subject", "math"), "math")
        self.assertEqual(review._check_name("exam-id", "INDEX"), "INDEX")


if __name__ == "__main__":
    unittest.main()

"""TASK-056 (56.1-56.3, 56.6): metrics catalogue, history line, backfill. No paid call, temp dirs only."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import metrics  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "metrics")


def load(name):
    with open(os.path.join(FIX, name, "result.json"), encoding="utf-8") as f:
        res = json.load(f)
    return res, metrics.load_log(os.path.join(FIX, name, "run.log"))


class CountsTest(unittest.TestCase):
    def setUp(self):
        res, log = load("mixed")
        self.m = metrics.compute(res, log)

    def test_counts_match_hand_count(self):
        c = self.m["counts"]
        self.assertEqual(self.m["n"], 8)
        self.assertEqual((c["answered"], c["declined"], c["declined_missing_text"]), (4, 2, 1))
        self.assertEqual((c["malformed"], c["not_solved"], c["qa_unavailable"]), (1, 1, 1))
        self.assertEqual((c["pass"], c["fail"], c["uncertain"]), (1, 0, 7))
        self.assertEqual(c["uncertain_by_reason"], {
            "no_independent_check": 1, "reviewer_disagrees": 1, "solver_declined": 2,
            "malformed_output": 1, "check_failed": 1, "not_solved": 1})
        self.assertIsNone(c["needs_review"])

    def test_rates(self):
        r = self.m["rates"]
        self.assertEqual(r["retry_rate"], 2 / 8)
        self.assertEqual(r["qa_disagree"], 1 / 4)
        self.assertEqual(r["low_conf"], 2 / 4)

    def test_cost_from_log(self):
        c = self.m["cost"]
        self.assertEqual((c["calls"], c["cost_usd"]), (5, 0.5))
        self.assertEqual(c["llm_s"], 150.5)
        self.assertEqual((c["prompt_kb"], c["answer_kb"]), (8.0, 6.0))
        self.assertIsNone(c["tokens"])
        self.assertIsNone(c["wall_s"])
        self.assertEqual(c["cost_per_answered"], 0.125)

    def test_no_accuracy_without_sources(self):
        self.assertEqual(self.m["accuracy"], {"key": None, "qa": None})

    def test_missing_log_is_null_not_zero(self):
        res, _ = load("mixed")
        c = metrics.compute(res, None)["cost"]
        self.assertIsNone(c["llm_s"])
        self.assertIsNone(c["prompt_kb"])
        self.assertEqual(c["calls"], 5)

    def test_per_question_rows(self):
        rows = {q["id"]: q for q in self.m["questions"]}
        self.assertEqual(rows["3"]["reason"], "reviewer_disagrees")
        self.assertEqual(rows["2"]["attempts"], 2)
        self.assertEqual(self.m["by_subject"]["Math"]["n"], 8)
        self.assertEqual(self.m["by_evidence"]["code oracle"]["n"], 1)


class AccuracyTest(unittest.TestCase):
    def test_key_only_over_keyed(self):
        res, log = load("keyed")
        k = metrics.compute(res, log)["accuracy"]["key"]
        self.assertEqual((k["correct"], k["keyed"]), (2, 3))
        self.assertEqual((k["points"], k["max_points"]), (2, 3))
        self.assertAlmostEqual(k["rate"], 2 / 3)

    def test_key_map_overrides_score(self):
        res, log = load("mixed")
        k = metrics.compute(res, log, key={"1": "A", "2": "C"})["accuracy"]["key"]
        self.assertEqual((k["correct"], k["keyed"]), (1, 2))

    def test_qa_agree_excludes_apart(self):
        res, log = load("mixed")
        qa = {"1": {"answer": "A", "flawed": False}, "2": {"answer": "C", "flawed": False},
              "3": {"answer": "C", "flawed": False}, "4": {"answer": "B", "flawed": False},
              "5": {"answer": "A", "flawed": True}, "6": {"answer": "-", "flawed": False},
              "7": {"answer": "D", "flawed": False}, "99": {"answer": "A", "flawed": False}}
        q = metrics.compute(res, log, qa=qa)["accuracy"]["qa"]
        self.assertEqual((q["agrees"], q["differs"]), (3, 1))
        self.assertEqual(q["agree_rate"], 3 / 4)
        self.assertEqual((q["flawed"], q["qa_only"], q["unresolved"], q["engine_nonletter"]), (1, 1, 1, 0))
        self.assertEqual(q["unmatched"], 1)

    def test_qa_ids_not_mapping_gives_null(self):
        res, log = load("mixed")
        m = metrics.compute(res, log, qa={"50": {"answer": "A", "flawed": False}})
        self.assertIsNone(m["accuracy"]["qa"])
        self.assertEqual(m["qa_unmatched"], 1)

    def test_group_kind_from_exam(self):
        res, log = load("mixed")
        exam = {"questions": [
            {"id": i, "text": t, "stem": t, "passage": p}
            for i, t, p in [(1, "q one", ""), (2, "q two", "P"), (3, "q three", "P"),
                            (4, "q four", ""), (5, "q five", ""), (6, "q six", ""),
                            (7, "tính kết quả câu trên", ""), (8, "q eight", "")]]}
        m = metrics.compute(res, log, exam=exam)
        kinds = {q["id"]: q["group_kind"] for q in m["questions"]}
        self.assertEqual(kinds["1"], "independent")
        self.assertEqual(kinds["2"], "passage")
        self.assertEqual(kinds["7"], "dependent")
        self.assertEqual(sum(v["n"] for v in m["by_group_kind"].values()), 8)

    def test_no_exam_no_group_kind(self):
        res, log = load("mixed")
        m = metrics.compute(res, log)
        self.assertEqual(m["by_group_kind"], {})
        self.assertIsNone(m["questions"][0]["group_kind"])


class LegacyStoppedTest(unittest.TestCase):
    def test_legacy_stopped_computes(self):
        res, log = load("stopped")
        m = metrics.compute(res, log)
        self.assertEqual(m["n"], 3)
        self.assertEqual((m["counts"]["answered"], m["counts"]["not_solved"]), (1, 2))
        self.assertEqual(m["rates"]["retry_rate"], 0.0)
        self.assertEqual(m["accuracy"]["key"], None)
        self.assertEqual(m["stopped"], "max_cost_usd")

    def test_empty_result(self):
        m = metrics.compute({"questions": [], "run": {}})
        self.assertEqual(m["n"], 0)
        self.assertIsNone(m["rates"]["retry_rate"])
        self.assertIsNone(m["cost"]["cost_usd"])


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_history_line_fields(self):
        res, log = load("keyed")
        m = metrics.compute(res, log)
        meta = {"run_id": "r1", "ts": "2026-01-01T00:00:00Z", "exam_id": "x", "exam_sha256": "ab",
                "git": {"commit": "c", "dirty": False}, "result_path": "/r/result.json", "source": "solve"}
        line = metrics.history_line(res, m, meta)
        for k in ("v", "run_id", "ts", "exam_id", "exam_sha256", "subject", "git", "prompt", "model", "llm",
                  "config", "result_path", "metrics", "source"):
            self.assertIn(k, line)
        self.assertEqual(line["v"], 1)
        self.assertEqual(line["subject"], "Science")
        self.assertEqual(line["prompt"], {"channel": "release", "version": "v1.0.0"})
        self.assertEqual(set(line["config"]), {"max_attempts", "timeout_s", "max_cost_usd", "lang"})
        self.assertNotIn("questions", line["metrics"])
        json.dumps(line)

    def test_missing_meta_is_null(self):
        res, log = load("stopped")
        line = metrics.history_line(res, metrics.compute(res, log), {})
        self.assertIsNone(line["git"])
        self.assertIsNone(line["exam_sha256"])
        self.assertIsNone(line["prompt"])
        self.assertTrue(line["ts"].endswith("Z"))

    def test_append_one_line_and_read(self):
        p = os.path.join(self.tmp, "sub", "h.jsonl")
        metrics.append(p, {"a": 1})
        metrics.append(p, {"a": 2})
        with open(p, encoding="utf-8") as f:
            self.assertEqual(len(f.read().splitlines()), 2)
        lines, bad = metrics.read_history(p)
        self.assertEqual((len(lines), bad), (2, 0))

    def test_read_history_skips_malformed(self):
        p = os.path.join(self.tmp, "h.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write('{"a": 1}\nnot json\n\n{"a": 2}\n')
        lines, bad = metrics.read_history(p)
        self.assertEqual((len(lines), bad), (2, 1))
        self.assertEqual(metrics.read_history(os.path.join(self.tmp, "none")), ([], 0))

    def test_backfill_idempotent(self):
        dirs = [os.path.join(FIX, n) for n in ("mixed", "keyed", "stopped", "nolog")]
        os.makedirs(os.path.join(self.tmp, "nolog"))
        shutil.copy(os.path.join(FIX, "mixed", "result.json"), os.path.join(self.tmp, "nolog"))
        dirs[3] = os.path.join(self.tmp, "nolog")
        hist = os.path.join(self.tmp, "h.jsonl")
        added, skipped = metrics.backfill(dirs + [self.tmp], hist)
        self.assertEqual((added, skipped), (4, 0))
        added, skipped = metrics.backfill(dirs, hist)
        self.assertEqual((added, skipped), (0, 4))
        lines, _ = metrics.read_history(hist)
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(ln["source"] == "backfill" and ln["git"] is None for ln in lines))
        nolog = [ln for ln in lines if ln["result_path"].startswith(self.tmp)][0]
        self.assertIsNone(nolog["metrics"]["cost"]["llm_s"])

    def test_backfill_exam_sha(self):
        exam = os.path.join(self.tmp, "e.md")
        with open(exam, "w", encoding="utf-8") as f:
            f.write("text")
        hist = os.path.join(self.tmp, "h.jsonl")
        d = os.path.join(FIX, "keyed")
        metrics.backfill([d], hist, exam_path=exam)
        lines, _ = metrics.read_history(hist)
        self.assertEqual(len(lines[0]["exam_sha256"]), 64)
        self.assertEqual(lines[0]["exam_id"], "e")
        self.assertEqual(metrics.backfill([d], hist, exam_path=exam), (0, 1))
        self.assertEqual(metrics.backfill([d], hist), (1, 0))  # other sha (null) -> new line


if __name__ == "__main__":
    unittest.main()

"""TASK-056 (56.4, 56.5): run-stats CLI and the metrics block. Temp dirs only, mock LLM, no paid call."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import report_kinds as rk  # noqa: E402
from exam_engine.pipeline import metrics  # noqa: E402

INPUT_001 = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(HERE, "fixtures", "mock_english_001.json")


def q(i, ans, ok=None, status="PASS"):
    pts = {"points": None, "max": None} if ok is None else {"points": 1 if ok else 0, "max": 1}
    return {"id": str(i), "answer": ans, "verification_status": status, "score": pts,
            "uncertainty": {"level": "low", "reason": ""}}


def result(qs):
    return {"exam": {"subject": "Science"}, "questions": qs,
            "run": {"llm": "claude-p", "model": "m", "calls": 1, "cost_usd": 0.1, "stopped": None,
                    "prompt": {"channel": "release", "version": "v1"}}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="run_stats_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.hist = os.path.join(self.tmp, "h.jsonl")

    def run_dir(self, name, qs):
        d = os.path.join(self.tmp, name)
        os.makedirs(d)
        with open(os.path.join(d, "result.json"), "w", encoding="utf-8") as f:
            json.dump(result(qs), f)
        return d

    def rs(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.run_stats_main(list(args) + ["--history", self.hist])
        return code, out.getvalue(), err.getvalue()


class CompareTest(Base):
    def test_fixed_regressed_vs_key_and_noise(self):
        a = self.run_dir("a", [q(1, "A", False), q(2, "B", True), q(3, "C", True)])
        b = self.run_dir("b", [q(1, "B", True), q(2, "C", False), q(3, "C", True)])
        code, out, _ = self.rs("compare", a, b)
        self.assertIn("fixed (vs key): 1", out)
        self.assertIn("regressed (vs key): 2", out)
        self.assertIn("unchanged: 1", out)
        self.assertIn("insufficient (flips 2<6)", out)  # 64.5
        self.assertIn("n=3 flips=2", out)
        self.assertEqual(code, 0)

    def test_regression_signal_exits_1(self):
        a = self.run_dir("a", [q(i, "A", True) for i in range(1, 7)])
        b = self.run_dir("b", [q(i, "B", False) for i in range(1, 7)])
        code, out, _ = self.rs("compare", a, b)
        self.assertIn("signal (regressed)", out)
        self.assertEqual(code, 1)

    def test_vs_qa_when_no_key(self):
        a = self.run_dir("a", [q(1, "A"), q(2, "B"), q(3, "C")])
        b = self.run_dir("b", [q(1, "B"), q(2, "B"), q(3, "D")])
        pack = os.path.join(self.tmp, "qa.md")
        with open(pack, "w", encoding="utf-8") as f:
            f.write("| n | QA | conf | note |\n| --- | --- | --- | --- |\n| 1 | B | high | x |\n| 2 | B | high | x |\n")
        code, out, _ = self.rs("compare", a, b, "--review-pack", pack)
        self.assertIn("fixed (vs QA): 1", out)
        self.assertIn("changed (answer differs): 3", out)
        self.assertEqual(code, 0)

    def test_different_exam_sha_exit_2(self):
        a = self.run_dir("a", [q(1, "A", True)])
        b = self.run_dir("b", [q(1, "A", True)])
        for d, sha in ((a, "1" * 64), (b, "2" * 64)):
            metrics.append(self.hist, {"run_id": d, "result_path": os.path.join(d, "result.json"),
                                       "exam_sha256": sha})
        code, _out, err = self.rs("compare", a, b)
        self.assertEqual(code, 2)
        self.assertIn("different exam", err)

    def test_noise_rule_boundaries(self):
        self.assertTrue(metrics.noise(3, 1))
        self.assertTrue(metrics.noise(0, 0))
        self.assertFalse(metrics.noise(6, 0))
        self.assertTrue(metrics.noise(3, 0))  # F+R < 4
        self.assertTrue(metrics.noise(0, 4))  # 64.4: exact p = .125


class HistoryTest(Base):
    def test_backfill_idempotent_and_stats_trend(self):
        a = self.run_dir("a", [q(1, "A", True), q(2, "B", False)])
        b = self.run_dir("b", [q(1, "A", True), q(2, "B", True)])
        self.assertIn("added 2 skipped 0", self.rs("backfill", a, b)[1])
        self.assertIn("added 0 skipped 2", self.rs("backfill", a, b)[1])
        self.assertEqual(len(metrics.read_history(self.hist)[0]), 2)
        out = self.rs("trend")[1]
        self.assertEqual(len(out.strip().splitlines()), 3)  # 2 runs + noise band (same prompt/model, no commit)

    def test_trend_marks_repeats_and_band(self):
        for i, ok in enumerate((True, False)):
            d = self.run_dir("r%d" % i, [q(1, "A", ok)])
            with open(os.path.join(d, "result.json"), encoding="utf-8") as f:
                m = metrics.compute(json.load(f))
            res = result([])
            metrics.append(self.hist, metrics.history_line(
                res, m, {"ts": "2026-01-0%dT00:00:00Z" % (i + 1), "git": {"commit": "abcdef012", "dirty": False}}))
        code, out, _ = self.rs("trend")
        self.assertEqual(sum(1 for ln in out.splitlines() if ln.endswith(" repeat")), 2)
        self.assertIn("noise band (2 repeats", out)
        self.assertEqual(code, 0)

    def test_stats_json_and_block(self):
        a = self.run_dir("a", [q(1, "A", True), q(2, "B", False)])
        code, out, _ = self.rs("stats", a, "--json")
        self.assertEqual(json.loads(out)["accuracy"]["key"]["correct"], 1)
        text = self.rs("stats", a)[1].splitlines()
        self.assertEqual(len(text), 3)
        self.assertTrue(text[0].startswith("metrics: answered 2/2 declined 0 malformed 0 retry"))
        self.assertEqual(text[1], "accuracy: key 1/2")
        self.assertTrue(text[2].startswith("cost: calls 1 $0.1000 llm_s -"))

    def test_usage_errors_exit_2(self):
        self.assertEqual(self.rs("stats")[0], 2)
        self.assertEqual(self.rs("stats", os.path.join(self.tmp, "nope"))[0], 2)
        self.assertEqual(self.rs("compare", "x")[0], 2)


class ProxyLabelTest(Base):
    """56.5: QA agreement is a proxy and must never read as accuracy."""
    def pack(self):
        pack = os.path.join(self.tmp, "qa.md")
        with open(pack, "w", encoding="utf-8") as f:
            f.write("| n | QA | conf | note |\n| --- | --- | --- | --- |\n| 1 | A | high | x |\n| 2 | C | high | x |\n")
        return pack

    def test_56_5_qa_only_block_says_proxy_and_no_key_accuracy(self):
        d = self.run_dir("a", [q(1, "A"), q(2, "B")])
        code, out, _ = self.rs("stats", d, "--review-pack", self.pack())
        acc = [ln for ln in out.splitlines() if ln.startswith("accuracy:")][0]
        self.assertEqual(acc, "accuracy: qa agree 1/2 (proxy)")
        self.assertNotIn("key", acc)
        code, js, _ = self.rs("stats", d, "--review-pack", self.pack(), "--json")
        m = json.loads(js)
        self.assertIsNone(m["accuracy"]["key"])
        self.assertEqual(m["accuracy"]["qa"]["agrees"], 1)

    def test_56_5_key_and_qa_shown_apart(self):
        d = self.run_dir("a", [q(1, "A", ok=True), q(2, "B", ok=False)])
        _c, out, _ = self.rs("stats", d, "--review-pack", self.pack())
        acc = [ln for ln in out.splitlines() if ln.startswith("accuracy:")][0]
        self.assertEqual(acc, "accuracy: key 1/2 | qa agree 1/2 (proxy)")

    def test_56_5_qa_never_creates_key_accuracy(self):
        d = self.run_dir("a", [q(1, "A"), q(2, "B")])
        _c, js, _ = self.rs("stats", d, "--review-pack", self.pack(), "--json")
        self.assertIsNone(json.loads(js)["accuracy"]["key"])
        self.assertNotIn("key", metrics.block(json.loads(js))[1])


class SolveTest(Base):
    def solve(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.solve_main([INPUT_001, "--mock", MOCK, "--out", os.path.join(self.tmp, "o"), "--no-pdf"]
                                  + list(extra))
        return code, out.getvalue()

    def test_mock_solve_prints_block_and_report_section_without_history(self):
        cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, cwd)
        _code, out = self.solve()
        lines = out.splitlines()
        i = [n for n, ln in enumerate(lines) if ln.startswith("pass=")][0]
        tail = [ln for ln in lines[i + 1:] if ln.startswith(("metrics:", "accuracy:", "cost:"))]
        self.assertEqual(len(tail), 3)
        with open(rk.find(os.path.join(self.tmp, "o"), "solution-report"), encoding="utf-8") as f:
            self.assertIn("\n## Metrics\n", f.read())
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "results")))
        self.assertFalse(os.path.exists(self.hist))

    def test_history_flag_appends_one_line(self):
        self.solve("--history", self.hist)
        lines, bad = metrics.read_history(self.hist)
        self.assertEqual((len(lines), bad), (1, 0))
        self.assertEqual(lines[0]["source"], "solve")
        self.assertEqual(lines[0]["llm"], "mock")
        self.assertTrue(lines[0]["exam_sha256"])


if __name__ == "__main__":
    unittest.main()

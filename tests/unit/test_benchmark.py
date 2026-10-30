"""REQ-0009: benchmark loops the engine over input/key pairs; fake llm only, $0."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli, engine  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.pipeline import benchmark  # noqa: E402

SRC = os.path.join(ROOT, "examples", "english")
ANSWER = json.load(open(os.path.join(HERE, "fixtures", "mock_english_001.json")))
SOLVE, QA = ANSWER[0], ANSWER[1]
WRONG = SOLVE.replace('"answer": "A"', '"answer": "B"')


class Fake:
    def __init__(self, solve=SOLVE, cost=0.01):
        self.solve, self.cost, self.prompts = solve, cost, []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        qa = "reviews" in prompt[:3000]
        return claude.Call(True, QA if qa else self.solve, self.cost, "", "", 0.0)


class Bench(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name
        for sub in ("english", "english2"):
            os.makedirs(os.path.join(self.root, "in", sub))
            os.makedirs(os.path.join(self.root, "keys", sub))
            shutil.copy(os.path.join(SRC, "input-001.md"), os.path.join(self.root, "in", sub, "input-001.md"))
            shutil.copy(os.path.join(SRC, "expected-001.md"), os.path.join(self.root, "keys", sub, "expected-001.md"))
        self.items = benchmark.discover(os.path.join(self.root, "in"), os.path.join(self.root, "keys"))
        self.cfg = {"max_attempts": 2, "max_cost_usd": 1.0, "timeout": 5, "model": "m",
                    "llm_name": "mock", "pdf": False}

    def test_discover_pairs_only(self):
        os.remove(os.path.join(self.root, "keys", "english2", "expected-001.md"))
        its = benchmark.discover(os.path.join(self.root, "in"), os.path.join(self.root, "keys"))
        self.assertEqual([(s, n) for s, n, _, _ in its], [("english", "001")])
        self.assertEqual(len(benchmark.discover(os.path.join(self.root, "in"),
                                                os.path.join(self.root, "keys"), "english2")), 0)

    def test_pass_and_fail_counted_per_subject_and_key_never_in_prompt(self):
        llm = Fake()
        rows = benchmark.run_all(self.items, os.path.join(self.root, "o"), self.cfg, llm, 5.0)
        sm = benchmark.summarize(rows, {"date": "d", "model": "m", "prompt": "p"})
        self.assertEqual(sm["totals"]["items"], 2)
        self.assertEqual(sm["totals"]["pass"], 2)
        self.assertEqual(rows[0]["questions"][0]["basis"], "key match")
        self.assertTrue(llm.prompts)
        for p in llm.prompts:
            self.assertNotIn("Correct answer: A. have", p)
        rows = benchmark.run_all(self.items, os.path.join(self.root, "o2"), self.cfg, Fake(WRONG), 5.0)
        sm = benchmark.summarize(rows, {"date": "d", "model": "m", "prompt": "p"})
        self.assertEqual((sm["totals"]["pass"], sm["totals"]["fail"]), (0, 2))
        self.assertIn("## Failures", benchmark.report_md(sm))

    def test_budget_stops_remaining_items(self):
        rows = benchmark.run_all(self.items, os.path.join(self.root, "o"), self.cfg,
                                 Fake(cost=0.6), 0.5)
        self.assertEqual([("skipped" in r) for r in rows], [False, True])
        sm = benchmark.summarize(rows, {"date": "d", "model": "m", "prompt": "p"})
        self.assertEqual(sm["skipped"], [["english2", "001", "budget_reached"]])

    def test_regression_flagged(self):
        meta = {"date": "d", "model": "m", "prompt": "p"}
        good = benchmark.summarize(benchmark.run_all(self.items, os.path.join(self.root, "a"),
                                                     self.cfg, Fake(), 5.0), meta)
        bad = benchmark.summarize(benchmark.run_all(self.items, os.path.join(self.root, "b"),
                                                    self.cfg, Fake(WRONG), 5.0), meta)
        self.assertEqual(benchmark.regression(good, bad), ["english", "english2"])
        self.assertEqual(benchmark.regression(bad, good), [])

    def run_cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["benchmark"] + args)
        return code, out.getvalue(), err.getvalue()

    def test_cli_modes(self):
        i, k = os.path.join(self.root, "in"), os.path.join(self.root, "keys")
        with mock.patch.object(claude, "run_claude", side_effect=AssertionError("real")):
            code, out, _ = self.run_cli(["--inputs", i, "--keys", k, "--dry-run"])
            self.assertEqual(code, 0)
            self.assertIn("2 items, calls <= 10", out)
            code, _, err = self.run_cli(["--inputs", i, "--keys", k, "--out", self.root])
            self.assertEqual(code, 2)
            self.assertIn("never defaults to real", err)
            mf = os.path.join(self.root, "m.json")
            json.dump([SOLVE, QA] * 2, open(mf, "w"))
            o = os.path.join(self.root, "out")
            code, out, _ = self.run_cli(["--inputs", i, "--keys", k, "--mock", mf, "--out", o])
            self.assertEqual(code, 0, out)
            sm = json.load(open(os.path.join(o, "summary.json")))
            self.assertEqual(sm["totals"]["pass"], 2)
            self.assertTrue(os.path.isfile(os.path.join(o, "report.md")))


if __name__ == "__main__":
    unittest.main()


class Robust(Bench):
    def test_engine_error_skips_item_not_run(self):
        real = engine.run
        def boom(path, out, cfg, llm):
            if "english2" in path:
                raise OSError("missing prompt")
            return real(path, out, cfg, llm)
        with mock.patch.object(engine, "run", boom):
            rows = benchmark.run_all(self.items, os.path.join(self.root, "o"), self.cfg, Fake(), 5.0)
        self.assertEqual(rows[1]["skipped"], "error: missing prompt")
        self.assertNotIn("skipped", rows[0])

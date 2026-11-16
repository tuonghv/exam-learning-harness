"""TASK-120 (REQ-0127, Fix-J): boundary windows keep every suspect, per-pass summary, and NaN cost
caps on every paid entry. Fake `ask`, dry-run only: no network, no paid call."""
import contextlib
import io
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.ingest import boundary  # noqa: E402

NAN = float("nan")


def sus(*nums):
    return [{"line": n, "kind": "QE", "token": ""} for n in nums]


def span(w):
    return (w["start"], w["end"], sorted(w["suspects"]))


class Fake:
    def __init__(self):
        self.calls = 0

    def __call__(self, prompt):
        self.calls += 1
        return types.SimpleNamespace(
            ok=True, cost_usd=0.003, reason="",
            text='{"windows":[{"window_id":"w1","items":[{"line":5,"label":"other","confidence":0.9}]}]}')


def reviewer(ask, **kw):
    return boundary.Reviewer(ask, **kw)


class WindowsF001(unittest.TestCase):
    def test_dense_chain_keeps_every_suspect(self):
        wins, skipped = boundary.windows(["x"] * 80, sus(10, 22, 34, 46, 58))
        self.assertEqual([span(w) for w in wins], [(2, 30, [10, 22]), (26, 54, [34, 46]), (50, 66, [58])])
        self.assertEqual(skipped, 0)

    def test_over_max_windows_is_counted(self):
        nums = list(range(10, 400, 12))
        wins, skipped = boundary.windows(["x"] * 420, sus(*nums), max_windows=2)
        sent = sum(len(w["suspects"]) for w in wins)
        self.assertEqual(len(wins), 2)
        self.assertGreater(skipped, 0)
        # every suspect is in a sent window or in a counted dropped window
        all_wins, _ = boundary.windows(["x"] * 420, sus(*nums), max_windows=999)
        self.assertEqual(sum(len(w["suspects"]) for w in all_wins), len(nums))
        self.assertEqual(len(all_wins) - skipped, len(wins))
        self.assertLess(sent, len(nums))

    def test_guard_single_span_unchanged(self):
        wins, skipped = boundary.windows(["x"] * 80, sus(10, 14))
        self.assertEqual([span(w) for w in wins], [(2, 22, [10, 14])])
        self.assertEqual(skipped, 0)


class SummaryF007(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(boundary, "suspects", lambda lines, p=None, k=None: sus(5))
        p.start()
        self.addCleanup(p.stop)
        self.lines = ["l%d" % i for i in range(30)]

    def msgs(self, rv):
        return [x["message"] for x in rv.warnings if x["code"] == "boundary_ai_summary"]

    def test_second_pass_summary_is_per_pass(self):
        ask = Fake()
        rv = reviewer(ask)
        rv(self.lines)
        self.assertEqual(self.msgs(rv), ["1 window(s), 1 call(s), 0 cached, cost $0.0030"])
        rv(self.lines)
        self.assertEqual(ask.calls, 1)
        self.assertEqual(self.msgs(rv), ["1 window(s), 0 call(s), 1 cached, cost $0.0000"])

    def test_guard_stats_stay_cumulative(self):
        rv = reviewer(Fake())
        rv(self.lines)
        rv(self.lines)
        self.assertEqual((rv.stats["calls"], rv.stats["cached"]), (1, 1))


class CapF009(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(boundary, "suspects", lambda lines, p=None, k=None: sus(5))
        p.start()
        self.addCleanup(p.stop)
        self.lines = ["l%d" % i for i in range(30)]

    def run_cap(self, **kw):
        ask = Fake()
        rv = reviewer(ask, **kw)
        rv(self.lines)
        return ask.calls, [x["code"] for x in rv.warnings]

    def test_nan_cap_stops_calls(self):
        n, codes = self.run_cap(max_cost=NAN)
        self.assertEqual(n, 0)
        self.assertIn("boundary_ai_budget", codes)

    def test_guard_zero_cap_and_default(self):
        n, codes = self.run_cap(max_cost=0.0)
        self.assertEqual(n, 0)
        self.assertIn("boundary_ai_budget", codes)
        n, codes = self.run_cap()
        self.assertEqual(n, 1)
        self.assertNotIn("boundary_ai_budget", codes)


class NanEntries(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        self.md = os.path.join(d, "t.md")
        with open(self.md, "w", encoding="utf-8") as f:
            f.write("Câu 1. Tính 1+1.\nA. 1\nB. 2\nC. 3\nD. 4\n")

    def call(self, fn, argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = fn(argv)
        return rc, err.getvalue()

    def cases(self):
        m = self.md
        return [
            ("ingest", cli.ingest_main, [m, "--boundary-ai", "haiku", "--dry-run", "--max-cost-usd", "nan"]),
            ("solve", cli.solve_main, [m, "--dry-run", "--max-cost-usd", "nan"]),
            ("refine", cli.refine_main, [m, "--pages", "1", "--dry-run", "--max-cost-usd", "nan"]),
            ("cross", cli.cross_main, [m, "--pdf", m, "--pages", "1", "--dry-run", "--max-cost-usd", "nan"]),
            ("benchmark-max", cli.benchmark_main, ["--dry-run", "--max-cost-usd", "nan"]),
            ("benchmark-budget", cli.benchmark_main, ["--dry-run", "--budget-usd", "nan"]),
            ("genexam", cli.genexam_main, ["--dry-run", "--max-cost-usd", "nan"]),
        ]

    def test_nan_cap_is_usage_error_everywhere(self):
        for name, fn, argv in self.cases():
            with self.subTest(entry=name):
                rc, err = self.call(fn, argv)
                self.assertEqual(rc, 2)
                self.assertIn(">= 0", err)

    def test_guard_negative_still_rejected(self):
        for name, fn, argv in self.cases():
            with self.subTest(entry=name):
                argv = [("-1" if a == "nan" else a) for a in argv]
                self.assertEqual(self.call(fn, argv)[0], 2)

    def test_guard_zero_cap_not_a_usage_error(self):
        rc, err = self.call(cli.ingest_main, [self.md, "--boundary-ai", "haiku", "--dry-run",
                                              "--max-cost-usd", "0"])
        self.assertNotIn("--max-cost-usd >= 0", err)
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

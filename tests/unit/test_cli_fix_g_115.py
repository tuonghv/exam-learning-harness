"""TASK-115 Fix-G cli: one test per AC (115.1 .. 115.4). Mock solves only, tmp cwd."""
import contextlib
import glob
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402

EX = os.path.join(ROOT, "examples", "english", "input-001.md")
MK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")


class FixG115(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self.T = tempfile.mkdtemp()
        os.chdir(self.T)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self.T, ignore_errors=True)

    def q(self, f, *a):
        o, e = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            r = f(*a)
        return r, o.getvalue(), e.getvalue()

    def solve(self, *extra):
        r, _, _ = self.q(cli.solve_main, [EX, "--mock", MK, "--line", "dev", "--no-pdf"] + list(extra))
        self.assertIn(r, (0, 1))  # 1 = uncertain answer in the mock
        return [x for x in glob.glob(self.T + "/plans/input-001/dev/runs/*")
                if os.path.isfile(x + "/result.json")][0]

    def runs(self):
        return sorted(glob.glob(self.T + "/reports/input-001/dev/run-*"))

    def test_ac1_failed_solve_leaves_no_run_dir(self):
        self.solve()
        r, _, _ = self.q(cli.solve_main, [EX, "--mock", "nosuch.json", "--line", "dev"])
        self.assertEqual(r, 2)
        left = [x for x in glob.glob(self.T + "/plans/input-001/dev/runs/*")
                if not os.path.isfile(x + "/plan.json")]
        self.assertEqual(left, [])
        r, _, _ = self.q(cli.publish_main, ["input-001", "--from", "dev"])
        self.assertEqual(r, 0)

    def _broken_plan(self):
        plan = self.solve()
        os.remove(plan + "/result.json")
        return plan

    def test_ac2a_report_failure_removes_fresh_dir(self):
        plan = self._broken_plan()
        before = self.runs()
        r, _, _ = self.q(cli._report_plan, [plan])
        self.assertEqual(r, 2)
        self.assertEqual(self.runs(), before)

    def test_ac2b_report_id_dir_kept(self):
        plan = self._broken_plan()
        keep = self.T + "/reports/input-001/dev/run-keep"
        os.makedirs(keep)
        open(keep + "/x", "w").close()
        r, _, _ = self.q(cli._report_plan, [plan, "--report-id", "keep"])
        self.assertEqual(r, 2)
        self.assertTrue(os.path.isfile(keep + "/x"))

    def test_ac2c_report_pack_failure_removes_fresh_dir(self):
        plan = self._broken_plan()
        before = self.runs()
        r, _, _ = self.q(cli.report_pack_main, [plan, "--exam", "input-001", "--no-pdf"])
        self.assertEqual(r, 2)
        self.assertEqual(self.runs(), before)

    def test_ac2d_drop_keeps_reports_root_no_line(self):
        d = self.T + "/reports/ex/run-x"
        os.makedirs(d)
        cli._drop_fresh_report_dir(d, self.T + "/reports")
        self.assertTrue(os.path.isdir(self.T + "/reports"))
        self.assertFalse(os.path.exists(self.T + "/reports/ex"))
        d = self.T + "/reports/run-y"  # run dir directly under the root
        os.makedirs(d)
        cli._drop_fresh_report_dir(d, self.T + "/reports")
        self.assertTrue(os.path.isdir(self.T + "/reports"))

    def test_ac2e_drop_keeps_sibling_run_under_line(self):
        keep = self.T + "/reports/ex/dev/run-keep"
        fresh = self.T + "/reports/ex/dev/run-new"
        os.makedirs(keep)
        os.makedirs(fresh)
        cli._drop_fresh_report_dir(fresh, self.T + "/reports")
        self.assertTrue(os.path.isdir(keep))
        self.assertFalse(os.path.exists(fresh))

    def test_ac2f_report_out_given_failure_keeps_dir(self):
        plan = self._broken_plan()
        out = self.T + "/myout"
        os.makedirs(out)
        open(out + "/x", "w").close()
        r, _, _ = self.q(cli._report_plan, [plan, "--out", out])
        self.assertEqual(r, 2)
        self.assertTrue(os.path.isfile(out + "/x"))

    def _stats(self, ref, hist):
        return self.q(cli.run_stats_main, ["stats", ref, "--history", hist, "--json"])

    def _rid(self, hist):
        with open(hist) as fh:
            return json.loads(fh.read().splitlines()[-1])["run_id"]

    def test_ac3_stats_by_run_id_equals_by_dir(self):
        hist = self.T + "/h"
        d = self.solve("--history", hist)
        r1, o1, _ = self._stats(self._rid(hist), hist)
        r2, o2, _ = self._stats(d, hist)
        self.assertEqual((r1, r2), (0, 0))
        self.assertEqual(o1, o2)

    def test_ac3b_explain_by_run_id_like_by_dir(self):
        hist = self.T + "/h"
        d = self.solve("--history", hist)
        rid = self._rid(hist)
        key = self.T + "/key.txt"
        with open(key, "w") as fh:
            fh.write("1 A\n")
        r_dir, _, _ = self.q(cli.run_stats_main, ["explain", d, "--history", hist, "--key", key])
        r_id, _, e = self.q(cli.run_stats_main, ["explain", rid, "--history", hist, "--key", key])
        self.assertEqual(r_dir, 0)
        self.assertEqual(r_id, r_dir, e)

    def test_ac4_write_recipe_dry_run_refused(self):
        rec = os.path.join(cli.settings.config_dir(), cli.RECIPE_FILE)
        shutil.copy(rec, self.T + "/r.json")
        os.makedirs(self.T + "/rep")
        with open(self.T + "/r.json") as fh:
            before = fh.read()
        r, _, e = self.q(cli.rebuild_reports_main, ["--write-recipe", "--dry-run", "--recipe", self.T + "/r.json",
                                                     "--reports", self.T + "/rep"])
        self.assertEqual(r, 2)
        self.assertIn("cannot be combined", e)
        with open(self.T + "/r.json") as fh:
            self.assertEqual(fh.read(), before)


if __name__ == "__main__":
    unittest.main()

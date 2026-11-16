"""TASK-133 (REQ-0140): one test per id 133.1 .. 133.9. Mocks and tmp dirs only, no network."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.ingest import refine  # noqa: E402
from exam_engine.pipeline import reporter, runlayout as L  # noqa: E402

EX = os.path.join(ROOT, "examples", "english", "input-001.md")
MK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")


class Fix133(unittest.TestCase):
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

    def w(self, name, text):
        p = os.path.join(self.T, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def test_133_1_report_failure_is_warn(self):
        with mock.patch.object(reporter, "git_info", return_value=None), \
                mock.patch.object(cli, "_build_default_report", side_effect=OSError("ro")):
            r, o, e = self.q(cli.solve_main, [EX, "--mock", MK, "--no-pdf"])
        self.assertIn(r, (0, 1))
        self.assertIn("pass=", o)
        self.assertIn("WARN: report not built", e)

    def test_133_2_refine_out_dir_checked_before_calls(self):
        calls = []

        def fake(doc, pages, llm, src, *a, trace=None, **k):
            calls.append(1)
            trace.append({"x": 1})
            return {"refined": {"pages": [1], "questions": [], "calls": 1, "cost_usd": 0.0}}
        with mock.patch.object(refine, "refine", fake), mock.patch.object(refine, "check_key_pages"), \
                mock.patch.object(refine, "pick_pages", return_value=[1]), mock.patch.object(refine, "mock_llm"):
            r, _, e = self.q(cli.refine_main, [EX, "--pages", "1", "--mock", "x", "--out", "/nonexistent/x.json"])
        self.assertEqual((r, calls), (2, []))
        self.assertIn("no such dir", e)

    def test_133_3_ingest_refined_without_block(self):
        x = self.w("x.json", "{}")
        r, _, e = self.q(cli.ingest_main, [EX, "--exam-out", self.T + "/e.md", "--refined", x])
        self.assertEqual(r, 2)
        self.assertIn("no refined block", e)

    def test_133_4_benchmark_missing_inputs(self):
        r, _, e = self.q(cli.benchmark_main, ["--dry-run", "--inputs", "/nonexistent"])
        self.assertEqual(r, 2)
        self.assertIn("ERROR", e)

    def test_133_5_lessons_unwritable_out_and_non_dict(self):
        s = self.w("summary.json", json.dumps({"items": []}))
        r, _, e = self.q(cli.lessons_main, ["--summary", s, "--out", "/nonexistent/x"])
        self.assertEqual(r, 2)
        self.assertIn("--out", e)
        # D1: default path next to --summary
        with mock.patch("builtins.open", side_effect=_ro_open):
            r, _, e = self.q(cli.lessons_main, ["--summary", s])
        self.assertEqual(r, 2)
        # D2: a list summary
        s2 = self.w("list.json", "[]")
        r, _, e = self.q(cli.lessons_main, ["--summary", s2])
        self.assertEqual(r, 2)

    def test_133_6_backfill_warns_per_dropped_ref(self):
        h = self.T + "/h"
        r, _, e = self.q(cli.run_stats_main, ["backfill", self.T + "/nosuch", "--history", h])
        self.assertEqual(r, 2)
        self.assertIn("WARN: not a result dir", e)
        ok = os.path.join(self.T, "ok")
        os.mkdir(ok)
        self.w("ok/result.json", "{}")
        with mock.patch.object(cli.metrics, "backfill", return_value=(0, 1)):
            r, _, e = self.q(cli.run_stats_main, ["backfill", ok, self.T + "/nosuch", "--history", h])
        self.assertEqual(r, 0)
        self.assertEqual(e.count("WARN: not a result dir"), 1)

    def test_133_7_run_list_bad_foreign_plan(self):
        d = os.path.join(self.T, "d")
        os.mkdir(d)
        self.w("d/plan.json", "{")
        rr = {"layout": "run", "manifest": {"plan_runs": [{"exam_id": "other", "plan_run_id": "p1"}]},
              "warn": None, "line": "-", "dir": d}
        with mock.patch.object(L, "folder_alias", return_value=None), \
                mock.patch.object(L, "list_plan_runs", return_value=[]), \
                mock.patch.object(L, "list_report_runs", return_value=[rr]), \
                mock.patch.object(L, "migration_folders", return_value={}), \
                mock.patch.object(L, "plan_ref", return_value=d):
            r, _, e = self.q(cli.run_list_main, ["E"])
        self.assertNotIn("Traceback", e)
        self.assertIn(r, (0, 1, 2))

    def test_133_8_adapter_decodes_utf8_with_replace(self):
        def r(argv, **kw):
            return subprocess.run([sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'\\xff')"], **kw)
        c = claude.run_claude("hi", model="m", timeout_s=5, runner=r)
        self.assertFalse(c.ok)

    def test_133_9_unparseable_stdout_reason(self):
        r = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, 'warning: x\n{"result":"ok"}', "")  # noqa: E731
        c = claude.run_claude("hi", model="m", timeout_s=5, runner=r)
        self.assertFalse(c.ok)
        self.assertEqual(c.cls, "other")
        self.assertIn("unparseable output", c.reason)


def _ro_open(path, mode="r", *a, **k):
    if "w" in mode:
        raise OSError("read-only")
    return _real_open(path, mode, *a, **k)


_real_open = open

if __name__ == "__main__":
    unittest.main()

"""TASK-058 58.7: plan-import turns an old run dir into a plan run that `report` rebuilds without AI."""
import contextlib
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import planrun, reporter  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "plan_import", "run-small")
EXAM = os.path.join(ROOT, "examples", "english", "input-001.md")


def run(fn, *a):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(*a)
    return code, out.getvalue(), err.getvalue()


class PlanImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.tmp)
        self.src = os.path.join(self.tmp, "old", "run3-Math")
        shutil.copytree(FIX, self.src)
        p = mock.patch.object(reporter, "git_info", return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def imp(self, *extra):
        return run(cli.plan_import_main, [self.src, "--exam", EXAM, "--exam-id", "ex"] + list(extra))

    def plan(self):
        base = os.path.join(self.tmp, "plans", "ex")
        return os.path.join(base, sorted(os.listdir(base))[0])

    def test_import_layout_and_meta(self):
        code, out, _ = self.imp()
        self.assertEqual(code, 0, out)
        p = self.plan()
        meta = json.load(open(os.path.join(p, "plan.json")))
        self.assertEqual((meta["source"], meta["calls_captured"], meta["exam_id"], meta["status"]),
                         ("import", False, "ex", "done"))
        self.assertEqual(meta["imported_from"], os.path.abspath(self.src))
        self.assertEqual(meta["calls"], 2)
        for n in ("result.json", "run.log", os.path.join("input", "exam.md")):
            self.assertTrue(os.path.isfile(os.path.join(p, n)), n)
        rows = [json.loads(x) for x in open(os.path.join(p, "calls", "index.jsonl"))]
        self.assertEqual([r["n"] for r in rows], [1, 2])
        self.assertTrue(all(r["captured"] is False and r["reply"] == "not captured" for r in rows))
        self.assertFalse(os.path.exists(os.path.join(p, "calls", "001-reply.txt")))

    def test_report_rebuilds_without_ai(self):
        self.imp()
        with mock.patch.object(socket, "socket", side_effect=AssertionError("network")):
            code, _, err = run(cli.report_main, [self.plan(), "--no-pdf"])
        self.assertEqual(code, 0, err)
        d = os.path.join(self.tmp, "reports", "ex", os.path.basename(self.plan()), "sheet")
        self.assertTrue(os.path.isfile(os.path.join(d, "report.md")))
        self.assertTrue(os.path.isfile(os.path.join(d, "metrics.json")))

    def test_idempotent(self):
        self.imp()
        code, out, _ = self.imp()
        self.assertEqual(code, 0)
        self.assertIn("skipped", out)
        self.assertEqual(len(os.listdir(os.path.join(self.tmp, "plans", "ex"))), 1)

    def test_changed_result_is_a_new_import(self):
        self.imp()
        with open(os.path.join(self.src, "result.json"), "a") as fh:
            fh.write("\n")
        self.imp()
        self.assertEqual(len(os.listdir(os.path.join(self.tmp, "plans", "ex"))), 2)

    def test_missing_run_log_tolerated(self):
        os.remove(os.path.join(self.src, "run.log"))
        self.assertEqual(self.imp()[0], 0)
        p = self.plan()
        self.assertFalse(os.path.exists(os.path.join(p, "run.log")))
        self.assertEqual(run(cli.report_main, [p, "--no-pdf"])[0], 0)

    def test_no_result_json_exit_2(self):
        os.remove(os.path.join(self.src, "result.json"))
        code, _, err = self.imp()
        self.assertEqual(code, 2)
        self.assertIn("not a result dir", err)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "plans", "ex")))

    def test_exam_unreadable_is_tolerated(self):
        code, _, _ = run(cli.plan_import_main, [self.src])  # result exam.path is relative, not readable
        self.assertEqual(code, 0)
        base = os.path.join(self.tmp, "plans", "input-001")  # exam-id defaults to the result exam path
        self.assertFalse(os.path.exists(os.path.join(base, os.listdir(base)[0], "input")))

    def test_trace_and_ingest_cache_picked_up(self):
        trace = os.path.join(self.src, "5-12.json.trace.json")
        with open(trace, "w") as fh:
            json.dump([{"ok": True, "cls": "", "cost_usd": 0.1, "text": "RAW", "reason": ""}], fh)
        cache = os.path.join(self.tmp, "old", "work", "ingest", "abcd1234")
        os.makedirs(cache)
        with open(os.path.join(cache, "page-1.json"), "w") as fh:
            fh.write('{"x": 1}')
        self.assertEqual(self.imp()[0], 0)
        ing = os.path.join(self.plan(), "ingest")
        self.assertTrue(os.path.isfile(os.path.join(ing, "5-12.json.trace.json")))
        self.assertTrue(os.path.isfile(os.path.join(ing, "cache", "abcd1234", "page-1.json")))
        meta = json.load(open(os.path.join(self.plan(), "plan.json")))
        self.assertEqual(meta["ingest_files"], 2)

    def test_ambiguous_ingest_cache_needs_flag(self):
        for h in ("aa", "bb"):
            os.makedirs(os.path.join(self.tmp, "old", "work", "ingest", h))
            open(os.path.join(self.tmp, "old", "work", "ingest", h, "f.json"), "w").write("{}")
        self.imp()
        self.assertFalse(os.path.exists(os.path.join(self.plan(), "ingest")))
        shutil.rmtree(os.path.join(self.tmp, "plans"))
        self.imp("--ingest-cache", os.path.join(self.tmp, "old", "work", "ingest", "bb"))
        self.assertTrue(os.path.isfile(os.path.join(self.plan(), "ingest", "cache", "bb", "f.json")))

    def test_run_stats_reads_imported_plan(self):
        self.imp()
        code, out, err = run(cli.run_stats_main, ["stats", self.plan()])
        self.assertEqual(code, 0, err)

    def test_import_dir_api(self):
        p, status = planrun.import_dir(self.src, "plans", exam_path=EXAM, exam_id="ex")
        self.assertEqual(status, "imported")
        self.assertEqual(planrun.import_dir(self.src, "plans", exam_path=EXAM, exam_id="ex"), (p, "skipped"))


if __name__ == "__main__":
    unittest.main()

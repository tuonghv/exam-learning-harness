"""TASK-058 58.3/58.4/58.6: report builder is pure, deterministic and AI-free. Mock LLM only."""
import ast
import contextlib
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.pipeline import report_build, report_kinds as rk, reporter  # noqa: E402

EXAM = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")
BUILDER = os.path.join(ROOT, "src", "exam_engine", "pipeline", "report_build.py")
FORBIDDEN = ("engine", "adapters", "solver", "verifier", "socket", "urllib", "http", "subprocess")


def tree(d):
    out = {}
    for base, _, names in os.walk(d):
        for n in names:
            p = os.path.join(base, n)
            with open(p, "rb") as fh:
                # REQ-0092: the run part of a standard name comes from the out dir; compare trees modulo it
                out[re.sub(r"_run-[a-z0-9-]+\.", "_run-X.", os.path.relpath(p, d))] = fh.read()
    return out


def pick(tr, legacy):
    """Entry of a tree() dict by legacy name (report.md ...): the standard-named file of that kind and ext."""
    kind = {"report.md": "solution-report", "metrics.json": "metrics", "report.json": "result-data",
            "answers.md": "answer-sheet", "learning.md": "learning-report"}[legacy]
    for k, v in tr.items():
        pr = rk.parse(k.replace("run-X", "run-x"))
        if pr and pr["kind"] == kind and k.endswith("." + legacy.rsplit(".", 1)[1]):
            return v
    raise KeyError(legacy)


def stdpath(d, kind, ext):
    """Path of the standard-named file of `kind` in directory d (None when absent)."""
    return rk.find(d, kind, ext=ext)


def quiet(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a)


class ReportBuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.tmp)
        p = mock.patch.object(reporter, "git_info", return_value=None)
        p.start()
        self.addCleanup(p.stop)
        self.assertIn(quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"]), (0, 1))
        base = os.path.join(self.tmp, "plans", "input-001", "main", "runs")
        self.plan = os.path.join(base, os.listdir(base)[0])

    def test_default_solve_report_in_reports_tree(self):
        rid = os.path.basename(self.plan)
        d = os.path.join(self.tmp, "reports", "input-001", "main", "run-" + rid)  # 87.3: one run dir, files flat
        names = sorted(os.listdir(d))
        for kind, ext in (("solution-report", "md"), ("answer-sheet", "md"), ("metrics", "json"), ("result-data", "json")):
            self.assertIsNotNone(stdpath(d, kind, ext), names)
        self.assertFalse(any(n in names for n in ("report.md", "answers.md", "metrics.json", "report.json")))
        self.assertIsNone(rk.find(self.plan, "solution-report"))
        self.assertIn("## Metrics", pick(tree(d), "report.md").decode())

    def test_determinism(self):
        a, b = os.path.join(self.tmp, "a"), os.path.join(self.tmp, "b")
        for d in (a, b):
            report_build.build(self.plan, d, pdf=False)
        self.assertEqual(tree(a), tree(b))
        run = tree(os.path.join(self.tmp, "reports", "input-001", "main", "run-" + os.path.basename(self.plan)))
        for k in ("run.json", "INDEX.md"):  # the run dir adds its manifest and index; the report files are equal
            run.pop(k)
        self.assertEqual(tree(a), run)

    def test_metrics_use_stored_exam(self):
        info = report_build.build(self.plan, os.path.join(self.tmp, "x"))
        self.assertEqual(json.loads(pick(tree(os.path.join(self.tmp, "x")), "metrics.json")), info["metrics"])
        self.assertTrue(any(r.get("group_kind") for r in info["metrics"]["questions"]))

    def test_ai_forbidden_import_check(self):
        with open(BUILDER, encoding="utf-8") as fh:
            t = ast.parse(fh.read())
        mods = []
        for n in ast.walk(t):
            if isinstance(n, ast.Import):
                mods += [x.name for x in n.names]
            elif isinstance(n, ast.ImportFrom):
                mods += [n.module] + [n.module + "." + x.name for x in n.names]
        for m in mods:
            for part in m.split("."):
                self.assertNotIn(part, FORBIDDEN, m)

    def test_builds_with_ai_network_process_blocked(self):
        boom = mock.Mock(side_effect=AssertionError("forbidden"))
        with mock.patch.object(claude, "run_claude", boom), mock.patch.object(claude, "_run", boom, create=True), \
                mock.patch.object(subprocess, "run", boom), mock.patch.object(subprocess, "Popen", boom), \
                mock.patch.object(socket, "socket", boom):
            report_build.build(self.plan, os.path.join(self.tmp, "o"), pdf=False)
        self.assertFalse(boom.called)
        self.assertIsNotNone(stdpath(os.path.join(self.tmp, "o"), "solution-report", "md"))

    def test_rebuild_with_changed_report_engine_no_llm(self):
        out = os.path.join(self.tmp, "o")
        report_build.build(self.plan, out)
        before = pick(tree(out), "report.md")
        with mock.patch.object(reporter, "build_markdown", return_value="CHANGED\n"), \
                mock.patch.object(reporter, "_compose", return_value="CHANGED\n"), \
                mock.patch.object(claude, "run_claude", side_effect=AssertionError("llm")):
            report_build.build(self.plan, out)
        self.assertEqual(pick(tree(out), "report.md"), b"CHANGED\n")
        self.assertNotEqual(before, b"CHANGED\n")

    def test_many_reports_per_plan_run(self):
        for args in (["--report-id", "a"], ["--report-id", "b"], ["--view", "learn", "--report-id", "l"]):
            self.assertEqual(quiet(cli.report_main, [self.plan, "--no-pdf"] + args), 0)
        base = os.path.join(self.tmp, "reports", "input-001", "main")
        self.assertEqual(sorted(os.listdir(base)), ["INDEX.md", "run-" + os.path.basename(self.plan), "run-a", "run-b", "run-l"])  # INDEX.md = exam runs index (87.6)

        def body(n):  # report files only: run.json holds created_utc, INDEX.md lists the run
            t = tree(os.path.join(base, n))
            return {k: v for k, v in t.items() if k not in ("run.json", "INDEX.md")}
        self.assertEqual(body("run-a"), body("run-b"))
        self.assertNotEqual(pick(body("run-a"), "report.md"), pick(body("run-l"), "learning.md"))

    def test_incomplete_plan_exit_2_and_old_form(self):
        empty = os.path.join(self.tmp, "empty")
        os.mkdir(empty)
        self.assertEqual(quiet(cli.report_main, [empty, "--no-pdf", "--out", os.path.join(self.tmp, "z")]), 2)
        out = os.path.join(self.tmp, "old")
        self.assertEqual(quiet(cli.report_main, [os.path.join(self.plan, "result.json"), "--out", out, "--no-pdf"]), 0)
        self.assertIsNotNone(stdpath(out, "solution-report", "md"))


if __name__ == "__main__":
    unittest.main()

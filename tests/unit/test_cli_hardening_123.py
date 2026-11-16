"""TASK-123 / REQ-0130: CLI hardening 123.1-123.6 (run-stats compare/trend/board, rebuild-reports, ingest)."""
import contextlib
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

EXAM = os.path.join(ROOT, "examples/english/input-001.md")
MOCK = os.path.join(ROOT, "tests/unit/fixtures/mock_english_001.json")


def quiet(fn, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = fn(argv)
        except Exception as exc:  # a traceback is the defect under test
            code = "raised %s" % type(exc).__name__
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, True)

    def solve(self, name, hist):
        o = os.path.join(self.tmp, name)
        code = quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--out", o, "--no-pdf", "--history", hist])[0]
        self.assertIn(code, (0, 1))  # 1 = an uncertain answer, result written
        return o


class T1CompareSha(Base):
    def test_history_sha_differs_with_exam_exits_2(self):
        h = os.path.join(self.tmp, "h.jsonl")
        a, b = self.solve("a", h), self.solve("b", h)
        with open(h, encoding="utf-8") as fh:
            rows = [json.loads(x) for x in fh if x.strip()]
        for i, r in enumerate(rows):
            r["exam_sha256"] = ("%d" % i) * 64
        with open(h, "w", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in rows))
        code, _, err = quiet(cli.run_stats_main, ["compare", a, b, "--exam", EXAM, "--history", h])
        self.assertEqual(code, 2)
        self.assertIn("different exam", err)


class T2Recipe(Base):
    def test_non_id_folder_skipped(self):
        os.makedirs(os.path.join(self.tmp, "rep", ".ipynb_checkpoints"))
        code, _, err = quiet(cli.rebuild_reports_main, ["--write-recipe", "--recipe", self.tmp + "/r.json",
                                                         "--reports", self.tmp + "/rep"])
        self.assertEqual(code, 0)
        self.assertIn("skipped .ipynb_checkpoints", err)
        self.assertTrue(os.path.isfile(self.tmp + "/r.json"))


class T3Trace(Base):
    def test_unwritable_trace_exit_2(self):
        with open("m.json", "w") as fh:
            fh.write("[]")
        code, _, err = quiet(cli.ingest_main, [EXAM, "--boundary-ai", "haiku", "--mock", "m.json",
                                               "--boundary-trace", "/nonexistent/t.txt"])
        self.assertEqual(code, 2)
        self.assertIn("ERROR", err)


class T4Last(Base):
    def test_negative_last_exit_2(self):
        h = os.path.join(self.tmp, "h.jsonl")
        self.solve("a", h)
        code, out, _ = quiet(cli.run_stats_main, ["trend", "--last", "-3", "--history", h])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")


class T5BoardSha(Base):
    def test_baseline_without_sha_message(self):
        h = os.path.join(self.tmp, "h.jsonl")
        o = self.solve("o", h)
        code, _, err = quiet(cli.run_stats_main, ["board", "--baseline", o, "--history", self.tmp + "/none.jsonl"])
        self.assertEqual(code, 2)
        self.assertIn("exam sha unknown", err)
        self.assertIn("pass --exam", err)


class T6IngestUsage(Base):
    def test_questions_without_refined(self):
        code, _, err = quiet(cli.ingest_main, [EXAM, "--exam-out", "e.md", "--questions", "1-2"])
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists("e.md"))

    def test_refined_without_exam_out(self):
        with open("r.json", "w") as fh:
            fh.write("{}")
        code, _, _ = quiet(cli.ingest_main, [EXAM, "--refined", "r.json", "--out", "o.json"])
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists("o.json"))


if __name__ == "__main__":
    unittest.main()

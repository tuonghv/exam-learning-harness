"""TASK-057 57.8 (RAW-00174): solve without --out writes under git-ignored reports/. Mock runner, temp git repo."""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402

EXAM = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")


def git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True, check=True).stdout


class DefaultOutTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        shutil.copy(os.path.join(ROOT, ".gitignore"), os.path.join(self.tmp, ".gitignore"))
        git(self.tmp, "init", "-q")
        git(self.tmp, "-c", "user.email=a@b", "-c", "user.name=t", "add", ".gitignore")
        git(self.tmp, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "i")
        os.chdir(self.tmp)

    def solve(self, *extra):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return cli.solve_main([EXAM, "--mock", MOCK] + list(extra))

    def test_no_out_goes_to_ignored_reports_dir(self):
        self.assertIn(self.solve(), (0, 1))
        base = os.path.join(self.tmp, "reports", "input-001")
        runs = os.listdir(base)
        self.assertEqual(len(runs), 1)
        self.assertTrue(os.path.isfile(os.path.join(base, runs[0], "result.json")))
        self.assertEqual(git(self.tmp, "status", "--porcelain"), "")

    def test_two_runs_do_not_collide(self):
        self.solve()
        self.solve()
        self.assertEqual(len(os.listdir(os.path.join(self.tmp, "reports", "input-001"))), 2)

    def test_explicit_out_honoured(self):
        self.solve("--out", "mine")
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "mine", "result.json")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "reports")))

    def test_dry_run_creates_nothing(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.solve_main([EXAM, "--dry-run"])
        self.assertEqual(os.listdir(self.tmp).count("reports"), 0)

    def test_history_default_and_legacy_fallback(self):
        self.assertEqual(cli.DEFAULT_HISTORY, os.path.join("reports", "run-history.jsonl"))
        os.makedirs("results")
        with open(cli.LEGACY_HISTORY, "w", encoding="utf-8") as f:
            f.write('{"run_id": "old", "exam_id": "x", "ts": "2026-01-01T00:00:00Z", "metrics": {}}\n')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            code = cli.run_stats_main(["trend", "--exam-id", "x", "--json"])
        self.assertIn(code, (0, 1))
        self.assertIn("2026-01-01T00:00:00Z", buf.getvalue())


if __name__ == "__main__":
    unittest.main()

"""scripts/exam.py subcommands, run as `python3 -I` from a foreign cwd; old shims agree."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
EXAM = os.path.join(ROOT, "scripts", "exam.py")
OLD_RUN = os.path.join(ROOT, "tools", "examples", "exam_run.py")
INPUT = os.path.join(ROOT, "examples", "english", "input-001.md")
KEY = os.path.join(ROOT, "examples", "english", "expected-001.md")
MOCK = os.path.join(HERE, "fixtures", "mock_english_001.json")


def run(script, *args, **kw):
    p = subprocess.run([sys.executable, "-I", script] + list(args), cwd=kw.get("cwd"),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return p.returncode, p.stdout, p.stderr


class Exam(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)

    def test_no_or_unknown_subcommand_is_usage_exit_2(self):
        for args in ((), ("bogus",)):
            code, _, err = run(EXAM, *args, cwd=self.tmp)
            self.assertEqual(code, 2)
            self.assertIn("usage: exam.py", err)

    def test_parse_prints_json(self):
        code, out, _ = run(EXAM, "parse", INPUT, cwd=self.tmp)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["fields"]["Subject"], "English")
        self.assertEqual(run(EXAM, "parse", "nope.md", cwd=self.tmp)[0], 2)

    def test_check_examples_ok(self):
        code, out, _ = run(EXAM, "check-examples", cwd=self.tmp)
        self.assertEqual(code, 0)
        self.assertTrue(out.splitlines()[-1].startswith("OK: "))

    def test_score_usage(self):
        self.assertEqual(run(EXAM, "score", cwd=self.tmp)[0], 2)

    def test_verify_and_report_from_a_mock_run(self):
        out = os.path.join(self.tmp, "r")
        code, line, _ = run(EXAM, "solve", INPUT, "--mock", MOCK, "--out", out, "--no-pdf",
                            cwd=self.tmp)
        self.assertIn(code, (0, 1))
        self.assertTrue(line.startswith("pass="))
        with open(MOCK, encoding="utf-8") as fh:
            solve_out = os.path.join(self.tmp, "solve.json")
            with open(solve_out, "w", encoding="utf-8") as g:
                g.write(json.load(fh)[0])
        code, o, _ = run(EXAM, "verify", INPUT, solve_out, cwd=self.tmp)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(o)[0]["id"], "1")
        out2 = os.path.join(self.tmp, "r2")
        code, o, _ = run(EXAM, "report", os.path.join(out, "result.json"), "--out", out2,
                         "--no-pdf", cwd=self.tmp)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(os.path.join(out2, "report.md")))

    def test_solve_and_old_exam_run_print_the_same_summary(self):
        a, b = os.path.join(self.tmp, "o"), os.path.join(self.tmp, "o")
        args = (INPUT, "--mock", MOCK, "--key", KEY, "--out", a, "--no-pdf")
        new = run(EXAM, "solve", *args, cwd=self.tmp)
        old = run(OLD_RUN, *args, cwd=self.tmp)
        self.assertEqual(new[0], old[0])
        self.assertEqual(new[1], old[1])
        self.assertTrue(new[1].startswith("pass=1 fail=0"))
        self.assertEqual(b, a)

    def test_solve_requires_one_mode(self):
        self.assertEqual(run(EXAM, "solve", INPUT, cwd=self.tmp)[0], 2)


if __name__ == "__main__":
    unittest.main()

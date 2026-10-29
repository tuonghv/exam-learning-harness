"""Tests 13-14 of docs/design/phase-3-example-checker.md (AC4)."""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TOOLS = os.path.join(ROOT, "tools", "examples")  # the old-command shims
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import scorer as se  # noqa: E402

SENTINEL = "ZQXSENTINELKEYTEXT"
KEY = """# Expected Output

## Question 1

Final answer: 2.50 m/s^2

### Solution
%s secret derivation line that must never be printed anywhere.

## Question 2

Final answer: B
""" % SENTINEL


def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class MatchTests(unittest.TestCase):
    def test_13_match(self):  # AC4
        m = se.match
        self.assertTrue(m("B", "B"))
        self.assertTrue(m("b. had", "B"))
        self.assertFalse(m("C", "B"))
        self.assertFalse(m("Bad", "B"))
        self.assertTrue(m("c-a-b", "c - a - b"))
        self.assertFalse(m("a-b-c", "c-a-b"))
        self.assertTrue(m("2.5 m/s^2", "2.50 m/s^2"))
        self.assertFalse(m("2.6 m/s^2", "2.50 m/s^2"))
        self.assertFalse(m("2.5 km/s^2", "2.50 m/s^2"))
        self.assertIsNone(m("anything", "Open (rubric)"))
        self.assertFalse(m(None, "B"))


class DirRunTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.d = td.name
        self.keys = os.path.join(self.d, "keys")
        self.ans = os.path.join(self.d, "ans")
        put(os.path.join(self.keys, "physics", "expected-003.md"), KEY)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = se.score_main(list(args))
        return rc, out.getvalue(), err.getvalue()

    def test_14_scores_and_hides_key(self):  # AC4
        put(os.path.join(self.ans, "physics", "answer-003.md"),
            "## Question 1\n\nFinal answer: 2.5 m/s^2\n")
        rc, out, err = self.run_cli("--answers-dir", self.ans, "--keys-dir", self.keys)
        self.assertEqual(rc, 0, err)
        self.assertIn("physics/003 Q1: correct", out)
        self.assertIn("physics/003 Q2: missing", out)
        self.assertIn("TOTAL 1/2", out)
        self.assertNotIn(SENTINEL, out + err)
        self.assertNotIn("secret", out + err)

    def test_14_missing_answer_file(self):  # AC4
        os.makedirs(self.ans)
        rc, out, _ = self.run_cli("--answers-dir", self.ans, "--keys-dir", self.keys)
        self.assertEqual(rc, 0)
        self.assertIn("TOTAL 0/2", out)
        self.assertEqual(out.count("missing"), 2)

    def test_14_wrong_answer_not_echoed(self):  # AC4
        put(os.path.join(self.ans, "physics", "answer-003.md"),
            "## Question 1\n\nFinal answer: 9 m/s^2\n\n## Question 2\n\nFinal answer: B\n")
        rc, out, _ = self.run_cli("--answers-dir", self.ans, "--keys-dir", self.keys)
        self.assertIn("Q1: wrong", out)
        self.assertIn("Q2: correct", out)
        self.assertNotIn("2.50", out)

    def test_14_overlap_exit_2(self):  # AC4
        for ans in (os.path.join(self.keys, "physics"), self.keys, self.d):
            with self.subTest(ans=ans):
                rc, out, err = self.run_cli("--answers-dir", ans, "--keys-dir", self.keys)
                self.assertEqual(rc, 2)
                self.assertNotIn(SENTINEL, out + err)

    def test_14_usage_exit_2(self):  # AC4
        self.assertEqual(self.run_cli()[0], 2)

    def test_14_keys_only_from_keys_dir(self):  # AC4
        # a key-shaped file in the answers dir must not become a key
        put(os.path.join(self.ans, "physics", "expected-009.md"), KEY)
        rc, out, _ = self.run_cli("--answers-dir", self.ans, "--keys-dir", self.keys)
        self.assertNotIn("009", out)

    def test_14_subprocess_isolated(self):  # AC5
        r = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "score_eval.py"),
                            "--answers-dir", self.d + "x", "--keys-dir", self.keys],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()

"""End to end with --real against a fake `claude` executable on a temp PATH (no network)."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
EXAM = os.path.join(ROOT, "scripts", "exam.py")
INPUT = os.path.join(ROOT, "examples", "english", "input-001.md")
KEY = os.path.join(ROOT, "examples", "english", "expected-001.md")
MOCK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")

FAKE = """#!%s
import json, os, sys
d = os.environ["FAKE_DIR"]
prompt = sys.stdin.read()
with open(os.path.join(d, "seen.txt"), "a") as fh:
    fh.write(json.dumps({"argv": sys.argv[1:], "bytes": len(prompt), "cwd": os.getcwd()}) + "\\n")
n = len(open(os.path.join(d, "seen.txt")).read().splitlines())
replies = json.load(open(os.path.join(d, "replies.json")))
print(json.dumps({"result": replies[n - 1], "total_cost_usd": 0.01, "is_error": False}))
"""


class FakeClaude(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        exe = os.path.join(self.bin, "claude")
        with open(exe, "w") as fh:
            fh.write(FAKE % sys.executable)
        os.chmod(exe, os.stat(exe).st_mode | stat.S_IXUSR)
        with open(MOCK, encoding="utf-8") as src, \
                open(os.path.join(self.tmp, "replies.json"), "w") as dst:
            dst.write(src.read())

    def go(self, *extra):
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ.get("PATH", ""),
                   FAKE_DIR=self.tmp)
        out = os.path.join(self.tmp, "out")
        p = subprocess.run([sys.executable, "-I", EXAM, "solve", INPUT, "--real", "--out", out,
                            "--key", KEY, "--no-pdf"] + list(extra), cwd=self.tmp, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True)
        return p, out

    def test_real_mode_runs_the_fake_claude_twice_and_passes(self):
        p, out = self.go()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("pass=1 fail=0 uncertain=0 unresolved=0 calls=2", p.stdout)
        with open(os.path.join(out, "result.json"), encoding="utf-8") as fh:
            res = json.load(fh)
        self.assertEqual(res["run"]["llm"], "claude-p")
        self.assertAlmostEqual(res["run"]["cost_usd"], 0.02)
        with open(os.path.join(self.tmp, "seen.txt")) as fh:
            seen = [json.loads(x) for x in fh]
        self.assertEqual(len(seen), 2)
        self.assertIn("-p", seen[0]["argv"])
        self.assertNotEqual(os.path.realpath(seen[0]["cwd"]), os.path.realpath(ROOT))

    def test_cost_cap_stops_with_exit_3(self):
        p, _ = self.go("--max-cost-usd", "0.005")
        self.assertEqual(p.returncode, 3)
        self.assertIn("calls=1", p.stdout)


if __name__ == "__main__":
    unittest.main()

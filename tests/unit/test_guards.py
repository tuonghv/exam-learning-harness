"""Static rules: only adapters/claude.py runs `claude`; the key is read only by the scorer."""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(ROOT, "src", "exam_engine")
ADAPTER = os.path.join(SRC, "adapters", "claude.py")


def py_files(top):
    for d, _, names in os.walk(top):
        for n in sorted(names):
            if n.endswith(".py"):
                yield os.path.join(d, n)


def text(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


class Guards(unittest.TestCase):
    def test_only_the_adapter_names_claude_as_a_command(self):
        self.assertIn('"claude"', text(ADAPTER))
        pat = re.compile(r"""["']claude["']""")
        bad = [p for p in py_files(SRC) if p != ADAPTER and pat.search(text(p))]
        self.assertEqual(bad, [])

    def test_only_reporter_and_adapter_start_processes(self):
        pat = re.compile(r"subprocess\.(run|Popen|call|check_output|check_call)|os\.system")
        users = sorted(os.path.relpath(p, SRC) for p in py_files(SRC) if pat.search(text(p)))
        self.assertEqual(users, [os.path.join("adapters", "claude.py"),
                                 os.path.join("pipeline", "reporter.py")])

    def test_only_scorer_reads_keys(self):
        for p in py_files(SRC):
            rel = os.path.relpath(p, SRC)
            if rel in (os.path.join("pipeline", "scorer.py"), os.path.join("pipeline", "parser.py"),
                       os.path.join("pipeline", "examples_check.py")):
                continue
            self.assertNotIn("parse_expected", text(p), rel)

    def test_no_key_text_in_prompts(self):
        for p in py_files(os.path.join(ROOT, "scripts")):
            self.assertNotIn("claude", text(p).replace("exam_engine", ""))
        for d, _, names in os.walk(os.path.join(ROOT, "prompts")):
            for n in names:
                t = text(os.path.join(d, n))
                self.assertNotIn("evals/", t)
                self.assertNotIn("expected-", t)


if __name__ == "__main__":
    unittest.main()

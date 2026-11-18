"""TASK-149 (REQ-0155): advisory post-commit checks. Temp git repos, $0."""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import post_commit_check as P  # noqa: E402

LEDGER_TOOL = os.path.join(ROOT, "tools", "review_ledger.py")


class PostCommit(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "t")
        self.git("config", "core.hooksPath", "/dev/null")
        self.write("README.md", "x\n")
        self.commit("init")

    def git(self, *args):
        subprocess.run(("git", "-C", self.root) + args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def write(self, rel, text="x\n", size=None):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p) or self.root, exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(b"0" * size if size else text.encode("utf-8"))

    def commit(self, msg, *paths):
        self.git("add", *(paths or ["-A"]))
        self.git("commit", "-q", "-m", msg)

    def out(self, env=None):
        err = io.StringIO()
        old = dict(os.environ)
        os.environ.update(env or {})
        try:
            with redirect_stderr(err):
                rc = P.main(["--root", self.root])
        finally:
            os.environ.clear()
            os.environ.update(old)
        self.assertEqual(rc, 0)
        return err.getvalue()

    def test_clean_commit_ok(self):
        self.write("docs/a.md")
        self.commit("docs")
        self.assertRegex(self.out(), r"^post-commit: OK [0-9a-f]+\n$")

    def test_left_behind_state_first(self):
        self.write("b.txt")
        self.write(".claude/state/task.json", "{}\n")
        self.commit("two files")
        os.remove(os.path.join(self.root, "b.txt"))
        self.write(".claude/state/task.json", "{\"x\": 1}\n")
        self.write("docs/c.md")
        self.commit("only c", "docs/c.md")
        o = self.out()
        self.assertIn("WARN left-behind: 2 tracked file(s) still changed after the commit: "
                      ".claude/state/task.json, b.txt", o)

    def test_big_file(self):
        self.write("input/x.pdf", size=P.BIG_BYTES + 1)
        self.write("input/small.pdf", size=P.BIG_BYTES)
        self.commit("prompt edit")
        o = self.out()
        self.assertIn("WARN big-file: input/x.pdf is 1.0 MiB", o)
        self.assertNotIn("small.pdf", o)

    def test_no_task_trailer(self):
        self.write("src/m.py")
        self.commit("fix")
        self.assertIn("WARN no-task: code changed without a `Task:` trailer", self.out())
        self.write("src/m.py", "y\n")
        self.commit("fix\n\nTask: TASK-001")
        self.assertNotIn("no-task", self.out())

    def test_ledger_problems_only_when_touched(self):
        os.makedirs(os.path.join(self.root, "tools"))
        shutil.copy(LEDGER_TOOL, os.path.join(self.root, "tools", "review_ledger.py"))
        self.write("docs/report/fable-review/2026-11-18-phase150-x.md", "### F001 – [LOW] a\n")
        self.write("docs/review/findings.tsv", "\t".join(["id", "report", "class", "disposition", "ref", "note"]) + "\n")
        self.commit("review\n\nTask: TASK-001")
        self.assertIn("WARN ledger: 150-F001 (2026-11-18-phase150-x.md): no ledger row", self.out())
        self.write("docs/x.md")
        self.commit("other")
        self.assertNotIn("ledger", self.out())

    def test_opt_out_and_error_never_fail(self):
        self.write("src/m.py")
        self.commit("fix")
        self.assertEqual(self.out({"POST_COMMIT_CHECK": "0"}), "")
        shutil.rmtree(os.path.join(self.root, ".git"))
        self.assertIn("post-commit: skipped (", self.out())

    def test_hook_script_runs_and_exits_0(self):
        hook = os.path.join(ROOT, ".githooks", "post-commit")
        self.assertTrue(os.access(hook, os.X_OK))
        r = subprocess.run(["sh", hook], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True, env=dict(os.environ, POST_COMMIT_CHECK="0"))
        self.assertEqual((r.returncode, r.stderr), (0, ""))


if __name__ == "__main__":
    unittest.main()

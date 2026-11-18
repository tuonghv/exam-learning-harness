"""TASK-149 (REQ-0155): advisory post-commit checks. Temp git repos, $0."""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
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


class AutoPush(unittest.TestCase):
    """Hook part 2 (RAW-00373): background push of non-main branches to a local bare origin."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.origin = os.path.join(self.tmp, "origin.git")
        self.repo = os.path.join(self.tmp, "repo")
        subprocess.run(["git", "init", "-q", "--bare", self.origin], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", self.repo], check=True)
        hooks = os.path.join(self.repo, ".githooks")
        os.makedirs(hooks)
        shutil.copy(os.path.join(ROOT, ".githooks", "post-commit"), hooks)
        for k, v in (("user.email", "t@example.invalid"), ("user.name", "t"), ("core.hooksPath", ".githooks")):
            self.git("config", k, v)
        self.git("remote", "add", "origin", self.origin)

    def git(self, *args, env=None):
        return subprocess.run(("git", "-C", self.repo) + args, check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True,
                              env=dict(os.environ, **(env or {}))).stdout

    def commit(self, name, env=None):
        with open(os.path.join(self.repo, name), "w") as fh:
            fh.write(name)
        self.git("add", name)
        self.git("commit", "-q", "-m", name, env=env)
        return self.git("rev-parse", "HEAD").strip()

    def remote_sha(self, branch, wait=15.0):
        log = os.path.join(self.repo, ".git", "autopush.log")
        end = time.time() + wait
        while time.time() < end:
            if os.path.exists(log) and (" pushed " in open(log).read() or "FAILED" in open(log).read()):
                break
            time.sleep(0.1)
        r = subprocess.run(["git", "-C", self.origin, "rev-parse", "-q", "--verify", "refs/heads/" + branch],
                           stdout=subprocess.PIPE, universal_newlines=True)
        return r.stdout.strip()

    def test_branch_commit_pushed_and_logged(self):
        self.commit("a", env={"AUTO_PUSH": "0"})
        self.git("checkout", "-q", "-b", "work")
        sha = self.commit("b")
        self.assertEqual(self.remote_sha("work"), sha)
        self.assertIn("pushed work", open(os.path.join(self.repo, ".git", "autopush.log")).read())

    def test_main_never_pushed(self):
        self.commit("a")
        self.assertEqual(self.remote_sha("main", wait=1.0), "")

    def test_auto_push_off(self):
        self.git("checkout", "-q", "-b", "work")
        self.commit("a", env={"AUTO_PUSH": "0"})
        self.assertEqual(self.remote_sha("work", wait=1.0), "")


if __name__ == "__main__":
    unittest.main()

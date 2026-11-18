"""TASK-150 (REQ-0156): delete guard hook + clean-work.sh. Pure checks and temp dirs only, nothing real deleted."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, ".claude", "hooks"))
import delete_guard as G  # noqa: E402

REPO = "/srv/repo"  # a path that does not exist: realpath keeps it, nothing on disk is touched
ENV = {"HOME": "/home/u"}

DENY = [
    # the incident shapes (RAW-00377/00378): cleaning ./work with rm went wrong
    'rm -rf "$W"/*',
    "rm -rf $WORKDIR/",
    "cd work/TASK-1 && rm -rf ../..",
    "cd work && rm -rf ..",
    "rm -rf ./*",
    "rm -rf *",
    "rm -rf .",
    "rm -rf /srv/repo",
    "cd .. && rm -rf repo",
    "rm -rf $(pwd)",
    "rm -rf `pwd`/work",
    "ls | xargs rm -rf",
    "rm -rf",
    "rm -rf /",
    "rm -rf ~",
    "rm -rf ~/",
    "rm -rf $HOME/*",
    "rm -rf ../other-repo",
    "rm -fr /srv/repo/../other",
    "sudo rm -rf /srv/repo",
    "bash -c 'rm -rf ~'",
    "sh -c \"cd /srv && rm -rf repo\"",
    "find . -delete",
    "find /srv/repo -name x -delete",
    "find . -exec rm -rf {} +",
    "git clean -fdx",
    "git clean -xdf work/",
    "git clean -fX",
    "git clean -f",
    "git -C /srv/repo clean -fd",
    "python3 -c 'import shutil; shutil.rmtree(p)'",
    "python3 -c \"import shutil; shutil.rmtree('/srv/repo')\"",
    "python3 - <<'EOF'\nimport shutil\nshutil.rmtree(root)\nEOF",
    # unrecoverable data inside the repo (git-ignored)
    "rm -rf plans/dgnl2025",
    "rm -rf reports",
    "rm reports/x.md",
    "rm -f input/dgnl/a.pdf",
    "rm -rf .git",
    "rm -rf results/*",
    "unlink plans/x/plan.json",
    "cd plans && rm -rf dgnl2025",
    "for d in a b; do rm -rf $d; done",
    "rm -rf p*",
    "rm -rf r?ports",
    "rm -rf /tmp/*",
    "rm -rf /srv/*",
]

ALLOW = [
    "rm -rf work/TASK-1/x",
    "rm -rf work/*",
    "rm -rf work/TASK-1/*.tmp",
    "cd work/TASK-1 && rm -rf out",
    "rm -rf src/old_pkg",
    "rm -rf tests/fixtures/tmp_case",
    "rm tools/x.py",
    "rm -f docs/report/x.md",
    'rm -f "$F"',
    "S=/tmp/claude-1/s; rm -rf $S/a",
    "S=/tmp/claude-1/s && rm -rf \"$S\"/a \"$S\"/b",
    "rm -rf /tmp/exam_x",
    "rm -rf /tmp/exam_chrome_*",
    "cat > f <<'EOF'\nrm -rf /\nEOF\necho ok",
    "echo 'rm -rf /'",
    "grep -n 'rm -rf' x.sh",
    "ls 2>&1 | grep rm",
    "git clean -n",
    "git clean -ndx",
    "git clean -fd work/TASK-1",
    "find work/TASK-1 -name '*.pyc' -delete",
    "find . -name '*.pyc'",
    "python3 - <<'EOF'\nimport shutil\nshutil.rmtree('work/TASK-1/a')\nEOF",
    "python3 -c \"import shutil; shutil.rmtree('/tmp/x')\"",
    "rmdir work/TASK-1/empty",
    "git rm --cached x",
    "bash .claude/scripts/clean-work.sh TASK-1",
    "rm -rf work/TASK-*",
    "rm -rf src/*.bak",
    "rm -rf build*",
]


class Guard(unittest.TestCase):
    def test_deny(self):
        for cmd in DENY:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(G.check(cmd, REPO, REPO, ENV), cmd)

    def test_allow(self):
        for cmd in ALLOW:
            with self.subTest(cmd=cmd):
                self.assertIsNone(G.check(cmd, REPO, REPO, ENV), cmd)

    def test_reason_names_the_cause(self):
        self.assertIn("unresolved variable", G.check('rm -rf "$W"/*', REPO, REPO, ENV))
        self.assertIn("plans/", G.check("rm -rf plans/x", REPO, REPO, ENV))
        self.assertIn("repo root", G.check("rm -rf ./*", REPO, REPO, ENV))

    def test_split_keeps_heredoc_apart(self):
        parts = G.split_commands("python3 - <<'EOF' | tail -1\nx = 1\nEOF\nrm -rf a")
        self.assertEqual([p[0] for p in parts], ["python3 -", "tail -1", "rm -rf a"])
        self.assertEqual(parts[0][1], ["x = 1"])

    def run_main(self, payload):
        out = io.StringIO()
        old = sys.stdin
        sys.stdin = io.StringIO(json.dumps(payload))
        try:
            with redirect_stdout(out):
                self.assertEqual(G.main(), 0)
        finally:
            sys.stdin = old
        return out.getvalue()

    def test_hook_json_deny_and_allow(self):
        out = self.run_main({"tool_name": "Bash", "cwd": G.REPO, "tool_input": {"command": "rm -rf ./*"}})
        d = json.loads(out)["hookSpecificOutput"]
        self.assertEqual((d["hookEventName"], d["permissionDecision"]), ("PreToolUse", "deny"))
        self.assertIn("clean-work.sh", d["permissionDecisionReason"])
        self.assertEqual(self.run_main({"tool_name": "Bash", "cwd": G.REPO,
                                        "tool_input": {"command": "rm -rf work/TASK-1/x"}}), "")
        self.assertEqual(self.run_main({"tool_name": "Read", "tool_input": {"file_path": "x"}}), "")

    def test_internal_error_allows(self):
        orig = G.check
        G.check = lambda *a, **k: 1 / 0
        try:
            self.assertEqual(self.run_main({"tool_name": "Bash", "cwd": "/", "tool_input": {"command": "rm x"}}), "")
        finally:
            G.check = orig


class CleanWork(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(os.path.join(self.root, ".claude", "scripts"))
        shutil.copy(os.path.join(ROOT, ".claude", "scripts", "clean-work.sh"),
                    os.path.join(self.root, ".claude", "scripts"))
        for d in ("work/TASK-1/a", "src", "outside"):
            os.makedirs(os.path.join(self.root, d))
        os.symlink(os.path.join(self.root, "outside"), os.path.join(self.root, "work", "TASK-1", "link"))

    def run_cw(self, *args):
        return subprocess.run(["bash", os.path.join(self.root, ".claude", "scripts", "clean-work.sh")] + list(args),
                              cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)

    def test_deletes_task_dir_only(self):
        r = self.run_cw("TASK-1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.root, "work", "TASK-1")))
        self.assertTrue(os.path.isdir(os.path.join(self.root, "work")))
        self.assertTrue(os.path.isdir(os.path.join(self.root, "outside")))  # symlink target untouched

    def test_refuses_escapes(self):
        for arg in ("work", "work/..", ".", "src", "work/TASK-1/../../src", "/etc", "work/TASK-1/link/x"):
            with self.subTest(arg=arg):
                r = self.run_cw(arg)
                self.assertEqual(r.returncode, 1, (arg, r.stdout))
                self.assertIn("REFUSED", r.stderr)
        self.assertTrue(os.path.isdir(os.path.join(self.root, "src")))

    def test_dry_run_and_usage(self):
        r = self.run_cw("--dry-run", "work/TASK-1/a")
        self.assertIn("WOULD DELETE", r.stdout)
        self.assertTrue(os.path.isdir(os.path.join(self.root, "work", "TASK-1", "a")))
        self.assertEqual(self.run_cw().returncode, 2)


if __name__ == "__main__":
    unittest.main()

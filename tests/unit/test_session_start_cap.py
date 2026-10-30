"""REQ-0006 AC2: SessionStart output is capped at 2000 bytes on any state."""
import os
import shutil
import subprocess
import tempfile
import unittest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     ".claude", "hooks")


class Cap(unittest.TestCase):
    def run_hook(self, body):
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(HOOKS, "session-start.sh"), d)
            with open(os.path.join(d, "session-start-body.sh"), "w") as fh:
                fh.write(body)
            p = subprocess.run(["bash", os.path.join(d, "session-start.sh")], input=b"{}",
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        return p.returncode, p.stdout

    def test_200_tasks_capped_with_note(self):
        rc, out = self.run_hook('for i in $(seq 1 200); do echo "TASK-$i active some long title text"; done\n')
        self.assertEqual(rc, 0)
        self.assertLessEqual(len(out), 2000)
        self.assertIn(b"[truncated", out)
        self.assertTrue(out.startswith(b"TASK-1 "))

    def test_small_output_unchanged(self):
        rc, out = self.run_hook("echo hello\n")
        self.assertEqual((rc, out), (0, b"hello\n"))

    def test_body_failure_still_exit_0(self):
        rc, _ = self.run_hook("exit 7\n")
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

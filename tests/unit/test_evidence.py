"""TASK-057 57.3/57.4/57.6/57.7: _evidence.py scan/publish/index, _tasks._path_ok, workflow-check gates."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO, ".claude", "scripts")
sys.path.insert(0, SCRIPTS)
sys.dont_write_bytecode = True
import _evidence as ev  # noqa: E402


def rules(text, name="x.txt"):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, name)
        with open(p, "wb") as f:
            f.write(text if isinstance(text, bytes) else text.encode("utf-8"))
        return sorted({r for _, _, r in ev.scan_file(p)})


class ScanRules(unittest.TestCase):
    def test_binary(self):
        self.assertIn("binary", rules(b"ab\x00cd"))
        self.assertIn("binary", rules(b"\xff\xfe\xfa"))
        self.assertEqual(rules("plain text\n"), [])

    def test_ext(self):
        self.assertIn("ext", rules("ok\n", "x.png"))
        self.assertNotIn("ext", rules("ok\n", "x.tsv"))

    def test_size(self):
        self.assertIn("size", rules("l\n" * 201))
        self.assertIn("size", rules("x" * 33000))
        self.assertNotIn("size", rules("l\n" * 200))

    def test_exam_heading(self):
        self.assertIn("exam-heading", rules("## Question 1\nfoo\n"))
        self.assertIn("exam-heading", rules("# Câu 3\n"))
        self.assertNotIn("exam-heading", rules("## Questions per group\n"))

    def test_options(self):
        self.assertIn("options", rules("stem\nA. one\nB. two\nC. three\nD. four\n"))
        self.assertIn("options", rules("A) one\nB) two\n"))
        self.assertNotIn("options", rules("Option A. and B. differ in one line\n"))
        self.assertNotIn("options", rules("A. one\n" + "pad\n" * 8 + "B. two\n"))

    def test_answer_line(self):
        self.assertIn("answer-line", rules("Final answer: B\n"))
        self.assertIn("answer-line", rules("Đáp án: C\n"))
        self.assertNotIn("answer-line", rules("the answer file lists letters\n"))

    def test_answer_json(self):
        self.assertIn("answer-json", rules('{"answer": "B"}\n'))
        self.assertIn("answer-json", rules('{"answer": "a-c"}\n'))
        self.assertNotIn("answer-json", rules('{"answer": null}\n'))

    def test_answer_tsv(self):
        self.assertIn("answer-tsv", rules("1\tA\n2\tB\n3\tC\n"))
        self.assertNotIn("answer-tsv", rules("1\tA\n2\tB\n"))

    def test_url(self):
        self.assertIn("url", rules("see https://example.com/x\n"))
        self.assertNotIn("url", rules("see example.com\n"))

    def test_secret(self):
        self.assertIn("secret", rules("key sk-" + "a" * 24 + "\n"))
        self.assertIn("secret", rules("AKIA" + "A" * 16 + "\n"))
        self.assertIn("secret", rules("password = hunter2hunter2\n"))
        self.assertNotIn("secret", rules("TASK-054 and task-sk-short\n"))

    def test_private_dir(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "reports", "x"))
            p = os.path.join(d, "reports", "x", "a.txt")
            with open(p, "w") as f:
                f.write("ok\n")
            self.assertEqual([r for _, _, r in ev.scan_file(p)], ["private-dir"])
            self.assertTrue(ev.private_dir("plans/x.txt"))
            self.assertFalse(ev.private_dir("docs/report/evidence/TASK-1/a.txt"))

    def test_dir_limits(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(21):
                with open(os.path.join(d, "f%d.txt" % i), "w") as f:
                    f.write("ok\n")
            self.assertIn("size", {r for _, _, r in ev.scan_paths([d])})


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = self.tmp
        for d in ("work/TASK-9/evidence", "work/TASK-9/handoff", "docs/report", ".claude/state", "docs/design"):
            os.makedirs(os.path.join(self.root, d))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def w(self, rel, text):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return rel


class Publish(Fixture):
    def test_copy_idempotent_and_redact(self):
        self.w("work/TASK-9/evidence/a.txt", "run in %s/x and /home/bob/y\n" % self.root)
        dests, errs = ev.publish(self.root, "TASK-9", ["work/TASK-9/evidence/a.txt"])
        self.assertEqual((dests, errs), (["docs/report/evidence/TASK-9/a.txt"], []))
        out = ev._read(os.path.join(self.root, dests[0]))
        self.assertNotIn(self.root, out)
        self.assertNotIn("bob", out)
        m1 = os.stat(os.path.join(self.root, dests[0])).st_mtime_ns
        ev.publish(self.root, "TASK-9", ["work/TASK-9/evidence/a.txt"])
        self.assertEqual(m1, os.stat(os.path.join(self.root, dests[0])).st_mtime_ns)

    def test_refuses_src_outside_and_bad_name(self):
        self.w("other/a.txt", "x\n")
        self.w("work/TASK-9/evidence/bad name.txt", "x\n")
        for s in ("other/a.txt", "work/TASK-9/evidence/bad name.txt", "work/TASK-9/../../etc/passwd"):
            dests, errs = ev.publish(self.root, "TASK-9", [s])
            self.assertEqual(dests, [])
            self.assertTrue(errs, s)

    def test_refuses_private_dir_src(self):
        self.w("work/TASK-9/reports/a.txt", "x\n")
        dests, errs = ev.publish(self.root, "TASK-9", ["work/TASK-9/reports/a.txt", "plans/a.txt"])
        self.assertEqual(dests, [])
        self.assertEqual(sum("private-dir" in e for e in errs), 2)

    def test_all_or_nothing(self):
        self.w("work/TASK-9/evidence/good.txt", "fine\n")
        self.w("work/TASK-9/evidence/bad.txt", "see https://x.example\n")
        dests, errs = ev.publish(self.root, "TASK-9", ["work/TASK-9/evidence/good.txt",
                                                       "work/TASK-9/evidence/bad.txt"])
        self.assertEqual(dests, [])
        self.assertTrue(any("url" in e for e in errs))
        self.assertFalse(os.path.exists(os.path.join(self.root, "docs/report/evidence/TASK-9/good.txt")))


class Index(Fixture):
    def setUp(self):
        Fixture.setUp(self)
        bl = [{"task_id": "TASK-8", "title": "Done one", "status": "done", "report": "docs/report/phase-8-x.md"},
              {"task_id": "TASK-9", "title": "Active with evidence", "status": "active"},
              {"task_id": "TASK-7", "title": "Todo", "status": "todo"}]
        self.w(".claude/state/backlog.json", json.dumps(bl))
        self.w("docs/report/phase-8-x.md", "run-history at reports/run-history.jsonl\n")
        self.w("docs/design/phase-8-x.md", "d\n")
        self.w("docs/report/evidence/TASK-9/a.txt", "ok\n")

    def test_rows_deterministic_check(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self._rows()

    def _rows(self):
        self.assertEqual(ev.index(self.root, False), 0)
        p = os.path.join(self.root, "docs/report/INDEX.md")
        a = ev._read(p)
        self.assertEqual(ev.index(self.root, False), 0)
        self.assertEqual(a, ev._read(p))
        rows = [l for l in a.splitlines() if l.startswith("| TASK-")]
        self.assertEqual([r.split()[1] for r in rows], ["TASK-8", "TASK-9"])
        self.assertIn("docs/report/evidence/TASK-9/ (1)", rows[1])
        self.assertIn("reports/run-history.jsonl", rows[0])
        self.assertEqual(ev.index(self.root, True), 0)
        with open(p, "a") as f:
            f.write("hand edit\n")
        self.assertEqual(ev.index(self.root, True), 1)


class PathOk(unittest.TestCase):
    def test_scope(self):
        import _tasks
        self.assertTrue(_tasks._path_ok("TASK-057", "docs/report/evidence/TASK-057/x.txt"))
        self.assertTrue(_tasks._path_ok("TASK-057", "docs/report/INDEX.md"))
        self.assertFalse(_tasks._path_ok("TASK-057", "docs/report/evidence/TASK-056/x.txt"))
        self.assertFalse(_tasks._path_ok("TASK-057", "docs/report/evidence/TASK-0570/x.txt"))


class Calibration(unittest.TestCase):
    def test_current_evidence_passes(self):
        d = os.path.join(REPO, "docs", "report", "evidence")
        r = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "_evidence.py"), "scan", d],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class WorkflowCheck(Fixture):
    """Gate cases run workflow-check.sh in a throwaway git repo."""

    def run_wc(self, task, extra=None):
        shutil.copytree(os.path.join(REPO, ".claude", "scripts"), os.path.join(self.root, ".claude", "scripts"),
                        ignore=shutil.ignore_patterns("checks", "__pycache__"))
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        t = {"task_id": "TASK-9", "state": task.pop("state"), "evidence_required": task.pop("evidence_required", None),
             "design": {"status": "completed", "path": "docs/design/phase-9-x.md"},
             "implementation": {"status": "completed", "files": ["a"]},
             "unit_test": {"status": "passed", "command": "c", "result": "r"},
             "security": {"status": "completed", "result": "r"},
             "report": {"status": "completed", "path": "docs/report/phase-9-x.md"}}
        t = {k: v for k, v in t.items() if v is not None}
        t.update(task)
        self.w(".claude/state/task.TASK-9.json", json.dumps(t))
        self.w(".claude/state/task.json", json.dumps(dict(t, schema=2, active=[{"task_id": "TASK-9", "state": t["state"]}])))
        self.w(".claude/state/backlog.json", json.dumps([{"task_id": "TASK-9", "title": "t", "status": "active"}]))
        self.w("docs/design/phase-9-x.md", "d\n")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.root, TASKS_ROOT=self.root)
        return subprocess.run(["bash", os.path.join(self.root, ".claude/scripts/workflow-check.sh"),
                               "--task", "TASK-9"], capture_output=True, text=True, env=env, cwd=self.root)

    def test_flagged_verified_needs_published(self):
        r = self.run_wc({"state": "VERIFIED", "evidence_required": True,
                         "verification": {"status": "passed", "evidence": ["work/TASK-9/e.txt"]}})
        self.assertIn("published", r.stdout)
        self.assertIn("FAIL", r.stdout)

    def test_unflagged_warn_only(self):
        r = self.run_wc({"state": "VERIFIED",
                         "verification": {"status": "passed", "evidence": ["work/TASK-9/e.txt"]}})
        self.assertNotIn("published", "\n".join(l for l in r.stdout.splitlines() if l.startswith("FAIL")))
        self.assertIn("WARN: no published evidence", r.stdout)

    def test_flagged_scan_fail(self):
        self.w("docs/report/evidence/TASK-9/a.txt", "see https://x.example\n")
        r = self.run_wc({"state": "VERIFIED", "evidence_required": True,
                         "verification": {"status": "passed", "evidence": ["e"],
                                          "published": ["docs/report/evidence/TASK-9/a.txt"]}})
        self.assertIn("FAIL: evidence scan", r.stdout)


if __name__ == "__main__":
    unittest.main()

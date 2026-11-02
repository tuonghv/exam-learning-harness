"""TASK-058 58.1/58.2/58.5/58.8: raw call capture and the plan run written by solve. Mock LLM only."""
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli, engine  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.pipeline import planrun  # noqa: E402

EXAM = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def rd(p, mode="r"):
    with open(p, mode) as fh:
        return fh.read()


class PlanRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        shutil.copy(os.path.join(ROOT, ".gitignore"), os.path.join(self.tmp, ".gitignore"))
        for args in (("init", "-q"), ("add", ".gitignore"), ("commit", "-qm", "i")):
            subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=t"] + list(args),
                           cwd=self.tmp, check=True, capture_output=True)
        os.chdir(self.tmp)

    def solve(self, *extra, mock=MOCK):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return cli.solve_main([EXAM, "--mock", mock] + list(extra))

    def plan_dir(self):
        base = os.path.join(self.tmp, "plans", "input-001")
        runs = os.listdir(base)
        self.assertEqual(len(runs), 1)
        return os.path.join(base, runs[0])

    def test_calls_captured_and_consistent(self):
        self.solve("--key", os.path.join(ROOT, "examples", "english", "expected-001.md"))
        d = self.plan_dir()
        plan = json.loads(rd(os.path.join(d, "plan.json")))
        res = json.loads(rd(os.path.join(d, "result.json")))
        self.assertEqual(plan["status"], "done")
        self.assertEqual(plan["calls"], res["run"]["calls"])
        self.assertTrue(plan["calls_captured"])
        self.assertEqual(plan["prompt"], res["run"]["prompt"])
        self.assertTrue(plan["config_sha256"])
        idx = [json.loads(x) for x in rd(os.path.join(d, "calls", "index.jsonl")).splitlines()]
        self.assertEqual(len(idx), res["run"]["calls"])
        self.assertEqual(idx[0]["tag"], "solve")
        for e in idx:
            self.assertIn(e["tag"], ("solve", "retry", "qa"))
            n = "%03d" % e["n"]
            self.assertEqual(sha(rd(os.path.join(d, "calls", n + "-prompt.txt"), "rb")), e["prompt_sha256"])
            self.assertEqual(e["reply_bytes"], len(rd(os.path.join(d, "calls", n + "-reply.txt"), "rb")))
        self.assertEqual(rd(os.path.join(d, "input", "exam.md"), "rb"), rd(EXAM, "rb"))
        cfg = json.loads(rd(os.path.join(d, "config.json")))
        self.assertEqual(cfg["key"]["sha256"], sha(rd(os.path.join(ROOT, "examples", "english", "expected-001.md"), "rb")))
        self.assertNotIn("Question", json.dumps(cfg))

    def test_git_status_clean_without_out(self):
        self.assertIn(self.solve(), (0, 1))
        self.assertTrue(os.path.isfile(os.path.join(self.plan_dir(), "result.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.plan_dir(), "report.md")))
        self.assertEqual(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout, "")

    def test_out_honoured_and_plan_inside(self):
        self.solve("--out", "mine")
        self.assertTrue(os.path.isfile(os.path.join("mine", "plan.json")))
        self.assertTrue(os.path.isfile(os.path.join("mine", "calls", "001-reply.txt")))
        self.assertFalse(os.path.exists("plans"))

    def test_crash_mid_run_keeps_calls(self):
        n = [0]
        inner = engine.mock_llm(MOCK)

        def llm(prompt):
            n[0] += 1
            if n[0] == 2:
                raise RuntimeError("boom")
            return inner(prompt)
        orig = engine.mock_llm
        engine.mock_llm = lambda p: llm
        self.addCleanup(setattr, engine, "mock_llm", orig)
        with self.assertRaises(RuntimeError):
            self.solve()
        d = self.plan_dir()
        plan = json.loads(rd(os.path.join(d, "plan.json")))
        self.assertEqual(plan["status"], "failed")
        self.assertTrue(os.path.isfile(os.path.join(d, "calls", "001-prompt.txt")))
        self.assertTrue(os.path.isfile(os.path.join(d, "calls", "001-reply.txt")))
        self.assertEqual(len(rd(os.path.join(d, "calls", "index.jsonl")).splitlines()), 1)

    def test_reply_masked_sha_unmasked(self):
        tok = "sk-" + "a" * 20
        d = os.path.join(self.tmp, "p")
        w = planrun.PlanWriter(d, EXAM, {"model": "m", "llm_name": "mock", "key": None})
        w.start()
        w.record(1, "solve", "prompt", claude.Call(True, "x " + tok, 0.0, "", "", 0.0))
        self.assertNotIn(tok, rd(os.path.join(d, "calls", "001-reply.txt")))
        e = json.loads(rd(os.path.join(d, "calls", "index.jsonl")))
        self.assertEqual(e["reply_sha256"], sha(("x " + tok).encode()))
        self.assertEqual(json.loads(rd(os.path.join(d, "plan.json")))["status"], "running")

    def test_capture_failure_warns_not_raises(self):
        w = planrun.PlanWriter(os.path.join(self.tmp, "nodir"), EXAM, {"key": None})
        w.record(1, "solve", "p", claude.Call(True, "r", 0.0, "", "", 0.0))  # start() never ran
        self.assertFalse(w.ok)

    def test_claim_run_dir_unique_under_race(self):
        root = os.path.join(self.tmp, "plans")
        got, lock = [], threading.Lock()

        def go():
            p = planrun.claim_run_dir(root, "e")
            with lock:
                got.append(p)
        ts = [threading.Thread(target=go) for _ in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(len(set(got)), 8)

    def test_history_path_and_plan_dir(self):
        self.assertEqual(cli.DEFAULT_HISTORY, os.path.join("plans", "run-history.jsonl"))
        self.assertEqual(len(cli.LEGACY_HISTORY), 2)
        self.solve("--history", "plans/run-history.jsonl")
        line = json.loads(rd("plans/run-history.jsonl").splitlines()[0])
        self.assertEqual(line["plan_dir"], os.path.realpath(self.plan_dir()))

    def test_legacy_histories_both_read(self):
        for i, p in enumerate(cli.LEGACY_HISTORY):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write(json.dumps({"run_id": p, "exam_id": "x", "ts": "2026-01-0%dT00:00:00Z" % (i + 1),
                                    "metrics": {}}) + "\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            cli.run_stats_main(["trend", "--exam-id", "x", "--json"])
        for ts in ("2026-01-01T", "2026-01-02T"):
            self.assertIn(ts, buf.getvalue())


if __name__ == "__main__":
    unittest.main()

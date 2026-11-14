"""TASK-058 QA gate: crash safety (D-4), distinct ids (D-2), solve/report parity (D-3), masking via the engine.
Mock LLM only."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli, engine  # noqa: E402
from exam_engine.pipeline import report_kinds as rk  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.pipeline import planrun, reporter  # noqa: E402

EXAM = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")


def quiet(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a)


def rd(p, mode="r"):
    with open(p, mode) as fh:
        return fh.read()



class PlanQA(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.tmp)
        p = mock.patch.object(reporter, "git_info", return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def runs(self):
        base = os.path.join(self.tmp, "plans", "input-001", "main", "runs")
        return sorted(os.path.join(base, r) for r in os.listdir(base))

    def _crash_at(self, k, exc):
        real = engine.mock_llm
        n = [0]

        def factory(path):
            inner = real(path)

            def llm(prompt):
                n[0] += 1
                if n[0] == k:
                    raise exc
                return inner(prompt)
            return llm
        with mock.patch.object(engine, "mock_llm", factory):
            with self.assertRaises(type(exc)):
                quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"])

    def test_58_2_crash_keeps_every_call_made_so_far(self):
        self._crash_at(2, RuntimeError("boom"))
        (d,) = self.runs()
        self.assertEqual(json.loads(rd(os.path.join(d, "plan.json")))["status"], "failed")
        self.assertEqual(len(rd(os.path.join(d, "calls", "index.jsonl")).splitlines()), 1)
        self.assertTrue(rd(os.path.join(d, "calls", "001-prompt.txt")))
        self.assertTrue(rd(os.path.join(d, "calls", "001-reply.txt")))
        self.assertFalse(os.path.exists(os.path.join(d, "calls", "002-reply.txt")))
        self.assertFalse(os.path.exists(os.path.join(d, "result.json")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "reports")))

    def test_58_2_keyboard_interrupt_keeps_plan_json(self):
        self._crash_at(2, KeyboardInterrupt())
        (d,) = self.runs()
        self.assertTrue(os.path.isfile(os.path.join(d, "plan.json")))
        self.assertEqual(len(rd(os.path.join(d, "calls", "index.jsonl")).splitlines()), 1)

    def test_58_2_plan_json_exists_before_first_call(self):
        seen = []
        real = engine.mock_llm

        def factory(path):
            inner = real(path)

            def llm(prompt):
                base = os.path.join(self.tmp, "plans", "input-001", "main", "runs")
                seen.append(os.path.isfile(os.path.join(base, os.listdir(base)[0], "plan.json")))
                return inner(prompt)
            return llm
        with mock.patch.object(engine, "mock_llm", factory):
            quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"])
        self.assertTrue(seen and all(seen))

    def test_58_2_distinct_run_ids_same_second(self):
        with mock.patch.object(time, "gmtime", return_value=time.gmtime(0)):
            for _ in range(3):
                quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"])
        names = [os.path.basename(d) for d in self.runs()]
        self.assertEqual(len(set(names)), 3, names)
        for d in self.runs():
            self.assertTrue(os.path.isfile(os.path.join(d, "result.json")))
        reps = os.listdir(os.path.join(self.tmp, "reports", "input-001", "main"))
        self.assertEqual(sorted(r[len("run-"):] for r in reps if r.startswith("run-")), sorted(names))

    def test_58_4_solve_and_report_same_metrics_and_text(self):
        flat = os.path.join(self.tmp, "flat")
        quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--out", flat])
        self.assertEqual(quiet(cli.report_main, [flat, "--no-pdf", "--out", os.path.join(self.tmp, "r")]), 0)
        quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"])
        (d,) = self.runs()
        dflt = os.path.join(self.tmp, "reports", "input-001", "main", "run-" + os.path.basename(d))
        for other in (os.path.join(self.tmp, "r"), dflt):
            for kind in ("solution-report", "answer-sheet"):
                self.assertEqual(rd(rk.find(flat, kind)), rd(rk.find(other, kind)), kind)
        md = rd(rk.find(flat, "solution-report"))
        self.assertIn("## Metrics", md)
        for other in (os.path.join(self.tmp, "r"), dflt):
            self.assertIsNone(rk.find(other, "metrics", ext="json"))  # TASK-101: only the md Metrics block

    def test_58_1_token_in_reply_masked_in_calls_through_engine(self):
        tok = "sk-ant-" + "b" * 30
        real = engine.mock_llm

        def factory(path):
            inner = real(path)

            def llm(prompt):
                c = inner(prompt)
                return c._replace(text=c.text + " " + tok)
            return llm
        with mock.patch.object(engine, "mock_llm", factory):
            quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"])
        (d,) = self.runs()
        blob = "".join(rd(os.path.join(d, "calls", f)) for f in os.listdir(os.path.join(d, "calls")))
        self.assertNotIn(tok, blob)
        e = json.loads(rd(os.path.join(d, "calls", "index.jsonl")).splitlines()[0])
        self.assertTrue(e["reply_sha256"])


if __name__ == "__main__":
    unittest.main()

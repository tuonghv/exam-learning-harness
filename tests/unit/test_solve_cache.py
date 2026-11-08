"""TASK-083 83.1-83.5 (REQ-0089): per-exam solve cache. Fake llm counting calls; tmp dirs; no paid calls."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli, engine  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.ingest.replycache import ReplyCache  # noqa: E402
from exam_engine.pipeline import planrun, solver  # noqa: E402

HEAD = "# Exam Input\n\nSubject: Mathematics\nLevel: Grade 12\nExam type: Test\nTask: Short Answer\nMode: Solve\n\n"
EXAM = HEAD + "## Instructions\n\nSolve.\n\n## Question 1\n\nCompute 2*sqrt(3).\n\n## Question 2\n\nCompute 3+4.\n"
PIN = "claude-sonnet-5-5"
KEYSTR = "ZZ-SOLVE-CACHE-KEY-SENTINEL-77"


def solve_json(text="x"):
    qs = [{"id": str(i), "type": "x", "answer": "A" + text, "answer_status": "answered", "solution": ["s"],
           "explanation": "e", "checks": [], "expr": None, "evidence": [],
           "uncertainty": {"level": "low", "reason": "r"},
           "reasoning_status": "not_independently_verified", "issues": []} for i in (1, 2)]
    return json.dumps({"schema_version": "1.0", "questions": qs, "input_issues": []})


class Fake(object):
    def __init__(self, cost=0.01):
        self.prompts, self.cost = [], cost

    def __call__(self, prompt, **kw):
        self.prompts.append(prompt)
        return claude.Call(True, solve_json(), self.cost, "", "", 0.0)


def cfg(**kw):
    c = {"max_attempts": 2, "max_cost_usd": 5.0, "timeout": 5, "model": PIN, "key": None, "llm_name": "claude-p"}
    c.update(kw)
    return c


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="solve_cache_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.tmp)
        g = mock.patch("exam_engine.pipeline.reporter.git_info", return_value=None)
        g.start()
        self.addCleanup(g.stop)
        self.exam = self.write("exam-a.md", EXAM)

    def write(self, name, text):
        p = os.path.join(self.tmp, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def rd(self, p):
        with open(p, encoding="utf-8") as fh:
            return fh.read()

    def run_engine(self, llm, cache, out, exam=None, **kw):
        ck = {k: kw.pop(k) for k in ("fresh",) if k in kw}
        with contextlib.redirect_stderr(io.StringIO()):
            return engine.run(exam or self.exam, out, cfg(**kw), llm, reports=False, cache=cache, **ck)

    def cli(self, *argv, llm=None, tty=False):
        llm = llm or Fake()
        o, e = io.StringIO(), io.StringIO()
        with mock.patch.object(claude, "run_claude", llm), \
                mock.patch.object(sys.stdin, "isatty", return_value=tty), \
                contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            code = cli.solve_main([self.exam, "--real", "--model", PIN, "--no-pdf"] + list(argv))
        return code, o.getvalue(), e.getvalue(), llm

    def plans(self, eid="exam-a"):
        base = os.path.join(self.tmp, "plans", eid, "runs")
        return sorted(os.listdir(base)) if os.path.isdir(base) else []


class T1HitSkipsLlm(Base):
    def test_1_second_run_zero_calls_identical_answers(self):  # AC1, AC9
        cache = ReplyCache(os.path.join(self.tmp, "c"))
        l1, l2 = Fake(), Fake()
        r1, _ = self.run_engine(l1, cache, os.path.join(self.tmp, "o1"))
        r2, _ = self.run_engine(l2, cache, os.path.join(self.tmp, "o2"))
        self.assertGreater(len(l1.prompts), 0)
        self.assertEqual(len(l2.prompts), 0)
        self.assertEqual(r1["questions"], r2["questions"])
        self.assertEqual(r2["run"]["cached"], len(l1.prompts))
        self.assertEqual(r2["run"]["calls"], 0)
        self.assertEqual(r1["run"]["cached"], 0)

    def test_1_index_rows_cached_true(self):
        self.assertIn(self.cli()[0], (0, 1))
        code, _, err, l2 = self.cli("--yes")
        self.assertEqual(len(l2.prompts), 0, err)
        self.assertIn(code, (0, 1))
        d = os.path.join(self.tmp, "plans", "exam-a", "runs", self.plans()[-1])
        with open(os.path.join(d, "calls", "index.jsonl"), encoding="utf-8") as fh:
            rows = [json.loads(x) for x in fh if x.strip()]
        self.assertTrue(rows)
        self.assertTrue(all(r.get("cached") is True for r in rows))


class T2KeyChanges(Base):
    def prime(self):
        cache = ReplyCache(os.path.join(self.tmp, "c"))
        l1 = Fake()
        self.run_engine(l1, cache, os.path.join(self.tmp, "o1"))
        return cache, len(l1.prompts)

    def test_2_model_change_calls_again(self):  # AC2
        cache, n = self.prime()
        l2 = Fake()
        self.run_engine(l2, cache, os.path.join(self.tmp, "o2"), model="claude-opus-4-5")
        self.assertEqual(len(l2.prompts), n)

    def test_2_prompt_byte_change_calls_again(self):
        cache, n = self.prime()
        orig = solver.base_prompt
        l2 = Fake()
        with mock.patch.object(solver, "base_prompt", lambda ex: orig(ex) + " "):
            self.run_engine(l2, cache, os.path.join(self.tmp, "o2"))
        self.assertGreater(len(l2.prompts), 0)

    def test_2_question_text_change_calls_again(self):
        cache, n = self.prime()
        other = self.write("exam-a2.md", EXAM.replace("3+4", "3+5"))
        l2 = Fake()
        self.run_engine(l2, cache, os.path.join(self.tmp, "o2"), exam=other)
        self.assertGreater(len(l2.prompts), 0)


class T3Pinned(Base):
    def test_3_pinned_table(self):  # AC3
        pins = {"sonnet": PIN}
        for m in ("sonnet", "opus", "haiku", "claude-x-latest", "claude-sonnet", ""):
            self.assertFalse(claude.pinned(m, pins)[0], m)
        for m in (PIN, "claude-haiku-4-5", "claude-opus-4-5"):
            self.assertTrue(claude.pinned(m, pins)[0], m)
        self.assertEqual(claude.pinned("sonnet", pins), (False, "--model " + PIN))

    def test_3_cli_alias_exit_2_no_plans_dir(self):
        o, e = io.StringIO(), io.StringIO()
        fake = Fake()
        with mock.patch.object(claude, "run_claude", fake), contextlib.redirect_stdout(o), \
                contextlib.redirect_stderr(e):
            code = cli.solve_main([self.exam, "--real", "--model", "sonnet", "--no-pdf"])
        self.assertEqual(code, 2)
        self.assertIn(PIN, e.getvalue())
        self.assertEqual(fake.prompts, [])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "plans")))


class T4Rerun(Base):
    def test_4_refuse_yes_fresh_and_other_sha(self):  # AC4
        self.assertIn(self.cli()[0], (0, 1))
        n_first = len(self.plans())
        code, _, err, l = self.cli()
        self.assertEqual((code, len(l.prompts)), (2, 0))
        self.assertIn("--yes", err)
        self.assertIn("model=" + PIN, err)
        self.assertIn("cost=", err)
        self.assertRegex(err, r"20\d\d-\d\d-\d\d")  # when
        self.assertEqual(len(self.plans()), n_first)  # refused: no new plan dir
        code, _, _, l = self.cli("--yes")
        self.assertEqual(len(l.prompts), 0)  # cache read
        self.assertIn(code, (0, 1))
        code, _, _, l = self.cli("--fresh")
        self.assertIn(code, (0, 1))
        self.assertGreater(len(l.prompts), 0)  # cache not read
        self.write("exam-a.md", EXAM.replace("3+4", "3+9"))  # other sha, same id: no prompt
        code, _, err, l = self.cli()
        self.assertIn(code, (0, 1), err)
        self.assertNotIn("already solved", err)

    def test_4_last_solved(self):
        self.assertIsNone(planrun.last_solved("plans", self.exam))
        self.cli()
        got = planrun.last_solved("plans", self.exam)
        self.assertEqual(got["model"], PIN)
        self.assertGreater(got["calls"], 0)


class T5Corrupt(Base):
    def test_5_garbage_entries_are_misses(self):  # AC5
        self.cli()
        cdir = os.path.join(self.tmp, "plans", "exam-a", "cache")
        files = [f for f in os.listdir(cdir) if f.startswith("solve-")]
        self.assertTrue(files)
        for i, f in enumerate(files):
            with open(os.path.join(cdir, f), "w") as fh:
                fh.write("{not json" if i % 2 else json.dumps({"text": 5, "cost_usd": "x"}))
        code, _, _, l = self.cli("--yes")
        self.assertIn(code, (0, 1))
        self.assertEqual(len(l.prompts), len(files))  # every entry missed -> called again

    def test_5_metrics_and_block_cache_line(self):
        self.cli()
        self.cli("--yes")
        d = os.path.join(self.tmp, "plans", "exam-a", "runs", self.plans()[-1])
        with open(os.path.join(d, "result.json"), encoding="utf-8") as fh:
            res = json.load(fh)
        self.assertGreater(res["run"]["cached"], 0)
        self.assertGreater(res["run"]["cost_saved_usd"], 0)
        from exam_engine.pipeline import metrics
        m = metrics.compute(res)
        self.assertEqual(m["cost"]["cached"], res["run"]["cached"])
        self.assertIn("cost_saved_usd", m["cost"])
        self.assertIn("cache: hits=%d" % res["run"]["cached"], "\n".join(metrics.block(m)))


class T6Isolation(Base):
    def test_6_two_exams_two_cache_dirs(self):  # AC8
        self.cli()
        a_dir = os.path.join(self.tmp, "plans", "exam-a", "cache")
        before = sorted(os.listdir(a_dir))
        self.exam = self.write("exam-b.md", EXAM.replace("3+4", "5+6"))
        self.cli()
        b_dir = os.path.join(self.tmp, "plans", "exam-b", "cache")
        self.assertTrue(os.path.isdir(b_dir) and os.listdir(b_dir))
        self.assertEqual(sorted(os.listdir(a_dir)), before)
        self.assertFalse(set(os.listdir(a_dir)) & set(os.listdir(b_dir)))


class T7Key(Base):
    def test_7_key_content_and_path_not_in_cache(self):
        key = self.write("expected-a.md", "# Expected\n\n## Question 1\n\nAnswer: %s\n" % KEYSTR)
        self.cli("--key", key)
        cdir = os.path.join(self.tmp, "plans", "exam-a", "cache")
        for f in os.listdir(cdir):
            body = self.rd(os.path.join(cdir, f))
            self.assertNotIn(KEYSTR, body)
            self.assertNotIn(key, body)
        r, _ = self.run_engine(Fake(), ReplyCache(os.path.join(self.tmp, "c")), os.path.join(self.tmp, "o"),
                               key=key)
        for f in os.listdir(os.path.join(self.tmp, "c")):
            self.assertNotIn(KEYSTR, self.rd(os.path.join(self.tmp, "c", f)))


class T8Mock(Base):
    MOCK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")
    ENG = os.path.join(ROOT, "examples", "english", "input-001.md")

    def mock_run(self, out):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return cli.solve_main([self.ENG, "--mock", self.MOCK])

    def test_8_mock_never_creates_cache_and_has_no_new_fields(self):
        self.assertIn(self.mock_run(None), (0, 1))
        self.assertFalse([p for p in self._glob("cache")])
        d = os.path.join(self.tmp, "plans", "input-001", "runs")
        d = os.path.join(d, os.listdir(d)[0])
        with open(os.path.join(d, "result.json"), encoding="utf-8") as fh:
            res = json.load(fh)
        self.assertNotIn("cached", res["run"])
        self.assertNotIn("cost_saved_usd", res["run"])
        with open(os.path.join(d, "calls", "index.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                self.assertNotIn("cached", json.loads(line))

    def _glob(self, name):
        out = []
        for dp, dn, _ in os.walk(self.tmp):
            out += [os.path.join(dp, d) for d in dn if d == name and os.path.basename(dp) != "x"]
        return out


class T9Failed(Base):
    def test_1_failed_call_not_stored(self):
        bad = lambda prompt, **kw: claude.Call(False, "", 0.0, "auth", "401", 0.0)
        cache = ReplyCache(os.path.join(self.tmp, "c"))
        self.run_engine(bad, cache, os.path.join(self.tmp, "o1"))
        self.assertFalse(os.path.isdir(os.path.join(self.tmp, "c")) and os.listdir(os.path.join(self.tmp, "c")))


if __name__ == "__main__":
    unittest.main()

"""TASK-066 66.1-66.3: benchmark --set (keyed regression set); fake llm only, $0."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import benchmark, metrics  # noqa: E402

SRC = os.path.join(ROOT, "examples", "english")
ANSWER = json.load(open(os.path.join(HERE, "fixtures", "mock_english_001.json")))
SOLVE, QA = ANSWER[0], ANSWER[1]
KEYTEXT = "Correct answer: A. have"  # key text from expected-001.md


class RegSet(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name
        items = []
        for sub, basis in (("english", "official"), ("other", "generated: test")):
            d = os.path.join(self.root, sub)
            os.makedirs(d)
            shutil.copy(os.path.join(SRC, "input-001.md"), os.path.join(d, "in.md"))
            shutil.copy(os.path.join(SRC, "expected-001.md"), os.path.join(d, "key.md"))
            items.append({"id": sub + "/001", "input": os.path.join(d, "in.md"),
                          "key": os.path.join(d, "key.md"), "key_basis": basis})
        self.setfile = self.write({"v": 1, "set_id": "s1", "items": items})
        self.items = items
        self.hist = os.path.join(self.root, "h.jsonl")

    def write(self, obj, name="set.json"):
        p = os.path.join(self.root, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(obj if isinstance(obj, str) else json.dumps(obj))
        return p

    def mock(self, n=2, solve=SOLVE):
        return self.write([solve, QA] * n, "mock.json")

    def run_cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["benchmark"] + args)
        return code, out.getvalue(), err.getvalue()

    def test_history_lines_carry_regset_fields(self):
        code, out, err = self.run_cli(["--set", self.setfile, "--mock", self.mock(), "--out",
                                       os.path.join(self.root, "o"), "--history", self.hist])
        self.assertEqual(code, 0, out + err)
        lines, bad = metrics.read_history(self.hist)
        self.assertEqual(bad, 0)
        self.assertEqual(len(lines), 2)
        self.assertEqual([ln["source"] for ln in lines], ["regset", "regset"])
        self.assertEqual([ln["set_id"] for ln in lines], ["s1", "s1"])
        self.assertEqual([ln["key_basis"] for ln in lines], ["official", "generated: test"])
        for ln in lines:
            self.assertIn("kind", ln)
            self.assertIn("prompt", ln)
            self.assertIn("git", ln)

    def test_key_text_never_in_history(self):
        self.run_cli(["--set", self.setfile, "--mock", self.mock(), "--out",
                      os.path.join(self.root, "o"), "--history", self.hist])
        with open(self.hist, encoding="utf-8") as fh:
            self.assertNotIn(KEYTEXT, fh.read())

    def test_key_text_never_in_prompts(self):
        _, items, _ = benchmark.load_set(self.setfile)
        seen = []

        def llm(prompt):
            seen.append(prompt)
            from exam_engine.adapters import claude
            return claude.Call(True, QA if "reviews" in prompt[:3000] else SOLVE, 0.0, "", "", 0.0)
        cfg = {"max_attempts": 2, "max_cost_usd": 1.0, "timeout": 5, "model": "m", "llm_name": "mock", "pdf": False}
        benchmark.run_all(items, os.path.join(self.root, "o"), cfg, llm, 5.0)
        self.assertTrue(seen)
        for p in seen:
            self.assertNotIn(KEYTEXT, p)

    def test_bad_set_file_fails_by_name(self):
        cases = ["not json", {"v": 2, "items": []}, {"v": 1, "items": [{"id": "a/1"}]},
                 {"v": 1, "items": self.items + self.items[:1]}]
        for i, c in enumerate(cases):
            p = self.write(c, "bad%d.json" % i)
            code, _, err = self.run_cli(["--set", p, "--mock", self.mock(), "--out",
                                         os.path.join(self.root, "o"), "--history", self.hist])
            self.assertEqual(code, 2)
            self.assertIn("bad%d.json" % i, err)
        self.assertFalse(os.path.exists(self.hist))
        code, _, err = self.run_cli(["--set", os.path.join(self.root, "none.json"), "--mock", self.mock(),
                                     "--out", os.path.join(self.root, "o")])
        self.assertEqual((code, "none.json" in err), (2, True))

    def test_missing_file_is_skipped_and_run_continues(self):
        os.remove(self.items[0]["key"])
        code, out, _ = self.run_cli(["--set", self.setfile, "--mock", self.mock(1), "--out",
                                     os.path.join(self.root, "o"), "--history", self.hist])
        self.assertEqual(code, 3)
        self.assertEqual(len(metrics.read_history(self.hist)[0]), 1)
        with open(os.path.join(self.root, "o", "summary.json")) as fh:
            sm = json.load(fh)
        self.assertEqual(sm["skipped"], [["english", "001", "missing"]])

    def test_skipped_item_is_not_a_regression(self):
        def row(sub, passed, skipped=False):
            if skipped:
                return {"subject": sub, "item": "1", "skipped": "budget_reached"}
            return {"subject": sub, "item": "1", "summary": {"pass": passed, "fail": 0, "uncertain": 0,
                                                              "unresolved": 0, "points": 0, "max_points": 0},
                    "calls": 1, "cost_usd": 0.0, "questions": []}
        meta = {"date": "d", "model": "m", "prompt": "p"}
        prev = benchmark.summarize([row("a", 1), row("b", 1)], meta)
        cur = benchmark.summarize([row("a", 1), row("b", 0, skipped=True)], meta)
        self.assertEqual(benchmark.regression(prev, cur), [])
        cur2 = benchmark.summarize([row("a", 1), row("b", 0)], meta)
        self.assertEqual(benchmark.regression(prev, cur2), ["b"])

    def test_no_set_keeps_discover(self):
        d = os.path.join(self.root, "in", "english")
        k = os.path.join(self.root, "keys", "english")
        os.makedirs(d)
        os.makedirs(k)
        shutil.copy(os.path.join(SRC, "input-001.md"), d)
        shutil.copy(os.path.join(SRC, "expected-001.md"), k)
        code, out, _ = self.run_cli(["--inputs", os.path.join(self.root, "in"), "--keys",
                                     os.path.join(self.root, "keys"), "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("1 items, calls <=", out)
        self.assertIn("english/001", out)

    def test_example_set_loads_and_paths_exist(self):
        sid, items, bases = benchmark.load_set(os.path.join(ROOT, "evals", "regset.example.json"), ROOT)
        self.assertTrue(items)
        for _s, _n, i, k in items:
            self.assertTrue(os.path.isfile(i) and os.path.isfile(k), i)
        self.assertEqual(set(b.split(":")[0] for b in bases.values()), {"official", "generated"})


if __name__ == "__main__":
    unittest.main()

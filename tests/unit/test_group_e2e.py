"""TASK-055 QA: golden (retry/QA prompt bytes unchanged for unlabelled files) and free end-to-end CLI
(dry-run passage count, mock run statuses) on a 2-page-slice labelled exam."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "fixtures"))
import golden_rq  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "src"))
from test_exam_run import a, qa, solve  # noqa: E402
from test_group_model import HEAD, _lab  # noqa: E402

PAS = "Tea was first grown in Yunnan, long ago."
TAB = "[Figure/table: sales 2019 40 2020 55]"


def exam_text():
    b = _lab(1, "", "", "Independent stem alpha?", "1")
    for n in range(2, 9):  # 7-question passage group across pages 1-2
        b += _lab(n, "Read the following passage and answer.", PAS, "Passage item%d?" % n, "1-2")
    b += _lab(9, "Look at the table.", TAB, "Table stem nine?", "2")
    b += _lab(10, "Look at the table.", TAB, "Using question 9, add five?", "2")
    b += _lab(11, "", "", "Using question 99, add one?", "2")
    b += _lab(12, "", "", "What does the text say?", "2")
    b += _lab(13, "Read the following passage and answer.", "", "Missing passage stem?", "2")
    return (HEAD % "") + b


def cli(*args):
    return subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "exam.py"), "solve"] + list(args),
                          capture_output=True, text=True, cwd=ROOT, timeout=60)


class TestGoldenRetryQa(unittest.TestCase):
    def test_55_golden_retry_qa_unchanged(self):
        gold = json.load(open(os.path.join(HERE, "fixtures", "golden_retry_qa.json"), encoding="utf-8"))
        self.assertGreaterEqual(len(gold), 20)
        self.assertEqual(golden_rq.compute(ROOT), gold)


class TestCliEndToEnd(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.p = os.path.join(self.d, "slice.md")
        with open(self.p, "w", encoding="utf-8") as f:
            f.write(exam_text())

    def test_55_4_dry_run_passage_once_per_group(self):
        r = cli(self.p, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.count(PAS), 1)
        self.assertEqual(r.stdout.count(TAB), 1)
        self.assertEqual(r.stdout.count("## Group 2-8"), 1)

    def test_55_4_round1_prompt_passage_once(self):
        from test_exam_run import Script
        from exam_engine import engine
        from test_exam_run import cfg
        ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12]
        llm = Script(solve(*[a(i, "A") for i in ids]), qa(*[(i, "agree") for i in ids]))
        engine.run(self.p, os.path.join(self.d, "o2"), cfg(), llm)
        self.assertEqual(llm.prompts[0].count(PAS), 1)
        self.assertEqual(llm.prompts[0].count(TAB), 1)
        self.assertNotIn("Using question 99", llm.prompts[0])
        self.assertNotIn("Missing passage stem", llm.prompts[0])

    def test_55_5_mock_statuses(self):
        ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12]
        mock = os.path.join(self.d, "m.json")
        with open(mock, "w") as f:
            json.dump([solve(*[a(i, "A") for i in ids]), json.dumps(
                {"reviews": [{"id": str(i), "verdict": "agree", "findings": []} for i in ids]})], f)
        out = os.path.join(self.d, "out")
        r = cli(self.p, "--mock", mock, "--out", out, "--no-pdf")
        res = json.load(open(os.path.join(out, "result.json"), encoding="utf-8"))
        st = {int(q["id"]): (q["verification_status"], q["status_reason"]) for q in res["questions"]}
        self.assertEqual(st[11], ("UNCERTAIN", "solver_declined: missing_text (question 99)"), r.stdout)
        self.assertEqual(st[13], ("UNCERTAIN", "solver_declined: missing_text (passage)"))
        self.assertNotIn("missing_text", st[12][1] or "")
        self.assertIn("group_link_uncertain: q 12", r.stdout + r.stderr)
        self.assertEqual(res["questions"][1].get("pages"), [1, 2])


if __name__ == "__main__":
    unittest.main()

"""TASK-098: parse_key issues, keybad scoring, calibration, score-summary.md sections, no-key pack, end to end."""
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
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import explain, report_pack, reporter  # noqa: E402

EXAM = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")

KEY_TEXT = "Câu 1. A\n2. b\nCâu 3.C \nCâu 4. I\n1. B\nCâu 7. D\n"


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def row(printed, ours, level="-", subject="S", steps=()):
    q = {"id": str(printed), "answer": ours, "verification_status": "verified", "solution": list(steps)}
    if level != "-":
        q["uncertainty"] = {"level": level}
    return subject, printed, q


class ParseKey(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="k98_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = os.path.join(self.tmp, "key.txt")
        write(self.path, KEY_TEXT)

    def test_98_1_keys_and_issues(self):
        key, issues = explain.parse_key(self.path)
        self.assertEqual(key, {"1": "A", "2": "B", "3": "C", "7": "D"})
        got = sorted((i["kind"], i["printed"], i["token"]) for i in issues)
        self.assertEqual(got, sorted([("bad_letter", "4", "I"), ("duplicate", "1", "B"),
                                      ("missing", "5", ""), ("missing", "6", "")]))

    def test_98_1_load_key_equals_parse_key(self):
        self.assertEqual(explain.load_key(self.path), explain.parse_key(self.path)[0])

    def test_98_1_clean_key_has_no_issues(self):
        write(self.path, "1 A\n2 B\n3 D\n")
        self.assertEqual(explain.parse_key(self.path), ({"1": "A", "2": "B", "3": "D"}, []))


class ScoreRows(unittest.TestCase):
    def test_98_2_keybad_excluded_from_accuracy(self):
        rows = [row(1, "A"), row(2, "B"), row(3, "C")]
        key = {"1": "A", "2": "A"}
        issues = [{"printed": "3", "kind": "bad_letter", "token": "I"}]
        sc = report_pack._score_rows(rows, key, issues)
        self.assertEqual([x["result"] for x in sc], ["correct", "WRONG", "keybad"])
        self.assertEqual(sc[2]["key"], "?I")
        sm = report_pack._summary([_part(sc)], sc, issues)
        self.assertEqual((sm["total_correct"], sm["total"], sm["n_items"]), (1, 2, 3))
        self.assertEqual(sm["per"]["S"]["keybad"], 1)

    def test_98_2_no_issue_means_nokey(self):
        sc = report_pack._score_rows([row(9, "A")], {"1": "A"}, [])
        self.assertEqual(sc[0]["result"], "nokey")

    def test_98_2_declined_is_scorable(self):
        sc = report_pack._score_rows([row(1, None)], {"1": "A"}, [])
        self.assertEqual(sc[0]["result"], "declined")
        sm = report_pack._summary([_part(sc)], sc)
        self.assertEqual(sm["total"], 1)


def _part(scored):
    return {"name": "S", "result": {"exam": {"subject": "S"}, "run": {"cost_usd": 0.5, "calls": 2}}}


class Summary(unittest.TestCase):
    def setUp(self):
        rows = [row(1, "A", "low"), row(2, "B", "low", steps=["step one", "step two"]), row(3, "C", "high"),
                row(4, None, "high"), row(5, "A"), row(6, "D", "low")]
        key = {"1": "A", "2": "A", "3": "C", "4": "B", "5": "A"}
        self.issues = [{"printed": "6", "kind": "bad_letter", "token": "I"}]
        self.sc = report_pack._score_rows(rows, key, self.issues)
        self.sm = report_pack._summary([_part(self.sc)], self.sc, self.issues)

    def test_98_3_calibration_sums_to_scorable(self):
        cal = self.sm["calibration"]
        self.assertEqual(sum(c["n"] for c in cal.values()), self.sm["total"])
        for c in cal.values():
            self.assertEqual(c["n"], c["correct"] + c["wrong"] + c["declined"])
        self.assertEqual(cal["low"]["n"], 2)  # keybad row 6 (low) is not counted
        self.assertEqual(cal["high"]["declined"], 1)

    def test_98_3_mismatches_carry_why(self):
        by = {x["printed"]: x for x in self.sm["not_correct"]}
        self.assertEqual(set(by), {2, 4})
        self.assertIn("step one", by[2]["why"])
        self.assertIn("step two", by[2]["why"])

    def test_98_3_md_sections(self):
        md = report_pack._summary_md(self.sm, "ex", "run-t")
        heads = [ln for ln in md.splitlines() if ln.startswith("## ")]
        self.assertEqual(heads, ["## Score", "## Per question", "## Calibration", "## Mismatches (2)", "## Key issues"])
        self.assertIn("- 6: bad_letter I", md)
        self.assertIn("| 6 | S | ?I | D | keybad |", md)

    def test_98_3_md_key_issues_none(self):
        sm = report_pack._summary([_part(self.sc)], self.sc, [])
        self.assertTrue(report_pack._summary_md(sm, "ex", "run-t").rstrip().endswith("## Key issues\n\nnone"))


class Packed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="k98p_")
        cwd = os.getcwd()
        os.chdir(cls.tmp)
        try:
            with mock.patch.object(reporter, "git_info", return_value=None), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                cli.solve_main([EXAM, "--mock", MOCK, "--no-pdf"])
        finally:
            os.chdir(cwd)
        base = os.path.join(cls.tmp, "plans", "input-001", "main", "runs")
        src = os.path.join(base, os.listdir(base)[0])
        cls.plan = os.path.join(cls.tmp, "p3")  # the one-question mock run widened to 3 questions (ids 1..3)
        shutil.copytree(src, cls.plan)
        rp = os.path.join(cls.plan, "result.json")
        with open(rp, encoding="utf-8") as fh:
            r = json.load(fh)
        q1 = r["questions"][0]
        r["questions"] = []
        for i, ans in ((1, "A"), (2, "C"), (3, "B")):
            q = json.loads(json.dumps(q1))
            q["id"], q["answer"] = str(i), ans
            r["questions"].append(q)
        write(rp, json.dumps(r))
        cls.n = 3

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def pack(self, name, key=None):
        out = os.path.join(self.tmp, name)
        err = io.StringIO()
        with mock.patch.object(reporter, "git_info", return_value=None), contextlib.redirect_stderr(err):
            info = report_pack.build_pack([self.plan], out, "ex", "run-t", key=key, pdf=False)
        return out, info, err.getvalue()

    def read(self, out, kind, ext):
        f = [x for x in os.listdir(out) if "_%s_" % kind in x and x.endswith("." + ext)]
        self.assertEqual(len(f), 1, f)
        with open(os.path.join(out, f[0]), encoding="utf-8") as fh:
            return fh.read()

    def test_98_5_no_key_pack_has_no_score_files(self):
        out, info, err = self.pack("nokey")
        self.assertFalse([f for f in info["files"] if "score-" in f])
        self.assertEqual(err, "")
        self.assertEqual(info["expected"], info["files"])
        self.assertIsNone(info["total"])

    def test_98_5_synthetic_three_question_key(self):
        key = os.path.join(self.tmp, "k3.txt")
        write(key, "Câu 1. A\nCâu 2. B\nCâu 3. I\n")
        out, info, err = self.pack("keyed", key)
        self.assertIn("key issue: 3 bad_letter I", err)
        self.assertEqual(info["expected"], info["files"])
        tsv = [ln.split("\t") for ln in self.read(out, "score-vs-key", "tsv").splitlines()][1:]
        res = {r[0]: r[4] for r in tsv}
        self.assertEqual(res, {"1": "correct", "2": "WRONG", "3": "keybad"})
        self.assertEqual(len(tsv), self.n)
        sm = json.loads(self.read(out, "score-summary", "json"))
        scorable = sum(r[4] in ("correct", "WRONG", "declined") for r in tsv)
        self.assertEqual(info["total"], scorable)
        self.assertEqual((sm["total"], sm["total_correct"]), (2, 1))
        self.assertEqual(sm["key_issues"], [{"printed": "3", "kind": "bad_letter", "token": "I"}])
        md = self.read(out, "score-summary", "md")
        for h in ("## Score", "## Per question", "## Calibration", "## Mismatches", "## Key issues"):
            self.assertIn(h, md)
        with open(os.path.join(out, "run.json"), encoding="utf-8") as fh:
            run = json.load(fh)
        self.assertEqual(run["key_issues"], sm["key_issues"])

    def test_98_5_answer_table_unchanged_by_key(self):
        a, _, _ = self.pack("a")
        key = os.path.join(self.tmp, "k1.txt")
        write(key, "1 A\n")
        b, _, _ = self.pack("b", key)
        self.assertEqual(self.read(a, "answer-table", "tsv"), self.read(b, "answer-table", "tsv"))


if __name__ == "__main__":
    unittest.main()

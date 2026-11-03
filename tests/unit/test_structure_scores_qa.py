"""69.x QA additions: separate denominators, known_miss vs improvement, split on the board, token estimate."""
import json
import os
import sys
import unittest
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
sys.path.insert(0, HERE)
import test_structure_scores as base  # noqa: E402
from test_structure_scope import emit  # noqa: E402
from exam_engine.pipeline import metrics  # noqa: E402


def classify(case):
    """(regressions, improvements): a miss not labelled known_miss regresses; a labelled miss now passing improves."""
    sc = metrics.structure_scores(emit(case["refined"])[1], case["gold"])["scores"]
    reg, imp = [], []
    for name, v in sc.items():
        missed = {m["id"] for m in v["miss"]}
        known = set(case["known_miss"].get(name, []))
        reg += [(name, i) for i in sorted(missed - known)]
        imp += [(name, i) for i in sorted(known - missed)]
    return reg, imp


class TestRates(unittest.TestCase):
    def test_69_1_each_rate_uses_its_own_denominator(self):
        s = metrics.structure_scores(base.exam3(), base.GOLD)["scores"]
        # gold has 4 rows; field metrics only count rows that carry the field and were extracted
        self.assertEqual([(k, s[k]["k"], s[k]["n"], s[k]["rate"]) for k in ("extraction", "instruction", "shared_ref")],
                         [("extraction", 3, 4, 0.75), ("instruction", 2, 3, metrics._rate(2, 3)), ("shared_ref", 2, 2, 1.0)])

    def test_69_1_deterministic(self):
        a = metrics.structure_scores(base.exam3(), base.GOLD)
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(metrics.structure_scores(base.exam3(), base.GOLD), sort_keys=True))

    def test_69_6_tokens_use_utf8_bytes_over_four(self):
        ex = {"questions": [base.qx(1, "", "", "", "éééé")]}  # 4 chars, 8 bytes
        self.assertEqual(metrics.tokens_per_question_est(ex), 2.0)
        self.assertIsNone(metrics.tokens_per_question_est({"questions": []}))


class TestFixture(unittest.TestCase):
    def setUp(self):
        with open(base.FIXTURE, encoding="utf-8") as f:
            self.cases = json.load(f)["cases"]

    def test_69_2_no_regression_and_improvement_reported(self):
        for c in self.cases:
            reg, imp = classify(c)
            self.assertEqual(reg, [], c["case"])
            if imp:  # a stale known_miss label is good news, not a failure
                warnings.warn("IMPROVEMENT %s now passes %s" % (c["case"], imp))

    def test_69_2_classify_splits_regression_from_improvement(self):
        c = dict(self.cases[0])
        reg, imp = classify(dict(c, known_miss={}))  # unlabelled miss -> regression
        self.assertTrue(reg)
        reg, imp = classify(dict(c, known_miss=dict(c["known_miss"], hierarchy=[1])))  # stale label -> improvement
        self.assertEqual(reg, [])
        self.assertEqual(imp, [("hierarchy", 1)])

    def test_69_2_known_miss_labels_are_valid(self):
        names = [c["case"] for c in self.cases]
        self.assertEqual(len(names), len(set(names)))
        for c in self.cases:
            ids = {g["id"] for g in c["gold"]}
            for name, miss in c["known_miss"].items():
                self.assertIn(name, metrics.STRUCTURE_METRICS)
                self.assertTrue(set(miss) <= ids, c["case"])

    def test_69_2_known_miss_not_counted_as_score_failure_but_stays_in_miss_list(self):
        c = [x for x in self.cases if "dropped" in x["case"]][0]
        s = metrics.structure_scores(emit(c["refined"])[1], c["gold"])["scores"]["extraction"]
        self.assertEqual((s["k"], s["n"]), (2, 3))  # the gap is visible in the score, not hidden
        self.assertEqual(classify(c), ([], []))


class TestBoardSeparate(base.trb.Base):
    def setUp(self):
        super().setUp()
        text, _ex, _ = emit([base.rq(1), base.rq(2)])
        self.exam = os.path.join(self.tmp, "exam.md")
        with open(self.exam, "w", encoding="utf-8") as f:
            f.write(text)
        self.sha = metrics.file_sha256(self.exam)
        self.gold = os.path.join(self.tmp, "gold.json")
        with open(self.gold, "w", encoding="utf-8") as f:
            json.dump([{"id": i, "stem": "Pick one."} for i in range(1, 5)], f)  # 4 gold rows, exam has 2

    def test_69_5_parsing_and_solving_denominators_differ(self):
        self.run_dir(base.trb.result(base.trb.states(3, 2, 0)), sha=self.sha)  # 5 solved questions
        code, out, _ = self.board("--exam", self.exam, "--structure-gold", self.gold)
        self.assertEqual(code, 0)
        self.assertIn("parsing gold n=4 extraction 50.0%", out)
        self.assertIn("coverage 5/5", out)
        self.assertNotIn("extraction 40.0%", out)

    def test_69_5_missing_gold_file_fails_by_name(self):
        self.run_dir(base.trb.result(base.trb.states(1, 0, 0)), sha=self.sha)
        miss = os.path.join(self.tmp, "nope.json")
        code, out, err = self.board("--exam", self.exam, "--structure-gold", miss)
        self.assertEqual(code, 2)
        self.assertIn("nope.json", err)

    def test_69_3_split_counts_unflagged_wrong_as_solver(self):
        d = self.run_dir(base.trb.result(base.trb.states(1, 3, 0)), sha=self.sha)  # ids 2,3,4 wrong
        os.makedirs(os.path.join(d, "input"))
        with open(os.path.join(d, "input", "assembly.json"), "w", encoding="utf-8") as f:
            json.dump({"schema": "assembly/1", "questions": [{"id": 2, "structure": ["x"]}, {"id": 3, "structure": ["x"]},
                                                              {"id": 1}]}, f)
        out = self.board()[1]
        self.assertIn("parsing flagged 2/4", out)
        self.assertIn("parse-suspect 2 solver 1", out)


if __name__ == "__main__":
    unittest.main()

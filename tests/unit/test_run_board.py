"""TASK-063 (63.1-63.5): engine scoreboard on synthetic result.json + history lines. Free, temp dirs only."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import metrics  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "metrics")
DECL = "solver_declined: x"


def q(i, state, flag=None, keyed=True):
    """state: ok (answered, key right), bad (answered, key wrong), dec (declined)."""
    r = {"id": str(i), "answer": None if state == "dec" else "A", "verification_status": "UNCERTAIN",
         "status_reason": DECL if state == "dec" else flag, "qa_findings": [], "attempts": 1,
         "uncertainty": {"level": "low", "reason": ""}}
    if keyed:  # the scorer leaves a declined question unscored (scorer.apply_key)
        r["score"] = {"points": None, "max": None} if state == "dec" else {"points": int(state == "ok"), "max": 1}
    return r


def result(qs, subject="chemistry", lang="fr", level="L2"):
    return {"exam": {"subject": subject, "language": lang, "level": level},
            "run": {"cost_usd": 0.1, "calls": 2}, "questions": qs}


def states(ok, bad, dec, flag_bad=None):
    """ok/bad/dec counts -> question list (ids 1..n); the first two bad ones carry flag_bad."""
    out, i = [], 0
    for state, n in (("ok", ok), ("bad", bad), ("dec", dec)):
        for k in range(n):
            i += 1
            out.append(q(i, state, flag_bad if state == "bad" and k < 2 else None))
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.hist = os.path.join(self.tmp, "h.jsonl")
        self.n = 0

    def run_dir(self, res, sha="s1", source="solve", rid=None, write=True):
        self.n += 1
        d = os.path.join(self.tmp, "r%d" % self.n)
        os.makedirs(d)
        if write:
            with open(os.path.join(d, "result.json"), "w", encoding="utf-8") as f:
                json.dump(res, f)
        line = {"v": 1, "run_id": rid or "r%d" % self.n, "ts": "2026-01-01T00:00:%02d" % self.n,
                "exam_id": "exam", "exam_sha256": sha, "source": source, "metrics": {},
                "result_path": os.path.join(d, "result.json")}
        metrics.append(self.hist, line)
        return d

    def board(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.run_stats_main(["board", "--history", self.hist] + list(args))
        return code, out.getvalue(), err.getvalue()


class VerdictTest(Base):
    def test_1_coverage_up_quality_down_flagged(self):
        self.run_dir(result(states(18, 2, 10)))
        self.run_dir(result(states(20, 10, 0)))
        code, out, _ = self.board()
        self.assertEqual(code, 1)
        self.assertIn("coverage 20/30 -> 30/30 (+10)", out)
        self.assertIn("verdict regression  COVERAGE_UP_QUALITY_DOWN", out)

    def test_2_better_f6_r0(self):
        self.run_dir(result(states(20, 6, 0)))
        self.run_dir(result(states(26, 0, 0)))
        code, out, _ = self.board()
        self.assertEqual(code, 0)
        self.assertIn("verdict better", out)

    def test_2_f3_r1_is_within_noise(self):
        self.run_dir(result(states(20, 3, 0) + [q(30, "ok")]))
        b = states(23, 0, 0) + [q(30, "bad")]
        self.run_dir(result(b))
        code, out, _ = self.board()
        self.assertEqual(code, 0)
        self.assertIn("same (within noise n=24 flips=4)", out)
        self.assertFalse(metrics.noise(6, 0))
        self.assertTrue(metrics.noise(3, 1))

    def test_3_unmeasured_never_better(self):
        a = [q(i, "ok", keyed=False) for i in range(1, 26)] + [q(i, "dec", keyed=False) for i in range(26, 31)]
        b = [q(i, "ok", keyed=False) for i in range(1, 31)]
        self.run_dir(result(a))
        self.run_dir(result(b))
        code, out, _ = self.board()
        self.assertEqual(code, 0)
        self.assertIn("coverage 25/30 -> 30/30 (+5)", out)
        self.assertIn("quality unmeasured (no key, no QA)", out)
        self.assertIn("verdict unmeasured", out)
        self.assertNotIn("better", out)

    def test_3_with_qa_reference_is_proxy_better(self):
        a = {"n": 6, "questions": [{"id": str(i), "answer": "B", "status": "UNCERTAIN", "reason": None,
                                    "key_ok": None} for i in range(1, 7)]}
        b = {"n": 6, "questions": [dict(x, answer="A") for x in a["questions"]]}
        qa = {str(i): {"answer": "A", "flawed": False} for i in range(1, 7)}
        d = metrics.pool([metrics.board_delta(a, b, qa)])
        self.assertEqual(d["basis"], "QA")
        self.assertEqual(metrics.verdict(d)[0], "better (proxy)")

    def test_5_pooling_two_exams_each_within_noise(self):
        for sha in ("s1", "s2"):  # R=3, F=0 each: noise alone, pooled R=6 is a signal
            self.run_dir(result(states(20, 0, 0)), sha=sha)
            self.run_dir(result(states(17, 3, 0)), sha=sha)
        code, out, _ = self.board()
        self.assertEqual(code, 1)
        self.assertIn("exams 2", out)
        self.assertIn("verdict regression", out)
        self.assertNotIn("COVERAGE_UP", out)

    def test_coverage_up_within_noise_watch(self):
        self.run_dir(result(states(18, 0, 6)))
        self.run_dir(result(states(18, 3, 3)))
        out = self.board()[1]
        self.assertIn("watch: coverage up, quality down within noise", out)
        self.assertIn("same (within noise", out)


class QualityTest(Base):
    def test_4_counts_match_hand_count(self):
        # 6 right, 4 wrong (2 flagged), 2 declined; one right answer is flagged too
        qs = states(6, 4, 2, flag_bad="reviewer_disagrees: x")
        qs[0]["status_reason"] = "check_failed: y"
        m = metrics.compute(result(qs), quality=True)["quality"]
        self.assertEqual((m["basis"], m["correct"], m["keyed"], m["wrong_answered"]), ("key", 6, 12, 4))
        self.assertEqual(m["keyed_scored"], 10)
        self.assertEqual((m["flagged"], m["flagged_correct"], m["silent_wrong"]), (3, 1, 2))
        self.assertAlmostEqual(m["precision"], 6 / 10)
        self.assertAlmostEqual(m["false_alarm"], 1 / 3)

    def test_unkeyed_run_is_unmeasured(self):
        m = metrics.compute(result([q(1, "ok", keyed=False)]), quality=True)["quality"]
        self.assertIsNone(m["basis"])
        self.assertTrue(m["unmeasured"])
        self.assertIsNone(m["correct"])


class AttemptAdjustedTest(Base):
    def test_30q_refusal_does_not_raise_headline(self):
        m = metrics.compute(result(states(16, 4, 10)), quality=True)
        self.assertEqual((m["accuracy"]["key"]["correct"], m["accuracy"]["key"]["keyed"]), (16, 20))  # scorer: 80%
        qu = m["quality"]
        self.assertEqual((qu["correct"], qu["keyed"]), (16, 30))
        self.assertAlmostEqual(qu["precision"], 0.8)
        self.run_dir(result(states(16, 4, 10)))
        out = self.board()[1]
        self.assertIn("quality key 16/30 (53% of all keyed)  precision 80%", out)

    def test_2q_one_of_one(self):
        qu = metrics.compute(result([q(1, "ok"), q(2, "dec")]), quality=True)["quality"]
        self.assertEqual((qu["correct"], qu["keyed"], qu["attempt_rate"]), (1, 2, 0.5))
        qu = metrics.compute(result([q(1, "ok"), q(2, "ok")]), quality=True)["quality"]
        self.assertEqual((qu["correct"], qu["keyed"], qu["attempt_rate"]), (2, 2, 1.0))

    def test_declined_then_wrong_is_wrong_new_on_score_path(self):
        ma = metrics.compute(result([q(1, "ok"), q(2, "dec")]), quality=True)
        mb = metrics.compute(result([q(1, "ok"), q(2, "bad")]), quality=True)
        d = metrics.board_delta(ma, mb)
        self.assertEqual((d["wrong_new"], d["cov_up"], d["cov_down"]), (1, 1, 0))
        d = metrics.board_delta(mb, ma)
        self.assertEqual((d["wrong_gone"], d["cov_down"]), (1, 1))


class ReviewPackScopeTest(Base):
    def pack(self, name, letter):
        p = os.path.join(self.tmp, name)
        with open(p, "w") as f:
            f.write("| n | answer | conf | flawed |\n|---|---|---|---|\n")
            f.write("".join("| %d | %s | high | no |\n" % (i, letter) for i in range(1, 4)))
        return p

    def two_exams(self):
        for sha in ("aaa111", "bbb222"):  # same ids 1..3 in both exams
            self.run_dir(result([q(i, "ok", keyed=False) for i in range(1, 4)]), sha=sha)

    def test_unscoped_pack_with_two_exams_exit_2(self):
        self.two_exams()
        code, _, err = self.board("--review-pack", self.pack("p.md", "A"))
        self.assertEqual(code, 2)
        self.assertIn("SHA_PREFIX=FILE", err)

    def test_scoped_pack_reaches_only_its_exam(self):
        self.two_exams()
        code, out, _ = self.board("--review-pack", "aaa=" + self.pack("p.md", "A"))
        self.assertEqual(code, 0)
        self.assertEqual(out.count("basis qa(proxy)"), 1)
        packs = cli._rs_board_packs(["aaa=x.md", "y.md"], 1)
        self.assertEqual(packs, {"aaa": ["x.md"], None: ["y.md"]})
        self.assertIsNone(cli._rs_board_qa({"aaa": [self.pack("p.md", "A")]}, {"exam_sha256": "bbb222"}, 0))


class PairTest(Base):
    def test_6_pairs_by_sha_not_exam_id(self):
        self.run_dir(result(states(5, 0, 0)), sha="s1")
        self.run_dir(result(states(5, 0, 0)), sha="s2")
        pairs, no_sha = metrics.pair(metrics.read_history(self.hist)[0])
        self.assertEqual((len(pairs), no_sha), (2, 0))
        self.assertTrue(all(p[1] is None for p in pairs))
        self.assertIn("baseline: none", self.board()[1])

    def test_6_baseline_other_sha_exit_2(self):
        d1 = self.run_dir(result(states(5, 0, 0)), sha="s1", rid="A")
        self.run_dir(result(states(5, 0, 0)), sha="s2", rid="B")
        ex = os.path.join(self.tmp, "exam.md")
        with open(ex, "w") as f:
            f.write("x")
        code, _, err = self.board("--baseline", d1, "--exam", ex)
        self.assertEqual(code, 2)
        self.assertIn("different exam", err)

    def test_baseline_run_id_same_sha(self):
        self.run_dir(result(states(10, 0, 0)), rid="OLD")
        self.run_dir(result(states(5, 5, 0)), rid="MID")
        self.run_dir(result(states(10, 0, 0)), rid="NEW")
        out = self.board("--baseline", "MID")[1]
        self.assertIn("coverage 10/10 -> 10/10", out)
        self.assertIn("precision 50% -> 100%", out)

    def test_10_missing_result_and_null_sha(self):
        self.run_dir(result(states(5, 0, 0)), rid="A")
        self.run_dir(result(states(5, 0, 0)), rid="GONE", write=False)
        self.run_dir(result(states(5, 0, 0)), sha=None, rid="NOSHA")
        code, out, _ = self.board()
        self.assertEqual(code, 0)
        self.assertIn("result missing: GONE", out)
        self.assertIn("no_sha 1", out)


class GeneralityTest(Base):
    def test_7_non_dgnl_kind_grouped_by_own_label(self):
        wide = [dict(q(1, "ok"), answer="G"), dict(q(2, "ok"), answer="F")]
        self.run_dir(result(wide, subject="physique", lang="fr", level="L3"), sha="p1")
        self.run_dir(result(states(3, 0, 0), subject="chemistry", lang="en", level=None), sha="c1")
        out = self.board()[1]
        self.assertIn("kind physique/fr/L3", out)
        self.assertIn("kind chemistry/en/-", out)
        self.assertNotIn("chemistry", self.board("--kind", "physique/fr/L3")[1])

    def test_7_no_literal_in_board_code(self):
        with open(os.path.join(ROOT, "src", "exam_engine", "pipeline", "metrics.py"), encoding="utf-8") as f:
            src = f.read()
        part = src[src.index("# ---- engine scoreboard"):]
        for lit in ("dgnl", "DGNL", "ABCD", "vietnam", "english", "math"):
            self.assertNotIn(lit, part)

    def test_d1_qa_label_is_single_not_substring(self):
        a = {"n": 1, "questions": [{"id": "1", "answer": "E", "status": "UNCERTAIN", "reason": None,
                                    "key_ok": None}]}
        b = {"n": 1, "questions": [dict(a["questions"][0], answer="X")]}
        self.assertIsNone(metrics.classify(a, b, {"1": {"answer": "AB", "flawed": False}})["basis"])
        self.assertIsNone(metrics.classify(a, b, {"1": {"answer": "", "flawed": False}})["basis"])
        self.assertEqual(metrics.classify(a, b, {"1": {"answer": "E", "flawed": False}})["basis"], "QA")

    def test_d5_declined_then_wrong_is_wrong_new(self):
        a = {"n": 1, "questions": [{"id": "1", "answer": None, "status": "UNCERTAIN", "reason": DECL,
                                    "key_ok": False}]}
        b = {"n": 1, "questions": [{"id": "1", "answer": "B", "status": "UNCERTAIN", "reason": None,
                                    "key_ok": False}]}
        d = metrics.classify(a, b)
        self.assertEqual((d["wrong_new"], d["cov_up"], d["unchanged"], d["fixed"]), (["1"], ["1"], 1, []))


class GoldenTest(unittest.TestCase):
    def test_8_default_metrics_unchanged_by_quality_kwarg(self):
        for name in sorted(os.listdir(FIX)):
            with open(os.path.join(FIX, name, "result.json"), encoding="utf-8") as f:
                res = json.load(f)
            plain = metrics.compute(res)
            self.assertNotIn("quality", plain)
            rich = metrics.compute(res, quality=True)
            rich.pop("quality")
            self.assertEqual(json.dumps(plain, sort_keys=True), json.dumps(rich, sort_keys=True))

    def test_8_history_line_gains_kind_only(self):
        res = result([q(1, "ok")])
        line = metrics.history_line(res, metrics.compute(res), {"run_id": "x"})
        self.assertEqual((line["kind"], line["v"]), ("chemistry/fr/L2", 1))
        self.assertEqual(metrics.kind({}), "-/-/-")


if __name__ == "__main__":
    unittest.main()

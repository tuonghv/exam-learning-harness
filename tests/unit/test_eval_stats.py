"""TASK-064 (64.1-64.7): evaluation statistics robustness; hand-computed numbers of the design. Free, temp dirs only."""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import metrics, scorer  # noqa: E402


def rec(answer, reason=None, status="UNCERTAIN", declined=False):
    """A recs entry as the engine hands it to scorer.apply_key."""
    ans = {"answer": answer, "answer_status": "declined" if declined else "answered"}
    return {"ans": ans, "status": status, "reason": reason, "findings": [], "code_checks": [], "checks": [], "review": None}


def rq(i, state, extra=None):
    """Result question. state: ok, bad, dec (declined), uns (not_solved), mal (malformed_output); keyed score
    as the 64.1 scorer writes it (non-answered keyed -> 0/1)."""
    reason = {"dec": "solver_declined: missing_text", "uns": "not_solved", "mal": "malformed_output"}.get(state)
    r = {"id": str(i), "answer": "A" if state in ("ok", "bad") else None, "verification_status": "UNCERTAIN",
         "status_reason": reason, "qa_findings": [], "attempts": 1, "uncertainty": {"level": "low", "reason": ""},
         "score": {"points": int(state == "ok"), "max": 1}}
    r.update(extra or {})
    return r


def result(qs, subject="chemistry", lang="fr", level="L2"):
    return {"exam": {"subject": subject, "language": lang, "level": level},
            "run": {"cost_usd": 0.1, "calls": 2}, "questions": qs}


def many(**counts):
    out, i = [], 0
    for state in ("ok", "bad", "dec", "uns", "mal"):
        for _ in range(counts.get(state, 0)):
            i += 1
            out.append(rq(i, state))
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.hist = os.path.join(self.tmp, "h.jsonl")
        self.n = 0

    def run_dir(self, res, sha="s1", source="solve", rid=None, commit=None, prompt=None, model="m"):
        self.n += 1
        d = os.path.join(self.tmp, "r%d" % self.n)
        os.makedirs(d)
        with open(os.path.join(d, "result.json"), "w", encoding="utf-8") as f:
            json.dump(res, f)
        metrics.append(self.hist, {
            "v": 1, "run_id": rid or "r%d" % self.n, "ts": "2026-01-01T00:00:%02d" % self.n, "exam_id": "exam",
            "exam_sha256": sha, "source": source, "metrics": {}, "git": {"commit": commit}, "prompt": prompt,
            "model": model, "result_path": os.path.join(d, "result.json")})
        return d

    def stats(self, sub, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.run_stats_main([sub] + list(args) + ["--history", self.hist])
        return code, out.getvalue(), err.getvalue()

    def q(self, qs, **kw):
        return metrics.compute(result(qs, **kw), quality=True)["quality"]


class Scorer641Test(unittest.TestCase):
    def apply(self, recs, final):
        key = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        self.addCleanup(os.unlink, key.name)
        key.write("## Question 1\n- Final answer: %s\n" % final)
        key.close()
        scorer.apply_key(recs, key.name)

    def test_declined_keyed_scores_zero_status_unchanged(self):
        r = {1: rec(None, "solver_declined", declined=True)}
        self.apply(r, "B")
        self.assertEqual(r[1]["score"], {"points": 0, "max": 1, "basis": "official_key", "detail": "not_answered"})
        self.assertEqual((r[1]["status"], r[1]["reason"], r[1]["findings"]), ("UNCERTAIN", "solver_declined", []))

    def test_open_key_and_no_key_stay_unscored(self):
        r = {1: rec(None, declined=True)}
        self.apply(r, "open (rubric)")
        self.assertIsNone(r[1]["score"]["points"])
        r = {2: rec(None, declined=True)}  # id with no key
        self.apply(r, "B")
        self.assertIsNone(r[2]["score"]["points"])

    def test_answered_unchanged(self):
        r = {1: rec("B", status="UNCERTAIN")}
        self.apply(r, "B")
        self.assertEqual(r[1]["score"]["points"], 1)


class Outcome642Test(Base):
    def test_1_30q_20_10(self):
        qu = self.q(many(ok=16, bad=4, dec=10))
        self.assertEqual(qu["outcomes"], {"correct": 16, "wrong": 4, "unkeyed_answered": 0, "declined": 10,
                                          "unanswered": 0, "invalid": 0})
        self.assertAlmostEqual(qu["score"], 16 / 30)
        lo, hi = qu["score_ci"]
        self.assertAlmostEqual(lo, 0.361, places=3)
        self.assertAlmostEqual(hi, 0.698, places=3)
        self.assertAlmostEqual(qu["coverage"], 20 / 30)
        self.assertAlmostEqual(qu["precision"], 0.8)
        m = metrics.compute(result(many(ok=16, bad=4, dec=10)))
        self.assertEqual(m["accuracy"]["key"]["keyed"], 30)  # scorer path, was 20
        self.assertNotIn("quality", m)  # stats/metrics.json shape unchanged

    def test_2_2q(self):
        qu = self.q(many(ok=1, dec=1))
        self.assertAlmostEqual(qu["score"], 0.5)
        self.assertAlmostEqual(qu["score_ci"][0], 0.095, places=3)
        self.assertAlmostEqual(qu["score_ci"][1], 0.905, places=3)
        a, b = self.q(many(ok=1, dec=1)), None
        ma = metrics.compute(result(many(ok=1, dec=1)), quality=True)
        mb = metrics.compute(result(many(ok=2)), quality=True)
        v = metrics.verdict(metrics.pool([metrics.board_delta(ma, mb)]))[0]
        self.assertEqual((a["keyed"], b), (2, None))
        self.assertEqual(v, "insufficient (flips 1<6)")

    def test_3_100q_mixed(self):
        qs = many(ok=70, bad=12, dec=10, uns=5, mal=3)
        qs[0]["qa_findings"] = [{"code": "review_malformed"}]  # answered + review_malformed: counted once, correct
        qu = self.q(qs)
        o = qu["outcomes"]
        self.assertEqual((o["correct"], o["wrong"], o["declined"], o["unanswered"], o["invalid"]),
                         (70, 12, 10, 5, 3))
        self.assertEqual(sum(o.values()), 100)
        self.assertAlmostEqual(qu["score"], 0.70)
        self.assertAlmostEqual(qu["score_ci"][0], 0.604, places=3)
        self.assertAlmostEqual(qu["score_ci"][1], 0.781, places=3)
        self.assertAlmostEqual(qu["precision"], 70 / 82)
        self.assertAlmostEqual(qu["coverage"], 0.82)

    def test_keyed_zero_is_none(self):
        qu = self.q([rq(1, "ok", {"score": None})])
        self.assertIsNone(qu["score"])
        self.assertIsNone(qu["score_ci"])
        self.assertEqual(qu["outcomes"]["unkeyed_answered"], 1)
        self.assertIsNone(metrics.wilson(0, 0))


class Pooled643Test(Base):
    def test_4_unusual_exam_own_kind_and_pooling(self):
        weird = result(many(ok=1, dec=4), subject="astro", lang="vi", level="L9")
        self.run_dir(result(many(ok=1, dec=1)), sha="a")
        self.run_dir(result(many(ok=16, bad=4, dec=10)), sha="b")
        self.run_dir(result(many(ok=70, bad=12, dec=10, uns=5, mal=3)), sha="c")
        self.run_dir(weird, sha="d")
        code, out, _ = self.stats("board", "--json")
        kinds = json.loads(out)["kinds"]
        w = kinds["exploratory|astro/vi/L9"]["cur"]
        self.assertEqual((w["correct"], w["keyed"]), (1, 5))
        self.assertAlmostEqual(w["score_ci"][0], 0.036, places=3)
        self.assertAlmostEqual(w["score_ci"][1], 0.624, places=3)
        c = kinds["exploratory|chemistry/fr/L2"]["cur"]
        self.assertEqual((c["correct"], c["keyed"]), (87, 132))  # pooled by question
        self.assertAlmostEqual(c["score"], 0.659, places=3)
        pooled = metrics.wilson(88, 137)
        self.assertIsNotNone(pooled)
        self.assertAlmostEqual(88 / 137, 0.642, places=3)
        self.assertAlmostEqual((1 / 2 + 16 / 30 + 70 / 100 + 1 / 5) / 4, 0.4833, places=3)  # per-exam mean, rejected

    def test_qa_agree_pooled(self):
        def m(agrees, differs):
            q = {"outcomes": dict.fromkeys(metrics.OUTCOMES, 0), "basis": "qa", "correct": None, "keyed": None,
                 "wrong_answered": None, "silent_wrong": None, "flagged": None, "flagged_correct": None,
                 "proxy": {"agree_rate": agrees / (agrees + differs), "agrees": agrees, "differs": differs,
                           "flagged": 0, "flagged_agrees": 0, "needs_review_by_why": None,
                           "image_agrees": None, "image_differs": None}}
            return {"quality": q, "counts": {"answered": 2}, "n": 2, "cost": {}}
        agg = metrics._side([m(0, 2), m(90, 10)])
        self.assertAlmostEqual(agg["agree_rate"], 90 / 102)  # per-exam mean would be .45


class Sign644Test(unittest.TestCase):
    def test_exact_boundaries(self):
        for f, r in ((4, 0), (5, 0), (7, 1), (9, 2), (11, 3), (12, 4), (3, 1), (9, 5), (0, 0)):
            self.assertTrue(metrics.noise(f, r), (f, r))
            self.assertTrue(metrics.noise(r, f), (r, f))
        for f, r in ((6, 0), (8, 1), (10, 2), (12, 2), (0, 6)):
            self.assertFalse(metrics.noise(f, r), (f, r))
        self.assertEqual(metrics.MIN_FLIPS, 6)
        self.assertFalse(metrics.decisive(5, 0))
        self.assertTrue(metrics.decisive(4, 2))


class Verdict645Test(Base):
    def compare(self, f, r, n=100):
        """Version A -> B on n questions: f fixed, r regressed."""
        a = [rq(i, "bad" if i <= f else "ok") for i in range(1, n + 1)]
        b = [rq(i, "bad" if f < i <= f + r else "ok") for i in range(1, n + 1)]
        da, db = self.run_dir(result(a), sha="x"), self.run_dir(result(b), sha="x")
        return self.stats("compare", da, db)

    def test_5_version_a_vs_b(self):
        code, out, _ = self.compare(9, 5)
        self.assertIn("within noise", out)
        self.assertEqual(code, 0)
        code, out, _ = self.compare(12, 2)
        self.assertIn("signal (improved)", out)
        code, out, _ = self.compare(4, 0)
        self.assertIn("insufficient (flips 4<6)", out)
        self.assertNotIn("signal", out)
        code, out, _ = self.compare(1, 9)
        self.assertEqual(code, 1)
        self.assertIn("signal (regressed)", out)

    def test_board_verdicts(self):
        for f, r, want in ((12, 2, "better"), (9, 5, "same (within noise"), (4, 0, "insufficient")):
            self.setUp()
            a = [rq(i, "bad" if i <= f else "ok") for i in range(1, 101)]
            b = [rq(i, "bad" if f < i <= f + r else "ok") for i in range(1, 101)]
            self.run_dir(result(a), commit="c1")
            self.run_dir(result(b), commit="c2")
            self.assertIn("verdict " + want, self.stats("board")[1])

    def test_unmeasured_compare(self):
        a = [rq(i, "ok", {"score": None}) for i in range(1, 8)]
        da, db = self.run_dir(result(a), sha="x"), self.run_dir(result(a), sha="x")
        code, out, _ = self.stats("compare", da, db)
        self.assertIn("unmeasured (no key, no QA)", out)
        self.assertNotIn("within noise", out)
        self.assertEqual(code, 0)


class Tier646Test(Base):
    def test_6_tiers_never_pooled_and_trend_filter(self):
        self.run_dir(result(many(ok=3)), sha="r1", source="regset")
        self.run_dir(result(many(ok=2, dec=1)), sha="e1", source="solve")
        out = self.stats("board")[1]
        self.assertEqual(out.count("kind chemistry/fr/L2"), 2)
        self.assertIn("tier official", out)
        self.assertIn("tier exploratory", out)
        keys = sorted(json.loads(self.stats("board", "--json")[1])["kinds"])
        self.assertEqual(keys, ["exploratory|chemistry/fr/L2", "official|chemistry/fr/L2"])
        t = self.stats("trend", "--source", "regset")[1]
        self.assertEqual(len([ln for ln in t.splitlines() if ln.startswith("2026")]), 1)
        self.assertEqual(len([ln for ln in self.stats("trend")[1].splitlines() if ln.startswith("2026")]), 2)


class Baseline647Test(Base):
    def ids(self):
        pairs, _ = metrics.pair(metrics.read_history(self.hist)[0])
        return [(c["run_id"], b["run_id"] if b else None) for c, b in pairs]

    def test_7_baseline_is_other_version(self):
        for rid, c in (("A", "v1"), ("B", "v2"), ("C", "v2")):
            self.run_dir(result(many(ok=3)), rid=rid, commit=c)
        self.assertEqual(self.ids(), [("C", "A")])
        self.assertNotIn("  repeat", self.stats("board")[1])

    def test_7_only_repeats_label(self):
        for rid in ("C", "D"):
            self.run_dir(result(many(ok=3)), rid=rid, commit="v2")
        self.assertEqual(self.ids(), [("D", "C")])
        self.assertIn("runs 2  tier exploratory  repeat", self.stats("board")[1])
        self.assertEqual(metrics.version_key({"git": {"commit": "x"}, "prompt": {"a": 1}, "model": "m"}),
                         ("x", '{"a": 1}', "m"))


class Generality9Test(Base):
    def test_9_non_dgnl_letters_beyond_d(self):
        qs = [rq(1, "ok", {"answer": "G"}), rq(2, "dec")]
        self.run_dir(result(qs, subject="astro", lang="vi", level=None))
        out = self.stats("board")[1]
        self.assertIn("kind astro/vi/-", out)
        self.assertIn("score 50%", out)

    def test_9_no_subject_literal_in_changed_code(self):
        bad = re.compile(r"toan|dgnl|vietnam|hoa hoc|vat ly", re.I)
        for rel in ("src/exam_engine/pipeline/metrics.py", "src/exam_engine/pipeline/scorer.py"):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                self.assertIsNone(bad.search(f.read()), rel)


if __name__ == "__main__":
    unittest.main()

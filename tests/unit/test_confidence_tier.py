"""TASK-075 phase-75: option_distance (75.1), confidence tier (75.3), by_confidence metrics (75.4).
Synthetic exams only; fake llm, no real call."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
sys.path.insert(0, HERE)
from exam_engine.core import decision as dec  # noqa: E402
from exam_engine.pipeline import metrics, verifier  # noqa: E402
import test_exam_run as t  # noqa: E402

Q = {"id": 1, "options": {"A": "10", "B": "20", "C": "40", "D": "80"}}


def ans(answer="B", expr="20", level="low", why="r", issues=()):
    return {"answer": answer, "answer_status": "answered", "expr": expr, "issues": list(issues),
            "uncertainty": {"level": level, "reason": why}}


def rec(status="UNCERTAIN", reason="no_independent_check", codes=(), verdict="agree", attempts=1, **kw):
    r = {"ans": ans(**kw), "status": status, "reason": reason, "attempts": attempts,
         "review": {"verdict": verdict}, "findings": [{"code": c} for c in codes]}
    return r


class OptionDistance(unittest.TestCase):
    def test_nearest_equal_passes_not_independent(self):
        c = verifier.option_distance(Q, ans("B", "20.5"))
        self.assertEqual((c["kind"], c["result"], c["independent"]), ("option_distance", "pass", False))
        self.assertFalse(verifier.option_mismatch(c))

    def test_mismatch_is_unknown_never_fail(self):
        c = verifier.option_distance(Q, ans("A", "41"))
        self.assertEqual(c["result"], "unknown")
        self.assertTrue(verifier.option_mismatch(c))
        self.assertIn("nearest=C chosen=A", c["detail"])

    def test_scale_mismatch_unknown_no_finding(self):
        c = verifier.option_distance(Q, ans("A", "40000000"))
        self.assertEqual(c["result"], "unknown")
        self.assertFalse(verifier.option_mismatch(c))

    def test_shared_number_unknown(self):
        q = {"options": {"A": "20", "B": "20", "C": "40"}}
        c = verifier.option_distance(q, ans("C", "20"))
        self.assertFalse(verifier.option_mismatch(c))
        self.assertEqual(c["result"], "unknown")

    def test_not_applicable_is_none(self):
        self.assertIsNone(verifier.option_distance(Q, ans("B", None)))
        self.assertIsNone(verifier.option_distance(Q, ans("Z", "20")))
        self.assertIsNone(verifier.option_distance({"options": {"A": "1.2.3", "B": "4"}}, ans("B", "4")))
        self.assertIsNone(verifier.option_distance(Q, ans("B", "import os")))


class Tier(unittest.TestCase):
    keys = ["A", "B", "C", "D"]

    def tier(self, r):
        return dec.confidence(r, self.keys)

    def test_none_cases(self):
        self.assertIsNone(dec.confidence({"ans": None}))
        r = rec()
        r["ans"]["answer_status"] = "declined"
        self.assertIsNone(self.tier(r))
        self.assertIsNone(self.tier(rec(answer="open")))

    def test_pass_is_verified(self):
        self.assertEqual(self.tier(rec(status="PASS", reason="x")), "verified")

    def test_likely_wrong_rules(self):
        for r in (rec(status="FAIL", reason="check_failed: computed"), rec(verdict="disagree"),
                  rec(verdict="unsure"), rec(level="high"),
                  rec(codes=["image_differs"]), rec(codes=["option_mismatch"]),
                  rec(codes=["adjudicated"]), rec(codes=["second_differs"])):
            self.assertEqual(self.tier(r), "likely_wrong", r)

    def test_unknown_when_no_positive_channel(self):
        self.assertEqual(self.tier(rec()), "unknown")
        self.assertEqual(self.tier(rec(level="medium")), "unknown")

    def test_option_distance_pass_never_positive(self):
        self.assertEqual(self.tier(rec(codes=["option_distance"])), "unknown")

    def test_likely_ok_needs_positive_and_no_negative(self):
        self.assertEqual(self.tier(rec(codes=["image_agrees"])), "likely_ok")
        self.assertEqual(self.tier(rec(codes=["second_agrees"])), "likely_ok")
        self.assertEqual(self.tier(rec(codes=["image_agrees"], attempts=2)), "unknown")  # retry
        self.assertEqual(self.tier(rec(codes=["image_agrees", "malformed_output"])), "unknown")
        self.assertEqual(self.tier(rec(codes=["image_agrees", "review_malformed"])), "unknown")
        self.assertEqual(self.tier(rec(codes=["image_agrees"], level="medium")), "unknown")
        self.assertEqual(self.tier(rec(codes=["image_agrees"], reason="reviewer_unsure")), "unknown")

    def test_alternative_reading_named_by_solver(self):
        # Math-63 reply shape (saved run): chosen C, the solver names another reading; synthetic text
        r = rec(answer="C", level="medium", why="Under the other reading the answer would be option B")
        self.assertEqual(self.tier(r), "likely_wrong")
        r = rec(answer="C", level="medium", why="x", issues=["Alternative: (B) if paid at the start"])
        self.assertEqual(self.tier(r), "likely_wrong")

    def test_alternative_reading_is_conservative(self):
        same = rec(answer="C", level="medium", why="option C is close but rounding")
        var = rec(answer="C", level="medium", why="A = 19.975.000 per month, A ≈ 20")
        low = rec(answer="C", level="low", why="option B is the other reading")
        for r in (same, var, low):
            self.assertEqual(self.tier(r), "unknown")
        self.assertEqual(dec.names_other_option(rec(answer="C", level="medium", why="Because")["ans"],
                                                self.keys), False)
        self.assertFalse(dec.names_other_option(rec(level="medium", why="B")["ans"], None))


MCQ = (t.HEAD % ("English", "Multiple Choice") + "## Instructions\n\nChoose.\n\n"
       "## Question 1\n\nPick the quantity.\n\nA. 10\nB. 20\nC. 40\nD. 80\n")


class EngineFlag(t.Base):
    def llm(self):
        return t.Script(t.solve(t.a(1, "B", expr="20")), t.qa((1, "agree")))

    def test_default_off_has_no_confidence_keys(self):
        self.go(MCQ, self.llm())
        r = self.result_file()
        self.assertNotIn("confidence", r["questions"][0])
        self.assertNotIn("confidence", r["summary"])
        self.assertEqual([c["kind"] for c in r["questions"][0]["checks"]].count("option_distance"), 0)

    def test_flag_adds_tier_and_check_without_status_change(self):
        self.go(MCQ, self.llm())
        base = self.result_file()["questions"][0]
        self.go(MCQ, self.llm(), confidence=True)
        r = self.result_file()
        q = r["questions"][0]
        self.assertEqual(q["confidence"], "unknown")
        self.assertEqual(r["summary"]["confidence"], {"unknown": 1})
        self.assertEqual((q["verification_status"], q["status_reason"], q["unresolved"], q["evidence_kind"]),
                         (base["verification_status"], base["status_reason"], base["unresolved"],
                          base["evidence_kind"]))
        self.assertEqual(q["checks"][-1]["kind"], "option_distance")

    def test_mismatch_adds_finding_and_wrong_tier(self):
        self.go(MCQ, t.Script(t.solve(t.a(1, "A", expr="41")), t.qa((1, "agree"))), confidence=True)
        q = self.result_file()["questions"][0]
        self.assertEqual(q["confidence"], "likely_wrong")
        self.assertIn("option_mismatch", [f["code"] for f in q["qa_findings"]])
        self.assertEqual(q["verification_status"], "UNCERTAIN")


def mres(items):
    return {"run": {}, "exam": {"subject": "S"}, "questions": [
        {"id": str(i), "answer": a, "verification_status": "UNCERTAIN", "status_reason": "no_independent_check",
         "uncertainty": {"level": "low"}, "qa_findings": [], "confidence": c, "attempts": 1}
        for i, (a, c) in enumerate(items, 1)]}


class Metrics(unittest.TestCase):
    def test_by_confidence_counts_and_wilson(self):
        res = mres([("A", "likely_ok"), ("A", "likely_ok"), ("B", "likely_ok"),
                    ("B", "likely_wrong"), ("A", "unknown")])
        key = {"1": "A", "2": "A", "3": "B", "4": "A", "5": "A"}
        m = metrics.compute(res, key=key)
        bc = m["confidence"]
        self.assertEqual((bc["by_confidence"]["likely_ok"]["n"], bc["by_confidence"]["likely_ok"]["correct"]), (3, 3))
        self.assertEqual(bc["by_confidence"]["likely_wrong"]["wrong"], 1)
        self.assertEqual(bc["wrong_in_likely_ok"], 0)
        self.assertEqual((bc["wrong_recall"]["k"], bc["wrong_recall"]["n"]), (1, 1))
        lo, hi = bc["by_confidence"]["likely_ok"]["precision_ci"]
        self.assertEqual((lo, hi), metrics.wilson(3, 3))
        self.assertTrue(any(ln.startswith("confidence: likely_ok 3/3") for ln in metrics.block(m)))
        m2 = metrics.compute(res, key=key, quality=True)
        self.assertEqual(m2["quality"]["wrong_in_likely_ok"], 0)

    def test_old_result_unchanged(self):
        res = mres([("A", None)])
        for q in res["questions"]:
            q.pop("confidence")
        m = metrics.compute(res, key={"1": "A"}, quality=True)
        self.assertNotIn("confidence", m)
        self.assertNotIn("by_confidence", m["quality"])
        self.assertEqual(len(metrics.block(m)), 3)


if __name__ == "__main__":
    unittest.main()

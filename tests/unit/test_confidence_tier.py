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


class MappedEngine(t.Base):
    def tier(self, answer):
        self.go(MCQ, t.Script(t.solve(t.a(1, answer, expr=None)), t.qa((1, "agree"))), confidence=True)
        return self.result_file()["questions"][0].get("confidence")

    def test_value_maps_vs_not(self):
        self.assertNotEqual(self.tier("40"), "likely_wrong")
        self.assertEqual(self.tier("33"), "likely_wrong")


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

    def test_value_answer_format_fail_is_no_flag_when_mapped(self):
        r = rec(status="FAIL", reason="check_failed: format", answer="40")
        self.assertEqual(dec.confidence(r, self.keys, mapped=True), "unknown")
        self.assertEqual(dec.confidence(r, self.keys, mapped=False), "likely_wrong")
        r = rec(status="FAIL", reason="check_failed: computed", answer="40")
        self.assertEqual(dec.confidence(r, self.keys, mapped=True), "likely_wrong")

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


class Adversarial(unittest.TestCase):
    """TASK-075 QA: malformed/missing fields, unicode, value answers, false positives of the alternative-reading rule."""
    keys = list("ABCD")

    def test_missing_optional_fields_do_not_crash(self):
        base = rec()["ans"]
        for r in ({}, {"ans": dict(base, uncertainty=None)}, {"ans": dict(base, issues=None)},
                  {"ans": dict(base), "findings": None, "review": None, "attempts": None, "status": None}):
            r.setdefault("ans", base)
            self.assertIn(dec.confidence(r, self.keys), (None, "unknown", "likely_wrong"))
        self.assertIsNone(dec.confidence({}, self.keys))
        r = {"ans": dict(base, uncertainty=None), "findings": None, "review": None, "attempts": None}
        self.assertEqual(dec.confidence(r, self.keys), "unknown")  # level None is not low: never likely_ok

    def test_medium_without_reason_is_not_flagged(self):
        r = rec(answer="C", level="medium", why=None)
        self.assertEqual(dec.confidence(r, self.keys), "unknown")
        r["ans"]["uncertainty"] = {"level": "medium"}
        self.assertEqual(dec.confidence(r, self.keys), "unknown")

    def test_unicode_and_lowercase_letters_are_not_option_keys(self):
        for why in ("\uff22 is the other one", "\u0412 option", "b is the other", "B1 variant", "AB"):
            self.assertFalse(dec.names_other_option(
                {"answer": "A", "uncertainty": {"level": "medium", "reason": why}}, self.keys), why)

    def test_unicode_keys_match_only_themselves(self):
        a = {"answer": "A", "uncertainty": {"level": "medium", "reason": "\uff22 is the other"}}
        self.assertTrue(dec.names_other_option(a, ["A", "\uff22"]))

    def test_explanation_text_is_never_read(self):
        # confident solver listing wrong options in the explanation: no flag, whatever the level
        for level in ("low", "medium"):
            r = rec(answer="C", level=level, why="calculation matches")
            r["ans"]["explanation"] = "Options A, B and D are far off; C matches."
            self.assertEqual(dec.confidence(r, self.keys), "unknown")

    def test_value_answer_keys_unaffected(self):
        r = rec(answer="230%", level="medium", why="plain")
        self.assertEqual(dec.confidence(r, self.keys), "unknown")
        r = rec(status="FAIL", reason="check_failed: format", answer="230%")
        self.assertEqual(dec.confidence(r, self.keys), "likely_wrong")  # known: a format FAIL on a value answer

    def test_eliminated_option_in_medium_reason_is_flagged_known_limit(self):
        # replay run3: reasons like "A and D are weaker" flag a right answer; documents the false-alarm class
        r = rec(answer="C", level="medium", why="options A and D are weaker")
        self.assertEqual(dec.confidence(r, self.keys), "likely_wrong")

    def test_wilson_known_values(self):
        lo, hi = metrics.wilson(5, 10)
        self.assertEqual((round(lo, 3), round(hi, 3)), (0.237, 0.763))
        lo, hi = metrics.wilson(10, 10)
        self.assertEqual((round(lo, 3), hi), (0.722, 1.0))
        self.assertIsNone(metrics.wilson(0, 0))

    def test_wrong_in_likely_ok_counts_silent_wrong(self):
        res = mres([("B", "likely_ok"), ("A", "likely_ok"), ("A", "unknown")])
        m = metrics.compute(res, key={"1": "A", "2": "A", "3": "A"})
        self.assertEqual(m["confidence"]["wrong_in_likely_ok"], 1)
        self.assertEqual(m["confidence"]["wrong_recall"]["k"], 0)
        self.assertEqual(m["confidence"]["wrong_recall"]["n"], 1)

    def test_flag_default_off_via_cli(self):
        import test_exam_run as er
        ap = os.path.join(er.ROOT, "src", "exam_engine", "cli.py")
        with open(ap, encoding="utf8") as fh:
            src = fh.read()
        self.assertIn('"--confidence", action="store_true"', src)  # no default=True
        self.assertNotIn("confidence=True", src)


if __name__ == "__main__":
    unittest.main()


# ---- 75.2 second sample ----
from exam_engine import engine as eng  # noqa: E402
from exam_engine.pipeline import parser as eparser, solver  # noqa: E402


def mcq(n, extra=""):
    body = t.HEAD % ("English", "Multiple Choice") + "## Instructions\n\nChoose.\n\n"
    for i in range(1, n + 1):
        body += "## Question %d\n\nPick %d.\n\nA. o%d1\nB. o%d2\nC. o%d3\nD. o%d4\n\n" % ((i, i) + (i,) * 4)
    return body + extra


def reply_for(prompt, pick):
    """Fake second reply: for each '## Question N' in the prompt, answer the letter whose text is o<N><pick>."""
    import re
    out = []
    for n in re.findall(r"## Question (\d+)", prompt):
        m = re.search(r"\n([A-D])\. o%s%d\b" % (n, pick(int(n))), prompt)
        out.append(t.a(n, m.group(1) if m else "A", expr=None))
    return t.solve(*out)


class Permuted(unittest.TestCase):
    def exam(self, n=4):
        import tempfile
        d = tempfile.mkdtemp()
        p = os.path.join(d, "e.md")
        with open(p, "w") as fh:
            fh.write(mcq(n))
        return eparser.parse_exam(p)

    def test_rotation_moves_every_position_and_back_inverts(self):
        exam = self.exam(6)
        exam2, back = solver.permuted(exam, [1, 2, 3, 4, 5, 6])
        orig = {q["id"]: q for q in exam["questions"]}
        for q in exam2["questions"]:
            for new, old in back[q["id"]].items():
                self.assertEqual(q["options"][new], orig[q["id"]]["options"][old])
                self.assertNotEqual(new, old)
        self.assertEqual([q["id"] for q in exam2["questions"]], [6, 5, 4, 3, 2, 1])

    def test_two_options_and_letter_reference(self):
        exam = self.exam(2)
        for q in exam["questions"]:
            q["options"] = {"A": "x", "B": "y"}
        exam["questions"][1]["options"] = {"A": "same as B", "B": "y"}
        exam2, back = solver.permuted(exam, [1, 2])
        self.assertEqual(back[1], {"A": "B", "B": "A"})
        self.assertNotIn(2, back)  # names letter B: not permuted


class SecondSample(t.Base):
    def first(self, n, answers="B"):
        return [t.solve(*[t.a(i, answers, expr=None) for i in range(1, n + 1)]),
                t.qa(*[(i, "agree") for i in range(1, n + 1)])]

    def run_ss(self, n, pick, **kw):
        items = self.first(n)
        llm = t.Script(*items)
        orig = llm.__call__

        def both(prompt):
            if "Solve independently" in prompt:
                llm.items.append(reply_for(prompt, pick))
            return orig(prompt)
        self.go(mcq(n), both, second_sample=True, confidence=True, **kw)
        return llm, {q["id"]: q for q in self.result_file()["questions"]}

    def test_agree_and_differ_per_id_with_mapping(self):
        # first answers all B (text o?2). pick 2 -> second picks o?2 again (agree); pick 3 for id 2 -> differ
        llm, qs = self.run_ss(3, lambda n: 3 if n == 2 else 2)
        self.assertEqual(qs["1"]["confidence"], "likely_ok")
        self.assertEqual(qs["2"]["confidence"], "likely_wrong")
        self.assertEqual(qs["3"]["confidence"], "likely_ok")
        self.assertEqual(qs["1"]["second_answer"], "B")
        self.assertEqual(qs["2"]["second_answer"], "C")

    def test_prompt_clean_and_status_untouched(self):
        llm, qs = self.run_ss(2, lambda n: 3)
        sp = llm.prompts[-1]
        self.assertTrue(sp.rstrip().endswith("Solve independently."))
        self.assertNotIn("Answer:", sp)
        self.assertLess(sp.index("## Question 2"), sp.index("## Question 1"))
        for q in qs.values():
            self.assertEqual((q["answer"], q["verification_status"], q["status_reason"]),
                             ("B", "UNCERTAIN", "no_independent_check"))

    def test_scope_excludes_pass_fail_declined(self):
        recs = {}
        for i, (st, rs) in enumerate([("PASS", "x"), ("FAIL", "reviewer_disagrees"),
                                      ("UNCERTAIN", "no_independent_check"),
                                      ("UNCERTAIN", "reviewer_unsure"), ("UNCERTAIN", "solver_declined"),
                                      ("UNCERTAIN", "open_task_no_rubric")], 1):
            r = {"ans": ans("B"), "status": st, "reason": rs}
            if rs == "solver_declined":
                r["ans"]["answer_status"] = "declined"
            if rs == "open_task_no_rubric":
                r["ans"]["answer"] = "Open"
            recs[i] = r
        self.assertEqual(eng.second_targets(recs, {}), [3, 4])
        self.assertEqual(eng.second_targets(recs, {3: "x"}), [4])

    def test_malformed_second_reply_changes_no_tier(self):
        llm = t.Script(*self.first(2), "not json")
        self.go(mcq(2), llm, second_sample=True, confidence=True)
        qs = self.result_file()["questions"]
        for q in qs:
            self.assertEqual(q["confidence"], "unknown")
            self.assertIn("second_failed", [f["code"] for f in q["qa_findings"]])
            self.assertNotIn("second_answer", q)

    def test_cost_cap_stops_sample_without_differ(self):
        n = eng.SECOND_BATCH + 3
        items = self.first(n)
        items[0] = exam_llm_call(items[0], 0.0)
        llm = t.Script(*items)
        orig = llm.__call__

        def both(prompt):
            if "Solve independently" in prompt:
                llm.items.append(exam_llm_call(reply_for(prompt, lambda k: 3), 2.0))  # costs past the cap
            return orig(prompt)
        self.go(mcq(n), both, second_sample=True, confidence=True, max_cost_usd=1.0)
        qs = {q["id"]: q for q in self.result_file()["questions"]}
        codes = lambda i: [f["code"] for f in qs[str(i)]["qa_findings"]]  # noqa: E731
        self.assertIn("second_differs", codes(1))  # first batch ran
        self.assertIn("second_skipped", codes(n))  # second batch stopped by the cap
        self.assertNotIn("second_differs", codes(n))
        self.assertEqual(qs[str(n)]["confidence"], "unknown")

    def test_default_run_makes_no_second_call(self):
        llm = t.Script(*self.first(2))
        self.go(mcq(2), llm)
        self.assertEqual(len(llm.prompts), 2)
        self.assertNotIn("second_answer", self.result_file()["questions"][0])


def exam_llm_call(text, cost):
    return t.exam_llm.Call(True, text, cost, "", "", 0.0)

"""Tests 5-9 of docs/design/phase-4-engine-core.md (+D6 independence); REQ-0010 AC3. No model call."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import exam_checks as ck  # noqa: E402

MC = {"fields": {"Subject": "English", "Task": "Multiple Choice"}, "passage": "The cat sat."}
OPTS = {"A": "have", "B": "had", "C": "will have", "D": "would have"}
QMC = {"id": 1, "text": "If I ___ time", "options": OPTS}
QNUM = {"id": 1, "text": "Compute 2*sqrt(3).", "options": {}}
NUM = {"fields": {"Subject": "Mathematics", "Task": "Short Answer"}, "passage": ""}
LIT = {"fields": {"Subject": "Literature", "Task": "Essay"}, "passage": "Quote line one."}
QLIT = {"id": 1, "text": "Analyse.", "options": {}}


def ans(answer="A", **kw):
    a = {"id": "1", "answer": answer, "answer_status": "answered", "expr": None, "evidence": [],
         "uncertainty": {"level": "low", "reason": "r"},
         "reasoning_status": "not_independently_verified"}
    a.update(kw)
    return a


def chk(kind, result, independent):
    return {"kind": kind, "detail": "d", "result": result, "independent": independent}


class SafeEval(unittest.TestCase):
    def test_5_allowed(self):
        self.assertAlmostEqual(ck.safe_eval("2*sqrt(3)"), 3.4641016, places=6)
        for expr, want in (("2**10", 1024), ("-3+4", 1), ("10 % 3", 1), ("abs(-2)", 2),
                           ("log(100)", 2), ("ln(e)", 1), ("round(2.567, 2)", 2.57),
                           ("(1+2)*3/9", 1), ("+5", 5)):
            self.assertAlmostEqual(ck.safe_eval(expr), want, msg=expr)
        self.assertAlmostEqual(ck.safe_eval("sin(pi)"), 0, places=9)
        self.assertIsInstance(ck.safe_eval("3"), float)

    def test_5_refused_code_names_attributes(self):
        for expr in ("__import__('os')", "__import__('os').system('true')", "x", "os",
                     "().__class__", "(1).real", "pi.real", "math.sqrt(4)", "open('f')",
                     "lambda: 1", "[1, 2]", "{1: 2}", "1 if 1 else 2", "True", "None",
                     "'abc'", "b'a'", "len('a')", "sqrt(x=4)", "sqrt()", "sqrt(1, 2)",
                     "round(1, 2, 3)", "sqrt.__call__(4)", "eval('1')", "1 < 2", "1; 2",
                     "import os", "a = 1", "~1", "1 << 2", "2 // 1", "1j", "(1+2j)",
                     "[x for x in ()]"):
            with self.assertRaises(ValueError, msg=expr):
                ck.safe_eval(expr)

    def test_5_refused_bad_input_and_math_errors(self):
        for expr in ("", "   ", None, 5, "1/0", "sqrt(-1)", "log(0)", "exp(1000)", "(1+",
                     "9" * 300, "1+" * 150 + "1", "(" * 500 + "1" + ")" * 500):
            with self.assertRaises(ValueError, msg=str(expr)[:30]):
                ck.safe_eval(expr)

    def test_5_exponent_cap_cheap(self):
        for expr in ("2**101", "10**1000", "2**-101", "2**(50*3)"):
            with self.assertRaises(ValueError, msg=expr):
                ck.safe_eval(expr)
        self.assertEqual(ck.safe_eval("2**100"), float(2 ** 100))

    def test_5_power_bomb_refused(self):
        for expr in ("9**9**9", "9**(9**9)", "2**(9**9)"):
            with self.assertRaises(ValueError, msg=expr):
                ck.safe_eval(expr)

    def test_5_huge_strings_refused(self):
        for expr in ("'a'*10**9", "'a'*99999999", "'a'" + "*2" * 40, "1" * 10000):
            with self.assertRaises(ValueError, msg=expr[:30]):
                ck.safe_eval(expr)


class DetChecks(unittest.TestCase):
    def kinds(self, cs):
        return [(c["kind"], c["result"], c["independent"]) for c in cs]

    def test_6_computed_pass_and_fail(self):
        cs = ck.det_checks(QNUM, ans("3.46", expr="2*sqrt(3)"), NUM)
        comp = [c for c in cs if c["kind"] == "computed"][0]
        self.assertEqual((comp["result"], comp["independent"]), ("pass", True))
        self.assertIn("arithmetic only", comp["detail"])
        comp = [c for c in ck.det_checks(QNUM, ans("3.47", expr="2*sqrt(3)"), NUM)
                if c["kind"] == "computed"][0]
        self.assertEqual(comp["result"], "fail")
        comp = [c for c in ck.det_checks(QNUM, ans("7", expr="3+4"), NUM)
                if c["kind"] == "computed"][0]
        self.assertEqual(comp["result"], "pass")
        comp = [c for c in ck.det_checks(QNUM, ans("1,5 m", expr="3/2"), NUM)
                if c["kind"] == "computed"][0]
        self.assertEqual(comp["result"], "pass")  # decimal comma and unit

    def test_6_computed_unusable_is_unknown_and_not_independent(self):
        for a in (ans("3.46", expr="__import__('os')"), ans("no number", expr="1+1"),
                  ans("3.46", expr="9**9**9")):
            comp = [c for c in ck.det_checks(QNUM, a, NUM) if c["kind"] == "computed"][0]
            self.assertEqual((comp["result"], comp["independent"]), ("unknown", False))
        self.assertEqual([c for c in ck.det_checks(QNUM, ans("3.46"), NUM)
                          if c["kind"] == "computed"], [])  # no expr, no check

    def test_6_format_letter(self):
        for a, want in (("A", "pass"), ("D", "pass"), ("E", "fail"), ("AB", "fail"),
                        ("a", "fail"), ("A. have", "fail")):
            c = [x for x in ck.det_checks(QMC, ans(a), MC) if x["kind"] == "format"][0]
            self.assertEqual(c["result"], want, a)
            self.assertIs(c["independent"], False)

    def test_6_format_ordering(self):
        exam = {"fields": {"Subject": "English", "Task": "Sentence Ordering"}, "passage": ""}
        q = {"id": 1, "text": "Arrange:\na. one\nb. two\nc. three", "options": {}}
        for a, want in (("c-a-b", "pass"), ("a-b-c", "pass"), ("a-a-b", "fail"),
                        ("a-b", "fail"), ("a-b-d", "fail"), ("abc", "fail")):
            c = [x for x in ck.det_checks(q, ans(a), exam) if x["kind"] == "format"][0]
            self.assertEqual(c["result"], want, a)
            self.assertIs(c["independent"], False)

    def test_6_quote_present_and_absent(self):
        cs = ck.det_checks(QMC, ans("A", evidence=["If I ___ time", "The  cat\nsat."]), MC)
        qs = [c for c in cs if c["kind"] == "quote"]
        self.assertEqual([c["result"] for c in qs], ["pass", "pass"])  # whitespace-insensitive
        cs = ck.det_checks(QMC, ans("A", evidence=["The dog barked."]), MC)
        q = [c for c in cs if c["kind"] == "quote"][0]
        self.assertEqual(q["result"], "fail")
        self.assertIs(q["independent"], False)
        self.assertEqual([c for c in ck.det_checks(QMC, ans("A", evidence=[None, "null", " "]), MC)
                          if c["kind"] == "quote"], [])

    def test_6_only_computed_is_independent(self):
        cs = (ck.det_checks(QMC, ans("A", evidence=["If I ___ time"]), MC)
              + ck.det_checks(QNUM, ans("3.46", expr="2*sqrt(3)", evidence=["Compute"]), NUM))
        for c in cs:
            self.assertEqual(c["independent"], c["kind"] == "computed" and c["result"] != "unknown")

    def test_8_declined_runs_no_check(self):
        for a in (ans("A", answer_status="uncertain"), ans("A", answer_status="unanswerable"),
                  ans(None), ans("   "), ans(None, expr="1+1")):
            self.assertTrue(ck.declined(a))
            self.assertEqual(ck.det_checks(QMC, a, MC), [])
            self.assertEqual(ck.decide([], {"verdict": "agree", "findings": []}, a),
                             ("UNCERTAIN", "solver_declined"))
        self.assertFalse(ck.declined(ans("A")))

    def test_9_literature_open_only_format_and_quote(self):
        cs = ck.det_checks(QLIT, ans("Open", evidence=["Quote line one.", "Not there"]), LIT)
        self.assertEqual(self.kinds(cs), [("format", "pass", False), ("quote", "pass", False),
                                          ("quote", "fail", False)])
        cs = ck.det_checks(QLIT, ans("Some essay", expr="1+1"), LIT)
        self.assertEqual(cs[0]["kind"], "format")
        self.assertEqual(cs[0]["result"], "fail")  # Literature answer must be Open

    def test_9_literature_always_uncertain(self):
        forged = [chk("format", "pass", True), chk("computed", "pass", True)]
        agree = {"verdict": "agree", "findings": []}
        st, why = ck.decide(forged, agree, ans("Open"))
        self.assertEqual(st, "UNCERTAIN")
        self.assertIn("open_task_no_rubric", why)
        st, why = ck.decide([chk("quote", "fail", False)], agree, ans("Open"))
        self.assertEqual(st, "UNCERTAIN")
        self.assertIn("quote", why)

    def test_9_score_basis_none_without_key_or_open(self):
        self.assertEqual(ck.score(ans("Open"), {"final": None})["basis"], "none")
        self.assertEqual(ck.score(ans("Open"), None)["basis"], "none")
        self.assertEqual(ck.score(ans("Open"), {"final": "Open (rubric)"})["basis"], "none")


class Decide(unittest.TestCase):
    AGREE = {"verdict": "agree", "findings": []}

    def test_7_ai_agree_alone_is_uncertain(self):
        st, why = ck.decide([], self.AGREE, ans("A"))
        self.assertEqual((st, why), ("UNCERTAIN", "no_independent_check"))
        st, why = ck.decide([chk("format", "pass", False), chk("quote", "pass", False)],
                            self.AGREE, ans("A"))
        self.assertEqual((st, why), ("UNCERTAIN", "no_independent_check"))

    def test_7_independent_pass_plus_agree_is_pass(self):
        for kind in ("computed", "key_match"):
            st, _ = ck.decide([chk("format", "pass", False), chk(kind, "pass", True)],
                              self.AGREE, ans("A"))
            self.assertEqual(st, "PASS", kind)

    def test_7_quote_or_format_pass_never_lifts(self):
        st, _ = ck.decide([chk("quote", "pass", False), chk("format", "pass", False),
                           chk("computed", "unknown", False)], self.AGREE, ans("A"))
        self.assertEqual(st, "UNCERTAIN")

    def test_7_any_code_fail_is_fail_even_with_agree(self):
        st, why = ck.decide([chk("computed", "pass", True), chk("quote", "fail", False)],
                            self.AGREE, ans("A"))
        self.assertEqual((st, why), ("FAIL", "check_failed: quote"))
        self.assertEqual(ck.decide([chk("format", "fail", False)], None, ans("A"))[0], "FAIL")

    def test_7_disagree_is_fail(self):
        st, why = ck.decide([chk("computed", "pass", True)],
                            {"verdict": "disagree", "findings": ["x"]}, ans("A"))
        self.assertEqual((st, why), ("FAIL", "reviewer_disagrees"))

    def test_7_unsure_missing_review_and_uncertainty(self):
        good = [chk("computed", "pass", True)]
        self.assertEqual(ck.decide(good, {"verdict": "unsure", "findings": []}, ans("A")),
                         ("UNCERTAIN", "reviewer_unsure"))
        self.assertEqual(ck.decide(good, None, ans("A")), ("UNCERTAIN", "no_review"))
        a = ans("A", uncertainty={"level": "medium", "reason": "r"})
        self.assertEqual(ck.decide(good, self.AGREE, a), ("UNCERTAIN", "solver_uncertainty_not_low"))

    def test_score_key(self):
        self.assertEqual(ck.score(ans("A"), {"final": "A"})["detail"], "matches key")
        s = ck.score(ans("B"), {"final": "A"})
        self.assertEqual((s["points"], s["max"], s["basis"], s["detail"]),
                         (0, 1, "official_key", "differs_from_key"))
        self.assertEqual(ck.score(ans("A"), {"final": None})["basis"], "none")


if __name__ == "__main__":
    unittest.main()

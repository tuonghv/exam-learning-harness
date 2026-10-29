"""Tests 5-9 of docs/design/phase-4-engine-core.md (+D6 independence); REQ-0010 AC3. No model call."""
import io
import contextlib
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TOOLS = os.path.join(ROOT, "tools", "examples")  # the old-command shims
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.core import decision as dc, safe_eval as sev  # noqa: E402
from exam_engine.pipeline import scorer as sc, verifier as vf  # noqa: E402
from exam_engine.adapters import claude as exam_llm  # noqa: E402
from exam_engine import cli, engine as er  # noqa: E402
from exam_engine.core import schema as sch  # noqa: E402

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
        self.assertAlmostEqual(sev.safe_eval("2*sqrt(3)"), 3.4641016, places=6)
        for expr, want in (("2**10", 1024), ("-3+4", 1), ("10 % 3", 1), ("abs(-2)", 2),
                           ("log(100)", 2), ("ln(e)", 1), ("round(2.567, 2)", 2.57),
                           ("(1+2)*3/9", 1), ("+5", 5)):
            self.assertAlmostEqual(sev.safe_eval(expr), want, msg=expr)
        self.assertAlmostEqual(sev.safe_eval("sin(pi)"), 0, places=9)
        self.assertIsInstance(sev.safe_eval("3"), float)

    def test_5_refused_code_names_attributes(self):
        for expr in ("__import__('os')", "__import__('os').system('true')", "x", "os",
                     "().__class__", "(1).real", "pi.real", "math.sqrt(4)", "open('f')",
                     "lambda: 1", "[1, 2]", "{1: 2}", "1 if 1 else 2", "True", "None",
                     "'abc'", "b'a'", "len('a')", "sqrt(x=4)", "sqrt()", "sqrt(1, 2)",
                     "round(1, 2, 3)", "sqrt.__call__(4)", "eval('1')", "1 < 2", "1; 2",
                     "import os", "a = 1", "~1", "1 << 2", "2 // 1", "1j", "(1+2j)",
                     "[x for x in ()]"):
            with self.assertRaises(ValueError, msg=expr):
                sev.safe_eval(expr)

    def test_5_refused_bad_input_and_math_errors(self):
        for expr in ("", "   ", None, 5, "1/0", "sqrt(-1)", "log(0)", "exp(1000)", "(1+",
                     "9" * 300, "1+" * 150 + "1", "(" * 500 + "1" + ")" * 500):
            with self.assertRaises(ValueError, msg=str(expr)[:30]):
                sev.safe_eval(expr)

    def test_5_exponent_cap_cheap(self):
        for expr in ("2**101", "10**1000", "2**-101", "2**(50*3)"):
            with self.assertRaises(ValueError, msg=expr):
                sev.safe_eval(expr)
        self.assertEqual(sev.safe_eval("2**100"), float(2 ** 100))

    def test_5_power_bomb_refused(self):
        for expr in ("9**9**9", "9**(9**9)", "2**(9**9)"):
            with self.assertRaises(ValueError, msg=expr):
                sev.safe_eval(expr)

    def test_5_huge_strings_refused(self):
        for expr in ("'a'*10**9", "'a'*99999999", "'a'" + "*2" * 40, "1" * 10000):
            with self.assertRaises(ValueError, msg=expr[:30]):
                sev.safe_eval(expr)


class DetChecks(unittest.TestCase):
    def kinds(self, cs):
        return [(c["kind"], c["result"], c["independent"]) for c in cs]

    def test_6_computed_pass_and_fail(self):
        cs = vf.det_checks(QNUM, ans("3.46", expr="2*sqrt(3)"), NUM)
        comp = [c for c in cs if c["kind"] == "computed"][0]
        self.assertEqual((comp["result"], comp["independent"]), ("pass", True))
        self.assertIn("arithmetic only", comp["detail"])
        comp = [c for c in vf.det_checks(QNUM, ans("3.47", expr="2*sqrt(3)"), NUM)
                if c["kind"] == "computed"][0]
        self.assertEqual(comp["result"], "fail")
        comp = [c for c in vf.det_checks(QNUM, ans("7", expr="3+4"), NUM)
                if c["kind"] == "computed"][0]
        self.assertEqual(comp["result"], "pass")
        comp = [c for c in vf.det_checks(QNUM, ans("1,5 m", expr="3/2"), NUM)
                if c["kind"] == "computed"][0]
        self.assertEqual(comp["result"], "pass")  # decimal comma and unit

    def test_6_computed_unusable_is_unknown_and_not_independent(self):
        for a in (ans("3.46", expr="__import__('os')"), ans("no number", expr="1+1"),
                  ans("3.46", expr="9**9**9")):
            comp = [c for c in vf.det_checks(QNUM, a, NUM) if c["kind"] == "computed"][0]
            self.assertEqual((comp["result"], comp["independent"]), ("unknown", False))
        self.assertEqual([c for c in vf.det_checks(QNUM, ans("3.46"), NUM)
                          if c["kind"] == "computed"], [])  # no expr, no check

    def test_6_format_letter(self):
        for a, want in (("A", "pass"), ("D", "pass"), ("E", "fail"), ("AB", "fail"),
                        ("a", "fail"), ("A. have", "fail")):
            c = [x for x in vf.det_checks(QMC, ans(a), MC) if x["kind"] == "format"][0]
            self.assertEqual(c["result"], want, a)
            self.assertIs(c["independent"], False)

    def test_6_format_ordering(self):
        exam = {"fields": {"Subject": "English", "Task": "Sentence Ordering"}, "passage": ""}
        q = {"id": 1, "text": "Arrange:\na. one\nb. two\nc. three", "options": {}}
        for a, want in (("c-a-b", "pass"), ("a-b-c", "pass"), ("a-a-b", "fail"),
                        ("a-b", "fail"), ("a-b-d", "fail"), ("abc", "fail")):
            c = [x for x in vf.det_checks(q, ans(a), exam) if x["kind"] == "format"][0]
            self.assertEqual(c["result"], want, a)
            self.assertIs(c["independent"], False)

    def test_6_quote_present_and_absent(self):
        cs = vf.det_checks(QMC, ans("A", evidence=["If I ___ time", "The  cat\nsat."]), MC)
        qs = [c for c in cs if c["kind"] == "quote"]
        self.assertEqual([c["result"] for c in qs], ["pass", "pass"])  # whitespace-insensitive
        cs = vf.det_checks(QMC, ans("A", evidence=["The dog barked."]), MC)
        q = [c for c in cs if c["kind"] == "quote"][0]
        self.assertEqual(q["result"], "fail")
        self.assertIs(q["independent"], False)
        self.assertEqual([c for c in vf.det_checks(QMC, ans("A", evidence=[None, "null", " "]), MC)
                          if c["kind"] == "quote"], [])

    def test_6_only_computed_is_independent(self):
        cs = (vf.det_checks(QMC, ans("A", evidence=["If I ___ time"]), MC)
              + vf.det_checks(QNUM, ans("3.46", expr="2*sqrt(3)", evidence=["Compute"]), NUM))
        for c in cs:
            self.assertEqual(c["independent"], c["kind"] == "computed" and c["result"] != "unknown")

    def test_8_declined_runs_no_check(self):
        for a in (ans("A", answer_status="uncertain"), ans("A", answer_status="unanswerable"),
                  ans(None), ans("   "), ans(None, expr="1+1")):
            self.assertTrue(dc.declined(a))
            self.assertEqual(vf.det_checks(QMC, a, MC), [])
            self.assertEqual(dc.decide([], {"verdict": "agree", "findings": []}, a),
                             ("UNCERTAIN", "solver_declined"))
        self.assertFalse(dc.declined(ans("A")))

    def test_9_literature_open_only_format_and_quote(self):
        cs = vf.det_checks(QLIT, ans("Open", evidence=["Quote line one.", "Not there"]), LIT)
        self.assertEqual(self.kinds(cs), [("format", "pass", False), ("quote", "pass", False),
                                          ("quote", "fail", False)])
        cs = vf.det_checks(QLIT, ans("Some essay", expr="1+1"), LIT)
        self.assertEqual(cs[0]["kind"], "format")
        self.assertEqual(cs[0]["result"], "fail")  # Literature answer must be Open

    def test_9_literature_always_uncertain(self):
        forged = [chk("format", "pass", True), chk("computed", "pass", True)]
        agree = {"verdict": "agree", "findings": []}
        st, why = dc.decide(forged, agree, ans("Open"))
        self.assertEqual(st, "UNCERTAIN")
        self.assertIn("open_task_no_rubric", why)
        st, why = dc.decide([chk("quote", "fail", False)], agree, ans("Open"))
        self.assertEqual(st, "UNCERTAIN")
        self.assertIn("quote", why)

    def test_9_score_basis_none_without_key_or_open(self):
        self.assertEqual(sc.score(ans("Open"), {"final": None})["basis"], "none")
        self.assertEqual(sc.score(ans("Open"), None)["basis"], "none")
        self.assertEqual(sc.score(ans("Open"), {"final": "Open (rubric)"})["basis"], "none")


class Decide(unittest.TestCase):
    AGREE = {"verdict": "agree", "findings": []}

    def test_7_ai_agree_alone_is_uncertain(self):
        st, why = dc.decide([], self.AGREE, ans("A"))
        self.assertEqual((st, why), ("UNCERTAIN", "no_independent_check"))
        st, why = dc.decide([chk("format", "pass", False), chk("quote", "pass", False)],
                            self.AGREE, ans("A"))
        self.assertEqual((st, why), ("UNCERTAIN", "no_independent_check"))

    def test_7_independent_pass_plus_agree_is_pass(self):
        for kind in ("computed", "key_match"):
            st, _ = dc.decide([chk("format", "pass", False), chk(kind, "pass", True)],
                              self.AGREE, ans("A"))
            self.assertEqual(st, "PASS", kind)

    def test_7_quote_or_format_pass_never_lifts(self):
        st, _ = dc.decide([chk("quote", "pass", False), chk("format", "pass", False),
                           chk("computed", "unknown", False)], self.AGREE, ans("A"))
        self.assertEqual(st, "UNCERTAIN")

    def test_7_any_code_fail_is_fail_even_with_agree(self):
        st, why = dc.decide([chk("computed", "pass", True), chk("quote", "fail", False)],
                            self.AGREE, ans("A"))
        self.assertEqual((st, why), ("FAIL", "check_failed: quote"))
        self.assertEqual(dc.decide([chk("format", "fail", False)], None, ans("A"))[0], "FAIL")

    def test_7_disagree_is_fail(self):
        st, why = dc.decide([chk("computed", "pass", True)],
                            {"verdict": "disagree", "findings": ["x"]}, ans("A"))
        self.assertEqual((st, why), ("FAIL", "reviewer_disagrees"))

    def test_7_unsure_missing_review_and_uncertainty(self):
        good = [chk("computed", "pass", True)]
        self.assertEqual(dc.decide(good, {"verdict": "unsure", "findings": []}, ans("A")),
                         ("UNCERTAIN", "reviewer_unsure"))
        self.assertEqual(dc.decide(good, None, ans("A")), ("UNCERTAIN", "no_review"))
        a = ans("A", uncertainty={"level": "medium", "reason": "r"})
        self.assertEqual(dc.decide(good, self.AGREE, a), ("UNCERTAIN", "solver_uncertainty_not_low"))

    def test_score_key(self):
        self.assertEqual(sc.score(ans("A"), {"final": "A"})["detail"], "matches key")
        s = sc.score(ans("B"), {"final": "A"})
        self.assertEqual((s["points"], s["max"], s["basis"], s["detail"]),
                         (0, 1, "official_key", "differs_from_key"))
        self.assertEqual(sc.score(ans("A"), {"final": None})["basis"], "none")


class SafeEvalRegression(unittest.TestCase):
    """Verifier defects: every refusal is a prompt ValueError (< 2 s), never a hang or other error."""

    def refused(self, expr):
        t0 = time.time()
        with self.assertRaises(ValueError, msg=expr[:40]):
            sev.safe_eval(expr)
        self.assertLess(time.time() - t0, 2.0, expr[:40])

    def test_5_value_and_overflow_refused_fast(self):
        for expr in ("(10**100)**4", "((((9**99)**99)**99)**99)**99", "10**100*10**100",
                     "10**101", "exp(500)", "1e308*10", "1e200"):
            self.refused(expr)

    def test_5_round_digits_refused_fast(self):
        for expr in ("round(5,-999999999)", "round(5,2.5)", "round(5,16)", "round(5,-16)"):
            self.refused(expr)
        self.assertEqual(sev.safe_eval("round(5.55,1)"), round(5.55, 1))

    def test_5_math_errors_refused_fast(self):
        for expr in ("1/0", "sqrt(-1)", "log(0)", "5%0", "0**-1"):
            self.refused(expr)

    def test_5_depth_and_length_caps(self):
        deep = "-(" * 45 + "1" + ")" * 45
        self.assertLess(len(deep), sev.MAX_EXPR_LEN)
        self.refused(deep)
        ok = "-(" * 10 + "1" + ")" * 10
        self.assertEqual(sev.safe_eval(ok), 1.0)
        self.refused("1+" * 200 + "1")  # 401 chars: length cap

    def test_5_valid_still_work(self):
        self.assertAlmostEqual(sev.safe_eval("2*sqrt(3)"), 3.4641, places=4)
        self.assertEqual(sev.safe_eval("round(2.567,2)"), 2.57)
        self.assertAlmostEqual(sev.safe_eval("pi*2"), 6.283185, places=5)
        self.assertEqual(sev.safe_eval("10**99"), 1e99)

    def test_6_bomb_expr_in_computed_check_is_unevaluable(self):
        t0 = time.time()
        for expr in ("(10**100)**4", "round(5,-999999999)"):
            cs = vf.det_checks(QNUM, ans("3.46", expr=expr), NUM)
            comp = [c for c in cs if c["kind"] == "computed"][0]
            self.assertEqual((comp["result"], comp["independent"]), ("unknown", False))
        self.assertLess(time.time() - t0, 2.0)

    def test_6_run_completes_with_bomb_expr_and_valid_result(self):
        tmp = tempfile.mkdtemp(prefix="exam_chk_test_")
        self.addCleanup(shutil.rmtree, tmp, True)
        exam = os.path.join(tmp, "e.md")
        with open(exam, "w", encoding="utf-8") as fh:
            fh.write("# Exam Input\n\nSubject: Mathematics\nLevel: Grade 12\nExam type: T\n"
                     "Task: Short Answer\nMode: Solve\n\n## Instructions\n\nSolve.\n\n"
                     "## Question 1\n\nCompute something.\n")
        reply = json.dumps({"schema_version": "1.0", "questions": [{
            "id": "1", "answer": "3.46", "answer_status": "answered", "solution": ["s"],
            "explanation": "e", "expr": "(10**100)**4", "evidence": [],
            "uncertainty": {"level": "low", "reason": "r"},
            "reasoning_status": "not_independently_verified"}]})
        review = json.dumps({"reviews": [{"id": "1", "verdict": "agree", "findings": []}]})
        replies = [reply, review, reply, review]
        calls = []

        def llm(prompt):
            calls.append(prompt)
            return exam_llm.Call(True, replies.pop(0), 0.0, "", "", 0.0)
        c = {"max_attempts": 2, "max_cost_usd": 1.0, "timeout": 5, "model": "m", "key": None,
             "llm_name": "mock"}
        out = os.path.join(tmp, "out")
        with contextlib.redirect_stderr(io.StringIO()):
            res, code = er.run(exam, out, c, llm)
        self.assertIn(code, (0, 1))
        with open(os.path.join(out, "result.json"), encoding="utf-8") as fh:
            disk = json.load(fh)
        self.assertEqual(sch.validate(disk, sch.RESULT), [])
        q = disk["questions"][0]
        self.assertNotEqual(q["verification_status"], "PASS")  # unevaluable is not proof
        self.assertTrue(all(not k["independent"] for k in q["checks"]))
        self.assertLessEqual(len(calls), 1 + 2 * c["max_attempts"])


if __name__ == "__main__":
    unittest.main()

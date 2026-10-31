"""Tests 4, 9-14 of docs/design/phase-4-engine-core.md; REQ-0010 AC1-AC6. Fake llm / --mock only:
subprocess.Popen is patched to fail, so a real `claude` call can never happen."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TOOLS = os.path.join(ROOT, "tools", "examples")  # the old-command shims
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.adapters import claude as exam_llm  # noqa: E402
from exam_engine.pipeline import parser as ep  # noqa: E402
from exam_engine import cli, engine as er  # noqa: E402
from exam_engine.core import schema as sch  # noqa: E402

INPUT_001 = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(HERE, "fixtures", "mock_english_001.json")
SENTINEL = "ZZ-KEY-SENTINEL-91"

HEAD = "# Exam Input\n\nSubject: %s\nLevel: Grade 12\nExam type: Test\nTask: %s\nMode: Solve\n\n"
MATH2 = (HEAD % ("Mathematics", "Short Answer") + "## Instructions\n\nSolve.\n\n"
         "## Question 1\n\nCompute 2*sqrt(3).\n\n## Question 2\n\nCompute 3+4.\n")
MATH1 = HEAD % ("Mathematics", "Short Answer") + "## Instructions\n\nSolve.\n\n## Question 1\n\nCompute 2*sqrt(3).\n"
LIT1 = (HEAD % ("Literature", "Essay") + "## Instructions\n\nWrite.\n\n## Passage\n\nQuote line one.\n\n"
        "## Question 1\n\nAnalyse the passage.\n")


def a(i, answer, **kw):
    d = {"id": str(i), "type": "x", "answer": answer, "answer_status": "answered",
         "solution": ["s"], "explanation": "e", "checks": [], "expr": None, "evidence": [],
         "uncertainty": {"level": "low", "reason": "r"},
         "reasoning_status": "not_independently_verified", "issues": []}
    d.update(kw)
    return d


def solve(*answers):
    return json.dumps({"schema_version": "1.0", "questions": list(answers), "input_issues": []})


def qa(*pairs):
    return json.dumps({"reviews": [{"id": str(i), "verdict": v, "findings": []} for i, v in pairs]})


def ok(text, cost=0.0):
    return exam_llm.Call(True, text, cost, "", "", 0.0)


class Script(object):
    """Fake llm: replays items (str -> ok Call, Call as is) and records every prompt."""

    def __init__(self, *items, **kw):
        self.items, self.prompts, self.events = list(items), [], kw.get("events")

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if self.events is not None:
            self.events.append("llm")
        if not self.items:
            raise AssertionError("unexpected extra llm call #%d" % len(self.prompts))
        it = self.items.pop(0)
        return ok(it) if isinstance(it, str) else it


def cfg(**kw):
    c = {"max_attempts": 2, "max_cost_usd": 1.0, "timeout": 5, "model": "sonnet", "key": None,
         "llm_name": "mock"}
    c.update(kw)
    return c


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="exam_run_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        p = mock.patch("subprocess.Popen", side_effect=AssertionError("real subprocess reached"))
        p.start()
        self.addCleanup(p.stop)
        self.out = os.path.join(self.tmp, "out")

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def go(self, exam, llm, **kw):
        path = exam if os.path.isfile(exam) else self.write("exam.md", exam)
        with contextlib.redirect_stderr(io.StringIO()):
            return er.run(path, self.out, cfg(**kw), llm)

    def result_file(self):
        with open(os.path.join(self.out, "result.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def main(self, *argv):
        o, e = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            code = cli.solve_main(list(argv))
        return code, o.getvalue(), e.getvalue()


class RetryAndCaps(Base):
    def test_4_malformed_twice_is_uncertain_attempts_equals_limit(self):
        llm = Script("prose, no json", "still prose")
        res, code = self.go(INPUT_001, llm)
        q = res["questions"][0]
        self.assertEqual((q["verification_status"], q["status_reason"]), ("UNCERTAIN", "malformed_output"))
        self.assertEqual(q["attempts"], 2)
        self.assertEqual(res["run"]["calls"], 2)
        self.assertTrue(q["unresolved"])
        self.assertEqual(code, 1)
        self.assertEqual(sch.validate(self.result_file(), sch.RESULT), [])

    def test_4_call_count_never_above_1_plus_2n(self):
        for n in (1, 2, 3):
            # solver answers, reviewer always disagrees -> FAIL, retried until the limit
            llm = Script(*([solve(a(1, "A")), qa((1, "disagree"))] * 10))
            res, code = self.go(INPUT_001, llm, max_attempts=n)
            self.assertLessEqual(len(llm.prompts), 1 + 2 * n)
            self.assertEqual(res["run"]["calls"], len(llm.prompts))
            self.assertEqual(res["questions"][0]["attempts"], n)
            self.assertEqual(res["questions"][0]["verification_status"], "FAIL")
            self.assertEqual(code, 1)

    def test_4_runner_call_cap_and_cost_cap(self):
        rn = er.Runner(cfg(max_attempts=1), Script(*(["x"] * 9)), [])
        for _ in range(3):
            rn.call("p")
        with self.assertRaises(er.Stop) as cm:
            rn.call("p")
        self.assertEqual(cm.exception.cls, "call_cap")
        rn = er.Runner(cfg(max_cost_usd=0.5), Script(ok("x", 0.6), "y"), [])
        rn.call("p")
        with self.assertRaises(er.Stop) as cm:
            rn.call("p")
        self.assertEqual(cm.exception.cls, "cost_cap")

    def test_4_cost_cap_stops_run_with_exit_3(self):
        llm = Script(ok(solve(a(1, "A")), 2.0), "never used")
        res, code = self.go(INPUT_001, llm, max_cost_usd=1.0)
        self.assertEqual(code, 3)
        self.assertEqual(res["run"]["stopped"], "cost_cap")
        self.assertEqual(len(llm.prompts), 1)

    def test_no_independent_check_is_uncertain_without_retry(self):
        llm = Script(solve(a(1, "A", evidence=["If I ______ enough time tomorrow"])),
                     qa((1, "agree")))
        res, code = self.go(INPUT_001, llm)
        q = res["questions"][0]
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual((q["verification_status"], q["status_reason"]),
                         ("UNCERTAIN", "no_independent_check"))
        self.assertEqual(q["attempts"], 1)
        self.assertFalse(q["unresolved"])
        self.assertEqual(code, 1)
        self.assertTrue(all(not c["independent"] for c in q["checks"]))
        self.assertNotIn("PASS", [x["verification_status"] for x in res["questions"]])


class Decisions(Base):
    def test_computed_pass_with_agree_gives_pass_exit_0(self):
        llm = Script(solve(a(1, "3.46", expr="2*sqrt(3)")), qa((1, "agree")))
        res, code = self.go(MATH1, llm)
        self.assertEqual((res["questions"][0]["verification_status"], code), ("PASS", 0))
        self.assertTrue(any(c["kind"] == "computed" and c["independent"]
                            for c in res["questions"][0]["checks"]))
        self.assertEqual(res["summary"]["pass"], 1)

    def test_lang_cfg_sets_result_language(self):
        for lang, want in ((None, "vi"), ("en", "en")):
            res, _ = self.go(MATH1, Script(solve(a(1, "3.46", expr="2*sqrt(3)")), qa((1, "agree"))), lang=lang)
            self.assertEqual(res["exam"]["language"], want)

    def test_cli_lang_dry_run(self):
        self.assertIn("Language: en", self.main(INPUT_001, "--dry-run", "--lang", "en")[1])
        self.assertIn("Language: vi", self.main(INPUT_001, "--dry-run")[1])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            self.main(INPUT_001, "--dry-run", "--lang", "fr")
        self.assertEqual(cm.exception.code, 2)

    def test_8_declined_is_uncertain_without_check_or_qa_call(self):
        llm = Script(solve(a(1, None, answer_status="unanswerable", expr="1+1")))
        res, code = self.go(MATH1, llm, max_attempts=1)
        q = res["questions"][0]
        self.assertEqual((q["verification_status"], q["status_reason"]), ("UNCERTAIN", "solver_declined"))
        self.assertEqual(q["checks"], [])
        self.assertEqual(len(llm.prompts), 1)  # no QA call for nothing to review
        self.assertEqual(code, 1)

    def test_8b_decline_on_missing_referenced_part_says_missing_text(self):
        exam = MATH1.replace("Compute 2*sqrt(3).", "(1) aa\n(2) bb\nMain idea of paragraph (5)?")
        llm = Script(solve(a(1, None, answer_status="unanswerable")))
        res, _ = self.go(exam, llm, max_attempts=1)
        self.assertEqual(res["questions"][0]["status_reason"],
                         "solver_declined: missing_text (paragraph (5))")

    def test_8c_answered_flagged_question_reason_unchanged(self):
        exam = MATH1.replace("Compute 2*sqrt(3).", "Main idea of paragraph (5)?")
        llm = Script(solve(a(1, "B")), qa((1, "agree")))
        res, _ = self.go(exam, llm)
        self.assertNotIn("missing_text", res["questions"][0]["status_reason"])

    def test_9_literature_open_always_uncertain_basis_none(self):
        llm = Script(solve(a(1, "Open", evidence=["Quote line one."])), qa((1, "agree")))
        res, code = self.go(LIT1, llm)
        q = res["questions"][0]
        self.assertEqual(q["verification_status"], "UNCERTAIN")
        self.assertEqual(q["answer"], "Open")
        self.assertEqual(q["score"]["basis"], "none")
        self.assertEqual(len(llm.prompts), 2)  # open item is not retried
        self.assertEqual({c["kind"] for c in q["checks"]} - {"ai_review"}, {"format", "quote"})
        self.assertEqual(code, 1)
        # even with a key file the Open item is not scored
        key = self.write("key.md", "# Expected\n\n## Question 1\n\nFinal answer: Open (rubric)\n")
        llm = Script(solve(a(1, "Open")), qa((1, "agree")))
        res, _ = self.go(LIT1, llm, key=key)
        self.assertEqual(res["questions"][0]["score"]["basis"], "none")
        self.assertEqual(res["questions"][0]["verification_status"], "UNCERTAIN")

    def test_13_missing_question_fails_and_summary_is_recounted(self):
        llm = Script(solve(a(1, "3.46", expr="2*sqrt(3)")), qa((1, "agree")),
                     solve(a(1, "3.46", expr="2*sqrt(3)")))  # retry for id 2 omits it again
        res, code = self.go(MATH2, llm)
        by = {q["id"]: q for q in res["questions"]}
        self.assertEqual(by["1"]["verification_status"], "PASS")
        self.assertEqual((by["2"]["verification_status"], by["2"]["status_reason"]),
                         ("FAIL", "missing_in_output"))
        self.assertEqual(by["2"]["attempts"], 2)
        self.assertEqual(by["1"]["attempts"], 1)
        s = res["summary"]
        self.assertEqual((s["pass"], s["fail"], s["uncertain"]), (1, 1, 0))
        self.assertEqual(s["unresolved"], sum(q["unresolved"] for q in res["questions"]))
        self.assertEqual(code, 1)
        self.assertEqual(len(llm.prompts), 3)
        self.assertNotIn("Compute 2*sqrt(3)", llm.prompts[2].split("Exam file (only the open questions)")[1])

    def test_extra_id_in_output_is_ignored(self):
        llm = Script(solve(a(1, "3.46", expr="2*sqrt(3)"), a(9, "zzz")), qa((1, "agree")))
        res, _ = self.go(MATH1, llm)
        self.assertEqual([q["id"] for q in res["questions"]], ["1"])

    def test_computed_fail_is_fail_and_not_sent_to_qa(self):
        llm = Script(solve(a(1, "9.9", expr="2*sqrt(3)")), solve(a(1, "9.9", expr="2*sqrt(3)")))
        res, code = self.go(MATH1, llm)
        self.assertEqual(res["questions"][0]["verification_status"], "FAIL")
        self.assertEqual(len(llm.prompts), 2)  # solve + retry solve, no QA call at all
        self.assertEqual(code, 1)

    def test_reviewer_disagree_is_fail_even_with_independent_pass(self):
        llm = Script(solve(a(1, "3.46", expr="2*sqrt(3)")), qa((1, "disagree")),
                     solve(a(1, "3.46", expr="2*sqrt(3)")), qa((1, "disagree")))
        res, _ = self.go(MATH1, llm)
        self.assertEqual(res["questions"][0]["status_reason"], "reviewer_disagrees")


class KeyIsolation(Base):
    def keyfile(self, final="B. had"):
        return self.write("key.md", "Solution\n\nQuestion 1\n\nCorrect answer: %s\n\nExplanation\n\n"
                          "Hidden note %s here.\n" % (final, SENTINEL))

    def test_10_sentinel_in_no_prompt_and_not_in_result(self):
        key = self.keyfile("A. have")
        # round 1: reviewer disagrees -> a retry solve + QA round happens too
        llm = Script(solve(a(1, "A")), qa((1, "disagree")), solve(a(1, "A")), qa((1, "agree")))
        res, code = self.go(INPUT_001, llm, key=key)
        self.assertEqual(len(llm.prompts), 4)
        for p in llm.prompts:
            self.assertNotIn(SENTINEL, p)
            self.assertNotIn("Hidden note", p)
        blob = json.dumps(res, ensure_ascii=False)
        self.assertNotIn(SENTINEL, blob)
        with open(os.path.join(self.out, "result.json"), encoding="utf-8") as fh:
            self.assertNotIn(SENTINEL, fh.read())
        with open(os.path.join(self.out, "run.log"), encoding="utf-8") as fh:
            self.assertNotIn(SENTINEL, fh.read())
        self.assertEqual(res["questions"][0]["verification_status"], "PASS")  # key_match lifted
        self.assertEqual(code, 0)

    def test_10_key_is_read_only_after_the_last_llm_call(self):
        events = []
        real = ep.parse_expected

        def spy(*args, **kw):
            events.append("key")
            return real(*args, **kw)
        llm = Script(solve(a(1, "A")), qa((1, "agree")), events=events)
        with mock.patch.object(ep, "parse_expected", spy):
            self.go(INPUT_001, llm, key=self.keyfile("A. have"))
        self.assertEqual(events, ["llm", "llm", "key"])

    def test_10_key_file_never_opened_before_decision(self):
        key = self.keyfile()
        opened = []
        real_open = open

        def spy(path, *args, **kw):
            if os.fspath(path) == key:
                opened.append(len(llm.prompts))
            return real_open(path, *args, **kw)
        llm = Script(solve(a(1, "A")), qa((1, "agree")))
        with mock.patch("builtins.open", spy):
            self.go(INPUT_001, llm, key=key)
        self.assertEqual(opened, [2])  # opened once, after both calls

    def test_11_key_mismatch_is_fail_differs_from_key_without_further_call(self):
        llm = Script(solve(a(1, "A")), qa((1, "agree")))  # a third call would raise
        res, code = self.go(INPUT_001, llm, key=self.keyfile("B. had"))
        q = res["questions"][0]
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual((q["verification_status"], q["status_reason"]), ("FAIL", "differs_from_key"))
        self.assertEqual((q["score"]["points"], q["score"]["basis"]), (0, "official_key"))
        self.assertTrue(any(f["source"] == "score" and f["code"] == "differs_from_key"
                            for f in q["qa_findings"]))
        self.assertEqual(code, 1)
        self.assertEqual(res["summary"]["points"], 0)

    def test_key_match_lifts_uncertain_to_pass_and_scores(self):
        llm = Script(solve(a(1, "A")), qa((1, "agree")))
        res, code = self.go(INPUT_001, llm, key=self.keyfile("A. have"))
        q = res["questions"][0]
        self.assertEqual(q["verification_status"], "PASS")
        self.assertTrue(any(c["kind"] == "key_match" and c["independent"] for c in q["checks"]))
        self.assertEqual((q["score"]["points"], res["summary"]["max_points"], code), (1, 1, 0))

    def test_key_not_applied_when_run_stopped(self):
        llm = Script(exam_llm.Call(False, "", 0.0, "auth", "401", 0.0))
        res, code = self.go(INPUT_001, llm, key=self.keyfile())
        self.assertEqual(code, 3)
        self.assertEqual(res["questions"][0]["score"]["basis"], "none")


class ExitCodes(Base):
    def test_14_exit_0_1(self):
        res, code = self.go(MATH1, Script(solve(a(1, "3.46", expr="2*sqrt(3)")), qa((1, "agree"))))
        self.assertEqual(code, 0)
        res, code = self.go(INPUT_001, Script(solve(a(1, "A")), qa((1, "agree"))))
        self.assertEqual(code, 1)

    def test_14_exit_2_invalid_input_writes_nothing(self):
        bad = self.write("bad.md", "# Exam Input\n\nSubject: Chemistry\n")
        llm = Script()
        res, code = self.go(bad, llm)
        self.assertEqual((res, code), (None, 2))
        self.assertEqual(llm.prompts, [])
        self.assertFalse(os.path.exists(os.path.join(self.out, "result.json")))
        with contextlib.redirect_stderr(io.StringIO()):
            res, code = er.run(os.path.join(self.tmp, "missing.md"), self.out, cfg(), llm)
        self.assertEqual((res, code), (None, 2))

    def test_14_exit_3_blocking_classes_leave_valid_partial_result(self):
        for cls in ("auth", "rate_limit", "service"):
            shutil.rmtree(self.out, ignore_errors=True)
            llm = Script(exam_llm.Call(False, "", 0.0, cls, "boom %s" % cls, 0.0), "never")
            res, code = self.go(INPUT_001, llm)
            self.assertEqual(code, 3, cls)
            self.assertEqual(len(llm.prompts), 1)
            disk = self.result_file()
            self.assertEqual(sch.validate(disk, sch.RESULT), [], cls)
            self.assertEqual(disk["run"]["stopped"], cls)
            q = disk["questions"][0]
            self.assertEqual(q["verification_status"], "UNCERTAIN")
            self.assertEqual(q["error"]["cls"], cls)

    def test_14_non_blocking_call_failure_retries_not_stops(self):
        llm = Script(exam_llm.Call(False, "", 0.0, "timeout", "t", 0.0),
                     exam_llm.Call(False, "", 0.0, "empty", "e", 0.0))
        res, code = self.go(INPUT_001, llm)
        self.assertEqual((code, res["run"]["stopped"], res["run"]["calls"]), (1, None, 2))
        self.assertEqual(res["questions"][0]["status_reason"], "call_failed")

    def test_14_exit_3_midway_keeps_earlier_pass(self):
        llm = Script(solve(a(1, "3.46", expr="2*sqrt(3)"), a(2, "7", expr="3+4")),
                     exam_llm.Call(False, "", 0.0, "rate_limit", "429", 0.0))
        res, code = self.go(MATH2, llm)
        self.assertEqual(code, 3)
        self.assertEqual(sch.validate(self.result_file(), sch.RESULT), [])
        self.assertEqual(res["run"]["stopped"], "rate_limit")


class Cli(Base):
    def test_12_mock_fixture_via_main_never_reaches_real_runner(self):
        code, out, _ = self.main(INPUT_001, "--mock", MOCK, "--out", self.out)
        res = self.result_file()
        self.assertEqual(sch.validate(res, sch.RESULT), [])
        self.assertEqual(res["run"]["llm"], "mock")
        self.assertEqual(code, 1)  # no key: not proven
        self.assertIn("calls=%d" % res["run"]["calls"], out)
        key = os.path.join(ROOT, "examples", "english", "expected-001.md")
        out2 = os.path.join(self.tmp, "out2")
        code, _, _ = self.main(INPUT_001, "--mock", MOCK, "--key", key, "--out", out2)
        self.assertEqual(code, 0)

    def test_12_dry_run_makes_no_call_and_no_output_dir_and_no_key_text(self):
        key = self.write("key.md", "Correct answer: A. have\n\nHidden note %s\n" % SENTINEL)
        with mock.patch.object(exam_llm, "run_claude", side_effect=AssertionError("called")):
            code, out, err = self.main(INPUT_001, "--dry-run", "--key", key)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("calls <= 5, cap $1.00", out)
        self.assertIn("If I ______ enough time tomorrow", out)
        self.assertNotIn(SENTINEL, out)
        self.assertFalse(os.path.exists(self.out))

    def test_12_no_mode_or_two_modes_is_usage_exit_2_without_call(self):
        with mock.patch.object(exam_llm, "run_claude", side_effect=AssertionError("called")):
            for argv in ([INPUT_001, "--out", self.out],
                         [INPUT_001, "--out", self.out, "--dry-run", "--mock", MOCK],
                         [INPUT_001, "--out", self.out, "--real", "--mock", MOCK],
                         [INPUT_001, "--mock", MOCK],  # no --out
                         [INPUT_001, "--mock", MOCK, "--out", self.out, "--max-attempts", "0"]):
                code, out, err = self.main(*argv)
                self.assertEqual(code, 2, argv)
                self.assertIn("usage", err)
        self.assertFalse(os.path.exists(os.path.join(self.out, "result.json")))

    def test_12_mock_file_missing_or_bad_is_exit_2(self):
        self.assertEqual(self.main(INPUT_001, "--mock", os.path.join(self.tmp, "nope.json"),
                                   "--out", self.out)[0], 2)
        bad = self.write("bad.json", '{"not": "a list"}')
        self.assertEqual(self.main(INPUT_001, "--mock", bad, "--out", self.out)[0], 2)

    def test_12_real_prints_count_and_cap_first_and_uses_empty_temp_cwd(self):
        seen = {}
        o = io.StringIO()

        def fake(prompt, *, model, timeout_s, cwd=None, **kw):
            seen.update(printed=o.getvalue(), cwd=cwd, listing=os.listdir(cwd), model=model,
                        timeout=timeout_s, isdir=os.path.isdir(cwd))
            return exam_llm.Call(False, "", 0.0, "auth", "401", 0.0)
        with mock.patch.object(exam_llm, "run_claude", fake), \
                contextlib.redirect_stdout(o), contextlib.redirect_stderr(io.StringIO()):
            code = cli.solve_main([INPUT_001, "--real", "--out", self.out, "--max-cost-usd", "0.5",
                            "--model", "haiku", "--timeout", "9"])
        self.assertEqual(code, 3)
        self.assertIn("calls <= 5, cap $0.50", seen["printed"])
        self.assertTrue(seen["isdir"])
        self.assertEqual(seen["listing"], [])
        self.assertNotEqual(os.path.realpath(seen["cwd"]), os.path.realpath(ROOT))
        self.assertFalse(os.path.exists(seen["cwd"]))  # removed afterwards
        self.assertEqual((seen["model"], seen["timeout"]), ("haiku", 9.0))
        self.assertEqual(self.result_file()["run"]["llm"], "claude-p")

    def test_12_invalid_exam_through_main_is_exit_2(self):
        bad = self.write("bad.md", "# Exam Input\n\nSubject: Chemistry\n")
        self.assertEqual(self.main(bad, "--mock", MOCK, "--out", self.out)[0], 2)
        self.assertEqual(self.main(bad, "--dry-run")[0], 2)

    def test_scratch_dirs_are_cleaned(self):
        before = {n for n in os.listdir(tempfile.gettempdir()) if n.startswith("exam_run_")}
        self.main(INPUT_001, "--mock", MOCK, "--out", self.out)
        after = {n for n in os.listdir(tempfile.gettempdir()) if n.startswith("exam_run_")}
        self.assertLessEqual(after, before | {os.path.basename(self.tmp)})


if __name__ == "__main__":
    unittest.main()

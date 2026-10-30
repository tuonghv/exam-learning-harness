"""REQ-0027: gen-exams writes paired exams with keys, rejects wrong keys and leaks, lessons classify; $0."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))

from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import genexam  # noqa: E402

GOOD = {"skill": "Xác suất", "question": "Một hộp có 5 bi đỏ và 4 bi xanh, lấy 3 bi. Tính xác suất có ít nhất một bi xanh.",
        "final_answer": "37/42", "solution": "1 - C(5,3)/C(9,3) = 37/42", "check": "1 - 10/84"}


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cli.main(argv)
    return rc, out.getvalue(), err.getvalue()


class Gen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def mockfile(self, replies):
        p = os.path.join(self.tmp, "mock.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump([json.dumps(r) if isinstance(r, dict) else r for r in replies], fh)
        return p

    def test_dry_run_writes_nothing(self):
        out = os.path.join(self.tmp, "g")
        rc, so, _ = run(["gen-exams", "--dry-run", "--out", out])
        self.assertEqual(rc, 0)
        self.assertIn("no call made", so)
        self.assertFalse(os.path.exists(out))

    def test_no_mode_is_usage_error(self):
        self.assertEqual(run(["gen-exams"])[0], 2)

    def test_mock_writes_pair_manifest_and_passes_checker(self):
        out = os.path.join(self.tmp, "g")
        rc, so, _ = run(["gen-exams", "--no-qa", "--n", "2", "--out", out, "--mock", self.mockfile([GOOD, GOOD])])
        self.assertEqual(rc, 0, so)
        for n in (101, 102):
            self.assertTrue(os.path.isfile(os.path.join(out, "inputs", "math", "input-%d.md" % n)))
            key = open(os.path.join(out, "keys", "math", "expected-%d.md" % n), encoding="utf-8").read()
            self.assertIn("Final answer: 37/42", key)
        man = json.load(open(os.path.join(out, "manifest.json"), encoding="utf-8"))
        self.assertTrue(man["generated"] and not man["reviewed"])
        self.assertEqual(man["runs"][0]["items"], ["math/101", "math/102"])
        # a second run continues the numbering
        run(["gen-exams", "--no-qa", "--n", "1", "--out", out, "--mock", self.mockfile([GOOD])])
        self.assertTrue(os.path.isfile(os.path.join(out, "inputs", "math", "input-103.md")))

    def test_generated_pair_passes_format_checker(self):
        out = os.path.join(self.tmp, "g")
        run(["gen-exams", "--no-qa", "--n", "1", "--out", out, "--mock", self.mockfile([GOOD])])
        root = os.path.join(self.tmp, "r")
        os.makedirs(os.path.join(root, "evals"))
        for k in ("inputs", "keys"):
            shutil.copytree(os.path.join(out, k), os.path.join(root, "evals", k))
        rc, so, _ = run(["check-examples", "--root", root])
        self.assertEqual(rc, 0, so)
        self.assertIn("1 pairs", so)

    def test_no_key_text_in_input(self):
        out = os.path.join(self.tmp, "g")
        run(["gen-exams", "--no-qa", "--n", "1", "--out", out, "--mock", self.mockfile([GOOD])])
        text = open(os.path.join(out, "inputs", "math", "input-101.md"), encoding="utf-8").read()
        self.assertNotIn("37/42", text)
        self.assertNotIn("C(5,3)", text)

    def test_wrong_key_rejected_after_retry(self):
        bad = dict(GOOD, final_answer="5/6")
        rc, _, err = run(["gen-exams", "--no-qa", "--n", "1", "--out", os.path.join(self.tmp, "g"),
                          "--mock", self.mockfile([bad, bad])])
        self.assertEqual(rc, 3)
        self.assertIn("bad_key", err)

    def test_retry_recovers(self):
        rc, _, _ = run(["gen-exams", "--no-qa", "--n", "1", "--out", os.path.join(self.tmp, "g"),
                        "--mock", self.mockfile(["not json", GOOD])])
        self.assertEqual(rc, 0)

    def test_leak_detected(self):
        leaky = dict(GOOD, question="Đáp số là 37/42?", solution="Đáp số là 37/42?")
        self.assertTrue(genexam.leak_check(genexam.input_md("math", leaky), leaky))
        self.assertFalse(genexam.leak_check(genexam.input_md("math", GOOD), GOOD))

    def test_cost_cap(self):
        with self.assertRaises(genexam.GenError) as cm:
            genexam.generate("math", 2, "s", lambda p: __import__("exam_engine.adapters.claude", fromlist=["x"]).Call(
                True, json.dumps(GOOD), 0.6, "", "", 0.0), max_cost=0.5)
        self.assertEqual(cm.exception.code, "cost_cap")

    def test_qa_pass_fail_and_rejected_dir(self):
        out = os.path.join(self.tmp, "g")
        ok = {"verdict": "ok", "bad_step": "", "my_answer": "37/42"}
        wrong = {"verdict": "wrong", "bad_step": "step 2", "my_answer": "5/6"}
        rc, so, _ = run(["gen-exams", "--n", "2", "--out", out,
                         "--mock", self.mockfile([GOOD, ok, GOOD, wrong])])
        self.assertEqual(rc, 0, so)
        self.assertIn("qa_fail=1", so)
        self.assertTrue(os.path.isfile(os.path.join(out, "inputs", "math", "input-101.md")))
        self.assertFalse(os.path.exists(os.path.join(out, "inputs", "math", "input-102.md")))
        self.assertTrue(os.path.isfile(os.path.join(out, "rejected", "math", "qa-102.txt")))
        man = json.load(open(os.path.join(out, "manifest.json"), encoding="utf-8"))
        self.assertEqual(man["runs"][0]["qa_counts"]["fail"], 1)
        self.assertEqual(man["runs"][0]["qa_rejected"], ["math/102"])

    def test_qa_ok_verdict_but_different_answer_fails(self):
        status, _, _ = genexam.qa(lambda p: __import__("exam_engine.adapters.claude", fromlist=["x"]).Call(
            True, json.dumps({"verdict": "ok", "bad_step": "", "my_answer": "5/6"}), 0.0, "", "", 0.0), GOOD)
        self.assertEqual(status, "fail")

    def test_qa_plain_integer_answers_match(self):
        obj = dict(GOOD, final_answer="7", check="3+4")
        status, _, _ = genexam.qa(lambda p: __import__("exam_engine.adapters.claude", fromlist=["x"]).Call(
            True, json.dumps({"verdict": "ok", "bad_step": "", "my_answer": "7"}), 0.0, "", "", 0.0), obj)
        self.assertEqual(status, "pass")
        self.assertEqual(genexam.check_reply(obj), [])
        self.assertEqual(genexam.value("x = 3"), genexam.value("3"))
        self.assertEqual(genexam.value("I = 26/3")[0], genexam.value("26/3")[0])

    def test_unsupported_subject(self):
        self.assertEqual(run(["gen-exams", "--subject", "physics", "--dry-run"])[0], 2)


DG = {"skill": "Dãy số", "question": "Cho cấp số cộng có u1 = 3 và công sai 4. Tìm u10.",
      "options": {"A": "39", "B": "43", "C": "36", "D": "40"}, "correct": "A",
      "solution": "u10 = 3 + 9*4 = 39", "check": "3 + 9*4"}


class Dgnl(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def mockfile(self, replies):
        p = os.path.join(self.tmp, "mock.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump([json.dumps(r) for r in replies], fh)
        return p

    def test_pair_written_checked_and_manifest_note(self):
        out = os.path.join(self.tmp, "g")
        qa_ok = {"verdict": "ok", "bad_step": "", "my_answer": "A"}
        rc, so, _ = run(["gen-exams", "--profile", "dgnl", "--n", "1", "--out", out,
                         "--mock", self.mockfile([DG, qa_ok])])
        self.assertEqual(rc, 0, so)
        text = open(os.path.join(out, "inputs", "math", "input-101.md"), encoding="utf-8").read()
        self.assertIn("University Entrance (DGNL)", text)
        self.assertIn("D. 40", text)
        self.assertNotIn("Final answer", text)
        key = open(os.path.join(out, "keys", "math", "expected-101.md"), encoding="utf-8").read()
        self.assertIn("Final answer: A\nCorrect answer: A. 39", key)
        man = json.load(open(os.path.join(out, "manifest.json"), encoding="utf-8"))
        self.assertEqual(man["runs"][0]["profile"], "dgnl")
        self.assertIn("not an official exam", man["runs"][0]["source"])
        root = os.path.join(self.tmp, "r")
        os.makedirs(os.path.join(root, "evals"))
        for k in ("inputs", "keys"):
            shutil.copytree(os.path.join(out, k), os.path.join(root, "evals", k))
        rc, so, _ = run(["check-examples", "--root", root])
        self.assertEqual(rc, 0, so)

    def test_bad_replies_rejected(self):
        for bad in (dict(DG, correct="B"),
                    dict(DG, options={"A": "39", "B": "39", "C": "36", "D": "40"}),
                    dict(DG, options={"A": "39", "B": "43", "C": "36"}),
                    dict(DG, correct="E")):
            self.assertTrue(genexam.check_dgnl(dict(bad)), bad)
        self.assertEqual(genexam.check_dgnl(dict(DG)), [])

    def test_qa_compares_letters(self):
        from exam_engine.adapters import claude
        obj = dict(DG, final_answer="A")

        def reply(letter):
            return lambda p: claude.Call(True, json.dumps({"verdict": "ok", "bad_step": "", "my_answer": letter}),
                                         0.0, "", "", 0.0)
        self.assertEqual(genexam.qa(reply("A"), obj)[0], "pass")
        self.assertEqual(genexam.qa(reply("B"), obj)[0], "fail")
        self.assertIn("A. 39", genexam.qa_prompt(obj))


EN = {"skill": "Conditionals", "question": "If I ______ more time, I would travel abroad.", "passage": "",
      "options": {"A": "have", "B": "had", "C": "will have", "D": "would have"}, "correct": "B",
      "solution": "Second conditional: past simple in the if-clause."}


class DgnlEn(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def mockfile(self, replies):
        p = os.path.join(self.tmp, "mock.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump([json.dumps(r) for r in replies], fh)
        return p

    def test_pair_manifest_and_format(self):
        out = os.path.join(self.tmp, "g")
        rc, so, _ = run(["gen-exams", "--profile", "dgnl-en", "--n", "1", "--out", out,
                         "--mock", self.mockfile([EN, {"answer": "B"}, {"answer": "B"}])])
        self.assertEqual(rc, 0, so)
        text = open(os.path.join(out, "inputs", "english", "input-101.md"), encoding="utf-8").read()
        self.assertIn("University Entrance (DGNL)", text)
        self.assertIn("B. had", text)
        key = open(os.path.join(out, "keys", "english", "expected-101.md"), encoding="utf-8").read()
        self.assertIn("Final answer: B\nCorrect answer: B. had", key)
        self.assertIn("two blind reviews", key)
        man = json.load(open(os.path.join(out, "manifest.json"), encoding="utf-8"))
        self.assertEqual(man["runs"][0]["key_basis"], "2 blind reviews")
        root = os.path.join(self.tmp, "r")
        os.makedirs(os.path.join(root, "evals"))
        for k in ("inputs", "keys"):
            shutil.copytree(os.path.join(out, k), os.path.join(root, "evals", k))
        rc, so, _ = run(["check-examples", "--root", root])
        self.assertEqual(rc, 0, so)

    def test_one_disagreeing_reviewer_rejects(self):
        out = os.path.join(self.tmp, "g")
        rc, so, _ = run(["gen-exams", "--profile", "dgnl-en", "--n", "1", "--out", out,
                         "--mock", self.mockfile([EN, {"answer": "B"}, {"answer": "C"}])])
        self.assertEqual(rc, 0, so)
        self.assertIn("qa_fail=1", so)
        self.assertTrue(os.path.isfile(os.path.join(out, "rejected", "english", "qa-101.txt")))
        self.assertFalse(os.path.exists(os.path.join(out, "inputs", "english", "input-101.md")))

    def test_blind_prompt_has_no_key_or_solution(self):
        obj = dict(EN, final_answer="B")
        p = genexam.blind_prompt(obj)
        self.assertNotIn(EN["solution"], p)
        self.assertNotIn("Second conditional", p)
        self.assertNotIn("Final answer", p)
        self.assertIn("D. would have", p)
        self.assertIn("Passage:", genexam.blind_prompt(dict(obj, passage="Tom likes tea.")))

    def test_bad_replies(self):
        for bad in (dict(EN, correct="E"), dict(EN, options={"A": "x", "B": "x", "C": "y", "D": "z"}),
                    dict(EN, options={"A": "x", "B": "y", "C": "z"}), dict(EN, solution="")):
            self.assertTrue(genexam.check_mc(dict(bad)), bad)
        ok = dict(EN)
        self.assertEqual(genexam.check_mc(ok), [])
        self.assertEqual(ok["final_answer"], "B")

    def test_subject_must_match_profile(self):
        self.assertEqual(run(["gen-exams", "--profile", "dgnl-en", "--subject", "math", "--dry-run"])[0], 2)
        self.assertEqual(run(["gen-exams", "--profile", "dgnl-en", "--dry-run"])[0], 0)


class Variety(unittest.TestCase):
    def test_topics_differ_within_a_round_and_prompt_carries_it(self):
        for prof in genexam.PROFILES:
            ts = [genexam.topic("seed-a", i, prof) for i in range(1, len(genexam.TOPICS[prof]) + 1)]
            self.assertEqual(len(set(ts)), len(ts))
            self.assertIn(ts[0], genexam.build_prompt("math", "seed-a", 1, "hard", prof))

    def test_seed_changes_the_start(self):
        starts = set(genexam.topic("s%d" % i, 1, "dgnl") for i in range(12))
        self.assertGreater(len(starts), 1)


class Lessons(unittest.TestCase):
    SUMMARY = {"items": [{"subject": "math", "item": "101", "questions": [
        {"id": "1", "verdict": "PASS", "answer": "1", "reason": "ok", "findings": [], "basis": "key match"},
        {"id": "2", "verdict": "FAIL", "answer": "3", "reason": "key mismatch", "findings": ["check_failed"],
         "basis": "key match"},
        {"id": "3", "verdict": "UNCERTAIN", "answer": "x", "reason": "reviewers differ", "findings": ["disagree"],
         "basis": "claude review only"}]}]}

    def test_one_lesson_per_non_pass(self):
        ls = genexam.lessons(self.SUMMARY)
        self.assertEqual([x["question"] for x in ls], ["2", "3"])
        self.assertTrue(all(x["status"] == "open" for x in ls))
        self.assertEqual(ls[1]["cause"], "variance")

    def test_cli_writes_files(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        p = os.path.join(tmp, "summary.json")
        json.dump(self.SUMMARY, open(p, "w"))
        rc, so, _ = run(["lessons", "--summary", p])
        self.assertEqual(rc, 0, so)
        self.assertEqual(len(json.load(open(os.path.join(tmp, "lessons.json")))), 2)
        self.assertIn("2 open", open(os.path.join(tmp, "lessons.md")).read())

    def test_cli_missing_summary(self):
        self.assertEqual(run(["lessons", "--summary", "/nonexistent.json"])[0], 2)


if __name__ == "__main__":
    unittest.main()


VI = {"skill": "Spelling", "question": "Từ nào dưới đây viết đúng chính tả?", "passage": "",
      "options": {"A": "xán lạn", "B": "sán lạn", "C": "sáng lạng", "D": "xáng lạn"}, "correct": "B",
      "solution": "Viết đúng là 'sán lạn' (rực rỡ)."}


class DgnlVi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def mockfile(self, replies):
        p = os.path.join(self.tmp, "mock.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump([json.dumps(r) for r in replies], fh)
        return p

    def test_pair_format_and_checker(self):
        out = os.path.join(self.tmp, "g")
        rc, so, _ = run(["gen-exams", "--profile", "dgnl-vi", "--n", "1", "--out", out,
                         "--mock", self.mockfile([VI, {"answer": "B"}, {"answer": "B"}])])
        self.assertEqual(rc, 0, so)
        text = open(os.path.join(out, "inputs", "vietnamese", "input-101.md"), encoding="utf-8").read()
        self.assertIn("Subject: Vietnamese", text)
        self.assertIn("Language: vi", text)
        self.assertIn("Chọn đáp án đúng nhất", text)
        key = open(os.path.join(out, "keys", "vietnamese", "expected-101.md"), encoding="utf-8").read()
        self.assertIn("Final answer: B\nCorrect answer: B. sán lạn", key)
        man = json.load(open(os.path.join(out, "manifest.json"), encoding="utf-8"))
        self.assertEqual(man["runs"][0]["key_basis"], "2 blind reviews")
        root = os.path.join(self.tmp, "r")
        os.makedirs(os.path.join(root, "evals"))
        for k in ("inputs", "keys"):
            shutil.copytree(os.path.join(out, k), os.path.join(root, "evals", k))
        rc, so, _ = run(["check-examples", "--root", root])
        self.assertEqual(rc, 0, so)

    def test_one_disagreeing_reviewer_rejects(self):
        out = os.path.join(self.tmp, "g")
        rc, so, _ = run(["gen-exams", "--profile", "dgnl-vi", "--n", "1", "--out", out,
                         "--mock", self.mockfile([VI, {"answer": "B"}, {"answer": "A"}])])
        self.assertEqual(rc, 0, so)
        self.assertTrue(os.path.isfile(os.path.join(out, "rejected", "vietnamese", "qa-101.txt")))

    def test_subject_must_match_profile_and_topic(self):
        self.assertEqual(run(["gen-exams", "--profile", "dgnl-vi", "--subject", "english", "--dry-run"])[0], 2)
        self.assertEqual(run(["gen-exams", "--profile", "dgnl-vi", "--dry-run"])[0], 0)
        self.assertIn(genexam.topic("s", 1, "dgnl-vi"), genexam.TOPICS["dgnl-vi"])


class Harder(unittest.TestCase):
    def test_prompt_carries_level_and_difficulty(self):
        for prof, sub in (("dgnl", "math"), ("dgnl-en", "english"), ("dgnl-vi", "vietnamese")):
            p = genexam.build_prompt(sub, "s", 1, "harder", prof)
            self.assertIn("Level: harder", p)
            self.assertIn('"harder" means', p)

    def test_cli_accepts_harder(self):
        self.assertEqual(run(["gen-exams", "--profile", "dgnl-en", "--level", "harder", "--dry-run"])[0], 0)

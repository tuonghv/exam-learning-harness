"""TASK-055 (55.4, 55.5): group-aware render/retry/QA prompts and the missing-context decline. Mock llm."""
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
sys.path.insert(0, HERE)
from exam_engine import engine  # noqa: E402
from exam_engine.core import refcheck  # noqa: E402
from exam_engine.pipeline import parser, solver, verifier  # noqa: E402
from test_exam_run import Script, a, cfg, qa, solve  # noqa: E402
from test_group_model import HEAD, OPT, _lab, _parse  # noqa: E402

PAS = "Tea was first grown in Yunnan."


def _file(body, head=""):
    return (HEAD % head) + body


def _recs(exam, ans):
    r = {q["id"]: engine.new_rec() for q in exam["questions"]}
    for i, v in ans.items():
        r[i]["ans"] = a(i, v)
    return r


def _run(text, *replies):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "e.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        llm = Script(*replies)
        res, code = engine.run(p, os.path.join(d, "out"), cfg(), llm)
    return res, llm


class TestRender(unittest.TestCase):
    def test_round1_passage_once_and_content_equal(self):
        t = _file("".join(_lab(n, "Read and answer.", PAS, "Why is item%d odd?" % n) for n in (1, 2, 3))
                  + _lab(4, "", "", "Unrelated zebra?"))
        ex = _parse(t)
        p = solver.solve_prompt(ex, t, None, [1, 2, 3, 4])
        self.assertEqual(p.count(PAS), 1)
        self.assertEqual(p.count("## Group 1-3"), 1)
        words = set(re.findall(r"\w+", "\n".join(q["text"] + " ".join(q["options"].values())
                                                 for q in ex["questions"])))
        self.assertTrue(words)
        self.assertFalse(words - set(re.findall(r"\w+", p)))

    def test_retry_only_open_with_context_once(self):
        ex = _parse(_file("".join(_lab(n, "Read.", PAS, "Stem number %d?" % (n * 11)) for n in (2, 3, 4))
                          .replace("Question 2", "Question 1").replace("Question 3", "Question 2")
                          .replace("Question 4", "Question 3")))
        recs = _recs(ex, {})
        p = solver.retry_prompt(ex, recs, [2])
        self.assertEqual(p.count(PAS), 1)
        self.assertIn("Stem number 33?", p)
        self.assertNotIn("Stem number 22?", p)
        self.assertNotIn("Stem number 44?", p)

    def test_dependent_retry_has_sibling_answer(self):
        t = _file(_lab(1, "Read.", PAS, "Compute the base?") + _lab(2, "Read.", PAS, "Using question 1, double it?"))
        ex = _parse(t)
        self.assertEqual(parser.groups(ex)[0]["kind"], "dependent")
        recs = _recs(ex, {1: "B"})
        p = solver.retry_prompt(ex, recs, [2])
        self.assertIn("### Sibling answers (context, do not re-answer)", p)
        self.assertRegex(p, r"Question 1: Compute the base\?\nAnswer: B")
        self.assertEqual(p.count(PAS), 1)
        # cycle: 1 <-> 2, only 2 open, no recursion
        t2 = _file(_lab(1, "Read.", PAS, "Given question 2, x?") + _lab(2, "Read.", PAS, "Given question 1, y?"))
        ex2 = _parse(t2)
        p2 = solver.retry_prompt(ex2, _recs(ex2, {1: "C"}), [2])
        self.assertIn("Answer: C", p2)

    def test_unlabelled_unchanged(self):
        t = _file("## Question 1\n\nA?\n" + OPT + "## Question 2\n\nB?\n" + OPT)
        ex = _parse(t)
        self.assertEqual(solver.solve_prompt(ex, t, None, [1, 2]), solver.solve_prompt(ex, t, None))

    def test_qa_prompt_context_and_siblings(self):
        t = _file(_lab(1, "Read.", PAS, "Compute the base?") + _lab(2, "Read.", PAS, "Using question 1, double it?"))
        ex = _parse(t)
        recs = _recs(ex, {1: "B", 2: "C"})
        text = verifier.qa_prompt(ex, recs, [2])
        self.assertEqual(text.count(PAS), 1)
        items = json.loads(text.split("Answers to review (JSON):\n", 1)[1])
        self.assertEqual(items[0]["sibling_answers"][0]["answer"], "B")


class TestDecline(unittest.TestCase):
    def test_missing_dependency_declined_no_call(self):
        t = _file(_lab(1, "Read.", PAS, "Stem one?") + _lab(2, "Read.", PAS, "Using question 99, add."))
        res, llm = _run(t, solve(a(1, "A")), qa((1, "agree")))
        q2 = res["questions"][1]
        self.assertEqual(q2["verification_status"], "UNCERTAIN")
        self.assertEqual(q2["status_reason"], "solver_declined: missing_text (question 99)")
        self.assertNotIn("Using question 99", llm.prompts[0])

    def test_passage_promised_but_empty(self):
        ex = _parse(_file(_lab(1, "Read the following passage and answer.", "", "Why?")))
        g = parser.groups(ex)
        self.assertEqual(refcheck.missing_group_parts(ex, g, parser.deps(ex)), {1: ["passage"]})
        ok = _parse(_file(_lab(1, "Read the following passage.", PAS, "Why?")))
        self.assertEqual(refcheck.missing_group_parts(ok, parser.groups(ok), parser.deps(ok)), {})

    def test_vague_ref_only_warns(self):
        t = _file(_lab(1, "", "", "What does the text say?") + _lab(2, "Read.", PAS, "Fine?"))
        ex = _parse(t)
        self.assertEqual(parser.exam_warnings(ex), ["group_link_uncertain: q 1"])
        self.assertEqual(engine.incomplete_ids(ex), {})


if __name__ == "__main__":
    unittest.main()

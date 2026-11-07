"""TASK-055 (55.3, 55.6): groups/deps of the parsed exam; Source pages -> q["pages"] -> result."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import api  # noqa: E402
from exam_engine.pipeline import parser  # noqa: E402

HEAD = """# Exam Input

Subject: english
Level: Grade 12
Exam type: Test
Task: Multiple Choice
Mode: Solve

## Instructions

Choose the best answer.%s

"""
OPT = "\nA. a\nB. b\nC. c\nD. d\n"


def _lab(n, ins="", pas="", stem="Stem?", pages=""):
    body = ("Source pages: %s\n\n" % pages) if pages else ""
    body += "### Instruction for this group\n\n%s\n\n" % ins if ins else ""
    body += "### Passage\n\n%s\n\n" % pas if pas else ""
    return "## Question %d\n\n%s### Question text\n\n%s\n%s" % (n, body, stem, OPT)


def _parse(text):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "e.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return parser.parse_exam(p)


class TestGroups(unittest.TestCase):
    def test_kinds_and_deps(self):
        t = HEAD % ""
        t += "## Question 1\n\nWhat is 2+2?\n" + OPT
        for n in (2, 3, 4):
            t += _lab(n, "Read and answer.", "Tea is old.", "Q%d?" % n, "1-2" if n == 3 else "")
        t += "## Question 5\n\nTable:\n| a | b |\n| 1 | 2 |\nWhat is the sum?\n" + OPT
        t += "## Question 6\n\nUsing your result of question 5, double it.\n" + OPT
        ex = _parse(t)
        g = parser.groups(ex)
        self.assertEqual([(x["kind"], x["ids"]) for x in g],
                         [("independent", [1]), ("passage", [2, 3, 4]), ("passage", [5]),
                          ("dependent", [5, 6])])
        self.assertEqual(g[1]["passage"], "Tea is old.")
        self.assertEqual(g[1]["instruction"], "Read and answer.")
        self.assertEqual(parser.deps(ex), {6: [5]})

    def test_printed_offset(self):
        off = "\n\nQuestions are numbered from 1 here; the printed exam number of question N is N + 46 (x)."
        t = (HEAD % off) + "## Question 1\n\nStem?\n" + OPT + "## Question 2\n\nFrom question 47, why?\n" + OPT
        self.assertEqual(parser.deps(_parse(t)), {2: [1]})

    def test_no_labels_no_groups(self):
        t = (HEAD % "") + "## Question 1\n\nA?\n" + OPT + "## Question 2\n\nB?\n" + OPT
        self.assertEqual([x["ids"] for x in parser.groups(_parse(t))], [[1], [2]])


class TestPages(unittest.TestCase):
    def test_parsed_not_in_text(self):
        ex = _parse((HEAD % "") + _lab(1, "Guide.", "", "Stem?", "1-2"))
        q = ex["questions"][0]
        self.assertEqual(q["pages"], [1, 2])
        self.assertNotIn("Source pages", q["text"])
        self.assertNotIn("Source pages", q["stem"])

    def test_emitted_for_every_question_with_page(self):
        lab = {"id": "1", "context": "Questions 1-2: Read.\nPassage text.", "text": "S?",
               "page": 1, "continued_pages": [2]}
        self.assertEqual(api.question_lines(lab)[0], "Source pages: 1-2")
        plain = {"id": "1", "text": "S?", "page": 1}
        self.assertEqual(api.question_lines(plain)[:2], ["Source pages: 1", ""])
        self.assertNotIn("Source pages", "\n".join(api.question_lines({"id": "1", "text": "S?"})))

    def test_unlabelled_pages_parsed_and_not_in_prompt(self):
        from exam_engine import engine
        from exam_engine.pipeline import solver
        plain = (HEAD % "") + "## Question 1\n\nStem?\n" + OPT
        withp = (HEAD % "") + "## Question 1\n\nSource pages: 3\n\nStem?\n" + OPT
        self.assertEqual(parser.strip_unlabelled_pages(withp), plain)
        self.assertEqual(parser.strip_unlabelled_pages(plain), plain)
        self.assertEqual(_parse(withp)["questions"][0]["pages"], [3])
        lab = (HEAD % "") + _lab(1, "Guide.", "", "Stem?", "1-2")
        self.assertEqual(parser.strip_unlabelled_pages(lab), lab)  # four-level keeps its line
        ex = _parse(plain)
        self.assertEqual(solver.solve_prompt(ex, parser.strip_unlabelled_pages(withp), None),
                         solver.solve_prompt(ex, plain, None))

    def test_result_carries_pages(self):
        from exam_engine import engine
        from exam_engine.core import schema
        ex = _parse((HEAD % "") + _lab(1, "Guide.", "", "Stem?", "3-4"))
        rec = {"ans": None, "status": None, "reason": None, "score": None, "checks": [],
               "findings": [], "attempts": 0, "error": None}
        class Rn:
            cost, calls, cache = 0.0, 0, None
        cfg = {"llm_name": "x", "model": "m", "max_attempts": 1, "timeout": 1, "max_cost_usd": None}
        res = engine.build_result(ex, "e.md", {1: rec}, cfg, Rn(), None)
        self.assertEqual(res["questions"][0]["pages"], [3, 4])
        self.assertEqual([e for e in schema.validate(res, schema.RESULT) if "pages" in str(e)], [])


if __name__ == "__main__":
    unittest.main()

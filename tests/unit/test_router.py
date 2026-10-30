"""router + config/subjects.json: a new subject needs a config entry, no engine code."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import parser, router, solver, verifier  # noqa: E402

CHEM = """# Exam Input

Subject: Chemistry
Level: Grade 12
Exam type: High School Graduation
Task: Short Answer
Mode: Solve

## Instructions

Answer.

## Question 1

Relative atomic mass of oxygen?
"""


class Router(unittest.TestCase):
    def test_default_subjects(self):
        self.assertEqual(sorted(router.subjects()), ["english", "informatics", "literature", "math", "physics", "science", "vietnamese"])
        self.assertEqual(router.subject_key("Mathematics"), "math")
        self.assertIsNone(router.subject_key("Chemistry"))

    def test_literature_is_open_without_score(self):
        p = router.policy("Literature")
        self.assertEqual((p["task"], p["checks"], p["score_basis"]),
                         ("Open", ["format", "quote"], "none"))

    def test_language_comes_from_config(self):
        self.assertEqual(router.language({"fields": {"Subject": "English"}}), "en")
        self.assertEqual(router.language({"fields": {"Subject": "Physics"}}), "vi")
        self.assertEqual(router.language({"fields": {"Subject": "Physics", "Language": "en"}}), "en")

    def test_new_subject_by_config_only(self):
        d = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, d, True)
        subj = router.subjects()
        subj["chemistry"] = {"aliases": ["chemistry", "hoa"], "task": "Closed",
                             "checks": ["format", "computed"], "score_basis": "official_key",
                             "language": "en", "prompt": "subjects/math.md"}
        for name in ("subjects", "engine"):
            with open(os.path.join(d, name + ".json"), "w") as fh:
                json.dump(subj if name == "subjects" else {"max_attempts": 2}, fh)
        path = os.path.join(d, "chem.md")
        with open(path, "w") as fh:
            fh.write(CHEM)
        self.assertTrue(parser.validate_exam(parser.parse_exam(path)))  # unknown by default
        with mock.patch.dict(os.environ, {"EXAM_ENGINE_CONFIG_DIR": d}):
            exam = parser.parse_exam(path)
            self.assertEqual(parser.validate_exam(exam), [])
            self.assertEqual(router.language(exam), "en")
            self.assertIn("Subject rules (Mathematics)", solver.base_prompt(exam))
            ans = {"answer": "16", "answer_status": "answered", "evidence": ["nothing"]}
            kinds = [c["kind"] for c in verifier.det_checks(exam["questions"][0], ans, exam)]
            self.assertNotIn("quote", kinds)  # "quote" is not in this subject's checks


if __name__ == "__main__":
    unittest.main()

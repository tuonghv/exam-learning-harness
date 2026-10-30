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
        self.assertEqual(router.language({"fields": {"Subject": "English"}}), "vi")
        self.assertEqual(router.language({"fields": {"Subject": "Physics"}}), "vi")
        self.assertEqual(router.language({"fields": {"Subject": "Physics", "Language": "en"}}), "en")

    def test_language_unknown_subject_is_vi(self):
        self.assertEqual(router.language({"fields": {"Subject": "Chemistry"}}), "vi")

    def test_override_beats_header_beats_policy(self):
        ex = {"fields": {"Subject": "Math", "Language": "vi"}, "questions": []}
        self.assertEqual(router.language(ex, "en"), "en")
        self.assertEqual(router.language({"fields": {"Subject": "Math", "Language": "en"}}), "en")

    def test_auto_detects_from_question_text(self):
        def ex(*texts):
            return {"fields": {"Subject": "English", "Language": "auto"},
                    "questions": [{"text": t} for t in texts]}
        self.assertEqual(router.language(ex("Choose the best answer.", "He go to school.")), "en")
        self.assertEqual(router.language(ex("Tính giá trị của biểu thức sau đây.")), "vi")
        self.assertEqual(router.language(ex("Choose the correct word for the sentence.",
                                            "Chọn.", "She was happy because she won the long race.")), "en")
        self.assertEqual(router.language({"fields": {"Subject": "English"}, "questions": []}, "auto"), "vi")

    def test_apply_lang(self):
        ex = {"fields": {"Subject": "Math"}}
        router.apply_lang(ex, None)
        self.assertNotIn("Language", ex["fields"])
        router.apply_lang(ex, "en")
        self.assertEqual(ex["fields"]["Language"], "en")

    def test_detect_lang(self):
        from exam_engine.utils import text
        self.assertEqual(text.detect_lang(""), "vi")
        self.assertEqual(text.detect_lang("Choose the best answer."), "en")
        self.assertEqual(text.detect_lang("Đáp án đúng là gì?"), "vi")

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

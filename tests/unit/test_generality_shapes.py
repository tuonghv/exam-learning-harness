"""TASK-062 62.4-62.6 + D1: answer shapes/open tasks, allowed scripts, gen-exams profiles as data. Synthetic exams, $0."""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))

from exam_engine.ingest.adapters import pdf  # noqa: E402
from exam_engine.pipeline import examples_check, genexam, reporter, verifier  # noqa: E402

SUBJ = {
    "chemistry": {"aliases": ["chemistry"], "task": "Closed", "checks": ["format"], "score_basis": "official_key",
                  "language": "en", "prompt": None, "answer_shapes": ["number"]},
    "history": {"aliases": ["history"], "task": "Open", "checks": ["format"], "score_basis": "none",
                "language": "en", "prompt": None, "label": "History"},
}


def tmp_cfg(name, data):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return d


class Shapes(unittest.TestCase):  # 62.4
    def setUp(self):
        d = tmp_cfg("subjects.json", SUBJ)
        self.addCleanup(shutil.rmtree, d, True)
        p = mock.patch.dict(os.environ, {"EXAM_ENGINE_CONFIG_DIR": d})
        p.start()
        self.addCleanup(p.stop)

    def fmt(self, subject, text, answer):
        exam = {"fields": {"Subject": subject}}
        return verifier._format({"text": text}, {"answer": answer}, exam)

    def test_new_subject_number_shape(self):
        r = self.fmt("chemistry", "Compute the molar mass.", "18")
        self.assertEqual((r["detail"], r["result"]), ("answer holds a number", "pass"))
        self.assertEqual(self.fmt("chemistry", "Compute the molar mass.", "water")["result"], "fail")
        # tf4 is not declared for chemistry: a-d items get no verdict check
        r = self.fmt("chemistry", "a) x\nb) y\nc) z\nd) w", "X")
        self.assertTrue(r is None or r["detail"] != "four true/false verdicts (a-d)")

    def test_open_task_label(self):
        r = self.fmt("history", "Discuss the causes.", "A")
        self.assertEqual((r["detail"], r["result"]), ("History answer must be Open", "fail"))
        self.assertEqual(self.fmt("history", "Discuss.", "Open")["result"], "pass")

    def test_reporter_open_by_policy(self):
        self.assertTrue(reporter._is_open({"answer": "A"}, {"subject": "history", "task": "Essay"}))
        self.assertFalse(reporter._is_open({"answer": "A"}, {"subject": "chemistry", "task": "Quiz"}))

    def test_examples_check_open_by_policy(self):
        self.assertEqual(examples_check.router.policy("history")["task"], "Open")


class ShapesDefault(unittest.TestCase):
    def test_math_physics_literature_unchanged(self):
        exam = lambda s: {"fields": {"Subject": s}}
        for s in ("math", "physics"):
            q = {"text": "a) p\nb) q\nc) r\nd) s"}
            r = verifier._format(q, {"answer": "a) Đ b) S c) Đ d) S"}, exam(s))
            self.assertEqual(r["detail"], "four true/false verdicts (a-d)")
            self.assertEqual(verifier._format({"text": "Tính"}, {"answer": "12"}, exam(s))["detail"],
                             "answer holds a number")
        r = verifier._format({"text": "x"}, {"answer": "A"}, exam("literature"))
        self.assertEqual(r["detail"], "Literature answer must be Open")


class Scripts(unittest.TestCase):  # 62.5
    def test_cyrillic(self):
        self.assertTrue(pdf._odd_chars("Привет"))
        self.assertFalse(pdf._odd_chars("Привет", scripts=("CYRILLIC",)))
        self.assertTrue(pdf._odd_chars("αβ"))
        self.assertFalse(pdf._odd_chars("αβ", scripts=("GREEK",)))
        self.assertFalse(pdf._odd_chars("hello Việt 12"))


BIO = {
    "bio-mc": {"subject": "biology", "subject_label": "Biology", "prompt": "dev/genexam_dgnl_en.md",
               "qa_prompt": "dev/genexam_qa.md", "topics": ["cells"], "check": "mc", "blind": True,
               "exam_type": "Entrance Test", "level": "Grade 10", "lang": "en",
               "instructions": "Pick the best answer."},
}


class Profiles(unittest.TestCase):  # 62.6 + D1
    def setUp(self):
        self.old = genexam.PROFILE_TABLE
        self.addCleanup(genexam.apply_profiles, self.old)

    def test_synthetic_profile(self):
        d = tmp_cfg("genexam_profiles.json", BIO)
        self.addCleanup(shutil.rmtree, d, True)
        genexam.apply_profiles(genexam.load_profiles(d))
        self.assertEqual(genexam.PROFILES, ("bio-mc",))
        self.assertIn("Topic (use exactly this): cells", genexam.build_prompt("biology", 1, 1, "hard", "bio-mc"))
        obj = {"question": "Q?", "options": dict(zip("ABCD", "wxyz")), "final_answer": "A", "solution": "s",
               "skill": "k", "check": "", "passage": ""}
        md = genexam.input_md("biology", obj)
        for want in ("Subject: Biology", "Language: en", "Level: Grade 10", "Exam type: Entrance Test",
                     "Pick the best answer."):
            self.assertIn(want, md)
        self.assertEqual(genexam.CHECKS["bio-mc"], genexam._CHECK_FN["mc"])

    def test_bad_profile(self):
        for data in ({}, {"x": {"subject": "a"}}, {"x": dict(BIO["bio-mc"], check="nope")}):
            d = tmp_cfg("genexam_profiles.json", data)
            self.addCleanup(shutil.rmtree, d, True)
            with self.assertRaises(genexam.GenError) as cm:
                genexam.load_profiles(d)
            self.assertEqual(cm.exception.code, "bad_profile")

    def test_default_profiles(self):
        self.assertEqual(genexam.PROFILES, ("hs", "dgnl", "dgnl-en", "dgnl-vi"))

    def test_manifest_hashes_profile_prompt(self):  # D1
        for prof in ("hs", "dgnl", "dgnl-vi"):
            out = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, out, True)
            genexam.write(genexam.PROFILE_SUBJECT[prof], [({"qa": "pass", "qa_note": ""}, "in", "key")], out,
                          {"profile": prof})
            with open(os.path.join(out, "manifest.json"), encoding="utf-8") as fh:
                got = json.load(fh)["runs"][0]["prompt_sha256"]
            want = hashlib.sha256(genexam.template(genexam.PROMPT_OF[prof]).encode("utf-8")).hexdigest()
            self.assertEqual(got, want, prof)
        self.assertNotEqual(hashlib.sha256(genexam.template().encode("utf-8")).hexdigest(), want)


if __name__ == "__main__":
    unittest.main()

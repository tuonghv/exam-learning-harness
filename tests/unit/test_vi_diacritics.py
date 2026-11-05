"""TASK-079 / REQ-0087: Vietnamese solve output must carry diacritics. Fake llm only, $0."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
import test_exam_run as T  # noqa: E402
from exam_engine import engine as er  # noqa: E402
from exam_engine.pipeline import verifier  # noqa: E402

ASCII = "Menh de nay khong dung vi cua mot nhung dap an sai va la dap an cho bai nay."
ACCENT = "Mệnh đề này không đúng vì đáp án sai và là đáp án cho bài này."


def exam(lang):
    return {"fields": {"Subject": "Mathematics", "Language": lang}, "questions": []}


def kind(res):
    return [c for c in res if c["kind"] == "diacritics"][0]["result"]


class Checks(unittest.TestCase):
    def run_check(self, text, lang="vi"):
        ans = T.a(1, "6", explanation=text)
        return kind(verifier.det_checks({"id": 1}, ans, exam(lang)))

    def test_unaccented_vi_fails(self):
        self.assertEqual(self.run_check(ASCII), "fail")

    def test_accented_vi_passes(self):
        self.assertEqual(self.run_check(ACCENT), "pass")

    def test_en_language_passes(self):
        self.assertEqual(self.run_check(ASCII, "en"), "pass")

    def test_english_text_passes(self):
        self.assertEqual(self.run_check("The answer is 6 because 2 * 3 = 6, so option A holds."), "pass")

    def test_prompt_has_rule(self):
        for rel, word in ((("exam", "solve.md"), "full diacritics"),
                          (("lang", "vi", "exam", "solve.md"), "đầy đủ dấu")):
            with open(os.path.join(ROOT, "prompts", "dev", *rel), encoding="utf-8") as fh:
                self.assertIn(word, fh.read())


class Retry(unittest.TestCase):
    def test_retry_until_accented(self):
        src = (T.HEAD % ("Mathematics", "Short Answer")).replace("Mode:", "Language: vi\nMode:") + \
            "## Instructions\n\nSolve.\n\n## Question 1\n\nCompute 3+4.\n"
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "e.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(src)
            llm = T.Script(T.solve(T.a(1, "7", explanation=ASCII)),
                           T.solve(T.a(1, "7", explanation=ACCENT)),
                           T.qa((1, "agree")), T.qa((1, "agree")))
            res, _ = er.run(p, os.path.join(d, "o"), T.cfg(max_attempts=2), llm)
        q = res["questions"][0]
        self.assertEqual(q["attempts"], 2)
        self.assertNotIn("diacritics", [f["code"] for f in q["qa_findings"]])
        self.assertNotEqual(q["verification_status"], "FAIL")
        self.assertIn("diacritics", llm.prompts[1])


if __name__ == "__main__":
    unittest.main()

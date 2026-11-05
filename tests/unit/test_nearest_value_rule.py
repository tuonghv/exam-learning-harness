"""TASK-074: dev solve prompts carry the nearest-value rule; release prompts and the rest stay frozen."""
import glob
import hashlib
import os
import re
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import settings  # noqa: E402
from exam_engine.pipeline import parser, solver  # noqa: E402

EN = os.path.join(ROOT, "prompts", "dev", "exam", "solve.md")
VI = os.path.join(ROOT, "prompts", "dev", "lang", "vi", "exam", "solve.md")
# sha256 of each file as of HEAD before TASK-074 (i.e. without the rule)
BASE_SHA = {EN: "fbfb040e6b5abd8a0db913ff70c7e117a0114127152d24e9097bc57add335fca",
            VI: "512131b08eda28c4b077288232596ee665db9c195478eb49104f9443003b1868"}
TRIGGERS = ("gần nhất", "xấp xỉ", "closest", "approximately", "nearest")
EXAMS = (sorted(glob.glob(os.path.join(ROOT, "examples", "*", "input-*.md")))
         + sorted(glob.glob(os.path.join(ROOT, "evals", "inputs", "*", "*.md"))))


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def rule(text):
    """The numbered rule block that carries the trigger words, or None."""
    for b in re.findall(r"^\d+\. [^\n]*\n(?:   [^\n]*\n)*", text, re.M):
        if all(t in b for t in TRIGGERS):
            return b
    return None


def strip_rule(text):
    r = rule(text)
    return text.replace(r, "", 1) if r else text


def prompts_for(channel, exam):
    i = exam["questions"][0]["id"]
    recs = {i: {"findings": [], "reason": "x"}}
    with mock.patch.dict(settings.PROMPT_SOURCE, {"channel": channel, "version": None}):
        return solver.base_prompt(exam), solver.retry_prompt(exam, recs, [i])


class Rule(unittest.TestCase):
    def test_rule_in_both_dev_files(self):
        for p in (EN, VI):
            r = rule(read(p))
            self.assertIsNotNone(r, p)
            for t in TRIGGERS:
                self.assertIn(t, r, (p, t))
        self.assertRegex(rule(read(EN)), r"^6\. ")

    def test_rule_content(self):
        r = rule(read(EN)).lower()
        for w in ("every plausible reading", "start", "end", "period", "`checks`", "distance", "never discard"):
            self.assertIn(w, r)
        v = rule(read(VI))
        self.assertIn("`checks`", v)
        self.assertRegex(v, r"đầu kỳ|đầu .*cuối")

    def test_no_subject_or_exam_literal(self):
        for p in (EN, VI):
            r = rule(read(p)).lower()
            for w in ("math", "toán", "dgnl", "63", "triệu", "million", "deposit", "gửi"):
                self.assertNotIn(w, r, (p, w))

    def test_rest_of_file_unchanged(self):
        for p, sha in BASE_SHA.items():
            self.assertEqual(hashlib.sha256(strip_rule(read(p)).encode("utf-8")).hexdigest(), sha, p)


class Assembled(unittest.TestCase):
    def test_exams_found(self):
        self.assertGreater(len(EXAMS), 10)

    def test_dev_has_rule_release_not(self):
        n = 0
        for f in EXAMS:
            try:
                exam = parser.parse_exam(f)
            except Exception:
                continue
            if not exam.get("questions"):
                continue
            n += 1
            try:
                rel = prompts_for("release", exam)
            except FileNotFoundError:  # release v1.0.0 lacks this subject addendum
                continue
            dev = prompts_for("dev", exam)
            for r, d in zip(rel, dev):
                self.assertNotIn("closest", r)
                self.assertIn("closest", d, f)
                self.assertNotEqual(r, d)
        self.assertGreater(n, 10)

    def test_release_files_frozen(self):
        for p in glob.glob(os.path.join(ROOT, "prompts", "releases", "*", "**", "solve.md"), recursive=True):
            t = read(p)
            self.assertFalse(any(x in t for x in ("closest", "gần nhất")), p)


if __name__ == "__main__":
    unittest.main()

"""TASK-054 54.1-54.6 regression golden + AC3/AC5 on the real DGNL refined3.json.

golden_unlabelled.json = sha256 of the parse dict (without the new keys) and of solve_prompt,
computed from the code at 2461f4f (before TASK-054), for every examples/*/input-*.md and
evals/inputs file. An unlabelled file must not change.
"""
import glob
import hashlib
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import api  # noqa: E402
from exam_engine.pipeline import parser, solver  # noqa: E402

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "golden_unlabelled.json")
REFINED = os.path.join(ROOT, "work", "dgnl-real", "refined3.json")
NEW_Q = ("section", "instruction", "passage", "stem")
SUBJECTS = (("Vietnamese", "1-30"), ("English", "31-60"), ("Math", "61-90"), ("Science", "91-120"))


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


class TestGoldenUnlabelled(unittest.TestCase):
    def test_parse_and_prompt_unchanged(self):
        gold = json.load(open(GOLDEN, encoding="utf-8"))
        paths = sorted(os.path.relpath(p, ROOT) for p in
                       glob.glob(os.path.join(ROOT, "examples", "*", "input-*.md")) +
                       glob.glob(os.path.join(ROOT, "evals", "inputs", "**", "*.md"), recursive=True))
        self.assertEqual(paths, sorted(gold))
        for p in paths:
            full = os.path.join(ROOT, p)
            ex = parser.parse_exam(full)
            self.assertEqual(ex["sections"], [], p)
            for q in ex["questions"]:
                for k in NEW_Q:
                    if k != "stem":  # stem mirrors text for an unlabelled question
                        self.assertFalse(q.get(k), "%s q%s %s" % (p, q["id"], k))
                    q.pop(k, None)
            ex.pop("sections", None)
            ex.pop("section_subjects", None)
            with open(full, encoding="utf-8") as fh:
                text = fh.read()
            try:
                pr = solver.solve_prompt(ex, text, None)
            except FileNotFoundError:  # subject prompt absent in the repo (informatics), same at baseline
                pr = "NOPROMPT"
            self.assertEqual(sha(json.dumps(ex, sort_keys=True, ensure_ascii=False)), gold[p]["parse"], p)
            self.assertEqual(sha(pr), gold[p]["prompt"], p)


@unittest.skipUnless(os.path.isfile(REFINED), "work/dgnl-real/refined3.json absent")
class TestDgnlReemit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.load(open(REFINED, encoding="utf-8"))
        cls.tmp = tempfile.mkdtemp()

    def emit(self, subject, spec):
        doc = json.loads(json.dumps(self.doc))
        doc["meta"].update({"Subject": subject, "Level": "Grade 12", "Exam type": "University Entrance (DGNL)",
                            "Task": "Multiple Choice", "Mode": "Solve", "Language": "vi"})
        text = api.to_exam_text(doc, {"use_refined": True, "questions": spec})
        path = os.path.join(self.tmp, "e3-%s.md" % subject)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path, text

    def test_ac3_counts_and_options(self):
        for subject, spec in SUBJECTS:
            old_path = os.path.join(ROOT, "work", "dgnl-real", "e3-%s.md" % subject)
            if not os.path.isfile(old_path):
                continue
            new_path, text = self.emit(subject, spec)
            old, new = parser.parse_exam(old_path), parser.parse_exam(new_path)
            self.assertEqual(len(new["questions"]), 30, subject)
            self.assertEqual(len(old["questions"]), 30, subject)
            self.assertEqual([q["options"] for q in new["questions"]],
                             [q["options"] for q in old["questions"]], subject)
            self.assertEqual(text.count("## Section:"), len(new["sections"]), subject)

    def test_ac5_english_group_slice(self):
        path, text = self.emit("English", "31-35")
        ex = parser.parse_exam(path)
        self.assertEqual(len(ex["questions"]), 5)
        pr = solver.solve_prompt(ex, text, None)
        self.assertEqual(pr.count("Instruction for this group"), 5)
        self.assertEqual(pr.count("1.2. TIẾNG ANH"), 1)
        # TASK-065 65.5 named golden update: the section line keeps its parent (FORMAT.md:50)
        self.assertEqual(pr.count("## Section: PHẦN 1: SỬ DỤNG NGÔN NGỮ > 1.2. TIẾNG ANH"), 1)


if __name__ == "__main__":
    unittest.main()

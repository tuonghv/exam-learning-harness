"""TASK-151 (REQ-0078): extraction gold draft tool. Synthetic published config in a temp root, $0, no PDF."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import extract_gold_draft as T  # noqa: E402

HEAD = ("# Exam Input\n\nSubject: %s\nLevel: Grade 12\nExam type: University Entrance (DGNL)\nTask: Multiple Choice\n"
        "Mode: Solve\nLanguage: vi\n\n## Instructions\n\nChoose.\n\n")


def exam_md(subject, n, start=1, no_opts=()):
    out = HEAD % subject
    for i in range(start, start + n):
        out += "## Question %d\n\nSource pages: %d\n\nCâu hỏi số %d của %s?\n\n" % (i, 1 + i // 5, i, subject)
        if i not in no_opts:
            out += "A. một %d.\nB. hai.\nC. ba.\nD. bốn.\n\n" % i
    return out


class Draft(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        exams = {}
        for exam, printed_offset in (("dgnl2025", 0), ("dgnl2026", 60), ("dhqg2024", 0)):
            runs = []
            for subj in ("Math", "Science"):
                run = "plans/%s/main/runs/r-%s" % (exam, subj.lower())
                d = os.path.join(self.root, run, "input")
                os.makedirs(d)
                with open(os.path.join(d, "exam.md"), "w", encoding="utf-8") as fh:
                    fh.write(exam_md(subj, 10, no_opts=(3,)))
                off = printed_offset + (0 if subj == "Math" else 10)
                with open(os.path.join(d, "assembly.json"), "w") as fh:
                    json.dump({"questions": [{"id": str(i), "printed": str(i + off)} for i in range(1, 11)]}, fh)
                runs.append(run)
            exams[exam] = {"key": "input/dgnl/%s.answer.txt" % exam, "plan_runs": runs}
        self.cfg = os.path.join(self.root, "published.json")
        with open(self.cfg, "w") as fh:
            json.dump({"version": 1, "exams": exams}, fh)
        self.out = os.path.join(self.root, "out")

    def build(self, *extra):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = T.main(["build", "--config", self.cfg, "--root", self.root, "--out", self.out, "--no-images"]
                        + list(extra))
        self.assertEqual(rc, 0)
        return buf.getvalue()

    def load(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8") as fh:
            return json.load(fh)

    def test_collect_ids_printed_and_skips_no_options(self):
        by = T.collect(self.cfg, self.root)
        self.assertEqual(sorted(by), ["dgnl2025", "dgnl2026", "dhqg2024"])
        ids = [r["id"] for r in by["dgnl2026"]]
        self.assertEqual(len(ids), 18)  # 2 runs x 10, question 3 of each has no options
        self.assertIn("26061", ids)  # yy + printed (Math offset 60)
        self.assertIn("26071", ids)  # Science printed 71
        self.assertNotIn("26063", ids)
        r = next(r for r in by["dgnl2026"] if r["id"] == "26061")
        self.assertEqual((r["printed"], r["subject"], r["pages"], r["pdf"]),
                         (61, "Math", [1], os.path.join("input", "dgnl", "dgnl2026.pdf")))

    def test_sample_stratified_seeded_sorted(self):
        out = self.build("--n", "10", "--seed", "7")
        self.assertIn("SAMPLE: 10 questions", out)
        qs = self.load("extracted.json")["questions"]
        per = {}
        for q in qs:
            per[q["exam"]] = per.get(q["exam"], 0) + 1
        self.assertEqual(sorted(per.values()), [3, 3, 4])
        self.assertEqual([q["id"] for q in qs], sorted((q["id"] for q in qs), key=int))
        first = [q["id"] for q in qs]
        self.build("--n", "10", "--seed", "7")
        self.assertEqual([q["id"] for q in self.load("extracted.json")["questions"]], first)
        self.build("--n", "10", "--seed", "8")
        self.assertNotEqual([q["id"] for q in self.load("extracted.json")["questions"]], first)

    def test_sample_too_large_fails(self):
        with self.assertRaises(ValueError):
            T.sample(T.collect(self.cfg, self.root), 100, 1)

    def test_files_and_review_sheet(self):
        self.build("--n", "6")
        ext, draft = self.load("extracted.json"), self.load("gold-draft.json")
        self.assertEqual([q["text"] for q in ext["questions"]], [q["text"] for q in draft["questions"]])
        self.assertTrue(all(q["checked"] is False for q in draft["questions"]))
        q = draft["questions"][0]
        self.assertEqual((q["formula"], q["figures"], sorted(q["options"])), ("", [], ["A", "B", "C", "D"]))
        with open(os.path.join(self.out, "review.html"), encoding="utf-8") as fh:
            h = fh.read()
        self.assertEqual(h.count('<section class="q"'), 6)
        self.assertIn("Keep the plain-text math notation", h)
        self.assertNotIn("</script></script>", h)

    def test_extract_eval_accepts_files(self):
        self.build("--n", "6")
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "exam.py"), "extract-eval",
                            os.path.join(self.out, "gold-draft.json"), os.path.join(self.out, "extracted.json"),
                            "--out", os.path.join(self.out, "eval")],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isdir(os.path.join(self.out, "eval")))

    def test_store_checks(self):
        self.build("--n", "6")
        ext = self.load("extracted.json")
        corr = self.load("gold-draft.json")
        dest = os.path.join(self.root, "evals", "gold.json")
        cpath = os.path.join(self.root, "corr.json")

        def store(doc):
            with open(cpath, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = T.main(["store", cpath, os.path.join(self.out, "extracted.json"), dest])
            return rc, buf.getvalue()

        rc, out = store(corr)
        self.assertEqual(rc, 1)
        self.assertIn("is not checked", out)
        for q in corr["questions"]:
            q["checked"] = True
        corr["questions"][0]["options"]["E"] = "x"
        rc, out = store(corr)
        self.assertEqual(rc, 1)
        self.assertIn("option letters changed", out)
        del corr["questions"][0]["options"]["E"]
        corr["questions"][0]["text"] = "Câu hỏi đã sửa?"
        rc, out = store(corr)
        self.assertEqual(rc, 0, out)
        with open(dest, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertIn("hand-checked", saved["origin"])
        self.assertEqual(len(saved["questions"]), len(ext["questions"]))
        corr["questions"].pop()
        self.assertEqual(store(corr)[0], 1)


if __name__ == "__main__":
    unittest.main()

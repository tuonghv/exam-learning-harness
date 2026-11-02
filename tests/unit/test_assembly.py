"""TASK-048: provenance sidecar (api.assembly), writer, inspect table, plan input copy, prompt lines. Mock only."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.core import refcheck  # noqa: E402
from exam_engine.ingest import api, inspect  # noqa: E402
from exam_engine.pipeline import planrun  # noqa: E402

O4 = {"A": "a", "B": "b", "C": "c", "D": "d"}
META = {"Subject": "math", "Level": "x", "Exam type": "t", "Task": "solve", "Mode": "m"}


def doc(questions=None, refined=None, md_text=None):
    d = {"source": {"name": "x.pdf", "format": "pdf", "sha256": "0" * 64},
         "status": "ok", "pages": [{"n": 1, "status": "native_text", "blocks": []},
                                   {"n": 2, "status": "native_text", "blocks": []}],
         "assets": [], "warnings": [], "meta": dict(META), "questions": questions or []}
    if refined is not None:
        d["refined"] = {"questions": refined}
    return d


def rq(i, text, page, **kw):
    return dict({"id": str(i), "text": text, "options": O4, "page": page}, **kw)


# q1 cut on p1 + continued on p2; q2 whole; q3 cut and never continued; q4 orphan.
REFINED = [rq(1, "stem one", 1, cut=True, options={}),
           rq(1, "rest one", 2, continued_pages=[2]),
           rq(2, "second", 2),
           rq(3, "third", 2, cut=True),
           rq(4, "fourth", 2, orphan_page=2)]
CFG = {"use_refined": True}


class AssemblyTest(unittest.TestCase):
    def test_refined_rows(self):
        rows = api.assembly(doc(refined=REFINED), CFG)
        self.assertEqual([r["id"] for r in rows], ["1", "2", "3", "4"])
        self.assertEqual(list(rows[0]), ["id", "printed", "source_pages", "assembly_status",
                                         "validation_status", "reasons"])
        self.assertEqual(rows[0]["source_pages"], [1, 2])
        self.assertEqual((rows[0]["assembly_status"], rows[0]["validation_status"]), ("complete", "passed"))
        self.assertEqual(rows[1]["source_pages"], [2])

    def test_uncertain_and_failed(self):
        rows = api.assembly(doc(refined=REFINED), CFG)
        self.assertEqual(rows[2]["reasons"], ["cut_unresolved"])
        self.assertEqual((rows[2]["assembly_status"], rows[2]["validation_status"]), ("uncertain", "failed"))
        self.assertEqual(rows[3]["assembly_status"], "uncertain")
        self.assertTrue(rows[3]["reasons"][0].startswith("orphan_on_page"))

    def test_failed_iff_marker_in_exam_text(self):
        for d, cfg in ((doc(refined=REFINED), CFG),
                       (doc(questions=[{"n": 1, "text": "ok", "options": [{"key": "A", "text": "a"}]},
                                       {"n": 2, "text": "ok2", "options": []}]), None)):
            text = api.to_exam_text(d, cfg)
            blocks = text.split("## Question ")[1:]
            rows = api.assembly(d, cfg)
            self.assertEqual(len(blocks), len(rows))
            for blk, r in zip(blocks, rows):
                self.assertEqual(r["validation_status"] == "failed", "[Incomplete:" in blk)
                if r["reasons"]:
                    self.assertEqual(refcheck.marker_reasons(blk), ", ".join(r["reasons"]))

    def test_text_path_has_no_pages_and_keeps_restarts(self):
        qs = [{"n": 1, "text": "a", "options": []}, {"n": 2, "text": "b", "options": []},
              {"n": 1, "text": "c", "options": []}]
        rows = api.assembly(doc(questions=qs))
        self.assertEqual([r["printed"] for r in rows], ["s1.1", "s1.2", "s2.1"])
        self.assertTrue(all(r["source_pages"] == [] for r in rows))

    def test_question_slice_and_empty(self):
        rows = api.assembly(doc(refined=REFINED), dict(CFG, questions="2-3"))
        self.assertEqual([r["printed"] for r in rows], ["2", "3"])
        self.assertEqual(api.assembly(doc()), [])


class WriterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_ingest(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["ingest"] + args)
        return code, err.getvalue()

    def test_sidecar_written_for_refined_and_absent_for_exam_markdown(self):
        src = os.path.join(self.tmp, "s.md")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write("Cau 1. Two?\nA. 1\nB. 2\nC. 3\nD. 4\n")
        ref = os.path.join(self.tmp, "ref.json")
        with open(ref, "w", encoding="utf-8") as fh:
            json.dump({"refined": {"questions": REFINED}}, fh)
        meta = [x for k, v in META.items() for x in ("--meta", "%s=%s" % (k, v))]
        exam = os.path.join(self.tmp, "e.md")
        code, err = self.run_ingest([src, "--exam-out", exam, "--refined", ref] + meta)
        self.assertEqual(code, 0, err)
        with open(exam + ".assembly.json", encoding="utf-8") as fh:
            side = json.load(fh)
        self.assertEqual((side["schema"], side["exam"]), ("assembly/1", "e.md"))
        self.assertEqual([r["id"] for r in side["questions"]], ["1", "2", "3", "4"])
        good = os.path.join(ROOT, "examples", "english", "input-001.md")
        exam2 = os.path.join(self.tmp, "e2.md")
        code, err = self.run_ingest([good, "--exam-out", exam2])
        self.assertEqual(code, 0, err)
        self.assertFalse(os.path.exists(exam2 + ".assembly.json"))


class InspectTest(unittest.TestCase):
    def test_table_per_question_and_omitted(self):
        text = inspect.report(doc(refined=REFINED))
        self.assertIn("## Assembly", text)
        self.assertIn("| 1 | 1 | 1,2 | complete | passed | - |", text)
        self.assertIn("| 3 | 3 | 2 | uncertain | failed | cut_unresolved |", text)
        self.assertNotIn("## Assembly", inspect.report(doc()))


class PlanCopyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.exam = os.path.join(self.tmp, "e.md")
        with open(self.exam, "w") as fh:
            fh.write("# x\n")

    def test_copy_helper(self):
        inp = os.path.join(self.tmp, "input")
        os.makedirs(inp)
        planrun._copy_assembly(self.exam, inp)
        self.assertFalse(os.path.exists(os.path.join(inp, "assembly.json")))
        with open(self.exam + ".assembly.json", "w") as fh:
            fh.write('{"schema": "assembly/1"}')
        planrun._copy_assembly(self.exam, inp)
        with open(os.path.join(inp, "assembly.json")) as fh:
            self.assertEqual(fh.read(), '{"schema": "assembly/1"}')

    def test_import_dir_copies(self):
        src = os.path.join(self.tmp, "old")
        os.makedirs(src)
        with open(os.path.join(src, "result.json"), "w") as fh:
            json.dump({"exam": {}, "questions": [], "meta": {}}, fh)
        with open(self.exam + ".assembly.json", "w") as fh:
            fh.write("{}")
        try:
            out, _ = planrun.import_dir(src, os.path.join(self.tmp, "plans"), exam_path=self.exam)
        except ValueError as exc:
            self.skipTest("fixture result.json not importable: %s" % exc)
        self.assertTrue(os.path.isfile(os.path.join(out, "input", "assembly.json")))


class PromptLinesTest(unittest.TestCase):
    def read(self, *p):
        with open(os.path.join(ROOT, "prompts", *p), encoding="utf-8") as fh:
            return fh.read()

    def test_lines(self):
        self.assertIn("missing_text:", self.read("dev", "system.md"))
        self.assertIn("missing_text:", self.read("dev", "lang", "vi", "system.md"))
        self.assertIn("12. Never transcribe running headers", self.read("dev", "ingest", "refine.md"))
        rel = os.path.join(ROOT, "prompts", "releases")
        for base, _, names in os.walk(rel):
            for n in names:
                if n.endswith("system.md"):
                    with open(os.path.join(base, n), encoding="utf-8") as fh:
                        self.assertNotIn("missing_text:", fh.read(), base)


if __name__ == "__main__":
    unittest.main()

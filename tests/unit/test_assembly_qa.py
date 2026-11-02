"""TASK-048 QA: 60.1-60.6 golden vs baseline 63a5299, sidecar content/determinism, PlanWriter copy,
prompt lines (dev only, releases untouched), G2 (real-shaped doc) and G3 (metrics)."""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exam_engine import cli  # noqa: E402
from exam_engine.ingest import inspect, optional  # noqa: E402
from exam_engine.ingest.schema import IngestError  # noqa: E402
from exam_engine.pipeline import metrics, planrun  # noqa: E402
import test_assembly as TA  # noqa: E402

BASE = "63a5299"
PDF = "examples/dgnl/De-thi-minh-hoa-2026-Final.pdf"
REAL = os.path.join(ROOT, "work", "dgnl-real", "v3", "13-22.json")
META = [x for k, v in TA.META.items() for x in ("--meta", "%s=%s" % (k, v))]
RUN = ("import sys; sys.path.insert(0, sys.argv[1] + '/src'); from exam_engine import cli; "
       "sys.exit(cli.main(['ingest'] + sys.argv[2:]))")


def ingest(tree, args):
    r = subprocess.run([sys.executable, "-I", "-c", RUN, tree] + args, capture_output=True, text=True, cwd=tree)
    return r.returncode


def rb(p):
    with open(p, "rb") as fh:
        return fh.read()


class Golden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)
        arc = subprocess.run(["git", "archive", BASE, "src", "config", "schemas", "prompts"], cwd=ROOT, capture_output=True)
        if arc.returncode:
            raise unittest.SkipTest("baseline %s absent" % BASE)
        cls.base = os.path.join(cls.tmp, "base")
        os.mkdir(cls.base)
        subprocess.run(["tar", "-x", "-C", cls.base], input=arc.stdout, check=True)

    def pair(self, src, extra, tag):
        out = {}
        for name, tree in (("b", self.base), ("h", ROOT)):
            d = os.path.join(self.tmp, tag + name)
            os.mkdir(d)
            args = [src, "--out", os.path.join(d, "doc.json"), "--exam-out", os.path.join(d, "e.md")] + META + extra
            self.assertEqual(ingest(tree, args), 0, tag + name)
            out[name] = d
        return out["b"], out["h"]

    def same(self, b, h):
        self.assertEqual(sorted(os.listdir(b)), ["doc.json", "e.md"])
        da, ha = rb(os.path.join(b, "doc.json")), rb(os.path.join(h, "doc.json"))
        if b'"method": "ocr"' in da:
            # OCR source: 51.1 re-spaces glued words (intended): equal up to whitespace, never fewer breaks
            ws = lambda x: re.sub(rb"\s+|\\n|\"chars\": ?\d+", b"", x)  # noqa: E731
            self.assertEqual(ws(da), ws(ha))
            self.assertGreaterEqual(len(ha.split()), len(da.split()))
            return sorted(set(os.listdir(h)) - {"doc.json", "e.md"})
        self.assertEqual(da, ha)
        self.assertEqual(rb(os.path.join(b, "e.md")), rb(os.path.join(h, "e.md")))
        return sorted(set(os.listdir(h)) - {"doc.json", "e.md"})

    def test_48_golden_exam_markdown_examples_no_sidecar(self):
        for n, name in enumerate(sorted(os.listdir(os.path.join(ROOT, "examples")))):
            p = os.path.join("examples", name, "input-001.md")
            if not os.path.isfile(os.path.join(ROOT, p)):
                continue
            b, h = self.pair(os.path.join(ROOT, p), [], "m%d" % n)
            self.assertEqual(self.same(b, h), [], p)

    def two_page_pdf(self):
        try:
            fitz = optional.load("fitz", "pymupdf")
        except IngestError:
            self.skipTest("pymupdf absent")
        doc = fitz.open()
        for t in ("Cau 1. What is two plus two in base ten?\nA. 3\nB. 4\nC. 5\nD. 6\n"
                  "Cau 2. What is three plus three here?\nA. 5\nB. 6\nC. 7\nD. 8",
                  "Cau 3. What is one plus one?\nA. 1\nB. 2\nC. 3\nD. 4\nCau 4. Name the missing option here?"):
            doc.new_page().insert_text((72, 100), t, fontsize=11)
        path = os.path.join(self.tmp, "two.pdf")
        doc.save(path)
        return path

    def test_48_golden_pdf_text_path_new_file_only_and_deterministic(self):
        pdf = self.two_page_pdf()
        b, h = self.pair(pdf, [], "pdf")
        self.assertEqual(self.same(b, h), ["e.md.assembly.json"])
        side = json.loads(rb(os.path.join(h, "e.md.assembly.json")))
        self.assertEqual(side["schema"], "assembly/1")
        self.assertEqual([r["id"] for r in side["questions"]], ["1", "2", "3", "4"])
        self.assertTrue(all(r["source_pages"] == [] for r in side["questions"]))
        failed = sum(r["validation_status"] == "failed" for r in side["questions"])
        self.assertEqual(failed, rb(os.path.join(h, "e.md")).decode("utf-8").count("[Incomplete:"))
        h2 = os.path.join(self.tmp, "pdf2")
        os.mkdir(h2)
        self.assertEqual(ingest(ROOT, [pdf, "--out", os.path.join(h2, "doc.json"),
                                       "--exam-out", os.path.join(h2, "e.md")] + META), 0)
        self.assertEqual(rb(os.path.join(h, "e.md.assembly.json")), rb(os.path.join(h2, "e.md.assembly.json")))

    @unittest.skipUnless(os.path.isfile(os.path.join(ROOT, PDF)) and os.path.isfile(REAL), "pdf/real doc absent")
    def test_48_golden_refined_real_doc(self):
        b, h = self.pair(os.path.join(ROOT, PDF), ["--refined", REAL], "ref")
        self.assertEqual(self.same(b, h), ["e.md.assembly.json"])
        side = json.loads(rb(os.path.join(h, "e.md.assembly.json")))
        self.assertTrue(all(r["source_pages"] for r in side["questions"]))
        self.assertEqual({r["validation_status"] for r in side["questions"]} - {"passed", "failed"}, set())


class SidecarContent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_cli(self):
        src = os.path.join(self.tmp, "s.md")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write("Cau 1. Two?\nA. 1\nB. 2\nC. 3\nD. 4\n")
        ref = os.path.join(self.tmp, "ref.json")
        with open(ref, "w", encoding="utf-8") as fh:
            json.dump({"refined": {"questions": TA.REFINED}}, fh)
        meta = [x for k, v in TA.META.items() for x in ("--meta", "%s=%s" % (k, v))]
        exam = os.path.join(self.tmp, "e.md")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["ingest", src, "--exam-out", exam, "--refined", ref] + meta), 0)
        return exam

    def test_48_60_2_rows_exact_and_deterministic(self):
        exam = self.run_cli()
        first = rb(exam + ".assembly.json")
        side = json.loads(first)
        want = [("1", "1", [1, 2], "complete", "passed", False), ("2", "2", [2], "complete", "passed", False),
                ("3", "3", [2], "uncertain", "failed", True), ("4", "4", [2], "uncertain", "failed", True)]
        got = [(r["id"], r["printed"], r["source_pages"], r["assembly_status"], r["validation_status"],
                bool(r["reasons"])) for r in side["questions"]]
        self.assertEqual(got, want)
        self.assertEqual(side["questions"][2]["reasons"], ["cut_unresolved"])
        os.remove(exam + ".assembly.json")
        self.run_cli()
        self.assertEqual(rb(exam + ".assembly.json"), first)

    def test_48_60_2_sidecar_never_replaces_exam_text(self):
        exam = self.run_cli()
        txt = rb(exam).decode("utf-8")
        self.assertIn("## Question 1", txt)
        self.assertNotIn("assembly/1", txt)
        self.assertNotEqual(rb(exam), rb(exam + ".assembly.json"))


class PlanStart(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.exam = os.path.join(self.tmp, "e.md")
        with open(self.exam, "w") as fh:
            fh.write("## Question 1\nx\n")

    def start(self, tag):
        d = os.path.join(self.tmp, tag)
        w = planrun.PlanWriter(d, self.exam, {"model": "m", "llm_name": "mock", "key": None})
        w.start()
        return os.path.join(d, "input")

    def test_48_60_4_planwriter_start_copies_only_when_present(self):
        self.assertFalse(os.path.exists(os.path.join(self.start("a"), "assembly.json")))
        with open(self.exam + ".assembly.json", "w") as fh:
            fh.write('{"schema": "assembly/1"}')
        inp = self.start("b")
        self.assertEqual(rb(os.path.join(inp, "assembly.json")), b'{"schema": "assembly/1"}')
        self.assertEqual(rb(os.path.join(inp, "exam.md")), rb(self.exam))

    def test_48_60_4_symlink_sidecar_not_followed(self):
        tgt = os.path.join(self.tmp, "secret.txt")
        with open(tgt, "w") as fh:
            fh.write("secret")
        os.symlink(tgt, self.exam + ".assembly.json")
        self.assertFalse(os.path.exists(os.path.join(self.start("c"), "assembly.json")))


class Prompts(unittest.TestCase):
    def test_48_60_5_6_dev_lines_present(self):
        for f in ("prompts/dev/system.md", "prompts/dev/lang/vi/system.md"):
            self.assertIn("missing_text:", open(os.path.join(ROOT, f), encoding="utf-8").read(), f)
        self.assertIn("\n12. Never transcribe running headers",
                      open(os.path.join(ROOT, "prompts/dev/ingest/refine.md"), encoding="utf-8").read())

    def test_48_releases_untouched_and_default_release(self):
        r = subprocess.run(["git", "diff", "--name-only", BASE, "--", "prompts/releases", "config/engine.json"],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            self.skipTest("baseline absent")
        self.assertEqual(r.stdout.strip(), "")
        for root, _, files in os.walk(os.path.join(ROOT, "prompts", "releases")):
            for f in files:
                self.assertNotIn("missing_text:", open(os.path.join(root, f), encoding="utf-8").read(), f)


class RealShaped(unittest.TestCase):
    @unittest.skipUnless(os.path.isfile(REAL), "work/dgnl-real/v3/13-22.json absent")
    def test_48_g2_inspect_prints_assembly_on_real_refined_doc(self):
        with open(REAL, encoding="utf-8") as fh:
            doc = json.load(fh)
        text = inspect.report(doc)
        self.assertEqual(text.count("## Assembly"), 1)
        n = len(doc["refined"]["questions"])
        rows = [ln for ln in text.split("## Assembly")[1].splitlines() if ln.startswith("| ") and "---" not in ln]
        self.assertGreaterEqual(len(rows), 10)
        self.assertLessEqual(len(rows) - 1, n)

    def test_48_g3_solver_missing_text_issue_not_counted_in_declined_missing_text(self):
        # status_reason is plain "solver_declined"; the model's `missing_text:` issue lives in findings only.
        res = {"questions": [{"id": "1", "status_reason": "solver_declined", "verification_status": "UNCERTAIN",
                              "qa_findings": [{"kind": "solver_declined", "detail": "missing_text: cut"}]},
                             {"id": "2", "status_reason": "solver_declined: missing_text (cut)",
                              "verification_status": "UNCERTAIN"}]}
        c = metrics.compute(res)["counts"]
        self.assertEqual((c["declined"], c["declined_missing_text"]), (2, 1))


if __name__ == "__main__":
    unittest.main()

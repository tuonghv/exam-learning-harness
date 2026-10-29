import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.abspath(os.path.join(HERE, "..", "..")), "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.ingest import api, inspect, optional, parts  # noqa: E402
from exam_engine.ingest.schema import IngestError, validate_document  # noqa: E402

try:
    fitz = optional.load("fitz", "pymupdf")
except IngestError:
    fitz = None

EXAM = [["Question 1. What is two plus two?", "A. three", "B. four"],
        ["Question 2. Pick the colour of grass.", "A. green", "B. red"]]
GUIDE = [["Answer key", "Item one is B", "Item two is A"], ["More working for the guide"]]
META = {"Subject": "Math", "Level": "12", "Exam type": "x", "Task": "t", "Mode": "m"}


def blk(i, text, typ="paragraph"):
    return {"id": "b%d" % i, "order": i, "type": typ, "text": text, "level": None,
            "bbox": [0, 0, 1, 1], "origin": "extracted", "asset": None}


def fake(pages_text, fmt="pdf"):
    pages = [{"n": n + 1, "blocks": [blk(10 * n + j, t) for j, t in enumerate(ts)],
              "status": "native_text"} for n, ts in enumerate(pages_text)]
    return {"schema_version": "1", "status": "native_text", "pages": pages, "assets": [],
            "warnings": [], "meta": {}, "extraction": {"method": "pdf", "tool": "t"},
            "source": {"path": "a.pdf", "name": "a.pdf", "format": fmt, "sha256": "ab" * 32,
                       "size": 1}}


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(args)
    return code, out.getvalue(), err.getvalue()


class PartsUnit(unittest.TestCase):
    def test_find_parts(self):
        doc = fake([["Q1"], ["Q2"], ["Hướng dẫn giải", "x"], ["y"]])
        self.assertEqual(parts.find_parts(doc), [{"kind": "exam", "pages": [1, 2]},
                                                 {"kind": "answer_key", "pages": [3, 4]}])
        self.assertEqual(parts.find_parts(fake([["Q1"], ["Q2"]])),
                         [{"kind": "exam", "pages": [1, 2]}])

    def test_parse_pages(self):
        self.assertEqual(parts.parse_pages("1,3,5-6"), [1, 3, 5, 6])
        for bad in ("", "a", "3-1", "0", "1,,2"):
            with self.assertRaises(IngestError) as c:
                parts.parse_pages(bad)
            self.assertEqual(c.exception.code, "invalid_pages")

    def test_select_pages(self):
        doc = fake([["Question 1. a"], ["Question 2. b"], ["Answer key"]])
        doc["parts"] = parts.find_parts(doc)
        before = copy.deepcopy(doc)
        new = parts.select_pages(doc, "1-2")
        self.assertEqual(doc, before)
        self.assertEqual([p["n"] for p in new["pages"]], [1, 2])
        self.assertEqual(new["parts"], [{"kind": "exam", "pages": [1, 2]}])
        self.assertEqual([q["n"] for q in new["questions"]], [1, 2])
        self.assertIn("pages_selected", [w["code"] for w in new["warnings"]])
        with self.assertRaises(IngestError):
            parts.select_pages(doc, "2-9")


class InspectUnit(unittest.TestCase):
    def codes(self, doc):
        return [s["code"] for s in inspect.suspicious(doc)]

    def test_heuristics(self):
        doc = fake([["\n".join("x" for _ in range(7)), "B. —", "ok text here", "@@@@@@@@ a"]])
        doc["questions"] = [{"n": 1, "text": "a", "options": []},
                            {"n": 3, "text": "b", "options": []}]
        doc["warnings"].append({"level": "warning", "code": "missing_text", "message": "m",
                                "page": 1})
        got = self.codes(doc)
        for c in ("split_formula", "option_without_text", "numbering_gap", "missing_text"):
            self.assertIn(c, got)
        self.assertEqual(self.codes(fake([["Fine sentence, with punctuation."]])), [])

    def test_stray(self):
        self.assertIn("stray_chars", self.codes(fake([["ab \x01\x02\x03\x04 cd"]])))

    def test_report_readonly(self):
        doc = fake([["Question 1. a"], ["Answer key"]])
        doc["parts"] = parts.find_parts(doc)
        before = json.dumps(doc, sort_keys=True)
        text = inspect.report(doc)
        self.assertEqual(json.dumps(doc, sort_keys=True), before)
        for needle in ("# Ingest report", "ANSWER KEY PRESENT", "answer_key p2-2",
                       "not proof of correctness"):
            self.assertIn(needle, text)

    def test_guard_and_schema(self):
        doc = fake([["Question 1. a"], ["Answer key"]])
        doc["parts"] = parts.find_parts(doc)
        doc["meta"] = dict(META)
        self.assertEqual(validate_document(doc), [])
        with self.assertRaises(IngestError) as c:
            api.to_exam_text(doc)
        self.assertEqual(c.exception.code, "answer_key_present")
        doc["questions"] = [{"n": 1, "text": "a", "options": []}]
        self.assertIn("Question 1", api.to_exam_text(doc, {"allow_key_pages": True}))
        doc["parts"][0]["kind"] = "bogus"
        self.assertTrue(validate_document(doc))

    def test_markdown_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "e.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("# Notes\n\nSome text.\n")
            doc = api.ingest_document(p)
            self.assertNotIn("parts", doc)
            self.assertIn("# Ingest report", inspect.report(doc))


@unittest.skipIf(fitz is None, "PyMuPDF (fitz) not installed")
class PdfInspect(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        d = fitz.open()
        for lines in EXAM + GUIDE:
            page = d.new_page()
            for i, ln in enumerate(lines):
                page.insert_text((72, 72 + 18 * i), ln, fontsize=12)
        self.pdf = os.path.join(self.dir, "t.pdf")
        d.save(self.pdf)
        d.close()
        self.cfg = {"asset_dir": os.path.join(self.dir, "assets")}

    def test_parts_and_guard(self):
        doc = api.ingest_document(self.pdf, dict(self.cfg), META)
        self.assertEqual(doc["parts"], [{"kind": "exam", "pages": [1, 2]},
                                        {"kind": "answer_key", "pages": [3, 4]}])
        with self.assertRaises(IngestError) as c:
            api.to_exam_text(doc)
        self.assertEqual(c.exception.code, "answer_key_present")
        api.to_exam_text(doc, {"allow_key_pages": True})

    def test_pages_option(self):
        doc = api.ingest_document(self.pdf, dict(self.cfg, pages="1-2"), META)
        self.assertEqual(doc["parts"], [{"kind": "exam", "pages": [1, 2]}])
        self.assertIn("Question 1", api.to_exam_text(doc))
        with self.assertRaises(IngestError) as c:
            api.ingest_document(self.pdf, dict(self.cfg, pages="1-9"), META)
        self.assertEqual(c.exception.code, "invalid_pages")

    def test_cli(self):
        meta = ["--meta=%s=%s" % kv for kv in META.items()]
        base = ["ingest", self.pdf, "--assets", self.cfg["asset_dir"]] + meta
        exam = os.path.join(self.dir, "e.md")
        code, _o, err = run(base + ["--exam-out", exam, "--out", os.path.join(self.dir, "d.json")])
        self.assertEqual(code, 2)
        self.assertIn("answer_key_present", err)
        self.assertEqual(run(base + ["--pages", "1-2", "--exam-out", exam])[0], 0)
        self.assertEqual(run(base + ["--allow-key-pages", "--exam-out", exam])[0], 0)
        self.assertEqual(run(base + ["--pages", "x"])[0], 2)

    def test_inspect_cli_unchanged(self):
        js = os.path.join(self.dir, "d.json")
        self.assertEqual(run(["ingest", self.pdf, "--assets", self.cfg["asset_dir"],
                              "--out", js])[0], 0)
        with open(js, "rb") as fh:
            raw = fh.read()
        rep = os.path.join(self.dir, "r.md")
        code, _o, _e = run(["ingest-inspect", js, "--out", rep])
        self.assertEqual(code, 0)
        with open(js, "rb") as fh:
            self.assertEqual(fh.read(), raw)
        with open(rep, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("ANSWER KEY PRESENT", text)
        code, out, _e = run(["ingest-inspect", js, "--pages", "1-2"])
        self.assertEqual(code, 0)
        self.assertNotIn("ANSWER KEY PRESENT", out)
        self.assertEqual(run(["ingest-inspect", self.pdf, "--pages", "1-2"])[0], 0)
        self.assertEqual(run(["ingest-inspect", js, "--pages", "9"])[0], 2)


if __name__ == "__main__":
    unittest.main()

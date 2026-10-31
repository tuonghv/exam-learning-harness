"""Phase 38 (REQ-0041): ingest keeps questions with numbering gaps / restarts. $0, no network."""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import api, inspect, optional, parts, refine, segment  # noqa: E402
from exam_engine.ingest.schema import IngestError  # noqa: E402
from exam_engine.pipeline import parser  # noqa: E402

try:
    fitz = optional.load("fitz", "pymupdf")
except IngestError:
    fitz = None
try:
    docx = optional.load("docx", "python-docx")
except IngestError:
    docx = None


META = {"Subject": "English", "Level": "Grade 12", "Exam type": "High School Graduation",
        "Task": "Multiple Choice", "Mode": "Solve"}
OPTS = [{"key": k, "text": "x"} for k in "ABCD"]


def qs_of(ns, text="t"):
    return [{"n": n, "text": text, "options": []} for n in ns]


def lines_for(ns):
    out = ["Read carefully."]
    for n in ns:
        out += ["%d. Question text %d" % (n, n), "A. x"]
    return out


def codes(doc):
    return [w["code"] for w in doc["warnings"]]


class TestNumbering(unittest.TestCase):
    def test_usable_table(self):
        rows = [([1, 150], True, "2-149"), (list(range(31, 61)), True, "1-30"),
                (list(range(1, 11)) * 2, True, None), ([1, 1], True, None),
                ([1, 2, 3, 4, 5, 1, 2, 3, 6], False, None), ([3, 2], False, None),
                ([1, 2, 2], False, None), (list(range(1, 21)) + [2019], False, None),
                ([0, 1], False, None), ([1, 5, 1, 2], False, None)]
        for ns, usable, missing in rows:
            info = segment.numbering(qs_of(ns))
            self.assertEqual(info["usable"], usable, ns)
            if missing:
                self.assertEqual(info["missing"], [[0, missing]])

    def test_empty_text_not_usable(self):
        self.assertFalse(segment.numbering(qs_of([1, 150], text=""))["usable"])

    def test_ranges(self):
        self.assertEqual(segment.ranges([2, 3, 4, 9]), "2-4, 9")
        self.assertEqual(segment.ranges([]), "")

    def test_warnings(self):
        self.assertEqual(segment.numbering_warnings(qs_of([1, 150])),
                         [("numbering_gap", "missing question numbers: 2-149")])
        self.assertEqual(segment.numbering_warnings(qs_of([1, 2, 3])), [])
        self.assertEqual(segment.numbering_warnings(qs_of([1, 2, 1, 2])),
                         [("numbering_restarted", "numbering restarts at 1: 2 sections (1-2, 1-2)")])
        w = segment.numbering_warnings(qs_of([1, 2, 3, 1, 2, 3, 6]))
        self.assertEqual([c for c, _ in w], ["numbering_restarted"])  # not usable: no gap row

    def test_old_segment_ok_unchanged(self):
        self.assertFalse(segment.segment(["1. a", "3. c"])[2])
        self.assertTrue(segment.segment(["1. a", "2. b"])[2])


@unittest.skipIf(fitz is None, "PyMuPDF (fitz) not installed")
class TestPdf(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def ingest(self, ns):
        d = fitz.open()
        for i, ln in enumerate(lines_for(ns)):
            if i % 40 == 0:
                page = d.new_page()
            page.insert_text((72, 60 + 14 * (i % 40)), ln, fontsize=10)
        path = os.path.join(self.dir, "t.pdf")
        d.save(path)
        d.close()
        return api.ingest_document(path, config={"asset_dir": os.path.join(self.dir, "a"),
                                                 "ocr": "off"})

    def test_gap_kept(self):
        doc = self.ingest([1, 150])
        self.assertEqual([q["n"] for q in doc["questions"]], [1, 150])
        self.assertNotIn("segmentation_skipped", codes(doc))
        msg = [w["message"] for w in doc["warnings"] if w["code"] == "numbering_gap"]
        self.assertEqual(len(msg), 1)
        self.assertIn("2-149", msg[0])

    def test_clean_restart_kept(self):
        doc = self.ingest(list(range(1, 11)) * 2)
        self.assertEqual(len(doc["questions"]), 20)
        self.assertIn("numbering_restarted", codes(doc))
        self.assertNotIn("numbering_gap", codes(doc))

    def test_restart_with_gap_skipped_and_flagged(self):
        doc = self.ingest([1, 2, 3, 4, 5, 1, 2, 3, 6])
        self.assertNotIn("questions", doc)
        self.assertIn("segmentation_skipped", codes(doc))
        self.assertIn("numbering_restarted", codes(doc))

    def test_stray_year_after_last_skipped(self):
        doc = self.ingest(list(range(1, 21)) + [2019])
        self.assertNotIn("questions", doc)
        self.assertIn("segmentation_skipped", codes(doc))

    def test_consecutive_unchanged(self):
        doc = self.ingest([1, 2, 3])
        self.assertEqual(len(doc["questions"]), 3)
        self.assertEqual([c for c in codes(doc) if "numbering" in c or "segm" in c], [])


@unittest.skipIf(docx is None, "python-docx not installed")
class TestDocx(unittest.TestCase):
    def test_gap_kept(self):
        with tempfile.TemporaryDirectory() as td:
            d = docx.Document()
            for ln in lines_for([1, 150]):
                d.add_paragraph(ln)
            path = os.path.join(td, "t.docx")
            d.save(path)
            doc = api.ingest_document(path, config={"asset_dir": os.path.join(td, "a")})
        self.assertEqual([q["n"] for q in doc["questions"]], [1, 150])
        self.assertIn("numbering_gap", codes(doc))


def fake_doc(ns):
    lines = lines_for(ns)
    half = len(lines) // 2
    blk = [{"id": "b%d" % i, "order": i, "type": "paragraph", "text": t, "origin": "extracted"}
           for i, t in enumerate(lines)]
    pages = [{"n": 1, "blocks": blk[:half], "status": "native_text"},
             {"n": 2, "blocks": blk[half:], "status": "native_text"}]
    return {"schema_version": "1", "status": "native_text", "pages": pages, "assets": [],
            "warnings": [], "meta": {}, "extraction": {"method": "pdf", "tool": "t"},
            "source": {"path": "a.pdf", "name": "a.pdf", "format": "pdf", "sha256": "ab" * 32,
                       "size": 1}}


class TestPartsExamRefineInspect(unittest.TestCase):
    def test_select_second_half(self):
        doc = fake_doc(list(range(1, 21)))
        new = parts.select_pages(doc, "2")
        ns = [q["n"] for q in new["questions"]]
        self.assertEqual(ns, list(range(ns[0], 21)))
        gap = [w for w in new["warnings"] if w["code"] == "numbering_gap"]
        self.assertEqual(len(gap), 1)
        self.assertIn("1-", gap[0]["message"])
        self.assertNotIn("segmentation_skipped", codes(new))

    def exam(self, ns):
        doc = fake_doc(ns)
        doc["questions"] = [{"n": n, "text": "T%d" % n, "options": OPTS} for n in ns]
        doc["intro"] = ""
        doc["meta"] = dict(META)
        return api.to_exam_text(doc, {})

    def test_exam_text_renumbered(self):
        text = self.exam([1, 150])
        self.assertIn("## Question 1", text)
        self.assertIn("## Question 2", text)
        self.assertNotIn("## Question 150", text)
        self.assertIn("printed numbers: 1=1, 2=150.", text)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "e.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.assertEqual(parser.validate_exam(parser.parse_exam(path)), [])

    def test_exam_text_restart_mapping(self):
        text = self.exam([1, 2, 1, 2])
        self.assertIn("1=s1.1, 2=s1.2, 3=s2.1, 4=s2.2", text)

    def test_exam_text_strict_golden(self):
        text = self.exam([1, 2])
        self.assertTrue(text.endswith("\n\n## Question 1\n\nT1\n\nA. x\nB. x\nC. x\nD. x\n\n"
                                      "## Question 2\n\nT2\n\nA. x\nB. x\nC. x\nD. x\n"))
        self.assertNotIn("printed numbers", text)
        self.assertNotIn("## Instructions", text)

    def test_refine_guard(self):
        for ns, expect in (([1, 2, 1, 2], False), ([1, 150], True), ([1, 2], True)):
            doc = fake_doc(ns)
            doc["questions"] = [{"n": n, "text": "T", "options": []} for n in ns]
            seen = []

            def ask(llm, n, png, originals):
                seen.append(dict(originals))
                raise refine.RefineError("stop", "stop")
            with mock.patch.object(refine, "_ask", ask):
                with self.assertRaises(refine.RefineError):
                    refine.refine(doc, "1-2", None, all_pages=True)
            self.assertEqual(bool(seen[0]), expect, ns)

    def test_inspect_no_duplicate(self):
        doc = fake_doc([1, 150])
        doc["questions"] = [{"n": 1, "text": "a", "options": []},
                            {"n": 150, "text": "b", "options": []}]
        own = [r for r in inspect.suspicious(doc) if r["code"] == "numbering_gap"]
        doc["warnings"].append({"level": "warning", "code": "numbering_gap", "message": "m"})
        after = [r for r in inspect.suspicious(doc) if r["code"] == "numbering_gap"]
        self.assertEqual(len(own), 1)
        self.assertEqual(len(after), 1)

class SpanText(unittest.TestCase):
    def test_span_shows_gaps_and_descents(self):
        from exam_engine.ingest import segment
        self.assertEqual(segment._span([1, 2, 3, 4, 5]), "1-5")
        self.assertEqual(segment._span([1, 2, 3, 6]), "1-3, 6")
        self.assertEqual(segment._span([3, 2, 1]), "3, 2, 1")
        self.assertEqual(segment._span([7]), "7")


if __name__ == "__main__":
    unittest.main()

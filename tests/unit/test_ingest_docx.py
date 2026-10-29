"""Phase 15 (REQ-0018): DOCX adapter on synthetic documents built with python-docx. $0, no network."""
import hashlib
import io
import json
import os
import struct
import sys
import tempfile
import unicodedata
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.ingest import api, optional  # noqa: E402
from exam_engine.ingest.schema import IngestError, validate_document  # noqa: E402

try:
    docx = optional.load("docx", "python-docx")
except IngestError:
    docx = None

META = {"Subject": "S", "Level": "L", "Exam type": "E", "Task": "T", "Mode": "M"}
OMML = ('<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        '<m:r><m:t>x+y=2</m:t></m:r></m:oMath>')


def png_bytes():
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    raw = b"\x00\xff\x00\x00"
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


@unittest.skipIf(docx is None, "python-docx not installed")
class DocxBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        self.assets = os.path.join(self.dir, "assets")

    def save(self, d, name="t.docx"):
        path = os.path.join(self.dir, name)
        d.save(path)
        return path

    def ingest(self, path, **cfg):
        cfg.setdefault("asset_dir", self.assets)
        return api.ingest_document(path, config=cfg)

    def blocks(self, doc):
        return doc["pages"][0]["blocks"]

    def questions_doc(self):
        d = docx.Document()
        d.add_paragraph("Câu 1. What is two plus two?")
        for o in ("A. three", "B. four"):
            d.add_paragraph(o)
        d.add_paragraph("Câu 2. Pick the colour of grass.")
        for o in ("A. green", "B. red"):
            d.add_paragraph(o)
        return d


class TestBlocks(DocxBase):
    def test_headings_paragraph_list_valid_and_hash(self):
        d = docx.Document()
        d.add_heading("Main title", 1)
        d.add_heading("Part two", 2)
        d.add_paragraph("Plain text here.")
        d.add_paragraph("item one", style="List Bullet")
        path = self.save(d)
        doc = self.ingest(path)
        self.assertEqual(validate_document(doc), [])
        got = [(b["type"], b["level"], b["text"]) for b in self.blocks(doc)]
        self.assertEqual(got, [("heading", 1, "Main title"), ("heading", 2, "Part two"),
                               ("paragraph", None, "Plain text here."),
                               ("list", None, "item one")])
        with open(path, "rb") as fh:
            self.assertEqual(doc["source"]["sha256"], hashlib.sha256(fh.read()).hexdigest())
        self.assertEqual(doc["source"]["format"], "docx")
        self.assertEqual({b["origin"] for b in self.blocks(doc)}, {"source"})
        self.assertEqual(doc["extraction"]["method"], "python-docx")
        self.assertEqual(len(doc["pages"]), 1)

    def test_table_one_block_merged_cells_once(self):
        d = docx.Document()
        t = d.add_table(rows=2, cols=3)
        t.cell(0, 0).merge(t.cell(0, 1)).text = "head"
        t.cell(0, 2).text = "h3"
        for i, v in enumerate(("a", "b", "c")):
            t.cell(1, i).text = v
        doc = self.ingest(self.save(d))
        tb = [b for b in self.blocks(doc) if b["type"] == "table"]
        self.assertEqual(len(tb), 1)
        self.assertEqual(tb[0]["text"], "head | h3\na | b | c")

    def test_image_saved_bytes_unchanged(self):
        d = docx.Document()
        d.add_paragraph("before")
        d.add_picture(io.BytesIO(png_bytes()))
        doc = self.ingest(self.save(d))
        img = [b for b in self.blocks(doc) if b["type"] == "image"]
        self.assertEqual(len(img), 1)
        a = doc["assets"][0]
        self.assertEqual(img[0]["asset"], a["id"])
        self.assertEqual(a["sha256"], hashlib.sha256(png_bytes()).hexdigest())
        full = os.path.join(self.assets, os.path.basename(a["path"]))
        with open(full, "rb") as fh:
            self.assertEqual(fh.read(), png_bytes())
        self.assertTrue(os.path.basename(a["path"]).startswith("docx-img-001"))

    def test_image_without_folder_warns(self):
        d = docx.Document()
        d.add_picture(io.BytesIO(png_bytes()))
        path = self.save(d)
        doc = api.ingest_document(path, config={})
        self.assertEqual(doc["assets"], [])
        self.assertIn("asset_not_saved", [w["code"] for w in doc["warnings"]])
        self.assertEqual(self.blocks(doc)[0]["type"], "image")

    def test_math_text_kept_with_warning(self):
        from lxml import etree
        d = docx.Document()
        p = d.add_paragraph("Solve ")
        p._p.append(etree.fromstring(OMML))
        doc = self.ingest(self.save(d))
        self.assertIn("x+y=2", self.blocks(doc)[0]["text"])
        self.assertIn("math_possible", [w["code"] for w in doc["warnings"]])

    def test_header_not_read_warns(self):
        d = docx.Document()
        d.add_paragraph("body text")
        d.sections[0].header.paragraphs[0].text = "SECRET HEADER"
        doc = self.ingest(self.save(d))
        self.assertNotIn("SECRET HEADER", json.dumps(doc))
        self.assertIn("unsupported_content", [w["code"] for w in doc["warnings"]])

    def test_vietnamese_nfc(self):
        d = docx.Document()
        d.add_paragraph(unicodedata.normalize("NFD", "Tiếng Việt có dấu"))
        doc = self.ingest(self.save(d))
        self.assertEqual(self.blocks(doc)[0]["text"], "Tiếng Việt có dấu")


class TestQuestions(DocxBase):
    def test_questions_to_exam_text(self):
        doc = self.ingest(self.save(self.questions_doc()))
        self.assertEqual(len(doc["questions"]), 2)
        text = api.to_exam_text(dict(doc, meta=dict(META)))
        self.assertIn("## Question 2", text)
        self.assertIn("B. four", text)

    def test_key_pages_guard_applies(self):
        doc = self.ingest(self.save(self.questions_doc()))
        doc["parts"] = [{"kind": "answer_key", "pages": [1, 1]}]
        doc["meta"] = dict(META)
        with self.assertRaises(IngestError) as cm:
            api.to_exam_text(doc)
        self.assertEqual(cm.exception.code, "answer_key_present")


class TestFailures(DocxBase):
    def code(self, path):
        with self.assertRaises(IngestError) as cm:
            self.ingest(path)
        return cm.exception.code

    def write(self, name, data):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_not_a_zip_is_corrupt(self):
        self.assertEqual(self.code(self.write("a.docx", b"plain text, not a zip")), "corrupt")

    def test_zip_without_package_is_corrupt(self):
        import zipfile
        path = os.path.join(self.dir, "z.docx")
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("hello.txt", "x")
        self.assertEqual(self.code(path), "corrupt")

    def test_zero_bytes_and_blank_are_empty(self):
        self.assertEqual(self.code(self.write("z.docx", b"")), "empty")
        self.assertEqual(self.code(self.save(docx.Document(), "blank.docx")), "empty")

    def test_ole_header_is_encrypted(self):
        data = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 64
        self.assertEqual(self.code(self.write("e.docx", data)), "encrypted")


if __name__ == "__main__":
    unittest.main()

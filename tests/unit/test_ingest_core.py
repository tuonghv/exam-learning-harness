"""Phase 12 (REQ-0016): ingestion core, schema + Markdown adapter + exam text + CLI. No external call."""
import contextlib
import glob
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.ingest import api  # noqa: E402
from exam_engine.ingest.schema import IngestError, validate_document  # noqa: E402
from exam_engine.pipeline import parser  # noqa: E402

SAMPLE = """# Tiêu đề

Đoạn văn tiếng Việt có dấu: đúng, ắ, ữ.

- một
- hai

| a | b |
|---|---|
| 1 | 2 |

```python
x = 1
```

$$
x^2 + y^2
$$

![hình](img/pic.png)
"""


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def write(self, name, data, mode="w"):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        kw = {} if "b" in mode else {"encoding": "utf-8"}
        with open(path, mode, **kw) as fh:
            fh.write(data)
        return path

    def code_of(self, fn, *a, **kw):
        with self.assertRaises(IngestError) as cm:
            fn(*a, **kw)
        return cm.exception.code


class SchemaTest(Base):
    def good(self):
        self.write("img/pic.png", b"\x89PNG", "wb")
        return api.ingest_document(self.write("a.md", SAMPLE))

    def test_good_doc_valid(self):
        self.assertEqual(validate_document(self.good()), [])

    def test_missing_version(self):
        doc = self.good()
        del doc["schema_version"]
        self.assertTrue(validate_document(doc))

    def test_bad_status(self):
        doc = self.good()
        doc["status"] = "perfect"
        self.assertTrue(validate_document(doc))

    def test_duplicate_block_id(self):
        doc = self.good()
        blocks = doc["pages"][0]["blocks"]
        blocks[1]["id"] = blocks[0]["id"]
        self.assertTrue(any("duplicate" in e for e in validate_document(doc)))

    def test_asset_not_in_assets(self):
        doc = self.good()
        doc["assets"] = []
        self.assertTrue(any("not in assets" in e for e in validate_document(doc)))


class MarkdownTest(Base):
    def blocks(self):
        self.write("img/pic.png", b"\x89PNG", "wb")
        doc = api.ingest_document(self.write("a.md", SAMPLE))
        return doc, doc["pages"][0]["blocks"]

    def test_block_types_in_order(self):
        _, blocks = self.blocks()
        self.assertEqual([b["type"] for b in blocks],
                         ["heading", "paragraph", "list", "table", "code", "math", "image"])
        self.assertEqual([b["order"] for b in blocks], list(range(7)))
        self.assertEqual(blocks[0]["level"], 1)

    def test_vietnamese_intact(self):
        _, blocks = self.blocks()
        self.assertIn("Đoạn văn tiếng Việt có dấu: đúng, ắ, ữ.", blocks[1]["text"])
        self.assertEqual(blocks[0]["text"], "Tiêu đề")

    def test_image_asset(self):
        doc, blocks = self.blocks()
        self.assertEqual(blocks[-1]["asset"], doc["assets"][0]["id"])
        self.assertEqual(doc["assets"][0]["mime"], "image/png")
        self.assertEqual(len(doc["assets"][0]["sha256"]), 64)

    def test_traversal_rejected(self):
        self.write("secret.png", b"x", "wb")
        path = self.write("sub/a.md", "![x](../secret.png)\n")
        self.assertEqual(self.code_of(api.ingest_document, path), "invalid_document")

    def test_absolute_rejected(self):
        path = self.write("a.md", "![x](/etc/passwd)\n")
        self.assertEqual(self.code_of(api.ingest_document, path), "invalid_document")

    def test_symlink_escape_rejected(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        with open(os.path.join(outside.name, "s.png"), "wb") as fh:
            fh.write(b"x")
        try:
            os.symlink(os.path.join(outside.name, "s.png"), os.path.join(self.dir, "link.png"))
        except (OSError, NotImplementedError):
            self.skipTest("symlink unsupported")
        path = self.write("a.md", "![x](link.png)\n")
        self.assertEqual(self.code_of(api.ingest_document, path), "invalid_document")

    def test_missing_asset_names_file(self):
        path = self.write("a.md", "![x](nope.png)\n")
        with self.assertRaises(IngestError) as cm:
            api.ingest_document(path)
        self.assertEqual(cm.exception.code, "missing_asset")
        self.assertIn("nope.png", cm.exception.message)

    def test_empty(self):
        self.assertEqual(self.code_of(api.ingest_document, self.write("a.md", " \n")), "empty")

    def test_invalid_utf8(self):
        path = self.write("a.md", b"\xff\xfe\xfa", "wb")
        self.assertEqual(self.code_of(api.ingest_document, path), "decode")

    def test_unsupported_extension(self):
        path = self.write("a.xyz", "hi")
        self.assertEqual(self.code_of(api.ingest_document, path), "unsupported_format")


class ExamTextTest(Base):
    def test_free_form_needs_meta(self):
        doc = api.ingest_document(self.write("a.md", "# Hi\n\ntext\n"))
        with self.assertRaises(IngestError) as cm:
            api.to_exam_text(doc)
        self.assertEqual(cm.exception.code, "missing_header")
        self.assertIn("Subject", cm.exception.message)

    def test_free_form_with_meta(self):
        meta = {"Subject": "English", "Level": "G12", "Exam type": "X", "Task": "T",
                "Mode": "Solve"}
        doc = api.ingest_document(self.write("a.md", "## Question 1\n\ntext\n"), meta=meta)
        out = api.to_exam_text(doc)
        self.assertIn("Subject: English", out)
        self.assertIn("## Question 1", out)

    def test_examples_backward_compatible(self):
        files = sorted(glob.glob(os.path.join(ROOT, "examples", "**", "input-*.md"),
                                 recursive=True))
        self.assertTrue(files)
        for path in files:
            with open(path, "rb") as fh:
                raw = fh.read()
            doc = api.ingest_document(path)
            self.assertEqual(api.to_exam_text(doc).encode("utf-8"), raw, path)
            self.assertEqual(parser.validate_exam(parser.parse_exam(path)), [], path)


class CliTest(Base):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["ingest"] + list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_stdout_json_and_exam_out(self):
        src = os.path.join(ROOT, "examples", "english", "input-001.md")
        exam = os.path.join(self.dir, "exam.md")
        code, out, _ = self.run_cli(src, "--exam-out", exam)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["schema_version"], "1")
        with open(src, "rb") as a, open(exam, "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_out_file(self):
        out = os.path.join(self.dir, "doc.json")
        code, _, _ = self.run_cli(self.write("a.md", "# x\n"), "--out", out,
                                  "--meta", "Subject=English")
        self.assertEqual(code, 0)
        with open(out, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["meta"]["Subject"], "English")

    def test_errors_exit_2(self):
        self.assertEqual(self.run_cli(self.write("a.xyz", "x"))[0], 2)
        self.assertEqual(self.run_cli(self.write("b.md", "# x\n"), "--meta", "bad")[0], 2)
        code, _, err = self.run_cli(self.write("c.md", "# x\n"), "--exam-out",
                                    os.path.join(self.dir, "e.md"))
        self.assertEqual(code, 2)
        self.assertIn("missing_header", err)


if __name__ == "__main__":
    unittest.main()

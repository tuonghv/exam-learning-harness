"""Image ingest (REQ-0019): formats, originals kept, structured errors, resize, claude images."""
import base64
import contextlib
import hashlib
import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.abspath(os.path.join(HERE, "..", "..")), "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.ingest import api, optional  # noqa: E402
from exam_engine.ingest.adapters import image as imgmod  # noqa: E402
from exam_engine.ingest.schema import IngestError, validate_document  # noqa: E402

try:
    PIL = optional.load("PIL.Image", "pillow")
except IngestError:
    PIL = None


def _chunk(tag, data):
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def png_bytes(w=3, h=2, noise=0):
    rows = b"".join(b"\x00" + (os.urandom(w * 3) if noise else b"\x10\x20\x30" * w)
                    for _ in range(h))
    return (imgmod.PNG_MAGIC + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(rows)) + _chunk(b"IEND", b""))


def pil_bytes(fmt, w=5, h=4):
    buf = io.BytesIO()
    PIL.new("RGB", (w, h), (200, 30, 30)).save(buf, format=fmt)
    return buf.getvalue()


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(["ingest"] + args)
    return code, out.getvalue(), err.getvalue()


class ImageBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.assets = os.path.join(self.tmp.name, "assets")

    def write(self, name, data):
        p = os.path.join(self.tmp.name, name)
        with open(p, "wb") as fh:
            fh.write(data)
        return p

    def ingest(self, name, data, **cfg):
        cfg.setdefault("asset_dir", self.assets)
        return api.ingest_document(self.write(name, data), config=cfg)

    def code(self, name, data, **cfg):
        with self.assertRaises(IngestError) as cm:
            self.ingest(name, data, **cfg)
        return cm.exception.code


class TestFormats(ImageBase):
    def check(self, name, data, w, h, mime):
        doc = self.ingest(name, data)
        self.assertEqual(validate_document(doc), [])
        pg = doc["pages"][0]
        self.assertEqual((pg["n"], pg["width"], pg["height"]), (1, w, h))
        self.assertEqual([b["type"] for b in pg["blocks"]], ["image"])
        self.assertEqual(doc["status"], "needs_review")
        self.assertEqual(doc["extraction"]["method"], "image")
        self.assertIn("image_only", [x["code"] for x in doc["warnings"]])
        a = doc["assets"][0]
        self.assertEqual((a["mime"], a["sha256"]), (mime, hashlib.sha256(data).hexdigest()))
        self.assertEqual(pg["blocks"][0]["asset"], a["id"])
        with open(os.path.join(self.assets, name), "rb") as fh:
            self.assertEqual(fh.read(), data)  # bytes unchanged
        self.assertEqual(doc["source"]["size"], len(data))

    def test_png(self):
        self.check("q.png", png_bytes(7, 5), 7, 5, "image/png")

    @unittest.skipIf(PIL is None, "PIL not installed")
    def test_jpeg_jpg_webp(self):
        self.check("q.jpg", pil_bytes("JPEG", 9, 6), 9, 6, "image/jpeg")
        self.check("q.jpeg", pil_bytes("JPEG", 4, 8), 4, 8, "image/jpeg")
        self.check("q.webp", pil_bytes("WEBP", 11, 3), 11, 3, "image/webp")

    def test_no_assets_dir_keeps_source_ref(self):
        doc = api.ingest_document(self.write("r.png", png_bytes()), config={})
        self.assertEqual(doc["assets"][0]["path"], "r.png")
        self.assertEqual(validate_document(doc), [])

    def test_ocr_off_by_default(self):
        with mock.patch.object(imgmod, "_ocr") as ocr:
            self.ingest("o.png", png_bytes())
            self.ingest("o.png", png_bytes(), ocr="auto")
        ocr.assert_not_called()

    def test_ocr_on_unavailable_warns_never_drops_image(self):
        with mock.patch.object(imgmod, "_ocr", return_value=(None, "no tesseract")):
            doc = self.ingest("o.png", png_bytes(), ocr="on")
        self.assertEqual(doc["pages"][0]["blocks"][0]["type"], "image")
        self.assertIn("ocr_unavailable", [x["code"] for x in doc["warnings"]])

    def test_ocr_on_adds_extracted_block_after_image(self):
        with mock.patch.object(imgmod, "_ocr", return_value=("Câu 1. x", None)):
            doc = self.ingest("o.png", png_bytes(), ocr="on")
        blocks = doc["pages"][0]["blocks"]
        self.assertEqual([(b["type"], b["origin"]) for b in blocks],
                         [("image", "source"), ("paragraph", "extracted")])
        self.assertNotIn("image_only", [x["code"] for x in doc["warnings"]])

    def test_cli_and_exam_text_no_text(self):
        src = self.write("c.png", png_bytes())
        out = os.path.join(self.tmp.name, "d.json")
        code, _, err = run_cli([src, "--assets", self.assets, "--out", out])
        self.assertEqual(code, 0, err)
        with open(out, encoding="utf-8") as fh:
            doc = json.load(fh)
        with self.assertRaises(IngestError) as cm:
            api.to_exam_text(doc)
        self.assertEqual(cm.exception.code, "no_text")
        code, _, err = run_cli([src, "--exam-out", os.path.join(self.tmp.name, "e.md")])
        self.assertEqual(code, 2)
        self.assertIn("no_text", err)


class TestErrors(ImageBase):
    def test_truncated(self):
        raw = png_bytes()
        self.assertEqual(self.code("t.png", raw[:20]), "corrupt")
        self.assertEqual(self.code("t2.png", raw[:-5]), "corrupt")
        self.assertEqual(self.code("t3.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF"), "corrupt")

    def test_wrong_extension(self):
        self.assertEqual(self.code("x.jpg", png_bytes()), "format_mismatch")

    def test_empty(self):
        self.assertEqual(self.code("e.png", b""), "empty")

    def test_text_named_png(self):
        self.assertEqual(self.code("t.png", b"hello, not an image at all, sorry"), "corrupt")

    def test_magic_check_decides_format(self):
        self.assertIsNone(imgmod.sniff(b"hello"))
        self.assertEqual(imgmod.sniff(png_bytes()), "png")

    def test_unsupported_extension(self):
        self.assertEqual(self.code("g.gif", b"GIF89a" + b"\0" * 20), "unsupported_format")


class TestOversize(ImageBase):
    @unittest.skipIf(PIL is None, "PIL not installed")
    def test_resize_lists_both_assets(self):
        data = png_bytes(120, 120, noise=1)
        doc = self.ingest("big.png", data, max_image_bytes=len(data) // 3)
        self.assertEqual(validate_document(doc), [])
        a1, a2 = doc["assets"]
        self.assertEqual((a1["origin"], a2["origin"], a2["derived_from"]),
                         ("source", "normalized", "a1"))
        self.assertEqual(doc["pages"][0]["blocks"][0]["asset"], "a1")
        with open(os.path.join(self.assets, "big.png"), "rb") as fh:
            self.assertEqual(fh.read(), data)
        with open(os.path.join(self.assets, "big.small.png"), "rb") as fh:
            small = fh.read()
        self.assertLessEqual(len(small), len(data) // 3)
        self.assertEqual(hashlib.sha256(small).hexdigest(), a2["sha256"])
        self.assertIn("image_resized", [x["code"] for x in doc["warnings"]])

    def test_without_pil_is_missing_dependency(self):
        data = png_bytes(20, 20, noise=1)
        err = IngestError("missing_dependency", "pip install pillow")
        with mock.patch.object(imgmod.optional, "load", side_effect=err):
            self.assertEqual(self.code("big.png", data, max_image_bytes=10),
                             "missing_dependency")

    def test_small_image_never_needs_pil(self):
        with mock.patch.object(imgmod.optional, "load", side_effect=AssertionError):
            doc = self.ingest("s.png", png_bytes())
        self.assertEqual(len(doc["assets"]), 1)


class Rec(object):
    def __init__(self, out=None):
        self.calls = []
        self.out = out or json.dumps({"result": "ok", "total_cost_usd": 0.0})

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        return subprocess.CompletedProcess(argv, 0, self.out, "")


class TestClaudeImages(unittest.TestCase):
    def call(self, images, rec=None, **kw):
        rec = rec or Rec()
        res = claude.run_claude_images("Solve it.", images, model="m", timeout_s=5, runner=rec,
                                       cwd="/empty", **kw)
        return res, rec

    def test_stdin_json_line_argv_cwd(self):
        raw = png_bytes()
        res, rec = self.call([("image/png", raw)])
        self.assertTrue(res.ok)
        argv, kw = rec.calls[0]
        self.assertIn("stream-json", argv)
        self.assertEqual(argv[argv.index("--input-format") + 1], "stream-json")
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertEqual(kw["cwd"], "/empty")
        self.assertFalse(kw["shell"])
        self.assertEqual(kw["input"].count("\n"), 1)
        self.assertTrue(kw["input"].endswith("\n"))
        msg = json.loads(kw["input"])
        self.assertEqual(msg["type"], "user")
        content = msg["message"]["content"]
        self.assertEqual(content[0]["type"], "image")
        self.assertEqual(content[0]["source"]["media_type"], "image/png")
        self.assertEqual(base64.b64decode(content[0]["source"]["data"]), raw)
        self.assertEqual(content[-1], {"type": "text", "text": "Solve it."})
        self.assertEqual(sorted(content[0]["source"]), ["data", "media_type", "type"])

    def test_run_claude_unchanged(self):
        rec = Rec()
        claude.run_claude("hi", model="m", timeout_s=5, runner=rec)
        argv, kw = rec.calls[0]
        self.assertNotIn("--input-format", argv)
        self.assertEqual(kw["input"], "hi")

    def test_validation_no_call(self):
        for imgs in ([("image/gif", b"x")], [("image/png", b"")], [],
                     [("image/png", b"x" * (claude.MAX_IMAGE_BYTES + 1))]):
            res, rec = self.call(imgs)
            self.assertFalse(res.ok)
            self.assertEqual(rec.calls, [])
        res, _ = self.call([("image/gif", b"x")])
        self.assertIn("unsupported media type", res.reason)


if __name__ == "__main__":
    unittest.main()

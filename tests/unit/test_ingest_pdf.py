"""Phase 13 (REQ-0017): PDF adapter, optional-lib loader, segmenter, ingest flags. $0, no network."""
import contextlib
import glob
import hashlib
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
from exam_engine.ingest import api, optional, segment  # noqa: E402
from exam_engine.ingest.adapters import pdf as pdfmod  # noqa: E402
from exam_engine.ingest.schema import IngestError, validate_document  # noqa: E402

try:
    fitz = optional.load("fitz", "pymupdf")
except IngestError:
    fitz = None
FONTS = glob.glob("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
_dir, _lang, _have = pdfmod.pick_ocr_language({})

QTEXT = ["Câu 1. What is two plus two?", "A. three", "B. four", "C. five", "D. six",
         "Câu 2. Pick the colour of grass.", "A. green", "B. red"]


def slurp(path, mode="rb"):
    with open(path, mode) as fh:
        return fh.read()


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(["ingest"] + args)
    return code, out.getvalue(), err.getvalue()


@unittest.skipIf(fitz is None, "PyMuPDF (fitz) not installed")
class PdfBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        self.assets = os.path.join(self.dir, "assets")

    def save(self, doc, name="t.pdf", **kw):
        path = os.path.join(self.dir, name)
        doc.save(path, **kw)
        doc.close()
        return path

    def lines_doc(self, lines, font=None, size=12):
        doc = fitz.open()
        page = doc.new_page()
        y = 72
        for ln in lines:
            if font:
                page.insert_text((72, y), ln, fontsize=size, fontname="dj", fontfile=font)
            else:
                page.insert_text((72, y), ln, fontsize=size)
            y += 18
        return doc

    def ingest(self, path, **cfg):
        cfg.setdefault("asset_dir", self.assets)
        return api.ingest_document(path, config=cfg)


class TestNative(PdfBase):
    def test_digital_pdf_valid_and_hash(self):
        path = self.save(self.lines_doc(QTEXT))
        before = hashlib.sha256(slurp(path)).hexdigest()
        doc = self.ingest(path)
        self.assertEqual(validate_document(doc), [])
        self.assertEqual(doc["status"], "native_text")
        self.assertEqual(doc["source"]["sha256"], before)
        self.assertEqual(hashlib.sha256(slurp(path)).hexdigest(), before)
        self.assertEqual([q["n"] for q in doc["questions"]], [1, 2])
        self.assertEqual(doc["questions"][0]["options"][1]["text"], "four")
        self.assertEqual(doc["pages"][0]["blocks"][0]["origin"], "extracted")
        self.assertNotIn("/", doc["source"]["path"])

    @unittest.skipUnless(FONTS, "no DejaVu TTF with diacritics")
    def test_vietnamese_unicode_kept(self):
        text = "Câu 1. Tính giá trị của biểu thức ắ ữ ơ đ"
        doc = self.ingest(self.save(self.lines_doc([text, "A. một", "B. hai"], FONTS[0])))
        joined = "\n".join(b["text"] for b in doc["pages"][0]["blocks"])
        self.assertIn("Tính giá trị của biểu thức ắ ữ ơ đ", joined)
        self.assertEqual(doc["status"], "native_text")

    def test_two_columns_read_left_then_right(self):
        d = fitz.open()
        p = d.new_page()
        for i in range(3):
            p.insert_text((50, 100 + i * 100), "LEFT%d some words here" % i, fontsize=11)
            p.insert_text((330, 100 + i * 100), "RIGHT%d some words here" % i, fontsize=11)
        doc = self.ingest(self.save(d))
        texts = [b["text"] for b in doc["pages"][0]["blocks"]]
        order = [t.split()[0] for t in texts]
        self.assertEqual(order, ["LEFT0", "LEFT1", "LEFT2", "RIGHT0", "RIGHT1", "RIGHT2"])

    def test_table_block_and_no_repeat(self):
        d = fitz.open()
        p = d.new_page()
        x0, y0, cw, rh = 72, 100, 100, 30
        for r in range(4):
            p.draw_line((x0, y0 + r * rh), (x0 + 3 * cw, y0 + r * rh))
        for c in range(4):
            p.draw_line((x0 + c * cw, y0), (x0 + c * cw, y0 + 3 * rh))
        for r in range(3):
            for c in range(3):
                p.insert_text((x0 + c * cw + 8, y0 + r * rh + 20), "cell%d%d" % (r, c))
        p.insert_text((72, 300), "A paragraph after the table with enough text.")
        doc = self.ingest(self.save(d))
        blocks = doc["pages"][0]["blocks"]
        tabs = [b for b in blocks if b["type"] == "table"]
        self.assertEqual(len(tabs), 1)
        self.assertEqual(tabs[0]["rows"][1][2], "cell12")
        paras = " ".join(b["text"] for b in blocks if b["type"] == "paragraph")
        self.assertNotIn("cell00", paras)
        self.assertIn("after the table", paras)

    def test_image_and_vector_diagram_crops(self):
        d = fitz.open()
        p = d.new_page()
        p.insert_text((72, 80), "Figure question about a picture and a diagram here.")
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 60), False)
        pix.set_rect(pix.irect, (200, 30, 30))
        p.insert_image(fitz.Rect(72, 100, 172, 200), pixmap=pix)
        p.draw_rect(fitz.Rect(250, 300, 400, 400))
        p.draw_circle((325, 350), 40)
        p.draw_line((250, 300), (400, 400))
        doc = self.ingest(self.save(d))
        self.assertEqual(validate_document(doc), [])
        self.assertEqual(len(doc["assets"]), 2)
        for a in doc["assets"]:
            self.assertTrue(os.path.isfile(os.path.join(self.assets, os.path.basename(a["path"]))))
            self.assertEqual(a["mime"], "image/png")
        self.assertEqual(len([b for b in doc["pages"][0]["blocks"] if b["type"] == "image"]), 2)

    def test_math_font_page_image_and_warning(self):
        d = fitz.open()
        p = d.new_page()
        p.insert_text((72, 100), "The integral sign and alpha follow here: abcdefg", fontsize=12)
        p.insert_text((72, 140), "abc", fontsize=12, fontname="symb")
        doc = self.ingest(self.save(d))
        self.assertIn("math_possible", [w["code"] for w in doc["warnings"]])
        self.assertEqual(len(doc["assets"]), 1)

    def test_no_numbering_warning(self):
        doc = self.ingest(self.save(self.lines_doc(["Just some prose without any numbers."])))
        codes = [w["code"] for w in doc["warnings"]]
        self.assertIn("no_question_numbering", codes)
        self.assertNotIn("questions", doc)

    def test_ocr_off_flags_page_needs_review(self):
        d = fitz.open()
        d.new_page().insert_text((72, 100), "short")
        doc = self.ingest(self.save(d), ocr="off")
        self.assertEqual(doc["status"], "needs_review")
        self.assertIn("missing_text", [w["code"] for w in doc["warnings"]])
        self.assertEqual(doc["pages"][0]["method"], "native")


class TestFailures(PdfBase):
    def test_encrypted(self):
        d = self.lines_doc(QTEXT)
        path = self.save(d, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")
        with self.assertRaises(IngestError) as cm:
            self.ingest(path)
        self.assertEqual(cm.exception.code, "encrypted")

    def test_corrupt(self):
        path = os.path.join(self.dir, "bad.pdf")
        with open(path, "wb") as fh:
            fh.write(b"this is not a pdf at all, just bytes " * 5)
        with self.assertRaises(IngestError) as cm:
            self.ingest(path)
        self.assertEqual(cm.exception.code, "corrupt")

    def test_empty_blank_page_and_zero_bytes(self):
        d = fitz.open()
        d.new_page()
        with self.assertRaises(IngestError) as cm:
            self.ingest(self.save(d))
        self.assertEqual(cm.exception.code, "empty")
        zero = os.path.join(self.dir, "zero.pdf")
        open(zero, "wb").close()
        with self.assertRaises(IngestError) as cm:
            self.ingest(zero)
        self.assertEqual(cm.exception.code, "empty")


def _scanned(case, text_lines, size=28):
    src = fitz.open()
    p = src.new_page()
    y = 100
    for ln in text_lines:
        p.insert_text((72, y), ln, fontsize=size)
        y += 50
    pix = p.get_pixmap(dpi=200)
    src.close()
    d = fitz.open()
    q = d.new_page()
    q.insert_image(q.rect, pixmap=pix)
    return d


class TestOcr(PdfBase):
    @unittest.skipUnless("eng" in _have, "tesseract eng data not found")
    def test_scanned_english_page_ocr(self):
        path = self.save(_scanned(self, ["Question 1. What is the capital", "of France today"]))
        doc = self.ingest(path)
        self.assertEqual(doc["status"], "ocr")
        blk = doc["pages"][0]["blocks"][0]
        self.assertEqual(blk["method"], "ocr")
        self.assertEqual(blk["origin"], "extracted")
        self.assertIn("capital", " ".join(b["text"] for b in doc["pages"][0]["blocks"]))
        if "vie" not in _have:
            self.assertIn("ocr_language_missing", [w["code"] for w in doc["warnings"]])

    @unittest.skipUnless("eng" in _have, "tesseract eng data not found")
    def test_good_native_page_is_not_ocred(self):
        doc = self.ingest(self.save(self.lines_doc(QTEXT)))
        self.assertEqual(doc["pages"][0]["method"], "native")
        self.assertTrue(all("method" not in b for b in doc["pages"][0]["blocks"]))

    @unittest.skipUnless("vie" in _have and "eng" in _have, "tesseract vie data not installed")
    def test_vietnamese_ocr(self):
        self.assertEqual(pdfmod.pick_ocr_language({})[1], "vie+eng")

    def test_no_language_gives_needs_review_not_exception(self):
        d = _scanned(self, ["Question 1. What is the capital of France"]) if fitz else None
        empty = os.path.join(self.dir, "emptytess")
        os.makedirs(empty)
        orig = pdfmod.TESSDATA_DIRS, os.environ.pop("TESSDATA_PREFIX", None)
        pdfmod.TESSDATA_DIRS = []
        try:
            doc = self.ingest(self.save(d), tessdata=empty)
        finally:
            pdfmod.TESSDATA_DIRS = orig[0]
            if orig[1] is not None:
                os.environ["TESSDATA_PREFIX"] = orig[1]
        self.assertEqual(doc["status"], "needs_review")
        self.assertIn("ocr_unavailable", [w["code"] for w in doc["warnings"]
                                          + doc["pages"][0]["warnings"]])


class TestLoader(unittest.TestCase):
    def test_missing_gives_missing_dependency(self):
        with self.assertRaises(IngestError) as cm:
            optional.load("no_such_mod_xyz", "somepkg")
        self.assertEqual(cm.exception.code, "missing_dependency")
        self.assertIn("pip install somepkg", cm.exception.message)

    def test_fake_user_site_appended_at_end(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "fake_opt_mod_q.py"), "w") as fh:
                fh.write("VALUE = 7\n")
            real = optional.site.getusersitepackages
            optional.site.getusersitepackages = lambda: td
            saved = list(sys.path)
            try:
                mod = optional.load("fake_opt_mod_q", "fakepkg")
                self.assertEqual(mod.VALUE, 7)
                self.assertEqual(sys.path[-1], td)
                self.assertNotIn("", sys.path[-1:])
            finally:
                optional.site.getusersitepackages = real
                sys.path[:] = saved
                sys.modules.pop("fake_opt_mod_q", None)


class TestSegment(unittest.TestCase):
    def test_consecutive_with_options_and_intro(self):
        intro, qs, ok = segment.segment(["Read carefully.", "Câu 1. First?", "A. x", "B) y",
                                         "continued", "2. Second?", "Question 3: Third?"])
        self.assertTrue(ok)
        self.assertEqual(intro, ["Read carefully."])
        self.assertEqual([q["n"] for q in qs], [1, 2, 3])
        self.assertEqual(qs[0]["options"][1]["text"], "y continued")

    def test_gap_or_empty_question_not_ok(self):
        self.assertFalse(segment.segment(["1. a", "3. c"])[2])
        self.assertFalse(segment.segment(["1. a", "2."])[2])
        self.assertFalse(segment.segment(["no numbers"])[2])


class TestCli(PdfBase):
    def test_check_smoke(self):
        code, out, _ = run_cli(["--check"])
        self.assertEqual(code, 0)
        for key in ("fitz:", "docx:", "PIL:", "tesseract:", "user site:"):
            self.assertIn(key, out)

    def test_flags_and_exam_out(self):
        path = self.save(self.lines_doc(QTEXT))
        outj = os.path.join(self.dir, "o.json")
        exam = os.path.join(self.dir, "e.md")
        meta = ["--meta", "Subject=S", "--meta", "Level=L", "--meta", "Exam type=E",
                "--meta", "Task=T", "--meta", "Mode=M"]
        code, _, err = run_cli([path, "--out", outj, "--assets", self.assets, "--ocr", "off",
                                "--exam-out", exam] + meta)
        self.assertEqual(code, 0, err)
        self.assertIn("Question 2", slurp(exam, "r"))
        self.assertEqual(json.loads(slurp(outj, "r"))["extraction"]["ocr"], "off")

    def test_no_questions_error_keeps_saved_doc(self):
        path = self.save(self.lines_doc(["Plain prose line number one here."]))
        outj = os.path.join(self.dir, "o.json")
        meta = ["--meta", "Subject=S", "--meta", "Level=L", "--meta", "Exam type=E",
                "--meta", "Task=T", "--meta", "Mode=M"]
        code, _, err = run_cli([path, "--out", outj, "--exam-out",
                                os.path.join(self.dir, "e.md")] + meta)
        self.assertEqual(code, 2)
        self.assertIn("no_questions", err)
        self.assertTrue(os.path.isfile(outj))


if __name__ == "__main__":
    unittest.main()

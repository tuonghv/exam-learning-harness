"""Phase 36 (REQ-0039): gold -> PDF -> ingest text route -> extract-eval. $0, no network."""
import contextlib
import copy
import glob
import io
import json
import os
import sys
import tempfile
import unicodedata
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.ingest import api, optional  # noqa: E402
from exam_engine.ingest.schema import IngestError  # noqa: E402
from exam_engine.pipeline import extract_eval, gold_pdf  # noqa: E402

try:
    fitz = optional.load("fitz", "pymupdf")
except IngestError:
    fitz = None
FONTS = glob.glob("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
GOLD = os.path.join(ROOT, "evals", "extract", "gold", "synthetic-001.json")
READY = fitz is not None and bool(FONTS)


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(args)
    return code, out.getvalue(), err.getvalue()


@unittest.skipUnless(READY, "PyMuPDF (fitz) or DejaVu TTF missing")
class GoldPdf(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def render(self, variant="text", gold=GOLD, name="g.pdf"):
        out = os.path.join(self.dir, name)
        return out, gold_pdf.render(gold, out, variant)

    def roundtrip(self, variant="text", gold=GOLD):
        pdf, info = self.render(variant, gold)
        doc = api.ingest_document(pdf, config={"asset_dir": os.path.join(self.dir, "a"), "ocr": "off"})
        path = os.path.join(self.dir, "doc.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        sm = extract_eval.evaluate(extract_eval.load_questions(GOLD), extract_eval.load_questions(path))
        return pdf, doc, sm

    def pages_text(self, pdf):
        d = fitz.open(pdf)
        try:
            return [unicodedata.normalize("NFC", p.get_text()) for p in d]
        finally:
            d.close()

    def test_render_text_pages_and_figures(self):
        pdf, info = self.render()
        self.assertEqual(info["pages"], 4)
        self.assertEqual(info["placed"][6], 1)
        self.assertEqual({k: v for k, v in info["placed"].items() if k in (6, 12, 13, 15)},
                         {6: 1, 12: 2, 13: 3, 15: 4})
        d = fitz.open(pdf)
        self.assertEqual(d.page_count, 4)
        for p in d:
            self.assertTrue(p.get_drawings())
        d.close()

    def test_diacritics_preserved(self):
        pdf, _ = self.render()
        d = fitz.open(pdf)
        try:
            raw = "".join(p.get_text() for p in d)
        finally:
            d.close()
        # 36.1 the text layer itself is NFC (no normalising here: an NFD renderer must fail)
        self.assertEqual(raw, unicodedata.normalize("NFC", raw))
        text = " ".join(self.pages_text(pdf)).replace("\n", " ")
        for s in ("Tính giá trị của biểu thức dưới đây.", "Sĩ số", "Bằng nhau",
                  "Hãy nêu ý nghĩa của định luật bảo toàn năng lượng."):
            self.assertIn(s, text)

    def test_e2e_text_route(self):
        _, doc, sm = self.roundtrip()
        self.assertEqual([q["n"] for q in doc["questions"]], list(range(1, 21)))
        self.assertNotIn("segmentation_skipped", json.dumps(doc.get("warnings", [])))
        self.assertEqual(sm["overall"]["k"], 8)
        self.assertEqual(sm["overall"]["n"], 20)
        self.assertEqual(sm["fields"]["text"]["k"], 10)
        self.assertEqual(sm["fields"]["options"]["k"], 20)
        self.assertEqual(sm["missing"], [])
        self.assertEqual(sm["extra"], [])

    def test_e2e_formula_image(self):
        pdf, doc, sm = self.roundtrip("formula-image")
        self.assertEqual(sm["fields"]["text"]["k"], 20)
        self.assertEqual(sm["fields"]["options"]["k"], 20)
        self.assertEqual(sm["overall"]["k"], 8)
        self.assertNotIn("\\frac{1}{2}+\\frac{1}{3}", " ".join(self.pages_text(pdf)))
        d = fitz.open(pdf)
        self.assertTrue(d[0].get_image_info())
        d.close()

    def test_bite_pdf_is_really_read(self):
        with open(GOLD, encoding="utf-8") as fh:
            g = json.load(fh)
        g = copy.deepcopy(g)
        by = {str(q["id"]): q for q in g["questions"]}
        self.assertIn("Sun", by["9"]["text"])
        by["9"]["text"] = by["9"]["text"].replace("Sun", "Moon")
        by["17"]["options"]["A"] = by["17"]["options"]["A"] + " zzz"
        alt = os.path.join(self.dir, "alt.json")
        with open(alt, "w", encoding="utf-8") as fh:
            json.dump(g, fh, ensure_ascii=False)
        _, _, sm = self.roundtrip(gold=alt)
        self.assertEqual(sm["overall"]["k"], 6)

    def test_errors(self):
        with open(GOLD, encoding="utf-8") as fh:
            g = json.load(fh)
        by = {str(q["id"]): q for q in g["questions"]}
        out = os.path.join(self.dir, "e.pdf")

        def dump(name):
            p = os.path.join(self.dir, name)
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(g, fh, ensure_ascii=False)
            return p
        by["20"]["figures"] = [1]  # cannot reach page 1
        with self.assertRaisesRegex(ValueError, "20"):
            gold_pdf.render(dump("a.json"), out)
        by["20"]["figures"] = []
        by["3"]["text"] = "x" * 400
        with self.assertRaisesRegex(ValueError, "3"):
            gold_pdf.render(dump("b.json"), out)
        with self.assertRaisesRegex(ValueError, "font"):
            gold_pdf.render(GOLD, out, font="/nonexistent/f.ttf")
        with self.assertRaisesRegex(ValueError, "variant"):
            gold_pdf.render(GOLD, out, variant="bad")

    def test_cli(self):
        out = os.path.join(self.dir, "c.pdf")
        code, so, _ = run_cli(["gold-pdf", GOLD, out])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(out))
        self.assertIn("pages=4", so)
        self.assertEqual(run_cli(["gold-pdf", GOLD, out, "--variant", "bad"])[0], 2)
        code, _, err = run_cli(["gold-pdf", os.path.join(self.dir, "nope.json"), out])
        self.assertEqual(code, 2)
        self.assertIn("ERROR: gold-pdf:", err)
        code, _, err = run_cli(["gold-pdf", GOLD, "/nonexistent-dir/x.pdf"])
        self.assertEqual(code, 2)
        self.assertIn("ERROR: gold-pdf:", err)


if __name__ == "__main__":
    unittest.main()

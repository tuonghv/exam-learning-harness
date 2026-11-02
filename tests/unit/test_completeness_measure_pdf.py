"""Phase 46 (REQ-0050): fixture families F1-F8 -> PDF (split layout) -> ingest -> completeness rates.

Synthetic text only, $0, no network. The vision path replays oracle replies built from the rendered
pages (tests the continuation bridge and the completeness gate, not vision accuracy).
"""
import contextlib
import glob
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.ingest import api, optional, refine  # noqa: E402
from exam_engine.ingest.schema import IngestError  # noqa: E402
from exam_engine.pipeline import extract_eval as ee, gold_pdf  # noqa: E402

try:
    fitz = optional.load("fitz", "pymupdf")
except IngestError:
    fitz = None
READY = fitz is not None and bool(glob.glob("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
GOLD = os.path.join(ROOT, "evals", "extract", "gold", "synthetic-001.json")
spec = importlib.util.spec_from_file_location("gen_families", os.path.join(ROOT, "evals", "extract", "gen_families.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

TAGS = {"F1": "b", "F2": "a", "F3": "c", "F4": "d", "F5": "e", "F6": "f", "F7": "g", "F8": "h"}
CROSS = {"F1": 0, "F2": 8, "F3": 8, "F4": 6, "F5": 8, "F6": 0, "F7": 8, "F8": 8}  # counted by hand from the layout


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(args)
    return code, out.getvalue(), err.getvalue()


def page_texts(pdf):
    d = fitz.open(pdf)
    try:
        return [p.get_text() for p in d]
    finally:
        d.close()


def pages_of(texts, tag, qid):
    """Independent oracle: pages holding a line of question qid (unique markers), read from the PDF text."""
    pat = re.compile(r"\(%s%d\.\d+\)|phương án %s%d[a-d]\b" % (tag, qid, tag, qid))
    return [i + 1 for i, t in enumerate(texts) if pat.search(t)]


@unittest.skipUnless(READY, "PyMuPDF (fitz) or DejaVu TTF missing")
class Families(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = cls._tmp.name
        meta = gen.write_all(os.path.join(cls.dir, "fx"))
        cls.fam = {}
        for name, m in sorted(meta.items()):
            pdf = os.path.join(cls.dir, name + ".pdf")
            gold = os.path.join(cls.dir, name + ".gold.json")
            info = gold_pdf.render(m["gold"], pdf, layout=m["layout"], furniture=m["furniture"], gold_out=gold)
            cls.fam[name] = {"pdf": pdf, "gold": gold, "info": info, "src": m["gold"]}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def texts(self, name):
        return page_texts(self.fam[name]["pdf"])

    def gold(self, name):
        with open(self.fam[name]["gold"], encoding="utf-8") as fh:
            return json.load(fh)["questions"]

    def test_25_questions_each_and_pages_match_the_pdf_text(self):
        for name in self.fam:
            qs = self.gold(name)
            self.assertEqual(len(qs), 25, name)
            texts = self.texts(name)
            for q in qs:
                got = pages_of(texts, TAGS[name], int(q["id"]))
                self.assertEqual(q["pages"], sorted(set(got) | set(q["figures"])), (name, q["id"]))

    def test_cross_page_counts(self):
        for name, n in CROSS.items():
            self.assertEqual(sum(1 for q in self.gold(name) if len(q["pages"]) > 1), n, name)

    def test_f3_options_start_on_the_page_after_the_stem(self):
        texts = self.texts("F3")
        for q in self.gold("F3"):
            if len(q["pages"]) > 1:
                qid, p = int(q["id"]), q["pages"]
                stem = [i + 1 for i, t in enumerate(texts) if "(c%d.2)" % qid in t]
                opts = [i + 1 for i, t in enumerate(texts) if "phương án c%da" % qid in t]
                self.assertEqual((stem, opts), ([p[0]], [p[1]]), qid)

    def test_f2_stem_is_cut_inside(self):
        texts = self.texts("F2")
        for q in self.gold("F2"):
            if len(q["pages"]) > 1:
                qid = int(q["id"])
                first = [i + 1 for i, t in enumerate(texts) if "(a%d.1)" % qid in t]
                last = [i + 1 for i, t in enumerate(texts) if "(a%d.6)" % qid in t]
                self.assertEqual((first, last), ([q["pages"][0]], [q["pages"][1]]))

    def test_f7_formula_is_cut_between_its_lines(self):
        texts = self.texts("F7")
        a = [i + 1 for i, t in enumerate(texts) if "x^{2}+3x" in t]
        b = [i + 1 for i, t in enumerate(texts) if "=7+y_{1}" in t]
        cut = [q for q in self.gold("F7") if len(q["pages"]) > 1]
        self.assertEqual(len(a), 8)
        self.assertEqual(sorted(set(b) - set(a)), sorted(set(b)))
        self.assertTrue(all(y == x + 1 for x, y in zip(a, b)))
        self.assertEqual(len(cut), 8)

    def test_f4_passage_spans_three_pages(self):
        spans = [len(q["pages"]) for q in self.gold("F4") if q["id"] in ("1", "5", "9")]
        self.assertEqual(spans, [3, 3, 3])

    def test_f5_figure_is_on_the_page_after_the_text(self):
        for q in self.gold("F5"):
            if q["figures"]:
                self.assertEqual(q["figures"], [q["pages"][-1]])
                self.assertEqual(len(q["pages"]), 2)

    def test_f8_furniture_on_every_page(self):
        texts = self.texts("F8")
        for i, t in enumerate(texts, 1):
            self.assertIn("Trang %d" % i, t)
            self.assertIn("Mã đề 101", t)
        self.assertNotIn("Mã đề", "".join(self.texts("F2")))

    def chain_text(self, name):
        doc = api.ingest_document(self.fam[name]["pdf"], config={"asset_dir": os.path.join(self.dir, "a" + name),
                                                                  "ocr": "off"})
        return self.rates(name, doc)

    def rates(self, name, doc, refined=False):
        path = os.path.join(self.dir, name + ".doc.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        raws = {}
        ext = ee.load_refined(path, raws) if refined else ee.load_questions(path, raws)
        return ee.completeness(ee.load_questions(self.fam[name]["gold"]), ext, raws)

    def test_chain_text_route_all_families(self):
        for name in self.fam:
            cm = self.chain_text(name)
            self.assertEqual(cm["n"], 25, name)
            self.assertEqual((cm["boundary"]["k"], cm["boundary"]["n"]), (25, 25), name)
            self.assertEqual((cm["cross_page"]["k"], cm["cross_page"]["n"]), (CROSS[name],) * 2, name)
            self.assertEqual(cm["false_merge"]["k"], 0, name)
            self.assertEqual(cm["incomplete_to_solver"]["k"], 0, name)
            self.assertFalse(cm["fail"], name)
        # the text route cannot see the figure stand-in, so the gate declines those 8 (right questions, marked)
        self.assertEqual(self.chain_text("F5")["false_alarm"]["k"], 8)
        self.assertEqual(self.chain_text("F2")["false_alarm"]["k"], 0)

    def vision(self, name, refined_pdf=None):
        scan = os.path.join(self.dir, name + ".scan.pdf")
        gold_pdf.scan_pdf(self.fam[name]["pdf"], scan)
        self.assertEqual("".join(page_texts(scan)).strip(), "")
        doc = api.ingest_document(scan, config={"asset_dir": os.path.join(self.dir, "s" + name), "ocr": "off"})
        replies = gold_pdf.vision_replies(self.fam[name]["info"])
        rp = os.path.join(self.dir, name + ".replies.json")
        with open(rp, "w", encoding="utf-8") as fh:
            json.dump(replies, fh, ensure_ascii=False)
        out = refine.refine(doc, "1-%d" % len(replies), refine.mock_llm(rp), all_pages=True, window=False)
        return out, replies

    def test_chain_vision_mock_replies_all_families(self):
        for name in self.fam:
            out, replies = self.vision(name)
            cm = self.rates(name, out, refined=True)
            self.assertEqual(out["refined"]["calls"], len(replies), name)
            self.assertEqual((cm["boundary"]["k"], cm["boundary"]["n"]), (25, 25), name)
            self.assertEqual((cm["cross_page"]["k"], cm["cross_page"]["n"]), (CROSS[name],) * 2, name)
            self.assertEqual(cm["incomplete_to_solver"]["k"], 0, name)
            self.assertEqual(cm["false_merge"]["k"], 0, name)

    def test_bite_dropped_continuation_lowers_cross_page_and_is_marked(self):
        out, replies = self.vision("F3")
        broken = []
        for r in replies:
            obj = json.loads(r)
            obj.pop("continues", None)  # the model forgot the remainder at the top of the next page
            broken.append(json.dumps(obj, ensure_ascii=False))
        rp = os.path.join(self.dir, "broken.json")
        with open(rp, "w", encoding="utf-8") as fh:
            json.dump(broken, fh)
        doc = api.ingest_document(os.path.join(self.dir, "F3.scan.pdf"), config={"ocr": "off", "asset_dir": self.dir})
        out = refine.refine(doc, "1-%d" % len(broken), refine.mock_llm(rp), all_pages=True, window=False)
        cm = self.rates("F3", out, refined=True)
        self.assertEqual(cm["cross_page"]["k"], 0)
        self.assertEqual(cm["missing_detection"]["n"], 8)
        self.assertFalse(cm["fail"], "every cut question must be marked, never reach the solver")

    @unittest.skipUnless(shutil.which("tesseract"), "tesseract missing")
    def test_chain_ocr_runs_on_a_scanned_family(self):
        scan = os.path.join(self.dir, "F6.scan.pdf")
        gold_pdf.scan_pdf(self.fam["F6"]["pdf"], scan)
        doc = api.ingest_document(scan, config={"asset_dir": os.path.join(self.dir, "ocr"), "ocr": "on"})
        cm = self.rates("F6", doc)
        self.assertEqual(cm["n"], 25)
        self.assertIn("incomplete_to_solver", cm)


@unittest.skipUnless(READY, "PyMuPDF (fitz) or DejaVu TTF missing")
class SplitLayout(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def big_gold(self):
        q = {"id": "1", "text": "\n".join("dòng %d của đoạn rất dài" % i for i in range(70)), "formula": "",
             "options": dict((k, "ý %s" % k) for k in "ABCD"), "figures": []}
        path = os.path.join(self.dir, "big.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"questions": [q]}, fh, ensure_ascii=False)
        return path

    def test_block_refuses_what_split_crosses(self):
        gold, pdf = self.big_gold(), os.path.join(self.dir, "b.pdf")
        with self.assertRaises(ValueError):
            gold_pdf.render(gold, pdf)
        info = gold_pdf.render(gold, pdf, layout="split")
        self.assertEqual(info["pages_of"][1], [1, 2])

    def test_default_layout_text_layer_unchanged(self):
        pdf = os.path.join(self.dir, "d.pdf")
        gold_pdf.render(GOLD, pdf)
        d = fitz.open(pdf)
        words = [p.get_text("words") for p in d]
        d.close()
        with open(os.path.join(HERE, "fixtures", "gold_pdf_base_words.json"), encoding="utf-8") as fh:
            base = json.load(fh)
        self.assertEqual(json.loads(json.dumps(words)), base)

    def test_gold_out_carries_pages_and_old_gold_still_loads(self):
        out = os.path.join(self.dir, "g.json")
        info = gold_pdf.render(GOLD, os.path.join(self.dir, "d.pdf"), gold_out=out)
        g = ee.load_questions(out)
        self.assertEqual(dict((int(k), v["pages"]) for k, v in g.items()), info["pages_of"])
        self.assertEqual(ee.evaluate(g, g)["overall"]["k"], 20)

    def test_bad_layout(self):
        with self.assertRaises(ValueError):
            gold_pdf.render(GOLD, os.path.join(self.dir, "x.pdf"), layout="wide")

    def test_cli_flags(self):
        d = self.dir
        code, out, err = run_cli(["gold-pdf", self.big_gold(), os.path.join(d, "s.pdf"), "--layout", "split",
                                  "--gold-out", os.path.join(d, "g.json"), "--replies", os.path.join(d, "r.json"),
                                  "--scan"])
        self.assertEqual(code, 0, err)
        self.assertEqual("".join(page_texts(os.path.join(d, "s.pdf"))).strip(), "")
        with open(os.path.join(d, "r.json"), encoding="utf-8") as fh:
            replies = json.load(fh)
        self.assertEqual(len(replies), 2)
        self.assertTrue(json.loads(replies[0])["questions"][0]["cut"])
        self.assertIn("continues", json.loads(replies[1]))
        self.assertEqual(run_cli(["gold-pdf", GOLD, os.path.join(d, "x.pdf"), "--layout", "wide"])[0], 2)


if __name__ == "__main__":
    unittest.main()

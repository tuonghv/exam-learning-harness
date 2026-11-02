"""47.x golden: `ingest` output of the existing PDFs vs baseline commit 2cc9808 (git archive of src).
Without a cut boundary the files are byte-identical; where the detector fires, the only
difference is added info warnings `page_cut_suspect` (REQ-0051 AC4)."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BASE = "2cc9808"
PDFS = ["examples/dgnl/De-thi-minh-hoa-2026-Final.pdf", "input/exam/math/math_12_graduation_2026_001.pdf"]
RUN = ("import sys; sys.path.insert(0, sys.argv[1] + '/src'); from exam_engine import cli; "
       "sys.exit(cli.main(['ingest', sys.argv[2], '--out', sys.argv[3]]))")


def run_ingest(tree, pdf, out):
    r = subprocess.run([sys.executable, "-I", "-c", RUN, tree, os.path.join(ROOT, pdf), out],
                       capture_output=True, text=True, cwd=tree)
    return r.returncode


class TestIngestGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        arc = subprocess.run(["git", "archive", BASE, "src", "config", "schemas", "prompts"], cwd=ROOT, capture_output=True)
        if arc.returncode:
            raise unittest.SkipTest("baseline %s absent" % BASE)
        cls.base = os.path.join(cls.tmp, "base")
        os.mkdir(cls.base)
        subprocess.run(["tar", "-x", "-C", cls.base], input=arc.stdout, check=True)

    def test_existing_pdfs_unchanged_but_cut_warnings(self):
        for pdf in PDFS:
            if not os.path.isfile(os.path.join(ROOT, pdf)):
                continue
            a, b = os.path.join(self.tmp, "a.json"), os.path.join(self.tmp, "b.json")
            self.assertEqual(run_ingest(self.base, pdf, a), run_ingest(ROOT, pdf, b), pdf)
            da, db = json.load(open(a, encoding="utf-8")), json.load(open(b, encoding="utf-8"))
            new = [w for w in db["warnings"] if w["code"] == "page_cut_suspect"]
            db["warnings"] = [w for w in db["warnings"] if w["code"] != "page_cut_suspect"]
            if '"method": "ocr"' in open(a, encoding="utf-8").read():
                # OCR source: 51.1 re-spaces glued words (intended); text is the same up to whitespace
                # and the new run has at least as many word breaks (fewer glued tokens).
                ta, tb = json.dumps(da, ensure_ascii=False), json.dumps(db, ensure_ascii=False)
                self.assertEqual(re.sub(r"\s+|\\n|\"chars\": \d+", "", ta), re.sub(r"\s+|\\n|\"chars\": \d+", "", tb), pdf)
                self.assertGreaterEqual(len(tb.split()), len(ta.split()), pdf)
                continue
            self.assertEqual(da, db, pdf)
            if not new:  # no cut detected: the file is byte-identical
                self.assertEqual(open(a, "rb").read(), open(b, "rb").read(), pdf)
            self.assertTrue(all(w["level"] == "info" for w in new))


if __name__ == "__main__":
    unittest.main()

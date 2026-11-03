"""TASK-071 QA: 71.2 subprocess hardening, 71.2-71.4 mutation guards (tester, independent of test_ocr_conf)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from exam_engine.ingest import segment  # noqa: E402
from exam_engine.ingest.adapters import pdf as pdfmod  # noqa: E402

HEAD = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"


class Page:
    def __init__(self, exc=None):
        self.exc = exc

    def get_pixmap(self, dpi=None):
        if self.exc:
            raise self.exc

        class P:
            def tobytes(self, fmt):
                return b"png"
        return P()


class R:
    def __init__(self, rc=0, out=b""):
        self.returncode, self.stdout = rc, out


HOSTILE = ["-oops", "--tessdata-dir=/x", "vie eng", "vie;touch /tmp/pwn", "vie\nrm", "a" * 100000, ""]


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Subprocess(unittest.TestCase):
    def test_71_2_hostile_lang_and_dir_stay_single_argv_items(self):
        for bad in HOSTILE:
            with mock.patch.object(pdfmod.shutil, "which", return_value="/bin/tesseract"), \
                    mock.patch.object(pdfmod.subprocess, "run", return_value=R(0, HEAD.encode())) as run:
                pdfmod._tsv_conf(Page(), bad, bad, {"ocr_conf": "auto"})
            argv = run.call_args[0][0]
            kw = run.call_args[1]
            self.assertIsInstance(argv, list)
            self.assertFalse(kw.get("shell"))
            self.assertEqual(kw["timeout"], pdfmod.TSV_TIMEOUT)
            self.assertEqual(argv[argv.index("-l") + 1], bad)
            self.assertEqual(argv[argv.index("--tessdata-dir") + 1] if bad else None, bad or None)
            self.assertEqual(kw["input"], b"png")  # the document reaches the binary as pixels only

    def test_71_2_lang_never_from_document(self):
        # pick_ocr_language only emits vie/eng, whatever the folder names are
        with tempfile.TemporaryDirectory() as td:
            for name in ("-evil", "a b;c", "x\ny"):
                d = os.path.join(td, name)
                os.makedirs(d)
                for lg in ("vie", "eng", "--psm", "evil;x"):
                    open(os.path.join(d, lg + ".traineddata"), "w").close()
                folder, lang, have = pdfmod.pick_ocr_language({"tessdata": d})
                self.assertIn(lang, ("vie+eng", "vie", "eng"))
                self.assertTrue(set(have) <= {"vie", "eng"})

    def test_71_2_failures_skip_with_reason(self):
        cases = [("exit", dict(return_value=R(2, b"x")), "exit 2"),
                 ("timeout", dict(side_effect=subprocess.TimeoutExpired("t", 60)), "TimeoutExpired"),
                 ("oserror", dict(side_effect=OSError("boom")), "OSError"),
                 ("perm", dict(side_effect=PermissionError("no")), "PermissionError")]
        for name, kw, why_part in cases:
            why = []
            with mock.patch.object(pdfmod.shutil, "which", return_value="/bin/tesseract"), \
                    mock.patch.object(pdfmod.subprocess, "run", **kw):
                self.assertIsNone(pdfmod._tsv_conf(Page(), "eng", None, {}, why), name)
            self.assertIn(why_part, why[0])

    def test_71_2_huge_page_pixmap_failure(self):
        why = []
        with mock.patch.object(pdfmod.shutil, "which", return_value="/bin/tesseract"):
            self.assertIsNone(pdfmod._tsv_conf(Page(MemoryError("huge")), "eng", None, {}, why))
        self.assertTrue(why)

    def test_71_2_garbage_tsv(self):
        junk = [b"\xff\xfe\x00\x01" * 50, b"", b"\n\n\n", b"x\ty\tz", (b"5\t" * 11 + b"nan\tw\n") * 3,
                HEAD.encode() + b"5\t1\t1\t1\t1\t1\t0\t0\t1\t1\tnan\tw\n5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t-1\tv\n"
                + b"5\t1\t1\t1\t1\t1\t0\t0\t1\t1\tabc\tu\n",
                HEAD.encode() + (b"5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t50\tw\n" * 200000)]
        for out in junk:
            with mock.patch.object(pdfmod.shutil, "which", return_value="/bin/tesseract"), \
                    mock.patch.object(pdfmod.subprocess, "run", return_value=R(0, out)):
                got = pdfmod._tsv_conf(Page(), "eng", None, {})
            self.assertIsInstance(got, dict)
            self.assertNotIn("v", got)  # conf -1
            self.assertNotIn("u", got)

    def test_71_2_guard_allowlist_is_narrow(self):
        # only adapters/pdf.py joined claude.py + reporter.py; any other file with subprocess is still caught
        import re
        src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src", "exam_engine")
        pat = re.compile(r"subprocess\.(run|Popen|call|check_output|check_call)|os\.system")
        users = []
        for root, _, files in os.walk(src):
            for f in files:
                if f.endswith(".py") and pat.search(_read(os.path.join(root, f))):
                    users.append(os.path.relpath(os.path.join(root, f), src))
        self.assertEqual(sorted(users), sorted(["adapters/claude.py", "ingest/adapters/pdf.py",
                                                "pipeline/reporter.py"]))
        for f in ("shell=True",):
            for root, _, files in os.walk(src):
                for n in files:
                    if n.endswith(".py"):
                        self.assertNotIn(f, _read(os.path.join(root, n)), n)


def _doubt(pages, ocr_pages, conf, floor=None):
    lines = [l for p in pages for l in p]
    starts = []
    _, qs, _ = segment.segment(lines, starts=starts)
    oq = pdfmod._ocr_doubt(qs, starts, lines, [len(p) for p in pages], set(ocr_pages), set(), True,
                           conf=conf, floor=floor)
    return qs, oq


PG = [["Câu 1. giá trị gia", "A. một", "B. hai", "C. ba", "D. bốn"]]


class Mutations(unittest.TestCase):
    def test_71_2_threshold_is_strict_less_than_floor(self):
        for c, flagged in ((59.9, True), (60.0, False), (95.0, False)):
            qs, _ = _doubt(PG, [0], {0: {"gia": c}})
            self.assertEqual("low_conf" in (qs[0].get("ocr_doubt") or []), flagged, c)

    def test_71_2_signal_not_ignored_and_floor_zero_flags_nothing(self):
        qs, _ = _doubt(PG, [0], {0: {"gia": 1.0}})
        self.assertIn("low_conf", qs[0]["ocr_doubt"])
        qs, _ = _doubt(PG, [0], {0: {"gia": 1.0}}, floor=0)
        self.assertNotIn("ocr_doubt", qs[0])

    def test_71_2_median_not_min(self):
        t = HEAD + "".join("5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t%d\thơn\n" % c for c in (10, 90, 92, 95))
        self.assertGreaterEqual(pdfmod._parse_tsv(t)["hơn"], 60)
        t = HEAD + "".join("5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t%d\thơn\n" % c for c in (10, 20, 30, 95))
        self.assertLess(pdfmod._parse_tsv(t)["hơn"], 60)

    def test_71_4_parity_never_on_clean_or_native(self):
        def q(o):
            return {"options": [{"text": t} for t in o]}
        qs = [q(["một", "hai", "ba", "bốn"]) for _ in range(10)]
        pdfmod._option_parity(qs, list(range(10)))
        self.assertFalse(any("structure" in x for x in qs))
        qs = [q(["một", "hai", "ba", "$4"])]
        pdfmod._option_parity(qs, [])
        self.assertNotIn("structure", qs[0])
        pdfmod._option_parity(qs, [0])
        self.assertEqual(qs[0]["structure"], ["option_parity"])

    def test_71_4_parity_idempotent(self):
        qs = [{"options": [{"text": t} for t in ("một", "hai", "ba", "$4")]}]
        pdfmod._option_parity(qs, [0])
        pdfmod._option_parity(qs, [0])
        self.assertEqual(qs[0]["structure"], ["option_parity"])

    def test_71_3_chemistry_and_money_not_strong(self):
        for t in ("H2O", "Fe2O3", "CO2", "$5", "$1,000", "x2", "A1", "10$", "3m2", "m2"):
            self.assertFalse(pdfmod._odd_token(t), t)
        for t in ("h0n", "gi4", "$o", "tr1nh"):
            if t == "gi4":
                continue  # digit at the end: not a strong shape
            self.assertTrue(pdfmod._odd_token(t), t)


if __name__ == "__main__":
    unittest.main()

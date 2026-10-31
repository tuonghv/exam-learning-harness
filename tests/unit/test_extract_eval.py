"""TASK-035 / REQ-0025: extraction accuracy benchmark (exact match, Wilson, claims); $0, no LLM."""
import contextlib
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
from exam_engine.ingest import refine  # noqa: E402
from exam_engine.pipeline import benchmark, extract_eval as ee  # noqa: E402

GOLD = os.path.join(ROOT, "evals", "extract", "gold", "synthetic-001.json")
FX = os.path.join(HERE, "fixtures", "extract_eval")


def fx(name):
    return os.path.join(FX, name)


def ev(name):
    return ee.evaluate(ee.load_questions(GOLD), ee.load_questions(fx(name)))


def tmpjson(obj):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    return path


class WilsonTests(unittest.TestCase):
    def test_known_values(self):
        for (k, n), (lo, hi) in {(20, 20): (0.8389, 1.0), (0, 20): (0.0, 0.1611),
                                 (10, 20): (0.2993, 0.7007), (8, 10): (0.4902, 0.9433)}.items():
            got = ee.wilson(k, n)
            self.assertAlmostEqual(got[0], lo, places=4, msg=(k, n))
            self.assertAlmostEqual(got[1], hi, places=4, msg=(k, n))

    def test_n_zero_and_clamp(self):
        self.assertIsNone(ee.wilson(0, 0))
        for k in (0, 1, 5):
            lo, hi = ee.wilson(k, 5)
            self.assertTrue(0.0 <= lo <= hi <= 1.0)


class ClaimTests(unittest.TestCase):
    def test_zero_error_n(self):
        self.assertEqual(ee.zero_error_n(0.99), 299)
        self.assertEqual(ee.zero_error_n(0.999), 2995)
        self.assertEqual(ee.zero_error_n(0.99999), 299572)

    def test_report_text(self):
        md = ee.report_md(ev("perfect.json"))
        self.assertIn("299572", md)
        self.assertIn("NOT claimed", md)


class CanonTests(unittest.TestCase):
    def test_canon(self):
        self.assertEqual(ee.canon("\u0054i\u0301nh"), ee.canon("\u0054\u00ednh"))
        self.assertNotEqual(ee.canon("Tinh"), ee.canon("T\u00ednh"))
        self.assertNotEqual(ee.canon("x^2"), ee.canon("x^3"))
        self.assertNotEqual(ee.canon("-1"), ee.canon("+1"))
        self.assertNotEqual(ee.canon("A"), ee.canon("a"))
        self.assertEqual(ee.canon("  a \n b\t c "), "a b c")


class MetricTests(unittest.TestCase):
    def test_perfect(self):
        sm = ev("perfect.json")
        self.assertEqual(sm["missing"], [])
        self.assertEqual(sm["extra"], [])
        for r in [sm["overall"]] + list(sm["fields"].values()) + [sm["verified_precision"]]:
            self.assertEqual((r["k"], r["n"], r["rate"]), (20, 20, 1.0))

    def test_corrupted_exact_counts(self):
        sm = ev("corrupted.json")
        got = {k: (v["k"], v["n"]) for k, v in sm["fields"].items()}
        self.assertEqual(got, {"text": (18, 20), "formula": (17, 20), "options": (18, 20), "figures": (18, 20)})
        self.assertEqual((sm["overall"]["k"], sm["overall"]["n"]), (14, 20))
        self.assertEqual((sm["verified_precision"]["k"], sm["verified_precision"]["n"]), (14, 19))
        self.assertEqual(sm["missing"], ["15"])
        self.assertEqual(sm["extra"], ["99"])
        self.assertGreater(ev("perfect.json")["overall"]["rate"], sm["overall"]["rate"])
        md = ee.report_md(sm)
        self.assertIn("overall 14/20", md)
        self.assertIn("verified precision 14/19", md)

    def test_review(self):
        sm = ev("review.json")
        self.assertEqual((sm["needs_review"]["k"], sm["needs_review"]["n"]), (4, 20))
        self.assertEqual((sm["verified_precision"]["k"], sm["verified_precision"]["n"]), (15, 15))

    def test_none_verified(self):
        sm = ev("none_verified.json")
        self.assertEqual(sm["verified_precision"]["n"], 0)
        self.assertIsNone(sm["verified_precision"]["rate"])
        self.assertIsNone(sm["verified_precision"]["wilson"])
        self.assertIn("n/a (0 verified)", ee.report_md(sm))


class LoaderTests(unittest.TestCase):
    def test_equivalent_shapes(self):
        a = tmpjson({"questions": [{"id": "1", "text": "t", "options": {"A": "x", "B": "y"}}]})
        b = tmpjson([{"n": 1, "text": "t", "options": [{"key": "A", "text": "x"}, {"key": "B", "text": "y"}]}])
        self.addCleanup(os.remove, a)
        self.addCleanup(os.remove, b)
        self.assertEqual(ee.load_questions(a), ee.load_questions(b))

    def test_rejects(self):
        q = {"id": "1", "text": "t"}
        bad = [{"questions": [q, dict(q)]},
               {"questions": [dict(q, answer="A")]},
               {"questions": [dict(q, verification={"status": "maybe"})]},
               {"questions": []},
               {"questions": [{"text": "no id"}]},
               {"answer": "A", "questions": [q]}]
        for obj in bad:
            p = tmpjson(obj)
            self.addCleanup(os.remove, p)
            with self.assertRaises(ValueError, msg=obj):
                ee.load_questions(p)
        with self.assertRaises(ValueError):
            ee.load_questions(os.path.join(FX, "does-not-exist.json"))


class GoldGuardTests(unittest.TestCase):
    def test_gold_file(self):
        with open(GOLD, encoding="utf-8") as fh:
            raw = json.load(fh)
        qs = raw["questions"]
        self.assertGreaterEqual(len(qs), 20)
        for q in qs:
            for k in refine.FORBIDDEN:
                self.assertNotIn(k, q)
        for k in refine.FORBIDDEN:
            self.assertNotIn(k, raw)
        viet = sum(1 for q in qs if any(ord(c) > 127 and c.isalpha() for c in q["text"]))
        latex = sum(1 for q in qs if q["formula"])
        abcd = sum(1 for q in qs if sorted(q["options"]) == ["A", "B", "C", "D"])
        figs = sum(1 for q in qs if q["figures"])
        tables = sum(1 for q in qs if "|---" in q["text"])
        openq = sum(1 for q in qs if not q["options"])
        self.assertGreaterEqual(viet, 5)
        self.assertGreaterEqual(latex, 8)
        self.assertGreaterEqual(abcd, 15)
        self.assertGreaterEqual(figs, 3)
        self.assertGreaterEqual(tables, 2)
        self.assertGreaterEqual(openq, 2)

    def test_not_scanned(self):
        rel = os.path.relpath(GOLD, ROOT).split(os.sep)
        self.assertEqual(rel[:2], ["evals", "extract"])
        found = benchmark.discover(os.path.join(ROOT, "evals", "inputs"), os.path.join(ROOT, "evals", "keys"))
        self.assertFalse([f for f in found if "extract" in f[2] or "extract" in f[3]])


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(["extract-eval"] + list(args))
        return rc, out.getvalue(), err.getvalue()

    def test_ok_and_files(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, _ = self.run_cli(GOLD, fx("perfect.json"), "--out", d)
            self.assertEqual(rc, 0)
            self.assertIn("overall 20/20", out)
            self.assertTrue(os.path.isfile(os.path.join(d, "extract_eval.json")))
            self.assertTrue(os.path.isfile(os.path.join(d, "extract_eval.md")))

    def test_missing_file(self):
        rc, _, err = self.run_cli(GOLD, fx("nope.json"))
        self.assertEqual(rc, 2)
        self.assertIn("ERROR: extract-eval:", err)


if __name__ == "__main__":
    unittest.main()

"""Phase 46 (REQ-0050): completeness rates of extract-eval, old outputs byte-identical. $0, no fitz needed."""
import contextlib
import copy
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
from exam_engine.pipeline import extract_eval as ee  # noqa: E402

GOLD = os.path.join(ROOT, "evals", "extract", "gold", "synthetic-001.json")
FX = os.path.join(HERE, "fixtures", "extract_eval")
GOLDEN = os.path.join(HERE, "fixtures", "extract_eval_golden")


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(args)
    return code, out.getvalue(), err.getvalue()


def stem(i):
    return "Mở đầu %d rồi nội dung riêng của mục thứ %d kết thúc ở đây" % (i, i)


def mk_gold(n=6, cross=(2, 4)):
    qs = []
    for i in range(1, n + 1):
        qs.append({"id": str(i), "text": stem(i), "formula": "", "figures": [],
                   "options": dict((k, "ý %s của %d" % (k, i)) for k in "ABCD"),
                   "pages": [i, i + 1] if i in cross else [i]})
    return qs


def write(obj, d, name):
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"questions": obj} if isinstance(obj, list) else obj, fh, ensure_ascii=False)
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def rates(self, gold, extracted):
        g = ee.load_questions(write(gold, self.dir, "g.json"))
        e = ee.load_questions(write(extracted, self.dir, "e.json"))
        return ee.completeness(g, e)

    def kn(self, cm, name):
        return (cm[name]["k"], cm[name]["n"])


class Rates(Base):
    def setUp(self):
        super().setUp()
        self.gold = mk_gold()
        self.ext = [dict((k, v) for k, v in q.items() if k != "pages") for q in copy.deepcopy(self.gold)]

    def test_perfect(self):
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "boundary"), (6, 6))
        self.assertEqual(self.kn(cm, "cross_page"), (2, 2))
        self.assertEqual(self.kn(cm, "missing_detection"), (0, 0))
        self.assertEqual(self.kn(cm, "false_merge"), (0, 6))
        self.assertEqual(self.kn(cm, "incomplete_to_solver"), (0, 6))
        self.assertFalse(cm["fail"])
        self.assertIsNone(cm["missing_detection"]["wilson"])
        self.assertEqual(cm["boundary"]["wilson"], list(ee.wilson(6, 6)))

    def test_cut_stem_and_missing_options_is_detected(self):
        # q2 (a cross-page one) lost its tail and options C-D: wrong, and the structure check marks it
        self.ext[1]["text"] = stem(2)[:30]
        self.ext[1]["options"] = dict((k, v) for k, v in self.ext[1]["options"].items() if k in "AB")
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "boundary"), (5, 6))
        self.assertEqual(self.kn(cm, "cross_page"), (1, 2))
        self.assertEqual(self.kn(cm, "missing_detection"), (1, 1))
        self.assertEqual(self.kn(cm, "incomplete_to_solver"), (0, 6))

    def test_unmarked_wrong_reaches_solver(self):
        # q5 loses its ending but looks whole: nothing marks it -> FAIL
        self.ext[4]["text"] = stem(5)[:-12]
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "boundary"), (5, 6))
        self.assertEqual(self.kn(cm, "missing_detection"), (0, 1))
        self.assertEqual(self.kn(cm, "incomplete_to_solver"), (1, 6))
        self.assertTrue(cm["fail"])
        self.assertIn("FAIL", "\n".join(ee.completeness_lines(cm)))

    def test_false_merge(self):
        # q3 swallowed the opening of q4
        self.ext[2]["text"] += " " + stem(4)
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "false_merge"), (1, 6))
        self.assertEqual(self.kn(cm, "boundary"), (5, 6))

    def test_missing_question_is_a_boundary_miss_not_a_wrong_extraction(self):
        del self.ext[0]
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "boundary"), (5, 6))
        self.assertEqual(self.kn(cm, "incomplete_to_solver"), (0, 5))

    def test_exact_but_marked_is_a_false_alarm_not_a_miss(self):
        self.gold[0]["text"] += " xem hình bên dưới"
        self.ext[0]["text"] += " xem hình bên dưới"
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "false_alarm"), (1, 6))
        self.assertEqual(self.kn(cm, "boundary"), (6, 6))

    def test_formula_folded_into_text_is_still_a_boundary(self):
        self.gold[0]["formula"] = "x^{2}+1"
        self.ext[0]["text"] += " x^{2}+1"
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "boundary"), (6, 6))

    def test_report_states_the_zero_error_n(self):
        text = "\n".join(ee.completeness_lines(self.rates(self.gold, self.ext)))
        self.assertIn("NOT claimed", text)
        self.assertIn(str(ee.zero_error_n(0.999)), text)
        self.assertEqual(ee.zero_error_n(0.999), 2995)
        self.assertIn("Wilson 95%", text)


class StrictVsContent(Base):
    def setUp(self):
        super().setUp()
        self.gold = mk_gold()
        self.ext = [dict((k, v) for k, v in q.items() if k != "pages") for q in copy.deepcopy(self.gold)]

    def test_glued_words_are_strict_wrong_but_content_equal(self):
        self.ext[0]["text"] = stem(1).replace(" ", "")
        self.ext[1]["options"]["A"] = self.ext[1]["options"]["A"].replace(" ", "")
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "incomplete_to_solver"), (2, 6))
        self.assertEqual(self.kn(cm, "incomplete_to_solver_strict"), (2, 6))
        self.assertEqual(self.kn(cm, "incomplete_to_solver_content"), (0, 6))
        self.assertEqual(self.kn(cm, "content_errors"), (0, 6))

    def test_real_content_error_counts_in_both(self):
        self.ext[2]["text"] = stem(3).replace("riêng", "riềng")
        self.ext[0]["text"] = stem(1).replace(" ", "")
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "incomplete_to_solver_strict"), (2, 6))
        self.assertEqual(self.kn(cm, "incomplete_to_solver_content"), (1, 6))
        self.assertEqual(self.kn(cm, "content_errors"), (1, 6))

    def test_content_ignores_nfc_form(self):
        import unicodedata
        self.ext[0]["text"] = unicodedata.normalize("NFD", stem(1))
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "incomplete_to_solver_content"), (0, 6))

    def test_marked_content_error_is_not_unmarked(self):
        self.ext[1]["text"] = stem(2)[:30]
        self.ext[1]["options"] = {"A": "x", "B": "y"}
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "content_errors"), (1, 6))
        self.assertEqual(self.kn(cm, "incomplete_to_solver_content"), (0, 6))

    def test_drop_moves_missing_to_solver_only(self):
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "missing_to_solver"), (0, 6))
        del self.ext[0], self.ext[2]
        cm = self.rates(self.gold, self.ext)
        self.assertEqual(self.kn(cm, "missing_to_solver"), (2, 6))
        self.assertEqual(self.kn(cm, "incomplete_to_solver"), (0, 4))
        self.assertFalse(cm["fail"])
        text = "\n".join(ee.completeness_lines(cm))
        self.assertIn("silent drop) 2/6", text)
        self.assertIn("incomplete_to_solver_content", text)

    def test_existing_lines_keep_their_order_and_text(self):
        lines = ee.completeness_lines(self.rates(self.gold, self.ext))
        self.assertTrue(lines[0].startswith("boundary 6/6"))
        self.assertTrue(lines[4].startswith("incomplete_to_solver 0/6"))


class LoadingAndIdentity(Base):
    def test_gold_without_pages_loads_unchanged(self):
        g = ee.load_questions(GOLD)
        self.assertTrue(all(r["pages"] == [] for r in g.values()))
        self.assertEqual(ee.evaluate(g, g)["overall"]["k"], 20)

    def test_pages_are_read(self):
        g = ee.load_questions(write(mk_gold(), self.dir, "g.json"))
        self.assertEqual(g["2"]["pages"], [2, 3])

    def test_old_outputs_byte_identical(self):
        for name in ("perfect", "corrupted"):
            out = os.path.join(self.dir, name)
            code, stdout, _ = run_cli(["extract-eval", GOLD, os.path.join(FX, name + ".json"), "--out", out])
            self.assertEqual(code, 0)
            with open(os.path.join(GOLDEN, name + ".txt"), encoding="utf-8") as fh:
                self.assertEqual(stdout, fh.read())
            with open(os.path.join(out, "extract_eval.json"), "rb") as a, \
                    open(os.path.join(GOLDEN, name + ".json"), "rb") as b:
                self.assertEqual(a.read(), b.read())
            with open(os.path.join(out, "extract_eval.md"), encoding="utf-8") as a, \
                    open(os.path.join(GOLDEN, name + ".md"), encoding="utf-8") as b:
                keep = lambda t: [ln for ln in t.read().split("\n") if not ln.startswith("gold: ")]  # noqa: E731
                self.assertEqual(keep(a), keep(b))
            self.assertEqual(sorted(os.listdir(out)), ["extract_eval.json", "extract_eval.md"])

    def test_cli_completeness_is_additive(self):
        out = os.path.join(self.dir, "o")
        code, stdout, _ = run_cli(["extract-eval", GOLD, os.path.join(FX, "perfect.json"),
                                   "--completeness", "--out", out])
        self.assertEqual(code, 0)
        with open(os.path.join(GOLDEN, "perfect.txt"), encoding="utf-8") as fh:
            old = fh.read()
        self.assertTrue(stdout.startswith(old))
        self.assertIn("boundary 20/20", stdout)
        self.assertEqual(sorted(os.listdir(out)), ["completeness.json", "completeness.md", "extract_eval.json",
                                                   "extract_eval.md"])

    def test_cli_exit_1_when_a_wrong_question_would_reach_the_solver(self):
        gold = mk_gold()
        ext = [dict((k, v) for k, v in q.items() if k != "pages") for q in copy.deepcopy(gold)]
        ext[4]["text"] = stem(5)[:-12]
        g, e = write(gold, self.dir, "g.json"), write(ext, self.dir, "e.json")
        code, stdout, _ = run_cli(["extract-eval", g, e, "--completeness"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL", stdout)
        self.assertEqual(run_cli(["extract-eval", g, e])[0], 0)


if __name__ == "__main__":
    unittest.main()

"""TASK-111 / REQ-0118: --help exits 0, --write-recipe never overwrites an unreadable recipe, run-stats --exam error exits 2."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402

HELP_MAINS = ["benchmark", "cross", "extract_eval", "genexam", "gold_pdf", "ingest", "inspect", "lessons", "parse",
              "refine", "report_index", "report", "review_apply", "review_pack", "run_compare", "verify"]


def quiet(fn, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(argv)
    return code, out.getvalue(), err.getvalue()


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)


class T1Help(unittest.TestCase):
    def test_help_exits_0_all(self):
        for name in HELP_MAINS:
            with self.subTest(name):
                self.assertEqual(quiet(getattr(cli, name + "_main"), ["--help"])[0], 0)

    def test_unknown_flag_exits_2(self):
        for name in ("ingest", "inspect", "lessons", "review_pack", "genexam", "gold_pdf"):
            with self.subTest(name):
                self.assertEqual(quiet(getattr(cli, name + "_main"), ["--no-such-flag"])[0], 2)

    def test_hand_parsed_bad_usage_still_2(self):
        for name in ("parse", "verify", "report_index", "run_compare"):
            with self.subTest(name):
                self.assertEqual(quiet(getattr(cli, name + "_main"), ["--no-such-flag"])[0], 2)


class T2Recipe(Tmp):
    def run_rb(self, path):
        os.makedirs(os.path.join(self.tmp, "reports"), exist_ok=True)
        return quiet(cli.rebuild_reports_main, ["--write-recipe", "--recipe", path,
                                                 "--reports", os.path.join(self.tmp, "reports")])

    def test_corrupt_recipe_refused_byte_identical(self):
        for body in (b"{bad", b'{"version": 99, "exams": {}}'):
            with self.subTest(body=body):
                p = os.path.join(self.tmp, "r.json")
                with open(p, "wb") as fh:
                    fh.write(body)
                code, _, err = self.run_rb(p)
                self.assertEqual(code, 2, err)
                self.assertIn("ERROR", err)
                with open(p, "rb") as fh:
                    self.assertEqual(fh.read(), body)

    def test_missing_recipe_still_created(self):
        p = os.path.join(self.tmp, "new.json")
        code, _, err = self.run_rb(p)
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(p))


class T3RunStats(Tmp):
    def test_missing_exam_exits_2_no_history(self):
        o, h = os.path.join(self.tmp, "o"), os.path.join(self.tmp, "h")
        code, _, err = quiet(cli.solve_main, [os.path.join(ROOT, "examples/english/input-001.md"), "--mock",
                                              os.path.join(ROOT, "tests/unit/fixtures/mock_english_001.json"),
                                              "--out", o, "--no-pdf"])
        self.assertTrue(os.path.isfile(os.path.join(o, "result.json")), err)
        for sub in ("stats", "compare"):
            argv = [sub, o] + ([o] if sub == "compare" else []) + ["--exam", os.path.join(self.tmp, "nosuch.md"),
                                                                    "--history", h]
            code, out, err = quiet(cli.run_stats_main, argv)
            self.assertEqual(code, 2, err)
            self.assertEqual(out, "")
            self.assertFalse(os.path.exists(h))


class T4Edges(Tmp):
    def test_short_h_exits_0_with_usage(self):
        for name in ("parse", "verify", "report", "lessons", "ingest"):
            with self.subTest(name):
                code, out, err = quiet(getattr(cli, name + "_main"), ["-h"])
                self.assertEqual(code, 0, err)
                self.assertIn("usage", (out + err).lower())

    def test_help_after_positional_exits_0(self):
        for name, argv in (("parse", ["x.md", "--help"]), ("verify", ["x.md", "--help"]),
                           ("lessons", ["x", "--help"]), ("ingest", ["x.pdf", "--help"])):
            with self.subTest(name):
                code, out, err = quiet(getattr(cli, name + "_main"), argv)
                self.assertEqual(code, 0, err)
                self.assertIn("usage", (out + err).lower())

    def test_help_prints_usage_all(self):
        for name in HELP_MAINS:
            with self.subTest(name):
                code, out, err = quiet(getattr(cli, name + "_main"), ["--help"])
                self.assertEqual(code, 0)
                self.assertIn("usage", (out + err).lower())

    def test_recipe_wrong_type_refused_byte_identical(self):
        os.makedirs(os.path.join(self.tmp, "reports"))
        for body in (b"[]", b'["a", 1]', b"null", b'"s"'):
            with self.subTest(body=body):
                p = os.path.join(self.tmp, "r.json")
                with open(p, "wb") as fh:
                    fh.write(body)
                code, _, err = quiet(cli.rebuild_reports_main, ["--write-recipe", "--recipe", p,
                                                                "--reports", os.path.join(self.tmp, "reports")])
                self.assertEqual(code, 2, err)
                self.assertIn("ERROR", err)
                with open(p, "rb") as fh:
                    self.assertEqual(fh.read(), body)

    def test_good_exam_stats_exit_0_and_solve_history_written(self):
        o, h = os.path.join(self.tmp, "o"), os.path.join(self.tmp, "h")
        exam = os.path.join(ROOT, "examples/english/input-001.md")
        code, _, err = quiet(cli.solve_main, [exam, "--mock", os.path.join(ROOT, "tests/unit/fixtures/mock_english_001.json"),
                                              "--out", o, "--no-pdf", "--history", h])
        self.assertTrue(os.path.isfile(os.path.join(o, "result.json")), err)  # solve exit 1 = answers not all correct
        with open(h, "rb") as fh:
            before = fh.read()
        self.assertEqual(before.count(b"\n"), 1)
        for sub in ("stats", "compare"):
            argv = [sub, o] + ([o] if sub == "compare" else []) + ["--exam", exam, "--history", h]
            code, out, err = quiet(cli.run_stats_main, argv)
            self.assertEqual(code, 0, err)
            self.assertTrue(out.strip())
        with open(h, "rb") as fh:
            self.assertEqual(fh.read(), before)


if __name__ == "__main__":
    unittest.main()

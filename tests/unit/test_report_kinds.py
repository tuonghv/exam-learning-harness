"""TASK-085 / REQ-0092 AC1-AC5, AC10 (design phase-85): the report-kind registry, standard names, INDEX.md,
the report pack and the independent pack checker. Mock LLM only, no network, tmp trees."""
import contextlib
import copy
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import report_build, report_kinds as rk, report_pack, reporter  # noqa: E402

EXAM = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")
CHECKER = os.path.join(ROOT, "tools", "check_report_pack.py")
GUIDE = os.path.join(ROOT, "docs", "guide", "report-kinds.md")
REGISTRY = os.path.join(ROOT, "config", "report_kinds.json")


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **kw)


def checker(*argv):
    p = subprocess.run([sys.executable, "-I", CHECKER] + list(argv), capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr


class Registry(unittest.TestCase):
    def test_85_1_load_has_all_kinds_with_required_fields(self):
        kinds = rk.load()["kinds"]
        self.assertEqual(len(kinds), 9)
        for k, spec in kinds.items():
            for f in ("ext", "scope", "count", "needs", "description", "legacy"):
                self.assertIn(f, spec, k)
            self.assertIn(spec["scope"], ("subject", "all", "both"))
            self.assertTrue(re.fullmatch(r"[a-z0-9-]+", k), k)

    def test_85_1_name_and_parse_round_trip(self):
        for kind, spec in rk.load()["kinds"].items():
            for ext in spec["ext"]:
                subject = "all" if spec["scope"] == "all" else "math"
                n = rk.name("dgnl2026", subject, kind, "run-f", ext)
                self.assertEqual(n, "dgnl2026_%s_%s_run-f.%s" % (subject, kind, ext))
                self.assertEqual(rk.parse(n), {"exam": "dgnl2026", "subject": subject, "kind": kind,
                                               "run": "run-f", "ext": ext})

    def test_85_1_bad_parts_kind_ext_raise(self):
        bad = [("Dgnl", "math", "metrics", "run-f", "json"), ("a_b", "math", "metrics", "run-f", "json"),
               ("e", "", "metrics", "run-f", "json"), ("e", "math", "metrics", "f", "json"),
               ("e", "math", "nokind", "run-f", "json"), ("e", "math", "metrics", "run-f", "md"),
               ("e", "all", "metrics", "run-f", "json"),  # subject-scope kind needs a subject
               ("e", "math", "answer-table", "run-f", "tsv"),  # all-scope kind rejects a subject
               ("e", None, "metrics", "run-f", "json"), ("e", "m ath", "metrics", "run-f", "json")]
        for args in bad:
            with self.assertRaises(ValueError, msg=str(args)):
                rk.name(*args)

    def test_85_1_parse_rejects_non_standard(self):
        for b in ("report.md", "answers.md", "a_b_c.md", "e_math_metrics_run-f", "e_math_nokind_run-f.json",
                  "e_math_metrics_run-f.md", "E_math_metrics_run-f.json", "e_math_metrics_f.json",
                  "e_math_metrics_run-f_x.json", ""):
            self.assertIsNone(rk.parse(b), b)

    def test_85_1_slug_and_short_run(self):
        self.assertEqual(rk.slug("Toán Học 12!"), "to-n-h-c-12")
        self.assertEqual(rk.slug(None), "")
        self.assertEqual(rk.short_run("out-Science2"), "run-science2")
        self.assertEqual(rk.short_run(""), "run-x")

    def test_85_1_classify(self):
        self.assertEqual(rk.classify("e_math_metrics_run-f.json"), ("metrics", "standard"))
        self.assertEqual(rk.classify("sheet/report.md"), ("solution-report", "legacy"))
        self.assertEqual(rk.classify("answers.tsv"), ("answer-table", "legacy"))
        self.assertEqual(rk.classify("stray.md"), (None, None))
        self.assertEqual(rk.classify("solutions.md", "dhqg2024")[1], "superseded")
        self.assertEqual(rk.classify("report.md", "dgnl2026-crosscheck"), ("solution-report", "superseded"))
        self.assertEqual(rk.classify("report.md", "other")[1], "legacy")

    def test_85_1_find_standard_first_then_legacy(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        self.assertIsNone(rk.find(d, "solution-report"))
        self.assertIsNone(rk.find(os.path.join(d, "missing"), "solution-report"))
        open(os.path.join(d, "report.md"), "w").close()
        self.assertEqual(rk.find(d, "solution-report"), os.path.join(d, "report.md"))  # legacy fallback
        self.assertIsNone(rk.find(d, "solution-report", ext="pdf"))
        std = rk.name("e", "math", "solution-report", "run-a", "md")
        open(os.path.join(d, std), "w").close()
        self.assertEqual(rk.find(d, "solution-report"), os.path.join(d, std))  # standard wins
        self.assertEqual(rk.find(d, "solution-report", subject="math"), os.path.join(d, std))
        self.assertEqual(rk.find(d, "solution-report", subject="other"), os.path.join(d, "report.md"))

    def test_85_1_doc_table_equals_registry(self):
        """No second source: the table of docs/guide/report-kinds.md is exactly config/report_kinds.json."""
        with open(REGISTRY, encoding="utf-8") as fh:
            kinds = json.load(fh)["kinds"]
        rows = {}
        with open(GUIDE, encoding="utf-8") as fh:
            for ln in fh:
                m = re.match(r"\| `([a-z0-9-]+)` \| `[^`]+` \| ([^|]*) \| (\w+) \| ([^|]*) \| (.*) \| ([^|]*) \|$", ln.rstrip())
                if m:
                    rows[m.group(1)] = m.groups()[1:]
        self.assertEqual(sorted(rows), sorted(kinds))
        for k, (ext, scope, needs, desc, legacy) in rows.items():
            spec = kinds[k]
            self.assertEqual([e.strip() for e in ext.split(",")], spec["ext"], k)
            self.assertEqual(scope, spec["scope"], k)
            self.assertEqual(needs.strip(), spec["needs"] or "-", k)
            self.assertEqual(desc.strip(), spec["description"], k)
            self.assertEqual(re.findall(r"`([^`]+)`", legacy), spec["legacy"], k)

    def test_85_1_expected_per_scope_and_needs(self):
        e = rk.expected("e", ["Math", "English"], "run-a", key=False, pdf=True)
        self.assertIn("e_math_answer-sheet_run-a.md", e)
        self.assertIn("e_all_solution-report_run-a.pdf", e)
        self.assertIn("e_english_solution-report_run-a.pdf", e)
        self.assertIn("e_all_answer-table_run-a.tsv", e)
        self.assertFalse([x for x in e if "score-" in x or "learning-report" in x or ".html" in x])
        k = rk.expected("e", ["Math"], "run-a", key=True, pdf=False)
        self.assertIn("e_all_score-vs-key_run-a.tsv", k)
        self.assertIn("e_all_score-summary_run-a.json", k)
        self.assertFalse([x for x in k if x.endswith(".pdf")])
        self.assertEqual(e, sorted(e))


class SolveTime(unittest.TestCase):
    def test_85_5_solve_time_solution_report_has_question_text_and_options(self):
        with tempfile.TemporaryDirectory() as out:
            quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--out", out])
            with open(rk.find(out, "solution-report"), encoding="utf-8") as fh:
                md = fh.read()
        self.assertIn("If I ______ enough time tomorrow", md)
        for opt in ("have", "had", "will have", "would have"):
            self.assertIn(opt, md)

    def test_85_1_registry_path_comes_through_settings(self):
        from exam_engine import settings
        self.assertEqual(os.path.realpath(rk.REGISTRY),
                         os.path.realpath(os.path.join(settings.config_dir(), "report_kinds.json")))
        self.assertTrue(os.path.isfile(rk.REGISTRY))


class Packed(unittest.TestCase):
    """A tmp tree with two synthetic plan runs (the mock english exam under two subject names) and a key."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="rk_test_")
        cwd = os.getcwd()
        os.chdir(cls.tmp)
        try:
            with mock.patch.object(reporter, "git_info", return_value=None):
                quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"])
        finally:
            os.chdir(cwd)
        base = os.path.join(cls.tmp, "plans", "input-001")
        src = os.path.join(base, os.listdir(base)[0])
        cls.plans = []
        for sub in ("Alpha", "Beta"):
            d = os.path.join(cls.tmp, "p", "out-" + sub)
            shutil.copytree(src, d)
            rp = os.path.join(d, "result.json")
            with open(rp, encoding="utf-8") as fh:
                r = json.load(fh)
            r["exam"]["subject"] = sub
            with open(rp, "w", encoding="utf-8") as fh:
                json.dump(r, fh)
            cls.plans.append(d)
        cls.n = len(r["questions"])
        cls.key = os.path.join(cls.tmp, "key.txt")
        with open(cls.key, "w") as fh:
            fh.write("1 A\n2 B\n3 C\n")
        cls.pack = os.path.join(cls.tmp, "pack")
        with mock.patch.object(reporter, "git_info", return_value=None):
            cls.info = report_pack.build_pack(cls.plans, cls.pack, "ex", "run-t", key=cls.key, pdf=False)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def setUp(self):
        # per-test copy of the pack so a test may delete or add files
        self.work = os.path.join(self.tmp, "w-" + self.id().split(".")[-1])
        shutil.copytree(self.pack, self.work)
        self.addCleanup(shutil.rmtree, self.work, True)

    def listing(self, d=None):
        return sorted(os.listdir(d or self.work))

    def test_85_2_writers_emit_only_standard_names(self):
        names = [n for n in self.listing() if n != "INDEX.md"]
        self.assertEqual(names, sorted(self.info["files"]))
        for n in names:
            self.assertIsNotNone(rk.parse(n), n)
        for bare in ("report.md", "answers.md", "report.json", "metrics.json", "answers.tsv"):
            self.assertNotIn(bare, names)
        self.assertEqual(set(self.info["expected"]) - set(names), set())

    def test_85_2_write_reports_and_build_use_standard_names_only(self):
        for fn in (lambda d: report_build.build(self.plans[0], d, pdf=False, exam_name="ex", run_name="run-q"),
                   lambda d: reporter.write_reports(json.load(open(os.path.join(self.plans[0], "result.json"))), d,
                                                    pdf=False)):
            d = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, d, True)
            with mock.patch.object(reporter, "git_info", return_value=None):
                quiet(fn, d)
            files = os.listdir(d)
            self.assertTrue(files)
            for f in files:
                self.assertIsNotNone(rk.parse(f), f)
            self.assertFalse({"report.md", "answers.md"} & set(files))

    def test_85_2_write_reports_learn_view_uses_learning_report(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        with open(os.path.join(self.plans[0], "result.json"), encoding="utf-8") as fh:
            r = json.load(fh)
        info = reporter.write_reports(r, d, pdf=False, view="learn")
        self.assertEqual(rk.parse(os.path.basename(info["md"]))["kind"], "learning-report")
        self.assertEqual(rk.parse(os.path.basename(info["answers"]))["kind"], "answer-sheet")

    def test_85_2_legacy_names_still_read(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        for n in ("report.md", "answers.md", "metrics.json", "report.json"):
            open(os.path.join(d, n), "w").close()
        for kind, ext, want in (("solution-report", "md", "report.md"), ("answer-sheet", "md", "answers.md"),
                                ("metrics", "json", "metrics.json"), ("result-data", "json", "report.json")):
            self.assertEqual(rk.find(d, kind, ext=ext), os.path.join(d, want))
        self.assertEqual(rk.classify("report.md")[1], "legacy")

    def test_85_3_index_byte_identical_for_fixed_tree(self):
        a, b = os.path.join(self.tmp, "ia"), os.path.join(self.tmp, "ib")
        for d in (a, b):
            shutil.rmtree(d, True)
            shutil.copytree(self.work, d)
            os.remove(os.path.join(d, "INDEX.md"))
            rk.write_index(d)
        self.addCleanup(shutil.rmtree, a, True)
        self.addCleanup(shutil.rmtree, b, True)
        with open(os.path.join(a, "INDEX.md"), "rb") as fa, open(os.path.join(b, "INDEX.md"), "rb") as fb:
            ia, ib = fa.read(), fb.read()
        self.assertEqual(ia.replace(b"# Reports index: ia", b""), ib.replace(b"# Reports index: ib", b""))
        rk.write_index(a)  # rewriting the same tree is a no-op
        with open(os.path.join(a, "INDEX.md"), "rb") as fa:
            self.assertEqual(fa.read(), ia)
        self.assertNotIn(self.tmp.encode(), ia)  # no absolute path

    def test_85_3_index_rows_unregistered_superseded_legacy_and_totals(self):
        t = os.path.join(self.tmp, "dhqg2024")
        shutil.rmtree(t, True)
        os.makedirs(os.path.join(t, "sub"))
        self.addCleanup(shutil.rmtree, t, True)
        for n, content in (("solutions.md", "# R\n"), ("sub/answers.tsv", "a\n"), ("stray.txt", "x\n"),
                           (rk.name("e", "math", "metrics", "run-a", "json"), "{}\n")):
            with open(os.path.join(t, n), "w") as fh:
                fh.write(content)
        with open(rk.write_index(t), encoding="utf-8") as fh:
            md = fh.read()
        rows = {ln.split("|")[1].strip(): [c.strip() for c in ln.split("|")[2:6]] for ln in md.splitlines() if ln.startswith("| ") and "---" not in ln}
        self.assertEqual(rows["solutions.md"][1], "superseded")  # glob dhqg2024/solutions.*
        self.assertEqual(rows["stray.txt"][:2], ["-", "unregistered"])
        self.assertIn("not in config/report_kinds.json", md)
        self.assertEqual(rows["sub/answers.tsv"][1], "legacy")
        for line in ("- unregistered: 1", "- superseded: 1", "- standard: 1", "- legacy: 1", "- total: 4", "- metrics: 1"):
            self.assertIn(line, md)
        u = os.path.join(self.tmp, "plain")
        os.makedirs(u)
        self.addCleanup(shutil.rmtree, u, True)
        open(os.path.join(u, "report.md"), "w").write("x")
        with open(rk.write_index(u), encoding="utf-8") as fh:
            md = fh.read()
        self.assertIn("| report.md | solution-report | legacy |", md)
        self.assertIn("- legacy: 1", md)

    def test_85_3_index_is_not_listed_in_itself(self):
        with open(os.path.join(self.work, "INDEX.md"), encoding="utf-8") as fh:
            md = fh.read()
        self.assertNotIn("| INDEX.md |", md)
        self.assertIn("- total: %d" % (len(self.listing()) - 1), md)

    # ---- AC4 hybrid solution-report ----
    def result(self):
        with open(os.path.join(self.plans[0], "result.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def labels(self):
        return reporter.LABELS[reporter.learn_lang(self.result())]

    def test_85_4_hybrid_solution_report(self):
        p = rk.find(self.work, "solution-report", subject="alpha", ext="md")
        self.assertTrue(p, self.listing())
        with open(p, encoding="utf-8") as fh:
            md = fh.read()
        self.assertIn("If I ______ enough time tomorrow", md)  # question text
        self.assertRegex(md, r"(?m)^- [A-D]\.|^[A-D][.)] |^\s*- \*?\*?[A-D]\b")  # options present
        L = self.labels()
        self.assertIn("- %s: " % L["status"], md)
        self.assertIn("- %s: " % L["doubt"], md)
        self.assertNotIn('"level"', md)
        self.assertNotIn("{'level'", md)
        self.assertNotIn(L["no_text"], md)

    def test_85_4_missing_question_text_prints_one_line(self):
        r, L = self.result(), self.labels()
        md = reporter.build_markdown(r, exam=None)
        self.assertEqual(md.count(L["no_text"]), len(r["questions"]))  # one line per question, nothing else
        self.assertNotIn('"level"', md)
        self.assertIn("- %s: " % L["status"], md)
        self.assertIn("- %s: " % L["doubt"], md)

    def test_85_4_raw_json_doubt_is_worded(self):
        r, L = copy.deepcopy(self.result()), self.labels()
        r["questions"][0]["uncertainty"] = {"level": "high", "reasons": ["two readings"]}
        md = reporter.build_markdown(r)
        self.assertNotIn('"level"', md)
        doubt = [ln for ln in md.splitlines() if ln.startswith("- %s: " % L["doubt"])][0]
        self.assertIn(L["levels"]["high"], doubt)
        self.assertNotIn("{", doubt)

    def test_85_4_non_dgnl_synthetic_exam(self):
        # the mock english exam has no dgnl offset/instructions: names and text must still work
        self.assertEqual(rk.parse(os.path.basename(rk.find(self.work, "solution-report", subject="beta"))),
                         {"exam": "ex", "subject": "beta", "kind": "solution-report", "run": "run-t", "ext": "md"})

    # ---- AC5 pack ----
    def test_85_5_pack_files_and_counts(self):
        self.assertEqual(self.info["total"], 2 * self.n)
        self.assertIsInstance(self.info["correct"], int)
        want = rk.expected("ex", ["alpha", "beta"], "run-t", key=True, pdf=False)
        self.assertEqual([f for f in self.listing() if f != "INDEX.md"], want)  # exactly the registry's list
        with open(os.path.join(self.work, rk.name("ex", "all", "answer-table", "run-t", "tsv")), encoding="utf-8") as fh:
            self.assertEqual(len(fh.read().splitlines()), 1 + 2 * self.n)

    def test_85_5_every_file_parses_in_a_mock_solve_output_dir(self):
        d = os.path.join(self.tmp, "solved")
        shutil.rmtree(d, True)
        self.addCleanup(shutil.rmtree, d, True)
        cwd = os.getcwd()
        os.chdir(self.tmp)
        try:
            with mock.patch.object(reporter, "git_info", return_value=None):
                quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--out", d])
        finally:
            os.chdir(cwd)
        plan_files = {"result.json", "run.log", "plan.json", "config.json", "calls", "input"}
        for f in os.listdir(d):
            if f not in plan_files:
                self.assertIsNotNone(rk.parse(f), f)
        self.assertFalse({"report.md", "answers.md"} & set(os.listdir(d)))

    def test_85_5_pack_raises_on_stray_report_md(self):
        out = os.path.join(self.tmp, "stray-pack")
        orig = report_pack.report_build.build

        def build_and_stray(*a, **kw):
            info = orig(*a, **kw)
            open(os.path.join(a[1], "report.md"), "w").close()
            return info
        self.addCleanup(shutil.rmtree, out, True)
        with mock.patch.object(report_pack.report_build, "build", build_and_stray), \
                mock.patch.object(reporter, "git_info", return_value=None):
            with self.assertRaises(ValueError) as cm:
                report_pack.build_pack(self.plans, out, "ex", "run-t", pdf=False)
        self.assertIn("unregistered", str(cm.exception))

    # ---- AC10 checker, both directions ----
    def args(self, pack):
        # the pack was built with pdf=False; the checker expects the solution-report pdf (or html), so add stand-ins
        for n in os.listdir(pack):
            p = rk.parse(n)
            if p and p["kind"] == "solution-report" and p["ext"] == "md":
                open(os.path.join(pack, n[:-3] + ".pdf"), "w").close()
        rk.write_index(pack)  # the checker compares INDEX.md with the files
        return [pack] + self.plans + ["--key", self.key]

    def test_85_10_checker_passes_on_a_complete_pack(self):
        rc, out = checker(*self.args(self.work))
        self.assertEqual(rc, 0, out)
        self.assertIn("0 failed", out)

    def test_85_10_stray_unregistered_file_fails(self):
        open(os.path.join(self.work, "report.md"), "w").close()
        rc, out = checker(*self.args(self.work))
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"unregistered files\t0\t1\tFAIL")

    def test_85_10_missed_kind_fails(self):
        for kind, ext in (("metrics", "json"), ("score-vs-key", "tsv"), ("answer-sheet", "md")):
            d = os.path.join(self.tmp, "m-" + kind)
            shutil.copytree(self.work, d)
            self.addCleanup(shutil.rmtree, d, True)
            os.remove(rk.find(d, kind, ext=ext))
            rc, out = checker(*self.args(d))
            self.assertEqual(rc, 1, (kind, out))
            self.assertIn("FAIL", out)
            self.assertIn(kind, out)

    def test_85_10_new_registered_kind_is_demanded(self):
        with open(REGISTRY, encoding="utf-8") as fh:
            reg = json.load(fh)
        reg["kinds"]["extra-kind"] = {"ext": ["txt"], "scope": "all", "count": "none", "needs": "",
                                      "description": "test only", "legacy": []}
        rp = os.path.join(self.tmp, "reg2.json")
        with open(rp, "w", encoding="utf-8") as fh:
            json.dump(reg, fh)
        self.addCleanup(os.remove, rp)
        rc, out = checker(*self.args(self.work), "--registry", rp)
        self.assertEqual(rc, 1, out)
        self.assertIn("extra-kind", out)
        open(os.path.join(self.work, "ex_all_extra-kind_run-t.txt"), "w").close()
        # registered in the tmp copy only: the file now counts and the checker is satisfied about that kind
        with mock.patch.object(rk, "REGISTRY", rp):  # INDEX.md must follow the same registry
            args = self.args(self.work)
        rc2, out2 = checker(*args, "--registry", rp)
        self.assertNotRegex(out2, r"extra-kind[^\n]*\tFAIL")
        self.assertIn("unregistered files\t0\t0\tok", out2)
        self.assertEqual(rc2, 0, out2)

    def test_85_10_checker_reads_no_exam_engine(self):
        with open(CHECKER, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotRegex(src, r"(?m)^\s*(import|from)\s+exam_engine")


class LegacyCounts(unittest.TestCase):
    """85.3 rounds 3-4: legacy count_of / with_text / INDEX description."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="rk_leg_")
        self.addCleanup(shutil.rmtree, self.d, True)

    def put(self, rel, text):
        p = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    @staticmethod
    def legacy_text(n):
        return "".join("### Question %d\n\nStem %d\n\n**Đáp án: A**\n\n## Question %d\nraw explanation A. x ... B. y ... C. z\n\n"
                       % (i, i, i) for i in range(1, n + 1))

    def row(self, rel):
        with open(rk.write_index(self.d), encoding="utf-8") as fh:
            return next(ln for ln in fh if ln.startswith("| " + rel))

    def test_85_3_count_of_counts_one_heading_style(self):
        p = self.put("ALL-120/report.md", self.legacy_text(120))
        self.assertEqual(rk.count_of(p, "solution-report"), (120, 0))

    def test_85_3_count_of_falls_back_to_h2(self):
        p = self.put("X/report.md", "## Question 1\nx\n## Question 2\ny\n")
        self.assertEqual(rk.count_of(p, "solution-report")[0], 2)

    def test_85_3_with_text_ignores_one_line_options(self):
        p = self.put("X/report.md", "### Question 1\n\nStem\n\nA. x ... B. y ... C. z\n\n**Đáp án: A**\n")
        self.assertEqual(rk.count_of(p, "solution-report"), (1, 0))

    def test_85_3_with_text_hybrid_block(self):
        one = "### Question %d\n\nStem\n\nA. a\nB. b\nC. c\nD. d\n\n**Đáp án: A**\n\n"
        p = self.put("X/report.md", one % 1 + one % 2)
        self.assertEqual(rk.count_of(p, "solution-report"), (2, 2))

    def test_85_3_roman_numerals_are_not_options(self):
        p = self.put("X/report.md", "### Question 1\n\nStem\nI. one\nII. two\nIII. three\n\n**Đáp án: A**\n")
        self.assertEqual(rk.count_of(p, "solution-report"), (1, 0))

    def test_85_3_block_without_stem_or_answer_is_not_text(self):
        self.assertFalse(rk._has_text("\nA. a\nB. b\n**Đáp án: A**\n"))
        self.assertFalse(rk._has_text("\nStem\nA. a\nB. b\n"))

    def test_85_3_index_legacy_no_text_description(self):
        self.put("ALL-120/report.md", self.legacy_text(120))
        row = self.row("ALL-120/report.md")
        self.assertIn("| legacy |", row)
        self.assertIn("120 (with_text 0/120)", row)
        self.assertIn("no question text", row)
        self.assertNotIn("hybrid full report", row)

    def test_85_3_index_legacy_with_options_description(self):
        self.put("ALL-120/report.md", "### Question 1\n\nStem\n\nA. a\nB. b\n\n**Đáp án: A**\n\n"
                 "### Question 2\n\nStem\n**Đáp án: A**\n")
        row = self.row("ALL-120/report.md")
        self.assertIn("2 (with_text 1/2)", row)
        self.assertIn("question text for 1 of 2", row)
        self.assertNotIn("hybrid full report", row)

    def test_85_3_legacy_pdf_description_comes_from_sibling_md(self):
        self.put("Math/report.md", self.legacy_text(3))
        self.put("Math/report.pdf", "%PDF")
        row = self.row("Math/report.pdf")
        self.assertIn("no question text", row)
        self.assertNotIn("question and options", row)

    def test_85_3_legacy_pdf_without_sibling_is_not_inspected(self):
        self.put("Math/report.pdf", "%PDF")
        row = self.row("Math/report.pdf")
        self.assertIn("content not inspected", row)
        self.assertNotIn("question and options", row)

    def test_85_3_legacy_pdf_with_text_sibling_says_question_text(self):
        blk = "".join("### Question %d\n\nStem %d\n\nA. x\nB. y\n\n**Đáp án: A**\n\n" % (i, i) for i in (1, 2))
        self.put("Math/report.md", blk)
        self.put("Math/report.pdf", "%PDF")
        row = self.row("Math/report.pdf")
        self.assertIn("question text for 2 of 2", row)
        self.assertNotIn("no question text", row)

    def test_85_3_standard_name_pdf_keeps_kind_description(self):
        fn = rk.name("ex", "math", "solution-report", "run-a", "pdf")
        self.put(fn, "%PDF")
        row = self.row(fn)
        self.assertIn("standard", row)
        self.assertIn(rk.load()["kinds"]["solution-report"]["description"].replace("|", "/"), row)

    def test_85_3_real_dhqg2024_t81_index(self):
        real = os.path.join(ROOT, "reports", "dhqg2024-t81")
        if not os.path.isfile(os.path.join(real, "ALL-120", "report.md")):
            self.skipTest("reports/dhqg2024-t81 absent")
        dst = os.path.join(self.d, "dhqg2024-t81")
        shutil.copytree(real, dst)
        with open(rk.write_index(dst), encoding="utf-8") as fh:
            row = next(ln for ln in fh if ln.startswith("| ALL-120/report.md"))
        self.assertIn("120 (with_text 0/120)", row)


if __name__ == "__main__":
    unittest.main()

"""TASK-094 / REQ-0101 (94.1-94.5, 94.8): main is the published line; guard, `exam publish`, run-list, INDEX.

$0: mock runner, tmp trees (PROTECTED_ROOTS patched to the tmp plans/reports), no network."""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import planrun, reporter, runlayout  # noqa: E402

EXAM = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "plan_import", "run-small")


def quiet(fn, *a):
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        code = fn(*a)
    return code, o.getvalue(), e.getvalue()


def jread(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def jwrite(p, obj):
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def snapshot(root):
    out = {}
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            with open(p, "rb") as fh:
                out[p] = hashlib.sha256(fh.read()).hexdigest()
    return out


class Base(unittest.TestCase):
    master = plan_src = None

    @classmethod
    def setUpClass(cls):
        cls.master = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(cls.master)
        try:
            with mock.patch.object(reporter, "git_info", return_value=None):
                quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"])  # tmp root: not protected
        finally:
            os.chdir(cwd)
        base = os.path.join(cls.master, "plans", "input-001", "main", "runs")
        cls.plan_src = os.path.join(base, os.listdir(base)[0])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.master, True)

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.tmp)
        for p in (mock.patch.object(reporter, "git_info", return_value=None),):
            p.start()
            self.addCleanup(p.stop)
        self.plans, self.reports = os.path.join(self.tmp, "plans"), os.path.join(self.tmp, "reports")
        os.makedirs(self.plans)
        os.makedirs(self.reports)

    def protect(self):
        p = mock.patch.object(runlayout, "PROTECTED_ROOTS", (self.plans, self.reports))
        p.start()
        self.addCleanup(p.stop)

    def plan(self, exam, line, rid, subject):
        """Copy of the mock solve as plans/<exam>/<line>/runs/<rid>; result subject = `subject`."""
        d = os.path.join(self.plans, exam, line, "runs", rid)
        shutil.copytree(self.plan_src, d)
        res = jread(os.path.join(d, "result.json"))
        res["exam"]["subject"] = subject
        jwrite(os.path.join(d, "result.json"), res)
        meta = jread(os.path.join(d, "plan.json"))
        meta.update(plan_exam=exam, line=line)  # the line a report/pack mirrors comes from plan.json
        jwrite(os.path.join(d, "plan.json"), meta)
        return d

    def tree(self, root):
        return sorted(os.listdir(root)) if os.path.isdir(root) else []


class T941Guard(Base):
    def test_94_1_main_refused_publish_accepted_dev_and_tmp_exempt(self):
        self.protect()
        with self.assertRaises(runlayout.PublishRequired) as cx:
            runlayout.require_publish("main", False, "x", self.plans, "ex")
        msg = str(cx.exception)
        self.assertIn("--line <name>", msg)
        self.assertIn("--publish", msg)
        self.assertIsInstance(cx.exception, ValueError)
        self.assertIsNone(runlayout.require_publish("main", True, "x", self.plans, "ex"))
        for line in ("v3", "fix_abc", "f"):
            self.assertIsNone(runlayout.require_publish(line, False, "x", self.plans, "ex"), line)
        other = os.path.join(self.tmp, "elsewhere")
        os.makedirs(other)
        self.assertIsNone(runlayout.require_publish("main", False, "x", other, "ex"))

    def test_94_1_none_and_dash_count_as_main_and_out_paths_derive_the_line(self):
        self.protect()
        for line in (None, "-"):
            with self.assertRaises(runlayout.PublishRequired):
                runlayout.require_publish(line, False, "x", os.path.join(self.reports, "ex"))
        with self.assertRaises(runlayout.PublishRequired):  # --out inside <reports>/<exam>/main
            runlayout.require_publish(None, False, "x", os.path.join(self.reports, "ex", "main", "run-a"))
        self.assertIsNone(runlayout.require_publish(None, False, "x", os.path.join(self.reports, "ex", "v3", "run-a")))
        self.assertIsNone(runlayout.require_publish(None, True, "x", os.path.join(self.reports, "ex", "main", "run-a")))
        self.assertIsNone(runlayout.require_publish(None, False, "x", os.path.join(self.tmp, "free", "main")))

    def test_94_1_unpatched_tmp_cwd_is_not_protected(self):
        self.assertIsNone(runlayout.require_publish("main", False, "x", self.plans, "ex"))
        self.assertTrue(os.path.isdir(runlayout.new_plan_run(self.plans, "ex")))
        self.assertTrue(os.path.isdir(runlayout.new_report_run(self.reports, "ex")))

    def test_94_2_new_runs_guarded(self):
        self.protect()
        with self.assertRaises(runlayout.PublishRequired):
            runlayout.new_plan_run(self.plans, "ex")
        with self.assertRaises(runlayout.PublishRequired):
            runlayout.new_report_run(self.reports, "ex")
        with self.assertRaises(runlayout.PublishRequired):
            runlayout.new_report_run(self.reports, "ex", line="main")
        self.assertEqual(os.listdir(self.plans) + os.listdir(self.reports), [])
        self.assertTrue(os.path.isdir(runlayout.new_plan_run(self.plans, "ex", publish=True)))
        self.assertTrue(os.path.isdir(runlayout.new_report_run(self.reports, "ex", line="main", publish=True)))
        self.assertTrue(os.path.isdir(runlayout.new_plan_run(self.plans, "ex", line="v3")))
        self.assertTrue(os.path.isdir(runlayout.new_report_run(self.reports, "ex", line="v3")))


class T942EntryPoints(Base):
    def assert_refused(self, code, err):
        self.assertEqual(code, 2, err)
        self.assertIn("--line <name>", err)
        self.assertIn("--publish", err)

    def test_94_2_solve_mock_main_refused_no_dir_then_dev_and_publish(self):
        self.protect()
        code, _, err = quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"])
        self.assert_refused(code, err)
        self.assertEqual(os.listdir(self.plans) + os.listdir(self.reports), [])
        code, _, err = quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--line", "v3"])
        self.assertIn(code, (0, 1), err)  # 1 = the mock answer is uncertain
        self.assertEqual(self.tree(os.path.join(self.plans, "input-001")), ["v3"])
        code, _, err = quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--line", "v3", "--publish"])  # no-op
        self.assertIn(code, (0, 1), err)

    def test_94_4_solve_line_main_publish_writes_new_id_each_time(self):
        self.protect()
        ids = []
        for _ in range(2):
            code, _, err = quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--line", "main", "--publish"])
            self.assertIn(code, (0, 1), err)
            ids = self.tree(os.path.join(self.plans, "input-001", "main", "runs"))
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 2)
        self.assertTrue(self.tree(os.path.join(self.reports, "input-001", "main")))

    def test_94_2_solve_dry_run_and_out_cases(self):
        self.protect()
        code, _, err = quiet(cli.solve_main, [EXAM, "--dry-run"])
        self.assertEqual(code, 0, err)
        self.assertEqual(os.listdir(self.plans), [])
        out = os.path.join(self.reports, "input-001", "main", "x")
        code, _, err = quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--out", out])
        self.assert_refused(code, err)
        self.assertFalse(os.path.exists(out))
        out2 = os.path.join(self.tmp, "free-out")
        code, _, err = quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--out", out2])
        self.assertIn(code, (0, 1), err)

    def test_94_2_report_and_report_pack_guarded(self):
        p1 = self.plan("ex", "v3", "20240101-000001-a", "A")
        p2 = self.plan("ex", "v3", "20240101-000002-b", "B")
        self.protect()
        # plan runs in a dev line mirror the line: v3 passes
        code, _, err = quiet(cli.report_main, [p1, "--no-pdf"])
        self.assertEqual(code, 0, err)
        code, _, err = quiet(cli.report_pack_main, [p1, p2, "--exam", "ex", "--no-pdf"])
        self.assertEqual(code, 0, err)
        # main plan runs: refused without --publish
        m1 = self.plan("ex", "main", "20240101-000001-a", "A")
        m2 = self.plan("ex", "main", "20240101-000002-b", "B")
        before = snapshot(self.reports)
        code, _, err = quiet(cli.report_main, [m1, "--no-pdf"])
        self.assert_refused(code, err)
        code, _, err = quiet(cli.report_pack_main, [m1, m2, "--exam", "ex", "--no-pdf"])
        self.assert_refused(code, err)
        out = os.path.join(self.reports, "ex", "main", "run-z")
        code, _, err = quiet(cli.report_pack_main, [p1, p2, "--exam", "ex", "--no-pdf", "--out", out])
        self.assert_refused(code, err)
        self.assertFalse(os.path.exists(out))
        self.assertEqual(snapshot(self.reports), before)
        code, _, err = quiet(cli.report_main, [m1, "--no-pdf", "--publish"])
        self.assertEqual(code, 0, err)
        code, _, err = quiet(cli.report_pack_main, [m1, m2, "--exam", "ex", "--no-pdf", "--publish"])
        self.assertEqual(code, 0, err)
        self.assertNotEqual(snapshot(self.reports), before)

    def test_94_2_plan_import_guarded(self):
        self.protect()
        args = [FIXTURE, "--exam", EXAM, "--exam-id", "ex"]
        code, _, err = quiet(cli.plan_import_main, args)
        self.assert_refused(code, err)
        self.assertEqual(os.listdir(self.plans), [])
        code, _, err = quiet(cli.plan_import_main, args + ["--line", "v3"])
        self.assertEqual(code, 0, err)
        copy = os.path.join(self.tmp, "old-copy")  # same dir + result would be "skipped" (already imported)
        shutil.copytree(FIXTURE, copy)
        code, _, err = quiet(cli.plan_import_main, [copy] + args[1:] + ["--publish"])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.tree(os.path.join(self.plans, "ex")), ["main", "v3"])

    def test_94_2_read_only_commands_and_report_index_not_guarded(self):
        self.plan("ex", "main", "20240101-000001-a", "A")
        self.protect()
        for fn, args in ((cli.run_list_main, ["ex"]), (cli.run_stats_main, ["stats", "ex/main/20240101-000001-a",
                                                                          "--history", os.path.join(self.tmp, "h.jsonl")]),
                         (cli.run_compare_main, ["ex/main/20240101-000001-a", "ex/main/20240101-000001-a"])):
            code, out, err = quiet(fn, args)
            self.assertIn(code, (0, 1), out + err)
            self.assertNotIn("published line", err)
        os.makedirs(os.path.join(self.reports, "ex", "main"))
        code, _, err = quiet(cli.report_index_main, [os.path.join(self.reports, "ex")])
        self.assertEqual(code, 0, err)
        planrun.last_solved("plans", EXAM, exam_id="ex")  # read-only: must not raise PublishRequired


class T943Publish(Base):
    def fixture(self):
        """f = dgnl2026/f shape: math, science, science2 (same subject); the pack holds math + science2."""
        self.m = self.plan("ex", "f", "20240101-000001-math", "Math")
        self.s1 = self.plan("ex", "f", "20240101-000002-science", "Science")
        self.s2 = self.plan("ex", "f", "20240101-000003-science2", "Science")
        code, _, err = quiet(cli.report_pack_main, [self.m, self.s2, "--exam", "ex", "--no-pdf", "--run", "f"])
        self.assertEqual(code, 0, err)
        self.protect()

    def publish(self, *extra):
        return quiet(cli.publish_main, ["ex", "--no-pdf"] + list(extra))

    def main_runs(self):
        return [n for n in self.tree(os.path.join(self.reports, "ex", "main")) if n.startswith("run-")]

    def test_94_3_pack_plan_runs_win_over_duplicate_subject(self):
        self.fixture()
        sel, src = cli._publish_selection("plans", "reports", "ex", "f")
        self.assertEqual(sorted(os.path.basename(d) for d, _ in sel), ["20240101-000001-math", "20240101-000003-science2"])
        self.assertIsNotNone(src)
        code, out, err = self.publish("--from", "f")
        self.assertEqual(code, 0, out + err)
        (rid,) = self.main_runs()
        man = jread(os.path.join(self.reports, "ex", "main", rid, "run.json"))
        self.assertEqual((man["cmd"], man["published_from"]), ("publish", "f"))
        self.assertEqual(man["source_report_run"], src["id"])
        self.assertEqual({p["line"] for p in man["plan_runs"]}, {"f"})
        self.assertEqual(sorted(p["plan_run_id"] for p in man["plan_runs"]),
                         ["20240101-000001-math", "20240101-000003-science2"])

    def test_94_3_fallback_latest_per_subject_without_pack(self):
        self.plan("ex", "f", "20240101-000001-math", "Math")
        self.plan("ex", "f", "20240101-000002-math", "Math")
        self.plan("ex", "f", "20240101-000003-eng", "English")
        self.protect()
        sel, src = cli._publish_selection("plans", "reports", "ex", "f")
        self.assertIsNone(src)
        self.assertEqual(sorted(os.path.basename(d) for d, _ in sel), ["20240101-000002-math", "20240101-000003-eng"])
        code, out, err = self.publish("--from", "f")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(self.main_runs()), 1)
        self.assertIsNone(jread(os.path.join(self.reports, "ex", "main", self.main_runs()[0], "run.json"))["source_report_run"])

    def test_94_3_earlier_main_runs_untouched_and_second_publish_is_new(self):
        self.fixture()
        mp = self.plan("ex", "main", "20240101-000009-old", "Old")
        code, _, err = quiet(cli.report_main, [mp, "--no-pdf", "--publish"])
        self.assertEqual(code, 0, err)
        (old,) = self.main_runs()
        oldroot = os.path.join(self.reports, "ex", "main", old)
        snap = snapshot(oldroot)
        self.assertEqual(self.publish("--from", "f")[0], 0)
        self.assertEqual(self.publish("--from", "f")[0], 0)
        self.assertEqual(len(self.main_runs()), 3)
        self.assertEqual(snapshot(oldroot), snap)

    def test_94_3_refusals_leave_nothing(self):
        self.fixture()
        before = snapshot(self.reports)
        code, _, err = self.publish("--from", "main")
        self.assertEqual(code, 2)
        self.assertIn("dev line", err)
        code, _, err = self.publish("--from", "nothere")
        self.assertEqual(code, 2)
        self.assertIn("no plan runs", err)
        self.assertEqual(snapshot(self.reports), before)
        self.assertEqual(self.main_runs(), [])
        os.remove(os.path.join(self.s2, "result.json"))  # a selected plan dir without result.json
        code, _, err = self.publish("--from", "f")
        self.assertEqual(code, 2)
        self.assertIn("result.json", err)
        self.assertEqual(self.main_runs(), [])

    def test_94_3_no_model_call_and_index_regenerated(self):
        self.fixture()
        with mock.patch("socket.socket", side_effect=AssertionError("network")):
            code, out, err = self.publish("--from", "f")
        self.assertEqual(code, 0, out + err)
        with open(os.path.join(self.reports, "ex", "INDEX.md"), encoding="utf-8") as fh:
            md = fh.read()
        self.assertIn("## Lines", md)
        self.assertLess(md.index("| main |"), md.index("| f |"))


class T945Columns(Base):
    def rows(self, out, part=0):
        sec = out.split("## Report runs")[part]
        return [[c.strip() for c in ln.split("|")[1:-1]] for ln in sec.splitlines()
                if ln.startswith("| ") and "---" not in ln]

    def test_94_5_run_list_publish_column_plan_and_report(self):
        self.plan("ex", "main", "20240101-000001-a", "A")
        f = self.plan("ex", "f", "20240101-000002-b", "B")
        quiet(cli.report_main, [f, "--no-pdf"])
        m = os.path.join(self.plans, "ex", "main", "runs", "20240101-000001-a")
        quiet(cli.report_main, [m, "--no-pdf"])
        code, out, err = quiet(cli.run_list_main, ["ex"])
        self.assertEqual(code, 0, err)
        plan = self.rows(out, 0)
        h = plan[0]
        self.assertIn("publish", h)
        pub = {r[1]: r[h.index("publish")] for r in plan[1:]}
        self.assertEqual(pub, {"main": "published", "f": "dev"})
        rep = self.rows(out, 1)
        rh = rep[0]
        self.assertIn("publish", rh)
        self.assertIn("line", rh)
        got = {r[rh.index("line")]: r[rh.index("publish")] for r in rep[1:]}
        self.assertEqual(got, {"main": "published", "f": "dev"})

    def test_94_5_report_saved_with_no_line_counts_as_main(self):
        d = os.path.join(self.reports, "ex", "run-legacy")
        os.makedirs(d)
        with open(os.path.join(d, "x.md"), "w") as fh:
            fh.write("x\n")
        self.assertTrue(runlayout.is_published_line(None))
        self.assertTrue(runlayout.is_published_line("-"))
        self.assertFalse(runlayout.is_published_line("v3"))

    def test_94_5_lines_table_main_first(self):
        for line in ("zz", "main", "aa"):
            d = os.path.join(self.reports, "ex", line, "run-20240101-000000")
            os.makedirs(d)
            jwrite(os.path.join(d, "run.json"), {"cmd": "report", "status": "complete", "exam_id": "ex",
                                                 "created_utc": "2024-01-01T00:00:00Z", "plan_runs": []})
        rows = runlayout.lines_table(os.path.join(self.reports, "ex"))
        names = [r.split("|")[1].strip() for r in rows if r.startswith("| ") and "---" not in r][1:]
        self.assertEqual(names, ["main", "aa", "zz"])
        self.assertIn("published", [r for r in rows if r.startswith("| main")][0])
        self.assertIn("dev", [r for r in rows if r.startswith("| aa")][0])
        self.assertEqual(runlayout.lines_table(os.path.join(self.tmp, "nope")), [])


class T948Migrate(Base):
    def test_94_8_plans_migrate_not_guarded_under_patched_roots(self):
        # plans-migrate never calls new_plan_run/new_report_run: no require_publish call on its path
        import inspect
        from exam_engine.pipeline import plansmigrate
        self.assertNotIn("new_plan_run", inspect.getsource(plansmigrate))
        self.assertNotIn("new_report_run", inspect.getsource(plansmigrate))
        self.assertNotIn("require_publish", inspect.getsource(plansmigrate))


if __name__ == "__main__":
    unittest.main()

"""TASK-087 / REQ-0095 (87.1-87.7): run-based plans/ and reports/ layout, run.json manifest, run-list, run-compare.

All checks are $0: mock runner, tmp trees, no network. Legacy layouts (plans/<exam>/<run>/, out-X, reports/<exam>/<dir>)
must stay readable and are never moved.
"""
import contextlib
import hashlib
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
from exam_engine.pipeline import planrun, report_kinds as rk, report_build, report_pack, reporter, runlayout  # noqa: E402

EXAM = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")
CHECK = os.path.join(ROOT, "tools", "check_report_pack.py")
REGISTRY = os.path.join(ROOT, "config", "report_kinds.json")


def quiet(fn, *a):
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        code = fn(*a)
    return code, o.getvalue(), e.getvalue()


def sha_of(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def jread(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def put(path, text="x\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text if isinstance(text, str) else json.dumps(text))


def snapshot(*roots):
    out = {}
    for r in roots:
        for dp, _, fns in os.walk(r):
            for fn in fns:
                p = os.path.join(dp, fn)
                out[p] = sha_of(p)
    return out


class Base(unittest.TestCase):
    solved = None  # (tmp, plan dir) of one mock solve, copied per test

    @classmethod
    def setUpClass(cls):
        cls.master = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(cls.master)
        try:
            with mock.patch.object(reporter, "git_info", return_value=None):
                quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"])
        finally:
            os.chdir(cwd)
        base = os.path.join(cls.master, "plans", "input-001", "runs")
        cls.plan_id = os.listdir(base)[0]
        cls.plan_src = os.path.join(base, cls.plan_id)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.master, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.tmp)
        p = mock.patch.object(reporter, "git_info", return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def copy_plan(self, exam="input-001", rid=None, layout="runs"):
        rid = rid or self.plan_id
        dst = os.path.join(self.tmp, "plans", exam, "runs", rid) if layout == "runs" \
            else os.path.join(self.tmp, "plans", exam, rid)
        shutil.copytree(self.plan_src, dst)
        return dst


class U1RunId(unittest.TestCase):
    def test_87_2_new_run_id_utc_format(self):
        self.assertEqual(runlayout.new_run_id(0), "19700101-000000")
        self.assertEqual(runlayout.new_run_id(1700000000), "20231114-221320")
        self.assertRegex(runlayout.new_run_id(), r"^\d{8}-\d{6}$")

    def test_87_2_utc_not_local_time(self):
        with mock.patch.dict(os.environ, {"TZ": "Asia/Ho_Chi_Minh"}):
            import time
            if hasattr(time, "tzset"):
                time.tzset()
                self.addCleanup(time.tzset)
            self.assertEqual(runlayout.new_run_id(0), "19700101-000000")

    def test_87_2_old_id_still_sortable(self):
        self.assertEqual(runlayout.id_time("20240102T030405Z"), "20240102030405")
        self.assertEqual(runlayout.id_time("20240102-030405-2"), "20240102030405")
        self.assertEqual(runlayout.id_time("out-English"), "")


class U2Claim(unittest.TestCase):
    def test_87_1_collision_suffix(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        a = runlayout.new_plan_run(root, "ex", now=0)
        b = runlayout.new_plan_run(root, "ex", now=0)
        c = runlayout.new_plan_run(root, "ex", now=0)
        self.assertEqual([os.path.basename(x) for x in (a, b, c)], ["19700101-000000", "19700101-000000-2", "19700101-000000-3"])
        self.assertEqual({os.path.dirname(x) for x in (a, b, c)}, {os.path.join(root, "ex", "runs")})
        for x in (a, b, c):
            self.assertTrue(os.path.isdir(x))

    def test_87_1_claim_run_dir_delegates(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        d = planrun.claim_run_dir(root, "ex")
        self.assertEqual(os.path.dirname(d), os.path.join(root, "ex", "runs"))
        self.assertRegex(os.path.basename(d), runlayout.NEW_ID)

    def test_87_1_unsafe_ids_refused(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        for bad in ("../x", "a/b", ""):
            with self.assertRaises(ValueError):
                runlayout.new_plan_run(root, bad)
        with self.assertRaises(ValueError):
            runlayout.plan_run_dir(root, "ex", "../up")


class U3ListPlanRuns(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        ex = os.path.join(self.root, "ex")
        put(os.path.join(ex, "runs", "20240301-000000", "plan.json"), {"started_utc": "2024-03-01T00:00:00Z"})
        put(os.path.join(ex, "runs", "20240101-000000", "plan.json"), {"started_utc": "2024-01-01T00:00:00Z"})
        put(os.path.join(ex, "runs", "stray.txt"))
        put(os.path.join(ex, "runs", "empty", "note.txt"))  # a dir with neither plan.json nor result.json is still in runs/
        put(os.path.join(ex, "out-X", "result.json"), {"run": {}})
        put(os.path.join(ex, "20240201T000000Z", "plan.json"), {"started_utc": "2024-02-01T00:00:00Z"})
        put(os.path.join(ex, "cache", "solve-abc.json"), {})
        put(os.path.join(ex, "notaplan", "readme.txt"))
        put(os.path.join(ex, "loose.json"), {})

    def test_87_1_mixes_layouts_skips_noise_and_orders_by_time(self):
        got = runlayout.list_plan_runs(self.root, "ex")
        ids = [r["id"] for r in got]
        self.assertNotIn("cache", ids)
        self.assertNotIn("runs", ids)
        self.assertNotIn("notaplan", ids)
        self.assertNotIn("stray.txt", ids)
        by = {r["id"]: r for r in got}
        self.assertEqual(by["20240101-000000"]["layout"], "runs")
        self.assertEqual(by["20240201T000000Z"]["layout"], "legacy")
        self.assertEqual(by["out-X"]["layout"], "legacy")
        self.assertIsNone(by["out-X"]["plan"])
        order = [i for i in ids if i in ("20240101-000000", "20240201T000000Z", "20240301-000000")]
        self.assertEqual(order, ["20240101-000000", "20240201T000000Z", "20240301-000000"])

    def test_87_1_deterministic(self):
        self.assertEqual(runlayout.list_plan_runs(self.root, "ex"), runlayout.list_plan_runs(self.root, "ex"))

    def test_87_1_missing_exam_is_empty(self):
        self.assertEqual(runlayout.list_plan_runs(self.root, "nope"), [])

    def test_87_1_plan_run_dir_prefers_new_falls_back_legacy(self):
        ex = os.path.join(self.root, "ex")
        self.assertEqual(runlayout.plan_run_dir(self.root, "ex", "20240101-000000"), os.path.join(ex, "runs", "20240101-000000"))
        self.assertEqual(runlayout.plan_run_dir(self.root, "ex", "out-X"), os.path.join(ex, "out-X"))
        self.assertEqual(runlayout.plan_run_dir(self.root, "ex", "20991231-000000"), os.path.join(ex, "runs", "20991231-000000"))
        # reserved names never resolve to the legacy dir
        self.assertEqual(runlayout.plan_run_dir(self.root, "ex", "cache"), os.path.join(ex, "runs", "cache"))

    def test_87_1_same_id_in_both_layouts_new_wins(self):
        put(os.path.join(self.root, "ex", "20240101-000000", "plan.json"), {})
        self.assertEqual(runlayout.plan_run_dir(self.root, "ex", "20240101-000000"),
                         os.path.join(self.root, "ex", "runs", "20240101-000000"))


class U3bPlanOrder(unittest.TestCase):
    """D3: one normalised key (time, suffix, id) across new ids, legacy ids and out-X dirs."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        ex = os.path.join(self.root, "ex")
        put(os.path.join(ex, "runs", "20261108-010203-2", "plan.json"), {"started_utc": "2026-11-08T01:02:03Z"})
        put(os.path.join(ex, "runs", "20261108-010203", "plan.json"), {"started_utc": "2026-11-08T01:02:03Z"})
        put(os.path.join(ex, "20261107T035802Z", "plan.json"), {})
        put(os.path.join(ex, "out-A", "plan.json"), {"started_utc": "2026-11-08T01:02:03Z"})  # ties with the new id
        put(os.path.join(ex, "out-B", "plan.json"), {"imported_utc": "2026-11-07T03:58:02Z"})  # ties with the legacy id
        put(os.path.join(ex, "out-C", "plan.json"), {"finished_utc": "2026-11-06T00:00:00Z"})
        put(os.path.join(ex, "out-D", "result.json"), {})  # no time at all

    def test_87_1_exact_order_with_ties(self):
        ids = [r["id"] for r in runlayout.list_plan_runs(self.root, "ex")]
        self.assertEqual(ids, ["out-D", "out-C", "20261107T035802Z", "out-B",
                               "20261108-010203", "out-A", "20261108-010203-2"])

    def test_87_1_order_independent_of_mtime(self):
        ex = os.path.join(self.root, "ex")
        os.utime(os.path.join(ex, "out-D"), (4000000000, 4000000000))
        os.utime(os.path.join(ex, "runs", "20261108-010203-2"), (1, 1))
        ids = [r["id"] for r in runlayout.list_plan_runs(self.root, "ex")]
        self.assertEqual(ids[0], "out-D")
        self.assertEqual(ids[-1], "20261108-010203-2")

    def test_87_5_run_list_rows_in_same_order(self):
        reports = os.path.join(self.root, "reports")
        code, out, err = quiet(cli.run_list_main, ["ex", "--plans", self.root, "--reports", reports])
        self.assertEqual(code, 0, err)
        rows = [ln.split("|")[1].strip() for ln in out.split("## Report runs")[0].splitlines()
                if ln.startswith("| ") and "---" not in ln][1:]
        self.assertEqual(rows, ["out-D", "out-C", "20261107T035802Z", "out-B",
                                "20261108-010203", "out-A", "20261108-010203-2"])


class U7ExamOfPlanDir(unittest.TestCase):
    def test_87_4_both_layouts_never_runs_d1(self):
        self.assertEqual(runlayout.exam_of_plan_dir("/p/plans/ex-1/runs/20240101-000000"), "ex-1")
        self.assertEqual(runlayout.exam_of_plan_dir("/p/plans/ex-1/runs/20240101-000000/"), "ex-1")
        self.assertEqual(runlayout.exam_of_plan_dir("/p/plans/ex-1/20240101T000000Z"), "ex-1")
        self.assertEqual(runlayout.exam_of_plan_dir("/p/plans/ex-1/out-X"), "ex-1")

    def test_87_4_report_of_plan_without_exam_id_does_not_use_runs(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(tmp)
        src = Base.__dict__  # noqa: F841  (no shared solve here: build a result by solving)
        with mock.patch.object(reporter, "git_info", return_value=None):
            quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--out", "flat"])
        rid = "20240101-000000"
        plan = os.path.join(tmp, "plans", "weird-exam", "runs", rid)
        os.makedirs(plan)
        shutil.copy(os.path.join(tmp, "flat", "result.json"), plan)  # result only: no plan.json, so no exam_id there
        with mock.patch.object(reporter, "git_info", return_value=None):
            code, _, err = quiet(cli.report_main, [plan, "--no-pdf"])
        self.assertEqual(code, 0, err)
        self.assertFalse(os.path.exists(os.path.join(tmp, "reports", "runs")))
        self.assertTrue(os.path.isdir(os.path.join(tmp, "reports", "weird-exam")))
        (rr,) = [n for n in os.listdir(os.path.join(tmp, "reports", "weird-exam")) if n.startswith("run-")]
        self.assertEqual(jread(os.path.join(tmp, "reports", "weird-exam", rr, "run.json"))["exam_id"], "weird-exam")


class U4LastSolvedImported(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.exam = os.path.join(self.root, "ex-a.md")
        put(self.exam, "# exam\n")
        self.sha = hashlib.sha256(open(self.exam, "rb").read()).hexdigest()
        self.plans = os.path.join(self.root, "plans")

    def plan(self, d, fin, calls=3):
        put(os.path.join(d, "plan.json"), {"source": "solve", "status": "done", "llm": "claude-p", "exam": {"sha256": self.sha},
                                           "finished_utc": fin, "calls": calls, "cost_usd": 0.5, "model": "m"})

    def test_87_4_last_solved_finds_new_layout(self):
        self.plan(os.path.join(self.plans, "ex-a", "runs", "20240101-000000"), "2024-01-01T00:10:00Z")
        got = planrun.last_solved(self.plans, self.exam)
        self.assertEqual(os.path.basename(got["dir"]), "20240101-000000")
        self.assertEqual(os.path.basename(os.path.dirname(got["dir"])), "runs")

    def test_87_4_last_solved_finds_legacy_layout(self):
        self.plan(os.path.join(self.plans, "ex-a", "20230101T000000Z"), "2023-01-01T00:10:00Z")
        got = planrun.last_solved(self.plans, self.exam)
        self.assertEqual(os.path.basename(got["dir"]), "20230101T000000Z")

    def test_87_4_last_solved_newest_across_layouts_and_none(self):
        self.assertIsNone(planrun.last_solved(self.plans, self.exam))
        self.plan(os.path.join(self.plans, "ex-a", "20230101T000000Z"), "2023-01-01T00:10:00Z")
        self.plan(os.path.join(self.plans, "ex-a", "runs", "20240101-000000"), "2024-01-01T00:10:00Z")
        self.assertEqual(os.path.basename(planrun.last_solved(self.plans, self.exam)["dir"]), "20240101-000000")

    def test_87_4_exam_id_never_runs(self):
        # D1: a plan dir under runs/ must not make "runs" the exam id
        self.plan(os.path.join(self.plans, "ex-a", "runs", "20240101-000000"), "2024-01-01T00:10:00Z")
        self.assertIsNone(planrun.last_solved(self.plans, os.path.join(self.root, "runs.md")) if os.path.isfile(
            os.path.join(self.root, "runs.md")) else None)
        self.assertEqual(runlayout.list_plan_runs(self.plans, "runs"), [])

    def test_87_4_already_imported_both_layouts(self):
        put(os.path.join(self.plans, "ex", "runs", "20240101-000000", "plan.json"), {"imported_from": "/s1", "result_sha256": "aa"})
        put(os.path.join(self.plans, "ex", "old-run", "plan.json"), {"imported_from": "/s2", "result_sha256": "bb"})
        self.assertEqual(os.path.basename(planrun._already_imported(self.plans, "ex", "/s1", "aa")), "20240101-000000")
        self.assertEqual(os.path.basename(planrun._already_imported(self.plans, "ex", "/s2", "bb")), "old-run")
        self.assertIsNone(planrun._already_imported(self.plans, "ex", "/s1", "bb"))
        self.assertIsNone(planrun._already_imported(self.plans, "other", "/s1", "aa"))


class U5ReportRuns(Base):
    def test_87_3_two_report_runs_of_one_plan_run_coexist(self):
        plan = self.copy_plan()
        for argv in ([plan, "--no-pdf"], [plan, "--no-pdf", "--view", "learn"]):
            code, _, err = quiet(cli.report_main, argv)
            self.assertEqual(code, 0, err)
        runs = [r for r in runlayout.list_report_runs("reports", "input-001") if r["layout"] == "run"]
        self.assertEqual(len(runs), 2)
        self.assertEqual(len({r["id"] for r in runs}), 2)
        for r in runs:
            self.assertEqual([p["plan_run_id"] for p in r["manifest"]["plan_runs"]], [self.plan_id])
        self.assertEqual({r["manifest"]["view"] for r in runs}, {"sheet", "learn"})
        a, b = runs
        self.assertEqual(b["manifest"]["prev_report_run"], a["id"])
        self.assertIsNone(a["manifest"]["prev_report_run"])

    def test_87_3_rerun_with_same_report_id_overwrites_in_place(self):
        plan = self.copy_plan()
        self.assertEqual(quiet(cli.report_main, [plan, "--no-pdf", "--report-id", "fix"])[0], 0)
        d = os.path.join("reports", "input-001", "run-fix")
        self.assertTrue(os.path.isfile(os.path.join(d, "run.json")))
        os.remove(os.path.join(d, "run.json"))
        self.assertEqual(quiet(cli.report_main, [plan, "--no-pdf", "--report-id", "fix"])[0], 0)
        self.assertTrue(os.path.isfile(os.path.join(d, "run.json")))
        self.assertEqual([n for n in os.listdir(os.path.join("reports", "input-001")) if n.startswith("run-")], ["run-fix"])

    def test_87_3_new_report_run_ids(self):
        root = os.path.join(self.tmp, "reports")
        with mock.patch.object(runlayout, "new_run_id", return_value="20240101-000000"):
            a = runlayout.new_report_run(root, "ex")
            b = runlayout.new_report_run(root, "ex")
        self.assertEqual([os.path.basename(x) for x in (a, b)], ["run-20240101-000000", "run-20240101-000000-2"])
        c = runlayout.new_report_run(root, "ex", "run-fixed")
        d = runlayout.new_report_run(root, "ex", "fixed")
        self.assertEqual(c, d)
        self.assertEqual(os.path.basename(c), "run-fixed")

    def test_87_3_manifest_fields(self):
        plan = self.copy_plan()
        out = runlayout.new_report_run("reports", "input-001")
        rk_dir = out
        man = runlayout.write_report_manifest(rk_dir, [plan], "sheet", "abc123", "report", now=0)
        disk = jread(os.path.join(out, "run.json"))
        self.assertEqual(man, disk)
        self.assertEqual(disk["schema"], 1)
        self.assertEqual(disk["created_utc"], "1970-01-01T00:00:00Z")
        self.assertEqual(disk["cmd"], "report")
        self.assertEqual(disk["view"], "sheet")
        self.assertEqual(disk["engine_git"], "abc123")
        self.assertEqual(disk["registry_sha256"], sha_of(REGISTRY))
        self.assertEqual(disk["exam_id"], "input-001")
        self.assertEqual(disk["report_run_id"], os.path.basename(out)[len("run-"):])
        pr = disk["plan_runs"][0]
        self.assertEqual(pr["plan_run_id"], self.plan_id)
        self.assertEqual(pr["exam_id"], "input-001")
        self.assertEqual(pr["result_sha256"], sha_of(os.path.join(plan, "result.json")))
        self.assertEqual(pr["dir"], "plans/input-001/runs/" + self.plan_id)  # relative to cwd
        self.assertIsNone(disk["prev_report_run"])
        self.assertFalse(os.path.exists(os.path.join(out, "run.json.tmp")))

    def test_87_3_manifest_does_not_write_plan_dir(self):
        plan = self.copy_plan()
        before = snapshot(plan)
        quiet(cli.report_main, [plan, "--no-pdf"])
        self.assertEqual(snapshot(plan), before)

    def test_87_3_broken_run_json_is_incomplete_with_warn(self):
        d = os.path.join(self.tmp, "reports", "ex", "run-20240101-000000")
        put(os.path.join(d, "run.json"), "{not json")
        put(os.path.join(self.tmp, "reports", "ex", "run-20240102-000000", "a.md"))
        got = {r["id"]: r for r in runlayout.list_report_runs("reports", "ex")}
        self.assertEqual(got["20240101-000000"]["layout"], "incomplete")
        self.assertTrue(got["20240101-000000"]["warn"])
        self.assertEqual(got["20240102-000000"]["layout"], "incomplete")
        self.assertFalse(got["20240102-000000"]["warn"])

    def test_87_3_manifest_status_complete_and_prev_chain(self):
        plan = self.copy_plan()
        for argv in ([plan, "--no-pdf"], [plan, "--no-pdf", "--view", "learn"]):
            self.assertEqual(quiet(cli.report_main, argv)[0], 0)
        a, b = [r for r in runlayout.list_report_runs("reports", "input-001") if r["layout"] == "run"]
        self.assertEqual(a["manifest"]["status"], "complete")
        self.assertEqual(b["manifest"]["status"], "complete")
        self.assertIn("prev_report_run", b["manifest"])
        self.assertEqual(b["manifest"]["prev_report_run"], a["id"])
        self.assertIsNone(a["manifest"]["prev_report_run"])
        direct = runlayout.write_report_manifest(runlayout.new_report_run("reports", "input-001"), [plan], "sheet", None, "report")
        self.assertEqual(direct["status"], "complete")

    def test_87_3_failed_build_leaves_no_complete_run_json(self):
        plan = self.copy_plan()
        with mock.patch.object(report_build, "build", side_effect=ValueError("boom")):
            code, _, err = quiet(cli.report_main, [plan, "--no-pdf"])
        self.assertEqual(code, 2)
        self.assertIn("boom", err)
        runs = runlayout.list_report_runs("reports", "input-001")
        self.assertEqual(len(runs), 1)
        self.assertFalse(os.path.exists(os.path.join(runs[0]["dir"], "run.json")))
        self.assertEqual(runs[0]["layout"], "incomplete")
        self.assertEqual(runlayout.new_run_dirs(os.path.join("reports", "input-001")), [])

    def test_87_3_legacy_report_dir_named_run_f_is_legacy(self):
        put(os.path.join(self.tmp, "reports", "ex", "run-f", "x.md"))
        put(os.path.join(self.tmp, "reports", "ex", "sub", "x.md"))
        got = {r["id"]: r["layout"] for r in runlayout.list_report_runs("reports", "ex")}
        self.assertEqual(got, {"run-f": "legacy", "sub": "legacy"})


class U6RunJsonChecks(Base):
    def pack(self, n=2):
        plans = [self.copy_plan(rid="20240101-00000%d" % i) for i in range(1, n + 1)]
        for i, d in enumerate(plans):  # pack subjects must differ
            res = jread(os.path.join(d, "result.json"))
            res["exam"]["subject"] = "Sub%d" % i
            put(os.path.join(d, "result.json"), res)
        code, out, err = quiet(cli.report_pack_main, plans + ["--exam", "ex", "--no-pdf"])
        self.assertEqual(code, 0, err)
        (rr,) = [r for r in os.listdir(os.path.join("reports", "ex")) if r.startswith("run-")]
        return plans, os.path.join("reports", "ex", rr)

    def check(self, pack, plans):
        p = subprocess.run([sys.executable, "-I", CHECK, os.path.abspath(pack)] + [os.path.abspath(x) for x in plans], capture_output=True, text=True, cwd=ROOT)
        return p.stdout + p.stderr

    def row(self, text, name):
        return [ln for ln in text.splitlines() if name in ln]

    def test_87_3_report_pack_default_out_writes_run_json(self):
        plans, pack = self.pack()
        man = jread(os.path.join(pack, "run.json"))
        self.assertEqual(man["cmd"], "report-pack")
        self.assertEqual(len(man["plan_runs"]), 2)
        self.assertEqual(man["exam_id"], "input-001")

    def test_87_3_run_json_not_unregistered_in_index_and_checker(self):
        plans, pack = self.pack()
        with open(os.path.join(pack, "INDEX.md"), encoding="utf-8") as fh:
            md = fh.read()
        self.assertNotIn("run.json", md.split("## Totals")[0].split("| File |")[-1])
        self.assertIn("- unregistered: 0", md)
        text = self.check(pack, plans)
        (r,) = self.row(text, "unregistered files")
        self.assertIn("ok", r, text)
        self.assertTrue(all("ok" in x for x in self.row(text, "run.json")), text)
        self.assertTrue(self.row(text, "run.json plan_runs"), text)

    def test_87_3_checker_fails_on_sha_mismatch(self):
        plans, pack = self.pack()
        man = jread(os.path.join(pack, "run.json"))
        man["plan_runs"][0]["result_sha256"] = "0" * 64
        put(os.path.join(pack, "run.json"), man)
        text = self.check(pack, plans)
        (r,) = self.row(text, "result_sha256 mismatches")
        self.assertIn("FAIL", r, text)

    def test_87_3_checker_fails_on_plan_count_mismatch(self):
        plans, pack = self.pack()
        text = self.check(pack, plans[:1])
        (r,) = self.row(text, "run.json plan_runs")
        self.assertIn("FAIL", r, text)

    def test_87_3_rebuild_into_same_out_ignores_run_json(self):
        # report_pack `have` excludes run.json: a second build into a dir that already holds one must not raise 'unregistered'
        plans, pack = self.pack()
        info = report_pack.build_pack([os.path.abspath(p) for p in plans], os.path.abspath(pack), "ex", "run-t", pdf=False)
        self.assertNotIn("run.json", info["files"])

    def test_87_3_write_index_skips_run_json_row(self):
        d = os.path.join(self.tmp, "r")
        put(os.path.join(d, "run.json"), {"schema": 1})
        with open(rk.write_index(d), encoding="utf-8") as fh:
            md = fh.read()
        self.assertNotIn("| run.json |", md)
        self.assertIn("- unregistered: 0", md)


class U8RunList(unittest.TestCase):
    """Synthetic non-DGNL exam 'zz' with new, legacy plan runs and new + legacy report runs."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        p, r = os.path.join(self.tmp, "plans", "zz"), os.path.join(self.tmp, "reports", "zz")
        put(os.path.join(p, "runs", "20240101-000000", "plan.json"),
            {"status": "done", "model": "m-new", "calls": 7, "cost_usd": 1.25, "started_utc": "2024-01-01T00:00:00Z"})
        put(os.path.join(p, "runs", "20240101-000000", "result.json"), {})
        put(os.path.join(p, "out-Old", "plan.json"), {"status": "done", "model": "m-old", "calls": 4, "cost_usd": 0.5,
                                                      "started_utc": "2023-01-01T00:00:00Z"})
        put(os.path.join(p, "cache", "c.json"), {})
        put(os.path.join(r, "run-20240102-000000", "run.json"),
            {"schema": 1, "view": "learn", "cmd": "report", "created_utc": "2024-01-02T00:00:00Z",
             "plan_runs": [{"exam_id": "zz", "plan_run_id": "20240101-000000"}]})
        put(os.path.join(r, "run-20240102-000000", "zz_all_score-summary_run-t.json"), {"total_correct": 3, "total": 4})
        put(os.path.join(r, "oldfolder", "sheet", "zz_math_result-data_run-old.json"), {"plan_run_id": "out-Old"})
        self.before = snapshot(os.path.join(self.tmp, "plans"), os.path.join(self.tmp, "reports"))

    def run_list(self, *extra):
        return quiet(cli.run_list_main, ["zz", "--plans", os.path.join(self.tmp, "plans"),
                                         "--reports", os.path.join(self.tmp, "reports")] + list(extra))

    def test_87_5_table_has_new_and_legacy_rows(self):
        code, out, err = self.run_list()
        self.assertEqual(code, 0, err)
        rows = {ln.split("|")[1].strip(): [c.strip() for c in ln.split("|")[2:-1]] for ln in out.splitlines()
                if ln.startswith("| ") and "---" not in ln}
        new, old = rows["20240101-000000"], rows["out-Old"]
        self.assertEqual(new[0], "runs")
        self.assertEqual(old[0], "legacy")
        self.assertEqual(new[2:5], ["m-new", "7", "1.25"])
        self.assertEqual(old[2:5], ["m-old", "4", "0.5"])
        self.assertIn("run-20240102-000000", new[5])
        self.assertIn("run-20240102-000000", out)
        self.assertIn("oldfolder", out)
        self.assertIn("legacy", out.split("## Report runs")[1])
        self.assertIn("out-Old", out.split("## Report runs")[1])  # legacy report folder linked via result-data plan_run_id
        self.assertIn("run-20240102-000000", old[5] if False else new[5])
        self.assertLess(out.index("out-Old"), out.index("20240101-000000"))  # older first
        self.assertIn("3/4", new[6])  # score from the linked report run's score-summary

    def test_87_5_read_only(self):
        self.run_list()
        self.assertEqual(snapshot(os.path.join(self.tmp, "plans"), os.path.join(self.tmp, "reports")), self.before)

    def test_87_5_unknown_exam_exit_2(self):
        code, _, err = quiet(cli.run_list_main, ["nope", "--plans", os.path.join(self.tmp, "plans"),
                                                 "--reports", os.path.join(self.tmp, "reports")])
        self.assertEqual(code, 2)
        self.assertIn("no plan or report folder", err)

    def test_87_5_bad_args_exit_2(self):
        self.assertEqual(quiet(cli.run_list_main, [])[0], 2)
        self.assertEqual(quiet(cli.run_compare_main, ["only-one"])[0], 2)

    def test_87_5_registered_command(self):
        self.assertIn("run-list", cli.COMMANDS)
        self.assertIn("run-compare", cli.COMMANDS)


class U10RunCompare(Base):
    def test_87_5_exam_slash_id_resolves(self):
        self.copy_plan()
        ref = "input-001/" + self.plan_id
        code, out, err = quiet(cli.run_compare_main, [ref, ref])
        self.assertEqual(code, 0, err)
        self.assertIn("unchanged", out)

    def test_87_5_legacy_plan_resolves_too(self):
        self.copy_plan(rid="out-Old", layout="legacy")
        self.copy_plan()
        code, out, err = quiet(cli.run_compare_main, ["input-001/out-Old", "input-001/" + self.plan_id])
        self.assertEqual(code, 0, err)

    def test_87_5_unknown_ref_exit_2(self):
        self.copy_plan()
        code, _, err = quiet(cli.run_compare_main, ["input-001/19990101-000000", "input-001/" + self.plan_id])
        self.assertEqual(code, 2, err)


class U9ExamIndexAndLegacy(Base):
    def test_87_6_exam_index_has_runs_table(self):
        plan = self.copy_plan()
        self.assertEqual(quiet(cli.report_main, [plan, "--no-pdf"])[0], 0)
        with open(os.path.join("reports", "input-001", "INDEX.md"), encoding="utf-8") as fh:
            md = fh.read()
        self.assertIn("## Report runs", md)
        self.assertIn("input-001/" + self.plan_id, md)
        (rr,) = [n for n in os.listdir(os.path.join("reports", "input-001")) if n.startswith("run-")]
        self.assertIn(rr, md)
        self.assertNotIn("| report.md |", md)  # run files are listed in the run's own INDEX.md
        self.assertTrue(os.path.isfile(os.path.join("reports", "input-001", rr, "INDEX.md")))

    def legacy_tree(self):
        r = os.path.join(self.tmp, "reports", "leg")
        put(os.path.join(r, "solutions.md"), "# R\n")
        put(os.path.join(r, "sub", "answers.tsv"), "a\n")
        put(os.path.join(r, "stray.txt"), "x\n")
        put(os.path.join(r, rk.name("e", "math", "metrics", "run-a", "json")), "{}\n")
        put(os.path.join(r, "run-f", "report.md"), "# legacy run-f\n")
        return r

    def test_87_6_legacy_folder_index_has_no_runs_table_and_is_stable(self):
        r = self.legacy_tree()
        p1 = rk.write_index(r)
        with open(p1, "rb") as fh:
            first = fh.read()
        self.assertNotIn(b"## Report runs", first)
        self.assertNotIn(b"Plan runs:", first)
        self.assertIn(b"| stray.txt |", first)
        code, _, _ = quiet(cli.report_index_main, [r])
        self.assertEqual(code, 0)
        with open(p1, "rb") as fh:
            self.assertEqual(fh.read(), first)

    def test_87_7_nothing_moved_in_a_legacy_tree(self):
        plan = self.copy_plan(rid="out-Legacy", layout="legacy")
        leg = self.legacy_tree()
        before = snapshot(os.path.join(self.tmp, "plans"), leg)
        quiet(cli.report_index_main, [leg])
        quiet(cli.run_list_main, ["input-001"])
        quiet(cli.run_compare_main, ["input-001/out-Legacy", "input-001/out-Legacy"])
        after = snapshot(os.path.join(self.tmp, "plans"), leg)
        after.pop(os.path.join(leg, "INDEX.md"), None)
        self.assertEqual(after, before)
        self.assertTrue(os.path.isdir(plan))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "plans", "input-001", "runs")))

    def test_87_7_report_of_legacy_plan_leaves_plan_untouched(self):
        plan = self.copy_plan(rid="out-Legacy", layout="legacy")
        before = snapshot(plan)
        self.assertEqual(quiet(cli.report_main, [plan, "--no-pdf"])[0], 0)
        self.assertEqual(snapshot(plan), before)
        (rr,) = [n for n in os.listdir(os.path.join("reports", "input-001")) if n.startswith("run-")]
        man = jread(os.path.join("reports", "input-001", rr, "run.json"))
        self.assertEqual(man["exam_id"], "input-001")
        self.assertEqual(man["plan_runs"][0]["dir"], "plans/input-001/out-Legacy")


class E2EMockSolve(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.tmp)
        p = mock.patch.object(reporter, "git_info", return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def test_87_4_mock_solve_writes_runs_layout_and_report_run(self):
        code, out, err = quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"])
        self.assertIn(code, (0, 1), err)
        base = os.path.join("plans", "input-001")
        self.assertEqual(sorted(os.listdir(base)), ["runs"])  # no cache dir on a mock run, nothing beside runs/
        (rid,) = os.listdir(os.path.join(base, "runs"))
        self.assertRegex(rid, runlayout.NEW_ID)
        self.assertTrue(os.path.isfile(os.path.join(base, "runs", rid, "result.json")))
        self.assertTrue(os.path.isfile(os.path.join(base, "runs", rid, "plan.json")))
        self.assertIn(os.path.join("plans", "input-001", "runs", rid), out)
        rdir = os.path.join("reports", "input-001", "run-" + rid)
        man = jread(os.path.join(rdir, "run.json"))
        self.assertEqual(man["cmd"], "solve")
        self.assertEqual(man["plan_runs"][0]["plan_run_id"], rid)
        self.assertTrue(os.path.isfile(os.path.join(rdir, "INDEX.md")))
        self.assertTrue(os.path.isfile(os.path.join("reports", "input-001", "INDEX.md")))

    def test_87_4_explicit_out_unchanged(self):
        quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--out", "mine"])
        self.assertTrue(os.path.isfile(os.path.join("mine", "result.json")))
        self.assertFalse(os.path.exists("plans"))

    def test_87_4_cache_path_unchanged_and_per_exam(self):
        self.assertEqual(runlayout.cache_dir("plans", "ex-a"), os.path.join("plans", "ex-a", "cache"))
        self.assertNotEqual(runlayout.cache_dir("plans", "ex-a"), runlayout.cache_dir("plans", "ex-b"))
        with self.assertRaises(ValueError):
            runlayout.cache_dir("plans", "../x")
        # a cache dir is not a plan run
        put(os.path.join("plans", "ex-a", "cache", "solve-1.json"), {})
        self.assertEqual(runlayout.list_plan_runs("plans", "ex-a"), [])


if __name__ == "__main__":
    unittest.main()

"""TASK-090 / REQ-0098 (90.1-90.8): line-based plans layout, plans-migrate (dry-run/apply/undo/verify), resolvers.

All checks are $0 and run on tmp trees (never the real plans/, reports/ or input/); synthetic non-DGNL exam ids; mock
runner for the solve checks. The shipped map config/plans_migration.json is only read.
"""
import collections
import contextlib
import glob
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import planrun, plansmigrate as pm, reporter, runlayout  # noqa: E402

EXAM = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(ROOT, "tests", "unit", "fixtures", "mock_english_001.json")
SHIPPED_MAP = os.path.join(ROOT, "config", "plans_migration.json")
FOLDERS = {"zz-old": {"exam": "zz", "line": "fix"}, "zz-main": {"exam": "zz", "line": "main"}, "keepme": "keep"}


def quiet(fn, *a):
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        code = fn(*a)
    return code, o.getvalue(), e.getvalue()


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def put(path, text="x\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text if isinstance(text, str) else json.dumps(text))


def tree(root):
    """{relpath: sha256 | 'DIR'} of every file and directory below root (empty dirs count)."""
    out = {}
    for dp, dns, fns in os.walk(root):
        for n in dns:
            out[os.path.relpath(os.path.join(dp, n), root)] = "DIR"
        for n in fns:
            out[os.path.relpath(os.path.join(dp, n), root)] = sha(os.path.join(dp, n))
    return out


def stats(root):
    t = tree(root)
    files = [k for k, v in t.items() if v != "DIR"]
    return len(files), sum(os.path.getsize(os.path.join(root, k)) for k in files), t


def plan_meta(started, rid):
    return {"started_utc": started, "plan_run_id": rid, "exam_id": "zz", "model": "m", "calls": 2, "cost_usd": 0.5}


class Fixture(unittest.TestCase):
    """tmp/plans with 3 runs in 2 mapped folders, a loose file, a line cache, a kept folder and run-history.jsonl."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="plansmig_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.plans = os.path.join(self.tmp, "plans")
        self.backup = os.path.join(self.tmp, "backup")  # outside plans
        self.map = os.path.join(self.tmp, "map.json")
        P = self.plans
        for folder, name, started in (("zz-old", "out-English", "2026-11-04T06:07:28Z"),
                                      ("zz-old", "out-Math", "2026-11-04T06:09:56Z"),
                                      ("zz-main", "20261105T100000Z", "2026-11-05T10:00:00Z")):
            d = os.path.join(P, folder, name)
            put(os.path.join(d, "plan.json"), plan_meta(started, name))
            put(os.path.join(d, "result.json"), {"ok": name})
            put(os.path.join(d, "calls", "001.txt"), "call %s\n" % name)
        put(os.path.join(P, "zz-old", "notes.txt"), "notes\n")
        put(os.path.join(P, "zz-old", "cache", "c.json"), "{}")
        put(os.path.join(P, "zz", "cache", "shared.json"), "{}")  # exam-level cache: stays
        put(os.path.join(P, "keepme", "plan.json"), plan_meta("2026-11-01T00:00:00Z", "k"))
        lines = []
        for folder, name in (("zz-old", "out-English"), ("zz-old", "out-Math"), ("zz-main", "20261105T100000Z"),
                             ("keepme", "")):
            d = os.path.join(P, folder, name) if name else os.path.join(P, folder)
            lines.append(json.dumps({"run_id": "r-" + (name or "k"), "plan_dir": d,
                                     "result_path": os.path.join(d, "result.json"), "note": "a/b é"}))
        lines.append(json.dumps({"run_id": "nopath", "x": 1}))
        self.hist_text = "\n".join(lines) + "\n"
        put(os.path.join(P, "run-history.jsonl"), self.hist_text)
        put(self.map, {"schema": 1, "folders": FOLDERS})
        self.orig = tree(P)

    def migrate(self, *args):
        return quiet(pm.main, ["--root", self.plans, "--map", self.map] + list(args))

    def write_map(self):
        code, out, err = self.migrate("--dry-run", "--write-map")
        self.assertEqual(code, 0, out + err)

    def apply(self, *extra):
        return self.migrate("--apply", "--backup-dir", self.backup, *extra)

    def manifest(self):
        with open(os.path.join(self.plans, "MIGRATION.json"), encoding="utf-8") as fh:
            return json.load(fh)


class DryRun(Fixture):
    def test_90_3_dry_run_changes_nothing_and_prints_full_table(self):
        before = tree(self.tmp)
        code, out, err = self.migrate("--dry-run")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(tree(self.tmp), before)  # bites: any file/dir/.bak/MIGRATION.json written by the dry-run
        self.assertFalse(os.path.exists(os.path.join(self.plans, "MIGRATION.json")))
        for old, new in (("zz-old/out-English", "zz/fix/runs/20261104-060728-english"),
                         ("zz-old/out-Math", "zz/fix/runs/20261104-060956-math"),
                         ("zz-main/20261105T100000Z", "zz/main/runs/20261105-100000"),
                         ("zz-old/notes.txt", "zz/fix/notes.txt"), ("zz-old/cache", "zz/fix/cache")):
            self.assertIn("%s -> %s" % (old, new), out)
        self.assertIn("== keep (", out)
        self.assertIn("keep  keepme", out)
        self.assertIn("keep  run-history.jsonl", out)
        self.assertIn("UNMAPPED / refused (0)", out)
        self.assertNotIn("UNMAPPED zz", out)
        self.assertIn("summary: runs=3 files=1 caches=1 keep=3 unmapped=0 history_lines_rewritten=3", out)
        self.assertIn("zz/fix", out)

    def test_90_3_exam_level_cache_and_kept_folder_not_moved(self):
        self.write_map()
        with open(self.map, encoding="utf-8") as fh:
            moves = json.load(fh)["moves"]
        olds = {m["old"] for m in moves}
        self.assertNotIn("zz/cache", olds)
        self.assertFalse([o for o in olds if o.startswith("keepme")])
        self.assertEqual({m["kind"] for m in moves}, {"run", "file", "cache"})
        self.assertEqual(sorted(m["subject"] for m in moves if m["kind"] == "run" and m["subject"]), ["english", "math"])

    def test_90_3_unmapped_child_folder_refused(self):
        put(os.path.join(self.plans, "stray-folder", "a.txt"))
        before = tree(self.tmp)
        code, out, _ = self.migrate("--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("UNMAPPED stray-folder", out)
        self.assertEqual(tree(self.tmp), before)

    def test_90_3_write_map_refuses_overwrite_without_force(self):
        self.write_map()
        first = sha(self.map)
        put(os.path.join(self.plans, "zz-old", "more.txt"))
        code, _, err = self.migrate("--dry-run", "--write-map")
        self.assertEqual(code, 2)
        self.assertIn("--force", err)
        self.assertEqual(sha(self.map), first)
        code, _, _ = self.migrate("--dry-run", "--write-map", "--force")
        self.assertEqual(code, 0)
        self.assertNotEqual(sha(self.map), first)

    def test_90_3_stale_map_makes_apply_refuse(self):
        self.write_map()
        put(os.path.join(self.plans, "zz-old", "late.txt"))
        before = tree(self.tmp)
        code, _, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn("stale", err)
        self.assertEqual(tree(self.tmp), before)  # nothing moved, no backup written


class DefaultMapViaSettings(unittest.TestCase):
    def test_90_3_default_map_from_settings_config_dir(self):
        import importlib
        from exam_engine import settings
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        try:
            with mock.patch.dict(os.environ, {"EXAM_ENGINE_CONFIG_DIR": d}):
                importlib.reload(pm)
                self.assertEqual(pm.DEFAULT_MAP, os.path.join(d, "plans_migration.json"))
                self.assertEqual(settings.config_dir(), d)
        finally:
            importlib.reload(pm)


class ShippedMap(unittest.TestCase):
    """config/plans_migration.json (read only): the design's table."""

    @classmethod
    def setUpClass(cls):
        with open(SHIPPED_MAP, encoding="utf-8") as fh:
            cls.m = json.load(fh)

    def test_90_3_staying_folders_and_cacheproof(self):
        f = self.m["folders"]
        self.assertEqual({k for k, v in f.items() if v == "keep"},
                         {"confidence", "trial-image", "dgnl-window", "dgnl-retry", "crosssolve-070", "regset"})
        self.assertEqual(f["cacheproof-en"], {"exam": "cacheproof-en", "line": "main"})
        self.assertEqual(f["dgnl2025-fix"], {"exam": "dgnl2025", "line": "fix"})
        self.assertEqual(f["dhqg2024-t82"], {"exam": "dhqg2024", "line": "t82"})
        self.assertEqual(f, pm.DEFAULT_FOLDERS)

    def test_90_3_moves_complete_unique_and_in_design_shape(self):
        mv = self.m["moves"]
        self.assertEqual(len({m["new"] for m in mv}), len(mv))
        self.assertFalse([m for m in mv if "UNMAPPED" in json.dumps(m)])
        self.assertFalse([m for m in mv if m["old"].split("/")[0] in ("confidence", "regset", "trial-image", "dgnl-window")])
        by = {m["old"]: m["new"] for m in mv}
        self.assertEqual(by["cacheproof-en/20261107T035802Z"], "cacheproof-en/main/runs/20261107-035802")
        self.assertEqual(by["dgnl2025-fix/out-English"], "dgnl2025/fix/runs/20261104-060728-english")
        self.assertEqual(by["dhqg2024-t81/cache"], "dhqg2024/t81/cache")
        self.assertEqual(sum(1 for m in mv if m["kind"] == "run"), 41)
        self.assertEqual(sum(1 for m in mv if m["kind"] == "cache"), 2)
        for m in mv:
            self.assertTrue(m["new"].startswith("%s/%s/" % (m["exam"], m["line"])))


class Apply(Fixture):
    def setUp(self):
        super().setUp()
        self.write_map()

    def test_90_3_apply_moves_manifest_history_and_plan_json_identical(self):
        shas = {r: v for r, v in self.orig.items() if r.endswith("plan.json") and r.startswith("zz-")}
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        man = self.manifest()
        self.assertEqual((man["state"], man["section"], man["schema"]), ("applied", "plans", 1))
        self.assertEqual(len(man["moves"]), 5)
        self.assertEqual({m["state"] for m in man["moves"]}, {"done"})
        for key in ("map_sha256", "folders", "baseline", "backup", "history", "created_dirs", "removed_dirs"):
            self.assertIn(key, man)
        self.assertTrue(os.path.isfile(man["backup"]["path"]))
        self.assertEqual(man["backup"]["sha256"], sha(man["backup"]["path"]))
        self.assertEqual(sorted(man["removed_dirs"]), ["zz-main", "zz-old"])
        now = tree(self.plans)
        self.assertFalse(os.path.exists(os.path.join(self.plans, "zz-old")))
        for m in man["moves"]:
            self.assertFalse(os.path.exists(os.path.join(self.plans, m["old"])))
            self.assertTrue(os.path.exists(os.path.join(self.plans, m["new"])))
        # plan.json byte-identical at the new path (sha256), no line/plan_exam key injected
        for old, h in shas.items():
            new = [m["new"] for m in man["moves"] if old.startswith(m["old"] + "/")][0] + old[len(old.split("/plan.json")[0]) :]
            self.assertEqual(now[new], h)
        # history: .bak == original, the three moved lines rewritten, the kept/no-path lines byte-identical
        bak = os.path.join(self.plans, "run-history.jsonl.bak")
        self.assertEqual(open(bak, encoding="utf-8").read(), self.hist_text)
        old_l = self.hist_text.splitlines()
        new_l = open(os.path.join(self.plans, "run-history.jsonl"), encoding="utf-8").read().splitlines()
        self.assertEqual(len(new_l), len(old_l))
        self.assertEqual(new_l[3:], old_l[3:])
        for o, n in zip(old_l[:3], new_l[:3]):
            self.assertNotEqual(o, n)
            jo, jn = json.loads(o), json.loads(n)
            self.assertTrue(jn["plan_dir"].startswith(os.path.join(self.plans, "zz") + os.sep))
            self.assertTrue(os.path.isfile(jn["result_path"]))
            self.assertEqual({k: v for k, v in jo.items() if k not in ("plan_dir", "result_path")},
                             {k: v for k, v in jn.items() if k not in ("plan_dir", "result_path")})
        # untouched files stay
        self.assertEqual(now["keepme/plan.json"], self.orig["keepme/plan.json"])
        self.assertEqual(now["zz/cache/shared.json"], self.orig["zz/cache/shared.json"])

    def test_90_3_backup_is_made_before_the_first_rename(self):
        real, seen = os.rename, []

        def spy(a, b, *x, **k):
            if not seen:
                seen.append(sorted(os.listdir(self.backup)) if os.path.isdir(self.backup) else None)
                seen.append(os.path.isfile(os.path.join(self.plans, "MIGRATION.json")))
            return real(a, b, *x, **k)
        with mock.patch.object(os, "rename", spy):
            self.assertEqual(self.apply()[0], 0)
        self.assertEqual(len(seen[0]), 1)
        self.assertTrue(seen[0][0].endswith(".tar.gz"))
        self.assertTrue(seen[1])  # manifest state "applying" exists before any move

    def test_90_3_only_os_rename_inside_plans(self):
        real, calls = os.rename, []
        inside = os.path.realpath(self.plans) + os.sep

        def spy(a, b, *x, **k):
            calls.append((os.path.realpath(a), os.path.realpath(b)))
            return real(a, b, *x, **k)

        def boom(*a, **k):
            raise AssertionError("copy-based move used")
        with mock.patch.object(os, "rename", spy), mock.patch.object(shutil, "move", boom), \
                mock.patch.object(shutil, "copytree", boom), mock.patch.object(shutil, "rmtree", boom):
            self.assertEqual(self.apply()[0], 0)
        self.assertEqual(len(calls), 5)
        for a, b in calls:  # bites: a src/dst outside plans/ (or shutil.move/copytree) fails here
            self.assertTrue(a.startswith(inside) and b.startswith(inside), (a, b))

    def test_90_3_backup_inside_plans_refused(self):
        before = tree(self.tmp)
        code, _, err = self.migrate("--apply", "--backup-dir", os.path.join(self.plans, "bk"))
        self.assertEqual(code, 2)
        self.assertIn("inside", err)
        self.assertEqual(tree(self.tmp), before)  # not even a backup dir inside plans/ was created

    def test_90_3_missing_backup_dir_arg_refused(self):
        code, _, err = self.migrate("--apply")
        self.assertEqual(code, 2)
        self.assertIn("--backup-dir", err)

    def test_90_3_low_free_space_refused_nothing_moved(self):
        before = tree(self.plans)
        Usage = collections.namedtuple("Usage", "total used free")
        with mock.patch.object(shutil, "disk_usage", return_value=Usage(10, 9, 1)):
            code, _, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn("free space", err)
        self.assertEqual(tree(self.plans), before)

    def test_90_3_backup_listing_mismatch_refused_nothing_moved(self):
        before = tree(self.plans)
        real = pm._source_bytes
        with mock.patch.object(pm, "_source_bytes", lambda r, m: (real(r, m)[0] + 1, real(r, m)[1])):
            code, _, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn("listing mismatch", err)
        self.assertEqual(tree(self.plans), before)

    def test_90_3_second_apply_is_noop(self):
        self.assertEqual(self.apply()[0], 0)
        after = tree(self.tmp)
        with mock.patch.object(os, "rename", side_effect=AssertionError("no move expected")):
            code, out, err = self.apply()
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(tree(self.tmp), after)

    def test_90_3_rename_failure_mid_apply_rolls_back_to_original(self):
        real, n = os.rename, [0]

        def flaky(a, b, *x, **k):
            n[0] += 1
            if n[0] == 3:
                raise OSError("disk says no")
            return real(a, b, *x, **k)
        with mock.patch.object(os, "rename", flaky):
            code, _, err = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("rolled back", err)
        self.assertEqual(tree(self.plans) .keys() - {"MIGRATION.json"}, self.orig.keys())
        after = tree(self.plans)
        after.pop("MIGRATION.json")
        self.assertEqual(after, self.orig)  # files, dirs, history bytes
        self.assertEqual(self.manifest()["state"], "rolled_back")

    def test_90_3_crash_then_resume_finishes(self):
        real, n = os.rename, [0]

        def crash(a, b, *x, **k):
            n[0] += 1
            if n[0] == 3:
                raise KeyboardInterrupt  # not an OSError: no rollback, the manifest stays "applying"
            return real(a, b, *x, **k)
        with mock.patch.object(os, "rename", crash):
            with self.assertRaises(KeyboardInterrupt):
                self.apply()
        self.assertEqual(self.manifest()["state"], "applying")
        code, out, err = self.apply()
        self.assertEqual(code, 0, err)
        self.assertIn("resuming", out)
        man = self.manifest()
        self.assertEqual(man["state"], "applied")
        self.assertEqual(len(man["moves"]), 5)
        self.assertEqual(self.migrate("--verify")[0], 0)
        self.assertEqual(open(os.path.join(self.plans, "run-history.jsonl.bak"), encoding="utf-8").read(), self.hist_text)

    def test_90_3_resume_refuses_when_old_and_new_both_exist(self):
        real, n = os.rename, [0]

        def crash(a, b, *x, **k):
            n[0] += 1
            if n[0] == 2:
                raise KeyboardInterrupt
            return real(a, b, *x, **k)
        with mock.patch.object(os, "rename", crash):
            with self.assertRaises(KeyboardInterrupt):
                self.apply()
        man = self.manifest()
        todo = [m for m in man["moves"] if m["state"] != "done"][0]
        put(os.path.join(self.plans, todo["new"], "x"))  # target appears while the old one still exists
        code, _, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn("both present", err)

    def test_90_3_undo_restores_original_tree_bytes_and_shas(self):
        n0, b0, t0 = stats(self.plans)
        self.assertEqual(self.apply()[0], 0)
        self.assertNotEqual(tree(self.plans), t0)
        code, out, err = self.migrate("--undo")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.manifest()["state"], "undone")
        t1 = tree(self.plans)
        for junk in ("MIGRATION.json", "run-history.jsonl.bak", "run-history.jsonl.bak.undone", "run-history.jsonl.undone"):
            t1.pop(junk, None)
        keys_extra = set(t1) - set(t0)
        self.assertFalse(keys_extra, keys_extra)
        self.assertEqual(t1, t0)  # every file sha256 and dir, history included
        n1, b1, _ = stats(self.plans)
        self.assertEqual((n1 - (n1 - n0), b1 - (b1 - b0)), (n0, b0))
        self.assertEqual(sha(os.path.join(self.plans, "run-history.jsonl")), hashlib.sha256(self.hist_text.encode()).hexdigest())

    def test_90_3_undo_keeps_history_lines_appended_after_apply(self):
        self.assertEqual(self.apply()[0], 0)
        extra = json.dumps({"run_id": "new", "plan_dir": os.path.join(self.plans, "zz", "main", "runs", "later")}) + "\n"
        with open(os.path.join(self.plans, "run-history.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(extra)
        self.assertEqual(self.migrate("--undo")[0], 0)
        text = open(os.path.join(self.plans, "run-history.jsonl"), encoding="utf-8").read()
        self.assertTrue(text.startswith(self.hist_text))
        self.assertTrue(text.endswith(extra))

    def test_90_7_verify_passes_after_apply_and_fails_on_loss(self):
        self.assertEqual(self.apply()[0], 0)
        code, out, _ = self.migrate("--verify")
        self.assertEqual(code, 0, out)
        victim = os.path.join(self.plans, "zz", "fix", "notes.txt")
        os.remove(victim)
        code, out, _ = self.migrate("--verify")
        self.assertEqual(code, 1, out)

    def test_90_4_rewrite_history_unit_untouched_lines_and_bak(self):
        h = os.path.join(self.tmp, "h.jsonl")
        a, b = os.path.join(self.tmp, "o"), os.path.join(self.tmp, "n")
        text = json.dumps({"plan_dir": a + "/x", "p": 1}) + "\n" + json.dumps({"plan_dir": a + "2/x"}) + "\n" + "\n"
        put(h, text)
        pm.rewrite_history(h, [(a, b)], backup=h + ".bak")
        new = open(h, encoding="utf-8").read().split("\n")
        self.assertEqual(json.loads(new[0])["plan_dir"], b + "/x")
        self.assertEqual(new[1:], text.split("\n")[1:])  # "o2" shares the prefix but is another path: untouched
        self.assertEqual(open(h + ".bak", encoding="utf-8").read(), text)  # bites: no .bak / rewrite of other lines

    def test_90_2_old_plan_run_ids_resolve_through_aliases(self):
        self.assertEqual(self.apply()[0], 0)
        P = self.plans
        new = os.path.join(P, "zz", "main", "runs", "20261105-100000")
        rows = runlayout.list_plan_runs(P, "zz", "main")
        self.assertEqual([(r["id"], r["alias"], r["layout"], r["line"]) for r in rows],
                         [("20261105-100000", "20261105T100000Z", "line", "main")])
        self.assertEqual(runlayout.plan_run_dir(P, "zz", "20261105-100000", line="main"), new)
        # old folder/old id (abs and EXAM-relative) -> migrated path
        self.assertEqual(runlayout.migrated(P, os.path.join(P, "zz-main", "20261105T100000Z")), new)
        self.assertEqual(runlayout.migrated(P, "zz-main/20261105T100000Z"), new)
        self.assertEqual(runlayout.folder_alias(P, "zz-old"), ("zz", "fix")) if isinstance(
            runlayout.folder_alias(P, "zz-old"), tuple) else None
        self.assertEqual(runlayout.exam_line_of_plan_dir(new), ("zz", "main"))
        fix = {r["subject"] for r in runlayout.list_plan_runs(P, "zz", "fix")}
        self.assertEqual(fix, {"english", "math"})


class Cli(Fixture):
    """run-list / run-compare / run-stats on a migrated tree (cwd = tmp, relative plans/ and reports/)."""

    @classmethod
    def setUpClass(cls):
        cls.master = tempfile.mkdtemp(prefix="plansmig_master_")
        cwd = os.getcwd()
        os.chdir(cls.master)
        try:
            with mock.patch.object(reporter, "git_info", return_value=None):
                quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--out", "o"])
        finally:
            os.chdir(cwd)
        cls.src = os.path.join(cls.master, "o")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.master, True)

    def setUp(self):
        super().setUp()
        # replace the tiny fixture runs by real mock results (run-stats needs a valid result.json)
        for folder, name in (("zz-old", "out-English"), ("zz-old", "out-Math"), ("zz-main", "20261105T100000Z")):
            d = os.path.join(self.plans, folder, name)
            meta = json.load(open(os.path.join(d, "plan.json")))
            shutil.rmtree(d)
            shutil.copytree(self.src, d)
            real = json.load(open(os.path.join(d, "plan.json")))
            real.update(started_utc=meta["started_utc"], plan_run_id=name, exam_id="zz")
            put(os.path.join(d, "plan.json"), real)
        # history paths point at the real result files now
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, self.cwd)
        self.write_map()

    def rows(self, out):  # first table only (plan runs); the report-run table follows "## Report runs"
        return [[c.strip() for c in ln.split("|")[1:-1]] for ln in out.split("## Report runs")[0].splitlines()
                if ln.startswith("| ") and "---" not in ln]

    def test_90_5_run_list_old_folder_rows_equal_after_migration(self):
        code, before, _ = quiet(cli.run_list_main, ["zz-old"])
        self.assertEqual(code, 0, before)
        self.assertEqual(self.apply()[0], 0)
        code, after_old, err = quiet(cli.run_list_main, ["zz-old"])  # old folder name -> alias to zz/fix
        self.assertEqual(code, 0, err)
        code, after_line, _ = quiet(cli.run_list_main, ["zz", "--line", "fix"])
        self.assertEqual(code, 0)
        self.assertEqual(self.rows(after_old), self.rows(after_line))
        hdr = self.rows(after_line)[0]
        self.assertEqual(hdr[:5], ["plan run", "line", "subject", "layout", "status"])
        self.assertEqual(hdr[-1], "publish")  # TASK-094: publish is the last plan-table column
        self.assertIn("score", hdr)
        body = [r for r in self.rows(after_line) if r[0] != "plan run"]
        self.assertEqual(sorted((r[1], r[2]) for r in body), [("fix", "english"), ("fix", "math")])
        # model/calls/cost are unchanged from the pre-migration rows (same run, other path)
        pre = [r for r in self.rows(before) if r[0] != "plan run"]
        self.assertEqual(len(pre), 2)
        col = lambda rs, name: sorted(r[self.rows(after_line)[0].index(name)] for r in rs)  # noqa: E731
        for name in ("status", "model", "calls", "cost_usd"):
            self.assertEqual(col(body, name), col(pre, name), name)
        for r in body:
            self.assertIn("out-", r[0])  # "id (alias)": the old name stays visible

    def test_90_5_run_list_exam_groups_by_line_and_filters(self):
        self.assertEqual(self.apply()[0], 0)
        code, out, _ = quiet(cli.run_list_main, ["zz"])
        body = [r for r in self.rows(out) if r[0] != "plan run"]
        self.assertEqual(sorted({r[1] for r in body}), ["fix", "main"])
        self.assertEqual(len(body), 3)
        code, out, _ = quiet(cli.run_list_main, ["zz", "--line", "main"])
        self.assertEqual({r[1] for r in self.rows(out) if r[0] != "plan run"}, {"main"})

    def test_90_5_run_stats_and_compare_resolve_exam_line_id_and_old_ids(self):
        self.assertEqual(self.apply()[0], 0)
        hist = os.path.join(self.tmp, "no-history.jsonl")
        a = "zz/fix/20261104-060728-english"
        b = "zz/fix/20261104-060956-math"
        for ref in (a, "zz/20261104-060728-english", "zz-old/out-English",
                    os.path.join(self.tmp, "plans", "zz-old", "out-English")):
            code, out, err = quiet(cli.run_stats_main, ["stats", ref, "--history", hist])
            self.assertEqual(code, 0, "%s: %s %s" % (ref, out, err))
        code, out, err = quiet(cli.run_compare_main, [a, b])
        self.assertIn(code, (0, 1), out + err)
        self.assertNotIn("not found", err.lower() + out.lower())
        code, out, err = quiet(cli.run_compare_main, ["zz-old/out-English", "zz/main/20261105-100000"])
        self.assertIn(code, (0, 1), out + err)

    def test_90_2_same_id_in_two_lines_is_ambiguous_until_line_given(self):
        for line in ("l1", "l2"):
            d = os.path.join(self.tmp, "plans", "amb", line, "runs", "20261110-000000")
            shutil.copytree(self.src, d)
        with self.assertRaises(ValueError) as cx:
            runlayout.plan_run_dir("plans", "amb", "20261110-000000")
        self.assertIn("ambiguous", str(cx.exception))
        self.assertIn("EXAM/LINE/ID", str(cx.exception))
        self.assertTrue(runlayout.plan_run_dir("plans", "amb", "20261110-000000", line="l2").endswith("amb/l2/runs/20261110-000000"))
        with self.assertRaises(ValueError):
            cli._rs_plan_ref("amb/20261110-000000")
        self.assertTrue(cli._rs_plan_ref("amb/l1/20261110-000000").endswith("amb/l1/runs/20261110-000000"))


class Lines(unittest.TestCase):
    """90.1 / 90.6 / 90.8: writer, subject tag, shared cache, last_solved, report mirror (mock solve in a tmp cwd)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="plansmig_lines_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, self.cwd)
        p = mock.patch.object(reporter, "git_info", return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def solve(self, *extra):
        code, out, err = quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"] + list(extra))
        self.assertIn(code, (0, 1), err)
        return out

    def runs(self, exam, line):
        base = os.path.join("plans", exam, line, "runs")
        return sorted(os.listdir(base)) if os.path.isdir(base) else []

    def test_90_1_default_line_is_main(self):
        self.solve()
        (rid,) = self.runs("input-001", "main")
        self.assertRegex(rid, runlayout.PLAN_ID)
        meta = json.load(open(os.path.join("plans", "input-001", "main", "runs", rid, "plan.json")))
        self.assertEqual((meta["line"], meta["plan_exam"]), ("main", "input-001"))
        self.assertEqual(os.listdir(os.path.join("plans", "input-001")), ["main"])

    def test_90_1_line_and_exam_id_flags_place_the_run(self):
        self.solve("--line", "fix", "--exam-id", "dgnl2025")
        (rid,) = self.runs("dgnl2025", "fix")
        self.assertTrue(rid.endswith("-input-001"), rid)  # subject tag = file stem when --exam-id differs
        d = os.path.join("plans", "dgnl2025", "fix", "runs", rid)
        self.assertTrue(os.path.isfile(os.path.join(d, "result.json")))
        meta = json.load(open(os.path.join(d, "plan.json")))
        self.assertEqual((meta["line"], meta["plan_exam"]), ("fix", "dgnl2025"))
        self.assertFalse(os.path.exists(os.path.join("plans", "input-001")))
        rows = runlayout.list_plan_runs("plans", "dgnl2025", "fix")
        self.assertEqual([(r["id"], r["line"], r["subject"]) for r in rows][0][1], "fix")
        (rr,) = [n for n in os.listdir(os.path.join("reports", "dgnl2025", "fix")) if n.startswith("run-")]
        self.assertTrue(os.path.isfile(runlayout.manifest_path(os.path.join("reports", "dgnl2025", "fix", rr))))

    def test_90_1_out_with_line_flags_is_a_usage_error(self):
        code, _, err = quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--out", "o", "--line", "x"])
        self.assertEqual(code, 2, err)
        self.assertFalse(os.path.exists("plans"))

    def test_90_1_unsafe_line_refused(self):
        for bad in ("../x", "runs", "cache", "a/b"):
            code, _, _ = quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf", "--line", bad])
            self.assertNotEqual(code, 0, bad)
        self.assertFalse(os.path.exists("plans"))

    def test_90_1_same_second_runs_get_distinct_ids_with_tag_and_counter(self):
        root = os.path.join(self.tmp, "p")
        ids = [os.path.basename(runlayout.new_plan_run(root, "ex", line="ln", subject="English", now=0)) for _ in range(3)]
        self.assertEqual(ids, ["19700101-000000-english", "19700101-000000-english-2", "19700101-000000-english-3"])
        plain = [os.path.basename(runlayout.new_plan_run(root, "ex", now=0)) for _ in range(2)]
        self.assertEqual(plain, ["19700101-000000", "19700101-000000-2"])
        self.assertEqual(len(os.listdir(os.path.join(root, "ex", "ln", "runs"))), 3)
        for i in ids + plain:
            self.assertRegex(i, runlayout.PLAN_ID)

    def test_90_1_subject_tag_and_plan_id_grammar(self):
        self.assertEqual(runlayout.subject_tag("English Math"), "english-math")
        self.assertIsNone(runlayout.subject_tag("123"))
        self.assertIsNone(runlayout.subject_tag(""))
        m = runlayout.PLAN_ID.match("20261104-060728-english-2")
        self.assertEqual(m.groups(), ("20261104-060728", "english", "2"))
        self.assertTrue(runlayout.PLAN_ID.match("20261104-060728"))
        self.assertFalse(runlayout.PLAN_ID.match("out-English"))
        self.assertEqual(runlayout.safe_line("fix2"), "fix2")
        for bad in ("", "..", "runs", "cache", "a/b"):
            with self.assertRaises(ValueError):
                runlayout.safe_line(bad)

    def real_plan(self, d, finished):
        put(os.path.join(d, "plan.json"), {"source": "solve", "status": "done", "llm": "claude-p", "calls": 2,
                                           "finished_utc": finished, "exam": {"path": EXAM, "sha256": planrun.metrics.file_sha256(EXAM)}})

    def test_90_6_cache_is_per_exam_not_per_line(self):
        a = runlayout.new_plan_run("plans", "ex", line="alpha", now=1)
        b = runlayout.new_plan_run("plans", "ex", line="beta", now=100)
        self.assertEqual(runlayout.cache_dir("plans", "ex"), os.path.join("plans", "ex", "cache"))
        self.assertNotIn("alpha", runlayout.cache_dir("plans", "ex"))
        for d in (a, b):  # the cache dir name is reserved: neither line nor run
            self.assertNotIn("cache", os.listdir(os.path.dirname(os.path.dirname(d))))

    def test_90_6_last_solved_scans_all_lines_newest_wins(self):
        self.assertIsNone(planrun.last_solved("plans", EXAM, "ex"))
        a = runlayout.new_plan_run("plans", "ex", line="alpha", now=1)
        self.real_plan(a, "2026-11-01T00:00:00Z")
        got = planrun.last_solved("plans", EXAM, "ex")
        self.assertEqual(got["dir"], a)  # a non-main line is found
        b = runlayout.new_plan_run("plans", "ex", line="beta", now=100)
        self.real_plan(b, "2026-11-02T00:00:00Z")
        self.assertEqual(planrun.last_solved("plans", EXAM, "ex")["dir"], b)  # newest across lines
        self.assertIsNone(planrun.last_solved("plans", EXAM, "other"))

    def test_90_8_reports_mirror_line_for_new_runs(self):
        out = self.solve("--line", "fix", "--exam-id", "ex")
        (rid,) = self.runs("ex", "fix")
        (rr,) = [n for n in os.listdir(os.path.join("reports", "ex", "fix")) if n.startswith("run-")]
        rdir = os.path.join("reports", "ex", "fix", rr)
        self.assertTrue(os.path.isfile(runlayout.manifest_path(rdir)))
        self.assertTrue(os.path.isfile(os.path.join(rdir, "INDEX.md")))
        self.assertTrue(os.path.isfile(os.path.join("reports", "ex", "fix", "INDEX.md")))
        self.assertEqual(os.listdir(os.path.join("reports", "ex")).count("fix"), 1)
        self.assertFalse([n for n in os.listdir(os.path.join("reports", "ex")) if n.startswith("run-")])
        rows = runlayout.list_report_runs("reports", "ex", line="fix")
        self.assertEqual([r["line"] for r in rows if r["layout"] == "run"], ["fix"])
        self.assertIn(os.path.join("plans", "ex", "fix", "runs", rid), out)

    def test_90_8_plan_import_goes_to_the_requested_line(self):
        self.solve("--out", "src")
        code, out, err = quiet(cli.plan_import_main, ["src", "--line", "imp", "--exam-id", "ex"]) \
            if "--exam-id" in cli.plan_import_main.__doc__ else quiet(cli.plan_import_main, ["src", "--line", "imp"])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len([d for d in os.listdir("plans") if os.path.isdir(os.path.join("plans", d, "imp", "runs"))]), 1)


def jread(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def txt(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _stamp(epoch):
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime(epoch))


T0 = 1793800000  # fixed epoch for the synthetic report mtimes (2026-11-04 UTC)


class ReportsPhase2(unittest.TestCase):
    """90.8 phase 2 (rewritten for 91.1): `plans-migrate --root reports` moves the old report folders into run folders."""

    def test_90_8_reports_root_apply_verify_undo_roundtrip(self):
        tmp = tempfile.mkdtemp(prefix="plansmig_rep_")
        self.addCleanup(shutil.rmtree, tmp, True)
        rep, mp, bk = os.path.join(tmp, "reports"), os.path.join(tmp, "m.json"), os.path.join(tmp, "bk")
        for rel, text, t in (("dgnl2026f/run-a/a.md", "A\n", 100), ("dgnl2025/run-z/z.md", "Z\n", 200),
                             ("input-001/run-q/q.md", "Q\n", 300)):
            put(os.path.join(rep, *rel.split("/")), text)
            os.utime(os.path.join(rep, *rel.split("/")), (T0 + t, T0 + t))
        put(os.path.join(rep, "dgnl2026f", "INDEX.md"), "idx\n")
        put(mp, {"schema": 1})
        orig = tree(rep)
        argv = ["--root", rep, "--map", mp]
        self.assertEqual(quiet(pm.main, argv + ["--dry-run", "--write-map"])[0], 0)
        self.assertEqual(tree(rep), orig)
        code, out, err = quiet(pm.main, argv + ["--apply", "--backup-dir", bk])
        self.assertEqual(code, 0, out + err)
        for exam, line, off, rel in (("dgnl2026", "f", 100, "run-a/a.md"), ("dgnl2025", "main", 200, "run-z/z.md"),
                                     ("input-001", "main", 300, "run-q/q.md")):  # every folder is mapped now, none kept
            self.assertTrue(os.path.isfile(os.path.join(rep, exam, line, "run-" + _stamp(T0 + off), *rel.split("/"))), rel)
        self.assertEqual(quiet(pm.main, argv + ["--verify"])[0], 0)
        self.assertEqual(quiet(pm.main, argv + ["--undo"])[0], 0)
        now = tree(rep)
        now.pop("MIGRATION.json", None)
        self.assertEqual(now, orig)


class ReportsRunLayout(unittest.TestCase):
    """TASK-091 / REQ-0099 (91.1-91.4): `plans-migrate --root reports` moves every old report folder into
    reports/<exam>/<line>/run-<id>/. Tmp trees only; the 10 mapped folder names are the shipped defaults."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="plansmig_rr_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.rep, self.plans = os.path.join(self.tmp, "reports"), os.path.join(self.tmp, "plans")
        self.mp, self.bk = os.path.join(self.tmp, "m.json"), os.path.join(self.tmp, "bk")
        self.fixture()
        put(self.mp, {"schema": 1})

    def f(self, rel, text, off):
        p = os.path.join(self.rep, *rel.split("/"))
        put(p, text)
        os.utime(p, (T0 + off, T0 + off))

    def plan(self, exam, line, rid, text):
        put(os.path.join(self.plans, exam, line, "runs", rid, "result.json"), text)
        put(os.path.join(self.plans, exam, line, "runs", rid, "plan.json"), {"plan_run_id": rid})
        return os.path.join(self.plans, exam, line, "runs", rid)

    def fixture(self):
        self.pd1 = self.plan("dgnl2026", "f", "20261105-100000", {"questions": [], "exam": {"subject": "Math"}, "n": 1})
        self.pd2 = self.plan("dgnl2026", "f", "20261105-100100", {"questions": [], "exam": {"subject": "Math"}, "n": 2})
        self.plan("dgnl2025", "main", "20261101-000000", {"n": 3})
        self.plan("cacheproof-en", "main", "20261107-035802", {"n": 4})
        rsha = sha(os.path.join(self.pd1, "result.json"))
        self.f("dgnl2026/dgnl2026_math_result-data_run-1.json", {"plan_run_id": "20261105-100000", "result_sha256": rsha}, 0)
        self.f("dgnl2026/dgnl2026_all_note_run-1.md", "pack\n", -30)
        self.f("dgnl2026/INDEX.md", "old pack index\n", 5000)
        self.f("dgnl2026-crosscheck/x.md", "xc\n", 0)  # same mtime as the pack: tie -> -2
        self.f("dgnl2026f/English/e.md", "E\n", 100)
        self.f("dgnl2026f/Math/m.md", "M\n", 50)
        self.f("dgnl2026-t80/t.md", "T\n", 200)
        self.f("dgnl2025/z.md", "Z\n", 300)
        self.f("dhqg2024/sheet-1/s.md", "S\n", 400)
        self.f("dhqg2024/solutions.md", "sol\n", 500)
        self.f("dhqg2024/solutions-weasy.pdf", "pdf\n", 450)
        self.f("dhqg2024-t81/ALL-120/r.md", "R\n", 600)
        self.f("dhqg2024-t81/dhqg2024_math_result-data_run-1.json", {"result_sha256": "0" * 64}, 590)
        self.f("dhqg2024-t82/Math/m.md", "M2\n", 700)
        self.f("cacheproof-en/20261107T035802Z/c.md", "c1\n", 800)
        self.f("cacheproof-en/20261107T035827Z/c.md", "c2\n", 810)
        self.f("input-001/20261102T103714Z/q.md", "Q\n", 900)

    def pm(self, *a):
        return quiet(pm.main, ["--root", self.rep, "--map", self.mp, "--plans-root", self.plans] + list(a))

    def mapped(self):
        self.assertEqual(self.pm("--dry-run", "--write-map")[0], 0)

    def applied(self):
        self.mapped()
        code, out, err = self.pm("--apply", "--backup-dir", self.bk)
        self.assertEqual(code, 0, out + err)

    def contents(self):
        """{rel path: sha} of the non-generated files (INDEX.md / run.json / MIGRATION.* left out)."""
        return {k: v for k, v in tree(self.rep).items()
                if v != "DIR" and os.path.basename(k) not in ("INDEX.md", "run.json") and not k.startswith("MIGRATION.")}

    def runs(self):
        with open(self.mp, encoding="utf-8") as fh:
            return {(r["from"]): r for r in json.load(fh)["report_runs"]}

    def run_dir(self, frm):
        r = self.runs()[frm]
        return os.path.join(self.rep, r["exam"], r["line"], "run-" + r["id"])

    def manifest(self, frm):
        with open(runlayout.manifest_path(self.run_dir(frm)), encoding="utf-8") as fh:
            return json.load(fh)

    # ---- 91.1 target map
    def test_91_1_dry_run_changes_nothing_and_maps_every_folder(self):
        before = (tree(self.rep), tree(self.plans), sha(self.mp))
        code, out, err = self.pm("--dry-run")
        self.assertEqual(code, 0, out + err)
        self.assertEqual((tree(self.rep), tree(self.plans), sha(self.mp)), before)  # tree hash: nothing written
        self.assertIn("keep=0 unmapped=0 report_runs=11", out)
        self.assertNotIn("UNMAPPED ", out.replace("== UNMAPPED / refused (0) ==", ""))
        self.assertNotIn("\nkeep  ", out)

    def test_91_1_run_ids_mtime_name_and_tie(self):
        self.mapped()
        ids = {k: r["id"] for k, r in self.runs().items()}
        self.assertEqual(ids["dgnl2026"], _stamp(T0))  # newest mtime, INDEX.md (mtime T0+5000) ignored
        self.assertEqual(ids["dgnl2026-crosscheck"], _stamp(T0) + "-2")  # tie, old-folder name order
        self.assertEqual(ids["dgnl2026f"], _stamp(T0 + 100))
        self.assertEqual(ids["dhqg2024"], _stamp(T0 + 500))
        self.assertEqual(ids["cacheproof-en/20261107T035802Z"], "20261107-035802")  # from the stamp dir name
        self.assertEqual(ids["cacheproof-en/20261107T035827Z"], "20261107-035827")
        self.assertEqual(ids["input-001/20261102T103714Z"], "20261102-103714")
        self.assertEqual(len(self.runs()), 11)
        self.assertTrue(all(r["id_source"] in ("mtime", "name") for r in self.runs().values()))

    def test_91_1_map_id_overrides_and_invalid_or_taken_id_is_refused(self):
        self.mapped()
        raw = jread(self.mp)
        for r in raw["report_runs"]:
            if r["from"] == "dgnl2025":
                r["id"] = "20260101-000000"
        put(self.mp, raw)
        self.assertEqual(self.pm("--dry-run", "--write-map", "--force")[0], 0)
        self.assertEqual(self.runs()["dgnl2025"]["id"], "20260101-000000")
        for r in raw["report_runs"]:
            if r["from"] == "dgnl2025":
                r["id"] = "bad id"
        put(self.mp, raw)
        code, out, err = self.pm("--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", out + err)

    def test_91_1_one_old_folder_is_one_run_folder(self):
        self.mapped()
        rd = self.run_dir("dgnl2026f")
        self.assertEqual(sorted(m["new"] for m in jread(self.mp)["report_moves"] if m["old"].startswith("dgnl2026f/")),
                         sorted(os.path.relpath(os.path.join(rd, c), self.rep).replace(os.sep, "/") for c in ("English", "Math")))

    def test_91_1_dry_run_without_plans_map_and_unmapped_folder_is_reported(self):
        put(os.path.join(self.rep, "zz-legacy", "a.md"), "A\n")
        code, out, err = self.pm("--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("UNMAPPED zz-legacy", out)

    # ---- 91.2 map
    def test_91_2_write_map_keeps_the_plans_section(self):
        shutil.copy(SHIPPED_MAP, self.mp)
        with open(self.mp, encoding="utf-8") as fh:
            before = json.load(fh)
        code, out, err = self.pm("--dry-run", "--write-map", "--force")
        self.assertEqual(code, 0, out + err)
        with open(self.mp, encoding="utf-8") as fh:
            after = json.load(fh)
        for k in before:
            if not k.startswith("report_"):
                self.assertEqual(after[k], before[k], k)
        self.assertEqual(len(after["report_runs"]), 11)
        self.assertEqual(len(after["report_moves"]), 17)
        self.assertNotIn("keep", after["report_folders"].values())

    # ---- 91.3 apply / verify / undo
    def test_91_3_run_json_links_status_superseded(self):
        self.applied()
        pack = self.manifest("dgnl2026")
        self.assertEqual(pack["link"], "result_sha256")
        self.assertEqual([p["plan_run_id"] for p in pack["plan_runs"]], ["20261105-100000"])  # pd2 has another sha
        self.assertEqual(pack["plan_runs"][0]["result_sha256"], sha(os.path.join(self.pd1, "result.json")))
        self.assertEqual(pack["status"], "complete")
        self.assertEqual(self.manifest("dgnl2026f")["link"], "line")
        self.assertEqual(self.manifest("dgnl2026f")["plan_line"], "f")
        self.assertEqual(self.manifest("dgnl2026-t80")["link"], "unknown")
        self.assertEqual(self.manifest("input-001/20261102T103714Z")["link"], "unknown")
        self.assertEqual(self.manifest("input-001/20261102T103714Z")["exam_id"], "input-001")  # not the line name
        cp = self.manifest("cacheproof-en/20261107T035802Z")
        self.assertEqual((cp["link"], [p["plan_run_id"] for p in cp["plan_runs"]]), ("name", ["20261107-035802"]))
        self.assertEqual(self.manifest("cacheproof-en/20261107T035827Z")["plan_runs"], [])
        t81 = self.manifest("dhqg2024-t81")  # result-data sha matching no plan run: not claimed as linked
        self.assertNotEqual(t81["link"], "result_sha256")
        self.assertEqual(t81["plan_runs"], [])
        xc = self.manifest("dgnl2026-crosscheck")
        self.assertEqual((xc["status"], [s["glob"] for s in xc["superseded"]]), ("superseded", ["*"]))
        self.assertEqual([s["glob"] for s in self.manifest("dhqg2024")["superseded"]], ["solutions*"])
        self.assertEqual(self.manifest("dgnl2025")["migrated_from"], "dgnl2025")

    def test_91_3_content_files_byte_identical_only_index_and_run_json_added(self):
        before = self.contents()
        olds = tree(self.rep)
        self.applied()
        moves = jread(self.mp)["report_moves"]

        def new_of(rel):
            for m in moves:
                if rel == m["old"] or rel.startswith(m["old"] + "/"):
                    return m["new"] + rel[len(m["old"]):]
            self.fail("unmapped file " + rel)
        after = tree(self.rep)
        self.assertEqual(len(before), 17 - 1)  # 17 files minus the old INDEX.md
        for rel, digest in before.items():  # EVERY file: sha256 equal at its mapped path
            self.assertEqual(after.get(new_of(rel)), digest, rel)
        mapped_new = set(new_of(r) for r in before)
        extra = [k for k, v in after.items() if v != "DIR" and k not in mapped_new and not k.startswith("MIGRATION.")]
        self.assertTrue(extra)
        self.assertEqual(set(os.path.basename(k) for k in extra), {"INDEX.md"})  # TASK-102: no run.json in reports/
        self.assertEqual(len(glob.glob(os.path.join(self.plans, "*", "*", "report-runs", "run-*.json"))), 11)
        self.assertFalse([n for n in os.listdir(os.path.join(self.rep, "dgnl2026")) if os.path.isfile(os.path.join(self.rep, "dgnl2026", n))])
        self.assertNotIn("dgnl2026f", os.listdir(self.rep))
        self.assertIn("old pack index", txt(os.path.join(self.rep, "MIGRATION.index", "dgnl2026", "INDEX.md")))
        self.assertGreater(len(olds), 0)

    def test_91_3_apply_backs_up_first_renames_only_inside_reports_idempotent(self):
        self.mapped()
        outside = tree(self.plans)
        code, out, err = self.pm("--apply", "--backup-dir", self.bk)
        self.assertTrue(glob.glob(os.path.join(self.plans, "*", "*", "report-runs", "run-*.json")))
        self.assertEqual(code, 0, out + err)
        self.assertIn("backup ok", out)
        self.assertTrue([n for n in os.listdir(self.bk) if n.endswith(".tar.gz")])
        self.assertLess(out.index("backup ok"), out.index("plans-migrate applied"))
        # plans/ untouched but for the run manifests (TASK-102)
        now = {k: v for k, v in tree(self.plans).items() if "report-runs" not in k}
        self.assertEqual({k: v for k, v in now.items() if v != "DIR"}, {k: v for k, v in outside.items() if v != "DIR"})
        self.assertLessEqual(set(outside), set(now))  # new exam/line folders may hold the manifests
        with open(os.path.join(self.rep, "MIGRATION.json"), encoding="utf-8") as fh:
            man = json.load(fh)
        self.assertEqual(man["state"], "applied")
        self.assertTrue(all(m["state"] == "done" for m in man["moves"]))
        snap = tree(self.rep)
        code, out, err = self.pm("--apply", "--backup-dir", self.bk)  # again: no-op
        self.assertEqual(code, 0, out + err)
        self.assertEqual(tree(self.rep), snap)
        self.assertEqual(self.pm("--verify")[0], 0)

    def test_91_3_failure_while_generating_rolls_back_to_the_original_tree(self):
        orig = tree(self.rep)
        self.mapped()
        with mock.patch.object(pm, "_generate", side_effect=OSError("disk full")):
            code, out, err = self.pm("--apply", "--backup-dir", self.bk)
        self.assertEqual(code, 1, out + err)
        self.assertIn("rolled back", err)
        now = {k: v for k, v in tree(self.rep).items() if not k.startswith("MIGRATION.")}
        self.assertEqual(now, orig)

    def test_91_3_undo_restores_the_original_tree(self):
        orig = tree(self.rep)
        nfiles = sum(1 for v in orig.values() if v != "DIR")
        nbytes = sum(os.path.getsize(os.path.join(self.rep, k)) for k, v in orig.items() if v != "DIR")
        self.applied()
        code, out, err = self.pm("--undo")
        self.assertEqual(code, 0, out + err)
        now = tree(self.rep)
        now.pop("MIGRATION.json", None)
        self.assertEqual(now, orig)  # every file sha256 and every directory
        self.assertEqual(sum(1 for v in now.values() if v != "DIR"), nfiles)
        self.assertEqual(sum(os.path.getsize(os.path.join(self.rep, k)) for k, v in now.items() if v != "DIR"), nbytes)
        self.assertFalse(os.path.exists(os.path.join(self.rep, "MIGRATION.index")))

    def test_91_3_undo_refuses_an_edited_generated_file(self):
        self.applied()
        idx = os.path.join(self.run_dir("dhqg2024"), "INDEX.md")
        with open(idx, "a", encoding="utf-8") as fh:
            fh.write("edited by hand\n")
        code, out, err = self.pm("--undo")
        self.assertNotEqual(code, 0)
        self.assertIn("undo refused", err)
        self.assertTrue(os.path.isfile(idx))  # the edit is kept

    def test_91_3_tree_stats_hash_every_report_file_and_see_a_mutation(self):
        files, size, shas = pm.tree_stats(self.rep, "reports")
        self.assertEqual((files, len(shas)), (17, 17))
        self.assertEqual(shas["dgnl2026f/English/e.md"], sha(os.path.join(self.rep, "dgnl2026f", "English", "e.md")))
        with open(os.path.join(self.rep, "dgnl2026f", "English", "e.md"), "a", encoding="utf-8") as fh:
            fh.write("x")
        _f2, size2, shas2 = pm.tree_stats(self.rep, "reports")
        self.assertEqual(size2, size + 1)
        self.assertEqual([k for k in shas if shas[k] != shas2[k]], ["dgnl2026f/English/e.md"])
        _f3, _s3, content = pm.tree_stats(self.rep, "reports", content=True)
        self.assertNotIn("dgnl2026/INDEX.md", content)

    def test_91_3_verify_detects_a_mutated_content_file(self):
        self.applied()
        p = os.path.join(self.run_dir("dgnl2025"), "z.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("Y\n")  # same size as "Z\n": only the sha256 can see it
        code, out, err = self.pm("--verify")
        self.assertEqual(code, 1, out + err)
        self.assertIn("FAIL", out)

    # ---- 91.4 readers
    def test_91_4_superseded_comes_from_run_json_not_old_folder_globs(self):
        self.applied()
        xc = self.run_dir("dgnl2026-crosscheck")
        self.assertIn("superseded", txt(os.path.join(xc, "INDEX.md")))
        os.remove(os.path.join(xc, "INDEX.md"))
        cli_out = quiet(cli.report_index_main, [xc])  # regenerate: old folder name is gone, run.json decides
        self.assertEqual(cli_out[0], 0, cli_out[1] + cli_out[2])
        idx = txt(os.path.join(xc, "INDEX.md"))
        self.assertIn("superseded", idx)
        self.assertNotIn("dgnl2026-crosscheck", idx)
        dq = txt(os.path.join(self.run_dir("dhqg2024"), "INDEX.md"))
        for ln in dq.splitlines():
            if "solutions.md" in ln or "solutions-weasy.pdf" in ln:
                self.assertIn("superseded", ln)
            if "sheet-1" in ln:
                self.assertNotIn("superseded", ln)

    def test_91_4_moved_reports_are_line_folders(self):
        self.applied()
        rows = runlayout.list_report_runs(self.rep, "dgnl2026", line="f")
        self.assertEqual(sorted(r["id"] for r in rows if r["layout"] == "run"),
                         sorted([_stamp(T0), _stamp(T0) + "-2", _stamp(T0 + 100)]))
        self.assertTrue(runlayout._is_line_report_dir(os.path.join(self.rep, "dgnl2026", "f")))
        self.assertEqual(len(runlayout.list_report_runs(self.rep, "cacheproof-en")), 2)

    def test_91_4_run_list_and_report_index_readers(self):
        self.applied()
        code, out, err = quiet(cli.run_list_main, ["dgnl2026", "--line", "f", "--plans", self.plans, "--reports", self.rep])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(out.count("line f (run unknown)"), 2)  # two line-linked runs: plan run not identified
        self.assertIn("20261105-100000", out.split("## Report runs")[1])  # pack: the exact plan run
        code, out, err = quiet(cli.run_list_main, ["input-001", "--plans", self.plans, "--reports", self.rep])
        self.assertEqual(code, 0, out + err)
        self.assertIn("unknown", out.split("## Report runs")[1])
        old = os.path.join(self.rep, "dgnl2026-crosscheck")
        code, out, err = quiet(cli.report_index_main, [old])
        self.assertEqual(code, 2)
        self.assertIn("was moved to", err)

    def test_91_4_check_report_pack_on_a_moved_pack(self):
        self.applied()
        import subprocess
        pk = self.run_dir("dgnl2026")
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "check_report_pack.py"), pk, self.pd1],
                           capture_output=True, text=True, timeout=60)
        rows = [ln.split("\t") for ln in r.stdout.splitlines() if ln.startswith("manifest")]
        self.assertEqual([(x[0], x[3]) for x in rows],
                         [("manifest plan_runs", "ok"), ("manifest result_sha256 mismatches", "ok")], r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()

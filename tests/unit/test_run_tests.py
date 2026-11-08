"""TASK-088 / REQ-0096 - tools/run_tests.py (tiers, known failures, --affected, gate key, worktree).

All tests use a tiny fake repo in a tempdir; the real suite and the real work/ are never touched.
"""
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
TOOL = os.path.join(ROOT, "tools", "run_tests.py")
_spec = importlib.util.spec_from_file_location("run_tests_tool", TOOL)
rt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rt)

GENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
            GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_NOSYSTEM="1")
PY = sys.executable
TEST_CMD = "%s -I -m unittest discover -s tests/unit" % shlex.quote(PY)

REG = {
    "slow": ["test_alpha.A.test_slow"],
    "known_failures": ["test_gamma.G.test_known"],
    "affected_map": {"cfg/*.json": ["test_delta"]},
    "affected_ignore": ["docs/*", "*.md", ".claude/state/*"],
    "cache_ignore": [".claude/state/", "docs/req/", "docs/design/", "docs/report/"],
}

FILES = {
    "tests/unit/test_alpha.py": (
        "import unittest\nclass A(unittest.TestCase):\n"
        "    def test_one(self): pass\n    def test_slow(self): pass\n"),
    "tests/unit/test_mod.py": (
        "import unittest\nclass M(unittest.TestCase):\n    def test_m(self): pass\n"),
    "tests/unit/test_beta.py": (
        "import unittest\nif False:\n    import pkg.mod\n"
        "class B(unittest.TestCase):\n    def test_b(self): pass\n"
        "    @unittest.skip('x')\n    def test_skipped(self): pass\n"),
    "tests/unit/test_gamma.py": (
        "import unittest\nclass G(unittest.TestCase):\n"
        "    def test_known(self): self.fail('known')\n"),
    "tests/unit/test_delta.py": (
        "import unittest\nclass D(unittest.TestCase):\n    def test_ok(self): pass\n"),
    "src/pkg/mod.py": "X = 1\n",
    "src/pkg/other.py": "Y = 1\n",
    "docs/guide/g.md": "g\n",
    ".claude/state/s.json": "{}\n",
    "docs/req/r.md": "r\n",
}
TOTAL, N_SLOW = 7, 1


def sh(cwd, *args):
    p = subprocess.run(args, cwd=cwd, env=GENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       universal_newlines=True)
    return p.returncode, p.stdout


def put(repo, rel, text):
    path = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def commit(repo, msg="c"):
    sh(repo, "git", "add", "-A")
    rc, out = sh(repo, "git", "commit", "-q", "-m", msg)
    assert rc == 0, out


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rt-unit-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(self.repo)
        sh(self.repo, "git", "init", "-q")
        for rel, text in FILES.items():
            put(self.repo, rel, text)
        self.set_reg(REG)
        commit(self.repo, "init")

    def set_reg(self, reg):
        put(self.repo, "config/test_tiers.json", json.dumps(reg))

    def run_tool(self, *args):
        p = subprocess.run([PY, "-I", TOOL, "--repo", self.repo] + list(args), env=GENV,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return p.returncode, p.stdout, p.stderr

    def wt_count(self):
        return len(rt.worktree_paths(self.repo))


class Fake:
    def __init__(self, tid, cls="TestCase"):
        self._id, self.__class__ = tid, type(cls, (), {"id": lambda s: s._id})

    def id(self):
        return self._id


class Matching(Base):
    def test_88_2_registry_load_defaults_and_file(self):
        reg = rt.load_registry(self.repo)
        self.assertEqual(reg["slow"], REG["slow"])
        self.assertEqual(reg["known_failures"], REG["known_failures"])
        empty = rt.load_registry(self.tmp)  # no config file -> defaults, all fast
        self.assertEqual((empty["slow"], empty["known_failures"], empty["threshold_s"]), ([], [], 2.0))

    def test_88_2_matches_module_class_method_boundaries(self):
        self.assertTrue(rt.matches("m.C.t", ["m"]))
        self.assertTrue(rt.matches("m.C.t", ["m.C"]))
        self.assertTrue(rt.matches("m.C.t", ["m.C.t"]))
        self.assertTrue(rt.matches("m.C.t (sub)", ["m.C.t"]))
        self.assertFalse(rt.matches("mod2.C.t", ["mod"]))  # no partial-name hit
        self.assertFalse(rt.matches("m.Cx.t", ["m.C"]))

    def test_88_2_untagged_test_is_fast(self):
        reg = rt.load_registry(self.repo)
        self.assertEqual(rt.tier_of("test_beta.B.test_b", reg), "fast")
        self.assertEqual(rt.tier_of("test_alpha.A.test_slow", reg), "slow")
        self.assertEqual(rt.tier_of("test_alpha.A.test_one", reg), "fast")

    def test_88_3_select_filters_by_id_and_partitions(self):
        reg = rt.load_registry(self.repo)
        ids = ["test_alpha.A.test_one", "test_alpha.A.test_slow", "test_beta.B.test_b"]
        tests = [Fake(i) for i in ids]
        fast = [t.id() for t in rt.select(tests, reg, "fast")]
        slow = [t.id() for t in rt.select(tests, reg, "slow")]
        self.assertEqual(slow, ["test_alpha.A.test_slow"])
        self.assertNotIn("test_alpha.A.test_slow", fast)
        self.assertEqual(sorted(fast + slow), sorted(ids))  # fast + slow == all
        self.assertEqual(len(rt.select(tests, reg, "all")), 3)

    def test_88_3_load_failures_always_kept(self):
        reg = rt.load_registry(self.repo)
        bad = Fake("unittest.loader._FailedTest.test_x", "_FailedTest")
        self.assertEqual(rt.select([bad], reg, "fast"), [bad])
        self.assertEqual(rt.select([bad], reg, "slow"), [bad])


class Cli(Base):
    def test_88_3_list_counts_add_up(self):
        rc, out, _ = self.run_tool("--list")
        self.assertEqual(rc, 0, out)
        self.assertIn("COUNT all=%d fast=%d slow=%d" % (TOTAL, TOTAL - N_SLOW, N_SLOW), out)
        self.assertIn("slow\ttest_alpha.A.test_slow", out)
        self.assertIn("fast\ttest_beta.B.test_b", out)

    def test_88_3_list_fails_on_stale_registry_id(self):
        for key in ("slow", "known_failures"):
            reg = dict(REG)
            reg[key] = REG[key] + ["test_gone.X.test_y"]
            self.set_reg(reg)
            rc, out, _ = self.run_tool("--list")
            self.assertEqual(rc, 1, key)
            self.assertIn("STALE test_gone.X.test_y", out)

    def test_88_3_fast_skips_slow_and_reports_known_not_new(self):
        rc, out, err = self.run_tool("--fast")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("KNOWN: 1 NEW: 0", out)
        self.assertIn("  known  test_gamma.G.test_known", out)
        self.assertIn("SKIPPED_SLOW: %d" % N_SLOW, out)
        self.assertNotIn("NEW    ", out)
        self.assertIn("Ran %d tests" % (TOTAL - N_SLOW), out)

    def test_88_3_new_failure_is_new_and_rc_nonzero(self):
        put(self.repo, "tests/unit/test_delta.py",
            "import unittest\nclass D(unittest.TestCase):\n    def test_boom(self): self.fail('b')\n")
        rc, out, _ = self.run_tool("--fast")
        self.assertEqual(rc, 1)
        self.assertIn("KNOWN: 1 NEW: 1", out)
        self.assertIn("  NEW    test_delta.D.test_boom", out)

    def test_88_3_known_registry_empty_makes_failure_new(self):
        reg = dict(REG, known_failures=[])
        self.set_reg(reg)
        rc, out, _ = self.run_tool("--fast")
        self.assertEqual(rc, 1)
        self.assertIn("NEW    test_gamma.G.test_known", out)


class Classify(unittest.TestCase):
    REG = {"known_failures": ["test_gamma.G.test_known", "test_k.Cls"]}

    def test_88_4_classify_known_vs_new(self):
        known, new = rt.classify(["test_gamma.G.test_known", "test_k.Cls.test_a", "test_n.X.t"], self.REG)
        self.assertEqual(known, ["test_gamma.G.test_known", "test_k.Cls.test_a"])
        self.assertEqual(new, ["test_n.X.t"])

    def test_88_4_parse_output_py310_and_py311_formats(self):
        t310 = ("FAIL: test_known (test_gamma.G)\nERROR: test_x (test_n.X)\n"
                "Ran 7 tests in 0.5s\n\nFAILED (failures=1, errors=1, skipped=2)\n")
        t311 = ("FAIL: test_known (test_gamma.G.test_known)\nERROR: test_x (test_n.X.test_x)\n"
                "Ran 7 tests in 0.5s\n\nFAILED (failures=1, errors=1, skipped=2)\n")
        for text in (t310, t311):
            r = rt.parse_output(text, self.REG)
            self.assertEqual(r["failed"], ["test_gamma.G.test_known", "test_n.X.test_x"])
            self.assertEqual(r["known"], ["test_gamma.G.test_known"])
            self.assertEqual(r["new"], ["test_n.X.test_x"])
            self.assertEqual((r["ran"], r["skipped"]), (7, 2))
            self.assertTrue(r["summary"].startswith("FAILED"))

    def test_88_4_parse_output_ok_and_no_result(self):
        r = rt.parse_output("Ran 3 tests in 0.1s\n\nOK\n", self.REG)
        self.assertEqual((r["summary"], r["ran"], r["new"], r["skipped"]), ("OK", 3, [], 0))
        r = rt.parse_output("Traceback...\n", self.REG)
        self.assertEqual((r["summary"], r["ran"]), ("NO RESULT", 0))


class Affected(Base):
    def aff(self, *files, **kw):
        return self.run_tool("--affected", "--files", *files)

    def test_88_6_src_module_maps_to_named_test_and_prints_reason(self):
        rc, out, _ = self.aff("src/pkg/mod.py")
        self.assertEqual(rc, 0, out)
        self.assertIn("test_mod\tsrc/pkg/mod.py: name matches mod", out)
        self.assertIn("Ran 3 tests", out)  # test_mod + importer test_beta (1 skipped)

    def test_88_6_import_scan_finds_importing_test(self):
        _, out, _ = self.aff("src/pkg/mod.py")
        self.assertIn("test_beta\tsrc/pkg/mod.py: imports pkg.mod", out)

    def test_88_6_test_file_change_maps_to_itself(self):
        _, out, _ = self.aff("tests/unit/test_delta.py")
        self.assertIn("test_delta\ttests/unit/test_delta.py: test file changed", out)

    def test_88_6_explicit_override_map(self):
        rc, out, _ = self.aff("cfg/x.json")
        self.assertEqual(rc, 0, out)
        self.assertIn("test_delta\tcfg/x.json: affected_map cfg/*.json", out)
        self.assertNotIn("FALLBACK", out)

    def test_88_6_unmapped_file_falls_back_to_fast(self):
        rc, out, _ = self.aff("src/pkg/other.py")  # no test_other, no importer
        self.assertIn("FALLBACK --fast (src/pkg/other.py unmapped)", out)
        self.assertIn("Ran %d tests" % (TOTAL - N_SLOW), out)

    def test_88_6_docs_only_is_nothing_changed(self):
        rc, out, _ = self.aff("docs/guide/g.md", ".claude/state/s.json")
        self.assertEqual((rc, out.strip()), (0, "NOTHING CHANGED"))

    def test_88_6_slow_skipped_by_default_unless_with_slow(self):
        _, out, _ = self.aff("tests/unit/test_alpha.py")
        self.assertIn("SKIPPED_SLOW test_alpha.A.test_slow", out)
        self.assertIn("Ran 1 test", out)
        _, out, _ = self.run_tool("--affected", "--with-slow", "--files", "tests/unit/test_alpha.py")
        self.assertNotIn("SKIPPED_SLOW test_", out)
        self.assertIn("Ran 2 tests", out)

    def test_88_6_changed_files_from_git_diff_and_untracked(self):
        put(self.repo, "src/pkg/mod.py", "X = 2\n")
        put(self.repo, "src/pkg/new.py", "Z = 1\n")
        files = rt.changed_files(self.repo, None)
        self.assertEqual(sorted(files), ["src/pkg/mod.py", "src/pkg/new.py"])


class Key(Base):
    def key(self):
        return rt.tree_key(self.repo, rt.load_registry(self.repo))

    def test_88_4_key_ignores_state_and_req_design_report(self):
        k0 = self.key()
        for rel in (".claude/state/s.json", "docs/req/r.md", "docs/design/d.md", "docs/report/x.md"):
            put(self.repo, rel, "changed %s\n" % rel)
            commit(self.repo, rel)
            self.assertEqual(self.key(), k0, rel)

    def test_88_4_key_changes_on_source_test_or_other_docs(self):
        seen = {self.key()}
        for rel in ("src/pkg/mod.py", "tests/unit/test_delta.py", "docs/guide/g.md"):
            put(self.repo, rel, "changed %s\n" % rel)
            commit(self.repo, rel)
            k = self.key()
            self.assertNotIn(k, seen, rel)
            seen.add(k)

    def test_88_4_key_depends_on_cache_ignore_registry(self):
        reg = dict(REG, cache_ignore=[])  # state no longer ignored -> bites if filter is dropped
        k0 = rt.tree_key(self.repo, reg)
        put(self.repo, ".claude/state/s.json", "{\"a\":1}\n")
        commit(self.repo)
        self.assertNotEqual(rt.tree_key(self.repo, reg), k0)

    def test_88_4_dirty_count_ignores_ignored_prefixes(self):
        reg = rt.load_registry(self.repo)
        put(self.repo, ".claude/state/s.json", "{\"a\":1}\n")
        self.assertEqual(rt.dirty_count(self.repo, reg), 0)
        put(self.repo, "src/pkg/mod.py", "X = 3\n")
        self.assertEqual(rt.dirty_count(self.repo, reg), 1)


class Gate(Base):
    def full(self, *extra):
        return self.run_tool("--out", self.out, "--full", "--test-cmd", TEST_CMD, *extra)

    def key(self):
        return rt.tree_key(self.repo, rt.load_registry(self.repo))

    def test_88_4_full_wait_result_schema_and_cleanup(self):
        before = sh(self.repo, "git", "status", "--porcelain")[1]
        rc, out, err = self.full("--wait")
        self.assertEqual(rc, 0, out + err)
        with open(os.path.join(self.out, self.key() + ".json")) as fh:
            r = json.load(fh)
        for k in ("status", "key", "head", "rc", "gate_ok", "ran", "summary", "failed", "known",
                  "new", "skipped", "dirty", "duration_s", "cmd", "log", "worktree_removed"):
            self.assertIn(k, r)
        self.assertEqual((r["status"], r["gate_ok"], r["rc"]), ("done", True, 1))  # raw rc 1: known fail
        self.assertEqual((r["ran"], r["skipped"]), (TOTAL, 1))
        self.assertEqual(r["known"], ["test_gamma.G.test_known"])
        self.assertEqual(r["new"], [])
        self.assertTrue(r["summary"].startswith("FAILED"))
        self.assertGreaterEqual(r["duration_s"], 0)
        self.assertTrue(r["worktree_removed"])
        self.assertEqual(self.wt_count(), 1)
        self.assertEqual(sh(self.repo, "git", "status", "--porcelain")[1], before)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "work")))
        self.assertFalse(os.path.exists(os.path.join(self.out, ".full.lock")))

    def test_88_4_full_new_failure_gate_rc1(self):
        put(self.repo, "tests/unit/test_delta.py",
            "import unittest\nclass D(unittest.TestCase):\n    def test_boom(self): self.fail('b')\n")
        commit(self.repo)
        rc, out, _ = self.full("--wait")
        self.assertEqual(rc, 1)
        self.assertIn("NEW  test_delta.D.test_boom", out)
        with open(os.path.join(self.out, self.key() + ".json")) as fh:
            r = json.load(fh)
        self.assertEqual((r["gate_ok"], r["new"]), (False, ["test_delta.D.test_boom"]))

    def test_88_4_reuse_when_hash_unchanged_without_worktree(self):
        os.makedirs(self.out)
        fake = {"status": "done", "key": self.key(), "gate_ok": True, "rc": 0, "ran": 5,
                "summary": "OK", "known": [], "new": [], "skipped": 0, "duration_s": 1.0}
        with open(os.path.join(self.out, self.key() + ".json"), "w") as fh:
            json.dump(fake, fh)
        rc, out, _ = self.full()
        self.assertEqual(rc, 0, out)
        self.assertIn("REUSED", out)
        self.assertNotIn("STARTED", out)
        self.assertEqual(os.listdir(self.out), [self.key() + ".json"])  # nothing was run
        # a state-only commit keeps the key -> still reused
        put(self.repo, ".claude/state/s.json", "{\"n\":2}\n")
        commit(self.repo)
        self.assertIn("REUSED", self.full()[1])

    def test_88_4_no_reuse_after_source_commit(self):
        os.makedirs(self.out)
        with open(os.path.join(self.out, self.key() + ".json"), "w") as fh:
            json.dump({"status": "done", "gate_ok": True, "new": []}, fh)
        put(self.repo, "src/pkg/mod.py", "X = 9\n")
        commit(self.repo)
        rc, out, _ = self.full("--wait")
        self.assertNotIn("REUSED", out)
        self.assertIn("RESULT", out)

    def test_88_4_running_with_live_pid_not_restarted(self):
        os.makedirs(self.out)
        with open(os.path.join(self.out, self.key() + ".json"), "w") as fh:
            json.dump({"status": "running", "pid": os.getpid()}, fh)
        rc, out, _ = self.full()
        self.assertEqual(rc, 0)
        self.assertIn("RUNNING pid %d" % os.getpid(), out)

    def test_88_5_worktree_removed_when_run_raises(self):
        os.makedirs(self.out)
        _, head = sh(self.repo, "git", "rev-parse", "HEAD")
        reg = rt.load_registry(self.repo)
        with self.assertRaises(OSError):
            rt.run_gate(self.repo, reg, "k1", head.strip(), self.out, ["/no/such/exe-xyz"], 5)
        self.assertEqual(self.wt_count(), 1)
        self.assertFalse(os.path.exists(os.path.join(self.out, ".full.lock")))
        with open(os.path.join(self.out, "k1.json")) as fh:
            r = json.load(fh)
        self.assertEqual(r["status"], "error")
        self.assertTrue(r["worktree_removed"])

    def test_88_5_timeout_kills_and_records(self):
        os.makedirs(self.out)
        _, head = sh(self.repo, "git", "rev-parse", "HEAD")
        reg = rt.load_registry(self.repo)
        rc = rt.run_gate(self.repo, reg, "k2", head.strip(), self.out,
                         [PY, "-c", "import time; time.sleep(30)"], 1)
        self.assertEqual(rc, 1)
        with open(os.path.join(self.out, "k2.json")) as fh:
            r = json.load(fh)
        self.assertEqual((r["status"], r["rc"], r["gate_ok"]), ("timeout", 124, False))
        self.assertEqual(self.wt_count(), 1)


class Safety(Base):
    def test_88_5_stale_worktree_cleaned_and_keep_respected(self):
        stale = os.path.join(self.tmp, "elh-test-stale")
        other = os.path.join(self.tmp, "keepme")
        sh(self.repo, "git", "worktree", "add", "-q", "--detach", stale, "HEAD")
        sh(self.repo, "git", "worktree", "add", "-q", "--detach", other, "HEAD")
        self.assertEqual(self.wt_count(), 3)
        self.assertEqual(rt.cleanup_stale(self.repo), 1)
        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.exists(other))  # only elh-test-* prefix is removed
        self.assertEqual(self.wt_count(), 2)
        sh(self.repo, "git", "worktree", "remove", "--force", other)

    def test_88_5_clean_command(self):
        stale = os.path.join(self.tmp, "elh-test-old")
        sh(self.repo, "git", "worktree", "add", "-q", "--detach", stale, "HEAD")
        rc, out, _ = self.run_tool("--clean")
        self.assertEqual(rc, 0)
        self.assertIn("CLEANED 1", out)
        self.assertEqual(self.wt_count(), 1)

    def test_88_5_lock_dead_pid_broken_live_pid_refused(self):
        os.makedirs(self.out)
        lock = os.path.join(self.out, ".full.lock")
        os.mkdir(lock)
        with open(os.path.join(lock, "pid"), "w") as fh:
            fh.write("2147483646")  # not a live process
        got = rt.acquire_lock(self.out)
        self.assertEqual(got, lock)
        with open(os.path.join(lock, "pid")) as fh:
            self.assertEqual(fh.read(), str(os.getpid()))
        self.assertIsNone(rt.acquire_lock(self.out))  # now held by a live pid (us)
        shutil.rmtree(lock)

    def test_88_5_run_gate_returns_3_when_locked(self):
        os.makedirs(self.out)
        self.assertIsNotNone(rt.acquire_lock(self.out))
        rc = rt.run_gate(self.repo, rt.load_registry(self.repo), "k3", "HEAD", self.out, [PY, "-c", "0"], 5)
        self.assertEqual(rc, 3)
        self.assertEqual(self.wt_count(), 1)

    def test_88_5_assert_outside_refuses_paths_in_repo(self):
        for p in (self.repo, os.path.join(self.repo, "work", "wt")):
            with self.assertRaises(SystemExit) as cm:
                rt.assert_outside(self.repo, p)
            self.assertEqual(cm.exception.code, 2)
        rt.assert_outside(self.repo, os.path.join(self.tmp, "elsewhere"))  # no raise
        rt.assert_outside(self.repo, self.repo + "-sibling")  # prefix, not a child


if __name__ == "__main__":
    unittest.main()

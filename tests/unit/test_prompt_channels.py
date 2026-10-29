"""Phase 9 (REQ-0013): prompt channels. Edits happen only in a temp copy of prompts/; the real
files are never touched. --dry-run / --mock only (no model call)."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli, settings  # noqa: E402
from exam_engine.core import schema as sch  # noqa: E402
from exam_engine.pipeline import prompts  # noqa: E402

INPUT = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(HERE, "fixtures", "mock_english_001.json")
MARK = "ZZ-DEV-MARKER-77"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pc_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.prm = os.path.join(self.tmp, "prompts")
        os.makedirs(os.path.join(self.prm, "releases"))
        shutil.copytree(os.path.join(ROOT, "prompts", "dev"), os.path.join(self.prm, "dev"))
        shutil.copytree(os.path.join(ROOT, "prompts", "releases", "v1.0.0"),
                        os.path.join(self.prm, "releases", "v1.0.0"))
        for p in (mock.patch.object(settings, "PROMPTS_DIR", self.prm),
                  mock.patch.dict(settings.PROMPT_SOURCE, {"channel": None, "version": None})):
            p.start()
            self.addCleanup(p.stop)
        with open(os.path.join(self.prm, "dev", "system.md"), "a", encoding="utf-8") as fh:
            fh.write("\n" + MARK + "\n")

    def dry(self, *extra):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.solve_main([INPUT, "--dry-run"] + list(extra))
        self.assertEqual(code, 0)
        return buf.getvalue()


class Channels(Base):
    def test_default_reads_release_not_dev(self):
        self.assertNotIn(MARK, self.dry())

    def test_dev_channel_reads_dev(self):
        self.assertIn(MARK, self.dry("--channel", "dev"))

    def test_prompt_version_selects_release(self):
        shutil.copytree(os.path.join(self.prm, "releases", "v1.0.0"),
                        os.path.join(self.prm, "releases", "v1.0.1"))
        with open(os.path.join(self.prm, "releases", "v1.0.1", "system.md"), "a") as fh:
            fh.write(MARK)
        self.assertIn(MARK, self.dry("--prompt-version", "v1.0.1"))

    def test_result_carries_channel_and_version(self):
        for extra, want in (([], {"channel": "release", "version": "v1.0.0"}),
                            (["--channel", "dev"], {"channel": "dev", "version": None})):
            out = os.path.join(self.tmp, "o%d" % len(extra))
            with contextlib.redirect_stdout(io.StringIO()):
                cli.solve_main([INPUT, "--mock", MOCK, "--out", out, "--no-pdf"] + extra)
            res = settings.load_json(os.path.join(out, "result.json"))
            self.assertEqual(res["run"]["prompt"], want)
            self.assertEqual(sch.validate(res, settings.load_schema("result")), [])


class Releases(Base):
    def test_release_copies_dev_and_refuses_existing(self):
        m = prompts.release("v2.0.0")
        self.assertIn("system.md", m["files"])
        self.assertEqual(prompts.verify_release("v2.0.0"), [])
        with open(os.path.join(self.prm, "releases", "v2.0.0", "system.md"), encoding="utf-8") as fh:
            self.assertIn(MARK, fh.read())
        with self.assertRaises(ValueError):
            prompts.release("v2.0.0")
        with self.assertRaises(ValueError):
            prompts.release("1.0")

    def test_verify_fails_after_one_byte_change(self):
        self.assertEqual(prompts.verify_release(), [])
        path = os.path.join(self.prm, "releases", "v1.0.0", "system.md")
        with open(path, "ab") as fh:
            fh.write(b" ")
        self.assertTrue(any("changed" in e for e in prompts.verify_release()))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(prompts.prompts_main(["verify"]), 1)

    def test_verify_flags_extra_and_missing(self):
        root = os.path.join(self.prm, "releases", "v1.0.0")
        open(os.path.join(root, "extra.md"), "w").close()
        os.remove(os.path.join(root, "system.md"))
        errs = " ".join(prompts.verify_release())
        self.assertIn("extra file extra.md", errs)
        self.assertIn("missing file system.md", errs)

    def test_real_release_is_intact(self):
        with mock.patch.object(settings, "PROMPTS_DIR", os.path.join(ROOT, "prompts")):
            self.assertEqual(prompts.verify_release("v1.0.0"), [])
            m = settings.load_json(os.path.join(ROOT, "prompts", "releases", "v1.0.0", "MANIFEST.json"))
            self.assertEqual(m["version"], "v1.0.0")


class VersionGuard(unittest.TestCase):
    def tearDown(self):
        settings.use_prompts()

    def test_traversal_and_bad_versions_rejected(self):
        for bad in ("../dev", "../../x", "1.0.0", "v1.0", "v1.0.0/../v1.0.0", ""):
            with self.assertRaises(ValueError):
                settings.use_prompts("release", bad)

    def test_version_with_dev_rejected(self):
        with self.assertRaises(ValueError):
            settings.use_prompts("dev", "v1.0.0")

    def test_cli_exit_2_on_bad_or_missing_version(self):
        for v in ("../dev", "v9.9.9"):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = cli.main(["solve", os.path.join(ROOT, "examples/math/input-001.md"),
                               "--dry-run", "--prompt-version", v])
            self.assertEqual(rc, 2, v)
            self.assertIn("ERROR", err.getvalue())


if __name__ == "__main__":
    unittest.main()

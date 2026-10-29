"""settings: paths come from __file__, not from the cwd; config loading and override."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import settings  # noqa: E402


class Settings(unittest.TestCase):
    def test_paths_point_into_the_repo(self):
        self.assertEqual(settings.ROOT, ROOT)
        for p in (settings.PROMPTS_DIR, settings.SCHEMAS_DIR, settings.CONFIG_DIR):
            self.assertTrue(os.path.isdir(p), p)
            self.assertTrue(p.startswith(ROOT))
        self.assertEqual(settings.WORKSPACE, os.path.join(ROOT, "workspace"))

    def test_no_cwd_dependence(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run(
                [sys.executable, "-I", "-c",
                 "import sys; sys.path.insert(0, %r); from exam_engine import settings; "
                 "print(settings.ROOT)" % os.path.join(ROOT, "src")],
                cwd=d, stdout=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(r.stdout.strip(), ROOT)

    def test_engine_defaults(self):
        cfg = settings.load_config("engine")
        self.assertEqual(sorted(cfg), ["max_attempts", "max_cost_usd", "model", "timeout"])

    def test_config_dir_override(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "engine.json"), "w") as fh:
                json.dump({"max_attempts": 7}, fh)
            with mock.patch.dict(os.environ, {"EXAM_ENGINE_CONFIG_DIR": d}):
                self.assertEqual(settings.load_config("engine"), {"max_attempts": 7})
            self.assertIn("model", settings.load_config("engine"))

    def test_schemas_and_prompts_load(self):
        for n in ("solve_out", "qa_out", "result"):
            self.assertEqual(settings.load_schema(n)["type"], "object")
        self.assertIn("Common rules", settings.read_prompt("system.md"))


if __name__ == "__main__":
    unittest.main()

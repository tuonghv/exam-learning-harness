"""REQ-0012 acceptance (AC2-AC6) not covered elsewhere: shim parity, claude-only-in-adapter,
prompt/key isolation, new subject by config+prompt file, cwd independence, README."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import settings  # noqa: E402
from exam_engine.pipeline import parser, solver  # noqa: E402

EXAM = os.path.join(ROOT, "scripts", "exam.py")
SHIMS = os.path.join(ROOT, "tools", "examples")
INPUT = os.path.join(ROOT, "examples", "english", "input-001.md")
KEY = os.path.join(ROOT, "examples", "english", "expected-001.md")
MOCK = os.path.join(HERE, "fixtures", "mock_english_001.json")
SENTINEL = "ZQSENTINEL91KEY"
CHEM = """# Exam Input

Subject: Chemistry
Level: Grade 12
Exam type: High School Graduation
Task: Short Answer
Mode: Solve

## Instructions

Answer.

## Question 1

Relative atomic mass of oxygen?
"""


def run(script, *args, **kw):
    p = subprocess.run([sys.executable, "-I", script] + list(args), cwd=kw.get("cwd"),
                       env=kw.get("env"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True)
    return p.returncode, p.stdout, p.stderr


def files(top, ext):
    for d, _, names in os.walk(top):
        if "__pycache__" in d:
            continue
        for n in sorted(names):
            if n.endswith(ext):
                yield os.path.join(d, n)


def text(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)


class ShimParity(Base):
    def test_6_2_every_shim_runs_under_isolated_python(self):
        shims = sorted(n for n in os.listdir(SHIMS) if n.endswith(".py"))
        self.assertGreaterEqual(len(shims), 9)
        for n in shims:
            if n in ("exam_run.py", "check_examples.py", "score_eval.py", "md2html.py"):
                continue  # CLI shims, covered below (md2html needs args)
            code, _, err = run(os.path.join(SHIMS, n), cwd=self.tmp)
            self.assertEqual(code, 0, "%s: %s" % (n, err[-200:]))

    def test_6_2_exam_run_mock_equals_solve(self):
        args = (INPUT, "--mock", MOCK, "--key", KEY, "--no-pdf")
        a, b = os.path.join(self.tmp, "a"), os.path.join(self.tmp, "b")
        new = run(EXAM, "solve", *args, "--out", a, cwd=self.tmp)
        old = run(os.path.join(SHIMS, "exam_run.py"), *args, "--out", b, cwd=self.tmp)
        self.assertEqual(new[0], old[0])
        self.assertEqual(new[1].replace(a, "OUT"), old[1].replace(b, "OUT"))
        self.assertTrue(new[1].startswith("pass="))
        self.assertEqual(json.loads(text(os.path.join(a, "result.json")))["questions"],
                         json.loads(text(os.path.join(b, "result.json")))["questions"])

    def test_6_2_exam_run_dry_run_equals_solve(self):
        new = run(EXAM, "solve", INPUT, "--dry-run", cwd=self.tmp)
        old = run(os.path.join(SHIMS, "exam_run.py"), INPUT, "--dry-run", cwd=self.tmp)
        self.assertEqual(new[0], 0)
        self.assertEqual(new[:2], old[:2])
        self.assertIn("Exam file:", new[1])

    def test_6_2_no_mode_exit_2_same_message(self):
        new = run(EXAM, "solve", INPUT, cwd=self.tmp)
        old = run(os.path.join(SHIMS, "exam_run.py"), INPUT, cwd=self.tmp)
        self.assertEqual((new[0], old[0]), (2, 2))
        self.assertEqual(new[2], old[2])
        self.assertIn("never defaults to real", new[2])

    def test_6_2_check_examples_and_score_shims_equal_subcommands(self):
        for shim, sub in (("check_examples.py", "check-examples"), ("score_eval.py", "score")):
            new = run(EXAM, sub, cwd=self.tmp)
            old = run(os.path.join(SHIMS, shim), cwd=self.tmp)
            self.assertEqual(new, old, shim)


class ClaudeOnlyInAdapter(unittest.TestCase):
    def test_6_3_claude_subprocess_only_in_adapter(self):
        adapter = os.path.join(ROOT, "src", "exam_engine", "adapters", "claude.py")
        pat = re.compile(r"""["']claude["']|\bclaude\s+-p\b|["']-p["']""")
        bad = [os.path.relpath(p, ROOT) for top in ("src", "scripts")
               for p in files(os.path.join(ROOT, top), ".py")
               if p != adapter and pat.search(text(p))]
        self.assertEqual(bad, [])
        self.assertRegex(text(adapter), r"subprocess\.")
        self.assertIn('"claude"', text(adapter))


class PromptsAndKeys(Base):
    def test_6_4_prompts_only_top_level_and_nothing_reads_docs_prompts(self):
        self.assertTrue(os.path.isdir(os.path.join(ROOT, "prompts")))
        self.assertTrue(settings.PROMPTS_DIR.endswith(os.sep + "prompts"))
        self.assertNotIn("docs", os.path.relpath(settings.PROMPTS_DIR, ROOT))
        for top in ("src", "scripts", "tools"):
            for p in files(os.path.join(ROOT, top), ".py"):
                self.assertNotIn("docs/prompts", text(p), p)
                self.assertNotIn('"docs"', text(p), p)
        for rel in ("system.md", "exam/solve.md", "subjects/math.md",
                    "verification/verify_answer.md"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "prompts", "dev", rel)), rel)

    def test_6_4_schemas_and_config_read_via_settings(self):
        for p in files(os.path.join(ROOT, "src"), ".py"):
            if p.endswith(os.path.join("exam_engine", "settings.py")):
                continue
            t = text(p)
            if p.endswith(os.path.join("exam_engine", "cli.py")):
                t = t.replace('"prompts"', "")  # the `prompts` subcommand name, not a path
            self.assertNotRegex(t, r"""["'](schemas|config|prompts)["']""", p)
            self.assertNotRegex(t, r"""["'][\w/]*\.schema\.json["']""", p)
        for n in ("solve_out", "qa_out", "result"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "schemas", n + ".schema.json")))
        for n in ("engine", "subjects"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "config", n + ".json")))

    def _key(self):
        k = os.path.join(self.tmp, "expected-001.md")
        with open(k, "w", encoding="utf-8") as fh:
            fh.write(text(KEY).replace("This sentence uses", SENTINEL + " This sentence uses"))
        return k

    def test_6_4_eval_key_text_never_in_assembled_prompts(self):
        k = self._key()
        exam = parser.parse_exam(INPUT)
        self.assertNotIn(SENTINEL, solver.solve_prompt(exam, text(INPUT), k))
        code, out, _ = run(EXAM, "solve", INPUT, "--dry-run", "--key", k, cwd=self.tmp)
        self.assertEqual(code, 0)
        self.assertNotIn(SENTINEL, out)

    def test_6_5_new_subject_by_config_and_prompt_file_only(self):
        cfg = os.path.join(self.tmp, "config")
        prm = os.path.join(self.tmp, "prompts", "dev")
        os.makedirs(os.path.join(prm, "subjects"))
        os.makedirs(os.path.join(prm, "exam"))
        os.makedirs(cfg)
        shutil.copy(os.path.join(ROOT, "prompts", "dev", "system.md"), prm)
        shutil.copy(os.path.join(ROOT, "prompts", "dev", "exam", "solve.md"),
                    os.path.join(prm, "exam", "solve.md"))
        with open(os.path.join(prm, "subjects", "chem.md"), "w") as fh:
            fh.write("ADDENDUM-CHEM-ZZ: use atomic masses.\n")
        subj = settings.load_config("subjects")
        subj["chemistry"] = {"aliases": ["chemistry"], "task": "Closed",
                             "checks": ["format"], "score_basis": "official_key",
                             "language": "en", "prompt": "subjects/chem.md"}
        with open(os.path.join(cfg, "subjects.json"), "w") as fh:
            json.dump(subj, fh)
        with open(os.path.join(cfg, "engine.json"), "w") as fh:
            json.dump(settings.load_config("engine"), fh)
        path = os.path.join(self.tmp, "chem.md")
        with open(path, "w") as fh:
            fh.write(CHEM)
        self.assertTrue(parser.validate_exam(parser.parse_exam(path)))  # unknown without entry
        with mock.patch.dict(os.environ, {"EXAM_ENGINE_CONFIG_DIR": cfg}), \
                mock.patch.object(settings, "PROMPTS_DIR", os.path.dirname(prm)), \
                mock.patch.dict(settings.PROMPT_SOURCE, {"channel": "dev"}):
            exam = parser.parse_exam(path)
            self.assertEqual(parser.validate_exam(exam), [])
            self.assertIn("ADDENDUM-CHEM-ZZ", solver.base_prompt(exam))
        env = dict(os.environ, EXAM_ENGINE_CONFIG_DIR=cfg)
        code, out, _ = run(EXAM, "parse", path, cwd=self.tmp, env=env)
        self.assertEqual(code, 0)


class CwdAndReadme(Base):
    def test_cwd_independence_of_subcommands(self):
        a = run(EXAM, "solve", INPUT, "--dry-run", cwd=self.tmp)
        b = run(EXAM, "solve", INPUT, "--dry-run", cwd=ROOT)
        self.assertEqual(a, b)
        self.assertEqual(a[0], 0)
        self.assertEqual(run(EXAM, "parse", INPUT, cwd=self.tmp)[0], 0)
        self.assertEqual(run(EXAM, "check-examples", cwd=self.tmp)[0], 0)

    def test_6_6_readme_documents_structure(self):
        t = text(os.path.join(ROOT, "README.md"))
        for word in ("src/exam_engine", "scripts/exam.py", "prompts/", "schemas/", "config/",
                     "adapters/claude.py", "subjects.json", "tests/", "tools/examples"):
            self.assertIn(word, t)
        for sub in ("solve", "parse", "verify", "report"):
            self.assertRegex(t, r"exam\.py %s" % sub)


if __name__ == "__main__":
    unittest.main()

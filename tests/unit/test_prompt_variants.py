"""Phase 10 (REQ-0014): prompt language variants + check-prompts. Every mutation happens in a temp
copy of prompts/ (real files never edited); variants the tests need are built there."""
import contextlib
import io
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
from exam_engine.pipeline import prompts, solver, verifier  # noqa: E402

SYS_VI = "VI-SYSTEM answer_status uncertain unanswerable not_independently_verified uncertainty issues sqrt(3)\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pv_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.prm = os.path.join(self.tmp, "prompts")
        os.makedirs(os.path.join(self.prm, "releases"))
        shutil.copytree(os.path.join(ROOT, "prompts", "dev"), os.path.join(self.prm, "dev"),
                        ignore=shutil.ignore_patterns("lang"))
        shutil.copy(os.path.join(ROOT, "prompts", "contract.json"), self.prm)
        for p in (mock.patch.object(settings, "PROMPTS_DIR", self.prm),
                  mock.patch.dict(settings.PROMPT_SOURCE, {"channel": "dev", "version": None})):
            p.start()
            self.addCleanup(p.stop)
        self.dev = os.path.join(self.prm, "dev")

    def path(self, *parts):
        return os.path.join(self.dev, *parts)

    def read(self, *parts):
        with open(self.path(*parts), encoding="utf-8") as fh:
            return fh.read()

    def write(self, text, *parts):
        os.makedirs(os.path.dirname(self.path(*parts)), exist_ok=True)
        with open(self.path(*parts), "w", encoding="utf-8") as fh:
            fh.write(text)

    def copy_variant(self, code="vi"):
        """lang/<code> = a verbatim copy of the default files (valid by construction)."""
        for rel in ("system.md", "exam/solve.md", "verification/verify_answer.md"):
            self.write(self.read(rel), "lang", code, rel)

    def check(self):
        return prompts.check_prompts("dev")

    def errors(self):
        return self.check()[0]


class Validator(Base):
    def test_default_only_is_ok(self):
        errs, files, variants = self.check()
        self.assertEqual((errs, variants), ([], 0))
        self.assertGreaterEqual(files, 3)

    def test_valid_variant_counts(self):
        self.copy_variant()
        errs, _, variants = self.check()
        self.assertEqual((errs, variants), ([], 1))

    def test_dropped_marker(self):
        self.copy_variant()
        rel = ("lang", "vi", "verification", "verify_answer.md")
        self.write(self.read(*rel).replace("disagree", "khong"), *rel)
        errs = self.errors()
        self.assertTrue(any("lang/vi/verification/verify_answer.md: missing marker 'disagree'" in e
                            for e in errs), errs)

    def test_changed_output_key(self):
        self.copy_variant()
        rel = ("lang", "vi", "verification", "verify_answer.md")
        self.write(self.read(*rel).replace('"findings":[]}', '"nhan_xet":[]}'), *rel)
        errs = self.errors()
        self.assertTrue(any("not in schema qa_out" in e for e in errs), errs)
        self.assertTrue(any("key structure differs" in e for e in errs), errs)

    def test_output_example_missing(self):
        self.copy_variant()
        rel = ("lang", "vi", "exam", "solve.md")
        self.write(self.read(*rel).replace('{"schema_version"', '{"schema"'), *rel)
        self.assertTrue(any("anchor" in e and "not found" in e for e in self.errors()))

    def test_stray_file_under_lang(self):
        self.copy_variant()
        self.write("x", "lang", "vi", "exam", "solv.md")
        errs = self.errors()
        self.assertTrue(any("lang/vi/exam/solv.md: file not in the prompt contract" in e for e in errs), errs)

    def test_stray_file_directly_in_lang(self):
        self.write("x", "lang", "notes.txt")
        self.assertTrue(any("lang/notes.txt: stray file" in e for e in self.errors()))

    def test_bad_code(self):
        self.copy_variant("xyz")
        errs = self.errors()
        self.assertTrue(any("lang/xyz: bad variant code" in e for e in errs), errs)

    def test_missing_default_file(self):
        os.remove(self.path("exam", "solve.md"))
        self.assertTrue(any("dev/exam/solve.md: missing default file" in e for e in self.errors()))

    def test_literature_variant_needs_passage(self):
        self.write("Van ban\n", "lang", "vi", "subjects", "literature.md")
        self.assertTrue(any("missing marker 'Passage'" in e for e in self.errors()))

    def test_cli_exit_codes_and_lines(self):
        def run(*a):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cli.main(["check-prompts"] + list(a))
            return code, buf.getvalue()
        code, out = run("--channel", "dev")
        self.assertEqual((code, out.startswith("OK: ")), (0, True), out)
        os.remove(self.path("system.md"))
        code, out = run("--channel", "dev")
        self.assertEqual(code, 1)
        self.assertIn("ERROR dev/system.md: missing default file", out)

    def test_real_prompts_pass(self):
        with mock.patch.object(settings, "PROMPTS_DIR", os.path.join(ROOT, "prompts")):
            errs, _, _ = prompts.check_prompts(all_=True)
        self.assertEqual(errs, [])


class Lookup(Base):
    def exam(self, lang):
        return {"fields": {"Language": lang, "Subject": "Literature"}, "questions": [],
                "instructions": "", "passage": ""}

    def test_fallback_to_default_when_variant_lacks_file(self):
        self.write(SYS_VI, "lang", "vi", "system.md")
        self.assertIn("VI-SYSTEM", settings.read_prompt("system.md", "vi"))
        self.assertEqual(settings.read_prompt("exam/solve.md", "vi"), settings.read_prompt("exam/solve.md"))

    def test_none_and_unknown_lang_use_default(self):
        self.write(SYS_VI, "lang", "vi", "system.md")
        self.assertNotIn("VI-SYSTEM", settings.read_prompt("system.md"))
        self.assertNotIn("VI-SYSTEM", settings.read_prompt("system.md", "fr"))

    def test_language_vi_picks_variant_en_picks_default(self):
        self.write(SYS_VI, "lang", "vi", "system.md")
        self.write("VI-LIT Passage\n", "lang", "vi", "subjects", "literature.md")
        self.assertIn("VI-SYSTEM", solver.base_prompt(self.exam("vi")))
        self.assertIn("VI-LIT", solver.base_prompt(self.exam("vi")))
        en = solver.base_prompt(self.exam("en"))
        self.assertNotIn("VI-SYSTEM", en)
        self.assertNotIn("VI-LIT", en)

    def test_qa_prompt_language(self):
        self.write("VI-QA verdict agree disagree unsure findings reviews\n",
                   "lang", "vi", "verification", "verify_answer.md")
        for lang, want in (("vi", True), ("en", False)):
            ex = self.exam(lang)
            ex["questions"] = [{"id": "1", "text": "q", "options": {}}]
            recs = {"1": {"ans": {"answer": "A"}, "checks": []}}
            # qa_prompt sorts ids; ids here are the question ids as stored
            ex["questions"][0]["id"] = "1"
            text = verifier.qa_prompt(ex, recs, ["1"])
            self.assertEqual("VI-QA" in text, want)


if __name__ == "__main__":
    unittest.main()

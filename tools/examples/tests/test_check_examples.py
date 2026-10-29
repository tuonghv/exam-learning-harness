"""Tests 1-12 and 15 of docs/design/phase-3-example-checker.md (AC1-AC3, AC5)."""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(TOOLS))
sys.path.insert(0, TOOLS)
import check_examples as ce  # noqa: E402

Q_EN = "If I ______ enough time tomorrow,\nI will help you prepare."
OPTS = "A. have\nB. had\nC. will have\nD. would have"
PASSAGE = "The sea was calm. \"A quiet dawn broke\" and \"the birds sang loudly\" overhead."


def inp(subject, task, qtext, opts="", mode="Solve", extra=""):
    return ("# Exam Input\n\nSubject: %s\nLevel: Grade 12\nExam type: Test\nTask: %s\nMode: %s\n\n"
            "## Instructions\n\nAnswer.\n\n%s## Question 1\n\n%s\n\n%s\n"
            % (subject, task, mode, extra, qtext, opts))


def exp(final, sol="The first conditional uses present simple in the if clause.",
        verif=None, interp=None, outline=True, expl="Because of grammar rules explained here."):
    if verif is None:
        verif = "- Check: tense\n- Final answer: %s\n- Status: Verified" % final
    s = "# Expected Output\n\n## Question 1\n\nFinal answer: %s\n\n" % final
    s += "### Solution\n%s\n\n### Explanation\n%s\n\n" % (sol, expl)
    if interp is not None:
        s += "### Accepted interpretations\n%s\n\n" % interp
    if outline:
        s += "### Model answer outline\nOutline.\n\n"
    s += "### Verification\n%s\n\n### Grading\n1 point.\n" % verif
    return s


def lit_exp(**kw):
    kw.setdefault("interp", '- "A quiet dawn broke" shows calm.\n- "the birds sang loudly" shows joy.')
    return exp("Open (rubric)", **kw)


def valid():
    return {
        "examples/english/input-001.md": inp("English", "Multiple Choice", Q_EN, OPTS),
        "examples/english/expected-001.md": exp("A"),
        "examples/literature/input-001.md": inp(
            "Literature", "Reading Comprehension", "What mood is shown?", "",
            extra="## Passage\n\n%s\n\n" % PASSAGE),
        "examples/literature/expected-001.md": lit_exp(),
        "evals/inputs/math/input-003.md": inp("Mathematics", "Short Answer", "Compute 2.5 + 0.0 now."),
        "evals/keys/math/expected-003.md": exp(
            "2.5", sol="Add the two numbers together and get the value exactly.",
            expl="Plain addition of decimals, nothing more is needed here."),
    }


def write(root, files):
    for rel, text in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)


class Base(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = td.name

    def run_main(self, files):
        for n in os.listdir(self.root):  # fresh tree per call (subTests reuse root)
            shutil.rmtree(os.path.join(self.root, n))
        write(self.root, files)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = ce.main(["--root", self.root])
        return rc, out.getvalue()

    def assertFails(self, files, chk, fname=None):
        rc, out = self.run_main(files)
        self.assertEqual(rc, 1, out)
        hits = [l for l in out.splitlines() if l.startswith("ERROR") and (": %s: " % chk) in l
                and (fname is None or fname in l)]
        self.assertTrue(hits, "no %s/%s error in:\n%s" % (chk, fname, out))


class Check(Base):
    def test_01_valid_fixture(self):  # AC1
        rc, out = self.run_main(valid())
        self.assertEqual(rc, 0, out)
        self.assertIn("OK: 3 pairs (2 few-shot, 1 eval)", out)

    def test_02_missing_pair(self):  # AC1
        for gone in ("examples/english/expected-001.md", "examples/english/input-001.md"):
            with self.subTest(gone=gone):
                f = valid()
                del f[gone]
                self.assertFails(f, "pairing", "examples/english/")

    def test_03_eval_pairing(self):  # AC1
        for gone in ("evals/keys/math/expected-003.md", "evals/inputs/math/input-003.md"):
            with self.subTest(gone=gone):
                f = valid()
                del f[gone]
                self.assertFails(f, "pairing", "math/")

    def test_04_disjoint_id(self):  # AC2
        f = valid()
        f["evals/inputs/english/input-001.md"] = inp("English", "Short Answer", "Different thing here?")
        f["evals/keys/english/expected-001.md"] = exp(
            "x", sol="Totally unrelated words to avoid any leak detection here.")
        self.assertFails(f, "disjoint-id", "evals/inputs/english/input-001.md")

    def test_05_disjoint_text(self):  # AC2
        f = valid()
        changed = Q_EN.upper().replace("\n", "   \n  ")
        f["evals/inputs/english/input-003.md"] = inp("English", "Multiple Choice", changed, OPTS)
        f["evals/keys/english/expected-003.md"] = exp(
            "B", sol="Wholly different wording avoids leaks in this fixture ok.",
            expl="Another unrelated explanation sentence for the fixture ok.")
        self.assertFails(f, "disjoint-text", "evals/inputs/english/input-003.md")

    def test_06_input_key(self):  # AC3
        for extra in ("### Solution\nx\n", "Final answer: A\n", "Correct answer: A\n"):
            with self.subTest(extra=extra):
                f = valid()
                f["evals/inputs/math/input-003.md"] = inp(
                    "Mathematics", "Short Answer", "Compute 2.5 + 0.0 now.", extra=extra + "\n")
                self.assertFails(f, "input-key", "evals/inputs/math/input-003.md")

    def test_07_key_leak(self):  # AC3
        sol = "Add the two numbers together and get the value exactly."
        f = valid()
        f["examples/english/expected-001.md"] = exp("A", sol=sol)
        self.assertFails(f, "key-leak", "evals/keys/math/expected-003.md")
        # leak into an eval input
        f = valid()
        f["evals/inputs/math/input-003.md"] = inp(
            "Mathematics", "Short Answer", "Compute 2.5 + 0.0 now.", extra="Hint: %s\n\n" % sol)
        self.assertFails(f, "key-leak", "evals/keys/math/expected-003.md")

    def test_07b_quoted_passage_line_is_not_a_leak(self):  # AC3
        quoted = '"The quick brown fox jumps over the lazy dog again and again"'
        f = valid()
        f["evals/keys/math/expected-003.md"] = exp("2.5", sol=quoted)
        f["examples/english/expected-001.md"] = exp("A", sol=quoted)
        rc, out = self.run_main(f)
        self.assertEqual(rc, 0, out)

    def test_08_header(self):  # AC1
        base = valid()["examples/english/input-001.md"]
        cases = {
            "missing": base.replace("Level: Grade 12\n", ""),
            "bad enum": base.replace("Mode: Solve", "Mode: Cheat"),
            "subject": base.replace("Subject: English", "Subject: Physics"),
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                f = valid()
                f["examples/english/input-001.md"] = text
                self.assertFails(f, "header", "examples/english/input-001.md")

    def test_09_options(self):  # AC1
        for name, opts in (("three", "A. have\nB. had\nC. will have"),
                           ("E", OPTS + "\nE. might have")):
            with self.subTest(name=name):
                f = valid()
                f["examples/english/input-001.md"] = inp("English", "Multiple Choice", Q_EN, opts)
                self.assertFails(f, "options", "examples/english/input-001.md")

    def test_10_verification(self):  # AC1
        cases = {
            "no check": "- Final answer: A\n- Status: Verified",
            "unverified": "- Check: x\n- Final answer: A\n- Status: Unverified",
            "mismatch": "- Check: x\n- Final answer: B\n- Status: Verified",
            "no status": "- Check: x\n- Final answer: A",
        }
        for name, v in cases.items():
            with self.subTest(name=name):
                f = valid()
                f["examples/english/expected-001.md"] = exp("A", verif=v)
                self.assertFails(f, "verification", "examples/english/expected-001.md")

    def test_11_literature_quotes(self):  # AC1
        f = valid()
        f["examples/literature/expected-001.md"] = lit_exp(
            interp='- "A quiet dawn broke" ok.\n- "never said in passage" bad.')
        self.assertFails(f, "literature", "examples/literature/expected-001.md")
        f = valid()
        f["examples/literature/expected-001.md"] = lit_exp(
            interp='- “A quiet dawn broke” ok.\n- “the birds sang loudly” ok.')
        rc, out = self.run_main(f)
        self.assertEqual(rc, 0, out)

    def test_12_legacy_expected_001(self):  # AC1
        src = os.path.join(REPO, "examples", "english")
        dst = os.path.join(self.root, "examples", "english")
        shutil.copytree(src, dst)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = ce.main(["--root", self.root])
        self.assertEqual(rc, 0, out.getvalue())
        self.assertIn("NOTE: legacy allowance: examples/english/expected-001.md", out.getvalue())
        with open(os.path.join(dst, "expected-001.md"), "a", encoding="utf-8") as fh:
            fh.write("x")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = ce.main(["--root", self.root])
        self.assertEqual(rc, 1, out.getvalue())

    def test_12b_real_repo_passes(self):  # AC1
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = ce.main(["--root", REPO])
        self.assertEqual(rc, 0, out.getvalue())

    def test_15_subprocess_isolated(self):  # AC5
        write(self.root, valid())
        r = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "check_examples.py"),
                            "--root", self.root], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.strip().splitlines()[-1].startswith("OK:"))
        self.assertEqual(subprocess.run(
            [sys.executable, "-I", os.path.join(TOOLS, "check_examples.py"), "--bogus"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode, 2)


if __name__ == "__main__":
    unittest.main()

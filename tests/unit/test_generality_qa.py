"""TASK-062 QA: multi-language merge, metachar/ReDoS escape, bad config fails loudly, data-only probe ($0)."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "..", "src"))
CONFIG = os.path.abspath(os.path.join(HERE, "..", "..", "config"))
sys.path.insert(0, SRC)

from exam_engine.core import refcheck  # noqa: E402
from exam_engine.ingest import segment  # noqa: E402
from exam_engine.ingest.adapters import pdf  # noqa: E402
from exam_engine.pipeline import cross, verifier  # noqa: E402
from exam_engine.utils import langtable  # noqa: E402

META = {"a.b": 1}
EVIL = ["a.b", "(x", "[", "*", "a|b", "\\", "(a+)+$", "?", "+"]
ALL = {"extra": {"x": {s: EVIL for s in langtable.SLOTS if s != "scripts"}}}


def run_py(code, cfg=None):
    env = {k: v for k, v in os.environ.items() if k != "EXAM_ENGINE_CONFIG_DIR"}
    if cfg:
        env["EXAM_ENGINE_CONFIG_DIR"] = cfg
    return subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r)\n%s" % (SRC, code)],
                          capture_output=True, text=True, env=env, timeout=60)


def cfg_dir(test, lang=None, subjects=None):
    d = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, d, True)
    for f in os.listdir(CONFIG):
        shutil.copy(os.path.join(CONFIG, f), d)
    if lang is not None:
        with open(os.path.join(d, "lang.json"), "w", encoding="utf-8") as fh:
            fh.write(lang if isinstance(lang, str) else json.dumps(lang, ensure_ascii=False))
    if subjects is not None:
        with open(os.path.join(d, "subjects.json"), "w", encoding="utf-8") as fh:
            json.dump(subjects, fh, ensure_ascii=False)
    return d


class Merge(unittest.TestCase):  # 62.1 mutation: drop vi, en or an extra language
    def test_two_languages_and_builtins_kept(self):
        t = {"extra": {"fr": {"part": ["PARTIE"], "question": ["Exercice"], "true": ["vrai"]},
                       "de": {"part": ["TEIL"], "question": ["Aufgabe"], "true": ["richtig"]}}}
        self.assertEqual(langtable.raw("part", t), ["PARTIE", "TEIL"])
        ns = segment.build(t)
        for s in ("PARTIE 1", "TEIL 2", "PART 3", "PHẦN 4", "PHAN 5"):
            self.assertTrue(ns._PART_ANY.match(s), s)
        for s in ("Exercice 1", "Aufgabe 2", "Question 3", "Câu 4", "Cau 5"):
            self.assertTrue(ns._Q.match(s), s)
        rx = verifier.verdict_re(t)
        self.assertEqual([w.lower() for w in rx.findall("vrai richtig đúng sai true F")],
                         ["vrai", "richtig", "đúng", "sai", "true", "f"])
        tf = cross.tf_map(t)
        self.assertEqual((tf["vrai"], tf["richtig"], tf["đúng"], tf["sai"], tf["false"]), ("T", "T", "T", "F", "F"))

    def test_casefold_lookup(self):
        t = {"extra": {"de": {"true": ["Richtig"], "false": ["FALSCH"]}}}
        tf = cross.tf_map(t)
        rx = verifier.verdict_re(t)
        self.assertEqual("".join(tf[w.casefold()] for w in rx.findall("RICHTIG falsch")), "TF")

    def test_longest_first(self):
        t = {"extra": {"x": {"question": ["Ex", "Exercice"]}}}
        self.assertTrue(re.match(langtable.alt("(?:Q)", "question", t) + r"\s*1", "Exercice 1"))


class Escape(unittest.TestCase):  # metachar words never reach the regex engine raw
    def test_every_builder_compiles_and_is_literal(self):
        ns = segment.build(ALL)
        for rx in (ns._Q, ns.GROUP_RE, ns._INTRO, ns._PART, ns._PART_ANY):
            rx.pattern  # compiled without error
        pars, fig, needs = refcheck.build(ALL)
        self.assertTrue(pars and fig.search("a.b") and not fig.search("axb"))
        self.assertTrue(needs.search("a.b") and not needs.search("axb"))
        self.assertTrue(pars[0].search("a.b 3") and not pars[0].search("axb 3"))
        self.assertTrue(pdf.page_re(ALL).match("a.b 2") and not pdf.page_re(ALL).match("axb 2"))
        rx = verifier.verdict_re(ALL)
        self.assertTrue(rx.findall("a.b") and not rx.findall("axb"))
        self.assertIn("a.b", cross.tf_map(ALL))  # dict key is literal, not a pattern

    def test_alternation_word_stays_one_word(self):
        ns = segment.build({"extra": {"x": {"question": ["a|b"]}}})
        self.assertTrue(ns._Q.match("a|b 1"))
        self.assertIsNone(ns._Q.match("b 1"))  # `|` did not split the word

    def test_no_catastrophic_backtracking(self):
        ns = segment.build(ALL)
        rx = verifier.verdict_re(ALL)
        pars, fig, needs = refcheck.build(ALL)
        text = "a" * 5000 + "!"
        t0 = time.time()
        for r in (ns._Q, ns.GROUP_RE, ns._INTRO, ns._PART_ANY, rx, fig, needs, pars[0], pdf.page_re(ALL)):
            r.search(text)
        self.assertLess(time.time() - t0, 5)


class BadConfig(unittest.TestCase):  # failure modes: never a silent fallback to wrong data
    def test_import_fails_naming_file(self):
        for bad in ("{", "[]", "{}", '{"extra": null}', '{"extra": {"fr": {"nope": ["a"]}}}',
                    '{"extra": {"fr": {"part": [""]}}}', '{"extra": {"fr": {"part": "PARTIE"}}}',
                    '{"extra": {"fr": {"part": [1]}}}', '{"extra": {"fr": ["part"]}}'):
            d = cfg_dir(self, lang=bad)
            for mod in ("ingest.segment", "pipeline.cross", "pipeline.verifier", "core.refcheck"):
                r = run_py("import exam_engine.%s" % mod, d)
                self.assertNotEqual(r.returncode, 0, (bad, mod))
                self.assertIn("lang.json", r.stderr, (bad, mod))

    def test_binary_file_fails(self):
        d = cfg_dir(self)
        with open(os.path.join(d, "lang.json"), "wb") as fh:
            fh.write(b"\xff\xfe\x00")
        r = run_py("import exam_engine.ingest.segment", d)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Error", r.stderr)

    def test_missing_file_is_builtin(self):
        d = cfg_dir(self)
        os.remove(os.path.join(d, "lang.json"))
        r = run_py("from exam_engine.ingest import segment; print(bool(segment._Q.match('Question 1')))", d)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "True"), r.stderr[-300:])

    def test_bad_profile_file_fails_clearly(self):
        d = cfg_dir(self)
        with open(os.path.join(d, "genexam_profiles.json"), "w") as fh:
            fh.write("{")
        r = run_py("import exam_engine.pipeline.genexam", d)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("genexam_profiles", r.stderr)


class Probe(unittest.TestCase):
    """Synthetic non-DGNL exam: French words + German verdicts + a chemistry subject, data-only (no code edit)."""

    def test_data_only(self):
        with open(os.path.join(CONFIG, "subjects.json"), encoding="utf-8") as fh:
            subj = json.load(fh)
        subj["chemistry"] = {"aliases": ["chemistry", "chimie"], "task": "Closed", "checks": ["format", "quote"],
                             "score_basis": "official_key", "language": "en", "prompt": "subjects/math.md",
                             "answer_shapes": ["number"]}
        lang = {"extra": {"fr": {"question": ["Exercice"], "part": ["PARTIE"], "true": ["vrai"], "false": ["faux"],
                                 "paragraph": ["paragraphe"]}}}
        d = cfg_dir(self, lang=lang, subjects=subj)
        code = r"""
from exam_engine.ingest import segment, refine
from exam_engine.pipeline import cross, router
from exam_engine.core import refcheck
lines = ["PARTIE I", "Exercice 1 Eau ?", "A. H2O", "B. CO2", "Exercice 2 Gaz ?", "A. N2", "B. O2", "PARTIE II", "Exercice 3 Na ?"]
intro, qs, ok = segment.segment(lines)
print([q["n"] for q in qs])
print(refine.split_part("PARTIE II\ncorps"))
print(cross.canon("a) vrai b) faux c) vrai d) faux"))
print(router.policy("chimie")["key"], router.policy("chimie")["answer_shapes"])
print(refcheck.referenced_parts("Lisez le paragraphe (2)"))
"""
        r = run_py(code, d)
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        out = r.stdout.strip().splitlines()
        self.assertEqual(out[0], "[1, 2, 3]")
        self.assertEqual(out[1], "('II', 'corps')")
        self.assertEqual(out[2], "V:TFTF")
        self.assertEqual(out[3], "chemistry ['number']")
        self.assertEqual(out[4], "['paragraph (2)']")
        # the same program on the default config knows none of it
        r0 = run_py(code)
        self.assertNotEqual(r0.stdout.strip().splitlines()[:1], ["[1, 2, 3]"], r0.stderr[-200:])


if __name__ == "__main__":
    unittest.main()

"""TASK-062 62.1-62.3: extra-language word table; synthetic non-vi/en fixtures built here ($0)."""
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))

from exam_engine.core import refcheck  # noqa: E402
from exam_engine.ingest import refine, segment  # noqa: E402
from exam_engine.ingest.adapters import pdf  # noqa: E402
from exam_engine.pipeline import cross, verifier  # noqa: E402
from exam_engine.utils import langtable  # noqa: E402

FR = {"extra": {"fr": {"question": ["Exercice"], "part": ["PARTIE"], "range": ["à"], "page": ["Seite"],
                       "group": ["Exercices"], "paragraph": ["paragraphe"], "figure": ["figure ci-dessous"]}}}
DE = {"extra": {"de": {"true": ["richtig"], "false": ["falsch"]}}}


class Table(unittest.TestCase):
    def cfg(self, text=None):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, True))
        if text is not None:
            with open(os.path.join(d, "lang.json"), "w", encoding="utf-8") as fh:
                fh.write(text)
        return d

    def test_load(self):
        self.assertEqual(langtable.load(self.cfg()), {"extra": {}})
        self.assertEqual(langtable.load(self.cfg('{"extra": {}}')), {"extra": {}})
        self.assertEqual(langtable.load(self.cfg(json.dumps(FR))), FR)
        for bad in ("{", "[]", '{"extra": {"x": {"nope": ["a"]}}}', '{"extra": {"x": {"part": "A"}}}'):
            with self.assertRaises(ValueError) as cm:
                langtable.load(self.cfg(bad))
            self.assertIn("lang.json", str(cm.exception))

    def test_alt_and_escape(self):
        self.assertEqual(langtable.alt("(?:a|b)", "part", {"extra": {}}), "(?:a|b)")
        t = {"extra": {"x": {"part": ["a.b", "(x"]}}}
        rx = re.compile(langtable.alt("(?:Z)", "part", t))
        self.assertTrue(rx.fullmatch("a.b"))
        self.assertFalse(rx.fullmatch("axb"))
        self.assertTrue(rx.fullmatch("(x"))


class Ingest(unittest.TestCase):  # 62.1
    def test_french_exam(self):
        ns = segment.build(FR)
        lines = ["Consigne", "PARTIE 1", "Exercice 1 Un", "2. Deux", "3) Trois", "Exercices 4 à 5 lire", "Exercice 4 Quatre",
                 "Exercice 5 Cinq", "Exercice 6 Six"]
        with mock.patch.multiple(segment, _Q=ns._Q, GROUP_RE=ns.GROUP_RE, _INTRO=ns._INTRO,
                                 _PART=ns._PART, _PART_ANY=ns._PART_ANY):
            intro, qs, ok = segment.segment(lines)
        self.assertEqual([q["n"] for q in qs], [1, 2, 3, 4, 5, 6])
        self.assertTrue(ns._PART_ANY.match("PARTIE 2") and ns._PART_ANY.match("PART II"))
        self.assertEqual(segment.group_span(ns.GROUP_RE.search("Exercices 3 à 5")), (3, 5))
        self.assertTrue(ns._INTRO.match("Exercices 3 à 5 lisez"))
        self.assertIsNone(segment._PART_ANY.match("PARTIE 2"))  # default config unchanged
        self.assertTrue(pdf.page_re(FR).match("Seite 2"))
        self.assertIsNone(pdf.page_re(FR).match("Seite 2 von 4"))  # `von` is not in the table: kept (documented limit)
        self.assertTrue(pdf.page_re(FR).match("- 2 -"))
        self.assertIsNone(pdf._PAGE_NO.match("Seite 2"))

    def test_english_only_unchanged(self):
        ns = segment.build({"extra": {}})
        self.assertEqual(ns._Q.pattern, segment._Q.pattern)
        self.assertTrue(ns._Q.match("Question 1"))
        self.assertEqual(ns._PART_ANY.match("PART II").group(0), "PART II")
        self.assertEqual(refine.split_part("PART II\nbody"), ("II", "body"))

    def test_part_word_in_refine(self):
        self.assertEqual(refine.split_part("PHẦN II\nbody"), ("II", "body"))


class Verdicts(unittest.TestCase):  # 62.2
    def test_german(self):
        rx = verifier.verdict_re(DE)
        tf = cross.tf_map(DE)
        found = rx.findall("a) richtig b) Falsch c) richtig d) falsch")
        self.assertEqual("".join(tf[w.casefold()] for w in found), "TFTF")
        with mock.patch.object(verifier, "_VERDICT", rx), mock.patch.object(cross, "_TF", tf):
            self.assertEqual(cross.canon("a) richtig b) falsch c) richtig d) falsch"), "V:TFTF")
            self.assertNotEqual(cross.canon("Die Antwort ist richtig und falsch"), "V:TFTF")
        self.assertEqual(cross.canon("a) Đ b) S c) T d) F"), "V:TFTF")  # default table
        self.assertEqual(verifier.verdict_re({"extra": {}}).pattern, verifier._VERDICT.pattern)


class Refs(unittest.TestCase):  # 62.3
    def test_french(self):
        pars, fig, needs = refcheck.build(FR)
        with mock.patch.object(refcheck, "_PAR_X", pars), mock.patch.object(refcheck, "_FIG", fig):
            self.assertEqual(refcheck.referenced_parts("Lisez le paragraphe (3) puis répondez"), ["paragraph (3)"])
            self.assertEqual(refcheck.referenced_parts("Voir la figure ci-dessous"), ["figure/table"])
            self.assertEqual(refcheck.referenced_parts("paragraphe 2\n(2) texte"), [])
        self.assertEqual(refcheck.referenced_parts("Lisez le paragraphe (3)"), [])  # default unchanged
        self.assertEqual(refcheck.build({"extra": {}})[1].pattern, refcheck._FIG.pattern)


if __name__ == "__main__":
    unittest.main()

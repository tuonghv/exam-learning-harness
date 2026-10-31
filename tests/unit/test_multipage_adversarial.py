"""TASK-040 QA (tester): adversarial bridge cases. Mock replies, synthetic placeholder text only."""
import itertools
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_multipage_assembly import ABCD, C, doc_of, q, rep, run_refine  # noqa: E402

from exam_engine.core import refcheck  # noqa: E402
from exam_engine.ingest import refine  # noqa: E402


def texts(out):
    return [x["text"] for x in out["refined"]["questions"]]


class TestBridgeAdversarial(unittest.TestCase):
    def test_a1_chain_over_5_pages_one_question_no_loss(self):
        rs = [rep([q(1, "first", ABCD), q(2, "stem2", cut=True)])]
        rs += [rep(continues={"text": "part%d" % i}) for i in (2, 3, 4)]
        rs += [rep(continues={"text": "part5", "options": ABCD})]
        out = run_refine(rs, "1-5", 5)
        qs = out["refined"]["questions"]
        self.assertEqual([x["id"] for x in qs], ["1", "2"])
        self.assertEqual(qs[1]["text"], "stem2\npart2\npart3\npart4\npart5")
        self.assertEqual(qs[1]["options"], ABCD)
        self.assertEqual(qs[1]["continued_pages"], [2, 3, 4, 5])
        self.assertEqual(qs[0]["text"], "first")

    def test_a2_continuation_on_first_page_is_orphan(self):
        out = run_refine([rep(continues={"text": "tail tail", "options": ABCD}),
                          rep([q(1, "t1", ABCD)])], "1-2", 2)
        self.assertEqual(len(out["refined"]["questions"]), 1)
        self.assertEqual(out["refined"]["questions"][0]["text"], "t1")
        self.assertEqual(out["refined"]["orphans"][0]["page"], 1)

    def test_a3_skipped_page_orphan_warning_names_prev(self):
        out = run_refine([rep([q(1, "s1", cut=True)]),
                          rep(continues={"text": "late"})], "1,3", 3)
        self.assertEqual(texts(out), ["s1"])
        w = [x for x in out["warnings"] if x["code"] == "orphan_continuation"][0]["message"]
        self.assertIn("page(s) 3", w)
        self.assertIn("add page(s) 2", w)

    def test_a4_continuation_starting_with_number_is_orphan(self):
        out = run_refine([rep([q(1, "s1", cut=True)]),
                          rep(continues={"text": "2. new question text", "options": ABCD})], "1-2", 2)
        self.assertEqual(texts(out), ["s1"])
        self.assertEqual(out["refined"]["orphans"][0]["kind"], "starts_with_number")

    def test_a5_duplicate_overlap_not_repeated(self):
        tail = "a repeated line long enough to count"
        out = run_refine([rep([q(1, "stem " + tail, cut=True)]),
                          rep(continues={"text": tail + " and more"})], "1-2", 2)
        self.assertEqual(texts(out)[0].count(tail), 1)
        self.assertTrue(texts(out)[0].endswith("and more"))

    def test_a6_options_when_owner_has_options_is_orphan_and_keeps_old(self):
        other = {"A": "w", "B": "x", "C": "y", "D": "z"}
        out = run_refine([rep([q(1, "s1", ABCD)]), rep(continues={"options": other})], "1-2", 2)
        self.assertEqual(out["refined"]["questions"][0]["options"], ABCD)
        self.assertEqual(out["refined"]["orphans"][0]["kind"], "owner_has_options")

    def test_a7_passage_continues_without_carry_is_orphan_not_lost_question(self):
        out = run_refine([rep([q(1, "s1", ABCD)]),
                          rep([q(2, "s2", ABCD)], continues={"text": "para", "passage": True})], "1-2", 2)
        self.assertEqual([x["id"] for x in out["refined"]["questions"]], ["1", "2"])

    def test_a8_huge_continuation_200kb(self):
        big = ("lorem ipsum " * 17000)[:200000]
        out = run_refine([rep([q(1, "s1", cut=True)]), rep(continues={"text": big})], "1-2", 2)
        self.assertEqual(len(texts(out)[0]), len("s1\n") + len(big.strip()))

    def test_a9_wrong_types_are_validation_errors(self):
        for bad in ("str", ["x"], 5):
            with self.assertRaises(refine.RefineError):
                refine_once([rep([q(1, "s1")], continues=bad)])
        for bad in ({"text": None}, {"text": 3}, {"options": ["A"]}, {"options": {"A": 1}},
                    {"figures": "f"}, {"passage": "yes"}):
            with self.assertRaises(refine.RefineError, msg=str(bad)):
                refine_once([rep([q(1, "s1")], continues=bad)])
        out = run_refine([rep([q(1, "s1")], continues=None)], "1", 1)  # null is accepted = absent
        self.assertEqual(texts(out), ["s1"])

    def test_a10_legacy_empty_id_no_loss_no_dup(self):
        out = run_refine([rep([q(1, "s1"), q(2, "stem2")]),
                          rep([q("", "tail2", ABCD), q(3, "s3", ABCD)])], "1-2", 2)
        qs = out["refined"]["questions"]
        self.assertEqual([x["id"] for x in qs], ["1", "2", "3"])
        self.assertEqual(qs[1]["options"], ABCD)
        self.assertEqual(qs[0]["options"], {})
        self.assertIn("tail2", qs[1]["text"])

    def test_a11_owner_is_last_question_of_prev_page(self):
        out = run_refine([rep([q(1, "s1"), q(2, "s2"), q(3, "s3", cut=True)]),
                          rep(continues={"text": "rest", "options": ABCD})], "1-2", 2)
        qs = out["refined"]["questions"]
        self.assertEqual([x["options"] for x in qs], [{}, {}, ABCD])
        self.assertEqual(texts(out), ["s1", "s2", "s3\nrest"])

    def test_a12_options_reasons_cases(self):
        r = refcheck.incomplete_reasons
        self.assertEqual(r({"text": "t", "options": {}}), [])  # numeric answer, no options
        self.assertEqual(r({"text": "t", "options": ABCD}), [])
        self.assertEqual(r({"text": "t", "options": {"A": "x", "B": "y"}}), ["options_incomplete"])
        self.assertEqual(r({"text": "t", "options": [{"key": "A", "text": "x"}]}), ["options_incomplete"])


def refine_once(replies):
    it = itertools.cycle(replies)
    llm = lambda prompt, png: C(True, json.dumps(next(it)), 0.0, "", "", 0.0)  # noqa: E731
    return refine.refine(doc_of(1), "1", llm, None, all_pages=True)


if __name__ == "__main__":
    unittest.main()


class TestParserStrict(unittest.TestCase):
    HEAD = ("# Exam Input\n\nSubject: Math\nLevel: Grade 12\nExam type: University Entrance (DGNL)\nTask: Multiple Choice\nMode: Solve\n\n"
            "## Question 1\n\nStem.\n\n")

    def validate(self, body):
        import tempfile
        from exam_engine.pipeline import parser
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "e.md")
            with open(p, "w") as fh:
                fh.write(self.HEAD + body)
            return parser.validate_exam(parser.parse_exam(p))

    def test_p1_unmarked_three_options_still_rejected(self):
        self.assertTrue(any("options must be exactly A-D" in e for e in self.validate("A. a\nB. b\nC. c\n")))

    def test_p2_marked_three_options_accepted(self):
        self.assertEqual(self.validate("[Incomplete: missing_text options_incomplete]\n\nA. a\nB. b\nC. c\n"), [])

    def test_p3_marker_in_other_question_does_not_loosen_this_one(self):
        body = ("A. a\nB. b\nC. c\n\n## Question 2\n\nS2.\n\n[Incomplete: missing_text x]\n\n"
                "A. a\nB. b\n")
        errs = self.validate(body)
        self.assertEqual([e for e in errs if "question 1" in e and "A-D" in e].__len__(), 1)
        self.assertFalse([e for e in errs if "question 2" in e])


class TestRealDocxTextBox(unittest.TestCase):
    """Real python-docx file (optional.load finds the user site even under -I); skip only if absent."""

    def test_d1_text_box_text_is_read_once_inline(self):
        import tempfile
        from lxml import etree
        from exam_engine.ingest import api as iapi, optional
        try:
            docx = optional.load("docx", "python-docx")
        except Exception:
            self.skipTest("python-docx not installed")
        if docx is None:
            self.skipTest("python-docx not installed")
        W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        xml = ('<w:r xmlns:w="%s"><w:pict xmlns:v="urn:schemas-microsoft-com:vml"><v:shape><v:textbox>'
               '<w:txbxContent><w:p><w:r><w:t>BOXEDTEXT</w:t></w:r></w:p></w:txbxContent>'
               '</v:textbox></v:shape></w:pict></w:r>' % W)
        d = docx.Document()
        p = d.add_paragraph("Question 1. Before ")
        p._p.append(etree.fromstring(xml))
        p.add_run(" after.")
        d.add_paragraph("A. a")
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "t.docx")
            d.save(path)
            doc = iapi.ingest_document(path, config={"asset_dir": os.path.join(t, "assets")})
        self.assertEqual(json.dumps(doc["pages"], ensure_ascii=False).count("BOXEDTEXT"), 1)
        self.assertEqual(doc["questions"][0]["text"], "Before BOXEDTEXT after.")
        self.assertIn("text_box_inlined", json.dumps(doc, ensure_ascii=False))

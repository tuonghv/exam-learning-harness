"""TASK-040 (phase 40): question assembled over N pages; completeness check; decline; DOCX text boxes.

Tier 0: mock replies only, synthetic placeholder text (never real exam text).
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from collections import namedtuple
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))

from exam_engine import engine as er  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.core import refcheck  # noqa: E402
from exam_engine.ingest import api, refine  # noqa: E402

C = namedtuple("C", "ok text cost_usd cls reason duration_s")
ABCD = {"A": "a", "B": "b", "C": "c", "D": "d"}


def doc_of(n_pages):
    return {"source": {"name": "x.pdf"}, "warnings": [], "meta": {},
            "pages": [{"n": i, "blocks": []} for i in range(1, n_pages + 1)]}


def run_refine(replies, spec, n_pages=3):
    it = iter(replies)
    llm = lambda prompt, png: C(True, json.dumps(next(it)), 0.0, "", "", 0.0)  # noqa: E731
    return refine.refine(doc_of(n_pages), spec, llm, None, all_pages=True)


def q(i, text, opts=None, **kw):
    d = {"id": str(i), "text": text, "options": opts or {}, "figures": []}
    d.update(kw)
    return d


def rep(questions=(), **kw):
    return dict({"questions": list(questions)}, **kw)


class TestAssembly(unittest.TestCase):
    def test_1_stem_split_over_two_pages(self):
        out = run_refine([rep([q(6, "Stem start", cut=True)]),
                          rep(continues={"text": "rest of stem", "options": ABCD})], "1-2")
        qs = out["refined"]["questions"]
        self.assertEqual(len(qs), 1)
        self.assertEqual((qs[0]["text"], qs[0]["options"]), ("Stem start\nrest of stem", ABCD))
        self.assertEqual(qs[0]["continued_pages"], [2])

    def test_2_figure_at_top_of_next_page(self):
        out = run_refine([rep([q(6, "Look at the figure below.", cut=True)]),
                          rep(continues={"figures": ["bar chart"]})], "1-2")
        self.assertEqual(out["refined"]["questions"][0]["figures"], ["bar chart"])
        out["meta"] = {"Subject": "S", "Level": "L", "Exam type": "E", "Task": "T", "Mode": "M"}
        self.assertIn("[Figure/table: bar chart]", api.to_exam_text(out, {"use_refined": True}))

    def test_3_passage_over_three_pages(self):
        out = run_refine([rep(carry="P1"),
                          rep(continues={"text": "P2", "passage": True}),
                          rep([q(1, "t1", ABCD)], continues={"text": "P3", "passage": True})], "1-3")
        qs = out["refined"]["questions"]
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0]["context"], "P1\nP2\nP3")

    def test_4_options_on_third_page(self):
        out = run_refine([rep([q(6, "Stem", cut=True)]),
                          rep(continues={"figures": ["graph"]}),
                          rep(continues={"options": ABCD})], "1-3")
        qs = out["refined"]["questions"]
        self.assertEqual(len(qs), 1)
        self.assertEqual((qs[0]["options"], qs[0]["figures"], qs[0]["continued_pages"]),
                         (ABCD, ["graph"], [2, 3]))
        self.assertEqual(out["refined"].get("orphans", []), [])

    def test_5_no_new_fields_is_unchanged(self):
        out = run_refine([rep([q(1, "t1", ABCD)], carry=""), rep([q(2, "t2", ABCD)])], "1-2")
        for x in out["refined"]["questions"]:
            self.assertEqual(sorted(x), ["context", "figures", "id", "needs_review", "options",
                                         "origin", "page", "part", "similarity", "text"])
        self.assertNotIn("orphans", out["refined"])
        self.assertEqual([w["code"] for w in out["warnings"]], ["refined_by_ai"])

    def test_6_wrong_owner_is_orphan(self):
        out = run_refine([rep([q(1, "stem one")]),
                          rep(continues={"text": "tail text", "options": ABCD})], "1,3")
        qs = out["refined"]["questions"]
        self.assertEqual((qs[0]["text"], qs[0]["options"]), ("stem one", {}))
        self.assertEqual(out["refined"]["orphans"][0]["page"], 3)
        w = [x for x in out["warnings"] if x["code"] == "orphan_continuation"]
        self.assertTrue(w and "2" in w[0]["message"])

    def test_7_old_refined_renders_same_marker_only_when_incomplete(self):
        d = doc_of(1)
        d["meta"] = {"Subject": "S", "Level": "L", "Exam type": "E", "Task": "T", "Mode": "M"}
        d["refined"] = {"questions": [q(1, "t1", ABCD, context="", part=None),
                                      q(2, "t2", {"A": "a", "B": "b"})]}
        text = api.to_exam_text(d, {"use_refined": True})
        self.assertIn("## Question 1\n\nt1\n\nA. a\nB. b\nC. c\nD. d\n", text)
        self.assertEqual(text.count("[Incomplete:"), 1)
        self.assertIn("t2\n\n[Incomplete: missing_text options_incomplete]\n\nA. a", text)

    def test_8_duplicate_prefix_dropped(self):
        tail = "the quick brown fox jumps over"
        out = run_refine([rep([q(1, "Begin " + tail, cut=True)]),
                          rep(continues={"text": tail + " the lazy dog", "options": ABCD})], "1-2")
        self.assertEqual(out["refined"]["questions"][0]["text"],
                         "Begin %s\nthe lazy dog" % tail)

    def test_8b_contained_continuation_skipped(self):
        tail = "the quick brown fox jumps over"
        out = run_refine([rep([q(1, "Begin " + tail, cut=True)]),
                          rep(continues={"text": tail, "options": ABCD})], "1-2")
        self.assertEqual(out["refined"]["questions"][0]["text"], "Begin " + tail)
        self.assertEqual(out["refined"]["questions"][0]["options"], ABCD)

    def test_9_number_guard(self):
        out = run_refine([rep([q(1, "stem", cut=True)]),
                          rep(continues={"text": "12. Another question"})], "1-2")
        self.assertEqual(out["refined"]["questions"][0]["text"], "stem")
        self.assertEqual(out["refined"]["orphans"][0]["page"], 2)

    def test_9b_owner_with_options_rejects_options(self):
        out = run_refine([rep([q(1, "stem", ABCD)]), rep(continues={"options": ABCD})], "1-2")
        self.assertEqual(out["refined"]["orphans"][0]["page"], 2)
        self.assertTrue(out["refined"]["questions"][0]["needs_review"])

    def test_14_legacy_empty_id_joins(self):
        out = run_refine([rep([q(6, "stem")]),
                          rep([q("", "", ABCD, unreadable=True)])], "1-2")
        x = out["refined"]["questions"][0]
        self.assertEqual((x["text"], x["options"], x["needs_review"], x["joined_page"]),
                         ("stem", ABCD, True, 2))

    def test_14b_legacy_goes_to_page_before_not_earlier_question(self):
        # D1: owner is the last question of page n-1; it has options, so the entry is an orphan
        out = run_refine([rep([q(1, "no options here")]), rep([q(2, "full", ABCD)]),
                          rep([q("", "", ABCD, unreadable=True)])], "1-3")
        qs = out["refined"]["questions"]
        self.assertEqual(qs[0]["options"], {})
        self.assertEqual(out["refined"]["orphans"][0]["page"], 3)

    def test_14c_legacy_text_without_options_not_dropped(self):
        # D2
        out = run_refine([rep([q(6, "stem", cut=True)]), rep([q("", "more stem")])], "1-2")
        self.assertEqual(out["refined"]["questions"][0]["text"], "stem\nmore stem")


class TestCompleteness(unittest.TestCase):
    def test_11_reasons(self):
        f = refcheck.incomplete_reasons
        self.assertEqual(f({"text": "t", "options": {"A": "a", "B": "b"}}), ["options_incomplete"])
        self.assertEqual(f({"text": "t", "options": ABCD, "cut": True}), ["cut_unresolved"])
        self.assertEqual(f({"text": "t", "options": ABCD, "cut": True, "continued_pages": [2]}), [])
        self.assertEqual(f({"text": "See the figure below.", "options": ABCD}),
                         ["referenced_part_missing figure/table"])
        self.assertEqual(f({"text": "See the figure below.", "options": ABCD}, shared_figure=True), [])
        self.assertEqual(f({"text": "t", "options": [{"key": "A", "text": "a"}] }), ["options_incomplete"])
        self.assertEqual(f({"text": "t", "options": ABCD}), [])
        self.assertEqual(f({"text": "t", "options": {}}), [])
        self.assertEqual(f({"text": "t", "options": ABCD, "orphan_page": 5}), ["orphan_on_page 5"])

    def test_marker_roundtrip(self):
        m = refcheck.marker(["a b", "c"])
        self.assertEqual(m, "[Incomplete: missing_text a b, c]")
        self.assertEqual(refcheck.marker_reasons("x\n" + m + "\ny"), "a b, c")
        self.assertIsNone(refcheck.marker_reasons("plain"))


HEAD = ("# Exam Input\n\nSubject: Mathematics\nLevel: Grade 12\nExam type: Test\n"
        "Task: Short Answer\nMode: Solve\n\n## Instructions\n\nSolve.\n\n")
MARK = "[Incomplete: missing_text options_incomplete]"


def solve_reply(i):
    return json.dumps({"schema_version": "1.0", "input_issues": [], "questions": [{
        "id": str(i), "type": "x", "answer": "4", "answer_status": "answered", "solution": ["s"],
        "explanation": "e", "checks": [], "expr": None, "evidence": [],
        "uncertainty": {"level": "low", "reason": "r"},
        "reasoning_status": "not_independently_verified", "issues": []}]})


def qa_reply(i):
    return json.dumps({"reviews": [{"id": str(i), "verdict": "agree", "findings": []}]})


class TestDecline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mp_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        p = mock.patch("subprocess.Popen", side_effect=AssertionError("real subprocess"))
        p.start()
        self.addCleanup(p.stop)

    def go(self, text, replies):
        path = os.path.join(self.tmp, "e.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        prompts, it = [], iter(replies)

        def llm(prompt):
            prompts.append(prompt)
            return claude.Call(True, next(it), 0.0, "", "", 0.0)
        cfg = {"max_attempts": 1, "max_cost_usd": 1.0, "timeout": 5, "model": "sonnet",
               "key": None, "llm_name": "mock"}
        with contextlib.redirect_stderr(io.StringIO()):
            res, _ = er.run(path, os.path.join(self.tmp, "out"), cfg, llm)
        return res, prompts

    def test_12_marked_id_never_sent_and_declined(self):
        text = (HEAD + "## Question 1\n\nMARKEDSTEM one.\n\n" + MARK + "\n\nA. a\nB. b\n\n"
                "## Question 2\n\nPlain two.\n")
        res, prompts = self.go(text, [solve_reply(2), qa_reply(2)])
        self.assertEqual(len(prompts), 2)
        self.assertTrue(all("MARKEDSTEM" not in p for p in prompts))
        by = dict((x["id"], x) for x in res["questions"])
        self.assertEqual((by["1"]["verification_status"], by["1"]["status_reason"]),
                         ("UNCERTAIN", "solver_declined: missing_text (options_incomplete)"))
        self.assertEqual(by["2"]["answer"], "4")
        self.assertNotIn("missing_text", by["2"]["status_reason"])

    def test_12b_all_marked_makes_no_call(self):
        text = HEAD + "## Question 1\n\nOnly.\n\n" + MARK + "\n"
        res, prompts = self.go(text, [])
        self.assertEqual(prompts, [])
        self.assertEqual(res["questions"][0]["verification_status"], "UNCERTAIN")


def _p(xml):
    from lxml import etree
    ns = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
          'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
          'xmlns:v="urn:schemas-microsoft-com:vml"')
    return etree.fromstring('<w:p %s>%s</w:p>' % (ns, xml))


class TestDocxTextBox(unittest.TestCase):
    BOX = ('<w:r><w:t>stem</w:t></w:r><mc:AlternateContent><mc:Choice><w:r><w:drawing>'
           '<w:txbxContent><w:p><w:r><w:t>BOXED</w:t></w:r></w:p></w:txbxContent></w:drawing></w:r>'
           '</mc:Choice><mc:Fallback><w:r><w:pict><v:textbox><w:txbxContent><w:p><w:r><w:t>BOXED'
           '</w:t></w:r></w:p></w:txbxContent></v:textbox></w:pict></w:r></mc:Fallback>'
           '</mc:AlternateContent><w:r><w:t>after</w:t></w:r>')

    def setUp(self):
        try:
            import lxml  # noqa: F401
        except ImportError:
            self.skipTest("lxml not installed")

    def test_13_text_box_inline_once_own_line(self):
        from exam_engine.ingest.adapters import docx
        state = {"unsupported": set(), "math": False}
        text = docx._text(_p(self.BOX), state)
        self.assertEqual(text.count("BOXED"), 1)
        self.assertEqual(text.split("\n"), ["stem", "BOXED", "after"])
        self.assertNotIn("text box", state["unsupported"])
        self.assertTrue(state.get("text_box"))

    def test_13b_question_over_page_breaks_is_one_question(self):
        from exam_engine.ingest import segment
        from exam_engine.ingest.adapters import docx
        state = {"unsupported": set(), "math": False}
        lines = []
        for xml in ('<w:r><w:t>Câu 1. Stem</w:t></w:r><w:r><w:br w:type="page"/></w:r>'
                    '<w:r><w:t>more stem</w:t></w:r>', self.BOX.replace("stem", "tail"),
                    '<w:r><w:t>A. a</w:t></w:r>'):
            lines += docx._text(_p(xml), state).split("\n")
        _, qs, ok = segment.segment(lines)
        self.assertEqual(len(qs), 1)
        self.assertIn("BOXED", qs[0]["text"])
        self.assertIn("more stem", qs[0]["text"])


if __name__ == "__main__":
    unittest.main()

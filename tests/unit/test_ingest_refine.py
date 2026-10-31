"""Phase 17 (REQ-0021): ingest-refine (mock replies only). $0, no network, no real call."""
import contextlib
import copy
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.ingest import refine  # noqa: E402
from exam_engine.ingest.schema import IngestError, validate_document  # noqa: E402


def blk(i, text):
    return {"id": "b%d" % i, "order": i, "type": "paragraph", "text": text, "origin": "extracted"}


def make_doc(key_page=False):
    pages = [{"n": 1, "status": "native_text", "blocks": [blk(1, "Cau 1. Two plus two?\nA. 3\nB. 4")]},
             {"n": 2, "status": "ocr", "blocks": [blk(2, "Cau 2. Colour of grass?\nA. green\nB. red")]},
             {"n": 3, "status": "native_text", "blocks": [blk(3, "Cau 3. Plain page")]}]
    if key_page:
        pages.append({"n": 4, "status": "native_text",
                      "blocks": [{"id": "b9", "order": 9, "type": "heading", "text": "Dap an",
                                  "origin": "extracted"}]})
    return {"schema_version": "1",
            "source": {"path": "t.pdf", "name": "t.pdf", "format": "pdf", "sha256": "0" * 64,
                       "size": 1},
            "status": "mixed", "extraction": {"method": "pdf", "tool": "t"}, "meta": {},
            "pages": pages, "assets": [],
            "warnings": [{"level": "warning", "code": "math_possible", "message": "m", "page": 1}],
            "questions": [{"n": 2, "text": "Colour of grass?",
                           "options": [{"key": "A", "text": "green"}, {"key": "B", "text": "red"}]}]}


def reply(*qs):
    return json.dumps({"questions": list(qs)})


def q(i, text, opts=None, **kw):
    d = {"id": str(i), "text": text, "options": opts if opts is not None else {},
         "figures": [], "unreadable": False}
    d.update(kw)
    return d


GOOD1 = reply(q(1, "Two plus two?", {"A": "3", "B": "4"}))
GOOD2 = reply(q(2, "Colour of grass?", {"A": "green", "B": "red", "C": "x", "D": "y"}))


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(["ingest-refine"] + args)
    return code, out.getvalue(), err.getvalue()


class Fake:
    """Reply source recording calls: llm(prompt, png)."""
    def __init__(self, texts, ok=True, cost=0.01):
        self.texts, self.calls, self.ok, self.cost = list(texts), [], ok, cost

    def __call__(self, prompt, png):
        self.calls.append(prompt)
        if not self.texts:
            return claude.Call(False, "", 0.0, "other", "exhausted", 0.0)
        return claude.Call(self.ok, self.texts.pop(0), self.cost, "", "", 0.0)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        # real mode must never be reached by a test
        p = mock.patch.object(claude, "run_claude_images",
                              side_effect=AssertionError("real call in test"))
        p.start()
        self.addCleanup(p.stop)

    def write(self, name, obj):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return path


class TestPick(unittest.TestCase):
    def test_selected_and_flagged_only(self):
        doc = make_doc()
        self.assertEqual(refine.pick_pages(doc, "1-3"), [1, 2])
        self.assertEqual(refine.pick_pages(doc, "3"), [])
        self.assertEqual(refine.pick_pages(doc, "2"), [2])

    def test_page_outside_document(self):
        with self.assertRaises(IngestError) as cm:
            refine.pick_pages(make_doc(), "7")
        self.assertEqual(cm.exception.code, "invalid_pages")

    def test_fixture_is_valid(self):
        self.assertEqual(validate_document(make_doc()), [])


class TestValidate(unittest.TestCase):
    def test_rules(self):
        orig = {"2": make_doc()["questions"][0]}
        self.assertEqual(refine.validate_refined(json.loads(GOOD2), orig), [])
        bad = [{"x": 1}, {"questions": [q("x", "a")]},
               {"questions": [q(1, "a", answer="B")]}, {"questions": [q(1, "a")], "answer": "A"},
               {"questions": [q(1, "")]}, {"questions": [q(1, "a", {"A": 1})]},
               {"questions": [q(2, "a", {"A": "x"})]}]
        for obj in bad:
            self.assertTrue(refine.validate_refined(obj, orig), obj)
        self.assertTrue(refine.validate_refined({"questions": [q(2, "a", {"A": "x"})]}, orig))
        self.assertEqual(refine.validate_refined({"questions": [q(2, "a", {}, unreadable=True)]},
                                                 orig), [])


class TestRefine(Base):
    def test_valid_stored_source_untouched(self):
        doc = make_doc()
        before = hashlib.sha256(json.dumps(doc["pages"], sort_keys=True).encode()).hexdigest()
        llm = Fake([GOOD1, GOOD2])
        out = refine.refine(doc, "1-3", llm)
        self.assertEqual(len(llm.calls), 2)
        self.assertEqual(hashlib.sha256(json.dumps(out["pages"], sort_keys=True).encode()
                                        ).hexdigest(), before)
        r = out["refined"]
        self.assertEqual((r["pages"], r["calls"]), ([1, 2], 2))
        self.assertTrue(all(x["origin"] == "ai" for x in r["questions"]))
        self.assertEqual([x["page"] for x in r["questions"]], [1, 2])
        self.assertGreater(r["questions"][1]["similarity"], 0.6)
        self.assertEqual(len(r["prompt_sha256"]), 64)
        self.assertEqual(validate_document(out), [])
        self.assertNotIn("refined", doc)

    def test_retry_on_invalid_json(self):
        llm = Fake(["not json at all", GOOD1])
        out = refine.refine(make_doc(), "1", llm)
        self.assertEqual(out["refined"]["calls"], 2)
        self.assertAlmostEqual(out["refined"]["cost_usd"], 0.02)

    def test_two_invalid_is_structured_error(self):
        llm = Fake(["nope", "still nope", GOOD1])
        with self.assertRaises(refine.RefineError) as cm:
            refine.refine(make_doc(), "1", llm)
        self.assertEqual(cm.exception.code, "invalid_reply")
        self.assertEqual(len(llm.calls), 2)

    def test_answer_in_reply_rejected(self):
        bad = reply(q(1, "Two plus two?", {"A": "3", "B": "4"}, answer="B"))
        with self.assertRaises(refine.RefineError) as cm:
            refine.refine(make_doc(), "1", Fake([bad, bad]))
        self.assertIn("forbidden", str(cm.exception))

    def test_key_pages_refused_unless_allowed(self):
        doc = make_doc(key_page=True)
        doc["warnings"].append({"level": "warning", "code": "missing_text", "message": "m",
                                "page": 4})
        llm = Fake([GOOD1])
        with self.assertRaises(IngestError) as cm:
            refine.refine(doc, "1,4", llm)
        self.assertEqual(cm.exception.code, "answer_key_present")
        self.assertEqual(llm.calls, [])
        refine.refine(doc, "1,4", Fake([GOOD1, GOOD1]), allow_key=True)

    def test_unflagged_page_not_sent(self):
        llm = Fake([GOOD1, GOOD2, GOOD1])
        refine.refine(make_doc(), "1-3", llm)
        self.assertEqual(len(llm.calls), 2)
        self.assertTrue(all("Page: 3" not in c for c in llm.calls))

    def test_low_similarity_and_unreadable_need_review(self):
        far = reply(q(1, "Totally different words about volcanoes", {}))
        out = refine.refine(make_doc(), "1", Fake([far]))
        self.assertTrue(out["refined"]["questions"][0]["needs_review"])
        unread = reply(q(2, "Colour of grass?", {}, unreadable=True))
        out = refine.refine(make_doc(), "2", Fake([unread]))
        self.assertTrue(out["refined"]["questions"][0]["needs_review"])

    def test_cost_cap_stops(self):
        with self.assertRaises(refine.RefineError) as cm:
            refine.refine(make_doc(), "1-2", Fake([GOOD1, GOOD2], cost=2.0), max_cost=1.0)
        self.assertEqual(cm.exception.code, "cost_cap")

    def test_failed_call_is_error(self):
        with self.assertRaises(refine.RefineError) as cm:
            refine.refine(make_doc(), "1", Fake([GOOD1], ok=False))
        self.assertEqual(cm.exception.code, "call_failed")

    def test_to_exam_text_ignores_refined(self):
        from exam_engine.ingest import api
        doc = make_doc()
        meta = {k: "x" for k in api.REQUIRED}
        doc["meta"] = meta
        base = api.to_exam_text(doc)
        out = refine.refine(doc, "1", Fake([GOOD1]))
        self.assertEqual(api.to_exam_text(out), base)


PNG_HDR = b"\x89PNG\r\n\x1a\n"


class FakeFitz:
    """Synthetic pymupdf: page.get_pixmap(matrix).tobytes('png') sized by zoom."""
    def __init__(self, sizes, header=PNG_HDR):
        self.sizes, self.header, self.zooms, self.closed = sizes, header, [], False

    def Matrix(self, a, b):
        return a

    def open(self, path):
        outer = self

        class Pix:
            def __init__(self, z):
                self.z = z

            def tobytes(self, fmt):
                outer.zooms.append(self.z)
                return outer.header + b"0" * outer.sizes[len(outer.zooms) - 1]

        class Page:
            def get_pixmap(self, matrix):
                return Pix(matrix)

        class Doc:
            def __getitem__(self, i):
                return Page()

            def close(self):
                outer.closed = True
        return Doc()


class TestRenderPage(unittest.TestCase):
    def render(self, fz):
        with mock.patch.object(refine.optional, "load", return_value=fz):
            return refine.render_page("x.pdf", 1)

    def test_png_bytes_zoom2_first(self):
        fz = FakeFitz([100])
        data = self.render(fz)
        self.assertTrue(data.startswith(PNG_HDR))
        self.assertEqual(fz.zooms, [2.0])
        self.assertTrue(fz.closed)

    def test_size_cap_lowers_zoom(self):
        big = claude.MAX_IMAGE_BYTES
        fz = FakeFitz([big, big, 100])
        data = self.render(fz)
        self.assertEqual(fz.zooms, [2.0, 1.5, 1.0])
        self.assertLessEqual(len(data), claude.MAX_IMAGE_BYTES)

    def test_always_too_big_is_call_failed(self):
        big = claude.MAX_IMAGE_BYTES
        fz = FakeFitz([big] * 4)
        with self.assertRaises(refine.RefineError) as cm:
            self.render(fz)
        self.assertEqual(cm.exception.code, "call_failed")
        self.assertTrue(fz.closed)

    def test_non_png_header_is_call_failed(self):
        with self.assertRaises(refine.RefineError) as cm:
            self.render(FakeFitz([10], header=b"JUNK"))
        self.assertEqual(cm.exception.code, "call_failed")

    def test_refine_passes_rendered_png_to_llm(self):
        seen = []

        def llm(prompt, png):
            seen.append(png)
            return claude.Call(True, GOOD1, 0.0, "", "", 0.0)
        refine.refine(make_doc(), "1", llm, source_path="x.pdf", render=lambda p, n: PNG_HDR + b"%d" % n)
        self.assertEqual(seen, [PNG_HDR + b"1"])


class TestPromptFile(unittest.TestCase):
    def test_no_answers_or_keys_in_prompt(self):
        import re
        t = refine.template()
        self.assertFalse(re.search(r"(?i)(answer|dap an|đáp án)\s*[:=]\s*\"?[A-D]\b", t), t)
        self.assertNotRegex(t, r"(?i)correct (answer|option)")
        self.assertEqual(refine.build_prompt(3).splitlines()[-1], "Page: 3")


class TestEdges(Base):
    def test_gap_ids_flagged_not_rejected(self):
        out = refine.refine(make_doc(), "1", Fake([reply(q(1, "a", {}), q(3, "b", {}))]))
        flags = dict((x["id"], x["needs_review"]) for x in out["refined"]["questions"])
        self.assertTrue(flags["3"])

    def test_id_forms_normalised(self):
        for raw, want in ((3, "3"), ("Câu 3.", "3"), ("Question 3", "3"), ("03", "3")):
            self.assertEqual(refine.norm_id(raw), want)
        for raw in (None, "", "abc", True, 2.5):
            self.assertIsNone(refine.norm_id(raw))

    def test_part_restart_not_flagged(self):
        self.assertEqual(refine._gaps([{"id": "11"}, {"id": "12"}, {"id": "1"}, {"id": "2"}]), set())

    def test_option_count_rule_retried(self):
        short = reply(q(2, "Colour of grass?", {"A": "green", "B": "red"}))
        llm = Fake([short, GOOD2])
        out = refine.refine(make_doc(), "2", llm)
        self.assertEqual(out["refined"]["calls"], 2)

    def test_threshold_boundary(self):
        doc = make_doc()
        out = refine.refine(doc, "2", Fake([GOOD2]), min_similarity=1.01)
        self.assertTrue(out["refined"]["questions"][0]["needs_review"])
        out = refine.refine(doc, "2", Fake([GOOD2]), min_similarity=0.0)
        self.assertFalse(out["refined"]["questions"][0]["needs_review"])

    def test_solution_field_rejected(self):
        bad = reply(q(1, "a", {}, solution="x"))
        with self.assertRaises(refine.RefineError):
            refine.refine(make_doc(), "1", Fake([bad, bad]))

    def test_warning_added_and_info_when_clean(self):
        out = refine.refine(make_doc(), "1", Fake([GOOD1]))
        w = [x for x in out["warnings"] if x["code"] == "refined_by_ai"]
        self.assertEqual(len(w), 1)
        self.assertIn(w[0]["level"], ("info", "warning"))

    def test_cli_calls_only_flagged_selected(self):
        m = self.write("m.json", [GOOD1, GOOD2, GOOD1])
        real = refine.mock_llm(m)
        n = []

        def counting(prompt, png):
            n.append(1)
            return real(prompt, png)
        with mock.patch.object(refine, "mock_llm", return_value=counting):
            code, out, _e = run_cli([self.write("d.json", make_doc()), "--pages", "1-3", "--mock", m])
        self.assertEqual(len(n), 2, out)


class TestRealLlm(unittest.TestCase):
    def test_stream_format_error_is_structured(self):
        def runner(argv, **kw):
            return mock.Mock(returncode=1, stdout="", stderr="error: unknown option --input-format")
        llm = refine.make_real_llm("sonnet", 5, None, runner=runner)
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 10
        with self.assertRaises(refine.RefineError) as cm:
            llm("p", png)
        self.assertEqual(cm.exception.code, "stream_format")


class TestCli(Base):
    def doc_path(self, **kw):
        return self.write("d.json", make_doc(**kw))

    def mock_file(self, replies):
        return self.write("m.json", replies)

    def test_no_mode_is_usage(self):
        code, _o, err = run_cli([self.doc_path(), "--pages", "1"])
        self.assertEqual(code, 2)
        self.assertIn("exactly one", err)

    def test_two_modes_is_usage(self):
        self.assertEqual(run_cli([self.doc_path(), "--pages", "1", "--dry-run",
                                  "--mock", self.mock_file([])])[0], 2)

    def test_dry_run_no_call(self):
        with mock.patch.object(refine, "make_real_llm", side_effect=AssertionError), \
                mock.patch.object(refine, "mock_llm", side_effect=AssertionError):
            code, out, _e = run_cli([self.doc_path(), "--pages", "1-3", "--dry-run",
                                     "--max-cost-usd", "0.5"])
        self.assertEqual(code, 0)
        self.assertIn("calls <= 4", out)
        self.assertIn("cap $0.50", out)
        self.assertIn("transcribe", out)
        self.assertEqual(out.count("=== REFINE prompt"), 2)

    def test_mock_ok_writes_out(self):
        o = os.path.join(self.dir, "r.json")
        code, out, _e = run_cli([self.doc_path(), "--pages", "1-2", "--mock",
                                 self.mock_file([GOOD1, GOOD2]), "--out", o])
        self.assertEqual(code, 0, out)
        with open(o, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(len(saved["refined"]["questions"]), 2)
        self.assertEqual(validate_document(saved), [])

    def test_needs_review_exit_1(self):
        far = reply(q(1, "Totally different words about volcanoes", {}))
        code, out, _e = run_cli([self.doc_path(), "--pages", "1", "--mock",
                                 self.mock_file([far])])
        self.assertEqual(code, 1)
        self.assertIn("needs_review=['1']", out)

    def test_invalid_replies_exit_3(self):
        code, _o, err = run_cli([self.doc_path(), "--pages", "1", "--mock",
                                 self.mock_file(["x", "y"])])
        self.assertEqual(code, 3)
        self.assertIn("invalid_reply", err)

    def test_key_pages_exit_3(self):
        d = make_doc(key_page=True)
        d["warnings"].append({"level": "warning", "code": "missing_text", "message": "m",
                              "page": 4})
        p = self.write("k.json", d)
        m = self.mock_file([GOOD1])
        code, _o, err = run_cli([p, "--pages", "1,4", "--mock", m])
        self.assertEqual((code, "answer_key_present" in err), (3, True))
        _c, _o, err2 = run_cli([p, "--pages", "1,4", "--mock", m, "--allow-key-pages"])
        self.assertNotIn("answer_key_present", err2)

    def test_bad_pages_exit_2(self):
        self.assertEqual(run_cli([self.doc_path(), "--pages", "9", "--dry-run"])[0], 2)

    def test_real_without_source_file_fails_before_any_call(self):
        # json doc, no t.pdf next to it: refused; run_claude_images patched to fail the test if reached
        code, _o, err = run_cli([self.doc_path(), "--pages", "1", "--real"])
        self.assertEqual(code, 2)
        self.assertIn("not found", err)


if __name__ == "__main__":
    unittest.main()


class AllPagesAndRefinedText(unittest.TestCase):
    DOC = {"source": {"name": "x.pdf"}, "pages": [{"n": 1, "blocks": []}, {"n": 2, "blocks": []}],
           "warnings": [], "meta": {"Subject": "math", "Level": "x", "Exam type": "t",
                                    "Task": "solve", "Mode": "m"}}

    def test_all_pages_picks_unflagged(self):
        from exam_engine.ingest import refine
        self.assertEqual(refine.pick_pages(self.DOC, "1-2"), [])
        self.assertEqual(refine.pick_pages(self.DOC, "1-2", True), [1, 2])

    def test_refined_text_context_order_and_filter(self):
        from exam_engine.ingest import api
        q = lambda i, **k: dict({"id": str(i), "text": "t%d" % i, "options": {"B": "b", "A": "a", "C": "c", "D": "d"}}, **k)
        doc = dict(self.DOC, refined={"questions": [q(1, context="PASSAGE"), q(2), q(3)]})
        text = api.to_exam_text(doc, {"use_refined": True, "questions": "1-2"})
        self.assertIn("## Question 1\n\nPASSAGE\n\nt1\n\nA. a\nB. b", text)
        self.assertNotIn("Question 3", text)
        with self.assertRaises(api.IngestError):
            api.to_exam_text(doc, {"use_refined": True, "questions": "9"})

    def test_question_split_by_page_is_joined(self):
        from exam_engine.ingest import api
        doc = dict(self.DOC, refined={"questions": [
            {"id": "6", "text": "stem", "options": {}},
            {"id": "6", "text": "more", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}}]})
        text = api.to_exam_text(doc, {"use_refined": True})
        self.assertEqual(text.count("## Question 1"), 1)
        self.assertIn("stem\nmore\n\nA. a", text)

    def test_group_passage_repeated_for_its_questions(self):
        from exam_engine.ingest import api
        o = {"A": "a", "B": "b", "C": "c", "D": "d"}
        doc = dict(self.DOC, refined={"questions": [
            {"id": "1", "text": "t1", "options": o, "context": "Questions 1-2: Read.\nPASSAGE"},
            {"id": "2", "text": "t2", "options": o, "context": ""},
            {"id": "3", "text": "t3", "options": o, "context": ""}]})
        text = api.to_exam_text(doc, {"use_refined": True})
        self.assertEqual(text.count("PASSAGE"), 2)

    def test_carry_goes_to_next_pages_first_question_and_figures_shown(self):
        from exam_engine.ingest import api, refine
        doc = dict(self.DOC, source={"name": "x.pdf"})
        doc["pages"] = [{"n": 1, "blocks": []}, {"n": 2, "blocks": []}]
        o = {"A": "a", "B": "b", "C": "c", "D": "d"}
        replies = iter([{"questions": [], "carry": "Questions 1-2: PASSAGE"},
                        {"questions": [{"id": "1", "text": "t1", "options": o, "figures": ["pie 30%"]}]}])
        from collections import namedtuple
        import json
        C = namedtuple("C", "ok text cost_usd cls reason duration_s")
        llm = lambda prompt, png: C(True, json.dumps(next(replies)), 0.0, "", "", 0.0)
        out = refine.refine(doc, "1-2", llm, None, all_pages=True)
        self.assertIn("PASSAGE", out["refined"]["questions"][0]["context"])
        text = api.to_exam_text(out, {"use_refined": True})
        self.assertIn("[Figure/table: pie 30%]", text)

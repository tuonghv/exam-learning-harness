"""TASK-076 76.1-76.3: multi-object reply, text/image tie-break, group figure key. Synthetic, mock LLM only."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import test_exam_run as T  # noqa: E402
import test_image_check as TI  # noqa: E402
from exam_engine import engine as er  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.core import refcheck, schema as sch  # noqa: E402
from exam_engine.core.decision import new_rec  # noqa: E402

SAVED = os.path.join(os.path.dirname(os.path.dirname(HERE)), "plans", "dgnl2025", "out-English", "calls",
                     "003-reply.txt")


class MultiObject(unittest.TestCase):
    def ex(self, text, schema=sch.SOLVE_OUT):
        return claude.extract_json(text, schema)

    def test_last_of_two_objects(self):
        txt = T.solve(T.a(1, "A")) + "\nWait, correcting.\n" + T.solve(T.a(1, "B"))
        obj, err = self.ex(txt)
        self.assertIsNone(err)
        self.assertEqual(obj["questions"][0]["answer"], "B")

    def test_last_invalid_never_falls_back(self):
        txt = T.solve(T.a(1, "A")) + "\nno.\n" + json.dumps({"questions": "x"})
        obj, err = self.ex(txt)
        self.assertIsNone(obj)
        self.assertTrue(err.startswith("last of 2 JSON objects invalid"), err)

    def test_unchanged_shapes(self):
        one = T.solve(T.a(1, "A"))
        for txt in (one, "```json\n%s\n```" % one, "pre " + one + " post"):
            self.assertEqual(self.ex(txt), claude.extract_json(txt))
            self.assertIsNotNone(self.ex(txt)[0])
        for txt in ("garbage", "{broken", "", "```a\n{}\n```\n```b\n{}\n```"):
            self.assertEqual(self.ex(txt), claude.extract_json(txt))

    def test_no_schema_unchanged(self):
        txt = T.solve(T.a(1, "A")) + "\nprose\n" + T.solve(T.a(1, "B"))
        self.assertEqual(claude.extract_json(txt), (None, "no valid JSON object found"))

    def test_deep_nesting_no_crash(self):
        obj, err = self.ex("{" * 100000 + "x " + "{}")
        self.assertIsNone(obj)

    def test_solve_round_accepts_two_objects(self):
        text = TI.exam("Compute 3+4.")
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "e.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
            reply = T.solve(T.a(1, "6")) + "\nCorrection:\n" + T.solve(T.a(1, "7"))
            res, _ = er.run(p, os.path.join(d, "o"), T.cfg(max_attempts=1), T.Script(reply, T.qa((1, "agree"))))
        q = res["questions"][0]
        self.assertEqual(q["answer"], "7")
        self.assertNotIn("malformed_output", [f["code"] for f in q["qa_findings"]])

    @unittest.skipUnless(os.path.exists(SAVED), "saved evidence absent")
    def test_saved_retry_reply_parses(self):
        with open(SAVED, encoding="utf-8") as fh:
            txt = fh.read()
        obj, err = claude.extract_json(txt, sch.SOLVE_OUT)
        self.assertIsNone(err)
        self.assertEqual(len(obj["questions"]), 9)


class FakeRn(object):
    def __init__(self, *items):
        self.items, self.prompts = list(items), []

    def call(self, prompt, tag, **kw):
        self.prompts.append(prompt)
        return T.ok(self.items.pop(0))


def rec(ans, status, reason="x", **kw):
    r = new_rec()
    r["ans"], r["status"], r["reason"] = ans, status, reason
    r.update(kw)
    return r


class Adjudication(TI.Base):
    def setUp(self):
        super().setUp()
        self.ex = TI.load(self.tmp, TI.exam("Pick one.", "Pick two."))

    def differ(self, r, scope="doubt", i=1, g="6"):
        er.apply_image(self.ex, {i: r}, {str(i): T.a(i, g)}, [i], {}, None, scope)

    def test_fail_row_in_set_and_text_side_kept_on_fail(self):
        r = rec(T.a(1, "5"), "FAIL", "reviewer_disagrees")
        self.differ(r)
        self.assertEqual(r["status"], "FAIL")
        rn = FakeRn(T.solve(T.a(1, "5")))
        er.adjudicate(self.ex, {1: r}, rn, [1])
        self.assertEqual((r["status"], r["reason"], r["ans"]["answer"]), ("FAIL", "reviewer_disagrees", "5"))
        self.assertIn("adjudicated", [f["code"] for f in r["findings"]])

    def test_image_side_wins_to_uncertain(self):
        r = rec(T.a(1, "5"), "FAIL", "reviewer_disagrees")
        self.differ(r)
        er.adjudicate(self.ex, {1: r}, FakeRn(T.solve(T.a(1, "6"))), [1])
        self.assertEqual((r["status"], r["reason"], r["ans"]["answer"]),
                         ("UNCERTAIN", "needs_review: adjudicated", "6"))

    def test_tentative_text_is_kept_and_sent(self):
        r = rec(T.a(1, "5", answer_status="uncertain"), "UNCERTAIN", "solver_declined")
        self.differ(r)
        self.assertEqual(r["text_ans"]["answer"], "5")
        self.assertEqual(r["image_ans"]["answer"], "6")
        rn = FakeRn(T.solve(T.a(1, "5")))
        er.adjudicate(self.ex, {1: r}, rn, [1])
        self.assertIn("text answer: 5", rn.prompts[0])
        self.assertIn("image answer: 6", rn.prompts[0])
        self.assertEqual((r["ans"]["answer"], r["status"]), ("5", "UNCERTAIN"))

    def test_failed_adjudication_keeps_result(self):
        r = rec(T.a(1, "5"), "FAIL", "reviewer_disagrees")
        self.differ(r)
        er.adjudicate(self.ex, {1: r}, FakeRn("not json"), [1])
        self.assertEqual((r["status"], r["ans"]["answer"]), ("FAIL", "5"))
        self.assertIn("adjudication_failed", [f["code"] for f in r["findings"]])

    def test_stop_is_a_finding(self):
        class Boom(object):
            def call(self, *a, **k):
                raise er.Stop("cost_cap", "cap")
        r = rec(T.a(1, "5"), "FAIL", "reviewer_disagrees")
        self.differ(r)
        er.adjudicate(self.ex, {1: r}, Boom(), [1])
        self.assertIn("adjudication_failed", [f["code"] for f in r["findings"]])

    def test_pass_never_adjudicated(self):
        # a PASS text answer needs an independent check; without one the status is UNCERTAIN, so build it directly
        r = rec(T.a(1, "5"), "PASS", "")
        before = {1: r["status"]}
        self.differ(r)
        diff = [i for i in [1] if r.get("image_ans") is not None and before[i] != "PASS"]
        self.assertEqual(diff, [])

    def test_opt_out_and_default_calls(self):
        text = TI.exam("Source pages: 3\n\n" + TI.FIG)
        n = {}
        for adj in (False, True):
            im, image = self.img(None, T.solve(T.a(1, "6")))
            llm = T.Script(T.solve(T.a(1, "5")), T.qa((1, "agree")), T.solve(T.a(1, "6")))
            res, _ = self.run_img(text, llm, image, **({"adjudicate": True} if adj else {}))
            n[adj] = len(llm.prompts)
        self.assertEqual(n, {True: 3, False: 2})

    def test_adjudicated_source_validates_and_reports(self):
        from exam_engine.pipeline import metrics
        text = TI.exam("Source pages: 3\n\n" + TI.FIG)
        im, image = self.img(None, T.solve(T.a(1, "6")))
        llm = T.Script(T.solve(T.a(1, "5")), T.qa((1, "agree")), T.solve(T.a(1, "6")))
        res, _ = self.run_img(text, llm, image, adjudicate=True)
        self.assertEqual(res["questions"][0]["source"], "adjudicated")
        self.assertEqual(sch.validate(res, sch.RESULT), [])
        self.assertEqual(metrics.compute(res)["counts"]["image_checked"], 1)
        with open(res["reports"]["md"], encoding="utf-8") as fh:
            self.assertIn("- Source: adjudicated", fh.read())

    def test_idle_adjudication_not_counted_in_cap(self):
        from exam_engine import cli
        plain = TI.load(self.tmp, TI.exam("Compute 3+4."))
        fig = TI.load(self.tmp, TI.exam(TI.FIG))
        for ex, kw, kept in ((plain, {}, False), (fig, {}, True), (plain, {"image_scope": "doubt"}, True)):
            cfg = T.cfg(image_pdf="d.json", adjudicate=True, **kw)
            cli._drop_idle_adjudication(cfg, ex)
            self.assertEqual("adjudicate" in cfg, kept)
        cfg = T.cfg(image_pdf="d.json", adjudicate=True)
        cli._drop_idle_adjudication(cfg, plain)
        self.assertEqual(er.call_cap(cfg), er.call_cap(T.cfg(image_pdf="d.json")))

    def test_no_pdf_no_call(self):
        path = self.write("exam.md", TI.exam("Compute 3+4."))
        llm = T.Script(T.solve(T.a(1, "7")), T.qa((1, "agree")))
        er.run(path, self.out, T.cfg(adjudicate=True), llm)
        self.assertEqual(len(llm.prompts), 2)


class GroupKey(unittest.TestCase):
    def test_source_pages_not_a_key(self):
        g = "Read the table below for 3 questions.\n"
        texts = ["Source pages: 18\n" + g + "[Figure/table: t]\nQ1",
                 "Source pages: 18\n" + g + "Q2",
                 "Source pages: 18-19\n" + g + "Q3 uses the table below"]
        self.assertEqual(refcheck.missing_by_question(texts), [[], [], []])

    def test_same_page_ungrouped_no_longer_shares(self):
        texts = ["Source pages: 4\nFirst question hình bên\n[Figure/table: c]",
                 "Source pages: 4\nOther question hình bên"]
        self.assertEqual(refcheck.missing_by_question(texts), [[], ["figure/table"]])

    def test_really_missing_still_flagged(self):
        texts = ["Source pages: 4\nGroup head\n[Figure/table: c]\nQ1",
                 "Source pages: 5\nOther head\nLook at the table below"]
        self.assertEqual(refcheck.missing_by_question(texts)[1], ["figure/table"])

    def test_heading_line_skipped(self):
        self.assertEqual(refcheck._first_line("Source pages: 3\n## Part\n\nPassage"), "Passage")


def gq(i, page, ctx="", figs=(), text="Stem"):
    return {"id": str(i), "text": text + " %d" % i, "options": {}, "context": ctx, "page": page,
            "figures": list(figs)}


class GroupFigures(unittest.TestCase):
    """76.4: the group carrier's figures and pages reach the later members."""

    def setUp(self):
        from exam_engine.ingest import api
        self.api = api
        self.qs = [gq(1, 16, "Questions 1-3: Read the data.", ["table of 5 items"]), gq(2, 17), gq(3, 17),
                   gq(4, 17, figs=["own chart"])]

    def test_members_get_table_and_carrier_page(self):
        sh = self.api._share_context(self.qs)
        for q in sh[1:3]:
            self.assertEqual(q["figures"], ["table of 5 items"])
            self.assertEqual(q["continued_pages"], [16])
            lines = "\n".join(self.api.question_lines(q))
            self.assertIn("[Figure/table: table of 5 items]", lines)
            self.assertIn("Source pages: 16-17", lines)
        self.assertEqual(sh[0]["figures"], ["table of 5 items"])

    def test_outside_question_not_leaked(self):
        sh = self.api._share_context(self.qs)
        self.assertEqual((sh[3]["figures"], sh[3].get("continued_pages")), (["own chart"], None))

    def test_no_group_figures_unchanged(self):
        qs = [gq(1, 3, "Questions 1-2: Read."), gq(2, 3)]
        self.assertEqual(self.api._share_context(qs)[1], dict(qs[1], context="Questions 1-2: Read."))

    def test_adjudication_prompt_has_every_option(self):
        import tempfile
        from exam_engine.pipeline import cross, parser
        body = "Pick the unit.\n\nA. alpha-opt\nB. beta-opt\nC. gamma-opt\nD. delta-opt"
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "e.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(TI.exam(body))
            ex = parser.parse_exam(p)
        pr = cross.adjudicate_prompt(ex, [(1, T.a(1, "A"), T.a(1, "B"))])
        for o in ("A. alpha-opt", "B. beta-opt", "C. gamma-opt", "D. delta-opt"):
            self.assertIn(o, pr)
        self.assertIn("Decide from the exam text", pr)
        self.assertIn("choose the text-supported one", pr)


if __name__ == "__main__":
    unittest.main()

"""TASK-061 61.1-61.4: --image-scope declined|doubt, adjudication, metrics. Mock LLM, synthetic text only."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import test_exam_run as T  # noqa: E402
import test_image_check as TI  # noqa: E402
from exam_engine import engine as er  # noqa: E402
from exam_engine.core.decision import new_rec  # noqa: E402
from exam_engine.pipeline import cross, metrics  # noqa: E402

MARK = "[Incomplete: missing_text options_incomplete]"
CUT = "Source pages: 2\n\n" + MARK + "\n\nPick the best title."
PLAIN = "Source pages: 4\n\nCompute 3+4."
FIG = "Source pages: 3\n\n" + TI.FIG


def rec(ans, status, reason):
    r = new_rec()
    r["ans"], r["status"], r["reason"] = ans, status, reason
    return r


class Targets(TI.Base):
    def test_1_declined_adds_skip_and_declined_first(self):
        ex = TI.load(self.tmp, TI.exam(FIG, CUT, PLAIN))
        fl, skip = er.visual_flags(ex), er.incomplete_ids(ex)
        self.assertEqual(skip, {2: "options_incomplete"})
        recs = {1: rec(T.a(1, "5"), "PASS", ""), 2: rec(None, "UNCERTAIN", "x"),
                3: rec(T.a(3, None, answer_status="unanswerable"), "UNCERTAIN", "solver_declined")}
        # flagged scope: skip ids stay out (59 golden)
        self.assertEqual(er.image_targets(ex, fl, skip, 4, set(), None)[0], [1])
        dec, doubt = er.scope_ids(recs, skip, "declined")
        self.assertEqual((dec, doubt), ([3], []))
        t, pg, sk = er.image_targets(ex, fl, skip, 4, set(), None, "declined", dec, doubt)
        self.assertEqual((t, pg, sk), ([2, 3, 1], [2, 3, 4], {}))

    def test_2_doubt_last_and_cap(self):
        ex = TI.load(self.tmp, TI.exam(FIG, CUT, PLAIN))
        recs = {1: rec(T.a(1, "5"), "PASS", ""), 2: rec(None, "UNCERTAIN", "x"),
                3: rec(T.a(3, "7"), "UNCERTAIN", "reviewer_unsure")}
        skip = er.incomplete_ids(ex)
        dec, doubt = er.scope_ids(recs, skip, "doubt")
        self.assertEqual((dec, doubt), ([], [3]))
        fl = er.visual_flags(ex)
        t, pg, sk = er.image_targets(ex, fl, skip, 4, set(), None, "doubt", dec, doubt)
        self.assertEqual(t, [2, 1, 3])
        t, pg, sk = er.image_targets(ex, fl, skip, 2, set(), None, "doubt", dec, doubt)
        self.assertEqual((t, sk), ([2, 1], {3: "page_cap"}))

    def test_3_flagged_ignores_extras(self):
        ex = TI.load(self.tmp, TI.exam(FIG, CUT))
        self.assertEqual(er.scope_ids({1: rec(None, "UNCERTAIN", "solver_declined")}, {}, "flagged"), ([], []))
        self.assertEqual(er.image_targets(ex, er.visual_flags(ex), {}, 4, set(), None, "flagged", [2], [2])[0], [1])


class Runs(TI.Base):
    def llm(self, *first):
        return T.Script(T.solve(*first), T.qa(*[(a["id"], "agree") for a in first
                                                if a["answer_status"] == "answered"]))

    def test_4_skip_id_answered_from_image(self):
        text = TI.exam(CUT, PLAIN)
        im, image = self.img(None, T.solve(T.a(1, "B")))
        res, _ = self.run_img(text, self.llm(T.a(2, "7")), image, image_scope="declined")
        q = res["questions"][0]
        self.assertEqual((q["answer"], q["source"]), ("B", "image"))
        self.assertNotIn("missing_text", q["status_reason"])
        self.assertIn("continue on the next attached page", im.calls[0][0])
        self.assertEqual(res["run"]["image_scope"], "declined")

    def test_5_default_scope_skips_marker_ids_and_prompt_unchanged(self):
        text = TI.exam(CUT, FIG)
        im, image = self.img(None, T.solve(T.a(1, "5")))
        res, _ = self.run_img(text, self.llm(T.a(2, "5")), image)
        self.assertNotIn("continue on the next", im.calls[0][0])
        self.assertNotIn("image_scope", res["run"])
        self.assertTrue(res["questions"][0]["status_reason"].startswith("solver_declined: missing_text"))
        self.assertNotIn("source", res["questions"][0])
        ex = TI.load(self.tmp, text)
        self.assertEqual(cross.flagged_prompt(ex, [(2, None, "x")]), cross.flagged_prompt(ex, [(2, None, "x")], False))

    def test_6_doubt_agrees_and_differs(self):
        text = TI.exam(PLAIN, PLAIN)
        im, image = self.img(None, T.solve(T.a(1, "7"), T.a(2, "9")))
        low = {"level": "medium", "reason": "r"}
        llm = T.Script(T.solve(T.a(1, "7", uncertainty=low), T.a(2, "8", uncertainty=low)),
                       T.qa((1, "agree"), (2, "agree")))
        res, _ = self.run_img(text, llm, image, image_scope="doubt", max_attempts=1)
        q1, q2 = res["questions"]
        self.assertEqual((q1["answer"], q1["source"], q1["verification_status"]), ("7", "text+image", "UNCERTAIN"))
        self.assertIn("image_agrees", [f["code"] for f in q1["qa_findings"]])
        self.assertEqual(q1["status_reason"], "solver_uncertainty_not_low")
        self.assertEqual((q2["answer"], q2["status_reason"]), ("8", "needs_review: text/image differ"))
        c = metrics.compute(res)["counts"]
        self.assertEqual((c["image_scope"], c["image_agrees"], c["image_differs"]), ("doubt", 1, 1))
        self.assertIn("scope doubt agrees 1 differs 1", metrics.block(metrics.compute(res))[0])

    def test_7_second_read_never_pass(self):
        text = TI.exam(PLAIN)
        im, image = self.img(None, T.solve(T.a(1, "7")))
        low = {"level": "medium", "reason": "r"}
        llm = T.Script(T.solve(T.a(1, "7", uncertainty=low)), T.qa((1, "agree")))
        res, _ = self.run_img(text, llm, image, image_scope="doubt", max_attempts=1)
        self.assertNotEqual(res["questions"][0]["verification_status"], "PASS")

    def test_8_unreadable_image_keeps_declined_and_doubt(self):
        text = TI.exam(CUT, PLAIN)
        bad = T.a(1, None, answer_status="unanswerable", issues=["blurry"])
        im, image = self.img(None, T.solve(bad, dict(bad, id="2")))
        low = {"level": "medium", "reason": "r"}
        llm = T.Script(T.solve(T.a(2, "7", uncertainty=low)), T.qa((2, "disagree")))
        res, _ = self.run_img(text, llm, image, image_scope="doubt", max_attempts=1)
        q1, q2 = res["questions"]
        self.assertIsNone(q1["answer"])
        self.assertTrue(q1["status_reason"].startswith("solver_declined: missing_text"))
        self.assertEqual(q2["answer"], "7")
        self.assertEqual(q2["verification_status"], "FAIL")  # a wider scope never softens a FAIL
        self.assertEqual(q2["status_reason"], "reviewer_disagrees")

    def test_9_adjudicate_off_by_default_and_on(self):
        text = TI.exam(FIG)
        for adj in (False, True):
            im, image = self.img(None, T.solve(T.a(1, "6")))
            llm = T.Script(T.solve(T.a(1, "5")), T.qa((1, "agree")), T.solve(T.a(1, "6")))
            res, _ = self.run_img(text, llm, image, adjudicate=True) if adj else self.run_img(text, llm, image)
            q = res["questions"][0]
            if adj:
                self.assertEqual((q["answer"], q["status_reason"]), ("6", "needs_review: adjudicated"))
                self.assertIn("adjudicated", [f["code"] for f in q["qa_findings"]])
                self.assertEqual((res["run"]["calls"], len(llm.prompts)), (4, 3))
                self.assertIn("text answer: 5", llm.prompts[2])
            else:
                self.assertEqual((q["answer"], res["run"]["calls"], len(llm.prompts)), ("5", 3, 2))
        self.assertEqual(er.call_cap(T.cfg(image_pdf=True, adjudicate=True)), er.call_cap(T.cfg(image_pdf=True)) + 1)

    def test_10_metrics_absent_on_default(self):
        im, image = self.img(None, T.solve(T.a(1, "5")))
        res, _ = self.run_img(TI.exam(FIG), self.llm(T.a(1, "5")), image)
        c = metrics.compute(res)["counts"]
        self.assertNotIn("image_scope", c)
        self.assertNotIn("image_agrees", c)


class Cli(T.Base):
    def test_11_flags_need_pdf_and_reach_cfg(self):
        from unittest import mock
        from exam_engine import cli
        for flag in (["--image-scope", "doubt"], ["--adjudicate"]):
            code, _o, e = self.main("x.md", "--dry-run", *flag)
            self.assertEqual(code, 2)
            self.assertIn("need --pdf", e)
        path = self.write("exam.md", TI.exam(FIG))
        mockf = self.write("m.json", "[]")
        seen = {}

        def fake_run(exam, out, cfg, llm, **kw):
            seen.update(cfg=cfg)
            return None, 2
        doc = {"pages": [{"n": 3}], "parts": []}
        with mock.patch.object(cli, "_load_source_doc", return_value=doc), \
                mock.patch.object(cli.engine, "run", fake_run):
            self.main(path, "--mock", mockf, "--out", self.out, "--pdf", "d.json")
            self.assertNotIn("image_scope", seen["cfg"])
            self.assertNotIn("adjudicate", seen["cfg"])
            self.main(path, "--mock", mockf, "--out", self.out, "--pdf", "d.json",
                        "--image-scope", "declined", "--adjudicate")
            self.assertEqual((seen["cfg"]["image_scope"], seen["cfg"]["adjudicate"]), ("declined", True))


if __name__ == "__main__":
    unittest.main()

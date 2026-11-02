"""TASK-059 QA gate: identity, trigger set, cap, key pages, reconciliation edges, render failures (mock LLM)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_image_check as TI  # noqa: E402
import test_exam_run as T  # noqa: E402
from exam_engine import cli, engine as er  # noqa: E402
from exam_engine.adapters import claude as exam_llm  # noqa: E402
from exam_engine.ingest import refine  # noqa: E402

F = TI.FIG


def src(page, body=F):
    return "Source pages: %s\n\n%s" % (page, body)


def msgs(q):
    return [f["message"] for f in q["qa_findings"]]


class Qa(TI.Base):
    def text5(self):
        # q1 plain, q2 flagged p3, q3 flagged p4, q4 plain (has pages), q5 flagged p7
        return TI.exam("Compute 3+4.", src(3), src(4), src(9, "Compute 1+1."), src(7))

    def llm5(self, a2="5", a3="6", a5="8"):
        return T.Script(T.solve(T.a(1, "7"), T.a(2, a2), T.a(3, a3), T.a(4, "2"), T.a(5, a5)),
                        T.qa((1, "agree"), (2, "agree"), (3, "agree"), (4, "agree"), (5, "agree")))

    def test_2a_unflagged_never_get_pages_or_source(self):
        im, image = self.img(None, T.solve(T.a(2, "5"), T.a(3, "6"), T.a(5, "8")))
        res, _ = self.run_img(self.text5(), self.llm5(), image)
        self.assertEqual(im.calls[0][1], [TI.png(3), TI.png(4), TI.png(7)])  # page 9 (unflagged q4) never rendered
        self.assertNotIn("id 1:", im.calls[0][0])
        self.assertNotIn("id 4:", im.calls[0][0])
        for i in (0, 3):
            self.assertNotIn("source", res["questions"][i])
        self.assertEqual([q.get("source") for q in res["questions"][1:3]], ["text+image"] * 2)

    def test_2b_page_cap_end_to_end(self):
        im, image = self.img(None, T.solve(T.a(2, "5"), T.a(3, "6")))
        res, _ = self.run_img(self.text5(), self.llm5(), image, cap=2)
        self.assertEqual(im.calls[0][1], [TI.png(3), TI.png(4)])
        q5 = res["questions"][4]
        self.assertIn("page_cap", msgs(q5))
        self.assertNotIn("source", q5)
        self.assertEqual(q5["answer"], "8")

    def test_2c_key_page_refused_others_still_checked(self):
        im, image = self.img(None, T.solve(T.a(2, "5"), T.a(5, "8")), key_pages={4})
        res, _ = self.run_img(self.text5(), self.llm5(), image)
        self.assertEqual(im.calls[0][1], [TI.png(3), TI.png(7)])
        self.assertNotIn("id 3:", im.calls[0][0])
        q3 = res["questions"][2]
        self.assertIn("answer_key_page", msgs(q3))
        self.assertNotIn("source", q3)

    def test_3_shifted_ids_rejected(self):
        # reply counted by position (1,2,3) instead of our ids (2,3,5): nothing may be applied
        im, image = self.img(None, T.solve(T.a(1, "99"), T.a(2, "99"), T.a(3, "99")))
        res, err = self.run_img(self.text5(), self.llm5(), image)
        q = res["questions"]
        self.assertEqual([q[1]["answer"], q[2]["answer"], q[4]["answer"]], ["5", "6", "8"])
        self.assertEqual(q[4].get("source"), "text")
        self.assertIn("image: not in reply", msgs(q[4]))
        self.assertEqual(q[0]["answer"], "7")
        self.assertNotIn("99", [x["answer"] for x in q])

    def test_3b_match_is_by_id_not_order(self):
        im, image = self.img(None, T.solve(T.a(5, "8"), T.a(3, "66"), T.a(2, "5")))
        res, _ = self.run_img(self.text5(), self.llm5(), image)
        q = res["questions"]
        self.assertEqual((q[1]["source"], q[2]["status_reason"], q[4]["source"]),
                         ("text+image", "needs_review: text/image differ", "text+image"))

    def test_4a_agree_keeps_text_result(self):
        im, image = self.img(None, T.solve(T.a(1, "5")))
        res, _ = self.run_img(TI.exam(src(3), "Compute 3+4."), T.Script(
            T.solve(T.a(1, "5"), T.a(2, "7")), T.qa((1, "agree"), (2, "agree"))), image)
        self.assertEqual((res["questions"][0]["source"], res["questions"][0]["status_reason"]),
                         ("text+image", "no_independent_check"))  # agree: text result untouched

    def test_4b_call_failure_keeps_text(self):
        def bad(prompt, pngs):
            return exam_llm.Call(False, "", 0.0, "timeout", "t", 0.0)
        im, image = self.img(None)
        image["llm"] = bad
        res, _ = self.run_img(TI.exam(src(3), "Compute 3+4."), T.Script(
            T.solve(T.a(1, "5"), T.a(2, "7")), T.qa((1, "agree"), (2, "agree"))), image)
        q = res["questions"][0]
        self.assertEqual(q["answer"], "5")
        self.assertTrue(any(f["code"] == "image_call_failed" for f in q["qa_findings"]))
        self.assertNotIn("source", q)

    def test_4c_declined_stays_declined_when_image_declines(self):
        im, image = self.img(None, T.solve(T.a(1, None, answer_status="unanswerable", issues=["not on page"])))
        llm = T.Script(T.solve(T.a(1, None, answer_status="unanswerable"), T.a(2, "7")), T.qa((2, "agree")))
        res, _ = self.run_img(TI.exam(src(3), "Compute 3+4."), llm, image, max_attempts=1)
        q = res["questions"][0]
        self.assertIsNone(q["answer"])
        self.assertEqual(q["status_reason"], "solver_declined: missing_text (figure/table; image: not on page)")

    def test_4d_call_cap_plus_one_only_with_pdf(self):
        self.assertEqual(er.call_cap(T.cfg(image_pdf=True)) - er.call_cap(T.cfg()), 1)
        self.assertEqual(er.call_cap(T.cfg(image_pdf=None)), er.call_cap(T.cfg()))

    def test_4e_cost_cap_after_image_call_is_respected(self):
        # text rounds cost 0.8 of 1.0; the image call is allowed (0.8 < 1.0) and ends at the cap
        im, image = self.img(None, T.solve(T.a(1, "5")))
        llm = T.Script(T.ok(T.solve(T.a(1, "5"), T.a(2, "7")), 0.4), T.ok(T.qa((1, "agree"), (2, "agree")), 0.4))
        res, _ = self.run_img(TI.exam(src(3), "Compute 3+4."), llm, image, max_attempts=1)
        self.assertEqual(len(im.calls), 1)
        self.assertLessEqual(res["run"]["calls"], er.call_cap(T.cfg(image_pdf=True)))

    def test_7a_render_returns_real_failure_class(self):
        # the real render_page on a missing PDF raises a RuntimeError subclass (fitz); the engine must not crash
        im, image = self.img(None)
        image["render"] = lambda n: refine.render_page("/nonexistent/none.pdf", n)
        res, _ = self.run_img(TI.exam(src(3), "Compute 3+4."), T.Script(
            T.solve(T.a(1, "5"), T.a(2, "7")), T.qa((1, "agree"), (2, "agree"))), image)
        self.assertEqual(im.calls, [])
        q = res["questions"][0]
        self.assertEqual(q["answer"], "5")
        self.assertTrue(any(f["code"] == "image_unavailable" for f in q["qa_findings"]))

    def test_7b_render_refine_error_on_declined_keeps_reason(self):
        def boom(n):
            raise refine.RefineError("call_failed", "page %d: no PNG within the size limit" % n)
        im, image = self.img(None)
        image["render"] = boom
        llm = T.Script(T.solve(T.a(1, None, answer_status="unanswerable"), T.a(2, "7")), T.qa((2, "agree")))
        res, _ = self.run_img(TI.exam(src(3), "Compute 3+4."), llm, image, max_attempts=1)
        q = res["questions"][0]
        self.assertIsNone(q["answer"])
        self.assertTrue(q["status_reason"].startswith("solver_declined: missing_text"))
        self.assertEqual(im.calls, [])

    def test_7c_solve_image_real_render_missing_pdf(self):
        class A(object):
            pdf = "/nonexistent/doc.json"
        with self.assertRaises(Exception):
            cli._solve_image(A(), True, None, None)  # unreadable source doc fails loudly, before any call


if __name__ == "__main__":
    unittest.main()

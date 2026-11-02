"""TASK-059 59.1-59.4: pre-solve WARN, image targets, the one image call, reconciliation. Mock LLM only."""
import contextlib
import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import test_exam_run as T  # noqa: E402
from exam_engine import engine as er  # noqa: E402
from exam_engine.pipeline import cross, parser  # noqa: E402

FIG = "Cho bảng biến thiên như hình dưới đây. Giá trị cực đại?"


def exam(*bodies):
    return T.HEAD % ("Mathematics", "Short Answer") + "## Instructions\n\nSolve.\n\n" + "".join(
        "## Question %d\n\n%s\n\n" % (n, b) for n, b in enumerate(bodies, 1))


def load(tmp, text):
    p = os.path.join(tmp, "e.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return parser.parse_exam(p)


def png(n):
    return b"\x89PNG\r\n\x1a\n" + b"%d" % n


class Imgs(object):
    def __init__(self, *items):
        self.items, self.calls = list(items), []

    def __call__(self, prompt, pngs):
        self.calls.append((prompt, pngs))
        return T.ok(self.items.pop(0))


class Base(T.Base):
    def img(self, text, *reply, **kw):
        im = Imgs(*reply)
        image = {"llm": im, "render": lambda n: png(n),
                 "key_pages": kw.get("key_pages", set()), "have_pages": kw.get("have_pages")}
        return im, image

    def run_img(self, text, llm, image, **kw):
        path = self.write("exam.md", text)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            res, code = er.run(path, self.out, T.cfg(image_pdf=True, max_image_pages=kw.pop("cap", 4), **kw),
                               llm, image=image)
        return res, err.getvalue()


class Flags(Base):
    def test_1_flags_and_warn(self):
        text = exam(FIG, "Compute 3+4.")
        ex = load(self.tmp, text)
        fl = er.visual_flags(ex)
        self.assertEqual(fl[1], ["figure/table"])
        self.assertEqual(fl[2], [])
        llm = T.Script(T.solve(T.a(1, "5"), T.a(2, "7")), T.qa((1, "agree"), (2, "agree")))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            er.run(self.write("x.md", text), self.out, T.cfg(), llm)
        self.assertIn("WARN: question 1 refers to figure/table not in text (pages unknown); "
                      "image check: off (no --pdf)", err.getvalue())
        self.assertNotIn("question 2 refers", err.getvalue())

    def test_1a_warn_printed_before_solve(self):
        text = exam(FIG, "Compute 3+4.")
        seen = []

        class Spy(T.Script):
            def __call__(self, prompt):
                seen.append(sys.stderr.getvalue())
                return T.Script.__call__(self, prompt)

        llm = Spy(T.solve(T.a(1, "5"), T.a(2, "7")), T.qa((1, "agree"), (2, "agree")))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            er.run(self.write("x.md", text), self.out, T.cfg(), llm)
        self.assertIn("WARN: question 1 refers to figure/table", seen[0])

    def test_1b_declined_missing_text_is_flagged(self):
        ex = load(self.tmp, exam("Main idea of paragraph (5)?\n\n(1) aa\n(2) bb"))
        self.assertTrue(er.visual_flags(ex)[1])

    def test_2_targets(self):
        qs = ["Source pages: %s\n\n%s" % (p, FIG) for p in ("1", "2", "3", "4", "5", "6")]
        ex = load(self.tmp, exam(*qs))
        fl = er.visual_flags(ex)
        t, pg, sk = er.image_targets(ex, fl, {}, 4, {5}, None)
        self.assertEqual((t, pg, sk), ([1, 2, 3, 4], [1, 2, 3, 4], {5: "answer_key_page", 6: "page_cap"}))
        self.assertEqual(er.image_targets(ex, fl, {}, 0, set(), None)[2][1], "disabled")
        self.assertEqual(er.image_targets(ex, fl, {}, 4, set(), {1})[2][2], "page_absent")
        self.assertEqual(er.image_targets(ex, fl, {1: "x"}, 4, set(), None)[0][0], 2)
        ex2 = load(self.tmp, exam(FIG))
        self.assertEqual(er.image_targets(ex2, er.visual_flags(ex2), {}, 4, set(), None)[2], {1: "no_pages"})

    def test_3_no_pdf_runs_text_only(self):
        text = exam(FIG, "Compute 3+4.")
        llm = T.Script(T.solve(T.a(1, "5"), T.a(2, "7")), T.qa((1, "agree"), (2, "agree")))
        res, _ = self.go(text, llm)
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(res["run"]["calls"], 2)
        self.assertTrue(all("source" not in q for q in res["questions"]))
        self.assertEqual(er.call_cap(T.cfg()), 5)
        self.assertEqual(er.call_cap(T.cfg(image_pdf=True)), 6)


class BadRender(Base):
    def check(self, render):
        text = exam("Source pages: 3\n\n" + FIG, "Compute 3+4.")
        im, image = self.img(None, T.solve(T.a(1, "9")))
        image["render"] = render
        llm = T.Script(T.solve(T.a(1, "5"), T.a(2, "7")), T.qa((1, "agree"), (2, "agree")))
        res, _ = self.run_img(text, llm, image)
        self.assertEqual(im.calls, [])
        q = res["questions"][0]
        self.assertEqual(q["answer"], "5")
        self.assertTrue([f for f in q["qa_findings"] if f["code"] == "image_unavailable"])

    def test_7_non_png_bytes_not_sent(self):
        self.check(lambda n: b"PNG3")

    def test_7b_oversize_png_not_sent(self):
        self.check(lambda n: png(n) + b"0" * (er.MAX_PNG_BYTES + 1))


class ImageCall(Base):
    def text(self):
        return exam("Source pages: 3\n\n" + FIG, "Compute 3+4.")

    def llm(self, first):
        return T.Script(T.solve(first, T.a(2, "7")), T.qa((1, "agree"), (2, "agree")))

    def test_4_key_page_no_image_call(self):
        im, image = self.img(None, key_pages={3})
        res, err = self.run_img(self.text(), self.llm(T.a(1, "5")), image)
        self.assertEqual(im.calls, [])
        self.assertIn("answer_key_page", [f["message"] for f in res["questions"][0]["qa_findings"]])
        self.assertEqual(res["run"]["calls"], 2)

    def test_5_prompt_by_id_and_prefix(self):
        ex = load(self.tmp, self.text())
        p = cross.flagged_prompt(ex, cross.flagged_items(ex, [1]))
        self.assertIn('id 1: "Cho bảng biến thiên', p)
        self.assertNotIn("reading order", p)
        self.assertNotIn("count continuously", p)

    def test_5b_extra_id_ignored_and_one_call(self):
        im, image = self.img(None, T.solve(T.a(1, "5"), T.a(99, "Z")))
        res, err = self.run_img(self.text(), self.llm(T.a(1, "5")), image)
        self.assertEqual(len(im.calls), 1)
        self.assertEqual(im.calls[0][1], [png(3)])
        self.assertIn("ignored: 99", err)
        q = res["questions"][0]
        self.assertEqual(q["source"], "text+image")
        self.assertNotIn("source", res["questions"][1])
        self.assertEqual(res["run"]["calls"], 3)

    def test_6_differ_needs_review(self):
        im, image = self.img(None, T.solve(T.a(1, "6")))
        res, _ = self.run_img(self.text(), self.llm(T.a(1, "5")), image)
        q = res["questions"][0]
        self.assertEqual((q["verification_status"], q["status_reason"], q["answer"], q["source"]),
                         ("UNCERTAIN", "needs_review: text/image differ", "5", "text+image"))

    def test_6b_declined_text_takes_image_answer(self):
        im, image = self.img(None, T.solve(T.a(1, "6")))
        llm = T.Script(T.solve(T.a(1, None, answer_status="unanswerable"), T.a(2, "7")), T.qa((2, "agree")))
        res, _ = self.run_img(self.text(), llm, image, max_attempts=1)
        q = res["questions"][0]
        self.assertEqual((q["answer"], q["source"], q["verification_status"], q["status_reason"]),
                         ("6", "image", "UNCERTAIN", "no_review"))
        self.assertEqual(q["attempts"], 2)

    def test_6c_unreadable_image_keeps_text_answer(self):
        im, image = self.img(None, T.solve(T.a(1, None, answer_status="unanswerable", issues=["blurry"])))
        res, _ = self.run_img(self.text(), self.llm(T.a(1, "5")), image)
        q = res["questions"][0]
        self.assertEqual((q["answer"], q["source"], q["verification_status"]), ("5", "text", "UNCERTAIN"))
        self.assertTrue(q["status_reason"].startswith("needs_review: image unreadable"))

    def test_6d_declined_stays_declined(self):
        im, image = self.img(None, T.solve())  # id missing from the reply
        llm = T.Script(T.solve(T.a(1, None, answer_status="unanswerable"), T.a(2, "7")), T.qa((2, "agree")))
        res, _ = self.run_img(self.text(), llm, image, max_attempts=1)
        q = res["questions"][0]
        self.assertIsNone(q["answer"])
        self.assertEqual(q["status_reason"], "solver_declined: missing_text (figure/table; image: not in reply)")

    def test_7_cost_cap_before_image_call(self):
        im, image = self.img(None)
        llm = T.Script(T.ok(T.solve(T.a(1, "5"), T.a(2, "7")), 0.6), T.ok(T.qa((1, "agree"), (2, "agree")), 0.6))
        res, _ = self.run_img(self.text(), llm, image, max_attempts=1)
        self.assertEqual(im.calls, [])
        self.assertEqual(res["run"]["stopped"], "cost_cap")

    def test_7b_malformed_reply_keeps_text(self):
        im, image = self.img(None, "not json")
        res, _ = self.run_img(self.text(), self.llm(T.a(1, "5")), image)
        q = res["questions"][0]
        self.assertEqual(q["answer"], "5")
        self.assertEqual(q["verification_status"], "UNCERTAIN")
        self.assertEqual(q["status_reason"], "no_independent_check")  # untouched by the failed image call

    def test_7c_render_failure_no_call(self):
        im, image = self.img(None)
        image["render"] = lambda n: (_ for _ in ()).throw(OSError("boom"))
        res, _ = self.run_img(self.text(), self.llm(T.a(1, "5")), image)
        self.assertEqual(im.calls, [])
        self.assertEqual(res["questions"][0]["answer"], "5")


if __name__ == "__main__":
    unittest.main()

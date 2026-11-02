"""TASK-059 59.5-59.6: result source, plan-run image call, report/metrics, CLI wiring. Mock LLM only."""
import hashlib
import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import test_image_check as TI  # noqa: E402
import test_exam_run as T  # noqa: E402
from exam_engine import cli, engine as er  # noqa: E402
from exam_engine.core import schema as sch  # noqa: E402
from exam_engine.pipeline import metrics, planrun, reporter  # noqa: E402

TEXT = TI.exam("Source pages: 3\n\n" + TI.FIG, "Compute 3+4.")


class Run(TI.Base):
    def run_with_plan(self, image_reply):
        im, image = self.img(None, image_reply)
        llm = T.Script(T.solve(T.a(1, "5"), T.a(2, "7")), T.qa((1, "agree"), (2, "agree")))
        path = self.write("exam.md", TEXT)
        pw = planrun.PlanWriter(self.out, path, T.cfg(image_pdf="x.pdf", max_image_pages=4))
        pw.start()
        with mock.patch("sys.stderr"):
            res, _ = er.run(path, self.out, T.cfg(image_pdf="x.pdf", max_image_pages=4), llm,
                            sink=pw.record, image=image)
        return res, im

    def test_schema_old_and_new(self):
        res, _ = self.run_with_plan(T.solve(T.a(1, "5")))
        self.assertEqual(res["questions"][0]["source"], "text+image")
        self.assertEqual(sch.validate(res, sch.RESULT), [])
        old = json.loads(json.dumps(res))
        del old["questions"][0]["source"]
        self.assertEqual(sch.validate(old, sch.RESULT), [])
        old["questions"][0]["source"] = "ocr"
        self.assertNotEqual(sch.validate(old, sch.RESULT), [])

    def test_plan_run_keeps_image_call(self):
        self.run_with_plan(T.solve(T.a(1, "5")))
        with open(os.path.join(self.out, "calls", "index.jsonl")) as fh:
            lines = [json.loads(x) for x in fh]
        img = [x for x in lines if x["tag"] == "image"]
        self.assertEqual(len(img), 1)
        self.assertEqual(img[0]["pages"], [3])
        self.assertEqual(img[0]["page_sha256"], [hashlib.sha256(TI.png(3)).hexdigest()])
        self.assertTrue(all("pages" not in x for x in lines if x["tag"] != "image"))
        self.assertTrue(os.path.isfile(os.path.join(self.out, "calls", "%03d-prompt.txt" % img[0]["n"])))
        self.assertFalse([f for f in os.listdir(os.path.join(self.out, "calls")) if f.endswith(".png")])

    def test_report_and_metrics(self):
        res, _ = self.run_with_plan(T.solve(T.a(1, "6")))
        md = reporter.build_markdown(res)
        self.assertEqual(md.count("- Source: text+image"), 1)
        c = metrics.compute(res)["counts"]
        self.assertEqual((c["image_checked"], c["image_changed"]), (1, 1))
        self.assertIn("image 1 checked 1 changed", metrics.block(metrics.compute(res))[0])

    def test_old_run_unchanged(self):
        res, _ = self.go(TEXT, T.Script(T.solve(T.a(1, "5"), T.a(2, "7")), T.qa((1, "agree"), (2, "agree")))), None
        res = res[0]
        self.assertNotIn("Source:", reporter.build_markdown(res))
        m = metrics.compute(res)
        self.assertNotIn("image_checked", m["counts"])
        self.assertNotIn("image", metrics.block(m)[0])


class Cli(T.Base):
    def test_max_pages_needs_pdf(self):
        code, _o, e = self.main("x.md", "--dry-run", "--max-image-pages", "2")
        self.assertEqual(code, 2)
        self.assertIn("needs --pdf", e)

    def test_wiring_and_no_pdf_default(self):
        path = self.write("exam.md", TEXT)
        mockf = self.write("m.json", "[]")
        seen = {}

        def fake_run(exam, out, cfg, llm, **kw):
            seen.update(cfg=cfg, kw=kw)
            return None, 2
        doc = {"pages": [{"n": 3}], "parts": [{"kind": "answer_key", "pages": [9, 10]}]}
        with mock.patch.object(cli, "_load_source_doc", return_value=doc), \
                mock.patch.object(cli.engine, "run", fake_run):
            self.main(path, "--mock", mockf, "--out", self.out, "--pdf", "d.json", "--max-image-pages", "2")
            self.assertEqual((seen["cfg"]["image_pdf"], seen["cfg"]["max_image_pages"]), ("d.json", 2))
            img = seen["kw"]["image"]
            self.assertEqual((img["key_pages"], img["have_pages"], img["render"](3)),
                             ({9, 10}, {3}, cli._STUB_PNG))
            seen.clear()
            self.main(path, "--mock", mockf, "--out", self.out)
            self.assertNotIn("image_pdf", seen["cfg"])
            self.assertNotIn("image", seen["kw"])

    def cli_run(self, render=None):
        path = self.write("exam.md", TEXT)
        mockf = self.write("m.json", json.dumps([
            T.solve(T.a(1, "5"), T.a(2, "7")), T.qa((1, "agree"), (2, "agree")), T.solve(T.a(1, "6"))]))
        doc = {"pages": [{"n": 3}], "parts": []}
        real_img = cli._solve_image
        def img(*a, **k):  # noqa: E306
            im = real_img(*a, **k)
            if render:
                im["render"] = render
            return im
        with mock.patch.object(cli, "_load_source_doc", return_value=doc), \
                mock.patch.object(cli, "_solve_image", img):
            code, _o, _e = self.main(path, "--mock", mockf, "--out", self.out, "--pdf", "d.pdf")
        self.assertIn(code, (0, 1), _o + _e)
        with open(os.path.join(self.out, "calls", "index.jsonl")) as fh:
            lines = [json.loads(x) for x in fh]
        with open(os.path.join(self.out, "result.json")) as fh:
            return code, lines, json.load(fh)

    def test_cli_mock_pdf_makes_one_image_call(self):
        _code, lines, res = self.cli_run()
        img = [x for x in lines if x["tag"] == "image"]
        self.assertEqual(len(img), 1)
        self.assertEqual(img[0]["page_sha256"], [hashlib.sha256(cli._STUB_PNG).hexdigest()])
        self.assertEqual(res["questions"][0]["source"], "text+image")
        self.assertEqual(metrics.compute(res)["counts"]["image_checked"], 1)

    def test_cli_non_png_render_is_image_unavailable(self):
        _code, lines, res = self.cli_run(render=lambda n: b"\x89PNG")
        self.assertFalse([x for x in lines if x["tag"] == "image"])
        self.assertIn("image_unavailable", [f["code"] for f in res["questions"][0]["qa_findings"]])

    def test_dry_run_prints_image_prompt_no_render(self):
        path = self.write("exam.md", TEXT)
        doc = {"pages": [{"n": 3}], "parts": []}
        with mock.patch.object(cli, "_load_source_doc", return_value=doc):
            code, out, _e = self.main(path, "--dry-run", "--pdf", "d.json")
        self.assertEqual(code, 0)
        self.assertIn("image check: 1 questions, pages [3]", out)
        self.assertIn("=== IMAGE prompt", out)


if __name__ == "__main__":
    unittest.main()

"""Tests 1-3, 5-10 of docs/design/phase-5-report.md (REQ-0011). No browser: fake renderer/runner
(Popen stand-ins), a fake PATH for the no-renderer case. Real subprocess.Popen is never reached."""
import contextlib
import copy
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TOOLS = os.path.join(ROOT, "tools", "examples")  # the old-command shims
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import reporter as rp  # noqa: E402
from exam_engine import cli, engine as er  # noqa: E402
from exam_engine.core import schema as sch  # noqa: E402

INPUT_001 = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(HERE, "fixtures", "mock_english_001.json")
VI = "Giải phương trình bậc hai: đáp án x = 3,46 (Việt Nam, ắ ằ ẳ)"


def chk(kind, result, independent=False, detail="d"):
    return {"kind": kind, "result": result, "independent": independent, "detail": detail}


def question(i, verdict="PASS", answer="42", checks=None, **kw):
    q = {"id": str(i), "answer": answer, "verification_status": verdict, "status_reason": "ok",
         "score": {"points": 1, "max": 1, "basis": "computed"}, "checks": checks or [],
         "solution": ["step one"], "explanation": "because",
         "uncertainty": {"level": "low", "reason": "r"}}
    q.update(kw)
    return q


def result(questions=None, summary=None, **exam):
    qs = questions if questions is not None else [question(1)]
    e = {"subject": "Math", "level": "G12", "exam_type": "Test", "task": "Short Answer",
         "mode": "Solve", "path": "x.md", "language": "en"}
    e.update(exam)
    return {"exam": e,
            "run": {"llm": "mock", "model": "sonnet", "calls": 2, "cost_usd": 0.0},
            "summary": summary or {"pass": 1, "fail": 0, "uncertain": 0, "unresolved": 0,
                                   "points": 1, "max_points": 1},
            "questions": qs}


class FakeProc(object):
    """Popen stand-in. mode: 'pdf' writes %PDF and exits; 'junk' writes non-pdf and exits;
    'hang' never exits until terminate()/kill()."""

    def __init__(self, argv, mode):
        self.argv, self.mode = argv, mode
        self.terminated = self.killed = False
        self.rc = None
        out = [a.split("=", 1)[1] for a in argv if a.startswith("--print-to-pdf=")]
        out = out[0] if out else argv[-1]
        if mode == "pdf":
            with open(out, "wb") as fh:
                fh.write(b"%PDF-1.4\nfake\n")
            self.rc = 0
        elif mode == "junk":
            with open(out, "wb") as fh:
                fh.write(b"<html>not a pdf")
            self.rc = 0
        elif mode == "dead":
            self.rc = 1

    def poll(self):
        return self.rc

    def terminate(self):
        self.terminated = True
        self.rc = -15

    def kill(self):
        self.killed = True
        self.rc = -9

    def wait(self, timeout=None):
        return self.rc


class Runner(object):
    def __init__(self, mode):
        self.mode, self.procs, self.argvs = mode, [], []

    def __call__(self, argv, **kw):
        self.argvs.append(argv)
        p = FakeProc(argv, self.mode)
        self.procs.append(p)
        return p


CHROME = ("chrome", "/fake/chrome")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="exam_report_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        p = mock.patch("subprocess.Popen", side_effect=AssertionError("real subprocess reached"))
        p.start()
        self.addCleanup(p.stop)
        self.out = os.path.join(self.tmp, "out")

    def read(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8") as fh:
            return fh.read()

    def files(self):
        return sorted(f for f in os.listdir(self.out) if f != "run.log")


class EvidenceKind(unittest.TestCase):
    def test_1_computed_independent_pass_is_code_oracle(self):
        q = question(1, checks=[chk("computed", "pass", True), chk("ai_review", "pass")])
        self.assertEqual(rp.evidence_kind(q), "code oracle")

    def test_1_key_match_pass(self):
        self.assertEqual(rp.evidence_kind(question(1, checks=[chk("key_match", "pass")])), "key match")

    def test_1_computed_beats_key_match(self):
        q = question(1, checks=[chk("key_match", "pass"), chk("computed", "pass", True)])
        self.assertEqual(rp.evidence_kind(q), "code oracle")

    def test_1_only_quote_format_review_passes_is_claude_review_only(self):
        for kinds in (["quote"], ["format"], ["ai_review"], ["quote", "format", "ai_review"]):
            q = question(1, checks=[chk(k, "pass") for k in kinds])
            self.assertEqual(rp.evidence_kind(q), "Claude review only", kinds)

    def test_1_no_pass_is_none(self):
        self.assertEqual(rp.evidence_kind(question(1, checks=[])), "none")
        self.assertEqual(rp.evidence_kind({"id": "1"}), "none")
        self.assertEqual(rp.evidence_kind(question(1, checks=[chk("computed", "fail", True),
                                                              chk("key_match", "fail")])), "none")
        self.assertEqual(rp.evidence_kind(question(1, checks=[chk("ai_review", "fail")])), "none")

    def test_1_computed_pass_not_independent_is_not_code_oracle(self):
        q = question(1, checks=[chk("computed", "pass", False)])
        self.assertEqual(rp.evidence_kind(q), "Claude review only")

    def test_1_values_in_KINDS(self):
        self.assertEqual(set(rp.KINDS), {"code oracle", "key match", "Claude review only", "none"})


class Markdown(Base):
    def test_2_contains_answer_verdict_evidence_checks_totals(self):
        r = result([question(1, answer="3.46", checks=[chk("computed", "pass", True, "2*sqrt(3)=3.46")])])
        md = rp.build_markdown(r)
        for s in ("Question 1", "3.46", "**PASS**", "code oracle", "| computed | pass | yes |",
                  "2*sqrt(3)=3.46", "Totals: PASS 1, FAIL 0, UNCERTAIN 0, unresolved 0",
                  "Points: 1 / 1", "step one", "because"):
            self.assertIn(s, md)

    def test_2_stored_evidence_kind_is_used(self):
        q = question(1, checks=[], evidence_kind="key match")
        self.assertIn("Evidence: key match", rp.build_markdown(result([q])))

    def test_2_script_never_becomes_live_markup(self):
        evil = "<script>alert(1)</script>"
        q = question(1, answer=evil, explanation=evil, solution=[evil],
                     checks=[chk("quote", "pass", False, evil)], status_reason=evil)
        r = result([q], subject=evil)
        md = rp.build_markdown(r)
        for html_ in (self.render(md, r),):
            self.assertNotIn("<script", html_.split("</style>", 1)[1])
            self.assertIn("&lt;script&gt;", html_)

    def render(self, md, r):
        from exam_engine.utils import md2html
        return md2html.convert(md, False, "t", "en")

    def test_2_javascript_link_in_model_text_is_not_a_link(self):
        q = question(1, explanation="[go](javascript:alert(1)) and [ok](https://e.com)")
        h = self.render(rp.build_markdown(result([q])), None)
        self.assertNotIn("javascript:alert", h.split("</style>", 1)[1].replace("[go](javascript:alert(1))", ""))
        self.assertNotIn('href="javascript', h)
        self.assertIn('<a href="https://e.com">', h)

    def test_2_pipe_and_newline_do_not_break_table_row(self):
        detail = "a | b\nc | d\r\ne"
        q = question(1, checks=[chk("quote|x", "pass", False, detail)])
        md = rp.build_markdown(result([q]))
        rows = [l for l in md.split("\n") if l.startswith("| ") and "---" not in l]
        self.assertEqual(len(rows), 2)  # header + the one check row
        h = self.render(md, None)
        self.assertEqual(h.count("<td>"), 4)
        self.assertEqual(h.count("<th>"), 4)
        self.assertIn("a | b c | d e", h)

    def test_2_newline_in_answer_and_id_stays_one_bullet(self):
        q = question(1, answer="line1\n## Injected heading\nline3")
        md = rp.build_markdown(result([q]))
        self.assertNotIn("\n## Injected", md)

    def test_2_model_fence_and_fake_pill_do_not_break_report(self):
        q = question(1, explanation="```python\nx", solution=["# step", "**PASS**"])
        md = rp.build_markdown(result([q]))
        self.assertNotIn("\n```", md)
        self.assertNotIn("**PASS**", md.split("### Solution")[1])
        self.assertIn("### Uncertainty", md)  # nothing swallowed after the fence

    def test_2_vietnamese_passes_unchanged(self):
        q = question(1, answer=VI, explanation=VI, solution=[VI],
                     checks=[chk("quote", "pass", False, VI)])
        r = result([q], subject="Toán", language="vi")
        md = rp.build_markdown(r)
        self.assertIn(VI, md)
        self.assertIn("Toán", md)
        info = rp.write_reports(r, self.out, pdf=True, renderer=CHROME, runner=Runner("junk"))
        self.assertIsNotNone(info["html"])
        self.assertFalse(os.path.exists(os.path.join(self.out, "report.pdf")))  # D1
        self.assertIn(VI, self.read("report.md"))
        h = self.read("report.html")
        self.assertIn(VI, h)
        self.assertIn('<html lang="vi">', h)

    def test_2_totals_come_from_summary_not_questions(self):
        qs = [question(1, "PASS"), question(2, "PASS"), question(3, "PASS")]
        r = result(qs, summary={"pass": 7, "fail": 5, "uncertain": 3, "unresolved": 2,
                                "points": 4.5, "max_points": 9})
        md = rp.build_markdown(r)
        self.assertIn("Totals: PASS 7, FAIL 5, UNCERTAIN 3, unresolved 2", md)
        self.assertIn("Points: 4.5 / 9", md)

    def test_2_summary_without_points_has_no_points_line(self):
        r = result(summary={"pass": 1, "fail": 0, "uncertain": 0, "unresolved": 0})
        self.assertNotIn("Points:", rp.build_markdown(r))

    def test_3_literature_open_item_shows_open_and_uncertain(self):
        q = question(1, "UNCERTAIN", answer="Open", checks=[chk("quote", "pass")],
                     score={"points": None, "max": None, "basis": "none"})
        md = rp.build_markdown(result([q], summary={"pass": 0, "fail": 0, "uncertain": 1,
                                                    "unresolved": 0}, task="Essay", subject="Literature"))
        self.assertIn("Open", md)
        self.assertIn("**UNCERTAIN**", md)
        self.assertIn("human rubric", md)

    def test_3_literature_task_marks_open_even_with_text_answer(self):
        q = question(1, "UNCERTAIN", answer="some essay")
        md = rp.build_markdown(result([q], task="Literature"))
        self.assertIn("Open (needs a human rubric)", md)

    def test_2_error_and_qa_findings_rendered(self):
        q = question(1, "FAIL", error={"cls": "Bad", "message": "boom"},
                     qa_findings=[{"source": "qa", "code": "C1", "message": "wrong"}])
        md = rp.build_markdown(result([q]))
        self.assertIn("Error: Bad: boom", md)
        self.assertIn("qa / C1: wrong", md)


class Renderer(unittest.TestCase):
    def test_5_order_chrome_bin_first(self):
        have = {"/x/mychrome": "/x/mychrome", "google-chrome": "/g", "weasyprint": "/w"}
        got = rp.find_pdf_renderer({"CHROME_BIN": "/x/mychrome"}, which=have.get)
        self.assertEqual(got, ("chrome", "/x/mychrome"))

    def test_5_chrome_bin_unusable_falls_through(self):
        have = {"chromium": "/c"}
        got = rp.find_pdf_renderer({"CHROME_BIN": "/nope"}, which=have.get)
        self.assertEqual(got, ("chrome", "/c"))

    def test_5_name_order(self):
        names = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "weasyprint", "wkhtmltopdf"]
        for i, n in enumerate(names):
            have = dict((x, "/p/" + x) for x in names[i:])
            kind = "chrome" if i < 4 else n
            self.assertEqual(rp.find_pdf_renderer({}, which=have.get), (kind, "/p/" + n), n)

    def test_5_none_when_nothing(self):
        self.assertIsNone(rp.find_pdf_renderer({}, which=lambda n: None))

    def test_5_real_which_with_empty_path_is_none(self):
        d = tempfile.mkdtemp(prefix="exam_report_path_")
        self.addCleanup(shutil.rmtree, d, True)
        with mock.patch.dict(os.environ, {"PATH": d}, clear=False):
            os.environ.pop("CHROME_BIN", None)
            self.assertIsNone(rp.find_pdf_renderer())


class Pdf(Base):
    def run_reports(self, mode, r=None, env=None, **kw):
        runner = Runner(mode)
        with mock.patch.dict(os.environ, env or {}):
            info = rp.write_reports(r or result(), self.out, pdf=True, renderer=kw.pop("renderer", CHROME),
                                    runner=runner)
        return info, runner

    def profile_dirs(self, runner):
        out = []
        for argv in runner.argvs:
            out += [a.split("=", 1)[1] for a in argv if a.startswith("--user-data-dir=")]
        return out

    def test_6_no_renderer_keeps_html_flags_report(self):
        d = tempfile.mkdtemp(prefix="exam_report_path_")
        self.addCleanup(shutil.rmtree, d, True)
        with mock.patch.dict(os.environ, {"PATH": d}):
            os.environ.pop("CHROME_BIN", None)
            info = rp.write_reports(result(), self.out, pdf=True)
        self.assertTrue(info["pdf_status"].startswith("skipped"))
        self.assertIsNone(info["pdf"])
        self.assertEqual(info["html"], os.path.join(self.out, "report.html"))
        self.assertEqual(self.files(), ["report.html", "report.md"])
        self.assertIn("PDF skipped: no PDF renderer found", self.read("report.md"))

    def test_7_fake_renderer_ok_pdf_written_html_removed(self):
        info, runner = self.run_reports("pdf")
        self.assertTrue(info["pdf_status"].startswith("ok"))
        self.assertEqual(info["pdf"], os.path.join(self.out, "report.pdf"))
        self.assertIsNone(info["html"])
        self.assertEqual(self.files(), ["report.md", "report.pdf"])
        self.assertNotIn("PDF skipped", self.read("report.md"))
        with open(info["pdf"], "rb") as fh:
            self.assertEqual(fh.read(4), b"%PDF")

    def test_7_chrome_argv_is_a_list_with_flags_and_temp_profile_removed(self):
        info, runner = self.run_reports("pdf")
        argv = runner.argvs[0]
        self.assertIsInstance(argv, list)
        self.assertEqual(argv[0], "/fake/chrome")
        for f in ("--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--disable-extensions"):
            self.assertIn(f, argv)
        self.assertTrue(argv[-1].startswith("file://"))
        profs = self.profile_dirs(runner)
        self.assertEqual(len(profs), 1)
        self.assertFalse(os.path.exists(profs[0]))

    def test_7_other_renderers_argv(self):
        for kind in ("weasyprint", "wkhtmltopdf"):
            info, runner = self.run_reports("pdf", renderer=(kind, "/fake/" + kind))
            self.assertTrue(info["pdf_status"].startswith("ok"), kind)
            self.assertEqual(runner.argvs[0][0], "/fake/" + kind)
            self.assertEqual(runner.argvs[0][-1], os.path.abspath(os.path.join(self.out, "report.pdf")))
            shutil.rmtree(self.out)

    def test_8_hang_is_terminated_at_timeout_and_html_kept(self):
        t0 = time.monotonic()
        info, runner = self.run_reports("hang", env={"PDF_RENDER_TIMEOUT": "1"})
        self.assertLess(time.monotonic() - t0, 10)
        self.assertTrue(runner.procs[0].terminated or runner.procs[0].killed)
        self.assertIsNotNone(runner.procs[0].poll())
        self.assertTrue(info["pdf_status"].startswith("skipped"))
        self.assertIn("timed out", info["pdf_status"])
        self.assertIsNone(info["pdf"])
        self.assertEqual(self.files(), ["report.html", "report.md"])
        self.assertIn("PDF skipped: ", self.read("report.md"))
        for p in self.profile_dirs(runner):
            self.assertFalse(os.path.exists(p))

    def test_8_md_to_pdf_returns_false_reason_without_raising(self):
        md = os.path.join(self.tmp, "r.md")
        with open(md, "w", encoding="utf-8") as fh:
            fh.write("# T\n")
        runner = Runner("hang")
        with mock.patch.dict(os.environ, {"PDF_RENDER_TIMEOUT": "2"}):
            ok, note = rp.md_to_pdf(md, os.path.join(self.tmp, "r.pdf"), renderer=CHROME, runner=runner)
        self.assertIs(ok, False)
        self.assertIn("timed out after 2s", note)
        self.assertTrue(runner.procs[0].terminated)

    def test_8_bad_timeout_env_falls_back_without_raising(self):
        md = os.path.join(self.tmp, "r.md")
        with open(md, "w", encoding="utf-8") as fh:
            fh.write("# T\n")
        with mock.patch.dict(os.environ, {"PDF_RENDER_TIMEOUT": "abc"}):
            ok, _ = rp.md_to_pdf(md, os.path.join(self.tmp, "r.pdf"), renderer=CHROME,
                                 runner=Runner("pdf"))
        self.assertTrue(ok)

    def test_8_non_pdf_output_is_failure_and_keeps_html(self):
        info, runner = self.run_reports("junk")
        self.assertTrue(info["pdf_status"].startswith("skipped"))
        self.assertIsNone(info["pdf"])
        self.assertIn("no valid PDF", info["pdf_status"])
        self.assertIn("PDF skipped", self.read("report.md"))
        self.assertTrue(os.path.exists(os.path.join(self.out, "report.html")))
        for p in self.profile_dirs(runner):
            self.assertFalse(os.path.exists(p))

    def test_8_renderer_exits_without_output_is_failure(self):
        info, _ = self.run_reports("dead")
        self.assertTrue(info["pdf_status"].startswith("skipped"))
        self.assertTrue(os.path.exists(os.path.join(self.out, "report.html")))

    def test_8_runner_that_raises_does_not_propagate(self):
        def boom(argv, **kw):
            raise OSError("no exec")
        info = rp.write_reports(result(), self.out, pdf=True, renderer=CHROME, runner=boom)
        self.assertTrue(info["pdf_status"].startswith("skipped"))
        self.assertIn("OSError", info["pdf_status"])
        self.assertTrue(os.path.exists(os.path.join(self.out, "report.html")))

    def test_8_stale_pdf_is_not_mistaken_for_success(self):
        os.makedirs(self.out)
        with open(os.path.join(self.out, "report.pdf"), "wb") as fh:
            fh.write(b"%PDF-old")
        info, _ = self.run_reports("dead")
        self.assertIsNone(info["pdf"])
        self.assertFalse(os.path.exists(os.path.join(self.out, "report.pdf")))

    def test_pdf_false_writes_only_md(self):
        info = rp.write_reports(result(), self.out, pdf=False, runner=Runner("pdf"))
        self.assertEqual(self.files(), ["report.md"])
        self.assertEqual(info["pdf_status"], "not requested")


class RunIntegration(Base):
    def go(self, **kw):
        c = {"max_attempts": 2, "max_cost_usd": 1.0, "timeout": 5, "model": "sonnet", "key": None,
             "llm_name": "mock"}
        c.update(kw)
        sys.path.insert(0, HERE)
        import test_exam_run as t
        llm = t.Script(t.solve(t.a(1, "3.46", expr="2*sqrt(3)")), t.qa((1, "agree")))
        path = os.path.join(self.tmp, "exam.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(t.MATH1)
        with contextlib.redirect_stderr(io.StringIO()):
            return er.run(path, self.out, c, llm)

    def test_9_run_writes_report_md_and_valid_result_with_evidence_kind(self):
        res, _ = self.go()
        self.assertEqual(self.files(), ["report.md", "result.json"])
        with open(os.path.join(self.out, "result.json"), encoding="utf-8") as fh:
            disk = json.load(fh)
        self.assertEqual(sch.validate(disk, sch.RESULT), [])
        self.assertEqual(disk["questions"][0]["evidence_kind"], "code oracle")
        self.assertNotIn("reports", disk)
        self.assertIn("code oracle", self.read("report.md"))
        self.assertEqual(res["reports"]["pdf_status"], "not requested")

    def test_9_run_totals_in_report_equal_summary(self):
        res, _ = self.go()
        s = res["summary"]
        self.assertIn("Totals: PASS %d, FAIL %d, UNCERTAIN %d, unresolved %d" % (
            s["pass"], s["fail"], s["uncertain"], s["unresolved"]), self.read("report.md"))

    def test_9_run_with_pdf_true_uses_renderer_lookup_not_real_popen(self):
        # no renderer on PATH -> html kept, still no exception, Popen never reached
        d = tempfile.mkdtemp(prefix="exam_report_path_")
        self.addCleanup(shutil.rmtree, d, True)
        with mock.patch.dict(os.environ, {"PATH": d}):
            os.environ.pop("CHROME_BIN", None)
            res, _ = self.go(pdf=True)
        self.assertTrue(res["reports"]["pdf_status"].startswith("skipped"))
        self.assertEqual(self.files(), ["report.html", "report.md", "result.json"])

    def test_schema_rejects_bad_evidence_kind(self):
        res, _ = self.go()
        bad = copy.deepcopy(res)
        bad.pop("reports", None)
        bad["questions"][0]["evidence_kind"] = "magic"
        self.assertNotEqual(sch.validate(bad, sch.RESULT), [])


class Cli(Base):
    def main(self, *argv):
        o, e = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            code = cli.solve_main(list(argv))
        return code, o.getvalue(), e.getvalue()

    def test_10_mock_no_pdf_end_to_end(self):
        code, out, _ = self.main(INPUT_001, "--mock", MOCK, "--no-pdf", "--out", self.out)
        self.assertEqual(code, 1)
        self.assertEqual(self.files(), ["report.md", "result.json"])
        with open(os.path.join(self.out, "result.json"), encoding="utf-8") as fh:
            res = json.load(fh)
        self.assertEqual(sch.validate(res, sch.RESULT), [])
        for q in res["questions"]:
            self.assertIn(q["evidence_kind"], rp.KINDS)
        md = self.read("report.md")
        s = res["summary"]
        self.assertIn("Totals: PASS %d, FAIL %d, UNCERTAIN %d, unresolved %d" % (
            s["pass"], s["fail"], s["uncertain"], s["unresolved"]), md)
        self.assertIn("report.md", out)


if __name__ == "__main__":
    unittest.main()
